"""Source contract and model checks for the Sky (D8) essence award gateways.

A minimal 65816-subset interpreter executes the routine text in
Dungeons/sky_d8_award.asm against a WRAM model. Native continuations are
modeled from usdasm and the qualified ROM bytes recorded below. This checks
the source contract only; it is not an assembler, CPU or native emulator
proof. Set OOS_SKY_AWARD_ROM to a built oos168x.sfc to also check every
preimage assert against real ROM bytes (read-only).
"""
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Dungeons" / "sky_d8_award.asm"
DUNGEONS = ROOT / "Dungeons" / "dungeons.asm"
SRAM = ROOT / "Core" / "sram.asm"

sys.path.insert(0, str(ROOT / "Scripts" / "Generate"))
from generate_hooks_json import scan_hooks  # noqa: E402

M_FLAG, X_FLAG = 0x20, 0x10
CRYSTALS = 0x7EF37A
SKY_BIT = 0x80
STACK_TOP = 0x01F0

# Complete overwritten bytes per hook site (usdasm; identical in base e75690ad
# and qualified ROM a81146de). Kind: (routine, entry M, entry X).
HOOKS = {
    0x01C508: ("SkyD8_PrizeTriggerDoor", "AD0C044AAA", 8, 8),
    0x01C709: ("SkyD8_HeartPrizeTag", "AD03042980", 8, 8),
    0x08CC3B: ("SkyD8_CrystalCollector", "AD0C044AAA", 8, 8),
    0x029897: ("SkyD8_CrystalTilemap", "A20EA5A0", 16, 8),
    0x00F959: ("SkyD8_BossExit", "A20CA5A0", 8, 8),
    0x1ECD8B: ("SkyD8_MaidenFollowerGfx", "AD0C04C918", 8, 8),
    0x1ECE1B: ("SkyD8_MaidenDraw", "BD800DC903", 8, 8),
    0x1ECECE: ("SkyD8_MaidenSpeech", "AD0C0438", 8, 8),
}
EXITS = {
    "SkyD8_PrizeTriggerDoor": {"$01C50D", "$01C529", "$01C53E"},
    "SkyD8_HeartPrizeTag": {"$01C70E", "$01C742", "$01C749", "$01C74D"},
    "SkyD8_CrystalCollector": {"$08CC48", "$08CC40", "$08C453"},
    "SkyD8_CrystalTilemap": {"$0298A7", "$02989B"},
    "SkyD8_BossExit": {"$00F96A", "$00F95D"},
    "SkyD8_MaidenFollowerGfx": {"$1ECDAD", "$1ECD90"},
    "SkyD8_MaidenDraw": {"$1ECE26", "$1ECE20"},
    "SkyD8_MaidenSpeech": {"$1ECF17", "$1ECED2"},
}
# RoomTagPrizeChecks ($02A1A4), 13 entries, then the code byte an index of
# $0D (Fortress $1A) over-reads.
PRIZE_CHECKS = [0x00, 0x00, 0x04, 0x02, 0x00, 0x10, 0x02, 0x01, 0x40, 0x04, 0x01,
                0x20, 0x08]
OVERREAD_BYTE = 0xAD
LEGACY_CRYSTAL_IDS = {0x0C: 0x02, 0x0E: 0x01, 0x10: 0x40, 0x12: 0x04, 0x16: 0x20,
                      0x18: 0x08, 0x0A: 0x10}
PENDANT_IDS = {0x04: 0x04, 0x06: 0x02, 0x14: 0x01}
NATIVE_TILEMAP_OFFSETS = {0x1618, 0x1658, 0x0658}
CRYSTAL_SAMPLES = (0x00, 0x7F, 0x80, 0xFF)


def code_lines(text):
    return [line.split(";", 1)[0].strip() for line in text.splitlines()]


def defines():
    text = SRAM.read_text()
    sky = re.search(r"(?m)^!Crystal_D8_Sky\s*=\s*\$([0-9A-F]{2})", text)
    crystals = re.search(r"(?m)^Crystals\s*=\s*\$([0-9A-F]{6})", text)
    return {"!Crystal_D8_Sky": int(sky.group(1), 16), "Crystals": int(crystals.group(1), 16)}


def routine(name):
    lines = SOURCE.read_text().splitlines()
    start = lines.index(f"{name}:")
    body = []
    for line in lines[start + 1:]:
        if line == "}":
            return body
        code = line.split(";", 1)[0].strip()
        if code in ("", "{"):
            continue
        body.extend(part.strip() for part in code.split(" : "))
    raise AssertionError(f"{name} block is not closed")


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


class Machine:
    def __init__(self, memory, p, a=0xBEEF, x=0x00, y=0x5A, stack=()):
        self.memory, self.p = dict(memory), p
        self.a, self.x, self.y = a, x & 0xFF if p & X_FLAG else x, y
        self.n = self.z = self.c = False
        self.sp = STACK_TOP
        self.reads, self.writes = [], {}
        for value in stack:
            self.push(value)
        self.symbols = defines()

    def m16(self):
        return not self.p & M_FLAG

    def x16(self):
        return not self.p & X_FLAG

    def push(self, value):
        self.memory[self.sp] = value & 0xFF
        self.sp -= 1

    def pull(self):
        self.sp += 1
        return self.memory.pop(self.sp)

    def nz(self, value, wide):
        self.z = value == 0
        self.n = bool(value & (0x8000 if wide else 0x80))

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

    def immediate(self, suffix, operand, wide):
        text = operand[1:]
        value = self.symbols.get(text)
        if value is None:
            value = int(text[1:], 16)
        if {"b": 1, "w": 2}[suffix] != (2 if wide else 1):
            raise AssertionError(f"#{text} width .{suffix} differs from runtime width")
        return value

    def effective(self, suffix, operand):
        if operand in self.symbols:
            if suffix != "l":
                raise AssertionError(f"{operand} must use long addressing")
            return self.symbols[operand]
        match = re.fullmatch(r"\$([0-9A-F]+)(?:,\s*X)?", operand)
        if not match:
            raise AssertionError(f"unsupported operand {operand!r}")
        address = int(match.group(1), 16)
        if suffix in ("b", "w") and address >= 0x2000:
            raise AssertionError(f"${address:X} is outside the low WRAM mirror")
        return address + (self.x if operand.endswith("X") else 0)

    def operand(self, suffix, operand, wide):
        if operand.startswith("#"):
            return self.immediate(suffix, operand, wide)
        return self.read(self.effective(suffix, operand), wide)

    def compare(self, register, value, wide):
        mask = 0xFFFF if wide else 0xFF
        self.c = (register & mask) >= value
        self.nz((register - value) & mask, wide)

    def set_a(self, value):
        self.a = value & 0xFFFF if self.m16() else (self.a & 0xFF00) | (value & 0xFF)

    def acc(self):
        return self.a if self.m16() else self.a & 0xFF

    def run(self, program, labels, limit=200):
        pc = 0
        for _ in range(limit):
            mnemonic, suffix, operand = program[pc]
            pc += 1
            wide = self.m16()
            if mnemonic == "LDA":
                value = self.operand(suffix, operand, wide)
                self.set_a(value)
                self.nz(value, wide)
            elif mnemonic in ("LDX", "LDY"):
                value = self.operand(suffix, operand, self.x16())
                setattr(self, mnemonic[2].lower(), value)
                self.nz(value, self.x16())
            elif mnemonic in ("AND", "ORA"):
                value = self.operand(suffix, operand, wide)
                result = self.acc() & value if mnemonic == "AND" else self.acc() | value
                self.set_a(result)
                self.nz(result, wide)
            elif mnemonic == "CMP":
                self.compare(self.acc(), self.operand(suffix, operand, wide), wide)
            elif mnemonic == "LSR":
                if operand != "A":
                    raise AssertionError("only LSR A is modeled")
                self.c = bool(self.acc() & 1)
                self.set_a(self.acc() >> 1)
                self.nz(self.acc(), wide)
            elif mnemonic == "TAX":
                self.x = self.acc() if not self.x16() else self.a
                self.nz(self.x, self.x16())
            elif mnemonic == "STA":
                self.write(self.effective(suffix, operand), self.acc(), wide)
            elif mnemonic == "STY":
                self.write(self.effective(suffix, operand), self.y, self.x16())
            elif mnemonic == "STZ":
                self.write(self.effective(suffix, operand), 0, wide)
            elif mnemonic == "PHA":
                self.push(self.acc())
            elif mnemonic == "PLX":
                self.x = self.pull()
                self.nz(self.x, False)
            elif mnemonic == "SEC":
                self.c = True
            elif mnemonic in ("BEQ", "BNE", "BCS", "BCC", "BRA"):
                taken = {"BEQ": self.z, "BNE": not self.z, "BCS": self.c,
                         "BCC": not self.c, "BRA": True}[mnemonic]
                if taken:
                    pc = labels[operand]
            elif mnemonic == "JML":
                return operand
            else:
                raise AssertionError(f"{mnemonic} is outside the modeled contract")
        raise AssertionError("step limit reached")


def wram(room=0x0096, dungeon=0x10, crystals=0x00, world=0x00, extra=None):
    memory = {0x00A0: room & 0xFF, 0x00A1: room >> 8, 0x040C: dungeon,
              CRYSTALS: crystals, 0x7EF3CA: world, 0x7EF374: 0x07, 0x000E: 0x01,
              0x0403: 0x80, 0x0011: 0x00, 0x00B0: 0x00}
    memory.update(extra or {})
    return memory


class SkyAwardModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.programs = {name: parse(routine(name)) for name, *_ in HOOKS.values()}

    def execute(self, name, memory, m=8, stack=(), **registers):
        p = (0 if m == 16 else M_FLAG) | X_FLAG
        machine = Machine(memory, p, stack=stack, **registers)
        target = machine.run(*self.programs[name])
        self.assertIn(target, EXITS[name])
        self.assertEqual(machine.p, p, "gateways never change P width")
        return target, machine

    # --- RoomTag_GetHeartForPrize ($01C709) ---------------------------------

    def test_heart_tag_sky_requires_boss_heart(self):
        for crystals in CRYSTAL_SAMPLES:
            target, machine = self.execute("SkyD8_HeartPrizeTag",
                                           wram(crystals=crystals, extra={0x0403: 0x7F}))
            self.assertEqual((target, machine.writes, machine.sp), ("$01C74D", {}, STACK_TOP))

    def test_heart_tag_sky_spawns_crystal_once_in_both_worlds(self):
        for world in (0x00, 0x40):
            for crystals in (0x00, 0x7F):
                with self.subTest(world=world, crystals=crystals):
                    target, machine = self.execute(
                        "SkyD8_HeartPrizeTag", wram(crystals=crystals, world=world))
                    self.assertEqual(target, "$01C742")
                    self.assertEqual(machine.a & 0xFF, 0x06)
                    self.assertEqual(machine.writes, {0x04C2: 0x80})
                    self.assertEqual((machine.sp, machine.memory[STACK_TOP]),
                                     (STACK_TOP - 1, 0x01), "native PHA of $0E")
                    self.assertFalse({0x7EF3CA, 0x7EF374} & set(machine.reads))
                    self.assertFalse(set(range(0x02A1A4, 0x02A1B2)) & set(machine.reads))

    def test_heart_tag_sky_owned_deletes_tag_without_spawn(self):
        for world in (0x00, 0x40):
            for crystals in (0x80, 0xFF):
                target, machine = self.execute("SkyD8_HeartPrizeTag",
                                               wram(crystals=crystals, world=world))
                self.assertEqual((target, machine.writes, machine.sp),
                                 ("$01C749", {}, STACK_TOP))

    def test_heart_tag_room_0196_is_not_sky(self):
        target, machine = self.execute("SkyD8_HeartPrizeTag", wram(room=0x0196))
        self.assertEqual(target, "$01C70E")
        self.assertEqual((machine.a & 0xFF, machine.z), (0x80, False))
        target, machine = self.execute("SkyD8_HeartPrizeTag",
                                       wram(room=0x0196, extra={0x0403: 0x00}))
        self.assertEqual((target, machine.z), ("$01C70E", True))

    def test_heart_tag_refuses_every_index_past_the_table(self):
        for dungeon in range(0x100):
            with self.subTest(dungeon=dungeon):
                target, machine = self.execute("SkyD8_HeartPrizeTag",
                                               wram(room=0x0090, dungeon=dungeon))
                if dungeon >> 1 < len(PRIZE_CHECKS):
                    self.assertEqual((target, machine.a & 0xFF, machine.z),
                                     ("$01C70E", 0x80, False))
                else:
                    self.assertEqual(target, "$01C74D")
                self.assertEqual((machine.writes, machine.sp), ({}, STACK_TOP))

    # --- RoomTag_PrizeTriggerDoorDoor ($01C508) -----------------------------

    def test_prize_door_sky_opens_only_when_owned(self):
        for world in (0x00, 0x40):
            for crystals in CRYSTAL_SAMPLES:
                target, machine = self.execute("SkyD8_PrizeTriggerDoor",
                                               wram(crystals=crystals, world=world))
                expected = "$01C529" if crystals & SKY_BIT else "$01C53E"
                self.assertEqual((target, machine.writes), (expected, {}))
                self.assertFalse({0x7EF3CA, 0x7EF374} & set(machine.reads))

    def test_prize_door_legacy_indices_and_refusals(self):
        for dungeon in range(0x100):
            target, machine = self.execute("SkyD8_PrizeTriggerDoor",
                                           wram(room=0x005A, dungeon=dungeon))
            if dungeon >> 1 < len(PRIZE_CHECKS):
                self.assertEqual((target, machine.x), ("$01C50D", dungeon >> 1))
            else:
                self.assertEqual(target, "$01C53E")
        target, machine = self.execute("SkyD8_PrizeTriggerDoor",
                                       wram(room=0x0196, crystals=0x80))
        self.assertEqual((target, machine.x), ("$01C50D", 0x08))

    # --- Ancilla3E_RisingCrystal collector ($08CC3B) ------------------------

    def collect(self, memory, ancilla=0x03):
        """Gateway plus the native $08CC40-$08CC48 OR/store it continues into."""
        target, machine = self.execute("SkyD8_CrystalCollector", memory,
                                       stack=(ancilla,), x=ancilla)
        crystals = machine.memory[CRYSTALS]
        if target == "$08CC40":
            index = machine.x
            mask = PRIZE_CHECKS[index] if index < len(PRIZE_CHECKS) else OVERREAD_BYTE
            crystals |= mask
        elif target == "$08CC48":
            crystals = machine.acc()
        return target, machine, crystals

    def test_collector_sky_commits_only_bit7_through_native_store(self):
        for world in (0x00, 0x40):
            for crystals in (0x00, 0x7F):
                target, machine, after = self.collect(wram(crystals=crystals, world=world))
                self.assertEqual(target, "$08CC48")
                self.assertEqual(after, crystals | SKY_BIT)
                self.assertEqual(machine.writes, {}, "the $08CC48 owner stores Crystals")
                self.assertEqual((machine.sp, machine.memory[STACK_TOP]), (STACK_TOP - 1, 0x03))
                self.assertFalse(set(range(0x02A1A4, 0x02A1B2)) & set(machine.reads))

    def assert_refused(self, machine, ancilla, water=False):
        self.assertEqual((machine.x, machine.sp), (ancilla, STACK_TOP), "PHX balanced")
        self.assertEqual(machine.writes, {0x005D: 0x04 if water else 0x00, 0x02D8: 0,
                                          0x02DA: 0, 0x037B: 0, 0x02E9: 0, 0x02E4: 0})

    def test_collector_refuses_repeat_sky_award(self):
        for crystals in (0x80, 0xFF):
            target, machine, after = self.collect(wram(crystals=crystals), ancilla=0x04)
            self.assertEqual((target, after), ("$08C453", crystals))
            self.assert_refused(machine, 0x04)
        target, machine, _ = self.collect(wram(crystals=0x80, extra={0x0345: 0x01}), 0x02)
        self.assert_refused(machine, 0x02, water=True)

    def test_collector_refuses_fortress_and_every_index_past_the_table(self):
        for dungeon in range(len(PRIZE_CHECKS) * 2, 0x100):
            with self.subTest(dungeon=dungeon):
                target, machine, after = self.collect(
                    wram(room=0x0096 + 0x100, dungeon=dungeon, crystals=0x00), ancilla=0x05)
                self.assertEqual((target, after), ("$08C453", 0x00))
                self.assert_refused(machine, 0x05)
                self.assertNotIn(0x0011, machine.writes)

    def test_collector_legacy_masks_match_native(self):
        for room in (0x005A, 0x0196):
            for dungeon, mask in {**LEGACY_CRYSTAL_IDS, **PENDANT_IDS}.items():
                for crystals in CRYSTAL_SAMPLES:
                    with self.subTest(room=room, dungeon=dungeon, crystals=crystals):
                        target, machine, after = self.collect(
                            wram(room=room, dungeon=dungeon, crystals=crystals))
                        self.assertEqual((target, machine.x), ("$08CC40", dungeon >> 1))
                        self.assertEqual(after, crystals | mask)
                        self.assertEqual(machine.sp, STACK_TOP - 1)
                        self.assertEqual(machine.writes, {})

    def test_legacy_d5_d7_bits_and_sky_bit_compose(self):
        _, _, after = self.collect(wram(room=0x00DE, dungeon=0x12, crystals=0x80))
        self.assertEqual(after, 0x84)
        _, _, after = self.collect(wram(room=0x00A4, dungeon=0x18, crystals=0xF7))
        self.assertEqual(after, 0xFF)
        _, _, after = self.collect(wram(crystals=0x77))
        self.assertEqual(after, 0xF7)

    # --- BuildCrystalCutsceneTilemap ($029897) ------------------------------

    def test_tilemap_sky_uses_link_quadrant_family(self):
        seen = set()
        for right in (0, 1):
            for bottom in (0, 1):
                memory = wram(extra={0x0023: 0x0C | right, 0x0024: 0x00,
                                     0x0021: 0x12 | bottom, 0x0022: 0x77, 0x0008: 0xEE})
                target, machine = self.execute("SkyD8_CrystalTilemap", memory, m=16, x=0x33)
                offset = machine.acc()
                self.assertEqual(target, "$0298A7")
                self.assertEqual(offset, 0x0618 + 0x40 * right + 0x1000 * bottom)
                self.assertEqual(set(machine.writes), {0x0008, 0x0009})
                self.assertFalse(set(range(0x02895C, 0x02896C)) & set(machine.reads))
                seen.add(offset)
        self.assertTrue(NATIVE_TILEMAP_OFFSETS < seen)
        last_word = max(seen) + 3 * 0x80 + 7 * 2 + 0x200
        self.assertLess(last_word + 1, 0x2000, "block stays inside the $7E4000 BG1 buffer")

    def test_tilemap_legacy_rooms_keep_native_search(self):
        for room in (0x0196, 0x0090, 0x00DE, 0x005A):
            target, machine = self.execute("SkyD8_CrystalTilemap", wram(room=room), m=16)
            self.assertEqual((target, machine.x, machine.acc(), machine.writes),
                             ("$02989B", 0x0E, room, {}))

    # --- PrepareDungeonExitFromBossFight ($00F959) --------------------------

    def test_boss_exit_sky_selects_room_90_crystal_victory(self):
        target, machine = self.execute("SkyD8_BossExit", wram())
        self.assertEqual(target, "$00F96A")
        self.assertEqual(machine.writes, {0x00A0: 0x90})
        self.assertEqual((machine.memory[0x00A1], machine.acc()), (0x00, 0x90))
        self.assertNotIn(machine.acc(), (0x20, 0x0D), "not an Agahnim exit")
        self.assertGreaterEqual(machine.x, 0x03, "CPX #$03 at $00F9BF -> module $16")
        self.assertFalse(set(range(0x00F92D, 0x00F945)) & set(machine.reads))

    def test_boss_exit_legacy_keeps_native_search(self):
        for room in (0x0196, 0x00DE, 0x0020):
            target, machine = self.execute("SkyD8_BossExit", wram(room=room))
            self.assertEqual((target, machine.x, machine.acc(), machine.writes),
                             ("$00F95D", 0x0C, room & 0xFF, {}))

    # --- Crystal maiden ($1ECD8B, $1ECE1B, $1ECECE) -------------------------

    def test_maiden_follower_gfx_skipped_for_sky_only(self):
        target, machine = self.execute("SkyD8_MaidenFollowerGfx", wram(), y=0x07)
        self.assertEqual((target, machine.writes, machine.y), ("$1ECDAD", {}, 0x07))
        for room, dungeon in ((0x0196, 0x18), (0x00A4, 0x18), (0x00DE, 0x12)):
            target, machine = self.execute("SkyD8_MaidenFollowerGfx",
                                            wram(room=room, dungeon=dungeon), y=0x07)
            self.assertEqual((target, machine.z, machine.y),
                             ("$1ECD90", dungeon == 0x18, 0x07))

    def test_maiden_never_drawn_for_sky(self):
        for stage in range(9):
            memory = wram(extra={0x0D80 + 0x02: stage})
            target, machine = self.execute("SkyD8_MaidenDraw", memory, x=0x02)
            self.assertEqual((target, machine.writes), ("$1ECE26", {}))
            target, machine = self.execute("SkyD8_MaidenDraw",
                                           wram(room=0x0196, extra={0x0D82: stage}), x=0x02)
            self.assertEqual((target, machine.c), ("$1ECE20", stage >= 3))

    def test_maiden_speech_sky_goes_to_kick_out_without_text_or_map_icon(self):
        target, machine = self.execute("SkyD8_MaidenSpeech",
                                       wram(extra={0x0D85: 0x05, 0x7EF3C7: 0x03}), x=0x05)
        self.assertEqual((target, machine.writes), ("$1ECF17", {0x0D85: 0x08}))
        self.assertNotIn(0x040C, machine.reads, "no D3 message index")
        target, machine = self.execute("SkyD8_MaidenSpeech", wram(room=0x0196), x=0x05)
        self.assertEqual((target, machine.acc(), machine.c, machine.writes),
                         ("$1ECED2", 0x10, True, {}))


class SkyAwardSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text()
        cls.lines = code_lines(cls.text)
        cls.asserts = {}
        for line in cls.lines:
            match = re.fullmatch(r"assert read([124])\(\$([0-9A-F]{6})(?:\+\$([0-9A-F]+))?\) == "
                                 r"\$([0-9A-F]+)(?: \|\| .*)?, \".+\"", line)
            if match:
                address = int(match.group(2), 16) + int(match.group(3) or "0", 16)
                cls.asserts[address] = (int(match.group(1)), int(match.group(4), 16))

    def asserted_bytes(self):
        found = {}
        for address, (size, value) in self.asserts.items():
            for offset in range(size):
                found[address + offset] = (value >> (8 * offset)) & 0xFF
        return found

    def test_each_hook_is_bounded_and_annotated(self):
        raw = self.text.splitlines()
        for address, (name, preimage, m, x) in HOOKS.items():
            size = len(preimage) // 2
            with self.subTest(site=f"${address:06X}"):
                index = next(i for i, line in enumerate(self.lines)
                             if line == f"org ${address:06X} : JML {name}")
                annotation = raw[index].split(";", 1)[1]
                for field in (f"name={name}", "kind=jml", f"target={name}",
                              f"expected_m={m}", f"expected_x={x}", f"expected_exit_m={m}",
                              f"expected_exit_x={x}", f"protected_size={size}"):
                    self.assertIn(field, annotation)
                tail = self.lines[index + 1:index + 3]
                if size == 5:
                    self.assertEqual(tail, ["NOP", f"assert pc() == ${address + 5:06X}"])
                else:
                    self.assertEqual(tail[0], f"assert pc() == ${address + 4:06X}")

    def test_preimage_asserts_cover_every_overwritten_byte(self):
        found = self.asserted_bytes()
        for address, (_, preimage, _, _) in HOOKS.items():
            expected = bytes.fromhex(preimage)
            for offset, byte in enumerate(expected):
                self.assertEqual(found.get(address + offset), byte, f"${address + offset:06X}")

    def test_every_continuation_is_guarded_by_a_read_assert(self):
        guarded = set(self.asserted_bytes())
        for name, exits in EXITS.items():
            program, _ = parse(routine(name))
            jumps = {operand for mnemonic, _, operand in program if mnemonic == "JML"}
            self.assertEqual(jumps, exits, name)
            for operand in jumps:
                self.assertIn(int(operand[1:], 16), guarded, f"{name} -> {operand}")
        self.assertIn(0x08CC3A, self.asserts, "native PHX before the collector")

    def test_exit_binding_is_guarded(self):
        self.assertEqual(self.asserts[0x02DD8A + 0x84], (2, 0x0090))
        self.assertEqual(self.asserts[0x02DE28 + 0x42], (1, 0x7A))

    def test_store_site_and_tables_stay_with_their_owners(self):
        orgs = [line for line in self.lines if line.startswith("org ")]
        self.assertEqual(sorted(int(line[5:11], 16) for line in orgs), sorted(HOOKS))
        owners = []
        for path in ROOT.rglob("*.asm"):
            for line in code_lines(path.read_text(errors="replace")):
                if re.match(r"org \$08CC4[4-9A-B]\b", line):
                    owners.append((path.relative_to(ROOT).as_posix(), line))
        self.assertEqual(owners, [("Sprites/Bosses/kydrog_boss.asm", "org $08CC48")])
        for line in self.lines:
            for mnemonic in ("STA", "STZ", "STY", "STX"):
                self.assertFalse(line.startswith(f"{mnemonic}.l"), line)

    def test_no_feature_flag_and_bank_2c_stream_placement(self):
        self.assertFalse([line for line in self.lines
                          if re.match(r"(if|else|endif)\b", line) or "!ENABLE" in line])
        self.assertFalse([line for line in self.lines if line.startswith("org $2C")])
        self.assertEqual([line for line in self.lines if line][-1],
                         "assert pc() <= $2CFD00")
        directives = [line for line in self.lines if line in ("pushpc", "pullpc")]
        self.assertEqual(directives, ["pushpc", "pullpc"])
        include = code_lines(DUNGEONS.read_text())
        position = include.index('incsrc "Dungeons/sky_d8_award.asm"')
        self.assertEqual(include[position - 2], 'incsrc "Collision/water_collision.asm"')
        self.assertLess(position, include.index('print "End of dungeons.asm               ", pc'))

    def test_generator_registers_each_gateway(self):
        found = {entry.address: entry for entry in scan_hooks(ROOT) if entry.address in HOOKS}
        self.assertEqual(set(found), set(HOOKS))
        for address, (name, preimage, m, x) in HOOKS.items():
            entry = found[address]
            self.assertEqual((entry.name, entry.kind, entry.target, entry.module),
                             (name, "jml", name, "Dungeons"))
            self.assertEqual((entry.expected_m, entry.expected_x, entry.expected_exit_m,
                              entry.expected_exit_x, entry.protected_size),
                             (m, x, m, x, len(preimage) // 2))

    @unittest.skipUnless(os.environ.get("OOS_SKY_AWARD_ROM"), "set OOS_SKY_AWARD_ROM")
    def test_asserts_hold_in_a_real_rom(self):
        data = Path(os.environ["OOS_SKY_AWARD_ROM"]).read_bytes()
        if len(data) % 0x8000 == 0x200:
            data = data[0x200:]

        def pc(address):
            return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)

        hooked = {address + offset for address, (_, image, _, _) in HOOKS.items()
                  for offset in range(len(image) // 2)}
        patched = data[pc(0x01C508)] == 0x5C
        for address, byte in self.asserted_bytes().items():
            if patched and address in hooked:
                continue
            with self.subTest(address=f"${address:06X}"):
                actual = data[pc(address)]
                if address == 0x08CC48:
                    self.assertIn(actual, (0x8F, 0x22))
                else:
                    self.assertEqual(actual, byte)
        self.assertEqual(list(data[pc(0x02A1A4):pc(0x02A1A4) + 14]),
                         PRIZE_CHECKS + [OVERREAD_BYTE])
        self.assertNotIn(0x96, data[pc(0x00F92D):pc(0x00F92D) + 12])
        rooms = data[pc(0x02895C):pc(0x02895C) + 16]
        self.assertNotIn(0x0096, [rooms[i] | rooms[i + 1] << 8 for i in range(0, 16, 2)])


if __name__ == "__main__":
    unittest.main()
