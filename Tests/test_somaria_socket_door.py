"""Source-model controls for the latent RoomTag_SomariaSocketDoor routine.

A minimal 65816-subset interpreter executes the routine text from
Dungeons/custom_tag.asm against a WRAM model. It checks the source contract
only; it is not CPU or native emulator proof, and the routine is not hooked.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Dungeons" / "custom_tag.asm"
ROUTINE = "RoomTag_SomariaSocketDoor"
RETURN_ADDRESS = 0x01CC5A

M_FLAG = 0x20
X_FLAG = 0x10

QUALIFYING_SLOT = {0x0C4A: 0x2C, 0x0394: 0x00, 0x03C5: 0x00, 0x0380: 0x00,
                   0x03DB: 0x04, 0x029E: 0x00}
DOOR_WRITES = {0x0468, 0x0469, 0x068E, 0x068F, 0x0690, 0x0691, 0x0011}
ALLOWED_OPERANDS = {0x001B, 0x0646, 0x0308, 0x03F4, 0x0C4A, 0x0394, 0x03C5,
                    0x0380, 0x03DB, 0x029E, 0x0468, 0x068E, 0x0690, 0x012F, 0x0011}
ALLOCATION_START = 0x2CFD00
ALLOCATION_END = 0x2CFE00
LEGACY_HOOK_ORGS = ["org $01CC18 : JML CustomTag",
                    "org $01CC10 : JML RoomTag_MinishShutterDoor",
                    "org $01CC04 : JML RoomTag_MinishSwitch"]


def code_lines(text):
    return [line.split(";", 1)[0].strip() for line in text.splitlines()]


def assembled_size(program):
    size = 0
    for mnemonic, suffix, operand in program:
        if mnemonic in ("SEP", "REP"):
            size += 2
        elif mnemonic == "DEX":
            size += 1
        elif mnemonic in ("BEQ", "BNE", "BMI", "BPL", "BRA"):
            size += 2
        elif mnemonic == "JML":
            size += 4
        else:
            size += 1 + {"b": 1, "w": 2}[suffix]
    return size


def routine_lines():
    lines = SOURCE.read_text().splitlines()
    start = lines.index(f"{ROUTINE}:")
    body = []
    for line in lines[start + 1:]:
        if line == "}":
            return body
        code = line.split(";", 1)[0].strip()
        if code in ("", "{"):
            continue
        body.extend(part.strip() for part in code.split(" : "))
    raise AssertionError("routine block is not closed")


def parse(lines):
    program, labels = [], {}
    for text in lines:
        if re.fullmatch(r"\.\w+", text):
            labels[text] = len(program)
            continue
        match = re.fullmatch(r"([A-Z]{3})(?:\.([bwl]))?(?:\s+(.*))?", text)
        if not match:
            raise AssertionError(f"unparsed line: {text!r}")
        program.append((match.group(1), match.group(2), (match.group(3) or "").strip()))
    return program, labels


def address_operands(program):
    found = set()
    for _, _, operand in program:
        match = re.fullmatch(r"\$([0-9A-F]+)(?:,\s*X)?", operand)
        if match:
            found.add(int(match.group(1), 16))
    return found


class Machine:
    def __init__(self, memory, p=M_FLAG | X_FLAG, a=0xBEEF, x=0x0006, y=0x1234):
        self.memory = dict(memory)
        self.p, self.a, self.x, self.y, self.sp = p, a, x, y, 0x01FB
        self.n = self.z = self.c = self.v = False
        self.reads, self.writes = [], {}
        self._normalize_index()

    def _normalize_index(self):
        if self.p & X_FLAG:
            self.x &= 0xFF
            self.y &= 0xFF

    def read(self, address, wide):
        self.reads.append(address)
        value = self.memory.get(address, 0)
        if wide:
            self.reads.append(address + 1)
            value |= self.memory.get(address + 1, 0) << 8
        return value

    def write(self, address, value, wide):
        for offset in range(2 if wide else 1):
            byte = (value >> (8 * offset)) & 0xFF
            self.memory[address + offset] = byte
            self.writes[address + offset] = byte

    def flags_nz(self, value, wide):
        self.z = value == 0
        self.n = bool(value & (0x8000 if wide else 0x80))

    def m16(self):
        return not self.p & M_FLAG

    def x16(self):
        return not self.p & X_FLAG

    def check_immediate(self, suffix, operand, wide):
        digits = len(operand) - 2
        size = {"b": 1, "w": 2}.get(suffix, 1 if digits <= 2 else 2)
        if size != (2 if wide else 1):
            raise AssertionError(f"immediate {operand} assembles {size} byte(s) "
                                 f"but runtime width is {2 if wide else 1}")
        return int(operand[2:], 16)

    def effective(self, operand):
        match = re.fullmatch(r"\$([0-9A-F]+)(,\s*X)?", operand)
        if not match:
            raise AssertionError(f"unsupported operand {operand!r}")
        address = int(match.group(1), 16)
        if match.group(2):
            address += self.x
        return address

    def load(self, suffix, operand, wide):
        if operand.startswith("#"):
            return self.check_immediate(suffix, operand, wide)
        return self.read(self.effective(operand), wide)

    def compare(self, register, value, wide):
        mask = 0xFFFF if wide else 0xFF
        result = (register - value) & mask
        self.c = (register & mask) >= value
        self.flags_nz(result, wide)

    def run(self, program, labels, limit=500):
        pc = 0
        for _ in range(limit):
            mnemonic, suffix, operand = program[pc]
            pc += 1
            if mnemonic == "SEP":
                self.p |= int(operand[2:], 16)
                self._normalize_index()
            elif mnemonic == "REP":
                self.p &= ~int(operand[2:], 16)
            elif mnemonic == "LDA":
                value = self.load(suffix, operand, self.m16())
                self.a = value if self.m16() else (self.a & 0xFF00) | value
                self.flags_nz(value, self.m16())
            elif mnemonic == "LDX":
                self.x = self.load(suffix, operand, self.x16())
                self.flags_nz(self.x, self.x16())
            elif mnemonic == "CMP":
                accumulator = self.a if self.m16() else self.a & 0xFF
                self.compare(accumulator, self.load(suffix, operand, self.m16()), self.m16())
            elif mnemonic == "CPX":
                self.compare(self.x, self.load(suffix, operand, self.x16()), self.x16())
            elif mnemonic == "BIT":
                wide = self.m16()
                value = self.read(self.effective(operand), wide)
                top = 0x8000 if wide else 0x80
                self.n, self.v = bool(value & top), bool(value & (top >> 1))
                self.z = (self.a & (0xFFFF if wide else 0xFF) & value) == 0
            elif mnemonic == "DEX":
                self.x = (self.x - 1) & (0xFFFF if self.x16() else 0xFF)
                self.flags_nz(self.x, self.x16())
            elif mnemonic == "STA":
                self.write(self.effective(operand), self.a, self.m16())
            elif mnemonic == "STX":
                self.write(self.effective(operand), self.x, self.x16())
            elif mnemonic == "STZ":
                self.write(self.effective(operand), 0, self.m16())
            elif mnemonic in ("BEQ", "BNE", "BMI", "BPL", "BRA"):
                taken = {"BEQ": self.z, "BNE": not self.z, "BMI": self.n,
                         "BPL": not self.n, "BRA": True}[mnemonic]
                if taken:
                    pc = labels[operand]
            elif mnemonic == "JML":
                return operand
            else:
                raise AssertionError(f"mnemonic {mnemonic} is outside the modeled contract")
        raise AssertionError("step limit reached")


def room(door=0x0001, extra=None):
    memory = {0x001B: 0x01, 0x0646: 0x00, 0x0308: 0x00, 0x03F4: 0x00,
              0x0468: door & 0xFF, 0x0469: door >> 8, 0x000E: 0x01,
              0x00AE: 0x24, 0x00AF: 0x16, 0x068E: 0x34, 0x068F: 0x12,
              0x0690: 0x78, 0x0691: 0x56, 0x0011: 0x00, 0x012F: 0x00}
    memory.update(extra or {})
    return memory


def with_block(memory, slot=0, **slot_overrides):
    fields = dict(QUALIFYING_SLOT)
    fields.update({int(key[1:], 16): value for key, value in slot_overrides.items()})
    for base, value in fields.items():
        memory[base + slot] = value
    memory[0x0646] = 0x01
    return memory


class SomariaSocketDoorModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = routine_lines()
        cls.program, cls.labels = parse(cls.lines)

    def execute(self, memory, **registers):
        machine = Machine(memory, **registers)
        target = machine.run(self.program, self.labels)
        self.assertEqual(target, "RoomTag_Return")
        self.assertEqual(machine.p & (M_FLAG | X_FLAG), M_FLAG | X_FLAG)
        self.assertEqual(machine.sp, 0x01FB)
        return machine

    def assert_opened(self, machine):
        self.assertEqual(machine.writes, {0x0468: 0, 0x0469: 0, 0x068E: 0, 0x068F: 0,
                                          0x0690: 0, 0x0691: 0, 0x012F: 0x25, 0x0011: 0x05})

    def assert_closed_now(self, machine):
        self.assertEqual(machine.writes, {0x0468: 1, 0x0469: 0, 0x068E: 0, 0x068F: 0,
                                          0x0690: 0, 0x0691: 0, 0x0011: 0x05})

    def test_return_constant_and_latent_wiring(self):
        text = SOURCE.read_text()
        self.assertRegex(text, r"(?m)^RoomTag_Return = \$01CC5A$")
        self.assertEqual(RETURN_ADDRESS, 0x01CC5A)
        users = []
        for path in ROOT.rglob("*.asm"):
            for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if ROUTINE in line.split(";", 1)[0]:
                    users.append((path.relative_to(ROOT).as_posix(), number, line.strip()))
        self.assertEqual([(path, line) for path, _, line in users],
                         [("Dungeons/custom_tag.asm", f"{ROUTINE}:")])
        for path in ROOT.rglob("hooks.json"):
            self.assertNotIn(ROUTINE, path.read_text(errors="replace"))

    def test_fixed_tail_allocation_is_not_a_hook(self):
        lines = code_lines(SOURCE.read_text())
        label = lines.index(f"{ROUTINE}:")
        self.assertEqual(lines[label - 2:label], ["pushpc", f"org ${ALLOCATION_START:06X}"])
        orgs = [line for line in lines if line.startswith("org ")]
        self.assertEqual(orgs, LEGACY_HOOK_ORGS + [f"org ${ALLOCATION_START:06X}"])
        self.assertEqual(ALLOCATION_START >> 16, 0x2C)
        collision = (ROOT / "Dungeons" / "Collision" / "custom_collision.asm").read_text()
        guard = (ROOT / "Core" / "patches.asm").read_text()
        self.assertIn(f"org ${ALLOCATION_END:06X}", code_lines(collision))
        self.assertIn("org $2CFF00", code_lines(guard))

    def test_pc_stack_balance_and_end_bound(self):
        lines = [line for line in code_lines(SOURCE.read_text()) if line]
        directives = [line for line in lines if line in ("pushpc", "pullpc")]
        self.assertEqual(directives, ["pullpc", "pushpc", "pullpc", "pushpc"])
        self.assertEqual(lines[-1], "pushpc")
        start = lines.index(f"{ROUTINE}:")
        close = lines.index("}", start)
        self.assertEqual(lines[close + 1:close + 3],
                         [f"assert pc() <= ${ALLOCATION_END:06X}", "pullpc"])
        size = assembled_size(self.program)
        self.assertEqual(size, 111)
        self.assertLessEqual(ALLOCATION_START + size, ALLOCATION_END)

    def test_routine_has_no_stack_or_subroutine_instructions(self):
        mnemonics = {mnemonic for mnemonic, _, _ in self.program}
        self.assertFalse(mnemonics & {"PHA", "PHX", "PHY", "PHP", "PHB", "PHD", "PHK",
                                      "PLA", "PLX", "PLY", "PLP", "PLB", "PLD",
                                      "JSR", "JSL", "RTS", "RTL", "RTI", "PEA", "PEI"})
        exits = [operand for mnemonic, _, operand in self.program if mnemonic == "JML"]
        self.assertEqual(exits, ["RoomTag_Return"])

    def test_static_operands_stay_inside_footprint(self):
        self.assertEqual(address_operands(self.program) - ALLOWED_OPERANDS, set())

    def test_qualifying_block_opens_closed_door_with_sfx(self):
        self.assert_opened(self.execute(with_block(room(door=1))))

    def test_qualifying_block_on_open_door_writes_nothing(self):
        self.assertEqual(self.execute(with_block(room(door=0))).writes, {})

    def test_no_block_closes_open_door_without_sfx(self):
        self.assert_closed_now(self.execute(room(door=0)))

    def test_no_block_on_closed_door_writes_nothing(self):
        self.assertEqual(self.execute(room(door=1)).writes, {})

    def test_transition_sequence_is_reversible(self):
        machine = self.execute(with_block(room(door=1)))
        self.assert_opened(machine)
        memory = machine.memory
        memory[0x0011] = 0x00
        machine = self.execute(memory)
        self.assertEqual(machine.writes, {})
        memory = machine.memory
        memory[0x0C4A] = 0x00  # pit deletion frees the slot and leaves SOMBTN set
        self.assertEqual(memory[0x0646], 0x01)
        machine = self.execute(memory)
        self.assert_closed_now(machine)
        memory = machine.memory
        memory[0x0011] = 0x00
        self.assert_opened(self.execute(with_block(memory)))

    def test_altitude_ff_counts_as_grounded(self):
        self.assert_opened(self.execute(with_block(room(door=1), x029E=0xFF)))

    def test_each_front_slot_qualifies_and_slot_five_does_not(self):
        for slot in range(5):
            with self.subTest(slot=slot):
                self.assert_opened(self.execute(with_block(room(door=1), slot=slot)))
        self.assertEqual(self.execute(with_block(room(door=1), slot=5)).writes, {})

    def test_stale_or_invalid_signal_is_rejected(self):
        cases = {
            "slot freed by pit deletion": {"x0C4A": 0x00},
            "slot became exploding block": {"x0C4A": 0x2D},
            "spawn delay running": {"x0394": 0x03},
            "bouncing": {"x03C5": 0x01},
            "lifted or carried": {"x0380": 0x03},
            "only three probe points on switch": {"x03DB": 0x03},
            "airborne": {"x029E": 0x10},
        }
        for name, slot_fields in cases.items():
            with self.subTest(name=name):
                self.assert_closed_now(self.execute(with_block(room(door=0), **slot_fields)))
        globals_cases = {"outdoors": {0x001B: 0x00}, "Link carrying": {0x0308: 0x80},
                         "transit lines": {0x03F4: 0x02}, "SOMBTN clear": {0x0646: 0x00}}
        for name, fields in globals_cases.items():
            with self.subTest(name=name):
                memory = with_block(room(door=0))
                memory.update(fields)
                self.assert_closed_now(self.execute(memory))

    def test_stale_slot_does_not_mask_live_slot(self):
        memory = with_block(room(door=1), slot=4, x03DB=0x00)
        self.assert_opened(self.execute(with_block(memory, slot=1)))

    def test_incompatible_pressure_sources_never_open(self):
        memory = room(door=0, extra={
            0x0642: 0x01,                          # sprite, ice block, follower tag
            0x0478: 0x02, 0x0500: 0x05, 0x0501: 0x00,
            0x0466: 0x00, 0x0467: 0x00,            # push block on switch latch
            0x02E4: 0x00, 0x004D: 0x00,            # Link free to press a floor switch
            0x0020: 0x40, 0x0022: 0x80,            # Link coordinates
            0x7EF350: 0x01,                        # Somaria owned in inventory
        })
        machine = self.execute(memory)
        self.assert_closed_now(machine)
        forbidden = {0x0642, 0x0466, 0x0467, 0x0478, 0x0479, 0x02E4, 0x004D,
                     0x0020, 0x0021, 0x0022, 0x0023, 0x7EF350}
        forbidden |= set(range(0x0500, 0x0560))
        self.assertEqual(set(machine.reads) & forbidden, set())

    def test_door_compare_is_sixteen_bit(self):
        machine = self.execute(with_block(room(door=0x0100)))
        self.assert_opened(machine)

    def test_abi_normalizes_widths_and_preserves_dispatcher_state(self):
        for p in (0x00, M_FLAG, X_FLAG, M_FLAG | X_FLAG):
            for memory in (with_block(room(door=1)), room(door=0), room(door=1)):
                with self.subTest(p=p, door=memory[0x0468]):
                    machine = self.execute(memory, p=p, y=0x0042)
                    self.assertEqual(machine.y, 0x0042)
                    for address in (0x000E, 0x00AE, 0x00AF):
                        self.assertEqual(machine.memory[address], memory[address])
                        self.assertNotIn(address, machine.writes)
                    self.assertLessEqual(set(machine.writes), DOOR_WRITES | {0x012F})


if __name__ == "__main__":
    unittest.main()
