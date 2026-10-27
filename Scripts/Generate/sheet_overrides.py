#!/usr/bin/env python3
"""Build source-owned 3bpp sprite sheets without writing a ROM.

Ported from the 2026-10-16 AFS sheet-pipeline prototype. The first contract owns
only bank $40's audited tail. Legacy sprite sheets $0C..$66 retain their
base-sheet SHA256 guard. Schema 2 can additionally describe source-authored
compressed 3bpp globals $DF..$FE, pinned by decoded artwork SHA256 instead of
an imaginary legacy pointer. This does not admit compiled-ROM editing.
Generated files are tracked; build_rom.sh checks them before replacing output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import lz2
import sheet_codec
from sheet_table import N, decomp, pc, ptr

START, CAPACITY = 0x40D000, 0x3000
# Relocated pointer arrays (Core/gfx_sheet_table.asm); the base ROM table is only read.
NEW_BANK, NEW_HIGH, NEW_LOW = 0x23FD00, 0x23FE00, 0x23FF00
SPEC = Path('Data/graphics/source_sprite_sheets.json')
OUTPUT = Path('Core/Generated/source_sprite_sheets')
FLAG = 'ENABLE_SOURCE_SPRITE_SHEETS'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, str), 'expected an integer or hexadecimal string')
    return int(value, 0) if isinstance(value, str) else value


def read_spec(path):
    spec = json.loads(Path(path).read_text())
    require(type(spec) is dict and set(spec) == {'schema_version', 'start', 'capacity', 'encoding', 'sheets'}, 'invalid source sheet spec keys')
    require(type(spec['schema_version']) is int and spec['schema_version'] in (1, 2), 'unsupported source sheet schema')
    require((number(spec['start']), number(spec['capacity'])) == (START, CAPACITY), 'only the audited $40:D000-$40:FFFF allocation is supported')
    require(spec['encoding'] in ('lz2', 'stored'), 'encoding must be lz2 or stored')
    require(type(spec['sheets']) is list and spec['sheets'], 'source sheet list must not be empty')
    seen = set()
    for entry in spec['sheets']:
        require(type(entry) is dict, 'invalid sheet entry')
        if 'global_sheet' in entry:
            require(spec['schema_version'] == 2, 'new global sheets require source schema 2')
            require(set(entry) == {'global_sheet', 'source', 'decoded_sha256', 'why'}, 'invalid new global sheet keys')
            global_id = number(entry['global_sheet'])
            require(0xDF <= global_id <= 0xFE, 'source-authored globals must be $DF-$FE; $FF is the default sentinel')
            require(isinstance(entry['decoded_sha256'], str) and re.fullmatch('[0-9a-f]{64}', entry['decoded_sha256']), 'decoded_sha256 must be a full lowercase SHA256')
        else:
            require(set(entry) == {'sprite_sheet', 'source', 'base_sha256', 'identity', 'why'}, 'invalid sheet entry keys')
            sheet = number(entry['sprite_sheet'])
            require(0x0C <= sheet <= 0x66, 'only compressed 3bpp sprite sheets $0C-$66 are supported')
            global_id = sheet+0x73
            require(isinstance(entry['base_sha256'], str) and re.fullmatch('[0-9a-f]{64}', entry['base_sha256']), 'base_sha256 must be a full lowercase SHA256')
            require(type(entry['identity']) is bool, 'identity must be boolean')
        require(global_id not in seen, 'duplicate sprite sheet/global sheet'); seen.add(global_id)
        require(isinstance(entry['why'], str) and '\n' not in entry['why'] and '\r' not in entry['why'], 'why must be a single line')
        relative = Path(entry['source'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'sheet source must stay inside the spec directory')
        require((Path(path).parent/relative).resolve().is_relative_to(Path(path).parent.resolve()), 'sheet source escapes through a symlink')
    return spec


def validate_reservation(root, rom):
    """Refuse an expanded base or new reachable owner that occupies our tail."""
    end = pc(START) + CAPACITY
    require(not any(rom[pc(START):end]), 'source sheet allocation is occupied in the editable base')
    world = root/'Overworld/world_map'
    require(sum((world/name).stat().st_size for name in ('LwMapTileset.bin', 'LwMapGfx.bin')) <= 0x5000, 'Light World map overlaps the source sheet allocation')
    # The map starts at $408000. Other reachable bank-40 writers need an
    # explicit allocation review, even if they happen to write zero bytes.
    from generate_hack_manifest import collect_reachable_asm_sources, ORG_BANK_RE
    for source in collect_reachable_asm_sources(root):
        if source.is_relative_to((root/OUTPUT).resolve()):
            continue
        for line in source.read_text().splitlines():
            match = ORG_BANK_RE.match(line.split(';', 1)[0])
            if match:
                address = int(match[1], 16) & 0x7FFFFF
                require(address >> 16 != 0x40 or (source == (root/'Overworld/world_map.asm').resolve() and address == 0x408000), 'another reachable source owns bank $40: '+str(source))
    # Check consumed stream extents, not just pointer starts, including aliases.
    for global_id in range(N):
        address = ptr(rom, global_id)
        require(address & 0x8000 and (address >> 16 & 0x7F) < 0x7E, 'invalid graphics pointer')
        begin = pc(address)
        if 115 <= global_id <= 126:
            used = 0x600
            require(begin+used <= len(rom), 'truncated stored graphics sheet')
        else:
            _, used = decomp(rom, address)
        require(not (begin < end and pc(START) < begin+used), 'base graphics stream overlaps source sheet allocation')


def build(spec_path, base_rom, root=None, *, rom_role="editable_base"):
    require(rom_role == 'editable_base', 'source sheet generation requires editable_base role; compiled-ROM writes are unsupported')
    spec_path = Path(spec_path)
    spec = read_spec(spec_path)
    rom = Path(base_rom).read_bytes()
    require(len(rom) >= 0x8000 and len(rom) % 0x8000 == 0, 'need an unheadered editable LoROM image')
    if root is not None:
        validate_reservation(Path(root).resolve(), rom)
    out, address = [], START
    for entry in spec['sheets']:
        new_global = 'global_sheet' in entry
        global_id = number(entry['global_sheet']) if new_global else number(entry['sprite_sheet'])+0x73
        sheet = global_id-0x73
        base_data = None
        if not new_global:
            pointer = ptr(rom, global_id)
            require(pointer & 0x8000 and (pointer >> 16 & 0x7F) < 0x7E, 'invalid base sheet pointer')
            base_data, _ = decomp(rom, pointer)
            require(len(base_data) == 0x600, 'base sprite sheet must decode to exactly 1536 bytes')
            digest = hashlib.sha256(base_data).hexdigest()
            require(digest == entry['base_sha256'], f'sheet ${sheet:02X}: base sheet changed ({digest}); re-export before overriding')
        source = spec_path.parent/entry['source']
        grid = sheet_codec.png_to_grid(source) if source.suffix.lower() == '.png' else sheet_codec.text_to_grid(source.read_text())
        raw = sheet_codec.grid_to_sheet(grid)
        require(len(raw) == 0x600, 'source 3bpp sheet must contain exactly 1536 bytes')
        if new_global:
            digest = hashlib.sha256(raw).hexdigest()
            require(digest == entry['decoded_sha256'], f'global ${global_id:02X}: decoded source changed ({digest})')
        else:
            require(not entry['identity'] or raw == base_data, 'identity override changes decoded sheet pixels')
        stream = lz2.stored(raw) if spec['encoding'] == 'stored' else lz2.compress(raw)
        require(lz2.decompress(stream, max_output=0x600) == (raw, len(stream)), 'compressed sheet round trip differs')
        require(address+len(stream) <= START+CAPACITY, 'source sprite sheet allocation is full')
        out.append(dict(s=sheet, g=global_id, raw=raw, stream=stream, snes=address, source=entry['source'], why=entry['why']))
        address += len(stream)
    return spec, out


def asm_text(items):
    lines = ['; GENERATED by Scripts/Generate/sheet_overrides.py. Do not edit.',
             '; Source-owned sprite sheets in audited bank $40 tail; global id = sprite + $73.',
             '; Pointer rows are patched in the relocated arrays, so this file follows Core/gfx_sheet_table.asm.',
             'pushpc', 'org $40D000']
    for item in items:
        lines.append(f'SourceSpriteSheet_{item["s"]:02X}: incbin "sheets/spr{item["s"]:02X}.bin"')
    lines.append('assert pc() <= $410000 || pc() == $418000, "Source sprite sheets crossed bank $40"')
    lines += [f'assert GfxSheet_Bank == ${NEW_BANK:06X} && GfxSheet_High == ${NEW_HIGH:06X} && GfxSheet_Low == ${NEW_LOW:06X}, "sheet_overrides.asm must follow Core/gfx_sheet_table.asm"']
    for item in items:
        global_id, address = item['g'], item['snes'] | 0x800000
        lines += [f'; Sprite ${item["s"]:02X}, global ${global_id:02X}: {item["why"]}',
                  f'org ${NEW_BANK+global_id:06X} ; @hook module=Core kind=data protected_size=1',
                  f'  db ${address>>16:02X}',
                  f'org ${NEW_HIGH+global_id:06X} ; @hook module=Core kind=data protected_size=1',
                  f'  db ${(address>>8)&255:02X}',
                  f'org ${NEW_LOW+global_id:06X} ; @hook module=Core kind=data protected_size=1',
                  f'  db ${address&255:02X}']
    return '\n'.join(lines+['pullpc', ''])


def generated_files(items):
    files = {Path('sheets')/f'spr{item["s"]:02X}.bin': item['stream'] for item in items}
    files[Path('sheet_overrides.asm')] = asm_text(items).encode()
    return files


def write_outputs(out, files, inputs):
    """Stage all files first, publish the include last, roll back ordinary errors.

    A hard process kill can leave complete files from two generations. Build
    --check detects that mismatch before any output ROM is replaced.
    """
    destinations = [out/name for name in files]
    for path in destinations:
        require(not path.is_symlink() and (not path.exists() or path.is_file()), 'generated output must be a regular file')
        for source in inputs:
            require(path.resolve() != source.resolve() and not (path.exists() and path.samefile(source)), 'generated output aliases an input')
    staged = {}; backups = {}; changed = []
    try:
        for name, data in files.items():
            path = out/name; path.parent.mkdir(parents=True, exist_ok=True)
            backups[path] = path.read_bytes() if path.exists() else None
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.'+path.name+'.', delete=False) as handle:
                staged[path] = Path(handle.name); handle.write(data); handle.flush(); os.fsync(handle.fileno())
        for path, temporary in staged.items():
            os.replace(temporary, path); changed.append(path)
    except BaseException:
        for path in reversed(changed):
            if backups[path] is None:
                path.unlink()
            else:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.'+path.name+'.rollback.', delete=False) as handle:
                    temporary = Path(handle.name); handle.write(backups[path]); handle.flush(); os.fsync(handle.fileno())
                os.replace(temporary, path)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def source_metadata(root, *, rom_role="build_output"):
    # This is build-output provenance/reservations, never writable source-origin
    # metadata. No development/compiled editor write contract exists here.
    require(rom_role == 'build_output', 'source metadata supports build_output provenance only; editor source origins are unsupported')
    spec_path = Path(root)/SPEC
    spec = read_spec(spec_path)
    globals_ = [number(e['global_sheet']) if 'global_sheet' in e else number(e['sprite_sheet'])+0x73 for e in spec['sheets']]
    return dict(schema_version=1, spec=SPEC.as_posix(), spec_sha256=hashlib.sha256(spec_path.read_bytes()).hexdigest(),
                feature_flag=FLAG, sprite_sheet_ids=[f'0x{g-0x73:02X}' for g in globals_],
                global_sheet_ids=[f'0x{g:02X}' for g in globals_],
                owned_region=dict(start='0x40D000', end='0x418000', end_exclusive=True, pc_start='0x205000', pc_end='0x208000', size=CAPACITY),
                generated_include=(OUTPUT/'sheet_overrides.asm').as_posix())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('spec', type=Path, nargs='?')
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument('--base-rom', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--respect-flags', action='store_true')
    ap.add_argument('--rom-role', default='editable_base')
    args = ap.parse_args(); root = args.root.resolve()
    try:
        require(args.rom_role == 'editable_base', 'source sheet generation requires editable_base role; compiled-ROM writes are unsupported')
        if args.respect_flags:
            from asm_source import _load_global_defines
            enabled = _load_global_defines(root).get(FLAG)
            require(enabled in (0, 1), 'source sheet feature flag is missing or invalid')
            if not enabled:
                print('Source sprite sheets disabled; no override is assembled.'); return 0
        spec_path = args.spec or root/SPEC
        spec, items = build(spec_path, args.base_rom, root, rom_role=args.rom_role)
        out = args.out_dir or root/OUTPUT
        files = generated_files(items)
        stale = [str(name) for name, data in files.items() if not (out/name).is_file() or (out/name).read_bytes() != data]
        if args.check:
            require(not stale, 'stale generated sprite sheets: '+', '.join(stale))
        else:
            write_outputs(out, files, [args.base_rom, spec_path]+[spec_path.parent/e['source'] for e in spec['sheets']])
        print(json.dumps(dict(checked=args.check, sheets=[dict(sprite_sheet=f'{i["s"]:02X}', global_sheet=f'{i["g"]:02X}', bytes=len(i['stream']), decoded_sha256=hashlib.sha256(i['raw']).hexdigest()) for i in items])))
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print('Source sprite sheets: '+str(error), file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
