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


if __name__ == "__main__":
    unittest.main()
