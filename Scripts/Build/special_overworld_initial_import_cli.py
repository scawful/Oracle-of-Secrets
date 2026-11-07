"""Complete candidate preparation behind the existing native Build CLI.

The candidate and receipt are published together only after maintained z3ed
inspection. Project adoption, Save and runtime Build retain their own owners.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import lyra_native_loaders as native
import special_overworld_initial_bootstrap as engine
import special_overworld_initial_import as composer


def _json_output(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    native.require(result.returncode == 0,
                   'Initial import inspection failed: ' + (result.stderr + result.stdout)[-4000:])
    first = result.stdout.find('{')
    native.require(first >= 0, 'Initial import inspection returned no JSON')
    return json.loads(result.stdout[first:])


def _field(result, name):
    # OutputFormatter wraps values under data; direct JSON fixtures remain
    # accepted for callers which already decoded that existing transport.
    if name in result:
        return result[name]
    return result['data'][name]


def validate_staged_image(path, image, terrain_raw, plan, inspection, z3ed, *, baseline):
    """Use the actual native model for all192 streams and96 tail asset states."""
    validation = _json_output([z3ed, 'overworld-validate', '--rom', str(path),
                               '--include-tail', '--check-tile16', '--baseline', str(baseline), '--format', 'json'])
    native.require(_field(validation, 'total_maps') == 192
                   and _field(validation, 'valid_maps') == 192
                   and _field(validation, 'invalid_maps') == 0
                   and _field(validation, 'skipped_maps') == 0
                   and _field(validation, 'baseline_maps_checked') == 160
                   and _field(validation, 'baseline_mismatches') == 0,
                   'Initial import did not validate all192 terrain maps')
    result = _json_output([z3ed, 'overworld-export-native-source', '--rom', str(path),
                           '--format', 'json'])
    exported = _field(result, 'native_source')
    native.require(exported['source_rom_sha256'] == composer.sha(image)
                   and exported['directory_revision'] == 4
                   and exported['materialized_map_count'] == 192
                   and {p['map_id'] for p in exported['pages']} == set(range(128, 192)),
                   'Initial import native export identity or coverage differs')
    pages = {p['map_id']: p for p in exported['pages']}
    assets = {(r['map_id'], r['native_assets']['state']): r['native_assets']
              for r in inspection['map_assets']}
    for saved in json.loads(terrain_raw)['maps']:
        map_id = saved['map_id']
        page = pages[map_id]
        native.require(page['tiles'] == [v for row in saved['tiles16'] for v in row]
                       and page['parent_map_id'] == plan['geometry'][map_id]['parent'],
                       f'Initial import terrain or membership differs for map{map_id:02X}')
        states = page['resolved_states']
        native.require(len(states) == 3 and {r['state'] for r in states} == {0, 1, 2},
                       'Initial import native asset states are incomplete')
        for state in states:
            original = assets[map_id, state['state']]
            native.require(state['graphics_sha256'] == original['graphics']['sha256']
                           and state['palette']['words'] == original['palette']['words']
                           and state['sprite_graphics'] == original['effective_sprite_graphics'],
                           f'Initial import graphics or colors differ for map{map_id:02X}')
    tail_areas = [{k: area[k] for k in ('parent_map_id', 'maps', 'size')}
                  for area in exported['gameplay_areas'] if area['parent_map_id'] >= 160]
    native.require(tail_areas == plan['gameplay_areas'],
                   'Initial import native gameplay-area assignments differ')
    native.require(path.read_bytes() == image, 'Initial import inspection changed staged image')
    return dict(validated_maps=192, original_terrain_maps_preserved=160,
                checked_tail_terrain_maps=32,
                checked_tail_asset_states=96, gameplay_area_count=len(tail_areas),
                native_source_sha256=composer.sha(json.dumps(exported, sort_keys=True).encode()))


def publish_candidate(output, receipt_path, image, receipt_raw, validate):
    """Create two new outputs, rolling back owned links on any failure."""
    output, receipt_path = Path(output), Path(receipt_path)
    native.require(output.parent.resolve() == receipt_path.parent.resolve()
                   and output.resolve() != receipt_path.resolve(),
                   'Initial candidate and receipt need distinct names in one output directory')
    native.require(not output.exists() and not output.is_symlink()
                   and not receipt_path.exists() and not receipt_path.is_symlink(),
                   'Initial import output already exists')
    created = []
    with tempfile.TemporaryDirectory(prefix='.native-import-', dir=output.parent) as name:
        folder = Path(name)
        staged = folder / 'candidate.sfc'
        staged.write_bytes(image)
        validation = validate(staged)
        native.require(staged.read_bytes() == image, 'Initial import validator changed the candidate')
        record = json.loads(receipt_raw)
        record['inspection'] = validation
        record['image_sha256'] = composer.sha(image)
        staged_receipt = folder / 'receipt.json'
        staged_receipt.write_text(json.dumps(record, indent=2) + '\n')
        try:
            for source, destination in ((staged, output), (staged_receipt, receipt_path)):
                os.link(source, destination)  # Atomic create, never replace a raced-in user file.
                created.append((source, destination, composer.sha(source.read_bytes())))
        except BaseException:
            for source, destination, expected_hash in reversed(created):
                native.require(destination.is_file() and destination.samefile(source)
                               and composer.sha(destination.read_bytes()) == expected_hash,
                               'Initial import output changed during rollback; preserved')
                destination.unlink()
            raise
    return record


def run_initial_import(args):
    """Prepare a complete private candidate; never modify inputs or a project."""
    try:
        names = ('rom', 'import_terrain', 'import_gameplay_areas', 'import_plan',
                 'import_inspection', 'engine_rom', 'engine_receipt', 'symbols')
        native.require(all(getattr(args, name, None) is not None for name in names)
                       and args.import_receipt is not None,
                       'Initial import requires source, terrain, gameplay areas, plan, inspection, '
                       'current engine ROM/receipt/symbols and output receipt')
        inputs = {name: getattr(args, name).read_bytes() for name in names}
        native.require(all(args.prepare_initial_import.resolve() != getattr(args, name).resolve()
                           and args.import_receipt.resolve() != getattr(args, name).resolve()
                           for name in names), 'Initial import output aliases an input')
        receipt = json.loads(inputs['engine_receipt'])
        root = Path(__file__).resolve().parents[2]
        paths = engine.bootstrap_source_paths(receipt)
        native.require(all(not Path(p).is_absolute() and '..' not in Path(p).parts
                           for p in paths), 'Initial engine source path leaves checkout')
        sources = {name: (root / name).read_bytes() for name in paths}
        bootstrap = engine.prepare_initial_bootstrap(inputs['rom'], inputs['engine_rom'],
            symbols_raw=inputs['symbols'], build_receipt=receipt, current_source_files=sources)
        plan, inspection = json.loads(inputs['import_plan']), json.loads(inputs['import_inspection'])
        image, result = composer.prepare_initial_import(inputs['rom'], inputs['import_terrain'],
            inputs['import_gameplay_areas'], plan, inspection, bootstrap)
        result['engine'] = {k: bootstrap[k] for k in ('compiled_rom_sha256', 'symbols_sha256',
                                                     'source_files', 'external_symbols')}
        command = shutil.which(args.z3ed or 'z3ed')
        native.require(command is not None, 'Initial import requires the maintained z3ed inspector')
        inspector_hash = composer.sha(Path(command).read_bytes())
        result['inspector'] = dict(path=command, sha256=inspector_hash)
        with tempfile.TemporaryDirectory(prefix='.native-appearance-',
                                         dir=args.prepare_initial_import.parent) as temporary:
            palette_source = Path(temporary) / 'appearance-source.sfc'
            palette_source.write_bytes(image)
            projection = _json_output([command, 'overworld-export-native-source', '--rom',
                                       str(palette_source), '--include-inactive-backgrounds', '--format', 'json'])
            native.require(palette_source.read_bytes() == image,
                           'Initial appearance inspection changed its source')
            image, appearance = composer.initialize_dormant_appearance(
                image, _field(projection, 'native_source'))
        result.update(appearance)
        native.require(result['appearance_activation_ready'],
                       'Initial image custom-color rows are not initialized')

        def validate(staged):
            checked = validate_staged_image(staged, image, inputs['import_terrain'], plan,
                                             inspection, command, baseline=args.rom)
            native.require(all(getattr(args, name).read_bytes() == raw
                               for name, raw in inputs.items())
                           and all((root / name).read_bytes() == raw for name, raw in sources.items())
                           and composer.sha(Path(command).read_bytes()) == inspector_hash,
                           'Initial import inputs changed during preparation')
            return checked

        published = publish_candidate(args.prepare_initial_import, args.import_receipt, image,
            json.dumps(result).encode(), validate)
        print(json.dumps(dict(complete_image=True, adopted=False, runtime_qualified=False,
            output=str(args.prepare_initial_import), receipt=str(args.import_receipt),
            image_sha256=published['image_sha256'], inspection=published['inspection'])))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'Initial special overworld import: {error}', file=sys.stderr)
        return 1
