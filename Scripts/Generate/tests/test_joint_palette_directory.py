"""Joint palette directory: spec validation and Asar assembly against a synthetic input ROM."""
from pathlib import Path
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

GEN = Path(__file__).resolve().parents[1]
ROOT = GEN.parents[1]
sys.path.insert(0, str(GEN))
sys.path.insert(0, str(ROOT / 'Scripts/Validate'))
import joint_palette_directory as jp
import verify_joint_palette_directory as verifier

ZS = ROOT / 'Overworld/ZSCustomOverworld.asm'
READERS = ROOT / 'Overworld/joint_palette_readers.asm'
pc = verifier.pc


def input_rom():
    rom = bytearray(0x200000)
    for i in range(jp.MAIN_LEGACY):
        rom[pc(jp.MAIN_OFFSETS) + 2 * i:pc(jp.MAIN_OFFSETS) + 2 * i + 2] = (70 * i).to_bytes(2, 'little')
    for i in range(jp.AUX_LEGACY):
        rom[pc(jp.AUX_OFFSETS) + 2 * i:pc(jp.AUX_OFFSETS) + 2 * i + 2] = (42 * i).to_bytes(2, 'little')
    for site, kind in verifier.NATIVE_READERS.items():
        rom[pc(site):pc(site) + 7] = verifier.LEGACY[kind]
    for row in range(jp.SET_ROWS):
        rom[pc(jp.SET_TABLE) + 4 * row:pc(jp.SET_TABLE) + 4 * row + 4] = bytes.fromhex('00ff07ff')
    rom[pc(jp.SET_TABLE) + 4 * 0x0D:pc(jp.SET_TABLE) + 4 * 0x10] = bytes.fromhex('101606ff00ff07ff141505ff')
    rom[pc(jp.AREA_SETS):pc(jp.AREA_SETS) + 0xA0] = bytes(i % jp.SET_ROWS for i in range(0xA0))
    rom[pc(jp.MAIN_TABLE):pc(jp.MAIN_TABLE) + 0xA0] = bytes(i % 5 for i in range(0xA0))
    rom[pc(jp.MAIN_TABLE) + 0x87] = 6
    rom[pc(jp.ARENA_START):pc(jp.ARENA_END)] = b'\xFF' * (jp.ARENA_END - jp.ARENA_START)
    return rom


def zs_fragment():
    text = ZS.read_text()
    start = text.index('    JointPalette_ZSMainReader = pc()')
    end = text.index('\n', text.index('    JointPalette_ZSMainReader_End = pc()'))
    return text[start:end]


class JointPaletteSpec(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / jp.SPEC).read_text())

    def check(self, spec, message):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'spec.json'
            path.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, message):
                jp.read_spec(path)

    def test_tracked_output_is_current(self):
        self.assertEqual(jp.build(ROOT / jp.SPEC), (ROOT / jp.OUTPUT).read_text())

    def test_layout_and_slot_coverage_are_fixed(self):
        bad = copy.deepcopy(self.spec)
        bad['records'][1]['address'] = '0x1BB730'
        self.check(bad, 'granted address')
        bad = copy.deepcopy(self.spec)
        bad['records'][1]['bgr555_hex'] = bad['records'][1]['bgr555_hex'][:-4]
        self.check(bad, 'must be 42 bytes')
        bad = copy.deepcopy(self.spec)
        bad['parked'].pop()
        self.check(bad, 'every granted slot')
        bad = copy.deepcopy(self.spec)
        bad['parked'].append(dict(kind='aux', id=20, address='0x1BB72E', why='dup'))
        self.check(bad, 'not a free granted slot')
        bad = copy.deepcopy(self.spec)
        bad['records'].append(copy.deepcopy(bad['records'][1]))
        self.check(bad, 'duplicate record')
        bad = copy.deepcopy(self.spec)
        bad['records'][0]['bgr555_hex'] = 'ff' * 70
        self.check(bad, 'non-BGR555')
        bad = copy.deepcopy(self.spec)
        bad['arena']['end'] = '0x1BB900'
        self.check(bad, 'granted')


@unittest.skipUnless(os.environ.get('ASAR_BIN') or shutil.which('asar'), 'Asar unavailable')
class JointPaletteAssembly(unittest.TestCase):
    asar = os.environ.get('ASAR_BIN') or shutil.which('asar')

    def assemble(self, folder, enabled, rom, directory=None, readers=True, fix_checksum=False):
        folder = Path(folder)
        (folder / 'directory.asm').write_text(directory or (ROOT / jp.OUTPUT).read_text())
        includes = ''
        if enabled:
            includes = ('incsrc "directory.asm"\n' if directory != '' else '') + \
                       (f'incsrc "{READERS}"\n' if readers else '')
        (folder / 'main.asm').write_text(
            'lorom\n'
            f'!JOINT_PALETTE_DIRECTORY_ENABLED = {enabled}\n!DISABLE_OVERWORLD = 0\n'
            'PaletteIDtoOffset_OW_Main = $1BEC3B\nPaletteData_owmain = $1BE6C8\n'
            f'org $3F8000\n{zs_fragment()}\n{includes}')
        out = folder / f'out{enabled}.sfc'
        out.write_bytes(rom)
        sym = folder / f'out{enabled}.sym'
        run = subprocess.run([self.asar, '--no-title-check', '--fix-checksum='+('on' if fix_checksum else 'off'), '--symbols=wla', f'--symbols-path={sym}', str(folder / 'main.asm'),
                              str(out)], capture_output=True, text=True, errors='replace')
        return run, out, sym

    def test_flag_off_is_identity_and_flag_on_matches_spec(self):
        with tempfile.TemporaryDirectory() as name:
            rom = input_rom()
            off_run, off, _ = self.assemble(name, 0, rom)
            self.assertEqual(off_run.returncode, 0, off_run.stdout + off_run.stderr)
            on_run, on, sym = self.assemble(name, 1, rom)
            self.assertEqual(on_run.returncode, 0, on_run.stdout + on_run.stderr)
            off_bytes, on_bytes = off.read_bytes(), on.read_bytes()
            self.assertEqual(off_bytes[pc(0x3F8000):pc(0x3F8000) + 7], verifier.LEGACY['main'])
            self.assertEqual(bytes(off_bytes[:pc(0x3F8000)]), bytes(rom[:pc(0x3F8000)]))
            zs_site = verifier.symbol(sym, 'JointPalette_ZSMainReader')
            self.assertEqual(zs_site, 0x3F8000)
            errors, changed = verifier.verify(off_bytes, on_bytes, zs_site, ROOT / jp.SPEC)
            self.assertEqual(errors, [])
            self.assertEqual(changed, 4 * 5 + 2 * (jp.MAIN_COUNT + jp.AUX_COUNT) + 70 + 3 * 42)
            tampered = bytearray(on_bytes)
            tampered[pc(0x1BB730)] ^= 1
            tampered[pc(0x1BB800)] ^= 1
            errors, _ = verifier.verify(off_bytes, tampered, zs_site, ROOT / jp.SPEC)
            self.assertTrue(any('$1BB730' in e for e in errors) and any('outside' in e for e in errors), errors)

    def test_real_asar_checksum_updates_are_verified_not_stray_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            off_run, off, _ = self.assemble(name, 0, input_rom(), fix_checksum=True)
            on_run, on, sym = self.assemble(name, 1, input_rom(), fix_checksum=True)
            self.assertEqual(off_run.returncode, 0, off_run.stdout+off_run.stderr)
            self.assertEqual(on_run.returncode, 0, on_run.stdout+on_run.stderr)
            off_bytes, on_bytes = off.read_bytes(), on.read_bytes()
            self.assertNotEqual(off_bytes[0x7FDC:0x7FE0], on_bytes[0x7FDC:0x7FE0])
            at = verifier.symbol(sym, 'JointPalette_ZSMainReader')
            self.assertEqual(verifier.verify(off_bytes, on_bytes, at, ROOT/jp.SPEC)[0], [])
            bad = bytearray(on_bytes)
            bad[0x7FDC] ^= 1
            errors, _ = verifier.verify(off_bytes, bad, at, ROOT/jp.SPEC)
            self.assertTrue(any('checksum/complement' in e for e in errors), errors)

    def test_missing_or_moved_generated_data_refuses(self):
        with tempfile.TemporaryDirectory() as name:
            run, _, _ = self.assemble(name, 1, input_rom(), directory='')
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('JointPalette_MainDirectory', run.stdout + run.stderr)
        with tempfile.TemporaryDirectory() as name:
            moved = (ROOT / jp.OUTPUT).read_text().replace('org $1BB6A8', 'org $1BB6AA')
            run, _, _ = self.assemble(name, 1, input_rom(), directory=moved)
            self.assertNotEqual(run.returncode, 0, run.stdout)

    def test_input_preimages_refuse(self):
        cases = {
            'Native aux1 palette reader changed': lambda r: r.__setitem__(pc(0x1BEEF3), 0x14),
            'reaches a missing palette record': lambda r: r.__setitem__(slice(pc(jp.SET_TABLE) + 0x4C,
                                                                             pc(jp.SET_TABLE) + 0x50),
                                                                       bytes.fromhex('001707ff')),
            'not free in the input ROM': lambda r: r.__setitem__(pc(0x1BB6B6), 0x6C),
            'Area main palette reaches a missing record': lambda r: r.__setitem__(pc(jp.MAIN_TABLE) + 3, 7),
            'outside the checked set table': lambda r: r.__setitem__(pc(jp.AREA_SETS) + 9, 0x1F),
            'Legacy aux palette offsets changed': lambda r: r.__setitem__(pc(jp.AUX_OFFSETS) + 2, 0x2B),
        }
        for message, mutate in cases.items():
            with self.subTest(message=message), tempfile.TemporaryDirectory() as name:
                rom = input_rom()
                mutate(rom)
                run, _, _ = self.assemble(name, 1, rom)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn(message, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main()
