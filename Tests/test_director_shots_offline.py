"""Offline controls for promo shot fixtures and director parse (no emulator)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MESEN_CLIENT = Path(
    __import__("os").environ.get("MESEN2_OOS_ROOT")
    or ROOT.parent / "mesen2-oos"
) / "tools" / "oos_client"

if str(MESEN_CLIENT) not in sys.path:
    sys.path.insert(0, str(MESEN_CLIENT))

from mesen2_client_lib.director_camera import (  # noqa: E402
    clamp_camera,
    parse_cutscene_shots,
    refuse_rc_play_socket,
    shot_extent,
)


SHOTS_PATH = ROOT / "Data" / "debug" / "promo_shots" / "starter_shots.json"


class DirectorShotsOfflineTest(unittest.TestCase):
    def test_starter_shots_parse_and_clamp_in_bounds(self):
        shots = parse_cutscene_shots(SHOTS_PATH.read_text())
        self.assertGreaterEqual(len(shots), 3)
        for shot in shots:
            extent = shot_extent(shot)
            cx, cy, clamped = clamp_camera(extent, shot.camera_x, shot.camera_y)
            self.assertFalse(
                clamped,
                f"{shot.name} camera ({shot.camera_x},{shot.camera_y}) "
                f"clamped to ({cx},{cy})",
            )

    def test_refuse_rc_play(self):
        refuse_rc_play_socket("/tmp/mesen2-owned.sock")
        with self.assertRaises(Exception):
            refuse_rc_play_socket("/tmp/mesen2-oos-rc-play.sock")

    def test_oos_director_help_runs(self):
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(ROOT / "Scripts" / "Mesen2" / "oos_director_capture.py"), "--help"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("capture", proc.stdout)

    def test_oos_director_validate_and_list(self):
        import json
        import subprocess

        validate = subprocess.run(
            [
                sys.executable,
                str(ROOT / "Scripts" / "Mesen2" / "oos_director_capture.py"),
                "validate",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stderr)
        payload = json.loads(validate.stdout)
        self.assertTrue(payload.get("ok"))
        self.assertGreaterEqual(payload.get("count", 0), 3)

        listing = subprocess.run(
            [
                sys.executable,
                str(ROOT / "Scripts" / "Mesen2" / "oos_director_capture.py"),
                "list",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(listing.returncode, 0)
        listed = json.loads(listing.stdout)
        self.assertTrue(listed.get("ok"))
        self.assertGreaterEqual(len(listed.get("shots", [])), 3)


if __name__ == "__main__":
    unittest.main()
