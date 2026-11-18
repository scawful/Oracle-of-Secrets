import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_attract_cast import ROOT, generate  # noqa: E402


class AttractCastGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT / "Dungeons/Data/attract_royal_cast.json").read_text())

    def test_generated_output_matches_tracked_asm(self):
        asm = (ROOT / "Dungeons/Data/attract_royal_poses.asm").read_text()
        self.assertEqual(generate(self.source), asm)
        self.assertIn("dl AttractRoyal_commander_south_0_x", asm)
        self.assertIn("AttractRoyal_TrackPointers:", asm)

    def test_rejects_missing_actor_in_track(self):
        bad = copy.deepcopy(self.source)
        bad["scenes"][0]["tracks"].append({"actor": "missing_actor", "t_start": "0x0100", "t_end": "0x0080"})
        with self.assertRaises(ValueError):
            generate(bad)

    def test_rejects_missing_pose_in_track(self):
        bad = copy.deepcopy(self.source)
        bad["scenes"][0]["tracks"].append({"actor": "farore", "t_start": "0x0100", "t_end": "0x0080", "pose_end": "no_such_pose"})
        with self.assertRaises(ValueError):
            generate(bad)

    def test_rejects_reversed_track_window(self):
        bad = copy.deepcopy(self.source)
        bad["scenes"][0]["tracks"].append({"actor": "farore", "t_start": "0x0080", "t_end": "0x0100"})
        with self.assertRaises(ValueError):
            generate(bad)

    def test_rejects_unknown_flag(self):
        bad = copy.deepcopy(self.source)
        bad["scenes"][0]["tracks"].append({"actor": "farore", "t_start": "0x0100", "t_end": "0x0080", "flags": ["warp"]})
        with self.assertRaises(ValueError):
            generate(bad)


if __name__ == "__main__":
    unittest.main()
