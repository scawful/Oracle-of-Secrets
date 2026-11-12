"""Contract and compiled Asar checks for Overworld/sky_tile_types.asm.

Covers the scoped Sky Tile8 lookup table plus the TileInteract_DashLift ($1BBE3E)
dig guard that prevents Wolf Mask / Shovel from overwriting Sky cloud void tile
$0034 with $0DC9 while preserving ordinary overworld digging and flag-off identity.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "Overworld" / "sky_tile_types.asm"

sys.path.insert(0, str(ROOT / "Scripts" / "Generate"))
from generate_hooks_json import scan_hooks  # noqa: E402

ASSEMBLER = os.environ.get("ASAR_BIN") or shutil.which("asar")

TABLE_READ_HOOKS = (0x00886E, 0x1BBEFD, 0x1BBF2A, 0x1BC04E)
TABLE_READ_PREIMAGE = bytes.fromhex("BF 59 94 0E")  # LDA.l $0E9459, X
DIG_GATE_ADDR = 0x1BBE3E
# Vanilla TileInteract_DashLift ($1BBE3E..$1BBE48):
#   AD 7A 03  LDA $037A
#   29 FF 00  AND #$00FF
#   C9 01 00  CMP #$0001
#   D0 F2     BNE $1BBE3B
DIG_GATE_PREIMAGE = bytes.fromhex("AD 7A 03 29 FF 00 C9 01 00 D0 F2")
SKY_AREAS = set(range(0x84, 0x88)) | set(range(0x8C, 0x90))


def snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + ((addr & 0xFFFF) - 0x8000)


def build_preimage_fixture() -> bytearray:
    """Create a 4 MiB headerless LoROM image with only required preimage bytes."""
    image = bytearray(0x400000)
    for addr in TABLE_READ_HOOKS:
        pc = snes_to_pc(addr)
        image[pc:pc + 4] = TABLE_READ_PREIMAGE
    dig_pc = snes_to_pc(DIG_GATE_ADDR)
    image[dig_pc:dig_pc + len(DIG_GATE_PREIMAGE)] = DIG_GATE_PREIMAGE
    # High byte after $0E9459..$0E9658 (native M16 read at char $1FF)
    image[snes_to_pc(0x0E9659)] = 0x5A
    return image


def assemble_sky_tile_types(
    directory: Path,
    image: bytes,
    *,
    graphics: int,
    route: int,
) -> tuple[subprocess.CompletedProcess[str], bytes, dict[str, int]]:
    rom = directory / "probe.sfc"
    asm = directory / "probe.asm"
    symbols = directory / "probe.sym"
    rom.write_bytes(image)
    asm.write_text(
        "lorom\n"
        f"!ENABLE_SKY_OVERWORLD_GRAPHICS = {graphics}\n"
        f"!ENABLE_SKY_OVERWORLD_ROUTE = {route}\n"
        "org $348000\n"
        f'incsrc "{SOURCE}"\n'
        "SkyTileType_TestModuleEnd:\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            ASSEMBLER,
            "--no-title-check",
            "--fix-checksum=off",
            "--symbols=wla",
            f"--symbols-path={symbols}",
            str(asm),
            str(rom),
        ],
        capture_output=True,
        text=True,
    )
    labels: dict[str, int] = {}
    if symbols.exists():
        labels = {
            name: int(bank + offset, 16)
            for bank, offset, name in re.findall(
                r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+([A-Za-z0-9_]+)$",
                symbols.read_text(encoding="utf-8"),
                re.M,
            )
        }
    return proc, rom.read_bytes(), labels


def _extract_macro_and_routines(source_text: str) -> tuple[dict[str, tuple[list[str], list[str]]], dict[str, list[str]]]:
    macros: dict[str, tuple[list[str], list[str]]] = {}
    routines: dict[str, list[str]] = {}
    lines = source_text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i].split(";", 1)[0].strip()
        macro_m = re.match(r"^macro\s+(\w+)\(([^)]*)\)$", raw)
        if macro_m:
            name = macro_m.group(1)
            params = [p.strip() for p in macro_m.group(2).split(",") if p.strip()]
            body: list[str] = []
            i += 1
            while i < len(lines):
                inner = lines[i].split(";", 1)[0].strip()
                if inner == "endmacro":
                    break
                if inner:
                    body.extend(part.strip() for part in inner.split(" : ") if part.strip())
                i += 1
            macros[name] = (params, body)
        elif raw.endswith(":") and i + 1 < len(lines) and lines[i + 1].split(";", 1)[0].strip() == "{":
            name = raw[:-1]
            body = []
            i += 2
            while i < len(lines):
                inner = lines[i].split(";", 1)[0].strip()
                if inner == "}":
                    break
                if inner:
                    for part in inner.split(" : "):
                        part = part.strip()
                        if not part:
                            continue
                        call_m = re.match(r"^%(\w+)\(([^)]*)\)$", part)
                        if call_m:
                            m_params, m_body = macros[call_m.group(1)]
                            args = [a.strip() for a in call_m.group(2).split(",")]
                            subst = dict(zip(m_params, args))
                            for m_line in m_body:
                                expanded = m_line
                                for k, v in subst.items():
                                    expanded = expanded.replace(f"<{k}>", v)
                                body.append(expanded)
                        else:
                            body.append(part)
                i += 1
            routines[name] = body
        i += 1
    return macros, routines


def _run_contract_routine(
    instructions: list[str],
    wram: dict[int, int],
    *,
    p: int,
    a: int,
    x: int,
    y: int,
    stack: list[int],
    sky_table: bytes,
    vanilla_table: bytes,
) -> dict[str, object]:
    """Execute the parsed 65816 routine subset under explicit entry registers/stack."""
    labels = {}
    program = []
    for item in instructions:
        if item.startswith(".") and " " not in item:
            labels[item] = len(program)
        else:
            program.append(item)

    sp_idx = len(stack)
    stk = list(stack)
    reg_a, reg_x, reg_y, reg_p = a & 0xFFFF, x & 0xFFFF, y & 0xFFFF, p & 0xFF
    if reg_p & 0x10:
        reg_x &= 0xFF
        reg_y &= 0xFF
    n_flag, z_flag, c_flag = (reg_p >> 7) & 1, (reg_p >> 1) & 1, reg_p & 1

    def update_nz16(val: int) -> None:
        nonlocal n_flag, z_flag
        n_flag = (val >> 15) & 1
        z_flag = int((val & 0xFFFF) == 0)

    def packed_p() -> int:
        return (reg_p & ~0x83) | (n_flag << 7) | (z_flag << 1) | c_flag

    pc_idx = 0
    steps = 0
    while pc_idx < len(program):
        steps += 1
        if steps > 100:
            raise AssertionError("Instruction loop bound exceeded")
        op = program[pc_idx]
        if op == "PHP":
            stk.append(packed_p())
        elif op == "PLP":
            reg_p = stk.pop()
            n_flag = (reg_p >> 7) & 1
            z_flag = (reg_p >> 1) & 1
            c_flag = reg_p & 1
            if reg_p & 0x10:
                reg_x &= 0xFF
                reg_y &= 0xFF
        elif op == "PLA":
            # M16 throughout both routines until SEP #$30 right before RTL.
            lo = stk.pop(len(stk) - 2)
            hi = stk.pop()
            reg_a = lo | (hi << 8)
            update_nz16(reg_a)
        elif op == "LDA 1,S":
            lo = stk[-2]
            hi = stk[-1]
            reg_a = lo | (hi << 8)
            update_nz16(reg_a)
        elif op.startswith("LDA.w #$"):
            reg_a = int(op.split("#$", 1)[1], 16) & 0xFFFF
            update_nz16(reg_a)
        elif op == "LDA.l SkyTileTypes, X":
            reg_a = sky_table[reg_x] | (sky_table[reg_x + 1] << 8)
            update_nz16(reg_a)
        elif op == "LDA.l $0E9459, X":
            reg_a = vanilla_table[reg_x] | (vanilla_table[reg_x + 1] << 8)
            update_nz16(reg_a)
        elif op.startswith("LDA.l $"):
            addr = int(op.split("$", 1)[1], 16)
            reg_a = wram.get(addr, 0) | (wram.get(addr + 1, 0) << 8)
            update_nz16(reg_a)
        elif op.startswith("AND.w #$"):
            reg_a &= int(op.split("#$", 1)[1], 16)
            update_nz16(reg_a)
        elif op.startswith("CMP.w #$"):
            imm = int(op.split("#$", 1)[1], 16)
            diff = reg_a - imm
            c_flag = int(reg_a >= imm)
            update_nz16(diff)
        elif op.startswith("BNE "):
            if not z_flag:
                pc_idx = labels[op.split()[1]]
                continue
        elif op.startswith("BCC "):
            if not c_flag:
                pc_idx = labels[op.split()[1]]
                continue
        elif op.startswith("BCS "):
            if c_flag:
                pc_idx = labels[op.split()[1]]
                continue
        elif op.startswith("SEP #$"):
            mask = int(op.split("#$", 1)[1], 16)
            reg_p = packed_p() | mask
            # Setting 65816 P.X (bit 4) clears XH and YH hardware-wide.
            if reg_p & 0x10:
                reg_x &= 0xFF
                reg_y &= 0xFF
        elif op.startswith("JML $"):
            return {
                "exit": op.split()[1],
                "a": reg_a,
                "x": reg_x,
                "y": reg_y,
                "p": packed_p(),
                "stack": stk,
                "sp_delta": len(stk) - sp_idx,
            }
        elif op == "RTL":
            return {
                "exit": "RTL",
                "a": reg_a,
                "x": reg_x,
                "y": reg_y,
                "p": packed_p(),
                "stack": stk,
                "sp_delta": len(stk) - sp_idx,
            }
        else:
            raise AssertionError(f"Unhandled instruction in contract model: {op}")
        pc_idx += 1
    raise AssertionError("Routine fell off end")


class SkyTileTypesTest(unittest.TestCase):
    def test_hook_annotations_match_flag_state(self):
        enabled = scan_hooks(
            ROOT,
            [SOURCE],
            defines={"ENABLE_SKY_OVERWORLD_GRAPHICS": 1, "ENABLE_SKY_OVERWORLD_ROUTE": 1},
        )
        by_addr = {hook.address: hook for hook in enabled}
        self.assertEqual(set(by_addr), set(TABLE_READ_HOOKS) | {DIG_GATE_ADDR})
        dig = by_addr[DIG_GATE_ADDR]
        self.assertEqual(dig.name, "SkyTileType_GuardVoidDig")
        self.assertEqual(dig.kind, "jml")
        self.assertEqual(dig.target, "SkyTileType_GuardVoidDig")
        self.assertEqual((dig.expected_m, dig.expected_x, dig.protected_size), (16, 16, 11))

        disabled = scan_hooks(
            ROOT,
            [SOURCE],
            defines={"ENABLE_SKY_OVERWORLD_GRAPHICS": 1, "ENABLE_SKY_OVERWORLD_ROUTE": 0},
        )
        self.assertEqual(disabled, [])

    def test_guard_void_dig_and_sky_selector_contracts(self):
        _, routines = _extract_macro_and_routines(SOURCE.read_text(encoding="utf-8"))
        guard = routines["SkyTileType_GuardVoidDig"]
        selector = routines["SkyTileType"]
        sky_table = bytes(range(256)) + bytes(range(256)) + b"\x5A"
        vanilla_table = bytes((i ^ 0xFF) for i in range(256)) * 2 + b"\xA5"

        # Entry from $1BBDF3: PHA with Tile16 pushed little-endian onto stack.
        def call_guard(
            *,
            indoors: int,
            area: int,
            usey2: int,
            tile16: int,
            caller_x: int = 0x0246,
            caller_y: int = 0x0377,
        ):
            wram = {0x7E001B: indoors, 0x7E008A: area, 0x7E037A: usey2}
            stack = [0xAA, 0xBB, 0x07, tile16 & 0xFF, (tile16 >> 8) & 0xFF]
            return _run_contract_routine(
                guard,
                wram,
                p=0x05,  # M=16, X=16, C=1, Z=0, I=1
                a=tile16,
                x=caller_x,
                y=caller_y,
                stack=stack,
                sky_table=sky_table,
                vanilla_table=vanilla_table,
            )

        # Vanilla exit contract reached via $1BBE3B (JMP $1BBF1A -> PLA : SEP #$30 : RTL).
        vanilla_exit = _run_contract_routine(
            ["PLA", "SEP #$30", "RTL"],
            {},
            p=0x05,
            a=0x0034,
            x=0x0246,
            y=0x0377,
            stack=[0xAA, 0xBB, 0x07, 0x34, 0x00],
            sky_table=sky_table,
            vanilla_table=vanilla_table,
        )
        self.assertEqual(vanilla_exit["exit"], "RTL")
        self.assertEqual(vanilla_exit["a"], 0x0034)
        self.assertEqual(vanilla_exit["p"] & 0x30, 0x30)
        self.assertEqual(vanilla_exit["sp_delta"], -2)
        self.assertEqual(vanilla_exit["stack"], [0xAA, 0xBB, 0x07])
        self.assertEqual((vanilla_exit["x"], vanilla_exit["y"]), (0x0046, 0x0077))

        # 1. Selected outdoors Sky maps block Tile16 $0034 under Shovel/Wolf dig ($037A=1),
        #    matching $1BBF1A exit widths (M=8, X=8, XH=0, YH=0, [Tile16] popped).
        for area in sorted(SKY_AREAS):
            with self.subTest(sky_area=hex(area)):
                res = call_guard(indoors=0, area=area, usey2=1, tile16=0x0034)
                self.assertEqual(res["exit"], "RTL")
                self.assertEqual(res["a"], 0x0000)
                self.assertEqual(res["p"] & 0x30, vanilla_exit["p"] & 0x30)
                self.assertEqual(res["sp_delta"], vanilla_exit["sp_delta"])
                self.assertEqual(res["stack"], vanilla_exit["stack"])
                self.assertEqual((res["x"], res["y"]), (0x0046, 0x0077))
                self.assertEqual((res["x"], res["y"]), (vanilla_exit["x"], vanilla_exit["y"]))

        # 2. Ordinary Overworld maps allow Tile16 $0034 digging ($1BBE49 -> $0DC9).
        for area in (0x00, 0x2A, 0x80, 0x83, 0x88, 0x8B, 0x90, 0xA0):
            with self.subTest(ordinary_area=hex(area)):
                res = call_guard(indoors=0, area=area, usey2=1, tile16=0x0034)
                self.assertEqual(res["exit"], "$1BBE49")
                self.assertEqual(res["p"] & 0x30, 0x00)  # M=16, X=16 preserved
                self.assertEqual(res["sp_delta"], 0)
                self.assertEqual((res["x"], res["y"]), (0x0246, 0x0377))

        # 3. Indoors $0034 and non-$0034 diggable tiles on Sky allow normal handling.
        for tile16 in (0x0035, 0x0071, 0x00DA, 0x00F8, 0x010D):
            res = call_guard(indoors=0, area=0x87, usey2=1, tile16=tile16)
            self.assertEqual(res["exit"], "$1BBE49")
            self.assertEqual(res["p"] & 0x30, 0x00)
            self.assertEqual(res["sp_delta"], 0)
            self.assertEqual((res["x"], res["y"]), (0x0246, 0x0377))
        res_indoor = call_guard(indoors=1, area=0x87, usey2=1, tile16=0x0034)
        self.assertEqual(res_indoor["exit"], "$1BBE49")
        self.assertEqual(res_indoor["p"] & 0x30, 0x00)
        self.assertEqual((res_indoor["x"], res_indoor["y"]), (0x0246, 0x0377))

        # 4. Non-dig actions (USEY2 != 1) take original BNE $1BBE3B (JMP $1BBF1A) exit.
        for usey2 in (0x00, 0x04, 0x08):
            res = call_guard(indoors=0, area=0x87, usey2=usey2, tile16=0x0034)
            self.assertEqual(res["exit"], "$1BBE3B")
            self.assertEqual(res["p"] & 0x30, 0x00)
            self.assertEqual(res["sp_delta"], 0)
            self.assertEqual((res["x"], res["y"]), (0x0246, 0x0377))

        # 5. SkyTileType selector shares exact area range and preserves P/X/Y/stack.
        for area in range(0x100):
            for indoors in (0, 1):
                wram = {0x7E001B: indoors, 0x7E008A: area}
                res = _run_contract_routine(
                    selector,
                    wram,
                    p=0x45,  # V=1, I=1, C=1, M=16, X=16
                    a=0x1234,
                    x=0x01FF,
                    y=0x0377,
                    stack=[0x01],
                    sky_table=sky_table,
                    vanilla_table=vanilla_table,
                )
                expected = sky_table if (indoors == 0 and area in SKY_AREAS) else vanilla_table
                expected_word = expected[0x01FF] | (expected[0x0200] << 8)
                self.assertEqual(res["exit"], "RTL")
                self.assertEqual(res["a"], expected_word)
                self.assertEqual(res["p"] & 0x7D, 0x45)  # C, I, V, M, X preserved
                self.assertEqual(res["sp_delta"], 0)
                self.assertEqual((res["x"], res["y"]), (0x01FF, 0x0377))

    @unittest.skipUnless(ASSEMBLER, "Asar required for compiled Sky tile-type checks")
    def test_disabled_route_emits_zero_bytes(self):
        original = bytes(build_preimage_fixture())
        with tempfile.TemporaryDirectory() as directory:
            proc, image, _ = assemble_sky_tile_types(
                Path(directory), original, graphics=0, route=0
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(image, original)

    @unittest.skipUnless(ASSEMBLER, "Asar required for compiled Sky tile-type checks")
    def test_enabled_route_binds_preimages_and_opcodes_cleanly(self):
        original = bytes(build_preimage_fixture())
        with tempfile.TemporaryDirectory() as directory:
            proc, image, labels = assemble_sky_tile_types(
                Path(directory), original, graphics=1, route=1
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        sky_target = labels["SkyTileType"]
        guard_target = labels["SkyTileType_GuardVoidDig"]
        module_end = labels["SkyTileType_TestModuleEnd"]
        self.assertLessEqual(
            (labels["SkyTileTypes"] & 0xFFFF) + 0x0201, 0x10000
        )

        # Verify compiled 11-byte JML + 7x NOP span at $1BBE3E and 4x JSL spans.
        expected_dig_hook = b"\x5C" + guard_target.to_bytes(3, "little") + (b"\xEA" * 7)
        dig_pc = snes_to_pc(DIG_GATE_ADDR)
        self.assertEqual(image[dig_pc:dig_pc + 11], expected_dig_hook)

        expected_jsl = b"\x22" + sky_target.to_bytes(3, "little")
        permitted = [(dig_pc, dig_pc + 11), (snes_to_pc(0x348000), snes_to_pc(module_end))]
        for addr in TABLE_READ_HOOKS:
            pc = snes_to_pc(addr)
            self.assertEqual(image[pc:pc + 4], expected_jsl)
            permitted.append((pc, pc + 4))

        # No stray writes anywhere outside Bank $34 payload and the 5 hooks.
        for idx, (old_b, new_b) in enumerate(zip(original, image)):
            if old_b != new_b:
                self.assertTrue(any(a <= idx < b for a, b in permitted), hex(idx))

        # Spot-check compiled machine opcodes in SkyTileType_GuardVoidDig.
        guard_bytes = image[snes_to_pc(guard_target):snes_to_pc(module_end)]
        self.assertIn(b"\xAF\x7A\x03\x7E", guard_bytes)  # LDA.l $7E037A
        self.assertIn(b"\xA3\x01\xC9\x34\x00", guard_bytes)  # LDA 1,S : CMP.w #$0034
        self.assertIn(b"\x68\xA9\x00\x00\xE2\x30\x6B", guard_bytes)  # PLA : LDA #$0000 : SEP #$30 : RTL
        self.assertIn(b"\x5C\x49\xBE\x1B", guard_bytes)  # JML $1BBE49
        self.assertIn(b"\x5C\x3B\xBE\x1B", guard_bytes)  # JML $1BBE3B

    @unittest.skipUnless(ASSEMBLER, "Asar required for compiled Sky tile-type checks")
    def test_corrupted_dig_preimage_refused(self):
        broken = build_preimage_fixture()
        broken[snes_to_pc(DIG_GATE_ADDR)] ^= 0xFF
        with tempfile.TemporaryDirectory() as directory:
            proc, _, _ = assemble_sky_tile_types(
                Path(directory), bytes(broken), graphics=1, route=1
            )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("TileInteract_DashLift", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
