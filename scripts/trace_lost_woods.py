#!/usr/bin/env python3
"""
Trace Lost Woods scroll and position values during transitions.

This script monitors the relevant registers to understand the full
state before, during, and after area transitions in Lost Woods.

Usage:
    ./scripts/trace_lost_woods.py [--continuous]
"""

import argparse
import time
from dataclasses import dataclass
from typing import Optional

from mesen2_client_lib.bridge import MesenBridge

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class FullState:
    """Complete snapshot of relevant registers."""

    # Core state
    mode: int
    submode: int
    area: int

    # Link position (16-bit)
    link_x: int
    link_y: int

    # Scroll registers (8-bit each)
    scroll_x_lo: int   # $E1
    scroll_x_hi: int   # $E3
    scroll_y_lo: int   # $E7
    scroll_y_hi: int   # $E9

    # BG scroll mirrors
    bg1_scroll_x: int  # $E0
    bg1_scroll_y: int  # $E6
    bg2_scroll_x: int  # $E2
    bg2_scroll_y: int  # $E8

    # Camera boundaries
    cam_y_min: int     # $0600
    cam_y_max: int     # $0602
    cam_x_min: int     # $0604
    cam_x_max: int     # $0606

    # Transition targets
    trans_north: int   # $0610
    trans_south: int   # $0612
    trans_west: int    # $0614
    trans_east: int    # $0616

    # Lost Woods specific
    combo_counter: int # $1CF7
    restore_cam: int   # $1CF8

    # Transition state
    scroll_dir: int    # $0416
    trans_dir: int     # $0418

    # True area ID
    true_area: int     # $0700

    timestamp: float

    @property
    def scroll_x_full(self) -> int:
        """Full 16-bit X scroll."""
        return (self.scroll_x_hi << 8) | self.scroll_x_lo

    @property
    def scroll_y_full(self) -> int:
        """Full 16-bit Y scroll."""
        return (self.scroll_y_hi << 8) | self.scroll_y_lo

    @property
    def offset_x(self) -> int:
        return self.link_x - self.scroll_x_full

    @property
    def offset_y(self) -> int:
        return self.link_y - self.scroll_y_full


def read_full_state(bridge: MesenBridge) -> FullState:
    """Read all relevant registers."""
    return FullState(
        mode=bridge.read_memory(0x7E0010),
        submode=bridge.read_memory(0x7E0011),
        area=bridge.read_memory(0x7E008A),

        link_x=bridge.read_memory16(0x7E0022),
        link_y=bridge.read_memory16(0x7E0020),

        scroll_x_lo=bridge.read_memory(0x7E00E1),
        scroll_x_hi=bridge.read_memory(0x7E00E3),
        scroll_y_lo=bridge.read_memory(0x7E00E7),
        scroll_y_hi=bridge.read_memory(0x7E00E9),

        bg1_scroll_x=bridge.read_memory(0x7E00E0),
        bg1_scroll_y=bridge.read_memory(0x7E00E6),
        bg2_scroll_x=bridge.read_memory(0x7E00E2),
        bg2_scroll_y=bridge.read_memory(0x7E00E8),

        cam_y_min=bridge.read_memory16(0x7E0600),
        cam_y_max=bridge.read_memory16(0x7E0602),
        cam_x_min=bridge.read_memory16(0x7E0604),
        cam_x_max=bridge.read_memory16(0x7E0606),

        trans_north=bridge.read_memory16(0x7E0610),
        trans_south=bridge.read_memory16(0x7E0612),
        trans_west=bridge.read_memory16(0x7E0614),
        trans_east=bridge.read_memory16(0x7E0616),

        combo_counter=bridge.read_memory(0x7E1CF7),
        restore_cam=bridge.read_memory(0x7E1CF8),

        scroll_dir=bridge.read_memory(0x7E0416),
        trans_dir=bridge.read_memory(0x7E0418),

        true_area=bridge.read_memory16(0x7E0700),

        timestamp=time.time(),
    )


def print_state(state: FullState, label: str = ""):
    """Pretty print the state."""
    if label:
        print(f"\n{BOLD}{CYAN}=== {label} ==={RESET}")

    print(f"\n{BOLD}Core State:{RESET}")
    print(f"  Mode: 0x{state.mode:02X}  Submode: 0x{state.submode:02X}  Area: 0x{state.area:02X}  TrueArea: 0x{state.true_area:04X}")

    print(f"\n{BOLD}Link Position:{RESET}")
    print(f"  X: {state.link_x} (0x{state.link_x:04X})  Y: {state.link_y} (0x{state.link_y:04X})")

    print(f"\n{BOLD}Scroll Registers:{RESET}")
    print(f"  $E1 (X lo): 0x{state.scroll_x_lo:02X}  $E3 (X hi): 0x{state.scroll_x_hi:02X}  -> Full X: {state.scroll_x_full} (0x{state.scroll_x_full:04X})")
    print(f"  $E7 (Y lo): 0x{state.scroll_y_lo:02X}  $E9 (Y hi): 0x{state.scroll_y_hi:02X}  -> Full Y: {state.scroll_y_full} (0x{state.scroll_y_full:04X})")

    print(f"\n{BOLD}BG Scroll Mirrors:{RESET}")
    print(f"  $E0 (BG1 X): 0x{state.bg1_scroll_x:02X}  $E6 (BG1 Y): 0x{state.bg1_scroll_y:02X}")
    print(f"  $E2 (BG2 X): 0x{state.bg2_scroll_x:02X}  $E8 (BG2 Y): 0x{state.bg2_scroll_y:02X}")

    print(f"\n{BOLD}Camera Offset from Link:{RESET}")
    offset_x = state.offset_x
    offset_y = state.offset_y
    x_color = RED if abs(offset_x) > 200 else GREEN
    y_color = RED if abs(offset_y) > 200 else GREEN
    print(f"  X Offset: {x_color}{offset_x}{RESET}  Y Offset: {y_color}{offset_y}{RESET}")

    print(f"\n{BOLD}Camera Boundaries:{RESET}")
    print(f"  Y: [{state.cam_y_min}, {state.cam_y_max}]  X: [{state.cam_x_min}, {state.cam_x_max}]")

    print(f"\n{BOLD}Transition Targets:{RESET}")
    print(f"  N: 0x{state.trans_north:04X}  S: 0x{state.trans_south:04X}  W: 0x{state.trans_west:04X}  E: 0x{state.trans_east:04X}")

    print(f"\n{BOLD}Lost Woods State:{RESET}")
    print(f"  ComboCounter: {state.combo_counter}  RestoreCam: 0x{state.restore_cam:02X}")

    print(f"\n{BOLD}Transition State:{RESET}")
    print(f"  ScrollDir: 0x{state.scroll_dir:02X}  TransDir: 0x{state.trans_dir:02X}")


def print_diff(before: FullState, after: FullState):
    """Print differences between two states."""
    print(f"\n{BOLD}{MAGENTA}=== CHANGES ==={RESET}")

    changes = []

    if before.area != after.area:
        changes.append(f"  Area: 0x{before.area:02X} -> 0x{after.area:02X}")

    if before.link_x != after.link_x or before.link_y != after.link_y:
        changes.append(f"  Link: ({before.link_x}, {before.link_y}) -> ({after.link_x}, {after.link_y})")

    if before.scroll_x_lo != after.scroll_x_lo:
        changes.append(f"  $E1 (X lo): 0x{before.scroll_x_lo:02X} -> 0x{after.scroll_x_lo:02X}")
    if before.scroll_x_hi != after.scroll_x_hi:
        changes.append(f"  $E3 (X hi): 0x{before.scroll_x_hi:02X} -> 0x{after.scroll_x_hi:02X}")
    if before.scroll_y_lo != after.scroll_y_lo:
        changes.append(f"  $E7 (Y lo): 0x{before.scroll_y_lo:02X} -> 0x{after.scroll_y_lo:02X}")
    if before.scroll_y_hi != after.scroll_y_hi:
        changes.append(f"  $E9 (Y hi): 0x{before.scroll_y_hi:02X} -> 0x{after.scroll_y_hi:02X}")

    if before.scroll_x_full != after.scroll_x_full:
        delta = after.scroll_x_full - before.scroll_x_full
        changes.append(f"  Full X Scroll: {before.scroll_x_full} -> {after.scroll_x_full} (delta: {delta})")
    if before.scroll_y_full != after.scroll_y_full:
        delta = after.scroll_y_full - before.scroll_y_full
        changes.append(f"  Full Y Scroll: {before.scroll_y_full} -> {after.scroll_y_full} (delta: {delta})")

    if before.combo_counter != after.combo_counter:
        changes.append(f"  ComboCounter: {before.combo_counter} -> {after.combo_counter}")

    if before.mode != after.mode:
        changes.append(f"  Mode: 0x{before.mode:02X} -> 0x{after.mode:02X}")

    if changes:
        for c in changes:
            print(c)
    else:
        print("  (no changes)")


def monitor_continuous(bridge: MesenBridge, interval: float = 0.1):
    """Continuously monitor state changes."""
    print(f"{BOLD}Monitoring Lost Woods state (Ctrl+C to stop)...{RESET}")
    print(f"Watching for area transitions and scroll changes.\n")

    prev_state = read_full_state(bridge)
    prev_area = prev_state.area

    sample_count = 0

    try:
        while True:
            state = read_full_state(bridge)

            # Check for area change
            if state.area != prev_area:
                print(f"\n{YELLOW}{'='*60}{RESET}")
                print(f"{YELLOW}AREA TRANSITION: 0x{prev_area:02X} -> 0x{state.area:02X}{RESET}")
                print(f"{YELLOW}{'='*60}{RESET}")
                print_state(prev_state, "BEFORE")
                print_state(state, "AFTER")
                print_diff(prev_state, state)
                prev_area = state.area

            # Check for mode change (transition states)
            elif state.mode != prev_state.mode:
                print(f"\n{BLUE}Mode change: 0x{prev_state.mode:02X} -> 0x{state.mode:02X}{RESET}")
                print(f"  Area: 0x{state.area:02X}  Scroll: ({state.scroll_x_full}, {state.scroll_y_full})")

            # Check for significant scroll changes without area change
            elif (abs(state.scroll_x_full - prev_state.scroll_x_full) > 10 or
                  abs(state.scroll_y_full - prev_state.scroll_y_full) > 10):
                print(f"\n{CYAN}Scroll change (no area change):{RESET}")
                print(f"  X: {prev_state.scroll_x_full} -> {state.scroll_x_full}")
                print(f"  Y: {prev_state.scroll_y_full} -> {state.scroll_y_full}")

            # Periodic status for Lost Woods areas
            if state.area in [0x28, 0x29, 0x2A, 0x38, 0x39, 0x3A]:
                sample_count += 1
                if sample_count % 50 == 0:  # Every 5 seconds at 0.1s interval
                    print(f"  [0x{state.area:02X}] Link:({state.link_x},{state.link_y}) Scroll:({state.scroll_x_full},{state.scroll_y_full}) Offset:({state.offset_x},{state.offset_y}) Combo:{state.combo_counter}")

            prev_state = state
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopped monitoring.{RESET}")


def single_snapshot(bridge: MesenBridge):
    """Take a single snapshot."""
    state = read_full_state(bridge)
    print_state(state, "Current State")


def main():
    parser = argparse.ArgumentParser(description="Trace Lost Woods transitions")
    parser.add_argument("--continuous", "-c", action="store_true",
                        help="Continuous monitoring mode")
    parser.add_argument("--interval", "-i", type=float, default=0.1,
                        help="Monitoring interval in seconds (default: 0.1)")
    args = parser.parse_args()

    bridge = MesenBridge()

    if not bridge.is_connected():
        print(f"{RED}Not connected to Mesen2{RESET}")
        return 1

    if args.continuous:
        monitor_continuous(bridge, args.interval)
    else:
        single_snapshot(bridge)

    return 0


if __name__ == "__main__":
    exit(main())
