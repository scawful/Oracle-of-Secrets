"""Compiled resource-body boundaries, not CPU/DMA or full-source proof."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lyra_native_loaders as N
from special_overworld_resident_abi import TRANSFER_CONSTANTS

ROOT = Path(__file__).resolve().parents[3]
ASSEMBLER = shutil.which('asar')


def constants(capacity=192):
    values = dict(SPECIAL_OVERWORLD_NATIVE=1,
                  SPECIAL_OVERWORLD_RESIDENT_ENABLED=1,
                  SPECIAL_OVERWORLD_RESOURCES_ENABLED=1,
                  SPECIAL_OVERWORLD_RESIDENT_FIRST=128,
                  SPECIAL_OVERWORLD_RESIDENT_END=capacity,
                  SPECIAL_OVERWORLD_RESOURCE_CODE_BASE=N.RESIDENT_RESOURCE_CODE_BASE,
                  SPECIAL_OVERWORLD_RESOURCE_CODE_END=N.RESIDENT_RESOURCE_CODE_LIMIT,
                  SPECIAL_OVERWORLD_TRANSFER_DIRECTORY=0x4E8000,
                  LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY=0x4E9000)
    values.update({'GfxRT_' + key: value for key, value in TRANSFER_CONSTANTS.items()})
    values.update(GfxRT_Bank=0x4E, GfxRT_ParentCount=capacity)
    return values


def assemble(directory, values):
    directory = Path(directory)
    rom, asm, symbols = (directory / name for name in ('probe.sfc', 'probe.asm', 'probe.sym'))
    original = bytes([0xCC]) * 0x400000
    rom.write_bytes(original)
    text = 'lorom\nOracle_SpecialOverworldMainCache = $7E1E88\n'
    text += ''.join(f'!{key} = ${value:X}\n' for key, value in values.items())
    text += f'incsrc "{ROOT / "Overworld/special_overworld_graphics.asm"}"\n'
    asm.write_text(text)
    result = subprocess.run([ASSEMBLER, '--no-title-check', '--fix-checksum=off',
                             '--symbols=wla', f'--symbols-path={symbols}', str(asm), str(rom)],
                            capture_output=True, text=True)
    labels = {}
    if symbols.exists():
        labels = {name: int(bank + offset, 16) for bank, offset, name in re.findall(
            r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\w+)$', symbols.read_text(), re.M)}
    return result, original, rom.read_bytes(), labels


@unittest.skipUnless(ASSEMBLER, 'Asar required for resource-body checks')
class SpecialOverworldGraphicsTest(unittest.TestCase):
    def test_disabled_body_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            result, original, image, _ = assemble(directory, {})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(image, original)

    def test_both_capacities_fit_only_the_assigned_code_interval(self):
        for capacity in (160, 192):
            with self.subTest(capacity=capacity), tempfile.TemporaryDirectory() as directory:
                result, original, image, labels = assemble(directory, constants(capacity))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                first = labels['Oracle_SpecialOverworldGraphicsCodeStart']
                end = labels['Oracle_SpecialOverworldGraphicsCodeEnd']
                self.assertEqual(first, N.RESIDENT_RESOURCE_CODE_BASE)
                self.assertLessEqual(end, N.RESIDENT_RESOURCE_CODE_LIMIT)
                lo, hi = N.pc(first), N.pc(first) + end - first
                self.assertEqual(image[:lo], original[:lo])
                self.assertEqual(image[hi:], original[hi:])
                for suffix in ('GraphicsNormalLoad', 'GraphicsInvalidateCache',
                               'GraphicsResetMainCache', 'GraphicsResolveSheet',
                               'GraphicsStageMain', 'GraphicsStageAux',
                               'AnimationForceTransition', 'AnimationStage',
                               'AnimationDecompress'):
                    self.assertTrue(first <= labels['Oracle_SpecialOverworld' + suffix] < end)

    def test_unbound_mismatched_and_unmapped_contracts_refuse(self):
        for key, value in (('SPECIAL_OVERWORLD_RESIDENT_END', 224),
                           ('GfxRT_ParentCount', 160),
                           ('GfxRT_HeaderSize', 21),
                           ('SPECIAL_OVERWORLD_RESOURCE_CODE_BASE', 0x7EC800),
                           ('SPECIAL_OVERWORLD_TRANSFER_DIRECTORY', 0x7E8000),
                           ('LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY', 0x4EFF00),
                           ('LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY', 0x14E9000),
                           ('SPECIAL_OVERWORLD_RESOURCE_CODE_END', None)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                values = constants()
                if value is None:
                    del values[key]
                else:
                    values[key] = value
                result, _, _, _ = assemble(directory, values)
                self.assertNotEqual(result.returncode, 0)

    def test_current_source_joins_keep_native_conversion_and_upload_owners(self):
        text = (ROOT / 'Overworld/ZSCustomOverworld.asm').read_text()
        self.assertEqual(text.count('JSL Oracle_SpecialOverworldGraphicsStageMain'), 2)
        self.assertEqual(text.count('JSL Oracle_SpecialOverworldGraphicsStageAux'), 1)
        self.assertEqual(text.count('JSL Oracle_SpecialOverworldGraphicsResetMainCache'), 2)
        self.assertEqual(text.count('JSL Oracle_SpecialOverworldAnimationDecompress'), 6)
        self.assertIn('JSR.w PrepTransMainGFX\n                if !SPECIAL_OVERWORLD_RESOURCES_ENABLED', text)
        self.assertIn('JSL.l PrepTransAuxGFX\n        if !SPECIAL_OVERWORLD_RESOURCES_ENABLED', text)
        # The existing native 0400 animation DMA remains in its source owner.
        self.assertIn('LDA.w #$0400 : STA.w DMA.0_TransferSizeLow', text)
        body = (ROOT / 'Overworld/special_overworld_graphics.asm').read_text()
        self.assertIn('LDA.l $7E008A\n  CMP.w #!SPECIAL_OVERWORLD_RESIDENT_FIRST', body)
        self.assertNotIn('STA.l $7EC2FC', body)  # No native sprite-cache write.


if __name__ == '__main__':
    unittest.main()
