"""Asset compiler tests; synthetic ROMs and a source-grounded stream interpreter.

These checks establish compiled data behavior, not installed runtime behavior.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

GENERATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GENERATE))
import room_graphics as rg  # noqa: E402


def native_row_writes(data, initial=None):
    """Model CustomObjectHandler's decrement/XBA loop, independently of rg.

    Dungeons/Objects/object_handler.asm saves Y at each row start, writes
    nonzero words, decrements the full header, then adds its remaining high
    byte to saved Y. In particular, the row stride is NOT added to row end.
    Native count zero means 32 writes; the compiler deliberately forbids it
    because Yaze's reader uses the low-five-bit count directly.
    """
    memory = dict(initial or {})
    cursor = destination = 0
    for _ in range(256):
        header = int.from_bytes(data[cursor:cursor + 2], "little")
        cursor += 2
        if header == 0:
            if cursor != len(data):
                raise AssertionError("unexpected bytes after native terminator")
            return memory
        row_start = destination
        remaining = header
        for _ in range(32):
            if cursor + 2 > len(data):
                raise AssertionError("truncated native fixture")
            value = int.from_bytes(data[cursor:cursor + 2], "little")
            cursor += 2
            if value:
                memory[destination] = value
            destination += 2
            remaining = (remaining - 1) & 0xFFFF
            if remaining & 0x1F == 0:
                destination = row_start + ((remaining >> 8) & 0xFF)
                break
    raise AssertionError("native fixture never terminates")


class NativePatternTests(unittest.TestCase):
    def test_golden_row_stream_preserves_palette_flips_priority_and_skips(self):
        # Palette rows 2, 3, 4 and 7, including priority and both mirror bits.
        grid = rg.pattern_grid([[0x0801, None, 0xFC02], [0x4C03, 0x9004, None]])
        encoded = rg.encode_pattern(grid)
        golden = bytes.fromhex("03 80 01 08 00 00 02 fc 03 80 03 4c 04 90 00 00 00 00")
        self.assertEqual(encoded, golden)
        initial = {2: 0x2222, 132: 0x3333}
        self.assertEqual(native_row_writes(encoded, initial),
                         {0: 0x0801, 2: 0x2222, 4: 0xFC02,
                          128: 0x4C03, 130: 0x9004, 132: 0x3333})
        self.assertEqual(rg.decode_pattern(golden),
                         [(0, 0, 0x0801), (2, 0, 0xFC02),
                          (0, 1, 0x4C03), (1, 1, 0x9004)])

    def test_arbitrary_widths_and_resized_bed_follow_native_row_start_stride(self):
        for width, height in [(2, 4), (4, 5), (7, 6), (31, 64)]:
            with self.subTest(width=width, height=height):
                rows = [[0x0800 | ((y * width + x) % 512)
                         for x in range(width)] for y in range(height)]
                data = rg.encode_pattern(rg.pattern_grid(rows))
                expected = {y * 128 + x * 2: rows[y][x]
                            for y in range(height) for x in range(width)}
                self.assertEqual(native_row_writes(data), expected)
                self.assertLess(max(expected), 0x2000)

    def test_null_is_skip_but_explicit_zero_word_is_refused(self):
        self.assertEqual(rg.pattern_grid([[None, 0x0800]]), [[0, 0x0800]])
        for zero in (0, "0x0000"):
            with self.subTest(zero=zero), self.assertRaisesRegex(ValueError, "zero"):
                rg.pattern_grid([[zero, 0x0801]])
        with self.assertRaisesRegex(ValueError, "empty pattern"):
            rg.pattern_grid([[None]])

    def test_palette_rows_and_background_tile_limits(self):
        for row in range(2, 8):
            self.assertEqual(rg.tile_word((row << 10) | 0x1FF), (row << 10) | 0x1FF)
        for word in (0x0001, 0x0401, 0xC001, 0xC401):
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, "HUD"):
                rg.tile_word(word)
        with self.assertRaisesRegex(ValueError, "eight BG"):
            rg.tile_word(0x0A00)  # row 2, tile $200
        for word in (-1, 0x10000, True, 1.0, "2048"):
            with self.subTest(word=word), self.assertRaises(ValueError):
                rg.tile_word(word)

    def test_grid_bounds_and_native32_yaze31_interoperability(self):
        for rows in ([], [[]], [[0x0801] * 32], [[0x0801]] * 65,
                     [[0x0801], [0x0801, None]]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                rg.pattern_grid(rows)
        native32 = b"\x20\x80" + b"\x01\x08" * 32 + b"\0\0"
        self.assertEqual(len(native_row_writes(native32)), 32)
        with self.assertRaisesRegex(ValueError, "count bits"):
            rg.decode_pattern(native32)
        with self.assertRaisesRegex(ValueError, "1..31"):
            rg.encode_pattern([[0x0801] * 32])

    def test_decoder_rejects_truncation_bad_headers_and_tilemap_overflow(self):
        invalid = [b"", b"\x01", b"\x01\x80", b"\0\0\0\0",
                   b"\x01\x81\x01\x08\0\0",  # odd byte stride
                   b"\x41\x80\x01\x08\0\0",  # reserved count bit
                   b"\x01\x80\x01\x08" * 65 + b"\0\0"]
        for data in invalid:
            with self.subTest(data=data[:12]), self.assertRaises(ValueError):
                rg.decode_pattern(data)

    def test_decoder_accepts_existing_short_byte_stride(self):
        data = bytes.fromhex("01 02 01 08 01 02 02 08 00 00")
        self.assertEqual(native_row_writes(data), {0: 0x0801, 2: 0x0802})
        self.assertEqual(rg.decode_pattern(data), [(0, 0, 0x0801), (1, 0, 0x0802)])

    def test_vram_conversion_slot_masks_preserve_transparent_zero(self):
        raw = bytearray(0x600)
        # First tile row has consecutive source indices 0,1,2,3,4,5,6,7.
        raw[0], raw[1], raw[16] = 0x55, 0x33, 0x0F
        for main, high_slots in [(3, {0, 1, 2, 3}), (0x20, {0, 3, 4, 5})]:
            for slot in range(8):
                with self.subTest(main=main, slot=slot):
                    vram, half = rg.vram_sheet(bytes(raw), main, slot)
                    high = slot in high_slots
                    self.assertEqual(half, "high" if high else "low")
                    self.assertEqual(len(vram), 0x800)
                    self.assertEqual(vram[:2], b"\x55\x33")
                    self.assertEqual(vram[16:18], bytes([0x0F, 0x7F if high else 0]))
                    pixels = [sum(((vram[offset] >> (7-x)) & 1) << plane
                                  for plane, offset in enumerate((0, 1, 16, 17)))
                              for x in range(8)]
                    self.assertEqual(pixels, [0, 9, 10, 11, 12, 13, 14, 15]
                                     if high else list(range(8)))


class RoomGraphicsCompilerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.profile = self.root / "profile.json"
        self.rom_path = self.root / "synthetic.sfc"
        rom = bytearray(0x80000)
        struct.pack_into("<H", rom, 0x78000 + 0x68 * 2, 0x0F)
        rom[0x79600 + 0x68] = 3
        # Real room header pointer chain: $028000 table -> $029000 header.
        rom[0xB5DD:0xB5E0] = bytes.fromhex("00 80 02")
        rom[0xB5E7] = 2
        struct.pack_into("<H", rom, 0x10000 + 0x0F * 2, 0x9000)
        rom[0x11000 + 2] = 3
        # Main group at $00D800; secondary nonzero values override slots3..6.
        struct.pack_into("<H", rom, 0x6237, 0xD800)
        rom[0x5800 + 3*8:0x5800 + 4*8] = bytes([0x61, 1, 0x13, 0x22, 0x0E, 0x22, 0x22, 0x0F])
        rom[0x5D97 + 3*4:0x5D97 + 4*4] = bytes([7, 0, 0x23, 0x1C])
        # Real sheet-table entries: sheet $61 -> SNES $04:8000 / PC $020000.
        rom[0x4F80 + 0x61] = 4
        rom[0x505F + 0x61] = 0x80
        rom[0x513E + 0x61] = 0
        # Independent LC-LZ2 fixture: 1024 zero fill, 512 zero fill, terminator.
        rom[0x20000:0x20007] = bytes.fromhex("e7 ff 00 e5 ff 00 ff")
        self.rom_path.write_bytes(rom)
        self.spec = {
            "schema_version": 1, "id": "hut_fixture",
            "base_sha256": hashlib.sha256(rom).hexdigest(),
            "context": {"room": "0x0F", "entrance": "0x68", "main_blockset": 3,
                        "room_blockset": 3,
                        "bg_sheets": [0x61, 1, 0x13, 7, 0x0E, 0x23, 0x1C, 0x0F]},
            "palette_rows": [{"row": 2, "colors": list(range(1, 16))}],
            "sheets": [],
            "patterns": [{"id": "resized_bed", "kind": "object",
                          "collision": "requires_overlay",
                          "states": [{"name": "normal", "rows": [
                              [0x0801, 0x4801], [0x0802, 0x4802],
                              [0x0803, 0x4803], [0x0804, 0x4804]]}]}],
        }

    def compile(self, spec=None):
        self.profile.write_text(json.dumps(self.spec if spec is None else spec))
        return rg.compile_profile(self.profile, self.rom_path)

    def test_real_profile_compiles_resized_object_multistate_door_and_palette(self):
        self.spec["patterns"].append({
            "id": "stone_frame", "kind": "door_frame", "collision": "preserve_existing",
            "states": [{"name": "closed", "rows": [[0x0805] * 7] * 6},
                       {"name": "open", "rows": [[0x0806, None, None, None, None, None, 0x4806]] * 6}],
        })
        before = self.rom_path.read_bytes()
        files, inputs = self.compile()
        self.assertEqual(self.rom_path.read_bytes(), before)
        self.assertEqual(inputs, {self.profile.resolve(), self.rom_path.resolve()})
        self.assertEqual(files["palettes/row_2.bin"], bytes.fromhex(
            "01 00 02 00 03 00 04 00 05 00 06 00 07 00 08 00 "
            "09 00 0a 00 0b 00 0c 00 0d 00 0e 00 0f 00"))
        metadata = json.loads(files["bundle.json"])
        self.assertEqual(metadata["stage"], "compiled_assets_unbound")
        self.assertFalse(metadata["runtime_installed"])
        self.assertEqual([(p["width"], p["height"]) for p in metadata["patterns"]], [(2, 4), (7, 6)])
        self.assertTrue(all(p["runtime_binding_required"] for p in metadata["patterns"]))
        self.assertEqual(len(native_row_writes(files["patterns/stone_frame/closed.bin"])), 42)
        self.assertEqual(native_row_writes(files["patterns/stone_frame/open.bin"]),
                         {address: word for y in range(6)
                          for address, word in [(128*y, 0x0806), (128*y+12, 0x4806)]})
        for name, info in metadata["files"].items():
            self.assertEqual(info, {"bytes": len(files[name]), "sha256": hashlib.sha256(files[name]).hexdigest()})

    def add_real_sheet_source(self):
        rows = [list("." * 128) for _ in range(32)]
        for y in range(8):
            rows[y][:8] = "77777777"
        rows[31][127] = "3"
        source = self.root / "sheet.txt"
        source.write_text("\n".join("".join(row) for row in rows) + "\n")
        self.spec["sheets"] = [{"slot": 0, "source": "sheet.txt",
                                "base_sha256": hashlib.sha256(bytes(0x600)).hexdigest()}]
        return source

    def test_real_sheet_codec_and_compression_use_pinned_base_payload(self):
        source = self.add_real_sheet_source()
        files, inputs = self.compile()
        expected = bytearray(0x600)
        expected[:24] = b"\xff" * 24  # tile 0, all three planes full
        expected[-10:-8] = b"\x01\x01"  # tile63 row7 rightmost pixel index3
        self.assertEqual(files["sheets/slot_0.3bpp"], bytes(expected))
        self.assertEqual(rg.lz2.decompress(files["sheets/slot_0.lz2"])[0], bytes(expected))
        self.assertIn(source.resolve(), inputs)
        sheet = json.loads(files["bundle.json"])["sheets"][0]
        self.assertFalse(sheet["identity"])
        self.assertEqual(sheet["base_sheet"], 0x61)
        self.assertEqual(sheet["palette_half"], "high")
        self.assertEqual(len(files["sheets/slot_0.vram4bpp"]), 0x800)
        self.spec["sheets"][0]["base_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "base background sheet"):
            self.compile()

    def test_pinned_rom_entrance_and_main_context_refuse_mismatch(self):
        for field, value, message in [("base_sha256", "0" * 64, "fingerprint"),
                                      ("room", 0x10, "entrance does not lead"),
                                      ("main_blockset", 4, "main blockset differs"),
                                      ("room_blockset", 4, "room header blockset differs"),
                                      ("room_blockset", 24, "outside")]:
            spec = copy.deepcopy(self.spec)
            target = spec if field == "base_sha256" else spec["context"]
            target[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                self.compile(spec)
        spec = copy.deepcopy(self.spec)
        spec["context"]["bg_sheets"][3] = 0x22  # secondary override must win
        with self.assertRaisesRegex(ValueError, "background sheet slots differ"):
            self.compile(spec)

    def test_complete_palette_bundle_is_sorted_and_contains_no_hud_rows(self):
        self.spec["palette_rows"] = [{"row": row, "colors": [row] * 15}
                                     for row in range(7, 1, -1)]
        files, _ = self.compile()
        self.assertEqual(files["palettes/dungeon_main.bin"],
                         b"".join(bytes([row, 0]) * 15 for row in range(2, 8)))
        self.assertEqual(len(files["palettes/dungeon_main.bin"]), 180)

    def test_palette_payload_refuses_hud_rows_duplicates_and_bad_colors(self):
        invalid = [[{"row": row, "colors": list(range(15))}] for row in (0, 1, 8)]
        invalid += [[{"row": 2, "colors": [0] * 14}],
                    [{"row": 2, "colors": [0] * 14 + [0x8000]}],
                    [self.spec["palette_rows"][0]] * 2]
        for palettes in invalid:
            spec = copy.deepcopy(self.spec)
            spec["palette_rows"] = palettes
            with self.subTest(palettes=palettes), self.assertRaises(ValueError):
                self.compile(spec)

    def test_pattern_states_require_consistent_footprints_and_unique_identity(self):
        cases = []
        spec = copy.deepcopy(self.spec)
        spec["patterns"][0]["states"].append({"name": "other", "rows": [[0x0801]]})
        cases.append(spec)
        spec = copy.deepcopy(self.spec)
        spec["patterns"][0]["states"] *= 2
        cases.append(spec)
        spec = copy.deepcopy(self.spec)
        spec["patterns"] *= 2
        cases.append(spec)
        for field, value in [("kind", "door"), ("collision", "automatic"), ("id", "../bad")]:
            spec = copy.deepcopy(self.spec)
            spec["patterns"][0][field] = value
            cases.append(spec)
        for spec in cases:
            with self.subTest(pattern=spec["patterns"]), self.assertRaises(ValueError):
                self.compile(spec)

    def test_source_traversal_and_symlink_escape_are_refused(self):
        self.add_real_sheet_source()
        outside = self.root.parent / (self.root.name + "-outside.txt")
        outside.write_bytes((self.root / "sheet.txt").read_bytes())
        self.addCleanup(outside.unlink)
        (self.root / "escape.txt").symlink_to(outside)
        for source in (str(outside), "../" + outside.name, "escape.txt"):
            self.spec["sheets"][0]["source"] = source
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "source"):
                self.compile()

    def test_duplicate_json_keys_and_unknown_fields_are_refused(self):
        self.profile.write_text('{"id":"one","id":"two"}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            rg.compile_profile(self.profile, self.rom_path)
        self.spec["runtime_installed"] = True
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            self.compile()

    def test_publish_and_check_detect_stale_missing_extra_files_without_rewriting(self):
        files, inputs = self.compile()
        out = self.root / "bundle"
        rg.publish(out, files, inputs)
        rg.publish(out, files, inputs, check=True)
        with self.assertRaisesRegex(ValueError, "already exists"):
            rg.publish(out, files, inputs)
        file = out / "patterns/resized_bed/normal.bin"
        old = file.read_bytes()
        file.write_bytes(b"stale")
        with self.assertRaisesRegex(ValueError, "stale output"):
            rg.publish(out, files, inputs, check=True)
        self.assertEqual(file.read_bytes(), b"stale")
        file.write_bytes(old)
        extra = out / "unexpected.txt"
        extra.write_text("retain")
        with self.assertRaisesRegex(ValueError, "file set differs"):
            rg.publish(out, files, inputs, check=True)
        extra.unlink()
        file.unlink()
        with self.assertRaisesRegex(ValueError, "file set differs"):
            rg.publish(out, files, inputs, check=True)

    def test_output_refuses_input_alias_rom_extension_and_symlinks(self):
        files, inputs = self.compile()
        before = self.rom_path.read_bytes()
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        for out in (self.root, self.profile, self.rom_path, self.root / "new.sfc", alias):
            with self.subTest(out=out), self.assertRaises(ValueError):
                rg.publish(out, files, inputs)
        self.assertEqual(self.rom_path.read_bytes(), before)
        self.assertFalse((self.root / "new.sfc").exists())

    def test_check_refuses_symlinked_payload_even_when_contents_match(self):
        files, inputs = self.compile()
        out = self.root / "bundle"
        rg.publish(out, files, inputs)
        file = out / "patterns/resized_bed/normal.bin"
        retained = self.root / "retained.bin"
        retained.write_bytes(file.read_bytes())
        file.unlink()
        file.symlink_to(retained)
        with self.assertRaisesRegex(ValueError, "stale output"):
            rg.publish(out, files, inputs, check=True)

    def test_cli_refusal_does_not_create_output_or_modify_inputs(self):
        self.spec["base_sha256"] = "0" * 64
        self.profile.write_text(json.dumps(self.spec))
        before = (self.profile.read_bytes(), self.rom_path.read_bytes())
        out = self.root / "refused"
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            rc = rg.main([str(self.profile), "--base-rom", str(self.rom_path),
                          "--out-dir", str(out)])
        self.assertEqual(rc, 1)
        self.assertIn("fingerprint", error.getvalue())
        self.assertFalse(out.exists())
        self.assertEqual(before, (self.profile.read_bytes(), self.rom_path.read_bytes()))


if __name__ == "__main__":
    unittest.main()
