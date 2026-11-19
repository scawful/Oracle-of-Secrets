#!/usr/bin/env python3
"""Compiled 65816 proofs for extended X-button item bindings & subtle menu SFX.

Assembles the real production ASM files (Items/item_bindings_adapter.asm,
Items/item_bindings_dispatch.asm, Menu/menu_hud_codex.asm, Menu_Bindings_Input,
QuestSongs_Frame, and Ocarina_SongLearned_Long / Ocarina_ValidSong_Long) and
executes them on LakeSnes's compiled 65816 CPU.

Covers every newly X-bindable item and runtime edge case:
1. Bottles 1-4 ($06, $0C, $12, $18 -> Action $0B):
   - X binding, X press latches and syncs BottleIndex ($7EF34F) to 1..4.
   - Simultaneous Y bottle + X bottle switches BottleIndex accurately per button.
   - Empty-bottle catch ($037A=$10, $3A=$40) holds latch and releases cleanly.
   - Bunny state ($02E0=1) allows Bottles on X and Y (matching vanilla $079B16).
   - HUD_CodexCells draws dynamic Bottle 1-4 contents (Empty, Potions, Fairy,
     Bee, Magic Bean, Milk) from $7EF35C..$7EF35F.
2. Mirror ($0B -> Action $14):
   - X launch, latch hold during warp ($5D=$14), clean release on $5D=0.
   - Bunny state ($02E0=1) allows Mirror on X and Y while blocking other items.
   - HUD_CodexCells draws Mirror icon ($2C62/$2C63/$2C72/$2C73).
3. Ocarina ($0D -> Action $08):
   - ItemBindings_IsOcarina returns Z=1 when Ocarina is latched on X even while
     Y holds Bow ($0202=$01), and Z=0 when Wolf form ($02B2=3) digs.
   - ItemBindings_UsePress bridges X press; $3A bit 6 holds latch during song.
   - QuestSongs_Frame emits SFX3.$20 and keeps Y's item when Ocarina is on X
     (or equips Ocarina onto Y when Ocarina is not on X).
   - HUD_CodexCells renders grey (unlearned) and all 6 song colors from
     HUD_OcarinaIcons (Healing, Storms, Soaring, Time, Secrets, Epona).
4. Book of Secrets ($0E -> Action $0C):
   - X launch, ItemBindings_UsePress bridges X press, clean release next frame.
   - HUD_CodexCells draws Book icon.
5. Fishing Rod ($10 -> Action $0D):
   - X launch, ItemBindings_EffectiveItem returns $10 even with Portal Rod ($19)
     or Byrna ($1B) on Y.
   - Latch stays busy while $7F5BA2 != 0 (cast/out/reel) and releases when 0.
   - Items/fishing_rod.asm routes both CheckYButtonPress and .waitforend reel
     press through ItemBindings_UsePress (accepting X when cast via X).
   - HUD_CodexCells always draws Fishing Rod ($2082,$2883,$208B,$288C) for both
     $7EF351=1 and $7EF351=2 (never Portal Rod or out-of-bounds).
6. Cane of Byrna ($1B -> Action $0D):
   - Ownership requires exact ByrnaOwned==1 (0 and 2 refused).
   - Latch stays busy while Ancilla $30 or $31 exists in $0C4A..$0C4E after
     cast animation clears $037A/$3A.
   - ItemBindings_ByrnaCancel cancels ONLY on X press ($F6&$40) when started
     via X (ignoring Y press $F4&$40) and ONLY on Y press when started via Y.
   - Menu swap off Byrna immediately releases latch on next Route tick.
   - HUD_CodexCells draws Byrna ($2CDC,$2CDD,$2CEC,$2CED).
7. Masks ($13-$17) and Garo Mask ($1E):
   - Rejected by ItemBindings_AssignX and Menu_Bindings_Input (SFX2.$3C).
8. Menu_Bindings_Input subtle SFX:
   - Y bind -> SFX3.$20, X bind -> SFX3.$20, X clear -> SFX3.$0C, refuse -> SFX2.$3C.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from d4_compiled_fight_check import Cpu, Fixture

ROOT = Path(__file__).resolve().parents[1]

ITEM_BINDING_ADDRS = {
    "SavedVersion": 0x7EF3B9,
    "SavedY": 0x7EF3BA,
    "SavedX": 0x7EF3BB,
    "Cursor": 0x7E02B3,
    "Logical": 0x7E02B4,
    "Action": 0x7E02B5,
    "Button": 0x7E02B6,
    "MenuY": 0x7E02B7,
}

# Exact vanilla bytes asserted by Items/item_bindings_dispatch.asm pushpc hooks.
VANILLA_HOOK_BYTES = {
    0x07B07B: bytes([0xA5, 0xF4, 0x29, 0x40]),  # LDA $F4 : AND #$40
    0x0288F9: bytes([0xA5, 0xF6, 0x29, 0x40]),  # LDA $F6 : AND #$40
    0x02A55A: bytes([0xA5, 0xF6, 0x29, 0x40]),  # LDA $F6 : AND #$40
    0x08DCBE: bytes([0x24, 0xF4, 0x50, 0x0B]),  # BIT $F4 : BVC $08DCCD
}

OCARINA_ICON_EXPECTED = {
    0: (0x30D4, 0x30D5, 0x30E4, 0x30E5),  # Unlearned grey
    1: (0x2CD4, 0x2CD5, 0x2CE4, 0x2CE5),  # Healing blue
    2: (0x3CD4, 0x3CD5, 0x3CE4, 0x3CE5),  # Storms green
    3: (0x24D4, 0x24D5, 0x24E4, 0x24E5),  # Soaring red
    4: (0x34D4, 0x34D5, 0x34E4, 0x34E5),  # Time ivory
    5: (0x28D4, 0x28D5, 0x28E4, 0x28E5),  # Secrets gold
    6: (0x20D4, 0x20D5, 0x20E4, 0x20E5),  # Epona bronze
}

BOTTLE_ICON_EXPECTED = {
    2: (0x2837, 0x2838, 0x2CC3, 0x2CD3),  # Empty bottle
    3: (0x24D2, 0x64D2, 0x24E2, 0x24E3),  # Red potion
    4: (0x3CD2, 0x7CD2, 0x3CE2, 0x3CE3),  # Green potion
    5: (0x2CD2, 0x6CD2, 0x2CE2, 0x2CE3),  # Blue potion
    6: (0x2855, 0x6855, 0x2C57, 0x2C5A),  # Fairy
    7: (0x2837, 0x2838, 0x2839, 0x283A),  # Bee
    9: (0x2837, 0x2838, 0x3CF7, 0x3CF8),  # Magic Bean
    10: (0x2837, 0x2838, 0x3CFB, 0x3CFC),  # Milk Bottle
}


def lorom_pc(addr: int) -> int:
    return (((addr >> 16) & 0x7F) << 15) | (addr & 0x7FFF)


def find_lakesnes() -> Path | None:
    env = os.environ.get("OOS_LAKESNES")
    candidates = [Path(env)] if env else []
    candidates.extend([
        ROOT.parent / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ])
    for cand in candidates:
        if (cand / "snes" / "cpu.c").is_file():
            return cand
    return None


def extract_block(path: Path, label: str) -> str:
    txt = path.read_text(encoding="utf-8")
    m = re.search(rf"^{label}:\s*\n\{{.*?^\}}", txt, re.M | re.S)
    if not m:
        raise AssertionError(f"Routine {label} not found in {path}")
    return m.group(0)


def extract_table(path: Path, start_label: str, end_label: str) -> str:
    txt = path.read_text(encoding="utf-8")
    i = txt.index(start_label + ":")
    j = txt.index(end_label, i)
    return txt[i:j]


def assemble_harness(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    # Extract verbatim production routines/tables needed by HUD_CodexCells & QuestSongs_Frame.
    ocarina_path = ROOT / "Items" / "ocarina.asm"
    hud_path = ROOT / "Menu" / "menu_hud.asm"
    select_path = ROOT / "Menu" / "menu_select_item.asm"
    bindings_menu_path = ROOT / "Menu" / "menu_item_bindings.asm"
    cursor_flow_path = ROOT / "Menu" / "menu_cursor_flow.asm"

    song_learned = extract_block(ocarina_path, "Ocarina_SongLearned_Long")
    valid_song = extract_block(ocarina_path, "Ocarina_ValidSong_Long")
    menu_bind_input = extract_block(bindings_menu_path, "Menu_Bindings_Input")
    quest_songs_frame = extract_block(cursor_flow_path, "QuestSongs_Frame")

    # Menu_ItemIndex and Menu_AddressIndex tables
    menu_item_index = extract_table(select_path, "Menu_ItemIndex", "Menu_ItemIndex_End:") + "Menu_ItemIndex_End:\n"
    menu_addr_index = extract_table(select_path, "Menu_AddressIndex", "; =====")
    menu_addr_long = extract_table(select_path, "Menu_AddressLong", "GotoNextItem_Local:")

    # HUD_OcarinaIcons and HUD_DrawItem .new_icons
    hud_txt = hud_path.read_text(encoding="utf-8")
    hud_ocarina = hud_txt[hud_txt.index("HUD_OcarinaIcons:"):hud_txt.index("assert pc()-HUD_OcarinaIcons")]
    new_icons_m = re.search(r"^\s*\.new_icons\n((?:\s*dw [^\n]+\n)+)", hud_txt, re.M)
    assert new_icons_m, "HUD_DrawItem .new_icons not found"
    hud_new_icons = "HUD_DrawItem_new_icons:\n" + new_icons_m.group(1)

    # Extract Bank $0D HudItems pointer table + Bottle/Mirror/FishingRod/Book tables verbatim
    hud_bank0d = hud_txt[hud_txt.index("org $0DFA93"):hud_txt.index("; $6FE77-$6FFC0")]

    asm_src = f"""lorom
!DISABLE_ITEMS = 0
!DISABLE_MASKS = 0
!ENABLE_GOLDSTAR_CELL = 1
!ENABLE_HORSE_FORM = 1
!BOMBCHU_AMMO_MAX = 99
!CurrentMask = $02B2
!SideQuest2_EponaSong = $04

BottleIndex = $7EF34F
PortalRodOwned = $7EF3A6
GoldstarOwned = $7EF3A9
ByrnaOwned = $7EF3AC
BombchuOwned = $7EF3AD
SwitchHookOwned = $7EF3AE
GaroMaskOwned = $7EF3AF
BombchuAmmo = $7EF3B0
SideQuestProg2 = $7EF3B6
SavedOcarinaSong = $7EF3AB
CurrentSong = $030F
GoldstarOrHookshot = $7EF3A7
HudCornerBuffer = $7EC84A

ItemBindingSavedVersion = $7EF3B9
ItemBindingSavedY = $7EF3BA
ItemBindingSavedX = $7EF3BB
ItemBindingCursor = $7E02B3
ItemBindingLogical = $7E02B4
ItemBindingAction = $7E02B5
ItemBindingButton = $7E02B6
ItemBindingMenuY = $7E02B7

org $0DF741
  ; Vanilla Book HUD icons (entry 0 blank, entry 1 Book of Mudora)
  dw $20F5, $20F5, $20F5, $20F5
  dw $2C50, $2C51, $2C60, $2C61

{hud_bank0d}

org $2B8000
{song_learned}
{valid_song}
Menu_SongOrder:
  db $01, $02, $03, $04, $05, $06
{quest_songs_frame}

org $2D8000
{menu_item_index}
{menu_addr_index}
{menu_addr_long}
Menu_RefreshInventoryScreen_Long:
  SEP #$30
  RTL

org $2E8200
{hud_new_icons}
{hud_ocarina}

org $548800
ItemBindings_SpanStart:
incsrc "{ROOT / 'Items' / 'item_bindings_adapter.asm'}"
incsrc "{ROOT / 'Items' / 'item_bindings_dispatch.asm'}"
assert pc()-ItemBindings_SpanStart <= $600

HudCodex_SpanStart:
incsrc "{ROOT / 'Menu' / 'menu_hud_codex.asm'}"
assert pc()-HudCodex_SpanStart <= $200

{menu_bind_input}
"""
    asm_file = folder / "harness.asm"
    asm_file.write_text(asm_src, encoding="utf-8")

    # 3 MB synthetic LoROM covering banks $00-$5F (bank $54 fits cleanly).
    rom = bytearray(b"\xFF" * (0x60 * 0x8000))
    for addr, raw in VANILLA_HOOK_BYTES.items():
        pc = lorom_pc(addr)
        rom[pc:pc + len(raw)] = raw
    img = folder / "harness.sfc"
    img.write_bytes(rom)

    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(asm_file), str(img)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    labels = {
        m[3]: (int(m[1], 16) << 16) | int(m[2], 16)
        for m in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            img.with_suffix(".sym").read_text(encoding="utf-8"),
        )
    }
    return img.read_bytes(), labels


class XBindFixture(Fixture):
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        self.stubs = {}
        self.ram7f = bytearray(0x10000)  # WRAM bank $7F (for $7F5BA2 fishing mode)
        self.jumped_addr: int | None = None

    def read(self, adr: int) -> int:
        bank = adr >> 16
        if bank == 0x7F:
            return self.ram7f[adr & 0xFFFF]
        return super().read(adr)

    def write(self, adr: int, val: int) -> None:
        bank = adr >> 16
        if bank == 0x7F:
            self.ram7f[adr & 0xFFFF] = val
            return
        super().write(adr, val)

    def put7f(self, adr: int, val: int) -> None:
        self.ram7f[adr & 0xFFFF] = val & 0xFF

    def get7f(self, adr: int) -> int:
        return self.ram7f[adr & 0xFFFF]

    def get_word(self, adr: int) -> int:
        return self.get(adr) | (self.get(adr + 1) << 8)

    def x_hud_tiles(self) -> tuple[int, int, int, int]:
        return (
            self.get_word(0x7EC770),
            self.get_word(0x7EC772),
            self.get_word(0x7EC7B0),
            self.get_word(0x7EC7B2),
        )

    def x_hud_border(self) -> tuple[int, int]:
        return (self.get_word(0x7EC7F0), self.get_word(0x7EC7F2))

    def call_jsl(self, name: str, *, a: int = 0, x: int = 0, y: int = 0,
                 m8: bool = True, x8: bool = True, db: int = 0x7E, limit: int = 1200) -> int:
        c = self.cpu
        entry = self.labels[name]
        c.mf = m8; c.xf = x8
        c.a = a; c.x = x; c.y = y; c.db = db; c.dp = 0; c.c = False; c.z = False
        sp = c.sp
        c.k = entry >> 16; c.pc = entry & 0xFFFF
        self.put(sp, c.k); self.put(sp - 1, 0x6F); self.put(sp - 2, 0xFF); c.sp -= 3
        sentinel = (entry & 0xFF0000) | 0x7000
        for _ in range(limit):
            if ((c.k << 16) | c.pc) == sentinel:
                assert c.sp == sp, f"{name} stack imbalance: {c.sp:#x} != {sp:#x}"
                return c.a & (0xFF if c.mf else 0xFFFF)
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name} did not RTL within {limit} ops (at ${c.k:02X}{c.pc:04X})")

    def call_byrna_cancel(self) -> int:
        c = self.cpu
        entry = self.labels["ItemBindings_ByrnaCancel"]
        c.mf = True; c.xf = True; c.a = 0; c.x = 0x03; c.y = 0x02; c.db = 0x08; c.dp = 0
        c.k = entry >> 16; c.pc = entry & 0xFFFF
        for _ in range(100):
            pc24 = (c.k << 16) | c.pc
            if pc24 in (0x08DCC2, 0x08DCCD):
                assert c.x == 0x03 and c.y == 0x02, "ItemBindings_ByrnaCancel clobbered X/Y"
                return pc24
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"ItemBindings_ByrnaCancel did not exit cleanly (at ${c.k:02X}{c.pc:04X})")


class TestExtendedXBindingsCompiled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lakesnes = find_lakesnes()
        if lakesnes is None:
            raise unittest.SkipTest("LakeSnes CPU source not found")
        cls._tmp = tempfile.TemporaryDirectory(prefix="w2b-xbind-cpu-")
        d = Path(cls._tmp.name)
        lib_path = d / "cpu.dylib"
        subprocess.run(
            [
                "cc", "-shared", "-fPIC", "-O2",
                str(lakesnes / "snes/cpu.c"),
                str(lakesnes / "snes/statehandler.c"),
                "-o", str(lib_path),
            ],
            check=True,
        )
        cls.lib = C.CDLL(str(lib_path))
        cls.lib.cpu_init.restype = C.POINTER(Cpu)
        cls.lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls.lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls.rom, cls.labels = assemble_harness(d / "build")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "_tmp"):
            cls._tmp.cleanup()

    def make_fx(self) -> XBindFixture:
        f = XBindFixture(self.lib, self.rom, self.labels)
        self.addCleanup(f.close)
        # Default valid base Link with Bow on Y
        f.put(0x7EF340, 1)  # Bow
        f.put(0x7E0202, 1)  # Y = Bow
        f.put(0x7EF3B9, 1)  # SavedVersion = 1
        f.put(0x7EF3BA, 1)  # SavedY = Bow
        f.put(0x7E02B3, 1)  # Cursor hydrated
        return f

    def test_bottles_1_to_4_x_and_y_sync_bottle_index_catch_and_bunny(self):
        bottles = (
            (0x06, 0x7EF35C, 1),
            (0x0C, 0x7EF35D, 2),
            (0x12, 0x7EF35E, 3),
            (0x18, 0x7EF35F, 4),
        )
        for item_id, sram, idx in bottles:
            with self.subTest(bottle=idx):
                f = self.make_fx()
                f.put(sram, 0x03)  # Red Potion
                f.put(0x7EF3BB, item_id)  # X = Bottle idx
                f.put(0x7EF34F, 0x00)     # stale BottleIndex
                f.put(0xF6, 0x40)         # Press X

                action = f.call_jsl("ItemBindings_Route")
                self.assertTrue(f.cpu.c)
                self.assertEqual(action, 0x0B)
                self.assertEqual(f.get(0x7EF34F), idx, "BottleIndex must match pressed X bottle")
                self.assertEqual(f.get(0x7E02B6), 2)
                self.assertEqual(f.get(0x7E02B4), item_id)

                # Simulate empty-bottle catch holding $037A=$10 and $3A=$40 across frames
                f.put(0xF6, 0x00)
                f.put(0x037A, 0x10)
                f.put(0x3A, 0x40)
                f.put(0x7EF34F, 0x09)  # corrupt to verify .busy keeps it synced
                action = f.call_jsl("ItemBindings_Route")
                self.assertTrue(f.cpu.c)
                self.assertEqual(action, 0x0B)
                self.assertEqual(f.get(0x7EF34F), idx)

                # Catch ends -> latch releases cleanly
                f.put(0x037A, 0x00)
                f.put(0x3A, 0x00)
                f.call_jsl("ItemBindings_Route")
                self.assertFalse(f.cpu.c)
                self.assertEqual(f.get(0x7E02B6), 0)

        # Simultaneous Bottle 1 on Y and Bottle 4 on X: each press syncs its own index
        f = self.make_fx()
        f.put(0x7EF35C, 0x03)  # Bottle 1 = Red Potion
        f.put(0x7EF35F, 0x0A)  # Bottle 4 = Milk
        f.put(0x7E0202, 0x06)  # Y = Bottle 1
        f.put(0x7EF3BB, 0x18)  # X = Bottle 4

        f.put(0xF6, 0x40)
        self.assertEqual(f.call_jsl("ItemBindings_Route"), 0x0B)
        self.assertTrue(f.cpu.c)
        self.assertEqual(f.get(0x7EF34F), 4)
        f.put(0xF6, 0x00)
        f.call_jsl("ItemBindings_Route")  # releases latch
        self.assertEqual(f.get(0x7E02B6), 0)

        f.put(0xF4, 0x40)  # Now press Y (Bottle 1)
        self.assertEqual(f.call_jsl("ItemBindings_Route"), 0x0B)
        self.assertTrue(f.cpu.c)
        self.assertEqual(f.get(0x7EF34F), 1)
        self.assertEqual(f.get(0x7E02B6), 1)

        # Bunny state ($02E0=1) still permits Bottles on X (matches vanilla $079B16)
        f.put(0xF4, 0x00)
        f.call_jsl("ItemBindings_Route")
        f.put(0x02E0, 0x01)
        f.put(0xF6, 0x40)
        self.assertEqual(f.call_jsl("ItemBindings_Route"), 0x0B)
        self.assertTrue(f.cpu.c)
        self.assertEqual(f.get(0x7EF34F), 4)

    def test_mirror_x_launch_warp_hold_and_bunny_rules(self):
        f = self.make_fx()
        f.put(0x7EF353, 0x02)  # Magic Mirror
        f.put(0x7EF3BB, 0x0B)  # X = Mirror
        f.put(0xF6, 0x40)

        action = f.call_jsl("ItemBindings_Route")
        self.assertTrue(f.cpu.c)
        self.assertEqual(action, 0x14)
        self.assertEqual(f.get(0x7E02B6), 2)

        # CheckYButtonPress bridge returns $40 on X press when $0303==$14
        f.put(0x0303, 0x14)
        self.assertEqual(f.call_jsl("ItemBindings_UsePress"), 0x40)

        # Mirror warp sets $5D=$14 -> latch stays busy while warping
        f.put(0xF6, 0x00)
        f.put(0x5D, 0x14)
        self.assertEqual(f.call_jsl("ItemBindings_Route"), 0x14)
        self.assertTrue(f.cpu.c)

        # Warp ends ($5D=0) -> latch releases cleanly
        f.put(0x5D, 0x00)
        f.call_jsl("ItemBindings_Route")
        self.assertFalse(f.cpu.c)
        self.assertEqual(f.get(0x7E02B6), 0)

        # Bunny state ($02E0=1) allows Mirror on X, but blocks non-Mirror/non-Bottle items
        f.put(0x02E0, 0x01)
        f.put(0xF6, 0x40)
        self.assertEqual(f.call_jsl("ItemBindings_Route"), 0x14)
        self.assertTrue(f.cpu.c)

        f.put(0xF6, 0x00)
        f.call_jsl("ItemBindings_Route")  # release
        f.put(0x7EF34C, 0x04)  # Ocarina
        f.put(0x7EF3BB, 0x0D)  # X = Ocarina
        f.put(0xF6, 0x40)
        f.call_jsl("ItemBindings_Route")
        self.assertFalse(f.cpu.c, "Ocarina must stay blocked in Bunny state ($02E0=1)")
        self.assertEqual(f.get(0x7E02B6), 0)

    def test_ocarina_x_dispatch_is_ocarina_and_quest_songs_preserve_y(self):
        f = self.make_fx()
        f.put(0x7EF34C, 0x06)  # Ocarina with 5 songs
        f.put(0x7E0202, 0x01)  # Y = Bow
        f.put(0x7EF3BB, 0x0D)  # X = Ocarina
        f.put(0xF6, 0x40)

        action = f.call_jsl("ItemBindings_Route")
        self.assertTrue(f.cpu.c)
        self.assertEqual(action, 0x08)
        f.put(0x0303, 0x08)

        # Critical bug check: ItemBindings_IsOcarina MUST return Z=1 when Ocarina is on X
        # even though $0202 == $01 (Bow)!
        f.call_jsl("ItemBindings_IsOcarina")
        self.assertTrue(f.cpu.z, "X-bound Ocarina must dispatch to LinkItem_Flute, not WolfMask!")

        # Active Wolf form ($02B2 == 3) still ALWAYS returns Z=0 (digs)
        f.put(0x02B2, 0x03)
        f.call_jsl("ItemBindings_IsOcarina")
        self.assertFalse(f.cpu.z, "Wolf form must always dig even with Ocarina bound")
        f.put(0x02B2, 0x00)

        # Song playing holds $3A bit 6 -> latch remains busy until $3A bit 6 clears
        f.put(0xF6, 0x00)
        f.put(0x3A, 0x40)
        self.assertEqual(f.call_jsl("ItemBindings_Route"), 0x08)
        self.assertTrue(f.cpu.c)
        f.put(0x3A, 0x00)
        f.call_jsl("ItemBindings_Route")
        self.assertFalse(f.cpu.c)
        self.assertEqual(f.get(0x7E02B6), 0)

        # QuestSongs_Frame: picking song 2 (Storms) when Ocarina is ALREADY on X keeps Y=Bow & plays SFX3.$20
        f.put(0x020B, 0x01)  # slot 1 = Song 2 (Storms)
        f.put(0xF6, 0x80)    # press A
        f.put(0x7E0202, 0x01)
        f.put(0x7E02B7, 0x01)
        f.put(0x012F, 0x00)
        f.call_jsl("QuestSongs_Frame")
        self.assertTrue(f.cpu.c)
        self.assertEqual(f.get(0x030F), 0x02)
        self.assertEqual(f.get(0x7EF3AB), 0x02)
        self.assertEqual(f.get(0x7E0202), 0x01, "Y item must be preserved when Ocarina is on X")
        self.assertEqual(f.get(0x7E02B7), 0x01)
        self.assertEqual(f.get(0x012F), 0x20, "QuestSongs_Frame must emit subtle SFX3.$20")

        # When Ocarina is NOT on X, picking a song still equips Ocarina onto Y
        f.put(0x7EF3BB, 0x02)  # X = Boomerang
        f.put(0x020B, 0x02)    # slot 2 = Song 3 (Soaring)
        f.put(0x012F, 0x00)
        f.call_jsl("QuestSongs_Frame")
        self.assertTrue(f.cpu.c)
        self.assertEqual(f.get(0x030F), 0x03)
        self.assertEqual(f.get(0x7E0202), 0x0D)
        self.assertEqual(f.get(0x7E02B7), 0x0D)
        self.assertEqual(f.get(0x012F), 0x20)

    def test_book_of_secrets_x_launch_and_release(self):
        f = self.make_fx()
        f.put(0x7EF34E, 0x01)  # Book of Secrets
        f.put(0x7EF3BB, 0x0E)  # X = Book
        f.put(0xF6, 0x40)

        action = f.call_jsl("ItemBindings_Route")
        self.assertTrue(f.cpu.c)
        self.assertEqual(action, 0x0C)
        f.put(0x0303, 0x0C)
        self.assertEqual(f.call_jsl("ItemBindings_UsePress"), 0x40)

        f.put(0xF6, 0x00)
        f.call_jsl("ItemBindings_Route")
        self.assertFalse(f.cpu.c)
        self.assertEqual(f.get(0x7E02B6), 0)

    def test_fishing_rod_x_cast_hold_reel_and_portal_coexistence(self):
        # Verify Items/fishing_rod.asm routes both press sites through ItemBindings_UsePress
        rod_src = (ROOT / "Items" / "fishing_rod.asm").read_text(encoding="utf-8")
        self.assertIn("JSL ItemBindings_UsePress : BEQ .exit", rod_src)
        self.assertIn("JSL ItemBindings_UsePress : BEQ .fail", rod_src)
        self.assertNotIn("LDA.b $F4 : AND", rod_src)

        f = self.make_fx()
        f.put(0x7EF351, 0x02)  # Fishing Rod + Portal Rod unlocked
        f.put(0x7EF3A6, 0x01)  # PortalRodOwned
        f.put(0x7E0202, 0x19)  # Y = Portal Rod (shares Action $0D!)
        f.put(0x7EF3BB, 0x10)  # X = Fishing Rod (shares Action $0D!)
        f.put(0xF6, 0x40)

        action = f.call_jsl("ItemBindings_Route")
        self.assertTrue(f.cpu.c)
        self.assertEqual(action, 0x0D)
        f.put(0x0303, 0x0D)
        self.assertEqual(f.call_jsl("ItemBindings_EffectiveItem"), 0x10,
                         "EffectiveItem must select Fishing Rod ($10), not Portal Rod ($19)")
        self.assertEqual(f.call_jsl("ItemBindings_UsePress"), 0x40,
                         "Initial cast press must see X")

        # While rod is out ($7F5BA2=1), latch stays busy EVEN if $037A/$3A are 0
        f.put(0xF6, 0x00)
        f.put7f(0x7F5BA2, 0x01)
        action = f.call_jsl("ItemBindings_Route")
        self.assertTrue(f.cpu.c)
        self.assertEqual(action, 0x0D)

        # Pressing X reels in; pressing Y does not spoof X
        f.put(0xF4, 0x40); f.put(0xF6, 0x00)
        self.assertEqual(f.call_jsl("ItemBindings_UsePress"), 0x00)
        f.put(0xF4, 0x00); f.put(0xF6, 0x40)
        self.assertEqual(f.call_jsl("ItemBindings_UsePress"), 0x40)

        # EndFishing clears $7F5BA2 -> latch releases cleanly, Y's Portal Rod restored
        f.put7f(0x7F5BA2, 0x00)
        f.put(0xF6, 0x00)
        f.call_jsl("ItemBindings_Route")
        self.assertFalse(f.cpu.c)
        self.assertEqual(f.get(0x7E02B6), 0)
        self.assertEqual(f.call_jsl("ItemBindings_EffectiveItem"), 0x19)

    def test_byrna_x_barrier_hold_toggle_off_and_menu_swap_cancel(self):
        f = self.make_fx()
        # Old-save garbage ByrnaOwned=2 must NOT validate; exact 1 must validate
        f.put(0x7EF3AC, 0x02)
        f.call_jsl("ItemBindings_IsLatchable", a=0x1B)
        self.assertFalse(f.cpu.c)
        f.put(0x7EF3AC, 0x01)
        f.call_jsl("ItemBindings_IsLatchable", a=0x1B)
        self.assertTrue(f.cpu.c)

        f.put(0x7E0202, 0x01)  # Y = Bow
        f.put(0x7EF3BB, 0x1B)  # X = Cane of Byrna
        f.put(0xF6, 0x40)

        action = f.call_jsl("ItemBindings_Route")
        self.assertTrue(f.cpu.c)
        self.assertEqual(action, 0x0D)
        f.put(0x0303, 0x0D)
        self.assertEqual(f.call_jsl("ItemBindings_EffectiveItem"), 0x1B)

        # After cast animation clears $037A/$3A, live Byrna ancilla ($30 or $31) keeps latch alive
        f.put(0xF6, 0x00)
        for ancilla_id in (0x30, 0x31):
            f.put(0x0C4A, 0x00); f.put(0x0C4C, ancilla_id)
            action = f.call_jsl("ItemBindings_Route")
            self.assertTrue(f.cpu.c, f"Ancilla ${ancilla_id:02X} must keep Byrna X latch alive")
            self.assertEqual(action, 0x0D)

        # ItemBindings_ByrnaCancel while X-started (Button==2):
        # - Neither pressed -> keep ($08DCCD)
        # - Y pressed alone -> keep ($08DCCD)
        # - X pressed -> cancel ($08DCC2)
        f.put(0xF4, 0x00); f.put(0xF6, 0x00)
        self.assertEqual(f.call_byrna_cancel(), 0x08DCCD)
        f.put(0xF4, 0x40); f.put(0xF6, 0x00)
        self.assertEqual(f.call_byrna_cancel(), 0x08DCCD, "Y press must not cancel X-cast Byrna")
        f.put(0xF4, 0x00); f.put(0xF6, 0x40)
        self.assertEqual(f.call_byrna_cancel(), 0x08DCC2, "X press must toggle X-cast Byrna off")

        # Ancilla cleared -> next Route releases latch cleanly
        f.put(0x0C4C, 0x00); f.put(0xF6, 0x00)
        f.call_jsl("ItemBindings_Route")
        self.assertFalse(f.cpu.c)
        self.assertEqual(f.get(0x7E02B6), 0)

        # Menu swap off X while Ancilla $31 is still present releases latch immediately
        f.put(0xF6, 0x40)
        self.assertEqual(f.call_jsl("ItemBindings_Route"), 0x0D)
        f.put(0xF6, 0x00); f.put(0x0C4C, 0x31)
        f.put(0x7EF3BB, 0x02)  # player swapped X to Boomerang in Menu
        f.call_jsl("ItemBindings_Route")
        self.assertFalse(f.cpu.c, "Swapping Byrna off X must release latch so Ancilla $31 shuts off")
        self.assertEqual(f.get(0x7E02B6), 0)

        # Y-started Byrna (Button==1): Y cancels ($08DCC2), X does NOT cancel ($08DCCD)
        f.put(0x7E0202, 0x1B); f.put(0x7EF3BB, 0x01)
        f.put(0x0C4C, 0x00); f.put(0xF4, 0x40); f.put(0xF6, 0x00)
        self.assertEqual(f.call_jsl("ItemBindings_Route"), 0x0D)
        self.assertEqual(f.get(0x7E02B6), 1)
        f.put(0x0C4C, 0x31)
        f.put(0xF4, 0x00); f.put(0xF6, 0x40)
        self.assertEqual(f.call_byrna_cancel(), 0x08DCCD, "X press must not cancel Y-cast Byrna")
        f.put(0xF4, 0x40); f.put(0xF6, 0x00)
        self.assertEqual(f.call_byrna_cancel(), 0x08DCC2, "Y press must toggle Y-cast Byrna off")

    def test_menu_bindings_input_sfx_and_mask_refusal_compiled(self):
        f = self.make_fx()
        # Own Mirror ($0B) and Deku Mask ($13) and Garo Mask ($1E)
        f.put(0x7EF353, 0x02)
        f.put(0x7EF349, 0x01)
        f.put(0x7EF3AF, 0x01)

        # Bind Mirror to Y -> SFX3.$20
        f.put(0x7E0202, 0x0B); f.put(0xF4, 0x40); f.put(0xF6, 0x00); f.put(0x012F, 0x00)
        f.call_jsl("Menu_Bindings_Input", db=0x2D)
        self.assertEqual(f.get(0x7E02B7), 0x0B)
        self.assertEqual(f.get(0x012F), 0x20)

        # Bind Mirror to X -> SFX3.$20
        f.put(0xF4, 0x00); f.put(0xF6, 0x40); f.put(0x012F, 0x00)
        f.call_jsl("Menu_Bindings_Input", db=0x2D)
        self.assertEqual(f.get(0x7EF3BB), 0x0B)
        self.assertEqual(f.get(0x012F), 0x20)

        # Press X again on Mirror -> clears X + soft SFX3.$0C
        f.put(0xF6, 0x40); f.put(0x012F, 0x00)
        f.call_jsl("Menu_Bindings_Input", db=0x2D)
        self.assertEqual(f.get(0x7EF3BB), 0x00)
        self.assertEqual(f.get(0x012F), 0x0C)

        # Pressing X on Masks ($13-$17) or Garo ($1E) -> refused + SFX2.$3C
        for mask_id in (0x13, 0x14, 0x15, 0x16, 0x17, 0x1E):
            f.put(0x7E0202, mask_id); f.put(0xF6, 0x40)
            f.put(0x012E, 0x00); f.put(0x012F, 0x00)
            f.call_jsl("Menu_Bindings_Input", db=0x2D)
            self.assertEqual(f.get(0x7EF3BB), 0x00, f"Mask ${mask_id:02X} must not bind to X")
            self.assertEqual(f.get(0x012E), 0x3C)
            self.assertEqual(f.get(0x012F), 0x00)

    def test_hud_x_slot_rendering_for_all_nine_new_items(self):
        # 1. Bottles 1-4 dynamic contents
        for item_id, sram in ((0x06, 0x7EF35C), (0x0C, 0x7EF35D), (0x12, 0x7EF35E), (0x18, 0x7EF35F)):
            for content, expected_tiles in BOTTLE_ICON_EXPECTED.items():
                with self.subTest(bottle=hex(item_id), content=content):
                    f = self.make_fx()
                    f.put(sram, content)
                    f.put(0x7EF3BB, item_id)
                    f.call_jsl("HUD_CodexCells", m8=False, x8=False, db=0x0D)
                    self.assertEqual(f.x_hud_tiles(), expected_tiles)
                    self.assertEqual(f.x_hud_border(), (0x207D, 0xA014))

        # 2. Ocarina dynamic song colors (unlearned grey + all 6 songs including Epona bit)
        for song_idx, expected_tiles in OCARINA_ICON_EXPECTED.items():
            with self.subTest(ocarina_song=song_idx):
                f = self.make_fx()
                f.put(0x7EF3BB, 0x0D)
                if song_idx == 0:
                    f.put(0x7EF34C, 0x01)  # owned, no songs
                    f.put(0x030F, 0x00)
                elif song_idx == 6:
                    f.put(0x7EF34C, 0x01)  # Epona learned via SideQuestProg2 bit $04
                    f.put(0x7EF3B6, 0x04)
                    f.put(0x030F, 0x06)
                else:
                    f.put(0x7EF34C, song_idx + 1)
                    f.put(0x030F, song_idx)
                f.call_jsl("HUD_CodexCells", m8=False, x8=False, db=0x0D)
                self.assertEqual(f.x_hud_tiles(), expected_tiles)
                self.assertEqual(f.x_hud_border(), (0x207D, 0xA014))

        # 3. Fishing Rod ($10): MUST draw Fishing Rod ($2082,$2883,$208B,$288C) for BOTH level 1 and 2
        for rod_lvl in (1, 2):
            with self.subTest(fishing_rod_level=rod_lvl):
                f = self.make_fx()
                f.put(0x7EF351, rod_lvl)
                f.put(0x7EF3BB, 0x10)
                f.call_jsl("HUD_CodexCells", m8=False, x8=False, db=0x0D)
                self.assertEqual(f.x_hud_tiles(), (0x2082, 0x2883, 0x208B, 0x288C))
                self.assertEqual(f.x_hud_border(), (0x207D, 0xA014))

        # 4. Mirror ($0B), Book ($0E), Cane of Byrna ($1B)
        for name, item_id, sram, val, expected_tiles in (
            ("Mirror-1", 0x0B, 0x7EF353, 1, (0x2C62, 0x2C63, 0x2C72, 0x2C73)),
            ("Mirror-2", 0x0B, 0x7EF353, 2, (0x2C62, 0x2C63, 0x2C72, 0x2C73)),
            ("Book", 0x0E, 0x7EF34E, 1, (0x2C50, 0x2C51, 0x2C60, 0x2C61)),
            ("Byrna", 0x1B, 0x7EF3AC, 1, (0x2CDC, 0x2CDD, 0x2CEC, 0x2CED)),
        ):
            with self.subTest(item=name):
                f = self.make_fx()
                f.put(sram, val)
                f.put(0x7EF3BB, item_id)
                f.call_jsl("HUD_CodexCells", m8=False, x8=False, db=0x0D)
                self.assertEqual(f.x_hud_tiles(), expected_tiles)
                self.assertEqual(f.x_hud_border(), (0x207D, 0xA014))

        # 5. Menu/menu_hud_cache.asm tracks Ocarina_ValidSong_Long when X == #$0D
        cache_src = (ROOT / "Menu" / "menu_hud_cache.asm").read_text(encoding="utf-8")
        self.assertIn("CMP.b #$0D : BEQ .codex_ocarina_song", cache_src)
        self.assertIn(".codex_ocarina_song : JSL Ocarina_ValidSong_Long : BRA .codex_ammo_ready", cache_src)


if __name__ == "__main__":
    unittest.main()
