"""Current-reader plans and sparse actual-source CPU/ABI controls.

The CPU fixture has an explicit synthetic phase query. It does not run a SNES,
load graphics, or grant runtime/allocation authority.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Build'))
import lyra_native_loaders as L


class CurrentFullPointerPlanTest(unittest.TestCase):
    def test_four_sizes_and_every_valid_member_resolve_all_native_requests(self):
        table = 0x5B8000
        layout = {r['name']:r for r in L.current_table_layout(table)}
        for parent in range(0xA0,0xC0):
            for code,size in enumerate(('small','large','wide','tall')):
                try:
                    members = L.A.gameplay_area_footprint(parent,size)
                except ValueError:
                    continue
                expected = (members*4 if code == 0 else members if code == 1 else
                            members*2 if code == 2 else (members[0],members[0],members[1],members[1]))
                for base in members:
                    for delta,resolved in zip((0,1,8,9),expected):
                        for plane in ('high','low'):
                            index = (base+delta)*3
                            row = L.current_full_pointer_location(index,map_id=base,parent=parent,
                                area_size=code,table_base=table,plane=plane)
                            self.assertTrue(row['selected'])
                            self.assertEqual(row['resolved_map'],resolved)
                            self.assertEqual(row['address'],layout['map32_'+plane]['snes']+resolved*3)
                            self.assertEqual(row['original_index'],index)

    def test_native160_full_loads_keep_original_operands_even_for_tail_quad_indices(self):
        for base in range(160):
            for delta in (0,1,8,9):
                for plane,original in (('high',0x02F94D),('low',0x02FB2D)):
                    index = (base+delta)*3
                    row = L.current_full_pointer_location(index,map_id=base,table_base=0x5B8000,plane=plane)
                    self.assertFalse(row['selected'])
                    self.assertEqual(row['address'],original+index)

    def test_original_selector_control_exposes_bf_spill_and_native_base_alias(self):
        # Original current source selected by requested X alone.
        self.assertFalse(L.current_pointer_location(0xC8*3,table_base=0x5B8000,plane='high')['selected'])
        fixed = L.current_full_pointer_location(0xC8*3,map_id=0xBF,parent=0xBF,area_size=0,
                                                table_base=0x5B8000,plane='high')
        self.assertEqual((fixed['selected'],fixed['resolved_map']),(True,0xBF))
        self.assertTrue(L.current_pointer_location(0xA0*3,table_base=0x5B8000,plane='high')['selected'])
        fixed = L.current_full_pointer_location(0xA0*3,map_id=0x9F,table_base=0x5B8000,plane='high')
        self.assertFalse(fixed['selected'])
        # Sub-overlay requests intentionally remain independent physical pages.
        self.assertTrue(L.current_pointer_location(0xBF*3,table_base=0x5B8000,plane='low')['selected'])

    def test_invalid_indices_and_unowned_parent_shapes_refuse(self):
        for index in (0xFFFF,0xA0*3+1):
            self.assertFalse(L.current_full_pointer_location(index,map_id=0xA0,parent=0xA0,
                area_size=0,table_base=0x5B8000,plane='low')['selected'])
        with self.assertRaisesRegex(ValueError,'does not own'):
            L.current_full_pointer_location(0xA1*3,map_id=0xA1,parent=0xA0,area_size=0,
                                            table_base=0x5B8000,plane='high')


class CurrentNativeLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = bytes(range(256)) * 8192
        # Host fixture addresses only. These do not declare production ownership.
        cls.origins = dict(table_base=0x5B8000, code_base=0x5CC000,
                           code_end=0x5CE000, descriptor_base=0x5CF000)
        cls.policy = dict(source_rom_sha256=hashlib.sha256(cls.source).hexdigest(),
                          source_profile_sha256='17' * 32,
                          allocation_granted=False, publication_authorized=False)
        cls.rows = {}
        for area in range(0xA0, 0xC0):
            values = {}
            for ordinal, (name, _, _, _, stride) in enumerate(L.CURRENT_TABLE_SPECS):
                value = (ordinal * 17 + area) % (1 << (8 * stride))
                if stride == 8:
                    value = [(area + slot) & 255 for slot in range(8)]
                elif name == 'parent':
                    value = area
                elif name == 'area_size':
                    value = 0
                elif name.startswith('map32_'):
                    value = 0x238000 + (area - 0xA0) * 0x200
                values[name] = value
            cls.rows[area] = values
        cls.plan = L.plan_current_tables(cls.source, cls.rows,
                                        origins=cls.origins, policy=cls.policy)

    def plan_with(self, *, source=None, rows=None, origins=None, policy=None):
        return L.plan_current_tables(self.source if source is None else source,
                                    self.rows if rows is None else rows,
                                    origins=self.origins if origins is None else origins,
                                    policy=self.policy if policy is None else policy)

    def test_complete_families_copy_actual_native_sections(self):
        self.assertEqual(len(self.plan['tables']), len(L.A.SPECS) + 8)
        for row in self.plan['tables']:
            raw = bytes.fromhex(row['payload_hex'])
            self.assertEqual(row['rows'], 192)
            self.assertEqual(len(raw), 192 * row['stride'])
            at = L.A.pc(row['legacy_snes'])
            size = row['legacy_rows'] * row['stride']
            first = row['legacy_first'] * row['stride']
            self.assertEqual(raw[first:first + size], self.source[at:at + size], row['name'])
            if row['legacy_first']:
                self.assertEqual(raw[:first], bytes(first))
                self.assertEqual(row['structural_unmapped_prefix_rows'], row['legacy_first'])
            if row['name'].startswith('music_phase'):
                old = L.A.pc(0x02C403)
                self.assertEqual(raw[64:160], self.source[old:old + 96])

    def test_all_explicit_tail_values_survive_including_both_endpoints(self):
        for area in (0xA0, 0xA1, 0xBF):
            for row in self.plan['tables']:
                stride = row['stride']
                raw = bytes.fromhex(row['payload_hex'])[area * stride:(area + 1) * stride]
                value = self.rows[area][row['name']]
                expected = bytes(value) if stride == 8 else value.to_bytes(stride, 'little')
                self.assertEqual(raw, expected, (area, row['name']))

    def test_phase_and_pointer_families_have_disjoint_full_extents(self):
        rows = {r['name']: r for r in self.plan['tables']}
        for names in (('sprite_phase0', 'sprite_phase1', 'sprite_phase2'),
                      ('map32_high', 'map32_low'),
                      tuple(f'music_phase{i}' for i in range(4)),
                      ('special_sprite_gfx', 'special_sprite_gfx_phase1', 'special_sprite_gfx_phase2'),
                      ('special_sprite_palettes', 'special_sprite_palettes_phase1', 'special_sprite_palettes_phase2')):
            intervals = [rows[n]['pc'] for n in names]
            for i, (a, b) in enumerate(intervals):
                for c, d in intervals[i + 1:]:
                    self.assertTrue(b <= c or a >= d)
        self.assertEqual(rows['map32_high']['pc'][1] - rows['map32_high']['pc'][0], 192 * 3)
        for area in (0xA0, 0xA1, 0xBF):
            values = [bytes.fromhex(rows[f'music_phase{i}']['payload_hex'])[area] for i in range(4)]
            self.assertEqual(len(set(values)), 4)

    def test_sprite_phase_families_append_without_moving_legacy_tables(self):
        rows = self.plan['tables']
        old_specs = tuple((s[0], s[1], s[2], s[3], s[5]) for s in L.A.SPECS) + tuple(
            (f'music_phase{i}', 0x02C303 + i * 0x40, 0x40, 0, 1) for i in range(4))
        offset = 0
        for row, spec in zip(rows, old_specs):
            self.assertEqual((row['name'], row['offset']), (spec[0], offset))
            offset += 192 * spec[4]
        self.assertEqual([r['name'] for r in rows[len(old_specs):]],
                         ['special_sprite_gfx_phase1', 'special_sprite_palettes_phase1',
                          'special_sprite_palettes_phase2', 'special_sprite_gfx_phase2'])

    def test_sprite_phase_indices_change_only_selected_tail_families(self):
        tables = {r['name']: r for r in self.plan['tables']}
        for name, family, bias in (
                ('SpriteGfxByArea', 'special_sprite_gfx', 0),
                ('SpecialSpriteGfx', 'special_sprite_gfx', 128),
                ('SpritePalette', 'special_sprite_palettes', 0),
                ('SpecialPalette', 'special_sprite_palettes', 128)):
            for phase in range(3):
                selected = family + (f'_phase{phase}' if phase else '')
                for area in (0xA0, 0xB0, 0xBF):
                    row = L.current_selector_location(name, area-bias,
                        table_base=self.origins['table_base'], placement_phase=phase)
                    self.assertEqual((row['family'], row['address']),
                                     (selected, tables[selected]['snes']+area))
                control = L.current_selector_location(name, 0x9F-bias,
                    table_base=self.origins['table_base'], placement_phase=phase)
                self.assertFalse(control['selected'])
                self.assertEqual(control['family'], family)
        for phase in (-1, 3, True):
            with self.assertRaisesRegex(ValueError, 'placement phase'):
                L.current_selector_location('SpritePalette', 0xB0,
                    table_base=self.origins['table_base'], placement_phase=phase)

    def test_original160_selector_fallbacks_and_tail_index_conversions(self):
        table = {r['name']: r for r in self.plan['tables']}
        for row in L.CURRENT_SELECTORS:
            name, family, old, reg, _, _, _ = row
            special = name in ('SpecialPalette', 'SpecialSpriteGfx', 'SpecialEntryGfx')
            scale = 8 if family == 'gfx' else table[family]['stride']
            bias = 128 if special else 0
            for area in range(bias, 160):
                index = (area - bias) * scale
                got = L.current_selector_location(name, index, table_base=self.origins['table_base'])
                self.assertFalse(got['selected'], (name, area))
                expected = old + index if reg == 'X' else 0x280000 + (old & 0xFFFF) + index
                self.assertEqual(got['address'], expected)
            for area in (0xA0, 0xA1, 0xBF):
                index = (area - bias) * scale
                got = L.current_selector_location(name, index, table_base=self.origins['table_base'])
                self.assertTrue(got['selected'])
                slot = int(name[-1]) if family == 'gfx' else 0
                self.assertEqual(got['address'], table[family]['snes'] + area * scale + slot)
            for index in ((192 - bias) * scale, 0xFFFF):
                self.assertFalse(L.current_selector_location(
                    name, index, table_base=self.origins['table_base'])['selected'])

    def test_full_and_sub_pointer_domain_uses_actual_triplet_index(self):
        for plane, original in (('high', 0x02F94D), ('low', 0x02FB2D)):
            for area in range(160):
                got = L.current_pointer_location(area * 3, table_base=self.origins['table_base'], plane=plane)
                self.assertFalse(got['selected'])
                self.assertEqual(got['address'], original + area * 3)
            for area in (160, 161, 191):
                got = L.current_pointer_location(area * 3, table_base=self.origins['table_base'], plane=plane)
                self.assertTrue(got['selected'])
            self.assertFalse(L.current_pointer_location(192 * 3,
                table_base=self.origins['table_base'], plane=plane)['selected'])

    def test_missing_or_extra_map_and_missing_family_are_refused(self):
        for bad in (159, 192, True):
            rows = copy.deepcopy(self.rows)
            rows[bad] = rows.pop(160)
            with self.assertRaisesRegex(ValueError, 'all32'):
                self.plan_with(rows=rows)
        rows = copy.deepcopy(self.rows)
        del rows[191]['sprite_phase2']
        with self.assertRaisesRegex(ValueError, 'every explicit table family'):
            self.plan_with(rows=rows)

    def test_invalid_tail_values_are_not_normalized(self):
        for name, value in (('animated', True), ('parent', 192), ('area_size', 4),
                            ('sprite_phase1', -1), ('sprite_phase2', 65536),
                            ('gfx', [True] * 8), ('map32_low', 0x7E8000)):
            rows = copy.deepcopy(self.rows)
            rows[160][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                self.plan_with(rows=rows)

    def test_explicit_rom_origins_and_nonoverlap_are_required(self):
        for key, value in (('table_base', None), ('table_base', 0x7E8000),
                           ('table_base', 0x5BF000), ('code_base', True),
                           ('code_end', 0x5D8100), ('descriptor_base', 0x5CC000),
                           ('descriptor_base', 0x5CFFF0)):
            origins = dict(self.origins, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.plan_with(origins=origins)

    def test_source_and_authority_mutants_are_refused(self):
        changed = self.source[:-1] + bytes([self.source[-1] ^ 1])
        with self.assertRaisesRegex(ValueError, 'source/profile'):
            self.plan_with(source=changed)
        for key, value in (('source_profile_sha256', 'x' * 64),
                           ('source_profile_sha256', False), ('allocation_granted', True),
                           ('publication_authorized', True), ('allocation_granted', 0),
                           ('ordinary_build_ready', True), ('runtime_admission', True),
                           ('activation', True), ('producer_enforcement_verified', True)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.plan_with(policy=dict(self.policy, **{key: value}))

    def test_no_historical_authority_or_output_writer_is_called(self):
        with mock.patch.object(L.R, 'reservation_claim', side_effect=AssertionError('historical ledger')):
            with mock.patch.object(Path, 'write_bytes', side_effect=AssertionError('file writer')):
                with mock.patch.object(Path, 'write_text', side_effect=AssertionError('file writer')):
                    plan = self.plan_with()
        for key in ('allocation_granted', 'producer_enforcement_verified', 'publication_authorized',
                    'ordinary_build_ready', 'runtime_admission', 'actors_compiled', 'rom_written'):
            self.assertIs(plan[key], False)
        self.assertIs(plan['current_code_fit_verified'], False)

    def test_source_plan_has_separate_constants_data_and_descriptor(self):
        plan = self.plan
        self.assertEqual(plan['tables_pc'][1] - plan['tables_pc'][0], plan['tables_bytes'])
        self.assertEqual(plan['descriptor_pc'][1] - plan['descriptor_pc'][0], 64)
        self.assertEqual(bytes.fromhex(plan['descriptor_hex'])[:8], b'LYC1\x01\xa0\xc0\xc0')
        for family in ('sprite_phase0', 'sprite_phase2', 'map32_high', 'map32_low', 'music_phase3'):
            self.assertIn('!LYRA_CURRENT_TABLE_' + family + ' = ', plan['constants_assembler'])
            self.assertIn('Lyra_CurrentTable_' + family + ':', plan['tables_assembler'])
        self.assertNotIn('!LYRA_CURRENT_MODE = 1', plan['assembler'])
        self.assertIn('org !LYRA_CURRENT_DESCRIPTOR_BASE', plan['descriptor_assembler'])

    def test_historical_asm_and_python_constructor_source_are_verbatim(self):
        root = Path(__file__).resolve().parents[1]
        asm = (root / 'Overworld/lyra_native_loaders.asm').read_bytes()
        original = asm.split(b'; BEGIN HISTORICAL NATIVE READERS (verbatim405 source)\n', 1)[1]
        original = original.split(b'; END HISTORICAL NATIVE READERS\n', 1)[0]
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         'd80f2195b21dc6ca2cc2e67775148a4411c53ae9de246c5d17d2e40f25138bd8')
        py = (root / 'Scripts/Build/lyra_native_loaders.py').read_bytes()
        historical = py.split(b'\n\n# Current-engine mode is a separate', 1)[0] + b'\n'
        self.assertEqual(hashlib.sha256(historical).hexdigest(),
                         '0700b57cfa3b594160c63d46ecff6dfbcc40b518ead16ff114b01ba64da7c97d')


class CurrentHiddenStreamsInspectorTest(unittest.TestCase):
    """Synthetic byte windows exercise the real optional compiled inspector."""
    @staticmethod
    def fixture():
        compiled = bytearray(0x400000)
        helper = 0xE0CDCE
        labels = dict(Lyra_CurrentNativeCodeStart=0xE0C000,
            Lyra_CurrentNativeCodeEnd=helper+25, Lyra_HiddenStreamsBank=helper,
            Lyra_HiddenStreamsBank_End=helper+25, LyraCall_HiddenStreamsBank=0x1BC8BE,
            Lyra_HiddenStreamsGuard=0x1BC8B1)
        for site, raw in ((helper, L.CURRENT_HIDDEN_STREAMS_BANK_BYTES),
                (0x1BC8BE, b'\x22'+helper.to_bytes(3, 'little')+b'\xea'),
                (0x1BC8B1, L.CURRENT_HIDDEN_STREAMS_GUARD_BYTES)):
            compiled[L.A.pc(site):L.A.pc(site)+len(raw)] = raw
        return compiled, labels

    def test_optional_off_is_absent_and_required_or_partial_binding_refuses(self):
        self.assertIsNone(L.inspect_current_hidden_streams_adapter(b'', {}))
        with self.assertRaisesRegex(ValueError, 'COMPILED_BINDING_REQUIRED'):
            L.inspect_current_hidden_streams_adapter(b'', {}, required=True)
        for required in (0, 1, None):
            with self.subTest(required=required), self.assertRaisesRegex(ValueError, 'SELECTION_INVALID'):
                L.inspect_current_hidden_streams_adapter(b'', {}, required=required)
        compiled, labels = self.fixture()
        for name in ('Lyra_HiddenStreamsBank', 'Lyra_HiddenStreamsBank_End',
                     'LyraCall_HiddenStreamsBank', 'Lyra_HiddenStreamsGuard'):
            with self.subTest(missing=name), self.assertRaisesRegex(ValueError, 'SYMBOLS_INCOMPLETE'):
                L.inspect_current_hidden_streams_adapter(compiled,
                    {k:v for k,v in labels.items() if k != name})

    def test_exact_selected_binding_reports_only_the_bank_adapter(self):
        compiled, labels = self.fixture()
        result = L.inspect_current_hidden_streams_adapter(compiled, labels, required=True)
        self.assertEqual(result['helper_snes'], [0xE0CDCE, 0xE0CDE7])
        self.assertEqual((result['native_bank'], result['tail_bank']), (0x9B, 0xE3))
        self.assertEqual(result['physical_selector_dp'], 0x8A)
        self.assertEqual(result['tail_stream_snes'], [0xE38000, 0xE40000])
        self.assertEqual(result['scope'], 'bank_selection_only')
        self.assertIs(result['pickup_state_implemented'], False)

    def test_wrong_native_bank_tail_bank_guard_hook_or_helper_owner_refuses(self):
        compiled, labels = self.fixture()
        for offset in (0, 2, 5, 10, 13, 16, 20, 23, 24):
            changed = bytearray(compiled)
            changed[L.A.pc(labels['Lyra_HiddenStreamsBank'])+offset] ^= 1
            with self.subTest(helper_byte=offset), self.assertRaisesRegex(ValueError, 'HELPER_BODY'):
                L.inspect_current_hidden_streams_adapter(changed, labels)
        for site, failure in ((0x1BC8B1, 'PREACCESS_GUARD'), (0x1BC8BE, 'BANK_HOOK')):
            changed = bytearray(compiled)
            changed[L.A.pc(site)+1] ^= 1
            with self.subTest(site=site), self.assertRaisesRegex(ValueError, failure):
                L.inspect_current_hidden_streams_adapter(changed, labels)
        for name, value in (('Lyra_CurrentNativeCodeStart', 0xF88600),
                            ('Lyra_CurrentNativeCodeEnd', 0xE0D001),
                            ('Lyra_HiddenStreamsBank_End', 0xE0CDE8)):
            with self.subTest(symbol=name), self.assertRaisesRegex(ValueError, 'HELPER_EXTENT'):
                L.inspect_current_hidden_streams_adapter(compiled, dict(labels, **{name:value}))


class CurrentHiddenStreamsCpuTest(unittest.TestCase):
    """Sparse actual-source CPU checks; synthetic continuations are not gameplay.

    An explicit LYRA_HIDDEN_STREAMS_CPU_OUTPUT directory retains every fixture
    under the coordinator's selected private evidence root. Nothing runs on
    import, and ordinary test runs without this opt-in write no ROM.
    """
    @classmethod
    def setUpClass(cls):
        output = os.environ.get('LYRA_HIDDEN_STREAMS_CPU_OUTPUT')
        cls.asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        cls.runner = os.environ.get('OOS_CPU_RUNNER')
        if not output or not cls.asar or not cls.runner:
            raise unittest.SkipTest('Select LYRA_HIDDEN_STREAMS_CPU_OUTPUT, ASAR_BIN and OOS_CPU_RUNNER')
        root = Path(__file__).resolve().parents[1]
        cls.folder = Path(output).absolute()
        if (cls.folder.exists() or cls.folder.resolve() != cls.folder
                or cls.folder.is_relative_to(root) or root.is_relative_to(cls.folder)):
            raise AssertionError('Hidden-stream CPU output must be new, external and canonical')
        native = (root/'Overworld/lyra_native_loaders.asm').read_text()
        zsc = (root/'Overworld/ZSCustomOverworld.asm').read_text()
        cls.validation = native.split('if not(defined("LYRA_CURRENT_HIDDEN_STREAMS_BOUND"))', 1)[1]
        cls.validation = 'if not(defined("LYRA_CURRENT_HIDDEN_STREAMS_BOUND"))'+cls.validation.split(
            'if !LyraNativeCurrentBranch == 1', 1)[0]
        cls.helper = native[native.index('if !LYRA_CURRENT_HIDDEN_STREAMS_BOUND == 1\nLyra_HiddenStreamsBank:'):
                            native.index('Lyra_CurrentNativeCodeEnd:')]
        cls.guard = zsc.split('; BEGIN CURRENT HIDDEN STREAM GUARD\n', 1)[1].split(
            '; END CURRENT HIDDEN STREAM GUARD', 1)[0]
        cls.bank_hook = native.split('; BEGIN CURRENT HIDDEN STREAM BANK HOOK\n', 1)[1].split(
            '; END CURRENT HIDDEN STREAM BANK HOOK', 1)[0]
        cls.constants = ('!LyraNativeCurrentBranch = 1\n!LYRA_CURRENT_MODE = 1\n'
            '!LYRA_CURRENT_HIDDEN_STREAMS_BOUND = 1\n!LYRA_CURRENT_HIDDEN_STREAMS_BANK = $E3\n'
            '!LYRA_CURRENT_HIDDEN_STREAMS_BASE = $E38000\n!LYRA_CURRENT_HIDDEN_STREAMS_END = $E40000\n')
        seed = bytearray(0x400000)
        def put(site, raw):
            seed[L.A.pc(site):L.A.pc(site)+len(raw)] = raw
        # Original saved preimages; only the two maintained hook blocks patch them.
        put(0x1BC8B1, bytes.fromhex('c98000b07d0aaabf84a7828500a99b008502'))
        put(0x1BC8C3, b'\x6b')  # Synthetic valid continuation returns to the runner.
        put(0x1BC933, b'\x18\x6b')  # Synthetic native no-match CLC/RTL continuation.
        cls.directory = b''.join((0x8000+i*3).to_bytes(2, 'little') for i in range(192))
        put(0x82A784, cls.directory)
        cls.native_data = bytes((i*7+3)&255 for i in range(0x2000))
        put(0x9B8000, cls.native_data)
        cls.seed = bytes(seed)
        cls.folder.mkdir(parents=True)
        cls.image, result = cls.assemble('enabled', cls.constants)
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        cls.labels = L._labels(cls.image.with_suffix('.sym').read_bytes())

    @classmethod
    def assemble(cls, name, constants, *, seed=None):
        image, driver = cls.folder/(name+'.sfc'), cls.folder/(name+'.asm')
        image.write_bytes(cls.seed if seed is None else seed)
        driver.write_text('lorom\n'+constants+cls.validation+'\norg $E0CDCE\n'+cls.helper+
                          cls.guard+cls.bank_hook)
        result = subprocess.run([cls.asar, '--no-title-check', '--fix-checksum=off',
            '--symbols=wla', str(driver), str(image)], capture_output=True, text=True, timeout=20)
        (cls.folder/(name+'-asar.log')).write_text(result.stdout+result.stderr)
        return image, result

    def run_cpu(self, name, requests):
        raw = ''.join(json.dumps(row)+'\n' for row in requests)
        (self.folder/(name+'-requests.jsonl')).write_text(raw)
        result = subprocess.run([self.runner, str(self.image)], input=raw,
                                capture_output=True, text=True, timeout=20)
        (self.folder/(name+'-results.jsonl')).write_text(result.stdout)
        (self.folder/(name+'-stderr.log')).write_text(result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows), len(requests))
        return rows

    def test_unbound_disabled_invalid_flag_mode_and_bank_origin_controls(self):
        for name, constants in (('disabled', self.constants.replace('BOUND = 1', 'BOUND = 0')),
                                ('undefined', '!LyraNativeCurrentBranch = 0\n')):
            image, result = self.assemble(name, constants)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            expected = bytearray(self.seed)
            expected[L.A.pc(0x1BC8B4):L.A.pc(0x1BC8B6)] = b'\xea\xea'
            self.assertEqual(image.read_bytes(), bytes(expected))
        for name, constants in (
                ('flag', self.constants.replace('BOUND = 1', 'BOUND = 2')),
                ('mode', self.constants.replace('LyraNativeCurrentBranch = 1', 'LyraNativeCurrentBranch = 0')),
                ('missing-bank', self.constants.replace('!LYRA_CURRENT_HIDDEN_STREAMS_BANK = $E3\n', '')),
                ('bank', self.constants.replace('BANK = $E3', 'BANK = $9B')),
                ('base', self.constants.replace('BASE = $E38000', 'BASE = $E38001')),
                ('end', self.constants.replace('END = $E40000', 'END = $E48000'))):
            with self.subTest(gate=name):
                _, result = self.assemble(name, constants)
                self.assertNotEqual(result.returncode, 0)
        legacy = bytearray(self.seed)
        at = L.A.pc(0x1BC8B4)
        legacy[at:at+2] = b'\xea\xea'
        image, result = self.assemble('enabled-legacy-nops', self.constants, seed=bytes(legacy))
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(image.read_bytes(), self.image.read_bytes())
        guard = L.A.pc(0x1BC8B1)
        self.assertEqual(image.read_bytes()[guard:guard+5], L.CURRENT_HIDDEN_STREAMS_GUARD_BYTES)
        for name, branch in (('unknown-zero-branch', b'\x00\x00'),
                             ('unknown-displacement', b'\xb0\x7c')):
            changed = bytearray(self.seed)
            changed[at:at+2] = branch
            with self.subTest(preimage=name):
                _, result = self.assemble(name, self.constants, seed=bytes(changed))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Hidden item native no-match branch moved', result.stdout+result.stderr)

    def test_helper_preserves_abi_scratch_and_resets_native_after_tail(self):
        contexts, requests = [], []
        for raw in (0, 0x7F, 0x80, 0x9F, 0xA0, 0xBF, 0xC0, 0x0100, 0x8000, 0xFFFF):
            for p in (0, 1, 0x40, 0x41, 0x08, 0x49, 0x82, 0xCB):
                d = 0x120 if p&1 else 0
                regs = dict(a=0xABCD, x=0x4567, y=0x7654, p=p, db=8, d=d, sp=0x1FFF)
                values = {d:0xA55A, d+2:0xFEFF, d+4:0xBCDE, d+0x8A:raw,
                          0x040A:0x9F if raw == 0xA0 else 0xA0}
                requests.append(dict(entry=self.labels['Lyra_HiddenStreamsBank'], reset_ram=True,
                    registers=regs, writes=[dict(address=0x7E0000+at, bytes=list(value.to_bytes(2, 'little')))
                                           for at,value in values.items()],
                    reads=[dict(address=0x7E0000+at, length=2) for at in values],
                    trace_writes=True, max_steps=50))
                contexts.append((raw, regs, values))
        # Keep DP02 from the previous call, so a native lookup must actively reset E3 to9B.
        for i, raw in enumerate((0xA0, 0x9F, 0xBF, 0, 0xC0)):
            regs = dict(a=0x9876, x=0x4567, y=0x7654, p=0x41, db=0x7E, d=0, sp=0x1FFF)
            values = {0:0xA55A, 4:0xBCDE, 0x8A:raw, 0x040A:0xA0}
            requests.append(dict(entry=self.labels['Lyra_HiddenStreamsBank'], reset_ram=i == 0,
                registers=regs, writes=[dict(address=0x7E0000+at, bytes=list(value.to_bytes(2, 'little')))
                                       for at,value in values.items()],
                reads=[dict(address=0x7E0000+at, length=2) for at in (0, 2, 4, 0x8A, 0x040A)],
                trace_writes=True, max_steps=50))
            contexts.append((raw, regs, values))
        for (raw, regs, values), row in zip(contexts, self.run_cpu('helper', requests)):
            with self.subTest(raw=raw, p=regs['p'], d=regs['d']):
                self.assertTrue(row['returned'], row)
                self.assertFalse(row.get('stub_calls'))
                self.assertFalse(row.get('mmio_writes'))
                expected = 0xE3 if 0xA0 <= raw < 0xC0 else 0x9B
                cpu = row['registers']
                self.assertEqual(cpu['a'], expected)
                self.assertEqual(cpu['p'], regs['p']&~0x82)
                for name in ('x', 'y', 'db', 'd', 'sp'):
                    self.assertEqual(cpu[name], regs[name])
                observed = {read['address']&65535:int.from_bytes(bytes(read['bytes']), 'little')
                            for read in row['reads']}
                self.assertEqual(observed[regs['d']+2], expected)
                for at,value in values.items():
                    if at != regs['d']+2:
                        self.assertEqual(observed[at], value)
                allowed = {regs['d']+2, regs['d']+3} | set(range(0x1F80, 0x2000))
                for write in row['writes']:
                    self.assertIn(write['address']&65535, allowed)

    def test_preaccess_guard_rejects_fullword_aliases_and_native_regions_are_unchanged(self):
        requests, values = [], []
        checkpoints = [0x1BC8B6, 0x1BC8B8, 0x1BC8BE]
        for raw in (0, 0x9F, 0xA0, 0xBF, 0xC0, 0x0100, 0xFFFF):
            requests.append(dict(entry=0x1BC8B1, reset_ram=True,
                registers=dict(a=raw, x=0x7777, y=0x7654, p=0x41, db=8, d=0, sp=0x1FFF),
                writes=[dict(address=0x7E0000, bytes=list(bytes.fromhex('5aa5effedebc'))),
                        dict(address=0x7E008A, bytes=list(raw.to_bytes(2, 'little'))),
                        dict(address=0x7E040A, bytes=[0xA0, 0])],
                reads=[dict(address=0x7E0000, length=6)], checkpoints=checkpoints,
                trace_writes=True, max_steps=100))
            values.append(raw)
        for raw, row in zip(values, self.run_cpu('guard', requests)):
            with self.subTest(raw=raw):
                self.assertTrue(row['returned'], row)
                observed = bytes(row['reads'][0]['bytes'])
                hits = [hit['address'] for hit in row['checkpoint_trace']]
                if raw >= 0xC0:
                    self.assertEqual(hits, [], 'Invalid selector reached the table/bank path')
                    self.assertEqual(observed, bytes.fromhex('5aa5effedebc'))
                    self.assertEqual(row['registers']['x'], 0x7777)
                    self.assertEqual(row['registers']['p']&1, 0)
                else:
                    self.assertEqual(hits, checkpoints, 'Valid control must traverse every checkpoint')
                    self.assertEqual(int.from_bytes(observed[:2], 'little'), 0x8000+raw*3)
                    self.assertEqual(int.from_bytes(observed[2:4], 'little'), 0xE3 if raw >= 0xA0 else 0x9B)
                    self.assertEqual(observed[4:], bytes.fromhex('debc'))
        compiled = self.image.read_bytes()
        self.assertEqual(compiled[L.A.pc(0x82A784):L.A.pc(0x82A784)+320], self.directory[:320])
        self.assertEqual(compiled[L.A.pc(0x9B8000):L.A.pc(0x9B8000)+len(self.native_data)], self.native_data)


class CurrentSpritePhaseCpuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        runner = os.environ.get('OOS_CPU_RUNNER')
        if not asar or not runner:
            raise unittest.SkipTest('Set ASAR_BIN and OOS_CPU_RUNNER for sparse reader CPU checks')
        cls.runner = runner
        cls.folder = tempfile.TemporaryDirectory(prefix='lyra-sprite-readers-')
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        cls.image = folder/'readers.sfc'
        root = Path(__file__).resolve().parents[1]
        native = (root/'Overworld/lyra_native_loaders.asm').read_text()
        start = native.index('macro LyraCurrentSpriteIndexed(')
        macro = native[start:native.index('endmacro', start)+len('endmacro')]
        start = native.index('Lyra_CurrentSpritePhase:')
        helper = native[start:native.index('Lyra_CurrentSpritePhase_End:', start)]
        invocations = [line for line in native.splitlines()
                       if line.startswith('%LyraCurrentSpriteIndexed(')]
        if len(invocations) != 4:
            raise AssertionError('Expected the four maintained sprite reader invocations')
        cls.layout = {r['name']:r for r in L.current_table_layout(0x5B8000)}
        seed = bytearray(0x400000)
        # Native fallback windows are distinct from every selected resource.
        for address in (0x02E661, 0x02E6E1, 0x02E701):
            at = L.A.pc(address)
            seed[at:at+256] = bytes((0x65+i)&255 for i in range(256))
        cls.tables = {}
        for family in ('special_sprite_gfx', 'special_sprite_palettes'):
            for phase in range(3):
                name = family + (f'_phase{phase}' if phase else '')
                data = bytearray((phase*0x31+i*3)&255 for i in range(192))
                data[0xB0] = ((0,27,4) if family.endswith('gfx') else (1,0,0))[phase]
                data[0xA1] = 0x80
                if family.endswith('palettes') and phase == 0:
                    data[0xBE:0xC0] = bytes([0x12,0x80])
                cls.tables[name] = bytes(data)
                at = L.A.pc(cls.layout[name]['snes'])
                seed[at:at+192] = data
        cls.seed = bytes(seed)
        cls.image.write_bytes(seed)
        constants = '\n'.join(f'!LYRA_CURRENT_TABLE_{name} = ${row["snes"]:06X}'
                              for name,row in cls.layout.items())
        # This fixture deliberately changes widths/X/Y/C/V and counts queries.
        # DP8A supplies a synthetic phase, not real progression/clock behavior.
        phase_query = ('org $5CD000\nOracle_CheckIfNight:\nSEP #$30\n'
                       'LDA.l $7E1E01 : INC : STA.l $7E1E01\n'
                       'LDX.b #$A5 : LDY.b #$D3\nLDA.b $8A\nCLC : CLV : RTL\n')
        driver = folder/'readers.asm'
        driver.write_text('lorom\n'+constants+'\n'+macro+'\norg $5CC000\n'+helper+
                          '\n'+'\n'.join(invocations)+'\nassert pc() <= $5CD000\n'+phase_query)
        result = subprocess.run([asar,'--no-title-check','--fix-checksum=off','--symbols=wla',
                                 str(driver),str(cls.image)],capture_output=True,text=True,timeout=20)
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        cls.labels = L._labels(cls.image.with_suffix('.sym').read_bytes())

    def test_emitted_readers_preserve_abi_phase_mapping_fallback_and_startup_word_copy(self):
        plans = []
        cache = bytes((0xF1+i)&255 for i in range(256))
        for name,family,bias,old in (
                ('SpriteGfxByArea','special_sprite_gfx',0,0x02E661),
                ('SpecialSpriteGfx','special_sprite_gfx',128,0x02E6E1),
                ('SpritePalette','special_sprite_palettes',0,0x7EFD40),
                ('SpecialPalette','special_sprite_palettes',128,0x02E701)):
            for phase in range(4):
                placement = 0 if phase < 2 else phase-1
                selected_family = family+(f'_phase{placement}' if placement else '')
                for p in (0x20,0x71):
                    for area in (0x9F,0xA0,0xA1,0xB0,0xBF,0xC0):
                        index = area-bias
                        selected = 0xA0 <= area < 0xC0
                        if selected:
                            expected = self.tables[selected_family][area]
                        elif old == 0x7EFD40:
                            expected = cache[index]
                        else:
                            expected = self.seed[L.A.pc(old)+index]
                        regs = dict(a=0xABCD,x=index,y=0x4567 if not p&0x10 else 0x67,
                                    p=p,db=8,d=0x100,sp=0x1FFF)
                        plans.append((name,phase,regs,expected,selected))
        # Real M16 bulk cache calls copy phase0 adjacent page bytes without a query.
        for phase in range(4):
            for area in (0xA0,0xBE):
                data = self.tables['special_sprite_palettes'][area:area+2]
                regs = dict(a=0xABCD,x=area-128,y=0x4567,p=0x41,db=8,d=0x100,sp=0x1FFF)
                plans.append(('SpecialPalette',phase,regs,int.from_bytes(data,'little'),False))
        requests = [dict(entry=self.labels['Lyra_Read'+name],reset_ram=True,registers=regs,
                         writes=[dict(address=0x7E008A,bytes=[phase]),
                                 dict(address=0x7EFD40,bytes=list(cache))],
                         reads=[dict(address=0x7E1E01,length=1)],trace_writes=True,max_steps=200)
                    for name,phase,regs,expected,query in plans]
        run = subprocess.run([self.runner,str(self.image)],
            input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,timeout=20)
        self.assertEqual(run.returncode,0,run.stderr)
        output = run.stdout.splitlines()
        self.assertEqual(len(output),len(plans))
        for plan,line in zip(plans,output):
            name,phase,regs,expected,query = plan
            result = json.loads(line)
            with self.subTest(reader=name,phase=phase,p=regs['p'],index=regs['x']):
                self.assertTrue(result['returned'],result)
                self.assertFalse(result.get('stub_calls'))
                self.assertFalse(result.get('mmio_writes'))
                cpu = result['registers']
                mask = 255 if regs['p']&0x20 else 65535
                self.assertEqual(cpu['a'],(regs['a']&~mask)|expected)
                for key in ('x','y','sp','d','db'):
                    self.assertEqual(cpu[key],regs[key],key)
                nz = (0x02 if expected == 0 else 0) | (0x80 if expected&(0x80 if mask == 255 else 0x8000) else 0)
                self.assertEqual(cpu['p'],(regs['p']&~0x82)|nz)
                self.assertEqual(result['reads'][0]['bytes'],[int(query)])
                for write in result['writes']:
                    address = write['address']
                    if address>>16&127 < 64 and address&65535 < 8192:
                        address = 0x7E0000|(address&65535)
                    self.assertTrue(0x7E1F00 <= address < 0x7E2000 or address == 0x7E1E01)


class CurrentResidentAtlasCpuTest(unittest.TestCase):
    """The original twelve readers with synthetic, unallocated current tables."""
    @classmethod
    def setUpClass(cls):
        cls.asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        cls.runner = os.environ.get('OOS_CPU_RUNNER')
        if not cls.asar or not cls.runner:
            raise unittest.SkipTest('Set ASAR_BIN and OOS_CPU_RUNNER for resident reader CPU checks')
        cls.folder = tempfile.TemporaryDirectory(prefix='lyra-resident-readers-')
        cls.addClassCleanup(cls.folder.cleanup)
        cls.folder_path = Path(cls.folder.name)
        cls.native = Path(__file__).resolve().parents[1]/'Overworld/lyra_resident_atlas.asm'
        seed = bytearray(0x400000)
        def put(address, raw):
            at = L.A.pc(address)
            seed[at:at+len(raw)] = raw
        cls.hooks = []
        for mode, sites, quadrants in (
                ('Full', (0x02FE1B,0x02FE22,0x02FE2B,0x02FE32), (0,2,1,3)),
                ('Horizontal', (0x02F456,0x02F45D,0x02F466,0x02F46D), (0,1,2,3)),
                ('Vertical', (0x02F51E,0x02F525,0x02F52E,0x02F535), (0,2,1,3))):
            for site, quadrant in zip(sites, quadrants):
                if mode == 'Full':
                    raw = bytes([0xB9])+(0x8000+quadrant*2).to_bytes(2,'little')
                    raw += bytes([0x9F])+(0x7F2000+(quadrant//2)*0x40).to_bytes(3,'little')
                else:
                    raw = bytes([0xBF])+(0xBD8000+quadrant*2).to_bytes(3,'little')
                put(site, raw)
                cls.hooks.append((site, mode, quadrant, len(raw)))
        cls.mutable_hooks = []
        for sites in ((0x1BC9B2, 0x1BC9B9, 0x1BC9C0, 0x1BC9C7),
                      (0x1BCA3F, 0x1BCA46, 0x1BCA4D, 0x1BCA54)):
            for quadrant, (site, destination) in enumerate(zip(sites, (0x1006, 0x1008, 0x100E, 0x1010))):
                raw = b'\xbf' + (0xBD8000 + quadrant * 2).to_bytes(3, 'little')
                store = b'\x99' + destination.to_bytes(2, 'little')
                put(site, raw + store)
                cls.mutable_hooks.append((site, 'Mutable', quadrant, 4, store))
        cls.native_words = {tile: tuple(0x6000+tile*4+q for q in range(4))
                            for tile in range(129)}
        put(0xBD8000, b''.join(word.to_bytes(2,'little')
            for words in cls.native_words.values() for word in words))
        # Test-only LoROM origins never declare candidate allocation authority.
        parent, sizes = bytearray(range(192)), bytearray(192)
        for base, size, members in ((0xA2,2,(0xA2,0xA3)), (0xA4,3,(0xA4,0xAC)),
                                    (0xB0,1,(0xB0,0xB1,0xB8,0xB9))):
            for page in members:
                parent[page], sizes[page] = base, size
        parent[0xA6], sizes[0xA6] = 0x9F, 1
        sizes[0xA7] = 4
        parent[0xB7], sizes[0xB7] = 0xBF, 1
        put(0x5BAC00, parent+b'\0')
        put(0x5BAD00, sizes+b'\0')
        cls.words = {}
        for ordinal, page in enumerate(range(0xA0,0xC0)):
            index, words = 0x5B8200+ordinal*0x100, 0x5BA200+ordinal*0x40
            # Two-level v1 ABI encoded independently of the product planner.
            table = bytearray(192)
            table[0], table[1], table[3] = 1, 2, 129
            table[128+1], table[128+3], table[160+1] = 1, 3, 2
            put(index, table)
            cls.words[page] = {
                1: (0,0x8000,0x2100+ordinal,0x4100+ordinal),
                33: tuple(0x1100+ordinal*16+q for q in range(4))}
            put(words, bytes(8)+b''.join(word.to_bytes(2,'little')
                for tile in (1,33) for word in cls.words[page][tile]))
            area = 7 if page in (0xB0,0xB1,0xB8,0xB9) else 0
            put(0x5B8000+ordinal*8, index.to_bytes(3,'little')
                +words.to_bytes(3,'little')+bytes([area,2]))
        cls.seed = bytes(seed)
        cls.constants = '\n'.join((
            '!LyraNativeCurrentBranch = 1', '!LYRA_CURRENT_RESIDENT_ENABLED = 1',
            '!LYRA_CURRENT_RESIDENT_ABI_VERSION = 1',
            '!LYRA_CURRENT_RESIDENT_CODE_BASE = $5CC000',
            '!LYRA_CURRENT_RESIDENT_CODE_END = $5CC600',
            '!LYRA_CURRENT_RESIDENT_DIRECTORY = $5B8000',
            '!LYRA_CURRENT_RESIDENT_TILE16_COUNT = 128',
            '!LYRA_CURRENT_TABLE_parent = $5BAC00', '!LYRA_CURRENT_TABLE_area_size = $5BAD00'))
        cls.image, result = cls.assemble('enabled', cls.constants)
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        cls.labels = L._labels(cls.image.with_suffix('.sym').read_bytes())

    @classmethod
    def assemble(cls, name, constants):
        image, driver = cls.folder_path/(name+'.sfc'), cls.folder_path/(name+'.asm')
        image.write_bytes(cls.seed)
        driver.write_text('lorom\n'+constants+'\n'+getattr(cls, 'caller_source', '')+
                          '\nincsrc "'+str(cls.native)+'"\n')
        result = subprocess.run([cls.asar,'--no-title-check','--fix-checksum=off',
            '--symbols=wla',str(driver),str(image)],capture_output=True,text=True,timeout=20)
        return image, result

    def test_disabled_unbound_wrong_abi_and_invalid_bounds_gates(self):
        image, result = self.assemble('disabled', '')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(image.read_bytes(),self.seed)
        for name, constants in (
                ('unbound','!LyraNativeCurrentBranch = 1\n!LYRA_CURRENT_RESIDENT_ENABLED = 1'),
                ('wrong-abi',self.constants.replace('ABI_VERSION = 1','ABI_VERSION = 2')),
                ('code-bound',self.constants.replace('CODE_END = $5CC600','CODE_END = $5CC601')),
                ('directory-bound',self.constants.replace('DIRECTORY = $5B8000','DIRECTORY = $5BFF80'))):
            with self.subTest(gate=name):
                _, result = self.assemble(name, constants)
                self.assertNotEqual(result.returncode,0,'Unbound resident source assembled')

    def test_twelve_emitted_hooks_page_words_fallbacks_and_caller_abi(self):
        compiled = self.image.read_bytes()
        for site, mode, q, length in self.hooks:
            expected = bytes([0x22])+self.labels[f'Lyra_Resident{mode}{q}'].to_bytes(3,'little')
            self.assertEqual(compiled[L.A.pc(site):L.A.pc(site)+length],expected+b'\xea'*(length-4))
        plans = []
        def add(mode, base, raw, q, tile=1, page=None, overlay=False, bank=0x7E):
            expected = self.native_words[tile][q] if page is None else self.words[page][tile][q]
            plans.append((mode,base,raw,q,tile,expected,overlay,bank))
        for base, pages in ((0xA0,(0xA0,)*4), (0xA2,(0xA2,0xA3)*2),
                            (0xA4,(0xA4,0xA4,0xAC,0xAC)), (0xB0,(0xB0,0xB1,0xB8,0xB9))):
            for physical, page in enumerate(pages):
                raw = (physical&1)*0x40+(physical>>1)*0x1000
                for mode in ('Full','Horizontal','Vertical'):
                    for q in range(4):
                        add(mode,base,raw,q,1 if (q+physical)%2 == 0 else 33,page)
        for mode in ('Full','Horizontal','Vertical'):
            for q, (base, raw, tile) in enumerate(((0x9F,0,1),(0xC0,0,33),
                    (0xA6,0x40,1),(0xA7,0,1),(0xB7,0x40,1),
                    (0xB0,0,128),(0xB0,0,2),(0xB0,0,3),
                    (0xB0,0,65),(0xB0,0,97))):
                add(mode,base,raw,q%4,tile)
            add(mode,0xBF,0x1040,3,33,0xBF)
        add('Full',0xB0,0,0,overlay=True)
        add('Full',0xB0,0,1,bank=0x7F)
        add('Full',0xB0,0x2000,2,page=0xB0)
        for mode in ('Horizontal','Vertical'):
            for raw in (0x2000,0xFFC0):
                add(mode,0xB0,raw,3)
        requests, contexts = [], []
        live = (0,2,4,6,0x0C,0x0E,0x84,0x86,0x88,0x8A,0x410,0x416,0x700)
        for ordinal, plan in enumerate(plans):
            mode,base,raw,q,tile,expected,overlay,bank = plan
            scroll = 0 if ordinal%2 == 0 else 6
            state = {0:0xA55A,2:0x32,4:0x4000 if overlay else 0x2000,6:bank,
                     0x0C:0xBCDE,0x0E:0xDCBA,0x86:0x13,0x88:0x16,
                     0x8A:base,0x410:0xCAFE,0x416:scroll,0x700:0x7E}
            delta = (state[2]-2-2*state[0x88 if mode == 'Horizontal' else 0x86])&63
            offset = ((0x3D0,0x410)[bool(scroll&2)] if mode == 'Horizontal' else
                      (0x410,0xF410)[bool(scroll&4)] if mode == 'Vertical' else 0x410)
            state[0x84] = (raw+offset-(delta<<6 if mode == 'Horizontal' else delta))&65535
            regs = dict(a=0xABCD,x=0x240 if mode == 'Full' else tile*8,
                        y=tile*8 if mode == 'Full' else 0x4567,
                        p=(0x09,0x44)[ordinal%2],db=0xBD if mode == 'Full' else (8,0x7E)[ordinal%2],
                        d=(0,0x120)[ordinal%2],sp=0x1FFF)
            destination = 0x7F2000+(q//2)*0x40+regs['x'] if mode == 'Full' else None
            requests.append(dict(entry=self.labels[f'Lyra_Resident{mode}{q}'],reset_ram=True,
                registers=regs,writes=[dict(address=0x7E0000+at,bytes=list(value.to_bytes(2,'little')))
                                      for at,value in state.items()],
                reads=[dict(address=0x7E0000+at,length=2) for at in live]
                      +([dict(address=destination,length=2)] if destination is not None else []),
                trace_writes=True,max_steps=1000))
            contexts.append((plan,regs,state,destination))
        result = subprocess.run([self.runner,str(self.image)],
            input=''.join(json.dumps(row)+'\n' for row in requests),capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        output = result.stdout.splitlines()
        self.assertEqual(len(output),len(plans))
        for context, line in zip(contexts,output):
            plan,regs,state,destination = context
            row = json.loads(line)
            with self.subTest(reader=plan[0],base=plan[1],raw=plan[2],quadrant=plan[3],tile=plan[4]):
                self.assertTrue(row['returned'],row)
                self.assertFalse(row.get('stub_calls'))
                self.assertFalse(row.get('mmio_writes'))
                cpu, expected = row['registers'], plan[5]
                self.assertEqual(cpu['a'],expected)
                for field in ('x','y','sp','d','db'):
                    self.assertEqual(cpu[field],regs[field],field)
                nz = (2 if expected == 0 else 0)|(0x80 if expected&0x8000 else 0)
                self.assertEqual(cpu['p'],(regs['p']&~0x82)|nz)
                for at, observed in zip(live,row['reads']):
                    self.assertEqual(observed['bytes'],list(state[at].to_bytes(2,'little')),hex(at))
                if destination is not None:
                    self.assertEqual(row['reads'][-1]['bytes'],list(expected.to_bytes(2,'little')))
                allowed = set(range(0x7E1F80,0x7E2000))|set(range(0x7E0000,0x7E0004))
                if destination is not None:
                    allowed.update((destination,destination+1))
                for write in row['writes']:
                    at = write['address']
                    if at>>16&127 < 64 and at&65535 < 8192:
                        at = 0x7E0000|(at&65535)
                    self.assertIn(at,allowed)
        self.assertEqual(self.image.read_bytes(),compiled)


class CurrentResidentMutableCpuTest(unittest.TestCase):
    """Eight mutable hooks, actual native caller slices, and four new readers."""
    @classmethod
    def setUpClass(cls):
        # Portable instruction slices from USDASM $1BC983..$1BCA9E. These
        # retain the real input/target/stripe calculations and following stores.
        # They seed a sparse native image before the product hooks are applied.
        cls.caller_source = '''
org $1BC983
Fixture_DrawMap16_Anywhere:
PHX
ASL : ASL : ASL
STA.b $0C
STY.b $00
TXA : CLC : ADC.b $00 : STA.b $00
JSR Fixture_FindMap16VRAMAddress
LDY.w $1000
LDA.b $02 : XBA : STA.w $1002,Y
LDA.b $02 : CLC : ADC.w #$0020 : XBA : STA.w $100A,Y
LDA.w #$0300 : STA.w $1004,Y : STA.w $100C,Y
LDX.b $0C
assert pc() == $1BC9B2
LDA.l $BD8000,X : STA.w $1006,Y
LDA.l $BD8002,X : STA.w $1008,Y
LDA.l $BD8004,X : STA.w $100E,Y
LDA.l $BD8006,X : STA.w $1010,Y
LDA.w #$FFFF : STA.w $1012,Y
TYA : CLC : ADC.w #$0010 : STA.w $1000
PLX
RTL
assert pc() == $1BC9DE
Fixture_AlterTileHardcore:
PHA
STA.l $7E2000,X
PHX
ASL : ASL : ASL : STA.b $0C
TXA : CLC : ADC.w #$0000 : STA.b $00
STZ.b $02
AND.w #$003F : CMP.w #$0020 : BCC .no_high_x
LDA.w #$0400 : STA.b $02
.no_high_x
LDA.b $00 : AND.w #$0FFF : CMP.w #$0800 : BCC .no_high_y
LDA.b $02 : ADC.w #$07FF : STA.b $02
.no_high_y
LDA.b $00 : AND.w #$001F : ADC.b $02 : STA.b $02
LDA.b $00 : AND.w #$0780 : LSR : ADC.b $02 : STA.b $02
LDY.w $1000
XBA : STA.w $1002,Y
LDA.b $02 : CLC : ADC.w #$0020 : XBA : STA.w $100A,Y
LDA.w #$0300 : STA.w $1004,Y : STA.w $100C,Y
LDX.b $0C
assert pc() == $1BCA3F
LDA.l $BD8000,X : STA.w $1006,Y
LDA.l $BD8002,X : STA.w $1008,Y
LDA.l $BD8004,X : STA.w $100E,Y
LDA.l $BD8006,X : STA.w $1010,Y
TYA : CLC : ADC.w #$0010 : STA.w $1000
PLX : INX : INX : PLA : INC
RTS
assert pc() == $1BCA69
Fixture_FindMap16VRAMAddress:
STZ.b $02
LDA.b $00 : AND.w #$003F : CMP.w #$0020 : BCC .no_high_x
LDA.w #$0400 : STA.b $02
.no_high_x
LDA.b $00 : AND.w #$0FFF : CMP.w #$0800 : BCC .no_high_y
LDA.b $02 : ADC.w #$07FF : STA.b $02
.no_high_y
LDA.b $00 : AND.w #$001F : ADC.b $02 : STA.b $02
LDA.b $00 : AND.w #$0780 : LSR : ADC.b $02 : STA.b $02
RTS
assert pc() == $1BCA9F
org $1BCB00
Fixture_AlterTileHardcoreEntry:
JSR Fixture_AlterTileHardcore
RTL
'''
        CurrentResidentAtlasCpuTest.setUpClass.__func__(cls)

    @classmethod
    def assemble(cls, name, constants):
        return CurrentResidentAtlasCpuTest.assemble.__func__(cls, name, constants)

    def run_mutable(self, requests, *, image=None):
        result = subprocess.run([self.runner, str(image or self.image)],
            input=''.join(json.dumps(row) + '\n' for row in requests),
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(output), len(requests))
        for row in output:
            self.assertTrue(row['returned'], row)
            self.assertFalse(row.get('stub_calls'))
            self.assertFalse(row.get('mmio_writes'))
        return output

    def test_twenty_emitted_hooks_keep_all_eight_mutable_following_stores(self):
        compiled = self.image.read_bytes()
        self.assertEqual((len(self.hooks), len(self.mutable_hooks)), (12, 8))
        for site, mode, quadrant, length in self.hooks:
            target = self.labels[f'Lyra_Resident{mode}{quadrant}']
            expected = b'\x22' + target.to_bytes(3, 'little') + b'\xea' * (length - 4)
            self.assertEqual(compiled[L.A.pc(site):L.A.pc(site) + length], expected)
        for site, mode, quadrant, length, store in self.mutable_hooks:
            target = self.labels[f'Lyra_Resident{mode}{quadrant}']
            self.assertEqual(compiled[L.A.pc(site):L.A.pc(site) + 7],
                             b'\x22' + target.to_bytes(3, 'little') + store)

    def test_mutable_readers_use_target_pages_and_preserve_complete_load_abi(self):
        plans = []
        for base, pages in ((0xA0, (0xA0,) * 4), (0xA2, (0xA2, 0xA3) * 2),
                            (0xA4, (0xA4, 0xA4, 0xAC, 0xAC)),
                            (0xB0, (0xB0, 0xB1, 0xB8, 0xB9))):
            for raw, page in zip((0, 0x40, 0x1000, 0x1040), pages):
                for quadrant in range(4):
                    for tile in (1, 33):
                        plans.append((base, raw, quadrant, tile, self.words[page][tile][quadrant]))
        for base, raw, tile in ((0, 0, 1), (0x9F, 0x40, 33), (0xC0, 0, 1),
                                (0xA6, 0x40, 1), (0xA7, 0, 1), (0xB7, 0x40, 1),
                                (0xB0, 0x2000, 1), (0xB0, 0xFFC0, 33),
                                (0xB0, 0, 128), (0xB0, 0, 2), (0xB0, 0, 3),
                                (0xB0, 0, 65), (0xB0, 0, 97)):
            for quadrant in range(4):
                plans.append((base, raw, quadrant, tile, self.native_words[tile][quadrant]))
        requests, contexts = [], []
        live = (0, 2, 4, 6, 0x0C, 0x0E, 0x84, 0x86, 0x88, 0x8A, 0x410, 0x416, 0x700)
        for ordinal, (base, raw, quadrant, tile, expected) in enumerate(plans):
            state = {0: raw, 2: 0xA55A, 4: 0xBEEF, 6: 0xCAFE,
                     0x0C: 0xBCDE, 0x0E: 0xDCBA, 0x84: 0x4567, 0x86: 0x13,
                     0x88: 0x16, 0x8A: base, 0x410: 0xCAFE, 0x416: 6,
                     0x700: 0xBF if base == 0xB0 else 0xA0}
            regs = dict(a=0xABCD, x=tile * 8, y=0x4567, p=(0x09, 0x44)[ordinal % 2],
                        db=(8, 0x7E)[ordinal % 2], d=(0, 0x120)[ordinal % 2], sp=0x1FFF)
            requests.append(dict(entry=self.labels[f'Lyra_ResidentMutable{quadrant}'],
                reset_ram=True, registers=regs,
                writes=[dict(address=0x7E0000 + at, bytes=list(value.to_bytes(2, 'little')))
                        for at, value in state.items()],
                reads=[dict(address=0x7E0000 + at, length=2) for at in live],
                trace_writes=True, max_steps=1000))
            contexts.append((base, raw, quadrant, tile, expected, regs, state))
        for row, context in zip(self.run_mutable(requests), contexts):
            base, raw, quadrant, tile, expected, regs, state = context
            with self.subTest(base=base, raw=raw, quadrant=quadrant, tile=tile):
                cpu = row['registers']
                self.assertEqual(cpu['a'], expected)
                for field in ('x', 'y', 'sp', 'd', 'db'):
                    self.assertEqual(cpu[field], regs[field], field)
                nz = (2 if expected == 0 else 0) | (0x80 if expected & 0x8000 else 0)
                self.assertEqual(cpu['p'], (regs['p'] & ~0x82) | nz)
                for at, observed in zip(live, row['reads']):
                    self.assertEqual(observed['bytes'], list(state[at].to_bytes(2, 'little')), hex(at))
                allowed = set(range(0x7E1F80, 0x7E2000)) | set(range(0x7E0000, 0x7E0004))
                for write in row['writes']:
                    at = write['address']
                    if at >> 16 & 127 < 64 and at & 65535 < 8192:
                        at = 0x7E0000 | (at & 65535)
                    self.assertIn(at, allowed)

    def caller_request(self, kind, base, raw, tile, *, ordinal=0):
        stripe = (0x20, 0x60)[ordinal % 2]
        relative = 2 if kind == 'draw' and raw >= 2 else 0
        initial_x = raw - relative if kind == 'draw' else raw
        regs = dict(a=tile, x=initial_x, y=relative if kind == 'draw' else 0x4567,
                    p=0x41, db=8, d=0, sp=0x1FFF)
        return dict(entry=0x1BC983 if kind == 'draw' else 0x1BCB00,
            reset_ram=True, registers=regs,
            writes=[dict(address=0x7E008A, bytes=[base, 0]),
                    dict(address=0x7E0700, bytes=[0xBF, 0]),
                    dict(address=0x7E1000, bytes=list(stripe.to_bytes(2, 'little')))],
            reads=[dict(address=0x7E1000 + stripe + at, length=2) for at in (6, 8, 14, 16)] +
                  [dict(address=0x7E0000, length=2), dict(address=0x7E1000, length=2)],
            trace_writes=True, max_steps=5000), regs, stripe

    def test_actual_native_callers_compute_target_coordinates_before_stripe_output(self):
        plans, requests = [], []
        for base, pages in ((0xA0, (0xA0,) * 4), (0xA2, (0xA2, 0xA3) * 2),
                            (0xA3, (0xA2, 0xA3) * 2),
                            (0xA4, (0xA4, 0xA4, 0xAC, 0xAC)),
                            (0xAC, (0xA4, 0xA4, 0xAC, 0xAC)),
                            (0xB0, (0xB0, 0xB1, 0xB8, 0xB9)),
                            (0xB1, (0xB0, 0xB1, 0xB8, 0xB9)),
                            (0xBF, (0xBF,) * 4)):
            for physical, (raw, page) in enumerate(zip((0, 0x40, 0x1000, 0x1040), pages)):
                for kind in ('draw', 'hardcore'):
                    tile = (1, 33)[physical % 2]
                    request, regs, stripe = self.caller_request(kind, base, raw, tile,
                                                               ordinal=len(plans))
                    requests.append(request)
                    plans.append((kind, base, raw, tile, self.words[page][tile], regs, stripe))
        for row, plan in zip(self.run_mutable(requests), plans):
            kind, base, raw, tile, expected, regs, stripe = plan
            with self.subTest(caller=kind, base=base, raw=raw, tile=tile):
                self.assertEqual([int.from_bytes(bytes(value['bytes']), 'little')
                                  for value in row['reads'][:4]], list(expected))
                self.assertEqual(row['reads'][4]['bytes'], list(raw.to_bytes(2, 'little')))
                self.assertEqual(row['reads'][5]['bytes'], list((stripe + 16).to_bytes(2, 'little')))
                cpu = row['registers']
                self.assertEqual(cpu['x'], regs['x'] + (2 if kind == 'hardcore' else 0))
                self.assertEqual(cpu['y'], stripe)
                for field in ('sp', 'd', 'db'):
                    self.assertEqual(cpu[field], regs[field], field)
                if kind == 'hardcore':
                    self.assertEqual(cpu['a'], tile + 1)

    def test_native_mutable_control_reproduces_global_words_at_b0_east(self):
        image, assembled = self.assemble('mutable-native-control',
            self.constants.replace('LYRA_CURRENT_RESIDENT_ENABLED = 1',
                                   'LYRA_CURRENT_RESIDENT_ENABLED = 0'))
        self.assertEqual(assembled.returncode, 0, assembled.stdout + assembled.stderr)
        request, _, _ = self.caller_request('draw', 0xB0, 0x40, 33)
        row = self.run_mutable([request], image=image)[0]
        observed = [int.from_bytes(bytes(value['bytes']), 'little') for value in row['reads'][:4]]
        self.assertEqual(observed, list(self.native_words[33]))
        self.assertNotEqual(observed, list(self.words[0xB1][33]))


class CurrentResidentIceRodCpuTest(unittest.TestCase):
    """Actual Ice Rod source and lookup; synthetic IO latches do not emulate DMA."""

    # Independent disabled-byte witness from exact 5539c17d's retained default
    # ROM SHA256 11ce2823007593742584711c189f345765d6013595c6ed89127744f3edd1bf6b.
    # No game ROM is loaded by this test: these literals seed a sparse fixture.
    native_main = bytes.fromhex(
        '9de403a8ad8c00d0016bada303c906f0016be004f0016bade803c908f008'
        'ade803c903f0016bad0303c906f0016bad0403c906f0016b8a8f04d07e'
        'ad12422980f0f9c230ad16218f05d07ea50038ed08072d0a070a0a0a8506'
        'a50238ed0c072d0e070506aaa9b7009f00207e1864028a293f00c920009005'
        'a9000485028a29ff0fc900089007a50269ff0785028a291f00650285028a29'
        '80074a65028d16218f07d07ea9831d8f00d07e8f02d07e2000fdc230af07'
        'd07e6920008d16212000fdaf05d07e8d1621e230af04d07eaa6b')
    native_dma = bytes.fromhex(
        'a97e008d0443a900d08d0243e230a9188d0143a9048d0543a9018d00438d0b4260')

    @classmethod
    def setUpClass(cls):
        # Reuse the existing sparse native hook/page seed, never its old tests.
        CurrentResidentAtlasCpuTest.setUpClass.__func__(cls)
        cls.constants = cls.ice_constants(cls.constants)

    @staticmethod
    def ice_constants(constants):
        constants = constants.replace('RESIDENT_TILE16_COUNT = 128',
                                      'RESIDENT_TILE16_COUNT = 256')
        if 'LYRA_CURRENT_MODE =' not in constants:
            constants += '\n!LYRA_CURRENT_MODE = 1'
        if 'LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED =' not in constants:
            constants += '\n!LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED = 1'
        return constants

    @classmethod
    def ice_seed(cls):
        seed = bytearray(cls.seed)
        def put(at, raw):
            seed[L.A.pc(at):L.A.pc(at)+len(raw)] = raw
        cls.ice_words = {}
        for ordinal, page in enumerate(range(0xA0, 0xC0)):
            index, words = 0x5B8200+ordinal*0x100, 0x5BA200+ordinal*0x40
            table = bytearray(224)
            table[0], table[1], table[5] = 1, 2, 3
            table[129], table[161], table[192+23] = 1, 2, 3
            # Four distinct fallback mechanisms for the same B7 query.
            if page == 0xA8:
                table[5] = 0
            elif page == 0xA9:
                table[192+23] = 0
            elif page == 0xAA:
                table[5] = 129
            elif page == 0xAB:
                table[192+23] = 4
            word = 0 if page == 0xA0 else 0x8100+ordinal
            cls.ice_words[page] = word
            put(index, table)
            put(words+24, word.to_bytes(2, 'little')*4)
            put(0x5B8000+ordinal*8+7, b'\x03')
        put(0xBD8000+0xB7*8, bytes.fromhex('831d')*4)
        return bytes(seed)

    @classmethod
    def assemble(cls, name, constants):
        image, driver = cls.folder_path/(name+'.sfc'), cls.folder_path/(name+'.asm')
        image.write_bytes(cls.ice_seed())
        item = cls.native.parents[1]/'Items/ice_rod.asm'
        driver.write_text('lorom\n'+cls.ice_constants(constants)+'\nnamespace Oracle\n'
            'incsrc "'+str(cls.native)+'"\nincsrc "'+str(item)+'"\nnamespace off\n')
        result = subprocess.run([cls.asar, '--no-title-check', '--fix-checksum=off',
            '--symbols=wla', str(driver), str(image)], capture_output=True, text=True, timeout=20)
        return image, result

    def run_ice(self, requests, *, image=None):
        run = subprocess.run([self.runner, str(image or self.image)],
            input=''.join(json.dumps(row)+'\n' for row in requests),
            capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        rows = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(rows), len(requests))
        for row in rows:
            self.assertTrue(row['returned'], row)
            self.assertFalse(row.get('stub_calls'))
        return rows

    def helper_request(self, base, raw, p, *, indoor=0, db=0xBD, d=0x120):
        live = {0: 0xA55A, 2: 0xBEEF, 4: 0xCAFE, 6: 0x1234,
                0x1B: indoor | 0xA500, 0x8A: base | 0x5A00, 0x700: 0xBF}
        regs = dict(a=0xABCD, x=raw, y=0x4567, p=p, db=db, d=d, sp=0x1FFF)
        return dict(entry=self.labels['Lyra_ResidentIceRodWord'], reset_ram=True,
            registers=regs, writes=[dict(address=0x7E0000+at,
                bytes=list(word.to_bytes(2, 'little'))) for at, word in live.items()],
            reads=[dict(address=0x7E0000+at, length=2) for at in live],
            trace_writes=True, max_steps=1200), regs, live

    def test_helper_target_pages_zero_word_fallbacks_and_complete_load_abi(self):
        plans = []
        for base, pages in ((0xA0, (0xA0,)*4), (0xA2, (0xA2, 0xA3)*2),
                            (0xA4, (0xA4, 0xA4, 0xAC, 0xAC)),
                            (0xB0, (0xB0, 0xB1, 0xB8, 0xB9)),
                            (0xB1, (0xB0, 0xB1, 0xB8, 0xB9))):
            for raw, page in zip((2, 0x42, 0x1002, 0x1042), pages):
                for p in (0x04, 0x05, 0x4C, 0x4D):
                    plans.append((base, raw, p, 0, self.ice_words[page]))
        for base, raw, indoor in ((0x9F, 2, 0), (0xC0, 2, 0), (0xA6, 2, 0),
                                  (0xA7, 2, 0), (0xB7, 0x42, 0),
                                  (0xB0, 0x2000, 0), (0xB0, 0xFFFF, 0),
                                  (0xB0, 0x42, 1), (0xB0, 0x42, 0x80),
                                  (0xA8, 2, 0), (0xA9, 2, 0),
                                  (0xAA, 2, 0), (0xAB, 2, 0)):
            for p in (0x04, 0x05, 0x4C, 0x4D):
                plans.append((base, raw, p, indoor, 0x1D83))
        requests, contexts = [], []
        for ordinal, (base, raw, p, indoor, expected) in enumerate(plans):
            request, regs, live = self.helper_request(base, raw, p, indoor=indoor,
                db=(8, 0xBD, 0x7E)[ordinal%3], d=(0, 0x120)[ordinal%2])
            requests.append(request)
            contexts.append((base, raw, indoor, expected, regs, live))
        for row, context in zip(self.run_ice(requests), contexts):
            base, raw, indoor, expected, regs, live = context
            with self.subTest(base=base, raw=raw, indoor=indoor, p=regs['p']):
                self.assertFalse(row.get('mmio_writes'))
                cpu = row['registers']
                self.assertEqual(cpu['a'], expected)
                for field in ('x', 'y', 'sp', 'd', 'db'):
                    self.assertEqual(cpu[field], regs[field], field)
                nz = (2 if expected == 0 else 0) | (0x80 if expected&0x8000 else 0)
                self.assertEqual(cpu['p'], (regs['p']&~0x82)|nz)
                for at, observed in zip(live, row['reads']):
                    self.assertEqual(observed['bytes'], list(live[at].to_bytes(2, 'little')))
                for write in row['writes']:
                    at = write['address']
                    if at>>16&127 < 64 and at&65535 < 8192:
                        at = 0x7E0000|(at&65535)
                    self.assertIn(at, set(range(0x7E1F80, 0x7E2000)) |
                                      set(range(0x7E0000, 0x7E0004)))

    def main_request(self, base, raw):
        # Actual entry checks, VBlank polling, coordinate arithmetic and DMA
        # routine execute. IO is an explicit byte latch, without PPU side effects.
        state = {0: ((raw&0x1F80)>>3)+0x10, 2: (raw&0x7E)+0x20,
                 0x1B: 0, 0x8A: base, 0x8C: 1, 0x303: 0x0606,
                 0x3A3: 6, 0x700: 0xBF, 0x708: 0x10, 0x70A: 0x03F0,
                 0x70C: 0x20, 0x70E: 0x007E}
        regs = dict(a=8, x=4, y=0x67, p=0x30, db=8, d=0, sp=0x1FFF)
        mmio = {0x4212: 0x80, 0x2116: 0xAA, 0x2117: 0x55, 0x420B: 0}
        mmio.update({at: 0 for at in range(0x4300, 0x4307)})
        return dict(entry=self.labels['LyraHost_IceRodStart'], reset_ram=True,
            registers=regs, writes=[dict(address=0x7E0000+at,
                bytes=list(word.to_bytes(2, 'little'))) for at, word in state.items()],
            reads=[dict(address=0x7E2000+raw, length=2),
                   dict(address=0x7ED000, length=9)],
            mmio=[dict(address=at, value=value) for at, value in mmio.items()],
            trace_mmio=True, trace_writes=True, max_steps=1600), regs

    def test_actual_main_target_b7_payload_and_two_native_dma_commands(self):
        plans = [(base, raw, page) for base, pages in (
            (0xA0, (0xA0,)*4), (0xA2, (0xA2, 0xA3)*2),
            (0xA4, (0xA4, 0xA4, 0xAC, 0xAC)),
            (0xB0, (0xB0, 0xB1, 0xB8, 0xB9)))
            for raw, page in zip((2, 0x42, 0x1002, 0x1042), pages)]
        requests = [self.main_request(base, raw)[0] for base, raw, page in plans]
        dma = [(0x4304, 0x7E), (0x4305, 0), (0x4302, 0), (0x4303, 0xD0),
               (0x4301, 0x18), (0x4305, 4), (0x4300, 1), (0x420B, 1)]
        for row, (base, raw, page) in zip(self.run_ice(requests), plans):
            with self.subTest(base=base, raw=raw, page=page):
                self.assertEqual(row['reads'][0]['bytes'], [0xB7, 0])
                expected = list(self.ice_words[page].to_bytes(2, 'little'))*2
                self.assertEqual(row['reads'][1]['bytes'][:4], expected)
                self.assertEqual(row['reads'][1]['bytes'][4:7], [4, 0xAA, 0x55])
                self.assertEqual(row['reads'][1]['bytes'][7:9], [2, 0])
                observed = [(write['address']&65535, write['value'])
                            for write in row['mmio_writes']]
                # Final native restore remains M8 after the second real DMA.
                self.assertEqual(observed, [(0x2116, 2), (0x2117, 0)]+dma+
                    [(0x2116, 0x22), (0x2117, 0)]+dma+[(0x2116, 0xAA)])
                for field, expected in (('x', 4), ('y', 8), ('sp', 0x1FFF),
                                        ('db', 8), ('d', 0)):
                    self.assertEqual(row['registers'][field], expected)

    def test_old_literal_control_fails_packed_appearance_and_disabled_bytes_match(self):
        old = self.folder_path/'ice-old-literal-control.sfc'
        image = bytearray(self.image.read_bytes())
        at = L.A.pc(self.labels['LyraCall_IceRodWord'])
        image[at:at+4] = bytes.fromhex('a9831dea')
        old.write_bytes(image)
        request, _ = self.main_request(0xB0, 0x42)
        row = self.run_ice([request], image=old)[0]
        self.assertEqual(row['reads'][1]['bytes'][:4], [0x83, 0x1D]*2)
        with self.assertRaises(AssertionError):
            self.assertEqual(row['reads'][1]['bytes'][:4],
                             list(self.ice_words[0xB1].to_bytes(2, 'little'))*2)
        constants = self.constants.replace('RESIDENT_ENABLED = 1', 'RESIDENT_ENABLED = 0')
        constants = constants.replace('RESIDENT_RESOURCES_ENABLED = 1',
                                      'RESIDENT_RESOURCES_ENABLED = 0')
        off, result = self.assemble('ice-disabled', constants)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        expected = bytearray(self.ice_seed())
        for address, raw in ((0x088A5D, bytes.fromhex('22a0fb0e')),
                (0x0EFBA0, self.native_main), (0x0EFD00, self.native_dma),
                (0x07DC9E, bytes.fromhex('2280fc0eea')),
                (0x07DD1B, bytes.fromhex('2290fc0e60')),
                (0x0EFC80, bytes.fromhex('a50a0c43030c48036b')),
                (0x0EFC90, bytes.fromhex('a50a0c5903ad5003c90001d0039c4a036b')),
                (0x0E95DC, bytes.fromhex('0e5757')),
                (0x0F85B8, bytes.fromhex('831d')*4)):
            expected[L.A.pc(address):L.A.pc(address)+len(raw)] = raw
        self.assertEqual(off.read_bytes(), bytes(expected))

    def test_compiled_adapter_call_extent_and_unchanged_native_dma_body(self):
        image = self.image.read_bytes()
        labels = self.labels
        start, end = labels['LyraHost_IceRodStart'], labels['LyraHost_IceRodEnd']
        call = labels['LyraCall_IceRodWord']
        self.assertEqual(end-start, len(self.native_main)+1)
        self.assertLessEqual(end, 0x0EFC80)
        self.assertEqual(labels['LyraCall_IceRodWord_End']-call, 4)
        expected = b'\x22'+labels['Lyra_ResidentIceRodWord'].to_bytes(3, 'little')
        self.assertEqual(image[L.A.pc(call):L.A.pc(call)+4], expected)
        self.assertEqual(image[L.A.pc(start):L.A.pc(end)],
                         self.native_main.replace(bytes.fromhex('a9831d'), expected, 1))
        self.assertEqual(labels['Lyra_ResidentIceRodWord_End']-
                         labels['Lyra_ResidentIceRodWord'], 46)
        self.assertLessEqual(labels['Lyra_ResidentAtlasCodeEnd']-
                             labels['Lyra_ResidentAtlasCodeStart'], 0x600)
        dma = labels['LyraHost_IceRodDmaStart']
        self.assertEqual(labels['LyraHost_IceRodDmaEnd']-dma, len(self.native_dma))
        self.assertEqual(image[L.A.pc(dma):L.A.pc(dma)+len(self.native_dma)], self.native_dma)


class CurrentWholeCompositionMeasurementTest(unittest.TestCase):
    """Opt-in, retained host measurement; never an ordinary build admission.

    LYRA_MEASUREMENT_OUTPUT selects a NEW evidence directory. PREPARE, API,
    LIBRARY, HEADER, CLI and PREVIEW require LYRA_MEASUREMENT_<ROLE> and <ROLE>_SHA256.
    PREPARE is the retained historical generated packet, not a current grant.
    PREVIEW is an external independently reviewed seeded checkpoint binding.
    LYRA_MEASUREMENT_HIDDEN_STREAMS=1 selects the separate E3 case; each
    case requires its own new output directory. Both remain HOST fixtures.
    No external API import, probe, file write or assembly occurs on import.
    """

    def test_whole_source_cli_and_library_have_identical_bytes_and_no_e3_writes(self):
        if os.environ.get('LYRA_MEASUREMENT_HIDDEN_STREAMS') == '1':
            self.skipTest('The E3 case needs its own retained measurement output')
        self._measure()

    def test_whole_source_cli_and_library_bind_e3_hidden_streams(self):
        if os.environ.get('LYRA_MEASUREMENT_HIDDEN_STREAMS') != '1':
            self.skipTest('Set LYRA_MEASUREMENT_HIDDEN_STREAMS=1 for the separate E3 case')
        self._measure(hidden_streams=True)

    def _measure(self, hidden_streams=False):
        if not os.environ.get('LYRA_MEASUREMENT_OUTPUT'):
            self.skipTest('Select LYRA_MEASUREMENT_OUTPUT and six hashed measurement inputs')
        import importlib.util
        import re
        from types import SimpleNamespace
        import build_receipt as receipt
        import lyra_project_bg_palette as bg
        import lyra_resident_graphics as resident
        from test_lyra_resident_constructor import resource_plan

        root = Path(__file__).resolve().parents[1]
        output = Path(os.environ['LYRA_MEASUREMENT_OUTPUT']).absolute()
        self.assertFalse(output.exists(), 'Retained measurement output must be new')
        self.assertEqual(output.resolve(), output, 'Output must not traverse a symlink')
        self.assertFalse(output.is_relative_to(root) or root.is_relative_to(output))

        def identity(path):
            return receipt.identity(Path(path))

        inputs = {}
        for role in ('PREPARE', 'API', 'LIBRARY', 'HEADER', 'CLI', 'PREVIEW'):
            path = Path(os.environ['LYRA_MEASUREMENT_' + role]).resolve(strict=True)
            binding = identity(path)
            self.assertEqual(binding['sha256'], os.environ['LYRA_MEASUREMENT_' + role + '_SHA256'], role)
            self.assertFalse(output.is_relative_to(path.parent), role)
            inputs[role] = binding
        reviewed_preview = json.loads(Path(inputs['PREVIEW']['path']).read_bytes())
        api_root = Path(inputs['API']['path']).parents[3]
        api_revision = subprocess.run(['git', '-C', str(api_root), 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        self.assertEqual(api_revision, '5fd539cd510e4a26afef66fc14e35ca6d8ff0497')
        original = json.loads(Path(inputs['PREPARE']['path']).read_bytes())
        saved = Path(original['base_rom']).resolve(strict=True)
        inputs['saved_source'] = identity(saved)
        self.assertEqual(inputs['saved_source']['sha256'], original['saved_rom_sha256'])
        source = saved.read_bytes()
        seed = L.A.expanded_rom(source)
        self.assertEqual(len(seed), 0x400000)
        old_generated = Path(inputs['PREPARE']['path']).parent
        for relative, digest in original['generated_files'].items():
            path = (old_generated / relative).resolve(strict=True)
            self.assertTrue(path.is_relative_to(old_generated))
            inputs['retained:' + relative] = identity(path)
            self.assertEqual(inputs['retained:' + relative]['sha256'], digest, relative)

        # Reuse the conservative source/asset snapshot and retained packet;
        # no symlinks, Git checkout, production generated output or cache.
        snapshot = receipt.source_snapshot(root, output / 'full-current.build.json')
        output.mkdir(parents=True)
        tree = output / 'source'
        for relative, binding in snapshot['files'].items():
            original_path = root / relative
            self.assertTrue(original_path.resolve().is_relative_to(root))
            raw = original_path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), binding['sha256'])
            target = tree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        generated = tree / 'Data/Generated/lyra_project'
        for relative in original['generated_files']:
            target = generated / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(inputs['retained:' + relative]['path']).read_bytes())
        (output / 'retained-prepare.json').write_bytes(Path(inputs['PREPARE']['path']).read_bytes())

        def write_json(path, value):
            path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')

        # All32 small tail rows are explicit HOST values. Historical native160
        # prefixes are reconstructed from the selected source by the real builder.
        old_tables = {row['name']: row for row in original['tables']['tables']}
        # The retained packet authored only A0/A1. Bind zero-only HOST aliases
        # to its actual emitted A0 streams, not to unmapped placeholder zero.
        retained_suffix = (generated / 'runtime_data.asm').read_text().split(
            '; Ungranted source-profile actor data; no activation.', 1)[1]
        placements = re.findall(r'^org \$([0-9A-Fa-f]+)\n'
            r'incbin "binaries/payload.bin":\$([0-9A-Fa-f]+)\.\.\$([0-9A-Fa-f]+)$',
            retained_suffix, re.M)
        terrain_payload = (generated / 'binaries/payload.bin').read_bytes()
        anchors, terrain_aliases = {}, []
        for name, plane in (('map32_high', 0), ('map32_low', 1)):
            raw = bytes.fromhex(old_tables[name]['payload_hex'])
            anchor = int.from_bytes(raw[0xA0 * 3:0xA1 * 3], 'little')
            at = L.A.pc(anchor)
            streams = [row for row in original['terrain_plan']['streams']
                       if row['map_id'] == 0xA0 and row['plane'] == plane]
            self.assertEqual(len(streams), 1)
            lo, hi = streams[0]['pc']
            self.assertTrue(at == lo < hi <= 0x400000)
            emitted = [(int(a, 16), int(b, 16)) for address, a, b in placements
                       if int(address, 16) == anchor]
            self.assertEqual(len(emitted), 1, 'Host terrain anchor has no unique retained payload write')
            begin, end = emitted[0]
            self.assertTrue(0 <= begin < end <= len(terrain_payload))
            self.assertEqual(end - begin, hi - lo)
            self.assertEqual(hashlib.sha256(terrain_payload[begin:end]).hexdigest(),
                             streams[0]['payload_sha256'])
            anchors[name] = anchor
        rows = {}
        for area in range(0xA0, 0xC0):
            values = {}
            for spec in L.current_table_layout(0xE08000):
                name, stride = spec['name'], spec['stride']
                fallback = re.sub(r'_phase[12]$', '', name)
                table = old_tables[name if name in old_tables else fallback]
                raw = bytes.fromhex(table['payload_hex'])[area * stride:(area + 1) * stride]
                self.assertEqual(len(raw), stride)
                values[name] = list(raw) if stride == 8 else int.from_bytes(raw, 'little')
                if name in anchors and values[name] == 0:
                    values[name] = anchors[name]
                    terrain_aliases.append(dict(map_id=area, table=name, original_pointer=0,
                        host_anchor_map_id=0xA0, host_pointer=anchors[name]))
            values.update(parent=area, area_size=0)
            rows[area] = values
        self.assertEqual(len(terrain_aliases), 60)
        write_json(output / 'host-terrain-aliases.json', terrain_aliases)
        hidden_plan, native_list_spans = None, []
        if hidden_streams:
            from lyra_project_terrain import TerrainDocument
            # Explicit HOST values, never an authenticated saved resource document.
            # Keep seeded-preview A0/A1 small; A2/A3 exercises a child-directory alias.
            areas = [dict(parent_map_id=0xA2, size='wide', maps=[0xA2, 0xA3])]
            areas.extend(dict(parent_map_id=page, size='small', maps=[page])
                         for page in range(0xA0, 0xC0) if page not in (0xA2, 0xA3))
            authoring = tuple(dict(native_resources=dict(secrets=[], event_behavior=None))
                              for _ in range(32))
            for page, record in (
                    (0xA0, dict(id=1, x=8, y=8, secret_id=1)),
                    (0xA2, dict(id=2, x=2, y=3, secret_id=0x80)),
                    (0xA3, dict(id=3, x=2, y=3, secret_id=2)),
                    (0xBF, dict(id=4, x=31, y=31, secret_id=0x86))):
                authoring[page-0xA0]['native_resources']['secrets'].append(record)
            document = TerrainDocument(dict(test='synthetic all32 hidden-stream host measurement'),
                (tuple([0]*1024),)*32, tuple({} for _ in range(32)), authoring=authoring,
                gameplay_areas=tuple(areas), next_native_resource_id=5)
            hidden_plan = resident.lower_hidden_streams(source, document, data_snes=0xE38000,
                capacity=0x8000, preimage=seed[0x318000:0x320000])
            self.assertEqual(hidden_plan['payload_bytes'], 3*4+2*31)
            self.assertEqual(len(hidden_plan['streams']), 31)
            tail = bytes.fromhex(hidden_plan['directory_tail_hex'])
            self.assertEqual(len(tail), 64)
            self.assertEqual(tail[4:6], tail[6:8])
            for area in areas:
                for page in area['maps']:
                    rows[page].update(parent=area['parent_map_id'],
                        area_size=2 if area['size'] == 'wide' else 0,
                        hidden_items=int.from_bytes(tail[(page-0xA0)*2:(page-0x9F)*2], 'little'))
            native_prefix = bytes.fromhex(hidden_plan['native_prefix_hex'])
            self.assertEqual(native_prefix, source[L.A.pc(0x82A784):L.A.pc(0x82A784)+320])
            # Protect the actual native list data, rather than the whole9B bank:
            # that physical bank also contains intentional hook code changes.
            for pointer in sorted({int.from_bytes(native_prefix[i:i+2], 'little')
                                   for i in range(0, 320, 2)}):
                self.assertTrue(0x8000 <= pointer <= 0xFFFE)
                begin = cursor = L.A.pc(0x9B0000 | pointer)
                limit = L.A.pc(0x9BFFFF)+1
                while True:
                    self.assertLessEqual(cursor+2, limit, 'Native hidden list lacks a same-bank terminator')
                    if source[cursor:cursor+2] == b'\xFF\xFF':
                        cursor += 2
                        break
                    cursor += 3
                native_list_spans.append(dict(pc=[begin, cursor], payload_hex=source[begin:cursor].hex()))
            write_json(output / 'host-hidden-streams.json', dict(synthetic_host_document=True,
                authenticated_save=False, gameplay_areas=areas, authoring=authoring,
                next_native_resource_id=5, plan=hidden_plan, native_list_spans=native_list_spans))
        tables = L.plan_current_tables(source, rows,
            origins=dict(table_base=0xE08000, code_base=0xE0C000,
                         code_end=0xE0D000, descriptor_base=0xE18000),
            policy=dict(source_rom_sha256=hashlib.sha256(source).hexdigest(),
                source_profile_sha256=hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
                allocation_granted=False, publication_authorized=False))
        self.assertEqual(len(tables['tables']), 38)
        self.assertEqual(tables['tables_pc'], [0x300000, 0x3030C0])
        write_json(output / 'current-table-plan.json', tables)

        # Existing pure resident builders supply a small explicit resource
        # fixture. These candidate ROM/RAM intervals grant no ownership.
        native = resident.plan_native_resident_abi(resource_plan(), tile16_count=4096)
        preimage = seed[0x340000:0x350000]
        emission = resident.emit_native_resident_abi(native, data_pc=0x340000,
            capacity=0x10000, preimage=preimage)
        (generated / emission['binary_path']).write_bytes(bytes.fromhex(emission['payload_hex']))
        palette = bg.plan_bg128([SimpleNamespace(**row) for row in resident.resident_bg128_rows(native)],
            data_snes=0xE18100, capacity=0x400, preimage=seed[0x308100:0x308500])
        write_json(output / 'resident-emission.json', emission)

        constants_path = generated / 'runtime_constants.asm'
        def assignments(text):
            return {name: int(value[1:], 16) if value.startswith('$') else int(value)
                    for name, value in re.findall(r'^!([A-Za-z0-9_]+)\s*=\s*(\$[0-9A-Fa-f]+|[0-9]+)\s*$', text, re.M)}
        constants = assignments(constants_path.read_text())
        constants.update(assignments(tables['constants_assembler']))
        constants.update(assignments(emission['constants_asm']))
        constants['LYRA_CURRENT_HIDDEN_STREAMS_BOUND'] = 0
        if hidden_plan is not None:
            constants.update(assignments(hidden_plan['constants_asm']))
        constants.update(LYRA_PROJECT_DATA_PRESENT=1, LYRA_NATIVE_A1_ENABLED=0,
            LYRA_CURRENT_MODE=1, LYRA_CURRENT_ACTORS_ENABLED=1, LYRA_CURRENT_ACTORS_BOUND=1,
            LYRA_CURRENT_EVENTS_ENABLED=1, LYRA_CURRENT_EVENTS_BOUND=1,
            LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED=1, LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND=1,
            LYRA_PRIVATE_PILOT_INGRESS_ENABLED=1, LYRA_PRIVATE_CHECKPOINT_ENABLED=1,
            LYRA_CURRENT_RESIDENT_ENABLED=1, LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED=1,
            LYRA_CURRENT_RESIDENT_CODE_BASE=0xF88000, LYRA_CURRENT_RESIDENT_CODE_END=0xF88600,
            LYRA_CURRENT_RESIDENT_RESOURCE_CODE_BASE=0xF88600,
            LYRA_CURRENT_RESIDENT_RESOURCE_CODE_END=0xF88700,
            LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE=0x7E1E20,
            LYRA_CURRENT_RESIDENT_MAIN_CACHE_END=0x7E1E24,
            LYRA_CURRENT_RESIDENT_MAIN_CACHE_RESET_BOUND=1,
            PROJECT_BG128_ENABLED=1, PROJECT_BG128_RESTORE_BOUND=1,
            PROJECT_BG128_CODE_BASE=0xE0D000, PROJECT_BG128_CODE_END=0xE10000,
            LYRA_CURRENT_GFX_ORIGIN=0xE28000, LYRA_CURRENT_GFX_END=0xE2E000,
            LYRA_AREA_TILESETS_BOUND=1, LYRA_AREA_FERRY_BOUND=1,
            LYRA_AREA_TILESETS_ORIGIN=0xE2E000, LYRA_AREA_TILESETS_END=0xE30000,
            JOINT_PALETTE_DIRECTORY_ENABLED=1)
        constants_path.write_text('; HOST measurement only; not a prepared publication context.\n' +
            ''.join(f'!{key} = ${value:X}\n' for key, value in sorted(constants.items())))
        runtime = (generated / 'runtime_data.asm').read_text()
        marker = '; Ungranted source-profile actor data; no activation.'
        self.assertEqual(runtime.count(marker), 1)
        (generated / 'runtime_data.asm').write_text(tables['tables_assembler'] +
            tables['descriptor_assembler'] + marker + runtime.split(marker, 1)[1] +
            emission['runtime_data_asm'] + bg.emit_bg128_data(palette) +
            (hidden_plan['runtime_data_asm'] if hidden_plan is not None else ''))
        overrides = dict(ENABLE_OW_AREA_TILESETS=1, ENABLE_SPECIAL_TRIGGER_TABLE_V2=0,
                         ENABLE_SPECIAL_EXIT_TABLE_V2=0, ENABLE_KALYXO_BOAT=0)
        feature_path = tree / 'Config/feature_flags.asm'
        feature_path.write_text(feature_path.read_text() + '\n; Explicit host measurement options.\n' +
            ''.join(f'!{key} = {value}\n' for key, value in overrides.items()))

        graphics_directory = str(root / 'Scripts/Graphics')
        sys.path.insert(0, graphics_directory)
        try:
            import compile_runtime_graphics as graphics
        finally:
            sys.path.remove(graphics_directory)
        catalog_path = tree / 'Overworld/graphics_catalog.json'
        catalog, assets = graphics.pack.load(catalog_path, parent_count=192)
        policy = graphics.pack.read_json(tree / 'Overworld/graphics_runtime_policy.json')
        # Validate the ACTUAL unchanged contract against its actual source root.
        # This low-level renderer never calls ordinary/publication preparation.
        contract = json.loads((root / 'Config/lyra_current_source_contract.json').read_bytes())
        graphics_source, graphics_report = graphics.render(catalog, assets, policy,
            catalog_path.parent, generated, legacy_root=tree, current_contract=contract,
            source_root=root, resident_native=dict(plan=native, emission=emission, preimage=preimage))
        (generated / 'graphics_runtime_tables.asm').write_text(graphics_source)
        write_json(output / 'graphics-report.json', graphics_report)

        driver = tree / 'full-current.asm'
        driver.write_text('lorom\n!LYRA_BUILD_CONTEXT = 1\n'
            '!REGIONAL_CHECKPOINTS_ENABLED = 1\n!REGIONAL_CHECKPOINTS_BOUND = 1\n'
            'incsrc "Oracle_main.asm"\n')
        image = output / 'full-current.sfc'
        base = output / 'input.sfc'
        image.write_bytes(seed)
        base.write_bytes(seed)
        receipt_path = output / 'full-current.build.json'
        def record(*args):
            self.assertEqual(receipt.main([*args, '--receipt', str(receipt_path)]), 0)
        record('init', '--root', str(tree), '--base-rom', str(base), '--version', 'fixture',
            '--requested-profile', ('E3 hidden-stream whole-current HOST measurement' if hidden_streams
                                    else 'unallocated whole-current host measurement'),
            '--assembler', inputs['CLI']['path'])
        for role in ('API', 'LIBRARY', 'CLI'):
            record('tool', '--name', role, '--path', inputs[role]['path'])
        record('artifact', '--name', 'api_header', '--path', inputs['HEADER']['path'])
        record('artifact', '--name', 'preview_binding', '--path', inputs['PREVIEW']['path'])
        record('snapshot', '--phase', 'pre_assembly')
        completed = False
        try:
            spec = importlib.util.spec_from_file_location('lyra_measurement_asar', inputs['API']['path'])
            api = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(api)
            self.assertTrue(api.init(inputs['LIBRARY']['path']))
            self.addCleanup(api.close)
            self.assertEqual(api.apiversion(), 303)
            self.assertEqual(api.version(), 10901)

            def run(name, command):
                result = subprocess.run(command, cwd=tree, capture_output=True, text=True,
                    timeout=180, env=dict(os.environ, OOS_LYRA_BUILD_CONTEXT='0', PYTHONDONTWRITEBYTECODE='1'))
                write_json(output / (name + '.json'), dict(argv=command, cwd=str(tree),
                    exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr))
                record('check', '--name', name, '--status', 'passed' if result.returncode == 0 else 'failed',
                    '--required', '1', '--detail', str(output / (name + '.json')),
                    '--exit-code', str(result.returncode))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            version = run('cli-version', [inputs['CLI']['path'], '--version'])
            self.assertRegex(version.stdout, r'^Asar 1\.91(?:,|\s)')
            write_json(output / 'measurement-inputs.json', dict(inputs=inputs,
                source_snapshot=snapshot, constants=constants, feature_overrides=overrides,
                synthetic_host_terrain_aliases=terrain_aliases,
                synthetic_host_hidden_streams=hidden_streams, authenticated_resource_save=False,
                api_source=dict(root=str(api_root), git_head=api_revision),
                api_version=api.apiversion(), assembler_version=api.version(),
                cli_version_stdout=version.stdout, cli_version_stderr=version.stderr,
                authority=dict(allocation_granted=False, publication_authorized=False,
                               ordinary_build_ready=False, runtime_admission=False),
                scope='host composition measurement; synthetic tail/resident/cache; no pickup state'))

            def library_patch(name, patch, original_bytes):
                previous = Path.cwd()
                try:
                    os.chdir(tree)
                    success, compiled = api.patch(str(patch), original_bytes,
                        includepaths=[str(tree).encode()], should_reset=True, override_checksum=False)
                finally:
                    os.chdir(previous)
                blocks = [dict(pcoffset=b.pcoffset, snesoffset=b.snesoffset, numbytes=b.numbytes)
                          for b in api.getwrittenblocks()]
                # Preserve the API's order and values before validation/union.
                write_json(output / (name + '-raw-blocks.json'), dict(success=success,
                    input_sha256=hashlib.sha256(original_bytes).hexdigest(),
                    output_sha256=hashlib.sha256(compiled).hexdigest(), written_blocks=blocks,
                    errors=[e.fullerrdata.decode() for e in api.geterrors()],
                    warnings=[e.fullerrdata.decode() for e in api.getwarnings()], prints=api.getprints()))
                self.assertTrue(success, api.geterrors())
                self.assertEqual(len(compiled), 0x400000)
                for block in blocks:
                    a, count, address = (block[k] for k in ('pcoffset', 'numbytes', 'snesoffset'))
                    self.assertTrue(type(a) is int and type(count) is int and
                                    0 <= a < a + count <= 0x400000, block)
                    self.assertTrue(0 <= address <= 0xFFFFFF and address & 0x8000, block)
                    self.assertNotIn(address >> 16, (0x7E, 0x7F))
                    self.assertEqual(L.A.pc(address), a, block)
                return compiled, blocks, api.getsymbolsfile('wla').encode()

            # One byte-identical control tests both unchanged-FF write tracking
            # and the real start after a non-writing skip, through the SAME API.
            control = tree / 'raw-block-control.asm'
            control.write_text('lorom\norg $E38000\nskip $10\ndb $FF\n')
            unchanged = b'\xFF' * 0x400000
            controlled, blocks, _ = library_patch('skip-ff-control', control, unchanged)
            self.assertEqual(controlled, unchanged)
            self.assertEqual(blocks, [dict(pcoffset=0x318010, snesoffset=0xE38010, numbytes=1)])
            # Snapshot already covers the driver/source; the control is an
            # independent source file and must not change the measured snapshot.
            control.rename(output / control.name)
            command = [inputs['CLI']['path'], '--no-title-check', '--fix-checksum=off',
                       '--symbols=wla', str(driver), str(image)]
            run('cli-assembly', command)
            compiled, blocks, api_symbols = library_patch('full-current', driver, seed)
            # Capture the WHOLE patch's actual define table before any other
            # patch can replace API state. Intended source/metadata is not proof
            # that Asar selected every required feature and origin.
            actual_defines = api.getalldefines()
            write_json(output / 'full-current-raw-defines.json', actual_defines)
            expected_defines = dict(receipt.profile(tree)['effective_flags'])
            expected_defines.update(constants, **overrides, LYRA_BUILD_CONTEXT=1,
                REGIONAL_CHECKPOINTS_ENABLED=1, REGIONAL_CHECKPOINTS_BOUND=1)
            self.assertTrue(all(type(value) is int for value in expected_defines.values()),
                            'Expected measurement profile has unresolved source values')
            resolved_defines = {}
            for name, expected in sorted(expected_defines.items()):
                self.assertIn(name, actual_defines, 'Assembled profile omitted !' + name)
                expression = actual_defines[name].strip()
                self.assertRegex(expression, r'\A(?:\$[0-9A-Fa-f]+|[0-9]+)\Z',
                                 'Assembled profile is not literal at !' + name)
                value = api.math(expression)
                resolved_defines[name] = dict(expected=expected, resolved_expression=expression,
                                              evaluated_value=value)
                write_json(output / 'full-current-resolved-defines.json', resolved_defines)
                self.assertEqual(value, expected, 'Assembled profile differs at !' + name)
            (output / 'full-current-library.sfc').write_bytes(compiled)
            (output / 'full-current-library.sym').write_bytes(api_symbols)
            self.assertEqual(compiled, image.read_bytes(), 'Whole library ROM differs from CLI output')
            cli_symbols = image.with_suffix('.sym').read_bytes()
            def all_labels(raw):
                result, active = {}, False
                for line in raw.decode().splitlines():
                    if line.startswith('['):
                        active = line == '[labels]'
                    match = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)', line)
                    if active and match:
                        value = int(match[1] + match[2], 16)
                        self.assertTrue(match[3] not in result or result[match[3]] == value)
                        result[match[3]] = value
                self.assertTrue(result)
                return result
            labels = all_labels(cli_symbols)
            self.assertEqual(all_labels(api_symbols), labels, 'CLI/API symbol maps differ')
            self.assertTrue(blocks, 'Empty raw write coverage cannot prove the composition')
            e3 = [b for b in blocks if b['pcoffset'] < 0x320000 and
                  b['pcoffset'] + b['numbytes'] > 0x318000]
            write_json(output / 'e3-write-intersections.json', e3)
            if hidden_plan is None:
                self.assertEqual(e3, [], 'BOUND0 composition writes the reserved E3 interval')
            else:
                payload = bytes.fromhex(hidden_plan['payload_hex'])
                end = 0x318000+len(payload)
                intervals = sorted((max(b['pcoffset'], 0x318000),
                    min(b['pcoffset']+b['numbytes'], 0x320000)) for b in e3)
                coverage = []
                for lo, hi in intervals:
                    if coverage and lo <= coverage[-1][1]:
                        coverage[-1][1] = max(coverage[-1][1], hi)
                    else:
                        coverage.append([lo, hi])
                self.assertEqual(coverage, [[0x318000, end]], 'E3 raw writes differ from the exact payload')
                self.assertEqual(compiled[0x318000:end], payload)
                self.assertEqual(compiled[end:0x320000], seed[end:0x320000])
                self.assertEqual(labels['Lyra_CurrentHiddenStreamsStart'], 0xE38000)
                self.assertEqual(labels['Lyra_CurrentHiddenStreamsEnd'], 0xE38000+len(payload))
                self.assertEqual(labels['Lyra_CurrentHiddenStreamsReservationBase'], 0xE38000)
                for stream in hidden_plan['streams']:
                    self.assertEqual(labels[stream['label']], stream['snes'])
                    self.assertEqual(labels[stream['label']+'_End'], stream['snes']+stream['byte_count'])
                directory = next(row for row in tables['tables'] if row['name'] == 'hidden_items')
                lo, hi = directory['pc']
                self.assertEqual(compiled[lo:hi], bytes.fromhex(hidden_plan['directory_hex']))
                self.assertEqual(compiled[lo:lo+320], bytes.fromhex(hidden_plan['native_prefix_hex']))
                self.assertEqual(compiled[L.A.pc(0x82A784):L.A.pc(0x82A784)+320],
                                 bytes.fromhex(hidden_plan['native_prefix_hex']))
                for span in native_list_spans:
                    lo, hi = span['pc']
                    self.assertEqual(compiled[lo:hi], bytes.fromhex(span['payload_hex']), span['pc'])
                for flag in ('allocation_granted', 'publication_authorized', 'ordinary_build_ready',
                             'runtime_admission', 'resource_closure_verified', 'pickup_state_selected',
                             'rom_written'):
                    self.assertIs(hidden_plan[flag], False, flag)
            pairs = (
                ('native_readers', 'Lyra_CurrentNativeCodeStart', 'Lyra_CurrentNativeCodeEnd', 0xE0C000, 0xE0D000),
                ('bg128', 'Oracle_ProjectBGPalette_CodeStart', 'Oracle_ProjectBGPalette_CodeEnd', 0xE0D000, 0xE10000),
                ('graphics', 'Oracle_SharedGraphicsRuntimeStart', 'Oracle_SharedGraphicsRuntimeEnd', 0xE28000, 0xE2E000),
                ('area', 'Oracle_AreaTileset_CodeStart', 'Oracle_AreaTileset_CodeEnd', 0xE2E000, 0xE2E200),
                ('atlas', 'Lyra_ResidentAtlasCodeStart', 'Lyra_ResidentAtlasCodeEnd', 0xF88000, 0xF88600),
                ('resources', 'Oracle_ResidentResourceCodeStart', 'Oracle_ResidentResourceCodeEnd', 0xF88600, 0xF88700))
            extents = {}
            for owner, start, end, lo, hi in pairs:
                self.assertEqual(labels[start], lo)
                self.assertTrue(lo < labels[end] <= hi, (owner, labels[end], hi))
                extents[owner] = dict(snes=[lo, labels[end]],
                    pc=[L.A.pc(lo), L.A.pc(labels[end] - 1) + 1],
                    byte_count=labels[end] - lo, remaining_bytes=hi - labels[end])
            self.assertEqual(labels['Oracle_FerryArea30BitmapEnd'], 0xE2ED79)
            write_json(output / 'compiled-extents.json', extents)
            for row in tables['tables']:
                a, b = row['pc']
                self.assertEqual(compiled[a:b], bytes.fromhex(row['payload_hex']), row['name'])
            for row in emission['placements']:
                a, b = row['pc']; offset = row['binary_offset']
                payload = bytes.fromhex(emission['payload_hex'])[offset:offset + b - a]
                self.assertEqual(compiled[a:b], payload, row['label'])
                self.assertEqual(labels[row['label']], row['snes'])
            consumers = L.inspect_current_consumers(compiled, cli_symbols, require_resident=True,
                require_hidden_streams=hidden_streams,
                checkpoint_preview=dict(mode='seeded_checkpoint_preview', source=source,
                                        reviewed=reviewed_preview))
            self.assertEqual(consumers['kind'], L.PREVIEW_CONSUMER_KIND)
            if hidden_streams:
                self.assertEqual(consumers['hidden_streams_adapter']['tail_bank'], 0xE3)
                self.assertEqual(consumers['hidden_streams_adapter']['native_bank'], 0x9B)
            else:
                self.assertNotIn('hidden_streams_adapter', consumers)
            self.assertIs(consumers['current_core_inspected'], True)
            guards = consumers['preview_guards']
            self.assertIs(guards['guards_verified'], True)
            self.assertEqual(guards['scope'], 'seeded_A0_A1_only')
            self.assertIs(consumers['broad_six_role_qualification'], False)
            for flag in ('ordinary_build_ready', 'runtime_admission', 'production_admission',
                         'native_gameplay_verified', 'save_reopen_verified'):
                self.assertIs(consumers[flag], False, flag)
                self.assertIs(guards[flag], False, flag)
            for flag in ('allocation_granted', 'producer_enforcement_verified'):
                self.assertIs(guards[flag], False, flag)
            write_json(output / 'compiled-consumers.json', consumers)

            # Source graph metadata is supplementary and estimated. Supply the
            # explicit fixture defines to these READ-ONLY metadata producers;
            # never forge selected prepare.json or invoke publication admission.
            sys.path.insert(0, str(root / 'Scripts/Generate'))
            try:
                import generate_hooks_json as hooks
                import generate_hack_manifest as manifest
                import asm_source
            finally:
                sys.path.remove(str(root / 'Scripts/Generate'))
            with mock.patch.dict(os.environ, OOS_LYRA_BUILD_CONTEXT='0'):
                defines = asm_source._load_global_defines(tree)
            defines.update(constants)
            defines.update(LYRA_BUILD_CONTEXT=1, REGIONAL_CHECKPOINTS_ENABLED=1, REGIONAL_CHECKPOINTS_BOUND=1)
            with mock.patch.object(hooks, '_load_global_defines', return_value=defines), \
                 mock.patch.object(manifest, '_load_global_defines', return_value=defines):
                reachable = manifest.collect_reachable_asm_sources(tree, defines=defines)
                self.assertTrue({
                    'Oracle_main.asm', 'Overworld/lyra_native_loaders.asm',
                    'Overworld/lyra_actor_stream.asm', 'Overworld/lyra_tail_events.asm',
                    'Overworld/lyra_private_pilot.asm', 'Overworld/lyra_resident_atlas.asm',
                    'Overworld/lyra_resident_resources.asm', 'Overworld/graphics_runtime.asm',
                    'Overworld/area_tilesets.asm', 'Overworld/project_bg_palette.asm',
                    'Overworld/goron_checkpoint.asm', 'Items/ice_rod.asm'
                } <= {p.relative_to(tree).as_posix() for p in reachable})
                write_json(output / 'source-graph.json', [identity(p) for p in reachable])
                args = ['generate_hooks_json.py', '--root', str(tree), '--rom', str(image),
                        '--output', str(output / 'hooks.json')]
                with mock.patch.object(sys, 'argv', args):
                    self.assertEqual(hooks.main(), 0)
                metadata = manifest.generate_manifest(tree, rom_path=image, dev_rom_path=base)
                self.assertFalse(metadata['hook_source']['exact'])
                write_json(output / 'hack_manifest.json', metadata)
            for role, binding in inputs.items():
                self.assertEqual(identity(binding['path']), binding, role)
            self.assertEqual(receipt.source_snapshot(root, receipt_path)['files'], snapshot['files'])
            for path in sorted(output.iterdir()):
                if path.is_file() and path != receipt_path and not path.name.endswith('.source.json'):
                    record('artifact', '--name', path.name, '--path', str(path))
            record('check', '--name', 'whole_output_and_raw_write_coverage', '--status', 'passed',
                '--required', '1', '--detail', ('CLI/API whole ROM and symbols equal; exact E3 payload coverage'
                    if hidden_streams else 'CLI/API whole ROM and symbols equal; raw E3 intersections empty'))
            completed = True
        finally:
            finish = receipt.main(['finish', '--receipt', str(receipt_path),
                '--exit-code', '0' if completed else '1', '--stage', 'host_measurement'])
            self.assertEqual(finish, 0 if completed else 1)


if __name__ == '__main__':
    unittest.main()
