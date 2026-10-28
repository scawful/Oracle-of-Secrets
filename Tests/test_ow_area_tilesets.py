"""Real-Asar checks for the selected current per-area loader composition."""
from pathlib import Path
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AreaTilesetComposition(unittest.TestCase):
    def setUp(self):
        self.asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        if not self.asar:
            self.skipTest('Asar unavailable')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def assemble(self, text, original=None):
        driver = self.folder/'driver.asm'
        driver.write_text(text)
        rom = self.folder/'synthetic.sfc'
        rom.write_bytes(bytes(0x400000) if original is None else original)
        run = subprocess.run([self.asar, '--no-title-check', '--fix-checksum=off',
                              '-I'+str(self.folder), '-I'+str(ROOT), str(driver), str(rom)],
                             capture_output=True, text=True)
        return run, rom.read_bytes()

    @staticmethod
    def pc(address):
        return ((address & 0x7F0000)>>1) | (address & 0x7FFF)

    def ferry_driver(self, bound=None, *, assets=True, bitmap=0xE2E259,
                     module='Overworld/area_tilesets.asm'):
        image = bytearray(0x400000)
        for at in (0x00886E, 0x1BBEFD, 0x1BBF2A, 0x1BC04E):
            image[self.pc(at):self.pc(at)+4] = bytes.fromhex('bf59940e')
        text = '''lorom
!ENABLE_OW_AREA_TILESETS = 1
!LYRA_CURRENT_MODE = 1
!LYRA_AREA_TILESETS_BOUND = 1
!LYRA_AREA_TILESETS_ORIGIN = $E2E000
!LYRA_AREA_TILESETS_END = $E30000
namespace Oracle
BoatBitmap = $349000
AdditionalBitmap = $34B000
SharedGraphicsResource_3fd640ea5f71e4301983dc4944b355f6d8582ea14797605688e5adaf37ffc3b4 = $E2856C
SharedGraphicsRuntimeEnd = $E28001
'''
        if bound is not None:
            text += f'!LYRA_AREA_FERRY_BOUND = {bound}\n'
        text += f'incsrc "{module}"\n'
        for name in ('AreaProfile', 'Profiles', 'NoTypes', 'BoatSheets', 'CodeEnd'):
            text += f'print "{name}=", hex(AreaTileset_{name})\n'
        if bound == 1:
            for name in ('FerryTypes', 'FerrySheets'):
                text += f'print "{name}=", hex(AreaTileset_{name})\n'
        if assets:
            text += f'''org $E2E200
FerryArea30Types:
  fillbyte $02 : fill $59
org ${bitmap:06X}
FerryArea30Bitmap:
  fillbyte $5A : fill $0B20
'''
        return text, image

    def test_ferry_profile_descriptors_and_default_zero_bytes(self):
        controls = []
        for bound in (None, 0, 1):
            with self.subTest(bound=bound):
                text, image = self.ferry_driver(bound)
                run, result = self.assemble(text, image)
                self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
                labels = {k:int(v, 16) for k,v in re.findall(
                    r'^(\w+)=([0-9A-Fa-f]+)$', run.stdout, re.M)}
                at = self.pc(labels['AreaProfile'])
                profiles = result[at:at+256]
                self.assertEqual(profiles[0x30], 2 if bound == 1 else 1)
                self.assertEqual(profiles[0x38], 1)
                self.assertEqual({i for i,v in enumerate(profiles) if v}, {0x30, 0x38})
                for hook in (0x00886E, 0x1BBEFD, 0x1BBF2A, 0x1BC04E):
                    self.assertEqual(result[self.pc(hook):self.pc(hook)+4],
                                     bytes.fromhex('bf00d07f'))
                if bound != 1:
                    controls.append(result)
                    self.assertEqual(labels['CodeEnd'], 0xE2E1C9)
                    # Immutable 2ac95c7e control module, before ferry binding.
                    self.assertEqual(hashlib.sha256(result[
                        self.pc(0xE2E000):self.pc(labels['CodeEnd'])]).hexdigest(),
                        '1b29e87070d74dce4f3eda6498bca66fda4e817cc78cfd4819dfc36e307c10ce')
                    continue
                self.assertEqual(labels['CodeEnd'], 0xE2E1F3)
                self.assertLessEqual(labels['CodeEnd'], 0xE2E200)
                at = self.pc(labels['Profiles'])
                self.assertEqual(struct.unpack_from('<6H', result, at),
                    (0, 0, labels['NoTypes'] & 0xFFFF, labels['BoatSheets'] & 0xFFFF,
                     labels['FerryTypes'] & 0xFFFF, labels['FerrySheets'] & 0xFFFF))
                at = self.pc(labels['FerryTypes'])
                self.assertEqual(result[at:at+8], bytes.fromhex('0001590000e2ffff'))
                at = self.pc(labels['FerrySheets'])
                self.assertEqual(result[at:at+30], bytes.fromhex(
                    '002c0020009034' '002c00086c85e2'
                    '0030200b59e2e2' '0050002000b034' 'ffff'))
                body = result[self.pc(0xE2E000):self.pc(labels['CodeEnd'])]
                for dest in (0x002116, 0x004305, 0x004302, 0x004300,
                             0x004304, 0x002115, 0x00420B):
                    self.assertIn(b'\x8F'+dest.to_bytes(3, 'little'), body)
        self.assertEqual(controls[0], controls[1])

    def test_ferry_binding_refuses_missing_or_out_of_bounds_data(self):
        for kwargs, error in ((dict(assets=False), 'FerryArea30'),
                              (dict(bitmap=0xE2F500), 'bitmap outside owned data suffix'),
                              (dict(bitmap=0xE2E200), 'sources overlap')):
            with self.subTest(kwargs=kwargs):
                text, image = self.ferry_driver(1, **kwargs)
                if kwargs.get('bitmap') == 0xE2F500:
                    # Let the source-span assertion diagnose the declared size
                    # before a synthetic fill crosses the ROM bank boundary.
                    text = text.replace('fillbyte $5A : fill $0B20',
                                        'fillbyte $5A : fill $01')
                run, _ = self.assemble(text, image)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn(error, run.stdout+run.stderr)
        # A module expansion past the exact generated-data boundary must fail.
        mutant = self.folder/'overrun.asm'
        mutant.write_text((ROOT/'Overworld/area_tilesets.asm').read_text().replace(
            'AreaTileset_CodeEnd = pc()', 'skip $0E\nAreaTileset_CodeEnd = pc()'))
        text, image = self.ferry_driver(1, module=str(mutant))
        run, _ = self.assemble(text, image)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('module overlaps generated ferry data', run.stdout+run.stderr)

    def test_allocation_bindings_match_real_source_symbols(self):
        sys.path.insert(0, str(ROOT/'Scripts/Generate'))
        from allocation_contracts import read_ledger, source_evidence
        ledger = read_ledger(ROOT/'Config/allocation_ownership.json')
        sets = ('lyra_joint_graphics_source_26', 'lyra_joint_area_tilesets_27')
        sources = {k:v for k,v in ledger['sources'].items() if v['source_set'] in sets}
        claims = [c for c in ledger['claims'] if c['id'] in
                  ('ExpandedGraphicsSheetTable', 'LyraAreaTileTypes', 'LyraAreaTilesetSuffix')]
        self.assertEqual(len(claims), 3)
        source_evidence(dict(sources=sources, claims=claims), {name:ROOT for name in sets})

    def test_main_checks_area_binding_after_generated_constants(self):
        main = (ROOT/'Oracle_main.asm').read_text()
        prefix = main[main.index('incsrc    "Util/macros.asm"'):
                      main.index('if !ENABLE_MASK_R_BINDING == 1')]
        # Select the feature after the actual checked-in flag include, exactly
        # where an isolated selected source config would already have enabled it.
        prefix = prefix.replace('incsrc    "Config/feature_flags.asm"',
                                'incsrc    "Config/feature_flags.asm"\n!ENABLE_OW_AREA_TILESETS = 1')
        generated = self.folder/'Data/Generated/lyra_project/runtime_constants.asm'
        generated.parent.mkdir(parents=True)
        for bound in (0, 1):
            with self.subTest(bound=bound):
                generated.write_text(f'''!LYRA_PROJECT_DATA_PRESENT = 1
!LYRA_NATIVE_A1_ENABLED = 0
!LYRA_CURRENT_MODE = 1
!LYRA_AREA_TILESETS_BOUND = {bound}
''')
                run, _ = self.assemble('lorom\n!LYRA_BUILD_CONTEXT = 1\n'+prefix)
                if bound:
                    self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
                else:
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn('Per-area source binding required', run.stdout+run.stderr)
        # Control: the former placement rejects even a generated bound=1.
        check = ('assert !ENABLE_OW_AREA_TILESETS == 0 || '
                 '!LYRA_AREA_TILESETS_BOUND == 1, "Per-area source binding required"\n')
        early = prefix.replace(check, '').replace(
            'if not(defined("REGIONAL_CHECKPOINTS_ENABLED"))',
            check+'if not(defined("REGIONAL_CHECKPOINTS_ENABLED"))', 1)
        run, _ = self.assemble('lorom\n!LYRA_BUILD_CONTEXT = 1\n'+early)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('Per-area source binding required', run.stdout+run.stderr)

    def test_module_uses_long_hardware_stores_and_refuses_missing_binding(self):
        image = bytearray(0x400000)
        pc = lambda a: ((a & 0x7F0000)>>1) | (a & 0x7FFF)
        sites = (0x00886E, 0x1BBEFD, 0x1BBF2A, 0x1BC04E)
        for at in sites:
            image[pc(at):pc(at)+4] = bytes.fromhex('bf59940e')
        for bound, end, error in ((1, 0xE28001, None),
                                  (0, 0xE28001, 'source binding required'),
                                  (1, 0xE2E001, 'Shared graphics overlap')):
            with self.subTest(bound=bound, end=end):
                driver = f'''lorom
!ENABLE_OW_AREA_TILESETS = 1
!LYRA_CURRENT_MODE = 1
!LYRA_AREA_TILESETS_BOUND = {bound}
!LYRA_AREA_TILESETS_ORIGIN = $E2E000
!LYRA_AREA_TILESETS_END = $E30000
namespace Oracle
BoatBitmap = $349000
AdditionalBitmap = $34B000
SharedGraphicsRuntimeEnd = ${end:06X}
incsrc "Overworld/area_tilesets.asm"
'''
                run, result = self.assemble(driver, image)
                if error:
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn(error, run.stdout+run.stderr)
                    continue
                self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
                for at in sites:
                    self.assertEqual(result[pc(at):pc(at)+4], bytes.fromhex('bf00d07f'))
                body = result[pc(0xE2E000):pc(0xE2E1C9)]
                for dest in (0x002116, 0x004305, 0x004302, 0x004300,
                             0x004304, 0x002115, 0x00420B):
                    self.assertIn(b'\x8F'+dest.to_bytes(3, 'little'), body)


if __name__ == '__main__':
    unittest.main()
