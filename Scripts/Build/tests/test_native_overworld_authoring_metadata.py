"""Cross-consumer structural metadata controls, without live sprite binding."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_overworld_authoring_metadata as M
import lyra_native_loaders as N

SPEC = importlib.util.spec_from_file_location(
    'authoring_metadata_fixture', Path(__file__).with_name('test_lyra_native_loaders.py'))
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


def placements():
    rows = [dict(id=identity, kind=1, state=1, phase=1, owner_map=0xB0,
                 ordinal=index, packed=[y, x, 0x52])
            for index, (identity, x, y) in enumerate((
                (0x5001, 23, 14), (0x5002, 15, 21), (0x5005, 40, 12),
                (0x5003, 13, 43), (0x5004, 37, 45)))]
    rows += [dict(id=0x6001, kind=2, state=2, map=0xB0, x=21, y=9, target=0x0B, row=None),
             dict(id=0x6002, kind=3, state=2, map=0xB0, x=22, y=11, target=0x83, row=None)]
    return dict(next_placement_id=0x6003, placements=rows)


class NativeAuthoringMetadataTest(unittest.TestCase):
    def test_round_trip_order_targets_and_present_zero(self):
        value = placements()
        raw = M.encode(value, 192)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'f4a8e2cd3c1fede254883fc646b0faa6d9c93389cb85b71c74e8fe58a7597781')
        self.assertEqual(len(raw), 8192)
        self.assertEqual(M.decode(raw, 192), value)
        self.assertEqual(raw[32:36], bytes.fromhex('01500000'))
        self.assertEqual(raw[32 * 6 + 7], 1)
        self.assertEqual(raw[32 * 7 + 7], 1)
        value['placements'][5].update(target=0, row=0)
        value['placements'][6].update(target=None, row=0)
        zeros = M.encode(value, 192)
        self.assertNotEqual(raw, zeros)
        self.assertEqual(zeros[32 * 6 + 7], 3)
        self.assertEqual(zeros[32 * 7 + 7], 2)
        self.assertEqual(M.decode(zeros, 192), value)

    def test_deleted_locator_can_be_reused_but_identity_cannot(self):
        value = placements()
        value['placements'][1]['state'] = 3
        value['placements'][2]['ordinal'] = 1
        self.assertEqual(M.decode(M.encode(value, 192), 192), value)
        value['placements'][1]['state'] = 1
        with self.assertRaises(ValueError):
            M.encode(value, 192)
        value['placements'][1]['state'] = 3
        value['placements'][2]['id'] = value['placements'][1]['id']
        with self.assertRaises(ValueError):
            M.encode(value, 192)

    def test_rejects_reserved_bytes_stale_next_id_and_unbounded_rows(self):
        encoded = M.encode(placements(), 192)
        for at, byte in ((0, 0), (20, 1), (255 * 32, 1),
                         (32 + 7, 1), (32 + 10, 255), (32 + 13, 1),
                         (32 * 6 + 6, 0), (32 * 6 + 11, 1)):
            with self.subTest(at=at):
                raw = bytearray(encoded)
                raw[at] = byte
                with self.assertRaises(ValueError):
                    M.decode(bytes(raw), 192)
        for change in (lambda v: v.update(next_placement_id=0x5000),
                       lambda v: v['placements'][6].update(row=0x4F),
                       lambda v: v['placements'][5].update(target=256),
                       lambda v: v['placements'][0].update(owner_map=192),
                       lambda v: v['placements'][0].update(phase=True),
                       lambda v: v['placements'][0].update(unknown=1)):
            value = placements()
            change(value)
            with self.assertRaises(ValueError):
                M.encode(value, 192)

    def test_optional_directory_capability_requires_typed_payload(self):
        fixture = F.Revision4AppearanceDirectoryTest()
        fixture.setUp()
        original = fixture.installed()
        before_directory = original[N.DIRECTORY_PC:N.DIRECTORY_PC + 1024]
        at = N.pc(N.AUTHORING_METADATA_BASE)
        fixture.image[at:at + M.SIZE] = M.encode(placements(), 192)
        fixture.entries.append(N.initial_authoring_entry(192))
        image = fixture.installed()
        directory = image[N.DIRECTORY_PC:N.DIRECTORY_PC + 1024]
        self.assertEqual(struct.unpack_from('<6HBBH', directory, 8),
                         (4, 32, 944, 192, 192, 57, 0x4C, 0x3C, 384))
        self.assertEqual(N.read_native_directory(image)[2][412], (N.AUTHORING_METADATA_BASE, 256))
        self.assertEqual(before_directory[15], directory[15])
        with self.assertRaisesRegex(ValueError, 'resident resource compilation'):
            N.reader_constants(image)
        fixture.image[at + 20] = 1
        with self.assertRaisesRegex(ValueError, 'authoring metadata'):
            fixture.encode()
        broken = bytearray(image)
        broken[N.DIRECTORY_PC] ^= 1
        with self.assertRaises(ValueError):
            N.read_native_directory(bytes(broken))


if __name__ == '__main__':
    unittest.main()
