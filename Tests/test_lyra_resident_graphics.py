"""Resident terrain packing checks using real 3bpp streams, without a game ROM."""

import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'Scripts/Build'), str(ROOT / 'Scripts/Generate')]
import lyra_project_terrain as T
import lyra_resident_graphics as R
import lz2
import sheet_codec
import sheet_table
import test_lyra_current_transfer as transfer_cases


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snes(pc):
    return (pc // 0x8000) << 16 | 0x8000 | pc % 0x8000


def tile(*rows):
    """Eight literal rows make source pictures readable in the controls below."""
    return tuple(int(value) for row in rows for value in row)


DIAGONAL = tile('10000000', '02000000', '00100000', '00020000',
                '00001000', '00000200', '00000010', '00000002')
STRIPES = tile(*(['12121212'] * 8))


class Fixture:
    """Complete 32-page/three-state inspection around a small authored picture."""

    def __init__(self, definitions=(((2 << 10) | 64,) * 4,), *, wide=True):
        self.definitions = definitions
        self.sheet_tiles = {sheet: {} for sheet in range(10)}
        self.sheet_tiles[1][0] = DIAGONAL
        self.map_sheets = [list(range(8)) for _ in range(32)]
        self.map_animation = [9] * 32
        self.map_tiles = [[0] * 1024 for _ in range(32)]
        self.palettes = [[0] * 256 for _ in range(32)]
        for palette in self.palettes:
            for bank in range(8):
                for index, color in ((1, 0x001F), (2, 0x03E0), (9, 0x7C00), (10, 0x7FFF)):
                    palette[bank * 16 + index] = color
        self.areas = ([dict(parent_map_id=0xA0, size='wide', maps=[0xA0, 0xA1])]
                      if wide else [])
        self.areas.extend(dict(parent_map_id=map_id, size='small', maps=[map_id])
                          for map_id in range(0xA2 if wide else 0xA0, 0xC0))

    def inputs(self):
        definitions = b''.join(struct.pack('<4H', *row) for row in self.definitions)
        source = bytearray(0x30000)
        source[0x865:0x868] = snes(0x10000).to_bytes(3, 'little')
        source[0x10000:0x10000 + len(definitions)] = definitions
        decoded = {}
        cursor = 0x18000
        for sheet, tiles in sorted(self.sheet_tiles.items()):
            grid = [[0] * 128 for _ in range(32)]
            for index, pixels in tiles.items():
                for y in range(8):
                    x = (index % 16) * 8
                    grid[(index // 16) * 8 + y][x:x + 8] = pixels[y * 8:y * 8 + 8]
            raw = sheet_codec.grid_to_sheet(grid)
            stream = lz2.stored(raw)
            source[cursor:cursor + len(stream)] = stream
            for address, shift in ((sheet_table.TBL_BANK, 16),
                                   (sheet_table.TBL_HIGH, 8), (sheet_table.TBL_LOW, 0)):
                source[sheet_table.pc(address) + sheet] = (snes(cursor) >> shift) & 255
            cursor += len(stream)
            decoded[sheet] = bytes(value for row in grid for value in row)
        profile = dict(graphics_sheets=list(range(8)), main_palette=0, palette_set=0,
                       animated_sheet=9, tile_count=len(self.definitions),
                       tile16_definition_fingerprint=sha(definitions),
                       graphics_fingerprint=sha(b'fixture graphics'),
                       palette_fingerprint=sha(b'fixture palette'),
                       animation_fingerprint=sha(b'fixture animation'))
        authoring, properties, observations = [], [], []
        for index in range(32):
            props = copy.deepcopy(T.DEFAULT_PROPERTIES)
            props.update(graphics_sheets=self.map_sheets[index], main_palette=0,
                         palette_set=0, animated_sheet=self.map_animation[index])
            authoring.append(dict(properties=props, sprites=[], doors=[], exits=[],
                                  asset_bindings=['', '', '']))
            properties.append(copy.deepcopy(props))
            saved = {name: copy.deepcopy(props[name]) for name in
                     ('graphics_sheets', 'main_palette', 'palette_set', 'animated_sheet',
                      'sprite_graphics', 'sprite_palettes')}
            palette = self.palettes[index]
            slots = []
            for slot in range(16):
                sheet = self.map_sheets[index][slot] if slot < 8 else None
                raw = decoded[sheet] if sheet is not None else None
                resolved = (bytes(value + (0x88 if slot in (0, 3, 4, 5) else 0)
                                  for value in raw) if raw is not None else None)
                if slot == 7:
                    resolved = decoded[self.map_animation[index]][:0x800] + raw[0x800:]
                slots.append(dict(slot=slot, sheet_id=sheet,
                                  decoded_sheet_sha256=sha(raw) if raw is not None else None,
                                  resolved_slot_sha256=sha(resolved) if resolved is not None else sha(bytes(0x1000))))
            for state in range(3):
                binding = sha(f'native fixture {index}/{state}'.encode())
                assets = dict(schema='yaze.lyra-native-resolution.v1', state=state,
                              inspection_only=True, resolution_mode='native-only', resolver_seed_map=0x3A,
                              saved_properties=saved, native_base_binding=binding,
                              slots=slots, animation=dict(sheet_id=self.map_animation[index],
                                  decoded_sheet_sha256=sha(decoded[self.map_animation[index]])),
                              palette=dict(words=palette,
                                  uint16le_sha256=sha(struct.pack('<256H', *palette))))
                observations.append(dict(map_id=0xA0 + index, state=state,
                                         native_base_binding=binding, current_binding=binding,
                                         stored_binding='', binding_changed=False,
                                         palette_words=palette, native_assets=assets))
        document = T.TerrainDocument(profile, tuple(tuple(row) for row in self.map_tiles),
                                    tuple(properties), authoring=tuple(authoring),
                                    gameplay_areas=tuple(self.areas))
        terrain_hash = sha(json.dumps(dict(maps=self.map_tiles, authoring=authoring,
                                           areas=self.areas), sort_keys=True).encode())
        inspection = dict(source_rom_sha256=sha(source), terrain_sha256=terrain_hash,
                          profile=profile, map_count=32, donor_map=0x3A, asset_binding_mismatches=0,
                          native_resolution_schema='yaze.lyra-native-resolution.v1',
                          inspection_only=True, map_assets=observations)
        return bytes(source), document, inspection, terrain_hash


def plan(inputs):
    source, document, inspection, terrain_hash = inputs
    return R.plan_resident_graphics(source, document, inspection,
                                   terrain_sha256=terrain_hash,
                                   provenance=dict(test='real 3bpp fixture'))


def decode4bpp(payload):
    """Independent SNES planar decoder for one emitted tile."""
    return tuple(sum(((payload[(plane // 2) * 16 + y * 2 + plane % 2] >> (7 - x)) & 1)
                     << plane for plane in range(4)) for y in range(8) for x in range(8))


def picture(area, word, frame=0):
    """Read the published bytes and palette, then apply native word flips."""
    char = word & 1023
    if 448 <= char < 480:
        payload = area['animation']['frame_payloads'][frame]
        offset = area['animation']['slots'].index(char) * 32
    else:
        payload = area['static_chr']
        offset = area['static_slots'].index(char) * 32
    pixels = decode4bpp(bytes.fromhex(payload['payload_hex'])[offset:offset + 32])
    palette = area['palette']['words']
    bank = (word >> 10) & 7
    colors = [None if value == 0 else palette[bank * 16 + value] for value in pixels]
    rows = [colors[y * 8:y * 8 + 8] for y in range(8)]
    if word & 0x4000:
        rows = [row[::-1] for row in rows]
    if word & 0x8000:
        rows.reverse()
    return tuple(value for row in rows for value in row)


class ResidentGraphicsTest(unittest.TestCase):
    def test_packing_is_deterministic_and_does_not_clear_resource_refusals(self):
        inputs = Fixture().inputs()
        first = plan(inputs)
        shuffled = copy.deepcopy(inputs)
        shuffled[2]['map_assets'].reverse()
        second = plan(shuffled)
        self.assertEqual(first['areas'], second['areas'])
        self.assertTrue(first['terrain_plan_ready'])
        for key in ('full_residency_ready', 'appearance_coherent', 'allocation_granted',
                    'publication_authorized', 'ordinary_build_ready', 'runtime_admission',
                    'compiled_consumers_verified'):
            self.assertIs(first[key], False, key)
        self.assertIn('active_obj_follower_ancilla_resources', first['unknowns'])
        self.assertIn('mutable_event_tile_closure', first['unknowns'])
        for area in first['areas']:
            self.assertIs(area['full_residency_ready'], False)
            witness = area['witness']
            self.assertEqual(witness['source_colors_sha256'], witness['reconstructed_colors_sha256'])
            for payload in (area['static_chr'], area['palette'], *area['animation']['frame_payloads']):
                raw = bytes.fromhex(payload['payload_hex'])
                self.assertEqual((len(raw), sha(raw)), (payload['byte_count'], payload['sha256']))

    def test_same_tile16_keeps_different_page_pictures(self):
        fixture = Fixture()
        fixture.map_sheets[1][1] = 2
        fixture.sheet_tiles[2][0] = STRIPES
        fixture.palettes[1][33:35] = [0x7C00, 0x7FFF]
        area = plan(fixture.inputs())['areas'][0]
        remaps = [row for row in area['remaps'] if row['quadrant'] == 0]
        self.assertEqual([(row['map_id'], row['tile16_id'], row['source_word']) for row in remaps],
                         [(0xA0, 0, (2 << 10) | 64), (0xA1, 0, (2 << 10) | 64)])
        self.assertNotEqual(remaps[0]['target_word'], remaps[1]['target_word'])
        for remap, source, colors in zip(remaps, (DIAGONAL, STRIPES),
                                        ((0x001F, 0x03E0), (0x7C00, 0x7FFF))):
            expected = tuple(None if value == 0 else colors[value - 1] for value in source)
            self.assertEqual(picture(area, remap['target_word']), expected)

    def test_high_palette_slot_keeps_transparency_and_opaque_black_distinct(self):
        fixture = Fixture((((2 << 10),) * 4,))
        fixture.sheet_tiles[0][0] = DIAGONAL
        for palette in fixture.palettes:
            palette[32], palette[33], palette[34] = 0x1234, 0x001F, 0x03E0
            palette[41], palette[42] = 0, 0x7C00
        area = plan(fixture.inputs())['areas'][0]
        expected = tuple(None if value == 0 else (0 if value == 1 else 0x7C00) for value in DIAGONAL)
        actual = picture(area, area['remaps'][0]['target_word'])
        self.assertEqual(actual, expected)
        self.assertIn(None, actual)
        self.assertIn(0, actual)

    def test_horizontal_vertical_flips_and_priority_survive_remapping(self):
        base = (2 << 10) | 64
        fixture = Fixture(((base, base | 0x6000, base | 0xA000, base | 0xE000),))
        area = plan(fixture.inputs())['areas'][0]
        expected = [None if value == 0 else (0x001F if value == 1 else 0x03E0) for value in DIAGONAL]
        for remap in area['remaps'][:4]:
            word = remap['source_word']
            self.assertEqual(remap['target_word'] & 0xE000, word & 0xE000)
            rows = [expected[y * 8:y * 8 + 8] for y in range(8)]
            if word & 0x4000:
                rows = [row[::-1] for row in rows]
            if word & 0x8000:
                rows.reverse()
            self.assertEqual(picture(area, remap['target_word']), tuple(value for row in rows for value in row))

    def test_three_native_animation_frames_and_static_lower_slot7(self):
        fixture = Fixture((((2 << 10) | 448, (2 << 10) | 480,
                            (2 << 10) | 448, (2 << 10) | 480),))
        fixture.sheet_tiles[8][0] = DIAGONAL
        fixture.sheet_tiles[8][32] = STRIPES
        fixture.sheet_tiles[9][0] = tuple(2 if value == 1 else 1 if value == 2 else 0 for value in DIAGONAL)
        fixture.sheet_tiles[7][32] = (2,) * 64
        area = plan(fixture.inputs())['areas'][0]
        animated, static = area['remaps'][:2]
        self.assertEqual((area['animated_pattern_count'], area['static_pattern_count']), (1, 1))
        self.assertTrue(448 <= animated['target_word'] & 1023 < 480)
        self.assertNotIn(static['target_word'] & 1023, range(448, 480))
        for frame, source in enumerate((DIAGONAL, STRIPES, fixture.sheet_tiles[9][0])):
            expected = tuple(None if value == 0 else (0x001F if value == 1 else 0x03E0) for value in source)
            self.assertEqual(picture(area, animated['target_word'], frame), expected)
        self.assertEqual(picture(area, static['target_word']), (0x03E0,) * 64)
        self.assertEqual(len({payload['sha256'] for payload in area['animation']['frame_payloads']}), 3)

    def test_changed_inspection_hashes_and_bindings_are_rejected(self):
        original = Fixture().inputs()
        changes = (
            (lambda v: v[2].update(source_rom_sha256='0' * 64), 'SOURCE_MISMATCH'),
            (lambda v: v[2].update(terrain_sha256='0' * 64), 'TERRAIN_MISMATCH'),
            (lambda v: v[2]['profile'].update(tile_count=2), 'PROFILE_MISMATCH'),
            (lambda v: v[2]['map_assets'][0].update(current_binding='0' * 64), 'ASSET_BINDING_MISMATCH'),
            (lambda v: v[2]['map_assets'][0]['native_assets']['palette'].update(uint16le_sha256='0' * 64), 'PALETTE_HASH_MISMATCH'),
            (lambda v: v[2]['map_assets'][0]['native_assets']['slots'][1].update(decoded_sheet_sha256='0' * 64), 'SHEET_HASH_MISMATCH'),
            (lambda v: v[2]['map_assets'][0]['native_assets']['animation'].update(decoded_sheet_sha256='0' * 64), 'ANIMATION_HASH_MISMATCH'),
            (lambda v: v[2]['map_assets'][0]['native_assets']['slots'][1].update(sheet_id=2), 'SHEET_SELECTOR_MISMATCH'),
            (lambda v: v[2]['map_assets'][0]['native_assets']['animation'].update(sheet_id=8), 'ANIMATION_SELECTOR_MISMATCH'),
        )
        for change, error in changes:
            bad = copy.deepcopy(original)
            # The producer profile is a distinct JSON object from the document profile.
            bad[2]['profile'] = copy.deepcopy(bad[2]['profile'])
            change(bad)
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, 'RESIDENT_GRAPHICS_' + error):
                plan(bad)

    def test_duplicate_and_missing_state_rows_are_rejected(self):
        inputs = Fixture().inputs()
        for duplicate in (False, True):
            bad = copy.deepcopy(inputs)
            bad[2]['map_assets'].pop()
            if duplicate:
                bad[2]['map_assets'].append(copy.deepcopy(bad[2]['map_assets'][0]))
            error = 'INSPECTION_ROW_DUPLICATE' if duplicate else 'INSPECTION_ROWS_INVALID'
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(ValueError, error):
                plan(bad)

    def test_exhaustion_retains_all_refusals_without_emitting_partial_resources(self):
        fixture = Fixture(tuple(tuple(range(index * 4, index * 4 + 4)) for index in range(128)))
        fixture.map_tiles[0] = fixture.map_tiles[1] = list(range(128)) * 8
        fixture.map_sheets[1] = list(range(10, 18))
        fixture.map_animation[1] = 19
        fixture.sheet_tiles = {sheet: {} for sheet in range(20)}
        for sheet in range(20):
            for index in range(64):
                identity = sheet * 64 + index + 1
                fixture.sheet_tiles[sheet][index] = tuple((identity >> bit) & 1 for bit in range(64))
        for palette in fixture.palettes:
            palette[1] = palette[9] = 0x001F
        result = plan(fixture.inputs())
        area = result['areas'][0]
        self.assertIs(result['terrain_plan_ready'], False)
        self.assertEqual(set(area['refusals']), {'STATIC_NAMESPACE_EXHAUSTED', 'ANIMATION_NAMESPACE_EXHAUSTED'})
        self.assertGreater(area['static_pattern_count'], 480)
        self.assertGreater(area['animated_pattern_count'], 32)
        for key in ('static_chr', 'animation', 'palette', 'witness'):
            self.assertIsNone(area[key], key)
        self.assertEqual(area['remaps'], [])
        self.assertIs(area['full_residency_ready'], False)
        self.assertEqual(area['unknowns'], result['unknowns'])

    def test_palette_budget_and_hud_conflict_are_both_retained(self):
        fixture = Fixture((tuple((bank << 10) | 64 for bank in range(2, 6)),), wide=False)
        members = [0xA0, 0xA1, 0xA8, 0xA9]
        fixture.areas = [dict(parent_map_id=0xA0, size='large', maps=members)] + [
            area for area in fixture.areas if area['parent_map_id'] not in members]
        fixture.sheet_tiles[1][0] = tuple(index % 7 + 1 for index in range(64))
        for number, map_id in enumerate(members):
            palette = fixture.palettes[map_id - 0xA0]
            for bank in range(2, 6):
                for color in range(1, 8):
                    palette[bank * 16 + color] = number * 28 + (bank - 2) * 7 + color
        fixture.palettes[1][0] = 0x7777
        area = plan(fixture.inputs())['areas'][0]
        self.assertEqual(set(area['refusals']), {'TERRAIN_PALETTE_PACKING_UNKNOWN', 'HUD_PALETTE_CONFLICT'})
        self.assertIs(area['terrain_plan_ready'], False)
        self.assertEqual(area['remaps'], [])
        self.assertIsNone(area['static_chr'])
        self.assertIsNone(area['palette'])


class ResidentTransferLifecycleTest(unittest.TestCase):
    """The existing transfer fixture supplies real receipt/context retirement."""

    def setUp(self):
        case = self.case = transfer_cases.CurrentSaveTransferTest(methodName='runTest')
        case.setUp()
        self.addCleanup(case.doCleanups)
        X = transfer_cases.X
        synthetic, document, inspection, _ = Fixture().inputs()
        for row in inspection['map_assets']:
            document.authoring[row['map_id'] - 0xA0]['asset_bindings'][row['state']] = row['current_binding']
            row['stored_binding'] = row['current_binding']
        original = case.rom.read_bytes()
        source = bytearray(original)
        source[:len(synthetic)] = synthetic
        # Keep the established native00-9F census streams and pointer rows.
        for table in X.N.POINTER_TABLES:
            at = X.A.pc(table)
            source[at:at + 160 * 3] = original[at:at + 160 * 3]
        case.rom.write_bytes(source)
        data = dict(schema='yaze.lyra-terrain', schema_version=5, columns=8, rows=4,
                    map_width=32, map_height=32, tile_pixels=16, profile=document.profile,
                    maps=[dict(map_id=0xA0 + index,
                               tiles16=[list(tiles[y * 32:y * 32 + 32]) for y in range(32)],
                               authoring=document.authoring[index])
                          for index, tiles in enumerate(document.maps)],
                    flight_points=[], edge_connections=[], gameplay_areas=list(document.gameplay_areas))
        case.terrain.write_bytes(X.P.encoded(data))
        inspection.update(source_rom_sha256=sha(source), terrain_sha256=sha(case.terrain.read_bytes()),
                          project_descriptor_identity_status='identified',
                          project_descriptor_path=str(case.project),
                          project_descriptor_sha256=sha(case.project.read_bytes()),
                          terrain_path=str(case.terrain))
        self.inspection = case.root / 'inspection.json'
        self.inspection.write_bytes(X.P.encoded(inspection))
        case.producer['source_bindings'].append(X.Q.bound(self.inspection))
        case.producer_path.write_bytes(X.P.encoded(case.producer))
        case.inputs = {key: X.Q.bound(binding['path']) for key, binding in case.inputs.items()}
        case.save['artifacts'] = case.artifacts(case.inputs)
        case.receipt.write_bytes(X.P.encoded(case.save))
        proof = transfer_cases.observation(bytes(source), data)[1]
        proof['terrain_sha256'] = sha(case.terrain.read_bytes())
        case.proof.clear()
        case.proof.update(proof)

    def prepare_review(self, request, output):
        case = self.case
        return transfer_cases.X.P.prepare(output, project=case.project, base_rom=case.rom,
                                         request=request, resident_data=True,
                                         resource_inspection=self.inspection)

    def test_review_writes_exact_unselected_data_and_later_save_retires_transfer(self):
        case, X = self.case, transfer_cases.X
        _, request = case.prepare()
        output = case.root / 'resident-review'
        prepared = self.prepare_review(request, output)
        self.assertEqual(json.loads((output / 'prepare.json').read_bytes()), prepared)
        self.assertIs(prepared['selected'], False)
        self.assertIs(prepared['rom_written'], False)
        self.assertFalse(case.candidate.exists())
        self.assertNotIn('runtime_constants.asm', prepared['generated_files'])
        for name, digest in prepared['generated_files'].items():
            self.assertEqual(sha((output / name).read_bytes()), digest, name)
        plan = prepared['review']['appearance']['resident_graphics']
        area = plan['areas'][0]
        self.assertEqual((output / 'resident/A0/static_chr.bin').read_bytes(),
                         bytes.fromhex(area['static_chr']['payload_hex']))
        self.assertIs(plan['full_residency_ready'], False)
        case.next_save()
        with self.assertRaisesRegex(ValueError, 'retired'):
            X.resident_graphics_plan(request, case.project, case.rom, self.inspection)

    def test_unselected_inspection_and_wrong_descriptor_hash_are_rejected(self):
        case, X = self.case, transfer_cases.X
        # A valid report at a different path is not the selected producer input.
        unselected = case.root / 'unselected-inspection.json'
        unselected.write_bytes(self.inspection.read_bytes())
        _, request = case.prepare()
        with self.assertRaisesRegex(ValueError, 'RESIDENT_INSPECTION_UNBOUND'):
            X.resident_graphics_plan(request, case.project, case.rom, unselected)
        wrong = json.loads(self.inspection.read_bytes())
        wrong['project_descriptor_sha256'] = '0' * 64
        self.inspection.write_bytes(X.P.encoded(wrong))
        case.producer['source_bindings'][-1] = X.Q.bound(self.inspection)
        case.producer_path.write_bytes(X.P.encoded(case.producer))
        case.output = case.root / 'fresh-snapshot'
        _, fresh_request = case.prepare()
        with self.assertRaisesRegex(ValueError, 'RESIDENT_INSPECTION_STALE'):
            X.resident_graphics_plan(fresh_request, case.project, case.rom, self.inspection)
        self.assertFalse(case.candidate.exists())

    def test_save_after_data_write_prevents_completion_marker_and_candidate_rom(self):
        case, X = self.case, transfer_cases.X
        _, request = case.prepare()
        output = case.root / 'interrupted-resident-review'
        write_outputs = X.P.write_outputs

        def save_after_data(folder, files, **kwargs):
            write_outputs(folder, files, **kwargs)
            if 'resident_graphics.json' in files:
                case.next_save()

        with mock.patch.object(X.P, 'write_outputs', side_effect=save_after_data):
            with self.assertRaisesRegex(ValueError, 'retired'):
                self.prepare_review(request, output)
        self.assertTrue((output / 'resident_graphics.json').is_file())
        self.assertFalse((output / 'prepare.json').exists())
        self.assertFalse(case.candidate.exists())


if __name__ == '__main__':
    unittest.main()
