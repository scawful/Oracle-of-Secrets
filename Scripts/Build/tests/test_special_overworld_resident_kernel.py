"""Assembled word-hook contracts, without native CPU/resource qualification."""
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
# Independent call-site census, including the native stores consumed by full
# rendering. The remaining36 dictionary operands must remain unchanged.
HOOKS = (
    (0x02FE1B, 'Full0', 7), (0x02FE22, 'Full2', 7),
    (0x02FE2B, 'Full1', 7), (0x02FE32, 'Full3', 7),
    (0x02F456, 'Horizontal0', 4), (0x02F45D, 'Horizontal1', 4),
    (0x02F466, 'Horizontal2', 4), (0x02F46D, 'Horizontal3', 4),
    (0x02F51E, 'Vertical0', 4), (0x02F525, 'Vertical2', 4),
    (0x02F52E, 'Vertical1', 4), (0x02F535, 'Vertical3', 4),
    (0x1BC9B2, 'Mutable0', 4), (0x1BC9B9, 'Mutable1', 4),
    (0x1BC9C0, 'Mutable2', 4), (0x1BC9C7, 'Mutable3', 4),
    (0x1BCA3F, 'Mutable0', 4), (0x1BCA46, 'Mutable1', 4),
    (0x1BCA4D, 'Mutable2', 4), (0x1BCA54, 'Mutable3', 4))


def source_fixture():
    image = bytearray(0x400000)
    readers = [(400, at, offset) for at, offset in N.TILE16_LONG_READERS]
    readers += list(N.TILE32_LONG_READERS)
    for entry_id, at, offset in readers:
        index = N.pc(at)
        image[index - 1] = 0xBF
        # Real source accepts both mapped FastROM and slow-bank aliases.
        image[index:index + 3] = (N.CURRENT_DICTIONARIES[entry_id] + offset
                                  | 0x800000).to_bytes(3, 'little')
    for at in N.TILE16_BANK_READERS:
        image[N.pc(at) - 1:N.pc(at) + 1] = bytes([0xA9, 0x3D])
    for at, offset in N.TILE16_WORD_READERS:
        index = N.pc(at)
        image[index - 1:index + 2] = bytes([0xB9]) + (0x8000 + offset).to_bytes(2, 'little')
        target = 0x7F2000 if offset < 4 else 0x7F2040
        image[index + 2:index + 6] = bytes([0x9F]) + target.to_bytes(3, 'little')
    return bytes(image)


def constants(capacity=192):
    tables = {family.name: family.snes for family in N.current_table_layout(N.TABLE_BASE)}
    return dict(ENABLE_SKY_OVERWORLD_ROUTE=0,
                SPECIAL_OVERWORLD_NATIVE=1, SPECIAL_OVERWORLD_RESIDENT_ENABLED=1,
                SPECIAL_OVERWORLD_RESIDENT_FIRST=0x80, SPECIAL_OVERWORLD_RESIDENT_END=capacity,
                LYRA_CURRENT_RESIDENT_ABI_VERSION=1, LYRA_CURRENT_RESIDENT_TILE16_COUNT=4096,
                LYRA_CURRENT_RESIDENT_CODE_BASE=N.RESIDENT_WORD_CODE_BASE,
                LYRA_CURRENT_RESIDENT_CODE_END=N.RESIDENT_WORD_CODE_LIMIT,
                LYRA_CURRENT_RESIDENT_DIRECTORY=0x4E8000,
                LYRA_CURRENT_TABLE_parent=tables['parent'],
                LYRA_CURRENT_TABLE_area_size=tables['area_size'],
                LYRA_CURRENT_MAP16_DEFINITIONS=0x3D8000)


def assemble(directory, image, values):
    directory = Path(directory)
    rom, asm, symbols = (directory / name for name in ('probe.sfc', 'probe.asm', 'probe.sym'))
    rom.write_bytes(image)
    text = 'lorom\n' + ''.join(f'!{key} = ${value:X}\n' for key, value in values.items())
    text += f'incsrc "{ROOT / "Overworld/special_overworld_resident.asm"}"\n'
    asm.write_text(text)
    result = subprocess.run([ASSEMBLER, '--no-title-check', '--fix-checksum=off',
                             '--symbols=wla', f'--symbols-path={symbols}', str(asm), str(rom)],
                            capture_output=True, text=True)
    labels = {}
    if symbols.exists():
        labels = {name: int(bank + offset, 16) for bank, offset, name in re.findall(
            r'^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\w+)$', symbols.read_text(), re.M)}
    return result, rom.read_bytes(), labels


@unittest.skipUnless(ASSEMBLER, 'Asar required for compiled kernel checks')
class SpecialOverworldResidentKernelTest(unittest.TestCase):
    def test_sky_overlay_variant_keeps_hook_contract_and_code_reservation(self):
        original = source_fixture()
        with tempfile.TemporaryDirectory() as directory:
            values = constants()
            values['ENABLE_SKY_OVERWORLD_ROUTE'] = 1
            result, image, labels = assemble(directory, original, values)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLessEqual(labels['Lyra_ResidentAtlasCodeEnd'],
                             N.RESIDENT_WORD_CODE_LIMIT)
        start = labels['Lyra_ResidentAtlasCodeStart']
        end = labels['Lyra_ResidentAtlasCodeEnd']
        permitted = [(N.pc(start), N.pc(start) + end - start)]
        for site, suffix, size in HOOKS:
            target = labels['Lyra_Resident' + suffix]
            expected = b'\x22' + target.to_bytes(3, 'little') + b'\xEA' * (size - 4)
            self.assertEqual(image[N.pc(site):N.pc(site) + size], expected)
            permitted.append((N.pc(site), N.pc(site) + size))
        for index, (old, new) in enumerate(zip(original, image)):
            if old != new:
                self.assertTrue(any(a <= index < b for a, b in permitted), hex(index))
        self.assertEqual(len(image), len(original))

    def test_disabled_module_emits_nothing(self):
        original = source_fixture()
        with tempfile.TemporaryDirectory() as directory:
            result, image, _ = assemble(directory, original, {})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(image, original)

    def test_both_capacities_bind_twenty_hooks_and_preserve_other_dictionary_readers(self):
        for capacity in (160, 192):
            with self.subTest(capacity=capacity), tempfile.TemporaryDirectory() as directory:
                original = source_fixture()
                N.verify_dictionary_readers(original,
                    {key: (value, 1) for key, value in N.CURRENT_DICTIONARIES.items()})
                result, image, labels = assemble(directory, original, constants(capacity))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                start, end = (labels['Lyra_ResidentAtlasCode' + suffix] for suffix in ('Start', 'End'))
                self.assertEqual(start, N.RESIDENT_WORD_CODE_BASE)
                self.assertLessEqual(end, N.RESIDENT_WORD_CODE_LIMIT)
                permitted = [(N.pc(start), N.pc(start) + end - start)]
                for site, suffix, size in HOOKS:
                    target = labels['Lyra_Resident' + suffix]
                    expected = b'\x22' + target.to_bytes(3, 'little') + b'\xEA' * (size - 4)
                    self.assertEqual(image[N.pc(site):N.pc(site) + size], expected)
                    permitted.append((N.pc(site), N.pc(site) + size))
                for index, (old, new) in enumerate(zip(original, image)):
                    if old != new:
                        self.assertTrue(any(a <= index < b for a, b in permitted), hex(index))
                self.assertEqual(len(image), len(original))

    def test_changed_hook_preimage_is_refused(self):
        original = bytearray(source_fixture())
        original[N.pc(HOOKS[-1][0])] ^= 1
        with tempfile.TemporaryDirectory() as directory:
            result, _, _ = assemble(directory, bytes(original), constants())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Tile16 reader moved', result.stdout + result.stderr)

    def test_unbound_or_invalid_origins_capacity_and_extent_are_refused(self):
        for key, value in (('SPECIAL_OVERWORLD_RESIDENT_FIRST', 0xA0),
                           ('SPECIAL_OVERWORLD_RESIDENT_END', 224),
                           ('LYRA_CURRENT_RESIDENT_DIRECTORY', 0x4EFF00),
                           ('LYRA_CURRENT_RESIDENT_DIRECTORY', 0x7E8000),
                           ('LYRA_CURRENT_RESIDENT_CODE_BASE', 0x7F8000),
                           ('LYRA_CURRENT_MAP16_DEFINITIONS', 0x3E8000),
                           ('LYRA_CURRENT_RESIDENT_CODE_END', N.RESIDENT_WORD_CODE_BASE + 8),
                           ('LYRA_CURRENT_RESIDENT_TILE16_COUNT', 4097),
                           ('LYRA_CURRENT_RESIDENT_CODE_BASE', None)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                values = constants()
                if value is None:
                    del values[key]
                else:
                    values[key] = value
                result, _, _ = assemble(directory, source_fixture(), values)
                self.assertNotEqual(result.returncode, 0, key)


if __name__ == '__main__':
    unittest.main()
