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
                                  preimage, reader_code_replacement=None):
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
    plan = resources.plan_saved_native_terrain(source, exported)
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
