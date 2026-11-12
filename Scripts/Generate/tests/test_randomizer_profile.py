"""Read-only consumer guards; synthetic bytes cannot be confused with release ROMs."""
import copy
import importlib.util
import json
import os
import re
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'generate_randomizer_profile.py'
spec = importlib.util.spec_from_file_location('randomizer_profile', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RandomizerProfileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.rom = Path(self.temp.name) / 'synthetic.bin'
        self.rom.write_bytes(b'synthetic consumer fixture, not a game ROM')
        self.release = json.loads(module.DEFAULT_OUTPUT.read_text())
        self.profile = copy.deepcopy(self.release)
        self.profile['artifacts'][0]['sha256'] = module.digest(self.rom.read_bytes())
        self.profile['artifacts'][0]['bytes'] = self.rom.stat().st_size

    def test_exact_input_and_reader_boundary(self):
        self.assertEqual(module.inspect_rom(self.profile, self.rom, 0x4C)['id'], 'beta-b49')
        for receipt in (0x4D, 0xFF, -1, 256):
            with self.subTest(receipt=receipt), self.assertRaisesRegex(ValueError, 'Unsupported'):
                module.inspect_rom(self.profile, self.rom, receipt)

    def test_same_size_mutation_rejected(self):
        self.rom.write_bytes(b'X' + self.rom.read_bytes()[1:])
        with self.assertRaisesRegex(ValueError, 'Unrecognized ROM'):
            module.inspect_rom(self.profile, self.rom)

    def test_authoring_input_not_admitted_as_playable(self):
        self.profile['artifacts'][0]['role'] = 'authoring_only'
        with self.assertRaisesRegex(ValueError, 'Authoring ROM'):
            module.inspect_rom(self.profile, self.rom)

    def test_published_profile_never_accepts_synthetic_fixture(self):
        with self.assertRaisesRegex(ValueError, 'Unrecognized ROM'):
            module.inspect_rom(self.release, self.rom)

    def test_receipt_domains_and_version_boundary(self):
        known = {item['id']: item for item in self.release['receipts']['known']}
        self.assertEqual(known[0x21]['catalog_item_id'], 0x15)
        self.assertNotIn('equipment_id', known[0x4D])
        # Independent source trace: ownership row's annotated selected index
        # must resolve to the same handler as the native Hookshot menu entry.
        source = (module.ROOT / 'Menu/menu_select_item.asm').read_text()
        selected = int(re.search(r'db SwitchHookOwned&\$FF ; \$([0-9A-Fa-f]+)', source)[1], 16)
        self.assertEqual(known[0x4D]['menu_selection_id'], selected)
        table = source.split('Menu_ItemIndex:', 1)[1].split('Menu_ItemIndex_End:', 1)[0]
        values = [int(token, 16) for line in table.splitlines() if line.strip().startswith('db ')
                  for token in re.findall(r'\$([0-9A-Fa-f]+)', line.split(';')[0])]
        self.assertEqual(known[0x4D]['engine_action_id'], values[selected])
        self.assertEqual(values[selected], values[3])  # Native Hookshot/chain handler.
        ownership = (module.ROOT / 'Menu/menu_draw.asm').read_text()
        self.assertIn('LDA.w $040C : LSR A', ownership)
        self.assertIn('db SwitchHookOwned&$FF ; $04 D8 Sky Tower', ownership)
        artifacts = {artifact['id']: artifact for artifact in self.release['artifacts']}
        b49, authoring = artifacts['beta-b49'], artifacts['authoring-c91']
        self.assertEqual(known[0x4D]['supported_artifacts'], ['beta-b50'])
        self.assertEqual(known[0x4C]['supported_artifacts'], ['beta-b49', 'beta-b50'])
        self.assertNotIn(0x4D, b49['receipt_reader_supported_ids'])
        self.assertEqual(authoring['receipt_reader_supported_ids'], [])
        self.assertEqual(b49['room_94_first_chest']['item_receipt'], 0x0A)
        self.assertEqual(authoring['room_94_first_chest']['item_receipt'], 0x4D)
        for artifact in self.release['artifacts']:
            allowed = set(artifact['receipt_reader_supported_ids'])
            unknown = set(artifact['unsupported_or_unknown_receipt_ids'])
            self.assertFalse(allowed & unknown)
            self.assertEqual(allowed | unknown, set(range(256)))


    def test_actual_b50_receipt_boundary_and_fingerprints(self):
        # Release ROMs stay external; opt in with the exact delivered fixture.
        path = os.environ.get('OOS_RANDOMIZER_B50_ROM')
        if not path:
            self.skipTest('Set OOS_RANDOMIZER_B50_ROM for actual delivered-ROM verification')
        rom = Path(path)
        data = module.pinned_rom(rom, module.B50_HASH)
        artifact = module.inspect_rom(self.release, rom, 0x4D)
        self.assertEqual(artifact['id'], 'beta-b50')
        self.assertEqual(artifact['room_94_first_chest']['item_receipt'], 0x4D)
        for receipt in (0x4E, 0xFF, -1, 256):
            with self.subTest(receipt=receipt), self.assertRaisesRegex(ValueError, 'Unsupported'):
                module.inspect_rom(self.release, rom, receipt)
        for table in artifact['native_receipt_tables'].values():
            self.assertEqual(table['sha256'], module.digest(
                data[table['pc']:table['pc'] + table['bytes']]))
        extension = artifact['receipt_reader_extension']
        self.assertEqual(extension['sha256'], module.digest(
            data[extension['pc']:extension['pc'] + extension['bytes']]))
        # Derive bounds independently from the delivered companion symbols.
        symbols = {}
        for line in rom.with_suffix('.sym').read_text().splitlines():
            match = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)', line)
            if match:
                bank, offset, name = match.groups()
                symbols[name] = int(bank, 16) * 0x8000 + (int(offset, 16) & 0x7FFF)
        start, end = (symbols[name] for name in extension['symbols'])
        self.assertEqual((extension['pc'], extension['bytes']), (start, end - start))
        self.rom.write_bytes(b'X' + data[1:])
        with self.assertRaisesRegex(ValueError, 'Unrecognized ROM'):
            module.inspect_rom(self.release, self.rom, 0x4D)


if __name__ == '__main__':
    unittest.main()
