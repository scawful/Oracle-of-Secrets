"""Offline tests for the scene director pathfinder and scene loader (no emulator)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "Scripts" / "Agents"))

from scene_director import pathfind  # noqa: E402
from scene_director.pathfind import Grid, NeedsRoomChangeError, NoPathError, find_path  # noqa: E402
from scene_director.scenefile import Expr, SceneError, load_scene, parse_scene  # noqa: E402


def room(*lines, width=24, height=20):
    """A walled box; `lines` maps row -> text overlay placed from column 0."""
    rows = ["#" * width] + ["#" + "." * (width - 2) + "#" for _ in range(height - 2)] + ["#" * width]
    for row, text in lines:
        rows[row] = text.ljust(width, "#")[:width]
    return rows


def assert_walkable(test, grid, points, **fits):
    test.assertGreaterEqual(len(points), 1)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        test.assertTrue(x0 == x1 or y0 == y1, f"diagonal leg {(x0, y0)} -> {(x1, y1)}")
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(steps + 1):
            x = x0 + (x1 - x0) * i // max(steps, 1)
            y = y0 + (y1 - y0) * i // max(steps, 1)
            test.assertTrue(grid.link_fits(x, y, **fits), f"Link at {(x, y)} overlaps a blocked cell")


class Geometry(unittest.TestCase):
    def test_index_matches_tiledetect_formula(self):
        for x, y in ((0, 0), (7, 7), (8, 8), (255, 300), (511, 511)):
            portal_formula = ((y & 0x1F8) << 3) + ((x & 0x1FF) >> 3)  # Tests/native/portal_placement.py
            self.assertEqual(pathfind.cell_index(x, y), portal_formula)

    def test_body_and_feet(self):
        # Link at (16, 24): body X 16..31, Y 32..47 -> cols 2-3, rows 4-5; feet (24, 44) -> (3, 5).
        self.assertEqual(pathfind.link_cells(16, 24), [(2, 4), (3, 4), (2, 5), (3, 5)])
        self.assertEqual(pathfind.feet_cell(16, 24), (3, 5))
        self.assertEqual(pathfind.node_to_link(2, 4), (16, 24))

    def test_layer_address(self):
        self.assertEqual(pathfind.colmap_address(0), 0x7F2000)
        self.assertEqual(pathfind.colmap_address(1), 0x7F3000)

    def test_classify(self):
        self.assertEqual(pathfind.classify(0x00), "floor")
        self.assertEqual(pathfind.classify(0x01), "solid")
        self.assertEqual(pathfind.classify(0x20), "hazard")
        self.assertEqual(pathfind.classify(0xB4), "hazard")
        self.assertEqual(pathfind.classify(0x64), "hazard")  # Oracle Minish portal tile
        self.assertEqual(pathfind.classify(0x80), "door")
        self.assertEqual(pathfind.classify(0x1D), "stairs")


class Walls(unittest.TestCase):
    def test_open_room_straight_line(self):
        grid = Grid.from_rows(room())
        points = find_path(grid, (16, 24), (120, 24))
        self.assertEqual(points, [(16, 24), (120, 24)])

    def test_wall_forces_detour(self):
        # Vertical wall at column 10 from row 1 to row 14; open below.
        rows = room()
        for r in range(1, 15):
            rows[r] = rows[r][:10] + "#" + rows[r][11:]
        grid = Grid.from_rows(rows)
        points = find_path(grid, (16, 24), (120, 24))
        assert_walkable(self, grid, points)
        self.assertEqual(points[-1], (120, 24))
        self.assertGreaterEqual(max(y for _, y in points), 8 * 15 - 8, "path must go under the wall")

    def test_target_inside_wall(self):
        grid = Grid.from_rows(room())
        with self.assertRaisesRegex(NoPathError, "blocked"):
            find_path(grid, (16, 24), (0, 0))


class Doorway(unittest.TestCase):
    def wall_with_gap(self, gap_rows):
        rows = room()
        for r in range(1, 19):
            if r not in gap_rows:
                rows[r] = rows[r][:12] + "#" + rows[r][13:]
        return Grid.from_rows(rows)

    def test_two_cell_gap_fits_link(self):
        grid = self.wall_with_gap({9, 10})
        points = find_path(grid, (16, 24), (150, 120))
        assert_walkable(self, grid, points)
        crossing = [p for a, p in zip(points, points[1:]) if a[0] < 96 <= p[0]]
        self.assertTrue(crossing)
        self.assertEqual(crossing[0][1], 8 * 9 - 8, "Link crosses the wall aligned to the gap")

    def test_one_cell_gap_is_too_narrow(self):
        grid = self.wall_with_gap({9})
        with self.assertRaisesRegex(NoPathError, "no in-room path"):
            find_path(grid, (16, 24), (150, 120))

    def test_door_tile_needs_room_change(self):
        rows = room()
        for r in range(1, 19):
            rows[r] = rows[r][:12] + ("D" if r in (9, 10) else "#") + rows[r][13:]
        grid = Grid.from_rows(rows)
        with self.assertRaises(NeedsRoomChangeError) as caught:
            find_path(grid, (16, 24), (150, 120))
        self.assertIn("(12, 9, '80')", str(caught.exception))
        allowed = Grid.from_rows(rows, allow_doors=True)
        assert_walkable(self, allowed, find_path(allowed, (16, 24), (150, 120)))


class Pit(unittest.TestCase):
    def test_path_avoids_pit(self):
        rows = room()
        for r in range(4, 12):
            rows[r] = rows[r][:6] + "oooooooo" + rows[r][14:]
        grid = Grid.from_rows(rows)
        points = find_path(grid, (8, 56), (150, 56))
        assert_walkable(self, grid, points)
        for x, y in points:
            for cell in pathfind.link_cells(x, y):
                self.assertNotEqual(grid.kind(*cell), "hazard")

    def test_pit_across_room_has_no_path(self):
        rows = room()
        for r in range(1, 19):
            rows[r] = rows[r][:10] + "oo" + rows[r][12:]
        grid = Grid.from_rows(rows)
        with self.assertRaisesRegex(NoPathError, "no in-room path"):
            find_path(grid, (16, 24), (150, 24))

    def test_feet_never_on_pit_even_at_edge(self):
        rows = room()
        rows[6] = rows[6][:5] + "o" + rows[6][6:]
        grid = Grid.from_rows(rows, allow_hazard_edge=True)
        # Body overlaps the pit at (5, 6) but feet (cell (5, 6)) would be on it: refused.
        self.assertFalse(grid.link_fits(32, 32))
        # Body corner on the pit, feet beside it: allowed only with allow_hazard_edge.
        self.assertTrue(grid.link_fits(40, 32))
        self.assertFalse(Grid.from_rows(rows).link_fits(40, 32))

    def test_blocked_cells_option(self):
        grid = Grid.from_rows(room(), blocked={(c, r) for c in range(10, 12) for r in range(1, 19)})
        with self.assertRaises(NoPathError):
            find_path(grid, (16, 24), (150, 24))


class Expressions(unittest.TestCase):
    def test_evaluate(self):
        ram = {0x7E0010: 7, 0x7E0011: 0, 0x7EF36D: 0x18, 0x7EF36E: 0x00}
        read = lambda a, n: int.from_bytes(bytes(ram.get(a + i, 0) for i in range(n)), "little")  # noqa: E731
        names = {"room": 0x104, "lx": 100, "ly": 50}
        self.assertTrue(Expr("u8(0x7E0010) == 7 and room == 0x104").evaluate(read, names))
        self.assertTrue(Expr("u16(0x7EF36D) == 0x18").evaluate(read, names))
        self.assertTrue(Expr("90 <= lx <= 110 and not ly > 60").evaluate(read, names))
        self.assertFalse(Expr("u8(0x7E0011) & 1").evaluate(read, names))

    def test_rejects_unsafe(self):
        for text in ("__import__('os')", "open('x')", "room.real", "[1]", "'a' == 'a'", "foo == 1",
                     "u8(1, 2)", "lambda: 1"):
            with self.assertRaises(SceneError, msg=text):
                Expr(text)


class SceneFiles(unittest.TestCase):
    def scene(self, steps):
        return {"scene": "t", "steps": steps}

    def test_valid_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps(self.scene([
                {"load": {"srm": "seed.srm", "fixtures": ["f.json"]}},
                {"walk_to": {"x": 120, "y": 200}},
                {"face": "up"},
                {"press": {"button": ["A", "Up"], "frames": 3}},
                {"wait_until": {"expr": "submodule == 0", "max_frames": 60}},
                {"check": {"expr": "room == 0x104", "label": "house"}},
                {"hold": {"frames": 30}},
            ])))
            scene = load_scene(path)
        self.assertEqual([s.kind for s in scene.steps],
                         ["load", "walk_to", "face", "press", "wait_until", "check", "hold"])
        self.assertEqual(scene.load.args["srm"], (Path(tmp) / "seed.srm").resolve())
        self.assertEqual(scene.steps[3].args["button"], "A,Up")
        self.assertFalse(scene.uses_record())

    def test_errors_name_the_step(self):
        bad = [
            ([{"walk_to": {"x": 1, "y": 1}}, {"load": {"srm": "a"}}], "step 1: load must be the first"),
            ([{"jump": {}}], "unknown kind"),
            ([{"press": {"button": "Z"}}], "step 0 press"),
            ([{"walk_to": {"x": 1}}], "walk_to.y"),
            ([{"wait_until": {"expr": "room == 1"}}], "max_frames"),
            ([{"load": {"srm": "a", "state": "b"}}], "exactly one"),
            ([{"record": "pause"}], "start' or 'stop"),
        ]
        for steps, message in bad:
            with self.assertRaisesRegex(SceneError, message):
                parse_scene(self.scene(steps), Path("/tmp/x.json"))

    def test_record_is_a_clear_stub(self):
        from scene_director import runner
        scene = parse_scene(self.scene([{"load": {"srm": "a"}}, {"record": "start"}]), Path("/tmp/x.json"))
        with self.assertRaisesRegex(SceneError, "not implemented in slice 1"):
            runner.run_scene(scene, Path("/nonexistent.sfc"))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = Path(tmp) / "good.json", Path(tmp) / "bad.json"
            good.write_text(json.dumps(self.scene([{"load": {"srm": "a"}}, {"hold": {"frames": 1}}])))
            bad.write_text(json.dumps(self.scene([{"hold": {}}])))
            cli = [sys.executable, str(REPO / "Scripts" / "Agents" / "scene.py")]
            self.assertEqual(subprocess.run(cli + ["check", str(good)], capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run(cli + ["check", str(bad)], capture_output=True).returncode, 2)
            rec = subprocess.run(cli + ["run", str(good), "--rom", "/nonexistent.sfc", "--record", "o.mp4"],
                                 capture_output=True, text=True)
            self.assertEqual(rec.returncode, 2)
            self.assertIn("not implemented in slice 1", rec.stderr)


if __name__ == "__main__":
    unittest.main()
