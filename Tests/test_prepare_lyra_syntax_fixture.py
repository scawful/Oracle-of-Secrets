"""CI fixture proofs use synthetic bytes and never run Asar or an emulator."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Build'))
import prepare_lyra_syntax_fixture as F


def seeded():
    raw = bytearray(0x200000)
    raw[0xE9E6:0xE9E9] = bytes.fromhex('738039')
    raw[0xE9F5:0xE9F8] = bytes.fromhex('7a8038')
    raw[0x773FF] = 0x7F
    raw[0xC0E:0xC13] = bytes.fromhex('a97f8d0443')
    raw[0xC2C5:0xC2C7] = bytes.fromhex('89cc')  # An unrelated existing CI seed.
    return bytes(raw)


class SelectedSyntaxFixtureTest(unittest.TestCase):
    def test_seeds_paired_pointer_and_other_new_guard_bytes_without_changing_existing_seed(self):
        before = seeded()
        rom, files, report = F.prepare_fixture(before)
        self.assertEqual(len(rom), 0x400000)
        self.assertEqual(before, seeded())
        self.assertEqual(rom[0xC2C5:0xC2C7], bytes.fromhex('89cc'))
        self.assertEqual(rom[0x1759D:0x175A9], bytes.fromhex('bf4df90285c8bf4ef90285c9'))
        self.assertEqual(rom[0x177E3:0x177EF], bytes.fromhex('bf4df90285c8bf4ef90285c9'))
        self.assertEqual(rom[0x144BC:0x144C0], bytes.fromhex('e210ab6b'))
        self.assertEqual(rom[0xDC8B8:0xDC8BC], bytes.fromhex('bf84a782'))
        self.assertEqual(rom[0x130F5:0x130F9], bytes.fromhex('bf40fd7e'))
        allowed = {at + offset for span in report['native_preimage_spans']
                   for at in [span['pc']] for offset in range(len(bytes.fromhex(span['payload_hex'])))}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, rom))))
        self.assertEqual(rom[0x200000:], bytes(0x200000))
        self.assertFalse(report['private_rom_used'])
        self.assertFalse(report['runtime_verified'])

    def test_normal_renderer_emits_full_table_labels_constants_and_synthetic_context(self):
        _, files, report = F.prepare_fixture(seeded())
        assembly = files['runtime_data.asm'].decode()
        constants = files['runtime_constants.asm'].decode()
        plan = json.loads(files['prepare.json'])
        self.assertEqual(plan['kind'], F.KIND)
        self.assertNotEqual(plan['kind'], 'lyra.ordinary_build_prepare.v1')
        self.assertTrue(plan['syntax_only'])
        self.assertEqual(report['table_count'], 30)
        for name, _, _, _, _, _, offset in F.A.SPECS:
            self.assertIn('LyraRuntime_' + name + ':', assembly)
            self.assertIn(f'!LYRA_TABLE_{name} = ${0x28C000 + offset:06X}', constants)
        self.assertIn('org $F8DFC0\nLyra_A1Descriptor:', assembly)
        descriptor = bytes.fromhex(plan['descriptor']['payload_hex'])
        self.assertEqual(len(descriptor), 64)
        self.assertEqual(descriptor[30:32], bytes(2))
        self.assertEqual(plan['production_maps'], [])
        self.assertEqual(plan['production_edge_ids'], [])
        self.assertEqual(files['binaries/payload.bin'], b''.join(bytes.fromhex(w['payload_hex']) for w in plan['writes']))

    def test_unseeded_real_header_already_assembled_or_wrong_size_inputs_refuse(self):
        for source in (bytes(0x200000), bytes(1024), seeded() + b'x',
                       b'\x78' + seeded()[1:], seeded()[:0x7FC0] + b'Real SNES title!' + seeded()[0x7FC0 + 16:]):
            with self.subTest(size=len(source)), self.assertRaises(ValueError):
                F.prepare_fixture(source)


if __name__ == '__main__':
    unittest.main()
