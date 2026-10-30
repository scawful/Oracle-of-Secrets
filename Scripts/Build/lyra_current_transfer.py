"""Native-save-first build transfers. No editable ROM or candidate is written.

Yaze owns successful-save generations and producer enforcement. This adapter
captures their identities, verifies immutable inputs, and calls the existing
native compiler only with a separately reviewed current-source allocation.
"""
from __future__ import annotations

import configparser
import contextlib
import contextvars
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
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
NATIVE_POLICY_KIND = 'lyra.current_save_transfer_policy.v2'
NATIVE_EXECUTION_KIND = 'yaze.lyra_verify_project_execution.v1'
COMPILE_ORDER = ['native_save', 'immutable_snapshot', 'compile_candidate', 'no_native_serializer']
REVIEW_KIND = 'lyra.current_save_reservation_review.v1'
PREVIEW_POLICY_KIND = 'lyra.private_checkpoint_preview_policy.v1'
PREVIEW_SCOPE = 'seeded_checkpoint_preview'
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


def _live(project, *, producer_identity=None):
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
    if producer_identity is None:
        producer_path = _reference(project, config, 'native_save_producer_file')
    else:
        producer_path = Path(producer_identity).resolve(strict=True)
        R.require(not producer_path.is_relative_to(project.parent.resolve()),
                  'Explicit producer identity must remain outside the saved project')
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
        R.require(role != 'dependency.planning',
                  'NATIVE_SAVE_RECEIPT_BINDS_LIVE_PLANNING: Planning is a live project reference, '
                  'not a build input; complete a new native Save with the selected yaze producer')
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
    workspace_controls = (project.parent / '.workspace/yaze/native-saves').resolve()
    R.require((not context_path.is_relative_to(project.parent.resolve())
               or context_path.parent == workspace_controls)
              and context_path.parent.name == 'native-saves',
              'Current native Save context must use native-saves outside the project '
              'or its managed .workspace/yaze controls')
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
    result = dict(project=str(project), inputs=inputs, producer=producer_binding,
        producer_identity=producer, save_receipt=receipt_binding,
        generation=receipt['generation'], operation_id=receipt['operation_id'],
        save_context=context_binding,
        enforcement_receipt=str(proof_path))
    if producer_identity is not None:
        result['producer_identity_override'] = producer_binding
    return result


def _recheck(live):
    try:
        override = live.get('producer_identity_override')
        if override is not None:
            Q.read_bound(override)
        current = _live(live['project'],
                        producer_identity=None if override is None else override['path'])
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


def prepare_transfer(project, z3ed, output, candidate, *, policy_id=None, producer_identity=None):
    """Capture a new immutable input; never advance Yaze's save generation."""
    project = Path(os.path.abspath(project))
    z3ed = Path(z3ed).resolve(strict=True)
    output = Path(os.path.abspath(output))
    candidate = Path(os.path.abspath(candidate))
    R.require(not output.exists() and not candidate.exists(), 'Transfer input/output paths must be new')
    R.require(not any(path.is_symlink() for path in (output, *output.parents, candidate, *candidate.parents)),
              'Current-save transfer paths use a symlink')
    R.require(not candidate.is_relative_to(output) and not output.is_relative_to(candidate),
              'Candidate must be separate from immutable transfer input')
    live = _live(project, producer_identity=producer_identity)
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
    # Yaze verifies its native Save and authored bytes, not Oracle's future
    # compiler. Record the actual successful selected-verifier invocation in
    # the immutable capture. Oracle owns the subsequent compile/readback order.
    execution = dict(kind=NATIVE_EXECUTION_KIND, binary=live['producer_identity']['verifier'],
        source_bindings=live['producer_identity']['source_bindings'],
        generation=live['generation'], operation_id=live['operation_id'],
        save_receipt=live['save_receipt'], save_context=live['save_context'],
        source_rom_sha256=R.sha(raw['rom']), exit_code=0,
        command=[str(Path(z3ed)), 'lyra-verify-project', f'--project-context={project}',
                 f'--rom={live["inputs"]["rom"]["path"]}', '--format=json'],
        observation=dict(path=str(output / 'observation.json'), sha256=R.sha(files['observation.json'])))
    files['native-verification.json'] = P.encoded(execution)
    request = dict(kind=KIND, live=live, snapshot_root=str(output), inputs=snapshots,
        observation=dict(path=str(output / 'observation.json'), sha256=R.sha(files['observation.json'])),
        save_snapshot=dict(path=str(output / 'native-save.json'), sha256=R.sha(files['native-save.json'])),
        producer_snapshot=dict(path=str(output / 'producer.json'), sha256=R.sha(files['producer.json'])),
        context_snapshot=dict(path=str(output / 'context.json'), sha256=R.sha(files['context.json'])),
        native_verification=dict(path=str(output / 'native-verification.json'),
                                 sha256=R.sha(files['native-verification.json'])),
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


_CANDIDATE_INSPECTION = contextvars.ContextVar('lyra_candidate_inspection',default=None)


@contextlib.contextmanager
def candidate_inspection(rom):
    """Internal read-only scope; an existing candidate must retain exact bytes."""
    binding=Q.bound(rom)
    token=_CANDIDATE_INSPECTION.set(binding)
    try:
        yield binding
        Q.read_bound(binding)
    finally:
        _CANDIDATE_INSPECTION.reset(token)


def _new_or_inspected_target(path):
    if not Path(path).exists():
        return True
    binding=_CANDIDATE_INSPECTION.get()
    return binding is not None and binding == Q.bound(path)


def verify_transfer(request_path, project, base_rom):
    """Reconstruct readers and compare the live generation before/after use."""
    binding = Q.bound(request_path)
    request = _json(Q.read_bound(binding))
    _keys(request, {'kind', 'live', 'snapshot_root', 'inputs', 'observation', 'save_snapshot',
                   'producer_snapshot', 'context_snapshot', 'census', 'allocation_policy_id', 'target', 'transfer_id'}
          | ({'native_verification'} if 'native_verification' in request else set()), 'current transfer request')
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
    if 'native_verification' in request:
        rows.append(request['native_verification'])
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
              and _new_or_inspected_target(target['path'])
              and not any(p.is_symlink() for p in (Path(target['path']), *Path(target['path']).parents))
              and Path(target['path']).is_absolute()
              and Path(os.path.abspath(target['path'])) == Path(target['path'])
              and not Path(target['path']).is_relative_to(root)
              and target['path'] not in {row['path'] for row in request['live']['inputs'].values()},
              'Current transfer requires a new separate4MiB compiled candidate')
    document = C._document(raw['terrain'], Q.read_bound(request['observation']), raw['rom'])
    if 'native_verification' in request:
        native_execution(request)
    R.require(request['census'] == _census(raw['rom'], document), 'Current native reader census differs')
    _recheck(request['live'])
    Q.read_bound(binding)
    return request, raw['rom'], document


def native_execution(request):
    """Validate selected-verifier evidence captured before compilation."""
    R.require('native_verification' in request, 'CURRENT_NATIVE_VERIFIER_EXECUTION_REQUIRED')
    value = _json(Q.read_bound(request['native_verification']))
    _keys(value, {'kind', 'binary', 'source_bindings', 'generation', 'operation_id',
                  'save_receipt', 'save_context', 'source_rom_sha256', 'exit_code',
                  'command', 'observation'}, 'native verifier execution')
    live = request['live']; producer = live['producer_identity']
    expected_command = [producer['verifier']['path'], 'lyra-verify-project',
        f'--project-context={live["project"]}', f'--rom={live["inputs"]["rom"]["path"]}', '--format=json']
    R.require(value['kind'] == NATIVE_EXECUTION_KIND and value['binary'] == producer['verifier']
              and value['source_bindings'] == producer['source_bindings']
              and type(value['generation']) is int and value['generation'] == live['generation']
              and value['operation_id'] == live['operation_id']
              and value['save_receipt'] == live['save_receipt'] and value['save_context'] == live['save_context']
              and value['source_rom_sha256'] == request['inputs']['rom']['sha256']
              and type(value['exit_code']) is int and value['exit_code'] == 0
              and value['command'] == expected_command and value['observation'] == request['observation'],
              'CURRENT_NATIVE_VERIFIER_EXECUTION_MISMATCH')
    for row in [value['binary'], *value['source_bindings'], value['save_receipt'],
                value['save_context'], value['observation']]:
        Q.read_bound(row)
    return value


def _git(root, *args):
    try:
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as error:
        raise ValueError('Selected Oracle source is not available at the exact revision') from error


def _git_source_blobs(root, engine_head, relatives):
    """Read exact committed blobs in one process, preserving binary framing."""
    relatives = tuple(relatives)
    R.require(type(engine_head) is str and re.fullmatch('[0-9a-f]{40}', engine_head) is not None
              and len(set(relatives)) == len(relatives)
              and all(type(name) is str and name and not Path(name).is_absolute()
                      and '..' not in Path(name).parts
                      and not any(char in name for char in '\r\n\0') for name in relatives),
              'Selected Oracle source blob names are invalid')
    query = ''.join(engine_head + ':' + name + '\n' for name in relatives).encode('utf-8')
    try:
        result = subprocess.run(['git', '-C', str(root), 'cat-file', '--batch'],
                                input=query, capture_output=True, check=True)
    except subprocess.CalledProcessError as error:
        raise ValueError('Selected Oracle source is not available at the exact revision') from error
    raw, offset, blobs = result.stdout, 0, {}
    for name in relatives:
        end = raw.find(b'\n', offset)
        header = re.fullmatch(rb'[0-9a-f]{40} blob ([0-9]+)', raw[offset:end]) if end >= 0 else None
        R.require(header is not None,
                  'Selected Oracle source is not available at the exact revision: ' + name)
        size = int(header[1]); start = end + 1; offset = start + size
        R.require(offset < len(raw) and raw[offset:offset+1] == b'\n',
                  'Selected Oracle source blob response is truncated: ' + name)
        blobs[name] = raw[start:offset]; offset += 1
    R.require(offset == len(raw), 'Selected Oracle source blob response has trailing data')
    return blobs


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
        # Source provenance always binds the normal root plus the separate
        # current source pin set, not generated selected outputs or recursion.
        prior_context = os.environ.get('OOS_LYRA_BUILD_CONTEXT')
        try:
            os.environ['OOS_LYRA_BUILD_CONTEXT'] = '0'
            defines = manifest._load_global_defines(root)
            sources = set(manifest.collect_reachable_asm_sources(root, defines=defines))
        finally:
            if prior_context is None:
                os.environ.pop('OOS_LYRA_BUILD_CONTEXT',None)
            else:
                os.environ['OOS_LYRA_BUILD_CONTEXT'] = prior_context
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
    committed = _git_source_blobs(root, engine_head,
        [path.relative_to(root).as_posix() for path in sorted(paths)])
    bindings = []
    for path in sorted(paths):
        R.require(path.is_file() and path.resolve().is_relative_to(root)
                  and not any(p.is_symlink() for p in (path, *path.parents)),
                  'Selected Oracle source input escapes its checkout or uses a symlink')
        relative = path.relative_to(root).as_posix()
        binding = Q.bound(path)
        R.require(Q.read_bound(binding) == committed[relative],
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
    R.require(type(document.gameplay_areas) is tuple,
              'CURRENT_GAMEPLAY_AREAS_MODEL_INVALID: parsed area tuple required')
    value = {key: getattr(document, key) for key in
             ('profile', 'maps', 'properties', 'authoring', 'edge_connections', 'flight_points')}
    # Legacy documents retain their exact identity; authored layout is never
    # allowed to change under a cached source profile.
    if document.gameplay_areas:
        value['gameplay_areas'] = document.gameplay_areas
    return T.digest(value)


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
    _keys(origins, {'tables', 'code', 'descriptor', 'bg_palette', 'graphics'}
          | ({'actors'} if 'actors' in origins else set()), 'current source origins')
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
                                         spare_tile32_ids=(), native_copy_maps=(), private_pilot=None):
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
        selected=V.FULL_MAPS
        if private_pilot is not None:
            import lyra_native_loaders as native
            native.private_pilot_document(document,private_pilot)
            selected=private_pilot['allowed_tail_maps']
        assignments = tuple(zip(ids, C._missing(A.expanded_rom(source), document, selected)))
        R.require(isinstance(allocation, Allocation)
                  and allocation.stream_ranges == (tuple(review['preimages'][-1]['pc']),)
                  and allocation.owned_tile32_ids == ids
                  and allocation.tile32_assignments == assignments
                  and tuple(spare_tile32_ids) == spare and not native_copy_maps,
                  'CURRENT_SOURCE_RESERVATION_MISMATCH: allocation, assignments or spares differ from reviewed generation')
    return profile


def plan_transfer(request_path, project, base_rom, *, ledger_path=None, current_source_profile=None, private_pilot=None):
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
                   'stream_ranges', 'preimages', 'spare_tile32_ids'}
          | ({'current_runtime'} if 'current_runtime' in policy else set())
          | ({'enforcement'} if policy.get('kind') == NATIVE_POLICY_KIND else set()), 'current allocation policy')
    R.require(policy['kind'] in (POLICY_KIND, NATIVE_POLICY_KIND) and policy['scope'] == 'disposable_build_only'
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
    if policy['kind'] == NATIVE_POLICY_KIND:
        _keys(policy['enforcement'], {'owner', 'required_order'}, 'compile-order ownership')
        R.require(policy['enforcement'] == dict(owner='oracle.current_builder', required_order=COMPILE_ORDER),
                  'CURRENT_COMPILE_ORDER_OWNER_MISMATCH')
        native_execution(request)
        proof_binding = request['native_verification']
        # This is a required compiler sequence, not a producer-issued claim
        # that a future assembly has already happened. Final readback owns it.
        proof = dict(writer_order=list(COMPILE_ORDER))
    else:
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
    selected=V.FULL_MAPS
    layout_document=document
    if private_pilot is not None:
        import lyra_native_loaders as native
        R.require(current_source_profile is not None,'PRIVATE_PILOT_SOURCE_UNBOUND')
        layout_document=native.private_pilot_document(document,private_pilot)
        selected=private_pilot['allowed_tail_maps']
    missing = C._missing(expanded, document, selected)
    spare = policy['spare_tile32_ids']
    R.require(type(spare) is list and len(spare) == len(set(spare))
              and all(type(i) is int and lo <= i < hi for i in spare), 'Invalid current spare IDs')
    ids = [i for i in range(lo, hi) if i not in spare]
    R.require(len(missing) <= len(ids), f'Current transfer needs {len(missing)} definitions; policy has {len(ids)} IDs')
    assignments = tuple(zip(ids, missing))
    allocation = Allocation(tuple(tuple(span) for span in policy['stream_ranges']), tuple(ids),
                            tile32_assignments=assignments)
    directory = A.render_dependency_plan(selected, document=layout_document)[0]
    plan, payload = V.compile_native_plan(source, document, allocation, directory, spare_tile32_ids=spare,
                                        current_source_profile=current_source_profile,private_pilot=private_pilot)
    final_request, _, _ = verify_transfer(request_path, project, base_rom)
    R.require(final_request == request, 'Current-save transfer request replaced during compilation')
    Q.read_bound(request_binding)
    Q.read_bound(ledger_binding)
    Q.read_bound(proof_binding)
    plan.update(transfer_id=request['transfer_id'], generation=request['live']['generation'],
        operation_id=request['live']['operation_id'], save_context=request['live']['save_context'],
        current_source_allocation_verified=True,
        producer_enforcement_verified=True,
        policy_sha256=T.digest(policy), enforcement_receipt=proof_binding,
        target=request['target'], retirement='next_native_save',
        writer_order=proof['writer_order'],
        enforcement_owner=('oracle.current_builder' if policy['kind'] == NATIVE_POLICY_KIND else 'legacy_producer'),
        producer_enforcement_scope=('native_save_only' if policy['kind'] == NATIVE_POLICY_KIND else 'legacy_protocol'),
        oracle_compile_order_verified=False)
    return plan, payload


def private_pilot_runtime(runtime, source, document):
    """Consume an explicit private selection and an existing native entry row.

    This source-owned policy input is separate from saved authoring. It grants
    no storage, producer authority or ingress code. An empty endpoint cannot
    silently turn a two-page terrain plan into a playable candidate.
    """
    binding=runtime.get('private_pilot')
    if binding is None: return None,None
    import lyra_native_loaders as native
    import lyra_native_state as state
    value=_json(Q.read_bound(binding))
    _keys(value,{'kind','selected_areas','entry_map_id','entry_room_id','entry_exit_row'},'private pilot runtime selection')
    R.require(value['kind']=='lyra.private_pilot_runtime_selection.v1','PRIVATE_PILOT_SELECTION_UNBOUND')
    pilot=native.plan_private_pilot_boundaries(document,value['selected_areas'])
    R.require(type(value['entry_map_id']) is int and value['entry_map_id'] in pilot['allowed_tail_maps']
              and type(value['entry_room_id']) is int and type(value['entry_exit_row']) is int,
              'PRIVATE_PILOT_ENDPOINT_UNBOUND: explicit selected native room/exit required')
    endpoint=state.room_return(source,value['entry_room_id'],value['entry_map_id'],value['entry_exit_row'])
    R.require(endpoint['requested_row_consumed'],
              'PRIVATE_PILOT_ENDPOINT_UNBOUND: source must actually dispatch the selected native exit into A0/A1')
    return pilot,binding


def native_checkpoint_boundaries(document):
    """The explicit preview mode supplies only the human-selected private pair."""
    import lyra_native_loaders as native
    return native.plan_private_pilot_boundaries(document,
        [dict(parent_map_id=a,size='small',maps=[a]) for a in (0xA0,0xA1)])


def require_preview_consumers(expected,guard,source):
    """Validate reviewed distinct snapshot metadata; post-Asar verifies actual bytes."""
    import lyra_native_loaders as native
    _keys(expected,{'kind','regions','source_calls','fixed_hooks','private_pilot_boundary','preview_guards',
        'current_core_inspected','broad_six_role_qualification','ordinary_build_ready','runtime_admission',
        'production_admission','native_gameplay_verified','save_reopen_verified'},'reviewed checkpoint preview consumers')
    _keys(guard,{'kind','scope','source_rom_sha256','guard_source_sha256','code_snes','code_sha256',
        'overlay_host_snes','overlay_host_sha256','home_snes','home_sha256'},'reviewed checkpoint preview guard binding')
    R.require(guard['kind']=='lyra.private_checkpoint_preview_binding.v1' and guard['scope']=='seeded_A0_A1_only'
              and guard['source_rom_sha256']==R.sha(source)
              and guard['guard_source_sha256']==R.sha((P.ROOT/'Overworld/lyra_private_pilot.asm').read_bytes()),
              'PRIVATE_PREVIEW_SOURCE_STALE')
    proof=expected['preview_guards']
    R.require(type(proof) is dict and expected['kind']==native.PREVIEW_CONSUMER_KIND
              and expected['current_core_inspected'] is True
              and all(expected[k] is False for k in ('broad_six_role_qualification','ordinary_build_ready',
                  'runtime_admission','production_admission','native_gameplay_verified','save_reopen_verified'))
              and all(type(expected[k]) is list and expected[k] for k in ('regions','source_calls','fixed_hooks'))
              and proof.get('kind')=='lyra.seeded_checkpoint_preview_guard_inspection.v1'
              and proof.get('mode')==PREVIEW_SCOPE and proof.get('scope')=='seeded_A0_A1_only'
              and proof.get('guards_verified') is True and proof.get('transport_native_only') is True
              and all(proof.get(k) is False for k in ('allocation_granted','producer_enforcement_verified',
                  'ordinary_build_ready','runtime_admission','production_admission','native_gameplay_verified',
                  'save_reopen_verified'))
              and proof.get('code_snes')==guard['code_snes'] and proof.get('home_snes')==guard['home_snes']
              and type(proof.get('credits_held')) is list and len(proof['credits_held'])==13
              and proof.get('source_rom_sha256')==R.sha(source)
              and proof.get('reviewed_binding_sha256')==R.sha(json.dumps(guard,sort_keys=True,separators=(',',':')).encode())
              and type(proof.get('held_routes')) is list and bool(proof['held_routes']),
              'PRIVATE_PREVIEW_COMPILED_BINDING_REQUIRED')
    return expected


def checkpoint_symbols(symbols):
    """Use the maintained allocation parser through an ephemeral symbol file."""
    from allocation_contracts import read_symbols
    raw=symbols if isinstance(symbols,bytes) else symbols.encode()
    with tempfile.NamedTemporaryFile(suffix='.sym') as handle:
        handle.write(raw);handle.flush()
        return read_symbols(handle.name)


def ordinary_plan(project, base_rom, request_path, *, ledger_path=None):
    """Select only a source-owned reviewed runtime policy; no A1 fallback."""
    request, source, document = verify_transfer(request_path, project, base_rom)
    ledger_path = Path(R.LEDGER).resolve(strict=True) if ledger_path is None else Path(ledger_path).resolve(strict=True)
    R.require(ledger_path == Path(R.LEDGER).resolve(strict=True), 'CURRENT_SAVE_POLICY_AUTHORITY_MISMATCH')
    ledger_binding = Q.bound(ledger_path)
    ledger = _json(Q.read_bound(ledger_binding))
    policies = [p for p in ledger.get('current_save_transfer_policies', [])
                if p.get('id') == request['allocation_policy_id']]
    R.require(len(policies) == 1, 'CURRENT_SAVE_ALLOCATION_UNGRANTED')
    runtime = policies[0].get('current_runtime')
    R.require(type(runtime) is dict, 'CURRENT_SAVE_RUNTIME_EMISSION_UNADMITTED: no reviewed current runtime policy')
    preview=runtime.get('kind') == PREVIEW_POLICY_KIND
    _keys(runtime, {'kind','scope','runtime_admission','review_file','tail_recipe',
                    'graphics_source','graphics_assets','compiled_consumers','event_state','origin_preimages'}
          | ({'bg128'} if 'bg128' in runtime else set())
          | ({'joint_art'} if 'joint_art' in runtime else set())
          | ({'private_checkpoint','guard_binding'} if preview else
             ({'private_pilot'} if 'private_pilot' in runtime else set())), 'current runtime policy')
    R.require(runtime['kind'] == (PREVIEW_POLICY_KIND if preview else 'lyra.current_runtime_policy.v1')
              and runtime['scope'] == (PREVIEW_SCOPE if preview else 'disposable_build_only')
              and runtime['runtime_admission'] is True,
              'CURRENT_SAVE_RUNTIME_EMISSION_UNADMITTED: runtime selection remains held')
    # Review is reconstructed from facts, not authority. A path instead of a
    # digest avoids policy -> review -> ledger -> policy hash self-reference.
    review_path = Path(runtime['review_file']).resolve(strict=True)
    review_binding = Q.bound(review_path)
    review = _json(Q.read_bound(review_binding))
    R.require(type(review) is dict and review.get('kind') == REVIEW_KIND, 'CURRENT_RUNTIME_REVIEW_REQUIRED')
    profile = current_native_source_profile(review, project, base_rom)
    checkpoint_context=None;checkpoint_registry=None;guard_binding=None
    if preview:
        import checkpoint_registry as checkpoints
        R.require(hasattr(checkpoints,'bind_private_preview'),'PRIVATE_PREVIEW_BINDER_UNAVAILABLE: source helper dependency required')
        selection=runtime['private_checkpoint']
        _keys(selection,{'plan','landing'},'private checkpoint selection')
        checkpoint_registry,checkpoint_context=checkpoints.bind_private_preview(
            project,base_rom,request_path,profile,selection['plan'],selection['landing'])
        pilot=native_checkpoint_boundaries(document)
        pilot_binding=None
        guard_binding=_json(Q.read_bound(runtime['guard_binding']))
    else:
        pilot,pilot_binding=private_pilot_runtime(runtime,source,document)
    plan, payload = plan_transfer(request_path, project, base_rom, ledger_path=ledger_path,
                                  current_source_profile=profile,private_pilot=pilot)
    import lyra_native_loaders as native
    native_full_paths=None if pilot is None else native.private_pilot_native_full_paths(source)
    R.require(preview or native_full_paths is None or native_full_paths['complete'],
              'PRIVATE_PILOT_NATIVE_FULL_UNBOUND: unchanged credits full caller requires its own cancellation/source binding')
    origin_spans = [row['pc'] for row in profile['origins'].values()]
    R.require(type(runtime['origin_preimages']) is list
              and sorted(row['pc'] for row in runtime['origin_preimages']) == sorted(origin_spans),
              'CURRENT_RUNTIME_ORIGIN_PREIMAGES_REQUIRED: every selected interval must be bound')
    expanded_source = A.expanded_rom(source)
    for row in runtime['origin_preimages']:
        R.require(R.sha(expanded_source[slice(*row['pc'])]) == row['sha256'],
                  'CURRENT_RUNTIME_ORIGIN_PREIMAGE_MISMATCH')
    write_spans = [row['pc'] for row in plan['writes']]
    R.require(all(b<=c or a>=d for a,b in origin_spans for c,d in write_spans),
              'CURRENT_RUNTIME_ORIGIN_OVERLAP: runtime and terrain allocations overlap')
    other_origins=[dict(id=other['id'],space='pc_rom',base=row['pc'][0],size=row['pc'][1]-row['pc'][0])
                   for other in ledger.get('current_save_transfer_policies',[]) if other is not policies[0]
                   for row in other.get('current_runtime',{}).get('origin_preimages',[])]
    V.require_no_named_conflicts(dict(ledger,claims=[*ledger.get('claims',[]),*other_origins]),
        tile32_range=policies[0]['tile32_id_range'],stream_ranges=origin_spans+policies[0]['stream_ranges'])
    rows = _json(Q.read_bound(runtime['tail_recipe']))
    selected=V.FULL_MAPS if pilot is None else pilot['allowed_tail_maps']
    layout_document=document if pilot is None else native.private_pilot_document(document,pilot)
    R.require(type(rows) is dict and set(rows) == {f'{a:02X}' for a in selected},
              'PRIVATE_PILOT_RECIPE_UNSELECTED: recipe must name only A0/A1' if pilot is not None else
              'CURRENT_RUNTIME_RECIPE_INCOMPLETE: all32 explicit native rows required')
    rows = {int(key,16):dict(value) for key,value in rows.items()}
    areas = A.gameplay_area_plan(layout_document)
    R.require(pilot is not None or areas['complete'], 'CURRENT_GAMEPLAY_AREAS_UNASSIGNED: selected build needs all32 explicit pages')
    for area, values in native.current_property_rows(document, source=source).items():
        if area in rows: rows[area].update(values)
    for area, values in A.gameplay_transition_rows(source,layout_document,private_pilot=pilot is not None).items():
        rows[area].update(values)
    actors = native.plan_current_actor_storage(source,document,current_source_profile=profile,
        data_snes=profile['origins']['actors']['snes'][0],
        capacity=profile['origins']['actors']['pc'][1]-profile['origins']['actors']['pc'][0],
        preimage=A.expanded_rom(source)[slice(*profile['origins']['actors']['pc'])],private_pilot=pilot)
    for area, values in actors['phase_rows'].items():
        rows[area].update(values)
    for stream in plan['streams']:
        rows[stream['map_id']]['map32_'+('high','low')[stream['plane']]] = A.snes(stream['pc'][0])
    tables = native.plan_current_tables(source,rows,
        origins=dict(table_base=profile['origins']['tables']['snes'][0],
            code_base=profile['origins']['code']['snes'][0],code_end=profile['origins']['code']['snes'][1],
            descriptor_base=profile['origins']['descriptor']['snes'][0]),
        policy=dict(source_rom_sha256=R.sha(source),source_profile_sha256=T.digest(profile),
                    allocation_granted=False,publication_authorized=False),private_pilot=pilot)
    graphics = Q.read_bound(runtime['graphics_source']).decode('utf-8')
    R.require(type(runtime['graphics_assets']) is list,'CURRENT_GRAPHICS_ASSETS_UNBOUND')
    assets={row['path']:row for row in runtime['graphics_assets']}
    R.require(len(assets)==len(runtime['graphics_assets']),'Duplicate current graphics asset binding')
    referenced=set()
    for line in graphics.splitlines():
        line=line.split(';',1)[0]
        R.require(not re.search(r'\bincsrc\b',line,re.I),'Current graphics cannot include unbound source')
        if re.search(r'\bincbin\b',line,re.I):
            match=re.fullmatch(r'\s*incbin\s+"([^"!]+)"\s*',line,re.I)
            R.require(match is not None,'Unsupported current graphics binary directive')
            name=Path(match[1]);name=(name if name.is_absolute() else P.ROOT/P.OUTPUT/name).resolve(strict=True)
            R.require(str(name) in assets,'CURRENT_GRAPHICS_ASSETS_UNBOUND: '+str(name))
            Q.read_bound(assets[str(name)]);referenced.add(str(name))
    R.require(referenced==set(assets),'Unused or missing current graphics asset binding')
    contract = _json(Q.read_bound(profile['contract']))
    report = dict(current_mode=True,parent_count=192,source_contract_sha256=R.sha(P.encoded(contract)),
        generated_sha256=R.sha(graphics.encode()),graphics_origin_snes=profile['origins']['graphics']['snes'])
    bg_plan,bg_binding = current_bg128(source,document,profile,ledger,runtime.get('bg128'),private_pilot=pilot)
    files = P.render_current_source_outputs(tables,contract=contract,graphics_source=graphics,
        graphics_report=report,current_source_profile=profile,actor_storage_plan=actors,bg128_plan=bg_plan,private_pilot=pilot)
    endpoint_state = _json(files['prepare.json'])['native_state_contract']
    R.require(not [r for r in document.flight_points if pilot is None or r['map_id'] in selected]
              and all(r['tile_match_verified'] for r in endpoint_state['requested_doors'])
              and all(r['position_match_verified'] for r in endpoint_state['requested_returns']),
              'CURRENT_RUNTIME_ENDPOINT_UNBOUND: native saved endpoints or transport writer required')
    events = current_event_state(runtime['event_state'],ledger)
    constants = files['runtime_constants.asm'].decode().replace('Source review only; current preparation is never selected.',
        'Reviewed disposable-build context; canonical flags are unchanged.')
    constants = constants.replace('!LYRA_CURRENT_ACTORS_ENABLED = 0','!LYRA_CURRENT_ACTORS_ENABLED = 1')
    constants = constants.replace('!LYRA_CURRENT_ACTORS_BOUND = 0','!LYRA_CURRENT_ACTORS_BOUND = 1')
    constants += ('!LYRA_CURRENT_EVENTS_ENABLED = 1\n!LYRA_CURRENT_EVENTS_BOUND = 1\n'
        + f"!LYRA_CURRENT_EVENT_BASE = ${events['flags']:06X}\n"
        + f"!LYRA_CURRENT_EVENT_VERSION = ${events['version']:06X}\n"
        + f"!LYRA_CURRENT_EVENT_MARKER = ${events['marker']:02X}\n")
    if bg_binding is not None:
        constants=constants.replace('!PROJECT_BG128_ENABLED = 0','!PROJECT_BG128_ENABLED = 1')
        constants=constants.replace('!PROJECT_BG128_RESTORE_BOUND = 0','!PROJECT_BG128_RESTORE_BOUND = 1')
        old_end=f"!LYRA_CURRENT_CODE_END = ${profile['origins']['code']['snes'][1]:06X}"
        R.require(constants.count(old_end)==1,'Current native-code end constant differs')
        constants=constants.replace(old_end,f"!LYRA_CURRENT_CODE_END = ${bg_binding['code_snes'][0]:06X}")
        constants+=(f"!PROJECT_BG128_CODE_BASE = ${bg_binding['code_snes'][0]:06X}\n"
                   +f"!PROJECT_BG128_CODE_END = ${bg_binding['code_snes'][1]:06X}\n")
    if pilot is not None:
        constants += ('!LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED = 1\n!LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND = 1\n'
                      '!LYRA_PRIVATE_PILOT_INGRESS_ENABLED = 1\n')
    if preview:
        emitted=checkpoints.emit_runtime_asm(checkpoint_registry)
        files['checkpoint_registry_constants.asm']=emitted['constants'].encode()
        files['checkpoint_registry_tables.asm']=emitted['tables'].encode()
        constants+='!LYRA_PRIVATE_CHECKPOINT_ENABLED = 1\n'
    joint_art = None
    if 'joint_art' in runtime:
        import lyra_joint_art
        R.require(preview, 'JOINT_ART_REQUIRES_PRIVATE_PREVIEW_POLICY')
        lyra_joint_art.require_source_profile(profile)
        R.require(profile['origins']['graphics']['snes'][1] <= lyra_joint_art.AREA_CODE[0],
                  'JOINT_ART_GRAPHICS_SUFFIX_OVERLAP')
        joint_art, extra_constants, extra_data, extra_binary = lyra_joint_art.prepare(
            runtime['joint_art'], request, source, occupied=origin_spans + write_spans)
        constants += extra_constants
        files['runtime_data.asm'] += extra_data
        files['binaries/joint-art.bin'] = extra_binary
    files['runtime_constants.asm'] = constants.encode()
    data = files['runtime_data.asm'].decode()+'pushpc\n'
    binary = bytearray()
    for row in plan['writes']:
        raw = bytes.fromhex(row['payload_hex'])
        data += f"org ${A.snes(row['pc'][0]):06X}\nincbin \"binaries/payload.bin\":${len(binary):X}..${len(binary)+len(raw):X}\n"
        binary.extend(raw)
    R.require(bytes(binary) and payload, 'Current runtime has no terrain payload')
    files['runtime_data.asm'] = (data+'pullpc\n').encode()
    files['binaries/payload.bin'] = bytes(binary)
    source_prepare = _json(files.pop('prepare.json'))
    expected = _json(Q.read_bound(runtime['compiled_consumers']))
    if preview:
        require_preview_consumers(expected,guard_binding,source)
    else:
        _keys(expected,{'kind','regions','source_calls','fixed_hooks'}
              | ({'private_pilot_boundary','private_pilot_ingress'} if pilot is not None else set()),
              'reviewed current compiled consumers')
        if pilot is not None:
            native.require_private_pilot_ingress(expected)
        R.require(expected['kind'] == 'lyra.current_compiled_consumers.v1'
                  and all(type(expected[k]) is list and expected[k] for k in ('regions','source_calls','fixed_hooks')),
                  'CURRENT_COMPILED_BINDING_REQUIRED')
    bindings = [ledger_binding,review_binding,profile['contract'],runtime['tail_recipe'],
                runtime['graphics_source'],*runtime['graphics_assets'],runtime['compiled_consumers'],Q.bound(request_path),
                Q.bound(base_rom),Q.bound(project),plan['enforcement_receipt'],
                *request['inputs'].values(),*profile['selected_source']['bindings'],
                *profile['review']['adapter_bindings']]
    if pilot_binding is not None: bindings.append(pilot_binding)
    if joint_art is not None:
        bindings += [*joint_art['inputs'], Q.bound(Path(lyra_joint_art.__file__))]
    if preview:
        bindings += [runtime['private_checkpoint']['plan'],runtime['private_checkpoint']['landing'],
                     runtime['guard_binding'],*checkpoint_context['inputs']]
    unique = {}
    for row in bindings:
        R.require(row['path'] not in unique or unique[row['path']] == row,
                  'Current prepared inputs have conflicting bindings')
        unique[row['path']] = row
    bindings = sorted(unique.values(),key=lambda row:row['path'])
    prepared = dict(source_prepare,kind='lyra.current_build_prepare.v1',selected=True,
        project=str(Path(project).resolve()),base_rom=str(Path(base_rom).resolve()),request=str(Path(request_path).resolve()),
        ledger=str(ledger_path),saved_rom_sha256=R.sha(source),current_ledger_sha256=ledger_binding['sha256'],
        allocation_granted=True,producer_enforcement_verified=True,runtime_admission=True,
        ordinary_build_ready=not preview,inputs=bindings,current_source_profile=profile,
        private_pilot=pilot,tables=tables,terrain_plan=plan,event_state=events,compiled_consumers=runtime['compiled_consumers'],
        bg128_binding=bg_binding,bg128_plan=(None if bg_plan is None else
            dict((key,value) for key,value in dict(bg_plan,payload_hex=bg_plan['payload'].hex()).items() if key!='payload')),
        generated_files={name:R.sha(raw) for name,raw in files.items()},
        save_exit_policy='unchanged_held',native_gameplay_verified=False,save_reopen_verified=False)
    if joint_art is not None:
        prepared['joint_art'] = joint_art
    if preview:
        prepared.update(runtime_scope=PREVIEW_SCOPE,production_admission=False,
            checkpoint_preview=dict(plan_binding=runtime['private_checkpoint']['plan'],
                                    landing_binding=runtime['private_checkpoint']['landing']),
            guard_binding=runtime['guard_binding'],held_routes=expected['preview_guards']['held_routes'],
            save_exit_policy='seeded_checkpoint_preview_only')
    if native_full_paths is not None: prepared['native_full_paths']=native_full_paths
    for row in bindings:
        Q.read_bound(row)
    verify_current_native_source_profile(profile,source,document)
    verify_transfer(request_path,project,base_rom)
    files['prepare.json'] = P.encoded(prepared)
    return dict(kind='lyra.current_build_prepare.v1',selected=True,current_files=files,inputs=bindings)


def current_bg128(source, document, profile, ledger, binding, *, private_pilot=None):
    """Bind existing BG data/restore code inside the same current allocation."""
    selected = set(V.FULL_MAPS)
    if private_pilot is not None:
        import lyra_native_loaders as native
        native.private_pilot_document(document, private_pilot)
        selected = set(private_pilot['allowed_tail_maps'])
    required=any('background_palette' in row for area,row in enumerate(document.properties,0xA0)
                 if area in selected)
    R.require(not required or binding is not None,
              'CURRENT_RUNTIME_BG128_UNADMITTED: saved palettes require explicit restore/code binding')
    if binding is None:
        return None,None
    _keys(binding,{'restore_bound','code_snes'},'current BG128 binding')
    code=binding['code_snes'];origin=profile['origins']['code']['snes']
    R.require(binding['restore_bound'] is True and type(code) is list and len(code)==2
              and all(type(value) is int for value in code)
              and origin[0]<code[0]<code[1]<=origin[1] and code[0]>>16==(code[1]-1)>>16,
              'CURRENT_BG128_CODE_UNBOUND: restore code must use a distinct suffix of the current code allocation')
    owners=[row for row in ledger.get('claims',[]) if row.get('id')=='ProjectBGPaletteNativeUnderlay']
    R.require(len(owners)==1,'CURRENT_BG128_WRAM_UNBOUND: missing native underlay owner')
    owner=owners[0]
    R.require(owner.get('space')=='wram' and owner.get('base')==0x7ECA00
              and owner.get('size')==514 and owner.get('status')=='shared' and owner.get('aliases')==[]
              and owner.get('condition')==dict(PROJECT_BG128_ENABLED=1),
              'CURRENT_BG128_WRAM_UNBOUND: native reference/effective/state owner differs')
    from allocation_contracts import physical
    for other in ledger.get('claims',[]):
        if other is owner or other.get('base') is None or other.get('space') not in ('wram','save_buffer'):
            continue
        R.require(type(other.get('size')) is int and other['size']>0,'Ambiguous current BG128 physical owner')
        space,lo,hi=physical(other)
        R.require(not (lo<0x7ECC02 and 0x7ECA00<hi),'CURRENT_BG128_WRAM_CONFLICT: '+str(other.get('id')))
    import lyra_project_bg_palette as bg
    from types import SimpleNamespace
    data=profile['origins']['bg_palette'];lo,hi=data['pc']
    plan=bg.plan_bg128([SimpleNamespace(map_id=0xA0+i,properties=row)
        for i,row in enumerate(document.properties)],data_snes=data['snes'][0],capacity=hi-lo,
        preimage=A.expanded_rom(source)[lo:hi])
    return plan,dict(restore_bound=True,code_snes=list(code))


def current_event_state(value, ledger):
    """Consume explicit named save-buffer owners, never infer a free block."""
    _keys(value, {'flags','version','marker'}, 'current event state')
    R.require(all(type(x) is int for x in value.values()) and 0 < value['marker'] <= 255
              and 0x7EF412 <= value['flags'] and value['flags']+32 <= 0x7EF4FE
              and 0x7EF412 <= value['version'] < 0x7EF4FE
              and not value['flags'] <= value['version'] < value['flags']+32,
              'CURRENT_EVENT_STATE_UNBOUND: invalid saved flag/version interval')
    from allocation_contracts import physical
    chosen = []
    for name,key,size in (('LyraCurrentTailFlags','flags',32),('LyraCurrentTailVersion','version',1)):
        matches = [r for r in ledger.get('claims',[]) if r.get('id') == name]
        R.require(len(matches)==1, 'CURRENT_EVENT_STATE_UNBOUND: missing named owner')
        row = matches[0]
        R.require(row.get('space') == 'save_buffer' and row.get('status') == 'shared'
                  and row.get('base') == value[key] and row.get('size') == size
                  and row.get('aliases') == []
                  and row.get('condition') == dict(LYRA_CURRENT_MODE=1,LYRA_CURRENT_EVENTS_ENABLED=1),
                  'CURRENT_EVENT_STATE_UNBOUND: ungranted or inactive named owner')
        chosen.append(row)
    for owner in ledger.get('claims',[]):
        if (owner in chosen or owner.get('base') is None
                or owner.get('space') not in ('wram','save_buffer')):
            continue
        R.require(type(owner['base']) is int and 0x7E0000 <= owner['base'] < 0x800000,
                  'CURRENT_EVENT_STATE_OWNER_CONFLICT: invalid WRAM owner base')
        # A forward extent starting above both candidate fields cannot reach
        # them. A missing size below that boundary remains ambiguous/refused.
        if owner['base'] >= max(value['flags']+32,value['version']+1):
            continue
        R.require(type(owner.get('size')) is int and owner['size'] > 0,
                  'CURRENT_EVENT_STATE_OWNER_CONFLICT: ambiguous owner extent')
        space,lo,hi = physical(owner)
        if space == 'wram':
            R.require(all(not (lo < value[key]+size and value[key] < hi)
                          for key,size in (('flags',32),('version',1))),
                      'CURRENT_EVENT_STATE_OWNER_CONFLICT: '+str(owner.get('id')))
    return dict(value)


def verify_current_context(root, prepared):
    """Reconstruct selected inputs from the canonical policy, not JSON booleans."""
    R.require(Path(root).resolve() == P.ROOT.resolve(), 'Current context uses another source root')
    target=Path(prepared['terrain_plan']['target']['path'])
    if target.exists() and _CANDIDATE_INSPECTION.get() is None:
        with candidate_inspection(target):
            files=verify_current_context(root,prepared)
            # Source graph inspection also runs before Asar. Compiled-byte
            # admission belongs to the separate mandatory post-assembly verifier.
            return files
    files = P.render_outputs(ordinary_plan(prepared['project'],prepared['base_rom'],prepared['request'],
                                          ledger_path=prepared['ledger']))
    R.require(P.encoded(prepared) == files['prepare.json'], 'CURRENT_BUILD_CONTEXT_STALE: preparation differs')
    folder=Path(root)/P.OUTPUT
    R.require(all((folder/name).read_bytes() == raw for name,raw in files.items()),
              'CURRENT_BUILD_CONTEXT_STALE: generated input differs')
    return files


def verify_current_output(prepared, compiled, symbols):
    """Verify exact reviewed code AND derived data; never run or patch a ROM."""
    import lyra_native_loaders as native
    source=Path(prepared['base_rom']).read_bytes()
    R.require(len(compiled)==0x400000 and R.sha(source)==prepared['saved_rom_sha256'],
              'CURRENT_COMPILED_SOURCE_MISMATCH: full4MiB output and original saved source required')
    expected=_json(Q.read_bound(prepared['compiled_consumers']))
    preview=prepared.get('runtime_scope') == PREVIEW_SCOPE
    checkpoint_context=None
    if preview:
        import checkpoint_registry as checkpoints
        R.require(hasattr(checkpoints,'bind_private_preview'),'PRIVATE_PREVIEW_BINDER_UNAVAILABLE: source helper dependency required')
        selection=prepared['checkpoint_preview']
        _keys(selection,{'plan_binding','landing_binding'},'prepared private checkpoint selection')
        _,checkpoint_context=checkpoints.bind_private_preview(
            prepared['project'],prepared['base_rom'],prepared['request'],prepared['current_source_profile'],
            selection['plan_binding'],selection['landing_binding'])
        guard_binding=_json(Q.read_bound(prepared['guard_binding']))
        require_preview_consumers(expected,guard_binding,source)
        observed=native.inspect_current_consumers(compiled,symbols,checkpoint_preview=dict(
            mode=PREVIEW_SCOPE,source=source,reviewed=guard_binding))
        # The maintained checkpoint verifier independently checks complete
        # generated table/cache bytes and actual owning hooks against this live context.
        checkpoint_proof=checkpoints.verify_compiled_checkpoint(P.ROOT,source,compiled,
            checkpoint_symbols(symbols),private_plan=checkpoint_context['plan'],
            verified_bindings=checkpoint_context['bindings'],
            expected_cache=bytes.fromhex(checkpoint_context['cache_hex']))
    else:
        observed=native.inspect_current_consumers(compiled,symbols)
    R.require(observed == expected, 'CURRENT_COMPILED_CONSUMERS_MISMATCH: reviewed active bytes differ')
    if prepared.get('private_pilot') is not None:
        bound=native.private_pilot_native_full_paths(source)
        R.require(prepared.get('native_full_paths')==bound,'PRIVATE_PILOT_NATIVE_FULL_SOURCE_STALE')
        for row in bound['spans']:
            at=A.pc(row['snes'])
            R.require(compiled[at:at+row['bytes']]==bytes.fromhex(row['payload_hex']),
                      'PRIVATE_PILOT_NATIVE_FULL_COMPILED_CHANGED')
    start,end=observed['regions'][0]['snes']
    origin=prepared['current_source_profile']['origins']['code']['snes']
    R.require(start==origin[0] and start<end<=origin[1], 'Current compiled code exceeds selected origin')
    gfx=observed['regions'][1]['snes']
    bounds=prepared['current_source_profile']['origins']['graphics']['snes']
    R.require(gfx[0]==bounds[0] and gfx[0]<gfx[1]<=bounds[1], 'Current graphics exceeds selected origin')
    bg_plan=prepared.get('bg128_plan');bg_binding=prepared.get('bg128_binding')
    bg_regions=[row for row in observed['regions'] if row['label']=='ProjectBGPalette_Code']
    R.require(bool(bg_plan)==bool(bg_binding)==bool(bg_regions),'CURRENT_BG128_COMPILED_BINDING_MISMATCH')
    if bg_binding:
        start_bg,end_bg=bg_regions[0]['snes'];lo,hi=bg_binding['code_snes']
        R.require(end<=lo==start_bg<end_bg<=hi<=origin[1], 'Current native/BG code spans overlap or exceed their allocation')
    writes=[*prepared['terrain_plan']['writes']]
    if bg_plan:
        a=A.pc(bg_plan['data_snes']);writes.append(dict(pc=[a,a+len(bytes.fromhex(bg_plan['payload_hex']))],
                                                     payload_hex=bg_plan['payload_hex']))
    for row in prepared['tables']['tables']:
        writes.append(dict(pc=row['pc'],payload_hex=row['payload_hex']))
    a=prepared['tables']['descriptor_pc'][0]
    writes.append(dict(pc=[a,a+64],payload_hex=prepared['tables']['descriptor_hex']))
    actors=prepared['actor_storage_plan'];a=A.pc(actors['data_snes'])
    writes.append(dict(pc=[a,a+actors['payload_bytes']],payload_hex=actors['payload_hex']))
    for row in writes:
        a,b=row['pc']
        R.require(0<=a<b<=len(compiled) and compiled[a:b].hex()==row['payload_hex'],
                  'CURRENT_COMPILED_PAYLOAD_MISMATCH: derived data differs')
    joint_art_proof = None
    if prepared.get('joint_art') is not None:
        import lyra_joint_art
        joint_art_proof = lyra_joint_art.verify(prepared['joint_art'], compiled, symbols, P.ROOT)
    # The original pointer directories and all320 decoded native planes remain
    # native controls even though readers now serve the extra32 pages.
    for area in range(160):
        for table in N.POINTER_TABLES:
            at=A.pc(table)+area*3
            R.require(source[at:at+3] == compiled[at:at+3], 'CURRENT_NATIVE_POINTER_CHANGED')
            R.require(N._plane(source,area,table)[0] == N._plane(compiled,area,table)[0],
                      'CURRENT_NATIVE_PLANE_CHANGED: '+str(area))
    changed={r['tile32_id'] for r in prepared['terrain_plan']['emitted_definitions']}
    for tile in range(0x4540):
        R.require(tile in changed or A.read_tile32(source,tile)==A.read_tile32(compiled,tile),
                  'CURRENT_NATIVE_DICTIONARY_CHANGED: '+str(tile))
    for row in prepared['inputs']:
        Q.read_bound(row)
    profile=prepared['current_source_profile']
    _,saved,document=verify_transfer(prepared['request'],prepared['project'],prepared['base_rom'])
    verify_current_native_source_profile(profile,saved,document)
    result=dict(kind='lyra.current_build_verification.v1',compiled_consumers_verified=True,
        saved_rom_sha256=R.sha(source),compiled_rom_sha256=R.sha(compiled),symbols_sha256=R.sha(symbols),
        current_ledger_sha256=prepared['current_ledger_sha256'],
        compiled_consumers_binding=prepared['compiled_consumers'],native_maps_preserved=160,
        native_planes_preserved=320,source_code_fit_bytes=end-start,data_writes_verified=len(writes),
        bg128_data_verified=bool(bg_plan),bg128_code_bytes=(0 if not bg_regions else
            bg_regions[0]['snes'][1]-bg_regions[0]['snes'][0]),
        production_maps=[],production_edge_ids=[],save_exit_policy='unchanged_held',
        native_gameplay_verified=False,save_reopen_verified=False,runtime_verified=False)
    if preview:
        result.update(runtime_scope=PREVIEW_SCOPE,ordinary_build_ready=False,production_admission=False,
                      checkpoint=checkpoint_proof,held_routes=observed['preview_guards']['held_routes'],
                      save_exit_policy='seeded_checkpoint_preview_only')
    if prepared['terrain_plan'].get('enforcement_owner') == 'oracle.current_builder':
        result['compile_order'] = dict(owner='oracle.current_builder', required_order=list(COMPILE_ORDER),
            native_verification=prepared['terrain_plan']['enforcement_receipt'],
            saved_generation_unchanged=True, immutable_snapshot_verified=True,
            derived_output_verified=True, oracle_compile_order_verified=True)
    if joint_art_proof is not None:
        result['joint_art'] = joint_art_proof
    return result
