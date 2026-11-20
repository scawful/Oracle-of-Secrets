#!/usr/bin/env python3
"""Hermetic tests for the Mesen2 runtime suite. No emulator."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests" / "native"))

import suite_runner as suite  # noqa: E402

SUITE_PATH = ROOT / "Tests" / "suites" / "beta_smoke.json"
REQUIRED_IDS = (
    "sq_lw_link",
    "sq_abyss_pre_farore",
    "sq_abyss_post_farore",
    "ent_d6_goron",
    "ent_shrine_power",
    "warp_whirlpool_33_15",
    "vblank_epona_ranch",
    "vblank_korl_quay",
    "vblank_deku_hover",
    "dlg_boot_intro_box",
    "ent_d1_grotto",
    "ent_d2_tail",
    "ent_d3_castle",
    "ent_d4_zora",
    "ent_d5_glacia",
    "ent_d7_dragon",
    "ent_d8_fortress",
    "ent_d8_sky",
    "ent_shrine_wisdom",
    "ent_shrine_courage",
    "epona_ride_boost_facing",
    "soar_kalyxo",
    "soar_abyss_moosh",
    "soar_lyra",
    "wolfos_blue",
    "wolfos_grey",
    "wolfos_ice",
    "vblank_chain_chomp",
    "urchin_killable",
    "rod_after_equipment",
    "sword_lv4_goronblade",
)


def _suite() -> dict:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


def _checkpoints() -> dict:
    path = ROOT / _suite()["checkpoints"]
    return suite.checkpoint_table(path)


class ScriptedRuntime:
    """Stands in for Mesen2. Checkpoint bytes land in SRAM on Save & Quit."""

    def __init__(self, *, fail_module: int | None = None):
        self.mem: dict[int, int] = {}
        self.sram = bytes(8192)
        self.area = 0
        self.room = 0
        self.fail_module = fail_module
        self.captures: list[Path] = []

    def boot(self):
        return {"module": 0x09, "sub": 0}

    def apply_writes(self, writes):
        suite.apply_write_list(self.mem, writes)

    def load_overworld(self, via_room, area):
        self.area = area
        self.room = via_room
        return self._world(0x09 if area < 0x80 else 0x0B, area=area)

    def enter_entrance(self, entrance, room):
        self.room = room
        return self._world(0x07, room=room, indoors=1)

    def exit_overworld(self, room, parent_map):
        self.area = parent_map
        return self._world(0x0B if parent_map >= 0x80 else 0x09, area=parent_map, x=120, y=140)

    def run_transport(self, transport, dest_map, submodule):
        self.area = dest_map
        return self._world(0x09, area=dest_map, x=200, y=180)

    def nudge(self, buttons, frames):
        return self._world(0x09, area=self.area, x=180, y=160)

    def save_and_quit(self):
        slot = bytearray(0x500)
        for addr, value in self.mem.items():
            offset = addr - suite.SRAM_BASE
            if 0 <= offset < 0x500:
                slot[offset] = value
        slot[0x3E5] = 0xAA
        slot[0x3E6] = 0x55
        suite.seal_checksum(slot)
        blob = bytearray(8192)
        blob[:0x500] = slot
        blob[0xF00:0x1400] = slot
        self.sram = bytes(blob)
        return {"module": 0x00, "sub": 0x08}

    def read_sram(self):
        return self.sram

    def open_file_select(self):
        return {"module": 0x01, "sub": 0x05, "black": 0, "bright": 0x0F}

    def cgram_word(self, addr):
        info = suite.slot_report(self.sram)
        if addr == suite.GBC_PREVIEW_ADDR and info["gbc"]:
            return suite.GBC_PREVIEW_WORD
        return 0x0C43

    def reload_file(self):
        info = suite.slot_report(self.sram)
        module = self.fail_module if self.fail_module is not None else 0x09
        gbc = info["gbc"]
        return self._world(module, mask=0x06 if gbc else 0, link_gfx=0x3B if gbc else 0x10)

    def arm_message(self, message_id):
        return {"module": 0x0E, "sub": 0x02, "message": message_id, "black": 0,
                "bright": 0x0F, "forced_blank": False, "x": 0, "y": 0, "area": 0, "room": self.room}

    def close_message(self):
        return self._world(0x09, message=0)

    def hold(self, buttons, frames):
        return {
            "frames_advanced": frames,
            "overruns": 0,
            "black": 0,
            "probe": self._world(0x09, area=self.area),
        }

    def tap(self, button, hold=6, settle=12):
        self.taps = getattr(self, "taps", [])
        self.taps.append(button)
        if button == "Start":
            self.mem[suite.MESSAGE] = 0
            self.mem[0x7E020B] = 0

    def u8(self, addr):
        return self.mem.get(addr, 0) & 0xFF

    def u16(self, addr):
        return (self.u8(addr) | (self.u8(addr + 1) << 8)) & 0xFFFF

    def screenshot(self):
        width, height = 320, 240
        rgb = bytes([40, 80, 30]) * (width * height)
        return suite.encode_png(width, height, rgb)

    def save_state(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"MSS" + b"\x00" * 64)
        self.captures.append(path)

    def _world(self, module, **extra):
        state = {
            "module": module, "sub": 0, "bright": 0x0F, "indoors": 0,
            "area": self.area, "room": self.room, "x": 64, "y": 72,
            "mask": 0, "link_gfx": 0x10, "message": 0, "black": 0, "forced_blank": False,
        }
        state.update(extra)
        return state


class BetaSmokeSchemaTest(unittest.TestCase):
    def test_required_scenarios_and_fields(self):
        document = _suite()
        checkpoints = _checkpoints()
        self.assertEqual(document["name"], "beta_smoke")
        ids = [item["id"] for item in document["scenarios"]]
        self.assertEqual(ids, list(REQUIRED_IDS))
        errors = suite.validate_suite(document, checkpoints)
        self.assertEqual({key: value for key, value in errors.items() if value}, {})
        cards = [item["id"] for item in document["scenarios"] if item.get("retroid_card")]
        self.assertEqual(cards, ["vblank_epona_ranch", "vblank_korl_quay", "vblank_deku_hover"])

    def test_checkpoint_chain_keeps_intro_before_loom(self):
        writes = suite.resolve_writes(_checkpoints(), "loom-beach")
        names = [item.get("name") for item in writes]
        self.assertLess(names.index("GameState"), names.index("IntroState"))
        self.assertIn("SavedWorld", names)

    def test_file_select_gbc_rule_matches_sram_layout(self):
        slot = bytearray(0x500)
        slot[0x3C5] = 0x02
        slot[0x3CA] = 0x40
        slot[0x3E5] = 0xAA
        slot[0x3E6] = 0x55
        suite.seal_checksum(slot)
        blob = bytes(slot) + bytes(0xA00) + bytes(slot)
        pre = suite.slot_report(blob)
        self.assertTrue(pre["gbc"] and pre["checksum_ok"] and pre["mirror_ok"])
        slot[0x3C5] = suite.FARORE_RESCUED
        suite.seal_checksum(slot)
        post = suite.slot_report(bytes(slot) + bytes(0xA00) + bytes(slot))
        self.assertFalse(post["gbc"])
        self.assertEqual(post["game_state"], 3)


class ReportContractTest(unittest.TestCase):
    def test_finding_key_and_jump_target_shape(self):
        scenario = _suite()["scenarios"][0]
        item = suite.make_finding(scenario, "file_select_form", "error", "bleed", "sram:0x3CA")
        self.assertEqual(set(item), set(suite.FINDING_KEYS))
        self.assertEqual(item["finding_key"], "save_quit_matrix.sq_lw_link.file_select_form")
        self.assertEqual(item["finding_key"], suite.finding_key("save_quit_matrix", "sq_lw_link", "file_select_form"))
        self.assertEqual(set(item["jump_target"]), {"kind", "id", "x", "y"})
        self.assertEqual(item["jump_target"]["kind"], "overworld")
        self.assertFalse(item["fixable"])
        self.assertEqual(item["severity"], "error")

    def test_dry_run_report_keys_and_exit(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = suite.main([
                "--suite", str(SUITE_PATH), "--dry-run", "--format", "json",
            ])
        self.assertEqual(code, 0)
        report = json.loads(buffer.getvalue())
        self.assertEqual(tuple(report), suite.REPORT_KEYS)
        self.assertEqual(report["tool"], "oos-runtime-suite")
        self.assertEqual(report["suite_name"], "beta_smoke")
        self.assertEqual(report["total_scenarios"], len(REQUIRED_IDS))
        self.assertEqual(report["passed"], len(REQUIRED_IDS))
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["findings"], [])
        self.assertIsNone(report["rom_sha256"])

    def test_unknown_scenario_fails_dry_run(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = suite.main([
                "--suite", str(SUITE_PATH), "--dry-run", "--scenario", "missing_case",
                "--format", "json",
            ])
        self.assertEqual(code, 1)
        report = json.loads(buffer.getvalue())
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["findings"][0]["severity"], "error")

    def test_black_scanline_counter(self):
        width, height = 8, 6
        row = bytes(width * 3)
        body = bytes([20, 40, 10]) * width
        rgb = row * 4 + body + body
        count, solid = suite.leading_black_scanlines(suite.encode_png(width, height, rgb))
        self.assertEqual(count, 4)
        self.assertFalse(solid)


class BaselineRatchetTest(unittest.TestCase):
    def _bad_suite(self, folder: Path, scenario_id: str = "broken") -> Path:
        path = folder / "bad.json"
        path.write_text(json.dumps({
            "name": "bad",
            "checkpoints": "Data/debug/checkpoints.json",
            "scenarios": [{"id": scenario_id, "kind": "nope"}],
        }), encoding="utf-8")
        return path

    def test_write_baseline_then_forgive_and_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            bad = self._bad_suite(folder)
            baseline = folder / "baseline.json"
            first = io.StringIO()
            with redirect_stdout(first):
                code = suite.main([
                    "--suite", str(bad), "--dry-run", "--format", "json",
                    "--write-baseline", str(baseline),
                ])
            self.assertEqual(code, 1)
            saved = json.loads(baseline.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["findings"]), 1)
            second = io.StringIO()
            with redirect_stdout(second):
                code = suite.main([
                    "--suite", str(bad), "--dry-run", "--format", "json",
                    "--baseline", str(baseline),
                ])
            self.assertEqual(code, 0)
            report = json.loads(second.getvalue())
            self.assertEqual(len(report["baselined_findings"]), 1)
            self.assertEqual(report["new_findings"], [])
            self.assertEqual(report["failed"], 1)

            good = folder / "good.json"
            good.write_text(json.dumps({
                "name": "bad",
                "checkpoints": "Data/debug/checkpoints.json",
                "scenarios": [_suite()["scenarios"][0]],
            }), encoding="utf-8")
            third = io.StringIO()
            with redirect_stdout(third):
                code = suite.main([
                    "--suite", str(good), "--dry-run", "--format", "json",
                    "--baseline", str(baseline),
                ])
            self.assertEqual(code, 0)
            resolved = json.loads(third.getvalue())
            self.assertEqual(len(resolved["resolved_findings"]), 1)
            self.assertEqual(resolved["new_findings"], [])

            fresh = self._bad_suite(folder, "other_break")
            fourth = io.StringIO()
            with redirect_stdout(fourth):
                code = suite.main([
                    "--suite", str(fresh), "--dry-run", "--format", "json",
                    "--baseline", str(baseline),
                ])
            self.assertEqual(code, 1)
            newer = json.loads(fourth.getvalue())
            self.assertEqual(len(newer["new_findings"]), 1)
            self.assertEqual(newer["new_findings"][0]["severity"], "error")


class RetroidCardTest(unittest.TestCase):
    def test_dry_run_writes_cards_without_captures(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = suite.main([
                    "--suite", str(SUITE_PATH), "--dry-run", "--format", "json",
                    "--export-retroid-cards", str(dest),
                ])
            self.assertEqual(code, 0)
            for name in ("vblank_epona_ranch", "vblank_korl_quay", "vblank_deku_hover"):
                card = json.loads((dest / name / "card.json").read_text(encoding="utf-8"))
                self.assertEqual(card["id"], name)
                self.assertTrue(card["title"] and card["badge"] and card["summary"])
                self.assertFalse((dest / name / "thumb.png").exists())
                self.assertFalse((dest / name / "state.mss").exists())

    def test_invalid_card_is_rejected_without_a_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "cards.json"
            scenario = json.loads(json.dumps(_suite()["scenarios"][6]))
            scenario["retroid_card"] = {"id": "vblank_epona_ranch", "title": "Test Epona Ranch"}
            path.write_text(json.dumps({
                "name": "cards",
                "checkpoints": "Data/debug/checkpoints.json",
                "scenarios": [scenario],
            }), encoding="utf-8")
            opened = {"count": 0}

            def explode(*_args, **_kwargs):
                opened["count"] += 1
                raise AssertionError("dry-run opened Mesen2")

            original = suite.MesenRuntime.open
            suite.MesenRuntime.open = explode
            try:
                with redirect_stdout(io.StringIO()):
                    code = suite.main([
                        "--suite", str(path), "--dry-run", "--format", "json",
                        "--export-retroid-cards", str(folder / "out"),
                    ])
            finally:
                suite.MesenRuntime.open = original
            self.assertEqual(code, 1)
            self.assertEqual(opened["count"], 0)

    def test_mocked_session_captures_thumb_and_state(self):
        document = _suite()
        chosen = [item for item in document["scenarios"] if item["id"] in ("sq_lw_link", "vblank_korl_quay")]
        runtime = ScriptedRuntime()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            report = suite.run_suite(
                document, checkpoints=_checkpoints(), scenarios=chosen,
                rom=SUITE_PATH, rom_sha="abc", dry_run=False, baseline=None,
                runtime=runtime, export_dir=dest)
            self.assertEqual(suite.exit_code(report, baseline_set=False, strict=False), 0)
            self.assertEqual(report["passed"], 2)
            thumb = dest / "vblank_korl_quay" / "thumb.png"
            state = dest / "vblank_korl_quay" / "state.mss"
            self.assertTrue(thumb.is_file() and state.is_file())
            width, height, _rows = suite.decode_png(thumb.read_bytes())
            self.assertEqual((width, height), (256, 224))
            self.assertGreater(state.stat().st_size, 32)
            card = json.loads((dest / "vblank_korl_quay" / "card.json").read_text(encoding="utf-8"))
            self.assertEqual(card["badge"], "NEW")
            self.assertFalse((dest / "sq_lw_link").exists())

    def test_mocked_softlock_is_a_critical_finding(self):
        document = _suite()
        scenario = next(item for item in document["scenarios"] if item["id"] == "sq_lw_link")
        report = suite.run_suite(
            document, checkpoints=_checkpoints(), scenarios=[scenario],
            rom=None, rom_sha=None, dry_run=False, baseline=None,
            runtime=ScriptedRuntime(fail_module=0))
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["findings"][0]["severity"], "critical")
        self.assertIn(report["findings"][0]["jump_target"]["kind"], suite.JUMP_KINDS)
        self.assertEqual(suite.exit_code(report, baseline_set=False, strict=False), 1)


class StateContractTest(unittest.TestCase):
    def test_sword_words_and_rod_cursor(self):
        document = _suite()
        sword = next(item for item in document["scenarios"] if item["id"] == "sword_lv4_goronblade")
        rod = next(item for item in document["scenarios"] if item["id"] == "rod_after_equipment")
        runtime = ScriptedRuntime()
        runtime.mem[0x2D8290] = 0x8A
        runtime.mem[0x2D8291] = 0x2C
        runtime.mem[0x2D8292] = 0x65
        runtime.mem[0x2D8293] = 0x2C
        runtime.mem[0x2BCDA1] = 0x8A
        runtime.mem[0x2BCDA2] = 0x24
        runtime.mem[0x2BCDA8] = 0x65
        runtime.mem[0x2BCDA9] = 0x24
        runtime.mem[0x2DAD0A] = 0x9C
        runtime.mem[0x2DAD0B] = 0x0B
        runtime.mem[0x2DAD0C] = 0x02
        report = suite.run_suite(
            document, checkpoints=_checkpoints(), scenarios=[sword, rod],
            rom=None, rom_sha=None, dry_run=False, baseline=None, runtime=runtime)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["passed"], 2)

    def test_chain_chomp_room_uses_the_dungeon_path(self):
        document = _suite()
        scenario = next(item for item in document["scenarios"] if item["id"] == "vblank_chain_chomp")
        report = suite.run_suite(
            document, checkpoints=_checkpoints(), scenarios=[scenario],
            rom=None, rom_sha=None, dry_run=False, baseline=None,
            runtime=ScriptedRuntime())
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["findings"], [])


if __name__ == "__main__":
    unittest.main()
