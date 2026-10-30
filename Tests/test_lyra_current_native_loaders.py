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


if __name__ == '__main__':
    unittest.main()
