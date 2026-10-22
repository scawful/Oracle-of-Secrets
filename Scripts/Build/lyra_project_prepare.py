#!/usr/bin/env python3
"""Bind a saved dev project to the existing isolated native37/A1 publisher.

Run against an isolated saved project copy. The source project, ROM, terrain and
qualification controls are read only. An incompatible source produces a refusal
report, never a request. This does not admit more maps or relocate native IDs.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
from pathlib import Path
import subprocess
import sys

import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_composition as C
import lyra_project_delta as D
import lyra_native_streams as N
import lyra_project_tile32 as T32
from lyra_project_terrain import resolve_project_terrain

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Generate'))
import validate_custom_collision_source as CC

KIND = 'lyra.current_saved_request.v1'
ASSIGNMENT_KIND = 'lyra.current_saved_assignment.v1'


def bound(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), sha256=R.sha(path.read_bytes()))


def read_bound(row):
    R.require(type(row) is dict and set(row) == {'path', 'sha256'}, 'Malformed current input binding')
    raw = Path(row['path']).read_bytes()
    R.require(R.sha(raw) == row['sha256'], f"Current saved input changed: {row['path']}")
    return raw


def controls(request_path):
    """Keep original controls in their original context, including source pins."""
    import lyra_project_publisher as P
    value = json.loads(Path(request_path).read_bytes())
    R.require(type(value) is dict and set(value) == set(P.ROLES), 'Qualification request roles differ')
    rows = {key: bound(path) for key, path in value.items()}
    R.require(all(row['sha256'] == C.PINS[key] for key, row in rows.items()),
              'Original qualification controls differ')
    data = {key: read_bound(row) for key, row in rows.items()}
    frozen = json.loads(data['frozen_assignment'])
    claim, digest = R.reservation_claim(value['historical_ledger'])
    pairs = T32.verify_contract(data['saved_rom'], frozen, claim, digest)
    manifest = json.loads(data['power_manifest'])
    D.validate_manifest(manifest)
    fixture_row = manifest['inputs']['candidate_fixture_rom']
    fixture = read_bound(fixture_row)
    R.require(T32.verify_contract(fixture, frozen, claim, digest) == pairs
              and len(pairs) == 115 and [i for i, _ in pairs] == list(range(0x44C0, 0x4533)),
              'Original frozen115 qualification differs')
    return rows, pairs, fixture_row


def resource_report(source, ledger_path):
    """Report occupied resources without treating apparently free bytes as owned."""
    import lyra_project_publisher as P
    blockers = []
    try:
        claim, _ = P.publication_authorization(ledger_path)
    except (ValueError, OSError) as error:
        return [dict(code='PUBLICATION_POLICY_REFUSED', detail=str(error))]
    def reservation():
        value = R.derive_allocation(source, ledger_path=ledger_path)
        allocation = A.parse_allocation(value, source)
        R.verify_reservation(source, allocation, value['reservation'], ledger_path=ledger_path)
        R.require(allocation.stream_ranges == ((0x3D4000, 0x3D4818),), 'Stream reservation differs')

    ownership = {}
    for check, code in ((reservation, 'ROM_RESERVATION_REFUSED'),
                        (lambda: T32.ownership(source, claim), 'TILE32_RESERVATION_REFUSED')):
        try:
            result = check()
            if code == 'TILE32_RESERVATION_REFUSED':
                ownership = result
        except ValueError as error:
            blockers.append(dict(code=code, detail=str(error)))
    if len(source) == 0x400000:
        references = []
        try:
            for area in range(160):
                planes = [N._plane(source, area, table)[0] for table in N.POINTER_TABLES]
                for cell, (high, low) in enumerate(zip(*planes)):
                    tile = high << 8 | low
                    if 0x44C0 <= tile < 0x4540:
                        references.append(dict(map_id=area, cell=cell, tile32_id=tile))
        except (ValueError, IndexError) as error:
            blockers.append(dict(code='NATIVE_CONSUMER_REFUSED', detail=str(error)))
        unexpected = [r for r in references if r not in ownership.get('retained_native_references', [])]
        if unexpected:
            blockers.append(dict(code='RESERVED_TILE32_NATIVE_REFERENCES', references=unexpected,
                detail='Review native ID relocation or a new ownership contract before preparing; no IDs were reassigned.'))
    return blockers


def collision_binding(rom):
    """Use the existing strict decoder, including explicit zero records."""
    import lyra_project_publisher as P
    CC.validate_contract(P.ROOT, Path(rom))
    return bound(P.ROOT / CC.SOURCE_PATH)


def current_assignment(source, terrain, document, frozen_pairs, ledger_path):
    """Retain frozen meanings; assign new quartets only in the declared tail."""
    claim, digest = R.reservation_claim(ledger_path)
    receipt = T32.ownership(source, claim)
    native = {A.read_tile32(source, i) for i in range(0x4540)}
    # An editor may have added a frozen quartet to the native dictionary. Reuse
    # that native definition rather than inventing a second assigned meaning.
    pairs = [(i, q) for i, q in frozen_pairs if q not in native]
    frozen_quads = {q for _, q in frozen_pairs}
    missing = C._missing(source, document, [0xA1])
    additional = sorted(set(missing) - frozen_quads)
    begin, end = claim['tile32_candidate_reservation']['id_range']
    R.require(begin == 0x44C0 and len(frozen_pairs) == 115, 'Frozen115 assignment boundary differs')
    retained = set(receipt.get('retained_native_ids', []))
    available = [i for i in range(begin + 115, end) if i not in retained]
    R.require(len(additional) <= len(available),
              f'Current A1 Tile32 capacity conflict: {len(additional)} new definitions exceed {len(available)} remaining IDs')
    pairs.extend(zip(available, additional))
    return dict(kind=ASSIGNMENT_KIND, source_rom_sha256=R.sha(source), terrain_sha256=R.sha(terrain),
        ledger_sha256=digest, consumer_receipt=receipt, candidate_maps=[0xA1],
        render_directory=[dict(map_id=0xA1, quadrant_maps=[0xA1] * 4)],
        frozen115=[dict(tile32_id=i, quadrants=list(q)) for i, q in frozen_pairs],
        assignments=[dict(tile32_id=i, quadrants=list(q)) for i, q in pairs],
        new_definition_count=len(additional), production_maps=[], production_edge_ids=[])


def current_plan(project, base_rom, request_path, *, ledger_path=None):
    import lyra_project_publisher as P
    project, project_rom, terrain, actual_request = P.project_context(project, request_path)
    request_path = actual_request
    request_raw = request_path.read_bytes()
    request_binding = dict(path=str(request_path), sha256=R.sha(request_raw))
    value = json.loads(request_raw)
    R.require(type(value) is dict and set(value) == {
        'kind', 'inputs', 'qualification_request', 'assignment', 'selected_maps', 'production_admission'},
        'Malformed current saved request')
    R.require(value['kind'] == KIND and value['selected_maps'] == [0x37, 0xA1]
              and value['production_admission'] is False, 'Current request exceeds isolated37/A1 publication')
    rows = value['inputs']
    R.require(type(rows) is dict and set(rows) == {'project', 'saved_rom', 'terrain', 'observation', 'ledger', 'z3ed', 'collision_source'},
              'Current request input roles differ')
    data = {key: read_bound(row) for key, row in rows.items()}
    ledger = Path(ledger_path or rows['ledger']['path']).resolve(strict=True)
    R.require(ledger == Path(rows['ledger']['path']).resolve(strict=True), 'Current request ledger differs')
    R.require(project.resolve() == Path(rows['project']['path']).resolve(strict=True)
              and project_rom == Path(rows['saved_rom']['path']).resolve(strict=True)
              and terrain == Path(rows['terrain']['path']).resolve(strict=True),
              'Current request does not bind the selected saved project')
    base_rom = Path(base_rom).resolve(strict=True)
    R.require(base_rom.read_bytes() == data['saved_rom'], 'Selected project/base ROM differs from current saved source')
    R.require(rows['collision_source'] == collision_binding(project_rom), 'Current collision source differs')
    control_request = value['qualification_request']
    read_bound(control_request)
    control_rows, frozen_pairs, fixture = controls(control_request['path'])
    blockers = resource_report(data['saved_rom'], ledger)
    R.require(not blockers, 'Current source resource refusal: ' + json.dumps(blockers, sort_keys=True))
    # This native observation verifies graphics, palettes and bindings from
    # actual saved assets; sidecar-provided hashes alone are never the proof.
    document = C._document(data['terrain'], data['observation'], data['saved_rom'])
    R.require(not A.consumer_blockers(document, [0xA1], {}), 'Current A1 metadata is unsupported')
    assignment = current_assignment(data['saved_rom'], data['terrain'], document, frozen_pairs, ledger)
    R.require(value['assignment'] == assignment, 'Current source-bound assignment differs')
    for name, digest in C.SOURCE_ANCHORS.items():
        R.require(R.sha((P.ROOT / name).read_bytes()) == digest, f'Publisher source anchor differs: {name}')
    pairs = tuple((row['tile32_id'], tuple(row['quadrants'])) for row in assignment['assignments'])
    result = P.compile_saved_plan(data['saved_rom'], document, pairs, D.native_map_grid(data['saved_rom'], 0x37))
    inputs = [*rows.values(), control_request, *control_rows.values(), fixture, request_binding,
              dict(path=str(base_rom), sha256=R.sha(data['saved_rom']))]
    inputs.extend(dict(path=str(P.ROOT / name), sha256=digest) for name, digest in C.SOURCE_ANCHORS.items())
    R.require(all(R.sha(Path(row['path']).read_bytes()) == row['sha256'] for row in inputs),
              'Current publisher input changed while preparing')
    return dict(kind='lyra.ordinary_build_prepare.v1', selected=True, project=str(project),
        base_rom=str(base_rom), request=str(request_path), ledger=str(ledger),
        current_ledger_sha256=rows['ledger']['sha256'], saved_rom_sha256=R.sha(data['saved_rom']),
        source_map_count=160, table_capacity=192, inputs=sorted(inputs, key=lambda r: r['path']),
        source_reservation=R.derive_allocation(data['saved_rom'], ledger_path=ledger)['reservation'],
        current_assignment=assignment, **result)


def prepare_request(project, z3ed, qualification_request, output, *, ledger_path=None):
    """Create a new request directory, or a machine-readable refusal report."""
    import lyra_project_publisher as P
    project = Path(os.path.abspath(project))
    output = Path(output).absolute()
    R.require(not output.exists(), 'Current preparation requires a new output directory')
    R.require(not any(p.is_symlink() for p in (output, *output.parents)), 'Generated output uses a symlink')
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string(project.read_text(encoding='utf-8-sig'))
    parser.defaults().clear()
    R.require(parser.get('rom', 'role', fallback='') == 'dev', 'Lyra build requires a dev project')
    rom = P.project_reference(project, parser, 'rom_filename')
    terrain = resolve_project_terrain(project)
    ledger = Path(ledger_path or R.LEDGER).resolve(strict=True)
    input_rows = {key: bound(path) for key, path in dict(project=project, saved_rom=rom, terrain=terrain,
                                                      ledger=ledger, z3ed=z3ed).items()}
    qualification = bound(qualification_request)
    control_rows, frozen, fixture = controls(qualification_request)
    protected = [project, rom, terrain, ledger, z3ed, qualification_request,
                 *[row['path'] for row in control_rows.values()], fixture['path']]
    # Refuse occupied ranges before launching even the read-only native CLI.
    blockers = resource_report(rom.read_bytes(), ledger)
    for key in ('dungeon_tile_patterns', 'custom_collision_json', 'palette_catalog_file', 'hack_manifest_file'):
        reference = parser.get('files', key, fallback='').strip()
        if reference:
            path = Path(reference)
            path = path if path.is_absolute() else project.parent / path
            if not path.is_file():
                blockers.append(dict(code='MISSING_PROJECT_RESOURCE', field=key, path=str(path)))
    try:
        input_rows['collision_source'] = collision_binding(rom)
    except (ValueError, OSError, CC.CustomCollisionSourceContractError) as error:
        blockers.append(dict(code='COLLISION_SOURCE_REFUSED', detail=str(error)))
    report = dict(kind='lyra.current_project_preparation.v1', ready=False, inputs=input_rows,
                  blockers=blockers, production_maps=[], production_edge_ids=[], rom_written=False)
    files = {}
    if not blockers:
        try:
            observation = A.native_verify(Path(z3ed), project, rom)
            document = C._document(terrain.read_bytes(), P.encoded(observation), rom.read_bytes())
            assignment = current_assignment(rom.read_bytes(), terrain.read_bytes(), document, frozen, ledger)
            input_rows['observation'] = dict(path=str(output / 'observation.json'), sha256=R.sha(P.encoded(observation)))
            value = dict(kind=KIND, inputs=input_rows, qualification_request=qualification,
                         assignment=assignment, selected_maps=[0x37, 0xA1], production_admission=False)
            # Validate complete compilation before making a usable request visible.
            R.require(not A.consumer_blockers(document, [0xA1], {}), 'Current A1 metadata is unsupported')
            pairs = tuple((row['tile32_id'], tuple(row['quadrants'])) for row in assignment['assignments'])
            P.compile_saved_plan(rom.read_bytes(), document, pairs, D.native_map_grid(rom.read_bytes(), 0x37))
            for name, digest in C.SOURCE_ANCHORS.items():
                R.require(R.sha((P.ROOT / name).read_bytes()) == digest, f'Publisher source anchor differs: {name}')
            files.update({'observation.json': P.encoded(observation), 'request.json': P.encoded(value)})
            report.update(ready=True, request=str(output / 'request.json'), assignment=assignment)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            stderr = getattr(error, 'stderr', None)
            if isinstance(stderr, bytes):
                stderr = stderr.decode('utf-8', errors='replace')
            report['blockers'].append(dict(code='CURRENT_INPUT_REFUSED', detail=str(error),
                stderr=stderr))
    R.require(all(R.sha(Path(row['path']).read_bytes()) == row['sha256']
                  for row in [*[r for k, r in input_rows.items() if k != 'observation'], qualification,
                              *control_rows.values(), fixture]), 'Saved inputs changed during preparation')
    request_bytes = files.pop('request.json', None)
    files['report.json'] = P.encoded(report)
    # The request is the completion marker. A failed report/observation write
    # cannot leave behind a usable request from an unsuccessful preparation.
    if request_bytes is not None:
        files['request.json'] = request_bytes
    output.mkdir(parents=True, exist_ok=False)
    P.write_outputs(output, files, protected=protected)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--z3ed', type=Path, required=True)
    parser.add_argument('--qualification-request', type=Path, required=True)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare_request(args.project, args.z3ed, args.qualification_request, args.output, ledger_path=args.ledger)
    except (ValueError, OSError, configparser.Error) as error:
        parser.exit(1, f'Current project preparation refused: {error}\n')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
