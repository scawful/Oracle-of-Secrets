from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "Scripts" / "Build" / "z3dk_safe_smoke.sh"


class Z3dkSafeSmokeTest(unittest.TestCase):
    def write_stub(self, root: Path, body: str) -> Path:
        stub = root / "z3asm-stub"
        stub.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
        stub.chmod(0o755)
        return stub

    def run_smoke(self, root: Path, stub: Path, timeout: int = 5) -> subprocess.CompletedProcess[str]:
        base = root / "base.sfc"
        base.write_bytes(bytes(range(32)))
        env = os.environ.copy()
        env["OOS_BASE_ROM"] = str(base)
        return subprocess.run(
            [
                str(SMOKE_SCRIPT),
                "168",
                "--z3asm",
                str(stub),
                "--temp-root",
                str(root),
                "--timeout",
                str(timeout),
                "--no-symbols",
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout + 5,
        )

    def test_seeds_target_and_preserves_source_rom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stub = self.write_stub(
                root,
                textwrap.dedent(
                    """\
                    target="${@: -1}"
                    printf '\\377' | dd of="$target" bs=1 seek=0 conv=notrunc status=none
                    """
                ),
            )

            result = self.run_smoke(root, stub)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "base.sfc").read_bytes(), bytes(range(32)))
            self.assertIn("Build succeeded", result.stdout)

    def test_rejects_success_without_a_patched_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stub = self.write_stub(root, ":\n")

            result = self.run_smoke(root, stub)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("without changing the seeded ROM", result.stderr)

    def test_times_out_hung_assembler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stub = self.write_stub(root, "sleep 30\n")

            started = time.monotonic()
            result = self.run_smoke(root, stub, timeout=1)

            self.assertNotEqual(result.returncode, 0)
            self.assertLess(time.monotonic() - started, 8)
            self.assertIn("timed out after 1s", result.stderr)


if __name__ == "__main__":
    unittest.main()
