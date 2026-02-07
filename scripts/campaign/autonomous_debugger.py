"""Autonomous debugger for Oracle of Secrets.

Monitors live gameplay via the Mesen2 socket API, detects soft locks
and anomalies, auto-captures save states, and generates crash reports.

Modes:
    --monitor      Watch alongside manual play (default 5 min, 4 Hz)
    --campaign     Run CampaignOrchestrator with monitoring injected
    --investigate  Load a save state and dump forensics

Dependencies (all existing):
    - MesenBridge         (scripts/mesen2_client_lib/bridge.py)
    - Mesen2Emulator      (scripts/campaign/emulator_abstraction.py)
    - GameStateSnapshot   (scripts/campaign/emulator_abstraction.py)
    - GameStateParser     (scripts/campaign/game_state.py)
    - CampaignOrchestrator(scripts/campaign/campaign_orchestrator.py)

Usage:
    python3 -m scripts.campaign.autonomous_debugger --monitor
    python3 -m scripts.campaign.autonomous_debugger --campaign
    python3 -m scripts.campaign.autonomous_debugger --investigate state.mss
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

_DEFAULT_ARTIFACT_ROOT = Path(tempfile.gettempdir()) / "oos_autodebug"
DEFAULT_REPORT_DIR = _DEFAULT_ARTIFACT_ROOT / "reports"
DEFAULT_STATE_DIR = _DEFAULT_ARTIFACT_ROOT / "states"

# Allow running as either:
# - `python3 -m scripts.campaign.autonomous_debugger ...` (recommended), or
# - `python3 scripts/campaign/autonomous_debugger.py ...`
if __name__ == "__main__" and __package__ is None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    __package__ = "scripts.campaign"

from .emulator_abstraction import GameStateSnapshot, Mesen2Emulator
from .game_state import GameStateParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Anomaly:
    """A detected gameplay anomaly."""
    type: str          # "stagnation", "black_screen", "mode_stuck"
    severity: str      # "warning", "error", "critical"
    description: str
    frame_count: int   # how many samples the condition persisted
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyReport:
    """Full report for a detected anomaly with forensics."""
    anomaly: Anomaly
    state: Dict[str, Any]
    forensics: Dict[str, Any]
    save_state_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Soft lock detection
# ---------------------------------------------------------------------------

class SoftLockDetector:
    """Detects gameplay anomalies by tracking state over time.

    Ported from sentinel detection patterns. Checks:
    - Position stagnation: Link hasn't moved while game is playable
    - Black screen: INIDISP=0x80 during mode 0x06/0x07
    - Mode stuck: GameMode unchanged for extended period
    """

    def __init__(
        self,
        stagnation_threshold: int = 120,
        black_screen_threshold: int = 30,
        mode_stuck_threshold: int = 300,
    ):
        self.history: deque[GameStateSnapshot] = deque(maxlen=600)
        self.stagnation_threshold = stagnation_threshold
        self.black_screen_threshold = black_screen_threshold
        self.mode_stuck_threshold = mode_stuck_threshold

    def update(self, state: GameStateSnapshot) -> Optional[Anomaly]:
        """Feed a state sample. Returns Anomaly if detected, else None."""
        self.history.append(state)

        if len(self.history) < 2:
            return None

        if anomaly := self._check_black_screen():
            return anomaly
        if anomaly := self._check_position_stagnation():
            return anomaly
        if anomaly := self._check_mode_stuck():
            return anomaly
        return None

    def _check_position_stagnation(self) -> Optional[Anomaly]:
        """Link's (X,Y) unchanged for N samples while Link is in a movement state."""
        if len(self.history) < self.stagnation_threshold:
            return None

        recent = list(self.history)[-self.stagnation_threshold:]

        # Only flag if game is in playable state the entire window
        if not all(s.is_playing for s in recent):
            return None

        # Reduce false positives during normal idle (standing still).
        # Require Link to be in a movement-like state for the full window.
        moving_states = {0x01, 0x02, 0x03}  # walking/swimming/diving
        if not all(s.link_state in moving_states for s in recent):
            return None

        ref_pos = recent[0].position
        if all(s.position == ref_pos for s in recent):
            return Anomaly(
                type="stagnation",
                severity="warning",
                description=(
                    f"Link position unchanged at ({ref_pos[0]}, {ref_pos[1]}) "
                    f"for {self.stagnation_threshold} samples while moving "
                    f"(link_state=0x{recent[-1].link_state:02X})"
                ),
                frame_count=self.stagnation_threshold,
                timestamp=time.time(),
                context={
                    "position": ref_pos,
                    "mode": recent[-1].mode,
                    "link_state": recent[-1].link_state,
                },
            )
        return None

    def _check_black_screen(self) -> Optional[Anomaly]:
        """INIDISP == 0x80 and mode in (0x06, 0x07) for N consecutive samples."""
        if len(self.history) < self.black_screen_threshold:
            return None

        recent = list(self.history)[-self.black_screen_threshold:]

        if all(s.is_black_screen for s in recent):
            return Anomaly(
                type="black_screen",
                severity="critical",
                description=(
                    f"Black screen (INIDISP=0x80, mode=0x{recent[-1].mode:02X}) "
                    f"persisted for {self.black_screen_threshold} samples"
                ),
                frame_count=self.black_screen_threshold,
                timestamp=time.time(),
                context={
                    "inidisp": recent[-1].inidisp,
                    "mode": recent[-1].mode,
                    "submode": recent[-1].submode,
                },
            )
        return None

    def _check_mode_stuck(self) -> Optional[Anomaly]:
        """GameMode byte unchanged for N samples (catches hung transitions)."""
        if len(self.history) < self.mode_stuck_threshold:
            return None

        recent = list(self.history)[-self.mode_stuck_threshold:]
        ref_mode = recent[0].mode

        # Mode 0x07 (dungeon) and 0x09 (overworld) are normal to be stuck in
        # during regular gameplay — only flag non-playable modes
        if ref_mode in (0x07, 0x09):
            return None

        if all(s.mode == ref_mode for s in recent):
            return Anomaly(
                type="mode_stuck",
                severity="error",
                description=(
                    f"GameMode stuck at 0x{ref_mode:02X} "
                    f"for {self.mode_stuck_threshold} samples"
                ),
                frame_count=self.mode_stuck_threshold,
                timestamp=time.time(),
                context={"mode": ref_mode, "submode": recent[-1].submode},
            )
        return None

    def reset(self) -> None:
        """Clear detection history."""
        self.history.clear()


# ---------------------------------------------------------------------------
# Debug session
# ---------------------------------------------------------------------------

class DebugSession:
    """Autonomous debugging session with anomaly detection.

    Connects to Mesen2, polls game state at configurable frequency,
    runs anomaly detection, and generates reports on findings.
    """

    def __init__(
        self,
        report_dir: str = str(DEFAULT_REPORT_DIR),
        state_dir: str = str(DEFAULT_STATE_DIR),
        socket_path: Optional[str] = None,
        trace_count: int = 0,
    ):
        self.emu = Mesen2Emulator(socket_path=socket_path)
        self.parser = GameStateParser()
        self.detector = SoftLockDetector()
        report_path = Path(report_dir).expanduser()
        if not report_path.is_absolute():
            report_path = REPO_ROOT / report_path
        self.report_dir = report_path
        state_path = Path(state_dir).expanduser()
        if not state_path.is_absolute():
            state_path = REPO_ROOT / state_path
        self.state_dir = state_path
        self.trace_count = max(0, int(trace_count))
        self._oracle_client = None
        self.anomalies: List[AnomalyReport] = []
        self.last_good_state_path: Optional[str] = None
        self.total_samples = 0
        self._running = False

    def connect(self) -> bool:
        """Connect to Mesen2 and verify responsiveness."""
        try:
            if self.emu.connect():
                state = self.emu.read_state()
                logger.info(
                    "Connected to Mesen2 — mode=0x%02X, area=0x%02X",
                    state.mode, state.area,
                )
                # Optional: richer forensics via the higher-level debug client.
                try:
                    from scripts.mesen2_client_lib.client import OracleDebugClient

                    socket_path = None
                    try:
                        socket_path = self.emu._get_bridge().socket_path
                    except Exception:
                        socket_path = None
                    self._oracle_client = OracleDebugClient(socket_path=socket_path)
                except Exception:
                    self._oracle_client = None
                return True
        except Exception as e:
            logger.error("Connection failed: %s", e)
        return False

    def monitor(self, duration_seconds: int = 300, poll_hz: int = 4) -> None:
        """Poll game state and check for anomalies.

        This is the main loop for --monitor mode.
        Runs for duration_seconds or until Ctrl+C / SIGINT.
        """
        interval = 1.0 / poll_hz
        start = time.time()
        self._running = True

        logger.info(
            "Monitoring for %ds at %d Hz (%d max samples)...",
            duration_seconds, poll_hz, duration_seconds * poll_hz,
        )

        while self._running and (time.time() - start) < duration_seconds:
            try:
                state = self.emu.read_state()
                self.total_samples += 1

                anomaly = self.detector.update(state)
                if anomaly:
                    self._on_anomaly(anomaly, state)

                # Periodic "good state" checkpoint (every 30 seconds)
                if self.total_samples % (poll_hz * 30) == 0:
                    self._checkpoint_good_state()

                # Status heartbeat (every 60 seconds)
                if self.total_samples % (poll_hz * 60) == 0:
                    elapsed = time.time() - start
                    logger.info(
                        "Heartbeat: %d samples, %d anomalies, %.0fs elapsed",
                        self.total_samples, len(self.anomalies), elapsed,
                    )

            except ConnectionError:
                logger.warning("Lost connection to Mesen2, attempting reconnect...")
                if not self._reconnect():
                    logger.error("Reconnect failed, stopping monitor")
                    break
            except Exception as e:
                logger.error("Poll error: %s", e)

            time.sleep(interval)

        logger.info(
            "Monitor complete: %d samples, %d anomalies detected",
            self.total_samples, len(self.anomalies),
        )

    def monitor_campaign(self, max_iterations: int = 10) -> None:
        """Run CampaignOrchestrator with monitoring integrated.

        Wraps each campaign iteration with anomaly detection polling.
        On anomaly, captures state and marks the iteration as failed.
        """
        from .campaign_orchestrator import CampaignOrchestrator

        orchestrator = CampaignOrchestrator(emulator=self.emu)
        if not orchestrator.connect():
            logger.error("Campaign orchestrator failed to connect")
            return

        self._running = True
        logger.info("Starting monitored campaign (max %d iterations)", max_iterations)

        for i in range(max_iterations):
            if not self._running:
                break

            logger.info("=== Campaign iteration %d/%d ===", i + 1, max_iterations)

            # Pre-iteration state check
            state = self.emu.read_state()
            anomaly = self.detector.update(state)
            if anomaly:
                self._on_anomaly(anomaly, state)
                logger.warning("Anomaly before iteration %d, attempting recovery", i + 1)
                if not self._attempt_recovery():
                    logger.error("Recovery failed, stopping campaign")
                    break

            # Run one exploration iteration
            success = orchestrator.run_exploration_iteration()

            # Post-iteration state check
            state = self.emu.read_state()
            anomaly = self.detector.update(state)
            if anomaly:
                self._on_anomaly(anomaly, state)

            if not success:
                logger.warning("Iteration %d failed", i + 1)

            self._checkpoint_good_state()

        logger.info(
            "Campaign complete: %d anomalies detected",
            len(self.anomalies),
        )
        print(orchestrator.get_status_report())

    def investigate_state(self, state_path: str) -> None:
        """Load a save state and dump forensics.

        Useful for post-mortem analysis of captured anomaly states.
        """
        logger.info("Investigating state: %s", state_path)

        path = Path(state_path).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        path = path.resolve()
        if not path.exists():
            logger.error("State file not found: %s", state_path)
            return

        if not self.emu.load_state(str(path)):
            logger.error("Failed to load state: %s", state_path)
            return

        # Brief delay for emulator to process the state load
        time.sleep(0.25)

        state = self.emu.read_state()
        parsed = self.parser.parse(state)
        forensics = self._gather_forensics()

        report = {
            "state_path": str(path),
            "timestamp": datetime.now().isoformat(),
            "game_state": {
                "mode": f"0x{state.mode:02X}",
                "submode": f"0x{state.submode:02X}",
                "area": f"0x{state.area:02X}",
                "room": f"0x{state.room:02X}",
                "link_position": state.position,
                "health": f"{state.health}/{state.max_health}",
                "inidisp": f"0x{state.inidisp:02X}",
                "is_black_screen": state.is_black_screen,
                "is_playing": state.is_playing,
            },
            "parsed": {
                "phase": parsed.phase.name,
                "location": parsed.location_name,
                "link_action": parsed.link_action.name,
                "can_move": parsed.can_move,
                "is_safe": parsed.is_safe,
            },
            "forensics": forensics,
        }

        # Print to console
        print(json.dumps(report, indent=2))

        # Save to file
        self.report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"investigation_{timestamp}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info("Investigation report saved to %s", report_path)

    def generate_summary(self) -> None:
        """Generate and print session summary."""
        summary = {
            "session_end": datetime.now().isoformat(),
            "total_samples": self.total_samples,
            "anomalies_detected": len(self.anomalies),
            "anomaly_types": {},
        }

        for report in self.anomalies:
            atype = report.anomaly.type
            summary["anomaly_types"][atype] = summary["anomaly_types"].get(atype, 0) + 1

        if self.anomalies:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # JSON summary
            json_path = self.report_dir / f"session_{timestamp}.json"
            with open(json_path, "w") as f:
                json.dump(summary, f, indent=2)

            # Markdown summary
            md_path = self.report_dir / f"session_{timestamp}.md"
            with open(md_path, "w") as f:
                f.write(self._format_markdown_report(summary))

            logger.info("Session reports saved to %s", self.report_dir)

        # Console output
        print(f"\n{'=' * 50}")
        print("AUTONOMOUS DEBUGGER SESSION SUMMARY")
        print(f"{'=' * 50}")
        print(f"Total samples:      {self.total_samples}")
        print(f"Anomalies detected: {len(self.anomalies)}")
        for atype, count in summary.get("anomaly_types", {}).items():
            print(f"  {atype}: {count}")
        if not self.anomalies:
            print("  No anomalies detected")
        print(f"{'=' * 50}")

    def stop(self) -> None:
        """Signal the monitor loop to stop."""
        self._running = False

    # -- Internal helpers --

    def _on_anomaly(self, anomaly: Anomaly, state: GameStateSnapshot) -> None:
        """Handle detected anomaly: save state + gather forensics + report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.warning(
            "ANOMALY [%s/%s]: %s",
            anomaly.type, anomaly.severity, anomaly.description,
        )

        # Auto-capture save state
        save_path = None
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            save_name = str((self.state_dir / f"anomaly_{anomaly.type}_{timestamp}.mss").resolve())
            save_path = self.emu.save_state(save_name)
            if save_path:
                logger.info("Save state captured: %s", save_path)
            else:
                logger.warning("Failed to capture save state")
        except Exception as e:
            logger.warning("Save state capture error: %s", e)

        # Gather forensics
        forensics = self._gather_forensics()
        if self.trace_count > 0 and self._oracle_client is not None:
            try:
                ok, frames = self._oracle_client.trace(count=self.trace_count)
                trace_path = None
                if ok:
                    self.report_dir.mkdir(parents=True, exist_ok=True)
                    trace_path = str((self.report_dir / f"trace_{anomaly.type}_{timestamp}.json").resolve())
                    with open(trace_path, "w") as f:
                        json.dump(frames, f, indent=2)
                forensics["trace"] = {
                    "ok": ok,
                    "count": len(frames),
                    "path": trace_path,
                }
            except Exception as e:
                forensics["trace"] = {"ok": False, "error": str(e)}

        # Build report
        state_dict = {
            "mode": f"0x{state.mode:02X}",
            "submode": f"0x{state.submode:02X}",
            "area": f"0x{state.area:02X}",
            "room": f"0x{state.room:02X}",
            "link_position": state.position,
            "health": f"{state.health}/{state.max_health}",
            "inidisp": f"0x{state.inidisp:02X}",
            "is_black_screen": state.is_black_screen,
        }

        report = AnomalyReport(
            anomaly=anomaly,
            state=state_dict,
            forensics=forensics,
            save_state_path=save_path,
        )
        self.anomalies.append(report)

        # Persist individual report
        self.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.report_dir / f"anomaly_{anomaly.type}_{timestamp}.json"
        with open(report_path, "w") as f:
            json.dump(self._report_to_dict(report), f, indent=2)
        logger.info("Anomaly report saved to %s", report_path)

    def _gather_forensics(self) -> Dict[str, Any]:
        """Collect diagnostic data from Mesen2."""
        forensics: Dict[str, Any] = {}
        bridge = self.emu._get_bridge()

        commands = {
            "cpu": "CPU",
            "rom_info": "ROMINFO",
        }

        for key, cmd in commands.items():
            try:
                result = bridge.send_command(cmd, timeout=2.0)
                if result.get("success"):
                    forensics[key] = result.get("data", {})
                else:
                    forensics[key] = {"error": result.get("error", "unknown")}
            except Exception as e:
                forensics[key] = {"error": str(e)}

        # Read key Oracle RAM addresses for context
        oracle_addrs = {
            "GameMode": 0x7E0010,
            "SubMode": 0x7E0011,
            "INIDISPQ": 0x7E0013,
            "Frame": 0x7E001A,
            "LinkState": 0x7E005D,
            "OOSPROG": 0x7EF3D6,
            "GameState": 0x7EF3C5,
            "Crystals": 0x7EF37A,
        }
        ram_snapshot = {}
        for name, addr in oracle_addrs.items():
            try:
                val = bridge.read_memory(addr)
                ram_snapshot[name] = f"0x{val:02X}"
            except Exception:
                ram_snapshot[name] = "read_error"
        forensics["oracle_ram"] = ram_snapshot

        return forensics

    def _checkpoint_good_state(self) -> None:
        """Save a checkpoint of the current (presumed good) state."""
        try:
            state = self.emu.read_state()
            if state.is_playing and not state.is_black_screen:
                self.state_dir.mkdir(parents=True, exist_ok=True)
                path = str((self.state_dir / "last_good.mss").resolve())
                save_path = self.emu.save_state(path)
                if save_path:
                    self.last_good_state_path = save_path
        except Exception:
            pass  # Checkpointing is best-effort

    def _attempt_recovery(self) -> bool:
        """Attempt to recover from an anomaly by reloading last good state."""
        if not self.last_good_state_path:
            logger.warning("No good state checkpoint available for recovery")
            return False

        logger.info("Attempting recovery from %s", self.last_good_state_path)
        if self.emu.load_state(self.last_good_state_path):
            time.sleep(0.5)  # Let emulator settle
            state = self.emu.read_state()
            if state.is_playing and not state.is_black_screen:
                logger.info("Recovery successful")
                self.detector.reset()
                return True

        logger.error("Recovery failed")
        return False

    def _reconnect(self, retries: int = 3, delay: float = 1.0) -> bool:
        """Attempt to reconnect to Mesen2."""
        for i in range(retries):
            logger.info("Reconnect attempt %d/%d...", i + 1, retries)
            time.sleep(delay)
            try:
                if self.emu.connect():
                    logger.info("Reconnected")
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def _report_to_dict(report: AnomalyReport) -> Dict[str, Any]:
        """Serialize an AnomalyReport to a JSON-safe dict."""
        return {
            "anomaly": {
                "type": report.anomaly.type,
                "severity": report.anomaly.severity,
                "description": report.anomaly.description,
                "frame_count": report.anomaly.frame_count,
                "timestamp": report.anomaly.timestamp,
                "context": report.anomaly.context,
            },
            "state": report.state,
            "forensics": report.forensics,
            "save_state_path": report.save_state_path,
        }

    @staticmethod
    def _format_markdown_report(summary: Dict[str, Any]) -> str:
        """Format session summary as markdown."""
        lines = [
            "# Autonomous Debugger Session Report",
            "",
            f"**Date:** {summary.get('session_end', 'unknown')}",
            f"**Total Samples:** {summary.get('total_samples', 0)}",
            f"**Anomalies Detected:** {summary.get('anomalies_detected', 0)}",
            "",
        ]

        anomaly_types = summary.get("anomaly_types", {})
        if anomaly_types:
            lines.append("## Anomaly Breakdown")
            lines.append("")
            lines.append("| Type | Count |")
            lines.append("|------|-------|")
            for atype, count in anomaly_types.items():
                lines.append(f"| {atype} | {count} |")
            lines.append("")
        else:
            lines.append("No anomalies detected during this session.")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Oracle of Secrets Autonomous Debugger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s --monitor                         Watch gameplay for 5 min at 4 Hz
  %(prog)s --monitor --duration 3600         Watch for 1 hour
  %(prog)s --campaign                        Run campaign with monitoring
  %(prog)s --investigate state.mss           Analyze a save state
""",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--monitor", action="store_true", help="Watch mode (alongside manual play)")
    mode.add_argument("--campaign", action="store_true", help="Run campaign orchestrator with monitoring")
    mode.add_argument("--investigate", type=str, metavar="STATE", help="Analyze a save state file")

    parser.add_argument("--duration", type=int, default=300, help="Monitor duration in seconds (default: 300)")
    parser.add_argument("--poll-hz", type=int, default=4, help="Polling frequency in Hz (default: 4)")
    parser.add_argument("--report-dir", type=str, default=str(DEFAULT_REPORT_DIR), help="Report output directory")
    parser.add_argument("--state-dir", type=str, default=str(DEFAULT_STATE_DIR), help="Save state output directory")
    parser.add_argument("--socket", type=str, default=None, help="Mesen2 socket path (auto-discovers if omitted)")
    parser.add_argument("--max-iterations", type=int, default=10, help="Max campaign iterations (default: 10)")
    parser.add_argument("--trace-count", type=int, default=0, help="Capture TRACE entries on anomaly (default: 0)")
    parser.add_argument(
        "--fail-on-anomaly",
        action="store_true",
        help="Exit non-zero if any anomalies are detected (useful for CI)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Logging setup
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    session = DebugSession(
        report_dir=args.report_dir,
        state_dir=args.state_dir,
        socket_path=args.socket,
        trace_count=args.trace_count,
    )

    # Handle Ctrl+C gracefully
    def _sigint_handler(signum, frame):
        logger.info("Interrupt received, stopping...")
        session.stop()

    signal.signal(signal.SIGINT, _sigint_handler)

    # Connect
    if not session.connect():
        print("ERROR: Cannot connect to Mesen2. Is it running?")
        sys.exit(1)

    # Dispatch mode
    if args.monitor:
        session.monitor(duration_seconds=args.duration, poll_hz=args.poll_hz)
    elif args.campaign:
        session.monitor_campaign(max_iterations=args.max_iterations)
    elif args.investigate:
        session.investigate_state(args.investigate)

    session.generate_summary()
    if args.fail_on_anomaly and session.anomalies:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
