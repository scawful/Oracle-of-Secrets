import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCATOR = ROOT / "Scripts/Build/z3ed_locator.sh"


def make_exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


class Z3edLocatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.repo = self.root / "work" / "oracle"
        self.repo.mkdir(parents=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def find(self, **extra):
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin"}
        env.update(extra)
        script = f'source "{LOCATOR}"; oos_find_z3ed "{self.repo}"'
        return subprocess.run(["bash", "-c", script], env=env,
                              capture_output=True, text=True)

    def test_override_is_returned_as_given(self):
        make_exe(self.bin / "z3ed")
        result = self.find(OOS_Z3ED_BIN="/explicit/z3ed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "/explicit/z3ed")

    def test_sibling_checkout_precedes_path(self):
        sibling = make_exe(self.root / "work/yaze/scripts/z3ed")
        make_exe(self.bin / "z3ed")
        result = self.find()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).resolve(), sibling.resolve())

    def test_path_is_used(self):
        on_path = make_exe(self.bin / "z3ed")
        result = self.find()
        self.assertEqual(result.stdout.strip(), str(on_path))

    def test_nightly_bundle_without_path(self):
        release = self.home / ".local/yaze/nightly/2026-11-10"
        (release / "yaze.app/Contents/MacOS").mkdir(parents=True)
        bundled = make_exe(release / "z3ed")
        (self.home / "Applications").mkdir()
        (self.home / "Applications/Yaze Nightly.app").symlink_to(release / "yaze.app")
        result = self.find()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).resolve(), bundled.resolve())

    def test_local_yaze_current(self):
        current = make_exe(self.home / ".local/yaze/nightly/current/z3ed")
        result = self.find()
        self.assertEqual(result.stdout.strip(), str(current))

    def test_local_yaze_bin(self):
        local_bin = make_exe(self.home / ".local/yaze/bin/z3ed")
        result = self.find()
        self.assertEqual(result.stdout.strip(), str(local_bin))

    def test_missing_fails_with_checked_locations(self):
        result = self.find()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("z3ed not found", result.stderr)
        self.assertIn(".local/yaze/nightly/current/z3ed", result.stderr)
        self.assertIn("OOS_Z3ED_BIN", result.stderr)

    def test_build_stages_use_locator(self):
        source = (ROOT / "Scripts/Build/build_rom.sh").read_text()
        self.assertIn('source "$repo_root/Scripts/Build/z3ed_locator.sh"', source)
        self.assertIn('native_z3ed="$(oos_find_z3ed "$repo_root")"', source)
        self.assertIn('z3ed_cli="$(oos_find_z3ed "$repo_root" 2>/dev/null || true)"', source)


if __name__ == "__main__":
    unittest.main()
