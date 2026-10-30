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


if __name__ == '__main__':
    unittest.main()
