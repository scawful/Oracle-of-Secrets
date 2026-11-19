#!/usr/bin/env python3
"""Generate the reproducible 3-slot Oracle of Secrets Feature Beta Showcase .srm.

Reuses Scripts/Agents/scene_director/srm.py for SRAM block layout, checksum
validation (sum of all 16-bit LE words == 0x5A5A with fix-up at +0x4FE), and
primary/backup mirror verification.

Slots (ALTTP 6-char file-select names):
  1. LINK  - Light World Kalyxo & Full Kit (Wayward Village / Link's House):
             Gust Jar (Y), Ocarina w/ all 6 songs & Song of Soaring (X),
             Garo Mask (R), all masks/rods/bottles/rings, Master Sword +
             Red Mail + Mirror Shield, TravelSpotsVisited=$FF,
             SkySoaringLearned=$A5, zero story-breaking flags corrupted.
  2. LYRA  - Special Overworld & Sea Tour (outdoors East Kalyxo via one-shot
             checkpoint $07): full kit, Ocarina (Y) / Gust Jar (X), Zora Mask
             (R), Boat & Special/Sky Soaring ready immediately outdoors.
  3. ABYSS - Eon Abyss GBC Tour (Dark World $7EF3CA=$40, GameState=3):
             opens the Abyss/Kalyxo spawn chooser directly outside Abyss
             Windmill ($63), GBC Mirror Shield + Golden Sword + full kit,
             Twin Brothers ($00F5), DW $4B <-> LW $0B Breach Portal & Finale
             pacing ready.

Usage:
  python3 Scripts/Build/generate_showcase_srm.py --out /tmp/oracle-showcase.srm
  python3 Scripts/Build/generate_showcase_srm.py --out /tmp/oracle-showcase.srm --verify-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_AGENTS_DIR = str(ROOT / "Scripts" / "Agents")
if _AGENTS_DIR not in sys.path:
    sys.path.insert(0, _AGENTS_DIR)

from scene_director import srm as srm_mod  # noqa: E402

SRM_SIZE = srm_mod.SRM_SIZE          # 0x2000 (8192 bytes)
BLOCK_SIZE = srm_mod.BLOCK_SIZE      # 0x500 (1280 bytes per slot)
BACKUP_OFFSET = srm_mod.BACKUP_OFFSET  # 0xF00
CHECKSUM_OFF = srm_mod.CHECKSUM      # 0x4FE
VALID_SUM = srm_mod.VALID_SUM        # 0x5A5A
SAVE_BASE = srm_mod.SAVE_BASE        # 0x7EF000

# ALTTP US 1.0 NameFile_CharacterLayout raw character codes -> 16-bit SRAM word:
#   word = ((c & 0xF0) << 1) | (c & 0x0F)
CHAR_CODE: dict[str, int] = {
    " ": 0x59,
    "I": 0x5F,
}
for _i, _ch in enumerate("ABCDEFGH"):
    CHAR_CODE[_ch] = _i
for _i, _ch in enumerate("JKLMNOP"):
    CHAR_CODE[_ch] = 0x09 + _i
for _i, _ch in enumerate("QRSTUVWXYZ"):
    CHAR_CODE[_ch] = 0x10 + _i


def encode_file_name(name: str) -> bytes:
    """Encode a <=6-char uppercase ALTTP file-select name into 12 SRAM bytes."""
    padded = name.upper().ljust(6)[:6]
    out = bytearray()
    for ch in padded:
        if ch not in CHAR_CODE:
            raise ValueError(f"Unsupported ALTTP file-select character: {ch!r}")
        c = CHAR_CODE[ch]
        w = ((c & 0xF0) << 1) | (c & 0x0F)
        out.extend(w.to_bytes(2, "little"))
    return bytes(out)


def build_slot_block(
    name: str,
    u8_fields: dict[int, int],
    u16_fields: dict[int, int] | None = None,
) -> bytes:
    """Construct one valid 0x500-byte ALTTP save slot block with exact 0x5A5A checksum."""
    block = bytearray(BLOCK_SIZE)

    # Vanilla InitializeSaveFile invariants ($0CDBF6-$0CDC0B)
    block[0x20C:0x20E] = (0xF000).to_bytes(2, "little")
    block[0x20E:0x210] = (0xF000).to_bytes(2, "little")
    block[0x3E5:0x3E7] = (0x55AA).to_bytes(2, "little")  # SaveFileValidity
    block[0x405:0x407] = (0xFFFF).to_bytes(2, "little")  # DeathsMaxed init
    block[0x36F] = 0xFF                                   # CurrentKeys outdoors sentinel
    block[0x3D9:0x3E5] = encode_file_name(name)

    for addr, val in u8_fields.items():
        off = addr - SAVE_BASE
        if not (0 <= off < CHECKSUM_OFF):
            raise ValueError(f"u8 address out of save block: {addr:#08x}")
        if not (0 <= val <= 0xFF):
            raise ValueError(f"u8 value out of range for {addr:#08x}: {val:#x}")
        block[off] = val

    for addr, val in (u16_fields or {}).items():
        off = addr - SAVE_BASE
        if not (0 <= off <= CHECKSUM_OFF - 2):
            raise ValueError(f"u16 address out of save block: {addr:#08x}")
        if not (0 <= val <= 0xFFFF):
            raise ValueError(f"u16 value out of range for {addr:#08x}: {val:#x}")
        block[off:off + 2] = val.to_bytes(2, "little")

    block[CHECKSUM_OFF:CHECKSUM_OFF + 2] = b"\x00\x00"
    fix = (VALID_SUM - srm_mod.word_sum(block)) & 0xFFFF
    block[CHECKSUM_OFF:CHECKSUM_OFF + 2] = fix.to_bytes(2, "little")
    if srm_mod.word_sum(block) != VALID_SUM:
        raise AssertionError(f"Checksum computation failed for slot {name!r}")
    return bytes(block)


def _common_showcase_kit() -> tuple[dict[int, int], dict[int, int]]:
    """Shared full feature-beta showcase kit (zero story-breaking flags set)."""
    u8: dict[int, int] = {
        # Clean post-intro Oracle progression flags (sunny, no Part 0 storm)
        0x7EF300: 0x01,  # KydrogFaroreRemoved
        0x7EF301: 0x01,  # DekuMaskQuestDone
        0x7EF302: 0x01,  # ZoraMaskQuestDone
        0x7EF30F: 0x01,  # Part00Flags (first wake done)
        # All 20 Y/X Items
        0x7EF340: 0x04,  # Silver Bow + Arrows
        0x7EF341: 0x02,  # Red Boomerang
        0x7EF342: 0x01,  # Blue Hookshot (keep SwitchHook trade clear)
        0x7EF343: 50,    # Bombs
        0x7EF344: 0x02,  # Magic Powder
        0x7EF345: 0x01,  # Fire Rod
        0x7EF346: 0x01,  # Ice Rod
        0x7EF347: 0x01,  # Zora Mask
        0x7EF348: 0x01,  # Bunny Hood
        0x7EF349: 0x01,  # Deku Mask
        0x7EF34A: 0x01,  # Lamp
        0x7EF34B: 0x01,  # Hammer
        0x7EF34C: 0x07,  # Ocarina + all 6 songs (incl. Song of Soaring & Song of Time)
        0x7EF34D: 0x01,  # Roc's Feather
        0x7EF34E: 0x01,  # Book of Secrets
        0x7EF34F: 0x01,  # BottleIndex = Bottle 1
        0x7EF350: 0x01,  # Cane of Somaria
        0x7EF351: 0x02,  # Fishing Rod + Portal Rod upgrade
        0x7EF352: 0x01,  # Stone Mask
        0x7EF353: 0x02,  # Magic Mirror
        # Equipment (Master Sword + Red Mail + Mirror Shield)
        0x7EF354: 0x02,  # Titan's Mitt
        0x7EF355: 0x01,  # Pegasus Boots
        0x7EF356: 0x01,  # Zora Flippers
        0x7EF357: 0x01,  # Moon Pearl
        0x7EF358: 0x01,  # Wolf Mask
        0x7EF359: 0x02,  # Master Sword
        0x7EF35A: 0x03,  # Mirror Shield
        0x7EF35B: 0x02,  # Red Mail (all 3 tunics selectable in Equipment)
        # 4 Bottles: Red Potion, Green Potion, Blue Potion, Fairy
        0x7EF35C: 0x03,
        0x7EF35D: 0x04,
        0x7EF35E: 0x05,
        0x7EF35F: 0x06,
        # Dungeon items
        0x7EF364: 0xFF, 0x7EF365: 0xFF,
        0x7EF366: 0xFF, 0x7EF367: 0xFF,
        0x7EF368: 0xFF, 0x7EF369: 0xFF,
        # Health, Magic, Ammo, Abilities
        0x7EF36B: 0x00,  # HeartPieces 0/4
        0x7EF36C: 0x80,  # 16 Hearts max
        0x7EF36D: 0x80,  # 16 Hearts current
        0x7EF36E: 0x80,  # Full Magic
        0x7EF370: 20,    # BombCapacity
        0x7EF371: 20,    # ArrowCapacity
        0x7EF377: 70,    # Arrows
        0x7EF379: 0xFE,  # AbilityFlags (Lift/Read/Talk/Pull/Run/Swim)
        0x7EF37B: 0x01,  # Half Magic
        # Per-dungeon keys (3 each)
        **{addr: 3 for addr in range(0x7EF37C, 0x7EF38A)},
        # Spoils & Collectibles
        0x7EF38B: 5,     # Bananas
        0x7EF38D: 5,     # Pineapples
        0x7EF38F: 3,     # Rock Meat
        0x7EF391: 10,    # Seashells
        0x7EF393: 5,     # Honeycombs
        0x7EF395: 10,    # Deku Sticks
        0x7EF396: 0xFF,  # TingleMaps (all owned)
        0x7EF398: 0xFF,  # DungeonScrolls translated
        0x7EF39E: 0x02,  # IntroState done
        # Extended SRAM ($7EF3A1-$7EF3C4)
        0x7EF3A2: 0x3F,  # MAGICRINGS (all 6 rings owned)
        0x7EF3A3: 0x02,  # RingSlot1 = Power Ring
        0x7EF3A6: 0x01,  # PortalRodOwned
        0x7EF3A7: 0x03,  # EonOwlFlags (both talks done)
        0x7EF3A8: 0x06,  # BoundMask = 6 (Garo Mask ready on R)
        0x7EF3A9: 0x01,  # GoldstarOwned
        0x7EF3AA: 0xA5,  # GoldstarInventoryVersion migrated
        0x7EF3AB: 0x03,  # SavedOcarinaSong = 3 (Song of Soaring)
        0x7EF3AC: 0x01,  # ByrnaOwned
        0x7EF3AD: 0x01,  # BombchuOwned
        0x7EF3AE: 0x01,  # GustJarOwned (SwitchHookOwned alias)
        0x7EF3AF: 0x01,  # GaroMaskOwned
        0x7EF3B0: 20,    # BombchuAmmo
        0x7EF3B2: 0xA5,  # SkySoaringLearned (!SKY_SOARING_LEARNED)
        0x7EF3B9: 0x01,  # ItemBindingSavedVersion = 1
        0x7EF3BA: 0x1D,  # ItemBindingSavedY = $1D (Gust Jar)
        0x7EF3BB: 0x0D,  # ItemBindingSavedX = $0D (Ocarina)
        0x7EF3BC: 0x02,  # SwordStoryBlade = Master Sword (Lv.2)
        0x7EF3BD: 0x8D,  # SwordSlotFlags: Init($80)|WornTunic=Green($08)|Reforged($04)|HeavyOwned($01)
        0x7EF3BF: 0xFF,  # ScrollsFound (all 8)
        0x7EF3C4: 0x00,  # RichardQuestFlags = 0 (Wayward Village dog quest playable fresh)
        # World / Progression defaults (customized per slot)
        0x7EF3C6: 0x3F,  # OOSPROG2 (all intro bits set; bit 7 Part0Storm CLEAR)
        0x7EF3D6: 0x07,  # OOSPROG (Intro + HallOfSecrets + PendantQuest)
        0x7EF3D7: 0x3F,  # SideQuestProgress
        0x7EF3D8: 0x7F,  # SideQuestProgress2 (EponaSong + SongOfHealing + TingleMet + Beanstalk)
        # Travel Spots & Dreams
        0x7EF410: 0x07,  # Dreams (all 3)
        0x7EF412: 0xFF,  # TravelSpotsVisited = $FF (all 8 Kalyxo soaring spots unlocked)
        0x7EF438: 0x7F,  # SpecialTravelSpotsVisited = $7F (all 7 Lyra Sea regions + Sky = 8 pins)
    }
    u16: dict[int, int] = {
        0x7EF360: 999,   # Rupees
        0x7EF362: 999,   # RupeesDisplay
    }
    return u8, u16


SLOT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "slot": 1,
        "name": "LINK",
        "title": "Kalyxo & Full Kit Showcase (Wayward Village / Link's House)",
        "summary": (
            "Light World ($7EF3CA=$00), Link's House / Wayward Village spawn, Gust Jar (Y), "
            "Ocarina + all 6 songs (X), Garo Mask (R), all masks/bottles/rods/rings, "
            "Master Sword + Red Mail + Mirror Shield, TravelSpotsVisited=$FF, SkySoaringLearned=$A5."
        ),
    },
    {
        "slot": 2,
        "name": "LYRA",
        "title": "Special Overworld & Lyra Sea Tour (Outdoors East Kalyxo)",
        "summary": (
            "Light World ($7EF3CA=$00), one-shot outdoor East Kalyxo spawn ($36 via SpawnPoint=$07), "
            "Ocarina (Y) + Gust Jar (X) + Zora Mask (R), Boat & Special/Sky Soaring ready immediately."
        ),
    },
    {
        "slot": 3,
        "name": "ABYSS",
        "title": "Eon Abyss GBC Tour (Dark World Windmill / Breach / Twin Brothers)",
        "summary": (
            "Dark World ($7EF3CA=$40, GameState=3 -> Abyss/Kalyxo spawn chooser outside Abyss Windmill $63), "
            "GBC Mirror Shield + Golden Sword + full kit, D1-D7 Essences + Maku Seed, "
            "Twin Brothers ($00F5) & DW $4B <-> LW $0B Breach Portal ready."
        ),
    },
)


def build_showcase_srm() -> bytes:
    """Build and strictly validate the 8192-byte 3-slot Feature Beta Showcase .srm."""
    # Slot 1: LINK — Kalyxo & Full Kit (Wayward Village / Day-Night / Gust Jar / Dogs / Scrubs)
    s1_u8, s1_u16 = _common_showcase_kit()
    s1_u8.update({
        0x7EF374: 0x07,  # All 3 Pendants
        0x7EF37A: 0x32,  # D1 + D2 + D4 Essences (mid/late Kalyxo without endgame lock)
        0x7EF3C5: 0x02,  # GameState = KydrogComplete (sunny Kalyxo)
        0x7EF3C7: 0x05,  # MapIcon = D5
        0x7EF3C8: 0x00,  # SpawnPoint = Link's House (Wayward Village)
        0x7EF3CA: 0x00,  # SavedWorld = Light World
        0x7EF3D4: 0x01,  # MakuTreeQuest = Met (no forced endgame override)
    })

    # Slot 2: LYRA — Special Overworld & Sea Tour (outdoors East Kalyxo, ready for Boat/Soaring)
    s2_u8, s2_u16 = _common_showcase_kit()
    s2_u8.update({
        0x7EF374: 0x07,  # All 3 Pendants
        0x7EF37A: 0x7F,  # D1-D7 Essences
        0x7EF3A8: 0x02,  # BoundMask = 2 (Zora Mask ready on R for coast/sea)
        0x7EF3BA: 0x0D,  # ItemBindingSavedY = $0D (Ocarina / Song of Soaring ready on Y)
        0x7EF3BB: 0x1D,  # ItemBindingSavedX = $1D (Gust Jar ready on X)
        0x7EF3C5: 0x02,  # GameState = 2 (required by Spawn_GoronCheckpoint one-shot outdoor load)
        0x7EF3C7: 0x07,  # MapIcon = D7 Dragon Ship
        0x7EF3C8: 0x07,  # SpawnPoint = !Spawn_GoronCheckpoint (outdoors East Kalyxo $36)
        0x7EF3CA: 0x00,  # SavedWorld = Light World
        0x7EF3CC: 0x00,  # FollowerId = 0 (required by Boat + GoronCheckpoint)
        0x7EF3D4: 0x01,  # MakuTreeQuest = Met
    })

    # Slot 3: ABYSS — Eon Abyss GBC Tour (Dark World $40, AbyssSpawnMenu, Twin Brothers & Breach)
    s3_u8, s3_u16 = _common_showcase_kit()
    s3_u8.update({
        0x7EF359: 0x04,  # Golden Sword equipped
        0x7EF3BC: 0x04,  # SwordStoryBlade = Lv.4
        0x7EF374: 0x07,  # All 3 Pendants
        0x7EF37A: 0x7F,  # D1-D7 Essences complete (D8 open)
        0x7EF3A8: 0x06,  # BoundMask = 6 (Garo Mask on R)
        0x7EF3BA: 0x1D,  # ItemBindingSavedY = $1D (Gust Jar)
        0x7EF3BB: 0x01,  # ItemBindingSavedX = $01 (Silver Bow)
        0x7EF3C5: 0x03,  # GameState = FaroreRescued (triggers AbyssSpawnMenu -> Abyss Windmill $63)
        0x7EF3C7: 0x08,  # MapIcon = Fortress
        0x7EF3C8: 0x00,  # SpawnPoint = 0
        0x7EF3CA: 0x40,  # SavedWorld = $40 (Eon Abyss / Dark World)
        0x7EF3D4: 0x03,  # MakuTreeQuest = Met + HasSeed (Fortress / Finale ready)
    })

    blocks = (
        build_slot_block("LINK", s1_u8, s1_u16),
        build_slot_block("LYRA", s2_u8, s2_u16),
        build_slot_block("ABYSS", s3_u8, s3_u16),
    )

    srm = bytearray(SRM_SIZE)
    for file_no, blk in enumerate(blocks, start=1):
        primary, backup = srm_mod.block_offsets(file_no)
        srm[primary:primary + BLOCK_SIZE] = blk
        srm[backup:backup + BLOCK_SIZE] = blk

    data = bytes(srm)
    validate_showcase_srm(data)
    return data


def validate_showcase_srm(data: bytes) -> dict[str, Any]:
    """Validate 8192-byte SRM structure, all 3 primary+backup checksums, and mirror parity."""
    if len(data) != SRM_SIZE:
        raise ValueError(f"Expected {SRM_SIZE}-byte SRM, got {len(data)} bytes")
    slots_info: list[dict[str, Any]] = []
    for file_no in (1, 2, 3):
        primary, backup = srm_mod.block_offsets(file_no)
        p_blk = data[primary:primary + BLOCK_SIZE]
        b_blk = data[backup:backup + BLOCK_SIZE]
        p_sum = srm_mod.word_sum(p_blk)
        b_sum = srm_mod.word_sum(b_blk)
        if p_sum != VALID_SUM:
            raise ValueError(f"Slot {file_no} primary checksum {p_sum:#06x} != {VALID_SUM:#06x}")
        if b_sum != VALID_SUM:
            raise ValueError(f"Slot {file_no} backup checksum {b_sum:#06x} != {VALID_SUM:#06x}")
        if p_blk != b_blk:
            raise ValueError(f"Slot {file_no} backup mirror differs from primary block")
        # Round-trip check through scene_director.srm.edit
        if srm_mod.edit(data, file_no, []) != data:
            raise ValueError(f"Slot {file_no} failed scene_director.srm.edit round-trip")
        slots_info.append({
            "slot": file_no,
            "name": SLOT_SPECS[file_no - 1]["name"],
            "primary_offset": f"0x{primary:04X}",
            "backup_offset": f"0x{backup:04X}",
            "checksum_offset": f"0x{primary + CHECKSUM_OFF:04X}",
            "word_sum": f"0x{p_sum:04X}",
            "game_state": p_blk[0x3C5],
            "saved_world": f"0x{p_blk[0x3CA]:02X}",
            "spawn_point": p_blk[0x3C8],
            "gust_jar_owned": p_blk[0x3AE],
            "travel_spots_visited": f"0x{p_blk[0x412]:02X}",
            "special_travel_spots_visited": f"0x{p_blk[0x438]:02X}",
            "sky_soaring_learned": f"0x{p_blk[0x3B2]:02X}",
            "bound_mask": p_blk[0x3A8],
            "item_y": f"0x{p_blk[0x3BA]:02X}",
            "item_x": f"0x{p_blk[0x3BB]:02X}",
            "hearts": p_blk[0x36C] // 8,
            "rupees": int.from_bytes(p_blk[0x360:0x362], "little"),
        })
    return {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "slots": slots_info,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", required=True, type=Path, help="Output .srm path (or path to verify)")
    ap.add_argument("--verify-only", action="store_true", help="Validate an existing .srm instead of writing")
    ap.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = ap.parse_args(argv)

    if args.verify_only:
        summary = validate_showcase_srm(args.out.read_bytes())
    else:
        data = build_showcase_srm()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(data)
        summary = validate_showcase_srm(data)

    summary["path"] = str(args.out)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        verb = "Verified" if args.verify_only else "Wrote"
        print(f"[+] {verb} {args.out} ({summary['size']} bytes) sha256={summary['sha256']}")
        for s in summary["slots"]:
            print(
                f"  Slot {s['slot']} ({s['name']:<5}): sum={s['word_sum']} "
                f"GS={s['game_state']} SW={s['saved_world']} Spawn={s['spawn_point']} "
                f"GustJar={s['gust_jar_owned']} Travel={s['travel_spots_visited']} "
                f"Sky={s['sky_soaring_learned']} Y={s['item_y']} X={s['item_x']} "
                f"Mask={s['bound_mask']} Hearts={s['hearts']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
