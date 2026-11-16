#!/usr/bin/env python3
"""Admit the private cell65 hook only with its exact paired room/art payload."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from verify_feature_flags import _iter_define_assignments

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Scripts/Rooms'))
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
import sky_d8_room_writer as rooms
import validate_custom_collision_source as collision


def enabled(root):
    flags = {}
    for name in ('Util/macros.asm', 'Config/module_flags.asm', 'Config/feature_flags.asm'):
        path = root / name
        if path.exists():
            flags.update((key, value) for key, value, _ in _iter_define_assignments(path))
    active = flags.get('ENABLE_D3_PRISON_CELL65', 0)
    if active not in (0, 1):
        raise ValueError('ENABLE_D3_PRISON_CELL65 must be 0 or 1')
    if active and flags.get('ENABLE_D3_PRISON_SEQUENCE') != 1:
        raise ValueError('Cell65 requires ENABLE_D3_PRISON_SEQUENCE=1')
    if active:
        for name in ('DISABLE_OVERWORLD', 'DISABLE_DUNGEON', 'DISABLE_SPRITES', 'DISABLE_MASKS'):
            if flags.get(name, 0) != 0:
                raise ValueError('Cell65 requires enabled module: ' + name)
        if flags.get('ENABLE_MINISH_AUTO_PORTAL') != 1:
            raise ValueError('Cell65 requires its Minish portal mechanic')
    return bool(active)


def armory_enabled(root):
    flags = {}
    for name in ('Util/macros.asm', 'Config/module_flags.asm', 'Config/feature_flags.asm'):
        path = root / name
        if path.exists():
            flags.update((key, value) for key, value, _ in _iter_define_assignments(path))
    value = flags.get('ENABLE_D3_PRISON_ARMORY', 0)
    if value not in (0, 1):
        raise ValueError('ENABLE_D3_PRISON_ARMORY must be0 or1')
    if value and (flags.get('ENABLE_D3_PRISON_CELL65') != 1 or flags.get('ENABLE_WALL_PROFILE_SELECTOR') != 1):
        raise ValueError('Armory requires CELL65 and wall selector')
    return bool(value)


def validate(data, contract):
    def require(ok, message):
        if not ok:
            raise ValueError('Prison cell65 paired-data admission: ' + message)

    sha = lambda value: hashlib.sha256(value).hexdigest()
    require(contract['version'] == 1, 'unknown contract version')
    inv = rooms.build_inventory(data)
    for key, expected in contract['rooms'].items():
        room = int(key, 16)
        stream = inv.objects[room]
        raw = data[stream.pc:stream.end]
        require(len(raw) == expected['object_stream_bytes'] and
                sha(raw) == expected['object_stream_sha256'], f'room {key} geometry mismatch')
        require(inv.door_target[room] == stream.door_pc, f'room {key} door pointer mismatch')
        at = inv.header_pc[room]
        require(data[at:at+14].hex() == expected['header_hex'], f'room {key} header mismatch')
    for key, expected in contract.get('actor_streams', {}).items():
        start, end = inv.spr_span[int(key, 16)]
        require(data[start:end].hex() == expected, f'room {key} actors mismatch')
    require(data[0x5ED3:0x5ED7].hex() == contract['aux4F_hex'], 'aux4F mismatch')
    for expected in contract['graphics']:
        sheet = expected['sheet']
        address = data[0x4F80+sheet] << 16 | data[0x505F+sheet] << 8 | data[0x513E+sheet]
        at = rooms.snes_to_pc(address)
        raw = data[at:at+expected['packed_bytes']]
        require(sha(raw) == expected['packed_sha256'], f'sheet {sheet:02X} mismatch')
    at = collision.POINTER_TABLE_START + 0x65*3
    pointer = int.from_bytes(data[at:at+3], 'little')
    require(pointer != 0, 'room65 collision missing')
    tiles = collision._decode_room(data, 0x65, pointer)
    require(set(tiles) == set(range(4096)), 'room65 must retain every explicit collision cell')
    require(sha(bytes(tiles[i] for i in range(4096))) == contract['collision65_sha256'],
            'room65 collision mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--rom', type=Path, required=True)
    args = parser.parse_args()
    armory = armory_enabled(args.root)
    if not enabled(args.root):
        print('Prison cell65 paired-data prototype disabled; no base change required')
        return 0
    contract = json.loads((args.root / 'Data/dungeons/prison_cell65_contract.json').read_text())
    if armory:
        if contract.get('armory') != 'room54-table-drawers-meadow-b' or '54' not in contract['rooms']:
            raise ValueError('Armory requires its exact paired room54 geometry contract')
        for name in ('prison_armory_worktable.bin', 'prison_armory_drawers.bin'):
            if 'Dungeons/Objects/Data/' + name not in contract['source_objects']:
                raise ValueError('Armory source asset is not bound: ' + name)
    for name, expected in contract['source_objects'].items():
        if hashlib.sha256((args.root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Prison source object changed: ' + name)
    validate(args.rom.read_bytes(), contract)
    print('Prison cell65 paired room/art/collision payload verified')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, IndexError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
