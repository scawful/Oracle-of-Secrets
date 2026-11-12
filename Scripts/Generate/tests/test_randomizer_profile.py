"""Read-only consumer guards; synthetic bytes cannot be confused with release ROMs."""
import copy
import importlib.util
import json
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
        self.assertEqual(known[0x4D]['equipment_id'], 4)
        b49, authoring = self.release['artifacts']
        self.assertNotIn(0x4D, b49['receipt_reader_supported_ids'])
        self.assertEqual(authoring['receipt_reader_supported_ids'], [])
        self.assertEqual(b49['room_94_first_chest']['item_receipt'], 0x0A)
        self.assertEqual(authoring['room_94_first_chest']['item_receipt'], 0x4D)
        for artifact in self.release['artifacts']:
            allowed = set(artifact['receipt_reader_supported_ids'])
            unknown = set(artifact['unsupported_or_unknown_receipt_ids'])
            self.assertFalse(allowed & unknown)
            self.assertEqual(allowed | unknown, set(range(256)))


if __name__ == '__main__':
    unittest.main()
