"""b45 Equipment menu SFX: source sound sites, fixture layout, exact store PCs; no native calls."""
import importlib.util
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("equipment_menu_sfx", ROOT / "Tests" / "native" / "equipment_menu_sfx.py")
sfx = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sfx)
EQUIPMENT = (ROOT / "Menu" / "menu_equipment.asm").read_text()
PAGE3 = (ROOT / "Menu" / "menu_page3.asm").read_text()
# Retained b45 (836cee2f) symbols; only immediates change, so the candidate keeps them.
B45_SYMBOLS = {"Menu_Equipment_Move_accept": 0x2DF5C3, "Menu_Equipment_Select_sound": 0x2DF676,
               "Menu_Page3_ToggleRing": 0x2DF232, "Menu_Page3_ToggleRing_wear": 0x2DF247}


def routine(text, name):
    return re.search(rf"^{name}:\n\{{\n(.*?)^\}}", text, re.M | re.S).group(1)


def sound_after(body, line):
    """SFX3 immediate of the first `STA.w $012F` after the source line `line`."""
    tail = body[re.search(rf"^\s*{re.escape(line)}\s*$", body, re.M).end():]
    return int(re.search(r"LDA\.b #\$([0-9A-F]{2}) : STA\.w \$012F", tail).group(1), 16)


def db_row(body, label):
    row = re.search(rf"^{re.escape(label)}\n\s*db ([$\dA-F, ]+)$", body, re.M).group(1)
    return [int(v.strip().replace("$", "0x"), 0) for v in row.split(",")]


class EquipmentMenuSfx(unittest.TestCase):
    def test_selection_sites_queue_cursor_sound(self):
        select, move = routine(EQUIPMENT, "Menu_Equipment_Select"), routine(EQUIPMENT, "Menu_Equipment_Move")
        ring = routine(PAGE3, "Menu_Page3_ToggleRing")
        sites = {"select .sound": sound_after(select, ".sound"), "ring .wear": sound_after(ring, ".wear"),
                 "ring .on": sound_after(ring, ".on"), "ring .off": sound_after(ring, ".off"),
                 "move .accept": sound_after(move, ".accept"),
                 "one-ring unwear": sound_after(ring, "CMP.l RingSlot1 : BNE .wear")}
        self.assertEqual(sites, dict.fromkeys(sites, sfx.MOVE_SOUND))
        self.assertNotIn("#$22 : STA.w $012F", select + ring)
        self.assertIn("LDA.b #$3C : STA.w $012E", select.split(".error", 1)[1])

    def test_fixture_layout_matches_b45_source(self):
        move, select = routine(EQUIPMENT, "Menu_Equipment_Move"), routine(EQUIPMENT, "Menu_Equipment_Select")
        starts = db_row(move, ".starts")
        self.assertEqual(tuple(starts + db_row(move, ".ends")[-1:]), sfx.ROW_STARTS)
        self.assertIn(f"CMP.b #${sfx.ROW_STARTS[-1]:02X} : BCC .valid", move)
        for bound in sfx.ROW_STARTS[1:4]:
            self.assertIn(f"CMP.b #${bound:02X} : BCS", select)
        self.assertIn(f"SEC : SBC.b #${sfx.ROW_STARTS[1] - 2:02X}", select)   # Power: slot 6 -> ring ID 2
        self.assertEqual(sfx.SLOT_POWER - (sfx.ROW_STARTS[1] - 2), sfx.POWER_ID)
        self.assertIn(f"SEC : SBC.b #${sfx.ROW_STARTS[2] - 1:02X} : STA.w CurrentSong", select)
        self.assertEqual((sfx.SLOT_DEKU, sfx.SLOT_POWER, sfx.SLOT_SONG1), tuple(starts[:3]))
        bits = db_row(PAGE3, "Menu_Page3_RingBits:")
        self.assertEqual(bits[sfx.SLOT_POWER - sfx.ROW_STARTS[1]], sfx.POWER_BIT)
        columns = db_row(EQUIPMENT, "Menu_Equipment_Columns:")
        self.assertEqual(len(columns), sfx.ROW_STARTS[-1])
        self.assertEqual({columns[s] for s in (sfx.SLOT_DEKU, sfx.SLOT_POWER, sfx.SLOT_SONG1)}, {columns[0]})

    def test_store_sites_reject_wrong_pc_and_original_sound(self):
        def flow(select_sound, expected):
            memory = {}
            for action, (label, offset) in sfx.STORE_SITES.items():
                sound = select_sound if action in ("select", "wear") else sfx.MOVE_SOUND
                pc = B45_SYMBOLS[label] + offset
                memory.update(zip(range(pc - 2, pc + 3), (0xA9, sound, 0x8D, 0x2F, 0x01)))
            job = tempfile.TemporaryDirectory()
            self.addCleanup(job.cleanup)
            Path(job.name, "candidatex.sym").write_text("".join(
                f"{a >> 16:02X}:{a & 0xFFFF:04X} Oracle_{label}\n" for label, a in B45_SYMBOLS.items()))
            bridge = SimpleNamespace(read_block=lambda a, n: bytes(memory.get(a + i, 0) for i in range(n)))
            run = sfx.EquipmentSfx(SimpleNamespace(job=job.name, b=bridge), Path(job.name, "R.json"), expected)
            run.resolve_sites()
            return run

        run = flow(sfx.MOVE_SOUND, sfx.MOVE_SOUND)
        self.assertEqual({k: v["pc"] for k, v in run.result["store_sites"].items()},
                         {"move": "2DF5CD", "select": "2DF678", "unwear": "2DF240", "wear": "2DF24D"})
        self.assertEqual(flow(sfx.BOSS_DYING, sfx.BOSS_DYING).sites["select"], (0x2DF678, sfx.BOSS_DYING))
        with self.assertRaisesRegex(sfx.Failure, "is not LDA.b #\\$20"):
            flow(sfx.BOSS_DYING, sfx.MOVE_SOUND)          # candidate run on original b45 bytes

        def window(pc, value):
            return {"label": "w", "nonzero": [{"pc": pc, "value": value}]}
        run.expect_sounds(window(0x2DF678, sfx.MOVE_SOUND), "select")
        for pc, value in ((0x2DF678, sfx.BOSS_DYING), (0x2DF67D, sfx.MOVE_SOUND), (0x2DF5CD, sfx.MOVE_SOUND)):
            with self.assertRaises(sfx.Failure):
                run.expect_sounds(window(pc, value), "select")


if __name__ == "__main__":
    unittest.main()
