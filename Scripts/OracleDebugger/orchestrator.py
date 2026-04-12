#!/usr/bin/env python3
"""
Oracle Debug Orchestrator - Unified debugging coordinator for Oracle of Secrets.

Coordinates multiple debugging tools:
- Sentinel watchdog (soft lock detection)
- Crash dump analyzer (post-mortem traces)
- Static analyzer (ASM pattern checks)
- MoE bridge (expert analysis routing)

Usage:
    # Start monitoring session
    python3 orchestrator.py --monitor

    # Investigate a save state
    python3 orchestrator.py --investigate path/to/state.mss

    # Run regression test
    python3 orchestrator.py --regression --suite smoke
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mesen2_client_lib.client import OracleDebugClient
from mesen2_client_lib.constants import OracleRAM

from oracle_debugger.session import DebugSession, Detection, TraceCapture, StateCapture, SessionState
from oracle_debugger.moe_bridge import MoEBridge
from oracle_debugger.reporters import MarkdownReporter, JSONReporter, RegressionTestGenerator

logger = logging.getLogger(__name__)


class OracleDebugOrchestrator:
    """
    Unified debugging orchestrator for Oracle of Secrets.

    Coordinates multiple debugging tools in a single session:
    - Real-time monitoring via Sentinel watchdog
    - Post-mortem analysis via crash dump
    - Expert routing via MoE bridge
    - Report generation
    """

    # Soft lock detection patterns (from Sentinel)
    SOFTLOCK_PATTERNS = {
        "B007": {
            "name": "Y-coordinate overflow",
            "check": lambda state: state.get("link_y", 0) > 60000,
            "description": "Link's Y position overflowed (16-bit wraparound)",
        },
        "B009": {
            "name": "Unexpected game reset",
            "check": lambda state: state.get("game_mode", 0) == 0,
            "description": "Game mode reset to 0x00 during gameplay",
        },
        "INIDISP": {
            "name": "Black screen (INIDISP stuck)",
            "check": lambda state: state.get("inidisp", 0) == 0x80,
            "description": "Screen stuck at INIDISP 0x80",
        },
        "MODE06_STUCK": {
            "name": "Dungeon load hang",
            "check": lambda state: state.get("game_mode", 0) == 0x06,
            "description": "Dungeon loading screen stuck (mode 0x06)",
        },
    }

    def __init__(
        self,
        socket_path: Optional[str] = None,
        moe_enabled: bool = True,
        verbose: bool = False,
        remote: bool = False,
    ):
        """
        Initialize the orchestrator.

        Args:
            socket_path: Path to Mesen2 socket (auto-detect if None)
            moe_enabled: Enable MoE expert routing
            verbose: Enable verbose logging
            remote: Use remote backend for MoE
        """
        self.verbose = verbose
        self.moe_enabled = moe_enabled

        # Initialize Mesen2 client
        self.client = OracleDebugClient(socket_path=socket_path)

        # Initialize MoE bridge
        self.moe: Optional[MoEBridge] = None
        if moe_enabled:
            self.moe = MoEBridge(verbose=verbose, remote=remote)

        # Session management
        self.session: Optional[DebugSession] = None
        self._running = False
        self._detection_count = 0

        # Reporters
        self.md_reporter = MarkdownReporter()
        self.json_reporter = JSONReporter()
        self.test_generator = RegressionTestGenerator()

        # Monitoring state
        self._last_state: dict = {}
        self._state_unchanged_count = 0
        self._mode_stuck_start: Optional[float] = None

    def start_session(self, tags: Optional[list[str]] = None) -> DebugSession:
        """
        Start a new debugging session.

        Args:
            tags: Optional tags for the session

        Returns:
            New DebugSession instance
        """
        self.session = DebugSession()
        self.session.tags = tags or []

        # Get ROM info if connected
        if self.client.is_connected():
            try:
                rom_info = self.client.get_rom_info()
                self.session.rom_path = rom_info.get("path")
                self.session.rom_crc = rom_info.get("crc32")
            except Exception as e:
                logger.warning(f"Could not get ROM info: {e}")

        self.session.add_note("Session started")
        logger.info(f"Started debug session: {self.session.session_id}")
        return self.session

    def end_session(self) -> tuple[Path, Path]:
        """
        End the current session and generate reports.

        Returns:
            Tuple of (markdown_report_path, json_report_path)
        """
        if not self.session:
            raise RuntimeError("No active session")

        self.session.set_state(SessionState.COMPLETED)
        self.session.add_note("Session ended")

        # Generate reports
        md_path = self.md_reporter.save(self.session)
        json_path = self.json_reporter.save(self.session)

        logger.info(f"Session ended. Reports: {md_path}, {json_path}")
        return md_path, json_path

    async def monitor(self, poll_interval: float = 0.5) -> None:
        """
        Start continuous monitoring for soft locks and anomalies.

        Args:
            poll_interval: Seconds between state checks
        """
        if not self.session:
            self.start_session(tags=["monitoring"])

        self.session.set_state(SessionState.MONITORING)
        self._running = True

        logger.info("Starting monitoring loop...")
        self.session.add_note("Monitoring started")

        try:
            while self._running:
                await self._monitor_tick()
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("Monitoring cancelled")
        finally:
            self._running = False

    async def _monitor_tick(self) -> None:
        """Single monitoring iteration."""
        if not self.client.is_connected():
            try:
                self.client.ensure_connected()
            except Exception as e:
                logger.warning(f"Connection failed: {e}")
                return

        # Get current state
        try:
            state = self._get_game_state()
        except Exception as e:
            logger.warning(f"Failed to get game state: {e}")
            return

        # Check for soft locks
        for pattern_id, pattern in self.SOFTLOCK_PATTERNS.items():
            if pattern["check"](state):
                await self._handle_detection(pattern_id, pattern, state)

        # Check for state stagnation
        self._check_stagnation(state)

        self._last_state = state

    def _get_game_state(self) -> dict:
        """Get current game state from emulator."""
        state = {}

        try:
            oracle_state = self.client.get_oracle_state()
            state.update({
                "game_mode": oracle_state.get("mode", 0),
                "submodule": oracle_state.get("submodule", 0),
                "link_x": oracle_state.get("link_x", 0),
                "link_y": oracle_state.get("link_y", 0),
                "link_z": oracle_state.get("link_z", 0),
                "area_id": oracle_state.get("area_id", 0),
                "indoors": oracle_state.get("indoors", False),
            })
        except Exception as e:
            logger.debug(f"Could not get oracle state: {e}")

        # Read INIDISP directly
        try:
            inidisp = self.client.bridge.send("read", OracleRAM.INIDISP)
            state["inidisp"] = int(inidisp[1]) if inidisp[0] else 0
        except Exception:
            pass

        return state

    def _check_stagnation(self, state: dict) -> None:
        """Check for state stagnation (potential soft lock)."""
        # Compare to last state
        if self._states_equal(state, self._last_state):
            self._state_unchanged_count += 1
        else:
            self._state_unchanged_count = 0

        # Stagnation threshold: 10 consecutive unchanged polls
        if self._state_unchanged_count >= 10:
            asyncio.create_task(self._handle_stagnation(state))
            self._state_unchanged_count = 0

        # Check mode 0x06 stuck (dungeon load)
        if state.get("game_mode") == 0x06:
            if self._mode_stuck_start is None:
                self._mode_stuck_start = time.time()
            elif time.time() - self._mode_stuck_start > 2.0:  # 2 second threshold
                asyncio.create_task(self._handle_detection(
                    "MODE06_STUCK",
                    self.SOFTLOCK_PATTERNS["MODE06_STUCK"],
                    state
                ))
                self._mode_stuck_start = None
        else:
            self._mode_stuck_start = None

    def _states_equal(self, a: dict, b: dict) -> bool:
        """Compare two game states for equality."""
        keys = ["game_mode", "submodule", "link_x", "link_y"]
        return all(a.get(k) == b.get(k) for k in keys)

    async def _handle_stagnation(self, state: dict) -> None:
        """Handle state stagnation detection."""
        await self._handle_detection(
            "STAGNATION",
            {
                "name": "State stagnation",
                "description": "Game state unchanged for extended period",
            },
            state
        )

    async def _handle_detection(
        self,
        pattern_id: str,
        pattern: dict,
        state: dict,
    ) -> None:
        """
        Handle a soft lock or anomaly detection.

        1. Capture state and trace
        2. Route to MoE for analysis
        3. Generate report
        4. Add to regression suite
        """
        if not self.session:
            return

        self._detection_count += 1
        detection_id = f"{pattern_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{self._detection_count:03d}"

        logger.warning(f"Detection: {pattern_id} - {pattern['name']}")
        self.session.add_note(f"Detection: {pattern_id}")

        # Create detection record
        detection = Detection(
            detection_id=detection_id,
            detection_type="softlock",
            pattern=pattern_id,
            frame_number=state.get("frame", 0),
            game_mode=state.get("game_mode", 0),
            submodule=state.get("submodule", 0),
            link_position=(
                state.get("link_x", 0),
                state.get("link_y", 0),
                state.get("link_z", 0),
            ),
            description=pattern.get("description", ""),
            raw_data=state,
        )
        self.session.add_detection(detection)

        # Capture state
        self.session.set_state(SessionState.CAPTURING)
        state_capture = await self._capture_state(detection_id)
        if state_capture:
            self.session.add_state(state_capture)

        # Capture trace
        trace_capture = await self._capture_trace()
        if trace_capture:
            self.session.add_trace(trace_capture)

        # Route to MoE for analysis
        if self.moe and self.moe.is_available():
            self.session.set_state(SessionState.ANALYZING)
            analysis = await self.moe.analyze_softlock(
                detection=detection.to_dict(),
                trace=trace_capture.frames if trace_capture else None,
                game_state=state,
            )
            self.session.add_analysis(analysis)

            # Get fix suggestion
            fix_analysis = await self.moe.suggest_fix({
                "id": detection_id,
                "type": detection.detection_type,
                "pattern": pattern_id,
                "description": detection.description,
            })
            self.session.add_analysis(fix_analysis)

        # Generate regression test
        if state_capture and state_capture.state_path:
            test_path = self.test_generator.save_test(
                detection,
                state_capture.state_path,
            )
            self.session.add_note(f"Regression test created: {test_path}")

        self.session.set_state(SessionState.MONITORING)

    async def _capture_state(self, label: str) -> Optional[StateCapture]:
        """Capture current emulator state."""
        try:
            # Save state to file
            state_dir = Path("Roms/SaveStates/auto")
            state_dir.mkdir(parents=True, exist_ok=True)
            state_path = state_dir / f"{label}.mss"

            result = self.client.save_state_sync(str(state_path))
            if not result:
                logger.warning("Failed to save state")
                return None

            # Get CPU state
            cpu_state = {}
            try:
                run_state = self.client.get_run_state()
                cpu_state = run_state.get("cpu", {})
            except Exception:
                pass

            return StateCapture(
                state_path=str(state_path),
                cpu_state=cpu_state,
                ram_snapshot=self._last_state,
            )
        except Exception as e:
            logger.error(f"State capture failed: {e}")
            return None

    async def _capture_trace(self, count: int = 1000) -> Optional[TraceCapture]:
        """Capture execution trace."""
        try:
            success, frames = self.client.trace(count=count)
            if not success:
                return None

            return TraceCapture(
                frames=frames,
                symbols_resolved=False,
            )
        except Exception as e:
            logger.debug(f"Trace capture failed: {e}")
            return TraceCapture()  # Empty trace

    async def investigate(self, state_path: str) -> DebugSession:
        """
        Investigate a save state for bugs.

        Args:
            state_path: Path to save state file

        Returns:
            DebugSession with investigation results
        """
        self.start_session(tags=["investigation"])
        self.session.add_note(f"Investigating: {state_path}")
        self.session.set_state(SessionState.INVESTIGATING)

        # Load the state
        try:
            self.client.load_state(state_path)
            await asyncio.sleep(1)  # Wait for state to load
        except Exception as e:
            self.session.add_note(f"Failed to load state: {e}")
            return self.session

        # Get initial state
        state = self._get_game_state()
        self.session.context["initial_state"] = state

        # Check for known patterns
        for pattern_id, pattern in self.SOFTLOCK_PATTERNS.items():
            if pattern["check"](state):
                await self._handle_detection(pattern_id, pattern, state)

        # Plan investigation if MoE available
        if self.moe and self.moe.is_available():
            plan = await self.moe.plan_investigation(
                f"Investigating save state: {state_path}\n"
                f"Initial game state: mode=${state.get('game_mode', 0):02X}, "
                f"submodule=${state.get('submodule', 0):02X}",
                available_tools=[
                    "sentinel (soft lock detection)",
                    "crash_dump (execution trace)",
                    "state_query (semantic queries)",
                    "memory_cartographer (RAM search)",
                ],
            )
            self.session.add_analysis(plan)

        return self.session

    def stop(self) -> None:
        """Stop monitoring loop."""
        self._running = False


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Oracle Debug Orchestrator - Unified debugging for Oracle of Secrets"
    )
    parser.add_argument(
        "--monitor", "-m",
        action="store_true",
        help="Start continuous monitoring"
    )
    parser.add_argument(
        "--investigate", "-i",
        type=str,
        help="Investigate a save state"
    )
    parser.add_argument(
        "--no-moe",
        action="store_true",
        help="Disable MoE expert routing"
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Use remote backend for MoE"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="crash_reports",
        help="Output directory for reports"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create orchestrator
    orchestrator = OracleDebugOrchestrator(
        moe_enabled=not args.no_moe,
        verbose=args.verbose,
        remote=args.remote,
    )

    # Set up signal handlers
    def signal_handler(sig, frame):
        logger.info("Received signal, stopping...")
        orchestrator.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.monitor:
            await orchestrator.monitor()
            md_path, json_path = orchestrator.end_session()
            print(f"Report saved: {md_path}")

        elif args.investigate:
            session = await orchestrator.investigate(args.investigate)
            md_path, json_path = orchestrator.end_session()
            print(f"Investigation complete. Report: {md_path}")

        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted")
        if orchestrator.session:
            orchestrator.end_session()


if __name__ == "__main__":
    asyncio.run(main())
