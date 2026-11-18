#!/usr/bin/env python3
"""Contract tests for Overworld bush burning (Items/fire_burn_bushes.asm) and
burnable doorway webs (Sprites/Objects/dungeon_web.asm) allocation invariants.
"""

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIRE_BUSHES = ROOT / "Items" / "fire_burn_bushes.asm"
DUNGEON_WEB = ROOT / "Sprites" / "Objects" / "dungeon_web.asm"
SYMBOLS_ASM = ROOT / "Core" / "symbols.asm"
REGISTRY_CSV = ROOT / "Sprites" / "registry.csv"
REGISTRY_IDS = ROOT / "Sprites" / "sprite_registry_ids.asm"
ALLOCATION_LEDGER = ROOT / "Config" / "allocation_ownership.json"


def strip_comments(asm_text: str) -> str:
    return "\n".join(line.split(";", 1)[0] for line in asm_text.splitlines())


def extract_block(asm_text: str, label: str) -> str:
    m = re.search(rf"^{re.escape(label)}:\s*\n\{{(.*?)\n\}}", asm_text, re.M | re.S)
    assert m is not None, f"Routine block {label} not found"
    return m.group(1)


class FireBurnBushesContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fire_text = FIRE_BUSHES.read_text(encoding="utf-8")
        cls.fire_code = strip_comments(cls.fire_text)
        cls.web_text = DUNGEON_WEB.read_text(encoding="utf-8")
        cls.web_code = strip_comments(cls.web_text)
        cls.symbols_text = SYMBOLS_ASM.read_text(encoding="utf-8")
        cls.ledger = json.loads(ALLOCATION_LEDGER.read_text(encoding="utf-8"))

    def test_try_burn_overworld_bush_accepts_only_green_and_dark_bushes(self):
        body = extract_block(self.fire_code, "Fire_TryBurnOverworldBush")
        self.assertIn("CMP.w #$00E0 : BCS .miss_16", body)
        self.assertIn("CMP.w #$0100 : BCS .miss_16", body)
        self.assertIn("LDA.l $7E2000, X", body)
        self.assertIn("CMP.w #$0036 : BEQ .is_bush", body)
        self.assertIn("CMP.w #$072A : BNE .miss_16", body)
        self.assertIn("JSL HandleItemTileAction_Overworld", body)

    def test_fire_rod_check_overworld_bush_contract(self):
        body = extract_block(self.fire_code, "FireRod_CheckOverworldBush")

        # Replays displaced $08872C-$088736 instructions
        self.assertIn("INC.w $0C5E, X", body)
        self.assertIn("LDA.w $0C72, X : AND.b #$F3 : STA.w $0C72, X", body)

        # Fast exits for Underworld, already collided, elevated priority
        self.assertIn("LDA.b $1B : BNE .exit", body)
        self.assertIn("LDA.w $0C54, X : BNE .exit", body)
        self.assertIn("LDA.w $0280, X : BNE .exit", body)

        # Must NOT pre-filter on TileType $40 / $0385 / $03E4
        self.assertNotIn("CMP.b #$40", body)
        self.assertNotIn("$0385", body)
        self.assertNotIn("$03E4", body)

        # Probe 1 (ORA #$08) and Probe 2 (ORA #$0C) both invoke .test_probe -> Fire_TryBurnOverworldBush
        p1_match = re.search(r"^\.probe_1\b", body, re.M)
        p2_match = re.search(r"^\.probe_2\b", body, re.M)
        burned_match = re.search(r"^\.burned\b", body, re.M)
        test_probe_match = re.search(r"^\.test_probe\b", body, re.M)
        self.assertIsNotNone(p1_match)
        self.assertIsNotNone(p2_match)
        self.assertIsNotNone(burned_match)
        self.assertIsNotNone(test_probe_match)

        probe_1_body = body[p1_match.start() : p2_match.start()]
        probe_2_body = body[p2_match.start() : burned_match.start()]

        self.assertIn("LDA.w $0C72, X : AND.b #$03 : ORA.b #$08 : TAY", probe_1_body)
        self.assertIn("JSR .test_probe : BCS .burned", probe_1_body)
        self.assertIn("LDA.w $0C72, X : AND.b #$03 : ORA.b #$0C : TAY", probe_2_body)
        self.assertIn("JSR .test_probe : BCC .exit", probe_2_body)

        self.assertIn("JSL Fire_TryBurnOverworldBush", body[test_probe_match.start() :])

    def test_rom_slot_bounds_and_hook_patch(self):
        self.assertIn("org $36F800", self.fire_code)
        self.assertIn("assert pc() <= $36FB00", self.fire_code)
        self.assertIn("org $08872C", self.fire_code)
        self.assertIn("JSL FireRod_CheckOverworldBush", self.fire_code)
        self.assertIn("NOP #7", self.fire_code)
        self.assertIn("assert pc() == $088737", self.fire_code)

    def test_dungeon_web_and_symbol_allocation_invariants(self):
        # Core/symbols.asm WRAM block ($7ECA00..$7ECC7F = 640 bytes)
        self.assertIn("DungeonWeb_BurnedMask    = $7ECA00", self.symbols_text)
        self.assertIn("DungeonWeb_BurnedMaskEnd = DungeonWeb_BurnedMask+$0280", self.symbols_text)
        self.assertIn("assert DungeonWeb_BurnedMaskEnd == $7ECC80", self.symbols_text)

        # Sprites/Objects/dungeon_web.asm Bank $36 slot ($36F200..$36F7FF)
        self.assertIn("org $36F200", self.web_code)
        self.assertIn("assert pc() <= $36F800", self.web_code)
        self.assertIn("Sprite_DungeonWeb = $B7", REGISTRY_IDS.read_text(encoding="utf-8"))
        self.assertIn("Sprite_DungeonWeb,$B7,Sprites/Objects/dungeon_web.asm", REGISTRY_CSV.read_text(encoding="utf-8"))

        # Config/allocation_ownership.json claims
        claims = {c["id"]: c for c in self.ledger["claims"]}
        self.assertEqual((claims["dungeon_web_burned_mask"]["base"], claims["dungeon_web_burned_mask"]["size"]), (0x7ECA00, 640))
        self.assertEqual((claims["dungeon_web_code"]["base"], claims["dungeon_web_code"]["size"]), (0x36F200, 1536))
        self.assertEqual((claims["fire_burn_bushes_code"]["base"], claims["fire_burn_bushes_code"]["size"]), (0x36F800, 768))
        # Touching boundary without overlap in Bank $36
        self.assertEqual(
            claims["dungeon_web_code"]["base"] + claims["dungeon_web_code"]["size"],
            claims["fire_burn_bushes_code"]["base"],
        )


if __name__ == "__main__":
    unittest.main()
