"""Native-save-first build transfers. No editable ROM or candidate is written.

Yaze owns successful-save generations and producer enforcement. This adapter
captures their identities, verifies immutable inputs, and calls the existing
native compiler only with a separately reviewed current-source allocation.
"""
from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import lyra_native_streams as N
import lyra_private_reservation as V
import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_composition as C
import lyra_project_prepare as Q
import lyra_project_publisher as P
import lyra_project_tile32 as T
from lyra_project_terrain import Allocation, resolve_project_terrain

KIND = 'lyra.current_save_transfer_request.v1'
SAVE_KIND = 'yaze.native_save.v1'
CONTEXT_KIND = 'yaze.native_save_context.v1'
PRODUCER_KIND = 'yaze.native_save_producer_identity.v1'
PROOF_KIND = 'yaze.current_save_transfer_enforcement.v1'
POLICY_KIND = 'lyra.current_save_transfer_policy.v1'
REVIEW_KIND = 'lyra.current_save_reservation_review.v1'
CURRENT_SOURCE_CONTRACT = Path(__file__).resolve().parents[2] / 'Config/lyra_current_source_contract.json'
CURRENT_CONTRACT_KIND = 'lyra.current_engine_source_contract.v1'
CURRENT_PROFILE_KIND = 'lyra.current_native_source_profile.v1'
CONTROL_FILES = {'lyra_build_request_file', 'native_save_receipt_file',
                 'native_save_producer_file', 'native_save_transfer_proof_file'}
# Yaze 7dbfa8ee ProjectSaveSources and SaveToFile define these [files] types.
# Roots are references, never an invitation to scan or hash whole directories.
DIRECTORY_REFERENCES = {'rom_backup_folder', 'code_folder', 'assets_folder', 'patches_folder',
                        'output_folder', 'custom_objects_folder', 'sprite_source_root'}
FILE_REFERENCES = {'labels_filename', 'symbols_filename', 'cutscene_shots',
                  'overworld_graphics_preview', 'dungeon_tile_patterns', 'custom_collision_json',
                  'hack_manifest_file', 'sprite_catalog_file', 'terrain_catalog_file', 'palette_catalog_file'}


def _json(raw):
    return json.loads(raw, object_pairs_hook=_unique)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        R.require(key not in result, 'Duplicate current-transfer JSON key')
        result[key] = value
    return result


def _keys(value, keys, label):
    R.require(type(value) is dict and set(value) == set(keys), f'Malformed {label}')


def _token(value):
    # Generic producer operation IDs are opaque, not an Oracle UUID schema.
    return type(value) is str and 0 < len(value) <= 128 and all(32 < ord(c) < 127 for c in value)


def _reference(project, config, key, *, existing=True):
    value = config.get('files', key, fallback='').strip()
    R.require(value and '\0' not in value, f'Current-save project has no {key}')
    path = Path(value)
    path = path if path.is_absolute() else project.parent / path
    return path.resolve(strict=existing)


def _input_file(project, value, field):
    R.require(value and '\0' not in value, f'Invalid configured input file: {field}')
    path = Path(value)
    path = (path if path.is_absolute() else project.parent / path).resolve(strict=True)
    R.require(path.is_file(), f'Configured input file {field} is not a regular file: {path}')
    return path


def _file_dependencies(project, config):
    known = CONTROL_FILES | DIRECTORY_REFERENCES | FILE_REFERENCES | {
        'rom_filename', 'lyra_terrain_file', 'additional_roms'}
    unknown = sorted(key for key, value in config.items('files') if value.strip() and key not in known)
    R.require(not unknown, 'Unsupported typed [files] reference: ' + ', '.join(unknown))
    paths = {}
    for key in sorted(FILE_REFERENCES):
        value = config.get('files', key, fallback='').strip()
        if value:
            paths['dependency.' + key] = _input_file(project, value, key)
    # Match Yaze ParseStringList: literal commas, space/tab trimming, compact
    # nonempty indices, stable order and duplicates. Quoting is not a CSV feature.
    entries = [part.strip(' \t') for part in config.get('files', 'additional_roms', fallback='').split(',')]
    for index, value in enumerate(part for part in entries if part):
        role = f'dependency.additional_roms.{index}'
        paths[role] = _input_file(project, value, role)
    return paths


def _live(project):
    project = Path(os.path.abspath(project))
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.optionxform = str
    config.read_string(project.read_text(encoding='utf-8-sig'))
    config.defaults().clear()
    R.require(config.get('rom', 'role', fallback='') == 'dev',
              'Current-save transfer requires an editable dev project')
    paths = dict(project=project, rom=_reference(project, config, 'rom_filename'),
                 terrain=resolve_project_terrain(project))
    paths.update(_file_dependencies(project, config))
    R.require(len({paths[key].resolve() for key in ('project', 'rom', 'terrain')}) == 3,
              'Current-save inputs alias each other')
    inputs = {key: Q.bound(path) for key, path in sorted(paths.items())}
    producer_path = _reference(project, config, 'native_save_producer_file')
    producer_binding = Q.bound(producer_path)
    producer = _json(Q.read_bound(producer_binding))
    _keys(producer, {'kind', 'source_head', 'editor', 'verifier', 'source_bindings'}, 'selected producer identity')
    R.require(producer['kind'] == PRODUCER_KIND and type(producer['source_head']) is str
              and re.fullmatch('[0-9a-f]{40}', producer['source_head'])
              and type(producer['source_bindings']) is list and producer['source_bindings'],
              'Current-save selected producer identity is incomplete')
    producer_rows = [producer['editor'], producer['verifier'], *producer['source_bindings']]
    for row in producer_rows:
        Q.read_bound(row)
    R.require(len({row['path'] for row in producer_rows}) == len(producer_rows),
              'Duplicate selected producer binding')
    receipt_path = Path(str(project.resolve()) + '.native-save.json')
    R.require(receipt_path.is_file(),
              'CURRENT_NATIVE_SAVE_RECEIPT_REQUIRED: complete an actual native Save before preparing a build transfer')
    receipt_binding = Q.bound(receipt_path)
    receipt = _json(Q.read_bound(receipt_binding))
    _keys(receipt, {'kind', 'generation', 'operation_id', 'operation', 'receipt_path',
                   'artifacts', 'bindings_complete', 'binding_errors'}, 'native save receipt')
    R.require(receipt['kind'] == SAVE_KIND and type(receipt['generation']) is int
              and 0 < receipt['generation'] <= 0xFFFFFFFFFFFFFFFF and _token(receipt['operation_id'])
              and receipt['operation'] in ('save', 'save_as') and receipt['receipt_path'] == str(receipt_path)
              and receipt['bindings_complete'] is True and receipt['binding_errors'] == [],
              'A fully bound native Save completion is required; ROM-only or incomplete receipts cannot admit a build')
    expected = {('sidecar' if key == 'terrain' else key): row for key, row in inputs.items()}
    expected['producer'] = producer['editor']
    R.require(type(receipt['artifacts']) is list, 'Malformed native Save artifacts')
    artifacts = {}
    for row in receipt['artifacts']:
        _keys(row, {'role', 'path', 'sha256', 'bytes'}, 'native Save artifact')
        role = row['role']
        R.require(type(role) is str and role not in artifacts
                  and (role in expected or role.startswith('dependency.')),
                  'Unknown or duplicate native Save artifact role')
        binding = dict(path=row['path'], sha256=row['sha256'])
        content = Q.read_bound(binding)
        R.require(type(row['bytes']) is int and row['bytes'] == len(content), 'Native Save artifact byte count differs')
        R.require(role not in expected or binding == expected[role],
                  'Native save receipt does not bind this project, inputs and selected producer')
        artifacts[role] = binding
        if role not in expected:
            inputs[role] = binding
    R.require(set(expected) <= set(artifacts), 'Native Save receipt omitted a configured project/sidecar/dependency/producer role')
    context_name = os.environ.get('YAZE_NATIVE_SAVE_CONTEXT', '')
    R.require(context_name and Path(context_name).is_absolute(),
              'CURRENT_SAVE_CONTEXT_REQUIRED: existing editor session must expose its live Save/SaveAs context')
    context_path = Path(context_name).resolve(strict=True)
    R.require(not context_path.is_relative_to(project.parent.resolve())
              and context_path.parent.name == 'native-saves',
              'Current native Save context must be outside the project in its stable native-saves control location')
    context_binding = Q.bound(context_name)
    context = _json(Q.read_bound(context_binding))
    _keys(context, {'kind', 'editing_source_path', 'project_path', 'rom_path', 'producer', 'state', 'native_commit'},
          'live native Save context')
    origin = context['editing_source_path']
    R.require(type(origin) is str and Path(origin).is_absolute() and str(Path(origin).resolve()) == origin
              and context_path.name == R.sha(origin.encode('utf-8')) + '.json',
              'Native Save context does not use its canonical editing-source identity key')
    R.require(context['kind'] == CONTEXT_KIND and context['project_path'] == str(project.resolve())
              and context['rom_path'] == inputs['rom']['path'],
              'Editor context moved or native Save context no longer matches this project')
    R.require(context['state'] == 'committed' and type(context['native_commit']) is dict,
              'CURRENT_SAVE_CONTEXT_REBOUND: this context has no current native commit')
    commit = context['native_commit']
    _keys(commit, {'receipt_path', 'generation', 'operation_id'}, 'live native commit')
    producer_artifact = next(row for row in receipt['artifacts'] if row['role'] == 'producer')
    R.require(type(commit['generation']) is int and 0 < commit['generation'] <= 0xFFFFFFFFFFFFFFFF
              and commit == dict(receipt_path=str(receipt_path), generation=receipt['generation'],
                                 operation_id=receipt['operation_id'])
              and context['producer'] == producer_artifact,
              'Live native commit/producer no longer matches the complete Save receipt')
    proof_path = _reference(project, config, 'native_save_transfer_proof_file', existing=False)
    R.require(proof_path not in {Path(row['path']) for row in inputs.values()},
              'Transfer proof aliases a saved input')
    return dict(project=str(project), inputs=inputs, producer=producer_binding,
        producer_identity=producer, save_receipt=receipt_binding,
        generation=receipt['generation'], operation_id=receipt['operation_id'],
        save_context=context_binding,
        enforcement_receipt=str(proof_path))


def _recheck(live):
    try:
        current = _live(live['project'])
    except (ValueError, OSError, configparser.Error) as error:
        raise ValueError(f'Current-save transfer retired: {error}') from error
    R.require(current == live,
              'Current-save transfer retired: a later save or input/producer change occurred')


def _census(source, document):
    rows = N.reject_stream_aliases(source, [])
    references = []
    for area in range(160):
        planes = [N._plane(source, area, table)[0] for table in N.POINTER_TABLES]
        references.extend([area, cell, high << 8 | low]
                          for cell, (high, low) in enumerate(zip(*planes)))
    R.require(all(tile < 0x4540 for area, cell, tile in references),
              'Current native reader references an out-of-range Tile32 definition')
    spans = {}
    for row in rows:
        spans.setdefault(tuple(row['pc']), []).append([row['map_id'], row['table']])
    return dict(source_rom_sha256=R.sha(source), source_size=len(source), native_maps=160,
        native_planes=320, native_streams_sha256=T.digest(rows),
        native_references_sha256=T.digest(references),
        native_unique_streams=len(spans),
        aliases=[dict(pc=list(span), consumers=users) for span, users in sorted(spans.items()) if len(users) > 1],
        required_definitions=len(C._missing(source, document, V.FULL_MAPS)),
        required_literal_stream_bytes=32 * 518)


def _identity(request):
    return T.digest({key: value for key, value in request.items() if key != 'transfer_id'})


def prepare_transfer(project, z3ed, output, candidate, *, policy_id=None):
    """Capture a new immutable input; never advance Yaze's save generation."""
    output = Path(os.path.abspath(output))
    candidate = Path(os.path.abspath(candidate))
    R.require(not output.exists() and not candidate.exists(), 'Transfer input/output paths must be new')
    R.require(not any(path.is_symlink() for path in (output, *output.parents, candidate, *candidate.parents)),
              'Current-save transfer paths use a symlink')
    R.require(not candidate.is_relative_to(output) and not output.is_relative_to(candidate),
              'Candidate must be separate from immutable transfer input')
    live = _live(project)
    R.require(candidate != Path(live['enforcement_receipt'])
              and not Path(live['enforcement_receipt']).is_relative_to(output),
              'Transfer proof must be separate from candidate and immutable snapshot input')
    R.require(Q.bound(z3ed) == live['producer_identity']['verifier'],
              'Current-save verifier differs from the selected producer')
    R.require(str(candidate) not in {row['path'] for row in live['inputs'].values()},
              'Candidate aliases a saved input')
    raw = {key: Q.read_bound(row) for key, row in live['inputs'].items()}
    R.require(len(raw['rom']) in (0x200000, 0x400000),
              'Unsupported current native source size: expanded writer requires unheadered2MiB or4MiB; '
              'no snapshot or candidate was created')
    proof = A.native_verify(Path(z3ed), Path(project), Path(live['inputs']['rom']['path']))
    _recheck(live)
    document = C._document(raw['terrain'], P.encoded(proof), raw['rom'])
    files, snapshots = {}, {}
    for index, (key, content) in enumerate(sorted(raw.items())):
        name = f'inputs/{index:03d}.bin'
        files[name] = content
        snapshots[key] = dict(path=str(output / name), sha256=R.sha(content))
    files['observation.json'] = P.encoded(proof)
    files['native-save.json'] = Q.read_bound(live['save_receipt'])
    files['producer.json'] = Q.read_bound(live['producer'])
    files['context.json'] = Q.read_bound(live['save_context'])
    request = dict(kind=KIND, live=live, snapshot_root=str(output), inputs=snapshots,
        observation=dict(path=str(output / 'observation.json'), sha256=R.sha(files['observation.json'])),
        save_snapshot=dict(path=str(output / 'native-save.json'), sha256=R.sha(files['native-save.json'])),
        producer_snapshot=dict(path=str(output / 'producer.json'), sha256=R.sha(files['producer.json'])),
        context_snapshot=dict(path=str(output / 'context.json'), sha256=R.sha(files['context.json'])),
        census=_census(raw['rom'], document), allocation_policy_id=policy_id,
        target=dict(path=str(candidate), size=0x400000, role='compiled_candidate',
                    native_serializer_after_compile='forbidden'))
    request['transfer_id'] = _identity(request)
    _recheck(live)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    protected = [row['path'] for row in live['inputs'].values()]
    try:
        P.write_outputs(output, files, protected=protected)
        for name in files:
            (output / name).chmod(0o444)
        _recheck(live)
        # Completion marker last; consumers still recheck authoritative Save.
        P.write_outputs(output, {'request.json': P.encoded(request)}, protected=protected)
        (output / 'request.json').chmod(0o444)
        _recheck(live)
    except BaseException as error:
        (output / 'request.json').unlink(missing_ok=True)
        try:
            P.write_outputs(output, {'refusal.json': P.encoded(dict(
                kind=KIND, transfer_id=request['transfer_id'], ready=False,
                error='Transfer preparation did not complete; no usable request published'))})
        except Exception as diagnostic_error:
            if hasattr(error, 'add_note'):
                error.add_note(f'Transfer refusal report also failed: {diagnostic_error}')
        raise
    return dict(kind=KIND, snapshot_ready=True, ready=False, transfer_id=request['transfer_id'],
        request=str(output / 'request.json'), allocation_granted=False,
        runtime_admission=False, ordinary_build_ready=False, rom_written=False)


def verify_transfer(request_path, project, base_rom):
    """Reconstruct readers and compare the live generation before/after use."""
    binding = Q.bound(request_path)
    request = _json(Q.read_bound(binding))
    _keys(request, {'kind', 'live', 'snapshot_root', 'inputs', 'observation', 'save_snapshot',
                   'producer_snapshot', 'context_snapshot', 'census', 'allocation_policy_id', 'target', 'transfer_id'}, 'current transfer request')
    R.require(request['kind'] == KIND and request['transfer_id'] == _identity(request),
              'Current transfer identity differs')
    R.require(Path(request['live']['project']).resolve() == Path(project).resolve(),
              'Current transfer belongs to a different project')
    _recheck(request['live'])
    root = Path(request['snapshot_root'])
    R.require(root.is_absolute() and root.resolve() == root, 'Current snapshot root is not canonical')
    R.require(Path(binding['path']) == root / 'request.json', 'Current transfer completion marker differs')
    rows = [binding, *request['inputs'].values(), request['observation'],
            request['save_snapshot'], request['producer_snapshot'], request['context_snapshot']]
    R.require(set(request['inputs']) == set(request['live']['inputs']), 'Transfer snapshot roles differ')
    R.require(len({row['path'] for row in rows}) == len(rows), 'Transfer snapshot files alias each other')
    for row in rows:
        path = Path(row['path'])
        R.require(path.resolve().is_relative_to(root) and not any(p.is_symlink() for p in (path, *path.parents))
                  and path.stat().st_mode & 0o222 == 0, 'Transfer snapshot must be immutable and owned')
        Q.read_bound(row)
    raw = {key: Q.read_bound(row) for key, row in request['inputs'].items()}
    R.require(all(R.sha(content) == request['live']['inputs'][key]['sha256'] for key, content in raw.items()),
              'Transfer snapshot differs from committed native Save')
    R.require(Q.read_bound(request['save_snapshot']) == Q.read_bound(request['live']['save_receipt'])
              and Q.read_bound(request['producer_snapshot']) == Q.read_bound(request['live']['producer'])
              and Q.read_bound(request['context_snapshot']) == Q.read_bound(request['live']['save_context']),
              'Transfer generation/producer snapshot differs')
    R.require(Path(base_rom).read_bytes() == raw['rom'], 'Build base differs from current-save snapshot')
    target = request['target']
    _keys(target, {'path', 'size', 'role', 'native_serializer_after_compile'}, 'current transfer target')
    R.require(type(target['size']) is int and target['size'] == 0x400000 and target['role'] == 'compiled_candidate'
              and target['native_serializer_after_compile'] == 'forbidden'
              and not Path(target['path']).exists()
              and not any(p.is_symlink() for p in (Path(target['path']), *Path(target['path']).parents))
              and Path(target['path']).is_absolute()
              and Path(os.path.abspath(target['path'])) == Path(target['path'])
              and not Path(target['path']).is_relative_to(root)
              and target['path'] not in {row['path'] for row in request['live']['inputs'].values()},
              'Current transfer requires a new separate4MiB compiled candidate')
    document = C._document(raw['terrain'], Q.read_bound(request['observation']), raw['rom'])
    R.require(request['census'] == _census(raw['rom'], document), 'Current native reader census differs')
    _recheck(request['live'])
    Q.read_bound(binding)
    return request, raw['rom'], document


def _git(root, *args):
    try:
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as error:
        raise ValueError('Selected Oracle source is not available at the exact revision') from error


def _engine_source_context(root, engine_head):
    """Bind selected ASM inputs, not ownership or assembled write extents."""
    root = Path(root).resolve(strict=True)
    R.require(type(engine_head) is str and re.fullmatch('[0-9a-f]{40}', engine_head) is not None,
              'Selected Oracle engine requires an exact commit')
    R.require(Path(_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() == root,
              'Selected Oracle source root is not a checkout root')
    checkout_head = _git(root, 'rev-parse', 'HEAD').decode().strip()
    R.require(_git(root, 'rev-parse', engine_head + '^{commit}').decode().strip() == engine_head,
              'Selected Oracle engine commit differs')
    generate = Path(__file__).resolve().parents[1] / 'Generate'
    sys.path.insert(0, str(generate))
    try:
        import generate_hack_manifest as manifest
    finally:
        sys.path.remove(str(generate))
    def discover():
        defines = manifest._load_global_defines(root)
        sources = set(manifest.collect_reachable_asm_sources(root, defines=defines))
        assets = set()
        for path in sorted(sources):
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                line = line.split(';', 1)[0]
                if re.search(r'\bincsrc\b', line, re.IGNORECASE):
                    R.require(re.match(r'^\s*incsrc\s+', line) is not None,
                              'Selected Oracle source has an unsupported inline incsrc')
                # Generated sheet data uses `Label: incbin ...` on the same line.
                match = re.search(r'(?:^|:\s*)\s*incbin\s+(.+)$', line, re.IGNORECASE)
                if match is None:
                    continue
                value = match.group(1).strip()
                literal = re.fullmatch(r'"([^"!<>]+)"|\'([^\'!<>]+)\'|([^\s!<>"\']+)', value)
                R.require(literal is not None,
                          'Selected Oracle source has an unsupported computed/ranged incbin')
                name = next(part for part in literal.groups() if part is not None)
                candidates = [path.parent / name, root / name]
                asset = next((candidate for candidate in candidates if candidate.is_file()), None)
                R.require(asset is not None, 'Selected Oracle incbin asset is missing: ' + name)
                assets.add(asset.resolve(strict=True))
        return defines, sources, assets
    defines, paths, assets = discover()
    initial = (defines.copy(), paths.copy(), assets.copy())
    asm_paths = sorted(path.relative_to(root).as_posix() for path in paths)
    paths.update(assets)
    paths.update(root / name for name in ('Config/allocation_ownership.json', 'Core/ZS ROM MAP.txt',
                                         'Scripts/Build/build_rom.sh'))
    bindings = []
    for path in sorted(paths):
        R.require(path.is_file() and path.resolve().is_relative_to(root)
                  and not any(p.is_symlink() for p in (path, *path.parents)),
                  'Selected Oracle source input escapes its checkout or uses a symlink')
        relative = path.relative_to(root).as_posix()
        binding = Q.bound(path)
        R.require(Q.read_bound(binding) == _git(root, 'show', engine_head + ':' + relative),
                  'Selected Oracle source differs from engine commit: ' + relative)
        bindings.append(binding)
    R.require(_git(root, 'rev-parse', 'HEAD').decode().strip() == checkout_head,
              'Selected Oracle checkout changed during source binding')
    R.require(discover() == initial,
              'Selected Oracle source closure/profile changed during binding')
    for binding in bindings:
        Q.read_bound(binding)
    return dict(root=str(root), engine_head=engine_head, checkout_head=checkout_head,
        ledger=Q.bound(root / 'Config/allocation_ownership.json'), bindings=bindings,
        asm_paths=asm_paths, incbin_paths=sorted(path.relative_to(root).as_posix() for path in assets),
        defines=defines,
        source_scope='reachable ASM, literal incbin assets, named ledger, ROM map and build entry',
        assembled_write_extents_verified=False)


def reservation_review(request_path, project, base_rom, proposal_path, source_root, engine_head):
    """Bind an ungranted reservation review to one existing saved generation.

    This never installs a policy, invokes the compiler, or emits a ROM. The
    historical adapter ledger is deliberately not used as current authority.
    """
    request_binding = Q.bound(request_path)
    request, source, document = verify_transfer(request_path, project, base_rom)
    proposal_binding = Q.bound(proposal_path)
    proposal = _json(Q.read_bound(proposal_binding))
    _keys(proposal, {'kind', 'status', 'allocation_granted', 'runtime_admission',
        'producer_enforcement_verified', 'source_rom_sha256', 'source_size', 'source_engine_head',
        'named_ledger_path', 'named_ledger_sha256', 'named_ledger_conflicts', 'native_reference_conflicts',
        'native_tile32_ids_used', 'proposed_tile32_id_range', 'proposed_id_capacity',
        'required_new_tile32_definitions', 'proposed_spare_ids', 'native_copy_maps', 'packed_preimages',
        'proposed_stream_pc_range', 'required_stream_bytes', 'stream_preimage_sha256',
        'proposed_lifetime', 'required_consumers', 'background_palette_runtime_data_range'},
        'current-source reservation proposal')
    R.require(proposal.get('kind') == 'lyra.current_saved_allocation_proposal.v1'
              and proposal.get('allocation_granted') is False
              and proposal.get('runtime_admission') is False
              and proposal.get('producer_enforcement_verified') is False,
              'Reservation review requires an explicitly ungranted proposal')
    R.require(proposal.get('source_rom_sha256') == R.sha(source)
              and type(proposal.get('source_size')) is int and proposal['source_size'] == len(source),
              'Reservation proposal belongs to a different saved ROM')
    ids = proposal.get('proposed_tile32_id_range')
    R.require(type(ids) is list and len(ids) == 2 and all(type(i) is int for i in ids)
              and 0 <= ids[0] < ids[1] <= 0x4540 and ids[0] % 4 == ids[1] % 4 == 0,
              'Reservation review requires complete packed Tile32 groups')
    lo, hi = ids
    count = hi - lo
    missing = request['census']['required_definitions']
    spare_count = proposal.get('proposed_spare_ids')
    R.require(type(spare_count) is int and 0 <= spare_count < count
              and type(proposal.get('proposed_id_capacity')) is int and proposal['proposed_id_capacity'] == count
              and type(proposal.get('required_new_tile32_definitions')) is int
              and proposal['required_new_tile32_definitions'] == missing
              and missing + spare_count == count and proposal.get('native_copy_maps') == [],
              'Reservation demand/spare semantics differ from this saved generation')
    expanded = A.expanded_rom(source)
    packed = [[base + lo // 4 * 6, base + hi // 4 * 6] for base in A.TILE32_BASES]
    stream = proposal.get('proposed_stream_pc_range')
    R.require(type(stream) is list and len(stream) == 2 and all(type(i) is int for i in stream)
              and 0 <= stream[0] < stream[1] <= len(expanded), 'Invalid proposed stream range')
    preimages = proposal.get('packed_preimages')
    R.require(type(preimages) is list and len(preimages) == 4
              and [row.get('pc') for row in preimages] == packed,
              'Reservation review needs all four exact packed spans')
    all_preimages = [*preimages, dict(pc=stream, sha256=proposal.get('stream_preimage_sha256'))]
    for row in all_preimages:
        _keys(row, {'pc', 'sha256'}, 'reservation preimage')
        R.require(R.sha(expanded[slice(*row['pc'])]) == row['sha256'],
                  'Reservation review preimage differs')
    R.require(type(proposal.get('required_stream_bytes')) is int
              and proposal['required_stream_bytes'] == request['census']['required_literal_stream_bytes']
              and stream[1] - stream[0] >= proposal['required_stream_bytes'],
              'Reservation stream capacity differs from this saved generation')
    used = set()
    for area in range(160):
        high, low = [N._plane(source, area, table)[0] for table in N.POINTER_TABLES]
        used.update(h << 8 | l for h, l in zip(high, low))
    R.require(not used.intersection(range(lo, hi)),
              'Reservation review overlaps native Tile32 consumers, including proposed spares')
    native_streams = N.reject_stream_aliases(source, [row['pc'] for row in all_preimages])
    atlas = A.pc(int.from_bytes(source[0x865:0x868], 'little'))
    atlas_span = [atlas, atlas+document.profile['tile_count']*8]
    pointer_tables = [dict(pc=[A.pc(table), A.pc(table)+160*3]) for table in N.POINTER_TABLES]
    dictionaries = [dict(pc=[base, base+0x4540//4*6]) for base in A.TILE32_BASES]
    tables = [dict(name=name, pc=[A.pc(old), A.pc(old)+count*stride], rows=count)
              for name, old, count, first, total, stride, at in A.SPECS]
    protected = [[0x864, 0x871], atlas_span, *[row['pc'] for row in pointer_tables+dictionaries+tables]]
    R.require(all(stream[1] <= a or stream[0] >= b for a, b in protected),
              'Reservation stream overlaps native definitions, pointers or tables')
    context = _engine_source_context(source_root, engine_head)
    R.require(proposal['source_engine_head'] == context['engine_head']
              and proposal['named_ledger_path'] == context['ledger']['path']
              and proposal['named_ledger_sha256'] == context['ledger']['sha256'],
              'Reservation proposal source/ledger binding is stale')
    R.require(type(proposal['native_tile32_ids_used']) is int
              and proposal['native_tile32_ids_used'] == len(used)
              and proposal['native_reference_conflicts'] == [] and proposal['named_ledger_conflicts'] == []
              and proposal['background_palette_runtime_data_range'] is None
              and proposal['proposed_lifetime'] ==
                  'fresh_native_save_to_disposable_build_only; expires_on_any_saved_ROM_or_sidecar_change',
              'Reservation proposal native census, unbound BG128 or lifetime differs')
    ledger = _json(Q.read_bound(context['ledger']))
    R.require(ledger.get('allocation_available') is False,
              'Reservation review requires a non-granting named ledger')
    V.require_no_named_conflicts(ledger, tile32_range=(lo, hi), stream_ranges=[stream])
    adapters = [Q.bound(Path(module.__file__)) for module in (sys.modules[__name__], V, N, A, R, C, T, P, Q)]
    adapters += [Q.bound(Path(__file__).resolve().parents[1] / 'Generate' / name)
                 for name in ('generate_hack_manifest.py', 'asm_source.py', 'generate_hooks_json.py')]
    adapters += [Q.bound(Path(__file__).resolve().parent / name) for name in
                 ('lyra_project_terrain.py', 'lyra_project_delta.py',
                  'lyra_native_loaders.py', 'lyra_native_state.py')]
    result = dict(kind=REVIEW_KIND, transfer=request_binding, transfer_id=request['transfer_id'],
        generation=request['live']['generation'], operation_id=request['live']['operation_id'],
        save_context=request['live']['save_context'], producer=request['live']['producer'],
        source_rom_sha256=R.sha(source), source_size=len(source), expanded_size=len(expanded),
        proposal=proposal_binding, selected_source=context, adapter_bindings=adapters,
        census=request['census'], tile32_id_range=ids, preimages=all_preimages,
        spare_tile32_ids=list(range(hi-spare_count, hi)),
        stream_payload_bytes=proposal['required_stream_bytes'],
        stream_slack_bytes=stream[1]-stream[0]-proposal['required_stream_bytes'],
        native_consumer_bounds=dict(maps=[0, 160], planes=320, referenced_ids=len(used),
            pointer_tables=pointer_tables, dictionaries=dictionaries, tables=tables,
            tile16_atlas_pc=atlas_span,
            decoded_streams=native_streams),
        status='UNGRANTED_SOURCE_REVIEW', allocation_granted=False, producer_enforcement_verified=False,
        assembled_write_extents_verified=False, runtime_admission=False, ordinary_build_ready=False,
        rom_written=False)
    final_request, _, _ = verify_transfer(request_path, project, base_rom)
    R.require(final_request == request, 'Current-save transfer request replaced during reservation review')
    Q.read_bound(request_binding)
    Q.read_bound(proposal_binding)
    for binding in [*context['bindings'], context['ledger'], *adapters]:
        Q.read_bound(binding)
    R.require(_git(context['root'], 'rev-parse', 'HEAD').decode().strip() == context['checkout_head'],
              'Selected Oracle checkout changed during reservation review')
    result['review_id'] = T.digest(result)
    return result


def verify_reservation_review(review, project, base_rom):
    """Re-read the exact review inputs; a fresh request cannot validate an old review."""
    R.require(type(review) is dict and review.get('kind') == REVIEW_KIND,
              'Malformed current reservation review')
    context = review['selected_source']
    for binding in [review['transfer'], review['proposal'], context['ledger'],
                    *context['bindings'], *review['adapter_bindings']]:
        Q.read_bound(binding)
    R.require(_git(context['root'], 'rev-parse', 'HEAD').decode().strip() == context['checkout_head'],
              'Selected Oracle checkout changed after reservation review')
    current = reservation_review(review['transfer']['path'], project, base_rom,
        review['proposal']['path'], context['root'], context['engine_head'])
    R.require(current == review, 'Current reservation review source/generation/bindings differ')
    return current


def _document_identity(document):
    return T.digest({key: getattr(document, key) for key in
                     ('profile', 'maps', 'properties', 'authoring', 'edge_connections', 'flight_points')})


def _current_table_layout(families):
    widths = {row[0]: row[5] for row in A.SPECS}
    widths.update({f'music_phase{i}': 1 for i in range(4)})
    R.require(type(families) is list and len(families) == len(widths)
              and all(type(name) is str for name in families)
              and len(set(families)) == len(families) and set(families) == set(widths),
              'CURRENT_SOURCE_TABLES_INCOMPLETE: every native family and four music phases require192 rows')
    layout, offset = {}, 0
    for name in families:
        layout[name] = dict(offset=offset, stride=widths[name], rows=192)
        offset += 192 * widths[name]
    return layout, offset


def validate_current_source_contract(review, project, base_rom, *, contract_path=None):
    """Validate explicit current source origins; this never grants publication."""
    canonical = Path(CURRENT_SOURCE_CONTRACT).resolve(strict=True)
    R.require(contract_path is None or Path(contract_path).resolve(strict=True) == canonical,
              'CURRENT_SOURCE_CONTRACT_AUTHORITY_MISMATCH: only the source-owned contract is accepted')
    binding = Q.bound(canonical)
    value = _json(Q.read_bound(binding))
    flags = ('allocation_granted', 'publication_authorized', 'producer_enforcement_verified',
             'ordinary_build_ready', 'runtime_admission')
    _keys(value, {'kind', 'status', 'scope', 'engine_head', 'base_head', 'source_domain',
        *flags, 'ledger', 'native_readers', 'origins', 'tables', 'saved_generation_required'},
        'current engine source contract')
    R.require(value['kind'] == CURRENT_CONTRACT_KIND and value['status'] == 'proposed'
              and value['scope'] == 'source_review_only' and value['saved_generation_required'] is True
              and all(value[key] is False for key in flags),
              'CURRENT_SOURCE_CONTRACT_UNGRANTED: source review cannot assert publication or runtime authority')
    R.require(all(type(value[key]) is str and re.fullmatch('[0-9a-f]{40}', value[key])
                  for key in ('engine_head', 'base_head')),
              'Current contract requires exact engine/base provenance')
    R.require(value['source_domain'] == dict(first_map=160, end_map=192,
              native_parent_count=160, parent_count=192)
              and all(type(n) is int for n in value['source_domain'].values()),
              'CURRENT_SOURCE_DOMAIN_INCOMPLETE: current source requires160 native and192 complete parent rows')
    _keys(value['tables'], {'rows', 'families'}, 'current source tables')
    R.require(type(value['tables']['rows']) is int and value['tables']['rows'] == 192,
              'CURRENT_SOURCE_TABLES_INCOMPLETE: a64/160-row table cannot serve the192-map domain')
    layout, table_bytes = _current_table_layout(value['tables']['families'])
    _keys(value['ledger'], {'path', 'sha256', 'source_set', 'engine_ledger_sha256'}, 'current source ledger')
    ledger = value['ledger']
    R.require(ledger['path'] == 'Config/allocation_ownership.json'
              and type(ledger['source_set']) is str and ledger['source_set'],
              'Current source ledger must name its explicit source set and canonical relative path')
    R.require(type(ledger['sha256']) is str and re.fullmatch('[0-9a-f]{64}', ledger['sha256']),
              'CURRENT_SOURCE_LEDGER_UNBOUND: current ledger has no selected source hash')
    current = verify_reservation_review(review, project, base_rom)
    context = current['selected_source']
    root = Path(context['root'])
    canonical_ledger = Path(R.LEDGER).resolve(strict=True)
    R.require(root == canonical.parent.parent and canonical_ledger == root / ledger['path']
              and context['ledger'] == Q.bound(canonical_ledger)
              and context['ledger']['sha256'] == ledger['sha256'],
              'CURRENT_SOURCE_LEDGER_MISMATCH: selected source, contract and canonical ledger differ')
    engine_ledger = _git(root, 'show', value['engine_head'] + ':' + ledger['path'])
    R.require(R.sha(engine_ledger) == ledger['engine_ledger_sha256'],
              'CURRENT_SOURCE_ENGINE_LEDGER_MISMATCH: engine provenance changed')
    R.require(_git(root, 'merge-base', value['engine_head'], value['base_head']).decode().strip()
              == value['engine_head']
              and _git(root, 'merge-base', value['base_head'], context['engine_head']).decode().strip()
              == value['base_head'], 'CURRENT_SOURCE_HEAD_MISMATCH: selected source is outside engine/base lineage')
    _, source, document = verify_transfer(current['transfer']['path'], project, base_rom)
    readers = value['native_readers']
    _keys(readers, {'decoder_spans', 'pointer_reader_spans'}, 'current native readers')
    reader_preimages = []
    for key in ('decoder_spans', 'pointer_reader_spans'):
        spans = readers[key]
        R.require(type(spans) is list and spans,
                  'CURRENT_SOURCE_READERS_UNBOUND: ' + key)
        for span in spans:
            R.require(type(span) is list and len(span) == 2 and all(type(n) is int for n in span)
                      and 0 <= span[0] < span[1] <= len(source), 'Invalid current native reader span')
            R.require(not any(span[0] < row['pc'][1] and row['pc'][0] < span[1] for row in reader_preimages),
                      'Current native reader spans overlap')
            reader_preimages.append(dict(pc=span, sha256=R.sha(source[slice(*span)])))
    origins = value['origins']
    _keys(origins, {'tables', 'code', 'descriptor', 'bg_palette', 'graphics'}, 'current source origins')
    missing = [key for key, origin in origins.items() if origin is None]
    R.require(not missing, 'CURRENT_SOURCE_ORIGIN_UNBOUND: ' + ', '.join(missing))
    origin_spans = []
    for name, origin in origins.items():
        _keys(origin, {'pc', 'snes', 'source_binding'}, 'current ' + name + ' origin')
        pc_span, snes_span = origin['pc'], origin['snes']
        R.require(type(pc_span) is list and len(pc_span) == 2
                  and all(type(n) is int for n in pc_span) and 0 <= pc_span[0] < pc_span[1] <= 0x400000
                  and type(snes_span) is list and len(snes_span) == 2
                  and all(type(n) is int for n in snes_span) and 0 < snes_span[0] < snes_span[1] <= 0x1000000
                  and [A.pc(snes_span[0]), A.pc(snes_span[1]-1)+1] == pc_span,
                  'Current ' + name + ' PC/SNES origin differs')
        R.require(origin['source_binding'] in context['bindings'],
                  'Current ' + name + ' origin lacks a selected source binding')
        Q.read_bound(origin['source_binding'])
        R.require(not any(pc_span[0] < hi and lo < pc_span[1] for lo, hi in origin_spans),
                  'Current source origin ranges overlap')
        origin_spans.append(tuple(pc_span))
    R.require(origins['tables']['pc'][1] - origins['tables']['pc'][0] >= table_bytes,
              'CURRENT_SOURCE_TABLES_INCOMPLETE: table origin cannot hold every192-row family')
    Q.read_bound(binding)
    verify_reservation_review(current, project, base_rom)
    return dict(kind='lyra.current_source_contract_review.v1', contract=binding,
        reservation_review_id=current['review_id'], selected_source=context,
        native_reader_preimages=reader_preimages, origins=origins, table_layout=layout,
        document_sha256=_document_identity(document), source_rom_sha256=R.sha(source), source_size=len(source),
        **{key: False for key in flags})


def current_native_source_profile(review, project, base_rom, *, contract_path=None):
    contract = validate_current_source_contract(review, project, base_rom, contract_path=contract_path)
    return dict(contract, kind=CURRENT_PROFILE_KIND, review=review, project=str(Path(project).resolve()),
        base_rom=str(Path(base_rom).resolve()))


def verify_current_native_source_profile(profile, source, document, *, allocation=None,
                                         spare_tile32_ids=(), native_copy_maps=()):
    R.require(type(profile) is dict and profile.get('kind') == CURRENT_PROFILE_KIND,
              'CURRENT_SOURCE_PROFILE_REQUIRED: an explicit current source profile is required')
    fresh = current_native_source_profile(profile['review'], profile['project'], profile['base_rom'],
                                         contract_path=profile['contract']['path'])
    R.require(profile == fresh and profile['source_rom_sha256'] == R.sha(source)
              and profile['source_size'] == len(source) and profile['document_sha256'] == _document_identity(document),
              'CURRENT_SOURCE_PROFILE_STALE: source, generation, document or contract changed')
    if allocation is not None:
        review = profile['review']
        lo, hi = review['tile32_id_range']
        spare = tuple(review['spare_tile32_ids'])
        ids = tuple(i for i in range(lo, hi) if i not in spare)
        assignments = tuple(zip(ids, C._missing(A.expanded_rom(source), document, V.FULL_MAPS)))
        R.require(isinstance(allocation, Allocation)
                  and allocation.stream_ranges == (tuple(review['preimages'][-1]['pc']),)
                  and allocation.owned_tile32_ids == ids
                  and allocation.tile32_assignments == assignments
                  and tuple(spare_tile32_ids) == spare and not native_copy_maps,
                  'CURRENT_SOURCE_RESERVATION_MISMATCH: allocation, assignments or spares differ from reviewed generation')
    return profile


def plan_transfer(request_path, project, base_rom, *, ledger_path=None, current_source_profile=None):
    """Bind an admitted source policy/proof to the common in-memory compiler."""
    canonical_ledger = Path(R.LEDGER).resolve(strict=True)
    R.require(ledger_path is None or Path(ledger_path).resolve(strict=True) == canonical_ledger,
              'CURRENT_SAVE_POLICY_AUTHORITY_MISMATCH: only the source-owned policy registry is accepted')
    request_binding = Q.bound(request_path)
    request, source, document = verify_transfer(request_path, project, base_rom)
    ledger_binding = Q.bound(canonical_ledger)
    ledger = _json(Q.read_bound(ledger_binding))
    policies = ledger.get('current_save_transfer_policies', [])
    R.require(type(policies) is list and all(type(row) is dict for row in policies),
              'Malformed current transfer policy registry')
    selected = [row for row in policies if row.get('id') == request['allocation_policy_id']]
    R.require(type(request['allocation_policy_id']) is str and len(selected) == 1,
              'CURRENT_SAVE_ALLOCATION_UNGRANTED: no reviewed policy matches this transfer')
    policy = selected[0]
    _keys(policy, {'id', 'kind', 'scope', 'producer_identity_sha256', 'tile32_id_range',
                   'stream_ranges', 'preimages', 'spare_tile32_ids'}, 'current allocation policy')
    R.require(policy['kind'] == POLICY_KIND and policy['scope'] == 'disposable_build_only'
              and policy['producer_identity_sha256'] == request['live']['producer']['sha256'],
              'Current allocation policy does not bind the selected producer')
    lo, hi = policy['tile32_id_range']
    R.require(type(lo) is int and type(hi) is int and 0 <= lo < hi <= 0x4540
              and lo % 4 == hi % 4 == 0, 'Current allocation must own complete packed Tile32 groups')
    spans = [[base + lo // 4 * 6, base + hi // 4 * 6] for base in A.TILE32_BASES] + policy['stream_ranges']
    R.require(type(policy['preimages']) is list and [row['pc'] for row in policy['preimages']] == spans,
              'Current allocation preimages do not cover its exact packed/stream extents')
    expanded = A.expanded_rom(source)
    for row in policy['preimages']:
        a, b = row['pc']
        R.require(type(a) is int and type(b) is int and 0 <= a < b <= len(expanded)
                  and R.sha(expanded[a:b]) == row['sha256'], 'Current allocation preimage differs')
    # This checks other named owners as well as actual native consumers.
    other_claims = []
    for other in policies:
        if other is policy:
            continue
        other_lo, other_hi = other['tile32_id_range']
        other_claims.append(dict(id=other['id'], space='tile32_id', base=other_lo, size=other_hi - other_lo))
        other_claims.extend(dict(id=other['id'], space='pc_rom', base=row['pc'][0],
                                 size=row['pc'][1] - row['pc'][0]) for row in other['preimages'])
    collision_ledger = dict(ledger, claims=[*ledger.get('claims', []), *other_claims])
    V.require_no_named_conflicts(collision_ledger, tile32_range=(lo, hi), stream_ranges=policy['stream_ranges'])
    R.require(Path(request['live']['enforcement_receipt']).is_file(),
              'CURRENT_SAVE_PRODUCER_PROOF_REQUIRED: selected producer must enforce this snapshot and writer order')
    proof_binding = Q.bound(request['live']['enforcement_receipt'])
    proof = _json(Q.read_bound(proof_binding))
    _keys(proof, {'kind', 'transfer_id', 'generation', 'operation_id', 'save_context',
                  'source_rom_sha256', 'policy_sha256', 'producer', 'source_bindings',
                  'verification', 'writer_order'}, 'current producer proof')
    producer = request['live']['producer_identity']
    R.require(proof['kind'] == PROOF_KIND and proof['transfer_id'] == request['transfer_id']
              and proof['generation'] == request['live']['generation']
              and proof['operation_id'] == request['live']['operation_id']
              and proof['save_context'] == request['live']['save_context']
              and proof['source_rom_sha256'] == R.sha(source) and proof['policy_sha256'] == T.digest(policy)
              and proof['producer'] == request['live']['producer']
              and proof['source_bindings'] == producer['source_bindings']
              and proof['writer_order'] == ['native_save', 'immutable_snapshot', 'compile_candidate', 'no_native_serializer'],
              'Current producer proof is stale or does not enforce this transfer/order')
    check = proof['verification']
    _keys(check, {'binary', 'log', 'command', 'tests', 'exit_code'}, 'current producer verification')
    R.require(check['binary'] == producer['verifier'] and type(check['command']) is str and check['command']
              and type(check['tests']) is list and check['tests'] and type(check['exit_code']) is int
              and check['exit_code'] == 0, 'Current producer verification is incomplete or failed')
    for row in [*proof['source_bindings'], check['binary'], check['log']]:
        Q.read_bound(row)
    missing = C._missing(expanded, document, V.FULL_MAPS)
    spare = policy['spare_tile32_ids']
    R.require(type(spare) is list and len(spare) == len(set(spare))
              and all(type(i) is int and lo <= i < hi for i in spare), 'Invalid current spare IDs')
    ids = [i for i in range(lo, hi) if i not in spare]
    R.require(len(missing) <= len(ids), f'Current transfer needs {len(missing)} definitions; policy has {len(ids)} IDs')
    assignments = tuple(zip(ids, missing))
    allocation = Allocation(tuple(tuple(span) for span in policy['stream_ranges']), tuple(ids),
                            tile32_assignments=assignments)
    directory = A.render_dependency_plan(V.FULL_MAPS)[0]
    plan, payload = V.compile_native_plan(source, document, allocation, directory, spare_tile32_ids=spare,
                                        current_source_profile=current_source_profile)
    final_request, _, _ = verify_transfer(request_path, project, base_rom)
    R.require(final_request == request, 'Current-save transfer request replaced during compilation')
    Q.read_bound(request_binding)
    Q.read_bound(ledger_binding)
    Q.read_bound(proof_binding)
    plan.update(transfer_id=request['transfer_id'], generation=request['live']['generation'],
        operation_id=request['live']['operation_id'], save_context=request['live']['save_context'],
        current_source_allocation_verified=current_source_profile is None,
        producer_enforcement_verified=current_source_profile is None,
        policy_sha256=T.digest(policy), enforcement_receipt=proof_binding,
        target=request['target'], retirement='next_native_save',
        writer_order=proof['writer_order'])
    return plan, payload


def ordinary_plan(project, base_rom, request_path, *, ledger_path=None):
    plan, payload = plan_transfer(request_path, project, base_rom, ledger_path=ledger_path)
    raise ValueError('CURRENT_SAVE_RUNTIME_EMISSION_UNADMITTED: verified current-save transfer '
                     + plan['transfer_id'] + '; full32 reader/emission and appearance/actor/palette '
                     'admission are required before Build. No A1 fallback or ROM write occurred.')
