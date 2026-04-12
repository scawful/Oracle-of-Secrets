#!/usr/bin/env python3
"""
Dungeon Transition Blackout Capture Script

This script automates the Phase 1 evidence capture workflow from the
dungeon_transition_blackout diagnosis plan. Run this immediately after
reproducing the blackout (do NOT reset the emulator first).

Usage:
    # Before reproducing, arm instrumentation:
    python3 capture_blackout.py arm --save-seed

    # Optional: also assert JumpTableLocal is entered with X/Y=8-bit.
    # If the assert triggers, capture immediately (no need to reach the blackout).
    python3 capture_blackout.py arm --save-seed --assert-jtl

    # After blackout occurs (do NOT reset):
    python3 capture_blackout.py capture

    # To review captured artifacts:
    python3 capture_blackout.py summary
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configuration
MESEN2_CLIENT = Path(__file__).parent / "mesen2_client.py"
OUTPUT_DIR = Path("/tmp/oos_blackout")
LAST_CAPTURE_MARKER = Path(__file__).resolve().parents[1] / "scratchpad" / "last_blackout_capture.json"
REPRO_SLOT = 20
CAPTURE_SLOT = 21

_MESEN2_GLOBAL_ARGS: list[str] = []

# Memory addresses to watch (base set)
WATCH_ADDRS_BASE: list[tuple[str, int, str]] = [
    ("0x7E0013", 1, "INIDISP queue (INIDISPQ)"),
    ("0x7E001A", 1, "Frame counter (FRAME)"),
    ("0x7E0010", 1, "GameMode"),
    ("0x7E0011", 1, "SubMode"),
    ("0x7E00A0", 1, "Room layout index"),
    ("0x7E00A4", 2, "Room ID (16-bit)"),
    ("0x7E009B", 1, "HDMA enable queue (HDMAENQ)"),
]

# Optional deeper instrumentation (fade state + color math + stack)
WATCH_ADDRS_DEEP: list[tuple[str, int, str]] = [
    ("0x7EC005", 2, "RMFADE/RMFADE2 (room fade flags)"),
    ("0x7EC007", 2, "FADETIME (transition fade timer)"),
    ("0x7EC009", 2, "RMFADEDIR (fade direction)"),
    ("0x7EC00B", 2, "FADETGT (target fade level)"),
    ("0x7EC011", 2, "MOSAICLEVEL (mosaic level)"),
    ("0x7EC017", 2, "DARKNESS (room darkness level)"),
    ("0x7E044A", 2, "EGSTR (layer interaction / darkness behavior)"),
    ("0x7E0458", 2, "DARKLAMP (lamp-in-dark-room flag)"),
    ("0x7E045A", 2, "LIGHT (torches lit count)"),
    ("0x7E067C", 2, "IRISTOP (spotlight HDMA top)"),
    ("0x7E067E", 2, "IRISTYPE (spotlight type)"),
    ("0x7E009A", 1, "Color math ($9A)"),
    ("0x7E009C", 1, "Color math ($9C)"),
    ("0x7E009D", 1, "Color math ($9D)"),
    ("0x7E01FC", 3, "Stack page tail ($01FC-$01FE)"),
    ("0x7E1F0A", 2, "NMI SP save ($1F0A)"),
]

JUMPTABLELOCAL_ADDR = "0x008781"  # JumpTableLocal
JUMPTABLELOCAL_XFLAG = "0x10"  # P bit 0x10 set => X/Y are 8-bit

def run_mesen_cmd(*args, json_output=False):
    """Run a mesen2_client.py command and return output."""
    cmd = [sys.executable, str(MESEN2_CLIENT)] + _MESEN2_GLOBAL_ARGS + list(args)
    if json_output:
        cmd.append("--json")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"  [WARN] Command failed: {' '.join(args)}")
            print(f"         stderr: {result.stderr.strip()}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"  [WARN] Command timed out: {' '.join(args)}")
        return None
    except FileNotFoundError:
        print(f"  [ERROR] mesen2_client.py not found at {MESEN2_CLIENT}")
        sys.exit(1)


def _parse_hexbytes(hexstr: str) -> bytes:
    raw = (hexstr or "").strip()
    if raw.startswith(("0x", "0X")):
        raw = raw[2:]
    raw = raw.replace(" ", "").replace("\n", "").replace("\t", "")
    if len(raw) % 2 != 0:
        raw = "0" + raw
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return b""


def _read_values(addrs: list[tuple[str, int, str]]) -> dict:
    values: dict[str, dict] = {}
    for addr, size, desc in addrs:
        out = run_mesen_cmd("mem-read", "--len", str(size), addr, json_output=True)
        if not out:
            values[addr] = {"desc": desc, "size": size, "ok": False}
            continue
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            values[addr] = {"desc": desc, "size": size, "ok": False, "raw": out}
            continue
        b = _parse_hexbytes(payload.get("bytes", ""))
        values[addr] = {
            "desc": desc,
            "size": size,
            "ok": True,
            "bytes": payload.get("bytes"),
            "value_le": int.from_bytes(b, "little") if b else None,
        }
    return values


def _summarize_blame(blame_res: dict) -> dict:
    """Extract most-recent writer info from MEM_BLAME response (best-effort)."""
    if not isinstance(blame_res, dict):
        return {"ok": False}

    data = blame_res.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = None

    writes = None
    if isinstance(data, dict):
        writes = data.get("writes")
    if not isinstance(writes, list):
        writes = []

    last = writes[0] if writes else None
    return {
        "ok": bool(blame_res.get("success")),
        "writes": writes,
        "last": last,
    }


def cmd_arm(args):
    """Arm instrumentation before reproducing the bug."""
    print("=== Arming Blackout Capture Instrumentation ===")
    print()

    # Check connection
    print("1. Checking Mesen2 connection...")
    health = run_mesen_cmd("health")
    if health is None or "error" in health.lower():
        print("   [ERROR] Cannot connect to Mesen2. Is it running?")
        print("   Set MESEN2_SOCKET_PATH if you have multiple instances.")
        return 1
    print(f"   OK: {health}")
    print()

    # Start P-watch
    print("2. Starting P-watch (P-register history)...")
    run_mesen_cmd("p-watch", "start", "--depth", "8000")
    print("   OK")
    print()

    # Start trace logging so TRACE fetch has data.
    print("3. Starting TRACE logging...")
    run_mesen_cmd("trace", "--action", "start", "--clear")
    print("   OK")
    print()

    # Optional: assert JumpTableLocal index-width contract (X/Y must be 8-bit on entry).
    if args.assert_jtl:
        print("4. Arming JumpTableLocal (0x008781) X/Y width assert (require X/Y=8-bit)...")
        out = run_mesen_cmd(
            "p-assert",
            JUMPTABLELOCAL_ADDR,
            JUMPTABLELOCAL_XFLAG,
            "--mask",
            JUMPTABLELOCAL_XFLAG,
            json_output=True,
        )
        if out:
            try:
                payload = json.loads(out)
                data = payload.get("data") if isinstance(payload, dict) else None
                assert_id = data.get("id") if isinstance(data, dict) else None
                if assert_id is not None:
                    print(f"   OK (id={assert_id})")
                else:
                    print("   OK")
            except json.JSONDecodeError:
                print("   OK")
        print()

    # Add memory watches
    watch_addrs = list(WATCH_ADDRS_BASE)
    if args.deep:
        watch_addrs.extend(WATCH_ADDRS_DEEP)

    print("5. Adding memory watches...")
    for addr, size, desc in watch_addrs:
        if size != 1:
            run_mesen_cmd("mem-watch", "add", "--depth", "4000", "--size", str(size), addr)
        else:
            run_mesen_cmd("mem-watch", "add", "--depth", "4000", addr)
        print(f"   - {addr}: {desc}")
    print()

    # Create repro seed state
    if args.save_seed:
        print(f"6. Saving repro seed state (slot {REPRO_SLOT})...")
        run_mesen_cmd("smart-save", str(REPRO_SLOT))
        run_mesen_cmd("lib-save", "Blackout repro seed", "-t", "dungeon", "-t", "blackout", "-t", "repro")
        print("   OK")
    else:
        print("6. Skipping seed save (use --save-seed to create one)")
    print()

    print("=== Instrumentation Armed ===")
    if args.assert_jtl:
        print("If the JumpTableLocal assert triggers, capture immediately (no need to reach the blackout):")
        print(f"    python3 {Path(__file__).name} capture")
        print()
    print("Otherwise, reproduce the blackout. When it happens, immediately run:")
    print(f"    python3 {Path(__file__).name} capture")
    return 0


def cmd_capture(args):
    """Capture evidence immediately after blackout occurs."""
    print("=== Capturing Blackout Evidence ===")
    print()

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_DIR / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    print()

    # Write a repo-local marker so other tools/agents can find the latest capture
    # without copying paths around.
    try:
        LAST_CAPTURE_MARKER.parent.mkdir(parents=True, exist_ok=True)
        LAST_CAPTURE_MARKER.write_text(
            json.dumps({"timestamp": timestamp, "path": str(output_dir)}, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass

    # Save failure state
    print(f"1. Saving failure state (slot {CAPTURE_SLOT})...")
    run_mesen_cmd("smart-save", str(CAPTURE_SLOT))
    run_mesen_cmd("savestate-label", "set", str(CAPTURE_SLOT), "--label", "blackout")
    print("   OK")
    print()

    # Capture CPU state
    print("2. Capturing CPU state...")
    cpu_out = run_mesen_cmd("cpu", json_output=True)
    if cpu_out:
        (output_dir / "cpu.json").write_text(cpu_out)
        print("   OK: cpu.json")
    print()

    # Capture stack
    print("3. Capturing stack trace...")
    stack_out = run_mesen_cmd("stack-retaddr", "--count", "12", json_output=True)
    if stack_out:
        (output_dir / "stack.json").write_text(stack_out)
        print("   OK: stack.json")
    print()

    # Capture P-log
    print("4. Capturing P-log (P-register history)...")
    plog_out = run_mesen_cmd("p-log", "--count", "200", json_output=True)
    if plog_out:
        (output_dir / "p_log.json").write_text(plog_out)
        print("   OK: p_log.json")
    print()

    # Capture current values (mem-read)
    watch_addrs = list(WATCH_ADDRS_BASE)
    if args.deep:
        watch_addrs.extend(WATCH_ADDRS_DEEP)

    print("5. Capturing key RAM values (mem-read)...")
    values = _read_values(watch_addrs)
    (output_dir / "values.json").write_text(json.dumps(values, indent=2))
    print("   OK: values.json")
    print()

    # Capture mem-blame for key addresses
    print("6. Capturing mem-blame for key addresses...")
    blame_addrs = [
        ("0x7E0013", "inidispq"),
        ("0x7E001A", "frame"),
        ("0x7E0010", "mode"),
        ("0x7E0011", "submode"),
        ("0x7E00A0", "room_layout"),
        ("0x7E00A4", "room_id"),
    ]
    if args.deep:
        blame_addrs.extend([
            ("0x7EC005", "rmfade"),
            ("0x7EC007", "fadetime"),
            ("0x7EC00B", "fadetgt"),
            ("0x7E009B", "hdmaenq"),
            ("0x7EC017", "darkness"),
            ("0x7E0458", "darklamp"),
            ("0x7E045A", "light"),
            ("0x7E067E", "iristype"),
            ("0x7E01FC", "stack_tail"),
            ("0x7E1F0A", "sp_save"),
        ])
    for addr, name in blame_addrs:
        blame_out = run_mesen_cmd("mem-blame", "--addr", addr, json_output=True)
        if blame_out:
            (output_dir / f"blame_{name}.json").write_text(blame_out)
            print(f"   OK: blame_{name}.json")
    print()

    # Capture disassembly
    print("7. Capturing disassembly around PC...")
    disasm_out = run_mesen_cmd("disasm", "--count", "40", json_output=True)
    if disasm_out:
        (output_dir / "disasm.json").write_text(disasm_out)
        print("   OK: disasm.json")
    print()

    # Capture trace
    print("8. Capturing recent trace...")
    trace_out = run_mesen_cmd("trace", "--count", "100", json_output=True)
    if trace_out:
        (output_dir / "trace.json").write_text(trace_out)
        print("   OK: trace.json")
    print()

    # Quick summary
    print("=== Capture Complete ===")
    print(f"Artifacts saved to: {output_dir}")
    print()
    print("Quick analysis:")
    if cpu_out:
        try:
            cpu = json.loads(cpu_out)
            pc = cpu.get("PC", cpu.get("pc", "unknown"))
            p = cpu.get("P", cpu.get("p", "unknown"))
            print(f"  PC: ${pc:06X}" if isinstance(pc, int) else f"  PC: {pc}")
            print(f"  P:  ${p:02X}" if isinstance(p, int) else f"  P:  {p}")
        except json.JSONDecodeError:
            print("  (Could not parse CPU state)")

    # Key values
    try:
        frame = (values.get("0x7E001A") or {}).get("value_le")
        inidispq = (values.get("0x7E0013") or {}).get("value_le")
        mode = (values.get("0x7E0010") or {}).get("value_le")
        submode = (values.get("0x7E0011") or {}).get("value_le")
        room_id = (values.get("0x7E00A4") or {}).get("value_le")

        if isinstance(mode, int):
            print(f"  Mode:   ${mode:02X}")
        if isinstance(submode, int):
            print(f"  Sub:    ${submode:02X}")
        if isinstance(room_id, int):
            print(f"  RoomID: ${room_id:04X}")
        if isinstance(inidispq, int):
            print(f"  INIDISPQ: ${inidispq:02X}")
            if (inidispq & 0x80) != 0:
                print("    ^ Forced blank bit set (0x80).")
            elif (inidispq & 0x0F) == 0:
                print("    ^ Brightness is 0 (screen black without forced blank).")
        if isinstance(frame, int):
            print(f"  Frame:  {frame}")
    except Exception:
        pass

    # Last INIDISPQ writer (MEM_BLAME)
    inidispq_blame_path = output_dir / "blame_inidispq.json"
    if inidispq_blame_path.exists():
        try:
            blame_res = json.loads(inidispq_blame_path.read_text())
            summary = _summarize_blame(blame_res)
            last = summary.get("last") if isinstance(summary, dict) else None
            if isinstance(last, dict):
                print(
                    "  Last INIDISPQ write: "
                    f"pc={last.get('pc')} value={last.get('value')} opcode={last.get('opcode')} sp={last.get('sp')}"
                )
        except json.JSONDecodeError:
            pass

    return 0


def cmd_summary(args):
    """Summarize captured artifacts."""
    print("=== Blackout Capture Summary ===")
    print()

    if not OUTPUT_DIR.exists():
        print(f"No captures found at {OUTPUT_DIR}")
        return 1

    if LAST_CAPTURE_MARKER.exists():
        try:
            meta = json.loads(LAST_CAPTURE_MARKER.read_text(encoding="utf-8"))
            p = meta.get("path")
            if p:
                print(f"Last capture marker: {p}")
                print()
        except Exception:
            pass

    captures = sorted(OUTPUT_DIR.iterdir(), reverse=True)
    if not captures:
        print("No captures found.")
        return 1

    for capture_dir in captures[:5]:  # Show last 5
        if not capture_dir.is_dir():
            continue
        print(f"Capture: {capture_dir.name}")

        # Best-effort one-line summary.
        try:
            pc = None
            cpu_path = capture_dir / "cpu.json"
            if cpu_path.exists():
                cpu = json.loads(cpu_path.read_text())
                pc = cpu.get("PC") or cpu.get("pc")

            frame = None
            inidispq = None
            mode = None
            submode = None
            room_id = None
            values_path = capture_dir / "values.json"
            if values_path.exists():
                vals = json.loads(values_path.read_text())
                frame = (vals.get("0x7E001A") or {}).get("value_le")
                inidispq = (vals.get("0x7E0013") or {}).get("value_le")
                mode = (vals.get("0x7E0010") or {}).get("value_le")
                submode = (vals.get("0x7E0011") or {}).get("value_le")
                room_id = (vals.get("0x7E00A4") or {}).get("value_le")

            bits = []
            if isinstance(pc, int):
                bits.append(f"PC=${pc:06X}")
            elif pc:
                bits.append(f"PC={pc}")
            if isinstance(mode, int):
                bits.append(f"Mode=${mode:02X}")
            if isinstance(submode, int):
                bits.append(f"Sub=${submode:02X}")
            if isinstance(inidispq, int):
                bits.append(f"INIDISPQ=${inidispq:02X}")
            if isinstance(frame, int):
                bits.append(f"Frame={frame}")
            if isinstance(room_id, int):
                bits.append(f"RoomID=${room_id:04X}")
            if bits:
                print(f"  {' | '.join(bits)}")
        except Exception:
            pass

        files = sorted([p.name for p in capture_dir.glob("*.json")])
        print(f"  Files: {len(files)}")
        for name in files:
            print(f"    - {name}")
        print()

    return 0


def main():
    parser = argparse.ArgumentParser(description="Dungeon Transition Blackout Capture Tool")
    parser.add_argument("--socket", help="Target Mesen2 socket path (optional; overrides auto-discovery)")
    parser.add_argument("--instance", help="Target Mesen2 registry instance name (optional)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # arm subcommand
    arm_parser = subparsers.add_parser("arm", help="Arm instrumentation before reproducing")
    arm_parser.add_argument("--save-seed", action="store_true", help="Save a repro seed state")
    arm_parser.add_argument("--deep", action="store_true", help="Add extra watches (fade + stack + color math)")
    arm_parser.add_argument(
        "--assert-jtl",
        action="store_true",
        help="Assert JumpTableLocal is entered with X/Y=8-bit (breaks on violation)",
    )

    # capture subcommand
    capture_parser = subparsers.add_parser("capture", help="Capture evidence after blackout")
    capture_parser.add_argument("--deep", action="store_true", help="Capture extra watches (fade + stack + color math)")

    # summary subcommand
    summary_parser = subparsers.add_parser("summary", help="Summarize captured artifacts")

    args = parser.parse_args()

    global _MESEN2_GLOBAL_ARGS
    if args.socket:
        _MESEN2_GLOBAL_ARGS += ["--socket", args.socket]
    if args.instance:
        _MESEN2_GLOBAL_ARGS += ["--instance", args.instance]

    if args.command == "arm":
        return cmd_arm(args)
    elif args.command == "capture":
        return cmd_capture(args)
    elif args.command == "summary":
        return cmd_summary(args)


if __name__ == "__main__":
    sys.exit(main())
