"""Compare the ferry producer's wire layout with existing native cache fixtures.

Source/data checks only. No assembler, ROM write, CPU or native behavior claim.
"""
from pathlib import Path
import re
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLACEMENTS = ROOT / "Data/overworld/kalyxo_boat_placements.asm"


def words_after(path, label):
    lines = path.read_text().split(label + ":", 1)[1].splitlines()
    words = []
    for line in lines:
        code = line.split(";", 1)[0].strip()
        if code.startswith("assert "):
            break
        if code.startswith("dw "):
            words.extend(int(v.strip()[1:], 16) for v in code[3:].split(","))
    return words


def emit_fixture(native_words):
    """Expand actual dw operands, with arguments from an existing native record."""
    source = PLACEMENTS.read_text()
    args, body = re.search(r"macro BoatNativeCache\(([^)]+)\)(.*?)endmacro", source, re.S).groups()
    # Native engine fields: area0, scroll4/6, position8/A, repeated areaC,
    # originE, triggers10/12, bounds14..22, graphics24/26, reserved/modifiers28..30.
    indexes = [0, 2, 3, 4, 5, 7, 8, 9, *range(10, 20)]
    values = dict(zip((a.strip() for a in args.split(",")), (native_words[i] for i in indexes)))
    actual = []
    for line in body.splitlines():
        if line.strip().startswith("dw "):
            for operand in line.strip()[3:].split(","):
                operand = operand.strip()
                actual.append(values[operand[1:-1]] if operand.startswith("<") else int(operand[1:], 16))
    return struct.pack("<" + "H" * len(actual), *actual)


class FerryNativeCacheContract(unittest.TestCase):
    def test_goron_native_cache_wire_equivalence(self):
        words = words_after(ROOT / "Overworld/goron_checkpoint.asm", "GoronCheckpoint_Cache")
        self.assertEqual(len(words), 25)
        self.assertEqual(emit_fixture(words), struct.pack("<25H", *words))

    def test_existing_special_soaring_cache_wire_equivalence(self):
        words = words_after(ROOT / "Items/special_soaring.asm", "SpecialSoaring_Caches")
        self.assertEqual(len(words), 50)
        for start in (0, 25):
            with self.subTest(area=words[start]):
                self.assertEqual(emit_fixture(words[start:start + 25]), struct.pack("<25H", *words[start:start + 25]))

    def test_no_current_geography_is_silently_bound(self):
        source = PLACEMENTS.read_text()
        self.assertRegex(source, r"(?m)^!KALYXO_BOAT_ENDPOINTS_BOUND = 0$")
        calls = re.findall(r"^  %BoatNativeCache\(([^)]+)\)", source, re.M)
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual([v.strip() for v in call.split(",")], ["$FFFF"] * 18)
        for name in ("DocksFacing", "IslandFacing", "DocksOpenTile", "IslandOpenTile", "DocksWaterTile", "IslandWaterTile"):
            self.assertRegex(source, rf"(?m)^!Boat_{name} = \$FFFF$")


if __name__ == "__main__":
    unittest.main()
