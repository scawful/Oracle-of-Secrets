"""Equipment menu selection sound contract.

Executes the assembly text of Menu_Equipment_Select, its Menu_Page3_ToggleRing
delegate and the Menu_Equipment_Move accept block on a small 8-bit model, for
every cursor slot, A/Y/other input, ownership and worn-ring state. SFX3 is
queued via $012F: $20 is the menu cursor sound, $22 is Boss dying / Deleting
file (Core/sfx.asm). Menu_Equipment_Owned, RingMenu_StoreRingToSlotStack and
MagicBag_ConsumeItem are stubs. No build, no emulator.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EQUIPMENT = ROOT / "Menu" / "menu_equipment.asm"
PAGE3 = ROOT / "Menu" / "menu_page3.asm"
SFX = ROOT / "Core" / "sfx.asm"
FLAGS = ROOT / "Config" / "feature_flags.asm"
MENU_CURSOR, BOSS_DYING, ERROR = 0x20, 0x22, 0x3C
SOUND_PORTS = ("$012E", "$012F")
INPUTS = [(f6, f4) for f6 in (0x00, 0x80, 0x40, 0x30) for f4 in (0x00, 0x40, 0x80, 0x3F)]


def feature_flags():
    text = FLAGS.read_text(encoding="utf-8")
    return {name: int(value) for name, value in re.findall(r"^!(\w+)\s*=\s*(\d+)", text, re.M)}


def routine_lines(text, name, flags):
    match = re.search(rf"^{name}:\s*\n\{{\n(.*?)^\}}", text, re.M | re.S)
    if not match:
        raise AssertionError(f"{name} not found")
    lines, active = [], []
    for raw in match.group(1).splitlines():
        code = raw.split(";", 1)[0].strip()
        if not code:
            continue
        condition = re.fullmatch(r"if !(\w+) == (\d+)", code)
        if condition:
            active.append(flags[condition.group(1)] == int(condition.group(2)))
        elif code == "else":
            active[-1] = not active[-1]
        elif code == "endif":
            active.pop()
        elif all(active):
            lines.extend(part.strip() for part in code.split(" : "))
    return lines


class Menu:
    def __init__(self, routines, memory, owned):
        self.routines, self.memory, self.owned = routines, dict(memory), owned
        self.a, self.n, self.z, self.c = 0, False, False, False
        self.stack, self.sounds, self.calls = [], [], []

    def nz(self, value):
        self.n, self.z = bool(value & 0x80), value == 0

    def value(self, arg):
        immediate = re.fullmatch(r"#\$([0-9A-F]{2})", arg)
        return int(immediate.group(1), 16) if immediate else self.memory.get(arg, 0)

    def write(self, arg, value):
        self.memory[arg] = value
        if arg in SOUND_PORTS:
            self.sounds.append((arg, value))

    def jsr(self, name):
        if name == "Menu_Equipment_Owned":
            self.a = self.owned.get(self.a, 0)
            self.nz(self.a)
        elif name == "MagicBag_ConsumeItem":
            self.calls.append((name, self.memory["$020B"]))
        elif name == "RingMenu_StoreRingToSlotStack":
            self.calls.append((name, self.a))
        else:
            raise AssertionError(f"unexpected JSR {name}")

    def run(self, name, label=None):
        lines = self.routines[name]
        labels = {line: i for i, line in enumerate(lines) if line.startswith(".")}
        pc = labels[label] if label else 0
        for _ in range(200):
            parts = lines[pc].split(None, 1)
            pc += 1
            if parts[0].startswith("."):
                continue
            op, arg = parts[0].split(".")[0], parts[1] if len(parts) > 1 else ""
            branches = {"BRA": True, "BEQ": self.z, "BNE": not self.z, "BMI": self.n,
                        "BCS": self.c, "BCC": not self.c}
            if op == "RTS":
                return
            if op in branches:
                if branches[op]:
                    pc = labels[arg]
            elif op == "JMP":
                lines = self.routines[arg]
                labels = {line: i for i, line in enumerate(lines) if line.startswith(".")}
                pc = 0
            elif op == "JSR":
                self.jsr(arg)
            elif op in ("LDA", "PLA"):
                self.a = self.stack.pop() if op == "PLA" else self.value(arg)
                self.nz(self.a)
            elif op == "STA":
                self.write(arg, self.a)
            elif op == "STZ":
                self.write(arg, 0)
            elif op == "PHA":
                self.stack.append(self.a)
            elif op == "BIT":
                operand = self.value(arg)
                self.z = (self.a & operand) == 0
                if not arg.startswith("#"):
                    self.n = bool(operand & 0x80)
            elif op == "CMP":
                operand = self.value(arg)
                self.c = self.a >= operand
                self.nz((self.a - operand) & 0xFF)
            elif op == "SEC":
                self.c = True
            elif op == "SBC":
                result = self.a - self.value(arg) - (0 if self.c else 1)
                self.c, self.a = result >= 0, result & 0xFF
                self.nz(self.a)
            elif op == "INC" and not arg:
                self.a = (self.a + 1) & 0xFF
                self.nz(self.a)
            elif op == "SEP" and arg == "#$30":
                continue
            else:
                raise AssertionError(f"opcode {lines[pc - 1]} not modeled")
        raise AssertionError(f"{name} did not return")


def ring_states(ring, one_ring):
    other = [r for r in range(2, 8) if r != ring]
    if one_ring:
        return [(0, 0, 0), (ring, 0, 0), (other[0], 0, 0)]
    return [(0, 0, 0), (ring, 0, 0), (0, ring, 0), (0, 0, ring), tuple(other[:3])]


def expected(slot, f6, f4, owned, rings, one_ring):
    """Returns (sound writes, changed selection state, stub calls)."""
    if not (f6 & 0x80 or f4 & 0x40):
        return [], {}, []
    if slot >= 0x18 or not owned:
        return [("$012E", ERROR)], {}, []
    if slot < 0x06:
        return [("$012F", MENU_CURSOR)], {"BoundMask": slot + 1, "$0207": 0x20}, []
    if slot < 0x0C:
        ring = slot - 4
        if ring in rings:
            return [("$012F", MENU_CURSOR)], {f"RingSlot{rings.index(ring) + 1}": 0, "$0207": 0x00}, []
        if one_ring:
            return [("$012F", MENU_CURSOR)], {"RingSlot1": ring, "$0207": 0x20}, []
        return [("$012F", MENU_CURSOR)], {"$0207": 0x20}, [("RingMenu_StoreRingToSlotStack", ring)]
    if slot < 0x12:
        song = slot - 0x0B
        state = {"CurrentSong": song, "SavedOcarinaSong": song, "$0202": 0x0D, "$0207": 0x20}
        return [("$012F", MENU_CURSOR)], state, []
    if not f6 & 0x80:
        return [], {}, []
    return [], {}, [("MagicBag_ConsumeItem", slot - 0x12)]


def check_select(test, equipment_text, page3_text, flags):
    """Runs every case through Menu_Equipment_Select; returns the case count."""
    routines = {name: routine_lines(text, name, flags) for text, name in (
        (equipment_text, "Menu_Equipment_Select"), (page3_text, "Menu_Page3_ToggleRing"))}
    one_ring = flags["ENABLE_ONE_RING"] == 1
    cases = 0
    for slot in list(range(0x18)) + [0xFF]:
        ownership = (True,) if 0x12 <= slot < 0x18 else (False,) if slot >= 0x18 else (False, True)
        for owned in ownership:
            rings_list = ring_states(slot - 4, one_ring) if 0x06 <= slot < 0x0C else [(0, 0, 0)]
            for rings in rings_list:
                for f6, f4 in INPUTS:
                    memory = {"$F6": f6, "$F4": f4, "$020B": slot, "$0207": 0x06,
                              "BoundMask": 0, "CurrentSong": 0, "SavedOcarinaSong": 0,
                              "$0202": 0x03, "RingSlot1": rings[0], "RingSlot2": rings[1],
                              "RingSlot3": rings[2]}
                    menu = Menu(routines, memory, {slot: 1} if owned else {})
                    menu.run("Menu_Equipment_Select")
                    changed = {k: v for k, v in menu.memory.items()
                               if memory.get(k) != v and k not in SOUND_PORTS}
                    label = (f"slot=${slot:02X} owned={owned} rings={rings} "
                             f"F6=${f6:02X} F4=${f4:02X} one_ring={one_ring}")
                    test.assertEqual((menu.sounds, changed, menu.calls),
                                     expected(slot, f6, f4, owned, rings, one_ring), label)
                    test.assertNotIn(("$012F", BOSS_DYING), menu.sounds, label)
                    cases += 1
    return cases


class EquipmentMenuSfxContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.equipment = EQUIPMENT.read_text(encoding="utf-8")
        cls.page3 = PAGE3.read_text(encoding="utf-8")
        cls.flags = feature_flags()

    def test_sound_ids_and_equipment_call_chain(self):
        sfx = SFX.read_text(encoding="utf-8")
        self.assertRegex(sfx, r"SFX3 - queued via \$012F")
        self.assertRegex(sfx, r"SFX3\.20 .*Menu / Text cursor moved")
        self.assertRegex(sfx, r"SFX3\.22 .*Boss dying / Deleting file")
        self.assertEqual(self.flags["ENABLE_EQUIPMENT_MENU"], 1)
        self.assertEqual(routine_lines(self.page3, "Menu_Page3_Select", self.flags)[0],
                         "JMP Menu_Equipment_Select")
        self.assertEqual(routine_lines(self.page3, "Menu_Page3_Move", self.flags)[0],
                         "JMP Menu_Equipment_Move")
        self.assertIn("JMP Menu_Page3_ToggleRing",
                      routine_lines(self.equipment, "Menu_Equipment_Select", self.flags))

    def test_select_active_flags_every_slot_input_and_ring_state(self):
        check_select(self, self.equipment, self.page3, self.flags)

    def test_select_multi_ring_delegate(self):
        flags = dict(self.flags, ENABLE_ONE_RING=0)
        check_select(self, self.equipment, self.page3, flags)

    def test_move_accept_plays_cursor_sound(self):
        routines = {"Menu_Equipment_Move": routine_lines(
            self.equipment, "Menu_Equipment_Move", self.flags)}
        for target in range(0x18):
            menu = Menu(routines, {"$02": target, "$020B": 0xFF, "$0207": 0x06}, {})
            menu.run("Menu_Equipment_Move", ".accept")
            self.assertEqual(menu.sounds, [("$012F", MENU_CURSOR)])
            self.assertEqual((menu.memory["$020B"], menu.memory["$0207"]), (target, 0))

    def test_pre_fix_boss_sound_fails_contract(self):
        mutants = [
            ("mask/song", r"(\.sound\n\s*LDA\.b #\$)20( : STA\.w \$012F)", self.flags),
            ("one-ring wear", r"(\.wear\n\s*STA\.l RingSlot1\n\s*LDA\.b #\$)20( : STA\.w \$012F)",
             self.flags),
            ("multi-ring on", r"(\.on\n\s*JSR RingMenu_StoreRingToSlotStack\n\s*SEP #\$30\n"
             r"\s*LDA\.b #\$)20( : STA\.w \$012F)", dict(self.flags, ENABLE_ONE_RING=0)),
        ]
        for name, pattern, flags in mutants:
            with self.subTest(name):
                equipment, page3 = self.equipment, self.page3
                if name == "mask/song":
                    equipment, count = re.subn(pattern, r"\g<1>22\2", equipment)
                else:
                    page3, count = re.subn(pattern, r"\g<1>22\2", page3)
                self.assertEqual(count, 1)
                with self.assertRaises(AssertionError):
                    check_select(self, equipment, page3, flags)


if __name__ == "__main__":
    unittest.main()
