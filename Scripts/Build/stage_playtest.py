#!/usr/bin/env python3
"""Stage a playtest build under its version name.

Versions come from Config/version.json ({"version": "0.9.0", "build": 12});
the in-game line (message $C7) is stamped by Scripts/Build/version_stamp.py
during build_rom.sh. The integrator bumps the build number before building a
playtest ROM, builds, then stages it:

  python3 Scripts/Build/stage_playtest.py bump            # build 12 -> 13
  ./Scripts/Build/build_rom.sh 168 --enable ...           # in an isolated copy
  python3 Scripts/Build/stage_playtest.py stage --from <copy>/Roms \
      --notes NOTES.md --flags feature_flags_used.asm

Output in Roms/Playtest/ (Roms/ is not committed):
  oos-v<version>-b<build>.sfc/.sym/.mlb/.hooks.json/.flags.asm/.md
  latest.json   name, SHA-256, version, build, staged time
  oos-play.sfc  copy of the latest ROM under a fixed name, so an emulator
                keyed on the ROM filename keeps one save (oos-play.srm)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO_ROOT / "Config" / "version.json"
PLAYTEST_DIR = REPO_ROOT / "Roms" / "Playtest"


def load_version() -> dict:
    return json.loads(VERSION_FILE.read_text())


def build_name(info: dict) -> str:
    return f"oos-v{info['version']}-b{info['build']}"


def cmd_bump(_args: argparse.Namespace) -> int:
    info = load_version()
    info["build"] = int(info["build"]) + 1
    VERSION_FILE.write_text(json.dumps(info, indent=2) + "\n")
    print(f"version: {build_name(info)}")
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    info = load_version()
    name = build_name(info)
    src = args.from_dir
    rom = src / "oos168x.sfc"
    if not rom.is_file():
        raise SystemExit(f"stage_playtest: {rom} not found")

    # The ROM must carry this version in message $C7.
    check = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Scripts/Build/version_stamp.py"), "--rom", str(rom), "--check"],
        capture_output=True, text=True, check=True).stdout
    # "... N bytes: <old> -> <new> (vX-bN)": stamped when old == new.
    old = check.split("bytes:", 1)[1].split("->")[0].split()
    new = check.split("->", 1)[1].split("(")[0].split()
    if old != new:
        raise SystemExit(f"stage_playtest: {rom} is not stamped {name[4:]}; rebuild after bump.\n{check}")

    PLAYTEST_DIR.mkdir(parents=True, exist_ok=True)
    dest = PLAYTEST_DIR / f"{name}.sfc"
    if dest.exists() and not args.force:
        raise SystemExit(f"stage_playtest: {dest} exists (use --force or bump)")
    shutil.copy2(rom, dest)
    for ext, out in ((".sym", ".sym"), (".mlb", ".mlb")):
        extra = src / f"oos168x{ext}"
        if extra.is_file():
            shutil.copy2(extra, PLAYTEST_DIR / f"{name}{out}")
    if (src / "hooks.json").is_file():
        shutil.copy2(src / "hooks.json", PLAYTEST_DIR / f"{name}.hooks.json")
    if args.flags:
        shutil.copy2(args.flags, PLAYTEST_DIR / f"{name}.flags.asm")
    if args.notes:
        shutil.copy2(args.notes, PLAYTEST_DIR / f"{name}.md")

    shutil.copy2(dest, PLAYTEST_DIR / "oos-play.sfc")
    for ext in (".sym", ".mlb"):
        play_side = PLAYTEST_DIR / f"oos-play{ext}"
        if (PLAYTEST_DIR / f"{name}{ext}").is_file():
            shutil.copy2(PLAYTEST_DIR / f"{name}{ext}", play_side)
        elif play_side.exists():
            # No symbols for this build: drop the previous build's file so the
            # play window never pairs this ROM with stale labels.
            play_side.unlink()

    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    latest = {"name": name, "rom": dest.name, "sha256": sha,
              "version": info["version"], "build": info["build"],
              "staged": dt.datetime.now().isoformat(timespec="seconds")}
    (PLAYTEST_DIR / "latest.json").write_text(json.dumps(latest, indent=2) + "\n")
    print(f"staged {dest.relative_to(REPO_ROOT)} sha256 {sha[:16]}; oos-play.sfc updated")
    if not args.no_offer:
        # Offer the new build to scawful's Mesen play window if it is open.
        subprocess.run([sys.executable, str(REPO_ROOT / "Scripts/Mesen2/oos_play.py"), "--offer-only",
                        "--notes", args.offer_notes or name], check=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bump", help="increment the build number in Config/version.json")
    st = sub.add_parser("stage", help="copy a finished build into Roms/Playtest/")
    st.add_argument("--from", dest="from_dir", type=Path, required=True,
                    help="directory holding oos168x.sfc (+ .sym, .mlb, hooks.json)")
    st.add_argument("--notes", type=Path)
    st.add_argument("--flags", type=Path)
    st.add_argument("--force", action="store_true")
    st.add_argument("--no-offer", action="store_true", help="do not offer the build to the play window")
    st.add_argument("--offer-notes", help="one line for the play window banner")
    args = parser.parse_args()
    return cmd_bump(args) if args.cmd == "bump" else cmd_stage(args)


if __name__ == "__main__":
    sys.exit(main())
