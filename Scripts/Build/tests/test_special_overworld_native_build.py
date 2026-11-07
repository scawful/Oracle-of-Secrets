"""Offline preparation controls; no ROM publication, assembly or emulator."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lyra_native_loaders as N
import special_overworld_native_build as B

SPEC = importlib.util.spec_from_file_location('native_build_resource_fixture',
    Path(__file__).with_name('test_special_overworld_resources.py'))
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


class NativeBuildPreparationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = F.SavedNativeTerrainResourcesTest()
        self.fixture.setUp()
        image = bytearray(self.fixture.source)
        count, bank, entries = N.read_native_directory(bytes(image))
        for index, site in enumerate((0x02F59D, 0x02F5C8, 0x02F7E3, 0x02F80E, 0x09C4F0)):
            target = N.CODE_BASE + index * 4
            instruction = bytes([0x22 if index < 4 else 0x5C]) + target.to_bytes(3, 'little')
            image[N.pc(site):N.pc(site) + 4] = instruction
            at = N.pc(entries[301][0]) + index * 16
            struct.pack_into('<IIHBB', image, at, site, target,
                (20 + index % 2) if index < 4 else 16,
                (1 if index < 2 else 2) if index < 4 else 4, 0)
            image[at + 12:at + 16] = instruction
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = N.encode_revision4_directory(
            bytes(image), [(key, at, rows) for key, (at, rows) in entries.items()],
            tail_actor_bank=bank, capacity=count)
        self.source = bytes(image)
        self.exported = self.fixture.make_export(self.source)
        self.origin, self.capacity = N.RESIDENT_DATA_PC, N.RESIDENT_DATA_CAPACITY
        self.preimage = self.source[self.origin:self.origin + self.capacity]

    def prepare(self, **kwargs):
        args = dict(data_pc=self.origin, capacity=self.capacity,
                    preimage=self.preimage)
        args.update(kwargs)
        return B.prepare_revision4_compilation(self.source, self.exported, **args)

    def test_existing_codecs_emit_bound_transactions_without_mutation_or_admission(self):
        old_export = copy.deepcopy(self.exported)
        old_source = self.source
        result = self.prepare()
        self.assertTrue(result['saved_payloads_preserved'])
        self.assertEqual(result['reader_code']['status'], 'preserved')
        self.assertEqual(result['source_reseal_writes'], [])
        self.assertEqual(self.exported, old_export)
        self.assertEqual(self.source, old_source)
        self.assertFalse(result['ordinary_build_ready'])
        self.assertFalse(result['allocation_granted'])
        self.assertFalse(result['runtime_admission'])
        self.assertFalse(result['publication_authorized'])
        self.assertFalse(result['full_residency_ready'])
        self.assertEqual(result['unresolved_full_residency_unknowns'],
                         result['resource_plan']['unknowns'])
        self.assertTrue(result['reader_bindings_validated'])
        self.assertFalse(result['reexport_required_after_reseal'])
        self.assertNotIn('!SPECIAL_OVERWORLD_NATIVE = 1', result['constants_asm'])
        with self.assertRaisesRegex(ValueError, 'cannot publish revision4'):
            N.reader_constants(self.source)
        # The emitter's binary offsets exclude bank padding: use each actual
        # placement, never pretend payload_hex is a contiguous ROM transaction.
        for row, write in zip(result['emission']['placements'], result['resource_writes']):
            self.assertEqual(write['pc'], row['pc'][0])
            self.assertEqual(write['before'], old_source[write['pc']:write['pc'] + len(write['after'])])
            self.assertEqual(hashlib.sha256(write['after']).hexdigest(), row['sha256'])
        self.assertEqual(self.prepare(), result)

    def test_explicit_same_extent_code300_reseal_preserves_every_other_entry(self):
        count, bank, entries = N.read_native_directory(self.source)
        at, size = entries[300]
        first = N.pc(at)
        old = self.source[first:first + size]
        new = bytes([old[0] ^ 1]) + old[1:]
        replacement = B.ReaderCodeReplacement(hashlib.sha256(old).hexdigest(), new)
        result = self.prepare(reader_code_replacement=replacement)
        self.assertEqual(result['reader_code']['status'], 'explicit_same_extent_reseal')
        self.assertTrue(result['reexport_required_after_reseal'])
        image = bytearray(self.source)
        for write in result['source_reseal_writes']:
            pc = write['pc']
            self.assertEqual(image[pc:pc + len(write['before'])], write['before'])
            image[pc:pc + len(write['after'])] = write['after']
        self.assertEqual(N.read_native_directory(bytes(image)), (count, bank, entries))
        for key, (address, rows) in entries.items():
            if key == 300:
                continue
            pc, length = N.pc(address), rows * N.entry_spec(key, count, 4)[2]
            self.assertEqual(image[pc:pc + length], self.source[pc:pc + length])
        with self.assertRaisesRegex(ValueError, 'cannot publish revision4'):
            N.reader_constants(bytes(image))

    def test_changed_installed_call_witness_refuses_before_compilation(self):
        image = bytearray(self.source)
        image[N.pc(0x02F59D) + 1] ^= 1
        self.source = bytes(image)
        with self.assertRaisesRegex(ValueError, 'READER_BINDING_INVALID'):
            self.prepare()

    def test_noop_reseal_preserves_accepted_directory_record_order(self):
        image = bytearray(self.source)
        first = N.DIRECTORY_PC
        size = struct.unpack_from('<H', image, first + 12)[0]
        records = [image[at:at + 16] for at in range(first + 32, first + size, 16)]
        image[first + 32:first + size] = b''.join(reversed(records))
        image[first + 28:first + 32] = bytes(4)
        struct.pack_into('<I', image, first + 28, zlib.crc32(image[first:first + N.DIRECTORY_SIZE]))
        self.source = bytes(image)
        self.exported = self.fixture.make_export(self.source)
        _, _, entries = N.read_native_directory(self.source)
        at, count = entries[300]
        old = self.source[N.pc(at):N.pc(at) + count]
        result = self.prepare(reader_code_replacement=B.ReaderCodeReplacement(
            hashlib.sha256(old).hexdigest(), old))
        self.assertEqual(result['source_reseal_writes'], [])
        self.assertFalse(result['reexport_required_after_reseal'])
        self.assertEqual(result['reader_code']['resealed_source_sha256'],
                         hashlib.sha256(self.source).hexdigest())

    def test_resource_interval_cannot_replace_an_installed_call_witness(self):
        image = bytearray(self.source)
        count, bank, entries = N.read_native_directory(self.source)
        record = N.pc(entries[301][0]) + 4 * 16
        target_site = 0x4E8000
        struct.pack_into('<I', image, record, target_site)
        image[N.pc(target_site):N.pc(target_site) + 4] = image[record + 12:record + 16]
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = N.encode_revision4_directory(
            bytes(image), [(key, at, rows) for key, (at, rows) in entries.items()],
            tail_actor_bank=bank, capacity=count)
        self.source = bytes(image)
        self.preimage = self.source[self.origin:self.origin + self.capacity]
        self.exported = self.fixture.make_export(self.source)
        with self.assertRaisesRegex(ValueError, 'RESIDENT_OVERLAPS_READER_CALL'):
            self.prepare()

    def test_stale_preimage_export_and_reader_reseal_refuse(self):
        with self.assertRaisesRegex(ValueError, 'PREIMAGE_MISMATCH'):
            self.prepare(preimage=bytes([self.preimage[0] ^ 1]) + self.preimage[1:])
        with self.assertRaisesRegex(ValueError, 'RESERVATION_MISMATCH'):
            self.prepare(data_pc=self.origin + 1)
        with self.assertRaisesRegex(ValueError, 'SOURCE_MISMATCH'):
            self.prepare(reader_code_replacement=B.ReaderCodeReplacement('0' * 64, b'x'))
        _, _, entries = N.read_native_directory(self.source)
        at, count = entries[300]
        old = self.source[N.pc(at):N.pc(at) + count]
        with self.assertRaisesRegex(ValueError, 'EXTENT_CHANGE_UNSUPPORTED'):
            self.prepare(reader_code_replacement=B.ReaderCodeReplacement(
                hashlib.sha256(old).hexdigest(), old + b'x'))
        self.exported = copy.deepcopy(self.exported)
        self.exported['native_source']['pages'][0]['tiles'][0] ^= 1
        with self.assertRaisesRegex(ValueError, 'EXPORT_HASH_MISMATCH'):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
