#!/usr/bin/env python3
"""Automated stack corruption repro and attribution script.

Connects to a running Mesen2 instance, sets up monitoring for SP corruption,
loads save state 1 (overworld softlock by default), then monitors for corruption.
Use --slot 2 --press-a for the file-load dungeon freeze repro.

Strategy (in priority order):
  1. Conditional breakpoint: SP >= 0x0200 (catches SP leaving valid page)
  2. TCS breakpoint: opcode 0x1B with A >= 0x0200 (catches vanilla TCS with bad A)
  3. Corruption PC breakpoint: exec at $83:A66D (fallback, catches post-corruption)
  4. Frame-by-frame SP polling: advance 1 frame, read CPU, check SP (slowest fallback)

On corruption detection: captures CPU, TRACE (500 instructions), STACK_RETADDR,
P_LOG, and MEM_BLAME for full attribution.

Usage:
    python3 repro_stack_corruption.py [--output report.json] [--slot 1]
                                      [--frames 600] [--strategy auto] [--press-a]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Add the client library to path
sys.path.insert(0, str(Path(__file__).parent))
from mesen2_client_lib.bridge import MesenBridge


# Stack region where the corrupted JSL return address lands
STACK_WATCH_START = "0x7E01FC"
STACK_WATCH_SIZE = 3       # $01FC, $01FD, $01FE

# PC where corruption manifests (invalid JSL $1D66CC)
CORRUPTION_PC = 0x83A66D

# SP boundary - valid stack is $01xx, corruption sends it to $0Dxx+
SP_VALID_MAX = 0x01FF

# NMI TCS sites that load SP from $7E1F0A
NMI_TCS_SITES = [0x0082CE, 0x008329]

# WRAM address where NMI saves/restores SP (LDA $1F0A : TCS). Write watch here catches corrupting stores.
SP_SAVE_ADDR = "0x7E1F0A"
SP_SAVE_SIZE = 2

# Maximum frames to wait for repro
DEFAULT_MAX_FRAMES = 600

# Save state slot to load
DEFAULT_SLOT = 1


def _parse_int(val) -> int:
    """Parse int from string or int."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        return int(val.replace("0x", "").replace("0X", "").replace("$", ""), 16)
    return 0


def _check_sp_corrupt(cpu: dict) -> bool:
    """Check if SP is outside valid stack page."""
    sp = _parse_int(cpu.get("sp", "0x01FF"))
    return sp > SP_VALID_MAX or sp < 0x0100


def _capture_full_attribution(bridge: MesenBridge, report: dict, watch_id=None, watch_id_1f0a=None) -> None:
    """Capture full attribution data after corruption detected."""

    # CPU state
    cpu_resp = bridge.send_command("CPU")
    if cpu_resp.get("success"):
        report["cpu"] = cpu_resp["data"]

    # Execution trace (500 instructions leading to this point)
    trace_resp = bridge.send_command("TRACE", count="500")
    if trace_resp.get("success"):
        report["trace"] = trace_resp["data"]

    # Stack return address chain
    retaddr_resp = bridge.send_command("STACK_RETADDR", count="16")
    if retaddr_resp.get("success"):
        report["stack_retaddr"] = retaddr_resp["data"]

    # P register log (last 100 changes)
    p_log_resp = bridge.send_command("P_LOG", count="100")
    if p_log_resp.get("success"):
        report["p_register_log"] = p_log_resp["data"]

    # MEM_BLAME (if watch was set up)
    if watch_id is not None:
        blame_resp = bridge.send_command("MEM_BLAME", watch_id=str(watch_id))
        if blame_resp.get("success"):
            report["blame"] = blame_resp["data"]

        # Per-address blame for precise attribution
        for offset in range(STACK_WATCH_SIZE):
            addr_val = int(STACK_WATCH_START, 16) + offset
            addr_blame = bridge.send_command("MEM_BLAME", addr=f"0x{addr_val:06X}")
            if addr_blame.get("success"):
                report[f"blame_0x{addr_val:06X}"] = addr_blame["data"]

    # MEM_BLAME for $7E1F0A (SP save location) — catches who wrote corrupt SP value
    if watch_id_1f0a is not None:
        blame_1f0a = bridge.send_command("MEM_BLAME", watch_id=str(watch_id_1f0a))
        if blame_1f0a.get("success"):
            report["blame_1F0A"] = blame_1f0a["data"]

    # Symbol resolution on blame PCs
    if "blame" in report:
        resolved = []
        for write in report["blame"].get("writes", [])[:20]:
            pc = write.get("pc", "0x000000")
            sym_resp = bridge.send_command("SYMBOLS_RESOLVE", addr=pc)
            if sym_resp.get("success"):
                resolved.append({
                    "pc": pc,
                    "symbol": sym_resp["data"],
                    "value": write.get("value"),
                    "opcode": write.get("opcode"),
                    "sp": write.get("sp"),
                    "cycle": write.get("cycle"),
                })
        if resolved:
            report["resolved_blame"] = resolved

    # Symbol resolution on CPU PC and trace entries
    if "cpu" in report:
        pc = report["cpu"].get("pc", "0x000000")
        sym_resp = bridge.send_command("SYMBOLS_RESOLVE", addr=pc)
        if sym_resp.get("success"):
            report["cpu_symbol"] = sym_resp["data"]

    # Try to identify the exact SP-corrupting instruction from trace
    if "trace" in report and "cpu" in report:
        sp_val = _parse_int(report["cpu"].get("sp", "0"))
        trace_entries = report["trace"].get("entries", [])
        report["sp_corruption_analysis"] = _analyze_trace_for_sp_corruption(trace_entries)


def _analyze_trace_for_sp_corruption(trace_entries: list) -> dict:
    """Walk backwards through trace to find where SP left $01xx page."""
    analysis = {
        "found": False,
        "corruption_instruction": None,
        "last_valid_sp": None,
        "first_corrupt_sp": None,
    }

    prev_sp = None
    for i, entry in enumerate(reversed(trace_entries)):
        sp = _parse_int(entry.get("sp", "0"))
        pc = entry.get("pc", "?")
        opcode = entry.get("opcode", "?")

        if sp <= SP_VALID_MAX and sp >= 0x0100:
            # This is the last instruction with valid SP
            if prev_sp is not None and (prev_sp > SP_VALID_MAX or prev_sp < 0x0100):
                analysis["found"] = True
                analysis["last_valid_sp"] = f"0x{sp:04X}"
                analysis["last_valid_pc"] = pc
                analysis["last_valid_opcode"] = opcode
                analysis["first_corrupt_sp"] = f"0x{prev_sp:04X}"
                # The NEXT instruction (in forward order) is the corruption point
                if i > 0:
                    corrupt_entry = trace_entries[len(trace_entries) - i]
                    analysis["corruption_instruction"] = {
                        "pc": corrupt_entry.get("pc", "?"),
                        "opcode": corrupt_entry.get("opcode", "?"),
                        "sp_after": f"0x{prev_sp:04X}",
                        "trace_index": len(trace_entries) - i,
                    }
                break
        prev_sp = sp

    return analysis


def run_repro(
    bridge: MesenBridge,
    slot: int = DEFAULT_SLOT,
    max_frames: int = DEFAULT_MAX_FRAMES,
    breakpoint_addr: int = CORRUPTION_PC,
    watch_depth: int = 500,
    strategy: str = "auto",
    press_a: bool = False,
) -> dict:
    """Execute the stack corruption repro workflow.

    Args:
        strategy: 'sp_range' for SP conditional breakpoint,
                  'tcs' for TCS breakpoint,
                  'polling' for frame-by-frame SP polling,
                  'breakpoint' for crash-site breakpoint only,
                  'auto' to try sp_range -> tcs -> breakpoint -> polling
    """
    report: dict = {
        "status": "no_repro",
        "strategy": strategy,
        "slot": slot,
        "max_frames": max_frames,
        "breakpoint_addr": f"0x{breakpoint_addr:06X}",
        "watch_addr": STACK_WATCH_START,
        "watch_size": STACK_WATCH_SIZE,
    }

    bp_ids = []

    # 1. Pause emulation
    bridge.send_command("PAUSE")

    # 2. Set up MEM_WATCH_WRITES on the stack region and on $7E1F0A (SP save location)
    watch_resp = bridge.send_command("MEM_WATCH_WRITES", action="add",
                             addr=STACK_WATCH_START,
                             size=str(STACK_WATCH_SIZE),
                             depth=str(watch_depth))
    watch_id = None
    if watch_resp.get("success"):
        watch_id = watch_resp["data"]["watch_id"]
        report["watch_id"] = watch_id
    else:
        print(f"Warning: MEM_WATCH setup failed: {watch_resp.get('error')}", file=sys.stderr)

    watch_id_1f0a = None
    watch_1f0a_resp = bridge.send_command("MEM_WATCH_WRITES", action="add",
                                          addr=SP_SAVE_ADDR,
                                          size=str(SP_SAVE_SIZE),
                                          depth=str(watch_depth))
    if watch_1f0a_resp.get("success"):
        watch_id_1f0a = watch_1f0a_resp["data"]["watch_id"]
        report["watch_id_1F0A"] = watch_id_1f0a
    else:
        print(f"Warning: MEM_WATCH $7E1F0A setup failed: {watch_1f0a_resp.get('error')}", file=sys.stderr)

    # 3. Set breakpoints based on strategy
    strategies_to_try = []
    if strategy == "auto":
        strategies_to_try = ["sp_range", "tcs", "breakpoint"]
    else:
        strategies_to_try = [strategy]

    active_strategy = None
    for strat in strategies_to_try:
        if strat == "sp_range":
            # Conditional breakpoint: SP >= 0x0200
            bp_resp = bridge.send_command("BREAKPOINT", action="add",
                                  addr="0x000000",
                                  condition="sp >= 0x0200",
                                  bptype="exec")
            if bp_resp.get("success") and "id" in bp_resp.get("data", {}):
                bp_ids.append(bp_resp["data"]["id"])
                active_strategy = "sp_range"
                print("Using SP-range conditional breakpoint (SP >= 0x0200)", file=sys.stderr)
                break
            print("SP-range conditional breakpoint not supported, trying next...", file=sys.stderr)

        elif strat == "tcs":
            # Breakpoint at each NMI TCS site
            tcs_set = False
            for tcs_addr in NMI_TCS_SITES:
                bp_resp = bridge.send_command("BREAKPOINT", action="add",
                                      addr=f"0x{tcs_addr:06X}",
                                      bptype="exec")
                if bp_resp.get("success") and "id" in bp_resp.get("data", {}):
                    bp_ids.append(bp_resp["data"]["id"])
                    tcs_set = True
            if tcs_set:
                active_strategy = "tcs"
                print(f"Using TCS breakpoints at NMI sites ({len(NMI_TCS_SITES)} sites)", file=sys.stderr)
                break
            print("TCS breakpoints failed, trying next...", file=sys.stderr)

        elif strat == "breakpoint":
            # Simple exec breakpoint at crash site
            bp_resp = bridge.send_command("BREAKPOINT", action="add",
                                  addr=f"0x{breakpoint_addr:06X}",
                                  bptype="exec")
            if bp_resp.get("success") and "id" in bp_resp.get("data", {}):
                bp_ids.append(bp_resp["data"]["id"])
                active_strategy = "breakpoint"
                print(f"Using crash-site breakpoint at 0x{breakpoint_addr:06X}", file=sys.stderr)
                break

    if active_strategy is None:
        active_strategy = "polling"
        print("All breakpoint strategies failed, using frame-by-frame SP polling", file=sys.stderr)

    report["active_strategy"] = active_strategy

    # 4. Enable P_WATCH to capture register state changes
    bridge.send_command("P_WATCH", action="start", depth="2000")

    # 5. Load save state
    load_resp = bridge.send_command("LOADSTATE", slot=str(slot))
    if not load_resp.get("success"):
        report["error"] = f"Failed to load state {slot}: {load_resp.get('error')}"
        return report

    # 6. Send A button to start the game
    if press_a:
        bridge.send_command("INPUT", buttons="A", frames="10")

    # 7. Run and monitor based on strategy
    if active_strategy == "polling":
        # Frame-by-frame SP polling (slowest but most reliable)
        _run_polling_strategy(bridge, report, max_frames)
    elif active_strategy == "tcs":
        # TCS breakpoint — need to check A register on each hit
        _run_tcs_strategy(bridge, report, max_frames)
    else:
        # sp_range or breakpoint — just wait for breakpoint hit
        _run_breakpoint_strategy(bridge, report, max_frames, breakpoint_addr, active_strategy)

    # 8. Pause if still running
    bridge.send_command("PAUSE")

    # 9. Capture full attribution data
    _capture_full_attribution(bridge, report, watch_id, watch_id_1f0a)

    # 10. Cleanup
    if watch_id is not None:
        bridge.send_command("MEM_WATCH_WRITES", action="remove", watch_id=str(watch_id))
    if watch_id_1f0a is not None:
        bridge.send_command("MEM_WATCH_WRITES", action="remove", watch_id=str(watch_id_1f0a))
    for bp_id in bp_ids:
        bridge.send_command("BREAKPOINT", action="remove", id=str(bp_id))
    bridge.send_command("P_WATCH", action="stop")
    bridge.send_command("RESUME")

    return report


def _run_breakpoint_strategy(bridge, report, max_frames, breakpoint_addr, strategy_name):
    """Wait for a breakpoint hit, checking periodically."""
    frames_elapsed = 0
    frame_batch = 30

    bridge.send_command("RESUME")

    while frames_elapsed < max_frames:
        time.sleep(frame_batch / 60.0)
        frames_elapsed += frame_batch

        state_resp = bridge.send_command("STATE")
        if not state_resp.get("success"):
            continue

        state = state_resp.get("data", {})
        if state.get("paused"):
            cpu_resp = bridge.send_command("CPU")
            if cpu_resp.get("success"):
                cpu = cpu_resp["data"]
                sp = _parse_int(cpu.get("sp", "0x01FF"))

                if _check_sp_corrupt(cpu):
                    report["status"] = "sp_corruption_detected"
                    report["detection_method"] = strategy_name
                    report["frames_to_repro"] = frames_elapsed
                    report["cpu"] = cpu
                    report["corrupt_sp"] = f"0x{sp:04X}"
                    print(f"SP corruption detected! SP=0x{sp:04X} at frame ~{frames_elapsed}", file=sys.stderr)
                    return

                pc_val = _parse_int(cpu.get("pc", "0"))
                if pc_val == breakpoint_addr:
                    report["status"] = "corruption_detected"
                    report["detection_method"] = "breakpoint_hit"
                    report["frames_to_repro"] = frames_elapsed
                    report["cpu"] = cpu
                    return

            # Not our target, resume
            bridge.send_command("RESUME")


def _run_tcs_strategy(bridge, report, max_frames):
    """Monitor TCS breakpoints, checking A register for bad values."""
    frames_elapsed = 0
    frame_batch = 10  # check more frequently for TCS hits
    tcs_hits = []

    bridge.send_command("RESUME")

    while frames_elapsed < max_frames:
        time.sleep(frame_batch / 60.0)
        frames_elapsed += frame_batch

        state_resp = bridge.send_command("STATE")
        if not state_resp.get("success"):
            continue

        state = state_resp.get("data", {})
        if state.get("paused"):
            cpu_resp = bridge.send_command("CPU")
            if cpu_resp.get("success"):
                cpu = cpu_resp["data"]
                pc_val = _parse_int(cpu.get("pc", "0"))
                a_val = _parse_int(cpu.get("a", "0"))
                sp_val = _parse_int(cpu.get("sp", "0"))

                # Check if A holds a bad SP value (would corrupt SP via TCS)
                if pc_val in NMI_TCS_SITES:
                    tcs_hit = {
                        "pc": f"0x{pc_val:06X}",
                        "a": f"0x{a_val:04X}",
                        "sp": f"0x{sp_val:04X}",
                        "frame": frames_elapsed,
                    }
                    tcs_hits.append(tcs_hit)

                    # But the NMI TCS loads from $1F0A, not A directly
                    # We need to read $7E1F0A to see what SP will become
                    mem_resp = bridge.send_command("READ_MEMORY", addr="0x7E1F0A", size="2")
                    if mem_resp.get("success"):
                        sp_new_bytes = mem_resp["data"].get("bytes", [])
                        if len(sp_new_bytes) >= 2:
                            sp_new = sp_new_bytes[0] | (sp_new_bytes[1] << 8)
                            tcs_hit["sp_from_1F0A"] = f"0x{sp_new:04X}"
                            if sp_new > SP_VALID_MAX or sp_new < 0x0100:
                                report["status"] = "sp_corruption_via_tcs"
                                report["detection_method"] = "tcs_bad_1F0A"
                                report["frames_to_repro"] = frames_elapsed
                                report["cpu"] = cpu
                                report["corrupt_sp_source"] = f"0x{sp_new:04X}"
                                report["tcs_hits"] = tcs_hits
                                print(f"SP corruption via TCS! $1F0A=0x{sp_new:04X} at frame ~{frames_elapsed}", file=sys.stderr)
                                return

                # Also check if SP is already corrupt
                if _check_sp_corrupt(cpu):
                    report["status"] = "sp_corruption_detected"
                    report["detection_method"] = "tcs_sp_check"
                    report["frames_to_repro"] = frames_elapsed
                    report["cpu"] = cpu
                    report["tcs_hits"] = tcs_hits
                    return

            bridge.send_command("RESUME")

    report["tcs_hits"] = tcs_hits


def _run_polling_strategy(bridge, report, max_frames):
    """Frame-by-frame SP polling (slowest but most reliable fallback)."""
    sp_history = []

    for frame in range(max_frames):
        # Advance exactly 1 frame
        bridge.send_command("FRAME", count="1")

        # Read CPU state
        cpu_resp = bridge.send_command("CPU")
        if not cpu_resp.get("success"):
            continue

        cpu = cpu_resp["data"]
        sp = _parse_int(cpu.get("sp", "0x01FF"))
        pc = _parse_int(cpu.get("pc", "0"))

        # Record SP history (keep last 100 for analysis)
        sp_history.append({
            "frame": frame,
            "sp": f"0x{sp:04X}",
            "pc": f"0x{pc:06X}",
        })
        if len(sp_history) > 100:
            sp_history.pop(0)

        # Check for SP corruption
        if sp > SP_VALID_MAX or sp < 0x0100:
            report["status"] = "sp_corruption_detected"
            report["detection_method"] = "sp_polling"
            report["frames_to_repro"] = frame
            report["cpu"] = cpu
            report["corrupt_sp"] = f"0x{sp:04X}"
            report["sp_history"] = sp_history
            print(f"SP corruption detected at frame {frame}! SP=0x{sp:04X}, PC=0x{pc:06X}", file=sys.stderr)

            # Pause and capture trace immediately
            bridge.send_command("PAUSE")
            return

    report["sp_history_tail"] = sp_history[-20:]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated stack corruption repro and attribution"
    )
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON report path (default: stdout)")
    parser.add_argument("--slot", type=int, default=DEFAULT_SLOT,
                        help=f"Save state slot to load (default: {DEFAULT_SLOT})")
    parser.add_argument("--press-a", action="store_true",
                        help="Press A after load (use for file-load dungeon freeze repro)")
    parser.add_argument("--frames", type=int, default=DEFAULT_MAX_FRAMES,
                        help=f"Max frames to wait (default: {DEFAULT_MAX_FRAMES})")
    parser.add_argument("--breakpoint", default=f"0x{CORRUPTION_PC:06X}",
                        help=f"Breakpoint address (default: 0x{CORRUPTION_PC:06X})")
    parser.add_argument("--depth", type=int, default=500,
                        help="Watch depth (max blame entries, default: 500)")
    parser.add_argument("--strategy", choices=["auto", "sp_range", "tcs", "breakpoint", "polling"],
                        default="auto",
                        help="Detection strategy (default: auto)")
    args = parser.parse_args()

    bp_addr = int(args.breakpoint.replace("0x", "").replace("0X", ""), 16)

    bridge = MesenBridge()
    if bridge.socket_path is None:
        print("Error: No Mesen2 instance found", file=sys.stderr)
        return 1

    # Verify connection
    ping = bridge.send_command("PING")
    if not ping.get("success"):
        print("Error: Cannot connect to Mesen2", file=sys.stderr)
        return 1

    print(f"Connected to Mesen2 at {bridge.socket_path}", file=sys.stderr)
    print(f"Strategy: {args.strategy}", file=sys.stderr)
    print(f"Loading state {args.slot}, watching {STACK_WATCH_START}+{STACK_WATCH_SIZE}", file=sys.stderr)
    print(f"Breakpoint at 0x{bp_addr:06X}, max {args.frames} frames", file=sys.stderr)

    report = run_repro(
        bridge,
        slot=args.slot,
        press_a=args.press_a,
        max_frames=args.frames,
        breakpoint_addr=bp_addr,
        watch_depth=args.depth,
        strategy=args.strategy,
    )

    output = json.dumps(report, indent=2)

    if args.output:
        Path(args.output).write_text(output + "\n")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    status = report["status"]
    if status in ("corruption_detected", "sp_corruption_detected", "sp_corruption_via_tcs"):
        frames = report.get("frames_to_repro", "?")
        method = report.get("detection_method", "?")
        print(f"\nCorruption detected after ~{frames} frames (method: {method})", file=sys.stderr)

        # Show SP corruption analysis
        sp_analysis = report.get("sp_corruption_analysis", {})
        if sp_analysis.get("found"):
            print(f"SP corruption instruction:", file=sys.stderr)
            ci = sp_analysis.get("corruption_instruction", {})
            print(f"  PC={ci.get('pc', '?')} opcode={ci.get('opcode', '?')} SP_after={ci.get('sp_after', '?')}", file=sys.stderr)
            print(f"  Last valid SP: {sp_analysis.get('last_valid_sp', '?')} at PC={sp_analysis.get('last_valid_pc', '?')}", file=sys.stderr)

        # Show blame entries
        blame_count = report.get("blame", {}).get("count", 0)
        print(f"Blame entries: {blame_count}", file=sys.stderr)
        if report.get("resolved_blame"):
            print("Top blame entries:", file=sys.stderr)
            for entry in report["resolved_blame"][:5]:
                sym = entry.get("symbol", {})
                label = sym.get("label", sym.get("name", "???"))
                print(f"  PC={entry['pc']} ({label})  opcode={entry.get('opcode', '??')}  sp={entry.get('sp', '??')}", file=sys.stderr)
        return 0
    else:
        print(f"\nNo corruption detected after {args.frames} frames (strategy: {report.get('active_strategy', '?')})", file=sys.stderr)
        blame_count = report.get("blame", {}).get("count", 0)
        if blame_count > 0:
            print(f"(Stack writes captured: {blame_count} - review for patterns)", file=sys.stderr)
        tcs_hits = report.get("tcs_hits", [])
        if tcs_hits:
            print(f"TCS hits observed: {len(tcs_hits)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
