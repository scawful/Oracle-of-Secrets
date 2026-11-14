"""Pure synthetic-input controls; no Asar, game ROM, Build or workflow run."""
from pathlib import Path
import unittest

import d4_hub_ci_fixture as fixture
import seed_sky_award_preimages as preimages

ROOT = Path(__file__).resolve().parents[2]


class D4HubCIFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed, cls.expected = fixture.fixture_inputs(ROOT)

    def data(self):
        return preimages.apply_seed(bytes(preimages.ROM_SIZE), self.seed)

    def test_source_derived_hooks_and_complete_typed_fixture(self):
        data = self.data()
        self.assertEqual(data[0x34003:0x34007], bytes.fromhex('22bcd605'))
        self.assertEqual(data[0x2d9f3:0x2d9f9], bytes.fromhex('a5f21022a5f0'))
        self.assertEqual(data[0x4f554:0x4f558], bytes.fromhex('c909d006'))
        self.assertEqual(data[0x2d953:0x2d956], bytes.fromhex('2050fa'))
        self.assertEqual(data[0x2d6ce], 0x6b)
        self.assertEqual(len(self.seed), 18)
        self.assertEqual(set(self.expected), {
            'Dungeons/generated/d4_water/25-low.bin',
            'Dungeons/generated/d4_water/25-high.bin',
            'Dungeons/generated/d4_water/25-low-collision.bin',
            'Dungeons/generated/d4_water/25-high-collision.bin',
            'Dungeons/generated/water_gate_runtime_tables.asm'})
        asm = self.expected['Dungeons/generated/water_gate_runtime_tables.asm']
        self.assertIn(b'D4HubContacts:', asm)
        self.assertIn(b'D4HubContactsBound = 1', asm)
        self.assertIn(b'db $02, $01', asm)
        self.assertIn(b'dw $0A70, $0460, $0A70, $04F0', asm)
        fixture.validate_fixture_inputs(data, self.expected, self.seed, self.expected)

    def test_each_missing_hook_or_draw_preimage_refuses(self):
        for offset in (0x34003, 0x2d9f3, 0x4f554, 0x2d953, 0x2d6ce):
            with self.subTest(offset=hex(offset)):
                data = self.data()
                data[offset] = 0
                with self.assertRaisesRegex(ValueError, 'hook preimage missing'):
                    fixture.validate_fixture_inputs(data, self.expected, self.seed, self.expected)

    def test_each_missing_generated_state_or_include_refuses(self):
        for name in self.expected:
            with self.subTest(name=name):
                incomplete = {k: v for k, v in self.expected.items() if k != name}
                with self.assertRaisesRegex(ValueError, 'state/type binding missing'):
                    fixture.validate_fixture_inputs(self.data(), incomplete, self.seed, self.expected)

    def test_missing_bound_flag_or_wrong_abi_refuses(self):
        name = 'Dungeons/generated/water_gate_runtime_tables.asm'
        for bad in (self.expected[name].replace(b'D4HubContactsBound = 1',
                                              b'D4HubContactsBound = 0'),
                    self.expected[name].replace(b'db $02, $01', b'db $00, $01')):
            with self.assertRaisesRegex(ValueError, 'state/type binding missing'):
                fixture.validate_fixture_inputs(self.data(), {**self.expected, name: bad},
                                                self.seed, self.expected)

    def test_changed_state_or_stale_collision_profile_refuses(self):
        for name in self.expected:
            if name.endswith('.bin'):
                with self.subTest(name=name):
                    bad = {**self.expected, name: self.expected[name] + b'\x00'}
                    with self.assertRaisesRegex(ValueError, 'state/type binding missing'):
                        fixture.validate_fixture_inputs(self.data(), bad, self.seed, self.expected)

    def test_conflicting_existing_synthetic_byte_is_not_overwritten(self):
        data = bytearray(preimages.ROM_SIZE)
        data[0x34003] = 0xff
        with self.assertRaises(preimages.SeedError):
            preimages.apply_seed(data, self.seed)

    def test_legacy_fixture_retains_original_prep_offset_and_abi(self):
        seed, expected = fixture.fixture_inputs(ROOT, paired=False)
        self.assertEqual(seed, self.seed)
        asm = expected['Dungeons/generated/water_gate_runtime_tables.asm']
        self.assertIn(b'db $01, $01', asm)
        self.assertIn(b'dw $0A70, $0465, $0A70, $04F0', asm)


if __name__ == '__main__':
    unittest.main()
