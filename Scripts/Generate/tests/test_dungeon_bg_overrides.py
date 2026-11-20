#!/usr/bin/env python3
"""ROM-free preservation, allocation and refusal checks for Tier A dungeon BG sheets."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
import dungeon_bg_overrides as dbg
import lz2
import sheet_codec
from sheet_table import NEW_BANK, NEW_HIGH, NEW_LOW, TBL_BANK, TBL_HIGH, TBL_LOW, pc


class DungeonBgOverridesTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.spec_dir = self.root / 'Data/graphics'
        self.spec_dir.mkdir(parents=True)
        self.spec_path = self.spec_dir / 'dungeon_bg_sheets.json'
        self.spec = json.loads((ROOT / dbg.SPEC).read_text())

        self.rom = bytearray(0x300000)
        self.bases = {}

        # Build synthetic 1536-byte 3bpp sheets for the audited set plus donor 0x09.
        sheet_configs = {
            0x07: 0x028000,
            0x09: 0x038000,
            0x1C: 0x068000,
            0x1F: 0x048000,
            0x22: 0x058000,
        }
        grids = {}
        for gid in sheet_configs:
            # Distinct non-zero pattern across every tile except tiles cleared below.
            g = [[((x + y + gid) % 7) + 1 for x in range(128)] for y in range(32)]
            grids[gid] = g

        # Clear blank targets: FD0 copies on $07, kettle glyphs on $1C.
        blank8 = [[0] * 8 for _ in range(8)]
        for tile in (0x12, 0x13, 0x2B, 0x3B):
            dbg._set_tile(grids[0x07], tile, blank8)
        for tile in (0x30, 0x31, 0x32, 0x33):
            dbg._set_tile(grids[0x1C], tile, blank8)

        # Populate expected_rows at $1F:33 and $22:33.
        for patch in self.spec['patches']:
            if patch['kind'] == 'tile_8x8':
                gid = dbg.number(patch['sheet'])
                tile = dbg.number(patch['tile'])
                dbg._set_tile(
                    grids[gid],
                    tile,
                    dbg._parse_rows(patch['expected_rows'], 8, 8, patch['name']),
                )
            elif patch['kind'] == 'grid_16x16':
                src_path = self.spec_dir / patch['source']
                src_path.parent.mkdir(parents=True, exist_ok=True)
                src_path.write_text((ROOT / 'Data/graphics' / patch['source']).read_text())

        for gid, pos in sheet_configs.items():
            raw = sheet_codec.grid_to_sheet(grids[gid])
            self.bases[gid] = raw
            sha = hashlib.sha256(raw).hexdigest()
            stream = lz2.stored(raw)
            self.rom[pc(pos):pc(pos) + len(stream)] = stream
            for tbl, shift in ((TBL_BANK, 16), (TBL_HIGH, 8), (TBL_LOW, 0)):
                self.rom[pc(tbl) + gid] = (pos >> shift) & 255
            for entry in self.spec['sheets']:
                if dbg.number(entry['global_sheet']) == gid:
                    entry['base_sha256'] = sha
            for patch in self.spec['patches']:
                if patch.get('source_sheet') and dbg.number(patch['source_sheet']) == gid:
                    patch['source_base_sha256'] = sha

        self.base = self.root / 'base.sfc'
        self.base.write_bytes(self.rom)
        self.write_spec()

    def write_spec(self):
        self.spec_path.write_text(json.dumps(self.spec))

    def build(self):
        return dbg.build(self.spec_path, self.base)

    def test_preserves_all_untargeted_tiles_exactly(self):
        _, items = self.build()
        touched = {
            0x07: {0x12, 0x13, 0x2B, 0x3B},
            0x1C: {0x30, 0x31, 0x32, 0x33},
            0x1F: {0x33},
            0x22: {0x33},
        }
        for item in items:
            gid = item['g']
            decoded, consumed = lz2.decompress(item['stream'], max_output=0x600)
            self.assertEqual(decoded, item['raw'])
            self.assertEqual(consumed, len(item['stream']))
            for t in range(64):
                off = t * 24
                if t in touched[gid]:
                    self.assertNotEqual(decoded[off:off + 24], self.bases[gid][off:off + 24])
                else:
                    self.assertEqual(decoded[off:off + 24], self.bases[gid][off:off + 24])
        # Verify FD0 copy transferred $09:{12,13,2B,3B} verbatim to $07.
        sheet07 = next(i['raw'] for i in items if i['g'] == 0x07)
        for t in (0x12, 0x13, 0x2B, 0x3B):
            off = t * 24
            self.assertEqual(sheet07[off:off + 24], self.bases[0x09][off:off + 24])
        self.assertEqual(self.base.read_bytes(), self.rom)

    def test_only_twelve_independent_pointer_bytes_owned(self):
        _, items = self.build()
        source = dbg.generated_files(items)[Path('bg_sheet_overrides.asm')].decode()
        owned = len(dbg.SHEETS) * 3
        self.assertEqual(owned, 12)
        self.assertEqual(source.count('protected_size=1'), owned)
        self.assertEqual(source.count('assert read1('), owned)
        self.assertEqual(source.count('assert pc() =='), owned)
        for gid in dbg.SHEETS:
            for table in (NEW_BANK, NEW_HIGH, NEW_LOW):
                self.assertIn(f'org ${table + gid:06X} ', source)
            for table in (TBL_BANK, TBL_HIGH, TBL_LOW):
                self.assertNotIn(f'org ${table + gid:06X} ', source)
        self.assertIn('defined("GfxSheet_TableDone")', source)
        self.assertIn('assert pc() <= $5DA000', source)

    def test_changed_base_sheet_or_nonblank_target_refused(self):
        self.spec['sheets'][0]['base_sha256'] = '0' * 64
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'base sheet changed'):
            self.build()

        # Non-blank kettle target on $1C is refused even when the SHA matches.
        self.setUp()
        g1c = sheet_codec.sheet_to_grid(self.bases[0x1C])
        dbg._set_tile(g1c, 0x30, [[1] * 8 for _ in range(8)])
        raw1c = sheet_codec.grid_to_sheet(g1c)
        stream1c = lz2.stored(raw1c)
        self.rom[pc(0x068000):pc(0x068000) + len(stream1c)] = stream1c
        self.base.write_bytes(self.rom)
        for entry in self.spec['sheets']:
            if dbg.number(entry['global_sheet']) == 0x1C:
                entry['base_sha256'] = hashlib.sha256(raw1c).hexdigest()
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'is not blank'):
            self.build()

    def test_unexpected_runner_pixels_refused(self):
        g1f = sheet_codec.sheet_to_grid(self.bases[0x1F])
        dbg._set_tile(g1f, 0x33, [[1] * 8 for _ in range(8)])
        raw1f = sheet_codec.grid_to_sheet(g1f)
        stream1f = lz2.stored(raw1f)
        self.rom[pc(0x048000):pc(0x048000) + len(stream1f)] = stream1f
        self.base.write_bytes(self.rom)
        self.spec['sheets'][1]['base_sha256'] = hashlib.sha256(raw1f).hexdigest()
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'do not match audited baseline'):
            self.build()

    def test_occupied_bank_and_competing_writer_refused(self):
        self.rom[pc(dbg.START)] = 1
        with self.assertRaisesRegex(ValueError, 'allocation .* is occupied'):
            dbg.validate_reservation(self.root, self.rom)
        self.rom[pc(dbg.START)] = 0
        (self.root / 'Oracle_main.asm').write_text('org $5D8100\n')
        with self.assertRaisesRegex(ValueError, 'another reachable source owns bank'):
            dbg.validate_reservation(self.root, self.rom)

    def test_check_refuses_stale_output_without_rewriting(self):
        out = self.root / 'generated'
        argv = ['dungeon_bg_overrides.py', str(self.spec_path), '--root', str(self.root),
                '--base-rom', str(self.base), '--out-dir', str(out)]
        with mock.patch.object(dbg, 'validate_reservation'), mock.patch.object(sys, 'argv', argv):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dbg.main(), 0)
        stale = out / 'sheets/bg07.bin'
        stale.write_bytes(b'stale')
        with mock.patch.object(dbg, 'validate_reservation'), mock.patch.object(sys, 'argv', argv + ['--check']):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(dbg.main(), 1)
        self.assertIn('stale generated', err.getvalue())
        self.assertEqual(stale.read_bytes(), b'stale')

    def test_timber_kettle_custom_object_words(self):
        kettle = (ROOT / 'Dungeons/Objects/Data/timber_kettle.bin').read_bytes()
        self.assertEqual(struct.unpack('<7H', kettle), (0x8002, 0x0DB0, 0x0DB1, 0x8002, 0x0DB2, 0x0DB3, 0x0000))


if __name__ == '__main__':
    unittest.main()
