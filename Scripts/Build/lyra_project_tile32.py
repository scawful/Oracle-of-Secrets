#!/usr/bin/env python3
"""Source-bound Tile32 assignments and in-memory packed-write/readback plans.

The source ledger names the ID reservation. Native reference absence and exact
preimages are additional guards, never a search for available IDs. Assignments
expire after any changed editor save. This module never writes a ROM.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lyra_project_allocation import require, sha, reservation_claim

KIND = 'lyra.post_editor_save_tile32_assignment.v1'
LIFETIME = 'exact_saved_source_to_private_candidate_only'
NATIVE_PARTITION = 'lyra.current_saved_native_tile32_partition.v1'


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def native_partition(policy, source_sha256):
    """An exact saved-source exception retains three authored native meanings.

    It grants no new ID: all remaining bytes/consumers keep the original
    reservation checks. The historical source does not activate this record.
    """
    partition = policy.get('current_saved_native_tile32_partition')
    if partition is None:
        return None
    require(type(partition) is dict and set(partition) == {
        'kind', 'scope', 'production_admission', 'source_rom_sha256', 'native_tile32_ids',
        'original_quadrants', 'native_definitions', 'native_references'}
        and partition['kind'] == NATIVE_PARTITION
        and partition['scope'] == 'isolated_candidate_only'
        and partition['production_admission'] is False
        and partition['native_tile32_ids'] == [0x453D, 0x453E, 0x453F]
        and partition['original_quadrants'] == [420] * 4,
        'Malformed current saved native Tile32 partition')
    require(partition['native_definitions'] == [
        dict(tile32_id=0x453D, quadrants=[338, 1389, 707, 1327]),
        dict(tile32_id=0x453E, quadrants=[740, 1433, 338, 1337]),
        dict(tile32_id=0x453F, quadrants=[1433, 1328, 1342, 338])]
        and partition['native_references'] == [
            dict(map_id=0x90, cell=87, tile32_id=0x453F),
            dict(map_id=0x90, cell=88, tile32_id=0x453E),
            dict(map_id=0x98, cell=152, tile32_id=0x453D)]
        and partition['source_rom_sha256'] ==
            '44f46bb06f589a39275ff40d35e40a3a5652502a981205eaebb54f4c447a3ee2',
        'Unreviewed current saved native Tile32 meanings/consumers')
    return partition if source_sha256 == partition['source_rom_sha256'] else None


def ownership(source, claim):
    """Verify the declared producer/consumer boundary on actual ROM bytes."""
    import lyra_project_admission as A
    policy = claim.get('tile32_candidate_reservation')
    require(type(policy) is dict and policy.get('lifetime') == LIFETIME
            and policy.get('editor_save_preserves_ids') is False
            and policy.get('id_range') == [0x44C0, 0x4540]
            and policy.get('dictionary_bases_pc') == list(A.TILE32_BASES),
            'No reviewed post-editor-save Tile32 source reservation')
    begin, end = policy['id_range']
    partition = native_partition(claim, sha(source))
    retained_ids = set(partition['native_tile32_ids']) if partition else set()
    decoder = policy['native_decoder']
    require(decoder['pc'] == [0x17691, 0x177CB]
            and sha(source[0x17691:0x177CB]) == decoder['sha256'],
            'Reviewed native Tile32 decoder differs')
    readers = policy.get('native_readers')
    require(type(readers) is list and [r.get('pc') for r in readers] == [
        [0x1759D, 0x175D2], [0x177E3, 0x17818]], 'Missing reviewed native Tile32 readers')
    for reader in readers:
        start, stop = reader['pc']
        require(sha(source[start:stop]) == reader['sha256'],
                'Reviewed native Tile32 pointer reader differs')
    spans = []
    for quadrant, base in enumerate(A.TILE32_BASES):
        start, stop = base + begin // 4 * 6, base + end // 4 * 6
        raw = source[start:stop]
        normalized = bytearray(raw)
        if partition:
            for row in partition['native_definitions']:
                tile = row['tile32_id']
                require(A.read_tile32(source, tile) == tuple(row['quadrants']),
                        'Retained native Tile32 meaning differs')
                # Normalize only the declared retained IDs in a scratch slice.
                # Adjacent slots and packed nibbles still use the original pin.
                group, slot = (tile - begin) // 4 * 6, tile % 4
                value = partition['original_quadrants'][quadrant]
                normalized[group + slot] = value & 255
                at, shift = group + 4 + slot // 2, 4 if slot % 2 == 0 else 0
                normalized[at] = (normalized[at] & ~(15 << shift)) | ((value >> 8) << shift)
        require(len(raw) == stop - start and sha(normalized) == policy['packed_preimage_sha256'],
                'Source-declared packed Tile32 preimage differs')
        spans.append(dict(pc=[start, stop], sha256=sha(raw)))
    rows, used, retained_references = [], set(), []
    for area in range(160):
        pointers = [int.from_bytes(source[A.pc(table) + area * 3:A.pc(table) + area * 3 + 3],
                                   'little') for table in (0x02F94D, 0x02FB2D)]
        planes = [A._decode_plane(source, pointer) for pointer in pointers]
        require(all(len(p) == 256 for p in planes), 'Incomplete native Tile32 consumer plane')
        tiles = [a << 8 | b for a, b in zip(*planes)]
        require(all(tile < 0x4540 for tile in tiles), 'Native Tile32 consumer exceeds capacity')
        require(not any(begin <= tile < end and tile not in retained_ids for tile in tiles),
                f'Source-declared Tile32 IDs referenced by native map{area:02X}')
        retained_references.extend(dict(map_id=area, cell=cell, tile32_id=tile)
                                   for cell, tile in enumerate(tiles) if tile in retained_ids)
        used.update(tiles)
        rows.append(dict(map_id=area, pointers=pointers,
                         tiles_sha256=sha(b''.join(t.to_bytes(2, 'little') for t in tiles))))
    if partition:
        require(retained_references == partition['native_references'],
                'Retained native Tile32 reference closure differs')
    result = dict(source_rom_sha256=sha(source), native_maps=160, native_planes=320,
                stream_consumers=['full_load', 'sub_overlay'],
                used_unique_ids=len(used), maximum_used_id=max(used), reserved_references=0,
                reference_directory_sha256=digest(rows), packed_preimages=spans,
                native_decoder_sha256=decoder['sha256'], native_readers=readers)
    if partition:
        result.update(native_partition_sha256=digest(partition),
                      retained_native_ids=sorted(retained_ids), retained_native_references=retained_references,
                      lyra_assignable_ids=[i for i in range(begin, end) if i not in retained_ids])
    return result


def _assignments(inputs, policy, partition_claim=None):
    require(type(inputs) is list and inputs, 'Tile32 assignment needs exact input requests')
    missing = set()
    for request in inputs:
        require(type(request) is dict and set(request) == {
            'source_rom_sha256', 'terrain_sha256', 'candidate_maps', 'render_directory',
            'missing_definitions', 'consumer_receipt'}, 'Malformed Tile32 assignment input')
        quads = request['missing_definitions']
        require(type(quads) is list and all(type(q) is list and len(q) == 4
                and all(type(v) is int and 0 <= v < 4096 for v in q) for q in quads),
                'Invalid requested Tile32 quartets')
        require(quads == [list(q) for q in sorted({tuple(q) for q in quads})],
                'Tile32 requests must contain sorted unique quartets')
        missing.update(map(tuple, quads))
    begin, end = policy['id_range']
    retained = set()
    for request in inputs:
        partition = native_partition(partition_claim or {}, request['source_rom_sha256'])
        if partition:
            retained.update(partition['native_tile32_ids'])
    available = [i for i in range(begin, end) if i not in retained]
    require(len(missing) <= len(available),
            f'Tile32 capacity conflict: {len(missing)} definitions exceed {len(available)} declared IDs')
    return [dict(tile32_id=tile, quadrants=list(quad))
            for tile, quad in zip(available, sorted(missing))]


def verify_contract(source, contract, claim, ledger_hash):
    require(type(contract) is dict and set(contract) == {
        'kind', 'lifetime', 'ledger_sha256', 'inputs', 'assignments'}
        and contract['kind'] == KIND and contract['lifetime'] == LIFETIME
        and contract['ledger_sha256'] == ledger_hash,
        'Tile32 assignment source policy is stale or malformed')
    receipt = ownership(source, claim)
    require(any(r.get('source_rom_sha256') == sha(source) and r.get('consumer_receipt') == receipt
                for r in contract['inputs']), 'Tile32 assignment consumer receipt is stale')
    expected = _assignments(contract['inputs'], claim['tile32_candidate_reservation'], claim)
    require(contract['assignments'] == expected, 'Tile32 joint assignment differs from reviewed requests')
    import lyra_project_admission as A
    native = {A.read_tile32(source, i) for i in range(0x4540)}
    require(not any(tuple(row['quadrants']) in native for row in expected),
            'Joint Tile32 assignment duplicates a native definition')
    return tuple((row['tile32_id'], tuple(row['quadrants'])) for row in expected)


def verify_input(source, terrain, admitted, directory, missing, contract):
    """Bind compilation to actual cells, selection and render dependencies."""
    row = dict(source_rom_sha256=sha(source), terrain_sha256=sha(terrain),
        candidate_maps=list(admitted),
        render_directory=[dict(map_id=a, quadrant_maps=list(q)) for a, q in directory.items()],
        missing_definitions=[list(q) for q in missing])
    require(any(all(request.get(k) == value for k, value in row.items())
                for request in contract['inputs']),
            'Tile32 assignment does not cover this terrain/selection/render directory')


def create_contract(requests):
    """Review a joint assignment from independently verified saved inputs.

    Each request supplies source bytes, terrain bytes, native observation,
    candidate_maps and render_footprints. Actor blockers remain in admission;
    they do not change the pure Tile16-to-Tile32 assignment.
    """
    import lyra_project_admission as A
    from lyra_project_allocation import derive_allocation
    claim, ledger_hash = reservation_claim()
    inputs = []
    for request in requests:
        source, terrain = request['source'], request['terrain']
        allocation = derive_allocation(source)
        allocation['admission']['candidate_maps'] = request['candidate_maps']
        allocation['admission']['render_footprints'] = request['render_footprints']
        # plan_admission verifies the observation, all32 drafts and bindings.
        plan = A.plan_admission(source, terrain, request['proof'], allocation)
        inputs.append(dict(source_rom_sha256=sha(source), terrain_sha256=sha(terrain),
            candidate_maps=plan['candidate_maps'], render_directory=plan['render_directory'],
            missing_definitions=plan['tile32_requirements']['missing_definitions'],
            consumer_receipt=ownership(source, claim)))
    inputs.sort(key=lambda r: (r['source_rom_sha256'], r['terrain_sha256'], r['candidate_maps']))
    require(len({digest(r) for r in inputs}) == len(inputs), 'Duplicate Tile32 assignment input')
    contract = dict(kind=KIND, lifetime=LIFETIME, ledger_sha256=ledger_hash, inputs=inputs,
                    assignments=_assignments(inputs, claim['tile32_candidate_reservation'], claim))
    for request in requests:
        verify_contract(request['source'], contract, claim, ledger_hash)
    return contract


def packed_write_plan(source, document, compiled, allocation):
    """Pack only assigned definitions, preserving neighboring packed nibbles.

    Read back from an in-memory ROM independently of compiler definitions;
    native streams/pointers and every unassigned dictionary ID must survive.
    """
    import lyra_project_admission as A
    from lyra_project_terrain import decode_literal_stream
    require(allocation.tile32_assignments is not None, 'Reviewed Tile32 assignments required')
    assigned = dict(allocation.tile32_assignments)
    proposed, changed_groups = bytearray(source), set()
    for tile, quad in compiled.new_definitions:
        require(tile in allocation.owned_tile32_ids and assigned.get(tile) == quad,
                'Packed write exceeds reviewed Tile32 assignment')
        group, slot = tile // 4 * 6, tile % 4
        for base, value in zip(A.TILE32_BASES, quad):
            at = base + group
            proposed[at + slot] = value & 255
            high, shift = at + 4 + slot // 2, 4 if slot % 2 == 0 else 0
            proposed[high] = (proposed[high] & ~(15 << shift)) | ((value >> 8) << shift)
            changed_groups.add(at)
    A.require_legacy_definition_preservation(source, compiled)
    # IDs and packed bytes are distinct resources. A relocated compressed
    # native stream must not alias the dictionary bytes being proposed here.
    for area in range(160):
        for table in (0x02F94D, 0x02FB2D):
            at = A.pc(table) + area * 3
            pointer = int.from_bytes(source[at:at + 3], 'little')
            require(source[at:at + 3] == proposed[at:at + 3]
                    and A._decode_plane(source, pointer) == A._decode_plane(proposed, pointer),
                    f'Packed writes change native terrain stream{area:02X}')
    changed = dict(compiled.new_definitions)
    for tile in range(0x4540):
        require(A.read_tile32(proposed, tile) == changed.get(tile, A.read_tile32(source, tile)),
                f'Packed definition readback differs at{tile:04X}')
    for plan in compiled.maps:
        planes = [decode_literal_stream(s.payload) for s in (plan.high, plan.low)]
        tiles = tuple(a << 8 | b for a, b in zip(*planes))
        require(tiles == plan.tiles32, 'Packed plan stream readback differs')
        rebuilt = [0] * 1024
        for cell, tile in enumerate(tiles):
            y, x = divmod(cell, 16)
            for quadrant, value in enumerate(A.read_tile32(proposed, tile)):
                rebuilt[(y * 2 + quadrant // 2) * 32 + x * 2 + quadrant % 2] = value
        require(tuple(rebuilt) == document.maps[plan.map_id - 0xA0],
                'Packed selected-map Tile16 readback differs')
    allowed = {at + offset for at in changed_groups for offset in range(6)}
    require(all(a == b or offset in allowed for offset, (a, b) in enumerate(zip(source, proposed))),
            'Packed plan changes bytes outside assigned groups')
    return dict(kind='lyra.tile32_packed_write_plan.v1', source_rom_sha256=sha(source),
        assignment_sha256=digest([dict(tile32_id=i, quadrants=list(q))
                                  for i, q in allocation.tile32_assignments]),
        native_maps_preserved=160, unassigned_definitions_preserved=True,
        definition_count=len(changed), proposed_rom_sha256=sha(proposed),
        writes=[dict(pc=[at, at + 6], preimage_hex=source[at:at + 6].hex(),
                     payload_hex=proposed[at:at + 6].hex()) for at in sorted(changed_groups)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--request', type=Path, action='append',
                        help='JSON with rom, terrain, observation paths and explicit map/footprint selection')
    mode.add_argument('--compose-native37-a1', type=Path,
                      help='Exact saved/fresh lineage request; one read-only in-memory composition plan')
    args = parser.parse_args(argv)
    if args.compose_native37_a1:
        from lyra_project_composition import plan_composition
        raw = args.compose_native37_a1.read_bytes()
        try:
            result = plan_composition(json.loads(raw))
        except (ValueError, OSError) as error:
            parser.exit(1, f'Native37+A1 composition refused: {error}\n')
        require(args.compose_native37_a1.read_bytes() == raw, 'Read-only composition request changed')
        result['request_sha256'] = sha(raw)
        print(json.dumps(result, sort_keys=True, indent=2))
        return
    requests, before = [], {}
    for path in args.request:
        value = json.loads(path.read_bytes())
        paths = {k: Path(value[k]) for k in ('rom', 'terrain', 'observation')}
        for p in (path, *paths.values()):
            before[p] = sha(p.read_bytes())
        requests.append(dict(source=paths['rom'].read_bytes(), terrain=paths['terrain'].read_bytes(),
            proof=json.loads(paths['observation'].read_bytes()), candidate_maps=value['candidate_maps'],
            render_footprints=value['render_footprints']))
    try:
        result = create_contract(requests)
    finally:
        require(all(sha(p.read_bytes()) == h for p, h in before.items()), 'Read-only assignment changed an input')
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
