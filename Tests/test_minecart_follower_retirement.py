"""Execute the actual follower-retirement ASM with the existing WRAM model.

Allocation/Prep calls are explicit ABI stubs. These source controls prove no
assembled bytes, native allocation, movement, graphics, or doorway behavior.
"""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cart_source_model", ROOT / "Tests/test_cart_shutter_local.py")
local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local)
SOURCE = ROOT / "Sprites/NPCs/followers.asm"
RETIRE = "MinecartFollower_RetireSupersededCart"
TRANSITION = "MinecartFollower_TransitionToSprite"
ANIMATION = 0x400000  # Separate model address for the source's four-byte ROM table.


def program(transition=False):
    lines = (local.body(SOURCE, TRANSITION) if transition else
             ["JSR.w " + RETIRE, "RTL"])
    lines += [".retire"] + local.body(SOURCE, RETIRE)
    lines = [line.replace("JSR " + RETIRE, "JSR.w .retire")
             .replace("JSR.w " + RETIRE, "JSR.w .retire") for line in lines]
    # Resolve only forward anonymous labels; preserve all actual branch targets.
    anonymous = {i: f".anon_{i}" for i, line in enumerate(lines) if line == "+"}
    for i, line in enumerate(lines):
        if i in anonymous:
            lines[i] = anonymous[i]
        elif line.endswith(" +"):
            target = next(j for j in anonymous if j > i)
            lines[i] = line[:-1] + anonymous[target]
    symbols = dict(local.SYMBOLS)
    for filename in ("Core/ram.asm", "Sprites/Objects/minecart.asm"):
        for name, value in re.findall(r"^(!?\w+)\s*=\s*\$([0-9A-Fa-f]+)",
                                      (ROOT / filename).read_text(), re.M):
            # Absolute .w WRAM operands use the low word of bank-$7E aliases.
            address = int(value, 16)
            symbols[name] = address & 0xFFFF if address >> 16 == 0x7E else address
    symbols["Minecart_AnimDirection"] = ANIMATION
    for name, value in sorted(symbols.items(), key=lambda pair: -len(pair[0])):
        lines = [line if line.startswith("JSL ") else
                 re.sub(r"(?<!\w)" + re.escape(name) + r"(\+1)?(?!\w)",
                        lambda m: f"${value + bool(m[1]):04X}", line) for line in lines]
    return local.base.parse(lines)


class Machine(local.Machine):
    """Delegate ordinary instructions; add only this caller's missing opcodes."""

    def run(self, code, labels, limit=500, spawn=True, prep="claim"):
        pc, stack = 0, []
        self.calls = []

        def push(kind, value, size):
            stack.append((kind, value, size))
            self.sp -= size

        def pop(kind, size):
            actual, value, count = stack.pop()
            assert (actual, count) == (kind, size), (actual, kind, count, size)
            self.sp += size
            return value

        def register(name, value):
            wide = self.m16() if name == "a" else self.x16()
            value &= 0xFFFF if wide else 0xFF
            if name == "a" and not wide:
                value |= self.a & 0xFF00
            setattr(self, name, value)
            self.flags_nz(value & (0xFFFF if wide else 0xFF), wide)

        for _ in range(limit):
            op, suffix, arg = code[pc]
            pc += 1
            if op in ("PHA", "PHX", "PHY"):
                name = {"PHA": "a", "PHX": "x", "PHY": "y"}[op]
                size = 2 if (self.m16() if name == "a" else self.x16()) else 1
                push(name, getattr(self, name) & (65535 if size == 2 else 255), size)
            elif op in ("PLA", "PLX", "PLY"):
                name = {"PLA": "a", "PLX": "x", "PLY": "y"}[op]
                size = 2 if (self.m16() if name == "a" else self.x16()) else 1
                register(name, pop(name, size))
            elif op in ("TAY", "TYA", "TYX", "TXA"):
                source, target = {"TAY": ("a", "y"), "TYA": ("y", "a"),
                                  "TYX": ("y", "x"), "TXA": ("x", "a")}[op]
                register(target, getattr(self, source))
            elif op in ("EOR", "ADC"):
                wide = self.m16()
                mask = 65535 if wide else 255
                value, old = self.load(suffix, arg, wide), self.a & mask
                if op == "EOR":
                    register("a", old ^ value)
                else:
                    total = old + value + int(self.c)
                    self.c = total > mask
                    self.v = bool((~(old ^ value) & (old ^ total)) & ((mask + 1) >> 1))
                    register("a", total)
            elif op in ("BEQ", "BNE", "BCC", "BCS", "BMI", "BPL", "BRA", "JMP"):
                taken = {"BEQ": self.z, "BNE": not self.z, "BCC": not self.c,
                         "BCS": self.c, "BMI": self.n, "BPL": not self.n,
                         "BRA": True, "JMP": True}[op]
                if taken:
                    pc = labels[arg]
            elif op == "JSR":
                push("return", pc, 2)
                pc = labels[arg]
            elif op == "RTS":
                pc = pop("return", 2)
            elif op == "JSL":
                self.calls.append(arg)
                if arg == "Sprite_SpawnDynamically":
                    # The allocator returns a negative A on failure, else Y=slot.
                    register("a", 15 if spawn else 0xFF)
                    register("y", 15 if spawn else 0xFF)
                    if spawn:
                        for address, value in ((0x0DD0, 9), (0x0E20, 0xA3), (0x0F20, 0)):
                            self.write(address + 15, value, False)
                elif arg == "Sprite_SetSpawnedCoords":
                    # This caller overwrites all four position bytes itself.
                    pass
                elif arg == "Sprite_Minecart_Prep":
                    assert self.x == 15
                    if prep != "unclaimed":
                        self.write(0x07EA, 15, True)
                    for mode, address, value in (("dead", 0x0DD0, 0),
                                                  ("wrong_kind", 0x0E20, 0xB0),
                                                  ("wrong_track", 0x0E30, 1),
                                                  ("wrong_floor", 0x0F20, 1)):
                        if prep == mode:
                            self.write(address + 15, value, False)
                    # Clobber A/Y so only the caller's saved old-owner byte survives.
                    register("a", 0xA5)
                    register("y", 0x3C)
                else:
                    raise AssertionError("Unadmitted external ABI stub: " + arg)
            elif op == "RTL":
                assert not stack, "Unbalanced stack at RTL"
                return "RTL"
            else:
                # Reuse the existing memory, width, compare, store and flag rules.
                super().run([(op, suffix, arg), ("JML", None, ".step")], {})
        raise AssertionError("Retirement source model exceeded step limit")


def actor(memory, slot, *, state=9, kind=0xA3, track=0, floor=0, action=6,
          x=0x0F78, y=0x1318):
    for address, value in ((0x0DD0, state), (0x0E20, kind), (0x0E30, track),
                           (0x0F20, floor), (0x0D80, action), (0x0D10, x & 255),
                           (0x0D30, x >> 8), (0x0D00, y & 255), (0x0D20, y >> 8)):
        memory[address + slot] = value


def fixture():
    memory = {0x10: 7, 0x11: 0, 0x1B: 1, 0x35: 1, 0xEE: 0, 0x7EF3CC: 0x0B,
              0x07E8: 0, 0x07E9: 1, 0x07EA: 15, 0x07EB: 0,
              0x20: 0xC0, 0x21: 0x12, 0x22: 0x78, 0x23: 0x0F}
    actor(memory, 14)
    actor(memory, 15, action=3, y=0x12B8)
    actor(memory, 3, track=7, floor=1, action=0)
    table = SOURCE.read_text().split("Minecart_AnimDirection:\n", 1)[1].splitlines()[0]
    for index, value in enumerate(re.findall(r"\$([0-9A-Fa-f]{2})", table)):
        memory[ANIMATION + index] = int(value, 16)
    return memory


class MinecartFollowerRetirement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = program()
        cls.transition = program(transition=True)

    def execute_helper(self, memory=None, old=14, replacement=15):
        machine = Machine(fixture() if memory is None else memory,
                          a=old, x=replacement, y=0x5A)
        self.assertEqual(machine.run(*self.helper), "RTL")
        self.assertEqual((machine.x, machine.y, machine.sp, machine.p & 0x30),
                         (replacement, 0x5A, 0x01FB, 0x30))
        return machine

    def test_retires_only_old_moving_or_releasing_actor_and_preserves_registers(self):
        for action in range(2, 7):
            with self.subTest(action=action):
                memory = fixture()
                memory[0x0D80 + 14] = action
                machine = self.execute_helper(memory)
                self.assertEqual(machine.writes, {0x0DD0 + 14: 0})
                self.assertEqual(machine.memory, {**memory, 0x0DD0 + 14: 0})

    def test_preserves_parked_waiting_and_unrecognized_old_actions(self):
        for action in (0, 1, 7, 0xFF):
            with self.subTest(action=action):
                memory = fixture()
                memory[0x0D80 + 14] = action
                self.assertFalse(self.execute_helper(memory).writes)

    def test_refuses_other_actor_track_floor_room_and_invalid_game_context(self):
        cases = [("old_inactive", 0x0DD0 + 14, 0), ("old_kind", 0x0E20 + 14, 0xB0),
                 ("old_track", 0x0E30 + 14, 1), ("old_floor", 0x0F20 + 14, 1),
                 ("old_x_room", 0x0D30 + 14, 0x0D), ("old_y_room", 0x0D20 + 14, 0x11),
                 ("new_inactive", 0x0DD0 + 15, 0), ("new_kind", 0x0E20 + 15, 0xB0),
                 ("new_track", 0x0E30 + 15, 1), ("new_floor", 0x0F20 + 15, 1),
                 ("module", 0x10, 9), ("submodule", 0x11, 1), ("outdoors", 0x1B, 0),
                 ("other_follower", 0x7EF3CC, 0), ("unmounted", 0x35, 0),
                 ("link_floor", 0xEE, 1), ("unclaimed_new", 0x07EA, 14),
                 ("malformed_owner", 0x07EB, 1)]
        for name, address, value in cases:
            with self.subTest(name=name):
                memory = fixture()
                memory[address] = value
                machine = self.execute_helper(memory)
                self.assertFalse(machine.writes)
                self.assertEqual(machine.memory, memory)

    def test_same_room_two_high_byte_pages_are_admitted_on_both_axes(self):
        for xh in (0x0E, 0x0F):
            for yh in (0x12, 0x13):
                with self.subTest(xh=xh, yh=yh):
                    memory = fixture()
                    memory[0x0D30 + 14], memory[0x0D20 + 14] = xh, yh
                    self.assertEqual(self.execute_helper(memory).writes, {0x0DD0 + 14: 0})

    def test_invalid_or_identical_prior_owner_does_not_retire_an_actor(self):
        for old in (15, 16, 0xFF):
            with self.subTest(old=old):
                self.assertFalse(self.execute_helper(old=old).writes)

    def execute_transition(self, *, spawn=True, prep="claim", owner=14):
        memory = fixture()
        memory[0x07EA], memory[0x07EB] = owner & 255, owner >> 8
        memory[0x0DD0 + 15] = 0
        machine = Machine(memory, a=0xCC, x=5, y=0x5A)
        self.assertEqual(machine.run(*self.transition, spawn=spawn, prep=prep), "RTL")
        self.assertEqual((machine.sp, machine.p & 0x30), (0x01FB, 0x30))
        return memory, machine

    def test_failed_allocation_preserves_old_actor_owner_and_follower(self):
        for owner in (14, 0x010E):
            with self.subTest(owner=owner):
                before, machine = self.execute_transition(spawn=False, owner=owner)
                self.assertEqual(machine.calls, ["Sprite_SpawnDynamically"])
                self.assertEqual(machine.memory, before)
                self.assertFalse(machine.writes)

    def test_successful_allocation_and_claim_retires_saved_old_owner_after_prep(self):
        before, machine = self.execute_transition()
        self.assertEqual(machine.calls, ["Sprite_SpawnDynamically", "Sprite_SetSpawnedCoords",
                                         "Sprite_Minecart_Prep"])
        self.assertEqual(machine.memory[0x0DD0 + 14], 0)
        self.assertEqual(machine.memory[0x0DD0 + 15], 9)
        self.assertEqual(machine.memory[0x07EA], 15)
        self.assertEqual(machine.memory[0x7EF3CC], 0)
        self.assertEqual(machine.x, 15)
        self.assertEqual(machine.y, 0x3C)
        self.assertEqual(machine.memory[0x0DD0 + 3], before[0x0DD0 + 3])

    def test_unclaimed_or_invalid_replacement_cannot_retire_old_actor(self):
        for prep in ("unclaimed", "dead", "wrong_kind", "wrong_track", "wrong_floor"):
            with self.subTest(prep=prep):
                _, machine = self.execute_transition(prep=prep)
                self.assertEqual(machine.memory[0x0DD0 + 14], 9)
        _, machine = self.execute_transition(owner=0x010E)
        self.assertEqual(machine.memory[0x0DD0 + 14], 9)


if __name__ == "__main__":
    unittest.main()
