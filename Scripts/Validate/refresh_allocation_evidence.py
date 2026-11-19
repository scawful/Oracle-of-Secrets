#!/usr/bin/env python3
"""Check allocation bindings and Room25 native-source presence.

Per-file SHA-256 pins are not part of either contract. Claims stay bound by
anchors and symbol addresses; Room25 stays bound by its loader admission.
--write is accepted for older callers and does not rewrite the ledger.

  refresh_allocation_evidence.py
  refresh_allocation_evidence.py --write [KEY..]
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS / 'Generate')]
from allocation_contracts import AllocationError, refresh_evidence

D4_SOURCES = (
    'Dungeons/Collision/CollisionTablesExpanded.asm',
    'Dungeons/wall_profile_selector.asm',
    'Dungeons/Data/wall_profiles/wall_profiles.asm',
    'Dungeons/Collision/water_collision.asm',
)


def _check_d4_native_sources(root: Path) -> None:
    d4_path = root / 'Scripts/Rooms/d4_water_rooms.py'
    if not d4_path.is_file():
        return
    rooms_dir = str(d4_path.parent)
    if rooms_dir not in sys.path:
        sys.path.insert(0, rooms_dir)
    spec = importlib.util.spec_from_file_location('_refresh_d4_water_rooms', d4_path)
    assert spec and spec.loader
    d4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d4)
    try:
        d4.validate_native_sources(root)
    except d4.StateDerivationError as exc:
        raise AllocationError(str(exc)) from exc


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('keys', nargs='*', help='source keys to check (default: every shared source)')
    p.add_argument('--root', type=Path, default=SCRIPTS.parent)
    p.add_argument('--write', action='store_true', help='accepted; no SHA pins are rewritten')
    a = p.parse_args(argv)
    path = a.root / 'Config/allocation_ownership.json'
    text = path.read_text()
    ledger_keys = [k for k in a.keys if k not in D4_SOURCES]
    try:
        if not a.keys or ledger_keys:
            refresh_evidence(json.loads(text), {'shared': a.root.resolve()}, ledger_keys or None)
        _check_d4_native_sources(a.root.resolve())
    except AllocationError as e:
        print(f'refused: {e}', file=sys.stderr)
        return 2
    print('source contracts are current (no per-file SHA pins)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
