"""Prepare minimal current-engine readers for a complete EDITABLE import.

No assembly, I/O, ROM publication or runtime admission occurs here. The complete
import composer owns allocation and directory sealing. In particular, resident
runtime hooks and caller blocks from the compiled donor are never transplanted.
"""
from __future__ import annotations

import hashlib
import re
import struct

import lyra_native_loaders as native
from special_overworld_native_build import _validate_reader_bindings


_ENGINE_FILES = ('Oracle_main.asm', 'Overworld/ZSCustomOverworld.asm',
    'Overworld/lyra_native_loaders.asm', 'Overworld/lyra_actor_stream.asm',
    'Overworld/lyra_tail_events.asm', 'Overworld/time_system.asm',
    'Overworld/HardwareRegisters.asm', 'Util/macros.asm', 'Core/ram.asm',
    'Core/symbols.asm', 'Config/allocation_ownership.json')
# Their restored filename comments are outside this bootstrap's source closure.
_UNRELATED_GENERATED = {'Dungeons/generated/water_fill_table.asm',
                        'Dungeons/generated/water_gate_runtime_tables.asm'}
_REQUIRED_CHECKS = {'source_sprite_sheets', 'menu_icon_sheets', 'collision_source',
    'message_source', 'native_overworld_constants', 'water_tables', 'water_fill',
    'flags', 'menu', 'version_stamp', 'assembly', 'native_overworld_readers',
    'native_overworld_preservation', 'hooks_generation', 'hooks', 'manifest',
    'symbol_export', 'overlap'}
_CALLS = ((0x02F59D, 'Lyra_FullHigh', 20, 1, 0x02F94D),
          (0x02F5C8, 'Lyra_FullLow', 21, 1, 0x02FB2D),
          (0x02F7E3, 'Lyra_SubHigh', 20, 2, 0x02F94D),
          (0x02F80E, 'Lyra_SubLow', 21, 2, 0x02FB2D))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _require(ok, code):
    if not ok:
        raise ValueError('INITIAL_BOOTSTRAP_' + code)


def bootstrap_source_paths(build_receipt):
    """Exact current files the caller must read, never a pinned source snapshot.

All assembled sources are bound, apart from two unrelated generated water files.
The mandatory engine files prevent a caller reducing the receipt to an empty
manifest. This is deliberately conservative about stale compiled dependencies.
"""
    files = build_receipt.get('snapshots', {}).get('pre_assembly', {}).get('files', {})
    _require(all(name in files for name in _ENGINE_FILES), 'SOURCE_MANIFEST_MISSING')
    return tuple(sorted(set(_ENGINE_FILES) | {
        name for name in files if name.endswith('.asm')
        and name not in _UNRELATED_GENERATED}))


def _symbols(raw):
    _require(type(raw) is bytes, 'SYMBOL_BYTES_REQUIRED')
    rows = {}
    in_labels = False
    for line in raw.decode('utf-8').splitlines():
        if line.startswith('['):
            in_labels = line == '[labels]'
            continue
        if not in_labels:
            continue
        match = re.fullmatch(r'([0-9a-fA-F]{2}):([0-9a-fA-F]{4})\s+:?([A-Za-z_]\w*(?:\.\w+)*)', line)
        if match:
            name = match[3]
            value = int(match[1] + match[2], 16)
            _require(name not in rows or rows[name] == value, 'SYMBOL_CONFLICT')
            rows[name] = value
    return rows


def prepare_initial_bootstrap(source, compiled, *, symbols_raw, build_receipt,
                              current_source_files):
    """Return preimage-bound patches and ID300/301 for a complete composer.

``source`` is the unchanged headerless project160 ROM; padding stays in memory.
``compiled`` is a current successful supported native192 Build, with its exact
WLA bytes and receipt. ``current_source_files`` maps bootstrap_source_paths()
to freshly read bytes. The result is incomplete and cannot be run or published.
"""
    _require(type(source) is bytes and type(compiled) is bytes
             and 0x200000 <= len(source) <= 0x400000
             and len(compiled) == 0x400000, 'IMAGE_EXTENT')
    original_source_hash = _sha(source)
    source = source.ljust(0x400000, b'\0')
    _require(native.read_native_directory(source) is None, 'ALREADY_NATIVE')
    receipt = build_receipt
    finish = receipt.get('finish', {})
    checks = receipt.get('checks', [])
    required = [row for row in checks if row.get('required')]
    _require(finish.get('exit_code') == 0 and finish.get('stage') == 'complete'
             and not finish.get('required_gaps')
             and _REQUIRED_CHECKS <= {row.get('name') for row in required}
             and all(row.get('status') == 'passed' and row.get('exit_code') == 0
                     for row in required), 'BUILD_NOT_COMPLETE')
    for role, raw in [('output_rom', compiled), ('symbols', symbols_raw)]:
        artifact = receipt.get('artifacts', {}).get(role, {})
        _require(artifact.get('sha256') == _sha(raw)
                 and artifact.get('size') == len(raw), 'ARTIFACT_HASH_MISMATCH')
    complement, checksum = struct.unpack_from('<HH', compiled, 0x7FDC)
    _require(compiled[0x7FD5] in (0x20, 0x30)
             and complement ^ checksum == 0xFFFF
             and sum(compiled) & 0xFFFF == checksum, 'COMPILED_HEADER')
    snapshot = receipt['snapshots']['pre_assembly']['files']
    paths = bootstrap_source_paths(receipt)
    _require(all(type(current_source_files.get(path)) is bytes
                 and _sha(current_source_files[path]) == snapshot[path]['sha256']
                 for path in paths), 'STALE_SOURCE_BINDING')
    symbols = _symbols(symbols_raw)

    def symbol(name):
        _require(name in symbols, 'MISSING_SYMBOL_' + name)
        return symbols[name]

    parsed = native.read_native_directory(compiled)
    _require(parsed is not None and parsed[:2] == (192, 0x4C)
             and len(parsed[2]) == 57, 'COMPILED_PROFILE')
    entries = parsed[2]
    start, end = symbol('Lyra_CurrentNativeCodeStart'), symbol('Lyra_CurrentNativeCodeEnd')
    _require(start == native.CODE_BASE and start < end <= native.CODE_LIMIT
             and entries[300] == (start, end - start)
             and entries[301] == (native.BINDINGS_BASE, 5), 'READER_EXTENT')
    for family in native.current_table_layout(native.TABLE_BASE):
        _require(entries[family.id][0] == family.snes, 'TABLE_LAYOUT')
    _validate_reader_bindings(compiled, entries)
    patches, rows, spans = [], [], []

    def patch(address, after, reason):
        at = native.pc(address)
        _require(at + len(after) <= len(source)
                 and (address & 0xFFFF) + len(after) <= 0x10000
                 and all(at >= hi or at + len(after) <= lo for lo, hi in spans)
                 and (at >= native.DIRECTORY_PC + native.DIRECTORY_SIZE
                      or at + len(after) <= native.DIRECTORY_PC), 'PATCH_OVERLAP_OR_EXTENT')
        spans.append((at, at + len(after)))
        patches.append(dict(reason=reason, snes=address, pc=at,
                            before_hex=source[at:at + len(after)].hex(),
                            after_hex=after.hex()))

    for site, target_name, table, kind, original in _CALLS:
        target = symbol(target_name)
        call = b'\x22' + target.to_bytes(3, 'little')
        installed = call + b'\xEA' * 8
        at = native.pc(site)
        before = source[at:at + 12]
        # Exact native producer pair, including both STA DP instructions.
        old = (b'\xBF' + original.to_bytes(3, 'little') + b'\x85\xC8'
               + b'\xBF' + (original + 1).to_bytes(3, 'little') + b'\x85\xC9')
        _require(before in (old, installed), 'TERRAIN_PREIMAGE')
        _require(compiled[at:at + 12] == installed, 'COMPILED_CALL')
        rows.append((site, target, table, kind, call))
        patch(site, installed, 'descriptor_required_reader_call')
    site, target = symbol('LyraCall_CurrentActors'), symbol('Lyra_LoadCurrentSprites')
    call = b'\x5C' + target.to_bytes(3, 'little')
    at = native.pc(site)
    _require(source[at:at + 4] in (b'\xBF\x38\x94\x28', call), 'ACTOR_PREIMAGE')
    _require(compiled[at:at + 4] == call, 'COMPILED_ACTOR_CALL')
    rows.append((site, target, 16, 4, call))
    bindings = b''.join(struct.pack('<IIHBB', site, target, table, kind, 0) + call
                        for site, target, table, kind, call in rows)
    _require(compiled[native.pc(native.BINDINGS_BASE):native.pc(native.BINDINGS_BASE)
                      + len(bindings)] == bindings, 'BINDING_ROWS')
    _require(all(start <= row[1] < end for row in rows), 'TARGET_OUTSIDE_BODY')
    patch(site, call, 'descriptor_required_reader_call')

    # These dictionary operands are an independent engine ABI. Resident compiled
    # hooks replace some whole instructions, so never copy their operand bytes.
    # The selected project profile already binds the current dictionary bodies;
    # unknown/older layouts must get an explicit profile, not guessed corrections.
    dictionaries = {key: (value, entries[key][1])
                    for key, value in native.CURRENT_DICTIONARIES.items()}
    native.verify_dictionary_readers(source, dictionaries)
    body = compiled[native.pc(start):native.pc(end)]
    patch(start, body, 'directory300_reader_body')
    patch(native.BINDINGS_BASE, bindings, 'directory301_reader_bindings')
    dependencies = {}
    for path in ('Overworld/lyra_native_loaders.asm', 'Overworld/lyra_actor_stream.asm',
                 'Overworld/lyra_tail_events.asm'):
        text = current_source_files[path].decode('utf-8')
        text = '\n'.join(line.split(';', 1)[0] for line in text.splitlines())
        for name in re.findall(r'\bOracle_\w+', text):
            dependencies[name] = symbol(name)
    return dict(schema='oracle.initial-reader-bootstrap.v1',
        source_rom_sha256=original_source_hash, padded_source_sha256=_sha(source),
        compiled_rom_sha256=_sha(compiled),
        symbols_sha256=_sha(symbols_raw),
        source_files={path: _sha(current_source_files[path]) for path in paths},
        external_symbols=dependencies, patches=patches,
        directory300=dict(snes=start, count=len(body), stride=1,
                          sha256=_sha(body), payload_hex=body.hex()),
        directory301=dict(snes=native.BINDINGS_BASE, count=5, stride=16,
                          sha256=_sha(bindings), payload_hex=bindings.hex()),
        bindings=[dict(site=site, target=target, table_id=table, kind=kind,
                       instruction_hex=call.hex())
                  for site, target, table, kind, call in rows],
        dictionary_operand_changes=0, dictionary_validation='PASS',
        complete_image=False, runtime_qualified=False, allocation_granted=False,
        transplant_full_compiled=False,
        runtime_dependency_policy='Editable-only bootstrap. Normal supported Build '
            'must regenerate source-owned callers, resources and ID300, then seal '
            'and validate the complete compiled directory before Run.')
