"""One read-only native37 + isolated A1 composition, with fresh lineage.

Historical assignments are verified in their original context. This coordinator
does not publish tables, install ingress, change the ledger, or write a ROM.
"""
from __future__ import annotations

import json
from pathlib import Path

import lyra_native_state as S
import lyra_native_streams as N
import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_delta as D
import lyra_project_tile32 as T32
from lyra_project_terrain import Allocation, compile_terrain, parse_terrain_document, resolve_project_terrain

PINS = {
    'rom': 'ef09c94b36a6b2fcdbbcf56046a096cfba9d4c666c140036f35dcf5a6dbff0f9',
    'saved_rom': 'dcb83f8963b72345a00b6eb9a4467d6a562d663df87f9cbaa1ba9a1d328df07b',
    'symbols': '65155045f8f6fbb0f4700116a3ef9595e99dad787ec25d52370e37278e28fa99',
    'build_receipt': '09c51896ba2e2f8d01b4dda6847e4cb817ae3c0bbf32772a6f5faea1a9e811ed',
    'ledger': '39f5ac504981566bd0333a82d554cf1a735d35c7607ed08c54d785e60ed3ed77',
    'historical_ledger': 'e782d3ef159a6f2506538c86bf94a0f11761620569ae1c617f2e72729e8e2ba3',
    'power_manifest': 'a794a382348ab8a0cff2fd33f7706788e6a8136dca5bd6d5024277cc9a4b833a',
    'terrain': '5317924d5442cf67de1752c09c3182aad180ddb9bd5e40d6d813efb70d5faf9b',
    'power_terrain': 'e335abdf782a54b3486cec029d3640fc548ea88af924c79c75be2d4d053cff90',
    'frozen_assignment': '24ca5f6c8deefcf2b937b2e7da1d2969a7c422b2a7f25a3907460558d109e34c',
    'authoring_observation': '3279cd687fcb598e08f6276c3d0569e1e653c6ec07ad5defcd9f986c4a2fb85d',
    'power_observation': '9c568bb8fdcd0d4bb192a87564fb967ebb2c171f1e38ce4fa05405699e936b64',
}
FIXTURE_SHA = 'c6baff80368fb79f8e73273def334ff82826034b6238462edc4e28548a2b4e1b'
SOURCE_ANCHORS = {
    'Items/ice_rod.asm': '8bcd1f79e44e182728726c49bccd99ff2067d56d63df6552376d1244abd87cd5',
    'Dungeons/Collision/GlobalCollisionTables.asm': '37b472419b5095eff2241b6792be43d3257252b0b645f3d72645189365658c8e',
    'Core/patches.asm': '66101c3b4a4a027c4fa13fbb121bc469c28809dc3f2414969935626c7d3e4619',
}
COLLISION_PATCHES = ((0x715DC, 0x51, 0x0E), (0x7166E, 1, 0),
    (0x716AE, 2, 0x20), (0x716D5, 0, 0x20), (0x7175E, 0x27, 0x64),
    (0x7176E, 0x20, 0x64), (0x7177E, 0x20, 0x64))


def collision_projection(saved, compiled, grids):
    """Verify the reviewed seven-byte projection and actual quarter consumers."""
    expected = bytearray(saved[0x71459:0x71859])
    for at, old, new in COLLISION_PATCHES:
        R.require(saved[at] == old and compiled[at] == new, 'Collision projection preimage/payload differs')
        expected[at - 0x71459] = new
    R.require(bytes(expected) == compiled[0x71459:0x71859]
              and compiled[0x715DD:0x715DF] == b'\x57\x57', 'Unknown/partial collision projection')
    for at, raw in ((0x864, b'\xbf\x00\x80\xbd'), (0x86E, b'\xbf\x59\x94\x0e')):
        R.require(saved[at:at + 4] == compiled[at:at + 4] == raw, 'Collision reader differs')
    atlas = A.pc(int.from_bytes(saved[0x865:0x868], 'little'))
    R.require(compiled[0x865:0x868] == saved[0x865:0x868]
              and saved[atlas:atlas + 0x8000] == compiled[atlas:atlas + 0x8000]
              and R.sha(saved[atlas:atlas + 0x8000]) ==
              'cbb31531734c9dbf4880a509b39df234924d03423692c0938ab4e222919ea838', 'Tile16 atlas differs')
    used = set()
    for grid in grids:
        for row in grid:
            for tile in row:
                for q in range(4):
                    at = atlas + tile * 8 + q * 2
                    used.add(int.from_bytes(compiled[at:at + 2], 'little') & 0x1FF)
    R.require(0x183 not in used, 'Selected collision quarters use changed tile8 $183')
    R.require(all(saved[0x71459 + i] == compiled[0x71459 + i] for i in used),
              'Selected collision attributes differ')
    return dict(kind='lyra.saved_to_compiled_collision_projection.v1', patches=[list(p) for p in COLLISION_PATCHES],
        saved_fingerprint=R.sha(saved[0x71459:0x71859]), compiled_fingerprint=R.sha(compiled[0x71459:0x71859]),
        saved_overworld_fingerprint=R.sha(saved[0x71459:0x71659]),
        compiled_overworld_fingerprint=R.sha(compiled[0x71459:0x71659]),
        tile8_quarters_checked=sorted(used), changed_tile8_183_used=False, movement_verified=False)


def apply_writes(source, writes):
    """Patch a bytearray only; reject resize, overlap, and stale preimages."""
    proposed, allowed = bytearray(source), set()
    for row in writes:
        start, end = row['pc']
        payload = bytes.fromhex(row['payload_hex'])
        R.require(0 <= start < end <= len(source) and len(payload) == end - start, 'Invalid write extent')
        R.require(not allowed.intersection(range(start, end)), 'Composition writes overlap')
        R.require(source[start:end].hex() == row['preimage_hex'], 'Composition write preimage differs')
        allowed.update(range(start, end))
        proposed[start:end] = payload
    R.require(len(proposed) == len(source) and all(a == b or i in allowed
              for i, (a, b) in enumerate(zip(source, proposed))), 'Composition write scope differs')
    return bytes(proposed)


def _document(raw, observation, source):
    proof = json.loads(observation)
    R.require(proof['source_rom_sha256'] == R.sha(source) and proof['terrain_sha256'] == R.sha(raw)
              and proof['map_count'] == 32 and proof['donor_map'] == 0x3A
              and proof['native_definitions'] == [list(A.read_tile32(source, i)) for i in range(0x4540)],
              'Historical source/terrain observation differs')
    return parse_terrain_document(raw, proof['profile'], allow_authoring_drafts=True,
        expected_asset_bindings={0xA0 + i: tuple(row) for i, row in enumerate(proof['verified_asset_bindings'])})


def _missing(source, document, maps):
    native = {A.read_tile32(source, i) for i in range(0x4540)}
    needed = set()
    for area in maps:
        flat = document.maps[area - 0xA0]
        grid = [flat[y:y + 32] for y in range(0, 1024, 32)]
        needed.update(tuple(D.quad_at(grid, x, y)) for y in range(0, 32, 2) for x in range(0, 32, 2))
    return sorted(needed - native)


def _compose(data, old_ledger_path, ledger_path):
    source, saved, fixture = data['rom'], data['saved_rom'], data['fixture']
    R.require(R.sha(source) == PINS['rom'] and R.sha(saved) == PINS['saved_rom']
              and R.sha(fixture) == FIXTURE_SHA and len(source) == len(saved) == len(fixture) == 0x400000,
              'Composition ROM lineage differs')
    receipt = json.loads(data['build_receipt'])
    R.require(receipt['base_rom']['sha256'] == R.sha(saved)
              and receipt['artifacts']['output_rom']['sha256'] == R.sha(source)
              and receipt['artifacts']['symbols']['sha256'] == R.sha(data['symbols'])
              and all(c['status'] == 'passed' for c in receipt['checks'] if c['required']),
              'Fresh build receipt binding differs')
    manifest, frozen, ledger = (json.loads(data[k]) for k in ('power_manifest', 'frozen_assignment', 'ledger'))
    D.validate_manifest(manifest)
    normalized = D.normalize_manifest(manifest, manifest_sha256=R.sha(data['power_manifest']))
    R.require([r['map_id'] for r in normalized.maps] == [0x37], 'Composition supports only native37 and A1')
    target = D.reconstruct(manifest, {0x37: D.native_map_grid(saved, 0x37)}, include_fixture=False)[0x37]
    R.require(target == D.native_map_grid(fixture, 0x37), 'Native37 fixture reconstruction differs')
    R.require(N.native_profile(saved, 0x37) == manifest['maps'][0]['source_profile']
              == N.native_profile(fixture, 0x37), 'Native37 manifest profile differs')
    R.require(R.sha(saved[0x71459:0x71859]) == manifest['inputs']['collision_table_sha256']
              == R.sha(fixture[0x71459:0x71859]), 'Historical collision fingerprint differs')
    old_claim, old_hash = R.reservation_claim(ledger_path=old_ledger_path)
    R.require(old_hash == PINS['historical_ledger'], 'Historical ownership context differs')
    pairs = T32.verify_contract(saved, frozen, old_claim, old_hash)
    R.require(T32.verify_contract(fixture, frozen, old_claim, old_hash) == pairs
              and len(pairs) == 115 and [i for i, _ in pairs] == list(range(0x44C0, 0x4533)),
              'Frozen joint meaning differs')
    document = _document(data['terrain'], data['authoring_observation'], saved)
    power_document = _document(data['power_terrain'], data['power_observation'], fixture)
    missing = _missing(saved, document, [0xA1])
    T32.verify_input(saved, data['terrain'], [0xA1], {0xA1: (0xA1,) * 4}, missing, frozen)
    power_maps = [0xB0, 0xB1, 0xB8, 0xB9]
    T32.verify_input(fixture, data['power_terrain'], power_maps, {a: (a,) * 4 for a in power_maps},
                     _missing(fixture, power_document, power_maps), frozen)
    R.require(len(missing) == 55, 'A1 source content requirement differs')
    value = R.derive_allocation(source, ledger_path=ledger_path)
    allocation = A.parse_allocation(value, source)
    R.verify_reservation(source, allocation, value['reservation'], ledger_path=ledger_path)
    claim, current_hash = R.reservation_claim(ledger_path=ledger_path)
    R.require(current_hash == PINS['ledger'], 'Current ownership context differs')
    ownership = T32.ownership(source, claim)
    old_rejections = {}
    for label, context_claim, context_hash in (('historical', old_claim, old_hash), ('current', claim, current_hash)):
        try:
            T32.verify_contract(source, frozen, context_claim, context_hash)
        except ValueError as error:
            old_rejections[label] = str(error)
        else:
            raise ValueError('Frozen assignment incorrectly accepts the fresh image')
    definitions = [A.read_tile32(source, i) for i in range(0x4540)]
    R.require(definitions == [A.read_tile32(saved, i) for i in range(0x4540)], 'Saved/fresh dictionary differs')
    profiles, original_planes, used = [], {}, set()
    for area in range(160):
        profile = N.native_profile(source, area)
        R.require(profile == N.native_profile(saved, area), f'Saved/fresh profile {area:02X} differs')
        profiles.append(profile)
        planes = [N._plane(source, area, table)[0] for table in N.POINTER_TABLES]
        R.require(planes == [N._plane(saved, area, table)[0] for table in N.POINTER_TABLES],
                  f'Saved/fresh native plane {area:02X} differs')
        original_planes[area] = planes
        used.update(hi << 8 | lo for hi, lo in zip(*planes))
    a1_grid = [list(document.maps[1][y:y + 32]) for y in range(0, 1024, 32)]
    projection_grids = [D.native_map_grid(source, a) for a in (0x36, 0x37, 0x3E, 0x3F)] + [target, a1_grid]
    projection = collision_projection(saved, source, projection_grids)
    originals = tuple(hi << 8 | lo for hi, lo in zip(*original_planes[0x37]))
    lookup = {}
    for i, quad in enumerate(definitions):
        if i < 0x44C0:
            lookup.setdefault(quad, []).append(i)
    tiles, changed = [], []
    for cell, original in enumerate(originals):
        y, x = divmod(cell, 16)
        quad = tuple(D.quad_at(target, x * 2, y * 2))
        if definitions[original] == quad:
            tiles.append(original)
        else:
            choices = lookup.get(quad, [])
            R.require(choices, 'Native37 needs a new unallocated dictionary definition')
            tiles.append(min(choices, key=lambda i: (i not in used, i)))
            changed.append(cell)
    cells = sum(a != b for row, target_row in zip(D.native_map_grid(source, 0x37), target)
                for a, b in zip(row, target_row))
    R.require(cells == 21 and len(changed) == 8, 'Native37 accepted delta differs')
    start, stop = allocation.stream_ranges[0]
    R.require((start, stop) == (0x3D4000, 0x3D4818), 'Composition stream reservation differs')
    a1_allocation = Allocation(((start + 518, start + 1036),), tuple(i for i, _ in pairs),
                               tile32_assignments=pairs)
    compiled = compile_terrain(document, dict(enumerate(definitions)), a1_allocation,
                               map_ids=[0xA1], render_directory={0xA1: (0xA1,) * 4})
    R.require(len(compiled.new_definitions) == 55 and all(dict(pairs)[i] == q for i, q in compiled.new_definitions),
              'A1 does not use exactly the frozen55 content assignments')
    packed = T32.packed_write_plan(source, document, compiled, a1_allocation)
    writes = [dict(kind='a1_dictionary_group', **row) for row in packed['writes']]

    def add(kind, at, payload):
        writes.append(dict(kind=kind, pc=[at, at + len(payload)],
                           preimage_hex=source[at:at + len(payload)].hex(), payload_hex=payload.hex()))

    for plane, shift in enumerate((8, 0)):
        at = start + plane * 259
        add('native37_stream', at, b'\xe0\xff' + bytes(i >> shift & 255 for i in tiles) + b'\xff')
        add('native37_pointer', A.pc(N.POINTER_TABLES[plane]) + 0x37 * 3, A.snes(at).to_bytes(3, 'little'))
    for stream in compiled.stream_writes:
        add('a1_stream', stream.pc, stream.payload)
    partial = apply_writes(source, writes)
    relocated = []
    for name, table in zip(('map32_high', 'map32_low'), N.POINTER_TABLES):
        spec = next(row for row in A.SPECS if row[0] == name)
        at = A.TABLE_START + spec[6]
        payload = bytearray(192 * 3)
        payload[:160 * 3] = partial[A.pc(table):A.pc(table) + 160 * 3]
        stream = compiled.maps[0].high if name == 'map32_high' else compiled.maps[0].low
        payload[0xA1 * 3:0xA1 * 3 + 3] = stream.snes.to_bytes(3, 'little')
        add('dormant_' + name, at, bytes(payload))
        relocated.append(at)
    streams = [row for row in writes if row['kind'] in ('native37_stream', 'a1_stream')]
    R.require(sum(row['pc'][1] - row['pc'][0] for row in streams) == 1036
              and all(start <= row['pc'][0] < row['pc'][1] <= stop
                  and row['pc'][0] // 0x8000 == (row['pc'][1] - 1) // 0x8000 for row in streams),
              'Composition stream children exceed bank-safe reservation')
    incoming = N.reject_stream_aliases(source, [tuple(row['pc']) for row in writes])
    proposed = apply_writes(source, writes)
    emitted = dict(compiled.new_definitions)
    for i, quad in enumerate(definitions):
        R.require(A.read_tile32(proposed, i) == emitted.get(i, quad), f'Unselected dictionary ID {i:04X} changed')
    controls = []
    for area in range(160):
        new = [N._plane(proposed, area, table)[0] for table in N.POINTER_TABLES]
        if area == 0x37:
            R.require(N._native_grid(new, dict(enumerate([A.read_tile32(proposed, i) for i in range(0x4540)])))
                      == target, 'Native37 proposed actual-pointer readback differs')
        else:
            R.require(new == original_planes[area], f'Other native component {area:02X} changed')
            for table in N.POINTER_TABLES:
                at = A.pc(table) + area * 3
                R.require(proposed[at:at + 3] == source[at:at + 3], 'Other native pointer changed')
        controls.append(dict(map_id=area, proposed_planes_sha256=R.sha(b''.join(new))))
    a1_planes = []
    for at in relocated:
        pointer = int.from_bytes(proposed[at + 0xA1 * 3:at + 0xA1 * 3 + 3], 'little')
        a1_planes.append(A._decode_plane(proposed, pointer))
    proposed_definitions = dict(enumerate(A.read_tile32(proposed, i) for i in range(0x4540)))
    R.require(all(len(p) == 256 for p in a1_planes)
              and N._native_grid(a1_planes, proposed_definitions) == a1_grid, 'A1 proposed relocated-pointer grid differs')
    R.require(tuple(a << 8 | b for a, b in zip(*a1_planes)) == compiled.maps[0].tiles32,
              'A1 proposed256 IDs differ')
    R.require(source[A.CODE_START:A.CODE_END] == proposed[A.CODE_START:A.CODE_END], 'Composition changes ingress code')
    projection_after = collision_projection(saved, proposed, [D.native_map_grid(proposed, a)
        for a in (0x36, 0x37, 0x3E, 0x3F)] + [a1_grid])
    state = S.plan_native_state(proposed, [0x37, 0xA1], symbols=data['symbols'].decode(), ownership=ledger)
    R.require(state['consumers_verified'] and state['persistent_event_storage'] is not None
              and not state['runtime_ready'], 'Proposed native state contract is not recognized/blocked')
    binding = dict(kind='lyra.native37_a1_fresh_lineage.v1', frozen_assignment_sha256=PINS['frozen_assignment'],
        frozen_assignments=frozen['assignments'], historical_ledger_sha256=old_hash, current_ledger_sha256=current_hash,
        saved_rom_sha256=R.sha(saved), compiled_rom_sha256=R.sha(source), proposed_rom_sha256=R.sha(proposed),
        current_consumer_receipt=ownership, native160_profiles_sha256=T32.digest(profiles),
        original_dictionary_sha256=T32.digest(definitions), collision_projection=projection,
        input_pins={k: R.sha(v) for k, v in data.items()}, source_anchors=SOURCE_ANCHORS)
    return dict(kind='lyra.native37_a1_composition_plan.v1', status='compiled_in_memory_unqualified',
        lineage_binding=binding, lineage_binding_sha256=T32.digest(binding), source_rom_sha256=R.sha(source),
        proposed_rom_sha256=R.sha(proposed), source_reservation=value['reservation'], writes=writes,
        stream_children=[dict(owner='native37', pc=[start, start + 518]), dict(owner='isolated_a1', pc=[start + 518, start + 1036])],
        stream_bytes=1036, stream_reservation_bytes=stop - start, native37=dict(cell_changes=cells,
            changed_block_indices=changed, retained_original_ids=248, tile32_ids=tiles, target_grid_sha256=R.sha(D.encoded_grid(target))),
        a1=dict(map_id=0xA1, tile32_ids=list(compiled.maps[0].tiles32), target_grid_sha256=R.sha(D.encoded_grid(a1_grid)),
            relocated_pointer_tables_pc=relocated, emitted_definitions=[dict(tile32_id=i, quadrants=list(q)) for i, q in compiled.new_definitions]),
        frozen115_preserved=True, frozen60_not_emitted=sorted(set(dict(pairs)) - set(emitted)),
        unassigned13_preserved=list(range(0x4533, 0x4540)), other_native_components_preserved=159,
        native_component_readbacks=controls, incoming320_read_directory_sha256=T32.digest(incoming),
        collision_after=projection_after, original_contract_fresh_refusals=old_rejections,
        native_state_contract=state, production_maps=[], production_edge_ids=[], runtime_build_ready=False,
        native_gameplay_verified=False, save_reopen_verified=False, rom_file_written=False,
        ingress_installed=False, composed_parent36_gameplay_verified=False)


def plan_composition(request):
    """Load exact saved inputs and fresh compiled context; never write inputs."""
    R.require(type(request) is dict and set(request) == set(PINS), 'Composition request paths differ')
    before, cache = {}, {}

    def read(path, expected):
        path = Path(path).resolve(strict=True)
        if path not in cache:
            cache[path] = path.read_bytes()
            before[path] = R.sha(cache[path])
        R.require(before[path] == expected, f'Composition pinned input differs: {path}')
        return cache[path]

    try:
        data = {key: read(request[key], digest) for key, digest in PINS.items()}
        for name, digest in SOURCE_ANCHORS.items():
            read(Path(__file__).resolve().parents[2] / name, digest)
        manifest = json.loads(data['power_manifest'])
        for name in ('source_rom', 'candidate_fixture_rom', 'project', 'recipe'):
            row = manifest['inputs'][name]
            raw = read(row['path'], row['sha256'])
            if name == 'candidate_fixture_rom':
                data['fixture'] = raw
        if 'lyra_sidecar_sha256' in manifest['inputs']:
            read(resolve_project_terrain(manifest['inputs']['project']['path']), manifest['inputs']['lyra_sidecar_sha256'])
        for group in (manifest.get('lyra_source_provenance', {}), manifest.get('existing_w02_complete_input_reference_only', {})):
            for row in group.values():
                if type(row) is dict and 'path' in row and 'sha256' in row:
                    read(row['path'], row['sha256'])
        result = _compose(data, request['historical_ledger'], request['ledger'])
        result['inputs'] = [dict(path=str(path), sha256=digest) for path, digest in sorted(before.items())]
    finally:
        R.require(all(R.sha(path.read_bytes()) == digest for path, digest in before.items()),
                  'Read-only composition changed an input')
    return result
