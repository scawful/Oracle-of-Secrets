"""Checks for seed_sky_award_preimages.py: python3 .github/scripts/test_seed_sky_award_preimages.py"""
import ast
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True  # importing the contract test must not add Tests/__pycache__
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "Dungeons" / "sky_d8_award.asm"
RECEIPT_SOURCE = ROOT / "Items" / "bombchu_receipt.asm"
sys.path.insert(0, str(HERE))
import seed_sky_award_preimages as seeder  # noqa: E402
from seed_sky_award_preimages import SeedError  # noqa: E402


def contract_hooks():
    """usdasm hook-site preimages recorded in Tests/test_sky_d8_award_contract.py."""
    spec = importlib.util.spec_from_file_location(
        "sky_contract", ROOT / "Tests" / "test_sky_d8_award_contract.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HOOKS


def seed_of(text):
    return seeder.guard_bytes(seeder.parse_guards(text))


class RealSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text()
        cls.guards = seeder.parse_guards(cls.text)
        cls.seed = seeder.guard_bytes(cls.guards)

    def test_every_read_guard_line_is_parsed(self):
        lines = [n for n, line in enumerate(self.text.splitlines(), 1)
                 if line.lstrip().startswith("assert read")]
        self.assertEqual([g[0] for g in self.guards], lines)
        self.assertEqual(len(self.guards), 41)

    def test_hook_sites_match_usdasm_preimages(self):
        for address, (name, preimage, *_) in contract_hooks().items():
            start = seeder.lorom_offset(address)
            got = bytes(self.seed[start + i] for i in range(len(preimage) // 2))
            self.assertEqual(got.hex().upper(), preimage, name)

    def test_or_guard_takes_first_alternative(self):
        self.assertEqual(self.seed[seeder.lorom_offset(0x08CC48)], 0x8F)

    def test_address_arithmetic(self):
        self.assertEqual(self.seed[seeder.lorom_offset(0x02DD8A + 0x84)], 0x90)
        self.assertEqual(self.seed[seeder.lorom_offset(0x02DD8A + 0x85)], 0x00)
        self.assertEqual(self.seed[seeder.lorom_offset(0x02DE28 + 0x42)], 0x7A)
        self.assertEqual(seeder.lorom_offset(0x02DE6A), 0x15E6A)

    def test_no_overlap_with_existing_workflow_seeds(self):
        workflow = (ROOT / ".github" / "workflows" / "test-rom.yml").read_text()
        loop_starts = (0x07401, 0x12E73, 0x13117, 0x13126, 0x132A1, 0x132AA, 0x134FE,
                       0x1427D, 0x1428F, 0x53C80, 0x1449A, 0x144AB)
        existing = {start + i for start in loop_starts for i in range(4)}
        for line in workflow.splitlines():
            if "seek=$((0x" in line:
                data = line.split("printf '", 1)[1].split("'", 1)[0]
                start = int(line.split("seek=$((", 1)[1].split(")", 1)[0], 16)
                existing.update(range(start, start + data.count("\\x")))
        self.assertGreater(len(existing), 48)
        self.assertFalse(existing & set(self.seed))

    def test_seed_file_writes_only_guard_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = Path(tmp) / "test.sfc"
            base = bytearray(seeder.ROM_SIZE)
            base[0xE9E6:0xE9E9] = b"\x73\x80\x39"
            rom.write_bytes(base)
            self.assertEqual(seeder.seed_file(SOURCE, rom), (41, len(self.seed)))
            data = rom.read_bytes()
        changed = {i for i in range(seeder.ROM_SIZE) if data[i] != base[i]}
        self.assertLessEqual(changed, set(self.seed))
        for offset, byte in self.seed.items():
            self.assertEqual(data[offset], byte)
        self.assertEqual(data[0xE9E6:0xE9E9], b"\x73\x80\x39")

    def test_d6_door_guards_match_native_preimages(self):
        source = ROOT / "Dungeons" / "d6_cart_circuit.asm"
        guards = seeder.parse_guards(source.read_text(), str(source))
        self.assertEqual(len(guards), 5)
        expected = {}
        for address, data in (
            (0x01B0F3, bytes.fromhex("AD8C0639C098")),
            (0x01CF22, bytes.fromhex("AF66F37E39C098D040")),
        ):
            start = seeder.lorom_offset(address)
            expected.update({start + i: value for i, value in enumerate(data)})
        self.assertEqual(seeder.guard_bytes(guards), expected)


class Parsing(unittest.TestCase):
    def test_widths_little_endian_and_offset(self):
        seed = seed_of('assert read4($018000) == $44332211, "a"\n'
                       'assert read2($018004+$2) == $6655, "b"\n'
                       'assert read1($808008) == $77, "c" ; mirror bank\n'
                       'assert read3($018009) == $CCBBAA, "d"\n')
        self.assertEqual(seed, {0x8000: 0x11, 0x8001: 0x22, 0x8002: 0x33, 0x8003: 0x44,
                                0x8006: 0x55, 0x8007: 0x66, 0x0008: 0x77,
                                0x8009: 0xAA, 0x800A: 0xBB, 0x800B: 0xCC})

    def test_comments_and_pc_asserts_are_ignored(self):
        text = ('; assert read1($018000) == $12, "commented"\n'
                'assert pc() <= $2CFD00 ; read1 mentioned in a comment\n'
                'assert read1($018000) == $AB, "x; read2($00) not code"\n')
        self.assertEqual(seed_of(text), {0x8000: 0xAB})

    def test_matching_overlap_is_allowed(self):
        seed = seed_of('assert read2($018000) == $2211, "a"\n'
                       'assert read1($018001) == $22, "b"\n')
        self.assertEqual(seed, {0x8000: 0x11, 0x8001: 0x22})


class ReceiptMacro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RECEIPT_SOURCE.read_text()

    def assertRejects(self, text, fragment):
        with self.assertRaisesRegex(SeedError, fragment):
            seed_of(text)

    def test_all_25_native_preimages_match_existing_receipt_fixture(self):
        # Read the existing fixture's literal metadata without running Asar/CPU tests.
        tree = ast.parse((ROOT / "Tests" / "test_bombchu_receipt.py").read_text())
        readers = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "READERS" for t in node.targets))
        hooks = {site: bytes.fromhex(raw) for site, raw, *_ in readers}
        hooks[0x00D4ED] = bytes.fromhex("8b4bab48")  # same native art hook as the fixture
        self.assertEqual(len(hooks), 25)
        expected = {seeder.lorom_offset(site) + n: byte
                    for site, data in hooks.items() for n, byte in enumerate(data)}
        guards = seeder.parse_guards(self.text)
        self.assertEqual(len(guards), 42)
        self.assertEqual([sum(g[1] == width for g in guards) for width in (1, 2, 3, 4)],
                         [11, 5, 1, 25])
        self.assertEqual(len(expected), 124)
        self.assertEqual(seeder.guard_bytes(guards), expected)
        with tempfile.TemporaryDirectory() as tmp:
            rom = Path(tmp) / "test.sfc"
            base = bytearray(seeder.ROM_SIZE)
            # Goldstar's adjacent operand belongs to the existing workflow seed.
            base[0x4863E:0x48640] = bytes.fromhex("3002")
            rom.write_bytes(base)
            self.assertEqual(seeder.seed_file(RECEIPT_SOURCE, rom), (42, 124))
            wanted = bytearray(base)
            for offset, byte in expected.items():
                wanted[offset] = byte
            self.assertEqual(rom.read_bytes(), wanted)

    def test_receipt_seeds_compose_with_existing_guard_sources(self):
        guards = []
        for path in (SOURCE, ROOT / "Dungeons/d7_farore_rescue.asm",
                     ROOT / "Dungeons/d6_cart_circuit.asm", RECEIPT_SOURCE):
            guards.extend(seeder.parse_guards(path.read_text(), str(path)))
        combined = seeder.guard_bytes(guards)
        self.assertTrue(set(seed_of(self.text)) <= set(combined))

    def test_changed_macro_guards_and_control_flow_are_rejected(self):
        for old, new in (("read4(<site>)", "read3(<site>)"),
                         ("read1(<site>+4)", "read1(<site>+5)"),
                         ("read2(<site>+4) == <tail>", "read2(<site>+4) != <tail>"),
                         ("if <count> == 5", "if <count> == 4"),
                         ("JML <target>", "JSL <target>"),
                         ("NOP #<count>-4", "NOP #<count>-3"),
                         ("assert pc() == <site>+<count>", "assert pc() == <site>+4")):
            with self.subTest(change=new):
                self.assertIn(old, self.text)
                self.assertRejects(self.text.replace(old, new, 1), "macro definition changed")

    def test_literal_arguments_and_native_count_bounds(self):
        call = "%BombchuReceiptHook($07B594, $85B528B9, $03, 5, BombchuReceipt_LoadOverflow, 0)"
        for old, new in (("$07B594", "$07B594+$0"), ("$85B528B9", "$85B528B9|0"),
                         ("$03", "$03+0"), (", 5,", ", 4+1,"),
                         ("BombchuReceipt_LoadOverflow", "BombchuReceipt_LoadOverflow+1"),
                         (", 0)", ", 2)"), (", 5,", ", 3,"), (", 5,", ", 8,")):
            with self.subTest(change=new):
                self.assertRejects(self.text.replace(call, call.replace(old, new), 1),
                                   "literal receipt caller|native count")

    def test_head_and_each_tail_width_refuse_oversized_literals(self):
        for old, new in (("$85B528B9, $03", "$185B528B9, $03"),
                         ("$85B528B9, $03", "$85B528B9, $103"),
                         ("$29836CB9, $00FF", "$29836CB9, $100FF"),
                         ("$02857EA9, $8580B9", "$02857EA9, $18580B9"),
                         ("$0984E8BF, $00, 4", "$0984E8BF, $01, 4")):
            with self.subTest(change=new):
                self.assertRejects(self.text.replace(old, new, 1),
                                   "does not fit|unused receipt tail")

    def test_missing_or_extra_native_caller_is_rejected(self):
        call = "%BombchuReceiptHook($07B594, $85B528B9, $03, 5, BombchuReceipt_LoadOverflow, 0)"
        self.assertRejects(self.text.replace(call, "", 1), "expected 25 receipt callers, found 24")
        extra = "\norg $018000\n" + call.replace("$07B594", "$018000") + "\n"
        self.assertRejects(self.text + extra, "expected 25 receipt callers, found 26")

    def test_org_mismatch_overlapping_hooks_and_direct_conflict_are_rejected(self):
        self.assertRejects(self.text.replace("org $07B594", "org $07B595", 1),
                           "matching literal org")
        for alias in ("$07B594", "$87B594"):
            with self.subTest(alias=alias):
                self.assertRejects(self.text.replace("$07B5A0", alias), "overlapping receipt")
        self.assertRejects(self.text + '\nassert read1($07B594) == $00, "conflict"\n', "conflicts")

    def test_unknown_macros_unparsed_reads_and_missing_definition_are_rejected(self):
        self.assertRejects(self.text.replace("BombchuReceiptHook", "UnknownReceiptHook"),
                           "unsupported read-guard macro")
        self.assertRejects(self.text + '\nmacro Unknown()\nassert read1($018000) == $12, "x"\nendmacro\n',
                           "unsupported read-guard macro")
        self.assertRejects(self.text + '\nassert read1(Label) == $12, "x"\n', "unsupported read guard")
        self.assertRejects(self.text.replace(seeder._RECEIPT_TEMPLATE.strip(), "", 1),
                           "validated macro")


class FailClosed(unittest.TestCase):
    def assertRejects(self, text, fragment):
        with self.assertRaises(SeedError) as caught:
            seed_of(text)
        self.assertIn(fragment, str(caught.exception))

    def test_unparsed_read_uses(self):
        for text in ('assert read1($018000) != $12, "ne"',
                     'assert read1($018000) == $12 && read1($018001) == $34, "and"',
                     'assert read1($018000) == $12',
                     'assert read1($018000)+1 == $13, "math"',
                     'assert read1(Label) == $12, "label"',
                     'if read1($018000) == $12',
                     'db read1($018000)',
                     'org $018000 : assert read1($018000) == $12, "chained"',
                     'assert readfile1("x.bin", 0) == $12, "file"'):
            with self.subTest(text=text):
                self.assertRejects(text, "")

    def test_unsupported_width(self):
        self.assertRejects('assert read5($018000) == $123456, "w"', "unsupported read width")

    def test_value_too_wide(self):
        self.assertRejects('assert read1($018000) == $123, "v"', "does not fit")
        self.assertRejects('assert read2($018000) == $00001234, "v"', "does not fit")
        self.assertRejects('assert read3($018000) == $1000000, "v"', "does not fit")

    def test_or_alternatives_must_share_site(self):
        self.assertRejects('assert read1($018000) == $8F || read1($018001) == $22, "o"',
                           "same width and address")
        self.assertRejects('assert read1($018000) == $8F || read2($018000) == $22, "o"',
                           "same width and address")

    def test_conflicting_overlap(self):
        self.assertRejects('assert read2($018000) == $2211, "a"\n'
                           'assert read1($018001) == $33, "b"\n', "conflicts")

    def test_unmapped_and_out_of_range(self):
        self.assertRejects('assert read1($017FFF) == $12, "low half"', "not a mapped")
        self.assertRejects('assert read1($7E8000) == $12, "wram"', "not a mapped")
        self.assertRejects('assert read1($408000) == $12, "past 2 MiB"', "past")
        self.assertRejects('assert read2($01FFFF) == $1234, "bank cross"', "crosses a bank")
        self.assertRejects('assert read3($01FFFE) == $123456, "bank cross"', "crosses a bank")
        self.assertRejects('assert read1($01FFFF+$1) == $12, "offset wrap"', "not a mapped")


class FileChecks(unittest.TestCase):
    GUARD = 'assert read2($018000) == $2211, "a"\n'

    def run_seed(self, rom_bytes, text=GUARD):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src.asm"
            rom = Path(tmp) / "test.sfc"
            source.write_text(text)
            rom.write_bytes(rom_bytes)
            try:
                return seeder.seed_file(source, rom), None, rom.read_bytes()
            except SeedError as error:
                return None, error, rom.read_bytes()

    def test_wrong_size_is_rejected_unchanged(self):
        result, error, data = self.run_seed(bytes(1024))
        self.assertIn("expected", str(error))
        self.assertEqual(data, bytes(1024))

    def test_conflicting_existing_byte_writes_nothing(self):
        base = bytearray(seeder.ROM_SIZE)
        base[0x8001] = 0x99
        result, error, data = self.run_seed(bytes(base))
        self.assertIn("$08001=$99", str(error))
        self.assertEqual(data, bytes(base))

    def test_equal_existing_byte_is_accepted(self):
        base = bytearray(seeder.ROM_SIZE)
        base[0x8000] = 0x11
        result, error, data = self.run_seed(bytes(base))
        self.assertIsNone(error)
        self.assertEqual(data[0x8000:0x8002], b"\x11\x22")

    def test_source_error_writes_nothing(self):
        base = bytes(seeder.ROM_SIZE)
        result, error, data = self.run_seed(
            base, self.GUARD + 'assert read1($018000) == $12 && 1, "and"\n')
        self.assertIsNotNone(error)
        self.assertEqual(data, base)

    def test_source_without_guards_is_rejected(self):
        result, error, _ = self.run_seed(bytes(seeder.ROM_SIZE), "nop\n")
        self.assertIn("no read guards", str(error))

    def test_receipt_tail_error_writes_nothing(self):
        base = bytes(seeder.ROM_SIZE)
        text = RECEIPT_SOURCE.read_text().replace("$02857EA9, $8580B9", "$02857EA9, $18580B9", 1)
        result, error, data = self.run_seed(base, text)
        self.assertIn("does not fit read3", str(error))
        self.assertEqual(data, base)

    def test_cli_reports_error_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src.asm"
            rom = Path(tmp) / "test.sfc"
            source.write_text(self.GUARD)
            rom.write_bytes(bytes(10))
            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(seeder.main([str(source), str(rom)]), 1)
            self.assertIn("::error::Sky preimage seed:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
