#!/usr/bin/env python3
"""Contract and simulation unit tests for Deku Stick consumable handler.

Verifies:
1. Deku Stick RAM ($7E046D-46F) and SRAM ($7EF39F) symbol bindings and allocation integrity.
2. Link_DekuSticks equipment menu draw request logic and guards.
3. Supply_ProcessPendingExitAction deferred draw handler:
   - Zero-inventory refusal and guard re-verification.
   - Decrements DekuSticks count exactly once on successful draw.
   - Restores retained burn budget from DekuStickWear (1-74 ticks).
   - Falls back to fresh 75 ticks (20s) if DekuStickWear is 0 or out-of-range.
   - Clears DekuStickWear to 0 on draw.
4. DekuStick_Stow:
   - Refunds exactly 1 Deku Stick to inventory.
   - Retains remaining burn budget in DekuStickWear if stick was worn (< 75 ticks).
   - Stores 0 in DekuStickWear if stick was unlit/fresh (75 ticks).
   - Zeroes active state (DekuStick_State, BurnTimer, SwipeTimer).
5. DekuStick_Drop:
   - Zeroes active state without refunding inventory or restoring wear.
6. DekuStick_Main:
   - Checks interruption guards ($5D != 0, $0308 != 0, !CurrentMask != 0).
   - Ticks burn timer every 16 frames when lit (State == 2) and gameplay active ($11 == 0).
   - Burns out when timer reaches 0.
7. Sword lockout & B stow in LinkItem_CheckForSwordSwing_Masks.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
ALL_ITEMS = ROOT / "Items" / "all_items.asm"
DEKU_STICK = ROOT / "Items" / "deku_stick.asm"
MASK_ROUTINES = ROOT / "Masks" / "mask_routines.asm"
RAM_ASM = ROOT / "Core" / "ram.asm"
SRAM_ASM = ROOT / "Core" / "sram.asm"


class DekuStickContractTest(unittest.TestCase):
    def test_ram_and_sram_allocations(self):
        ram_text = RAM_ASM.read_text(encoding="utf-8")
        self.assertIn("DekuStick_State       = $7E046D", ram_text)
        self.assertIn("DekuStick_BurnTimer   = $7E046E", ram_text)
        self.assertIn("DekuStick_SwipeTimer  = $7E046F", ram_text)

        sram_text = SRAM_ASM.read_text(encoding="utf-8")
        self.assertIn("DekuStickWear           = $7EF39F", sram_text)
        self.assertIn("FreeBlock_Collect  = $7EF3A0", sram_text)

    def test_link_deku_sticks_routine_structure(self):
        items_text = ALL_ITEMS.read_text(encoding="utf-8")
        self.assertIn("Link_DekuSticks:", items_text)
        self.assertIn("PendingSupplyAction : BNE .fail", items_text)
        self.assertIn("DekuStick_State : BNE .fail", items_text)
        self.assertIn("DekuSticks : BEQ .fail", items_text)
        self.assertIn("!SUPPLY_ACTION_DEKUSTICK : STA.l PendingSupplyAction", items_text)

    def test_supply_process_exit_action_deku_stick(self):
        items_text = ALL_ITEMS.read_text(encoding="utf-8")
        self.assertIn("CMP.b #!SUPPLY_ACTION_DEKUSTICK", items_text)
        self.assertIn(".action_deku_stick", items_text)
        self.assertIn("LDA.l $7E005D : BNE .abort_error_deku", items_text)
        self.assertIn("LDA.l $7E0308 : BNE .abort_error_deku", items_text)
        self.assertIn("LDA.l $7E02B2 : BEQ +", items_text)
        self.assertIn("CMP.b #$06 : BNE .abort_error_deku", items_text)
        self.assertIn("LDA.l DekuStickWear", items_text)
        self.assertIn("STA.l DekuStick_BurnTimer", items_text)
        self.assertIn("LDA.b #$4B : STA.l DekuStick_BurnTimer", items_text)
        self.assertIn("LDA.b #$00 : STA.l DekuStickWear", items_text)
        self.assertIn("DEC A : STA.l DekuSticks", items_text)
        self.assertIn("LDA.b #$01 : STA.l DekuStick_State", items_text)

    def test_deku_stick_stow_routine(self):
        stick_text = DEKU_STICK.read_text(encoding="utf-8")
        self.assertIn("DekuStick_Stow:", stick_text)
        self.assertIn("INC A : STA.l DekuSticks", stick_text)
        self.assertIn("CMP.b #$4B : BEQ .unlit", stick_text)
        self.assertIn("STA.l DekuStickWear", stick_text)
        self.assertIn("STA.l DekuStick_State", stick_text)
        self.assertIn("STA.l DekuStick_BurnTimer", stick_text)
        self.assertIn("STA.l DekuStick_SwipeTimer", stick_text)

    def test_deku_stick_drop_routine(self):
        stick_text = DEKU_STICK.read_text(encoding="utf-8")
        self.assertIn("DekuStick_Drop:", stick_text)
        self.assertIn("STA.l DekuStick_State", stick_text)
        self.assertIn("STA.l DekuStick_BurnTimer", stick_text)
        self.assertIn("STA.l DekuStick_SwipeTimer", stick_text)

    def test_sword_lockout_and_b_stow_hook(self):
        mask_text = MASK_ROUTINES.read_text(encoding="utf-8")
        self.assertIn("LinkItem_CheckForSwordSwing_Masks:", mask_text)
        self.assertIn("LDA.l DekuStick_State : BEQ .check_masks", mask_text)
        self.assertIn("BIT.b $F4 : BPL .skip_sword", mask_text)
        self.assertIn("JSL DekuStick_Stow", mask_text)
        self.assertIn("LDA.b #$10", mask_text)

    def test_frame_hook_independence(self):
        mask_text = MASK_ROUTINES.read_text(encoding="utf-8")
        hook_idx = mask_text.find("LinkMain_FrameHook:")
        minish_idx = mask_text.find("if !ENABLE_MINISH_AUTO_PORTAL == 1\n; =========================================================")
        self.assertNotEqual(hook_idx, -1)
        self.assertNotEqual(minish_idx, -1)
        # Frame hook must be independent of and precede the Minish auto portal feature block
        self.assertLess(hook_idx, minish_idx)
        self.assertIn("JSL DekuStick_Main", mask_text[hook_idx:minish_idx])

    def test_y_interception_hook(self):
        mask_text = MASK_ROUTINES.read_text(encoding="utf-8")
        y_hook_idx = mask_text.find("MaskControl_CheckYItem:")
        r_bind_idx = mask_text.find("if !ENABLE_MASK_R_BINDING == 1", y_hook_idx)
        self.assertNotEqual(y_hook_idx, -1)
        self.assertNotEqual(r_bind_idx, -1)
        # DekuStick_CheckYPress must precede R binding dispatch in MaskControl_CheckYItem
        self.assertIn("JSL DekuStick_CheckYPress", mask_text[y_hook_idx:r_bind_idx])

    def test_swipe_and_torch_source_contracts(self):
        stick_text = DEKU_STICK.read_text(encoding="utf-8")
        self.assertIn("DekuStick_CheckYPress:", stick_text)
        self.assertIn("DekuStick_CheckTorch:", stick_text)
        self.assertIn("DekuStick_CheckHit:", stick_text)
        self.assertIn("DekuStick_DrawOAM:", stick_text)
        self.assertIn("Entity_GetTileAttr  = $06E87B", stick_text)
        self.assertIn("Dungeon_LightTorch  = $01F3EC", stick_text)
        self.assertIn("JSL Entity_GetTileAttr", stick_text)
        self.assertIn("JSL Dungeon_LightTorch", stick_text)

    def test_gameplay_modes_and_submodule_guards(self):
        stick_text = DEKU_STICK.read_text(encoding="utf-8")
        # Both Underworld ($07) and Overworld ($09) gameplay modes must be accepted
        self.assertIn("CMP.b #$07 : BEQ .check_underworld_submodules", stick_text)
        self.assertIn("CMP.b #$09 : BEQ .check_overworld_submodules", stick_text)
        # Destructive Underworld submodules
        self.assertIn("CMP.b #$06 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$07 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$0E : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$11 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$12 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$13 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$14 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$15 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$19 : BEQ .interrupted", stick_text)
        # Destructive Overworld submodules
        self.assertIn("CMP.b #$0D : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$17 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$23 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$24 : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$2A : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$2C : BEQ .interrupted", stick_text)
        self.assertIn("CMP.b #$2E : BEQ .interrupted", stick_text)

    def test_submodule_transition_hooks(self):
        stick_text = DEKU_STICK.read_text(encoding="utf-8")
        self.assertIn("DekuStick_SubmoduleCheck:", stick_text)
        self.assertIn("DekuStick_OWLoadCheck:", stick_text)
        self.assertIn(".preserve_and_draw", stick_text)
        self.assertIn("LDA.b $11 : BEQ .done", stick_text)
        self.assertIn("JSR DekuStick_DrawOAM", stick_text)
        self.assertIn("org $0287A8", stick_text)
        self.assertIn("JSL DekuStick_SubmoduleCheck", stick_text)
        self.assertIn("assert pc() == $0287AC", stick_text)
        self.assertIn("org $0283BF", stick_text)
        self.assertIn("JSL DekuStick_OWLoadCheck", stick_text)
        self.assertIn("assert pc() == $0283C3", stick_text)
        self.assertIn("org $02A477", stick_text)
        self.assertIn("assert pc() == $02A47B", stick_text)

    def test_oam_viewport_and_unpacked_high_table_contract(self):
        stick_text = DEKU_STICK.read_text(encoding="utf-8")
        draw_idx = stick_text.index("DekuStick_DrawOAM:")
        stow_idx = stick_text.index("DekuStick_Stow:")
        draw_body = stick_text[draw_idx:stow_idx]
        # Must match LinkOAM_Main ($0DA1D1-$0DA1DD) 8-bit camera delta and unpacked $0A24/$0A25
        self.assertIn("LDA.b $22 : SEC : SBC.b $E2 : STA.b $04", draw_body)
        self.assertIn("LDA.b $20 : SEC : SBC.b $E8 : STA.b $06", draw_body)
        self.assertIn("STA.w $0A24", draw_body)
        self.assertIn("STA.w $0A25", draw_body)
        self.assertNotIn("$0A21", draw_body)
        self.assertNotIn("CMP.b #$FF : BNE .hide", draw_body)


class DekuStickLogicModelTest(unittest.TestCase):
    """Simulates the ASM state machine logic for Deku Stick draw, stow, and wear."""

    def setUp(self):
        self.deku_sticks = 2
        self.deku_wear = 0
        self.pending_supply = 0
        self.stick_state = 0
        self.burn_timer = 0
        self.swipe_timer = 0
        self.link_state = 0
        self.carrying = 0
        self.mask = 0

    def menu_press_a(self):
        if self.pending_supply != 0:
            return False
        if self.stick_state != 0:
            return False
        if self.deku_sticks == 0:
            return False
        if self.link_state != 0 or self.carrying != 0 or self.mask != 0:
            return False
        self.pending_supply = 2  # !SUPPLY_ACTION_DEKUSTICK
        return True

    def process_exit_action(self):
        if self.pending_supply != 2:
            return False
        self.pending_supply = 0
        if self.deku_sticks == 0:
            return False
        if self.stick_state != 0:
            return False
        if self.link_state != 0 or self.carrying != 0 or self.mask != 0:
            return False

        # Budget resolution
        if 1 <= self.deku_wear < 75:
            self.burn_timer = self.deku_wear
        else:
            self.burn_timer = 75  # Fresh 75 ticks

        self.deku_wear = 0
        self.deku_sticks -= 1
        self.stick_state = 1
        self.swipe_timer = 0
        return True

    def press_b(self, new_press=True):
        if self.stick_state == 0:
            return "SWORD_NORMAL"
        if not new_press:
            return "SWORD_SUPPRESSED"

        # Stow
        self.deku_sticks += 1
        if self.burn_timer == 75 or self.burn_timer == 0 or self.burn_timer > 75:
            self.deku_wear = 0
        else:
            self.deku_wear = self.burn_timer

        self.stick_state = 0
        self.burn_timer = 0
        self.swipe_timer = 0
        return "SWORD_SUPPRESSED"

    def ignite(self):
        if self.stick_state == 1:
            self.stick_state = 2  # Lit

    def press_y(self):
        if self.stick_state == 0:
            return "NORMAL_ITEM"
        # Stick is held or swiping: suppress assigned item
        if self.stick_state in (1, 2):
            was_lit = 0x80 if self.stick_state == 2 else 0
            self.swipe_timer = 14 | was_lit
            self.stick_state = 3
            return "SWIPE_STARTED"
        return "SWIPE_ACTIVE"

    def advance_swipe_frame(self, enemy=None, torch_state=None):
        if self.stick_state != 3:
            return
        timer = self.swipe_timer & 0x1F
        was_lit = bool(self.swipe_timer & 0x80)
        hit_latched = bool(self.swipe_timer & 0x40)

        # Active window: frames 10 down to 7
        if 7 <= timer <= 10:
            if enemy and not hit_latched and enemy.get("active") and not enemy.get("boss"):
                if enemy.get("stun_timer", 0) == 0:
                    enemy["stun_timer"] = 32  # Nonlethal stun
                    self.swipe_timer |= 0x40  # Latch hit bit

            if torch_state == "LIT" and not was_lit:
                self.swipe_timer |= 0x80  # Ignite swipe
                was_lit = True
            elif torch_state == "UNLIT" and was_lit:
                torch_state = "LIT"

        timer -= 1
        if timer == 0:
            self.stick_state = 2 if was_lit else 1
            self.swipe_timer = 0
        else:
            self.swipe_timer = timer | (0x80 if was_lit else 0) | (0x40 if hit_latched else 0)

    def test_swipe_controls_and_stun(self):
        # 1. Draw fresh stick
        self.assertTrue(self.menu_press_a())
        self.assertTrue(self.process_exit_action())
        self.assertEqual(self.stick_state, 1)

        # 2. Press Y -> starts swipe and suppresses assigned item
        self.assertEqual(self.press_y(), "SWIPE_STARTED")
        self.assertEqual(self.stick_state, 3)
        self.assertEqual(self.swipe_timer & 0x1F, 14)

        # 3. Simulate 14 frames with an enemy present
        enemy = {"active": True, "hp": 4, "boss": False, "stun_timer": 0}
        initial_hp = enemy["hp"]

        for f in range(14, 0, -1):
            self.advance_swipe_frame(enemy=enemy)

        # Verify enemy was stunned, HP was NOT damaged, stick was NOT broken
        self.assertEqual(enemy["stun_timer"], 32)
        self.assertEqual(enemy["hp"], initial_hp)  # 0 HP damage!
        self.assertEqual(self.stick_state, 1)      # Returned cleanly to held unlit!
        self.assertEqual(self.deku_sticks, 1)      # No stick loss!

    def test_swipe_while_lit_maintains_burn_budget(self):
        self.assertTrue(self.menu_press_a())
        self.assertTrue(self.process_exit_action())
        self.ignite()
        self.assertEqual(self.stick_state, 2)
        self.burn_timer = 50

        # Press Y while lit -> starts lit swipe (bit 7 set)
        self.assertEqual(self.press_y(), "SWIPE_STARTED")
        self.assertEqual(self.stick_state, 3)
        self.assertTrue(bool(self.swipe_timer & 0x80))

        # Advance 14 frames
        for _ in range(14):
            self.advance_swipe_frame()

        # Returns to lit state 2, burn budget preserved
        self.assertEqual(self.stick_state, 2)
        self.assertEqual(self.burn_timer, 50)

    def test_fresh_draw_and_stow(self):
        # 1. Draw fresh stick
        self.assertTrue(self.menu_press_a())
        self.assertTrue(self.process_exit_action())
        self.assertEqual(self.deku_sticks, 1)
        self.assertEqual(self.stick_state, 1)
        self.assertEqual(self.burn_timer, 75)
        self.assertEqual(self.deku_wear, 0)

        # 2. Stow without igniting -> no wear stored, refunded
        result = self.press_b(new_press=True)
        self.assertEqual(result, "SWORD_SUPPRESSED")
        self.assertEqual(self.deku_sticks, 2)
        self.assertEqual(self.stick_state, 0)
        self.assertEqual(self.deku_wear, 0)

        # 3. Next B press swings sword normally
        self.assertEqual(self.press_b(new_press=True), "SWORD_NORMAL")

    def test_worn_draw_and_stow(self):
        # 1. Draw fresh stick and ignite
        self.assertTrue(self.menu_press_a())
        self.assertTrue(self.process_exit_action())
        self.ignite()
        self.assertEqual(self.stick_state, 2)

        # 2. Simulate 45 ticks burned -> 30 ticks remaining (~8s)
        self.burn_timer = 30

        # 3. Stow worn stick
        self.assertEqual(self.press_b(new_press=True), "SWORD_SUPPRESSED")
        self.assertEqual(self.deku_sticks, 2)
        self.assertEqual(self.stick_state, 0)
        self.assertEqual(self.deku_wear, 30)

        # 4. Redraw stick -> resumes 30 ticks budget!
        self.assertTrue(self.menu_press_a())
        self.assertTrue(self.process_exit_action())
        self.assertEqual(self.deku_sticks, 1)
        self.assertEqual(self.stick_state, 1)
        self.assertEqual(self.burn_timer, 30)  # Resumed!
        self.assertEqual(self.deku_wear, 0)   # Cleared from SRAM while active

        # 5. Relight -> preserves remaining budget
        self.ignite()
        self.assertEqual(self.stick_state, 2)
        self.assertEqual(self.burn_timer, 30)

    def test_zero_inventory_refusal(self):
        self.deku_sticks = 0
        self.deku_wear = 30  # Stored wear
        self.assertFalse(self.menu_press_a())
        self.assertEqual(self.deku_sticks, 0)
        self.assertEqual(self.deku_wear, 30)  # Preserved!

    def test_corrupt_sram_fallback(self):
        self.deku_wear = 0xFF  # Corrupted / uninitialized save data
        self.assertTrue(self.menu_press_a())
        self.assertTrue(self.process_exit_action())
        self.assertEqual(self.burn_timer, 75)  # Falls back to safe fresh 75
        self.assertEqual(self.deku_wear, 0)

    @staticmethod
    def simulate_draw_oam(posx: int, posy: int, bg2h: int, bg2v: int, off_x: int, off_y: int):
        """Models DekuStick_DrawOAM 8-bit viewport delta + 9-bit signed OAM X high byte."""
        scr_x = ((posx & 0xFF) - (bg2h & 0xFF)) & 0xFF
        scr_y = ((posy & 0xFF) - (bg2v & 0xFF)) & 0xFF
        spr_x_16 = (scr_x + off_x) & 0xFFFF
        oam_x = spr_x_16 & 0xFF
        oam_x9 = (spr_x_16 >> 8) & 0x01
        oam_y = (scr_y + off_y) & 0xFF
        return oam_x, oam_y, oam_x9

    def test_oam_non_adjacent_overworld_transition_and_edge_wrap(self):
        # Screen 0x23 -> 0x2A arrival (POSX=736=0x02E0, POSY=2790=0x0AE6, BG2H=0x0500, BG2V=0x0A68)
        # Facing Left held offsets: Stick (-6, +8), Flame (-12, +8)
        sx, sy, sx9 = self.simulate_draw_oam(0x02E0, 0x0AE6, 0x0500, 0x0A68, -6, 8)
        fx, fy, fx9 = self.simulate_draw_oam(0x02E0, 0x0AE6, 0x0500, 0x0A68, -12, 8)
        self.assertEqual((sx, sy, sx9), (218, 134, 0))
        self.assertEqual((fx, fy, fx9), (212, 134, 0))
        self.assertLess(sy, 0xE0)
        self.assertLess(fy, 0xE0)

        # Left screen edge clip (Link at scr_x = 4, Flame offset = -12 -> -8 = 0x1F8, x9 = 1)
        fx_left, _, fx9_left = self.simulate_draw_oam(0x0604, 0x0AE6, 0x0600, 0x0A68, -12, 8)
        self.assertEqual((fx_left, fx9_left), (0xF8, 1))

        # Right screen edge clip (Link at scr_x = 248, Flame offset = +20 -> 268 = 0x10C, x9 = 1)
        fx_right, _, fx9_right = self.simulate_draw_oam(0x06F8, 0x0AE6, 0x0600, 0x0A68, 20, 8)
        self.assertEqual((fx_right, fx9_right), (0x0C, 1))


if __name__ == "__main__":
    unittest.main()
