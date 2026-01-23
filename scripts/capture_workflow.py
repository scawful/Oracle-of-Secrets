#!/usr/bin/env python3
"""
Guided capture workflow for save-state library.

Reads a JSON/YAML plan, prompts the user to position the game, and captures
states with snapshots + metadata via state_library.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROM = REPO_ROOT / "Roms" / "oos168x.sfc"
DEFAULT_STATE_LIBRARY = REPO_ROOT / "scripts" / "state_library.py"
DEFAULT_MESEN_CLI = REPO_ROOT / "scripts" / "mesen_cli.sh"


def load_plan(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Plan not found: {path}")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise SystemExit(f"PyYAML not available for {path}: {exc}") from exc
        data = yaml.safe_load(path.read_text()) or {}
    else:
        data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit("Plan must be a JSON/YAML object.")
    return data


def run(cmd: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        out = (result.stdout or "").strip()
        if result.returncode == 0:
            return True, out
        return False, (result.stderr or out or "command failed").strip()
    except Exception as exc:
        return False, str(exc)


def entry_to_args(entry: dict) -> list[str]:
    args: list[str] = []
    for key, flag in [
        ("description", "--description"),
        ("label", "--label"),
        ("location", "--location"),
        ("summary", "--summary"),
        ("notes", "--notes"),
        ("progress", "--progress"),
        ("module", "--module"),
        ("room", "--room"),
        ("area", "--area"),
        ("link_state", "--link-state"),
    ]:
        if entry.get(key) is not None:
            args += [flag, str(entry[key])]
    tags = entry.get("tags")
    if isinstance(tags, list):
        args += ["--tags", ",".join(str(t) for t in tags)]
    elif isinstance(tags, str):
        args += ["--tags", tags]
    return args


def main() -> int:
    parser = argparse.ArgumentParser(description="Guided save-state capture workflow")
    parser.add_argument("--plan", required=True, help="Plan JSON/YAML file")
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--rom-base", help="Override ROM base name")
    parser.add_argument("--no-pause", action="store_true", help="Do not pause between entries")
    parser.add_argument("--snapshot", action="store_true", help="Capture screenshot + state JSON")
    parser.add_argument("--state-library", default=str(DEFAULT_STATE_LIBRARY))
    parser.add_argument("--mesen-cli", default=str(DEFAULT_MESEN_CLI))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan = load_plan(Path(args.plan))
    entries = plan.get("entries", [])
    if not isinstance(entries, list) or not entries:
        raise SystemExit("Plan has no entries")

    set_name = plan.get("set")

    print(f"Plan: {args.plan} ({len(entries)} entries)")
    for idx, entry in enumerate(entries, 1):
        state_id = entry.get("id")
        slot = entry.get("slot")
        if not state_id or slot is None:
            raise SystemExit(f"Entry {idx} missing id/slot")

        title = entry.get("title") or entry.get("description") or state_id
        print(f"\n[{idx}/{len(entries)}] {state_id} (slot {slot}) - {title}")
        if not args.no_pause:
            input("Position the game, then press Enter to capture...")

        cmd = [
            "python3",
            args.state_library,
            "capture",
            "--id",
            str(state_id),
            "--rom",
            args.rom,
            "--slot",
            str(slot),
            "--mesen-cli",
            args.mesen_cli,
        ]
        if args.rom_base:
            cmd += ["--rom-base", args.rom_base]
        if args.snapshot or entry.get("snapshot"):
            cmd.append("--snapshot")
        cmd += entry_to_args(entry)

        if args.dry_run:
            print("DRY RUN:", " ".join(cmd))
            continue

        ok, out = run(cmd, cwd=REPO_ROOT)
        if not ok:
            print(f"Capture failed: {out}", file=sys.stderr)
            return 1
        if out:
            print(out)

    if set_name and not args.dry_run:
        # Create or update the set mapping from the captured entries
        slot_specs = [f"{e['slot']}:{e['id']}" for e in entries]
        cmd = [
            "python3",
            args.state_library,
            "set-create",
            "--set",
            str(set_name),
        ]
        for spec in slot_specs:
            cmd += ["--slot", spec]
        if args.rom_base:
            cmd += ["--rom-base", args.rom_base]
        cmd += ["--rom", args.rom, "--force"]
        ok, out = run(cmd, cwd=REPO_ROOT)
        if not ok:
            print(f"Set create failed: {out}", file=sys.stderr)
            return 1
        if out:
            print(out)

    print("\nCapture workflow complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
