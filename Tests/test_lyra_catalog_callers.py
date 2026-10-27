"""Actual guarded call-site/source contracts; no assembler or CPU executor."""
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from test_lyra_current_port_integration import S, statements

ROOT = Path(__file__).resolve().parents[1]
ZS = 'Overworld/ZSCustomOverworld.asm'
FROZEN = '6e7e5f15d555dffb9f4b3d8807595c9e3f13305f'


def body(text, start, end):
    return text[text.index(start+'\n'):text.index(end+'\n')]


class CatalogCallersSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zs = (ROOT/ZS).read_text()
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV:'0'}):
            cls.disabled = S._load_global_defines(ROOT)
        cls.current = dict(cls.disabled, LYRA_CURRENT_MODE=1,
            LYRA_NATIVE_A1_ENABLED=0, LYRA_PROJECT_DATA_PRESENT=1)

    def active(self, text):
        return statements(text, self.current)

    def test_all_four_callbacks_have_real_guarded_callers(self):
        tokens = self.active(self.zs)
        for callback, count in (
                ('InvalidateCustomGraphicsCache', 4),
                ('SelectCustomGraphicsTransitionSource', 2),
                ('SelectShipIncrementalGraphicsSource', 1),
                ('SharedGraphicsStageNative', 1),
                ('ResolveCustomGraphicsTransitionSheet', 5)):
            with self.subTest(callback=callback):
                self.assertEqual(tokens.count('JSL Oracle_'+callback), count)
        disabled = statements(self.zs, self.disabled)
        self.assertFalse(any('Oracle_SelectCustomGraphicsTransitionSource' in t or
            'Oracle_SelectShipIncrementalGraphicsSource' in t or
            'Oracle_SharedGraphicsStageNative' in t or
            'Oracle_InvalidateCustomGraphicsCache' in t for t in disabled))

    def test_each_transition_dma_reestablishes_bank_and_passes_target_before_count(self):
        nmi = self.active(body(self.zs, 'NMI_UpdateChr_Bg2HalfAndAnimatedLONG:',
                               'NewPrepTransAuxGFX:'))
        for slot in (1, 2):
            expected = [f'LDA.w NewNMISource{slot}', 'STA.w DMA.0_SourceAddrOffsetLow',
                'LDY.b #$7F', 'STY.w DMA.0_SourceAddrBank', 'PHP', 'PHA',
                f'LDA.w NewNMITarget{slot}', 'JSL Oracle_SelectCustomGraphicsTransitionSource',
                'PLA', 'PLP', f'LDA.w NewNMICount{slot}', 'STA.w DMA.0_TransferSizeLow',
                'LDY.b #$01', 'STY.w SNES.DMAChannelEnable']
            at = nmi.index(expected[0])
            self.assertEqual(nmi[at:at+len(expected)], expected)
        self.assertEqual(nmi.count('STY.w SNES.DMAChannelEnable'), 2)
        self.assertEqual(nmi.count('STA.w SNES.VRAMAddrReadWriteLow'), 2)
        # The original count==0 branch precedes each entire DMA/source path.
        self.assertLess(nmi.index('BEQ .skipFirst'), nmi.index('LDA.w NewNMISource1'))
        self.assertLess(nmi.index('BEQ .skipSecond'), nmi.index('LDA.w NewNMISource2'))

    def test_cache_resolution_precedes_skip_and_post_schedule_invalidation_preserves_cursor(self):
        aux = self.active(body(self.zs, 'NewLoadTransAuxGFX:',
                               'NMI_UpdateChr_Bg2HalfAndAnimatedLONG:'))
        self.assertLess(aux.index('JSL Oracle_InvalidateCustomGraphicsCache'),
                        aux.index('CMP.w TransGFXModule_PriorSheets+3'))
        # Resolvers retain XY16, including Y's high byte, at all four aux sites.
        for slot in range(3, 7):
            at = aux.index(f'LDX.w #$0{slot}')
            self.assertEqual(aux[at-1:at+3], ['PHX', f'LDX.w #$0{slot}',
                'JSL Oracle_ResolveCustomGraphicsTransitionSheet', 'PLX'])
        block = self.active(body(self.zs, 'BlockGFXCheck:',
                                 'CheckForChangeGraphicsTransitionLoad:'))
        at = block.index('JSL Oracle_ResolveCustomGraphicsTransitionSheet')
        self.assertEqual(block[at-2:at+4], ['PHX', 'LDX.b $02',
            'JSL Oracle_ResolveCustomGraphicsTransitionSheet', 'PLX', 'STA.b $00', 'SEP #$10'])
        self.assertLess(at, block.index('CMP.b #$FF'))
        self.assertNotIn('JSL Oracle_InvalidateCustomGraphicsCache', block)
        finish = self.active(body(self.zs, 'NewOverworld_FinishTransGfx:', 'BlockGFXCheck:'))
        calls = [i for i,t in enumerate(finish) if t=='JSR.w BlockGFXCheck']
        self.assertEqual(len(calls), 2)
        for at in calls:
            self.assertEqual(finish[at+1:at+3],
                ['JSL Oracle_InvalidateCustomGraphicsCache', 'CPY.b #$08'])

    def test_stage_only_follows_real_conversion_and_incremental_hook_owns_exact5bytes(self):
        stage = self.active(body(self.zs, 'NewPrepTransAuxGFX:', 'InitTilesetsLongCalls:'))
        self.assertEqual(stage[:4], ['LDA.b $04', 'BEQ .dontPrep',
            'JSL.l PrepTransAuxGFX', 'JSL Oracle_SharedGraphicsStageNative'])
        self.assertLess(stage.index('JSL Oracle_SharedGraphicsStageNative'), stage.index('.dontPrep'))
        self.assertEqual(stage[stage.index('.dontPrep')+1], 'RTL')
        self.assertIn('assert read4($008C0E) == $048D7FA9 && read1($008C12) == $43', self.zs)
        self.assertIn('assert pc() == $008C13', self.zs)
        tokens = self.active(self.zs)
        at = next(i for i,t in enumerate(tokens) if t.startswith('org $008C0E'))
        self.assertEqual(tokens[at+1:at+3],
            ['JSL Oracle_SelectShipIncrementalGraphicsSource', 'NOP'])
        self.assertEqual(sum(t.startswith('org $008C0E') for t in tokens), 1)

    def test_disabled_and_historical_a1_instructions_match_frozen6e(self):
        old = subprocess.check_output(['git','-C',str(ROOT),'show',FROZEN+':'+ZS]).decode()
        for defines in (self.disabled, dict(self.disabled, LYRA_CURRENT_MODE=0,
                LYRA_PROJECT_DATA_PRESENT=1, LYRA_NATIVE_A1_ENABLED=1)):
            self.assertEqual(statements(self.zs, defines), statements(old, defines))


if __name__ == '__main__':
    unittest.main()
