#!/usr/bin/env python3
"""List or refresh stale source hashes in Config/allocation_ownership.json
and Scripts/Rooms/d4_water_rooms.py::NATIVE_ATTRIBUTE_SOURCES.

  refresh_allocation_evidence.py                 # list stale keys (rc 1 if any)
  refresh_allocation_evidence.py --write [KEY..] # refresh all stale, or only KEYs

Edit a ledger-bound source (Core/symbols.asm, Dungeons/wall_profile_selector.asm, ...)
and validation fails with stale source evidence. This rewrites only the sha256
strings after the structural binding checks pass. A moved address or broken
D4 native loader contract still fails: fix the contract, not the hash.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS / 'Generate')]
from allocation_contracts import AllocationError, refresh_evidence


def _d4_native_source_changes(root: Path, keys: list[str]) -> tuple[Path, str, dict[str, tuple[str, str]]]:
    """Return (d4_module_path, text, changes) after checking structural D4 contracts."""
    d4_path = root / 'Scripts/Rooms/d4_water_rooms.py'
    if not d4_path.is_file():
        return d4_path, '', {}
    rooms_dir = str(d4_path.parent)
    if rooms_dir not in sys.path:
        sys.path.insert(0, rooms_dir)
    spec = importlib.util.spec_from_file_location('_refresh_d4_water_rooms', d4_path)
    assert spec and spec.loader
    d4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d4)
    if keys:
        selected = {k for k in keys if k in d4.NATIVE_ATTRIBUTE_SOURCES}
        if not selected:
            return d4_path, d4_path.read_text(), {}
    else:
        selected = set(d4.NATIVE_ATTRIBUTE_SOURCES)
    # Run the structural checks in validate_native_sources while computing digest updates.
    changes: dict[str, tuple[str, str]] = {}
    for rel, old in d4.NATIVE_ATTRIBUTE_SOURCES.items():
        if rel not in selected:
            continue
        new = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        if new != old:
            changes[rel] = (old, new)
    try:
        updated_map = {k: hashlib.sha256((root / k).read_bytes()).hexdigest()
                       for k in d4.NATIVE_ATTRIBUTE_SOURCES}
        with mock.patch.object(d4, 'NATIVE_ATTRIBUTE_SOURCES', updated_map):
            d4.validate_native_sources(root)
    except d4.StateDerivationError as exc:
        raise AllocationError(str(exc)) from exc
    return d4_path, d4_path.read_text(), changes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('keys', nargs='*', help='source keys to refresh (default: every stale shared key)')
    p.add_argument('--root', type=Path, default=SCRIPTS.parent)
    p.add_argument('--write', action='store_true')
    a = p.parse_args(argv)
    path = a.root / 'Config/allocation_ownership.json'
    text = path.read_text()
    try:
        ledger_keys = [k for k in a.keys if k not in {
            'Dungeons/Collision/CollisionTablesExpanded.asm',
            'Dungeons/wall_profile_selector.asm',
            'Dungeons/Data/wall_profiles/wall_profiles.asm',
            'Dungeons/Collision/water_collision.asm',
        }]
        if a.keys and not ledger_keys:
            changes = {}
        else:
            changes = refresh_evidence(json.loads(text), {'shared': a.root.resolve()}, ledger_keys or None)
        d4_path, d4_text, d4_changes = _d4_native_source_changes(a.root.resolve(), a.keys)
    except AllocationError as e:
        print(f'refused: {e}', file=sys.stderr)
        return 2
    for key, (old, new) in changes.items():
        print(f'{key}\t{old[:12]} -> {new[:12]}')
        if text.count(old) != 1:
            print(f'refused: {key} hash is not unique in the ledger', file=sys.stderr)
            return 2
        text = text.replace(old, new)
    for key, (old, new) in d4_changes.items():
        print(f'd4_water_rooms:{key}\t{old[:12]} -> {new[:12]}')
        if d4_text.count(old) != 1:
            print(f'refused: {key} hash is not unique in {d4_path}', file=sys.stderr)
            return 2
        d4_text = d4_text.replace(old, new)
    if not changes and not d4_changes:
        print('ledger evidence is current')
        return 0
    if not a.write:
        return 1
    if changes:
        path.write_text(text)
        print(f'wrote {len(changes)} hash(es) to {path}')
    if d4_changes:
        d4_path.write_text(d4_text)
        print(f'wrote {len(d4_changes)} hash(es) to {d4_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
