"""Current tail-event source contracts; native save/reopen remains required."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Scripts/Generate'))
sys.path.insert(0, str(ROOT/'Scripts/Build'))
import asm_source as S
import generate_hack_manifest as H
import lyra_native_state as N


class CurrentTailEventsTest(unittest.TestCase):
    def test_default_build_has_no_event_module_or_storage_binding(self):
        defines = S._load_global_defines(ROOT)
        self.assertEqual((defines['LYRA_CURRENT_EVENTS_ENABLED'], defines['LYRA_CURRENT_EVENTS_BOUND']), (0, 0))
        self.assertNotIn('LYRA_CURRENT_EVENT_BASE', defines)
        self.assertNotIn(ROOT/'Overworld/lyra_tail_events.asm', H.collect_reachable_asm_sources(ROOT))
        source = (ROOT/'Oracle_main.asm').read_text()
        self.assertIn('!LYRA_CURRENT_EVENTS_ENABLED == 0 || !LYRA_CURRENT_MODE == 1', source)
        self.assertIn('!LYRA_CURRENT_EVENTS_ENABLED == 0 || !LYRA_CURRENT_EVENTS_BOUND == 1', source)

    def test_fixed_native_hooks_keep_complete_preimages_and_actual_widths(self):
        source = (ROOT/'Overworld/lyra_tail_events.asm').read_text()
        loads = {int(site,16) for site in re.findall(r'org \$([0-9A-F]{6}) : JSL Lyra_TailEvent_Load', source)}
        stores = {int(site,16) for site in re.findall(r'org \$([0-9A-F]{6}) : JSL Lyra_TailEvent_Store', source)}
        self.assertEqual(loads, set(N.TAIL_LOAD_SITES))
        self.assertEqual(stores, {row[0] for row in N.TAIL_STORE_SITES})
        for site, opcode in [(a,'BF') for a in loads]+[(a,'9F') for a in stores]:
            self.assertIn(f'assert read1(${site:06X}) == ${opcode} && read3(${site:06X}+1) == $7EF280', source)
        self.assertEqual(source.count('expected_m=8 '), len(loads)+len(stores))
        self.assertIn('expected_m=16 name=TailEventLoad1BC902', source)
        self.assertIn('assert read3($1BC906) == $000229', source)
        self.assertIn('!LYRA_CURRENT_EVENT_BASE+$20 <= $7EF4FE', source)
        self.assertIn('!LYRA_CURRENT_EVENT_VERSION >= !LYRA_CURRENT_EVENT_BASE+$20', source)

    def test_project_callers_switch_together_without_changing_legacy_instructions(self):
        for relative in ('Overworld/overlays.asm','Sprites/Bosses/octoboss.asm',
                         'Sprites/NPCs/goron.asm','Util/item_cheat.asm'):
            source = (ROOT/relative).read_text()
            def active(flag):
                return '\n'.join(line for _,line,_ in S._iter_active_lines(source.splitlines(),
                    dict(S._load_global_defines(ROOT), LYRA_CURRENT_EVENTS_ENABLED=flag)))
            legacy, current = active(0), active(1)
            legacy_loads = len(re.findall(r'LDA\.l \$7EF280,\s*X', legacy))
            legacy_stores = len(re.findall(r'STA\.l \$7EF280,\s*X', legacy))
            self.assertGreater(legacy_loads, 0, relative)
            self.assertEqual(current.count('JSL Lyra_TailEvent_Load'), legacy_loads, relative)
            self.assertEqual(current.count('JSL Lyra_TailEvent_Store'), legacy_stores, relative)
            self.assertNotRegex(current, r'(?:LDA|STA)\.l \$7EF280,\s*X')
        checkpoint = (ROOT/'Overworld/goron_checkpoint.asm').read_text()
        self.assertLess(checkpoint.index('JSL Lyra_TailEvent_MigrateSave'), checkpoint.index('LDA.l SpawnPoint'))
        module = (ROOT/'Overworld/lyra_native_loaders.asm').read_text()
        self.assertLess(module.index('incsrc "lyra_tail_events.asm"'), module.index('Lyra_CurrentNativeCodeEnd:'))


class LegacyEmptyBombAsarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import lyra_native_loaders as L
        cls.asar=os.environ.get('ASAR_BIN') or shutil.which('asar')
        if not cls.asar:raise unittest.SkipTest('Asar unavailable')
        cls.tmp=tempfile.TemporaryDirectory(prefix='oos-empty-bomb-asar-')
        cls.addClassCleanup(cls.tmp.cleanup);cls.folder=Path(cls.tmp.name)
        seed=bytearray(0x400000)
        def put(at,raw):seed[L.A.pc(at):L.A.pc(at)+len(raw)]=raw
        for at in N.TAIL_LOAD_SITES:put(at,bytes.fromhex('bf80f27e'))
        for at,_ in N.TAIL_STORE_SITES:put(at,bytes.fromhex('9f80f27e'))
        put(0x02EF40,bytes.fromhex('e230'));put(0x02EF54,bytes.fromhex('a68a'))
        put(0x02EF5A,bytes.fromhex('2902f01b'))
        put(0x1BC906,bytes.fromhex('290200'))
        cls.seed=bytes(seed);cls.images={};cls.labels={}
        for enabled in (0,1):
            asm=cls.folder/f'guard-{enabled}.asm';rom=asm.with_suffix('.sfc')
            text=('lorom\n!LYRA_CURRENT_MODE = 1\n!LYRA_CURRENT_EVENTS_ENABLED = 1\n'
                  '!LYRA_CURRENT_EVENTS_BOUND = 1\n!LYRA_CURRENT_EVENT_BASE = $7EF4C0\n'
                  '!LYRA_CURRENT_EVENT_VERSION = $7EF4E0\n!LYRA_CURRENT_EVENT_MARKER = $A1\n'
                  '!LYRA_CURRENT_HIDDEN_STREAMS_BOUND = 0\n'
                  f'!LYRA_CURRENT_LEGACY_EMPTY_RESOURCES = {enabled}\norg $E0C000\n'
                  + (ROOT/'Overworld/lyra_tail_events.asm').read_text())
            asm.write_text(text);rom.write_bytes(cls.seed)
            result=subprocess.run([cls.asar,'--no-title-check','--fix-checksum=off',
                '--symbols=wla',str(asm),str(rom)],capture_output=True,text=True,timeout=30)
            if result.returncode:raise AssertionError(result.stdout+result.stderr)
            cls.images[enabled]=rom.read_bytes();cls.labels[enabled]=L._labels(rom.with_suffix('.sym').read_bytes())

    def body(self,enabled,name,size):
        import lyra_native_loaders as L
        at=L.A.pc(self.labels[enabled][name]);return self.images[enabled][at:at+size]

    def test_actual_emitted_guard_preserves_sram_and_native_flags(self):
        from test_lyra_native_loaders import CPU
        body=self.body(1,'Lyra_TailEvent_LoadLegacyEmptyBomb',27)
        self.assertEqual(body.hex(),'08c210e0a000900de0c000b00828bf20f47e29fd6b28bf80f27e6b')
        for ix in (0,0x10):
            for cv in (0,1,0x40,0x41):
                for area in (0,0x9F,0xA0,0xBF,0xC0,0xFF)+(() if ix else (0x100,0x1A0,0xFFFF)):
                    for flag in range(256):
                        p=0x20|ix|cv;cpu=CPU(body,a=0xA512,x=area,y=0x37,p=p,db=0x19,d=0x60)
                        at=0x7EF4C0+area-0xA0 if 0xA0<=area<0xC0 else 0x7EF280+area
                        cpu.put(at,bytes([flag]));before=dict(cpu.mem);cpu.run()
                        expected=flag&0xFD if 0xA0<=area<0xC0 else flag
                        self.assertEqual(cpu.a,0xA500|expected)
                        self.assertEqual((cpu.x,cpu.y,cpu.db,cpu.d),(area,0x37,0x19,0x60))
                        self.assertEqual(cpu.p&~0x82,p&~0x82);self.assertEqual(cpu.stack,[])
                        self.assertEqual(cpu.mem,before);self.assertEqual(cpu.writes,[])
                        if 0xA0<=area<0xC0:self.assertEqual(cpu.a&2,0)

    def test_unsupported_bank_and_changed_caller_width_refuse_assembly(self):
        base=(self.folder/'guard-1.asm').read_text()
        for name,text,seed in (
            ('bank',base.replace('HIDDEN_STREAMS_BOUND = 0','HIDDEN_STREAMS_BOUND = 1'),self.seed),
            ('mode',base,self.seed[:0x16F40]+b'\xc2\x30'+self.seed[0x16F42:])):
            with self.subTest(name=name):
                asm=self.folder/(name+'.asm');rom=asm.with_suffix('.sfc')
                asm.write_text(text);rom.write_bytes(seed)
                result=subprocess.run([self.asar,'--no-title-check','--fix-checksum=off',str(asm),str(rom)],
                                      capture_output=True,text=True,timeout=30)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('assertion failed',result.stderr.lower())

    def test_generic_reader_still_exposes_real_bomb_bit_at_offset_zero(self):
        from test_lyra_native_loaders import CPU
        for enabled in (0,1):
            body=self.body(enabled,'Lyra_TailEvent_Load',25)
            cpu=CPU(body,a=0xAD00,x=0xA0,p=0x30)
            cpu.put(0x7EF4C0,b'\x02');cpu.run()
            self.assertEqual(cpu.a,0xAD02);self.assertEqual(cpu.writes,[])
        self.assertNotIn('Lyra_TailEvent_LoadLegacyEmptyBomb',self.labels[0])

    def test_existing_store_and_migration_bytes_are_identical(self):
        # Their positions may move; their instructions and save semantics do not.
        for name,size in (('Lyra_TailEvent_Load',25),('Lyra_TailEvent_Store',25),
                          ('Lyra_TailEvent_MigrateSave',39)):
            self.assertEqual(self.body(0,name,size),self.body(1,name,size),name)


if __name__ == '__main__':
    unittest.main()
