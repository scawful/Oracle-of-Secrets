from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from Scripts.Validate.verify_hooks_json import _run_generator


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_GENERATOR = REPO_ROOT / "Scripts" / "Generate" / "generate_hooks_json.py"


class HookToolPathTest(unittest.TestCase):
    def test_verifier_uses_categorized_generator_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generator = root / "Scripts" / "Generate" / "generate_hooks_json.py"
            generator.parent.mkdir(parents=True)
            generator.write_text(
                textwrap.dedent(
                    """\
                    import argparse
                    import json

                    parser = argparse.ArgumentParser()
                    parser.add_argument("--root")
                    parser.add_argument("--output")
                    parser.add_argument("--rom")
                    args = parser.parse_args()
                    with open(args.output, "w", encoding="utf-8") as handle:
                        json.dump({"hooks": []}, handle)
                    """
                ),
                encoding="utf-8",
            )
            output = root / "generated.json"

            _run_generator(root, root / "rom.sfc", output)

            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")), {"hooks": []}
            )
            self.assertFalse((root / "scripts" / "generate_hooks_json.py").exists())

    def test_generator_canonicalizes_absolute_rom_path_before_relativizing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            real_root = temp_root / "real"
            alias_root = temp_root / "alias"
            rom = real_root / "Roms" / "test.sfc"
            rom.parent.mkdir(parents=True)
            rom.write_bytes(b"test-rom")
            (real_root / "test.asm").write_text("org $008000\nnop\n", encoding="utf-8")

            try:
                os.symlink(real_root, alias_root, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")

            output = temp_root / "hooks.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(HOOK_GENERATOR),
                    "--root",
                    str(alias_root),
                    "--rom",
                    str(alias_root / "Roms" / "test.sfc"),
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            metadata = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(metadata["rom"]["path"], "Roms/test.sfc")


if __name__ == "__main__":
    unittest.main()
