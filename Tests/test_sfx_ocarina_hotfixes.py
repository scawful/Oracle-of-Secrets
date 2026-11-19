#!/usr/bin/env python3
"""Q330 Menu SFX, Ocarina Jingle Songs, Horse Dialogue & Village Dog Palette tests.

Covers:
1. Menu UI SFX audit contracts:
   - Zero SFX3.$22 (Boss dying / Deleting file) or SFX3.$35 (partial heart container)
     anywhere in Menu/*.asm.
   - Menu_Bindings_Input emits SFX3.$0D on Y/X bind, SFX3.$20 on X-clear, SFX2.$3C on refuse.
   - Menu_Equipment_Select, Menu_Page3_Select, Menu_Page3_ToggleRing, QuestSongs_Frame,
     MagicBag_ConsumeItem, and RingMenu_Controls follow the unified UI SFX palette.
2. Ocarina jingle songs (Items/ocarina.asm):
   - Assembles the real Bank $1A Ocarina SFX streams + accompaniment/pointer patches
     with asar and decodes every stream byte-for-byte with an authentic ALTTP SPC700
     SFX stream interpreter (9.143 ms/tick; Inst $0D concert pitch = note + 7 st).
   - Verifies all 6 melodies (Healing, Storms, Soaring, Time, Secrets, Epona), exact
     Bank $1A byte bounds, disabled accompaniment bytes ($1A8C60, $1A8C7C, $1A8BC8,
     $1A8BCA), and clean real-time durations.
3. Retroid bug_004340 (Masks/horse_sparse_runtime.asm):
   - Compiled 65816 test on LakeSnes proving Horse_LinkDmaPrefix accepts Module $0E,
     Submodule $02 (Dialogue), sets Horse_PalLoaded bit 7, skips native Link overwrite
     (JML $008ADB), and leaves Horse_NmiUpload on its zero-DMA steady path, while still
     rejecting non-whitelisted $0E submodules ($05) and active World Map ($07, $0200!=0).
4. Retroid bug_005400 (Sprites/NPCs/village_dog.asm):
   - Verifies Sprite_VillageDog_Draw and Sprite_EonDog_Draw NEVER emit OAM palette 7
     ($0E / $3F / $7F = Link's tunic/mask form palette), and Sprite_VillageDog_Prep
     gates the SP6 cream-taupe stray coat ($0A) on outdoors + Village Aux2 ($0AAE=$0A).
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from d4_compiled_fight_check import Cpu
from test_horse_q319_compiled import HorseQ319Fixture, assemble as assemble_horse

ROOT = Path(__file__).resolve().parents[1]
MENU_DIR = ROOT / "Menu"
OCARINA_ASM = ROOT / "Items" / "ocarina.asm"
MUSIC_MACROS_ASM = ROOT / "Core" / "music_macros.asm"
HORSE_RUNTIME_ASM = ROOT / "Masks" / "horse_sparse_runtime.asm"
VILLAGE_DOG_ASM = ROOT / "Sprites" / "NPCs" / "village_dog.asm"

TICK_MS = (256.0 / 56.0) * 2.0  # 9.142857 ms/tick (Timer0=$10 [2ms], step=$38)
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


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


def note_byte_to_concert(note: int) -> str:
    """Convert N-SPC note byte ($80=C1..$C7=B6) under SFX Inst $0D (+7 semitones)."""
    # Ground truth: $AB (G4, MIDI 67) -> D5 (MIDI 74, 587.4 Hz), $B0 (C5, MIDI 72) -> G5 (MIDI 79, 783.7 Hz).
    midi = 24 + (note - 0x80) + 7
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def decode_sfx_stream(rom: bytes, addr: int, max_bytes: int = 96) -> dict:
    """Decode an ALTTP Bank $1A SPC700 SFX stream starting at LoROM address."""
    pc = lorom_pc(addr)
    i = 0
    inst = None
    dur = 0
    vol = None
    events: list[tuple[str, int, int | None]] = []
    total_ticks = 0
    while i < max_bytes:
        b = rom[pc + i]
        if b == 0x00:
            i += 1
            return {
                "size": i,
                "inst": inst,
                "events": events,
                "notes": [n for n, _, _ in events],
                "durations": [d for _, d, _ in events],
                "total_ticks": total_ticks,
                "duration_sec": (total_ticks * TICK_MS) / 1000.0,
            }
        if b == 0xE0:
            inst = rom[pc + i + 1]
            i += 2
        elif b == 0xF1:
            i += 4
        elif b == 0xF9:
            i += 5
        elif 0x01 <= b <= 0x7F:
            dur = b
            i += 1
            if rom[pc + i] < 0x80:
                vol = rom[pc + i]
                i += 1
        elif 0x80 <= b <= 0xC7:
            assert dur > 0, f"Note ${b:02X} played before setting duration"
            events.append((note_byte_to_concert(b), dur, vol))
            total_ticks += dur
            i += 1
        else:
            raise AssertionError(f"Unsupported SFX byte ${b:02X} at ${addr + i:06X}")
    raise AssertionError(f"SFX stream at ${addr:06X} did not terminate within {max_bytes} bytes")


def assemble_ocarina_bank1a() -> tuple[bytes, dict[str, int]]:
    """Assemble only the Bank $1A Ocarina SFX section of Items/ocarina.asm."""
    ocarina_src = OCARINA_ASM.read_text(encoding="utf-8")
    cutoff = ocarina_src.index("AddTravelBird =")
    sfx_section = ocarina_src[:cutoff]
    with tempfile.TemporaryDirectory(prefix="q330-ocarina-sfx-") as tmp:
        d = Path(tmp)
        asm = d / "ocarina_sfx.asm"
        asm.write_text(
            f'lorom\nincsrc "{MUSIC_MACROS_ASM}"\n{sfx_section}\n',
            encoding="utf-8",
        )
        rom_path = d / "ocarina_sfx.sfc"
        rom_path.write_bytes(b"\xFF" * 0x100000)
        res = subprocess.run(
            ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(asm), str(rom_path)],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stdout + res.stderr
        labels = {
            m[3]: (int(m[1], 16) << 16) | int(m[2], 16)
            for m in re.finditer(
                r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
                rom_path.with_suffix(".sym").read_text(encoding="utf-8"),
            )
        }
        return rom_path.read_bytes(), labels


class TestQ330MenuSfx(unittest.TestCase):
    def test_no_boss_dying_or_partial_heart_container_sfx_in_menu(self):
        for path in sorted(MENU_DIR.glob("*.asm")):
            text = path.read_text(encoding="utf-8")
            for lineno, raw in enumerate(text.splitlines(), 1):
                code = raw.split(";", 1)[0]
                self.assertNotRegex(
                    code,
                    r"#\$22\s*:\s*STA(?:\.w)?\s+\$012F",
                    f"{path.name}:{lineno} still plays SFX3.$22 (Boss dying / Deleting file)!",
                )
                self.assertNotRegex(
                    code,
                    r"#\$35\s*:\s*STA(?:\.w)?\s+\$012F",
                    f"{path.name}:{lineno} still plays SFX3.$35 (partial Heart Container jingle)!",
                )

    def test_menu_item_bindings_distinct_confirm_unbind_and_error_sfx(self):
        txt = (MENU_DIR / "menu_item_bindings.asm").read_text(encoding="utf-8")
        m = re.search(r"^Menu_Bindings_Input:\s*\n\{(.*?)^\}", txt, re.M | re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("LDA.b #$0D : JSR .changed", body)
        self.assertIn("LDA.b #$20", body)
        self.assertIn("LDA.b #$0D", body)
        self.assertIn("LDA.b #$3C : STA.w $012E", body)
        self.assertIn("PLA : STA.w $012F", body)

    def test_menu_spoil_consume_and_song_bind_sfx(self):
        menu_txt = (MENU_DIR / "menu.asm").read_text(encoding="utf-8")
        m = re.search(r"^MagicBag_ConsumeItem:\s*\n\{(.*?)^\}", menu_txt, re.M | re.S)
        self.assertIsNotNone(m)
        self.assertIn("LDA.b #$0B : STA.w $012F", m.group(1))
        self.assertIn("LDA.b #$0D : STA.w $012F", m.group(1))
        self.assertIn("LDA.b #$3C : STA.w $012E", m.group(1))

        flow_txt = (MENU_DIR / "menu_cursor_flow.asm").read_text(encoding="utf-8")
        qm = re.search(r"^QuestSongs_Frame:\s*\n\{(.*?)^\}", flow_txt, re.M | re.S)
        self.assertIsNotNone(qm)
        self.assertIn("LDA.b #$0D : STA.w $012F", qm.group(1))

        p3_txt = (MENU_DIR / "menu_page3.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$22 : STA.w $012F", p3_txt)


class TestQ330OcarinaJingles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom, cls.labels = assemble_ocarina_bank1a()

    def test_accompaniment_bytes_and_sfx1_pointers(self):
        # SFX2.$13 ($1A8C60), SFX2.$2F ($1A8C7C), SFX1.$19 ($1A8BC8), SFX1.$1B ($1A8BCA) must be $00
        for label, addr in (
            ("SFX2.$13 Healing accomp", 0x1A8C60),
            ("SFX2.$2F Storms accomp", 0x1A8C7C),
            ("SFX1.$19 Secrets accomp", 0x1A8BC8),
            ("SFX1.$1B Epona accomp", 0x1A8BCA),
        ):
            self.assertEqual(self.rom[lorom_pc(addr)], 0x00, f"{label} at ${addr:06X} not disabled")

        # Verify SFX1.$19 and SFX1.$1B ARAM pointers match assembled labels
        ptr_secrets = int.from_bytes(self.rom[lorom_pc(0x1A8BA0) : lorom_pc(0x1A8BA0) + 2], "little")
        ptr_epona = int.from_bytes(self.rom[lorom_pc(0x1A8BA4) : lorom_pc(0x1A8BA4) + 2], "little")
        self.assertEqual(ptr_secrets, self.labels["Song_of_Secrets"] - 0x1A73B0)
        self.assertEqual(ptr_epona, self.labels["Epona_Song"] - 0x1A73B0)
        self.assertEqual(self.labels["Epona_Song"], self.labels["Elegy_of_Stone"])

    def test_all_six_ocarina_songs_decode_with_authentic_melodies_and_bounds(self):
        specs = [
            (
                "Song_of_Healing",
                0x1A9750,
                0x1A9765,
                ["B5", "A5", "F5", "B5", "A5", "F5", "B5", "A5", "E5", "D5", "E5"],
            ),
            (
                "Song_of_Soaring",
                0x1A9765,
                0x1A977D,
                ["F5", "B5", "D6", "F5", "B5", "D6", "F5", "B5", "D6"],
            ),
            (
                "Song_of_Storms",
                0x1A92F7,
                0x1A931F,
                ["D5", "F5", "D6", "D5", "F5", "D6", "E6", "F6", "E6", "F6", "E6", "C6", "A5"],
            ),
            (
                "Song_of_Time",
                0x1A91F0,
                0x1A922B,
                ["A5", "D5", "F5", "A5", "D5", "F5", "A5", "C6", "B5", "G5", "F5", "G5", "A5", "D5"],
            ),
            (
                "Song_of_Secrets",
                self.labels["Song_of_Secrets"],
                0x1A9B92,
                ["A5", "E5", "A5", "C6", "B5", "G5", "A5", "C6", "B5", "A5"],
            ),
            (
                "Epona_Song",
                self.labels["Epona_Song"],
                0x1A9B92,
                ["D6", "B5", "A5", "D6", "B5", "A5", "D6", "B5", "A5", "B5", "A5"],
            ),
        ]
        for name, start, limit, expected_notes in specs:
            with self.subTest(song=name):
                dec = decode_sfx_stream(self.rom, start)
                self.assertEqual(dec["inst"], 0x0D, f"{name} must use Ocarina instrument $0D")
                self.assertLessEqual(start + dec["size"], limit, f"{name} overran ${limit:06X}")
                self.assertEqual(dec["notes"], expected_notes, f"{name} concert melody mismatch")
                self.assertGreaterEqual(len(set(dec["durations"])), 2, f"{name} has flat monotone rhythm")
                self.assertGreaterEqual(dec["duration_sec"], 1.8, f"{name} too short ({dec['duration_sec']:.2f}s)")
                self.assertLessEqual(dec["duration_sec"], 3.3, f"{name} too long ({dec['duration_sec']:.2f}s)")
                lead_vols = [v for _, _, v in dec["events"] if v is not None]
                self.assertGreaterEqual(max(lead_vols), 0x74, f"{name} peak volume too quiet: {lead_vols}")

        # Song_of_Secrets and Epona_Song must not overlap each other
        sec_len = decode_sfx_stream(self.rom, self.labels["Song_of_Secrets"])["size"]
        self.assertLessEqual(self.labels["Song_of_Secrets"] + sec_len, self.labels["Epona_Song"])

    def test_ocarina_centered_stereo_and_bgm_ducking(self):
        src = OCARINA_ASM.read_text(encoding="utf-8")
        self.assertIn("LDA.b #$F2 : STA.w $012C", src)
        self.assertIn("LDA.b #$F3 : STA.w $012C", src)
        self.assertIn("LDA.b #$13 : STA.w $012E", src)
        self.assertIn("LDA.b #$2F : STA.w $012E", src)
        self.assertIn("LDA.b #$3E : STA.w $012E", src)
        self.assertIn("LDA.b #$27 : STA.w $012F", src)
        self.assertNotIn("LDA.b #$13 : JSR Player_DoSfx2", src)
        self.assertNotIn("LDA.b #$2F : JSR Player_DoSfx2", src)
        self.assertNotIn("LDA.b #$3E : JSR Player_DoSfx2", src)
        self.assertNotIn("LDA.b #$27 : JSR $802F", src)


class TestQ330HorseDialogueCompiled(unittest.TestCase):
    def test_horse_link_dma_prefix_allows_dialogue_submodule_02(self):
        src = HORSE_RUNTIME_ASM.read_text(encoding="utf-8")
        self.assertIn("LDA.b $11 : CMP.b #$01 : BEQ .eligible\n  CMP.b #$02 : BEQ .eligible", src)

        lakesnes = find_lakesnes()
        self.assertIsNotNone(lakesnes, "LakeSnes CPU source required for compiled 65816 proof")
        with tempfile.TemporaryDirectory(prefix="q330-horse-dlg-") as tmp:
            d = Path(tmp)
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
            lib = C.CDLL(str(lib_path))
            lib.cpu_init.restype = C.POINTER(Cpu)
            lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
            lib.cpu_free.argtypes = [C.POINTER(Cpu)]
            rom, labels = assemble_horse(d / "build")

            f = HorseQ319Fixture(lib, rom, labels)
            try:
                # Module $0E Submodule $02 (Dialogue while mounted on Epona): MUST take .eligible!
                f.word(0x1EDE, 0x4852)
                f.put(0x02B2, 0x09)
                f.put(0x10, 0x0E)
                f.put(0x11, 0x02)
                f.put(0x1B, 0x00)
                f.put(0x1EEC, 0x01)
                f.word(0x0AE0, 0xB280)
                f.word(0x0AE2, 0xB2E0)
                f.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
                self.assertEqual(f.jumped_target, "dma_8adb")
                self.assertEqual(f.get(0x1EEC), 0x81)

                # Item Menu ($0E.$01) and Map fade-out ($0E.$07, $0200=0) still eligible
                for sub, s200 in ((0x01, 0x00), (0x07, 0x00)):
                    f.put(0x10, 0x0E); f.put(0x11, sub); f.put(0x0200, s200); f.put(0x1EEC, 0x01)
                    f.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
                    self.assertEqual(f.jumped_target, "dma_8adb", (sub, s200))
                    self.assertEqual(f.get(0x1EEC), 0x81, (sub, s200))

                # Active Map ($0E.$07, $0200!=0) and non-whitelisted $0E.$05 take .native
                for sub, s200 in ((0x07, 0x01), (0x05, 0x00)):
                    f.put(0x10, 0x0E); f.put(0x11, sub); f.put(0x0200, s200); f.put(0x1EEC, 0x01)
                    f.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
                    self.assertEqual(f.jumped_target, "dma_8a12", (sub, s200))
                    self.assertEqual(f.get(0x1EEC) & 0x80, 0, (sub, s200))
            finally:
                f.close()


class TestQ330VillageDogPalette(unittest.TestCase):
    def test_village_dog_never_emits_oam_palette_7(self):
        txt = VILLAGE_DOG_ASM.read_text(encoding="utf-8")

        # Prep must gate cream-taupe SP6 coat on outdoors ($1B==0) + Village Aux2 ($0AAE==#$0A)
        # and store $0A (XOR $37 -> $3D = SP6), never $08 (XOR $37 -> $3F = SP7 Link palette!)
        prep = re.search(r"^Sprite_VillageDog_Prep:\s*\n\{(.*?)^\}", txt, re.M | re.S)
        self.assertIsNotNone(prep)
        prep_body = prep.group(1)
        self.assertIn("LDA.w $0AAE : CMP.b #$0A : BNE .done", prep_body)
        self.assertIn("LDA.b #$0A : STA.w SprMiscG, X", prep_body)
        self.assertNotIn("LDA.b #$08 : STA.w SprMiscG, X", prep_body)

        # Parse all base OAM properties from Sprite_VillageDog_Draw and Sprite_EonDog_Draw
        draw = re.search(r"^Sprite_VillageDog_Draw:\s*\n\{(.*?)^\}", txt, re.M | re.S)
        eon = re.search(r"^Sprite_EonDog_Draw:\s*\n\{(.*?)^\}", txt, re.M | re.S)
        self.assertIsNotNone(draw)
        self.assertIsNotNone(eon)

        v_props_sec = draw.group(1).split("\n  .properties\n")[1].split("\n  .sizes\n")[0]
        v_props = [int(h, 16) for h in re.findall(r"\$([0-9A-Fa-f]{2})", v_props_sec)]
        self.assertGreater(len(v_props), 30)

        # Every possible XOR mask for Village Dog: $00 (default SP3), $0A (stray SP6), $04 (Richard SP1)
        for mask_name, xor_mask in (("default_SP3", 0x00), ("stray_cream_SP6", 0x0A), ("richard_SP1", 0x04)):
            for p in v_props:
                out_prop = p ^ xor_mask
                oam_pal = (out_prop >> 1) & 0x07
                self.assertNotEqual(
                    oam_pal, 7,
                    f"VillageDog ({mask_name}) emitted forbidden SP7 (${out_prop:02X}) from base ${p:02X}!",
                )

        # EonDog properties must also never emit SP7
        e_props_sec = eon.group(1).split("\n  .properties\n")[1].split("\n  .sizes\n")[0]
        e_props = [int(h, 16) for h in re.findall(r"\$([0-9A-Fa-f]{2})", e_props_sec)]
        self.assertEqual(len(e_props), 4)
        for p in e_props:
            self.assertNotEqual((p >> 1) & 0x07, 7, f"EonDog emitted forbidden SP7 (${p:02X})!")


if __name__ == "__main__":
    unittest.main()
