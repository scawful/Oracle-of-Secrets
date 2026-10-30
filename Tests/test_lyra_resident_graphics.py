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

    def test_native_row_capacity_preserves_raw_resources_and_completion_marker(self):
        case = self.case
        _, request = case.prepare()
        output = case.root / 'resident-native-capacity-review'
        # The pure 256-row control below verifies the real capacity boundary.
        # Inject only that exact refusal into the real transfer/publisher lifecycle.
        code = 'RESIDENT_GRAPHICS_NATIVE_ROW_CAPACITY_EXCEEDED'
        with mock.patch.object(R, 'plan_native_resident_abi',
                               side_effect=ValueError(code)) as constructor:
            prepared = self.prepare_review(request, output)
        constructor.assert_called_once()
        self.assertEqual(json.loads((output / 'prepare.json').read_bytes()), prepared)
        self.assertIs(prepared['selected'], False)
        self.assertIs(prepared['ordinary_build_ready'], False)
        self.assertFalse(case.candidate.exists())
        self.assertFalse((output / 'resident_native_abi.json').exists())
        refusal = json.loads((output / 'resident_native_abi_refusal.json').read_bytes())
        self.assertIs(refusal.get('selected'), False)
        self.assertIn(code, json.dumps(refusal))
        for name, digest in prepared['generated_files'].items():
            self.assertEqual(sha((output / name).read_bytes()), digest, name)
        resident = prepared['review']['appearance']['resident_graphics']
        for area in resident['areas']:
            prefix = output / 'resident' / f"{area['parent_map_id']:02X}"
            payloads = {'static_chr.bin': area['static_chr'],
                        'palette.bgr555.bin': area['palette']}
            payloads.update({f'animation-frame{index}.bin': payload
                             for index, payload in enumerate(area['animation']['frame_payloads'])})
            for name, payload in payloads.items():
                self.assertEqual((prefix / name).read_bytes(), bytes.fromhex(payload['payload_hex']))
            self.assertEqual(json.loads((prefix / 'remaps.json').read_bytes()), area['remaps'])


class ResidentNativeAbiTest(unittest.TestCase):
    @staticmethod
    def rehash(value, field):
        value[field] = sha(json.dumps({key: item for key, item in value.items() if key != field},
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode())

    @staticmethod
    def lookup(native, page, tile16, quadrant):
        """Independent consumer of the public two-level byte layout."""
        if not 0xA0 <= page < 0xC0 or not 0 <= tile16 < native['tile16_count']:
            return None
        row = native['pages'][page - 0xA0]
        blobs = {value['label']: bytes.fromhex(value['payload_hex']) for value in native['blobs']}
        index = blobs[row['index_label']]
        block = index[tile16 // 32]
        if not block:
            return None
        entry = index[128 + (block - 1) * 32 + tile16 % 32]
        if not 1 <= entry <= row['row_count']:
            return None
        return struct.unpack_from('<H', blobs[row['words_label']], entry * 8 + quadrant * 2)[0]

    def test_every_page_and_quadrant_round_trips_with_native_zero_valid(self):
        fixture = Fixture(tuple(((2 << 10) | 64,) * 4 for _ in range(4096)))
        fixture.map_tiles[0] = ([31, 32, 4095] * 342)[:1024]
        fixture.map_tiles[1] = [32] * 1024
        resident = plan(fixture.inputs())
        resident['areas'][0]['remaps'][0]['target_word'] = 0
        self.rehash(resident, 'plan_sha256')
        native = R.plan_native_resident_abi(resident, tile16_count=4096)
        R.validate_native_resident_abi(native)
        for area in resident['areas']:
            for remap in area['remaps']:
                self.assertEqual(self.lookup(native, remap['map_id'], remap['tile16_id'],
                                             remap['quadrant']), remap['target_word'])
        self.assertEqual(self.lookup(native, 0xA0, 31, 0), 0)
        for page, tile16 in ((0x9F, 31), (0xC0, 31), (0xA0, 4096), (0xA0, 0),
                             (0xA1, 31), (0xA0, -1)):
            self.assertIsNone(self.lookup(native, page, tile16, 0))
        self.assertEqual([row['map_id'] for row in native['pages']], list(range(0xA0, 0xC0)))
        self.assertEqual(native['abi_version'], 1)
        self.assertEqual(native['directory_stride'], 8)
        self.assertIs(native['consumer_status']['main_chr_staging_implemented'], False)
        self.assertIs(native['consumer_status']['palette_lifecycle_implemented'], False)
        self.assertIs(native['consumer_status']['animation_lifecycle_implemented'], False)
        self.assertIn('mutable_event_tile_closure', native['unknowns'])

    def test_b0_sides_keep_physical_page_keys_and_one_area_resource_owner(self):
        fixture = Fixture()
        members = [0xB0, 0xB1, 0xB8, 0xB9]
        fixture.areas = [row for row in fixture.areas if row['parent_map_id'] not in members]
        fixture.areas.append(dict(parent_map_id=0xB0, size='large', maps=members))
        fixture.map_sheets[0xB1 - 0xA0][1] = 2
        fixture.sheet_tiles[2][0] = STRIPES
        native = R.plan_native_resident_abi(plan(fixture.inputs()), tile16_count=1)
        rows = [native['pages'][page - 0xA0] for page in members]
        self.assertEqual(len({row['area_index'] for row in rows}), 1)
        self.assertNotEqual(self.lookup(native, 0xB0, 0, 0), self.lookup(native, 0xB1, 0, 0))
        self.assertEqual(native['areas'][rows[0]['area_index']]['maps'], members)
        R.validate_native_resident_abi(native)

    def test_identical_lookup_resources_deduplicate_without_losing_page_aliases(self):
        native = R.plan_native_resident_abi(plan(Fixture().inputs()), tile16_count=1)
        self.assertEqual(len({page['index_label'] for page in native['pages']}), 1)
        self.assertEqual(len({page['words_label'] for page in native['pages']}), 1)
        self.assertEqual(len({page['index_alias'] for page in native['pages']}), 32)
        self.assertEqual(native['byte_counts']['page_index'], 160)
        self.assertEqual(native['byte_counts']['page_words'], 16)
        self.assertEqual(native['byte_counts']['page_directory'], 256)
        self.assertEqual(native['unaligned_byte_count'], sum(native['byte_counts'].values()))

    def test_more_than_255_distinct_tile16_rows_refuses_before_emission(self):
        fixture = Fixture(tuple(((2 << 10) | 64,) * 4 for _ in range(256)))
        fixture.map_tiles[0] = list(range(256)) * 4
        with self.assertRaisesRegex(ValueError, 'NATIVE_ROW_CAPACITY_EXCEEDED'):
            R.plan_native_resident_abi(plan(fixture.inputs()), tile16_count=256)

    def test_duplicate_quadrant_or_changed_source_plan_refuses(self):
        resident = plan(Fixture().inputs())
        changed = copy.deepcopy(resident)
        changed['areas'][0]['remaps'][0]['target_word'] ^= 1
        with self.assertRaisesRegex(ValueError, 'NATIVE_SOURCE_PLAN_MISMATCH'):
            R.plan_native_resident_abi(changed, tile16_count=1)
        resident['areas'][0]['remaps'].append(copy.deepcopy(resident['areas'][0]['remaps'][0]))
        self.rehash(resident, 'plan_sha256')
        with self.assertRaisesRegex(ValueError, 'NATIVE_REMAP_DUPLICATE'):
            R.plan_native_resident_abi(resident, tile16_count=1)

    def test_invalid_leaf_and_payload_hash_refuse_independent_validation(self):
        native = R.plan_native_resident_abi(plan(Fixture().inputs()), tile16_count=1)
        index = next(blob for blob in native['blobs'] if blob['role'] == 'page_index')
        raw = bytearray.fromhex(index['payload_hex'])
        raw[128] = 255
        index.update(payload_hex=raw.hex(), sha256=sha(raw))
        self.rehash(native, 'abi_sha256')
        with self.assertRaisesRegex(ValueError, 'NATIVE_ROW_INDEX_INVALID'):
            R.validate_native_resident_abi(native)
        index['sha256'] = '0' * 64
        self.rehash(native, 'abi_sha256')
        with self.assertRaisesRegex(ValueError, 'NATIVE_PAYLOAD_MISMATCH'):
            R.validate_native_resident_abi(native)

    def test_parameterized_emission_binds_every_byte_and_keeps_bank_bounds(self):
        native = R.plan_native_resident_abi(plan(Fixture().inputs()), tile16_count=1)
        emission = R.emit_native_resident_abi(native, data_pc=0x7FF0, capacity=0x20000,
                                             preimage=bytes(0x20000))
        binary = bytes.fromhex(emission['payload_hex'])
        self.assertEqual(emission['payload_sha256'], sha(binary))
        labels = {row['label']: row for row in emission['placements']}
        directory = labels['LyraResidentPageDirectory']
        self.assertEqual(directory['pc'][0], 0x8000)
        for row in emission['placements']:
            self.assertEqual(row['snes'] >> 16, (row['snes'] + row['byte_count'] - 1) >> 16)
            raw = binary[row['binary_offset']:row['binary_offset'] + row['byte_count']]
            self.assertEqual(sha(raw), row['sha256'])
        for offset, page in enumerate(native['pages']):
            raw = binary[offset * 8:offset * 8 + 8]
            self.assertEqual(int.from_bytes(raw[:3], 'little'), labels[page['index_label']]['snes'])
            self.assertEqual(int.from_bytes(raw[3:6], 'little'), labels[page['words_label']]['snes'])
            self.assertEqual(tuple(raw[6:]), (page['area_index'], page['row_count']))
        self.assertNotIn('ENABLED', emission['constants_asm'])
        self.assertNotIn('BOUND', emission['constants_asm'])
        self.assertIn('LyraResidentPageIndex_BF = LyraResidentPageIndex_A0', emission['runtime_data_asm'])
        self.assertIs(emission['allocation_granted'], False)
        with self.assertRaisesRegex(ValueError, 'NATIVE_ALLOCATION_CAPACITY'):
            R.emit_native_resident_abi(native, data_pc=0, capacity=255, preimage=bytes(255))
        with self.assertRaisesRegex(ValueError, 'NATIVE_ORIGIN_PREIMAGE_REQUIRED'):
            R.emit_native_resident_abi(native, data_pc=0, capacity=256, preimage=bytes(255))

    def test_animation_directory_binds_three_sources_per_physical_page(self):
        fixture = Fixture((((2 << 10) | 448,) * 4,))
        native = R.plan_native_resident_abi(plan(fixture.inputs()), tile16_count=1)
        emission = R.emit_native_resident_abi(native, data_pc=0x7D00, capacity=0x20000,
                                             preimage=bytes(0x20000))
        rows = {row['label']: row for row in emission['placements']}
        directory = rows['LyraResidentAnimationDirectory']
        self.assertEqual(directory['byte_count'], 32 * 11)
        self.assertEqual(native['byte_counts']['animation_directory'], 352)
        self.assertEqual(directory['snes'] >> 16, (directory['snes'] + 351) >> 16)
        data = bytes.fromhex(emission['payload_hex'])
        for page in native['pages']:
            at = directory['binary_offset'] + (page['map_id'] - 0xA0) * 11
            area = native['areas'][page['area_index']]
            self.assertEqual(int.from_bytes(data[at + 9:at + 11], 'little'),
                             area['animation_byte_count'])
            for frame, label in enumerate(area['animation_labels']):
                self.assertEqual(int.from_bytes(data[at + frame * 3:at + frame * 3 + 3], 'little'),
                                 rows[label]['snes'])
        empty = R.plan_native_resident_abi(plan(Fixture().inputs()), tile16_count=1)
        emitted = R.emit_native_resident_abi(empty, data_pc=0, capacity=0x20000,
                                            preimage=bytes(0x20000))
        row = next(row for row in emitted['placements'] if row['role'] == 'animation_directory')
        self.assertEqual(bytes.fromhex(emitted['payload_hex'])[row['binary_offset']:
                         row['binary_offset'] + 352], bytes(352))

    def test_runtime_bridge_uses_exact_static_slot_runs_and_external_sources(self):
        resident = plan(Fixture().inputs())
        raw = bytes(range(256)) * 60
        for area in resident['areas']:
            area['static_slots'] = list(R.STATIC_SLOTS)
            area['static_chr'] = dict(payload_hex=raw.hex(), byte_count=len(raw), sha256=sha(raw))
        self.rehash(resident, 'plan_sha256')
        native = R.plan_native_resident_abi(resident, tile16_count=1)
        preimage = bytes(0x20000)
        emission = R.emit_native_resident_abi(native, data_pc=0x300000,
                                             capacity=len(preimage), preimage=preimage)
        bridge = R.resident_runtime_inputs(native, emission, preimage=preimage)
        self.assertEqual(set(bridge['parents']), {str(page) for page in range(0xA0, 0xC0)})
        self.assertEqual(len(bridge['resources']), 1)
        resource = next(iter(bridge['resources'].values()))
        self.assertEqual(resource['sha256'], sha(raw))
        profile = bridge['profiles'][bridge['parents'][str(0xA0)]['profile_id']]
        self.assertEqual(profile['cache_slot_mask'], 255)
        self.assertEqual([row['wram_address'] for row in profile['staging']],
            [0x7F2000, 0x7F2800, 0x7F3000, 0x7F0000, 0x7F0800, 0x7F1000, 0x7F1800, 0x7F3C00])
        self.assertEqual([row['vram_word_address'] for row in profile['normal']],
            [0x2000, 0x2400, 0x2800, 0x2C00, 0x3000, 0x3400, 0x3800, 0x3E00])
        self.assertEqual([row['byte_count'] for row in profile['normal']], [2048] * 7 + [1024])
        self.assertEqual(profile['normal'][-1]['source_offset'], 14336)
        self.assertEqual(profile['transition']['mode'], 'native_staging')
        self.assertIs(bridge['selected'], False)
        self.assertIs(bridge['ordinary_build_ready'], False)

    def test_bridge_rederives_placement_payload_and_complete_preimage(self):
        native = R.plan_native_resident_abi(plan(Fixture().inputs()), tile16_count=1)
        preimage = bytes(0x10000)
        emission = R.emit_native_resident_abi(native, data_pc=0x300000,
                                             capacity=len(preimage), preimage=preimage)
        for mutate in (lambda value: value['placements'][-1].update(snes=0x908000),
                       lambda value: value.update(payload_sha256='0' * 64),
                       lambda value: value.update(selected=True)):
            changed = copy.deepcopy(emission)
            mutate(changed)
            with self.assertRaisesRegex(ValueError, 'NATIVE_EMISSION_MISMATCH'):
                R.resident_runtime_inputs(native, changed, preimage=preimage)
        with self.assertRaisesRegex(ValueError, 'NATIVE_EMISSION_MISMATCH'):
            R.resident_runtime_inputs(native, emission, preimage=bytes([1]) * len(preimage))
        with self.assertRaisesRegex(ValueError, 'NATIVE_ORIGIN_PREIMAGE_REQUIRED'):
            R.resident_runtime_inputs(native, emission, preimage=preimage[:-1])

    def test_rehashed_static_destination_mutant_is_not_a_resident_authority(self):
        native = R.plan_native_resident_abi(plan(Fixture().inputs()), tile16_count=1)
        for field, value in (('wram_address', 0x7F4000), ('vram_word_address', 0x3C00),
                             ('byte_count', 2048), ('native_sheet', 7)):
            changed = copy.deepcopy(native)
            changed['areas'][0]['static_runs'][0][field] = value
            self.rehash(changed, 'abi_sha256')
            with self.assertRaisesRegex(ValueError, 'NATIVE_RESOURCE_LAYOUT_INVALID'):
                R.validate_native_resident_abi(changed)

    def test_derived_bg_rows_cover_shared_area_without_mutating_saved_properties(self):
        fixture = Fixture()
        members = [0xB0, 0xB1, 0xB8, 0xB9]
        fixture.areas = [row for row in fixture.areas if row['parent_map_id'] not in members]
        fixture.areas.append(dict(parent_map_id=0xB0, size='large', maps=members))
        inputs = fixture.inputs()
        properties = copy.deepcopy(inputs[1].properties)
        native = R.plan_native_resident_abi(plan(inputs), tile16_count=1)
        before = copy.deepcopy(native)
        rows = R.resident_bg128_rows(native)
        self.assertEqual([row['map_id'] for row in rows], list(range(0xA0, 0xC0)))
        palettes = {row['map_id']: row['properties']['background_palette'] for row in rows}
        self.assertTrue(all(palettes[page] == palettes[0xB0] for page in members))
        palettes[0xB1][0] ^= 1
        self.assertNotEqual(palettes[0xB1], palettes[0xB0])
        self.assertEqual(inputs[1].properties, properties)
        self.assertEqual(native, before)


class ConditionalDemandTest(unittest.TestCase):
    """Literal native predicates in a synthetic ROM; no game ROM or runtime."""

    def fixture(self, *, wide=True):
        definitions = [((2 << 10) | 64,) * 4 for _ in range(4096)]
        fixture = Fixture(tuple(definitions), wide=wide)
        fixture.sheet_tiles[1][1] = STRIPES
        return fixture

    def inputs(self, fixture, *, native_types=None):
        source, document, inspection, terrain_hash = fixture.inputs()
        source = bytearray(source.ljust(0x200000, b'\0'))
        # Public byte contracts seed a source fixture only. Expected demand
        # families/pages, colors and native door targets are literal below.
        for address, raw in R.CONDITIONAL_NATIVE_PREIMAGES.items():
            at = sheet_table.pc(address)
            source[at:at+len(bytes.fromhex(raw))] = bytes.fromhex(raw)
        # The native reader's operand at008865 is itself the maintained
        # definition pointer. Preserve that real coupling in the fixture.
        definitions = b''.join(struct.pack('<4H', *row) for row in fixture.definitions)
        at = sheet_table.pc(0xBD8000)
        source[at:at+len(definitions)] = definitions
        at = sheet_table.pc(0x0E9459)
        source[at:at+512] = bytes(512)
        source[at+0x183:at+0x186] = bytes.fromhex('515757')
        for char, value in (native_types or {}).items():
            source[at+char] = value
        source = bytes(source)
        inspection['source_rom_sha256'] = sha(source)
        files = [dict(path=path, sha256=sha((ROOT/path).read_bytes()),
                      source_utf8=(ROOT/path).read_bytes().decode('utf-8')) for path in R.CONDITIONAL_SOURCE_FILES]
        preimages = []
        for address, expected in R.CONDITIONAL_NATIVE_PREIMAGES.items():
            size = len(bytes.fromhex(expected))
            raw = source[sheet_table.pc(address):sheet_table.pc(address)+size]
            preimages.append(dict(snes=address, payload_hex=raw.hex(), sha256=sha(raw)))
        native = source[at:at+512]
        preimages.append(dict(snes=0x0E9459, payload_hex=native.hex(), sha256=sha(native)))
        recipe = R._json_bytes({f'{page:02X}': {} for page in range(0xA0, 0xC0)})
        policy = dict(kind=R.CONDITIONAL_POLICY_KIND, source_epoch='1'*40,
            selected_features=dict(ice_rod=True, area_tilesets=False), source_files=files,
            native_preimages=preimages, tail_recipe=dict(
                binding=dict(path='/synthetic/selected-tail-recipe.json', sha256=sha(recipe)),
                payload_hex=recipe.hex()), area_tilesets=None,
            save_identity=dict(transfer_id='2'*64, generation=1, operation_id='synthetic-save',
                source_rom_sha256=sha(source), terrain_sha256=terrain_hash,
                inspection_sha256=sha(R._json_bytes(inspection)),
                document_sha256=R.conditional_document_identity(document)))
        return source, document, inspection, terrain_hash, policy

    def derive(self, inputs):
        source, document, inspection, _, policy = inputs
        return R.derive_conditional_demands(source, document, inspection, source_policy=policy)

    def packed(self, inputs, witness):
        source, document, inspection, terrain_hash, _ = inputs
        return R.plan_resident_graphics(source, document, inspection,
            terrain_sha256=terrain_hash, provenance=dict(test='synthetic conditional source'),
            conditional_demands=witness)

    @staticmethod
    def rehash(value, key='witness_sha256'):
        value[key] = sha(R._json_bytes({name: raw for name, raw in value.items() if name != key}))

    def test_all_native_dig_and_supported_object_ids_derive_without_a_51_row_cap(self):
        fixture = self.fixture()
        triggers = (0x34, 0x71, 0x35, 0x10D, 0x10F, 0xE1, 0xE2, 0xDA, 0xF8, 0x10E,
                    0x36, 0x72A, 0x20F, 0x239, 0x101)
        fixture.map_tiles[0][:len(triggers)] = triggers
        for tiles in fixture.map_tiles[1:]:
            tiles[:2] = [0x34, 0x36]
        witness = self.derive(self.inputs(fixture))
        rows = {row['tile16_id']: row for row in witness['rows'] if row['map_id'] == 0xA0}
        self.assertEqual(set(rows), {0xDC9, 0xDC7, 0xDC8, 0xDCA, 0xDC6})
        self.assertEqual({row['source_tile16_id'] for row in rows[0xDC9]['triggers']}, set(triggers[:10]))
        self.assertEqual({row['source_tile16_id'] for row in rows[0xDCA]['triggers']}, {0x20F, 0x239})
        self.assertEqual(len(witness['additional_rows']), 67)
        for key in ('full_residency_ready', 'appearance_coherent', 'allocation_granted',
                    'publication_authorized', 'ordinary_build_ready', 'runtime_admission',
                    'compiled_consumers_verified', 'resource_closure_verified', 'selected', 'rom_written'):
            self.assertIs(witness[key], False)
        self.assertIn('ice_rod_direct_dma_adapter', witness['unclosed_families'])

    def test_added_quadrants_pack_with_original_colors_and_no_saved_data_mutation(self):
        fixture = self.fixture()
        fixture.map_tiles[0][0] = 0x34
        definitions = list(fixture.definitions)
        definitions[0xDC9] = (0x0840, 0x0841, 0x4840, 0x8841)
        fixture.definitions = tuple(definitions)
        inputs = self.inputs(fixture)
        before = copy.deepcopy(inputs[:4])
        witness = self.derive(inputs)
        result = self.packed(inputs, witness)
        area = next(row for row in result['areas'] if row['parent_map_id'] == 0xA0)
        extra = [row for row in area['remaps'] if row['map_id'] == 0xA0 and row['tile16_id'] == 0xDC9]
        self.assertEqual([row['quadrant'] for row in extra], [0, 1, 2, 3])
        source_area = plan(inputs[:4])['areas'][0]
        # The independent decoder checks every emitted quadrant against a
        # separately packed authored picture of precisely the source word.
        for row in extra:
            reference = self.fixture()
            reference.definitions = ((row['source_word'],) * 4,)
            expected_area = plan(reference.inputs())['areas'][0]
            expected_word = expected_area['remaps'][0]['target_word']
            self.assertEqual(picture(area, row['target_word']), picture(expected_area, expected_word))
        self.assertTrue(result['terrain_plan_ready'])
        self.assertIn('mutable_event_tile_closure', result['unknowns'])
        self.assertFalse(result['full_residency_ready'])
        self.assertEqual(inputs[:4], before)
        self.assertEqual(source_area['maps'], area['maps'])
        native = R.plan_native_resident_abi(result, tile16_count=4096)
        page = next(row for row in native['pages'] if row['map_id'] == 0xA0)
        self.assertIn(0xDC9, page['tile16_ids'])
        self.assertNotIn(0xDC9, next(row for row in native['pages'] if row['map_id'] == 0xA1)['tile16_ids'])

    def test_water_uses_each_quadrant_and_keeps_b0_east_physical_page(self):
        fixture = self.fixture(wide=False)
        fixture.areas = [row for row in fixture.areas if row['parent_map_id'] not in (0xB0, 0xB1)]
        fixture.areas.append(dict(parent_map_id=0xB0, size='wide', maps=[0xB0, 0xB1]))
        definitions = list(fixture.definitions)
        definitions[1] = (0x0840, 0x0840, 0x0840, 0x0841)
        fixture.definitions = tuple(definitions)
        fixture.map_tiles[0xB1-0xA0][7] = 1
        inputs = self.inputs(fixture, native_types={65: 8})
        witness = self.derive(inputs)
        self.assertEqual(witness['additional_rows'], [dict(map_id=0xB1, tile16_id=0xB7)])
        self.assertEqual(witness['rows'][0]['triggers'][0]['eligible_quadrants'], [3])
        result = self.packed(inputs, witness)
        area = next(row for row in result['areas'] if row['parent_map_id'] == 0xB0)
        self.assertTrue(any(row['map_id'] == 0xB1 and row['tile16_id'] == 0xB7 for row in area['remaps']))
        self.assertFalse(any(row['map_id'] == 0xB0 and row['tile16_id'] == 0xB7 for row in area['remaps']))

    def test_ice_source_projects_all_three_type_bytes_without_changing_the_source(self):
        inputs = self.inputs(self.fixture())
        before = inputs[0]
        witness = self.derive(inputs)
        raw = bytearray.fromhex(next(row['payload_hex'] for row in inputs[4]['native_preimages']
                                    if row['snes'] == 0x0E9459))
        raw[0x183:0x186] = bytes.fromhex('0e5757')
        self.assertEqual(witness['native_type_source']['effective_sha256'], sha(raw))
        self.assertEqual(witness['native_type_source']['patches'], [dict(source_path='Items/ice_rod.asm',
            snes=0x0E95DC, before_hex='515757', after_hex='0e5757')])
        self.assertEqual(inputs[0], before)

    def test_door_source_predicates_and_native_neighbor_target_cross_a_page_boundary(self):
        fixture = self.fixture()
        definitions = list(fixture.definitions)
        definitions[0xFB] = (0x0840, 0x00E9, 0x0840, 0x0840)
        definitions[0xFC] = (0x40E9, 0x0840, 0x0840, 0x0840)
        fixture.definitions = tuple(definitions)
        fixture.map_tiles[0][31] = 0xFB
        fixture.map_tiles[1][1] = 0xFC
        witness = self.derive(self.inputs(fixture))
        self.assertEqual(witness['additional_rows'], [dict(map_id=0xA0, tile16_id=0xDA4),
                                                     dict(map_id=0xA1, tile16_id=0xDA6)])
        left, right = witness['rows']
        self.assertEqual({row['target_cell_index'] for row in left['triggers']}, {31})
        self.assertEqual({row['target_cell_index'] for row in right['triggers']}, {0})
        self.assertEqual({row['branch'] for row in left['triggers']},
                         {'current_q1_00E9', 'neighbor_q0_40E9'})

    def test_door_raw_border_and_unsupported_mutation_families_refuse(self):
        for tile_id in (0x37E, 0x21B, 0x36D, 0x36E, 0x374, 0x375,
                        0x23B, 0x23C, 0x23D, 0x23E, 0x226, 0x227, 0x228, 0x229):
            fixture = self.fixture()
            fixture.map_tiles[0][0] = tile_id
            with self.subTest(tile16=tile_id), self.assertRaisesRegex(ValueError, 'CONDITIONAL_UNSUPPORTED_FAMILY'):
                self.derive(self.inputs(fixture))
        fixture = self.fixture()
        definitions = list(fixture.definitions)
        definitions[1] = (0x40E9, 0x0840, 0x0840, 0x0840)
        fixture.definitions = tuple(definitions)
        fixture.map_tiles[0][1] = 1
        with self.assertRaisesRegex(ValueError, 'CONDITIONAL_DOOR_TARGET_OUT_OF_DOMAIN'):
            self.derive(self.inputs(fixture))

    def test_door_queries_exclude_absent_quadrants_but_keep_literal_edge_targets(self):
        cases = (
            ('small', [0xA0], 0x0FBE, 0xA0, 31*32),
            ('wide', [0xA0, 0xA1], 0x0FFE, 0xA0, 0),
            ('tall', [0xA0, 0xA8], 0x1FBE, 0xA8, 31*32),
        )
        for size, members, raw, right_page, right_cell in cases:
            fixture = self.fixture(wide=False)
            fixture.areas = [row for row in fixture.areas if row['parent_map_id'] not in members]
            fixture.areas.append(dict(parent_map_id=0xA0, size=size, maps=members))
            definitions = list(fixture.definitions)
            definitions[0xFB] = (0x0840, 0x00E9, 0x0840, 0x0840)
            fixture.definitions = tuple(definitions)
            fixture.map_tiles[members[-1]-0xA0][1023] = 0xFB
            with self.subTest(size=size):
                witness = self.derive(self.inputs(fixture))
                rows = {(row['map_id'], row['tile16_id']): row for row in witness['rows']}
                self.assertEqual(set(rows), {(members[-1], 0xDA4), (right_page, 0xDA6)})
                left = rows[members[-1], 0xDA4]['triggers']
                right = rows[right_page, 0xDA6]['triggers']
                self.assertEqual([row['native_raw_offset'] for row in left], [raw])
                self.assertEqual([row['native_raw_offset'] for row in right], [raw])
                self.assertEqual(left[0]['target_cell_index'], 1023)
                self.assertEqual(right[0]['target_raw_offset'], raw+2)
                self.assertEqual(right[0]['target_cell_index'], right_cell)
                mask = {'small': 0, 'wide': 1, 'tall': 8}[size]
                self.assertTrue(all((((row['native_raw_offset'] & 0x1000) >> 9)
                    | ((row['native_raw_offset'] & 0x40) >> 6)) & ~mask == 0
                    for row in left+right))

    def test_door_actual_large_area_overflow_still_refuses(self):
        fixture = self.fixture(wide=False)
        members = [0xA0, 0xA1, 0xA8, 0xA9]
        fixture.areas = [row for row in fixture.areas if row['parent_map_id'] not in members]
        fixture.areas.append(dict(parent_map_id=0xA0, size='large', maps=members))
        definitions = list(fixture.definitions)
        definitions[0xFB] = (0x0840, 0x00E9, 0x0840, 0x0840)
        fixture.definitions = tuple(definitions)
        fixture.map_tiles[0xA9-0xA0][1023] = 0xFB
        with self.assertRaisesRegex(ValueError, 'CONDITIONAL_DOOR_TARGET_OUT_OF_DOMAIN'):
            self.derive(self.inputs(fixture))

    def test_repeated_triggers_and_already_authored_targets_do_not_duplicate_rows(self):
        fixture = self.fixture()
        fixture.map_tiles[0][:4] = [0x34, 0x34, 0xE1, 0xDC9]
        inputs = self.inputs(fixture)
        witness = self.derive(inputs)
        self.assertEqual(len(witness['rows']), 1)
        self.assertEqual(len(witness['rows'][0]['triggers']), 3)
        self.assertTrue(witness['rows'][0]['already_authored'])
        self.assertEqual(witness['additional_rows'], [])
        remaps = self.packed(inputs, witness)['areas'][0]['remaps']
        self.assertEqual(len([row for row in remaps if row['map_id'] == 0xA0 and row['tile16_id'] == 0xDC9]), 4)

    def test_rehashed_missing_extra_or_changed_quadrants_are_not_a_witness_authority(self):
        fixture = self.fixture()
        fixture.map_tiles[0][0] = 0x34
        inputs = self.inputs(fixture)
        original = self.derive(inputs)
        for mutation in ('missing', 'extra', 'word', 'generation'):
            witness = copy.deepcopy(original)
            if mutation == 'missing':
                witness['rows'].clear()
            elif mutation == 'extra':
                witness['rows'].append(dict(witness['rows'][0], map_id=0xA1))
            elif mutation == 'word':
                witness['rows'][0]['source_words'][0] ^= 1
            else:
                witness['source_policy']['save_identity']['generation'] += 1
            self.rehash(witness)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'CONDITIONAL_WITNESS_MISMATCH'):
                self.packed(inputs, witness)

    def test_source_native_feature_recipe_and_saved_identity_tampering_refuse(self):
        original = self.inputs(self.fixture())
        for mutation, error in (('source', 'SOURCE_FILE_MISMATCH'), ('native', 'NATIVE_PREIMAGE_MISMATCH'),
                                ('feature', 'FEATURE_SOURCE_MISMATCH'), ('recipe', 'RECIPE_INCOMPLETE'),
                                ('document', 'SAVE_IDENTITY_MISMATCH'), ('area', 'AREA_TYPES_UNQUALIFIED')):
            inputs = copy.deepcopy(original)
            policy = inputs[4]
            if mutation == 'source':
                policy['source_files'][0]['source_utf8'] += ';changed\n'
            elif mutation == 'native':
                row = policy['native_preimages'][0]
                raw = bytearray.fromhex(row['payload_hex']); raw[0] ^= 1
                row.update(payload_hex=raw.hex(), sha256=sha(raw))
            elif mutation == 'feature':
                policy['selected_features']['ice_rod'] = False
            elif mutation == 'recipe':
                raw = R._json_bytes({f'{page:02X}': {} for page in range(0xA1, 0xC0)})
                policy['tail_recipe']['payload_hex'] = raw.hex()
                policy['tail_recipe']['binding']['sha256'] = sha(raw)
            elif mutation == 'document':
                policy['save_identity']['document_sha256'] = '0'*64
            else:
                policy['selected_features']['area_tilesets'] = True
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'CONDITIONAL_' + error):
                self.derive(inputs)


if __name__ == '__main__':
    unittest.main()
