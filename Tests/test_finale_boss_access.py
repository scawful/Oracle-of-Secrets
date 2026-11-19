"""Final Boss Sequences (Lane D) source and compiled ROM contract tests.

Verifies:
1. Sprite_Ganondorf_Prep guards Final Boss song $1F ($012C) with LDA.w $0136
   (underworld song bank loaded) matching Sprite_Kydreeok_Prep, so an overworld
   song bank cannot crash the SPC driver and hang Module19_02_LoadMusicAndScreen.
2. Ganondorf_DoorGate scans for a live Sprite_Ganondorf ($D3, covering human
   Ganondorf actions 0..7 and Ganon Beast actions 8..15) before checking
   FinaleBeat, and re-arms FinaleBeat = #$40 when Kydreeok's saved kill flag
   ($7EF005 bit 3) is set and FinaleBeat == 0, preventing empty-room softlocks
   on direct Room $00 reloads after Save & Quit or stale GanondorfFight == 3.
3. DetermineConsequencesOfFalling ($0794D9..$0794E7) routes pit transitions
   through Overworld_ResolvePitDestination, which redirects any camera-clamped
   or desynced OW $4D (Final Sanctum) pit miss ($010E == #$82 Chris Houlihan)
   to Entrance $7B (Room $0002 Kydreeok) in Dark World ($7EF3CA = #$40).
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
GANONDORF_ASM = ROOT / "Sprites" / "Bosses" / "ganondorf.asm"
KYDREEOK_ASM = ROOT / "Sprites" / "Bosses" / "kydreeok.asm"
OVERWORLD_ASM = ROOT / "Overworld" / "overworld.asm"
ROM_PATH = ROOT / "Roms" / "oos168x.sfc"
SYM_PATH = ROOT / "Roms" / "oos168x.sym"


def snes_to_pc(address: int) -> int:
    bank = (address >> 16) & 0x7F
    offset = address & 0x7FFF
    return (bank << 15) | offset


def load_symbols(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    section = None
    for raw in sym_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("["):
            section = line
            continue
        if section == "[labels]":
            m = re.fullmatch(r"([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)", line)
            if m:
                labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    return labels


class FinaleBossAccessContractTests(unittest.TestCase):
    def test_ganondorf_prep_guards_song_1f_on_underworld_song_bank(self) -> None:
        text = GANONDORF_ASM.read_text(encoding="utf-8")
        m = re.search(r"Sprite_Ganondorf_Prep:\s*\{(.*?)^\}", text, re.M | re.S)
        self.assertIsNotNone(m, "Sprite_Ganondorf_Prep block not found")
        body = m.group(1)
        guard_pos = body.find("LDA.w $0136 : BEQ .keep_song")
        song_pos = body.find("LDA.b #$1F : STA.w $012C")
        label_pos = body.find("\n  .keep_song")
        self.assertGreater(guard_pos, 0)
        self.assertGreater(song_pos, guard_pos)
        self.assertGreater(label_pos, song_pos)

    def test_ganondorf_door_gate_recovers_stale_fight_and_cleared_beat(self) -> None:
        text = GANONDORF_ASM.read_text(encoding="utf-8")
        m = re.search(r"Ganondorf_DoorGate:\s*\{(.*?)^\}", text, re.M | re.S)
        self.assertIsNotNone(m, "Ganondorf_DoorGate block not found")
        body = m.group(1)
        self.assertNotIn("CMP.b #$03 : BEQ .shut", body)
        scan_pos = body.find(".scan")
        beat_pos = body.find("LDA.w FinaleBeat : BNE .have_beat")
        kyd_flag_pos = body.find("LDA.l $7EF005 : AND.b #$08 : BEQ .wait")
        self.assertGreater(scan_pos, 0)
        self.assertGreater(beat_pos, scan_pos)
        self.assertGreater(kyd_flag_pos, beat_pos)

    def test_overworld_pit_resolution_guards_sanctum_hole_7b(self) -> None:
        text = OVERWORLD_ASM.read_text(encoding="utf-8")
        self.assertIn("Overworld_ResolvePitDestination:", text)
        self.assertIn("JSL Overworld_GetPitDestination", text)
        self.assertIn("LDA.b $8A : CMP.b #$4D : BNE .done", text)
        self.assertIn("LDA.w $010E : CMP.b #$82 : BNE .done", text)
        self.assertIn("LDA.b #$7B : STA.w $010E", text)
        self.assertIn("LDA.b #$40 : STA.l $7EF3CA", text)
        self.assertIn("JSL Overworld_ResolvePitDestination", text)
        self.assertIn("assert pc() == $0794E8", text)

    def test_kydreeok_preserves_crlf_and_remnant_recovery(self) -> None:
        raw = KYDREEOK_ASM.read_bytes()
        self.assertIn(b"\r\n", raw, "Sprites/Bosses/kydreeok.asm must preserve CRLF")
        text = raw.decode("utf-8")
        self.assertIn("Kydreeok_SaveKill:", text)
        self.assertIn("Kydreeok_Remnant:", text)

    def test_compiled_rom_bytes_when_present(self) -> None:
        if not (ROM_PATH.is_file() and SYM_PATH.is_file()):
            self.skipTest("Compiled ROM/symbols not present")
        rom = ROM_PATH.read_bytes()
        labels = load_symbols(SYM_PATH)

        def sym(name: str) -> int:
            for candidate in (name, f"Oracle_{name}", f"Overworld_{name}", f"Sprites_{name}"):
                if candidate in labels:
                    return labels[candidate]
            raise KeyError(name)

        # 1. $0794D9..$0794E7 calls LoadOverworldPitAreas and Overworld_ResolvePitDestination
        pit_areas = sym("LoadOverworldPitAreas")
        resolve_pit = sym("Overworld_ResolvePitDestination")
        hook_pc = snes_to_pc(0x0794D9)
        expected_hook = bytes([
            0x22, pit_areas & 0xFF, (pit_areas >> 8) & 0xFF, (pit_areas >> 16) & 0xFF,
            0x90, 0x05,
            0x22, 0xD9, 0xFF, 0x01,
            0x60,
            0x22, resolve_pit & 0xFF, (resolve_pit >> 8) & 0xFF, (resolve_pit >> 16) & 0xFF,
        ])
        self.assertEqual(rom[hook_pc:hook_pc + len(expected_hook)], expected_hook)

        # 2. Overworld_ResolvePitDestination body
        resolve_pc = snes_to_pc(resolve_pit)
        expected_resolve = bytes([
            0x22, 0x60, 0xB8, 0x1B,             # JSL $1BB860
            0xA5, 0x8A, 0xC9, 0x4D, 0xD0, 0x12, # LDA $8A : CMP #$4D : BNE .done
            0xAD, 0x0E, 0x01, 0xC9, 0x82, 0xD0, 0x0B, # LDA $010E : CMP #$82 : BNE .done
            0xA9, 0x7B, 0x8D, 0x0E, 0x01,       # LDA #$7B : STA $010E
            0xA9, 0x40, 0x8F, 0xCA, 0xF3, 0x7E, # LDA #$40 : STA.l $7EF3CA
            0x6B,                               # RTL
        ])
        self.assertEqual(rom[resolve_pc:resolve_pc + len(expected_resolve)], expected_resolve)

        # 3. Sprite_Ganondorf_Prep song bank guard: AD 36 01 F0 05 A9 1F 8D 2C 01
        prep_pc = snes_to_pc(sym("Sprite_Ganondorf_Prep"))
        prep_slice = rom[prep_pc:prep_pc + 0x90]
        self.assertIn(bytes([0xAD, 0x36, 0x01, 0xF0, 0x05, 0xA9, 0x1F, 0x8D, 0x2C, 0x01]), prep_slice)


if __name__ == "__main__":
    unittest.main()
