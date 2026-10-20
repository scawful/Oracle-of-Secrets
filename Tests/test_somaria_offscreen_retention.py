"""Execute compiled cull-hook bytes with OOS_SOMARIA_ROM=/path/to/candidate.sfc.

This instruction-level 65816 subset checks the hook's M/X=8 contract, not
native rendering or cycle timing. Room/slot fixtures reuse the tag24 model.
"""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_somaria_socket_door import room, with_block

HOOK, KEEP, FALLBACK = 0x08E731, 0x08E74B, 0x08E737
EXIT_BYTES = bytes.fromhex("8a1acdec02d00d9cec02ad08032980f0039c080360")


def offset(address):
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


class CPU:
    """Decode actual ROM opcodes; unsupported instructions fail closed."""
    def __init__(self, rom, memory, slot=4, p=0xF3, y=0x11, a=0xBEEF,
                 pc=HOOK, dbr=0x08):
        self.rom, self.memory = rom, dict(memory)
        self.a, self.x, self.y, self.p = a, slot, y, p
        self.sp, self.dbr, self.d, self.pc = 0x01F0, dbr, 0, pc
        self.memory.update({self.sp + 1: 0xCD, self.sp + 2: 0xAB})
        self.writes, self.stack_writes = [], []

    def fetch(self, size=1):
        start = offset(self.pc)
        data = self.rom[start:start + size]
        if len(data) != size:
            raise AssertionError("ROM fetch outside candidate")
        self.pc += size
        return int.from_bytes(data, "little")

    def read(self, address):
        if self.dbr not in (8, 9) or not 0 <= address < 0x2000:
            raise AssertionError("data access outside admitted WRAM mirror")
        return self.memory.get(address, 0)

    def push(self, value):
        self.memory[self.sp] = value & 0xFF
        self.stack_writes.append(self.sp)
        self.sp -= 1

    def pull(self):
        self.sp += 1
        return self.read(self.sp)

    def nz(self, value):
        self.p = (self.p & ~0x82) | (value & 0x80) | (2 if value == 0 else 0)

    def load(self, value):
        self.a = (self.a & 0xFF00) | value
        self.nz(value)

    def compare(self, left, right):
        self.p = (self.p & ~1) | int(left >= right)
        self.nz((left - right) & 0xFF)

    def registers(self):
        return self.a, self.x, self.y, self.p, self.sp, self.dbr, self.d

    def step(self):
        if self.p & 0x30 != 0x30:
            raise AssertionError("hook leaked M/X width")
        address, op = self.pc, self.fetch()
        if op == 0x08:  # PHP
            self.push(self.p)
        elif op == 0x48:  # PHA, M=8; hidden B stays intact
            self.push(self.a)
        elif op == 0x68:
            self.load(self.pull())
        elif op == 0x28:
            self.p = self.pull()
        elif op == 0x5C:
            self.pc = self.fetch(3)
        elif op in (0xA5, 0xAD, 0xBD):
            self.load(self.read(self.fetch(1 if op == 0xA5 else 2)
                                + (self.x if op == 0xBD else 0)))
        elif op == 0xA2:
            self.x = self.fetch()
            self.nz(self.x)
        elif op == 0x29:
            self.load((self.a & 0xFF) & self.fetch())
        elif op == 0x1D:  # ORA absolute,X
            self.load((self.a & 0xFF) | self.read(self.fetch(2) + self.x))
        elif op == 0x2C:
            value = self.read(self.fetch(2))
            self.p = (self.p & ~0xC2) | (value & 0xC0) | (2 if not self.a & value else 0)
        elif op in (0xC9, 0xCD, 0xE0):
            right = self.read(self.fetch(2)) if op == 0xCD else self.fetch()
            self.compare(self.x if op == 0xE0 else self.a & 0xFF, right)
        elif op in (0xF0, 0xD0, 0xB0, 0x30, 0x10, 0x80):
            displacement = self.fetch()
            taken = {0xF0: bool(self.p & 2), 0xD0: not self.p & 2,
                     0xB0: bool(self.p & 1), 0x30: bool(self.p & 0x80),
                     0x10: not self.p & 0x80, 0x80: True}[op]
            if taken:
                self.pc += displacement - 256 if displacement & 128 else displacement
        elif op in (0x64, 0x9C, 0x9E):
            dest = self.fetch(1 if op == 0x64 else 2) + (self.x if op == 0x9E else 0)
            self.read(dest)  # Enforce the same data-bank/address boundary on writes.
            self.memory[dest] = 0
            self.writes.append((dest, 0))
        elif op == 0x8A:
            self.load(self.x)
        elif op == 0x9B:
            self.y = self.x
            self.nz(self.y)
        elif op == 0xCA:
            self.x = (self.x - 1) & 0xFF
            self.nz(self.x)
        elif op == 0x1A:
            self.load((self.a + 1) & 0xFF)
        elif op == 0xEA:
            pass
        elif op == 0x60:
            low, high = self.pull(), self.pull()
            self.pc = (address & 0xFF0000) | ((low | high << 8) + 1)
            return True
        else:
            raise AssertionError(f"unsupported opcode {op:02X} at {address:06X}")
        return False

    def boundary(self, targets=(KEEP, FALLBACK), limit=100):
        for _ in range(limit):
            if self.pc in targets:
                return self.pc
            self.step()
        raise AssertionError("hook did not reach a vanilla continuation")

    def finish(self):
        for _ in range(16):
            if self.step():
                return
        raise AssertionError("vanilla continuation did not return")


@unittest.skipUnless(os.environ.get("OOS_SOMARIA_ROM"), "set OOS_SOMARIA_ROM to compiled candidate")
class SomariaOffscreenRetention(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path(os.environ["OOS_SOMARIA_ROM"]).read_bytes()

    def execute(self, memory, keep, *, rom=None, **registers):
        cpu = CPU(self.rom if rom is None else rom, memory, **registers)
        before, initial = cpu.registers(), dict(cpu.memory)
        self.assertEqual(cpu.boundary(), KEEP if keep else FALLBACK)
        self.assertEqual(cpu.registers(), before, "hook must restore registers, flags and SP")
        expected_writes = [] if keep else [(0x0646, 0), (0x0C4A + cpu.x, 0)]
        self.assertEqual(cpu.writes, expected_writes)
        expected = dict(initial)
        expected.update(expected_writes)
        actual = {key: value for key, value in cpu.memory.items()
                  if key not in cpu.stack_writes}
        self.assertEqual(actual, {key: value for key, value in expected.items()
                                  if key not in cpu.stack_writes})
        cpu.finish()
        self.assertEqual((cpu.pc, cpu.sp), (0x08ABCE, before[4] + 2))
        self.assertEqual(cpu.writes, expected_writes, "inherited RTS must keep the same data writes")
        return cpu

    def test_gateway_and_untouched_cleanup(self):
        start = offset(HOOK)
        self.assertEqual(self.rom[start], 0x5C)
        self.assertEqual(self.rom[start + 4:start + 6], b"\xEA\xEA")
        helper = int.from_bytes(self.rom[start + 1:start + 4], "little")
        self.assertEqual(helper, 0x2CFD6F)
        self.assertEqual(self.rom[offset(FALLBACK):offset(KEEP) + 1], EXIT_BYTES)

    def test_qualifying_slots_tags_ground_altitudes_and_all_status_flags(self):
        for slot in range(5):
            for tags in ((0x24, 0), (0, 0x24)):
                for altitude in (0, 0xFF):
                    memory = with_block(room(), slot=slot, x029E=altitude)
                    memory.update(zip((0xAE, 0xAF), tags))
                    for p in range(256):
                        if p & 0x30 != 0x30:
                            continue
                        for y, a in ((0x11, 0xBEEF), (4, 0x9700)):
                            with self.subTest(slot=slot, tags=tags, z=altitude, p=p, y=y):
                                self.execute(memory, True, slot=slot, p=p, y=y, a=a)

    def test_unqualified_states_replay_only_the_vanilla_pair(self):
        cases = {"no tag24": {0xAE: 0x16, 0xAF: 0}, "outdoors": {0x1B: 0},
                 "signal clear": {0x646: 0}, "carrying": {0x308: 0x80},
                 "transit": {0x3F4: 1}, "free slot": {0xC4E: 0},
                 "other ancilla": {0xC4E: 7}, "fizz": {0xC4E: 0x2D},
                 "split": {0xC4E: 0x2E}, "spawn delay": {0x398: 1},
                 "bounce": {0x3C9: 1}, "lift": {0x384: 1}, "held": {0x384: 3},
                 "airborne": {0x2A2: 1}, "negative airborne": {0x2A2: 0xFE},
                 "no probes": {0x3DF: 0}, "three probes": {0x3DF: 3},
                 "invalid probes": {0x3DF: 5}}
        for name, changes in cases.items():
            with self.subTest(case=name):
                memory = with_block(room(), slot=4)
                memory.update(changes)
                self.execute(memory, False)
        self.execute(with_block(room(), slot=5), False, slot=5)

    def test_mutation_global_retention_is_rejected(self):
        mutant = bytearray(self.rom)
        mutant[offset(HOOK):offset(HOOK) + 6] = b"\x5C\x4B\xE7\x08\xEA\xEA"
        self.execute(with_block(room(), slot=4), True, rom=bytes(mutant))
        memory = with_block(room(extra={0xAE: 0, 0xAF: 0}), slot=4)
        with self.assertRaises(AssertionError):
            self.execute(memory, False, rom=bytes(mutant))

    def test_mutation_missing_status_pop_is_rejected(self):
        mutant = bytearray(self.rom)
        start = int.from_bytes(mutant[offset(HOOK) + 1:offset(HOOK) + 4], "little")
        restore = mutant.find(bytes.fromhex("68285c4be708"), offset(start), offset(0x2CFE00))
        self.assertNotEqual(restore, -1, "candidate lacks the keep-path register restore")
        mutant[restore + 1] = 0xEA
        with self.assertRaises(AssertionError):
            self.execute(with_block(room(), slot=4), True, rom=bytes(mutant))


TERM_HOOK, TERM_KEEP, TERM_FALLBACK = 0x09AC81, 0x09ACA9, 0x09AC86
TERM_ORIGINAL = bytes.fromhex("9c4606a548")


@unittest.skipUnless(os.environ.get("OOS_SOMARIA_ROM"), "set OOS_SOMARIA_ROM to compiled candidate")
class SomariaInternalLandingRetention(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path(os.environ["OOS_SOMARIA_ROM"]).read_bytes()

    @staticmethod
    def fixture(slot=4, **fields):
        memory = with_block(room(extra={0x10: 7, 0x11: 1, 0xA0: 0x93, 0xA1: 0,
                                       0x48E: 0x93, 0x48F: 0, 0x48: 0xB5}), slot=slot)
        memory.update({int(key[1:], 16): value for key, value in fields.items()})
        return memory

    def execute(self, memory, keep, *, rom=None, slot=4, p=0x73, y=0x55, a=0xBE2C):
        cpu = CPU(self.rom if rom is None else rom, memory, slot=slot, p=p, y=y,
                  a=a, pc=TERM_HOOK, dbr=9)
        before, initial = cpu.registers(), dict(cpu.memory)
        self.assertEqual(cpu.boundary((TERM_KEEP, TERM_FALLBACK)),
                         TERM_KEEP if keep else TERM_FALLBACK)
        expected = list(before)
        writes = []
        if not keep:
            value = memory.get(0x48, 0)
            expected[0] = (a & 0xFF00) | value
            expected[3] = (p & ~0x82) | (value & 0x80) | (2 if value == 0 else 0)
            writes = [(0x646, 0)]
        self.assertEqual(cpu.registers(), tuple(expected), "internal hook ABI/vanilla replay differs")
        self.assertEqual(cpu.writes, writes)
        initial.update(writes)
        self.assertEqual({k: v for k, v in cpu.memory.items() if k not in cpu.stack_writes},
                         {k: v for k, v in initial.items() if k not in cpu.stack_writes})
        return cpu

    def test_gateway_and_native_loop_guards(self):
        start = offset(TERM_HOOK)
        self.assertEqual(self.rom[start:start + 5], bytes.fromhex("5c00fc2cea"))
        for address, raw in ((0x09AC6B, "8b4baba205"), (0x09AC7A, "bd4a0cc92cd00d"),
                             (TERM_FALLBACK, "2980f0046448645e"), (0x09ACA6, "9e4a0cca10c4")):
            expected = bytes.fromhex(raw)
            self.assertEqual(self.rom[offset(address):offset(address) + len(expected)], expected)

    def test_qualifying_internal_slots_tags_altitudes_and_status_abi(self):
        for slot in range(5):
            for tags in ((0x24, 0), (0, 0x24)):
                for z in (0, 0xFF):
                    memory = self.fixture(slot, xAE=tags[0], xAF=tags[1])
                    memory[0x29E + slot] = z
                    for p in range(256):
                        if p & 0xB3 != 0x33:  # Real CMP #$2C entry: M/X=8, C/Z=1, N=0.
                            continue
                        for a, y in ((0xBE2C, 0x55), (0x972C, 4)):
                            self.execute(memory, True, slot=slot, p=p, a=a, y=y)

    def test_rejections_replay_pressure_clear_and_load_with_exact_flags(self):
        cases = {"module": {0x10: 9}, "normal play": {0x11: 0}, "external unload": {0x11: 2},
                 "changed room low": {0x48E: 0x92}, "changed room high": {0x48F: 1},
                 "no tag": {0xAE: 0x16, 0xAF: 0}, "outdoors": {0x1B: 0},
                 "no pressure": {0x646: 0}, "carrying": {0x308: 0x80}, "transit": {0x3F4: 1},
                 "not block": {0xC4E: 0x2D}, "spawn": {0x398: 1}, "bounce": {0x3C9: 1},
                 "lift": {0x384: 1}, "air": {0x2A2: 1}, "negative air": {0x2A2: 0xFE},
                 "no probes": {0x3DF: 0}, "partial probes": {0x3DF: 3}, "bad probes": {0x3DF: 5}}
        for changes in cases.values():
            for value in (0, 0x7F, 0x80, 0xFF):
                memory = self.fixture(x48=value)
                memory.update(changes)
                self.execute(memory, False)
        self.execute(self.fixture(5), False, slot=5)

    def test_whole_per_slot_loop_keeps_only_cube_and_preserves_vanilla_controls(self):
        vanilla = bytearray(self.rom)
        vanilla[offset(TERM_HOOK):offset(TERM_HOOK) + 5] = TERM_ORIGINAL
        contexts = ({}, {0x11: 2}, {0x11: 0}, {0x48E: 0x94}, {0x48F: 1},
                    {0xAE: 0, 0xAF: 0}, {0x308: 0x80, 0x2EC: 3})
        for slot in (0, 2, 4):
            for changes in contexts:
                memory = self.fixture(slot, x48=0, x5E=0x29)
                memory.update({0xC4A + i: 0x3E if i == 5 else 7 for i in range(6)})
                memory[0xC4A + slot] = 0x2C
                memory.update(changes)
                runs = []
                for image in (self.rom, bytes(vanilla)):
                    cpu = CPU(image, memory, pc=0x09AC6E, dbr=9, p=0x73, a=0xBE2C)
                    self.assertEqual(cpu.boundary((0x09ACAC,), limit=600), 0x09ACAC)
                    self.assertEqual((cpu.x, cpu.y, cpu.sp, cpu.dbr, cpu.d), (0xFF, 5, 0x1F0, 9, 0))
                    runs.append(cpu)
                actual, control = runs
                expected = dict(control.memory)
                writes = list(control.writes)
                if not changes:
                    expected[0xC4A + slot], expected[0x646] = 0x2C, 1
                    writes = [w for w in writes if w[0] not in (0xC4A + slot, 0x646)]
                self.assertEqual(actual.writes, writes, "neighbor slots and vanilla cleanup must match")
                stack = set(actual.stack_writes + control.stack_writes)
                self.assertEqual({k: v for k, v in actual.memory.items() if k not in stack},
                                 {k: v for k, v in expected.items() if k not in stack})

    def test_mutation_unconditional_internal_retention_is_rejected(self):
        mutant = bytearray(self.rom)
        mutant[offset(TERM_HOOK):offset(TERM_HOOK) + 5] = bytes.fromhex("5ca9ac09ea")
        self.execute(self.fixture(), True, rom=bytes(mutant))
        for memory in (self.fixture(x11=2), self.fixture(xAE=0, xAF=0)):
            with self.assertRaises(AssertionError):
                self.execute(memory, False, rom=bytes(mutant))

    def test_mutation_internal_missing_status_pop_is_rejected(self):
        mutant = bytearray(self.rom)
        restore = mutant.find(bytes.fromhex("68285ca9ac09"), offset(0x2CFC00), offset(0x2CFD00))
        self.assertNotEqual(restore, -1)
        mutant[restore + 1] = 0xEA
        with self.assertRaises(AssertionError):
            self.execute(self.fixture(), True, rom=bytes(mutant))


if __name__ == "__main__":
    unittest.main()
