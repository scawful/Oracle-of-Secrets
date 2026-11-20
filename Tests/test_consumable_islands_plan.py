"""Catalog and CLI checks for the consumable-island planner.

The live project ROM and shared Roms/oos168*.sfc are never opened. The CLI
test runs only when a private copy is already at the path below, or at
$OOS_CONSUMABLE_ROM.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "Scripts" / "Proposals" / "plan_consumable_islands.py"
DEFAULT_ROM = Path("/tmp/oos-w2b-consumables/base.sfc")
FORTRESS = {0x4B, 0x4C, 0x53, 0x54}


def load_plan():
    spec = importlib.util.spec_from_file_location("plan_consumable_islands", PLAN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {PLAN_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLAN = load_plan()


class CatalogTests(unittest.TestCase):
    def test_schema_and_bounds(self) -> None:
        self.assertEqual(PLAN.catalog_problems(), [])
        supplies = {row["supply"] for row in PLAN.PLACEMENTS}
        self.assertEqual(supplies, set(PLAN.SUPPLIES))
        for row in PLAN.PLACEMENTS:
            self.assertIn("id", row)
            self.assertIn("method", row)
            self.assertIn("forbids", row)
            if row.get("kind") == "dungeon_chest":
                self.assertIsNone(row["map_id"])
                continue
            self.assertNotIn(row["map_id"], FORTRESS)
            self.assertNotIn(row["parent"], FORTRESS)
            self.assertGreaterEqual(row["x"], 0)
            self.assertLessEqual(row["x"], 31)
            self.assertGreaterEqual(row["y"], 0)
            self.assertLessEqual(row["y"], 31)
            self.assertGreaterEqual(row["area_x"], 0)
            self.assertLessEqual(row["area_x"], 63)
            self.assertGreaterEqual(row["area_y"], 0)
            self.assertLessEqual(row["area_y"], 63)

    def test_rock_meat_is_basic_glove_only(self) -> None:
        meat = [row for row in PLAN.PLACEMENTS if row["supply"] == "rock_meat"]
        self.assertEqual(len(meat), 5)
        for row in meat:
            self.assertEqual(row["requires"], ["power_glove"])
            self.assertNotIn("hammer", row["requires"])
            self.assertIn("hammer", row["forbids"])
            self.assertIn("titans_mitt", row["forbids"])
            self.assertIn("lupo", row["forbids"])
            self.assertIn(row["map_id"], {0xB0, 0xB1, 0xB8, 0xB9})
            self.assertNotEqual(row["map_id"], 0x5E)
            self.assertNotEqual(row["map_id"], 0xB2)
            self.assertEqual(row["sprite_id"], 0x52)

    def test_sprite_52_is_only_meat_and_pineapple(self) -> None:
        for row in PLAN.PLACEMENTS:
            if row.get("sprite_id") == 0x52:
                self.assertIn(row["supply"], {"rock_meat", "pineapple"})
            if row["supply"] == "banana":
                self.assertIsNone(row["sprite_id"])

    def test_fortress_and_oob_are_rejected(self) -> None:
        bad = {
            "id": "bad_fortress",
            "supply": "banana",
            "home": "nope",
            "map_id": 0x4B,
            "x": 1,
            "y": 1,
            "parent": 0x4B,
            "area_x": 1,
            "area_y": 1,
            "surface": "walk",
            "sprite_id": None,
            "method": "palm_harvest",
            "requires": [],
            "forbids": ["enemy_drop"],
            "access": "",
            "note": "",
        }
        oob = dict(bad)
        oob["id"] = "bad_oob"
        oob["map_id"] = 0x01
        oob["parent"] = 0x01
        oob["x"] = 40
        problems = PLAN.catalog_problems(PLAN.PLACEMENTS + [bad, oob])
        self.assertTrue(any("fortress" in item for item in problems))
        self.assertTrue(any("out of range" in item for item in problems))

    def test_surface_rules(self) -> None:
        self.assertTrue(PLAN.surface_ok([0x00, 0x00, 0x00, 0x00], "walk"))
        self.assertFalse(PLAN.surface_ok([0x00, 0x09, 0x00, 0x00], "walk"))
        self.assertTrue(PLAN.surface_ok([0x00, 0x09, 0x00, 0x00], "shore"))
        self.assertTrue(PLAN.surface_ok([0x09, 0x09, 0x09, 0x09], "shallow"))
        self.assertFalse(PLAN.surface_ok([0x08, 0x09], "shore"))


class CliTests(unittest.TestCase):
    def test_cli_is_deterministic_and_passes(self) -> None:
        rom = Path(os.environ.get("OOS_CONSUMABLE_ROM", DEFAULT_ROM))
        if not rom.is_file():
            self.skipTest(f"no private ROM copy at {rom}")
        out_a = Path("/tmp/oos-w2b-consumables/cli-a")
        out_b = Path("/tmp/oos-w2b-consumables/cli-b")
        for folder in (out_a, out_b):
            folder.mkdir(parents=True, exist_ok=True)
        cmd = [
            "python3",
            str(PLAN_PATH),
            "--rom",
            str(rom),
            "--no-render",
        ]
        first = subprocess.run([*cmd, "--out-dir", str(out_a)], capture_output=True, text=True, check=False)
        second = subprocess.run([*cmd, "--out-dir", str(out_b)], capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        text_a = (out_a / "consumable_islands_manifest.json").read_text(encoding="utf-8")
        text_b = (out_b / "consumable_islands_manifest.json").read_text(encoding="utf-8")
        self.assertEqual(text_a, text_b)
        manifest = json.loads(text_a)
        self.assertTrue(manifest["ok"])
        self.assertEqual(manifest["failed"], [])
        self.assertEqual(manifest["rock_meat_rule"]["requires"], ["power_glove"])
        self.assertIn("hammer", manifest["rock_meat_rule"]["forbids"])
        self.assertEqual(manifest["fortress_maps"], ["0x4B", "0x4C", "0x53", "0x54"])
        for row in manifest["placements"]:
            if "map_id" not in row:
                continue
            self.assertNotIn(int(row["map_id"], 16), FORTRESS)
            self.assertGreaterEqual(row["x"], 0)
            self.assertLessEqual(row["x"], 31)
            self.assertGreaterEqual(row["y"], 0)
            self.assertLessEqual(row["y"], 31)
            if row["supply"] == "rock_meat":
                self.assertEqual(row["requires"], ["power_glove"])
                self.assertNotIn("hammer", row["requires"])
                self.assertEqual(row["sprite_id"], "0x52")
                self.assertEqual(row["status"], "pass")


if __name__ == "__main__":
    unittest.main()
