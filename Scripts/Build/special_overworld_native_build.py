"""Offline revision4 resource preparation; ordinary Build admission is unchanged.

The input is a saved native ROM plus its fresh z3ed resident-gameplay-area
export. This module performs no file I/O, assembly, sidecar lowering or ROM
publication. The existing directory/resource codecs remain the format owners.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct

import lyra_native_loaders as native
import special_overworld_resources as resources
import special_overworld_resident_abi as resident


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _require(ok, message):
    if not ok:
        raise ValueError(message)


@dataclass(frozen=True)
class ReaderCodeReplacement:
    """Explicit same-extent compiled ID300 replacement, never an ABI waiver.

    The caller owns the exact source/compiler evidence. Changed binding rows,
    call sites or code extents need their own future contract; this seam does
    not infer or install them. An old hash prevents an unintended second reseal.
    """
    expected_sha256: str
    compiled_bytes: bytes


def _write(source, pc, raw, purpose):
    before = source[pc:pc + len(raw)]
    _require(len(before) == len(raw), 'NATIVE_BUILD_WRITE_OUTSIDE_SOURCE')
    return dict(pc=pc, before=before, after=raw, purpose=purpose)


def _validate_reader_bindings(source, entries):
    """Check installed call witnesses without revision3 runtime admission."""
    code, size = entries[300]
    bindings, count = entries[301]
    _require(code == native.CODE_BASE and 0 < size <= native.CODE_LIMIT - code
             and bindings == native.BINDINGS_BASE
             and count * 16 <= native.CODE_BASE - bindings,
             'NATIVE_BUILD_READER_RESERVATION_MISMATCH')
    required = {0x02F59D: (20, 1), 0x02F5C8: (21, 1),
                0x02F7E3: (20, 2), 0x02F80E: (21, 2)}
    seen, bound, actor = [], set(), False
    for index in range(count):
        at = native.pc(bindings) + index * 16
        site, target, table, kind, reserved = struct.unpack_from('<IIHBB', source, at)
        instruction = source[at + 12:at + 16]
        site_pc, target_pc = native.pc(site), native.pc(target)
        _require(table in range(1, 40) and table != 29 and 1 <= kind <= 5
                 and reserved == 0 and instruction[0] in (0x22, 0x5C)
                 and int.from_bytes(instruction[1:], 'little') == target
                 and native.pc(code) <= target_pc < native.pc(code) + size
                 and (site & 0xFFFF) + 4 <= 0x10000
                 and source[site_pc:site_pc + 4] == instruction
                 and all(site_pc >= end or site_pc + 4 <= first for first, end in seen),
                 'NATIVE_BUILD_READER_BINDING_INVALID')
        for key, (address, rows) in entries.items():
            first = native.pc(address)
            end = first + rows * native.entry_spec(key, native.MAP_CAPACITY, 4)[2]
            _require(site_pc >= end or site_pc + 4 <= first,
                     'NATIVE_BUILD_READER_SITE_OVERLAPS_PAYLOAD')
        _require(site_pc >= native.DIRECTORY_PC + native.DIRECTORY_SIZE
                 or site_pc + 4 <= native.DIRECTORY_PC,
                 'NATIVE_BUILD_READER_SITE_OVERLAPS_DIRECTORY')
        seen.append((site_pc, site_pc + 4))
        if kind in (1, 2):
            _require(required.get(site) == (table, kind) and instruction[0] == 0x22,
                     'NATIVE_BUILD_TERRAIN_BINDING_MISMATCH')
            bound.add(site)
        if kind == 4:
            _require(16 <= table <= 18 and instruction[0] == 0x5C,
                     'NATIVE_BUILD_ACTOR_BINDING_MISMATCH')
            actor = True
    _require(bound == set(required) and actor,
             'NATIVE_BUILD_REQUIRED_READER_BINDING_MISSING')
    return seen


def _code_reseal(source, capacity, bank, entries, replacement):
    address, count = entries[300]
    start = native.pc(address)
    before = source[start:start + count]
    if replacement is None:
        return [], dict(status='preserved', before_sha256=_sha(before),
                        after_sha256=_sha(before))
    _require(type(replacement) is ReaderCodeReplacement
             and type(replacement.compiled_bytes) is bytes
             and replacement.expected_sha256 == _sha(before),
             'NATIVE_BUILD_READER_RESEAL_SOURCE_MISMATCH')
    after = replacement.compiled_bytes
    _require(len(after) == count, 'NATIVE_BUILD_READER_EXTENT_CHANGE_UNSUPPORTED')
    if after == before:
        # Accepted record order is not an ABI. A no-op must retain the original
        # directory bytes and describe the exact source that remains untouched.
        return [], dict(status='explicit_same_extent_reseal',
            before_sha256=_sha(before), after_sha256=_sha(after),
            resealed_source_sha256=_sha(source), bindings_preserved=True,
            compiled_source_evidence_required=True)
    image = bytearray(source)
    image[start:start + count] = after
    rows = [(key, at, rows) for key, (at, rows) in entries.items()]
    directory = native.encode_revision4_directory(bytes(image), rows,
        tail_actor_bank=bank, capacity=capacity)
    image[native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE] = directory
    _require(native.read_native_directory(bytes(image)) == (capacity, bank, entries),
             'NATIVE_BUILD_RESEAL_CHANGED_LAYOUT')
    # The sole payload exception is explicit code300. Binding records and every
    # authored table/dictionary/stream/appearance/identity payload stay exact.
    for key, (at, rows) in entries.items():
        if key == 300:
            continue
        width = native.entry_spec(key, capacity, 4)[2]
        pc, size = native.pc(at), rows * width
        _require(image[pc:pc + size] == source[pc:pc + size],
                 'NATIVE_BUILD_RESEAL_CHANGED_SAVED_PAYLOAD')
    writes = []
    if after != before:
        writes = [_write(source, start, after, 'explicit_reader_code300_reseal'),
                  _write(source, native.DIRECTORY_PC, directory,
                         'explicit_reader_code300_directory_crc')]
    return writes, dict(status='explicit_same_extent_reseal',
        before_sha256=_sha(before), after_sha256=_sha(after),
        resealed_source_sha256=_sha(image), bindings_preserved=True,
        compiled_source_evidence_required=True)


def prepare_revision4_compilation(source, exported, *, data_pc, capacity,
                                  preimage, reader_code_replacement=None,
                                  graphics_root=None):
    """Return pure compilation inputs and preimage-bound writes, not a ROM.

    ``data_pc/capacity`` name the caller-owned current resident reservation;
    they grant no allocation authority. Each write retains its exact preimage,
    and bank padding is deliberately absent from the write list. The resource
    constants do not enable flags or replace reader_constants(). A separate
    reviewed orchestrator must assemble, validate the whole composition and
    enforce the existing ordinary Build/publication gates.
    """
    _require(type(source) is bytes, 'NATIVE_BUILD_SAVED_SOURCE_REQUIRED')
    installed = native.read_native_directory(source)
    _require(installed is not None
             and struct.unpack_from('<H', source, native.DIRECTORY_PC + 8)[0] == 4,
             'NATIVE_BUILD_REVISION4_REQUIRED')
    map_count, bank, entries = installed
    _require(map_count == native.MAP_CAPACITY,
             'NATIVE_BUILD_CURRENT_ENGINE_REQUIRES192')
    native.verify_dictionary_readers(source, entries)
    call_spans = _validate_reader_bindings(source, entries)
    _require(type(data_pc) is int and type(capacity) is int
             and data_pc == native.RESIDENT_DATA_PC
             and capacity == native.RESIDENT_DATA_CAPACITY,
             'NATIVE_BUILD_RESIDENT_RESERVATION_MISMATCH')
    _require(type(preimage) is bytes and len(preimage) == capacity
             and source[data_pc:data_pc + capacity] == preimage,
             'NATIVE_BUILD_RESIDENT_PREIMAGE_MISMATCH')
    _require(all(data_pc >= end or data_pc + capacity <= first
                 for first, end in call_spans),
             'NATIVE_BUILD_RESIDENT_OVERLAPS_READER_CALL')
    for key, (at, rows) in entries.items():
        size = rows * native.entry_spec(key, map_count, 4)[2]
        pc = native.pc(at)
        _require(data_pc >= pc + size or data_pc + capacity <= pc,
                 'NATIVE_BUILD_RESIDENT_OVERLAPS_SAVED_PAYLOAD')
    reseal_writes, code = _code_reseal(source, map_count, bank, entries,
                                      reader_code_replacement)
    # This validates fresh export identity/profiles/topology/resolved bytes;
    # the retained packer and emitter own all byte formats and bank placement.
    plan = resources.plan_saved_native_terrain(source, exported,
                                               graphics_root=graphics_root)
    abi = resident.plan_native_resident_abi(plan, tile16_count=entries[400][1])
    emission = resident.emit_native_resident_abi(abi, data_pc=data_pc,
        capacity=capacity, preimage=preimage)
    runtime = resident.resident_runtime_inputs(abi, emission, preimage=preimage)
    binary = bytes.fromhex(emission['payload_hex'])
    writes = []
    for row in emission['placements']:
        first, end = row['pc']
        offset = row['binary_offset']
        raw = binary[offset:offset + end - first]
        _require(_sha(raw) == row['sha256'], 'NATIVE_BUILD_EMISSION_MISMATCH')
        writes.append(_write(source, first, raw, row['role']))
    return dict(schema='special_overworld.native_build_preparation.v1',
        source_rom_sha256=_sha(source),
        native_export_sha256=exported['native_source_sha256'],
        resource_plan=plan, resident_abi=abi, emission=emission,
        runtime_inputs=runtime, constants_asm=emission['constants_asm'],
        data_asm=emission['runtime_data_asm'], binary=binary,
        resource_writes=writes, source_reseal_writes=reseal_writes,
        reader_code=code, saved_payloads_preserved=True,
        reader_bindings_validated=True,
        reexport_required_after_reseal=bool(reseal_writes),
        unresolved_full_residency_unknowns=list(plan['unknowns']),
        full_residency_ready=False,
        reader_constants_admission_unchanged=True,
        allocation_granted=False, ordinary_build_ready=False,
        runtime_admission=False, publication_authorized=False)


# Current resident engine instruction spans, not dictionary operand spans.
# Long reads become JSL; full-page reads also replace the following STA with
# three NOPs because their wrapper performs the destination write itself.
RESIDENT_READER_HOOKS = (
    (0x02FE1B, 'Lyra_ResidentFull0', 7),
    (0x02FE22, 'Lyra_ResidentFull2', 7),
    (0x02FE2B, 'Lyra_ResidentFull1', 7),
    (0x02FE32, 'Lyra_ResidentFull3', 7),
    (0x02F456, 'Lyra_ResidentHorizontal0', 4),
    (0x02F45D, 'Lyra_ResidentHorizontal1', 4),
    (0x02F466, 'Lyra_ResidentHorizontal2', 4),
    (0x02F46D, 'Lyra_ResidentHorizontal3', 4),
    (0x02F51E, 'Lyra_ResidentVertical0', 4),
    (0x02F525, 'Lyra_ResidentVertical2', 4),
    (0x02F52E, 'Lyra_ResidentVertical1', 4),
    (0x02F535, 'Lyra_ResidentVertical3', 4),
    (0x1BC9B2, 'Lyra_ResidentMutable0', 4),
    (0x1BC9B9, 'Lyra_ResidentMutable1', 4),
    (0x1BC9C0, 'Lyra_ResidentMutable2', 4),
    (0x1BC9C7, 'Lyra_ResidentMutable3', 4),
    (0x1BCA3F, 'Lyra_ResidentMutable0', 4),
    (0x1BCA46, 'Lyra_ResidentMutable1', 4),
    (0x1BCA4D, 'Lyra_ResidentMutable2', 4),
    (0x1BCA54, 'Lyra_ResidentMutable3', 4),
)

RUNTIME_CODE_EXTENTS = (
    ('Lyra_ResidentAtlasCodeStart', 'Lyra_ResidentAtlasCodeEnd',
     native.RESIDENT_WORD_CODE_BASE, native.RESIDENT_WORD_CODE_LIMIT),
    ('Oracle_SpecialOverworldGraphicsCodeStart', 'Oracle_SpecialOverworldGraphicsCodeEnd',
     native.RESIDENT_RESOURCE_CODE_BASE, native.RESIDENT_RESOURCE_CODE_LIMIT),
    ('Oracle_SpecialOverworldPaletteCodeStart', 'Oracle_SpecialOverworldPaletteCodeEnd',
     native.RESIDENT_PALETTE_CODE_BASE, native.RESIDENT_PALETTE_CODE_BASE + 0x500),
    ('SpecialPaletteAdaptersStart', 'SpecialPaletteAdaptersEnd',
     native.RESIDENT_PALETTE_CODE_BASE + 0x500, native.RESIDENT_PALETTE_CODE_LIMIT),
)

# Existing source policy in Overworld/overworld.asm: phase0 ambience is
# explicit silence for these eight intro maps. The low music nibble remains
# authored source data; no other byte or phase belongs to this exception.
INTRO_AMBIENCE_PHASE0_MAPS = (0x13, 0x14, 0x1B, 0x1C, 0x23, 0x24, 0x2B, 0x2C)


def _symbol(symbols, name, *, exclusive_end=False):
    value = symbols.get(name)
    _require(type(value) is int, f'NATIVE_BUILD_REQUIRED_SYMBOL_MISSING:{name}')
    # Exclusive code ends may be the next bank's $0000. They have no ROM
    # operand of their own; map the last actual byte instead.
    native.pc(value - 1 if exclusive_end else value)
    return value


def plan_revision4_compiled_seal(source, exported, compiled, symbols, *,
                                allow_stale_directory=False, graphics_root=None):
    """Validate compilation and return directory bytes for source reassembly.

    Inputs are immutable ROM bytes, a fresh source export and WLA label names
    mapped to integer SNES addresses. Only a same-extent ID300 regeneration can
    change a directory payload. In the explicitly requested first pass, the
    compiled descriptor may still be the *exact* source descriptor; all other
    checks remain mandatory. The strict final pass requires the expected seal.

    No ROM, checksum or file is patched. The orchestrator must assemble the
    returned directory into the ORIGINAL saved input and run this validator
    again without ``allow_stale_directory``. This is a compiler composition
    proof, not native execution or publication admission.
    """
    _require(type(compiled) is bytes and type(source) is bytes
             and len(compiled) == len(source), 'NATIVE_BUILD_COMPILED_EXTENT_MISMATCH')
    _require(type(symbols) is dict and type(allow_stale_directory) is bool,
             'NATIVE_BUILD_COMPILED_ARGUMENT_INVALID')
    prep = prepare_revision4_compilation(source, exported,
        data_pc=native.RESIDENT_DATA_PC, capacity=native.RESIDENT_DATA_CAPACITY,
        preimage=source[native.RESIDENT_DATA_PC:
                        native.RESIDENT_DATA_PC + native.RESIDENT_DATA_CAPACITY],
        graphics_root=graphics_root)
    capacity, bank, entries = native.read_native_directory(source)
    code_address, code_size = entries[300]
    code_start = _symbol(symbols, 'Lyra_CurrentNativeCodeStart')
    code_end = _symbol(symbols, 'Lyra_CurrentNativeCodeEnd', exclusive_end=True)
    _require(code_start == code_address and code_end == code_address + code_size,
             'NATIVE_BUILD_COMPILED_READER_EXTENT_MISMATCH')
    protected = [(native.DIRECTORY_PC, native.DIRECTORY_PC + native.DIRECTORY_SIZE,
                  'directory')]
    for key, (address, rows) in entries.items():
        first, length = native.pc(address), rows * native.entry_spec(key, capacity, 4)[2]
        protected.append((first, first + length, f'ID{key}'))
        if key != 300:
            _require(compiled[first:first + length] == source[first:first + length],
                     f'NATIVE_BUILD_COMPILED_SAVED_PAYLOAD_CHANGED:ID{key}')
    call_spans = _validate_reader_bindings(source, entries)
    for first, end in call_spans:
        _require(compiled[first:end] == source[first:end],
                 'NATIVE_BUILD_COMPILED_READER_CALL_CHANGED')
        protected.append((first, end, 'reader_call'))
    for key, mirror in ((20, 0x1794D), (21, 0x17B2D)):
        first = native.pc(entries[key][0])
        expected = source[first:first + native.FIRST_TAIL_MAP * 3]
        _require(source[mirror:mirror + len(expected)] == expected,
                 'NATIVE_BUILD_SOURCE_POINTER_MIRROR_MISMATCH')
        _require(compiled[mirror:mirror + len(expected)] == expected,
                 'NATIVE_BUILD_COMPILED_POINTER_MIRROR_CHANGED')
        protected.append((mirror, mirror + len(expected), f'mirror{key}'))
    prefix_transforms = []
    for name, address, rows, _, stride in native.CURRENT_TABLE_SPECS:
        if name in ('map32_high', 'map32_low'):
            continue
        first, length = native.pc(address), rows * stride
        expected_prefix = bytearray(source[first:first + length])
        if name == 'music_phase0':
            _require(address == 0x02C303 and rows == 64 and stride == 1,
                     'NATIVE_BUILD_INTRO_AMBIENCE_SOURCE_PROFILE_MISMATCH')
            for map_id in INTRO_AMBIENCE_PHASE0_MAPS:
                before = expected_prefix[map_id]
                after = (before & 0x0F) | 0x50
                expected_prefix[map_id] = after
                prefix_transforms.append(dict(policy='intro_ambience_silence',
                    prefix=name, map_id=map_id, snes=address + map_id,
                    pc=first + map_id, before=before, after=after,
                    preserved_mask=0x0F, compiler_owned_mask=0xF0,
                    compiler_owned_value=0x50, changed=before != after))
        _require(compiled[first:first + length] == bytes(expected_prefix),
                 f'NATIVE_BUILD_COMPILED_NATIVE_PREFIX_CHANGED:{name}')
        protected.append((first, first + length, name))

    extents = []
    for start_name, end_name, lower, upper in RUNTIME_CODE_EXTENTS:
        first = _symbol(symbols, start_name)
        end = _symbol(symbols, end_name, exclusive_end=True)
        _require(first == lower and first < end <= upper,
                 f'NATIVE_BUILD_RUNTIME_EXTENT_MISMATCH:{start_name}')
        pc_first, pc_end = native.pc(first), native.pc(end - 1) + 1
        _require(pc_end <= len(compiled), 'NATIVE_BUILD_RUNTIME_OUTSIDE_IMAGE')
        for at, limit, role in protected:
            _require(pc_first >= limit or pc_end <= at,
                     f'NATIVE_BUILD_RUNTIME_OVERLAPS_SAVED_SOURCE:{role}')
        extents.append(dict(start_symbol=start_name, end_symbol=end_name,
                            snes=[first, end], pc=[pc_first, pc_end]))

    restored = bytearray(compiled)
    word_start, word_end = extents[0]['snes']
    for site, name, length in RESIDENT_READER_HOOKS:
        target = _symbol(symbols, name)
        _require(word_start <= target < word_end,
                 f'NATIVE_BUILD_READER_TARGET_OUTSIDE_KERNEL:{name}')
        at = native.pc(site)
        expected = bytes([0x22]) + target.to_bytes(3, 'little') + b'\xEA' * (length - 4)
        _require(compiled[at:at + length] == expected,
                 f'NATIVE_BUILD_RESIDENT_READER_HOOK_MISMATCH:{site:06X}')
        for first, end, role in protected:
            _require(at >= end or at + length <= first,
                     f'NATIVE_BUILD_RESIDENT_HOOK_OVERLAPS_SAVED_SOURCE:{role}')
        restored[at:at + length] = source[at:at + length]
    # Only the validated resident hook spans are normalized. Every remaining
    # native operand/opcode must still bind the saved dictionaries exactly.
    native.verify_dictionary_readers(bytes(restored), entries)

    data_pc, data_size = native.RESIDENT_DATA_PC, native.RESIDENT_DATA_CAPACITY
    expected_resources = bytearray(source[data_pc:data_pc + data_size])
    for write in prep['resource_writes']:
        first = write['pc']
        end = first + len(write['after'])
        _require(compiled[first:end] == write['after'],
                 f'NATIVE_BUILD_COMPILED_RESOURCE_CHANGED:{write["purpose"]}')
        offset = first - data_pc
        expected_resources[offset:offset + end - first] = write['after']
    _require(compiled[data_pc:data_pc + data_size] == bytes(expected_resources),
             'NATIVE_BUILD_COMPILED_RESOURCE_GAP_CHANGED')

    first = native.pc(code_address)
    before, after = source[first:first + code_size], compiled[first:first + code_size]
    reseal_writes, code = _code_reseal(source, capacity, bank, entries,
        ReaderCodeReplacement(_sha(before), after))
    directory = source[native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE]
    expected_directory = next((write['after'] for write in reseal_writes
        if write['pc'] == native.DIRECTORY_PC), directory)
    installed = compiled[native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE]
    needed = installed != expected_directory
    _require(not needed or (allow_stale_directory and installed == directory),
             'NATIVE_BUILD_COMPILED_DIRECTORY_SEAL_MISMATCH')
    if not needed:
        _require(native.read_native_directory(compiled) == (capacity, bank, entries),
                 'NATIVE_BUILD_COMPILED_DIRECTORY_LAYOUT_CHANGED')
    return dict(schema='special_overworld.native_compiled_seal.v1',
        source_rom_sha256=_sha(source), compiled_rom_sha256=_sha(compiled),
        native_export_sha256=prep['native_export_sha256'],
        directory_bytes=expected_directory, directory_sha256=_sha(expected_directory),
        needed_reassembly=needed, first_pass_stale_directory_accepted=needed,
        reader_code=code, saved_payloads_preserved=True,
        native_prefixes_preserved=not any(row['changed'] for row in prefix_transforms),
        native_prefixes_preserved_except_compiler_owned_fields=True,
        compiler_owned_prefix_transforms=prefix_transforms,
        pointer_mirrors_preserved=True,
        reader_bindings_validated=True, resident_reader_hook_count=len(RESIDENT_READER_HOOKS),
        remaining_dictionary_readers_validated=True, runtime_code_extents=extents,
        resource_placement_count=len(prep['resource_writes']),
        resource_writes_verified=True, unclaimed_resource_bytes_preserved=True,
        unresolved_full_residency_unknowns=prep['unresolved_full_residency_unknowns'],
        full_residency_ready=False, runtime_admission=False, publication_authorized=False)


def verify_revision4_compiled_output(source, exported, compiled, symbols, *,
                                    graphics_root=None):
    """Strict final composition proof; a stale ID300 seal always refuses."""
    return plan_revision4_compiled_seal(source, exported, compiled, symbols,
                                      graphics_root=graphics_root)
