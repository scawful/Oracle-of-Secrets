from __future__ import annotations

import unittest
from pathlib import Path

from Scripts.Generate.export_yazeproj_bundle import should_skip


class ShouldSkipTest(unittest.TestCase):
    def test_skips_canonical_evaluations_root(self) -> None:
        self.assertTrue(should_skip(Path("Evaluations")))
        self.assertTrue(should_skip(Path("Evaluations/results/report.json")))

    def test_skips_visual_test_artifacts(self) -> None:
        for directory in ("screenshots", "baselines", "baseline", "current", "diffs"):
            with self.subTest(directory=directory):
                self.assertTrue(should_skip(Path("Tests") / directory / "artifact.png"))

    def test_preserves_normal_test_and_project_files(self) -> None:
        for path in (
            Path("Tests/smoke/lint_pass.json"),
            Path("Tests/unit/test_validator.py"),
            Path("Docs/Planning/editor_plan.md"),
            Path("Sprites/Npcs/test_sprite.asm"),
        ):
            with self.subTest(path=path):
                self.assertFalse(should_skip(path))

    def test_skips_current_and_legacy_scratchpad_roots(self) -> None:
        self.assertTrue(should_skip(Path("Scratchpad/notes.md")))
        self.assertTrue(should_skip(Path("scratchpad/notes.md")))


if __name__ == "__main__":
    unittest.main()
