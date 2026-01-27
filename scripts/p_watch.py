#!/usr/bin/env python3
"""
P Register Watch - Track P register (M/X flags) changes during execution.

Monitors the SNES CPU P register at hook entry points and compares against
expected states from hooks.json. Useful for detecting M/X flag mismatches
that can cause soft locks and corrupted behavior.

Usage:
    python3 p_watch.py --hooks hooks.json --frames 600
    python3 p_watch.py --addresses 0x028A5B,0x079CD9 --frames 300
    python3 p_watch.py --hooks hooks.json --output p_watch_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Set

# Add script directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from mesen2_client_lib.client import OracleDebugClient
from mesen2_client_lib.bridge import MesenBridge


@dataclass
class PMismatch:
    """Record of a P register mismatch at a hook entry point."""
    pc: int
    hook_name: str
    flag_type: str  # 'M' or 'X'
    expected: int   # 8 or 16
    actual: int     # 8 or 16
    frame: int
    timestamp: float


@dataclass
class HookExpectation:
    """Expected P register state at a hook."""
    address: int
    name: str
    expected_m: Optional[int] = None  # 8 or 16
    expected_x: Optional[int] = None  # 8 or 16
    source: Optional[str] = None


class PRegisterWatch:
    """Track P register (M/X flags) changes during execution."""

    def __init__(self, client: OracleDebugClient):
        self.client = client
        self.log: List[PMismatch] = []
        self.hooks: Dict[int, HookExpectation] = {}
        self.breakpoint_ids: Dict[int, int] = {}  # addr -> breakpoint id
        self.frame_count = 0
        self.start_time = 0.0

    def load_hooks(self, hooks_json: Path) -> int:
        """Load hooks from hooks.json and return count of loaded hooks."""
        if not hooks_json.exists():
            print(f"Warning: hooks file not found: {hooks_json}", file=sys.stderr)
            return 0

        with open(hooks_json) as f:
            data = json.load(f)

        for hook in data.get('hooks', []):
            addr_str = hook.get('address', '0')
            if addr_str.startswith('0x'):
                addr = int(addr_str, 16)
            elif addr_str.startswith('$'):
                addr = int(addr_str[1:], 16)
            else:
                addr = int(addr_str)

            exp_m = hook.get('expected_m')
            exp_x = hook.get('expected_x')

            if exp_m is not None or exp_x is not None:
                self.hooks[addr] = HookExpectation(
                    address=addr,
                    name=hook.get('name', f'hook_{addr:06X}'),
                    expected_m=exp_m,
                    expected_x=exp_x,
                    source=hook.get('source'),
                )

        # Also load critical addresses
        for addr_info in data.get('critical_addresses', []):
            addr_str = addr_info.get('address', '0')
            if addr_str.startswith('0x'):
                addr = int(addr_str, 16)
            elif addr_str.startswith('$'):
                addr = int(addr_str[1:], 16)
            else:
                addr = int(addr_str)

            exp_m = addr_info.get('expected_m')
            exp_x = addr_info.get('expected_x')

            if exp_m is not None or exp_x is not None:
                self.hooks[addr] = HookExpectation(
                    address=addr,
                    name=addr_info.get('name', f'addr_{addr:06X}'),
                    expected_m=exp_m,
                    expected_x=exp_x,
                )

        return len(self.hooks)

    def add_address(self, addr: int, name: Optional[str] = None,
                    expected_m: int = 8, expected_x: int = 8) -> None:
        """Add a specific address to monitor."""
        self.hooks[addr] = HookExpectation(
            address=addr,
            name=name or f'addr_{addr:06X}',
            expected_m=expected_m,
            expected_x=expected_x,
        )

    def set_hook_breakpoints(self) -> int:
        """Set breakpoints at all hook addresses. Returns count set."""
        count = 0
        for addr, hook in self.hooks.items():
            # Set execution breakpoint at hook entry
            result = self.client.add_breakpoint(
                address=addr,
                breakpoint_type='execute',
                enabled=True,
            )
            if result:
                bp_id = result.get('id') if isinstance(result, dict) else None
                if bp_id:
                    self.breakpoint_ids[addr] = bp_id
                count += 1
        return count

    def check_p_register(self) -> List[PMismatch]:
        """Check current P register against expected states at PC.

        Returns list of mismatches found.
        """
        mismatches = []

        # Get CPU state
        cpu_state = self.client.get_cpu_state()
        if not cpu_state:
            return mismatches

        pc = cpu_state.get('PC', 0)
        p = cpu_state.get('P', 0)

        if pc not in self.hooks:
            return mismatches

        hook = self.hooks[pc]

        # Extract M and X flags from P register
        # P register bit 5 = M flag (1 = 8-bit A, 0 = 16-bit A)
        # P register bit 4 = X flag (1 = 8-bit X/Y, 0 = 16-bit X/Y)
        m_flag = 8 if (p & 0x20) else 16
        x_flag = 8 if (p & 0x10) else 16

        # Check M flag
        if hook.expected_m is not None and m_flag != hook.expected_m:
            mismatches.append(PMismatch(
                pc=pc,
                hook_name=hook.name,
                flag_type='M',
                expected=hook.expected_m,
                actual=m_flag,
                frame=self.frame_count,
                timestamp=time.time() - self.start_time,
            ))

        # Check X flag
        if hook.expected_x is not None and x_flag != hook.expected_x:
            mismatches.append(PMismatch(
                pc=pc,
                hook_name=hook.name,
                flag_type='X',
                expected=hook.expected_x,
                actual=x_flag,
                frame=self.frame_count,
                timestamp=time.time() - self.start_time,
            ))

        return mismatches

    def run(self, frames: int = 600, poll_interval: float = 0.01) -> List[PMismatch]:
        """Run for N frames, collecting P register events.

        Args:
            frames: Number of frames to run (60 frames ~= 1 second)
            poll_interval: How often to poll CPU state (seconds)

        Returns:
            List of all P register mismatches found
        """
        self.start_time = time.time()
        self.frame_count = 0
        self.log = []

        # Ensure emulator is running
        if not self.client.ensure_running():
            print("Warning: Could not ensure emulator is running", file=sys.stderr)

        # Run frames in batches, checking P register periodically
        frames_per_batch = max(1, frames // 100)  # ~100 checks total

        while self.frame_count < frames:
            # Run a batch of frames
            batch_size = min(frames_per_batch, frames - self.frame_count)
            self.client.run_frames(batch_size)
            self.frame_count += batch_size

            # Check P register
            mismatches = self.check_p_register()
            self.log.extend(mismatches)

            # Report mismatches as they occur
            for mismatch in mismatches:
                print(f"[Frame {mismatch.frame}] {mismatch.flag_type}_MISMATCH at "
                      f"${mismatch.pc:06X} ({mismatch.hook_name}): "
                      f"expected {mismatch.expected}-bit, got {mismatch.actual}-bit",
                      file=sys.stderr)

            # Brief sleep to allow other processes
            time.sleep(poll_interval)

        return self.log

    def export_report(self, output_path: Path) -> None:
        """Export mismatch log to JSON file."""
        report = {
            'summary': {
                'total_mismatches': len(self.log),
                'm_mismatches': sum(1 for m in self.log if m.flag_type == 'M'),
                'x_mismatches': sum(1 for m in self.log if m.flag_type == 'X'),
                'hooks_monitored': len(self.hooks),
                'frames_run': self.frame_count,
            },
            'mismatches': [
                {
                    'pc': f"${m.pc:06X}",
                    'hook': m.hook_name,
                    'flag': m.flag_type,
                    'expected': m.expected,
                    'actual': m.actual,
                    'frame': m.frame,
                    'timestamp': round(m.timestamp, 3),
                }
                for m in self.log
            ],
            'hooks': [
                {
                    'address': f"${h.address:06X}",
                    'name': h.name,
                    'expected_m': h.expected_m,
                    'expected_x': h.expected_x,
                    'source': h.source,
                }
                for h in self.hooks.values()
            ],
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"Report exported to: {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Track P register (M/X flags) at hook entry points",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor P register at all hooks for 10 seconds (600 frames)
  %(prog)s --hooks hooks.json --frames 600

  # Monitor specific addresses
  %(prog)s --addresses 0x028A5B,0x079CD9 --frames 300

  # Output JSON report
  %(prog)s --hooks hooks.json --output p_watch_report.json
"""
    )

    parser.add_argument('--hooks', type=Path, default=Path('hooks.json'),
                       help='Hooks manifest JSON (default: hooks.json)')
    parser.add_argument('--addresses', type=str,
                       help='Comma-separated addresses to monitor (hex)')
    parser.add_argument('--frames', type=int, default=600,
                       help='Number of frames to run (default: 600, ~10 seconds)')
    parser.add_argument('--output', '-o', type=Path,
                       help='Output report to JSON file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    # Connect to emulator
    client = OracleDebugClient()
    if not client.ensure_connected():
        print("Error: Could not connect to Mesen2 socket", file=sys.stderr)
        return 1

    # Create watcher
    watcher = PRegisterWatch(client)

    # Load hooks
    if args.hooks.exists():
        count = watcher.load_hooks(args.hooks)
        print(f"Loaded {count} hooks with P register expectations", file=sys.stderr)

    # Add specific addresses
    if args.addresses:
        for addr_str in args.addresses.split(','):
            addr_str = addr_str.strip()
            if addr_str.startswith('0x'):
                addr = int(addr_str, 16)
            elif addr_str.startswith('$'):
                addr = int(addr_str[1:], 16)
            else:
                addr = int(addr_str, 16)
            watcher.add_address(addr)
            print(f"Added monitor at ${addr:06X}", file=sys.stderr)

    if not watcher.hooks:
        print("Error: No hooks to monitor. Use --hooks or --addresses", file=sys.stderr)
        return 1

    # Run monitoring
    print(f"Monitoring {len(watcher.hooks)} addresses for {args.frames} frames...",
          file=sys.stderr)

    mismatches = watcher.run(args.frames)

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"P Register Watch Summary", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Frames run: {watcher.frame_count}", file=sys.stderr)
    print(f"Hooks monitored: {len(watcher.hooks)}", file=sys.stderr)
    print(f"Total mismatches: {len(mismatches)}", file=sys.stderr)

    m_count = sum(1 for m in mismatches if m.flag_type == 'M')
    x_count = sum(1 for m in mismatches if m.flag_type == 'X')
    if m_count:
        print(f"  M flag mismatches: {m_count}", file=sys.stderr)
    if x_count:
        print(f"  X flag mismatches: {x_count}", file=sys.stderr)

    # Export report if requested
    if args.output:
        watcher.export_report(args.output)

    # Return non-zero if mismatches found
    return 1 if mismatches else 0


if __name__ == '__main__':
    sys.exit(main())
