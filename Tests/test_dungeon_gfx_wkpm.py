#!/usr/bin/env python3
"""Timber-kettle low-half slot, audited BG sheets, and WKPM table integrity.

The kettle art in kettle_3L.txt is palette 3's low half. House slot 6 is
global sheet $1C, so the four glyphs are tiles $30-$33 (chars $1B0-$1B3)
and the tile words keep the $0C00 palette row. Slot 3 sheet $07 is the high
half and is no longer the kettle target.
"""
from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Scripts/Generate"))
import dungeon_bg_overrides as dbg
import gen_wall_profiles as profiles

SPEC = ROOT / "Data/graphics/dungeon_bg_sheets.json"
KETTLE = ROOT / "Dungeons/Objects/Data/timber_kettle.bin"
SELECTOR = ROOT / "Dungeons/wall_profile_selector.asm"
PROFILES_ASM = ROOT / "Dungeons/Data/wall_profiles/wall_profiles.asm"
PROFILES_JSON = ROOT / "Dungeons/Data/wall_profiles/wall_profiles.json"
KITS = ROOT / "Dungeons/Data/kits"

# Palette 3, slot 6, tiles $30-$33. Not the placed $0C8 cells $1BA-$1BD.
KETTLE_WORDS = (0x8002, 0x0DB0, 0x0DB1, 0x8002, 0x0DB2, 0x0DB3, 0x0000)
KETTLE_CHARS = (0x1B0, 0x1B1, 0x1B2, 0x1B3)


def _expanded_base_rom() -> Path | None:
    candidates = []
    for key in ("OOS_BASE_ROM", "YAZE_PROJECT_ROM"):
        if os.environ.get(key):
            candidates.append(Path(os.environ[key]))
    candidates.append(ROOT / "Roms/oos168.sfc")
    candidates.append(Path(
        "/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"))
    for path in candidates:
        if path.is_file() and path.stat().st_size >= 0x300000:
            return path
    return None


class TimberKettleLowSlot(unittest.TestCase):
    def test_bin_keeps_palette_3_on_slot6_low_half(self):
        words = struct.unpack("<7H", KETTLE.read_bytes())
        self.assertEqual(words, KETTLE_WORDS)
        chars = [words[1] & 0x3FF, words[2] & 0x3FF, words[4] & 0x3FF, words[5] & 0x3FF]
        self.assertEqual(tuple(chars), KETTLE_CHARS)
        for word in (words[1], words[2], words[4], words[5]):
            self.assertEqual((word >> 10) & 7, 3)
            self.assertEqual(word & 0x3FF, word - 0x0C00)
            # Slot 6 is chars $180-$1BF. $1B0-$1B3 are below the $0C8 cells.
            self.assertGreaterEqual(word & 0x3FF, 0x180)
            self.assertLess(word & 0x3FF, 0x1BA)

    def test_sheet_patch_matches_the_bin(self):
        spec = json.loads(SPEC.read_text())
        self.assertEqual(
            [entry["global_sheet"] for entry in spec["sheets"]],
            ["0x07", "0x1F", "0x22", "0x1C"],
        )
        kettle = next(p for p in spec["patches"] if p["name"] == "timber_kettle")
        self.assertEqual(kettle["sheet"], "0x1C")
        self.assertEqual(kettle["tiles"], ["0x30", "0x31", "0x32", "0x33"])
        self.assertTrue(kettle["require_blank"])
        chars = [0x180 + int(tile, 16) for tile in kettle["tiles"]]
        self.assertEqual(chars, list(KETTLE_CHARS))
        self.assertIn(0x1C, dbg.SHEETS)

    def test_dungeon_bg_overrides_check(self):
        rom = _expanded_base_rom()
        if rom is None:
            self.skipTest("no expanded editable base ROM")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "Scripts/Generate/dungeon_bg_overrides.py"),
             "--root", str(ROOT), "--base-rom", str(rom), "--check"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["checked"])
        self.assertEqual(
            [row["global_sheet"] for row in payload["sheets"]],
            ["07", "1F", "22", "1C"],
        )


class WallProfileWkpm(unittest.TestCase):
    def test_gen_wall_profiles_check(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "Scripts/Generate/gen_wall_profiles.py"),
             "build", "--check"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_palette_ids_are_private_and_unique(self):
        seen = {}
        for path in sorted(KITS.glob("*.kit.json")):
            kit = json.loads(path.read_text())
            palette = kit.get("palette")
            if not palette:
                continue
            pid = int(str(palette["id"]), 16)
            self.assertIn(pid, profiles.PRIVATE_PALETTES, path.name)
            self.assertNotIn(pid, seen, f"{path.name} shares palette with {seen.get(pid)}")
            seen[pid] = path.name
        dragon = json.loads((KITS / "dragon_ship_timber.kit.json").read_text())
        self.assertEqual(dragon["verdict"], "in_base")
        self.assertIsNone(dragon["profile"])
        self.assertIsNone(dragon["palette"])
        config = json.loads(PROFILES_JSON.read_text())
        bound = {group["profile"] for group in config["groups"]}
        self.assertNotIn("dragon_ship_timber", bound)

    def test_live_headers_do_not_select_private_palettes(self):
        rom = _expanded_base_rom()
        if rom is None:
            self.skipTest("no expanded editable base ROM")
        facts = profiles.verify_palette_ownership(rom.read_bytes())
        self.assertEqual(facts["rooms_checked"], profiles.ROOM_COUNT)

    def test_wkpm_metadata_matches_the_selector_tables(self):
        selector = SELECTOR.read_text()
        self.assertIn('db "WKPM", $01', selector)
        self.assertIn("dl WallSel_RenderMetadata", selector)
        asm = PROFILES_ASM.read_text()
        match = re.search(
            r'WallSel_RenderMetadata:.*?\n\s*db "WSR1"\n\s*dw \$([0-9A-Fa-f]+)\n'
            r'\s*db (\d+), (\d+), \$([0-9A-Fa-f]+), (\d+)\n'
            r'(?:\s*dl WallSel_(\w+)\n){10}',
            asm)
        self.assertIsNotNone(match, "WSR1 metadata block missing")
        config = json.loads(PROFILES_JSON.read_text())
        routed = 0
        for path in KITS.glob("*.kit.json"):
            kit = json.loads(path.read_text())
            if kit.get("private_row") is not None:
                routed += 1
        self.assertEqual(int(match.group(1), 16), profiles.ROOM_COUNT)
        self.assertEqual(int(match.group(2)), len(profiles.CLASSES))
        self.assertEqual(int(match.group(3)), len(config["profiles"]))
        self.assertEqual(int(match.group(4), 16), profiles.KIT_ROW0)
        self.assertEqual(int(match.group(5)), routed)
        labels = re.findall(r"dl WallSel_(\w+)", match.group(0))
        self.assertEqual(labels, [
            "RoomProfile", "Sub1Class", "Sub2Class", "ProfileBase", "SlotSrc",
            "SlotLen", "Data", "ProfileBlockset", "ProfilePalette", "KitHighPalette",
        ])


if __name__ == "__main__":
    unittest.main()
