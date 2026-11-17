"""Controls for Scripts/Rooms/pot_item_bank_migration.py.

Runs on a synthetic 4 MiB image with a small bank-$01 pot layout. No real ROM
is read or written; file cases use temporary directories only.
"""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pot_item_bank_migration", ROOT / "Scripts" / "Rooms" / "pot_item_bank_migration.py")
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

EMPTY = b"\xff\xff"
KEY_POT = bytes.fromhex("1a0c08") + EMPTY                    # one record
TWO_POTS = bytes.fromhex("4a12015e1288") + EMPTY             # two records
TAIL_AT = 3                                                  # second record of TWO_POTS
ROOM_STREAMS = {0x000: KEY_POT, 0x001: TWO_POTS, 0x002: TWO_POTS,
                0x003: TWO_POTS[TAIL_AT:], 0x127: KEY_POT[:0] + bytes.fromhex("0c0a0b") + EMPTY}


def synthetic_rom() -> bytearray:
    rom = bytearray(0x400000)
    rom[M.LOADER_PC:M.LOADER_PC + 3] = bytes.fromhex("a90100")
    at = M.OLD_START_PC
    rom[at:at + 2] = EMPTY
    empty_pc, at = at, at + 2
    placed = {}
    for stream in (KEY_POT, TWO_POTS, ROOM_STREAMS[0x127]):
        rom[at:at + len(stream)] = stream
        placed[stream] = at
        at += len(stream)
    placed[TWO_POTS[TAIL_AT:]] = placed[TWO_POTS] + TAIL_AT     # pointer into a stream
    rom[M.OLD_END_PC - 2:M.OLD_END_PC] = EMPTY                  # vanilla pad target
    for room in range(M.ROOM_COUNT):
        pc = placed[ROOM_STREAMS[room]] if room in ROOM_STREAMS else empty_pc
        rom[M.TABLE_PC + room * 2:M.TABLE_PC + room * 2 + 2] = (
            M.lorom_address(pc).to_bytes(2, "little"))
    for slot in range(M.PAD_COUNT):
        rom[M.PAD_PC + slot * 2:M.PAD_PC + slot * 2 + 2] = (
            M.lorom_address(M.OLD_END_PC - 2).to_bytes(2, "little"))
    return rom


def game_stream(rom: bytes, room: int) -> bytes:
    """Independent of the tool: read a room's pot list the way RevealPotItem does."""
    assert rom[M.LOADER_PC] == 0xA9 and rom[M.LOADER_PC + 2] == 0x00
    bank = rom[M.LOADER_PC + 1]
    pointer = int.from_bytes(rom[M.TABLE_PC + room * 2:M.TABLE_PC + room * 2 + 2], "little")
    start = at = (bank & 0x7F) * 0x8000 + (pointer - 0x8000)
    while rom[at:at + 2] != EMPTY:
        at += 3
    return bytes(rom[start:at + 2])


def run(argv):
    stream = io.StringIO()
    with redirect_stdout(stream):
        code = M.main(argv)
    return code, json.loads(stream.getvalue())


class PlanTest(unittest.TestCase):
    def test_every_room_reads_the_same_stream_from_bank_5c(self):
        rom = bytes(synthetic_rom())
        out, report = M.build_plan(rom)
        self.assertEqual(out[M.LOADER_PC:M.LOADER_PC + 3], bytes.fromhex("a95c00"))
        for room in range(M.ROOM_COUNT):
            self.assertEqual(game_stream(out, room), game_stream(rom, room), hex(room))
            self.assertEqual(game_stream(out, room), ROOM_STREAMS.get(room, EMPTY))
        self.assertEqual(report["rooms_with_pots"], 5)
        self.assertEqual(report["pot_records"], 1 + 2 + 2 + 1 + 1)
        self.assertEqual(report["distinct_streams"], 5)   # empty + 4 pointers
        self.assertEqual(report["output_sha256"], hashlib.sha256(out).hexdigest())

    def test_shared_pointers_stay_shared_and_distinct_stay_distinct(self):
        out, _ = M.build_plan(bytes(synthetic_rom()))
        word = lambda room: out[M.TABLE_PC + room * 2:M.TABLE_PC + room * 2 + 2]
        self.assertEqual(word(1), word(2))
        self.assertNotEqual(word(1), word(3))
        self.assertEqual(word(4), word(5))                # both empty
        self.assertEqual(word(0), (0x8002).to_bytes(2, "little"))   # after the empty list

    def test_only_table_operand_and_bank_5c_change(self):
        rom = bytes(synthetic_rom())
        out, report = M.build_plan(rom)
        changed = [pc for pc in range(len(rom)) if rom[pc] != out[pc]]
        for pc in changed:
            self.assertTrue(M.TABLE_PC <= pc < M.OLD_START_PC or pc == M.OPERAND_PC
                            or M.NEW_START_PC <= pc < M.BANK_END_PC, hex(pc))
        self.assertEqual(report["changed_bytes"], len(changed))
        self.assertEqual(out[M.OLD_START_PC:M.OLD_END_PC], rom[M.OLD_START_PC:M.OLD_END_PC])

    def test_pad_words_point_at_the_reserved_terminator(self):
        out, _ = M.build_plan(bytes(synthetic_rom()))
        self.assertEqual(out[M.PAD_SENTINEL_PC:M.PAD_SENTINEL_PC + 2], EMPTY)
        self.assertEqual(out[M.PAD_PC:M.OLD_START_PC], (0xFFFE).to_bytes(2, "little") * M.PAD_COUNT)
        self.assertLessEqual(M.NEW_END_PC, M.PAD_SENTINEL_PC)

    def test_unexpected_layouts_are_refused(self):
        def mutate(pc, data):
            rom = synthetic_rom()
            rom[pc:pc + len(data)] = data
            return bytes(rom)
        cases = {
            "loader_changed": (mutate(M.LOADER_PC, b"\xea"), "expected A90100"),
            "bank_in_use": (mutate(M.NEW_START_PC + 0x100, b"\x01"), "is not empty"),
            "pointer_outside": (mutate(M.TABLE_PC + 8, (0xDB69).to_bytes(2, "little")),
                                "room 0x004: pot pointer"),
            "pointer_unmapped": (mutate(M.TABLE_PC + 8, (0x7000).to_bytes(2, "little")),
                                 "not a ROM address"),
            "pad_word_wrong": (mutate(M.PAD_PC, (0xDDE9).to_bytes(2, "little")),
                               "pad word 0 "),
            "too_small": (bytes(synthetic_rom()[:0x200000]), "needs 0x2E8000"),
        }
        unterminated = synthetic_rom()
        unterminated[M.OLD_START_PC:M.OLD_END_PC] = b"\x01" * (M.OLD_END_PC - M.OLD_START_PC)
        cases["unterminated"] = (bytes(unterminated), "unterminated|cut off")
        for name, (rom, message) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(M.PlanError, message):
                    M.build_plan(rom)

    def test_a_migrated_image_is_refused(self):
        out, _ = M.build_plan(bytes(synthetic_rom()))
        with self.assertRaisesRegex(M.PlanError, "already migrated"):
            M.build_plan(out)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.rom = self.dir / "rom.sfc"
        self.before = bytes(synthetic_rom())
        self.rom.write_bytes(self.before)
        self.sha = hashlib.sha256(self.before).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_is_the_default_and_writes_nothing(self):
        code, report = run(["--rom", str(self.rom)])
        self.assertEqual((code, report["status"], report["mode"]), (0, "ok", "dry-run"))
        self.assertEqual(self.rom.read_bytes(), self.before)
        self.assertEqual([path.name for path in self.dir.iterdir()], ["rom.sfc"])
        self.assertNotIn("written", report)

    def test_write_needs_the_pinned_hash_and_one_target(self):
        out, back = self.dir / "out.sfc", self.dir / "back.sfc"
        cases = [
            (["--write", "--output", str(out)], "needs --expect-sha256"),
            (["--write", "--expect-sha256", "0" * 64, "--output", str(out)], "sha256 is"),
            (["--write", "--expect-sha256", self.sha], "exactly one of"),
            (["--write", "--expect-sha256", self.sha, "--in-place", "--output", str(out)],
             "exactly one of"),
            (["--write", "--expect-sha256", self.sha, "--in-place"], "needs --rollback"),
            (["--output", str(out)], "only accepted with --write"),
            (["--write", "--expect-sha256", self.sha, "--output", str(self.rom)],
             "already exists"),
            (["--write", "--expect-sha256", self.sha, "--output", str(out),
              "--rollback", str(out)], "already in use"),
        ]
        for extra, message in cases:
            with self.subTest(extra=extra):
                code, report = run(["--rom", str(self.rom), *extra])
                self.assertEqual((code, report["status"]), (1, "refused"))
                self.assertRegex(report["error"], message)
                self.assertEqual(self.rom.read_bytes(), self.before)
                self.assertFalse(out.exists() or back.exists())

    def test_write_to_a_new_file_leaves_the_input_alone(self):
        out, back = self.dir / "out.sfc", self.dir / "back.sfc"
        code, report = run(["--rom", str(self.rom), "--expect-sha256", self.sha, "--write",
                            "--output", str(out), "--rollback", str(back),
                            "--report", str(self.dir / "report.json")])
        self.assertEqual((code, report["status"]), (0, "ok"))
        self.assertEqual(self.rom.read_bytes(), self.before)
        self.assertEqual(back.read_bytes(), self.before)
        self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(), report["output_sha256"])
        self.assertEqual(json.loads((self.dir / "report.json").read_text()), report)

    def test_in_place_replaces_the_input_and_keeps_a_rollback(self):
        back = self.dir / "back.sfc"
        code, report = run(["--rom", str(self.rom), "--expect-sha256", self.sha, "--write",
                            "--in-place", "--rollback", str(back)])
        self.assertEqual((code, report["status"]), (0, "ok"))
        self.assertEqual(back.read_bytes(), self.before)
        self.assertEqual(hashlib.sha256(self.rom.read_bytes()).hexdigest(),
                         report["output_sha256"])
        self.assertEqual(sorted(path.name for path in self.dir.iterdir()),
                         ["back.sfc", "rom.sfc"])
        code, report = run(["--rom", str(self.rom)])       # second run: refused
        self.assertEqual(code, 1)
        self.assertRegex(report["error"], "already migrated")

    def test_an_error_after_the_rollback_copy_reports_it_as_failed(self):
        out, back = self.dir / "out.sfc", self.dir / "back.sfc"
        real = M.publish_exclusive

        def fail_on_output(path, data, mode):
            if path == out.resolve():
                raise OSError("disk full")
            real(path, data, mode)
        with mock.patch.object(M, "publish_exclusive", fail_on_output):
            code, report = run(["--rom", str(self.rom), "--expect-sha256", self.sha, "--write",
                                "--output", str(out), "--rollback", str(back)])
        self.assertEqual((code, report["status"]), (1, "failed"))
        self.assertEqual(report["written"], {"rollback": str(back.resolve())})
        self.assertEqual(back.read_bytes(), self.before)
        self.assertEqual(self.rom.read_bytes(), self.before)
        self.assertFalse(out.exists())

    def test_a_bad_readback_after_the_replace_is_failed_not_refused(self):
        back = self.dir / "back.sfc"
        real = M.os.replace

        def replace_then_damage(source, target):
            real(source, target)
            with open(target, "r+b") as handle:
                handle.write(b"\xa5")       # the image starts with 00
        with mock.patch.object(M.os, "replace", replace_then_damage):
            code, report = run(["--rom", str(self.rom), "--expect-sha256", self.sha, "--write",
                                "--in-place", "--rollback", str(back)])
        self.assertEqual((code, report["status"]), (1, "failed"))
        self.assertRegex(report["error"], "output readback differs")
        self.assertEqual(report["written"], {"rollback": str(back.resolve()),
                                             "output": str(self.rom.resolve())})
        self.assertEqual(back.read_bytes(), self.before)
        self.assertNotEqual(self.rom.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
