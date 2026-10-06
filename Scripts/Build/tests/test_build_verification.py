"""Focused checks for build gates that previously returned misleading results."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


overlap = load_module("check_zscream_overlap", ROOT / "Scripts/Build/check_zscream_overlap.py")
hooks = load_module("verify_hooks_json", ROOT / "Scripts/Validate/verify_hooks_json.py")


class OverlapCheckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fixture.sym"
        self.ranges = [{"start": 0x128000, "end": 0x12FFFF, "name": "collision"}]

    def symbols(self, address="25:9000", source="Dungeons/accidental.asm", labels=""):
        self.path.write_text(
            f"[labels]\n{labels}\n[source files]\n0000 01234567 {source}\n"
            f"[addr-to-line mapping]\n{address} 0000:00000010\n"
        )
        return self.path

    def test_lorom_mapping_and_fastrom_mirror(self):
        self.assertEqual(overlap.snes_to_pc(0x259000), 0x129000)
        self.assertEqual(overlap.snes_to_pc(0xA59000), 0x129000)
        self.assertEqual(overlap.snes_to_pc(0x3FFFFF), 0x1FFFFF)
        self.assertEqual(overlap.snes_to_pc(0x400000), 0x200000)
        self.assertIsNone(overlap.snes_to_pc(0x7E9000))
        self.assertIsNone(overlap.snes_to_pc(0x002100))
        self.assertIsNone(overlap.snes_to_pc(0x700000))

    def test_unlabeled_emission_is_rejected(self):
        hits = overlap.check_overlaps(self.symbols(), self.ranges)
        self.assertEqual(hits[0]["pc"], "0x129000")
        self.assertEqual(hits[0]["source"], "Dungeons/accidental.asm:16")
        self.assertEqual(hits[0]["label"], "<unlabeled emission>")

    def test_fastrom_emission_is_rejected(self):
        hits = overlap.check_overlaps(self.symbols("A5:9000"), self.ranges)
        self.assertEqual(hits[0]["pc"], "0x129000")

    def test_constant_alias_is_not_a_write(self):
        path = self.symbols("2C:9000", labels="25:9000 ExistingCollisionData")
        self.assertEqual(overlap.check_overlaps(path, self.ranges), [])

    def test_generated_source_owned_region_is_allowed(self):
        path = self.symbols("25:E000", "Dungeons/generated/water_fill_table.asm")
        self.assertEqual(overlap.check_overlaps(path, self.ranges), [])

    def test_absolute_repository_source_is_normalized_for_ownership(self):
        source = (ROOT / "Dungeons/generated/water_fill_table.asm").as_posix()
        path = self.symbols("25:E000", source)
        self.assertEqual(overlap.check_overlaps(path, self.ranges), [])

    def test_other_source_at_owned_address_is_rejected(self):
        self.assertEqual(len(overlap.check_overlaps(self.symbols("25:E000"), self.ranges)), 1)

    def test_owned_source_outside_its_allocation_is_rejected(self):
        path = self.symbols("25:DFFF", "Dungeons/generated/water_fill_table.asm")
        self.assertEqual(len(overlap.check_overlaps(path, self.ranges)), 1)

    def test_all_declared_ownership_requires_source_and_bounds(self):
        for source, start, end in overlap.OWNED_REGIONS:
            with self.subTest(source=source, end=end):
                ranges = [{"start": start, "end": end, "name": "reserved"}]
                for pc in (start, end):
                    snes = ((pc >> 15) << 16) | (pc & 0x7FFF) | 0x8000
                    address = f"{snes >> 16:02X}:{snes & 0xFFFF:04X}"
                    self.assertEqual(overlap.check_overlaps(self.symbols(address, source), ranges), [])
                    self.assertEqual(len(overlap.check_overlaps(self.symbols(address), ranges)), 1)

    def test_missing_symbols_fail(self):
        with self.assertRaises(FileNotFoundError):
            overlap.check_overlaps(self.path, self.ranges)

    def test_incomplete_or_malformed_symbols_fail(self):
        for content in ("", "[labels]\n25:E000 Label\n", "[source files]\nbad\n"):
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(ValueError):
                    overlap.check_overlaps(self.path, self.ranges)

    def test_unknown_source_id_fails(self):
        self.symbols()
        self.path.write_text(self.path.read_text().replace("0000:00000010", "0001:00000010"))
        with self.assertRaisesRegex(ValueError, "Unknown source id"):
            overlap.check_overlaps(self.path, self.ranges)

    def test_map_parses_plural_and_crlf(self):
        path = Path(self.temp.name) / "map.txt"
        path.write_bytes(b"0x1F0000 - 0x1FFFFF: 2 Banks\r\n    Tile32\r\n")
        self.assertEqual(overlap.parse_zs_map(path), [
            {"start": 0x1F0000, "end": 0x1FFFFF, "name": "Tile32"}])

    def test_cli_missing_symbols_returns_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "Scripts/Build/check_zscream_overlap.py"),
             "--symbols", str(self.path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error:", result.stdout)
        self.assertNotIn("[+]", result.stdout)


class HookGeneratorPathTest(unittest.TestCase):
    def test_dispatches_to_relocated_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generator = root / "Scripts/Generate/generate_hooks_json.py"
            generator.parent.mkdir(parents=True)
            generator.write_text(
                "import pathlib, sys\n"
                "pathlib.Path(sys.argv[sys.argv.index('--output') + 1]).write_text('generated')\n")
            output = root / "hooks.json"
            hooks._run_generator(root, root / "rom.sfc", output)
            self.assertEqual(output.read_text(), "generated")


class BuildOverlapDispatchTest(unittest.TestCase):
    def dispatch(self, emit_symbols: int):
        # Execute the real call-site block with a recording checker substitute;
        # no assembler, ROM writes, symbol exports, or emulator are involved.
        source = (ROOT / "Scripts/Build/build_rom.sh").read_text()
        block = source.split("# Run ZScream overlap check\n", 1)[1].split(
            "# Generate annotations.json", 1)[0]
        script = (
            'set -euo pipefail\n'
            'repo_root="/fixture repo"\n'
            'symbols_path="/fixture repo/Roms/oos999x.sym"\n'
            f'emit_symbols={emit_symbols}\n'
            'python3() { printf "ARG:%s\\n" "$@"; }\n'
            + block
        )
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    def test_build_passes_exact_version_specific_symbols(self):
        result = self.dispatch(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "ARG:/fixture repo/Scripts/Build/check_zscream_overlap.py",
            "ARG:--symbols",
            "ARG:/fixture repo/Roms/oos999x.sym",
        ])

    def test_no_symbols_skips_checker_explicitly(self):
        result = self.dispatch(0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("ARG:", result.stdout)
        self.assertIn("Skipping ZScream overlap check: --no-symbols requested", result.stdout)


if __name__ == "__main__":
    unittest.main()
