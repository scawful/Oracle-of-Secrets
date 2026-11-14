"""Offline native resource preparation; ordinary Build admission is unchanged.

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


def _validate_reader_bindings(source, entries, *, capacity=native.MAP_CAPACITY, revision=4):
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
            end = first + rows * native.entry_spec(key, capacity, revision)[2]
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


def _code_reseal(source, capacity, bank, entries, replacement, *, revision=4):
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
    directory = (native.encode_revision4_directory(bytes(image), rows,
        tail_actor_bank=bank, capacity=capacity) if revision == 4 else
        native._encode_native_directory(bytes(image), rows, tail_actor_bank=bank,
                                        capacity=capacity, revision=revision))
    image[native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE] = directory
    _require(native.read_native_directory(bytes(image),
        experimental_page_tile16=revision == 5) == (capacity, bank, entries),
             'NATIVE_BUILD_RESEAL_CHANGED_LAYOUT')
    # The sole payload exception is explicit code300. Binding records and every
    # authored table/dictionary/stream/appearance/identity payload stay exact.
    for key, (at, rows) in entries.items():
        if key == 300:
            continue
        width = native.entry_spec(key, capacity, revision)[2]
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


def prepare_native_compilation(source, exported, *, data_pc, capacity,
                               preimage, reader_code_replacement=None,
                               graphics_root=None, experimental_page_tile16=False):
    """Return pure compilation inputs and preimage-bound writes, not a ROM.

    ``data_pc/capacity`` name the caller-owned current resident reservation;
    they grant no allocation authority. Each write retains its exact preimage,
    and bank padding is deliberately absent from the write list. The resource
    constants do not enable flags or replace reader_constants(). A separate
    reviewed orchestrator must assemble, validate the whole composition and
    enforce the existing ordinary Build/publication gates.
    """
    _require(type(source) is bytes, 'NATIVE_BUILD_SAVED_SOURCE_REQUIRED')
    _require(type(experimental_page_tile16) is bool, 'NATIVE_BUILD_EXPERIMENTAL_ADMISSION_INVALID')
    installed = native.read_native_directory(
        source, experimental_page_tile16=experimental_page_tile16)
    revision = (struct.unpack_from('<H', source, native.DIRECTORY_PC + 8)[0]
                if installed is not None else None)
    _require(installed is not None and revision in ((4, 5) if experimental_page_tile16 else (4,)),
             'NATIVE_BUILD_REVISION4_REQUIRED')
    map_count, bank, entries = installed
    _require(map_count == native.MAP_CAPACITY,
             'NATIVE_BUILD_CURRENT_ENGINE_REQUIRES192')
    native.verify_dictionary_readers(source, entries)
    call_spans = _validate_reader_bindings(source, entries, capacity=map_count, revision=revision)
    _require(type(data_pc) is int and type(capacity) is int
             and data_pc == native.RESIDENT_DATA_PC
             and capacity == native.RESIDENT_DATA_CAPACITY,
             'NATIVE_BUILD_RESIDENT_RESERVATION_MISMATCH')
    _require(type(preimage) is bytes and len(preimage) == capacity
             and source[data_pc:data_pc + capacity] == preimage,
             'NATIVE_BUILD_RESIDENT_PREIMAGE_MISMATCH')
    # This narrowly selected spill reservation has a measured zero preimage
    # in the editable source. A later owner/data import must not be overwritten.
    _require(source[native.RESIDENT_SPILL_PC:native.RESIDENT_SPILL_END]
             == bytes(native.RESIDENT_SPILL_END-native.RESIDENT_SPILL_PC),
             'NATIVE_BUILD_RESIDENT_SPILL_PREIMAGE_CHANGED')
    _require(all(data_pc >= end or data_pc + capacity <= first
                 for first, end in call_spans),
             'NATIVE_BUILD_RESIDENT_OVERLAPS_READER_CALL')
    for key, (at, rows) in entries.items():
        size = rows * native.entry_spec(key, map_count, revision)[2]
        pc = native.pc(at)
        _require(data_pc >= pc + size or data_pc + capacity <= pc,
                 'NATIVE_BUILD_RESIDENT_OVERLAPS_SAVED_PAYLOAD')
    reseal_writes, code = _code_reseal(source, map_count, bank, entries,
                                      reader_code_replacement, revision=revision)
    # This validates fresh export identity/profiles/topology/resolved bytes;
    # the retained packer and emitter own all byte formats and bank placement.
    plan = resources.plan_saved_native_terrain(source, exported,
        graphics_root=graphics_root, experimental_page_tile16=experimental_page_tile16)
    abi = resident.plan_native_resident_abi(plan, tile16_count=entries[400][1],
        experimental_page_tile16=experimental_page_tile16)
    emission = resident.emit_native_resident_abi(abi, data_pc=data_pc,
        capacity=capacity, preimage=preimage,
        excluded_pc_spans=native.RESIDENT_DATA_EXCLUDED_PC,
        experimental_page_tile16=experimental_page_tile16)
    runtime = resident.resident_runtime_inputs(abi, emission, preimage=preimage,
        experimental_page_tile16=experimental_page_tile16)
    binary = bytes.fromhex(emission['payload_hex'])
    writes = []
    for row in emission['placements']:
        first, end = row['pc']
        offset = row['binary_offset']
        raw = binary[offset:offset + end - first]
        _require(_sha(raw) == row['sha256'], 'NATIVE_BUILD_EMISSION_MISMATCH')
        writes.append(_write(source, first, raw, row['role']))
    result = dict(schema='special_overworld.native_build_preparation.v1',
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

    if revision == 5:
        result.update(schema='special_overworld.native_build_preparation.experimental-v2',
                      semantic_source_contract=_semantic_source_contract(source, map_count, entries))
    return result


def _semantic_source_contract(source, capacity, entries):
    """Expose authenticated existing413 storage, never choose code/allocation."""
    address, count = entries[413]
    kind, _, stride = native.entry_spec(413, capacity, 5)
    first = native.pc(address)
    raw = source[first:first + count * stride]
    decoded = native.decode_page_tile16(raw, capacity)
    records = struct.unpack_from('<H', source, native.DIRECTORY_PC + 18)[0]
    record_pc = next(native.DIRECTORY_PC + 32 + index * 16 for index in range(records)
        if struct.unpack_from('<H', source, native.DIRECTORY_PC + 32 + index * 16)[0] == 413)
    return dict(revision=5, capacity=capacity, table_id=413, kind=kind,
        rows_snes=address, rows_pc=first, count=count, stride=stride,
        populated_rows=len(decoded), payload_sha256=_sha(raw),
        payload_crc32=struct.unpack_from('<I', source, record_pc + 12)[0],
        directory_record_pc=record_pc, source_rom_sha256=_sha(source),
        directory_sha256=_sha(source[native.DIRECTORY_PC:
            native.DIRECTORY_PC + native.DIRECTORY_SIZE]),
        directory_crc32=struct.unpack_from('<I', source, native.DIRECTORY_PC + 28)[0],
        consumer_bindings=dict(SPECIAL_OVERWORLD_SEMANTIC_REVISION=5,
            SPECIAL_OVERWORLD_SEMANTIC_CAPACITY=capacity,
            SPECIAL_OVERWORLD_SEMANTIC_ROWS=address, SPECIAL_OVERWORLD_SEMANTIC_COUNT=count,
            SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE=None, SPECIAL_OVERWORLD_SEMANTIC_CODE_END=None),
        required_semantic_consumers=list(resources.PAGE_TILE16_RUNTIME_REQUIREMENTS),
        effective_source_lookup='physical_page/local12bit_id/quadrant; global400 fallback',
        source_word_bits_preserved=True, code_extent_bound=False,
        runtime_admission=False, allocation_granted=False)


def prepare_revision4_compilation(source, exported, *, data_pc, capacity,
                                  preimage, reader_code_replacement=None,
                                  graphics_root=None):
    """Strict legacy API; experimental callers must select the generic API."""
    return prepare_native_compilation(source, exported, data_pc=data_pc,
        capacity=capacity, preimage=preimage,
        reader_code_replacement=reader_code_replacement, graphics_root=graphics_root)


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



# Exact native instruction prefixes replaced by the semantic source consumers.
# The source operands may retain a legal LoROM mirror; compare their PC identity.
SEMANTIC_READER_HOOKS = (
    (0x008864, 'Lyra_SemanticCollisionWord', b''),
    (0x1BBEDF, 'Lyra_SemanticTileActionWord', bytes.fromhex(
        '0A0A8506A5002908004A4A0406A50229010005060AAA')),
    (0x1BBF1E, 'Lyra_SemanticHammerWord', bytes.fromhex('0A0A0AAA')),
    (0x1BC027, 'Lyra_SemanticLiftWord', bytes.fromhex(
        '0A0A8506A5022908004A4A0406A5004A4A4A29010005060AAA')),
)
SEMANTIC_ENTRANCE_SITES = (
    ('Lyra_SemanticEntranceSite2', 'Lyra_SemanticEntrance2'),
    ('Lyra_SemanticNeighborSite0', 'Lyra_SemanticNeighbor0'),
    ('Lyra_SemanticCastleSite4', 'Lyra_SemanticEntrance4'),
    ('Lyra_SemanticCastleSite6', 'Lyra_SemanticEntrance6'),
    ('Lyra_SemanticNeighborSite4', 'Lyra_SemanticNeighbor4'),
    ('Lyra_SemanticNeighborSite6', 'Lyra_SemanticNeighbor6'),
    ('Lyra_SemanticPlainSite4', 'Lyra_SemanticEntrance4'),
    ('Lyra_SemanticPlainSite6', 'Lyra_SemanticEntrance6'),
)


SEMANTIC_SPECIAL_SITES = (
    ('Lyra_SemanticSpecialEntrySite0', 'Lyra_SemanticEntrance0',
     'Overworld_CheckForSpecialOverworldTrigger', 'GetMap16Tile'),
    ('Lyra_SemanticSpecialReturnSite0', 'Lyra_SemanticEntrance0',
     'SpecialOverworld_CheckForReturnTrigger', 'LoadSpecialOverworld'),
)


def _semantic_compiled_readers(source, compiled, entries, symbols, protected):
    """Validate actual enabled consumers before normalizing a comparison copy."""
    code_pc = native.pc(native.SEMANTIC_CODE_BASE)
    code_limit = native.pc(native.SEMANTIC_CODE_LIMIT - 1) + 1
    native.semantic_reader_constants(source, code_preimage=source[code_pc:code_limit],
                                     experimental_page_tile16=True)
    first = _symbol(symbols, 'Lyra_SemanticCodeStart')
    end = _symbol(symbols, 'Lyra_SemanticCodeEnd', exclusive_end=True)
    _require(first == native.SEMANTIC_CODE_BASE and first < end <= native.SEMANTIC_CODE_LIMIT,
             'NATIVE_BUILD_SEMANTIC_CODE_EXTENT_MISMATCH')
    first_pc, end_pc = native.pc(first), native.pc(end - 1) + 1
    _require(compiled[first_pc:end_pc] != source[first_pc:end_pc],
             'NATIVE_BUILD_SEMANTIC_CODE_NOT_EMITTED')
    _require(compiled[end_pc:code_limit] == source[end_pc:code_limit],
             'NATIVE_BUILD_SEMANTIC_UNCLAIMED_CODE_CHANGED')
    _require(all(first_pc >= limit or end_pc <= at for at, limit, _ in protected),
             'NATIVE_BUILD_SEMANTIC_CODE_OVERLAPS_SAVED_SOURCE')
    targets, hooks, normalized = {}, [], []

    def hook(site, name, length):
        target = _symbol(symbols, name)
        _require(first <= target < end, 'NATIVE_BUILD_SEMANTIC_TARGET_OUTSIDE_CODE:' + name)
        targets[name] = target
        at = native.pc(site)
        _require((site & 0xFFFF) + length <= 0x10000
                 and all(at >= limit or at + length <= start for start, limit, _ in protected),
                 'NATIVE_BUILD_SEMANTIC_HOOK_OVERLAPS_SAVED_SOURCE')
        expected = b'\x22' + target.to_bytes(3, 'little') + b'\xEA' * (length - 4)
        _require(compiled[at:at + length] == expected,
                 f'NATIVE_BUILD_SEMANTIC_HOOK_MISMATCH:{site:06X}')
        hooks.append(dict(site=site, target=target, symbol=name, length=length))

    for site, name, prefix in SEMANTIC_READER_HOOKS:
        at, length = native.pc(site), len(prefix) + 4
        original = source[at:at + length]
        _require(original[:len(prefix)] == prefix and original[len(prefix)] == 0xBF
                 and native.pc(int.from_bytes(original[-3:], 'little')) == native.pc(entries[400][0]),
                 f'NATIVE_BUILD_SEMANTIC_SOURCE_PREIMAGE_MISMATCH:{site:06X}')
        hook(site, name, length)
        normalized.append((at, at + length))
    entrance = _symbol(symbols, 'Overworld_UseEntrance')
    entrance_end = _symbol(symbols, 'Lyra_SemanticEntranceConsumersEnd', exclusive_end=True)
    _require(entrance < entrance_end and entrance_end - entrance <= 0x2000
             and entrance >> 16 == (entrance_end - 1) >> 16,
             'NATIVE_BUILD_SEMANTIC_ENTRANCE_EXTENT_INVALID')
    previous = entrance - 1
    for label, name in SEMANTIC_ENTRANCE_SITES:
        site = _symbol(symbols, label)
        _require(previous < site and entrance <= site and site + 4 <= entrance_end,
                 'NATIVE_BUILD_SEMANTIC_ENTRANCE_SITE_INVALID:' + label)
        hook(site, name, 4)
        previous = site
    for label, name, start_name, end_name in SEMANTIC_SPECIAL_SITES:
        start = _symbol(symbols, start_name)
        limit = _symbol(symbols, end_name, exclusive_end=True)
        site = _symbol(symbols, label)
        _require(start < limit and limit - start <= 0x2000
                 and start >> 16 == (limit - 1) >> 16
                 and start <= site and site + 4 <= limit,
                 'NATIVE_BUILD_SEMANTIC_SPECIAL_SITE_INVALID:' + label)
        hook(site, name, 4)
    _require(len(set(targets.values())) == len(targets),
             'NATIVE_BUILD_SEMANTIC_TARGET_ALIASED')
    return normalized, dict(code_extent=dict(snes=[first, end], pc=[first_pc, end_pc]),
        hooks=hooks, hook_count=len(hooks), source_preimages_validated=True,
        actual_compiled_consumers_verified=True, normalization_comparison_only=True)


def plan_native_compiled_seal(source, exported, compiled, symbols, *,
                              allow_stale_directory=False, graphics_root=None,
                              experimental_page_tile16=False, semantic_readers=False):
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
    _require(type(semantic_readers) is bool and (not semantic_readers or experimental_page_tile16 is True),
             'NATIVE_BUILD_SEMANTIC_ADMISSION_INVALID')
    prep = prepare_native_compilation(source, exported,
        data_pc=native.RESIDENT_DATA_PC, capacity=native.RESIDENT_DATA_CAPACITY,
        preimage=source[native.RESIDENT_DATA_PC:
                        native.RESIDENT_DATA_PC + native.RESIDENT_DATA_CAPACITY],
        graphics_root=graphics_root, experimental_page_tile16=experimental_page_tile16)
    capacity, bank, entries = native.read_native_directory(
        source, experimental_page_tile16=experimental_page_tile16)
    revision = struct.unpack_from('<H', source, native.DIRECTORY_PC + 8)[0]
    _require(not semantic_readers or revision == 5, 'NATIVE_BUILD_SEMANTIC_REVISION5_REQUIRED')
    code_address, code_size = entries[300]
    code_start = _symbol(symbols, 'Lyra_CurrentNativeCodeStart')
    code_end = _symbol(symbols, 'Lyra_CurrentNativeCodeEnd', exclusive_end=True)
    _require(code_start == code_address and code_end == code_address + code_size,
             'NATIVE_BUILD_COMPILED_READER_EXTENT_MISMATCH')
    protected = [(native.DIRECTORY_PC, native.DIRECTORY_PC + native.DIRECTORY_SIZE,
                  'directory')]
    for key, (address, rows) in entries.items():
        first, length = native.pc(address), rows * native.entry_spec(key, capacity, revision)[2]
        protected.append((first, first + length, f'ID{key}'))
        if key != 300:
            _require(compiled[first:first + length] == source[first:first + length],
                     f'NATIVE_BUILD_COMPILED_SAVED_PAYLOAD_CHANGED:ID{key}')
    call_spans = _validate_reader_bindings(source, entries, capacity=capacity, revision=revision)
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

    semantic_spans, semantic_proof = (
        _semantic_compiled_readers(source, compiled, entries, symbols, protected)
        if semantic_readers else ([], None))
    restored = bytearray(compiled)
    for at, end in semantic_spans:
        restored[at:end] = source[at:end]
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
    # Retain the complete old4E/4F gap check and add the new spill interval.
    # The skipped50:8000-A000 reservation belongs to D4's own source/checks,
    # not this atlas. It may contain normally compiled water-control code.
    cursor = data_pc
    for first, end in (*native.RESIDENT_DATA_EXCLUDED_PC,
                       (data_pc + data_size, data_pc + data_size)):
        _require(compiled[cursor:first] == bytes(expected_resources[
            cursor-data_pc:first-data_pc]),
                 'NATIVE_BUILD_COMPILED_RESOURCE_GAP_CHANGED')
        cursor = end

    first = native.pc(code_address)
    before, after = source[first:first + code_size], compiled[first:first + code_size]
    reseal_writes, code = _code_reseal(source, capacity, bank, entries,
        ReaderCodeReplacement(_sha(before), after), revision=revision)
    directory = source[native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE]
    expected_directory = next((write['after'] for write in reseal_writes
        if write['pc'] == native.DIRECTORY_PC), directory)
    installed = compiled[native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE]
    needed = installed != expected_directory
    _require(not needed or (allow_stale_directory and installed == directory),
             'NATIVE_BUILD_COMPILED_DIRECTORY_SEAL_MISMATCH')
    if not needed:
        _require(native.read_native_directory(compiled,
            experimental_page_tile16=experimental_page_tile16) == (capacity, bank, entries),
                 'NATIVE_BUILD_COMPILED_DIRECTORY_LAYOUT_CHANGED')
    result = dict(schema='special_overworld.native_compiled_seal.v1',
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

    if revision == 5:
        result.update(schema='special_overworld.native_compiled_seal.experimental-v2',
                      semantic_source_contract=prep['semantic_source_contract'])
        if semantic_readers:
            result['semantic_readers'] = semantic_proof
    return result


def plan_revision4_compiled_seal(source, exported, compiled, symbols, *,
                                allow_stale_directory=False, graphics_root=None):
    """Strict legacy seal; does not silently admit experimental revision5."""
    return plan_native_compiled_seal(source, exported, compiled, symbols,
        allow_stale_directory=allow_stale_directory, graphics_root=graphics_root)


def verify_native_compiled_output(source, exported, compiled, symbols, *,
                                  graphics_root=None, experimental_page_tile16=False,
                                  semantic_readers=False):
    """Strict final composition; explicit experimental source admission only."""
    return plan_native_compiled_seal(source, exported, compiled, symbols,
        graphics_root=graphics_root, experimental_page_tile16=experimental_page_tile16,
        semantic_readers=semantic_readers)


def verify_revision4_compiled_output(source, exported, compiled, symbols, *,
                                    graphics_root=None):
    """Strict final composition proof; a stale ID300 seal always refuses."""
    return plan_revision4_compiled_seal(source, exported, compiled, symbols,
                                      graphics_root=graphics_root)
