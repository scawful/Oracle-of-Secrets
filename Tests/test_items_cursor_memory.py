"""Items page cursor memory ($0202 / MenuFlow_ItemsCursor) contract tests.

Verifies Core/symbols.asm, Menu/menu.asm, Menu/menu_select_item.asm, and
Menu/menu_item_bindings.asm structural invariants and executes the parsed ASM
of Menu_Bindings_Open, Menu_Bindings_Close, Menu_Bindings_DrawMarkers, and
ItemBindings_ValidateY on a compact 8/16-bit 65816 model. No build, no emulator.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ROOT / "Core" / "symbols.asm"
MENU = ROOT / "Menu" / "menu.asm"
SELECT_ITEM = ROOT / "Menu" / "menu_select_item.asm"
BINDINGS = ROOT / "Menu" / "menu_item_bindings.asm"
ITEM_BINDINGS = ROOT / "Items" / "item_bindings.asm"
FLAGS = ROOT / "Config" / "feature_flags.asm"


def load_flags(overrides: dict[str, int] | None = None) -> dict[str, int]:
    text = FLAGS.read_text(encoding="utf-8")
    flags = {name: int(val) for name, val in re.findall(r"^!(\w+)\s*=\s*(\d+)", text, re.M)}
    if overrides:
        flags.update(overrides)
    return flags


def eval_cond(expr: str, flags: dict[str, int]) -> bool:
    clauses = [c.strip() for c in expr.split("||")]
    for clause in clauses:
        m = re.fullmatch(r"!(\w+)\s*==\s*(\d+)", clause)
        if not m:
            raise AssertionError(f"Unsupported ASM condition syntax: {expr!r}")
        if flags[m.group(1)] == int(m.group(2)):
            return True
    return False


def parse_routine(text: str, name: str, flags: dict[str, int]) -> list[str]:
    match = re.search(rf"^{name}:\s*\n\{{\n(.*?)^\}}", text, re.M | re.S)
    if not match:
        raise AssertionError(f"{name} not found")
    lines: list[str] = []
    active: list[bool] = []
    for raw in match.group(1).splitlines():
        code = raw.split(";", 1)[0].strip()
        if not code:
            continue
        if code.startswith("if "):
            active.append(eval_cond(code[3:].strip(), flags))
        elif code == "else":
            active[-1] = not active[-1]
        elif code == "endif":
            active.pop()
        elif all(active):
            for part in code.split(" : "):
                part = part.strip()
                if part:
                    lines.append(part)
    return lines


def parse_db_bytes(text: str, start_label: str, end_label: str, flags: dict[str, int]) -> list[int]:
    m = re.search(rf"^{start_label}:\s*\n(.*?)^{end_label}:", text, re.M | re.S)
    if not m:
        raise AssertionError(f"Table {start_label}..{end_label} not found")
    active: list[bool] = []
    out: list[int] = []
    sym_offsets = {
        "PortalRodOwned": 0xA6,
        "GoldstarOwned": 0xA9,
        "ByrnaOwned": 0xAC,
        "BombchuOwned": 0xAD,
        "SwitchHookOwned": 0xAE,
        "GaroMaskOwned": 0xAF,
    }
    for raw in m.group(1).splitlines():
        code = raw.split(";", 1)[0].strip()
        if not code:
            continue
        if code.startswith("if "):
            active.append(eval_cond(code[3:].strip(), flags))
        elif code == "else":
            active[-1] = not active[-1]
        elif code == "endif":
            active.pop()
        elif all(active) and code.startswith("db "):
            for tok in code[3:].split(","):
                tok = tok.strip()
                if tok.endswith("&$FF"):
                    out.append(sym_offsets[tok[:-4].strip()])
                else:
                    out.append(int(tok.lstrip("$"), 16))
    return out


class CursorModel:
    ADDR_MAP = {
        "$0202": 0x7E0202,
        "$0207": 0x7E0207,
        "ItemBindingMenuY": 0x7E02B7,
        "ItemBindingSavedVersion": 0x7EF3B9,
        "ItemBindingSavedY": 0x7EF3BA,
        "ItemBindingSavedX": 0x7EF3BB,
        "MenuFlow_ItemsCursor": 0x7E02BE,
    }

    def __init__(self, flags: dict[str, int]):
        self.flags = flags
        bind_txt = BINDINGS.read_text(encoding="utf-8")
        item_txt = ITEM_BINDINGS.read_text(encoding="utf-8")
        self.routines = {
            "Menu_Bindings_Open": parse_routine(bind_txt, "Menu_Bindings_Open", flags),
            "Menu_Bindings_Close": parse_routine(bind_txt, "Menu_Bindings_Close", flags),
            "Menu_Bindings_DrawMarkers": parse_routine(bind_txt, "Menu_Bindings_DrawMarkers", flags),
        }
        # ItemBindings_ValidateY shares ItemBindings_CheckOwner with ItemBindings_Validate.
        m = re.search(
            r"^ItemBindings_ValidateY:\s*\n\{\n(.*?)^\}",
            item_txt,
            re.M | re.S,
        )
        if not m:
            raise AssertionError("ItemBindings_ValidateY not found")
        self.validate_y_lines: list[str] = []
        for raw in m.group(1).splitlines():
            code = raw.split(";", 1)[0].strip()
            if code:
                self.validate_y_lines.extend(p.strip() for p in code.split(" : ") if p.strip())

        self.owner_table = parse_db_bytes(item_txt, "ItemBindings_Owner", "ItemBindings_Owner_End", flags)
        self.max_table = parse_db_bytes(item_txt, "ItemBindings_Max", "ItemBindings_ActionTable", flags)
        assert len(self.owner_table) == len(self.max_table)

        self.mem: dict[int, int] = {}
        self.a = 0
        self.x = 0
        self.y = 0
        self.m8 = True
        self.x8 = True
        self.c = False
        self.z = False
        self.n = False
        self.stack: list[int] = []

    def r8(self, addr: int) -> int:
        return self.mem.get(addr, 0) & 0xFF

    def w8(self, addr: int, val: int) -> None:
        self.mem[addr] = val & 0xFF

    def r16(self, addr: int) -> int:
        return self.r8(addr) | (self.r8(addr + 1) << 8)

    def w16(self, addr: int, val: int) -> None:
        self.w8(addr, val & 0xFF)
        self.w8(addr + 1, (val >> 8) & 0xFF)

    def set_nz(self, val: int, bits: int) -> None:
        mask = (1 << bits) - 1
        sign = 1 << (bits - 1)
        v = val & mask
        self.z = v == 0
        self.n = bool(v & sign)

    def p_byte(self) -> int:
        return (int(self.m8) << 5) | (int(self.x8) << 4) | (int(self.n) << 7) | (int(self.z) << 1) | int(self.c)

    def set_p_byte(self, val: int) -> None:
        self.m8 = bool(val & 0x20)
        self.x8 = bool(val & 0x10)
        self.n = bool(val & 0x80)
        self.z = bool(val & 0x02)
        self.c = bool(val & 0x01)

    def resolve_addr(self, arg: str) -> int:
        if arg in self.ADDR_MAP:
            return self.ADDR_MAP[arg]
        if arg.startswith("$"):
            val = int(arg[1:], 16)
            return (0x7E0000 | val) if val < 0x2000 else val
        raise AssertionError(f"Unknown symbol/address: {arg!r}")

    def exec_lines(self, lines: list[str], stop_at_draw_clear: bool = False) -> None:
        labels = {line.rstrip(":"): i for i, line in enumerate(lines)
                  if line.startswith(".") or line.endswith(":")}
        pc = 0
        for _ in range(400):
            line = lines[pc]
            pc += 1
            if line.startswith(".") or line.endswith(":"):
                continue
            parts = line.split(None, 1)
            op = parts[0].split(".")[0]
            arg = parts[1].strip() if len(parts) > 1 else ""

            if op in ("RTL", "RTS"):
                return
            if op == "PHP":
                self.stack.append(self.p_byte())
            elif op == "PLP":
                self.set_p_byte(self.stack.pop())
            elif op == "SEP":
                v = int(arg.lstrip("#$"), 16)
                if v & 0x20:
                    self.m8 = True
                if v & 0x10:
                    self.x8 = True
                    self.x &= 0xFF
                    self.y &= 0xFF
            elif op == "REP":
                v = int(arg.lstrip("#$"), 16)
                if v & 0x20:
                    self.m8 = False
                if v & 0x10:
                    self.x8 = False
                if stop_at_draw_clear and line == "REP #$30":
                    return
            elif op == "PHA":
                if self.m8:
                    self.stack.append(self.a & 0xFF)
                else:
                    self.stack.append((self.a >> 8) & 0xFF)
                    self.stack.append(self.a & 0xFF)
            elif op == "PLA":
                if self.m8:
                    v = self.stack.pop()
                    self.a = (self.a & 0xFF00) | v
                    self.set_nz(v, 8)
                else:
                    lo = self.stack.pop()
                    hi = self.stack.pop()
                    self.a = (hi << 8) | lo
                    self.set_nz(self.a, 16)
            elif op == "PHX":
                if self.x8:
                    self.stack.append(self.x & 0xFF)
                else:
                    self.stack.append((self.x >> 8) & 0xFF)
                    self.stack.append(self.x & 0xFF)
            elif op == "PLX":
                if self.x8:
                    self.x = self.stack.pop()
                    self.set_nz(self.x, 8)
                else:
                    lo = self.stack.pop()
                    hi = self.stack.pop()
                    self.x = (hi << 8) | lo
                    self.set_nz(self.x, 16)
            elif op == "PHY":
                if self.x8:
                    self.stack.append(self.y & 0xFF)
                else:
                    self.stack.append((self.y >> 8) & 0xFF)
                    self.stack.append(self.y & 0xFF)
            elif op == "PLY":
                if self.x8:
                    self.y = self.stack.pop()
                    self.set_nz(self.y, 8)
                else:
                    lo = self.stack.pop()
                    hi = self.stack.pop()
                    self.y = (hi << 8) | lo
                    self.set_nz(self.y, 16)
            elif op == "TAX":
                assert self.x8
                self.x = self.a & 0xFF
                self.set_nz(self.x, 8)
            elif op == "SEC":
                self.c = True
            elif op == "CLC":
                self.c = False
            elif op == "JSR":
                if arg == "ItemBindings_ValidateY":
                    self.exec_lines(self.validate_y_lines)
                else:
                    raise AssertionError(f"Unexpected JSR {arg}")
            elif op == "LDA":
                bits = 8 if self.m8 else 16
                if arg.startswith("#$"):
                    val = int(arg[2:], 16)
                elif arg == "1,S":
                    val = self.stack[-1]
                elif arg.endswith(", X") or arg.endswith(",X"):
                    sym = arg.split(",")[0].strip()
                    if sym == "ItemBindings_Max":
                        val = self.max_table[self.x]
                    elif sym == "ItemBindings_Owner":
                        val = self.owner_table[self.x]
                    elif sym == "$7EF300":
                        val = self.r8(0x7EF300 + self.x)
                    else:
                        raise AssertionError(f"Unexpected indexed LDA {arg}")
                else:
                    addr = self.resolve_addr(arg)
                    val = self.r8(addr) if self.m8 else self.r16(addr)
                if self.m8:
                    self.a = (self.a & 0xFF00) | (val & 0xFF)
                else:
                    self.a = val & 0xFFFF
                self.set_nz(val, bits)
            elif op == "STA":
                addr = self.resolve_addr(arg)
                if self.m8:
                    self.w8(addr, self.a)
                else:
                    self.w16(addr, self.a)
            elif op == "CMP":
                bits = 8 if self.m8 else 16
                lhs = (self.a & 0xFF) if self.m8 else (self.a & 0xFFFF)
                if arg == "#ItemBindings_Owner_End-ItemBindings_Owner":
                    rhs = len(self.owner_table)
                elif arg.startswith("#$"):
                    rhs = int(arg[2:], 16)
                elif arg == "1,S":
                    rhs = self.stack[-1]
                else:
                    raise AssertionError(f"Unexpected CMP {arg}")
                diff = lhs - rhs
                self.c = lhs >= rhs
                self.set_nz(diff, bits)
            elif op == "BRA":
                pc = labels[arg]
            elif op == "BEQ":
                if self.z:
                    pc = labels[arg]
            elif op == "BNE":
                if not self.z:
                    pc = labels[arg]
            elif op == "BCS":
                if self.c:
                    pc = labels[arg]
            elif op == "BCC":
                if not self.c:
                    pc = labels[arg]
            else:
                raise AssertionError(f"Unhandled opcode: {line!r}")
        raise AssertionError("Instruction limit exceeded")

    def run(self, name: str, m8: bool = True, x8: bool = True) -> None:
        self.m8, self.x8 = m8, x8
        self.exec_lines(self.routines[name], stop_at_draw_clear=(name == "Menu_Bindings_DrawMarkers"))


class TestItemsCursorMemory(unittest.TestCase):
    def test_symbols_and_hooks(self):
        sym_text = SYMBOLS.read_text(encoding="utf-8")
        self.assertRegex(sym_text, r"(?m)^MenuFlow_ItemsCursor\s*=\s*\$7E02BE\b")
        self.assertIn("assert MenuFlow_ItemsCursor+1 <= $7E02C0", sym_text)

        menu_text = MENU.read_text(encoding="utf-8")
        m_init = re.search(r"^Menu_InitGraphics:\s*\n\{(.*?)^\}", menu_text, re.M | re.S)
        self.assertIsNotNone(m_init)
        body = m_init.group(1)
        pos_clean = body.index("STZ.w $020C")
        pos_open = body.index("JSL Menu_Bindings_Open")
        pos_inc = body.index("INC $0200")
        self.assertLess(pos_clean, pos_open)
        self.assertLess(pos_open, pos_inc)

        sel_text = SELECT_ITEM.read_text(encoding="utf-8")
        m_sel = re.search(r"^Menu_InitItemScreen:\s*\n\{(.*?)^\}", sel_text, re.M | re.S)
        self.assertIsNotNone(m_sel)
        self.assertGreaterEqual(m_sel.group(1).count("STA.l MenuFlow_ItemsCursor"), 2)

    def test_open_cold_boot_follows_y(self):
        m = CursorModel(load_flags())
        m.w8(0x7E0202, 0x01)
        m.w8(0x7EF340, 0x01)
        m.run("Menu_Bindings_Open", m8=False, x8=False)
        self.assertEqual(m.r8(0x7E02B7), 0x01)
        self.assertEqual(m.r8(0x7E0202), 0x01)
        self.assertEqual(m.r8(0x7E02BE), 0x00)
        self.assertFalse(m.m8)
        self.assertFalse(m.x8)

    def test_open_restores_owned_remembered_cursor_without_clobbering_y(self):
        m = CursorModel(load_flags())
        m.w8(0x7EF340, 0x02)  # Bow
        m.w8(0x7EF342, 0x01)  # Hookshot
        m.w8(0x7EF3AE, 0x01)  # Switch Hook ($1D)
        m.w8(0x7E0202, 0x01)  # Equipped Y = Bow
        m.w8(0x7E02BE, 0x1D)  # Last Items cursor = Switch Hook
        m.run("Menu_Bindings_Open", m8=False, x8=False)
        self.assertEqual(m.r8(0x7E02B7), 0x01)
        self.assertEqual(m.r8(0x7E0202), 0x1D)
        self.assertEqual(m.r8(0x7E02BE), 0x1D)
        self.assertEqual(m.stack, [])

        # Closing restores Y and leaves MenuFlow_ItemsCursor untouched.
        m.run("Menu_Bindings_Close", m8=False, x8=False)
        self.assertEqual(m.r8(0x7E0202), 0x01)
        self.assertEqual(m.r8(0x7EF3BA), 0x01)
        self.assertEqual(m.r8(0x7E02BE), 0x1D)

    def test_open_clears_unowned_or_invalid_remembered_cursor(self):
        cases = [
            ("unowned_hookshot", 0x03, {}),
            ("upgraded_hookshot_to_goldstar", 0x03, {0x7EF3A9: 1}),
            ("invalid_byrna_level", 0x1B, {0x7EF3AC: 2}),
            ("mask_deku_under_page3", 0x13, {0x7EF349: 1}),
            ("mask_stone_under_page3", 0x17, {0x7EF352: 1}),
            ("garo_mask", 0x1E, {0x7EF3AF: 1}),
            ("out_of_range", 0xFF, {}),
        ]
        for label, cursor, extra_sram in cases:
            with self.subTest(label):
                m = CursorModel(load_flags())
                m.w8(0x7EF340, 0x01)  # Bow owned
                for addr, val in extra_sram.items():
                    m.w8(addr, val)
                m.w8(0x7E0202, 0x01)
                m.w8(0x7E02BE, cursor)
                m.run("Menu_Bindings_Open")
                self.assertEqual(m.r8(0x7E02B7), 0x01)
                self.assertEqual(m.r8(0x7E0202), 0x01)
                self.assertEqual(m.r8(0x7E02BE), 0x00)
                self.assertEqual(m.stack, [])

    def test_mask_y_preserves_items_cursor_across_open_and_close(self):
        m = CursorModel(load_flags())
        m.w8(0x7EF342, 0x01)  # Hookshot owned
        m.w8(0x7EF349, 0x01)  # Deku Mask owned
        m.w8(0x7E0202, 0x13)  # Equipped Y = Deku Mask
        m.w8(0x7E02BE, 0x03)  # Remembered Items cursor = Hookshot
        m.run("Menu_Bindings_Open")
        self.assertEqual(m.r8(0x7E02B7), 0x13)
        self.assertEqual(m.r8(0x7E0202), 0x03)

        # Idempotent close (Menu_InitiateScrollDown + Menu_Exit both call Close).
        m.run("Menu_Bindings_Close")
        m.run("Menu_Bindings_Close")
        self.assertEqual(m.r8(0x7E0202), 0x13)
        self.assertEqual(m.r8(0x7EF3BA), 0x13)
        self.assertEqual(m.r8(0x7E02BE), 0x03)

    def test_draw_markers_records_cursor_and_keeps_widths(self):
        m = CursorModel(load_flags())
        m.w8(0x7E0202, 0x04)
        m.run("Menu_Bindings_DrawMarkers", m8=True, x8=True)
        self.assertEqual(m.r8(0x7E02BE), 0x04)
        self.assertFalse(m.m8)
        self.assertFalse(m.x8)
        self.assertEqual(len(m.stack), 1)


if __name__ == "__main__":
    unittest.main()
