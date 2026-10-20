"""Checks for seed_sky_award_preimages.py: python3 .github/scripts/test_seed_sky_award_preimages.py"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True  # importing the contract test must not add Tests/__pycache__
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "Dungeons" / "sky_d8_award.asm"
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


class Parsing(unittest.TestCase):
    def test_widths_little_endian_and_offset(self):
        seed = seed_of('assert read4($018000) == $44332211, "a"\n'
                       'assert read2($018004+$2) == $6655, "b"\n'
                       'assert read1($808008) == $77, "c" ; mirror bank\n')
        self.assertEqual(seed, {0x8000: 0x11, 0x8001: 0x22, 0x8002: 0x33, 0x8003: 0x44,
                                0x8006: 0x55, 0x8007: 0x66, 0x0008: 0x77})

    def test_comments_and_pc_asserts_are_ignored(self):
        text = ('; assert read1($018000) == $12, "commented"\n'
                'assert pc() <= $2CFD00 ; read1 mentioned in a comment\n'
                'assert read1($018000) == $AB, "x; read2($00) not code"\n')
        self.assertEqual(seed_of(text), {0x8000: 0xAB})

    def test_matching_overlap_is_allowed(self):
        seed = seed_of('assert read2($018000) == $2211, "a"\n'
                       'assert read1($018001) == $22, "b"\n')
        self.assertEqual(seed, {0x8000: 0x11, 0x8001: 0x22})


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
        self.assertRejects('assert read3($018000) == $123456, "w"', "unsupported read width")

    def test_value_too_wide(self):
        self.assertRejects('assert read1($018000) == $123, "v"', "does not fit")
        self.assertRejects('assert read2($018000) == $00001234, "v"', "does not fit")

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

    def test_cli_reports_error_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src.asm"
            rom = Path(tmp) / "test.sfc"
            source.write_text(self.GUARD)
            rom.write_bytes(bytes(10))
            self.assertEqual(seeder.main([str(source), str(rom)]), 1)


if __name__ == "__main__":
    unittest.main()
