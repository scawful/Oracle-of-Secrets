#!/usr/bin/env python3
"""Repro harness for dungeon transition blackouts (deterministic input + quick capture).

Goal: make the blackout bug easy to iterate on by:
  1) (optional) building a ROM with feature-flag overrides
  2) loading a known seed savestate slot/path
  3) injecting a simple input sequence (e.g., hold DOWN to take stairs)
  4) monitoring INIDISPQ/mode/frame for a hang/blank condition
  5) if detected: trigger the standard capture workflow

This does not try to navigate the world; it assumes the seed state is already
positioned "one action away" from the problematic transition.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# When running as `python3 scripts/foo.py`, sys.path[0] is `scripts/`, not the repo root,
# so `import scripts.*` fails unless we explicitly add the repo root.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ADDR_MODE = 0x7E0010
ADDR_SUBMODE = 0x7E0011
ADDR_INIDISPQ = 0x7E0013
ADDR_FRAME = 0x7E001A  # Optional debug read; do not use for progress/stall detection.
ADDR_MODE_CACHE = 0x7E010C
ADDR_ENTRANCE = 0x7E010E
ADDR_SONGQ = 0x7E0132
ADDR_LASTAPU0 = 0x7E0133
ADDR_SONGBANK = 0x7E0136
ADDR_APUIO0 = 0x002140
ADDR_APUIO1 = 0x002141
ADDR_APUIO2 = 0x002142
ADDR_APUIO3 = 0x002143

# If GameMode enters the 0x30+ range during normal play, we treat it as corruption.
# This is intentionally conservative to avoid false positives.
INVALID_MODE_MIN = 0x30
APU_SPIN_FULL_PC = 0x0088EC  # CMP $2140 ; BNE $0088EC (common hang signature)


def _run(cmd: list[str], *, cwd: Path, timeout_s: int | None = None) -> int:
    r = subprocess.run(cmd, cwd=cwd, timeout=timeout_s)
    return int(r.returncode)


def _launch_mesen2_instance(*, instance: str, rom_path: Path, home_dir: Path, headless: bool) -> int:
    cmd = [
        str(REPO_ROOT / "scripts" / "mesen2_launch_instance.sh"),
        "--instance",
        str(instance),
        "--source",
        "repro",
        "--title",
        str(instance),
        "--rom",
        str(rom_path),
        "--home",
        str(home_dir),
        "--no-state-set",
    ]
    if headless:
        cmd.append("--headless")
    return _run(cmd, cwd=REPO_ROOT, timeout_s=20)


def _csv(raw: str | None) -> str:
    return (raw or "").strip()


def _emit_report(path_arg: str | None, payload: dict) -> None:
    out_raw = (path_arg or "").strip()
    if not out_raw:
        return
    out_path = Path(out_raw).expanduser()
    if not out_path.is_absolute():
        out_path = (REPO_ROOT / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote report: {out_path}")


def build_rom(version: int, *, enable: str, disable: str, profile: str, persist_flags: bool) -> int:
    cmd = ["./scripts/build_rom.sh", str(version)]
    if profile and profile != "defaults":
        cmd += ["--profile", profile]
    if enable:
        cmd += ["--enable", enable]
    if disable:
        cmd += ["--disable", disable]
    if persist_flags:
        cmd += ["--persist-flags"]
    return _run(cmd, cwd=REPO_ROOT, timeout_s=240)


def main() -> int:
    ap = argparse.ArgumentParser(description="Repro dungeon transition blackout from a seed state.")
    ap.add_argument("--version", type=int, default=168, help="ROM version (default 168)")
    ap.add_argument("--build", action="store_true", help="Build ROM before running (supports --enable/--disable)")
    ap.add_argument(
        "--rom-load",
        action="store_true",
        help="After --build, hot-load the built ROM into the connected Mesen2 instance (LOADROM).",
    )
    ap.add_argument("--enable", default="", help="Comma-separated feature flags to enable (passed to build_rom.sh)")
    ap.add_argument("--disable", default="", help="Comma-separated feature flags to disable (passed to build_rom.sh)")
    ap.add_argument("--profile", default="defaults", help="Feature profile: defaults|all-on|all-off (passed to build_rom.sh)")
    ap.add_argument("--persist-flags", action="store_true", help="Persist generated Config/feature_flags.asm")

    ap.add_argument("--socket", default="", help="Mesen2 socket path override")
    ap.add_argument("--instance", default="", help="Mesen2 instance name (registry-backed)")
    ap.add_argument("--launch", action="store_true", help="Auto-launch an isolated Mesen2 instance if not connected")
    ap.add_argument("--launch-ui", action="store_true", help="Launch Mesen2 with UI (default is --headless)")
    ap.add_argument("--arm", action="store_true", help="Run agentic_autodebug arm before repro (p-watch/mem-watch)")

    seed = ap.add_mutually_exclusive_group(required=False)
    seed.add_argument("--lib", type=str, help="Seed state ID from the local state library manifest")
    seed.add_argument("--slot", type=int, default=20, help="Seed savestate slot (default 20)")
    seed.add_argument("--state", type=str, help="Seed savestate path (.mss)")

    ap.add_argument("--press", default="DOWN", help="Button(s) to press (default DOWN)")
    ap.add_argument("--press-frames", type=int, default=90, help="How many frames to hold the button (default 90)")
    ap.add_argument("--settle-frames", type=int, default=120, help="Frames to run after press to let transition start (default 120)")
    ap.add_argument("--max-frames", type=int, default=1200, help="Max frames to run while watching (default 1200)")
    ap.add_argument("--poll-every", type=int, default=10, help="Poll interval in frames (default 10)")

    ap.add_argument(
        "--capture-kind",
        default="repro",
        help="Capture kind label (passed to agentic_autodebug capture)",
    )
    ap.add_argument(
        "--capture-desc",
        default="transition blackout repro harness",
        help="Capture description (passed to agentic_autodebug capture)",
    )
    ap.add_argument(
        "--no-capture",
        action="store_true",
        help="Do not trigger agentic_autodebug capture when an anomaly is detected (still exits 1).",
    )
    ap.add_argument(
        "--report-out",
        default="",
        help="Optional JSON report output path (relative to repo root if not absolute).",
    )
    args = ap.parse_args()

    os.chdir(REPO_ROOT)

    if args.socket:
        os.environ["MESEN2_SOCKET_PATH"] = str(args.socket)
    if args.instance:
        os.environ["MESEN2_INSTANCE"] = str(args.instance)

    if args.build:
        rc = build_rom(
            int(args.version),
            enable=_csv(args.enable),
            disable=_csv(args.disable),
            profile=str(args.profile or "defaults"),
            persist_flags=bool(args.persist_flags),
        )
        if rc != 0:
            print("Build failed; aborting.", file=sys.stderr)
            return 2
    rom_path = (REPO_ROOT / "Roms" / f"oos{int(args.version)}x.sfc").resolve()

    try:
        from scripts.mesen2_client_lib.client import OracleDebugClient
    except Exception as exc:
        print(f"Failed to import mesen2 client lib: {exc}", file=sys.stderr)
        return 2

    client = OracleDebugClient()

    if not client.bridge.ensure_connected():
        if not args.launch:
            print("Mesen2 not connected (socket not found).", file=sys.stderr)
            return 125

        instance = str(args.instance or "oos-repro")
        rom_path = REPO_ROOT / "Roms" / f"oos{int(args.version)}x.sfc"
        if not rom_path.exists():
            print(f"ROM not found for launch: {rom_path} (run with --build, or pass --version matching existing ROM).", file=sys.stderr)
            return 2
        sock_path = f"/tmp/mesen2-{instance}.sock"
        os.environ["MESEN2_SOCKET_PATH"] = sock_path
        os.environ["MESEN2_INSTANCE"] = instance

        home_dir = (REPO_ROOT / ".cache" / "mesen2-instances" / instance).resolve()
        _launch_mesen2_instance(
            instance=instance,
            rom_path=rom_path,
            home_dir=home_dir,
            headless=not bool(args.launch_ui),
        )
        # Give the socket a moment to appear and respond.
        deadline = time.time() + 20.0
        while time.time() < deadline:
            if client.bridge.ensure_connected():
                break
            time.sleep(0.5)
        if not client.bridge.ensure_connected():
            print("Mesen2 still not connected after launch attempt.", file=sys.stderr)
            return 125

    if args.build and args.rom_load:
        if not rom_path.exists():
            print(f"Built ROM not found: {rom_path}", file=sys.stderr)
            return 2
        if not client.load_rom(str(rom_path)):
            print(f"ROM hot-load failed: {client.last_error}", file=sys.stderr)
            return 2
        # Give the ROM a moment to initialize before we load savestates.
        time.sleep(0.25)

    report: dict = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "version": int(args.version),
        "profile": str(args.profile or "defaults"),
        "enable": _csv(args.enable),
        "disable": _csv(args.disable),
        "instance": str(args.instance or ""),
        "socket": os.environ.get("MESEN2_SOCKET_PATH", ""),
        "seed": args.lib or args.state or f"slot:{int(args.slot)}",
        "press": str(args.press),
        "press_frames": int(args.press_frames),
        "settle_frames": int(args.settle_frames),
        "max_frames": int(args.max_frames),
        "poll_every": int(args.poll_every),
        "rom_path": str(rom_path),
    }

    # Load seed state
    if args.arm:
        arm_cmd = [sys.executable, "-m", "scripts.campaign.agentic_autodebug"]
        # Global args must appear before the subcommand for argparse.
        if os.environ.get("MESEN2_SOCKET_PATH"):
            arm_cmd += ["--socket", os.environ["MESEN2_SOCKET_PATH"]]
        elif args.instance:
            arm_cmd += ["--instance", str(args.instance)]
        arm_cmd += ["arm"]
        _run(arm_cmd, cwd=REPO_ROOT, timeout_s=30)

    if args.lib:
        ok = client.load_library_state(str(args.lib))
    elif args.state:
        state_path = Path(str(args.state)).expanduser()
        if not state_path.is_absolute():
            state_path = (REPO_ROOT / state_path).resolve()
        report["seed"] = str(state_path)
        ok = client.load_state(path=str(state_path))
    else:
        ok = client.load_state(slot=int(args.slot))
    if not ok:
        seed_desc = args.lib or args.state or f"slot {args.slot}"
        print(f"Failed to load seed state ({seed_desc}).", file=sys.stderr)
        return 125

    # Nudge a couple frames so the engine can settle after load.
    client.bridge.run_frames(count=2)

    # Input sequence to trigger the transition.
    # Do not require "running" here; the socket server may keep the emulator paused
    # while still allowing frame-stepping.
    ok = client.press_button(str(args.press), frames=int(args.press_frames), ensure_running=False)
    if not ok:
        print(f"Input injection failed: {client.last_error}", file=sys.stderr)
        return 2
    client.bridge.run_frames(count=int(args.settle_frames))

    # Watch loop
    stall = 0
    forced_blank_ticks = 0
    brightness0_ticks = 0
    apu_spin_ticks = 0
    invalid_mode_ticks = 0
    last_cycles = None

    for t in range(0, int(args.max_frames), max(1, int(args.poll_every))):
        step_n = max(1, int(args.poll_every))
        cyc0 = client.get_cpu_state().get("CYC")
        if not client.bridge.run_frames(count=step_n):
            print("Anomaly detected: failed to advance emulator frames; triggering capture...")
            snapshot = {
                "pc": client.get_pc().get("full"),
                "mode": client.bridge.read_memory(ADDR_MODE),
                "submode": client.bridge.read_memory(ADDR_SUBMODE),
                "inidispq": client.bridge.read_memory(ADDR_INIDISPQ),
                "songq": client.bridge.read_memory(ADDR_SONGQ),
                "songbank": client.bridge.read_memory(ADDR_SONGBANK),
                "mode_cache": client.bridge.read_memory(ADDR_MODE_CACHE),
                "entrance": client.bridge.read_memory(ADDR_ENTRANCE),
                "apuio0": client.bridge.read_memory(ADDR_APUIO0),
                "apuio1": client.bridge.read_memory(ADDR_APUIO1),
                "apuio2": client.bridge.read_memory(ADDR_APUIO2),
                "apuio3": client.bridge.read_memory(ADDR_APUIO3),
            }
            report["result"] = "anomaly"
            report["reason"] = "run_frames_failed"
            report["snapshot"] = snapshot
            if not args.no_capture:
                _run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.campaign.agentic_autodebug",
                        "capture",
                        "--kind",
                        str(args.capture_kind),
                        "--desc",
                        str(args.capture_desc),
                    ],
                    cwd=REPO_ROOT,
                    timeout_s=60,
                )
                _run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.campaign.agentic_autodebug",
                        "triage",
                        "--latest",
                    ],
                    cwd=REPO_ROOT,
                    timeout_s=30,
                )
            _emit_report(args.report_out, report)
            return 1

        cyc1 = client.get_cpu_state().get("CYC")
        if cyc0 is not None and cyc1 is not None:
            progressed = int(cyc1) != int(cyc0)
        else:
            progressed = True

        if not progressed:
            stall += 1
        else:
            stall = 0

        mode = client.bridge.read_memory(ADDR_MODE)
        submode = client.bridge.read_memory(ADDR_SUBMODE)
        inidispq = client.bridge.read_memory(ADDR_INIDISPQ)
        wram_frame = client.bridge.read_memory(ADDR_FRAME)
        pc_full = client.get_pc().get("full")
        songq = client.bridge.read_memory(ADDR_SONGQ)
        last_apu0 = client.bridge.read_memory(ADDR_LASTAPU0)
        songbank = client.bridge.read_memory(ADDR_SONGBANK)
        mode_cache = client.bridge.read_memory(ADDR_MODE_CACHE)
        entrance = client.bridge.read_memory(ADDR_ENTRANCE)
        apuio0 = client.bridge.read_memory(ADDR_APUIO0)
        apuio1 = client.bridge.read_memory(ADDR_APUIO1)
        apuio2 = client.bridge.read_memory(ADDR_APUIO2)
        apuio3 = client.bridge.read_memory(ADDR_APUIO3)

        # "Forced blank" inidispq persists outside the brief transition window.
        if (inidispq & 0x80) != 0 and mode in (0x06, 0x07, 0x09):
            forced_blank_ticks += 1
        else:
            forced_blank_ticks = 0

        # Brightness 0 (black screen without forced blank). Be conservative:
        # only count it when we're back in submode 0 (normal play), to avoid
        # false positives during fades.
        if (inidispq & 0x0F) == 0 and (inidispq & 0x80) == 0 and mode in (0x07, 0x09) and submode == 0:
            brightness0_ticks += 1
        else:
            brightness0_ticks = 0

        # APU spin loop: emulator is alive but the game is wedged.
        if pc_full == APU_SPIN_FULL_PC:
            apu_spin_ticks += 1
        else:
            apu_spin_ticks = 0

        # Invalid mode detection (common corruption signature).
        if mode >= INVALID_MODE_MIN:
            invalid_mode_ticks += 1
        else:
            invalid_mode_ticks = 0

        # Optional stall diagnostic: CPU cycle counter didn't advance across our step window.
        # This indicates the socket server isn't actually executing frames/instructions.
        last_cycles = cyc1

        print(
            f"t={t:4d} mode=0x{mode:02X} sub=0x{submode:02X} inidispq=0x{inidispq:02X} "
            f"wram_frame={wram_frame:3d} pc=0x{(pc_full or 0):06X} cyc={cyc1}"
        )

        # Trip conditions: either we are forced-blanked too long, or main loop is stalled.
        if forced_blank_ticks >= 12 or brightness0_ticks >= 12 or stall >= 12 or apu_spin_ticks >= 6 or invalid_mode_ticks >= 3:
            reasons: list[str] = []
            if forced_blank_ticks >= 12:
                reasons.append("forced_blank")
            if brightness0_ticks >= 12:
                reasons.append("brightness_zero")
            if stall >= 12:
                reasons.append("cpu_stall")
            if apu_spin_ticks >= 6:
                reasons.append("apu_spin_0088EC")
            if invalid_mode_ticks >= 3:
                reasons.append("invalid_mode")
            report["result"] = "anomaly"
            report["reason"] = ",".join(reasons) if reasons else "unknown"
            report["snapshot"] = {
                "t": int(t),
                "pc": int(pc_full or 0),
                "mode": int(mode),
                "submode": int(submode),
                "mode_cache": int(mode_cache),
                "entrance": int(entrance),
                "inidispq": int(inidispq),
                "wram_frame": int(wram_frame),
                "songq": int(songq),
                "last_apu0": int(last_apu0),
                "songbank": int(songbank),
                "apuio0": int(apuio0),
                "apuio1": int(apuio1),
                "apuio2": int(apuio2),
                "apuio3": int(apuio3),
                "forced_blank_ticks": int(forced_blank_ticks),
                "brightness0_ticks": int(brightness0_ticks),
                "stall_ticks": int(stall),
                "apu_spin_ticks": int(apu_spin_ticks),
                "invalid_mode_ticks": int(invalid_mode_ticks),
                "cycles": int(cyc1 or 0),
            }
            print("Anomaly detected; triggering capture...")
            if not args.no_capture:
                # Use the shared capture tool (more complete forensics).
                _run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.campaign.agentic_autodebug",
                        "capture",
                        "--kind",
                        str(args.capture_kind),
                        "--desc",
                        str(args.capture_desc),
                    ],
                    cwd=REPO_ROOT,
                    timeout_s=60,
                )
                _run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.campaign.agentic_autodebug",
                        "triage",
                        "--latest",
                    ],
                    cwd=REPO_ROOT,
                    timeout_s=30,
                )
            _emit_report(args.report_out, report)
            return 1

    print("No anomaly detected in window.")
    report["result"] = "ok"
    report["snapshot"] = {
        "pc": int(client.get_pc().get("full") or 0),
        "mode": int(client.bridge.read_memory(ADDR_MODE)),
        "submode": int(client.bridge.read_memory(ADDR_SUBMODE)),
        "mode_cache": int(client.bridge.read_memory(ADDR_MODE_CACHE)),
        "entrance": int(client.bridge.read_memory(ADDR_ENTRANCE)),
        "inidispq": int(client.bridge.read_memory(ADDR_INIDISPQ)),
        "songq": int(client.bridge.read_memory(ADDR_SONGQ)),
        "last_apu0": int(client.bridge.read_memory(ADDR_LASTAPU0)),
        "songbank": int(client.bridge.read_memory(ADDR_SONGBANK)),
        "apuio0": int(client.bridge.read_memory(ADDR_APUIO0)),
        "apuio1": int(client.bridge.read_memory(ADDR_APUIO1)),
        "apuio2": int(client.bridge.read_memory(ADDR_APUIO2)),
        "apuio3": int(client.bridge.read_memory(ADDR_APUIO3)),
    }
    _emit_report(args.report_out, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
