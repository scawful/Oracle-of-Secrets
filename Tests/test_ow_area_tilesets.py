"""Real-Asar checks for the selected current per-area loader composition."""
from pathlib import Path
import os
import shutil
import subprocess
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
