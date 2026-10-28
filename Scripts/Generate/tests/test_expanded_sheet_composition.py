"""Assemble the real selected table and generated overrides, without a game run."""
from pathlib import Path
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
