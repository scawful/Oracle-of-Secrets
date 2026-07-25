from __future__ import annotations

import unittest
from pathlib import Path

from Scripts.Generate.water_fill_author import LOCAL_Z3ED, REPO_ROOT, is_patched_build_rom


class WaterFillAuthorTest(unittest.TestCase):
    def test_local_z3ed_uses_lowercase_sibling_scripts_directory(self) -> None:
        self.assertEqual(
            LOCAL_Z3ED,
            REPO_ROOT.parent / "yaze" / "scripts" / "z3ed",
        )

    def test_identifies_patched_build_outputs(self) -> None:
        for name in ("oos168x.sfc", "OOS-PATCHED.SFC"):
            with self.subTest(name=name):
                self.assertTrue(is_patched_build_rom(Path(name)))

        self.assertFalse(is_patched_build_rom(Path("oos168.sfc")))
        self.assertFalse(is_patched_build_rom(Path("water-authoring-copy.sfc")))


if __name__ == "__main__":
    unittest.main()
