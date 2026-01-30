#!/usr/bin/env python3
"""ROM version management for Oracle of Secrets.

Manages a dense local ROM library in Roms/ (never committed). Supports:
- list: scan Roms/ for *.sfc, show optional catalog tags
- tag: add/update metadata (label, pass/fail, note) in Roms/versions.json
- select: print path for a ROM by name or --pass
- diff: run diff tool on two ROMs (by name or path)
- run-test: run a command with OOS_BASE_ROM set to a chosen ROM

Run from repo root. Roms/ and Roms/versions.json are gitignored.

Usage:
  python3 scripts/rom_version_manage.py list
  python3 scripts/rom_version_manage.py tag Roms/oos167x.sfc --label "Pre refactor" --pass
  python3 scripts/rom_version_manage.py select oos167x
  python3 scripts/rom_version_manage.py select --pass
  python3 scripts/rom_version_manage.py diff oos168x.sfc oos167x.sfc
  python3 scripts/rom_version_manage.py run-test oos167x.sfc -- python3 scripts/bisect_softlock.py
  python3 scripts/rom_version_manage.py run-test --pass -- run_regression_tests.sh regression
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ROMS_DIR = REPO_ROOT / "Roms"
VERSIONS_JSON = ROMS_DIR / "versions.json"


def _roms_dir() -> Path:
    if not ROMS_DIR.is_dir():
        sys.exit(f"Roms directory not found: {ROMS_DIR}")
    return ROMS_DIR


def _load_catalog() -> dict:
    if not VERSIONS_JSON.is_file():
        return {}
    try:
        with open(VERSIONS_JSON) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_catalog(data: dict) -> None:
    _roms_dir()
    with open(VERSIONS_JSON, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Updated {VERSIONS_JSON}")


def _rom_path(name: str) -> Path | None:
    """Resolve name to a path under Roms/. Name can be filename or stem (e.g. oos167x)."""
    roms = _roms_dir()
    if (roms / name).is_file():
        return roms / name
    if not name.endswith(".sfc"):
        candidate = roms / f"{name}.sfc"
        if candidate.is_file():
            return candidate
    for p in roms.glob("*.sfc"):
        if p.stem == name or p.name == name:
            return p
    return None


def cmd_list(args: argparse.Namespace) -> int:
    roms = _roms_dir()
    catalog = _load_catalog()
    paths = sorted(roms.glob("*.sfc"))
    if not paths:
        print("No .sfc ROMs in Roms/")
        return 0
    for p in paths:
        meta = catalog.get(p.name, {})
        label = meta.get("label", "")
        pass_ = meta.get("pass", None)
        note = meta.get("note", "")
        tags = []
        if pass_ is True:
            tags.append("pass")
        elif pass_ is False:
            tags.append("fail")
        if label:
            tags.append(label)
        if note:
            tags.append(f"({note})")
        tag_str = "  " + " | ".join(tags) if tags else ""
        print(p.name + tag_str)
    return 0


def cmd_tag(args: argparse.Namespace) -> int:
    path = Path(args.rom_path).resolve()
    if not path.is_file():
        sys.exit(f"Not a file: {path}")
    roms = _roms_dir()
    try:
        path.relative_to(roms)
    except ValueError:
        sys.exit(f"ROM must be under Roms/: {path}")
    name = path.name

    catalog = _load_catalog()
    entry = catalog.get(name, {})
    if args.label is not None:
        entry["label"] = args.label
    if args.pass_ is not None:
        entry["pass"] = args.pass_
    if args.note is not None:
        entry["note"] = args.note
    catalog[name] = entry
    _save_catalog(catalog)
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    roms = _roms_dir()
    catalog = _load_catalog()
    if args.pass_:
        if not catalog:
            print("No catalog (Roms/versions.json); tag a ROM with --pass first", file=sys.stderr)
            return 1
        for name, meta in catalog.items():
            if meta.get("pass") is True:
                p = roms / name
                if p.is_file():
                    print(str(p))
                    return 0
        print("No ROM tagged pass=true", file=sys.stderr)
        return 1
    if not args.name:
        print("select requires name or --pass", file=sys.stderr)
        return 1
    path = _rom_path(args.name)
    if not path:
        print(f"No such ROM: {args.name}", file=sys.stderr)
        return 1
    print(str(path))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    a = _rom_path(args.rom_a) if not Path(args.rom_a).is_file() else Path(args.rom_a)
    b = _rom_path(args.rom_b) if not Path(args.rom_b).is_file() else Path(args.rom_b)
    if a is None or not (a and a.is_file()):
        sys.exit(f"ROM not found: {args.rom_a}")
    if b is None or not (b and b.is_file()):
        sys.exit(f"ROM not found: {args.rom_b}")
    a, b = Path(a), Path(b)
    # Prefer cmp -l for byte diff; fallback to Python byte diff summary
    if shutil.which("cmp"):
        r = subprocess.run(["cmp", "-l", str(a), str(b)], capture_output=True, text=True)
        if r.returncode == 0:
            print("ROMs are identical")
            return 0
        lines = (r.stdout or r.stderr or "").strip().splitlines()
        print(f"First 50 differing bytes (of {len(lines)}):")
        for line in lines[:50]:
            print(line)
        if len(lines) > 50:
            print(f"... and {len(lines) - 50} more")
        return 0
    with open(a, "rb") as fa, open(b, "rb") as fb:
        ba, bb = fa.read(), fb.read()
    if ba == bb:
        print("ROMs are identical")
        return 0
    n = sum(1 for i, (x, y) in enumerate(zip(ba, bb)) if x != y)
    print(f"ROMs differ: {n} bytes (sizes {len(ba)} vs {len(bb)})")
    return 0


def cmd_run_test(args: argparse.Namespace) -> int:
    if args.pass_:
        path = None
        catalog = _load_catalog()
        for name, meta in catalog.items():
            if meta.get("pass") is True:
                p = ROMS_DIR / name
                if p.is_file():
                    path = p
                    break
        if not path:
            print("No ROM tagged pass=true", file=sys.stderr)
            return 1
    else:
        if not args.rom_name:
            print("run-test requires rom_name or --pass", file=sys.stderr)
            return 1
        path = _rom_path(args.rom_name)
        if not path:
            print(f"No such ROM: {args.rom_name}", file=sys.stderr)
            return 1
    cmd = args.cmd
    if not cmd:
        print("run-test requires a command after --", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["OOS_BASE_ROM"] = str(path.resolve())
    # Run first token as script if it looks like a script
    if cmd[0].endswith(".sh"):
        r = subprocess.run(["bash", "-e", cmd[0]] + cmd[1:], cwd=REPO_ROOT, env=env)
    else:
        r = subprocess.run(cmd, cwd=REPO_ROOT, env=env)
    return r.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ROM version management (list, tag, select, diff, run-test)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List ROMs in Roms/ with optional catalog tags")
    list_p.set_defaults(func=cmd_list)

    tag_p = sub.add_parser("tag", help="Tag a ROM in Roms/versions.json")
    tag_p.add_argument("rom_path", help="Path to ROM under Roms/ (e.g. Roms/oos167x.sfc)")
    tag_p.add_argument("--label", default=None, help="Human-readable label")
    tag_p.add_argument("--pass", dest="pass_", action="store_true", default=None, help="Mark as pass (known good)")
    tag_p.add_argument("--fail", dest="pass_", action="store_false", help="Mark as fail")
    tag_p.add_argument("--note", default=None, help="Short note")
    tag_p.set_defaults(func=cmd_tag)

    sel_p = sub.add_parser("select", help="Print path for a ROM (by name or --pass)")
    sel_p.add_argument("name", nargs="?", default=None, help="ROM name or stem (e.g. oos167x)")
    sel_p.add_argument("--pass", dest="pass_", action="store_true", help="First ROM tagged pass=true")
    sel_p.set_defaults(func=cmd_select)

    diff_p = sub.add_parser("diff", help="Diff two ROMs (by name or path)")
    diff_p.add_argument("rom_a", help="First ROM (name or path)")
    diff_p.add_argument("rom_b", help="Second ROM (name or path)")
    diff_p.set_defaults(func=cmd_diff)

    run_p = sub.add_parser("run-test", help="Run command with OOS_BASE_ROM set to a ROM")
    run_p.add_argument("rom_name", nargs="?", default=None, help="ROM name or stem")
    run_p.add_argument("--pass", dest="pass_", action="store_true", help="Use first ROM tagged pass=true")
    run_p.add_argument("cmd", nargs="*", help="Command after -- (e.g. -- run_regression_tests.sh regression)")
    run_p.set_defaults(func=cmd_run_test)

    # Parse only up to -- so remainder is the command for run-test
    argv = sys.argv[1:]
    if "run-test" in argv and "--" in argv:
        idx = argv.index("--")
        run_test_args = argv[:idx]
        run_test_cmd = argv[idx + 1 :]
    else:
        run_test_args = argv
        run_test_cmd = []
    args = parser.parse_args(run_test_args)
    if args.command == "run-test":
        args.cmd = run_test_cmd
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
