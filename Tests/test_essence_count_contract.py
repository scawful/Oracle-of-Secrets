"""Source contract and exhaustive model for the eight-essence counter.

Executes the assembly text of GetCrystalCount and GetEssenceCount in
Core/progression.asm on a width-aware model of the 65816 subset they use,
for all 256 Crystals values and every entry M/X width. No build, no emulator.
"""
from pathlib import Path
import random
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROGRESSION = ROOT / "Core" / "progression.asm"
SRAM = ROOT / "Core" / "sram.asm"
CRYSTALS = 0x7EF37A
FLAG_M, FLAG_X, FLAG_N, FLAG_Z, FLAG_C = 0x20, 0x10, 0x80, 0x02, 0x01


def routine_lines(text, name):
    match = re.search(rf"^{name}:\s*\n\{{\n(.*?)^\}}", text, re.M | re.S)
    if not match:
        raise AssertionError(f"{name} not found")
    lines = []
    for raw in match.group(1).splitlines():
        line = raw.split(";", 1)[0].strip()
        if line:
            lines.append(line)
    return lines


class Cpu:
    def __init__(self, p, a, x, y, crystals):
        self.p, self.a, self.x, self.y = p, a, x, y
        self.sp, self.stack = 0x1FF0, {}
        self.memory = {CRYSTALS: crystals, CRYSTALS + 1: 0xA5}

    def flag(self, bit):
        return bool(self.p & bit)

    def set_p(self, value):
        self.p = value & 0xFF
        if self.flag(FLAG_X):
            self.x &= 0xFF
            self.y &= 0xFF

    def nz(self, value, wide):
        mask = 0xFFFF if wide else 0xFF
        value &= mask
        self.p &= ~(FLAG_N | FLAG_Z) & 0xFF
        if value == 0:
            self.p |= FLAG_Z
        if value & (0x8000 if wide else 0x80):
            self.p |= FLAG_N

    def push(self, value, size):
        for shift in ((8, 0) if size == 2 else (0,)):
            self.stack[self.sp] = (value >> shift) & 0xFF
            self.sp -= 1

    def pull(self, size):
        value = 0
        for shift in ((0, 8) if size == 2 else (0,)):
            self.sp += 1
            value |= self.stack.pop(self.sp) << shift
        return value

    def set_a(self, value):
        if self.flag(FLAG_M):
            self.a = (self.a & 0xFF00) | (value & 0xFF)
        else:
            self.a = value & 0xFFFF

    def immediate(self, operand, wide):
        digits = re.fullmatch(r"#\$([0-9A-Fa-f]+)", operand).group(1)
        if len(digits) != (4 if wide else 2):
            raise AssertionError(f"immediate {operand} does not match register width")
        return int(digits, 16)

    def run(self, lines):
        labels = {line: i for i, line in enumerate(lines) if line.startswith(".")}
        pc, steps = 0, 0
        while True:
            steps += 1
            if steps > 500:
                raise AssertionError("routine did not terminate")
            parts = lines[pc].split(None, 1)
            op, arg = parts[0], parts[1] if len(parts) > 1 else ""
            pc += 1
            wide_a, wide_x = not self.flag(FLAG_M), not self.flag(FLAG_X)
            if op.startswith("."):
                continue
            if op == "PHP":
                self.push(self.p, 1)
            elif op == "PLP":
                self.set_p(self.pull(1))
            elif op == "REP":
                self.set_p(self.p & ~self.immediate(arg, False))
            elif op == "SEP":
                self.set_p(self.p | self.immediate(arg, False))
            elif op in ("PHX", "PHY"):
                self.push(self.x if op == "PHX" else self.y, 2 if wide_x else 1)
            elif op in ("PLX", "PLY"):
                value = self.pull(2 if wide_x else 1)
                self.nz(value, wide_x)
                if op == "PLX":
                    self.x = value
                else:
                    self.y = value
            elif op == "LDA.l":
                if arg != "Crystals":
                    raise AssertionError(f"unexpected load {arg}")
                value = self.memory[CRYSTALS]
                if wide_a:
                    value |= self.memory[CRYSTALS + 1] << 8
                self.set_a(value)
                self.nz(value, wide_a)
            elif op == "LDX":
                self.x = self.immediate(arg, wide_x)
                self.nz(self.x, wide_x)
            elif op == "AND":
                value = self.a & self.immediate(arg, wide_a)
                self.set_a(value)
                self.nz(value, wide_a)
            elif op == "CMP":
                value = self.a & (0xFFFF if wide_a else 0xFF)
                operand = self.immediate(arg, wide_a)
                self.p = (self.p | FLAG_C) if value >= operand else (self.p & ~FLAG_C)
                self.nz(value - operand, wide_a)
            elif op == "LSR":
                value = self.a & (0xFFFF if wide_a else 0xFF)
                self.p = (self.p | FLAG_C) if value & 1 else (self.p & ~FLAG_C)
                self.set_a(value >> 1)
                self.nz(value >> 1, wide_a)
            elif op == "INX":
                self.x = (self.x + 1) & (0xFFFF if wide_x else 0xFF)
                self.nz(self.x, wide_x)
            elif op == "TXA":
                self.set_a(self.x)
                self.nz(self.x, wide_a)
            elif op in ("BCC", "BNE"):
                taken = not self.flag(FLAG_C if op == "BCC" else FLAG_Z)
                if taken:
                    pc = labels[arg]
            elif op == "RTL":
                return
            else:
                raise AssertionError(f"opcode {op} not modeled")


def entry_states():
    rng = random.Random(0x7EF37A)
    for m in (0, FLAG_M):
        for x in (0, FLAG_X):
            for low in (0, FLAG_N | FLAG_C, FLAG_Z):
                p = m | x | low
                a, xr, yr = (rng.randrange(0x10000) for _ in range(3))
                if x:
                    xr, yr = xr & 0xFF, yr & 0xFF
                yield p, a, xr, yr


class EssenceCountContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.progression = PROGRESSION.read_text(encoding="utf-8")
        cls.sram = SRAM.read_text(encoding="utf-8")

    def crystal_bits(self):
        return {name: int(value, 16) for name, value in re.findall(
            r"^!Crystal_(D\d_\w+)\s*=\s*\$([0-9A-Fa-f]{2})", self.sram, re.M)}

    def test_eight_distinct_essence_bits(self):
        bits = self.crystal_bits()
        self.assertEqual(len(bits), 8)
        self.assertEqual(sorted(name[:2] for name in bits), [f"D{n}" for n in range(1, 9)])
        self.assertEqual(bits["D8_Sky"], 0x80)
        for value in bits.values():
            self.assertEqual(bin(value).count("1"), 1)
        legacy = 0
        for name, value in bits.items():
            if name != "D8_Sky":
                legacy |= value
        self.assertEqual(legacy, 0x7F)
        self.assertEqual(legacy | bits["D8_Sky"], 0xFF)

    def run_routine(self, name, check):
        lines = routine_lines(self.progression, name)
        for crystals in range(256):
            for p, a, x, y in entry_states():
                cpu = Cpu(p, a, x, y, crystals)
                cpu.run(lines)
                label = f"{name} crystals=${crystals:02X} P=${p:02X}"
                self.assertEqual(cpu.sp, 0x1FF0, label)
                self.assertEqual(cpu.stack, {}, label)
                self.assertEqual(cpu.p, p, label)
                check(cpu, crystals, x, y, label)

    def test_get_essence_count_all_256_values(self):
        def check(cpu, crystals, x, y, label):
            self.assertEqual(cpu.a, bin(crystals).count("1"), label)
            self.assertEqual((cpu.x, cpu.y), (x, y), label)
        self.run_routine("GetEssenceCount", check)

    def test_get_crystal_count_stays_seven_bit(self):
        def check(cpu, crystals, x, y, label):
            self.assertEqual(cpu.a, bin(crystals & 0x7F).count("1"), label)
            self.assertEqual(cpu.x & 0xFF, x & 0xFF, label)
            self.assertEqual(cpu.y & 0xFF, y & 0xFF, label)
        self.run_routine("GetCrystalCount", check)
        self.assertIn("AND #$7F", routine_lines(self.progression, "GetCrystalCount"))

    def test_legacy_helpers_keep_addresses_and_count(self):
        order = [self.progression.index(f"\n{name}:\n") for name in (
            "GetCrystalCount", "UpdateMapIcon", "SelectReactionMessage", "GetEssenceCount")]
        self.assertEqual(order, sorted(order))
        for name in ("UpdateMapIcon", "SelectReactionMessage"):
            body = routine_lines(self.progression, name)
            self.assertIn("JSL GetCrystalCount", body)
            self.assertNotIn("JSL GetEssenceCount", body)

    def test_no_consumer_calls_get_essence_count(self):
        callers = []
        for path in ROOT.rglob("*.asm"):
            if path == PROGRESSION or ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            code = "\n".join(line.split(";", 1)[0] for line in text.splitlines())
            if re.search(r"\bGetEssenceCount\b", code):
                callers.append(str(path.relative_to(ROOT)))
        self.assertEqual(callers, [])


if __name__ == "__main__":
    unittest.main()
