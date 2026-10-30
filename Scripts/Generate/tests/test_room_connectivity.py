"""Unit tests for extract_room_connectivity.py (schema_version=2).

Verifies that the connectivity evidence report distinguishes registry grid adjacency
from raw ROM-header destinations, preserves raw slot and plane identities, refuses
invalid/aliased inputs without touching prior outputs, and leaves canonical data intact.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "Scripts" / "Generate" / "extract_room_connectivity.py"
SENTINEL = '{"sentinel": "prior output must survive a refused run"}\n'


def load_extractor():
    spec = importlib.util.spec_from_file_location("extract_room_connectivity", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_synthetic_rom(headers: dict[int, dict], rom_size: int = 0x40000) -> bytes:
    """Create a minimal valid SNES LoROM bytearray with synthetic room headers.

    Pointers:
      kRoomHeaderPointer (0xB5DD) -> SNES $04:8000 -> PC 0x20000
      kRoomHeaderPointerBank (0xB5E7) -> 0x04
      Room pointer table: PC 0x20000 + (room_id * 2)
      Room headers start at PC 0x21000 (SNES $04:9000 + room_id * 16)
    """
    rom = bytearray(rom_size)
    # Base pointer table at $04:8000 (PC 0x20000)
    rom[0xB5DD] = 0x00
    rom[0xB5DE] = 0x80
    rom[0xB5DF] = 0x04
    rom[0xB5E7] = 0x04

    base_pc = 0x20000
    header_base_pc = 0x21000
    header_base_snes_offset = 0x9000

    for rid, hdata in headers.items():
        loc_offset = header_base_snes_offset + (rid * 16)
        loc_pc = header_base_pc + (rid * 16)

        table_entry = base_pc + (rid * 2)
        rom[table_entry] = loc_offset & 0xFF
        rom[table_entry + 1] = (loc_offset >> 8) & 0xFF

        rom[loc_pc] = hdata.get("bg2_collision", 0)
        rom[loc_pc + 1] = hdata.get("palette", 0)
        rom[loc_pc + 2] = hdata.get("blockset", 0)
        rom[loc_pc + 3] = hdata.get("spriteset", 0)
        rom[loc_pc + 4] = hdata.get("effect", 0)
        rom[loc_pc + 5] = hdata.get("tag1", 0)
        rom[loc_pc + 6] = hdata.get("tag2", 0)

        pit_plane = hdata.get("pit_plane", 0) & 0x03
        s0_plane = hdata.get("stair0_plane", 0) & 0x03
        s1_plane = hdata.get("stair1_plane", 0) & 0x03
        s2_plane = hdata.get("stair2_plane", 0) & 0x03
        s3_plane = hdata.get("stair3_plane", 0) & 0x03

        rom[loc_pc + 7] = pit_plane | (s0_plane << 2) | (s1_plane << 4) | (s2_plane << 6)
        rom[loc_pc + 8] = s3_plane
        rom[loc_pc + 9] = hdata.get("holewarp", 0)

        stair_rooms = hdata.get("staircase_rooms", [0, 0, 0, 0])
        for sidx in range(4):
            rom[loc_pc + 10 + sidx] = stair_rooms[sidx] if sidx < len(stair_rooms) else 0

    return bytes(rom)


def make_synthetic_registry(dungeons: list[dict]) -> dict:
    return {
        "_meta": {
            "description": "Synthetic test registry",
        },
        "dungeons": dungeons,
    }


class RoomConnectivityTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_extractor()

    def test_grid_neighbors_remain_candidates_and_non_neighbors_absent(self):
        """Grid neighbors with no door data remain candidates; non-neighbors are absent."""
        registry = make_synthetic_registry([
            {
                "id": "D1",
                "name": "Test Dungeon",
                "rooms": [
                    {"id": "0x10", "name": "Room 10", "grid_row": 1, "grid_col": 0, "type": "normal"},
                    {"id": "0x11", "name": "Room 11", "grid_row": 1, "grid_col": 1, "type": "normal"},
                    {"id": "0x22", "name": "Room 22", "grid_row": 2, "grid_col": 2, "type": "normal"},
                ],
            }
        ])
        rom_bytes = make_synthetic_rom({
            0x10: {},
            0x11: {},
            0x22: {},
        })

        report = self.mod.build_connectivity_report(rom_bytes, registry)
        d1 = report["dungeons"][0]

        # No door key
        self.assertNotIn("doors", d1)

        candidates = d1["adjacency_candidates"]
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c["from_room"], "0x10")
        self.assertEqual(c["to_room"], "0x11")
        self.assertEqual(c["direction"], "east")
        self.assertEqual(c["source"], "registry_grid")
        self.assertEqual(c["verification_status"], "unverified")

        # Diagonal / non-adjacent room 0x22 is absent from candidates
        for cand in candidates:
            self.assertNotIn("0x22", cand["rooms"])

    def test_one_way_stairs_never_gain_reverse_record(self):
        """One-way stairs never gain a reverse record; reciprocity is not invented."""
        registry = make_synthetic_registry([
            {
                "id": "D1",
                "name": "Test Dungeon",
                "rooms": [
                    {"id": "0x10", "name": "Room 10", "grid_row": 0, "grid_col": 0, "type": "normal"},
                    {"id": "0x20", "name": "Room 20", "grid_row": 2, "grid_col": 2, "type": "normal"},
                ],
            }
        ])
        # Room 0x10 has stair slot 0 -> 0x20; Room 0x20 has all zero destinations
        rom_bytes = make_synthetic_rom({
            0x10: {"staircase_rooms": [0x20, 0, 0, 0]},
            0x20: {"staircase_rooms": [0, 0, 0, 0]},
        })

        report = self.mod.build_connectivity_report(rom_bytes, registry)
        d1 = report["dungeons"][0]
        dests = d1["header_destinations"]

        # Find stair records originating from 0x10 and 0x20
        dests_from_10 = [d for d in dests if d["source_room"] == "0x10" and d["transition_kind"] == "stair"]
        dests_from_20 = [d for d in dests if d["source_room"] == "0x20" and d["transition_kind"] == "stair"]

        slot0_from_10 = [d for d in dests_from_10 if d["slot"] == 0][0]
        self.assertEqual(slot0_from_10["target_room"], "0x20")

        # 0x20 has NO stair pointing to 0x10
        for d in dests_from_20:
            self.assertNotEqual(d["target_room"], "0x10")

    def test_duplicate_target_slots_retain_slot_and_plane_identity(self):
        """Duplicate-target slots retain distinct slot index and plane identity."""
        registry = make_synthetic_registry([
            {
                "id": "D1",
                "name": "Test Dungeon",
                "rooms": [
                    {"id": "0x10", "name": "Room 10", "grid_row": 0, "grid_col": 0, "type": "normal"},
                    {"id": "0x11", "name": "Room 11", "grid_row": 0, "grid_col": 1, "type": "normal"},
                ],
            }
        ])
        # Slot 0 -> 0x11 (plane 1), Slot 1 -> 0x11 (plane 2)
        rom_bytes = make_synthetic_rom({
            0x10: {
                "stair0_plane": 1,
                "stair1_plane": 2,
                "staircase_rooms": [0x11, 0x11, 0, 0],
            },
            0x11: {},
        })

        report = self.mod.build_connectivity_report(rom_bytes, registry)
        d1 = report["dungeons"][0]
        stair_dests = [
            d for d in d1["header_destinations"]
            if d["source_room"] == "0x10" and d["transition_kind"] == "stair" and d["target_room"] == "0x11"
        ]

        self.assertEqual(len(stair_dests), 2, "Duplicate targets must not be deduplicated")
        self.assertEqual(stair_dests[0]["slot"], 0)
        self.assertEqual(stair_dests[0]["header_byte_offset"], 10)
        self.assertEqual(stair_dests[0]["destination_plane"], 1)

        self.assertEqual(stair_dests[1]["slot"], 1)
        self.assertEqual(stair_dests[1]["header_byte_offset"], 11)
        self.assertEqual(stair_dests[1]["destination_plane"], 2)

    def test_reciprocal_headers_remain_directed_observations(self):
        """Reciprocal headers remain two directed observations, not a bidirectional traversal claim."""
        registry = make_synthetic_registry([
            {
                "id": "D1",
                "name": "Test Dungeon",
                "rooms": [
                    {"id": "0x10", "name": "Room 10", "grid_row": 0, "grid_col": 0, "type": "normal"},
                    {"id": "0x11", "name": "Room 11", "grid_row": 0, "grid_col": 1, "type": "normal"},
                ],
            }
        ])
        rom_bytes = make_synthetic_rom({
            0x10: {"staircase_rooms": [0x11, 0, 0, 0]},
            0x11: {"staircase_rooms": [0x10, 0, 0, 0]},
        })

        report = self.mod.build_connectivity_report(rom_bytes, registry)
        d1 = report["dungeons"][0]

        dests = [d for d in d1["header_destinations"] if d["transition_kind"] == "stair"]
        d_10_to_11 = [d for d in dests if d["source_room"] == "0x10" and d["target_room"] == "0x11"]
        d_11_to_10 = [d for d in dests if d["source_room"] == "0x11" and d["target_room"] == "0x10"]

        self.assertEqual(len(d_10_to_11), 1)
        self.assertEqual(len(d_11_to_10), 1)
        self.assertEqual(d_10_to_11[0]["verification_status"], "unverified")
        self.assertEqual(d_11_to_10[0]["verification_status"], "unverified")

        # Text rendering must not use bidirectional arrow
        text_out = self.mod.format_text(report)
        self.assertNotIn("↔", text_out)
        self.assertIn("0x10 stair slot 0", text_out)
        self.assertIn("0x11 stair slot 0", text_out)

    def test_stale_targets_synthetic_room35_and_room96_models(self):
        """Stale header targets without trigger evidence remain unverified; retain raw targets."""
        registry = make_synthetic_registry([
            {
                "id": "D4",
                "name": "Zora Temple",
                "rooms": [
                    {"id": "0x25", "name": "Room 25", "grid_row": 2, "grid_col": 5, "type": "normal"},
                    {"id": "0x35", "name": "Room 35 (Deep Well)", "grid_row": 3, "grid_col": 5, "type": "normal"},
                ],
            },
            {
                "id": "D8",
                "name": "Sky Tower",
                "rooms": [
                    {"id": "0x96", "name": "Room 96 (Empty)", "grid_row": 9, "grid_col": 6, "type": "normal"},
                ],
            },
        ])
        # Model Room 0x35: stair header target 0x25 without trigger
        # Model Room 0x96: empty room with stale targets 0x40, 0x41
        rom_bytes = make_synthetic_rom({
            0x25: {},
            0x35: {"staircase_rooms": [0x25, 0, 0, 0]},
            0x96: {"holewarp": 0x40, "staircase_rooms": [0x41, 0, 0, 0]},
        })

        report = self.mod.build_connectivity_report(rom_bytes, registry)

        # Room 35
        d4_dests = report["dungeons"][0]["header_destinations"]
        r35_dests = [d for d in d4_dests if d["source_room"] == "0x35" and d["transition_kind"] == "stair" and d["slot"] == 0]
        self.assertEqual(len(r35_dests), 1)
        self.assertEqual(r35_dests[0]["target_room"], "0x25")
        self.assertEqual(r35_dests[0]["verification_status"], "unverified")
        self.assertEqual(r35_dests[0]["lookup_status"], "same_dungeon")

        # Room 96
        d8_dests = report["dungeons"][1]["header_destinations"]
        r96_pit = [d for d in d8_dests if d["source_room"] == "0x96" and d["transition_kind"] == "pit"][0]
        self.assertEqual(r96_pit["raw_target_byte"], 0x40)
        self.assertEqual(r96_pit["lookup_status"], "unregistered")
        self.assertEqual(r96_pit["verification_status"], "unverified")

        r96_stair = [d for d in d8_dests if d["source_room"] == "0x96" and d["transition_kind"] == "stair" and d["slot"] == 0][0]
        self.assertEqual(r96_stair["raw_target_byte"], 0x41)
        self.assertEqual(r96_stair["lookup_status"], "unregistered")
        self.assertEqual(r96_stair["verification_status"], "unverified")

    def test_raw_zero_self_cross_dungeon_and_unregistered_targets(self):
        """Retain raw 0x00, self, cross-dungeon, and unregistered targets."""
        registry = make_synthetic_registry([
            {
                "id": "D1",
                "name": "Dungeon One",
                "rooms": [
                    {"id": "0x10", "name": "Room 10", "grid_row": 0, "grid_col": 0, "type": "normal"},
                ],
            },
            {
                "id": "D2",
                "name": "Dungeon Two",
                "rooms": [
                    {"id": "0x20", "name": "Room 20", "grid_row": 0, "grid_col": 0, "type": "normal"},
                ],
            },
        ])
        # Room 0x10 targets:
        # pit: 0x00 (raw 0)
        # stair 0: 0x10 (self)
        # stair 1: 0x20 (cross-dungeon to D2)
        # stair 2: 0xFE (unregistered)
        # stair 3: 0x00 (raw 0)
        rom_bytes = make_synthetic_rom({
            0x10: {
                "holewarp": 0x00,
                "staircase_rooms": [0x10, 0x20, 0xFE, 0x00],
            },
            0x20: {},
        })

        report = self.mod.build_connectivity_report(rom_bytes, registry)
        d1_dests = report["dungeons"][0]["header_destinations"]

        # Pit -> 0x00
        pit = [d for d in d1_dests if d["transition_kind"] == "pit"][0]
        self.assertEqual(pit["raw_target_byte"], 0)
        self.assertEqual(pit["target_room"], "0x00")
        self.assertEqual(pit["lookup_status"], "unregistered")

        # Stair 0 -> self (0x10)
        s0 = [d for d in d1_dests if d["transition_kind"] == "stair" and d["slot"] == 0][0]
        self.assertEqual(s0["raw_target_byte"], 0x10)
        self.assertTrue(s0["is_self_target"])
        self.assertEqual(s0["lookup_status"], "same_dungeon")

        # Stair 1 -> cross-dungeon (0x20 in D2)
        s1 = [d for d in d1_dests if d["transition_kind"] == "stair" and d["slot"] == 1][0]
        self.assertEqual(s1["raw_target_byte"], 0x20)
        self.assertEqual(s1["lookup_status"], "cross_dungeon")
        self.assertEqual(s1["target_dungeon_id"], "D2")

        # Stair 2 -> unregistered (0xFE)
        s2 = [d for d in d1_dests if d["transition_kind"] == "stair" and d["slot"] == 2][0]
        self.assertEqual(s2["raw_target_byte"], 0xFE)
        self.assertEqual(s2["lookup_status"], "unregistered")

        # Stair 3 -> 0x00
        s3 = [d for d in d1_dests if d["transition_kind"] == "stair" and d["slot"] == 3][0]
        self.assertEqual(s3["raw_target_byte"], 0)
        self.assertEqual(s3["lookup_status"], "unregistered")

    def test_refusal_missing_or_truncated_inputs_preserves_output(self):
        """Invalid or truncated inputs refuse and preserve prior output sentinel."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            out_file = tmp / "report.json"
            out_file.write_text(SENTINEL, encoding="utf-8")

            # Missing ROM
            rc = self.mod.main([
                "--rom", str(tmp / "nonexistent.sfc"),
                "--registry", "Docs/Dev/Planning/dungeons.json",
                "--output", str(out_file),
            ])
            self.assertEqual(rc, 1)
            self.assertEqual(out_file.read_text(encoding="utf-8"), SENTINEL)

            # Truncated ROM
            trunc_rom = tmp / "trunc.sfc"
            trunc_rom.write_bytes(b"short")
            rc = self.mod.main([
                "--rom", str(trunc_rom),
                "--registry", "Docs/Dev/Planning/dungeons.json",
                "--output", str(out_file),
            ])
            self.assertEqual(rc, 1)
            self.assertEqual(out_file.read_text(encoding="utf-8"), SENTINEL)

            # Malformed registry
            bad_reg = tmp / "bad_reg.json"
            bad_reg.write_text("not json", encoding="utf-8")
            valid_rom = tmp / "valid.sfc"
            valid_rom.write_bytes(make_synthetic_rom({0x10: {}}))
            rc = self.mod.main([
                "--rom", str(valid_rom),
                "--registry", str(bad_reg),
                "--output", str(out_file),
            ])
            self.assertEqual(rc, 1)
            self.assertEqual(out_file.read_text(encoding="utf-8"), SENTINEL)

    def test_refusal_output_alias_preserves_inputs(self):
        """Output aliases of ROM or registry refuse and preserve input hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rom_file = tmp / "rom.sfc"
            rom_bytes = make_synthetic_rom({0x10: {}})
            rom_file.write_bytes(rom_bytes)
            rom_hash_before = hashlib.sha256(rom_bytes).hexdigest()

            reg_file = tmp / "registry.json"
            reg_data = make_synthetic_registry([{
                "id": "D1", "name": "D", "rooms": [{"id": "0x10", "name": "R", "grid_row": 0, "grid_col": 0, "type": "normal"}]
            }])
            reg_bytes = json.dumps(reg_data).encode("utf-8")
            reg_file.write_bytes(reg_bytes)
            reg_hash_before = hashlib.sha256(reg_bytes).hexdigest()

            # Output is exact path to ROM
            rc = self.mod.main([
                "--rom", str(rom_file),
                "--registry", str(reg_file),
                "--output", str(rom_file),
            ])
            self.assertEqual(rc, 1)
            self.assertEqual(hashlib.sha256(rom_file.read_bytes()).hexdigest(), rom_hash_before)

            # Output is exact path to registry
            rc = self.mod.main([
                "--rom", str(rom_file),
                "--registry", str(reg_file),
                "--output", str(reg_file),
            ])
            self.assertEqual(rc, 1)
            self.assertEqual(hashlib.sha256(reg_file.read_bytes()).hexdigest(), reg_hash_before)

            # Output is symlink alias to ROM
            sym_rom = tmp / "sym_rom.sfc"
            try:
                sym_rom.symlink_to(rom_file)
                rc = self.mod.main([
                    "--rom", str(rom_file),
                    "--registry", str(reg_file),
                    "--output", str(sym_rom),
                ])
                self.assertEqual(rc, 1)
                self.assertEqual(hashlib.sha256(rom_file.read_bytes()).hexdigest(), rom_hash_before)
            except OSError:
                pass  # On systems without symlink permission

    def test_json_and_text_parity_deterministic_ordering_metadata_preserved(self):
        """JSON/text express the same evidence; schema is 2; metadata is preserved; bytes unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rom_file = tmp / "rom.sfc"
            rom_bytes = make_synthetic_rom({
                0x10: {"stair0_plane": 1, "staircase_rooms": [0x11, 0, 0, 0]},
                0x11: {},
            })
            rom_file.write_bytes(rom_bytes)
            rom_hash = hashlib.sha256(rom_bytes).hexdigest()

            reg_file = tmp / "registry.json"
            reg_data = make_synthetic_registry([{
                "id": "D1",
                "name": "Dungeon One",
                "vanilla_name": "Vanilla One",
                "rooms": [
                    {"id": "0x10", "name": "Room Ten", "floor": "B1", "grid_row": 1, "grid_col": 0, "type": "custom_type"},
                    {"id": "0x11", "name": "Room Eleven", "floor": "B1", "grid_row": 1, "grid_col": 1, "type": "custom_type2"},
                ],
            }])
            reg_bytes = json.dumps(reg_data, indent=2).encode("utf-8")
            reg_file.write_bytes(reg_bytes)
            reg_hash = hashlib.sha256(reg_bytes).hexdigest()

            out_json1 = tmp / "report1.json"
            out_json2 = tmp / "report2.json"
            out_text = tmp / "report.txt"

            rc1 = self.mod.main(["--rom", str(rom_file), "--registry", str(reg_file), "--format", "json", "--output", str(out_json1)])
            self.assertEqual(rc1, 0)

            rc2 = self.mod.main(["--rom", str(rom_file), "--registry", str(reg_file), "--format", "json", "--output", str(out_json2)])
            self.assertEqual(rc2, 0)

            rc3 = self.mod.main(["--rom", str(rom_file), "--registry", str(reg_file), "--format", "text", "--output", str(out_text)])
            self.assertEqual(rc3, 0)

            # Deterministic runs produce identical bytes
            self.assertEqual(out_json1.read_bytes(), out_json2.read_bytes())

            data = json.loads(out_json1.read_text(encoding="utf-8"))
            self.assertEqual(data["_meta"]["schema_version"], 2)
            self.assertEqual(data["_meta"]["rom_sha256"], rom_hash)
            self.assertEqual(data["_meta"]["registry_sha256"], reg_hash)

            # Metadata preserved
            r10 = data["dungeons"][0]["rooms"][0]
            self.assertEqual(r10["floor"], "B1")
            self.assertEqual(r10["type"], "custom_type")

            # Inputs unchanged
            self.assertEqual(hashlib.sha256(rom_file.read_bytes()).hexdigest(), rom_hash)
            self.assertEqual(hashlib.sha256(reg_file.read_bytes()).hexdigest(), reg_hash)

            # Text content expresses the same candidates and destinations
            text_content = out_text.read_text(encoding="utf-8")
            self.assertIn("schema_version=2", text_content)
            self.assertIn("0x10 -> 0x11", text_content)
            self.assertIn("0x10 stair slot 0 (byte +10) -> 0x11", text_content)

    def test_old_code_failure_control(self):
        """Capture old-code false-door and false-reciprocity failure control.

        Demonstrates that old code:
        1. Emitted a 'doors' record from grid adjacency without door data.
        2. Deduplicated two stair slots and invented reciprocity '↔'.
        3. Dropped 0x00, self, and cross-dungeon targets.

        Demonstrates that new code fixes all of these behaviors.
        """
        # Old code logic simulation:
        def old_compute_doors(rooms):
            doors = []
            for i, ra in enumerate(rooms):
                for rb in rooms[i + 1:]:
                    dr = abs(ra["grid_row"] - rb["grid_row"])
                    dc = abs(ra["grid_col"] - rb["grid_col"])
                    if dr + dc == 1:
                        direction = ("south" if rb["grid_row"] > ra["grid_row"] else "north") if dr == 1 else ("east" if rb["grid_col"] > ra["grid_col"] else "west")
                        doors.append({"from": ra["id"], "to": rb["id"], "direction": direction})
            return doors

        def old_build_stairs(rooms_dict, headers):
            stairs = []
            seen = set()
            for rid, h in headers.items():
                for dest in h.get("staircase_rooms", []):
                    if dest == 0 or dest == rid:
                        continue
                    pair = tuple(sorted([rid, dest]))
                    if pair in seen:
                        continue
                    seen.add(pair)
                    dest_info = rooms_dict.get(dest)
                    from_info = rooms_dict.get(rid)
                    if dest_info and from_info and dest_info["dungeon_id"] == from_info["dungeon_id"]:
                        stairs.append({
                            "from": f"0x{rid:02X}",
                            "to": f"0x{dest:02X}",
                            "label": f"{from_info['name']} ↔ {dest_info['name']}",
                        })
            return stairs

        rooms = [
            {"id": "0x10", "name": "Room A", "grid_row": 1, "grid_col": 0, "dungeon_id": "D1"},
            {"id": "0x11", "name": "Room B", "grid_row": 1, "grid_col": 1, "dungeon_id": "D1"},
        ]
        rooms_dict = {0x10: rooms[0], 0x11: rooms[1]}
        headers = {
            0x10: {"staircase_rooms": [0x11, 0x11, 0x00, 0x10]},  # two to 0x11, one zero, one self
            0x11: {"staircase_rooms": [0, 0, 0, 0]},
        }

        # Old code execution:
        old_doors = old_compute_doors(rooms)
        old_stairs = old_build_stairs(rooms_dict, headers)

        # Old code flaw 1: false door record
        self.assertEqual(len(old_doors), 1)
        self.assertEqual(old_doors[0]["from"], "0x10")
        self.assertEqual(old_doors[0]["to"], "0x11")

        # Old code flaw 2: collapsed 2 slots into 1, invented reciprocity ↔
        self.assertEqual(len(old_stairs), 1)
        self.assertIn("↔", old_stairs[0]["label"])
        self.assertEqual(old_stairs[0]["label"], "Room A ↔ Room B")

        # Now run new code on the same input:
        rom_bytes = make_synthetic_rom(headers)
        registry = make_synthetic_registry([{
            "id": "D1", "name": "D", "rooms": [
                {"id": "0x10", "name": "Room A", "grid_row": 1, "grid_col": 0, "type": "normal"},
                {"id": "0x11", "name": "Room B", "grid_row": 1, "grid_col": 1, "type": "normal"},
            ]
        }])
        report = self.mod.build_connectivity_report(rom_bytes, registry)
        d1 = report["dungeons"][0]

        # New code property 1: no 'doors' key; adjacency candidates explicitly unverified
        self.assertNotIn("doors", d1)
        self.assertEqual(len(d1["adjacency_candidates"]), 1)
        self.assertEqual(d1["adjacency_candidates"][0]["source"], "registry_grid")
        self.assertEqual(d1["adjacency_candidates"][0]["verification_status"], "unverified")

        # New code property 2: preserves both slot 0 and slot 1 separately
        dests_10 = [d for d in d1["header_destinations"] if d["source_room"] == "0x10" and d["transition_kind"] == "stair"]
        dests_to_11 = [d for d in dests_10 if d["target_room"] == "0x11"]
        self.assertEqual(len(dests_to_11), 2)
        self.assertEqual(dests_to_11[0]["slot"], 0)
        self.assertEqual(dests_to_11[1]["slot"], 1)

        # New code property 3: retains zero and self targets
        zero_targets = [d for d in dests_10 if d["raw_target_byte"] == 0]
        self.assertEqual(len(zero_targets), 1)
        self.assertEqual(zero_targets[0]["slot"], 2)

        self_targets = [d for d in dests_10 if d["is_self_target"]]
        self.assertEqual(len(self_targets), 1)
        self.assertEqual(self_targets[0]["slot"], 3)

        # New code property 4: no reverse record invented under 0x11
        dests_11 = [d for d in d1["header_destinations"] if d["source_room"] == "0x11" and d["transition_kind"] == "stair"]
        for d in dests_11:
            self.assertNotEqual(d["target_room"], "0x10")


if __name__ == "__main__":
    unittest.main()
