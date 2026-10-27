"""Current tail-event source contracts; native save/reopen remains required."""
from pathlib import Path
import re
import sys
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
        self.assertEqual(source.count('expected_m=8 '), len(loads)+len(stores)-1)
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


if __name__ == '__main__':
    unittest.main()
