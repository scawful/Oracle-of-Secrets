#!/usr/bin/env python3
"""Unit tests for overworld seam checker, region board, showcase .srm, and BPS packager."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for _rel in ("Scripts/Build", "Scripts/Tools", "Scripts/Agents"):
    _p = str(ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_overworld_seams as cos  # noqa: E402
import check_tile16_pins as ctp  # noqa: E402
import generate_showcase_srm as gsrm  # noqa: E402
import overworld_region_board as orb  # noqa: E402
import package_beta_bps as pbps  # noqa: E402
import scene_intent_common as sic  # noqa: E402
from scene_director import srm as srm_mod  # noqa: E402


def _lz2_compress_literals(data: bytes) -> bytes:
    """Minimal valid ALTTP LC-LZ2 stream using direct-copy (cmd 0) chunks + 0xFF end."""
    out = bytearray()
    i = 0
    while i < len(data):
        chunk = data[i:i + 32]
        out.append(len(chunk) - 1)  # cmd=0, length=len-1
        out.extend(chunk)
        i += len(chunk)
    out.append(0xFF)
    return bytes(out)


def _pc_to_snes(pc: int) -> int:
    bank = pc // 0x8000
    offset = 0x8000 + (pc % 0x8000)
    return (bank << 16) | offset


def _build_synthetic_ow_rom(
    map_grids: dict[int, list[list[int]]],
    *,
    shared_large_parent_00: bool = False,
) -> bytes:
    """Build a minimal synthetic 2 MiB ZSOW v3 ROM with deterministic Tile16/Map32 tables.

    Tile16 IDs configured:
      0x000: all walkable (char 0 -> tt 0x00)
      0x001: all solid    (char 1 -> tt 0x01)
      0x002: all deep     (char 2 -> tt 0x08)
      0x003: all shallow  (char 3 -> tt 0x09)
      0x004: all ledge    (char 4 -> tt 0x29)
      0x005: left walkable, right solid (tl=0, tr=1, bl=0, br=1)
    """
    rom = bytearray(0x200000)
    # ZSCustomOverworld v3 flags (expanded Map16 + Map32)
    rom[sic.PC_ZS_VERSION] = 3
    rom[ctp.TILE16_EXP_FLAG_PC] = 0x3D
    rom[ctp.MAP32_EXP_FLAG_PC] = 0x00
    rom[sic.PC_ZS_TILE_GFX_EN] = 0x00
    rom[sic.PC_ZS_MAIN_PAL_EN] = 0x00
    rom[sic.PC_ZS_CUSTOM_BG_EN] = 0x00

    # Parent table ($140998) & area size table ($1788D)
    for m in range(0xA0):
        rom[sic.PC_ZS_PARENT_EXPANDED + m] = m
        rom[0x1788D + m] = 0
    if shared_large_parent_00:
        for child in (0x00, 0x01, 0x08, 0x09):
            rom[sic.PC_ZS_PARENT_EXPANDED + child] = 0x00
        rom[0x1788D + 0x00] = 1  # Large 64x64

    # OverworldTileTypes ($71459, 512 bytes)
    rom[sic.PC_TILETYPE + 0] = 0x00  # walkable
    rom[sic.PC_TILETYPE + 1] = 0x01  # solid
    rom[sic.PC_TILETYPE + 2] = 0x08  # deep_water
    rom[sic.PC_TILETYPE + 3] = 0x09  # shallow_water
    rom[sic.PC_TILETYPE + 4] = 0x29  # ledge

    # Expanded Tile16 table ($1E8000, 8 bytes each: tl, tr, bl, br)
    tile_defs = {
        0: (0, 0, 0, 0),
        1: (1, 1, 1, 1),
        2: (2, 2, 2, 2),
        3: (3, 3, 3, 3),
        4: (4, 4, 4, 4),
        5: (0, 1, 0, 1),
    }
    for tid, (w0, w1, w2, w3) in tile_defs.items():
        base = ctp.TILE16_EXPANDED_PC + tid * 8
        for k, w in enumerate((w0, w1, w2, w3)):
            rom[base + k * 2:base + k * 2 + 2] = w.to_bytes(2, "little")

    # Build unique Map32 quads across all supplied 32x32 grids
    quad_to_id: dict[tuple[int, int, int, int], int] = {(0, 0, 0, 0): 0}
    quads: list[tuple[int, int, int, int]] = [(0, 0, 0, 0)]

    map32_per_map: dict[int, list[int]] = {}
    for m, grid in map_grids.items():
        ids: list[int] = []
        for by in range(16):
            for bx in range(16):
                q = (
                    grid[by * 2][bx * 2],
                    grid[by * 2][bx * 2 + 1],
                    grid[by * 2 + 1][bx * 2],
                    grid[by * 2 + 1][bx * 2 + 1],
                )
                qid = quad_to_id.get(q)
                if qid is None:
                    qid = len(quads)
                    quad_to_id[q] = qid
                    quads.append(q)
                ids.append(qid)
        map32_per_map[m] = ids

    # Write expanded Map32 tables (groups of 4 quads per 6 bytes in 4 quadrant tables)
    addrs = ctp.MAP32_EXPANDED_PCS
    for qid, q in enumerate(quads):
        g = qid // 4
        s = qid % 4
        for qi, base in enumerate(addrs):
            p = base + g * 6
            val = q[qi]
            rom[p + s] = val & 0xFF
            hi = (val >> 8) & 0x0F
            if s == 0:
                rom[p + 4] = (rom[p + 4] & 0x0F) | (hi << 4)
            elif s == 1:
                rom[p + 4] = (rom[p + 4] & 0xF0) | hi
            elif s == 2:
                rom[p + 5] = (rom[p + 5] & 0x0F) | (hi << 4)
            else:
                rom[p + 5] = (rom[p + 5] & 0xF0) | hi

    # Write LZ2 Map32 hi/lo streams starting at PC 0x100000 and set pointers at 0x1794D/0x17B2D
    cursor = 0x100000
    default_hi = _lz2_compress_literals(bytes(256))
    default_lo = _lz2_compress_literals(bytes(256))
    def_hi_snes = _pc_to_snes(cursor)
    rom[cursor:cursor + len(default_hi)] = default_hi
    cursor += len(default_hi)
    def_lo_snes = _pc_to_snes(cursor)
    rom[cursor:cursor + len(default_lo)] = default_lo
    cursor += len(default_lo)

    for m in range(0xA0):
        if m in map32_per_map:
            hi_bytes = bytes((qid >> 8) & 0xFF for qid in map32_per_map[m])
            lo_bytes = bytes(qid & 0xFF for qid in map32_per_map[m])
            hi_cmp = _lz2_compress_literals(hi_bytes)
            lo_cmp = _lz2_compress_literals(lo_bytes)
            p_hi = _pc_to_snes(cursor)
            rom[cursor:cursor + len(hi_cmp)] = hi_cmp
            cursor += len(hi_cmp)
            p_lo = _pc_to_snes(cursor)
            rom[cursor:cursor + len(lo_cmp)] = lo_cmp
            cursor += len(lo_cmp)
        else:
            p_hi, p_lo = def_hi_snes, def_lo_snes
        rom[ctp.MAP32_PTR_HI_PC + m * 3:ctp.MAP32_PTR_HI_PC + m * 3 + 3] = p_hi.to_bytes(3, "little")
        rom[ctp.MAP32_PTR_LO_PC + m * 3:ctp.MAP32_PTR_LO_PC + m * 3 + 3] = p_lo.to_bytes(3, "little")

    # Initialize all 79 Exits & 129 OW Entrances as inactive (0xFFFF)
    for i in range(0x4F):
        rom[0x16051 + i * 2:0x16053 + i * 2] = b"\xFF\xFF"
        rom[0x160EF + i * 2:0x160F1 + i * 2] = b"\xFF\xFF"
    for i in range(129):
        rom[0x0DB96F + i * 2:0x0DB971 + i * 2] = b"\xFF\xFF"
        rom[0x0DBA71 + i * 2:0x0DBA73 + i * 2] = b"\xFF\xFF"
        rom[0x0DBB73 + i] = 0xFF

    # Initialize sprite list pointers to a 0xFF terminator in bank $09 ($09:8000 -> PC 0x48000)
    rom[0x48000] = 0xFF
    for phase_base in (0x141438, 0x141578, 0x1416B8):
        for m in range(0xA0):
            rom[phase_base + m * 2:phase_base + m * 2 + 2] = (0x8000).to_bytes(2, "little")

    return bytes(rom)


class TestOverworldSeams(unittest.TestCase):
    def test_classify_tiletype(self) -> None:
        self.assertEqual(cos.classify_tiletype(0x00), "walkable")
        self.assertEqual(cos.classify_tiletype(0x40), "walkable")
        self.assertEqual(cos.classify_tiletype(0x48), "walkable")
        self.assertEqual(cos.classify_tiletype(0x65), "walkable")
        self.assertEqual(cos.classify_tiletype(0x09), "shallow_water")
        self.assertEqual(cos.classify_tiletype(0x08), "deep_water")
        self.assertEqual(cos.classify_tiletype(0x4B), "deep_water")
        self.assertEqual(cos.classify_tiletype(0x29), "ledge")
        self.assertEqual(cos.classify_tiletype(0x50), "interactive")
        self.assertEqual(cos.classify_tiletype(0x01), "solid")
        self.assertEqual(cos.classify_tiletype(0x02), "solid")
        self.assertEqual(cos.classify_tiletype(0x20), "solid")

    def test_seam_pair_alignment_and_mismatch_detection(self) -> None:
        g0 = [[0] * 32 for _ in range(32)]
        g1 = [[0] * 32 for _ in range(32)]
        # Rows 4..6: map 0 walkable -> map 1 solid (walkable_into_solid error)
        for y in (4, 5, 6):
            g1[y][0] = 1
        # Rows 10..11: map 0 deep_water -> map 1 walkable (open_sea_cutoff error)
        for y in (10, 11):
            g0[y][31] = 2
        # Row 15: map 0 deep_water -> map 1 solid (unclosed_cliff_band warn)
        g0[15][31] = 2
        g1[15][0] = 1
        # Row 20: tile 5 on map 0 has right half solid -> map 1 solid (clean match!)
        g0[20][31] = 5
        g1[20][0] = 1

        rom = _build_synthetic_ow_rom({0x00: g0, 0x01: g1})
        ctx = cos.OverworldContext(rom)
        res = cos.audit_seam_pair(ctx, 0x00, 0x01, "H", False)

        self.assertEqual(res["error_tiles"], [4, 5, 6, 10, 11])
        self.assertEqual(res["warn_tiles"], [15])
        kinds = {(sp["kind"], sp["start_tile"], sp["end_tile"]) for sp in res["spans"]}
        self.assertIn(("walkable_into_solid", 4, 6), kinds)
        self.assertIn(("open_sea_cutoff", 10, 11), kinds)
        self.assertIn(("unclosed_cliff_band", 15, 15), kinds)

    def test_shared_parent_internal_seams_ignored(self) -> None:
        g0 = [[0] * 32 for _ in range(32)]
        g1 = [[1] * 32 for _ in range(32)]
        rom = _build_synthetic_ow_rom({0x00: g0, 0x01: g1}, shared_large_parent_00=True)
        ctx = cos.OverworldContext(rom)
        seams, _ = cos.enumerate_active_seams(ctx)
        pairs = {(a, b, ax) for a, b, ax, _ in seams}
        self.assertNotIn((0x00, 0x01, "H"), pairs)
        self.assertNotIn((0x00, 0x08, "V"), pairs)
        self.assertIn((0x01, 0x02, "H"), pairs)

    def test_lyra_edge_guard_permissions_loaded(self) -> None:
        perms = cos.load_lyra_edge_permissions(ROOT)
        self.assertEqual(len(perms), 64)
        # Overlay $93-$97 and curtain $88 must be 0x00
        self.assertEqual(perms[0x88 - 0x80], 0x00)
        self.assertEqual(perms[0x93 - 0x80], 0x00)
        # Open sea/coast seams permitted; walled $A0<->$A8 and $A9<->$AA blocked
        rom = _build_synthetic_ow_rom({})
        ctx = cos.OverworldContext(rom)
        self.assertTrue(ctx.special_seam_permitted(0x98, 0x99, "H"))
        self.assertTrue(ctx.special_seam_permitted(0xB9, 0xBA, "H"))
        self.assertFalse(ctx.special_seam_permitted(0xA0, 0xA8, "V"))
        self.assertFalse(ctx.special_seam_permitted(0xA9, 0xAA, "H"))
        self.assertFalse(ctx.special_seam_permitted(0x90, 0x91, "H"))

    def test_exit_and_entrance_arrival_clearance(self) -> None:
        g0 = [[0] * 32 for _ in range(32)]
        # Solid 5x5 rock patch around (10, 10)
        for y in range(8, 14):
            for x in range(8, 14):
                g0[y][x] = 1
        rom = bytearray(_build_synthetic_ow_rom({0x00: g0}))

        # Exit 0: clean landing at (2, 2) -> px (32, 16)
        rom[0x15D8A:0x15D8C] = (0x0104).to_bytes(2, "little")
        rom[0x15E28] = 0x00
        rom[0x16051:0x16053] = (16).to_bytes(2, "little")
        rom[0x160EF:0x160F1] = (32).to_bytes(2, "little")

        # Exit 1: blocked landing deep inside solid patch at (10, 10) -> px (160, 144)
        rom[0x15D8A + 2:0x15D8C + 2] = (0x0055).to_bytes(2, "little")
        rom[0x15E28 + 1] = 0x00
        rom[0x16051 + 2:0x16053 + 2] = (144).to_bytes(2, "little")
        rom[0x160EF + 2:0x160F1 + 2] = (160).to_bytes(2, "little")

        # Entrance 0: trapped inside solid patch at (10, 10)
        tile_10_10 = (10 * 64 + 10) * 2
        rom[0x0DB96F:0x0DB971] = (0x0000).to_bytes(2, "little")
        rom[0x0DBA71:0x0DBA73] = tile_10_10.to_bytes(2, "little")
        rom[0x0DBB73] = 0x01

        # Entrance 1: OOB tile_y = 90
        tile_oob = (90 * 64 + 5) * 2
        rom[0x0DB96F + 2:0x0DB971 + 2] = (0x0000).to_bytes(2, "little")
        rom[0x0DBA71 + 2:0x0DBA73 + 2] = tile_oob.to_bytes(2, "little")
        rom[0x0DBB73 + 1] = 0x02

        ctx = cos.OverworldContext(bytes(rom))
        ex_f, ent_f = cos.audit_exits_and_entrances(ctx, {0x00})
        self.assertEqual(len(ex_f), 1)
        self.assertEqual(ex_f[0]["exit_id"], "0x01")
        self.assertEqual(ex_f[0]["kind"], "exit_landing_blocked")
        self.assertEqual(len(ent_f), 2)
        self.assertEqual({e["kind"] for e in ent_f}, {"entrance_trapped_in_solid_or_deep_water", "entrance_trigger_oob"})

    def test_markdown_report_and_region_filters(self) -> None:
        g0 = [[0] * 32 for _ in range(32)]
        g1 = [[1] * 32 for _ in range(32)]
        rom = _build_synthetic_ow_rom({0x00: g0, 0x01: g1})
        report = cos.audit_overworld_seams(rom, region="kalyxo")
        self.assertGreaterEqual(report["seam_error_pair_count"], 1)
        md = cos.format_markdown_report(report)
        self.assertIn("Overworld Seam & Arrival Audit", md)
        self.assertIn("0x00 <-> 0x01", md)


class TestOverworldRegionBoard(unittest.TestCase):
    def test_custom_grid_parser(self) -> None:
        self.assertEqual(
            orb._parse_custom_grid("90,91,92;98,99,9A"),
            [[0x90, 0x91, 0x92], [0x98, 0x99, 0x9A]],
        )
        with self.assertRaises(ValueError):
            orb._parse_custom_grid("90,91;98")

    def test_board_render_and_diff_panel_python_fallback(self) -> None:
        g0_prev = [[0] * 32 for _ in range(32)]
        g1_prev = [[3] * 32 for _ in range(32)]
        g0_new = [row[:] for row in g0_prev]
        g0_new[5][5] = 1
        g0_new[5][6] = 1
        g0_new[6][5] = 2

        rom_prev = _build_synthetic_ow_rom({0x00: g0_prev, 0x01: g1_prev})
        rom_new = _build_synthetic_ow_rom({0x00: g0_new, 0x01: g1_prev})

        with tempfile.TemporaryDirectory(prefix="oos_test_board_") as tmp:
            p_prev = Path(tmp) / "prev.sfc"
            p_new = Path(tmp) / "new.sfc"
            p_prev.write_bytes(rom_prev)
            p_new.write_bytes(rom_new)
            before_sha = hashlib.sha256(p_new.read_bytes()).hexdigest()

            img2, meta2 = orb.build_region_board(
                p_new, [[0x00, 0x01]], title="Synthetic 2-Panel", cell_px=128, use_z3ed=False
            )
            img3, meta3 = orb.build_region_board(
                p_new,
                [[0x00, 0x01]],
                title="Synthetic 3-Panel Diff",
                cell_px=128,
                use_z3ed=False,
                diff_rom_path=p_prev,
            )

            self.assertEqual(hashlib.sha256(p_new.read_bytes()).hexdigest(), before_sha)
            self.assertEqual(img2.mode, "RGB")
            self.assertGreater(img3.size[0], img2.size[0])
            self.assertEqual(meta3["diff"]["total_changed_tile16"], 3)
            self.assertEqual(meta3["diff"]["per_map_changed"], {"0x00": 3})
            self.assertEqual(meta2["seam_error_count"], 0)


class TestShowcaseSrm(unittest.TestCase):
    def test_build_determinism_and_all_three_slots(self) -> None:
        srm_a = gsrm.build_showcase_srm()
        srm_b = gsrm.build_showcase_srm()
        self.assertEqual(len(srm_a), 8192)
        self.assertEqual(srm_a, srm_b)

        meta = gsrm.validate_showcase_srm(srm_a)
        self.assertEqual(len(meta["slots"]), 3)

        # Verify all 3 primary & backup checksums and scene_director round-trip
        for slot_no, expected_name in ((1, "LINK"), (2, "LYRA"), (3, "ABYSS")):
            p_off, b_off = srm_mod.block_offsets(slot_no)
            p_blk = srm_a[p_off:p_off + srm_mod.BLOCK_SIZE]
            b_blk = srm_a[b_off:b_off + srm_mod.BLOCK_SIZE]
            self.assertEqual(p_blk, b_blk)
            self.assertEqual(srm_mod.word_sum(p_blk), srm_mod.VALID_SUM)
            self.assertEqual(p_blk[0x3D9:0x3E5], gsrm.encode_file_name(expected_name))
            self.assertEqual(srm_mod.edit(srm_a, slot_no, []), srm_a)
            # Common showcase unlocks across all 3 slots
            self.assertEqual(p_blk[0x3AE], 0x01)      # Gust Jar owned
            self.assertEqual(p_blk[0x34C], 0x07)      # Ocarina + all 6 songs
            self.assertEqual(p_blk[0x3AF], 0x01)      # Garo Mask owned
            self.assertEqual(p_blk[0x347], 0x01)      # Zora Mask
            self.assertEqual(p_blk[0x348], 0x01)      # Bunny Hood
            self.assertEqual(p_blk[0x349], 0x01)      # Deku Mask
            self.assertEqual(p_blk[0x352], 0x01)      # Stone Mask
            self.assertEqual(p_blk[0x358], 0x01)      # Wolf Mask
            self.assertEqual(p_blk[0x3AC], 0x01)      # Cane of Byrna
            self.assertEqual(p_blk[0x34E], 0x01)      # Book of Secrets
            self.assertEqual(p_blk[0x353], 0x02)      # Magic Mirror
            self.assertEqual(p_blk[0x35A], 0x03)      # Mirror Shield
            self.assertEqual(p_blk[0x35B], 0x02)      # Red Mail
            self.assertEqual(p_blk[0x412], 0xFF)      # TravelSpotsVisited = $FF
            self.assertEqual(p_blk[0x3B2], 0xA5)      # SkySoaringLearned = $A5
            self.assertEqual(p_blk[0x3C6] & 0x80, 0)  # Part0Storm clear

        # Slot-specific assertions
        s1 = srm_a[0x000:0x500]
        self.assertEqual(s1[0x3CA], 0x00)  # Light World
        self.assertEqual(s1[0x3C8], 0x00)  # Link's House
        self.assertEqual(s1[0x359], 0x02)  # Master Sword
        self.assertEqual(s1[0x3C4], 0x00)  # RichardQuestFlags fresh

        s2 = srm_a[0x500:0xA00]
        self.assertEqual(s2[0x3CA], 0x00)  # Light World
        self.assertEqual(s2[0x3C5], 0x02)  # GameState=2 (GoronCheckpoint compatible)
        self.assertEqual(s2[0x3C8], 0x07)  # Outdoors East Kalyxo checkpoint
        self.assertEqual(s2[0x3CC], 0x00)  # No follower (Boat compatible)

        s3 = srm_a[0xA00:0xF00]
        self.assertEqual(s3[0x3CA], 0x40)  # Eon Abyss Dark World
        self.assertEqual(s3[0x3C5], 0x03)  # FaroreRescued -> AbyssSpawnMenu
        self.assertEqual(s3[0x37A], 0x7F)  # D1-D7 Essences complete
        self.assertEqual(s3[0x3D4], 0x03)  # MakuTree Met + Maku Seed

    def test_validate_rejects_bad_checksum_or_mirror(self) -> None:
        good = bytearray(gsrm.build_showcase_srm())
        bad_sum = bytearray(good)
        bad_sum[0x010] ^= 0x01
        with self.assertRaises(ValueError):
            gsrm.validate_showcase_srm(bytes(bad_sum))

        bad_mirror = bytearray(good)
        bad_mirror[0xF10] ^= 0x01
        with self.assertRaises(ValueError):
            gsrm.validate_showcase_srm(bytes(bad_mirror))


class TestPackageBetaBps(unittest.TestCase):
    def test_verify_vanilla_rom_strict_check(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oos_test_van_") as tmp:
            fake = Path(tmp) / "fake.sfc"
            fake.write_bytes(b"\x00" * 1024)
            with self.assertRaises(ValueError):
                pbps.verify_vanilla_rom(fake, allow_custom=False)
            custom_info = pbps.verify_vanilla_rom(fake, allow_custom=True)
            self.assertFalse(custom_info["canonical_us_1_0"])
            self.assertEqual(custom_info["size"], 1024)

    def test_flips_round_trip_and_bundle_packaging(self) -> None:
        try:
            flips = pbps.find_flips_bin()
        except FileNotFoundError:
            self.skipTest("flips binary not installed in this environment")

        with tempfile.TemporaryDirectory(prefix="oos_test_bps_") as tmp:
            tmp_dir = Path(tmp)
            base_rom = tmp_dir / "base.sfc"
            target_rom = tmp_dir / "target.sfc"
            out_dir = tmp_dir / "release"

            base_bytes = bytes((i * 37) & 0xFF for i in range(0x10000))
            target_bytes = bytearray(base_bytes) + bytes((i * 13 + 7) & 0xFF for i in range(0x10000))
            target_bytes[0x1234:0x1244] = b"ORACLEOFSECRETS!"
            base_rom.write_bytes(base_bytes)
            target_rom.write_bytes(bytes(target_bytes))

            manifest = pbps.package_beta_release(
                label="test-v0.1",
                out_dir=out_dir,
                vanilla_path=base_rom,
                rom_path=target_rom,
                flips_bin=flips,
                skip_gates=True,
                allow_custom_vanilla=True,
            )

            self.assertTrue(manifest["round_trip_verified"])
            self.assertEqual(
                manifest["round_trip_sha256"],
                hashlib.sha256(bytes(target_bytes)).hexdigest(),
            )
            bps_path = out_dir / manifest["bps_patch"]["file"]
            srm_path = out_dir / manifest["showcase_srm"]["file"]
            manifest_path = out_dir / "oracle-of-secrets-test-v0.1.manifest.json"
            discord_path = out_dir / manifest["discord_draft_file"]
            for p in (bps_path, srm_path, manifest_path, discord_path):
                self.assertTrue(p.is_file(), f"Missing bundle artifact: {p}")

            # Independent flips --apply cross-check
            rebuilt = tmp_dir / "rebuilt.sfc"
            proc = subprocess.run(
                [str(flips), "--apply", str(bps_path), str(base_rom), str(rebuilt)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(rebuilt.read_bytes(), bytes(target_bytes))

            # Verify manifest JSON & Discord draft contents
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["label"], "test-v0.1")
            draft = discord_path.read_text(encoding="utf-8")
            self.assertIn("RomPatcher.js", draft)
            self.assertIn("Slot 1 (`LINK`)", draft)
            self.assertIn("Slot 2 (`LYRA`)", draft)
            self.assertIn("Slot 3 (`ABYSS`)", draft)
            self.assertIn(manifest["round_trip_sha256"], draft)

    def test_beta_patch_sh_help_compat(self) -> None:
        script = ROOT / "Scripts" / "Build" / "beta_patch.sh"
        proc = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        for flag in ("--out-dir", "--skip-build", "--notes", "--label", "--rom", "--vanilla"):
            self.assertIn(flag, proc.stdout)


if __name__ == "__main__":
    unittest.main()
