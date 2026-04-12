#!/usr/bin/env python3
"""Verify hooks.json matches generator output.

By default ignores source/note/rom metadata to avoid churn.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_KEYS = (
    "address",
    "name",
    "kind",
    "target",
    "expected_m",
    "expected_x",
    "expected_exit_m",
    "expected_exit_x",
    "skip_abi",
    "abi_class",
    "module",
)


def _load_json(path: Path) -> dict:
    with path.open("r") as handle:
        return json.load(handle)


def _normalize_hook(hook: dict, keys: tuple[str, ...]) -> tuple:
    addr = hook.get("address")
    if isinstance(addr, str):
        if addr.startswith("0x"):
            addr_val = int(addr, 16)
        elif addr.startswith("$"):
            addr_val = int(addr[1:], 16)
        else:
            addr_val = int(addr, 0)
    else:
        addr_val = int(addr) if addr is not None else 0
    normalized = []
    for key in keys:
        if key == "address":
            normalized.append(addr_val)
            continue
        value = hook.get(key)
        if isinstance(value, bool):
            normalized.append(int(value))
        else:
            normalized.append(value)
    return tuple(normalized)


def _collect(path: Path, keys: tuple[str, ...]) -> list[tuple]:
    data = _load_json(path)
    hooks = data.get("hooks", [])
    normalized = [_normalize_hook(hook, keys) for hook in hooks]
    normalized.sort()
    return normalized


def _run_generator(root: Path, rom: Path, out_path: Path) -> None:
    script = root / "scripts" / "generate_hooks_json.py"
    if not script.exists():
        raise FileNotFoundError(f"generate_hooks_json.py not found at {script}")
    cmd = [sys.executable, str(script), "--root", str(root), "--output", str(out_path), "--rom", str(rom)]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify hooks.json matches generator output")
    parser.add_argument("--root", type=Path, required=True, help="Repo root")
    parser.add_argument("--rom", type=Path, required=True, help="ROM path for generator")
    parser.add_argument("--hooks", type=Path, required=True, help="Existing hooks.json to compare")
    parser.add_argument("--generated", type=Path, help="Path to pre-generated hooks.json (optional)")
    parser.add_argument("--include-source", action="store_true", help="Include source/note fields in comparison")
    args = parser.parse_args()

    keys = list(DEFAULT_KEYS)
    if args.include_source:
        keys.extend(["source", "note"])
    keys_tuple = tuple(keys)

    generated_path = args.generated
    temp_file = None
    if generated_path is None:
        temp_file = tempfile.NamedTemporaryFile(prefix="hooks_gen_", suffix=".json", delete=False)
        generated_path = Path(temp_file.name)
        temp_file.close()
        _run_generator(args.root, args.rom, generated_path)

    base_hooks = _collect(args.hooks, keys_tuple)
    new_hooks = _collect(generated_path, keys_tuple)

    if base_hooks == new_hooks:
        if temp_file is not None:
            generated_path.unlink(missing_ok=True)
        print("hooks.json matches generator output")
        return 0

    base_set = set(base_hooks)
    new_set = set(new_hooks)
    missing = sorted(base_set - new_set)
    extra = sorted(new_set - base_set)

    print("hooks.json mismatch:")
    print(f"  missing: {len(missing)}")
    print(f"  extra:   {len(extra)}")
    if missing:
        print("  sample missing (address,name,kind,target,...):")
        for item in missing[:5]:
            print("   ", item)
    if extra:
        print("  sample extra (address,name,kind,target,...):")
        for item in extra[:5]:
            print("   ", item)

    if temp_file is not None:
        generated_path.unlink(missing_ok=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
