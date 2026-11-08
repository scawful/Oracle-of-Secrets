"""render_review_sheet.py: entrance flag choice, binding, native alignment, height metric.

z3ed is replaced by a small fake executable; no ROM or real renderer is used.
"""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "Scripts/Rooms/render_review_sheet.py"
SPEC = importlib.util.spec_from_file_location("render_review_sheet", SCRIPT)
sheet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sheet)

# Entrance 0x81 leads into room 0x11 (direct); entrance 0x34 leads into room 0xDB.
FAKE_Z3ED = '''#!{python}
import json, sys
from PIL import Image, ImageDraw
args = sys.argv[1:]
with open({log!r}, "a") as log:
    log.write(json.dumps(args) + "\\n")
opts = dict(a.split("=", 1) for a in args if "=" in a)
if args[0] == "dungeon-get-entrance":
    ent = opts["--entrance"].lower()
    room = {{"0x81": "0x0011", "0x34": "0x00DB"}}[ent]
    print(json.dumps({{"entrance_id": ent, "room_id": room, "camera": {{"x": 768, "y": 744}},
                      "properties": {{"blockset": "0x01", "dungeon_id": "0x00"}}}}))
elif args[0] == "dungeon-render":
    entrance = "--entrance" in opts or "--graphics-entrance" in opts
    img = Image.new("RGB", (512, 512), (40, 90, 40) if entrance else (40, 90, 140))
    d = ImageDraw.Draw(img)
    for i in range(0, 512, 16):
        d.line((i, 0, i, 511), fill=(200, 200, 200))
        d.line((0, i * 2 % 512, 511, i * 2 % 512), fill=(i % 256, 30, 30))
    img.save(opts["--output"])
    print("note: banner text before json")
    print(json.dumps({{"main_blockset": "0x01" if entrance else "0x03",
                      "graphics_entrance_id": opts.get("--graphics-entrance"),
                      "entrance_id": opts.get("--entrance"),
                      "slots": [{{"sheet": "0x61"}}]}}))
'''


class RenderReviewSheet(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.log = self.dir / "argv.log"
        self.z3ed = self.dir / "z3ed"
        self.z3ed.write_text(FAKE_Z3ED.format(python=sys.executable, log=str(self.log)))
        self.z3ed.chmod(0o755)
        self.rom = self.dir / "fake.sfc"
        self.rom.write_bytes(b"\0" * 1024)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def run_sheet(self, *extra):
        out = self.dir / "out"
        rc = sheet.main(["--z3ed", str(self.z3ed), "--rom", str(self.rom), "--out", str(out), *extra])
        manifest = json.loads((out / "manifest.json").read_text()) if rc == 0 else None
        return rc, manifest

    def test_direct_entrance_uses_entrance_flag(self):
        rc, manifest = self.run_sheet("--room", "0x11", "--graphics-entrance", "0x81", "--before-header")
        self.assertEqual(rc, 0)
        renders = [c for c in self.calls() if c[0] == "dungeon-render"]
        self.assertIn("--entrance=0x81", renders[0])
        self.assertFalse(any(a.startswith("--graphics-entrance") or a.startswith("--entrance")
                             for a in renders[1]), "header-default BEFORE must not pass an entrance")
        self.assertEqual(manifest["after"]["mode"], "direct_entrance")
        self.assertEqual(manifest["before"]["mode"], "header_default")
        self.assertEqual(manifest["graphics_entrance"]["id"], "0x81")
        self.assertTrue((self.dir / "out/sheet.png").exists())

    def test_other_room_entrance_uses_graphics_entrance_flag(self):
        rc, manifest = self.run_sheet("--room", "0xCD", "--graphics-entrance", "0x34")
        self.assertEqual(rc, 0)
        render = [c for c in self.calls() if c[0] == "dungeon-render"][0]
        self.assertIn("--graphics-entrance=0x34", render)
        self.assertEqual(manifest["after"]["mode"], "inherited_entrance")
        self.assertEqual(manifest["after"]["main_blockset"], "0x01")

    def test_bind_reports_unbound_when_pixels_differ(self):
        wrong = self.dir / "wrong.png"
        Image.new("RGB", (512, 512), (1, 2, 3)).save(wrong)
        rc, manifest = self.run_sheet("--room", "0xCD", "--graphics-entrance", "0x34",
                                      "--after-png", str(wrong), "--before-png", str(wrong), "--bind", "before")
        self.assertEqual(rc, 0)
        self.assertEqual(manifest["graphics_binding"]["status"], "UNBOUND")
        self.assertGreater(manifest["graphics_binding"]["differing_pixels"], 0)

    def test_prerendered_without_rom_is_unbound(self):
        img = self.dir / "a.png"
        Image.new("RGB", (512, 512), (9, 9, 9)).save(img)
        out = self.dir / "o2"
        self.assertEqual(sheet.main(["--room", "0xCD", "--after-png", str(img), "--out", str(out)]), 0)
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["graphics_binding"]["status"], "UNBOUND")
        self.assertEqual(manifest["self_check"][:7], "PENDING")

    def test_native_alignment_finds_offset(self):
        render = Image.new("RGB", (512, 512))
        d = ImageDraw.Draw(render)
        for i in range(0, 512, 7):
            d.line((i, 0, (i * 3) % 512, 511), fill=(i % 256, (i * 5) % 256, 90))
        native = render.crop((250, 228, 506, 452))
        fit = sheet.align_native(native, render, (256, 232))
        self.assertEqual((fit["x"], fit["y"]), (250, 228))
        self.assertEqual(fit["match"], 1.0)

    def test_height_metric_step(self):
        img = Image.new("RGB", (512, 512), (100, 100, 100))
        ImageDraw.Draw(img).rectangle((0, 0, 511, 200), fill=(220, 220, 220))
        present = sheet.height_metric(img, None, {"lower": (10, 40), "upper": (10, 10)})
        self.assertEqual(present["status"], "LUMA_STEP_PRESENT")
        flat = sheet.height_metric(img, None, {"lower": (10, 40), "upper": (20, 40)})
        self.assertEqual(flat["status"], "LUMA_STEP_ABSENT")
        self.assertEqual(sheet.height_metric(img, None, {"lower": (1, 1)})["status"], "NOT_MEASURED")

    def test_bad_callout_role_is_rejected(self):
        rc, _ = self.run_sheet("--room", "0x11", "--callout", "floor:1,1")
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
