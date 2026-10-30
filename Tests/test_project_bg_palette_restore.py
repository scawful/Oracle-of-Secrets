"""BG128 protocol oracle + source binding tests, not 65816/native execution."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Protocol:
    """Independent transaction oracle with visibly distinct fade/reference data."""
    def __init__(self):
        self.reference = list(range(128))
        self.effective = list(range(1000, 1128))
        self.obj = list(range(128))
        self.backing = None
        self.reset()

    def reset(self):
        self.state, self.area = 0, 255

    def depart(self):
        if self.state in (1, 2) and 0 <= self.area < 192:
            self.state = 0
            self.reference[:], self.effective[:] = map(list, self.backing)
        self.reset()

    def begin(self, destination):
        self.depart()
        if 0 <= destination < 192:
            self.area = destination

    def complete(self, area, override, *, both, observe=None):
        if self.state == 2:
            return
        if self.state != 0 or self.area != area or not 0 <= area < 192 or override is None:
            self.reset()
            return
        self.backing = list(self.reference), list(self.effective)
        if observe:
            observe(self)
        self.area, self.state = area, 1
        # Deliberately non-idempotent tint: detects a duplicate application.
        self.reference[:] = [word + 1 for word in override]
        if both:
            self.effective[:] = self.reference
        self.state = 2


class RestoreProtocolTest(unittest.TestCase):
    def test_power_intro_cold_invalidate_before_use(self):
        p = Protocol()
        p.state, p.area = 2, 17  # plausible uninitialized flags
        p.reset()
        self.assertEqual((p.state, p.area), (0, 255))
        p.begin(18)  # no access to nonexistent backing
        self.assertEqual(p.reference, list(range(128)))
        p.reset()  # destructive intro/cold load cannot reuse the snapshot
        p.complete(18, [7] * 128, both=True)
        self.assertEqual((p.state, p.area), (0, 255))

    def test_restore_source_even_after_destination_area_changed(self):
        p = Protocol()
        native = (p.reference[:], p.effective[:])
        p.begin(17)
        p.complete(17, [9] * 128, both=True)
        p.begin(18)
        self.assertEqual((p.reference, p.effective), native)
        p.reference[4] = 333  # destination partial writer must win
        p.complete(18, None, both=False)
        self.assertEqual(p.reference[4], 333)
        self.assertEqual(p.state, 0)

    def test_native_capture_validity_last_distinct_arrays_obj_preserved(self):
        p = Protocol()
        p.begin(17)
        native = p.reference[:], p.effective[:]
        seen = []
        p.complete(17, [5] * 128, both=False,
                   observe=lambda row: seen.append((row.state, row.backing)))
        self.assertEqual(seen, [(0, native)])
        self.assertNotEqual(p.backing[0], p.backing[1])
        self.assertEqual(p.effective, native[1])
        self.assertEqual(p.obj, list(range(128)))
        p.begin(18)
        self.assertEqual((p.reference, p.effective), native)

    def test_same_id_skipped_main_and_single_tint(self):
        p = Protocol()
        p.begin(17)
        p.complete(17, [5] * 128, both=True)
        p.begin(18)  # native main ID is unchanged; no main writer runs
        p.complete(18, [7] * 128, both=True)
        self.assertEqual(p.reference, [8] * 128)
        first = tuple(map(tuple, p.backing))
        p.complete(18, [7] * 128, both=True)  # no contaminated recapture
        self.assertEqual(tuple(map(tuple, p.backing)), first)
        self.assertEqual(p.reference, [8] * 128)

    def test_unknown_state_and_wrong_capture_context_refuse(self):
        p = Protocol()
        p.state, p.area = 0x7F, 17
        p.begin(18)  # no backing read on random nonzero state
        self.assertEqual(p.reference, list(range(128)))
        p.complete(19, [9] * 128, both=True)
        self.assertEqual((p.state, p.area), (0, 255))

    def test_exact_source_ledger_and_byte_flag_stores(self):
        ledger = json.loads((ROOT / 'Config/allocation_ownership.json').read_text())
        row, = (r for r in ledger['claims'] if r['id'] == 'ProjectBGPaletteNativeUnderlay')
        self.assertEqual((row['base'], row['size']), (0x7ECA00, 514))
        self.assertEqual([(f['offset'], f['size']) for f in row['fields']],
                         [(0, 256), (256, 256), (512, 1), (513, 1)])
        self.assertFalse(row['source_reservation']['activation'])
        for source in row['provenance']:
            record = ledger['sources'][source]
            self.assertEqual(hashlib.sha256((ROOT / record['path']).read_bytes()).hexdigest(),
                             record['sha256'])
        asm = (ROOT / 'Overworld/project_bg_palette.asm').read_text()
        self.assertNotIn('org $1BEEE2', asm)  # original near/long frame unchanged
        self.assertIn('LDA.b #$01 : STA.l ProjectBGPalette_RestoreState', asm)
        self.assertIn('LDA.b #$02 : STA.l ProjectBGPalette_RestoreState', asm)
        self.assertIn('LDA.l ProjectBGPalette_NativeEffective, X : STA.l $7EC500, X', asm)
        self.assertNotIn('STA.l $7EC400', asm)
        self.assertEqual(asm.count('CPX.w #$0100'), 3)

    def test_reset_owner_and_unconditional_completion_source(self):
        masks = (ROOT / 'Masks/mask_routines.asm').read_text()
        self.assertIn('if !ProjectBG128_OwnsStartup == 0', masks)
        asm = (ROOT / 'Overworld/project_bg_palette.asm').read_text()
        self.assertIn('JML StartupMasks', asm)
        self.assertIn('ProjectBGPalette_IntroReset:', asm)
        cold = (ROOT / 'Overworld/goron_checkpoint.asm').read_text()
        self.assertLess(cold.index('JSL ProjectBGPalette_RestoreAndInvalidate'), cold.index('LDA.l SpawnPoint'))
        zs = (ROOT / 'Overworld/ZSCustomOverworld.asm').read_text()
        transition = zs[zs.index('CheckForChangeGraphicsTransitionLoad:\n'):]
        self.assertLess(transition.index('JSL Oracle_ProjectBGPalette_Begin'),
                        transition.index('CMP.w $0AB3'))
        normal_tail = transition[transition.index('.dontUpdateBGColor1\n\n'):]
        self.assertIn('JSL Oracle_ProjectBGPalette_CompleteBoth', normal_tail.split('RTS', 1)[0])
        mosaic_tail = transition[transition.index('CheckForChangeGraphicsTransitionLoadRetrun:'):]
        self.assertIn('JSL Oracle_ProjectBGPalette_CompleteBuffer', mosaic_tail.split('RTS', 1)[0])
        time = (ROOT / 'Overworld/time_system.asm').read_text()
        update = time[time.index('TimeSystem_UpdatePalettes:\n'):].split('CheckForSongOfTime:', 1)[0]
        self.assertLess(update.index('JSL RefreshOverworldBackdrop'),
                        update.index('JSL ProjectBGPalette_CompleteBoth'))


class ActualCallerOrderTest(unittest.TestCase):
    def applied(self):
        p = Protocol()
        native = p.reference[:], p.effective[:]
        p.begin(0xBF)
        p.complete(0xBF, [0x1234] * 128, both=True)
        return p, native

    def native_main_aux(self, p):
        # Same shape as the actual native main/aux producers; HUD and LOW7
        # remain separate. In particular word48/C360 is not one of these.
        for row in range(2, 7):
            for col in range(1, 8):
                p.reference[row * 16 + col] = 200 + row * 16 + col
        p.begin(0xBF)  # actual second Begin at hooked 0ED5A8
        for row in range(2, 8):
            for col in range(9, 16):
                p.reference[row * 16 + col] = 400 + row * 16 + col

    def normal_load(self, p, *, special):
        order = []
        p.begin(0xBF)
        order.append('outer-begin')
        self.native_main_aux(p)
        order.append('main-then-aux-begin-and-writers')
        self.assertEqual(p.state, 0)  # not yet project-applied
        p.reference[0] = p.reference[32] = 0
        order.append('backdrop')
        if special:
            p.effective[32:] = [0] * 96
            p.effective[:32] = p.reference[:32]
        else:
            p.effective[:] = p.reference
        order.extend(('native-cache', 'fixed-color'))
        native = p.reference[:], p.effective[:]
        p.complete(0xBF, [7] * 128, both=not special)
        order.append('complete')
        return order, native

    def test_normal_outer_final_state_after_second_aux_begin(self):
        p = Protocol()
        order, native = self.normal_load(p, special=False)
        self.assertEqual(order[-3:], ['native-cache', 'fixed-color', 'complete'])
        self.assertEqual((p.state, p.area), (2, 0xBF))
        self.assertEqual(p.backing, native)
        self.assertEqual(p.reference, [8] * 128)
        self.assertEqual(p.effective, [8] * 128)

    def test_special_outer_completion_preserves_effective_fade_black(self):
        p = Protocol()
        _, native = self.normal_load(p, special=True)
        self.assertEqual((p.state, p.area), (2, 0xBF))
        self.assertEqual(p.reference, [8] * 128)
        self.assertEqual(p.effective, native[1])
        self.assertEqual(p.effective[32:], [0] * 96)
        self.assertEqual(p.backing, native)

    def test_warm_continue_restores_holes_before_partial_native_reload(self):
        p, native = self.applied()
        p.depart()  # actual Module05 warm boundary, not destructive Reset
        self.assertEqual((p.state, p.area), (0, 255))
        self.assertEqual((p.reference, p.effective), native)
        _, reloaded = self.normal_load(p, special=False)
        self.assertEqual(reloaded[0][48], native[0][48])
        self.assertEqual(p.backing[0][48], native[0][48])
        self.assertEqual((p.state, p.area), (2, 0xBF))

    def test_old_reset_is_a_negative_control_for_warm_hole_contamination(self):
        p, native = self.applied()
        p.reset()  # cab24083 discarded validity without restoring colors
        _, reloaded = self.normal_load(p, special=False)
        self.assertNotEqual(reloaded[0][48], native[0][48])
        self.assertEqual(reloaded[0][48], 0x1235)

    def test_indoor_departure_terminal_hole_and_later_outdoor_no_stale_restore(self):
        p, native = self.applied()
        p.depart()  # runs before native02C55E sprite/HUD/UW partial producers
        # Native SetBGAndFixedColorBlack and UW6x15 color producer.
        p.reference[0] = p.reference[32] = 0
        for row in range(2, 8):
            for col in range(1, 16):
                p.reference[row * 16 + col] = 900 + row * 16 + col
        terminal = p.reference[:], p.effective[:]
        self.assertEqual(terminal[0][48], native[0][48])  # C360 is a hole
        self.assertEqual((p.state, p.area), (0, 255))
        p.begin(0xA0)
        self.assertEqual((p.reference, p.effective), terminal)
        self.assertNotEqual(p.reference[49], native[0][49])

    def test_unknown_warm_state_never_reads_uninitialized_backing(self):
        p = Protocol()
        p.state, p.area = 0x7F, 0xBF
        p.depart()
        self.assertEqual((p.state, p.area), (0, 255))
        self.assertEqual(p.reference, list(range(128)))

    def test_source_exact_outer_warm_indoor_bindings(self):
        zs = (ROOT / 'Overworld/ZSCustomOverworld.asm').read_text()
        outer = zs[zs.index('; This outer load also runs auxiliary'):]
        outer = outer.split('; Set darkness level to zero for the overworld.', 1)[0]
        self.assertIn('JSR.w ProjectBGPalette_AreaNativeBody', outer)
        self.assertLess(outer.index('JSL.l Overworld_LoadPalettes'),
                        outer.index('JSL.l Palette_SetOwBgColor_Long'))
        self.assertLess(outer.index('JSR.w SpecialOverworld_CopyPalettesToCache'),
                        outer.index('JSL.l Overworld_SetFixedColorAndScroll'))
        fixed = outer.index('JSL.l Overworld_SetFixedColorAndScroll')
        self.assertLess(fixed, outer.index('JSL Oracle_ProjectBGPalette_CompleteBoth'))
        self.assertLess(fixed, outer.index('JSL Oracle_ProjectBGPalette_CompleteBuffer'))
        asm = (ROOT / 'Overworld/project_bg_palette.asm').read_text()
        indoor = asm.split('ProjectBGPalette_IndoorDeparture:', 1)[1].split(
            'ProjectBGPalette_NativeAllBegin:', 1)[0]
        self.assertLess(indoor.index('JSL ProjectBGPalette_RestoreAndInvalidate'),
                        indoor.index('JSL $1BEC77'))
        self.assertIn('JML $02C562', indoor)
        self.assertIn('assert read4($02C55E) == $1BEC7722', asm)
        self.assertNotIn('org $1BEEE2', asm)
        cold = (ROOT / 'Overworld/goron_checkpoint.asm').read_text()
        self.assertIn('JSL ProjectBGPalette_RestoreAndInvalidate', cold)
        self.assertNotIn('JSL ProjectBGPalette_Reset', cold)
        reset = asm.split('ProjectBGPalette_Reset:', 1)[1].split(
            'ProjectBGPalette_Startup:', 1)[0]
        self.assertNotIn('NativeReference, X', reset)


if __name__ == '__main__':
    unittest.main()
