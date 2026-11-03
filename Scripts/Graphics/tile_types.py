#!/usr/bin/env python3
"""Extract per-char tile types from an Oracle ROM into slot_types.json (stdlib only; ROM is read-only)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = 1
CHARS = 0x200
# Vanilla bank $0E tables (usdasm bank_0E.asm). OverworldTileTypes is 512 bytes, one per char.
OVERWORLD = (0x0E, 0x9459)
# UnderworldTileTypes is $180 bytes ($0E:9659-$0E:97D8). LoadDefaultTileTypes ($0E:97D9) copies
# table bytes $000-$13F to $7EFE00 (chars $000-$13F) and bytes $140-$17F to $7EFFC0 (chars $1C0-$1FF).
# Chars $140-$1BF ($7EFF40-$7EFFBF) always come from the blockset groups.
DUNGEON_SHARED = (0x0E, 0x9659)
DUNGEON_SHARED_SIZE = 0x180
OVERLAY = range(0x140, 0x1C0)
BLOCKSETS = 24  # CollisionTablesExpanded.asm group_offsets: 24 dw entries
GROUP_OFFSET_LABELS = ('Oracle_group_offsets', 'group_offsets')
GROUP_DATA_LABELS = ('Oracle_offs', 'offs', 'Oracle_group00', 'group00')
WORLDS = ('overworld', 'dungeon')


def lorom_pc(bank, addr):
    """Headerless LoROM: pc = (bank & $7F) * $8000 + (addr - $8000)."""
    if not 0x8000 <= addr <= 0xFFFF:
        raise ValueError('LoROM address must be $8000-$FFFF: $%02X:%04X' % (bank, addr))
    return (bank & 0x7F) * 0x8000 + (addr - 0x8000)


def snes_text(bank, addr):
    return '$%02X:%04X' % (bank, addr)


def read(rom, bank, addr, size):
    pc = lorom_pc(bank, addr)
    if pc + size > len(rom):
        raise ValueError('%s + $%X is outside the ROM' % (snes_text(bank, addr), size))
    return rom[pc:pc + size]


def parse_sym(text):
    """Return {label: (bank, addr)} from the [labels] section of an asar WLA sym file."""
    labels = {}
    section = None
    for line in text.splitlines():
        line = line.split(';')[0].strip()
        if not line:
            continue
        if line.startswith('['):
            section = line
            continue
        if section != '[labels]':
            continue
        match = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)', line)
        if match:
            labels.setdefault(match.group(3), (int(match.group(1), 16), int(match.group(2), 16)))
    return labels


def find_label(labels, names):
    for name in names:
        if name in labels:
            return name, labels[name]
    raise ValueError('sym has none of the labels: ' + ', '.join(names))


def dungeon_shared(rom):
    table = read(rom, *DUNGEON_SHARED, DUNGEON_SHARED_SIZE)
    return list(table[:0x140]) + [None] * len(OVERLAY) + list(table[0x140:])


def dungeon_blocksets(rom, labels):
    """Mirror Dungeon_LoadCustomTileAttr: 0x40 bytes from groups+off (slot 5), 0x40 from groups+off+$40 (slot 6)."""
    _, offsets_at = find_label(labels, GROUP_OFFSET_LABELS)
    _, groups_at = find_label(labels, GROUP_DATA_LABELS)
    words = read(rom, *offsets_at, BLOCKSETS * 2)
    out = {}
    for blockset in range(BLOCKSETS):
        offset = words[blockset * 2] | words[blockset * 2 + 1] << 8
        bank, addr = groups_at
        if addr + offset + 0x80 > 0x10000:
            raise ValueError('blockset %d group crosses the end of bank $%02X' % (blockset, bank))
        out[str(blockset)] = list(read(rom, bank, addr + offset, 0x80))
    return out, offsets_at, groups_at


def extract(rom, labels=None):
    """Return the schema-1 tile type dict (without the source block)."""
    types = {'overworld': list(read(rom, *OVERWORLD, CHARS)), 'dungeon_shared': dungeon_shared(rom), 'dungeon_blocksets': {}}
    addresses = {'overworld': snes_text(*OVERWORLD), 'dungeon_shared': snes_text(*DUNGEON_SHARED), 'group_offsets': None, 'groups': None}
    if labels is not None:
        types['dungeon_blocksets'], offsets_at, groups_at = dungeon_blocksets(rom, labels)
        addresses['group_offsets'] = snes_text(*offsets_at)
        addresses['groups'] = snes_text(*groups_at)
    return types, addresses


def load_types(path):
    """Read and check a slot_types.json written by this tool."""
    types = json.loads(Path(path).read_text())
    if types.get('schema') != SCHEMA:
        raise ValueError('slot_types.json schema must be %d' % SCHEMA)
    if len(types.get('overworld', ())) != CHARS or len(types.get('dungeon_shared', ())) != CHARS:
        raise ValueError('overworld and dungeon_shared must each have 512 entries')
    blocksets = types.get('dungeon_blocksets')
    if not isinstance(blocksets, dict) or any(len(v) != len(OVERLAY) for v in blocksets.values()):
        raise ValueError('dungeon_blocksets must map blockset numbers to 128 entries')
    return types


def char_type(types, world, char, blockset=None):
    """Tile type of VRAM char in world; dungeon chars $140-$1BF need a blockset present in the file."""
    if world not in WORLDS:
        raise ValueError('world must be overworld or dungeon')
    if type(char) is not int or not 0 <= char < CHARS:
        raise ValueError('char must be $000-$1FF')
    if world == 'overworld':
        return types['overworld'][char]
    if char not in OVERLAY:
        return types['dungeon_shared'][char]
    if blockset is None:
        raise ValueError('dungeon char $%03X (slot %d) needs a blockset' % (char, char // 0x40))
    if str(blockset) not in types['dungeon_blocksets']:
        raise ValueError('blockset %s is not in slot_types.json (extracted without --sym?)' % blockset)
    return types['dungeon_blocksets'][str(blockset)][char - OVERLAY.start]


def dumps(data):
    # One line per int array keeps 512-entry tables readable and diffable.
    text = json.dumps(data, indent=1)
    return re.sub(r'\[[\s\dnul,]*\]', lambda m: json.dumps(json.loads(m.group(0)), separators=(',', ':')), text) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--sym', type=Path, help='asar WLA sym; resolves Oracle_group_offsets and Oracle_offs')
    parser.add_argument('--out', type=Path, required=True, help='new slot_types.json')
    args = parser.parse_args()
    if args.out.exists():
        parser.error('--out already exists; previous outputs are never replaced')
    rom = args.rom.read_bytes()
    labels = None
    sym_sha = None
    if args.sym:
        sym_bytes = args.sym.read_bytes()
        sym_sha = hashlib.sha256(sym_bytes).hexdigest()
        labels = parse_sym(sym_bytes.decode('utf-8', 'replace'))
    else:
        print('warning: no --sym; dungeon_blocksets is {} (dungeon chars $140-$1BF unknown)', file=sys.stderr)
    types, addresses = extract(rom, labels)
    data = {'schema': SCHEMA, 'source': {'rom': str(args.rom.resolve()), 'rom_sha256': hashlib.sha256(rom).hexdigest(),
            'sym': str(args.sym.resolve()) if args.sym else None, 'sym_sha256': sym_sha, 'addresses': addresses}}
    data.update(types)
    with open(args.out, 'x') as handle:
        handle.write(dumps(data))
    print(json.dumps({'output': str(args.out.resolve()), 'blocksets': len(types['dungeon_blocksets'])}))


if __name__ == '__main__':
    main()
