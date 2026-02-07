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
ADDR_FRAME = 0x7E001A


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
    ]
    if headless:
        cmd.append("--headless")
    return _run(cmd, cwd=REPO_ROOT, timeout_s=20)


def _csv(raw: str | None) -> str:
    return (raw or "").strip()


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
        # Give the socket a moment to appear.
        time.sleep(0.5)
        if not client.bridge.ensure_connected():
            print("Mesen2 still not connected after launch attempt.", file=sys.stderr)
            return 125

    # Load seed state
    if args.arm:
        arm_cmd = [
            sys.executable,
            "-m",
            "scripts.campaign.agentic_autodebug",
            "arm",
        ]
        if os.environ.get("MESEN2_SOCKET_PATH"):
            arm_cmd += ["--socket", os.environ["MESEN2_SOCKET_PATH"]]
        elif args.instance:
            arm_cmd += ["--instance", str(args.instance)]
        _run(arm_cmd, cwd=REPO_ROOT, timeout_s=30)

    if args.lib:
        ok = client.load_library_state(str(args.lib))
    elif args.state:
        ok = client.load_state(path=args.state)
    else:
        ok = client.load_state(slot=int(args.slot))
    if not ok:
        seed_desc = args.lib or args.state or f"slot {args.slot}"
        print(f"Failed to load seed state ({seed_desc}).", file=sys.stderr)
        return 125

    # Ensure running
    client.bridge.resume()
    time.sleep(0.05)

    # Input sequence to trigger the transition.
    client.press_button(str(args.press), frames=int(args.press_frames), ensure_running=True)
    client.bridge.run_frames(count=int(args.settle_frames))

    # Watch loop
    last_frame = None
    stall = 0
    forced_blank_ticks = 0

    for t in range(0, int(args.max_frames), max(1, int(args.poll_every))):
        client.bridge.run_frames(count=max(1, int(args.poll_every)))
        mode = client.bridge.read_memory(ADDR_MODE)
        submode = client.bridge.read_memory(ADDR_SUBMODE)
        inidispq = client.bridge.read_memory(ADDR_INIDISPQ)
        frame = client.bridge.read_memory(ADDR_FRAME)

        # "Forced blank" inidispq persists outside the brief transition window.
        if (inidispq & 0x80) != 0 and mode in (0x06, 0x07, 0x09):
            forced_blank_ticks += 1
        else:
            forced_blank_ticks = 0

        # Frame stall detection (main loop not advancing).
        if last_frame is None:
            last_frame = frame
            stall = 0
        else:
            if frame == last_frame and mode != 0x00:
                stall += 1
            else:
                stall = 0
                last_frame = frame

        print(f"t={t:4d} mode=0x{mode:02X} sub=0x{submode:02X} inidispq=0x{inidispq:02X} frame={frame:3d}")

        # Trip conditions: either we are forced-blanked too long, or main loop is stalled.
        if forced_blank_ticks >= 12 or stall >= 12:
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
            return 1

    print("No anomaly detected in window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
