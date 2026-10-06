"""Exercise the real validator/generator after the Scripts directory migration."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / "Scripts/Validate/validate_sprite_registry.py"


class SpriteRegistryCommandTest(unittest.TestCase):
    def run_validator(self, cwd, ids):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--strict", "--registry",
             str(ROOT / "Sprites/registry.csv"), "--ids", str(ids)],
            cwd=cwd, capture_output=True, text=True, check=False,
        )

    def test_repository_ids_pass_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_validator(directory, ROOT / "Sprites/sprite_registry_ids.asm")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("sprite registry OK", result.stdout)

    def test_stale_ids_are_rejected_after_generator_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            ids = Path(directory) / "stale.asm"
            ids.write_text("; stale generated IDs\n")
            result = self.run_validator(directory, ids)
            self.assertEqual(ids.read_text(), "; stale generated IDs\n")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("out of date", result.stdout)
        self.assertNotIn("not found", result.stdout)


if __name__ == "__main__":
    unittest.main()
