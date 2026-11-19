#!/usr/bin/env python3
"""SNES N-SPC music mastering & mix regression suite for Oracle of Secrets.

Assembles all 9 active custom tracks listed in Music/all_music.asm with asar
into an isolated LoROM image (no base ROM required), decodes every N-SPC
bytecode stream, and verifies:

1. ROM & ARAM slot/chain budgets (Lost Woods v2 slot, OW aux chain, UW main
   Color Dungeon + Stone Tower slot, Song of Healing slot, UW aux chain).
2. Master volume ceilings (calibrated to vanilla ALTTP: Hyrule Field $A0,
   Kakariko $B4, dungeons/overworld without $C8+$7F S-DSP clipping).
3. Echo warmth & stability:
   - Feedback (EFB) <= $34 (no muddy $40/$50 resonant wash).
   - Echo delay (EDL) == $02 (standard ALTTP ARAM $C000-$CFFF) and filter == $02
     (warm ALTTP low-pass FIR) everywhere echo is configured.
   - Echo L/R volume (EVOL) <= $20.
   - Percussion channels (Inst $02 Tympani, $0C Cymbal, $13/$14 Snare) are
     always DRY (their EON bit is 0 whenever percussion plays).
4. Percussion & harsh-instrument ceilings (Tympani, Snare, Cymbal, Trumpet,
   Square wave) plus melody-over-percussion lead clearance.
5. Valid stereo panning ($00..$14) and accompaniment stereo separation.
6. Static S-DSP multi-voice headroom bounds (using ALTTP's PanTable at $1178
   and echo feedback resonance 1/(1 - EFB/128)).
7. Exact note-stream & loop structure invariants (zero note/rhythm/timing
   regressions across all 9 tracks).
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUSIC_DIR = ROOT / "Music"
ALL_MUSIC_ASM = MUSIC_DIR / "all_music.asm"
MUSIC_MACROS_ASM = ROOT / "Core" / "music_macros.asm"

# ALTTP N-SPC S1.20 PanTable (ARAM $1178, entries $00..$14, center = $0A -> $51)
PAN_TABLE = (
    0x00, 0x01, 0x03, 0x07, 0x0D, 0x15, 0x1E, 0x29, 0x34, 0x42, 0x51,
    0x5E, 0x67, 0x6E, 0x73, 0x77, 0x7A, 0x7C, 0x7D, 0x7E, 0x7F,
)

# Standard N-SPC 16-step velocity table (nibbles $0..$F)
VEL_TABLE = (
    0x19, 0x32, 0x4C, 0x65, 0x72, 0x7F, 0x8C, 0x98,
    0xA5, 0xB2, 0xBF, 0xCB, 0xD8, 0xE5, 0xF2, 0xFC,
)

# N-SPC VCMD argument byte counts ($E0..$FB)
VCMD_LEN = {
    0xE0: 1, 0xE1: 1, 0xE2: 2, 0xE3: 3, 0xE4: 0, 0xE5: 1, 0xE6: 2, 0xE7: 1,
    0xE8: 2, 0xE9: 1, 0xEA: 1, 0xEB: 3, 0xEC: 0, 0xED: 1, 0xEE: 2, 0xEF: 3,
    0xF0: 1, 0xF1: 3, 0xF2: 3, 0xF3: 0, 0xF4: 1, 0xF5: 3, 0xF6: 0, 0xF7: 3,
    0xF8: 3, 0xF9: 3, 0xFA: 1, 0xFB: 2,
}

# Pure mastering/mix/pan/echo VCMDs (excluded from musical-stream fingerprint)
MIX_VCMDS = frozenset({0xE1, 0xE2, 0xE5, 0xE6, 0xED, 0xEE, 0xF5, 0xF6, 0xF7, 0xF8})

PERCUSSION_INSTS = frozenset({0x02, 0x0C, 0x13, 0x14})

# The 9 active custom tracks assembled by Music/all_music.asm
ACTIVE_TRACKS = (
    ("lost_woods_v2.asm", "LostWoodsTheme", "owmain"),
    ("frozen_hyrule.asm", "FrozenHyruleTheme", "owaux"),
    ("deku_theme.asm", "GreatDekuTreeTheme", "owaux"),
    ("great_sea.asm", "GreatSea", "owaux"),
    ("color_dungeon_theme.asm", "ColorDungeonTheme", "uwmain"),
    ("stone_tower_temple_v2.asm", "StoneTowerTempleTheme", "uwmain"),
    ("song_of_healing.asm", "SongOfHealingTheme", "uwmain"),
    ("ww_ganondorf.asm", "GanondorfBattle", "uwaux"),
    ("dungeon_theme.asm", "DungeonTheme", "uwaux"),
)


def lorom_pc(addr: int) -> int:
    return (((addr >> 16) & 0x7F) << 15) | (addr & 0x7FFF)


def rom_to_aram(bank_kind: str, snes_addr: int) -> int:
    if bank_kind == "owmain":
        return snes_addr - (0x1A9EF9 - 0x1A9EF5 + 0x20B000) + 0xD000
    if bank_kind == "owaux":
        return snes_addr - (0x1ACCAB - 0x1A9EF5 + 0x20B000) + 0x2B00
    if bank_kind == "uwmain":
        return snes_addr - 0x1B8004 + 0xD000
    if bank_kind == "uwaux":
        return snes_addr - 0x1BACC7 + 0x2B00
    raise ValueError(f"Unknown bank kind: {bank_kind}")


def assemble_custom_music() -> tuple[bytes, dict[str, int]]:
    """Assemble all 9 active custom music tracks with asar + real slot asserts."""
    harness = f"""\
lorom
incsrc "{MUSIC_MACROS_ASM}"

function owrom(a) = a-$1A9EF5+$20B000
function owmain_aram(x) = x-owrom($1A9EF9)+$D000
function owaux_aram(x) = x-owrom($1ACCAB)+$2B00
function uwmain_aram(x) = x-$1B8004+$D000
function uwaux_aram(x) = x-$1BACC7+$2B00

!SongAuxAramLimit = $3938
!SongAuxAramOWLimit = $3C00
LoadIntroSongBankExpanded = $20EF80

; Overworld main slot: Lost Woods v2
incsrc "{MUSIC_DIR / 'lost_woods_v2.asm'}"
LostWoodsThemeEnd:

; Overworld aux chain: Frozen Hyrule + Deku + Great Sea
org $20E43E : assert pc() == owrom($1AD333)
incsrc "{MUSIC_DIR / 'frozen_hyrule.asm'}"
FrozenHyruleThemeEnd:
incsrc "{MUSIC_DIR / 'deku_theme.asm'}"
incsrc "{MUSIC_DIR / 'great_sea.asm'}"
OWSongChainEnd:
  dw $0000, $0800
assert owaux_aram(OWSongChainEnd) <= !SongAuxAramOWLimit, "OW aux block overruns sample-pointer ARAM"
assert pc() <= $20F000, "OW chain overruns $20F000"
assert pc() <= $20EE00, "OW aux songs overrun the NMI area-song remap"
assert pc() <= LoadIntroSongBankExpanded, "OW aux songs overrun cold-loader reservation"

; Underworld main slots: Color Dungeon + Stone Tower v2, Song of Healing
incsrc "{MUSIC_DIR / 'color_dungeon_theme.asm'}"
ColorDungeonThemeEnd:
incsrc "{MUSIC_DIR / 'stone_tower_temple_v2.asm'}"
StoneTowerTempleThemeEnd:
assert pc() <= $1B9C0F+$5C6, "Stone Tower v2 overruns song $17"

incsrc "{MUSIC_DIR / 'song_of_healing.asm'}"
SongOfHealingThemeEnd:
assert pc() <= $1BA584, "Song of Healing overruns song $1A (ARAM $F580)"

; Underworld aux chain: WW Ganondorf + Z1 Dungeon Theme
org $1BB1D3
incsrc "{MUSIC_DIR / 'ww_ganondorf.asm'}"
GanondorfBattleEnd:
incsrc "{MUSIC_DIR / 'dungeon_theme.asm'}"
UWSongChainEnd:
  dw $0000, $0800
assert uwaux_aram(UWSongChainEnd) <= !SongAuxAramLimit, "UW aux block overruns ARAM"
assert pc() <= $1BB800, "UW aux songs overrun the bank $1B free run"
"""
    with tempfile.TemporaryDirectory(prefix="oos-music-mix-") as tmp:
        d = Path(tmp)
        asm_path = d / "music_mix_harness.asm"
        rom_path = d / "music_mix_harness.sfc"
        asm_path.write_text(harness, encoding="utf-8")
        # 2 MiB blank LoROM covers banks $00..$3F (including $1B and $20)
        rom_path.write_bytes(b"\x00" * 0x200000)
        res = subprocess.run(
            [
                "asar",
                "--no-title-check",
                "--fix-checksum=off",
                "--symbols=wla",
                str(asm_path),
                str(rom_path),
            ],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"asar failed:\n{res.stdout}\n{res.stderr}"
        sym_text = rom_path.with_suffix(".sym").read_text(encoding="utf-8")
        labels = {
            m[3]: (int(m[1], 16) << 16) | int(m[2], 16)
            for m in re.finditer(r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$", sym_text)
        }
        return rom_path.read_bytes(), labels


def load_song_aram(rom: bytes, start_snes: int, end_snes: int, bank_kind: str) -> tuple[bytearray, int]:
    """Load an assembled song slice into a 64 KiB ARAM buffer at its true ARAM base."""
    aram = bytearray(0x10000)
    base_aram = rom_to_aram(bank_kind, start_snes)
    pc_start = lorom_pc(start_snes)
    pc_end = lorom_pc(end_snes)
    size = pc_end - pc_start
    assert size > 0, f"Empty song slice ${start_snes:06X}..${end_snes:06X}"
    aram[base_aram : base_aram + size] = rom[pc_start:pc_end]
    return aram, base_aram


def parse_song(aram: bytearray, base_aram: int) -> dict:
    """Decode an assembled N-SPC song into section/channel/echo/note diagnostics."""
    p = base_aram
    sections: list[int] = []
    loop_idx: int | None = None
    while True:
        val = struct.unpack_from("<H", aram, p)[0]
        p += 2
        if val == 0x0000:
            break
        if val == 0x00FF:
            loop_target = struct.unpack_from("<H", aram, p)[0]
            loop_idx = (loop_target - base_aram) // 2
            break
        sections.append(val)

    mv_history: list[int] = []
    echo_vbits_events: list[tuple[int, int, int, int, int]] = []  # (sec, ch, eon, vl, vr)
    echo_params_events: list[tuple[int, int, int, int, int]] = []  # (sec, ch, edl, efb, flt)
    echo_fade_events: list[tuple[int, int, int, int, int]] = []  # (sec, ch, len, vl, vr)
    pans_used: list[int] = []

    # Carry N-SPC persistent state across sections (Intro -> Main)
    mv = 0xC0
    eon = 0x00
    evol = (0x00, 0x00)
    efb = 0x00
    ch_state = {c: {"inst": None, "cv": 0xFF, "pan": 0x0A, "vel": 0x0F} for c in range(8)}

    section_reports: list[dict] = []
    musical_tokens: list[tuple] = [("loop", loop_idx)]
    total_note_events = 0

    for si, sec_addr in enumerate(sections):
        ch_ptrs = [struct.unpack_from("<H", aram, sec_addr + c * 2)[0] for c in range(8)]
        active = [c for c, cp in enumerate(ch_ptrs) if cp != 0]

        # Track per-channel instruments, volumes, and exact EON state when notes fire
        sec_channels: dict[int, dict] = {}
        sec_eon_before_mid_changes: int | None = None

        # Pass 1: apply initial header global commands (MV / Echo) from channels in order
        # so channels evaluated in the same section see the section's EON/EVOL/EFB.
        for ch in active:
            cur = ch_ptrs[ch]
            seen_note = False
            while not seen_note:
                b = aram[cur]
                cur += 1
                if b == 0x00:
                    break
                if b < 0x80:
                    if 0x00 < aram[cur] < 0x80:
                        cur += 1
                elif b < 0xE0:
                    seen_note = True
                elif b == 0xEF:
                    seen_note = True
                elif b in VCMD_LEN:
                    n = VCMD_LEN[b]
                    args = list(aram[cur : cur + n])
                    cur += n
                    if b == 0xE5:
                        mv = args[0]
                    elif b == 0xF5:
                        eon = args[0]
                        evol = (args[1], args[2])
                    elif b == 0xF6:
                        eon = 0x00
                        evol = (0x00, 0x00)
                    elif b == 0xF7:
                        efb = args[1]
                    elif b == 0xF8:
                        evol = (args[1], args[2])
                else:
                    raise AssertionError(f"Unknown N-SPC opcode ${b:02X}")

        sec_eon_before_mid_changes = eon

        # Pass 2: full channel walk (including subroutine unrolling)
        for ch in active:
            st = dict(ch_state[ch])
            inst_cv_pairs: list[tuple[int | None, int]] = []
            inst_eon_pairs: list[tuple[int | None, int]] = []
            cvs_seen: list[int] = []
            insts_seen: list[int] = []
            ch_pans: list[int] = []
            ch_vels: list[int] = []
            local_eon = sec_eon_before_mid_changes
            dur = 0
            ch_notes = 0

            def walk(addr: int, depth: int = 0) -> None:
                nonlocal mv, eon, evol, efb, local_eon, dur, ch_notes, total_note_events
                cur = addr
                while True:
                    b = aram[cur]
                    cur += 1
                    if b == 0x00:
                        return
                    if b < 0x80:
                        dur = b
                        if 0x00 < aram[cur] < 0x80:
                            qvel = aram[cur]
                            cur += 1
                            st["vel"] = qvel & 0x0F
                            ch_vels.append(st["vel"])
                            musical_tokens.append(("qv", si, ch, qvel))
                    elif b < 0xE0:
                        if b != 0xC9:  # non-Rest note/tie
                            inst_cv_pairs.append((st["inst"], st["cv"]))
                            inst_eon_pairs.append((st["inst"], local_eon))
                        ch_notes += 1
                        total_note_events += 1
                        musical_tokens.append(("n", si, ch, b, dur))
                    elif b == 0xEF:
                        sub = aram[cur] | (aram[cur + 1] << 8)
                        rep = aram[cur + 2]
                        cur += 3
                        # Unroll once for rep==0, rep times for rep>=1 (preserves exact fingerprint)
                        for _ in range(max(rep, 1)):
                            walk(sub, depth + 1)
                    elif b in VCMD_LEN:
                        n = VCMD_LEN[b]
                        args = tuple(aram[cur : cur + n])
                        cur += n
                        if b not in MIX_VCMDS:
                            musical_tokens.append(("v", si, ch, b, args))
                        if b == 0xE0:
                            st["inst"] = args[0]
                            insts_seen.append(args[0])
                        elif b == 0xE1:
                            pans_used.append(args[0])
                            st["pan"] = args[0] & 0x1F
                            ch_pans.append(st["pan"])
                        elif b == 0xE5:
                            mv = args[0]
                            mv_history.append(mv)
                        elif b == 0xE6:
                            mv = args[1]
                            mv_history.append(mv)
                        elif b == 0xED:
                            st["cv"] = args[0]
                            cvs_seen.append(st["cv"])
                        elif b == 0xF5:
                            eon = args[0]
                            local_eon = args[0]
                            evol = (args[1], args[2])
                            echo_vbits_events.append((si, ch, args[0], args[1], args[2]))
                        elif b == 0xF6:
                            eon = 0x00
                            local_eon = 0x00
                            evol = (0x00, 0x00)
                        elif b == 0xF7:
                            efb = args[1]
                            echo_params_events.append((si, ch, args[0], args[1], args[2]))
                        elif b == 0xF8:
                            evol = (args[1], args[2])
                            echo_fade_events.append((si, ch, args[0], args[1], args[2]))
                    else:
                        raise AssertionError(f"Unknown N-SPC opcode ${b:02X}")

            walk(ch_ptrs[ch])
            ch_state[ch] = st
            sec_channels[ch] = {
                "insts": insts_seen or ([st["inst"]] if st["inst"] is not None else []),
                "cvs": cvs_seen or [st["cv"]],
                "pans": ch_pans or [st["pan"]],
                "vels": ch_vels or [st["vel"]],
                "inst_cv_pairs": list(dict.fromkeys(inst_cv_pairs)),
                "inst_eon_pairs": list(dict.fromkeys(inst_eon_pairs)),
                "notes": ch_notes,
            }

        # Static S-DSP multi-voice headroom calculation for this section
        gain_l = 0.0
        gain_r = 0.0
        echo_l = 0.0
        echo_r = 0.0
        for ch, info in sec_channels.items():
            cv = max(info["cvs"])
            pan = info["pans"][0]
            vel = max(info["vels"])
            v_gain = (mv / 256.0) * (cv / 256.0) * (VEL_TABLE[vel] / 256.0)
            p_r = PAN_TABLE[min(pan, 20)] / 128.0
            p_l = PAN_TABLE[20 - min(pan, 20)] / 128.0
            gain_l += v_gain * p_l
            gain_r += v_gain * p_r
            if sec_eon_before_mid_changes & (1 << ch):
                echo_l += v_gain * p_l
                echo_r += v_gain * p_r

        fb_boost = 1.0 / max(1.0 - (efb / 128.0), 0.1)
        wet_l = echo_l * (evol[0] / 128.0) * fb_boost
        wet_r = echo_r * (evol[1] / 128.0) * fb_boost

        section_reports.append({
            "mv": mv,
            "eon": sec_eon_before_mid_changes,
            "evol": evol,
            "efb": efb,
            "fb_boost": fb_boost,
            "dry_gain_sum": max(gain_l, gain_r),
            "total_gain_sum": max(gain_l + wet_l, gain_r + wet_r),
            "channels": sec_channels,
        })

    fingerprint = hashlib.sha256(repr(musical_tokens).encode("utf-8")).hexdigest()[:16]
    return {
        "sections": section_reports,
        "loop_idx": loop_idx,
        "mv_history": mv_history,
        "echo_vbits": echo_vbits_events,
        "echo_params": echo_params_events,
        "echo_fade": echo_fade_events,
        "pans": pans_used,
        "total_note_events": total_note_events,
        "fingerprint": fingerprint,
    }


class TestMusicMixMastering(unittest.TestCase):
    """Assemble and verify all 9 custom tracks in Music/all_music.asm."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rom, cls.labels = assemble_custom_music()
        end_labels = {
            "LostWoodsTheme": "LostWoodsThemeEnd",
            "FrozenHyruleTheme": "FrozenHyruleThemeEnd",
            "GreatDekuTreeTheme": "GreatDekuTreeThemeEnd",
            "GreatSea": "OWSongChainEnd",
            "ColorDungeonTheme": "ColorDungeonThemeEnd",
            "StoneTowerTempleTheme": "StoneTowerTempleThemeEnd",
            "SongOfHealingTheme": "SongOfHealingThemeEnd",
            "GanondorfBattle": "GanondorfBattleEnd",
            "DungeonTheme": "UWSongChainEnd",
        }
        cls.songs: dict[str, dict] = {}
        for filename, label, bank_kind in ACTIVE_TRACKS:
            start = cls.labels[label]
            end = cls.labels[end_labels[label]]
            aram, base_aram = load_song_aram(cls.rom, start, end, bank_kind)
            parsed = parse_song(aram, base_aram)
            parsed["start_snes"] = start
            parsed["end_snes"] = end
            parsed["size"] = lorom_pc(end) - lorom_pc(start)
            parsed["base_aram"] = base_aram
            cls.songs[filename] = parsed

    def test_all_music_includes_all_nine_tracks(self) -> None:
        text = ALL_MUSIC_ASM.read_text(encoding="utf-8")
        for filename, _, _ in ACTIVE_TRACKS:
            self.assertIn(f'incsrc "Music/{filename}"', text)

    def test_rom_and_aram_budgets(self) -> None:
        # Lost Woods v2 slot: owrom($1AADDE) + $246 = $20C12F
        self.assertLessEqual(self.labels["LostWoodsThemeEnd"], 0x20BEE9 + 0x246)
        # OW aux chain: ARAM <= $3C00 and ROM <= $20EE00
        ow_end = self.labels["OWSongChainEnd"]
        self.assertLessEqual(rom_to_aram("owaux", ow_end), 0x3C00)
        self.assertLessEqual(ow_end + 4, 0x20EE00)
        # UW main Color Dungeon + Stone Tower v2: <= $1B9C0F + $5C6 ($1BA1D5)
        self.assertLessEqual(self.labels["StoneTowerTempleThemeEnd"], 0x1B9C0F + 0x5C6)
        # Song of Healing slot: <= $1BA584
        self.assertLessEqual(self.labels["SongOfHealingThemeEnd"], 0x1BA584)
        # UW aux chain: ARAM <= $3938 and ROM <= $1BB800
        uw_end = self.labels["UWSongChainEnd"]
        self.assertLessEqual(rom_to_aram("uwaux", uw_end), 0x3938)
        self.assertLessEqual(uw_end + 4, 0x1BB800)

    def test_master_volume_ceilings(self) -> None:
        for filename, song in self.songs.items():
            self.assertTrue(song["mv_history"], f"{filename} must set %SetMasterVolume")
            for mv in song["mv_history"]:
                self.assertLessEqual(
                    mv,
                    0xA8,
                    f"{filename} master volume ${mv:02X} exceeds safe $A8 ceiling",
                )

        # Track-specific calibrated mastering windows
        self.assertIn(self.songs["lost_woods_v2.asm"]["sections"][0]["mv"], range(0x9C, 0xA9))
        self.assertIn(self.songs["great_sea.asm"]["sections"][0]["mv"], range(0x98, 0xA3))
        self.assertIn(self.songs["ww_ganondorf.asm"]["sections"][1]["mv"], range(0x98, 0xA5))
        self.assertIn(self.songs["dungeon_theme.asm"]["sections"][0]["mv"], range(0x98, 0xA1))
        self.assertLessEqual(self.songs["frozen_hyrule.asm"]["sections"][0]["mv"], 0x70)
        self.assertLessEqual(self.songs["song_of_healing.asm"]["sections"][0]["mv"], 0x78)

    def test_echo_warmth_and_delay_filter_safety(self) -> None:
        for filename, song in self.songs.items():
            for si, ch, edl, efb, flt in song["echo_params"]:
                self.assertEqual(
                    edl,
                    0x02,
                    f"{filename} sec{si} ch{ch}: EDL=${edl:02X} must be $02 (ARAM $C000-$CFFF)",
                )
                self.assertLessEqual(
                    efb,
                    0x34,
                    f"{filename} sec{si} ch{ch}: EFB=${efb:02X} exceeds warm $34 ceiling",
                )
                self.assertEqual(
                    flt,
                    0x02,
                    f"{filename} sec{si} ch{ch}: FIR filter ${flt:02X} must be $02 (warm LPF)",
                )
            for si, ch, _, vl, vr in song["echo_vbits"]:
                self.assertLessEqual(vl, 0x20, f"{filename} EchoVBits L=${vl:02X} > $20")
                self.assertLessEqual(vr, 0x20, f"{filename} EchoVBits R=${vr:02X} > $20")
            for si, ch, _, vl, vr in song["echo_fade"]:
                self.assertLessEqual(vl, 0x20, f"{filename} EchoVolumeFade L=${vl:02X} > $20")
                self.assertLessEqual(vr, 0x20, f"{filename} EchoVolumeFade R=${vr:02X} > $20")

        # Frozen Hyrule explicitly configures echo so prior overworld echo cannot bleed onto ch5 snare
        self.assertTrue(self.songs["frozen_hyrule.asm"]["echo_vbits"])
        self.assertTrue(self.songs["frozen_hyrule.asm"]["echo_params"])

    def test_percussion_channels_always_dry_in_echo(self) -> None:
        for filename, song in self.songs.items():
            for si, sec in enumerate(song["sections"]):
                for ch, info in sec["channels"].items():
                    for inst, active_eon in info["inst_eon_pairs"]:
                        if inst in PERCUSSION_INSTS and max(info["cvs"]) > 0:
                            self.assertEqual(
                                active_eon & (1 << ch),
                                0,
                                f"{filename} sec{si} ch{ch} (Inst ${inst:02X}) must stay DRY "
                                f"but EON=${active_eon:02X} has bit {ch} set",
                            )
                        # Even muted snare in dungeon_theme should stay excluded from EON
                        if inst in PERCUSSION_INSTS:
                            self.assertEqual(
                                active_eon & (1 << ch),
                                0,
                                f"{filename} sec{si} ch{ch} (Inst ${inst:02X}) should not have "
                                f"EON bit {ch} set (EON=${active_eon:02X})",
                            )

    def test_percussion_and_harsh_instrument_levels(self) -> None:
        for filename, song in self.songs.items():
            for si, sec in enumerate(song["sections"]):
                mv = sec["mv"]
                for ch, info in sec["channels"].items():
                    for inst, cv in info["inst_cv_pairs"]:
                        if inst is None or cv == 0:
                            continue
                        eff_mv_cv = (mv * cv) / 65536.0
                        # Never max out CV=$FF on harsh/percussive instruments
                        if inst in (0x02, 0x03, 0x0C, 0x11, 0x13, 0x14):
                            self.assertLess(
                                cv,
                                0xE0,
                                f"{filename} sec{si} ch{ch} Inst ${inst:02X} CV=${cv:02X} too hot",
                            )
                        if inst == 0x02:  # Tympani
                            self.assertLessEqual(
                                eff_mv_cv,
                                0.34,
                                f"{filename} sec{si} ch{ch} Tympani MV*CV={eff_mv_cv:.3f} > 0.34",
                            )
                        elif inst == 0x0C:  # Cymbal
                            self.assertLessEqual(
                                cv,
                                0xA4,
                                f"{filename} sec{si} ch{ch} Cymbal CV=${cv:02X} > $A4",
                            )
                        elif inst == 0x11:  # Trumpet
                            self.assertLessEqual(
                                cv,
                                0xC0,
                                f"{filename} sec{si} ch{ch} Trumpet CV=${cv:02X} > $C0",
                            )
                        elif inst == 0x03:  # Square wave
                            self.assertLessEqual(
                                eff_mv_cv,
                                0.35,
                                f"{filename} sec{si} ch{ch} Square MV*CV={eff_mv_cv:.3f} > 0.35",
                            )
                        elif inst in (0x13, 0x14):  # Snare
                            self.assertLessEqual(
                                eff_mv_cv,
                                0.32,
                                f"{filename} sec{si} ch{ch} Snare MV*CV={eff_mv_cv:.3f} > 0.32",
                            )

        # Lost Woods: Tympani strictly tamed (<= $64) and well below Ocarina lead
        lw_main = self.songs["lost_woods_v2.asm"]["sections"][1]["channels"]
        lw_tymp = lw_main[0]["cvs"][0]
        lw_oca = lw_main[1]["cvs"][0]
        self.assertLessEqual(lw_tymp, 0x64)
        self.assertGreaterEqual(lw_oca - lw_tymp, 0x30)

        # Great Sea: Trumpet tamed (<= $B6), Tympani tamed (<= $7C) and well below Trumpet
        gs_main = self.songs["great_sea.asm"]["sections"][1]["channels"]
        gs_tpt = gs_main[3]["cvs"][0]
        gs_tymp = gs_main[5]["cvs"][0]
        self.assertLessEqual(gs_tpt, 0xB6)
        self.assertLessEqual(gs_tymp, 0x7C)
        self.assertGreaterEqual(gs_tpt - gs_tymp, 0x34)

    def test_stereo_pan_validity_and_spread(self) -> None:
        for filename, song in self.songs.items():
            for pan in song["pans"]:
                self.assertLessEqual(
                    pan & 0x1F,
                    0x14,
                    f"{filename} invalid N-SPC pan byte ${pan:02X} (> $14)",
                )

        # Verify stereo spread on primary retouched tracks
        for filename in (
            "lost_woods_v2.asm",
            "great_sea.asm",
            "ww_ganondorf.asm",
            "dungeon_theme.asm",
            "color_dungeon_theme.asm",
            "stone_tower_temple_v2.asm",
            "deku_theme.asm",
            "song_of_healing.asm",
        ):
            distinct_pans = {
                p
                for sec in self.songs[filename]["sections"]
                for info in sec["channels"].values()
                for p in info["pans"]
            }
            self.assertGreaterEqual(
                len(distinct_pans),
                3,
                f"{filename} expected >= 3 distinct stereo pan positions, got {distinct_pans}",
            )

    def test_static_sdsp_headroom(self) -> None:
        """Worst-case dry+echo linear voice gain sum stays cleanly below S-DSP saturation."""
        for filename, song in self.songs.items():
            for si, sec in enumerate(song["sections"]):
                # Pre-fix Lost Woods hit total_gain_sum = 2.91 (severe clipping/mud)
                # and pre-fix WW Ganondorf hit dry_gain_sum > 2.20.
                # All 9 mastered tracks sit comfortably <= 1.70 (dry <= 1.50).
                self.assertLessEqual(
                    sec["dry_gain_sum"],
                    1.50,
                    f"{filename} sec{si} dry_gain_sum={sec['dry_gain_sum']:.2f} > 1.50",
                )
                self.assertLessEqual(
                    sec["total_gain_sum"],
                    1.70,
                    f"{filename} sec{si} total_gain_sum={sec['total_gain_sum']:.2f} > 1.70",
                )
                self.assertLessEqual(
                    sec["fb_boost"],
                    1.68,
                    f"{filename} sec{si} echo resonance boost={sec['fb_boost']:.2f}x > 1.68x",
                )

    def test_note_stream_and_loop_integrity(self) -> None:
        """Guard against accidental melody, rhythm, or loop regressions."""
        expected_structure = {
            "lost_woods_v2.asm": (2, 1, 694, "c1092e3d2bf7aaa7"),
            "great_sea.asm": (2, 1, 849, "64254db3bc240a16"),
            "frozen_hyrule.asm": (2, 1, 1966, "b51d5afcad7d0ef0"),
            "deku_theme.asm": (1, 0, 102, "7da6540ff27d7277"),
            "color_dungeon_theme.asm": (1, 0, 1586, "ddab63d57444440c"),
            "stone_tower_temple_v2.asm": (1, 0, 1008, "c3af5404bf3b6fad"),
            "song_of_healing.asm": (1, 0, 681, "302f63f864a035ea"),
            "ww_ganondorf.asm": (2, 1, 2196, "a610b4d0addec939"),
            "dungeon_theme.asm": (1, 0, 429, "9d318ae5fd5b28a5"),
        }
        for filename, (exp_secs, exp_loop, exp_notes, exp_fp) in expected_structure.items():
            song = self.songs[filename]
            self.assertEqual(len(song["sections"]), exp_secs, f"{filename} section count")
            self.assertEqual(song["loop_idx"], exp_loop, f"{filename} loop index")
            self.assertEqual(
                song["total_note_events"],
                exp_notes,
                f"{filename} unrolled note count changed (expected {exp_notes}, got {song['total_note_events']})",
            )
            self.assertEqual(
                song["fingerprint"],
                exp_fp,
                f"{filename} non-mix musical stream fingerprint changed",
            )


if __name__ == "__main__":
    unittest.main()
