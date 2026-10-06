#!/usr/bin/env python3
"""Verify nonempty hooks and their current-ROM identity before comparison.

Source/note fields are optional for scanner comparisons. ROM identity is always
checked, including in validation-only mode for exact assembler hook records.
"""
from __future__ import annotations

import argparse
import hashlib
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
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: hooks document must be an object")
    return data


def validate_identity(path: Path, rom: Path) -> dict:
    """Require hooks bound to the exact ROM; accept legacy SHA-1 provenance.

    SHA-256 producers must record size. Legacy SHA-1-only files may omit it,
    but any supplied size or digest must match; a bad SHA-256 never falls back
    to a matching SHA-1. Paths are descriptive, since artifacts can be moved.
    """
    data = _load_json(path)
    hooks = data.get("hooks")
    if not isinstance(hooks, list) or not hooks:
        raise ValueError(f"{path}: hooks must be a nonempty list")
    if any(not isinstance(hook, dict) or not hook for hook in hooks):
        raise ValueError(f"{path}: hooks must contain nonempty objects")
    metadata = data.get("rom")
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: missing ROM identity metadata")
    payload = rom.read_bytes()
    if not payload:
        raise ValueError(f"{rom}: ROM must not be empty")
    if "sha256" not in metadata and "sha1" not in metadata:
        raise ValueError(f"{path}: missing ROM SHA-256 or legacy SHA-1")
    if "sha256" in metadata and "size" not in metadata:
        raise ValueError(f"{path}: SHA-256 ROM metadata requires size")
    if "size" in metadata:
        size = metadata["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size != len(payload):
            raise ValueError(f"{path}: ROM size mismatch (expected {len(payload)}, got {size!r})")
    for algorithm in ("sha256", "sha1"):
        if algorithm in metadata:
            expected = hashlib.new(algorithm, payload).hexdigest()
            actual = metadata[algorithm]
            if not isinstance(actual, str) or actual.lower() != expected:
                raise ValueError(f"{path}: ROM {algorithm.upper()} mismatch")
    return data


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
    hooks = data.get("hooks")
    if not isinstance(hooks, list) or not hooks:
        raise ValueError(f"{path}: hooks must be a nonempty list")
    normalized = [_normalize_hook(hook, keys) for hook in hooks]
    normalized.sort()
    return normalized


def _run_generator(root: Path, rom: Path, out_path: Path) -> None:
    script = root / "Scripts" / "Generate" / "generate_hooks_json.py"
    if not script.exists():
        raise FileNotFoundError(f"generate_hooks_json.py not found at {script}")
    cmd = [sys.executable, str(script), "--root", str(root), "--output", str(out_path), "--rom", str(rom)]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify hooks.json matches generator output")
    parser.add_argument("--root", type=Path, required=True, help="Repo root")
    parser.add_argument("--rom", type=Path, required=True, help="Current ROM whose identity must match")
    parser.add_argument("--hooks", type=Path, required=True, help="Existing hooks.json to compare")
    parser.add_argument("--generated", type=Path, help="Path to pre-generated hooks.json (optional)")
    parser.add_argument("--include-source", action="store_true", help="Include source/note fields in comparison")
    parser.add_argument("--identity-only", action="store_true", help="Validate assembler hooks and ROM identity without estimated scanner comparison")
    args = parser.parse_args()
    if args.identity_only and (args.generated is not None or args.include_source):
        parser.error("--identity-only cannot be combined with --generated or --include-source")

    root = args.root.resolve()
    rom = args.rom if args.rom.is_absolute() else root / args.rom
    hooks_path = args.hooks if args.hooks.is_absolute() else root / args.hooks

    keys = list(DEFAULT_KEYS)
    if args.include_source:
        keys.extend(["source", "note"])
    keys_tuple = tuple(keys)

    generated_path = args.generated
    if generated_path is not None and not generated_path.is_absolute():
        generated_path = root / generated_path
    temporary_path = None
    try:
        validate_identity(hooks_path, rom)
        if args.identity_only:
            print("hooks.json has nonempty hooks and matches current ROM identity")
            return 0
        if generated_path is None:
            with tempfile.NamedTemporaryFile(prefix="hooks_gen_", suffix=".json", delete=False) as handle:
                temporary_path = generated_path = Path(handle.name)
            _run_generator(root, rom, generated_path)
        validate_identity(generated_path, rom)
        base_hooks = _collect(hooks_path, keys_tuple)
        new_hooks = _collect(generated_path, keys_tuple)
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"hooks.json verification failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    if base_hooks == new_hooks:
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

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
