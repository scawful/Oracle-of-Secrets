#!/usr/bin/env python3
"""Prepare ordinary-build Lyra inputs and verify the assembled result.

The saved source and frozen assignments are historical inputs. The current
ledger authorizes only native37 plus isolated A1; no output-ROM hash is an input.
This program writes generated inputs/receipts, never a ROM or a saved project.
"""
from __future__ import annotations

import argparse
import configparser
import importlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_composition as C
import lyra_project_delta as D
import lyra_native_streams as N
import lyra_project_tile32 as T32
from lyra_project_terrain import Allocation, compile_terrain, resolve_project_terrain

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path('Data/Generated/lyra_project')
GENERATED_FILES = ('runtime_constants.asm', 'runtime_data.asm', 'descriptor.json',
                   'prepare.json', 'binaries/payload.bin')
ROLES = tuple(k for k in C.PINS if k not in ('rom', 'symbols', 'build_receipt', 'ledger'))
DESCRIPTOR_PC = 0x3C5FC0
TABLE_CAPACITY = 192
PUBLICATION = dict(kind='lyra.ordinary_private_native_readers.v1', enabled=True,
    scope='isolated_candidate_only', production_admission=False, selected_maps=[0x37, 0xA1],
    source_map_count=160, table_capacity=192, save_destination='unchanged',
    code_pc=[A.CODE_START, DESCRIPTOR_PC], descriptor_pc=[DESCRIPTOR_PC, DESCRIPTOR_PC + 64],
    source_reader_variant='original_native160', compiled_reader_variant='lyra.ordinary_private_native_readers.v1')


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def project_reference(project, parser, key):
    value = parser.get('files', key, fallback='').strip()
    R.require(value and '\0' not in value, f'Project has no {key}')
    path = Path(value)
    return (path if path.is_absolute() else project.parent / path).resolve(strict=True)


def project_context(project, request=None):
    # Like Yaze, resolve relative references beside the opened descriptor.
    project = Path(os.path.abspath(project))
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string(project.read_text(encoding='utf-8-sig'))
    parser.defaults().clear()
    R.require(parser.get('rom', 'role', fallback='') == 'dev', 'Lyra build requires a dev project')
    rom = project_reference(project, parser, 'rom_filename')
    terrain = resolve_project_terrain(project)
    request = Path(request).resolve(strict=True) if request else project_reference(
        project, parser, 'lyra_build_request_file')
    return project, rom, terrain, request


def publication_authorization(ledger_path):
    claim, digest = R.reservation_claim(ledger_path)
    auth = claim.get('ordinary_build_publication', {})
    R.require(auth == PUBLICATION,
              'Current ledger does not authorize ordinary native37+A1 publication')
    return claim, digest


def descriptor_payload(properties):
    raw_phase = {key: list(properties[key]) for key in ('sprite_graphics', 'sprite_palettes', 'music')}
    R.require(all(len(set(row)) == 1 and row[0] == (-1 if key != 'music' else 0)
                  for key, row in raw_phase.items()),
              'Isolated A1 requires the reviewed empty-actor phase selectors')
    sheets = properties['graphics_sheets']
    R.require(len(sheets) == 8, 'A1 requires eight saved graphics selectors')
    raw = (b'LYR1' + bytes([1, 0xA1, 0, 0xA1]) + bytes([0xA1]) * 4 + bytes(sheets)
           + bytes([properties['main_palette'], properties['palette_set'], properties['animated_sheet'],
                    0x30, 0x30, 0, 0, 0, 0x10, 7, 0, 0]) + bytes(32))
    R.require(len(raw) == 64, 'Descriptor must be exactly64 bytes')
    return raw, dict(kind='lyra.ordinary_a1_descriptor.v1', pc=DESCRIPTOR_PC, snes=0xF8DFC0,
        payload_hex=raw.hex(), raw_source_phase=raw_phase,
        effective_empty_actor_phase={key: 0 for key in raw_phase},
        phase_rule='The shared table producer maps source -1 to effective0 for empty actors.',
        source_map_count=160, table_capacity=TABLE_CAPACITY, production_admission=False,
        production_maps=[], production_edge_ids=[], save_exit_policy='unchanged_held')


def make_plan(project, base_rom, request=None, *, ledger_path=None):
    """Read saved inputs, validate original frozen meaning, and plan normal data."""
    project, project_rom, project_terrain, request_path = project_context(project, request)
    request_kind = json.loads(request_path.read_bytes())
    R.require(type(request_kind) is dict, 'Ordinary request must be an object')
    if request_kind.get('kind') == 'lyra.current_save_transfer_request.v1':
        from lyra_current_transfer import ordinary_plan
        return ordinary_plan(project, base_rom, request_path, ledger_path=ledger_path)
    R.require(request_kind.get('kind') != 'lyra.current_save_reservation_review.v1',
              'CURRENT_SAVE_RESERVATION_REVIEW_UNGRANTED: source review is not a build request')
    if request_kind.get('kind') == 'lyra.current_saved_request.v1':
        from lyra_project_prepare import current_plan
        return current_plan(project, base_rom, request_path, ledger_path=ledger_path)
    base_rom = Path(base_rom).resolve(strict=True)
    ledger_path = Path(ledger_path or R.LEDGER).resolve(strict=True)
    before, cache = {}, {}

    def read(path, expected=None):
        path = Path(path).resolve(strict=True)
        if path not in cache:
            cache[path] = path.read_bytes()
            before[path] = R.sha(cache[path])
        if expected is not None:
            R.require(before[path] == expected, f'Historical publisher input differs: {path}')
        return cache[path]

    try:
        request_value = json.loads(read(request_path))
        R.require(type(request_value) is dict and set(request_value) == set(ROLES),
                  'Ordinary request must contain only the eight historical input roles')
        data = {key: read(request_value[key], C.PINS[key]) for key in ROLES}
        saved = data['saved_rom']
        R.require(read(base_rom) == saved and read(project_rom) == saved,
                  'Selected project/base ROM differs from saved authoring source')
        R.require(read(project_terrain) == data['terrain'], 'Selected project terrain differs')
        read(project)
        for name, digest in C.SOURCE_ANCHORS.items():
            read(ROOT / name, digest)
        manifest = json.loads(data['power_manifest'])
        D.validate_manifest(manifest)
        normalized = D.normalize_manifest(manifest, manifest_sha256=R.sha(data['power_manifest']))
        R.require([row['map_id'] for row in normalized.maps] == [0x37], 'Only native37 delta is selected')
        for key in ('source_rom', 'candidate_fixture_rom', 'project', 'recipe'):
            row = manifest['inputs'][key]
            raw = read(row['path'], row['sha256'])
            if key == 'candidate_fixture_rom':
                fixture = raw
        if 'lyra_sidecar_sha256' in manifest['inputs']:
            read(resolve_project_terrain(manifest['inputs']['project']['path']),
                 manifest['inputs']['lyra_sidecar_sha256'])
        for group in (manifest.get('lyra_source_provenance', {}),
                      manifest.get('existing_w02_complete_input_reference_only', {})):
            for row in group.values():
                if type(row) is dict and 'path' in row and 'sha256' in row:
                    read(row['path'], row['sha256'])
        read(ledger_path)
        claim, ledger_sha = publication_authorization(ledger_path)
        value = R.derive_allocation(saved, ledger_path=ledger_path)
        allocation = A.parse_allocation(value, saved)
        R.verify_reservation(saved, allocation, value['reservation'], ledger_path=ledger_path)
        R.require(allocation.stream_ranges == ((0x3D4000, 0x3D4818),), 'Stream reservation differs')
        old_claim, old_sha = R.reservation_claim(request_value['historical_ledger'])
        frozen = json.loads(data['frozen_assignment'])
        pairs = T32.verify_contract(saved, frozen, old_claim, old_sha)
        R.require(T32.verify_contract(fixture, frozen, old_claim, old_sha) == pairs
                  and len(pairs) == 115 and [i for i, _ in pairs] == list(range(0x44C0, 0x4533)),
                  'Historical joint assignments differ')
        document = C._document(data['terrain'], data['authoring_observation'], saved)
        power = C._document(data['power_terrain'], data['power_observation'], fixture)
        T32.verify_input(saved, data['terrain'], [0xA1], {0xA1: (0xA1,) * 4},
                         C._missing(saved, document, [0xA1]), frozen)
        power_maps = [0xB0, 0xB1, 0xB8, 0xB9]
        T32.verify_input(fixture, data['power_terrain'], power_maps,
                         {a: (a,) * 4 for a in power_maps}, C._missing(fixture, power, power_maps), frozen)
        R.require(not A.consumer_blockers(document, [0xA1], {}),
                  'A1 active metadata is unsupported by this isolated publication')
        target = D.reconstruct(manifest, {0x37: D.native_map_grid(saved, 0x37)}, include_fixture=False)[0x37]
        R.require(target == D.native_map_grid(fixture, 0x37)
                  and N.native_profile(saved, 0x37) == manifest['maps'][0]['source_profile']
                  == N.native_profile(fixture, 0x37), 'Native37 target/profile differs')
        compiled_plan = compile_saved_plan(saved, document, pairs, target)
        R.require(compiled_plan['native37_changed_blocks'] == 8, 'Native37 changed-block count differs')
        R.require(len(compiled_plan['emitted_definitions']) == 55, 'A1 must emit exactly the original55 definitions')
        return dict(kind='lyra.ordinary_build_prepare.v1', selected=True,
            project=str(project), base_rom=str(base_rom), request=str(request_path), ledger=str(ledger_path),
            current_ledger_sha256=ledger_sha, historical_ledger_sha256=old_sha,
            saved_rom_sha256=R.sha(saved), inputs=[dict(path=str(p), sha256=h) for p, h in sorted(before.items())],
            source_reservation=value['reservation'], source_map_count=160, table_capacity=TABLE_CAPACITY,
            **compiled_plan)
    finally:
        R.require(all(R.sha(path.read_bytes()) == digest for path, digest in before.items()),
                  'Publisher input changed while preparing')


def compile_saved_plan(saved, document, pairs, target):
    """Compile the existing isolated37/A1 consumer without rewriting saved maps."""
    definitions = dict(enumerate(A.read_tile32(saved, i) for i in range(0x4540)))
    originals, used = {}, set()
    for area in range(160):
        planes = [N._plane(saved, area, table)[0] for table in N.POINTER_TABLES]
        originals[area] = planes
        used.update(hi << 8 | lo for hi, lo in zip(*planes))
    lookup = {}
    for i, quad in definitions.items():
        if i < 0x44C0:
            lookup.setdefault(quad, []).append(i)
    native_ids, changed = [], []
    for cell, original in enumerate(hi << 8 | lo for hi, lo in zip(*originals[0x37])):
        y, x = divmod(cell, 16)
        quad = tuple(D.quad_at(target, x * 2, y * 2))
        if definitions[original] == quad:
            native_ids.append(original)
        else:
            choices = lookup.get(quad, [])
            R.require(choices, 'Native37 needs an unallocated dictionary definition')
            native_ids.append(min(choices, key=lambda i: (i not in used, i)))
            changed.append(cell)
    a1_allocation = Allocation(((0x3D4206, 0x3D440C),), tuple(i for i, _ in pairs),
                               tile32_assignments=pairs)
    compiled = compile_terrain(document, definitions, a1_allocation,
                               map_ids=[0xA1], render_directory={0xA1: (0xA1,) * 4})
    appearance = A.appearance_plan(saved, document, {0xA1: (0xA1,) * 4})
    R.require(appearance['coherent'], 'A1 appearance is incoherent')
    packed = T32.packed_write_plan(saved, document, compiled, a1_allocation)
    writes = [dict(kind='a1_dictionary_group', **row) for row in packed['writes']]

    def add(kind, at, raw, label=None):
        writes.append(dict(kind=kind, pc=[at, at + len(raw)], preimage_hex=saved[at:at + len(raw)].hex(),
                           payload_hex=raw.hex(), **({'label': label} if label else {})))

    for plane, shift in enumerate((8, 0)):
        at = 0x3D4000 + plane * 259
        add('native37_stream', at, b'\xe0\xff' + bytes(i >> shift & 255 for i in native_ids) + b'\xff')
        add('native37_pointer', A.pc(N.POINTER_TABLES[plane]) + 0x37 * 3, A.snes(at).to_bytes(3, 'little'))
    for stream in compiled.stream_writes:
        add('a1_stream', stream.pc, stream.payload)
    partial = C.apply_writes(saved, writes)
    tables = A.relocated_table_payloads(partial, document, compiled, [0xA1])
    for table in tables:
        add('runtime_table', table['proposed_pc'][0], bytes.fromhex(table['payload_hex']),
            'LyraRuntime_' + table['name'])
    descriptor, descriptor_json = descriptor_payload(compiled.maps[0].properties)
    add('a1_descriptor', DESCRIPTOR_PC, descriptor, 'Lyra_A1Descriptor')
    N.reject_stream_aliases(saved, [tuple(row['pc']) for row in writes])
    proposed = C.apply_writes(saved, writes)
    verify_data(saved, proposed, writes, definitions, dict(compiled.new_definitions), target,
                [list(document.maps[1][y:y + 32]) for y in range(0, 1024, 32)])
    return dict(
        writes=writes, native37_changed_blocks=len(changed), descriptor=descriptor_json, table_rows=[{k: v for k, v in t.items() if k != 'payload_hex'} for t in tables],
        emitted_definitions=[dict(tile32_id=i, quadrants=list(q)) for i, q in compiled.new_definitions],
        targets={'native37': target, 'a1': [list(document.maps[1][y:y + 32]) for y in range(0, 1024, 32)]},
        stream_bytes=1036, stream_capacity=2072, frozen115_preserved=True,
        production_maps=[], production_edge_ids=[], save_exit_policy='unchanged_held')


def verify_data(saved, compiled, writes, definitions, emitted, native_target, a1_target):
    """Read actual pointers, complete dictionary and all legacy table prefixes."""
    R.require(len(saved) == len(compiled) == 0x400000, 'Compiled ROM must remain unheadered4MiB')
    for row in writes:
        start, end = row['pc']
        R.require(compiled[start:end].hex() == row['payload_hex'], f"Compiled payload differs: {row['kind']}")
    for i, quad in definitions.items():
        R.require(A.read_tile32(compiled, i) == emitted.get(i, quad), f'Dictionary readback differs: {i:04X}')
    actual_definitions = dict(enumerate(A.read_tile32(compiled, i) for i in range(0x4540)))
    controls = []
    for area in range(160):
        planes = [N._plane(compiled, area, table)[0] for table in N.POINTER_TABLES]
        if area == 0x37:
            R.require(N._native_grid(planes, actual_definitions)
                      == native_target, 'Native37 actual-pointer readback differs')
        else:
            for table, plane in zip(N.POINTER_TABLES, planes):
                at = A.pc(table) + area * 3
                R.require(compiled[at:at + 3] == saved[at:at + 3]
                          and plane == N._plane(saved, area, table)[0], f'Native component {area:02X} changed')
        controls.append(R.sha(b''.join(planes)))
    planes = []
    for name, old, legacy, first, count, stride, offset in A.SPECS:
        at = A.TABLE_START + offset
        raw = compiled[at:at + count * stride]
        R.require(raw[:legacy * stride] == compiled[A.pc(old):A.pc(old) + legacy * stride],
                  f'Final legacy table prefix differs: {name}')
        if name in ('map32_high', 'map32_low'):
            pointer = int.from_bytes(raw[(0xA1 - first) * stride:(0xA1 - first + 1) * stride], 'little')
            planes.append(A._decode_plane(compiled, pointer))
    R.require(all(len(p) == 256 for p in planes)
              and N._native_grid(planes, actual_definitions)
              == a1_target, 'A1 actual relocated-pointer readback differs')
    return dict(native160_planes_sha256=T32.digest(controls), native37_verified=True, isolated_a1_verified=True,
                dictionary_verified=True, legacy_tables_verified=30)


def render_outputs(plan):
    constants = ['; Generated from the current build invocation; not a feature flag.',
        f'!LYRA_PROJECT_DATA_PRESENT = {int(plan["selected"])}',
        f'!LYRA_NATIVE_A1_ENABLED = {int(plan["selected"])}', '!LYRA_A1_ID = $A1',
        '!LYRA_RUNTIME_TABLE_BASE = $28C000', '!LYRA_RUNTIME_CODE_BASE = $F8C000']
    constants += [f'!LYRA_TABLE_{name} = ${0x28C000 + offset:06X}'
                  for name, _, _, _, _, _, offset in A.SPECS]
    asm = ['; Prepared before Asar. No post-assembly ROM patch is permitted.']
    payload = bytearray()
    for row in plan.get('writes', []):
        raw = bytes.fromhex(row['payload_hex'])
        address = A.snes(row['pc'][0])
        if row['kind'] == 'runtime_table':
            address &= 0x7FFFFF  # Preserve the native loader's bank28 table ABI.
        asm.append(f'org ${address:06X}')
        if 'label' in row:
            asm.append(row['label'] + ':')
        asm.append(f'incbin "binaries/payload.bin":${len(payload):X}..${len(payload) + len(raw):X}')
        payload.extend(raw)
    files = {'runtime_constants.asm': ('\n'.join(constants) + '\n').encode(),
             'runtime_data.asm': ('\n'.join(asm) + '\n').encode(),
             'descriptor.json': encoded(plan.get('descriptor', {'selected': False})),
             'binaries/payload.bin': bytes(payload)}
    plan = dict(plan, generated_files={name: R.sha(raw) for name, raw in files.items()})
    files['prepare.json'] = encoded(plan)
    return files


def validate_current_source_set(contract):
    """Bind inactive current consumers too; normal ASM reachability excludes them."""
    ledger = contract.get('ledger', {})
    R.require(contract.get('kind') == 'lyra.current_engine_source_contract.v1'
              and all(contract.get(key) is False for key in ('allocation_granted', 'publication_authorized',
                  'producer_enforcement_verified', 'ordinary_build_ready', 'runtime_admission')),
              'Current source composition cannot assert authority')
    R.require(ledger.get('path') == 'Config/allocation_ownership.json'
              and type(ledger.get('sha256')) is str,
              'CURRENT_SOURCE_LEDGER_UNBOUND: current source set needs an exact ledger')
    binding = dict(path=str(ROOT / ledger['path']), sha256=ledger['sha256'])
    raw = Path(binding['path']).read_bytes()
    value = json.loads(raw)
    R.require(R.sha(raw) == ledger['sha256'],
              'Current source-set ledger changed')
    name = ledger.get('source_set')
    R.require(name in value.get('source_sets', {}), 'Current source set is not declared')
    records = [row for row in value.get('sources', {}).values() if row.get('source_set') == name]
    R.require(records, 'Current source set has no bound consumers')
    bindings = [binding]
    for row in records:
        path = ROOT / row['path']
        R.require(path.is_file() and path.resolve().is_relative_to(ROOT.resolve())
                  and not any(p.is_symlink() for p in (path, *path.parents)),
                  'Current source-set consumer escaped its root')
        content = path.read_bytes()
        R.require(R.sha(content) == row['sha256'], 'Current source-set consumer changed: ' + row['path'])
        bindings.append(dict(path=str(path), sha256=row['sha256']))
    return bindings


def render_current_source_outputs(table_plan, *, contract, graphics_source, graphics_report,
                                  current_source_profile=None, bg128_plan=None, actor_storage_plan=None):
    """Compose reviewable source through the existing generated-input layout.

    A source plan remains unselected and cannot pass the build-context loader.
    Actual output publication keeps the independent current-save refusal.
    """
    native = importlib.import_module('lyra_native_loaders')
    current = importlib.import_module('lyra_current_transfer')
    source_bindings = validate_current_source_set(contract)
    profile = current_source_profile
    R.require(type(profile) is dict and profile.get('kind') == current.CURRENT_PROFILE_KIND,
              'CURRENT_COMPOSER_PROFILE_REQUIRED: freshly verified current source profile required')
    _, source, document = current.verify_transfer(profile['review']['transfer']['path'],
                                                  profile['project'], profile['base_rom'])
    current.verify_current_native_source_profile(profile, source, document)
    bound_contract = current._json(current.Q.read_bound(profile['contract']))
    R.require(contract == bound_contract
              and Path(profile['selected_source']['root']).resolve() == ROOT.resolve(),
              'CURRENT_COMPOSER_CONTRACT_MISMATCH: source profile and selected contract differ')
    R.require(table_plan.get('kind') == native.CURRENT_KIND
              and all(table_plan.get(key) is False for key in
                      ('allocation_granted', 'producer_enforcement_verified', 'publication_authorized',
                       'ordinary_build_ready', 'runtime_admission', 'rom_written')),
              'Current source output requires an ungranted current table plan')
    profile_digest = current.T.digest(profile)
    R.require(table_plan.get('source_rom_sha256') == R.sha(source)
              and table_plan.get('source_profile_sha256') == profile_digest
              and profile['source_size'] == len(source),
              'CURRENT_COMPOSER_SOURCE_MISMATCH: table plan differs from exact saved source/profile')
    origins = profile['origins']
    table_origins = dict(table_base=origins['tables']['snes'][0],
        code_base=origins['code']['snes'][0], code_end=origins['code']['snes'][1],
        descriptor_base=origins['descriptor']['snes'][0])
    R.require(table_plan.get('origins') == table_origins,
              'CURRENT_COMPOSER_ORIGIN_MISMATCH: table/code/descriptor origins differ from source profile')
    layout = native.current_table_layout(table_origins['table_base'])
    expected_layout = {row['name']: dict(offset=row['pc'][0]-origins['tables']['pc'][0],
        stride=row['stride'], rows=row['rows']) for row in layout}
    R.require(profile['table_layout'] == expected_layout,
              'CURRENT_COMPOSER_TABLES_MISMATCH: current table family layout differs from source profile')
    supplied = table_plan.get('tables')
    R.require(type(supplied) is list and len(supplied) == len(layout)
              and all(type(row) is dict for row in supplied)
              and [row.get('name') for row in supplied] == [row['name'] for row in layout],
              'CURRENT_COMPOSER_TABLES_MISMATCH: complete ordered current table families required')
    tail_rows = {area: {} for area in range(native.CURRENT_FIRST, native.CURRENT_END)}
    for row, expected in zip(supplied, layout):
        raw = bytes.fromhex(row['payload_hex'])
        stride = expected['stride']
        R.require(len(raw) == native.CURRENT_PARENT_COUNT * stride,
                  'CURRENT_COMPOSER_TABLES_MISMATCH: current table payload extent differs')
        for area, values in tail_rows.items():
            value = raw[area*stride:(area+1)*stride]
            values[expected['name']] = list(value) if stride == 8 else int.from_bytes(value, 'little')
    rebuilt = native.plan_current_tables(source, tail_rows, origins=table_origins,
        policy=dict(source_rom_sha256=R.sha(source), source_profile_sha256=profile_digest,
                    allocation_granted=False, publication_authorized=False))
    for name, used in (('tables', rebuilt['tables_pc']), ('descriptor', rebuilt['descriptor_pc'])):
        reserved = origins[name]['pc']
        R.require(used[0] == reserved[0] and used[1] <= reserved[1],
                  'CURRENT_COMPOSER_ORIGIN_MISMATCH: ' + name + ' exceeds its source profile interval')
    R.require(rebuilt['code_pc'] == origins['code']['pc'] and table_plan == rebuilt,
              'CURRENT_COMPOSER_TABLES_MISMATCH: table payload, assembler or extents differ from canonical plan')
    property_rows = native.current_property_rows(document)
    for area, values in property_rows.items():
        R.require(all(tail_rows[area][name] == value for name, value in values.items()),
                  'CURRENT_COMPOSER_PROPERTIES_MISMATCH: native selectors differ from saved properties')
    actor_stream_plan = native.plan_current_actor_streams(
        source, document, current_source_profile=profile)
    if actor_storage_plan is not None:
        actor_origin = origins.get('actors')
        R.require(type(actor_origin) is dict,
                  'CURRENT_COMPOSER_ACTORS_ORIGIN_UNBOUND: explicit source-profile actors interval required')
        lo, hi = actor_origin['pc']
        expected_actors = native.plan_current_actor_storage(source, document,
            current_source_profile=profile, data_snes=actor_origin['snes'][0], capacity=hi-lo,
            preimage=A.expanded_rom(source)[lo:hi])
        R.require(actor_storage_plan == expected_actors,
                  'CURRENT_COMPOSER_ACTORS_MISMATCH: actor payload/extent/preimage/source differs')
        R.require(all(tail_rows[area][name] == pointer for area, rows in expected_actors['phase_rows'].items()
                      for name, pointer in rows.items()),
                  'CURRENT_COMPOSER_ACTOR_POINTERS_MISMATCH: table pointers differ from bound actor storage')
    gameplay_area_plan = A.gameplay_area_plan(document)
    for row in gameplay_area_plan['assignments']:
        values = tail_rows[row['map_id']]
        R.require(values['parent'] == row['parent_map_id']
                  and values['area_size'] == row['area_size_code'],
                  'CURRENT_COMPOSER_GAMEPLAY_AREAS_MISMATCH: table parent/size differs from authored area')
    if gameplay_area_plan['complete']:
        for area, values in A.gameplay_transition_rows(source, document).items():
            R.require(all(tail_rows[area][name] == value for name, value in values.items()),
                      'CURRENT_COMPOSER_GAMEPLAY_TRANSITIONS_MISMATCH: table differs from saved-area transition lowering')
    R.require(type(graphics_source) is str and graphics_source
              and graphics_report.get('current_mode') is True and graphics_report.get('parent_count') == 192
              and graphics_report.get('source_contract_sha256') == R.sha(encoded(contract))
              and graphics_report.get('generated_sha256') == R.sha(graphics_source.encode()),
              'Current source output requires matching192-row graphics source')
    graphics = contract.get('origins', {}).get('graphics')
    R.require(type(graphics) is dict and type(graphics.get('snes')) is list and len(graphics['snes']) == 2
              and all(type(v) is int for v in graphics['snes']),
              'CURRENT_SOURCE_ORIGIN_UNBOUND: graphics source origin is required')
    start, end = graphics['snes']
    R.require(graphics_report.get('graphics_origin_snes') == [start, end],
              'Current graphics source origin differs from selected contract')
    R.require(0 <= start < end <= 0x1000000 and start & 0xFFFF >= 0x8000
              and start >> 16 == (end-1) >> 16, 'Current graphics source must own one mapped bank')
    constants = ('; Source review only; current preparation is never selected.\n'
        '!LYRA_PROJECT_DATA_PRESENT = 1\n!LYRA_NATIVE_A1_ENABLED = 0\n!LYRA_CURRENT_MODE = 1\n'
        + table_plan['constants_assembler']
        + f'!LYRA_CURRENT_GFX_ORIGIN = ${start:06X}\n!LYRA_CURRENT_GFX_END = ${end:06X}\n'
        + '!LYRA_CURRENT_ACTORS_ENABLED = 0\n!LYRA_CURRENT_ACTORS_BOUND = 0\n'
        + '!PROJECT_BG128_ENABLED = 0\n!PROJECT_BG128_RESTORE_BOUND = 0\n')
    data = table_plan['tables_assembler'] + table_plan['descriptor_assembler']
    if actor_storage_plan is not None:
        constants += f"!LYRA_CURRENT_ACTOR_BANK = ${actor_storage_plan['bank']:02X}\n"
        data += native.emit_current_actor_data(actor_storage_plan)
    remaining = list(table_plan['remaining_consumers'])
    if actor_storage_plan is None:
        remaining.append('actor stream storage/bank binding')
    if gameplay_area_plan['areas']:
        remaining.append('authored gameplay-area native render/actor aggregation')
    if gameplay_area_plan['unassigned_maps']:
        remaining.append('unassigned gameplay-area pages')
    if bg128_plan is not None:
        bg = importlib.import_module('lyra_project_bg_palette')
        bg_origin = origins['bg_palette']
        lo, hi = bg_origin['pc']
        expanded_source = A.expanded_rom(source)
        expected_bg = bg.plan_bg128([SimpleNamespace(map_id=0xA0+index, properties=properties)
            for index, properties in enumerate(document.properties)],
            data_snes=bg_origin['snes'][0], capacity=hi-lo, preimage=expanded_source[lo:hi])
        R.require(type(bg128_plan) is dict and bg128_plan.get('publication_authorized') is False
                  and bg128_plan == expected_bg,
                  'CURRENT_COMPOSER_BG128_MISMATCH: BG origin, capacity, document payload or source preimage differs')
        data += bg.emit_bg128_data(bg128_plan)
    else:
        remaining.append('BG128 source data/code origin and consumer binding')
    files = {'runtime_constants.asm': constants.encode(), 'runtime_data.asm': data.encode(),
             'graphics_runtime_tables.asm': graphics_source.encode(),
             'descriptor.json': encoded(dict(kind=native.CURRENT_KIND, payload_hex=table_plan['descriptor_hex']))}
    prepared = dict(kind='lyra.current_source_prepare.v1', selected=False, source_bindings=source_bindings,
        source_rom_sha256=table_plan['source_rom_sha256'], source_profile_sha256=table_plan['source_profile_sha256'],
        source_size=len(source), document_sha256=profile['document_sha256'],
        generation=profile['review']['generation'], operation_id=profile['review']['operation_id'],
        reservation_review_id=profile['reservation_review_id'],
        source_contract_sha256=R.sha(encoded(contract)), source_domain=table_plan['source_domain'],
        actor_stream_plan=actor_stream_plan,
        actor_storage_plan=actor_storage_plan,
        saved_property_rows_sha256=current.T.digest(property_rows),
        gameplay_area_plan=gameplay_area_plan,
        generated_files={name:R.sha(raw) for name,raw in files.items()}, remaining_consumers=remaining,
        allocation_granted=False, producer_enforcement_verified=False, publication_authorized=False,
        ordinary_build_ready=False, runtime_admission=False, rom_written=False)
    files['prepare.json'] = encoded(prepared)
    for row in source_bindings:
        R.require(R.sha(Path(row['path']).read_bytes()) == row['sha256'],
                  'Current source changed while composing generated inputs')
    current.verify_current_native_source_profile(profile, source, document)
    return files


def write_outputs(folder, files, *, protected=()):
    folder = Path(folder)
    protected = {Path(path).resolve() for path in protected}
    for name in files:
        path = folder / name
        R.require(not any(p.is_symlink() for p in (path, *path.parents)), 'Generated output uses a symlink')
        R.require(path.resolve() not in protected, 'Generated output aliases an input')
        R.require(not path.exists() or path.is_file(), 'Generated output is not a regular file')
    for name, raw in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(raw)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def prepare(folder, *, project=None, base_rom=None, request=None, ledger_path=None):
    R.require(bool(project) or not request, 'A request requires a selected Lyra project')
    plan = (make_plan(project, base_rom, request, ledger_path=ledger_path) if project
            else dict(kind='lyra.ordinary_build_prepare.v1', selected=False, production_maps=[], production_edge_ids=[]))
    files = render_outputs(plan)
    write_outputs(folder, files, protected=[row['path'] for row in plan.get('inputs', [])])
    return json.loads(files['prepare.json'])


def require_verified_native_receipt(result, compiled_sha256):
    """An inspection result cannot authorize publication of assembled bytes."""
    R.require(type(result) is dict
              and result.get('kind') == PUBLICATION['compiled_reader_variant']
              and result.get('compiled_consumers_verified') is True
              and result.get('compiled_rom_sha256') == compiled_sha256
              and result.get('production_admission') is False
              and result.get('save_exit_policy') == 'held',
              'Native loader receipt is unverified, stale, or outside publication scope')
    return result


def verify(folder, rom, symbols, *, receipt):
    folder, rom, symbols, receipt = map(Path, (folder, rom, symbols, receipt))
    R.require(receipt.parent.resolve() == rom.parent.resolve(),
              'Verification receipt must be beside the assembled ROM')
    prior = json.loads((folder / 'prepare.json').read_bytes())
    R.require(prior.get('selected') is True, 'No selected current Lyra prepare context')
    plan = make_plan(prior['project'], prior['base_rom'], prior['request'], ledger_path=prior['ledger'])
    files = render_outputs(plan)
    R.require(all((folder / name).read_bytes() == raw for name, raw in files.items()),
              'Prepared context changed after generation')
    saved, compiled = Path(plan['base_rom']).read_bytes(), rom.read_bytes()
    native = importlib.import_module('lyra_native_loaders')  # Missing strict verifier is a hard refusal.
    descriptor = compiled[DESCRIPTOR_PC:DESCRIPTOR_PC + 64]
    symbol_bytes = symbols.read_bytes()
    native_result = native.verify_native_loaders(saved, compiled, symbol_bytes, descriptor,
                                                 ledger_path=plan['ledger'])
    require_verified_native_receipt(native_result, R.sha(compiled))
    result = verify_data(saved, compiled, plan['writes'], dict(enumerate(A.read_tile32(saved, i)
        for i in range(0x4540))), {r['tile32_id']: tuple(r['quadrants']) for r in plan['emitted_definitions']},
        plan['targets']['native37'], plan['targets']['a1'])
    projection = C.collision_projection(saved, compiled,
        [D.native_map_grid(compiled, a) for a in (0x36, 0x37, 0x3E, 0x3F)] + [plan['targets']['a1']])
    result.update(kind='lyra.ordinary_build_verification.v1', prepared_sha256=R.sha(files['prepare.json']),
        saved_rom_sha256=R.sha(saved), compiled_rom_sha256=R.sha(compiled), symbols_sha256=R.sha(symbol_bytes),
        current_ledger_sha256=plan['current_ledger_sha256'], native_loaders=native_result,
        collision_projection=projection, production_maps=[], production_edge_ids=[],
        save_exit_policy='unchanged_held', native_gameplay_verified=False, save_reopen_verified=False)
    R.require(not receipt.resolve().is_relative_to((ROOT / 'Data').resolve()),
              'Verification receipt must remain outside build source inputs')
    R.require(all(R.sha(Path(row['path']).read_bytes()) == row['sha256'] for row in plan['inputs'])
              and rom.read_bytes() == compiled and symbols.read_bytes() == symbol_bytes,
              'Publisher verification input changed during readback')
    write_outputs(receipt.parent, {receipt.name: encoded(result)},
                  protected=[rom, symbols, *[folder / name for name in GENERATED_FILES],
                             *[row['path'] for row in plan['inputs']]])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--project', type=Path)
    p.add_argument('--request', type=Path)
    p.add_argument('--base-rom', type=Path)
    p.add_argument('--ledger', type=Path)
    p.add_argument('--output', type=Path, default=ROOT / OUTPUT)
    v = sub.add_parser('verify')
    v.add_argument('--input', type=Path, default=ROOT / OUTPUT)
    v.add_argument('--rom', type=Path, required=True)
    v.add_argument('--symbols', type=Path, required=True)
    v.add_argument('--receipt', type=Path, required=True)
    e = sub.add_parser('export-request', help='Copy historical roles from a pinned composition request')
    e.add_argument('--composition-request', type=Path, required=True)
    e.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.output, project=args.project, base_rom=args.base_rom,
                         request=args.request, ledger_path=args.ledger)
    elif args.command == 'verify':
        result = verify(args.input, args.rom, args.symbols, receipt=args.receipt)
    else:
        old = json.loads(args.composition_request.read_bytes())
        R.require(set(old) == set(C.PINS), 'Pinned composition request roles differ')
        R.require(not args.output.exists(), 'Request exporter refuses to replace an existing file')
        result = {key: old[key] for key in ROLES}
        write_outputs(args.output.parent, {args.output.name: encoded(result)}, protected=[args.composition_request])
    print(json.dumps({'kind': result.get('kind', 'lyra.ordinary_request.v1'),
                      'selected': result.get('selected'), 'rom_written': False}, sort_keys=True))


if __name__ == '__main__':
    main()
