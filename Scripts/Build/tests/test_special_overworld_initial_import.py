"""Complete import controls: preservation, grouping, refusal and publication."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import special_overworld_initial_import as I
import special_overworld_initial_import_cli as C
import lyra_native_loaders as N
import test_special_overworld_initial_bootstrap as bootstrap_fixture


def fixture():
    f = bootstrap_fixture.InitialBootstrapTest()
    f.setUp()
    source = bytearray(f.source)
    hidden = next(row for row in N.current_table_layout(N.TABLE_BASE)
                  if row.name == 'hidden_items')
    at = N.pc(hidden.legacy_snes)
    source[at:at + 320] = b'\0\x80' * 160
    at = N.pc(0x9B8000)
    source[at:at + 2] = b'\xFF\xFF'
    f.source = bytes(source)
    bootstrap = f.prepare()
    source = f.source
    areas = [dict(parent_map_id=m, maps=[m], size='small') for m in range(160, 192)]
    geometry = [dict(parent=m, size='small', words=[0] * 8) for m in range(192)]
    maps, assets = [], []
    for m in range(160, 192):
        properties = dict(main_palette=0, animated_sheet=0, graphics_sheets=[0] * 8,
            message_id=0, palette_set=0, sprite_palettes=[0] * 3, music=[0] * 4)
        maps.append(dict(map_id=m, tiles16=[[0] * 32 for _ in range(32)],
            authoring=dict(properties=properties, sprites=[], doors=[], exits=[])))
        for phase in range(3):
            assets.append(dict(map_id=m, state=phase, current_binding='bound', binding_changed=False,
                native_assets=dict(state=phase, schema='yaze.lyra-native-resolution.v1',
                    native_base_binding='bound', resolver_seed_map=0x3A,
                    effective_sprite_palette=0, effective_sprite_graphics=0,
                    palette=dict(words=[0] * 256))))
    maps[1]['authoring']['sprites'] = [dict(id=1, sprite_id=0x52, x=8, y=12, state=1)]
    maps[0]['authoring']['exits'] = [dict(id=2, x=22, y=11, room_id=0x83, exit_row=None)]
    dictionary = N.pc(N.CURRENT_DICTIONARIES[400])
    document = dict(maps=maps, edge_connections=[], flight_points=[], profile=dict(tile_count=4096,
        tile16_definition_fingerprint=I.sha(source[dictionary:dictionary + 4096 * 8])))
    terrain_raw, areas_raw = json.dumps(document).encode(), json.dumps(areas).encode()
    inspection = dict(source_rom_sha256=I.sha(source), terrain_sha256=I.sha(terrain_raw),
                      map_count=32, asset_binding_mismatches=0, donor_map=0x3A, map_assets=assets)
    plan = dict(schema='yaze.special-overworld-terrain-import.v1', capacity=192, complete_image=False,
        source_rom_sha256=I.sha(source), source_terrain_sha256=I.sha(terrain_raw),
        gameplay_areas_sha256=I.sha(areas_raw), initial_image_sha256=I.sha(source),
        gameplay_areas=areas, geometry=geometry, high_table_pc=N.pc(0x469E00),
        low_table_pc=N.pc(0x46A040), stream_start=N.pc(0x488000), stream_end=N.pc(0x4C8000),
        native_prefix=dict(high_table_pc=0x1794D, low_table_pc=0x17B2D, map_count=160),
        dictionary_definition_count=4, quadrant_bytes=[[0] * 6 for _ in range(4)], terrain_writes=[])
    for at, count in ((plan['high_table_pc'], 192), (plan['low_table_pc'], 192),
                      (0x1794D, 160), (0x17B2D, 160)):
        plan['terrain_writes'].append(dict(pc=at, before=list(source[at:at + count * 3]),
                                           after=list(b'\0\x80\x48' * count)))
    return source, terrain_raw, areas_raw, plan, inspection, bootstrap


class InitialImportTest(unittest.TestCase):
    def test_complete_image_preserves_inputs_and_pending_placement_identity(self):
        args = fixture()
        before = copy.deepcopy(args)
        image, result = I.prepare_initial_import(*args)
        self.assertEqual(args, before)
        self.assertTrue(result['complete_image'])
        self.assertFalse(result['adopted'])
        self.assertFalse(result['runtime_qualified'])
        self.assertEqual(result['gameplay_area_count'], 32)
        self.assertEqual(len(N.read_native_directory(image)[2]), 57)
        at = N.pc(N.AUTHORING_METADATA_BASE)
        metadata = N.authoring_metadata.decode(image[at:at + 0x2000], 192)
        by_id = {row['id']: row for row in metadata['placements']}
        self.assertEqual(by_id[1]['owner_map'], 161)
        self.assertEqual(by_id[2]['target'], 0x83)
        self.assertIsNone(by_id[2]['row'])
        for first, end in I.ORIGINAL_POOLS:
            self.assertEqual(image[first:end], args[0][first:end])

    def test_explicit_reassignment_changes_owner_without_hardcoded_area_count(self):
        source, terrain, _, plan, inspection, bootstrap = fixture()
        areas = [dict(parent_map_id=160, maps=[160, 161], size='wide')] + plan['gameplay_areas'][2:]
        raw = json.dumps(areas).encode()
        plan.update(gameplay_areas=areas, gameplay_areas_sha256=I.sha(raw))
        for m in (160, 161):
            plan['geometry'][m].update(parent=160, size='wide')
        image, result = I.prepare_initial_import(source, terrain, raw, plan, inspection, bootstrap)
        self.assertEqual(result['gameplay_area_count'], 31)
        at = N.pc(N.AUTHORING_METADATA_BASE)
        records = N.authoring_metadata.decode(image[at:at + 0x2000], 192)['placements']
        self.assertEqual(next(r['owner_map'] for r in records if r['id'] == 1), 160)
        actor = N.pc(N.ACTORS_BASE)
        self.assertIn(bytes([12, 40, 0x52, 255]), image[actor:actor + 100])

    def test_stale_input_or_partial_assignment_refuses(self):
        for index in (0, 1, 2):
            args = list(fixture())
            args[index] += b' '
            with self.assertRaises(ValueError):
                I.prepare_initial_import(*args)
        args = list(fixture())
        args[3]['gameplay_areas'] = args[3]['gameplay_areas'][:-1]
        args[2] = json.dumps(args[3]['gameplay_areas']).encode()
        args[3]['gameplay_areas_sha256'] = I.sha(args[2])
        with self.assertRaisesRegex(ValueError, 'all32'):
            I.prepare_initial_import(*args)

    def test_foreign_overlapping_or_stale_terrain_write_refuses(self):
        changes = [lambda p: p['terrain_writes'][0].update(pc=0x7FDC),
                   lambda p: p['terrain_writes'].append(copy.deepcopy(p['terrain_writes'][0])),
                   lambda p: p['terrain_writes'][0]['before'].__setitem__(0, 255)]
        for change in changes:
            args = list(fixture())
            change(args[3])
            with self.assertRaises(ValueError):
                I.prepare_initial_import(*args)

    def test_unlowered_routes_and_changed_tile16_are_never_silently_discarded(self):
        for name in ('edge_connections', 'flight_points'):
            args = list(fixture())
            doc = json.loads(args[1])
            doc[name] = [dict(id=1)]
            args[1] = json.dumps(doc).encode()
            args[3]['source_terrain_sha256'] = args[4]['terrain_sha256'] = I.sha(args[1])
            with self.assertRaisesRegex(ValueError, 'cannot discard'):
                I.prepare_initial_import(*args)


class DormantAppearanceTest(unittest.TestCase):
    def fixture(self):
        image, _ = I.prepare_initial_import(*fixture())
        output = bytearray(image)
        _, bank, entries = N.read_native_directory(image)
        flags = N.pc(entries[410][0])
        palettes = N.pc(entries[411][0])
        output[flags + 160] = 3
        output[palettes + 32 * 256:palettes + 33 * 256] = b'\x34\x12' * 128
        directory = N.encode_revision4_directory(bytes(output),
            [(key, address, count) for key, (address, count) in entries.items()],
            tail_actor_bank=bank)
        output[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = directory
        image = bytes(output)
        exported = dict(source_rom_sha256=I.sha(image), pages=[
            dict(map_id=m, background_palette_words=[m + color for color in range(128)])
            for m in range(128, 192)])
        return image, exported

    def test_customize_rows_start_with_source_colors_and_explicit_rows_stay_exact(self):
        image, exported = self.fixture()
        output, result = I.initialize_dormant_appearance(image, exported)
        self.assertTrue(result['appearance_activation_ready'])
        entries = N.read_native_directory(image)[2]
        final = N.read_native_directory(output)[2]
        at = N.pc(entries[411][0])
        for row in exported['pages']:
            m = row['map_id']
            stored = output[at + (m - 128) * 256:at + (m - 127) * 256]
            if m == 160:
                self.assertEqual(stored, b'\x34\x12' * 128)
            else:
                self.assertEqual(list(I.struct.unpack('<128H', stored)),
                                 row['background_palette_words'])
        for key, (address, count) in entries.items():
            self.assertEqual(final[key], entries[key])
            if key != 411:
                stride = N.entry_spec(key, 192, 4)[2]
                at = N.pc(address)
                self.assertEqual(output[at:at + count * stride], image[at:at + count * stride])
        flags = N.pc(entries[410][0])
        self.assertEqual(output[flags + 128], 0)
        self.assertEqual(output[flags + 161], 1)
        # The existing Customize action only switches either flag to3; its
        # stored color input is already the source palette, not zero fill.
        self.assertIn(128, result['dormant_appearance_maps'])
        self.assertIn(161, result['dormant_appearance_maps'])
        self.assertNotIn(160, result['dormant_appearance_maps'])

    def test_stale_missing_or_invalid_source_palette_refuses(self):
        for change in (lambda p: p.update(source_rom_sha256='stale'),
                       lambda p: p['pages'].pop(),
                       lambda p: p['pages'][0].pop('background_palette_words'),
                       lambda p: p['pages'][0]['background_palette_words'].__setitem__(0, 0x8000)):
            image, projection = self.fixture()
            change(projection)
            with self.assertRaises(ValueError):
                I.initialize_dormant_appearance(image, projection)

    def test_baseline_guard_rejects_a_valid_but_changed_original_map(self):
        validation = dict(total_maps=192, valid_maps=192, invalid_maps=0, skipped_maps=0,
                          baseline_maps_checked=160, baseline_mismatches=1)
        with mock.patch.object(C, '_json_output', return_value=validation) as command:
            with self.assertRaises(ValueError):
                C.validate_staged_image(Path('candidate.sfc'), b'image', b'{}', {}, {},
                                        'z3ed', baseline=Path('saved160.sfc'))
            self.assertEqual(command.call_count, 1)
            self.assertIn('--baseline', command.call_args.args[0])


class PublicationTest(unittest.TestCase):
    def paths(self, folder):
        return Path(folder) / 'candidate.sfc', Path(folder) / 'receipt.json'

    def test_failed_inspection_or_changed_stage_exposes_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            out, receipt = self.paths(folder)
            def reject(path):
                raise ValueError('actual inspector rejected')
            with self.assertRaises(ValueError):
                C.publish_candidate(out, receipt, b'candidate', b'{}', reject)
            self.assertEqual(list(Path(folder).iterdir()), [])
            def change(path):
                path.write_bytes(b'changed')
                return {}
            with self.assertRaisesRegex(ValueError, 'validator changed'):
                C.publish_candidate(out, receipt, b'candidate', b'{}', change)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_second_output_failure_rolls_back_only_unchanged_owned_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            out, receipt = self.paths(folder)
            real_link = C.os.link
            def fail_second(source, destination):
                if destination == receipt:
                    raise OSError('receipt publication failed')
                real_link(source, destination)
            with mock.patch.object(C.os, 'link', side_effect=fail_second):
                with self.assertRaises(OSError):
                    C.publish_candidate(out, receipt, b'candidate', b'{}', lambda p: {})
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_existing_output_is_preserved_and_success_creates_complete_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            out, receipt = self.paths(folder)
            out.write_bytes(b'user')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                C.publish_candidate(out, receipt, b'candidate', b'{}', lambda p: {})
            self.assertEqual(out.read_bytes(), b'user')
            out.unlink()
            result = C.publish_candidate(out, receipt, b'candidate', b'{}', lambda p: dict(validated_maps=192))
            self.assertEqual(out.read_bytes(), b'candidate')
            self.assertEqual(json.loads(receipt.read_text()), result)
            self.assertEqual(result['inspection']['validated_maps'], 192)


if __name__ == '__main__':
    unittest.main()
