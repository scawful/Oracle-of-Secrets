"""Assemble the real selected table and generated overrides, without a game run."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

GEN = Path(__file__).resolve().parents[1]
ROOT = GEN.parents[1]
sys.path.insert(0, str(GEN))
import lz2
import sheet_overrides as sheets
import sheet_table as table


class ExpandedSheetComposition(unittest.TestCase):
    def test_snowpeak_copy_binds_only_three_areas_with_both_features(self):
        asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        if not asar:
            self.skipTest('Asar unavailable')
        import sheet_codec
        spec = sheets.read_spec(ROOT/'Data/graphics/snowpeak_sheet.json')
        metadata = sheets.source_metadata(ROOT, spec_path=Path('Data/graphics/snowpeak_sheet.json'),
                                          output=Path('Core/Generated/source_sprite_sheets/snowpeak'),
                                          feature_flag='ENABLE_EXPANDED_GRAPHICS_TABLE')
        self.assertEqual(metadata['global_sheet_ids'], ['0xDF'])
        self.assertEqual(metadata['generated_include'], 'Core/Generated/source_sprite_sheets/snowpeak/sheet_overrides.asm')
        entry = spec['sheets'][0]
        raw = sheet_codec.grid_to_sheet(sheet_codec.text_to_grid(
            (ROOT/'Data/graphics'/entry['source']).read_text()))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['decoded_sha256'])
        payload = lz2.compress(raw)
        self.assertEqual(lz2.decompress(payload), (raw, len(payload)))
        native = (ROOT/'Overworld/ZSCustomOverworld.asm').read_text()
        native = native[native.index('; Sheet $DF is a private copy'):]
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder/'binding.asm').write_text(native)
            initial = bytearray(0x210000)
            for area in range(160):
                initial[table.pc(0x288484)+area*8] = 0x37
            for expanded, source in ((0, 1), (1, 0), (1, 1)):
                with self.subTest(expanded=expanded, source=source):
                    rom = folder/'candidate.sfc'
                    rom.write_bytes(initial)
                    (folder/'driver.asm').write_text(f'''lorom
!ENABLE_EXPANDED_GRAPHICS_TABLE = {expanded}
!ENABLE_SOURCE_SPRITE_SHEETS = {source}
!ENABLE_EON_OWL_ONE_SHOT = 0
if !ENABLE_EXPANDED_GRAPHICS_TABLE == 1
incsrc "{ROOT/'Core/gfx_sheet_table.asm'}"
endif
if !ENABLE_EXPANDED_GRAPHICS_TABLE == 1 && !ENABLE_SOURCE_SPRITE_SHEETS == 1
incsrc "{ROOT/'Core/Generated/source_sprite_sheets/snowpeak/sheet_overrides.asm'}"
endif
incsrc "binding.asm"
''')
                    run = subprocess.run([asar, '--no-title-check', '--fix-checksum=off',
                                          str(folder/'driver.asm'), str(rom)],
                                         capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
                    result = rom.read_bytes()
                    selected = bool(expanded and source)
                    for area in range(160):
                        self.assertEqual(result[table.pc(0x288484)+area*8],
                                         0xDF if selected and area in (5, 6, 7) else 0x37)
                    if selected:
                        self.assertEqual(table.ptr(result, 0xDF), 0xC0E800)
                        self.assertEqual(table.decomp(result, table.ptr(result, 0xDF))[0], raw)
                    else:
                        self.assertEqual(result[table.pc(0x40E800):table.pc(0x40E800)+len(payload)],
                                         initial[table.pc(0x40E800):table.pc(0x40E800)+len(payload)])

    def test_real_table_overrides_and_eon_reader_have_one_owner(self):
        asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        if not asar:
            self.skipTest('Asar unavailable')
        raw = bytes(range(256))*6
        payload = lz2.compress(raw)
        item = dict(s=0x64, g=0xD7, stream=payload, snes=0x40D000, why='fixture')
        owl = (ROOT/'Sprites/NPCs/eon_owl.asm').read_text()
        start = owl.index('if !ENABLE_EON_OWL_ONE_SHOT == 1\n; Arrival graphics:')
        end = owl.index('; =========================================================', start)
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder/'owl.asm').write_text(owl[start:end])
            original = bytearray(0x210000)
            original[0x10000:0x10000+len(payload)] = payload
            for g in range(table.N):
                for at, value in ((table.TBL_BANK, 0x82), (table.TBL_HIGH, 0x80), (table.TBL_LOW, 0)):
                    original[table.pc(at)+g] = value
            for expanded, new in ((0, False), (1, False), (1, True), (0, True)):
                with self.subTest(expanded=expanded, new=new):
                    entries = [item]
                    if new:
                        entries.append(dict(item, s=0x6C, g=0xDF, snes=0x40D000+len(payload)))
                    outputs = sheets.generated_files(entries)
                    for relative, data in outputs.items():
                        path = folder/relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                    driver = folder/'driver.asm'
                    driver.write_text(f'''lorom
!ENABLE_EXPANDED_GRAPHICS_TABLE = {expanded}
!ENABLE_EON_OWL_ONE_SHOT = 1
org $308000
namespace Oracle
incsrc "owl.asm"
namespace off
if !ENABLE_EXPANDED_GRAPHICS_TABLE == 1
incsrc "{ROOT/'Core/gfx_sheet_table.asm'}"
endif
incsrc "sheet_overrides.asm"
''')
                    rom = folder/'test.sfc'
                    rom.write_bytes(original)
                    run = subprocess.run([asar, '--no-title-check', '--fix-checksum=off',
                                          str(driver), str(rom)], capture_output=True, text=True)
                    if new and not expanded:
                        self.assertNotEqual(run.returncode, 0)
                        self.assertIn('New sheet rows require', run.stderr)
                        continue
                    self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
                    result = rom.read_bytes()
                    self.assertEqual(table.ptr(result, 0xD7), 0xC0D000)
                    if expanded:
                        # The shared reader replaces the old Owl JML, while the
                        # selection callback remains part of the real helper.
                        self.assertEqual(result[table.pc(0xE772)], 0x22)
                        for at in (table.TBL_BANK, table.TBL_HIGH, table.TBL_LOW):
                            self.assertEqual(result[table.pc(at):table.pc(at)+table.N],
                                             original[table.pc(at):table.pc(at)+table.N])
                        for g in range(table.N):
                            if g != 0xD7:
                                self.assertEqual(table.ptr(result, g), table.ptr(original, g))
                        if new:
                            data, count = table.decomp(result, table.ptr(result, 0xDF))
                            self.assertEqual((data, count), (raw, len(payload)))
                            row = table.survey(result)[0xDF]
                            self.assertEqual(row['bpp'], 3)
                    else:
                        self.assertEqual(result[table.pc(0xE772)], 0x5C)
                        self.assertEqual(result[table.pc(0x23FC00):table.pc(0x240000)],
                                         original[table.pc(0x23FC00):table.pc(0x240000)])


if __name__ == '__main__':
    unittest.main()
