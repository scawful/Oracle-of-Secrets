#!/usr/bin/env python3
"""Private exact-save producer transfer and standalone full32 terrain compiler.

The source declaration transfers a fixed native producer extent; no space scan
creates authority. Yaze must enforce an attachment before this compiler accepts
the grant. Outputs are standalone payloads and exact write plans, never a ROM.
Actor, appearance, endpoint and ordinary runtime admission remain separate.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import lyra_native_streams as N
import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_composition as C
import lyra_project_prepare as Q
import lyra_project_publisher as P
import lyra_project_tile32 as T
from lyra_project_terrain import Allocation, compile_terrain, decode_literal_stream

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'Config/lyra_private_reservation.json'
YAZE_PINS = ROOT / 'Config/lyra_private_yaze_sources.json'
KIND = 'lyra.private_exact_save_producer_reservation.v1'
SOURCE = '44f46bb06f589a39275ff40d35e40a3a5652502a981205eaebb54f4c447a3ee2'
TERRAIN = 'e335abdf782a54b3486cec029d3640fc548ea88af924c79c75be2d4d053cff90'
IDS = (13992, 14436)
STREAM = (0x133D3A, 0x138000)  # Half-open; 66 literal streams end exactly at138000.
FULL_MAPS = list(range(0xA0, 0xC0))
TRANSFER = dict(**{'from': 'yaze.native_overworld_terrain'},
                to='oracle.lyra_private_candidate', native_terrain_policy='refuse_changes')
DIRECTORY_SHA = '30033e360b42a6e26718f7c2f5cf58ef9fb30b9fd33d5b4ffca2f536157110eb'
OLD_A0 = (0x132000, 0x132400)


def declaration():
    """A narrow source-owner declaration, independent of the historical ledger."""
    value = json.loads(POLICY.read_bytes())
    R.require(set(value) == {'kind', 'scope', 'production_admission', 'source_rom_sha256',
        'producer_transfer', 'tile32_id_range', 'stream_pc_range', 'dictionary_bases_pc',
        'packed_preimages', 'stream_preimage'} and value['kind'] == KIND
        and value['scope'] == 'private_candidate_only' and value['production_admission'] is False
        and value['source_rom_sha256'] == SOURCE and value['producer_transfer'] == TRANSFER
        and value['tile32_id_range'] == list(IDS) and value['stream_pc_range'] == list(STREAM)
        and value['dictionary_bases_pc'] == list(A.TILE32_BASES),
        'Unsupported private producer transfer')
    spans = [[base + IDS[0] // 4 * 6, base + IDS[1] // 4 * 6] for base in A.TILE32_BASES]
    R.require(value['packed_preimages'] == [dict(pc=span,
        sha256='a81832a1890ee3808d233633a5cc4f90cd77edd8ef68781c8c1701dea4c09175') for span in spans]
        and value['stream_preimage'] == dict(pc=list(STREAM),
        sha256='412194777d0a23bcff78ea17b498da632466066462a6f0f2dc28b2758fced844'),
        'Unsupported private packed/stream preimage declaration')
    return value


def source_receipt(source):
    """Close actual native references, packed groups and every decoder read."""
    policy = declaration()
    R.require(type(source) is bytes and len(source) == 0x400000 and R.sha(source) == SOURCE,
              'Private producer reservation requires the exact saved source')
    for row in [*policy['packed_preimages'], policy['stream_preimage']]:
        a, b = row['pc']
        R.require(R.sha(source[a:b]) == row['sha256'], 'Private producer preimage differs')
    spans = [tuple(row['pc']) for row in policy['packed_preimages']] + [STREAM]
    R.require(all(b <= OLD_A0[0] or a >= OLD_A0[1] for a, b in spans),
              'Private grant overlaps the existing A0 slots')
    rows = N.reject_stream_aliases(source, spans)
    R.require(T.digest(rows) == DIRECTORY_SHA, 'Exact native pointer/alias directory differs')
    references, by_span = [], collections.defaultdict(list)
    windows = ((0x58000, 0x5FE70), (0x60000, 0x6411F), (0x130000, 0x138000))
    external = []
    for row in rows:
        by_span[tuple(row['pc'])].append([row['map_id'], row['table']])
        if not any(a <= row['pc'][0] < row['pc'][1] <= b for a, b in windows):
            external.append(row)
    for area in range(160):
        planes = [N._plane(source, area, table)[0] for table in N.POINTER_TABLES]
        R.require(all(len(p) == 256 for p in planes), 'Incomplete native Tile32 plane')
        for cell, (h, l) in enumerate(zip(*planes)):
            tile = h << 8 | l
            R.require(tile < 0x4540 and not IDS[0] <= tile < IDS[1],
                      f'Private Tile32 producer transfer conflicts with native map{area:02X}')
            references.append([area, cell, tile])
    aliases = [dict(pc=list(span), consumers=users) for span, users in sorted(by_span.items()) if len(users) > 1]
    R.require(len(rows) == 320 and len(by_span) == 317 and len(aliases) == 3 and len(external) == 18,
              'Exact saved native alias/external closure differs')
    claim, _ = R.reservation_claim()
    retained = T.ownership(source, claim)
    return dict(native_maps=160, native_planes=320, native_streams_sha256=T.digest(rows),
        native_references_sha256=T.digest(references), exact_alias_groups=aliases,
        external_saved_reference_rows=external, native_partition_sha256=retained['native_partition_sha256'],
        retained_native_ids=retained['retained_native_ids'],
        retained_native_references=retained['retained_native_references'],
        preserved_old_a0=dict(pc=list(OLD_A0), sha256=R.sha(source[slice(*OLD_A0)])))


def require_no_named_conflicts(ledger, *, tile32_range=None, stream_ranges=None):
    """Unemitted named owners count too; the explicit transfer is only native terrain."""
    ids = IDS if tile32_range is None else tile32_range
    spans = ([tuple(row['pc']) for row in declaration()['packed_preimages']] + [STREAM]
             if tile32_range is None and stream_ranges is None else
             [(base + ids[0] // 4 * 6, base + ids[1] // 4 * 6) for base in A.TILE32_BASES]
             + [tuple(span) for span in (stream_ranges or ())])
    owners = list(ledger.get('claims', []))
    owners += [dict(id=row['id'], space=row.get('space'), base=row.get('address'),
                    size=row['count'] * row['stride']) for row in ledger.get('tables', [])]
    for claim in ledger.get('rom_candidate_reservations', []):
        owners += [dict(id=claim.get('id'), space='pc_rom', base=row['pc'][0],
                        size=row['pc'][1] - row['pc'][0]) for row in claim.get('regions', [])]
        reservation = claim.get('tile32_candidate_reservation')
        if reservation:
            lo, hi = reservation['id_range']
            owners.append(dict(id=claim.get('id'), space='tile32_id', base=lo, size=hi - lo))
    for owner in owners:
        space, lo, size = owner.get('space'), owner.get('base'), owner.get('size')
        if space not in ('tile32_id', 'pc_rom', 'snes_rom') or lo is None or size is None:
            continue
        R.require(type(lo) is int and type(size) is int and size > 0, 'Invalid named private ownership boundary')
        hi = lo + size
        if space == 'snes_rom':
            lo, hi = A.pc(lo), A.pc(hi - 1) + 1
        conflict = (lo < ids[1] and ids[0] < hi) if space == 'tile32_id' else any(
            lo < b and a < hi for a, b in spans)
        R.require(not conflict, f"Private producer grant conflicts with named owner {owner.get('id')}")


def _intake(request_path):
    request_path = Path(request_path).resolve(strict=True)
    raw = request_path.read_bytes()
    value = json.loads(raw)
    R.require(value.get('kind') == Q.KIND and value.get('selected_maps') == [0x37, 0xA1]
              and value.get('production_admission') is False, 'Expected unchanged current37/A1 request')
    # The current request and historical controls retain their original bindings.
    rows = value['inputs']
    data = {key: Q.read_bound(row) for key, row in rows.items()}
    source, terrain = data['saved_rom'], data['terrain']
    R.require(R.sha(terrain) == TERRAIN, 'Private reservation requires the exact saved full32 terrain')
    native = source_receipt(source)
    document = C._document(terrain, data['observation'], source)
    control_rows, frozen, fixture = Q.controls(value['qualification_request']['path'])
    Q.read_bound(value['qualification_request'])
    claim, ledger_hash = R.reservation_claim(rows['ledger']['path'])
    require_no_named_conflicts(json.loads(data['ledger']))
    R.require(value['assignment'] == Q.current_assignment(source, terrain, document, frozen, rows['ledger']['path']),
              'Original current source assignment differs')
    # The old ordinary allocator and ledger are independently validated and kept.
    R.require(not Q.resource_report(source, rows['ledger']['path']), 'Historical resources differ')
    bindings = [dict(path=str(request_path), sha256=R.sha(raw)), *rows.values(),
                value['qualification_request'], *control_rows.values(), fixture]
    directory, closure = A.render_dependency_plan(FULL_MAPS, [])
    R.require(list(closure) == FULL_MAPS, 'Full32 natural render closure differs')
    missing = C._missing(source, document, FULL_MAPS)
    frozen_dict = dict(frozen)
    frozen_quads = {q for _, q in frozen}
    extra = sorted(set(missing) - frozen_quads)
    R.require(len(missing) == 566 and len(extra) == 451, 'Exact full32 definition request differs')
    tail = list(range(0x4533, 0x453D))
    supplement = list(range(*IDS))
    pairs = tuple(frozen) + tuple(zip(tail + supplement[:441], extra))
    R.require(len(pairs) == 566 and len(set(i for i, _ in pairs)) == 566
              and len(set(q for _, q in pairs)) == 566, 'Private joint assignments alias')
    R.require(dict(pairs).items() >= frozen_dict.items(), 'Frozen115 assignments differ')
    R.require(all(Q.read_bound(row) is not None for row in bindings), 'Private inputs changed')
    return source, terrain, document, directory, pairs, native, bindings, ledger_hash


def create_attachment(request_path):
    """Build a source-bound attachment; it alone cannot authorize compilation."""
    source, terrain, document, directory, pairs, native, bindings, ledger_hash = _intake(request_path)
    policy = declaration()
    policy.update(request=Q.bound(request_path), inputs=sorted(bindings, key=lambda row: row['path']),
        source_declaration=Q.bound(POLICY), terrain_sha256=R.sha(terrain),
        oracle_source_bindings=[Q.bound(ROOT / name) for name in (
            'Scripts/Build/lyra_private_reservation.py', 'Scripts/Build/lyra_project_admission.py',
            'Scripts/Build/lyra_project_terrain.py', 'Scripts/Build/lyra_project_tile32.py',
            'Scripts/Build/lyra_native_streams.py')],
        historical_ledger_sha256=ledger_hash, native_receipt=native,
        selected_maps=FULL_MAPS, spare_tile32_ids=list(range(IDS[1] - 3, IDS[1])),
        assignments=[dict(tile32_id=i, quadrants=list(q)) for i, q in pairs],
        production_maps=[], production_edge_ids=[], actors_compiled=False,
        runtime_admission=False, rom_written=False)
    return policy


def verify_attachment(source, attachment):
    R.require(type(attachment) is dict and attachment.get('source_rom_sha256') == R.sha(source) == SOURCE,
              'Private attachment source differs')
    R.require(attachment == create_attachment(attachment['request']['path']),
              'Private exact-save attachment differs from source-owner declaration')


def verify_producer_evidence(attachment, evidence):
    """Require concrete source/test/binary bindings, never a caller boolean."""
    R.require(type(evidence) is dict and evidence.get('kind') == 'lyra.private_producer_enforcement_receipt.v1'
              and evidence.get('source_rom_sha256') == SOURCE
              and evidence.get('attachment_sha256') == T.digest(attachment),
              'Missing source-bound Yaze producer enforcement receipt')
    bindings = evidence.get('source_bindings')
    verification = evidence.get('verification', {})
    R.require(type(bindings) is list and len(bindings) >= 3 and verification.get('exit_code') == 0
              and type(verification.get('command')) is str and verification['command']
              and type(verification.get('tests')) is list and verification['tests']
              and type(verification.get('binary')) is dict and type(verification.get('log')) is dict,
              'Yaze producer evidence needs source, binary and successful focused test bindings')
    for row in [*bindings, verification['binary'], verification['log']]:
        Q.read_bound(row)
    R.require(YAZE_PINS.is_file(), 'Reviewed Yaze producer source pins unavailable')
    pins = json.loads(YAZE_PINS.read_bytes())
    R.require(pins.get('kind') == 'lyra.reviewed_yaze_private_producer_sources.v1'
              and type(pins.get('source_root')) is str
              and Path(pins['source_root']).is_absolute()
              and type(pins.get('sources')) is list and pins['sources'], 'Yaze producer source review pins missing')
    actual = {}
    for row in bindings:
        suffixes = [pin['path'] for pin in pins['sources']
                    if Path(row['path']) == Path(pins['source_root']) / pin['path']]
        R.require(len(suffixes) == 1 and suffixes[0] not in actual, 'Unexpected/duplicate Yaze producer evidence source')
        actual[suffixes[0]] = row['sha256']
    R.require(actual == {row['path']: row['sha256'] for row in pins['sources']},
              'Yaze producer evidence differs from reviewed enforcement source')


def allocation_value(attachment, evidence):
    ids = [row['tile32_id'] for row in attachment['assignments']]
    return dict(kind='lyra.project_runtime_allocation.v1', source_rom_sha256=SOURCE,
        expanded_size=0x400000, table_range=[A.TABLE_START, A.TABLE_END],
        code_range=[A.CODE_START, A.CODE_END], stream_ranges=[list(STREAM)], owned_tile32_ids=ids,
        private_reservation=dict(attachment=attachment, producer_evidence=evidence),
        reservation=dict(kind='lyra.private_producer_reservation.v1'),
        tile32_assignment=dict(assignments=attachment['assignments']))


def verify_private_allocation(value, source):
    private = value.get('private_reservation')
    R.require(type(private) is dict and set(private) == {'attachment', 'producer_evidence'},
              'Malformed private producer allocation')
    attachment, evidence = private['attachment'], private['producer_evidence']
    verify_attachment(bytes(source), attachment)
    verify_producer_evidence(attachment, evidence)
    R.require(value == allocation_value(attachment, evidence),
              'Private allocation exceeds the exact producer grant')


def compile_native_plan(source, document, granted, directory, *, native_copy_maps=(),
                        protected_spans=(), spare_tile32_ids=(), current_source_profile=None):
    """Compile current saved terrain in memory using an explicit allocation.

    This pure compiler does not grant the allocation or authorize publication.
    Callers must validate ownership and producer enforcement before publishing.
    The historical CLI below retains its exact attachment/evidence gates.
    """
    R.require(type(source) is bytes and len(source) in (0x200000, 0x400000),
              'Current full32 planning requires an unheadered2MiB or4MiB source')
    if document.gameplay_areas:
        R.require(current_source_profile is not None,
                  'CURRENT_GAMEPLAY_AREAS_NATIVE_UNBOUND: historical compiler has no authored area consumer')
        expected_directory = A.render_dependency_plan(FULL_MAPS, document=document)[0]
        R.require(directory == expected_directory,
                  'CURRENT_GAMEPLAY_AREAS_RENDER_MISMATCH: directory differs from saved gameplay areas')
    original_source = source
    source_hash, source_size = R.sha(source), len(source)
    source = A.expanded_rom(source)
    R.require(isinstance(granted, Allocation) and granted.tile32_assignments is not None,
              'Current full32 planning requires explicit reviewed Tile32 assignments')
    R.require(type(granted.tile32_capacity) is int and granted.tile32_capacity == 0x4540,
              'Current native profile requires Tile32 capacity0x4540')
    R.require(type(native_copy_maps) in (tuple, list)
              and all(type(area) is int and 0 <= area < 160 for area in native_copy_maps)
              and len(native_copy_maps) == len(set(native_copy_maps)), 'Invalid native copy maps')
    missing = C._missing(source, document, FULL_MAPS)
    R.require(len(missing) <= len(granted.owned_tile32_ids),
              f'Current full32 Tile32 capacity conflict: {len(missing)} required, '
              f'{len(granted.owned_tile32_ids)} explicitly allocated')
    # The native copy option preserves the historical37 payload. New current
    # plans need not spend space copying a native map whose pointers stay intact.
    copy_bytes = len(native_copy_maps) * 518
    ranges = granted.stream_ranges
    R.require(ranges, 'Explicit current stream ranges required')
    atlas = A.pc(int.from_bytes(source[0x865:0x868], 'little'))
    atlas_end = atlas + document.profile['tile_count'] * 8
    R.require(atlas_end <= len(source), 'Native Tile16 definitions exceed expanded source')
    if current_source_profile is None:
        R.require(source_hash == SOURCE and source_size == 0x400000,
                  'CURRENT_SOURCE_PROFILE_REQUIRED: current planning cannot use the historical reader ledger')
        claim, digest = R.reservation_claim()
        readers = claim['tile32_candidate_reservation']
        reader_spans = [tuple(readers['native_decoder']['pc']),
                        *(tuple(row['pc']) for row in readers['native_readers'])]
    else:
        from lyra_current_transfer import verify_current_native_source_profile
        verify_current_native_source_profile(current_source_profile, original_source, document,
            allocation=granted, spare_tile32_ids=spare_tile32_ids, native_copy_maps=native_copy_maps)
        reader_spans = [tuple(row['pc']) for row in current_source_profile['native_reader_preimages']]
    native_spans = [(0x864, 0x871), (atlas, atlas_end),
        *reader_spans,
        *((A.pc(old), A.pc(old) + count * stride) for name, old, count, first, total, stride, at in A.SPECS),
        *((base, base + 0x4540 // 4 * 6) for base in A.TILE32_BASES)]
    R.require(all(len(span) == 2 and all(type(at) is int for at in span)
                  and 0 <= span[0] < span[1] <= len(source) for span in ranges),
              'Invalid current stream allocation')
    R.require(all(end <= lo or start >= hi for start, end in ranges for lo, hi in native_spans),
              'Current stream allocation overlaps native definitions, tables or reader code')
    if copy_bytes:
        start, end = ranges[0]
        R.require(start + copy_bytes < end
                  and start // 0x8000 == (start + copy_bytes - 1) // 0x8000,
                  'Native copies exceed the first stream allocation bank')
        ranges = ((start + copy_bytes, end), *ranges[1:])
    sea_allocation = Allocation(ranges, granted.owned_tile32_ids,
                               tile32_capacity=granted.tile32_capacity,
                               tile32_assignments=granted.tile32_assignments)
    definitions = {i: A.read_tile32(source, i) for i in range(0x4540)}
    compiled = compile_terrain(document, definitions, sea_allocation,
                               map_ids=FULL_MAPS, render_directory=directory)
    before_rows = N.reject_stream_aliases(source, granted.stream_ranges)
    packed = T.packed_write_plan(source, document, compiled, sea_allocation)
    writes = [dict(kind='dictionary', **row) for row in packed['writes']]
    copies, payloads = [], []
    for index, area in enumerate(native_copy_maps):
        for plane, table in enumerate(N.POINTER_TABLES):
            decoded, pointer, span = N._plane(source, area, table)
            payload = b'\xe0\xff' + decoded + b'\xff'
            at = granted.stream_ranges[0][0] + index * 518 + plane * 259
            copies.append(dict(map_id=area, plane=plane, pc=[at, at + 259],
                               payload_sha256=R.sha(payload)))
            payloads.append(payload)
            writes.append(dict(kind='native37_copy' if area == 0x37 else 'native_copy',
                pc=[at, at + 259], preimage_hex=source[at:at + 259].hex(), payload_hex=payload.hex()))
    streams = []
    for plan in compiled.maps:
        for plane, stream in enumerate((plan.high, plan.low)):
            payloads.append(stream.payload)
            streams.append(dict(map_id=plan.map_id, plane=plane,
                pc=[stream.pc, stream.pc + len(stream.payload)], payload_sha256=R.sha(stream.payload)))
            writes.append(dict(kind='terrain_stream', pc=[stream.pc, stream.pc + len(stream.payload)],
                preimage_hex=source[stream.pc:stream.pc + len(stream.payload)].hex(), payload_hex=stream.payload.hex()))
    payload = b''.join(payloads)
    candidate = C.apply_writes(source, writes)  # Memory only; no output ROM exists.
    # Recompute every pointer decode and every dictionary meaning after combined
    # writes: this includes all18 saved external rows and the three exact aliases.
    after_rows = N.reject_stream_aliases(candidate, [])
    R.require(before_rows == after_rows, 'Private writes change native pointer/stream closure')
    changed = dict(compiled.new_definitions)
    R.require(all(A.read_tile32(candidate, i) == changed.get(i, definitions[i]) for i in range(0x4540)),
              'Private write readback changes an unassigned dictionary meaning')
    R.require(all(type(i) is int and 0 <= i < 0x4540 for i in spare_tile32_ids),
              'Invalid protected spare Tile32 IDs')
    R.require(all(A.read_tile32(candidate, i) == definitions[i] for i in spare_tile32_ids),
              'Private spare packed neighbors changed')
    for span in protected_spans:
        R.require(type(span) in (tuple, list) and len(span) == 2
                  and all(type(at) is int for at in span)
                  and 0 <= span[0] < span[1] <= len(source), 'Invalid protected current source span')
        R.require(candidate[slice(*span)] == source[slice(*span)],
                  'Private writes change protected source span')
    for plan in compiled.maps:
        tiles = tuple(h << 8 | l for h, l in zip(*[decode_literal_stream(candidate[s.pc:s.pc + len(s.payload)])
                                                   for s in (plan.high, plan.low)]))
        R.require(tiles == plan.tiles32, 'Full32 actual plan-byte readback differs')
    appearance = A.appearance_plan(source, document, directory)
    if current_source_profile is not None:
        # Only explicit current origins may describe destination addresses.
        origin = current_source_profile['origins']['tables']['pc'][0]
        layout = current_source_profile['table_layout']
        for row in appearance['selector_rows']:
            for table in row['native_table_rows']:
                field = layout[table['table']]
                table['pc'] = origin + field['offset'] + row['map_id'] * field['stride']
        verify_current_native_source_profile(current_source_profile, original_source, document,
            allocation=granted, spare_tile32_ids=spare_tile32_ids, native_copy_maps=native_copy_maps)
    actors = A.consumer_blockers(document, FULL_MAPS, FULL_MAPS)
    result = dict(kind='lyra.native_full32_write_plan.v1', source_rom_sha256=source_hash,
        source_size=source_size, expanded_size=len(source),
        selected_maps=FULL_MAPS, natural_render_maps=FULL_MAPS,
        stream_payload_bytes=len(payload), stream_pc_ranges=[list(span) for span in granted.stream_ranges],
        emitted_definitions=[dict(tile32_id=i, quadrants=list(q)) for i, q in compiled.new_definitions],
        native_copies=copies, streams=streams, packed_dictionary_plan=packed, writes=writes,
        native_maps_preserved=160, native_planes_preserved=320,
        native_streams_sha256=T.digest(before_rows),
        spare_tile32_ids_preserved=list(spare_tile32_ids), appearance=appearance,
        appearance_blockers=appearance['blockers'], actor_blockers=actors,
        runtime_admission=False, ordinary_build_ready=False, actors_compiled=False,
        production_maps=[], production_edge_ids=[], rom_written=False,
        producer_enforcement_verified=False, proposed_in_memory_sha256=R.sha(candidate))
    if current_source_profile is not None:
        result.update(current_source_profile_sha256=T.digest(current_source_profile),
                      source_origins=current_source_profile['origins'])
        if document.gameplay_areas:
            result.update(gameplay_area_plan=A.gameplay_area_plan(document),
                gameplay_transition_rows=A.gameplay_transition_rows(original_source, document),
                render_directory=[dict(map_id=plan.map_id, quadrant_maps=list(plan.quadrant_maps))
                                  for plan in compiled.maps])
    return result, payload


def compile_private(request_path, attachment, evidence):
    source, terrain, document, directory, pairs, native, bindings, ledger_hash = _intake(request_path)
    verify_attachment(source, attachment)
    verify_producer_evidence(attachment, evidence)
    granted = A.parse_allocation(allocation_value(attachment, evidence), source)
    result, payload = compile_native_plan(source, document, granted, directory,
        native_copy_maps=(0x37,), protected_spans=(OLD_A0,),
        spare_tile32_ids=attachment['spare_tile32_ids'])
    R.require(len(result['emitted_definitions']) == 566
              and len(payload) == STREAM[1] - STREAM[0] == 17094
              and result['streams'][-1]['pc'][1] == STREAM[1], 'Full32 exact grant coverage differs')
    for row in [*bindings, *attachment['oracle_source_bindings'], attachment['source_declaration']]:
        Q.read_bound(row)
    verify_producer_evidence(attachment, evidence)
    result.update(kind='lyra.private_full32_compilation.v1',
        attachment_sha256=T.digest(attachment), producer_evidence_sha256=T.digest(evidence),
        bank_padding_bytes=0, stream_pc_range=list(STREAM), native37_copy=result['native_copies'],
        native_receipt=native, inputs=bindings, producer_enforcement_verified=True,
        endpoint_holds=dict(entrance='B0 entrance0B remains native2F; no assignment',
                            return_exit='room83 exit_row=null; no policy'))
    return result, payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--attachment', type=Path)
    parser.add_argument('--producer-evidence', type=Path)
    args = parser.parse_args(argv)
    R.require(bool(args.attachment) == bool(args.producer_evidence),
              'Compile requires both attachment and producer evidence; omit both to create attachment only')
    R.require(not args.output.exists(), 'Private output directory must be new')
    attachment = create_attachment(args.request)
    files = {'attachment.json': P.encoded(attachment),
             'hack_manifest.json': P.encoded(dict(lyra_private_reservation=attachment))}
    protected = [Path(row['path']) for row in attachment['inputs']]
    if args.attachment:
        R.require(json.loads(args.attachment.read_bytes()) == attachment, 'Selected attachment differs')
        evidence = json.loads(args.producer_evidence.read_bytes())
        result, payload = compile_private(args.request, attachment, evidence)
        files.update({'write-plan.json': P.encoded(result), 'terrain.bin': payload})
        protected += [args.attachment, args.producer_evidence]
    P.write_outputs(args.output, files, protected=protected)
    print(json.dumps(dict(status='PASS', outputs=sorted(files), rom_written=False)))


if __name__ == '__main__':
    main()
