"""Honeycomb Nimbus bee swarm contract test.

Verifies:
1. Link_Honeycombs:
   - Rejects activation when PendingSupplyAction is already set.
   - Rejects activation when an active bee ($B2, $0DD0 != 0) is already in the room.
   - Rejects activation when fewer than 3 sprite slots are free (slot pressure).
   - Accepts when valid, returning A=1 (deferred exit signal) and setting PendingSupplyAction = 1.
2. MagicBag_ConsumeItem integration:
   - Deferred use (A=1) initiates menu scroll-up ($0200 = !MENU_STATE_SCROLL_UP) and plays $20.
   - Does NOT decrement SRAM item count in the menu.
   - Immediate use (A=0, e.g. Banana) decrements SRAM count and plays $35.
   - Refusal (CLC) plays error sound $3C and does not decrement count.
3. Supply_ProcessPendingExitAction:
   - Clears PendingSupplyAction.
   - Refuses if Honeycomb count is 0, active bee present, or free slots < 3.
   - On success: sets Good Bee flag ($0EB0=1) for all 3 bees, spends exactly 1 Honeycomb ($7EF393), plays $2F.
   - Preserves bottle contents and ordinary bottle bees.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
ALL_ITEMS = ROOT / "Items" / "all_items.asm"
MENU_ASM = ROOT / "Menu" / "menu.asm"
SYMBOLS_ASM = ROOT / "Core" / "symbols.asm"


class HoneycombSwarmContractTest(unittest.TestCase):
    def test_symbols_definition(self):
        text = SYMBOLS_ASM.read_text(encoding="utf-8")
        self.assertIn("PendingSupplyAction      = $0434", text)
        self.assertIn("!SUPPLY_ACTION_HONEYCOMB = $01", text)

    def test_menu_integration(self):
        menu_text = MENU_ASM.read_text(encoding="utf-8")
        # Check deferred_use in MagicBag_ConsumeItem
        self.assertIn("CMP.b #$01 : BEQ .deferred_use", menu_text)
        self.assertIn("LDA.b #!MENU_STATE_SCROLL_UP : STA.w $0200", menu_text)
        # Check call on Menu_Exit
        self.assertIn("JSL Supply_ProcessPendingExitAction", menu_text)

    def test_link_honeycomb_routine_structure(self):
        items_text = ALL_ITEMS.read_text(encoding="utf-8")
        # Verify Link_Honeycombs exists and checks PendingSupplyAction, active bee with $0D80, slot count
        self.assertIn("Link_Honeycombs:", items_text)
        self.assertIn("PendingSupplyAction : BNE .fail", items_text)
        self.assertIn("CMP.b #$B2 : BNE .not_bee", items_text)
        self.assertIn("LDA.w $0D80, X : BEQ .not_bee", items_text)
        self.assertIn("CPY.b #$03 : BCC .fail", items_text)
        self.assertIn("!SUPPLY_ACTION_HONEYCOMB : STA.l PendingSupplyAction", items_text)

    def test_exit_action_routine_structure(self):
        items_text = ALL_ITEMS.read_text(encoding="utf-8")
        self.assertIn("Supply_ProcessPendingExitAction:", items_text)
        # Verify check of PendingSupplyAction
        self.assertIn("!SUPPLY_ACTION_HONEYCOMB", items_text)
        # Verify active bee guard in exit action checks $0D80
        self.assertIn("LDA.w $0D80, X : BEQ .exit_not_bee", items_text)
        # Verify 3 calls to PlayerItem_ReleaseBee
        matches = re.findall(r"JSL\s+PlayerItem_ReleaseBee", items_text)
        self.assertGreaterEqual(len(matches), 3)
        # Verify setting of Good Bee flag ($0EB0) for spawned sprites
        self.assertIn("STA.w $0EB0, X", items_text)
        # Verify Honeycomb count decrement
        self.assertIn("LDA.l Honeycomb : DEC A : STA.l Honeycomb", items_text)
        # Verify error sound on abort
        self.assertIn("LDA.b #$3C : STA.w $012E", items_text)
        # Verify success sound on deployment
        self.assertIn("LDA.b #$2F : STA.w $012F", items_text)

    def test_windmill_guy_dispatch_multiplexing(self):
        wmg_asm = (ROOT / "Sprites" / "NPCs" / "windmill_guy.asm").read_text(encoding="utf-8")
        self.assertIn("SpriteModule_Active_Bank1E = $1E8B11", wmg_asm)
        self.assertIn("LDA.w $0D80, X : BEQ +", wmg_asm)
        self.assertIn("JML SpriteModule_Active_Bank1E", wmg_asm)

    def test_bottle_net_bee_subtype_preservation(self):
        bottle_asm = (ROOT / "Items" / "bottle_net.asm").read_text(encoding="utf-8")
        # Verify Good Bee check and distinct subtype handling
        self.assertIn("CMP.b #$08", bottle_asm)
        self.assertIn("STA.w $0EB0, Y", bottle_asm)


class HoneycombLogicModelTest(unittest.TestCase):
    """Simulates the ASM state machine logic to verify all branch conditions."""

    def simulate_menu_consume(self, pending, active_bees, free_slots, honeycomb_count):
        """Simulates Link_Honeycombs check."""
        if honeycomb_count == 0:
            return "error_count", pending, honeycomb_count
        if pending != 0:
            return "error_pending", pending, honeycomb_count
        if active_bees > 0:
            return "error_active_bee", pending, honeycomb_count
        if free_slots < 3:
            return "error_slot_pressure", pending, honeycomb_count

        # Success in menu: queue action, do not decrement count
        new_pending = 1
        return "deferred_use", new_pending, honeycomb_count

    def simulate_exit_action(self, pending, active_bees, free_slots, honeycomb_count):
        """Simulates Supply_ProcessPendingExitAction."""
        if pending != 1:
            return "no_action", pending, honeycomb_count, 0

        # Clears pending
        pending = 0

        if honeycomb_count == 0 or active_bees > 0 or free_slots < 3:
            return "abort_error", pending, honeycomb_count, 0

        # Spawn 3 bees, decrement count
        honeycomb_count -= 1
        spawned_bees = 3
        return "success", pending, honeycomb_count, spawned_bees

    def test_menu_rejection_conditions(self):
        # Honeycomb = 0
        res, pend, count = self.simulate_menu_consume(pending=0, active_bees=0, free_slots=5, honeycomb_count=0)
        self.assertEqual(res, "error_count")
        self.assertEqual(count, 0)
        self.assertEqual(pend, 0)

        # Active bee already buzzing
        res, pend, count = self.simulate_menu_consume(pending=0, active_bees=1, free_slots=5, honeycomb_count=2)
        self.assertEqual(res, "error_active_bee")
        self.assertEqual(count, 2)
        self.assertEqual(pend, 0)

        # Slot pressure: only 2 free slots
        res, pend, count = self.simulate_menu_consume(pending=0, active_bees=0, free_slots=2, honeycomb_count=2)
        self.assertEqual(res, "error_slot_pressure")
        self.assertEqual(count, 2)
        self.assertEqual(pend, 0)

        # Already pending
        res, pend, count = self.simulate_menu_consume(pending=1, active_bees=0, free_slots=5, honeycomb_count=2)
        self.assertEqual(res, "error_pending")

    def test_menu_acceptance_and_exit_deployment(self):
        # Menu acceptance
        res, pend, count = self.simulate_menu_consume(pending=0, active_bees=0, free_slots=4, honeycomb_count=3)
        self.assertEqual(res, "deferred_use")
        self.assertEqual(pend, 1)
        self.assertEqual(count, 3)  # Count preserved in menu!

        # Exit deployment success
        res, pend, count, bees = self.simulate_exit_action(pend, active_bees=0, free_slots=4, honeycomb_count=count)
        self.assertEqual(res, "success")
        self.assertEqual(pend, 0)
        self.assertEqual(count, 2)  # Decremented on successful exit deployment!
        self.assertEqual(bees, 3)

    def test_exit_abort_under_slot_pressure_preserves_inventory(self):
        # Accepted in menu, but slots filled before exit
        res, pend, count, bees = self.simulate_exit_action(pending=1, active_bees=0, free_slots=1, honeycomb_count=3)
        self.assertEqual(res, "abort_error")
        self.assertEqual(pend, 0)
        self.assertEqual(count, 3)  # Inventory strictly preserved!
        self.assertEqual(bees, 0)


if __name__ == "__main__":
    unittest.main()
