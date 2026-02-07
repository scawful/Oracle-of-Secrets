"""Agentic autonomous debugging runner for Oracle of Secrets.

This is a pragmatic "autodebug" layer that:
- Knows where Link is (area/room names + coordinates).
- Detects invalid states (forced blank / hung transitions / unexpected pauses).
- Captures a forensics bundle immediately on anomaly (savestate + CPU + stack +
  P-log + trace + mem-blame).
- Can run in manual-monitor mode or as a callback injected into campaign
  autopilot (frame-by-frame).

Design constraints:
- Keep per-frame overhead low in campaign mode (no heavy socket calls every
  frame; only on anomaly).
- Prefer repo-local "latest capture" markers so humans/agents don't paste paths.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

_DEFAULT_ARTIFACT_ROOT = Path(tempfile.gettempdir()) / "oos_autodebug" / "agentic"
DEFAULT_CAPTURE_DIR = _DEFAULT_ARTIFACT_ROOT / "captures"

# Repo-local (gitignored) markers/reports so we don't have to copy/paste paths.
_CACHE_DIR = REPO_ROOT / ".cache" / "oos_agentic_autodebug"
LAST_CAPTURE_MARKER = _CACHE_DIR / "last_capture.json"
LATEST_REPORT_MD = _CACHE_DIR / "latest_report.md"

logger = logging.getLogger(__name__)


class AutodebugAbort(RuntimeError):
    """Raised to abort autopilot when an anomaly is captured."""


@dataclass(frozen=True)
class AutodebugAnomaly:
    kind: str
    severity: str
    description: str
    timestamp: float
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForensicsBundle:
    root: Path
    anomaly: AutodebugAnomaly
    state_path: Optional[Path] = None
    files: dict[str, str] = field(default_factory=dict)


def _room_id16(raw_state: Any) -> int:
    try:
        v = (raw_state.raw_data or {}).get("room_id")
        if isinstance(v, int):
            return int(v) & 0xFFFF
    except Exception:
        pass
    try:
        return int(raw_state.room) & 0xFFFF
    except Exception:
        return 0


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve_socket_from_instance(instance: str) -> Optional[str]:
    """Resolve socket path from the local mesen2 registry record (best-effort)."""
    if not instance:
        return None
    record = REPO_ROOT / ".context" / "scratchpad" / "mesen2" / "instances" / f"{instance}.json"
    if not record.exists():
        return None
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except Exception:
        return None
    sp = data.get("socket")
    if isinstance(sp, str) and sp:
        return sp
    return None


class DetectorSuite:
    """Lightweight per-tick anomaly detection.

    In campaign mode this is called every frame, so it must be cheap.
    """

    def __init__(
        self,
        *,
        forced_blank_frames: int = 120,
        mode06_frames: int = 360,
        pause_frames: int = 30,
        frame_stall_ticks: int = 30,
    ) -> None:
        self.forced_blank_frames = int(forced_blank_frames)
        self.mode06_frames = int(mode06_frames)
        self.pause_frames = int(pause_frames)
        self.frame_stall_ticks = int(frame_stall_ticks)
        self._forced_blank_run = 0
        self._mode06_run = 0
        self._paused_run = 0
        self._stall_run = 0
        self._last_frame: int | None = None

    def update(
        self,
        *,
        raw_state: Any,
        parsed_state: Any | None = None,
        run_state: dict[str, Any] | None = None,
    ) -> Optional[AutodebugAnomaly]:
        mode = int(getattr(raw_state, "mode", 0) or 0)
        submode = int(getattr(raw_state, "submode", 0) or 0)
        inidisp = int(getattr(raw_state, "inidisp", 0) or 0)
        forced_blank = (inidisp & 0x80) != 0
        paused = bool((run_state or {}).get("paused")) if run_state is not None else False
        frame = int(((getattr(raw_state, "raw_data", {}) or {}).get("frame")) or 0)

        # Forced blank streak
        if forced_blank and mode in (0x06, 0x07):
            self._forced_blank_run += 1
        else:
            self._forced_blank_run = 0

        # Mode 0x06 streak (transition/load hang)
        if mode == 0x06:
            self._mode06_run += 1
        else:
            self._mode06_run = 0

        # Paused unexpectedly streak (often p-assert / breakpoint / crash)
        if paused:
            self._paused_run += 1
        else:
            self._paused_run = 0

        # Frame stall streak (main loop not progressing while emulator is running).
        # FRAME ($7E001A) is 8-bit and wraps. We only care about "no change at all".
        if self._last_frame is None:
            self._last_frame = frame
            self._stall_run = 0
        else:
            if not paused and frame == self._last_frame and mode != 0x00:
                self._stall_run += 1
            else:
                self._stall_run = 0
                self._last_frame = frame

        room_id = _room_id16(raw_state)
        area = int(getattr(raw_state, "area", 0) or 0)
        x = int(getattr(raw_state, "link_x", 0) or 0)
        y = int(getattr(raw_state, "link_y", 0) or 0)

        if self._paused_run >= self.pause_frames:
            return AutodebugAnomaly(
                kind="paused",
                severity="critical",
                description=f"Emulator paused for {self._paused_run} ticks (p-assert/breakpoint/crash?)",
                timestamp=time.time(),
                context={
                    "mode": mode,
                    "submode": submode,
                    "inidisp": inidisp,
                    "frame": frame,
                    "area": area,
                    "room_id": room_id,
                    "pos": [x, y],
                },
            )

        if self._stall_run >= self.frame_stall_ticks:
            return AutodebugAnomaly(
                kind="frame_stall",
                severity="critical",
                description=f"Frame counter did not advance for {self._stall_run} ticks (hung main loop?)",
                timestamp=time.time(),
                context={
                    "mode": mode,
                    "submode": submode,
                    "inidisp": inidisp,
                    "frame": frame,
                    "area": area,
                    "room_id": room_id,
                    "pos": [x, y],
                },
            )

        if self._mode06_run >= self.mode06_frames:
            return AutodebugAnomaly(
                kind="transition_stuck",
                severity="critical",
                description=f"Mode 0x06 persisted for {self._mode06_run} ticks (hung transition/load)",
                timestamp=time.time(),
                context={
                    "mode": mode,
                    "submode": submode,
                    "inidisp": inidisp,
                    "frame": frame,
                    "area": area,
                    "room_id": room_id,
                    "pos": [x, y],
                },
            )

        # A forced blank during mode 0x06 can be normal, so require a longer window.
        if self._forced_blank_run >= self.forced_blank_frames:
            return AutodebugAnomaly(
                kind="forced_blank",
                severity="critical",
                description=f"Forced blank (INIDISP bit7) persisted for {self._forced_blank_run} ticks",
                timestamp=time.time(),
                context={
                    "mode": mode,
                    "submode": submode,
                    "inidisp": inidisp,
                    "frame": frame,
                    "area": area,
                    "room_id": room_id,
                    "pos": [x, y],
                },
            )

        return None


class AgenticAutodebugSession:
    def __init__(
        self,
        *,
        socket_path: Optional[str] = None,
        instance: Optional[str] = None,
        capture_dir: Path = DEFAULT_CAPTURE_DIR,
        arm_p_watch_depth: int = 8000,
        arm_mem_watch_depth: int = 4000,
        arm_assert_jtl: bool = True,
        trace_count: int = 200,
        p_log_count: int = 200,
        stack_count: int = 12,
    ) -> None:
        self.socket_path = socket_path or (_resolve_socket_from_instance(instance or "") if instance else None)
        self.capture_dir = capture_dir
        self.arm_p_watch_depth = int(arm_p_watch_depth)
        self.arm_mem_watch_depth = int(arm_mem_watch_depth)
        self.arm_assert_jtl = bool(arm_assert_jtl)
        self.trace_count = int(trace_count)
        self.p_log_count = int(p_log_count)
        self.stack_count = int(stack_count)

        from .emulator_abstraction import Mesen2Emulator
        from .game_state import GameStateParser

        self.emu = Mesen2Emulator(socket_path=self.socket_path)
        self.parser = GameStateParser()
        self.detectors = DetectorSuite()

        self.client = None
        self._captured = False

    def connect(self) -> None:
        if not self.emu.connect():
            raise RuntimeError("Cannot connect to Mesen2 (socket missing or not running)")
        # Use the actual resolved socket so both interfaces talk to the same instance.
        bridge_socket = None
        try:
            bridge_socket = self.emu._get_bridge().socket_path
        except Exception:
            bridge_socket = self.socket_path

        from scripts.mesen2_client_lib.client import OracleDebugClient

        self.client = OracleDebugClient(socket_path=bridge_socket)

    def arm_instrumentation(self) -> dict[str, Any]:
        if self.client is None:
            raise RuntimeError("Not connected")

        out: dict[str, Any] = {}
        out["p_watch_start"] = self.client.p_watch_start(depth=self.arm_p_watch_depth)
        out["trace_start"] = self.client.trace_control("start", clear=True)

        if self.arm_assert_jtl:
            # JumpTableLocal requires X/Y=8-bit on entry (P bit 0x10 set).
            out["p_assert_jtl"] = self.client.p_assert(0x008781, 0x10, mask=0x10)

        # Memory watches used by MEM_BLAME (write attribution).
        watch_addrs: list[tuple[int, int, str]] = [
            (0x7E0013, 1, "INIDISPQ"),
            (0x7E001A, 1, "FRAME"),
            (0x7E0010, 1, "GameMode"),
            (0x7E0011, 1, "SubMode"),
            (0x7E00A0, 1, "RoomLayout"),
            (0x7E00A4, 2, "RoomID16"),
            (0x7EC005, 2, "RMFADE"),
            (0x7EC007, 2, "FADETIME"),
            (0x7EC00B, 2, "FADETGT"),
            (0x7E009A, 1, "ColorMath9A"),
            (0x7E009C, 1, "ColorMath9C"),
            (0x7E009D, 1, "ColorMath9D"),
        ]
        watches: list[dict[str, Any]] = []
        for addr, size, name in watch_addrs:
            res = self.client.mem_watch_add(addr, size=size, depth=self.arm_mem_watch_depth)
            watches.append({"addr": f"0x{addr:06X}", "size": size, "name": name, "res": res})
        out["mem_watch_add"] = watches
        return out

    def monitor_manual(self, *, duration_s: int = 300, poll_hz: int = 4, arm: bool = True) -> int:
        if self.client is None:
            raise RuntimeError("Not connected")

        if arm:
            # For manual play, arm by default so MEM_BLAME/TRACE/P-log are meaningful on capture.
            self.arm_instrumentation()

        duration_s = int(duration_s)
        poll_hz = max(1, int(poll_hz))
        interval = 1.0 / float(poll_hz)
        start = time.time()

        while (time.time() - start) < duration_s:
            raw = self.emu.read_state()
            parsed = self.parser.parse(raw)
            run_state = self.client.get_run_state()

            anomaly = self.detectors.update(raw_state=raw, parsed_state=parsed, run_state=run_state)
            if anomaly:
                self.capture(anomaly, raw, parsed, run_state=run_state)
                self._freeze()
                return 2

            time.sleep(interval)

        return 0

    def campaign_autopilot(self, *, max_iterations: int = 50, arm: bool = True) -> int:
        """Run CampaignOrchestrator with per-frame anomaly detection injected."""
        if self.client is None:
            raise RuntimeError("Not connected")

        if arm:
            # Arm once before running the campaign so any anomaly capture has attribution.
            self.arm_instrumentation()

        from .campaign_orchestrator import CampaignOrchestrator

        tick_counter = 0
        last_run_state: dict[str, Any] | None = None

        def tick(parsed_state: Any) -> None:
            nonlocal tick_counter, last_run_state
            tick_counter += 1
            # Keep per-frame overhead low: do not query run_state here.
            raw = parsed_state.raw
            run_state = None
            # Sample run-state occasionally so we still detect "paused" anomalies (p-assert/breakpoint)
            # without paying for a socket roundtrip every frame.
            if tick_counter % 30 == 0:
                try:
                    last_run_state = self.client.get_run_state()
                except Exception:
                    last_run_state = {}
            run_state = last_run_state

            anomaly = self.detectors.update(raw_state=raw, parsed_state=parsed_state, run_state=run_state)
            if anomaly and not self._captured:
                # On autopilot, capture immediately and abort the campaign loop.
                self.capture(anomaly, raw, parsed_state, run_state=run_state)
                self._freeze()
                raise AutodebugAbort(anomaly.description)

        orchestrator = CampaignOrchestrator(emulator=self.emu, tick_callback=tick)
        if not orchestrator.connect():
            raise RuntimeError("CampaignOrchestrator could not connect")

        try:
            orchestrator.run_campaign(max_iterations=int(max_iterations))
        except AutodebugAbort:
            return 2
        return 0

    def _freeze(self) -> None:
        # Recovery policy: freeze and wait (don't reset/reload).
        try:
            self.emu.pause()
        except Exception:
            pass

    def capture(
        self,
        anomaly: AutodebugAnomaly,
        raw_state: Any,
        parsed_state: Any,
        *,
        run_state: dict[str, Any] | None,
    ) -> ForensicsBundle:
        if self.client is None:
            raise RuntimeError("Not connected")
        if self._captured:
            # Don't spam multiple bundles in a single freeze scenario.
            return ForensicsBundle(root=Path("."), anomaly=anomaly)
        self._captured = True

        tag = _now_tag()
        room_id = _room_id16(raw_state)
        cap_root = (self.capture_dir / f"{tag}_{anomaly.kind}_room_{room_id:04X}").resolve()
        cap_root.mkdir(parents=True, exist_ok=True)

        bundle = ForensicsBundle(root=cap_root, anomaly=anomaly)

        # World/context summary (with both parser + canonical location description).
        try:
            from .locations import get_location_description

            location_desc = get_location_description(
                area_id=int(getattr(raw_state, "area", 0) or 0),
                room_id=room_id,
                is_indoors=bool(getattr(raw_state, "indoors", False)),
            )
        except Exception:
            location_desc = parsed_state.location_name if parsed_state is not None else "unknown"

        world = {
            "timestamp": tag,
            "anomaly": {
                "kind": anomaly.kind,
                "severity": anomaly.severity,
                "description": anomaly.description,
                "context": anomaly.context,
            },
            "location": {
                "parser_location": getattr(parsed_state, "location_name", "unknown"),
                "canonical_location": location_desc,
                "area_id": int(getattr(raw_state, "area", 0) or 0),
                "room_layout": int(getattr(raw_state, "room", 0) or 0),
                "room_id": room_id,
                "indoors": bool(getattr(raw_state, "indoors", False)),
                "pos": [int(getattr(raw_state, "link_x", 0) or 0), int(getattr(raw_state, "link_y", 0) or 0)],
            },
            "raw": {
                "mode": int(getattr(raw_state, "mode", 0) or 0),
                "submode": int(getattr(raw_state, "submode", 0) or 0),
                "inidispq": int(getattr(raw_state, "inidisp", 0) or 0),
                "frame": int((getattr(raw_state, "raw_data", {}) or {}).get("frame") or 0),
            },
            "run_state": run_state or {},
        }
        _write_json(cap_root / "world.json", world)
        bundle.files["world"] = str((cap_root / "world.json").resolve())

        # Save state file (path-based, not slot-based).
        state_path = cap_root / "anomaly.mss"
        ok_state = False
        try:
            ok_state = bool(self.client.save_state(path=str(state_path)))
        except Exception:
            ok_state = False
        if ok_state and state_path.exists():
            bundle.state_path = state_path
            bundle.files["savestate"] = str(state_path)

        # CPU
        try:
            cpu = self.client.get_cpu_state()
            _write_json(cap_root / "cpu.json", cpu)
            bundle.files["cpu"] = str((cap_root / "cpu.json").resolve())
        except Exception as exc:
            _write_json(cap_root / "cpu.json", {"error": str(exc)})

        # Stack return addresses (decoded)
        try:
            stack = self.client.stack_retaddr(count=self.stack_count, mode="rtl")
            _write_json(cap_root / "stack.json", stack)
            bundle.files["stack"] = str((cap_root / "stack.json").resolve())
        except Exception as exc:
            _write_json(cap_root / "stack.json", {"error": str(exc)})

        # P log
        try:
            plog = self.client.p_log(count=self.p_log_count)
            _write_json(cap_root / "p_log.json", plog)
            bundle.files["p_log"] = str((cap_root / "p_log.json").resolve())
        except Exception as exc:
            _write_json(cap_root / "p_log.json", {"error": str(exc)})

        # Trace snapshot (recent instructions)
        try:
            ok, frames = self.client.trace(count=self.trace_count)
            _write_json(cap_root / "trace.json", {"ok": ok, "count": len(frames), "frames": frames})
            bundle.files["trace"] = str((cap_root / "trace.json").resolve())
        except Exception as exc:
            _write_json(cap_root / "trace.json", {"error": str(exc)})

        # Disasm around PC
        try:
            pc_info = self.client.get_pc()
            full = pc_info.get("full")
            if isinstance(full, int):
                disasm = self.client.disassemble(full, count=40)
                _write_json(cap_root / "disasm.json", {"pc": pc_info, "disasm": disasm})
            else:
                _write_json(cap_root / "disasm.json", {"pc": pc_info, "disasm": []})
            bundle.files["disasm"] = str((cap_root / "disasm.json").resolve())
        except Exception as exc:
            _write_json(cap_root / "disasm.json", {"error": str(exc)})

        # Mem reads + blame for key addresses (best-effort).
        watch_addrs: list[tuple[str, int, int]] = [
            ("inidispq", 0x7E0013, 1),
            ("ppu_inidisp", 0x002100, 1),
            ("frame", 0x7E001A, 1),
            ("mode", 0x7E0010, 1),
            ("submode", 0x7E0011, 1),
            ("room_layout", 0x7E00A0, 1),
            ("room_id", 0x7E00A4, 2),
            ("rmfade", 0x7EC005, 2),
            ("fadetime", 0x7EC007, 2),
            ("fadetgt", 0x7EC00B, 2),
            ("colormath_9a", 0x7E009A, 1),
            ("colormath_9c", 0x7E009C, 1),
            ("colormath_9d", 0x7E009D, 1),
        ]
        mem: dict[str, Any] = {"read": {}, "blame": {}}
        for name, addr, size in watch_addrs:
            try:
                if size == 2:
                    value = self.client.bridge.read_memory16(addr)
                else:
                    value = self.client.bridge.read_memory(addr)
                mem["read"][name] = {"addr": f"0x{addr:06X}", "size": size, "value": value}
            except Exception as exc:
                mem["read"][name] = {"addr": f"0x{addr:06X}", "size": size, "error": str(exc)}
            try:
                # MEM_BLAME only makes sense for WRAM addresses.
                if addr < 0x7E0000:
                    continue
                mem["blame"][name] = self.client.mem_blame(addr=addr)
            except Exception as exc:
                mem["blame"][name] = {"addr": f"0x{addr:06X}", "error": str(exc)}
        _write_json(cap_root / "mem.json", mem)
        bundle.files["mem"] = str((cap_root / "mem.json").resolve())

        # Progress snapshot (SRAM and story flags) is useful, but not required for most hang bugs.
        try:
            from .progress_validator import ProgressValidator

            validator = ProgressValidator(self.emu)
            snap = validator.capture_progress()
            _write_json(cap_root / "progress.json", snap.to_dict())
            bundle.files["progress"] = str((cap_root / "progress.json").resolve())
        except Exception as exc:
            _write_json(cap_root / "progress.json", {"error": str(exc)})

        # Marker + markdown summary
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _write_json(LAST_CAPTURE_MARKER, {"timestamp": tag, "path": str(cap_root), "kind": anomaly.kind})
            _write_text(LATEST_REPORT_MD, self._format_latest_report(world=world, bundle=bundle))
        except Exception:
            pass

        return bundle

    @staticmethod
    def _format_latest_report(*, world: dict[str, Any], bundle: ForensicsBundle) -> str:
        loc = world.get("location", {})
        raw = world.get("raw", {})
        run_state = world.get("run_state", {})
        lines = [
            "# Agentic Autodebug: Latest Capture",
            "",
            f"- Timestamp: `{world.get('timestamp')}`",
            f"- Anomaly: `{world.get('anomaly', {}).get('kind')}` ({world.get('anomaly', {}).get('severity')})",
            f"- Description: {world.get('anomaly', {}).get('description')}",
            "",
            "## Location",
            f"- Canonical: `{loc.get('canonical_location')}`",
            f"- Parser: `{loc.get('parser_location')}`",
            f"- Area: `0x{int(loc.get('area_id', 0)):02X}`",
            f"- RoomID: `0x{int(loc.get('room_id', 0)):04X}`",
            f"- RoomLayout: `0x{int(loc.get('room_layout', 0)):02X}`",
            f"- Indoors: `{bool(loc.get('indoors'))}`",
            f"- Pos: `{loc.get('pos')}`",
            "",
            "## State",
            f"- Mode: `0x{int(raw.get('mode', 0)):02X}`",
            f"- SubMode: `0x{int(raw.get('submode', 0)):02X}`",
            f"- Frame: `{int(raw.get('frame', 0))}`",
            f"- INIDISPQ: `0x{int(raw.get('inidispq', 0)):02X}`",
            f"- RunState: paused=`{run_state.get('paused')}` running=`{run_state.get('running')}` frame=`{run_state.get('frame')}`",
            "",
            "## Files",
        ]
        for k, v in sorted(bundle.files.items()):
            lines.append(f"- `{k}`: `{v}`")
        if bundle.state_path:
            lines.append(f"- `savestate`: `{bundle.state_path}`")
        lines.append("")
        lines.append(f"Capture root: `{bundle.root}`")
        return "\n".join(lines)


def cmd_triage_latest() -> int:
    if not LAST_CAPTURE_MARKER.exists():
        print("No agentic autodebug captures found (missing last_capture marker).")
        return 1
    meta = json.loads(LAST_CAPTURE_MARKER.read_text(encoding="utf-8"))
    path = meta.get("path")
    print(json.dumps(meta, indent=2))
    if path and isinstance(path, str):
        report = Path(path) / "world.json"
        if report.exists():
            print()
            print("world.json:")
            print(report.read_text(encoding="utf-8"))
    if LATEST_REPORT_MD.exists():
        print()
        print(LATEST_REPORT_MD.read_text(encoding="utf-8"))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Agentic autonomous debugger (world-aware + forensics capture)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python3 -m scripts.campaign.agentic_autodebug arm          # includes JumpTableLocal p-assert by default
  python3 -m scripts.campaign.agentic_autodebug monitor --duration 600 --poll-hz 4
  python3 -m scripts.campaign.agentic_autodebug run --max-iterations 50
  python3 -m scripts.campaign.agentic_autodebug capture --kind manual --desc "suspected blackout"
  python3 -m scripts.campaign.agentic_autodebug triage --latest
""",
    )
    parser.add_argument("--socket", default=None, help="Target Mesen2 socket path (recommended)")
    parser.add_argument("--instance", default=None, help="Mesen2 registry instance name (optional)")
    parser.add_argument("--capture-dir", default=str(DEFAULT_CAPTURE_DIR), help="Capture output directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    sub = parser.add_subparsers(dest="cmd", required=True)

    arm_p = sub.add_parser("arm", help="Arm instrumentation (p-watch, trace, mem-watches, optional JumpTableLocal assert)")
    arm_p.add_argument("--no-assert-jtl", action="store_true", help="Do not arm JumpTableLocal p-assert")
    arm_p.add_argument("--p-watch-depth", type=int, default=8000)
    arm_p.add_argument("--mem-watch-depth", type=int, default=4000)

    mon_p = sub.add_parser("monitor", help="Monitor manual play (polling) and capture on anomaly")
    mon_p.add_argument("--duration", type=int, default=300)
    mon_p.add_argument("--poll-hz", type=int, default=4)
    mon_p.add_argument("--no-arm", action="store_true", help="Skip instrumentation arming (faster, less forensic detail)")

    run_p = sub.add_parser("run", help="Run campaign autopilot with per-frame anomaly detection")
    run_p.add_argument("--max-iterations", type=int, default=50)
    run_p.add_argument("--no-arm", action="store_true", help="Skip instrumentation arming (faster, less forensic detail)")

    cap_p = sub.add_parser("capture", help="Force a capture bundle right now (no detection required)")
    cap_p.add_argument("--kind", default="manual")
    cap_p.add_argument("--desc", default="manual capture")

    tri_p = sub.add_parser("triage", help="Show last capture marker + summary")
    tri_p.add_argument("--latest", action="store_true", help="Show latest capture")

    args = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    session = AgenticAutodebugSession(
        socket_path=args.socket,
        instance=args.instance,
        capture_dir=Path(args.capture_dir).expanduser(),
        arm_assert_jtl=not getattr(args, "no_assert_jtl", False),
        arm_p_watch_depth=getattr(args, "p_watch_depth", 8000),
        arm_mem_watch_depth=getattr(args, "mem_watch_depth", 4000),
    )

    if args.cmd == "triage":
        if args.latest:
            return cmd_triage_latest()
        parser.error("triage requires --latest")

    # Remaining commands require live emulator connection.
    session.connect()

    if args.cmd == "arm":
        res = session.arm_instrumentation()
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "monitor":
        return session.monitor_manual(duration_s=args.duration, poll_hz=args.poll_hz, arm=not args.no_arm)

    if args.cmd == "run":
        try:
            return session.campaign_autopilot(max_iterations=args.max_iterations, arm=not args.no_arm)
        except AutodebugAbort:
            return 2

    if args.cmd == "capture":
        raw = session.emu.read_state()
        parsed = session.parser.parse(raw)
        anomaly = AutodebugAnomaly(
            kind=str(args.kind),
            severity="info",
            description=str(args.desc),
            timestamp=time.time(),
            context={},
        )
        run_state = session.client.get_run_state() if session.client is not None else {}
        bundle = session.capture(anomaly, raw, parsed, run_state=run_state)
        print(f"Captured: {bundle.root}")
        if LAST_CAPTURE_MARKER.exists():
            print(f"Marker: {LAST_CAPTURE_MARKER}")
        return 0

    parser.error(f"Unhandled cmd: {args.cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
