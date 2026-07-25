from __future__ import annotations

import unittest
from pathlib import Path

from Scripts.Analysis.dungeon_viz import local_z3ed_path


class DungeonVizTest(unittest.TestCase):
    def test_local_z3ed_uses_lowercase_sibling_scripts_directory(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]

        self.assertEqual(
            local_z3ed_path(),
            repo_root.parent / "yaze" / "scripts" / "z3ed",
        )


if __name__ == "__main__":
    unittest.main()
