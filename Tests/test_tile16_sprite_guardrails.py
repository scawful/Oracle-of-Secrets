#!/usr/bin/env python3
"""Unit and read-only ROM smoke tests for Q328/Q329 guardrail tools:
  - Scripts/Build/check_tile16_pins.py + Data/tile16_pins.json
  - Scripts/Build/check_sheet_reveal_safety.py
  - Scripts/Build/check_sprite_sheet_compat.py
  - Scripts/Review/render_liftables_sheet.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_ROM = Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom")
PINS_JSON = ROOT / "Data" / "tile16_pins.json"

sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
sys.path.insert(0, str(ROOT / "Scripts" / "Review"))
sys.path.insert(0, str(ROOT / "Scripts" / "Tools"))

import check_sheet_reveal_safety as csrs  # noqa: E402
import check_sprite_sheet_compat as cssc  # noqa: E402
import check_tile16_pins as ctp  # noqa: E402
import render_liftables_sheet as rls  # noqa: E402


@unittest.skipUnless(LIVE_ROM.exists(), "Live read-only authoring ROM required")
class Tile16AndSpriteGuardrailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = LIVE_ROM.read_bytes()

    # ------------------------------------------------------------------
    # 1. check_tile16_pins.py + Data/tile16_pins.json
    # ------------------------------------------------------------------

    def test_pins_manifest_covers_all_five_categories_and_passes_on_base_rom(self) -> None:
        self.assertTrue(PINS_JSON.exists(), "Data/tile16_pins.json must exist")
        data = json.loads(PINS_JSON.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 2)
        cats = data["category_counts"]
        for req_cat in (
            "overlay_stream",
            "asm_draw_persist",
            "bank1b_interactive",
            "bank02_map32_update",
            "custom_reveal_override",
        ):
            self.assertGreater(cats.get(req_cat, 0), 0, f"missing category {req_cat}")

        # Verify key pins exist across all categories
        t16 = data["tile16"]
        self.assertIn("036", t16)  # Bank $1B bush
        self.assertIn("172", t16)  # DW $63 override
        self.assertIn("EB1", t16)  # Q326 grave reveal
        self.assertIn("F83", t16)  # Q326 Grave 14 pit reveal
        self.assertIn("68F", t16)  # Sprites/Bosses/octoboss.asm DrawMap16_Persist
        self.assertIn("B82", t16)  # Overworld/entrances.asm OverworldDoorStyles
        self.assertTrue(t16["72A"].get("intentionally_skipped"))
        self.assertEqual(t16["72A"]["policy"], "warn")

        rc = ctp.main(["--rom", str(LIVE_ROM), "--pins", str(PINS_JSON)])
        self.assertEqual(rc, 0)

    def test_pins_detects_mutated_block_tile16_and_warns_on_072a(self) -> None:
        with tempfile.TemporaryDirectory(prefix="q329-pins-") as td:
            mut = bytearray(self.rom)
            base = ctp.tile16_table_pc(self.rom)
            # Mutate $072A (warn-only intentionally skipped) -> must STILL return 0
            mut[base + 0x072A * 8] ^= 0xFF
            p_warn = Path(td) / "warn.sfc"
            p_warn.write_bytes(mut)
            self.assertEqual(ctp.main(["--rom", str(p_warn), "--pins", str(PINS_JSON)]), 0)

            # Mutate $0EB1 (Q326 grave reveal, block policy) -> MUST return 1!
            mut[base + 0x0EB1 * 8] ^= 0xFF
            p_block = Path(td) / "block.sfc"
            p_block.write_bytes(mut)
            self.assertEqual(ctp.main(["--rom", str(p_block), "--pins", str(PINS_JSON)]), 1)

    def test_free_range_scans_all_192_maps_and_excludes_tail_and_pins(self) -> None:
        report = ctp.find_free_ranges(self.rom, min_run=12)
        self.assertEqual(report["maps_scanned"], 192)
        self.assertGreater(report["static_used"], 3300)
        self.assertGreater(report["engine_pinned"], 300)
        self.assertGreater(len(report["runs"]), 0)

        # Verify every single ID in every returned run is genuinely unplaced & unpinned
        _cap, usage = ctp.decode_all_maps_usage(self.rom)
        pins = ctp.collect_all_pins(self.rom)
        for run in report["runs"]:
            start = int(run["start"], 16)
            end = int(run["end"], 16)
            self.assertEqual(end - start + 1, run["length"])
            self.assertGreaterEqual(run["length"], 12)
            for tid in range(start, end + 1):
                self.assertNotIn(tid, usage, f"0x{tid:03X} is placed on a map!")
                self.assertNotIn(tid, pins, f"0x{tid:03X} is engine-pinned!")

    def test_exit_door_audit_flags_room_0106_lw23_and_exit_25_oob(self) -> None:
        # Live ROM after Wave 2 Batch A must have 0 exit issues & 0 missing/wrong entrance exit doors
        report = ctp.audit_overworld_exit_doors(self.rom)
        self.assertEqual(report["exits_checked"], 0x4F)
        self.assertEqual(report["ow_entrances_checked"], 129)
        self.assertEqual(report["exit_findings"], [])
        missing_doors = [
            e for e in report["entrance_findings"]
            if e["kind"] == "missing_or_wrong_entrance_exit_door"
        ]
        self.assertEqual(missing_doors, [])

        # Synthetic regression: reverting Ent $48 -> $0000 and Exit $25 dt2 -> $82BE MUST be caught!
        mut = bytearray(self.rom)
        mut[0x0157B4:0x0157B6] = b"\x00\x00"  # Ent $48 (Room $0106 -> LW $23) missing $1112
        mut[0x01644F:0x016451] = b"\xBE\x82"  # Exit $25 OOB dt2 ($82BE on SmallArea LW $15)
        mut_rep = ctp.audit_overworld_exit_doors(bytes(mut))

        ent48 = [
            e for e in mut_rep["entrance_findings"]
            if e["entrance_id"] == "0x48" and e["room_id"] == "0x0106" and e["map_id"] == "0x23"
        ]
        self.assertEqual(len(ent48), 1)
        self.assertEqual(ent48[0]["expected_exit_field"], "0x1112")
        self.assertEqual(ent48[0]["actual_exit_field"], "0x0000")

        ex25 = [e for e in mut_rep["exit_findings"] if e["exit_id"] == "0x25"]
        self.assertEqual(len(ex25), 1)
        self.assertEqual(ex25[0]["kind"], "exit_dt2_oob")

    # ------------------------------------------------------------------
    # 2. check_sheet_reveal_safety.py
    # ------------------------------------------------------------------

    def test_sheet_reveal_safety_detects_dw64_f8_bleed_and_respects_dw63_override(self) -> None:
        report = csrs.scan_sheet_reveal_safety(self.rom)
        self.assertEqual(report["maps_scanned"], 192)
        self.assertGreaterEqual(len(report["custom_sheets_found"]), 18)

        # DW $64 (parent $63, Sheet $F8) has known slot-6 interactive TileType bleed
        f8_bleeds = [
            f for f in report["check_b_findings"]
            if f["parent_id"] == "0x63" and f["sheet"] == "0xF8"
        ]
        self.assertGreaterEqual(len(f8_bleeds), 20)

        # DW $63 bush/sign reveals are protected by Q325 ASM override -> 0 Check A errors on $63!
        dw63_err = [
            f for f in report["check_a_findings"]
            if f["parent_id"] == "0x63" and f["severity"] == "error"
        ]
        self.assertEqual(len(dw63_err), 0)

    def test_sheet_reveal_safety_catches_synthetic_blanked_reveal_char(self) -> None:
        # Remove DW $63 ASM override temporarily in memory to prove Check A catches
        # Sheet $F8's overwritten bush/sign reveal chars ($18F/$19F/$1AF/$1BF)!
        saved = dict(csrs.ASM_REVEAL_OVERRIDES)
        try:
            csrs.ASM_REVEAL_OVERRIDES.clear()
            report = csrs.scan_sheet_reveal_safety(self.rom)
            dw63_errs = [
                f for f in report["check_a_findings"]
                if f["parent_id"] == "0x63" and f["sheet"] == "0xF8" and f["severity"] == "error"
            ]
            self.assertGreater(len(dw63_errs), 0, "Without Q325 override, DW $63 $F8 reveal corruption MUST be caught")
        finally:
            csrs.ASM_REVEAL_OVERRIDES.update(saved)

    # ------------------------------------------------------------------
    # 3. check_sprite_sheet_compat.py
    # ------------------------------------------------------------------

    def test_sprite_sheet_compat_catches_lw12_blue_soldier_sw90_and_water_on_land(self) -> None:
        # Live ROM after Wave 2 Batch A must be clean across all 4 overworld checks!
        report = cssc.scan_rom_sprite_compat(self.rom)
        self.assertEqual(report["overworld_maps_scanned"], 192)
        self.assertEqual(report["dungeon_rooms_scanned"], 296)
        self.assertEqual(len(report["ow_palette_oob"]), 0)
        self.assertEqual(len(report["ow_invalid_sheet_fmt"]), 0)
        self.assertEqual(len(report["dungeon_invalid_sheet_fmt"]), 0)
        self.assertEqual(len(report["ow_sheet_mismatches"]), 0)
        self.assertEqual(
            [w for w in report["ow_water_terrain"] if w["severity"] == "error"],
            [],
        )

        # Synthetic regressions: injecting LW $12 p2 SprGfx=$1A, SW $90 OOB SprPal=$C2,
        # 2bpp font sheet $DA / BG sheet $E3, and LW $1E WalkingZora on dry land (5,43)
        # MUST all be caught by check_sprite_sheet_compat!
        mut = bytearray(self.rom)
        mut[0x007AD3] = 0x1A                                  # LW $12 p2 BlueSoldier mismatch
        mut[0x016701 + (0x90 - 0x80)] = 0xC2                  # SW $90 OOB sprite palette
        mut[cssc.SPRITE_BLOCKSET_PC + 0x1F * 4 + 3] = 0xDA - 0x73  # 2bpp font in slot 3
        mut[cssc.SPRITE_BLOCKSET_PC + 0x2F * 4 + 3] = 0xE3 - 0x73  # 3bpp BG sheet in slot 3
        mut[0x04CAA5] = 0x05                                  # LW $1E p1 WalkingZora back onto dry land (5,43)
        mut[0x005D22] = 0x44                                  # Room $009A SeaZora Slot 3 back to $B7
        mut_rep = cssc.scan_rom_sprite_compat(bytes(mut))

        lw12_41 = [
            m for m in mut_rep["ow_sheet_mismatches"]
            if m["map_id"] == "0x12" and m["sprite_id"] == "0x41"
        ]
        self.assertGreaterEqual(len(lw12_41), 2, "Must catch LW $12 phase 2 BlueSoldier $41 sheet mismatch")
        self.assertEqual(lw12_41[0]["spr_gfx"], "0x1A")
        self.assertEqual(lw12_41[0]["loaded_sheet"], "0xCA")

        oob_maps = {x["map_id"] for x in mut_rep["ow_palette_oob"]}
        self.assertIn("0x90", oob_maps)
        self.assertIn("0x98", oob_maps)

        mut_reasons = {(x["sheet"], x["reason"]) for x in mut_rep["ow_invalid_sheet_fmt"]}
        self.assertIn(("0xDA", "2bpp_font_hud_sheet_in_sprite_slot"), mut_reasons)
        self.assertIn(("0xE3", "3bpp_bg_or_unmapped_sheet_in_sprite_slot"), mut_reasons)

        dry_errs = [
            w for w in mut_rep["ow_water_terrain"]
            if w["severity"] == "error" and w["map_id"] == "0x1E" and w["sprite_id"] == "0x56"
        ]
        self.assertEqual(len(dry_errs), 1)
        self.assertEqual(dry_errs[0]["pos"], [5, 43])

        # 5. Live ROM must have Room $009A fixed (no SeaZora mismatch) while mutated ROM catches it,
        # and Room $0046 (D4 Warden) / Room $0105 (Refuge $E7) never false-positive!
        dun_mm_rooms = {x["room_id"] for x in report["dungeon_sheet_mismatches"]}
        mut_dun_mm_rooms = {x["room_id"] for x in mut_rep["dungeon_sheet_mismatches"]}
        self.assertNotIn("0x009A", dun_mm_rooms)
        self.assertIn("0x009A", mut_dun_mm_rooms)
        self.assertNotIn("0x0046", dun_mm_rooms)
        self.assertNotIn("0x0105", dun_mm_rooms)

        # 6. Verify Special Overworld 64-map audit table is complete ($80-$BF)
        self.assertEqual(len(report["special_ow_audit"]), 64)

        # 7. Verify --strict exits 1 on mutated ROM with mismatches and JSON/MD outputs succeed
        with tempfile.TemporaryDirectory(prefix="q329-compat-") as td:
            mut_rom_path = Path(td) / "mut.sfc"
            mut_rom_path.write_bytes(bytes(mut))
            out_j = Path(td) / "out.json"
            out_m = Path(td) / "out.md"
            rc = cssc.main(["--rom", str(mut_rom_path), "--out-json", str(out_j), "--out-md", str(out_m), "--strict"])
            self.assertEqual(rc, 1)
            self.assertTrue(out_j.exists() and out_j.stat().st_size > 1000)
            self.assertTrue(out_m.exists() and "BlueSoldier" in out_m.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # 4. render_liftables_sheet.py
    # ------------------------------------------------------------------

    def test_render_liftables_contact_sheet_smoke(self) -> None:
        with tempfile.TemporaryDirectory(prefix="q329-lift-") as td:
            out_png = Path(td) / "sheet.png"
            out_json = Path(td) / "sheet.json"
            rc = rls.main(["--rom", str(LIVE_ROM), "--out", str(out_png), "--json", str(out_json)])
            self.assertEqual(rc, 0)
            self.assertTrue(out_png.exists() and out_png.stat().st_size > 2000)
            meta = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(meta["strips"], 15)


if __name__ == "__main__":
    unittest.main()
