"""Source contract for the Eon Owl Hall of Secrets crystal gate.

Executes the area $0E branch of Sprite_EonOwl_Long in Sprites/NPCs/eon_owl.asm
on an 8-bit model of the instructions it uses, for all 256 Crystals values and
all 256 Flute values. The D8 Sky bit ($80) must not change the outcome. No
build, no emulator.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EON_OWL = ROOT / "Sprites" / "NPCs" / "eon_owl.asm"
SRAM = ROOT / "Core" / "sram.asm"
CRYSTALS, FLUTE, AREA = 0x7EF37A, 0x7EF34C, 0x8A
FLAG_Z, FLAG_C = 0x02, 0x01


def gaebora_branch(text):
    match = re.search(r"^Sprite_EonOwl_Long:\s*\n\{\n(.*?)^\}", text, re.M | re.S)
    if not match:
        raise AssertionError("Sprite_EonOwl_Long not found")
    instructions = []
    for raw in match.group(1).splitlines():
        code = raw.split(";", 1)[0].strip()
        instructions.extend(part.strip() for part in code.split(" : ") if part.strip())
    start = instructions.index("LDA.b $8A")
    end = instructions.index(".NotGaebora")
    return instructions[start:end]


def sram_define(text, pattern):
    match = re.search(pattern, text, re.M)
    if not match:
        raise AssertionError(f"{pattern} not found in sram.asm")
    return int(match.group(1), 16)


def run_branch(lines, area, crystals, flute):
    memory = {AREA: area, CRYSTALS: crystals, FLUTE: flute}
    a, p, pc = 0, 0, 0
    while pc < len(lines):
        op, arg = lines[pc].split(None, 1)
        pc += 1
        if op in ("BNE", "BCS"):
            taken = not (p & FLAG_Z) if op == "BNE" else bool(p & FLAG_C)
            if taken:
                return arg
        elif op == "JMP":
            return arg
        elif op in ("LDA.b", "LDA.l") and arg.startswith("$"):
            a = memory[int(arg[1:], 16)]
        elif op == "LDA.b" and arg.startswith("#$"):
            a = int(arg[2:], 16)
        elif op == "AND.b":
            a &= int(re.fullmatch(r"#\$([0-9A-F]{2})", arg).group(1), 16)
        elif op == "CMP.b":
            operand = int(re.fullmatch(r"#\$([0-9A-F]{2})", arg).group(1), 16)
            p = (FLAG_C if a >= operand else 0) | (FLAG_Z if a == operand else 0)
        elif op in ("STA.w", "JSR"):
            continue
        else:
            raise AssertionError(f"opcode {op} not modeled")
    raise AssertionError("branch fell through without an outcome")


def legacy_retains(crystals, flute):
    return (crystals & 0x7F) == 0x77 and flute < 0x04


class EonOwlCrystalCompat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = gaebora_branch(EON_OWL.read_text(encoding="utf-8"))
        cls.sram = SRAM.read_text(encoding="utf-8")

    def test_source_flow_and_mask(self):
        crystals = sram_define(self.sram, r"^Crystals\s*=\s*\$([0-9A-F]{6})")
        flute = sram_define(self.sram, r"^Flute\s*=\s*\$([0-9A-F]{6})")
        sky = sram_define(self.sram, r"^!Crystal_D8_Sky\s*=\s*\$([0-9A-F]{2})")
        self.assertEqual((crystals, flute, sky), (CRYSTALS, FLUTE, 0x80))
        self.assertEqual(self.lines[:9], [
            "LDA.b $8A", "CMP.b #$0E", "BNE .NotGaebora",
            "LDA.l $7EF37A", f"AND.b #${~sky & 0xFF:02X}", "CMP.b #$77", "BNE .Despawn",
            "LDA.l $7EF34C", "CMP.b #$04",
        ])
        self.assertEqual(self.lines[9], "BCS .Despawn")
        self.assertEqual(self.lines[-1], "JMP .HandleSprite")
        self.assertEqual(sum(line.startswith("AND.b") for line in self.lines), 1)
        for area in range(256):
            if area != 0x0E:
                self.assertEqual(run_branch(self.lines, area, 0x77, 0), ".NotGaebora")

    def test_all_crystal_and_flute_bytes_match_legacy(self):
        cases = 0
        for crystals in range(256):
            for flute in range(256):
                outcome = run_branch(self.lines, 0x0E, crystals, flute)
                expected = ".HandleSprite" if legacy_retains(crystals, flute) else ".Despawn"
                self.assertEqual(outcome, expected, f"crystals=${crystals:02X} flute=${flute:02X}")
                cases += 1
        self.assertEqual(cases, 65536)

    def test_sky_bit_invariance_and_boundaries(self):
        for crystals in range(128):
            for flute in range(256):
                self.assertEqual(
                    run_branch(self.lines, 0x0E, crystals, flute),
                    run_branch(self.lines, 0x0E, crystals | 0x80, flute),
                    f"crystals=${crystals:02X} flute=${flute:02X}")
        for crystals in (0x77, 0xF7):
            for flute in range(4):
                self.assertEqual(run_branch(self.lines, 0x0E, crystals, flute), ".HandleSprite")
            for flute in range(4, 256):
                self.assertEqual(run_branch(self.lines, 0x0E, crystals, flute), ".Despawn")
        for crystals in (0x7F, 0xFF, 0x80, 0x00, 0x37, 0xB7):
            for flute in range(256):
                self.assertEqual(run_branch(self.lines, 0x0E, crystals, flute), ".Despawn")


if __name__ == "__main__":
    unittest.main()
