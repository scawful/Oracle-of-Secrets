"""Compiled palette-body boundaries; no CPU/fade or full-source qualification."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lyra_native_loaders as N

ROOT = Path(__file__).resolve().parents[3]
ASSEMBLER = shutil.which('asar')


def constants(capacity=192):
    return dict(SPECIAL_OVERWORLD_NATIVE=1, SPECIAL_OVERWORLD_RESIDENT_ENABLED=1,
        SPECIAL_OVERWORLD_PALETTE_ENABLED=1, SPECIAL_OVERWORLD_RESIDENT_FIRST=128,
        SPECIAL_OVERWORLD_RESIDENT_END=capacity,
        SPECIAL_OVERWORLD_PALETTE_CODE_BASE=N.RESIDENT_PALETTE_CODE_BASE,
        SPECIAL_OVERWORLD_PALETTE_CODE_END=N.RESIDENT_PALETTE_CODE_LIMIT,
        SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY=0xCFE000,
        SPECIAL_OVERWORLD_RESIDENT_PALETTE_STRIDE=3)


def assemble(directory, values):
    directory = Path(directory)
    rom, asm, symbols = (directory / name for name in ('probe.sfc', 'probe.asm', 'probe.sym'))
    original = bytes([0xCC]) * 0x400000
    rom.write_bytes(original)
    text = 'lorom\n'
    for name, address in dict(SpecialOverworldPaletteHoleReference=0x7E1E8C,
            SpecialOverworldPaletteHoleEffective=0x7E1E98,
            SpecialOverworldPaletteHoleState=0x7E1EA4,
            SpecialOverworldPaletteHoleArea=0x7E1EA5).items():
        text += f'Oracle_{name} = ${address:06X}\n'
    text += 'Oracle_LoadDayNightPaletteEffect = $3B8000\n'
    text += 'struct TimeState $7EE010\n'
    for name in ('BlueVal', 'GreenVal', 'RedVal', 'TempColor', 'SubColor'):
        text += f'.{name}: skip 2\n'
    text += 'endstruct\n'
    text += ''.join(f'!{key} = ${value:X}\n' for key, value in values.items())
    text += f'incsrc "{ROOT / "Overworld/special_overworld_palette.asm"}"\n'
    asm.write_text(text)
    result = subprocess.run([ASSEMBLER, '--no-title-check', '--fix-checksum=off',
        '--symbols=wla', f'--symbols-path={symbols}', str(asm), str(rom)],
        capture_output=True, text=True)
    labels = {}
    if symbols.exists():
        labels = {name: int(bank + offset, 16) for bank, offset, name in re.findall(
            r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\w+)$', symbols.read_text(), re.M)}
    return result, original, rom.read_bytes(), labels


@unittest.skipUnless(ASSEMBLER, 'Asar required for palette-body checks')
class SpecialOverworldPaletteTest(unittest.TestCase):
    def test_disabled_body_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            result, original, image, _ = assemble(directory, {})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(image, original)

    def test_capacities_fit_only_reserved_code_and_bind_native_bg_readers(self):
        for capacity in (160, 192):
            with self.subTest(capacity=capacity), tempfile.TemporaryDirectory() as directory:
                result, original, image, labels = assemble(directory, constants(capacity))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                lo = labels['Oracle_SpecialOverworldPaletteCodeStart']
                hi = labels['Oracle_SpecialOverworldPaletteCodeEnd']
                self.assertEqual(lo, N.RESIDENT_PALETTE_CODE_BASE)
                self.assertLessEqual(hi, N.RESIDENT_PALETTE_CODE_LIMIT)
                body = image[N.pc(lo):N.pc(lo) + hi-lo]
                self.assertEqual(image[:N.pc(lo)], original[:N.pc(lo)])
                self.assertEqual(image[N.pc(lo)+hi-lo:], original[N.pc(lo)+hi-lo:])
                for name in ('Begin', 'CompleteBuffer', 'CompleteBoth', 'Reset'):
                    self.assertTrue(lo <= labels['Oracle_SpecialOverworldPalette'+name] < hi)
                # The shared16-entry offset table exceeds the14 actual animated
                # palette records. Never admit14/15, which alias main BG data.
                self.assertIn(bytes.fromhex('AFB80A7E29FF00C90E00'), body)
                for address in (0x1BEEC7, 0x1BEEE8, 0x1BEF0C, 0x1BEEA8, 0x3B8000):
                    self.assertEqual(body.count(b'\x22'+address.to_bytes(3,'little')),1)

    def test_unbound_or_unmapped_contracts_refuse(self):
        for key, value in (('SPECIAL_OVERWORLD_RESIDENT_END',224),
                ('SPECIAL_OVERWORLD_PALETTE_CODE_BASE',0x7EF000),
                ('SPECIAL_OVERWORLD_PALETTE_CODE_END',None),
                ('SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY',0x7E8000),
                ('SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY',0xCFFF80),
                ('SPECIAL_OVERWORLD_RESIDENT_PALETTE_STRIDE',2)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                values = constants()
                if value is None:
                    del values[key]
                else:
                    values[key] = value
                result, _, _, _ = assemble(directory, values)
                self.assertNotEqual(result.returncode,0)


if __name__ == '__main__':
    unittest.main()
