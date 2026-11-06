"""Initial native data lowering; fixtures do not qualify a production ROM."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
import zlib

SOURCE = Path(__file__).resolve().parents[1] / 'lyra_native_loaders.py'
SPEC = importlib.util.spec_from_file_location('native_overworld_producer', SOURCE)
N = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = N
SPEC.loader.exec_module(N)


class NativeTableLoweringTest(unittest.TestCase):
    def setUp(self):
        self.source = bytes(range(256)) * (0x220000 // 256)
        self.layout = N.current_table_layout(0x468000)
        self.rows = {}
        for map_id in range(0xA0, 0xC0):
            values = {f.name: ([map_id] * 8 if f.stride == 8 else map_id)
                      for f in self.layout}
            values.update(parent=map_id, area_size=0, role=255,
                          map32_high=0x488000, map32_low=0x488100)
            self.rows[map_id] = values

    def lower(self, source=None):
        return N.lower_tables(self.source if source is None else source, self.rows,
                              table_base=0x468000, legacy_roles=[255] * 160)

    def test_retained_physical_layout_and_revision3_ids(self):
        by_id = {f.id: f for f in self.layout}
        self.assertEqual(len(by_id), 39)
        self.assertEqual(by_id[20].snes, 0x469E00)
        self.assertEqual(by_id[24].snes, 0x46A580)
        self.assertEqual(by_id[30].snes, 0x46A940)
        self.assertEqual(by_id[36].snes, 0x46ADC0)
        self.assertEqual(by_id[38].name, 'special_sprite_palettes_phase2')
        self.assertEqual(by_id[39].name, 'special_sprite_gfx_phase2')
        self.assertEqual(by_id[29].snes, 0x46B0C0)
        self.assertEqual(by_id[29].snes + 192, 0x46B180)

    def test_all_native_domains_and_tail_values_survive_lowering(self):
        result = self.lower()
        for f in self.layout:
            if f.name != 'role':
                first, length = f.legacy_first * f.stride, f.legacy_rows * f.stride
                start = N.pc(f.legacy_snes)
                self.assertEqual(result[f.id][first:first + length],
                                 self.source[start:start + length], f.name)
                if f.name.startswith('music_phase'):
                    start = N.pc(0x02C403)
                    self.assertEqual(result[f.id][0x40:0xA0], self.source[start:start + 0x60])
            for map_id in range(0xA0, 0xC0):
                start = map_id * f.stride
                self.assertEqual(result[f.id][start:start + f.stride],
                                 N._row_bytes(self.rows[map_id][f.name], f.stride, f.name))
        self.assertEqual(result[24][:0x80], bytes(0x80))
        self.assertEqual(result[29], bytes([255]) * 192)

    def test_missing_page_family_grouping_or_role_is_never_invented(self):
        del self.rows[0xBF]
        with self.assertRaisesRegex(ValueError, 'all32'):
            self.lower()
        self.setUp()
        del self.rows[0xA0]['parent']
        with self.assertRaisesRegex(ValueError, 'every explicit'):
            self.lower()
        self.setUp()
        self.rows[0xA0]['role'] = 4
        with self.assertRaisesRegex(ValueError, 'role'):
            self.lower()

    def test_non_small_areas_require_consistent_explicit_children(self):
        for child in (0xA0, 0xA1, 0xA8, 0xA9):
            self.rows[child].update(parent=0xA0, area_size=1)
        result = self.lower()
        self.assertEqual(result[7][0xA9], 0xA0)
        self.rows[0xA9]['parent'] = 0xA9
        with self.assertRaisesRegex(ValueError, 'footprint'):
            self.lower()
        self.setUp()
        self.rows[0xBF].update(parent=0xBF, area_size=2)
        with self.assertRaisesRegex(ValueError, 'footprint'):
            self.lower()

    def test_already_imported_rom_is_not_relowered(self):
        source = bytearray(self.source)
        source[N.DIRECTORY_PC:N.DIRECTORY_PC + 8] = N.MAGIC
        with self.assertRaisesRegex(ValueError, 'must not be regenerated'):
            self.lower(bytes(source))

    def test_storage_bounds_and_strict_numeric_inputs(self):
        for bad in (0x7E8000, 0x7F8000, 0x460000, True):
            with self.assertRaises(ValueError):
                N.current_table_layout(bad)
        with self.assertRaisesRegex(ValueError, 'cross'):
            N.current_table_layout(0x46D000)
        self.rows[0xA0]['map32_high'] = 0x7E8000
        with self.assertRaisesRegex(ValueError, 'mapped'):
            self.lower()


class NativeActorsTest(unittest.TestCase):
    def setUp(self):
        self.streams = {(map_id, phase): bytes([phase, map_id, 0x42, 0xFF])
                        for map_id in range(0xA0, 0xC0) for phase in range(3)}

    def pack(self, capacity=0x8000):
        return N.lower_actor_lists(self.streams, data_snes=0x4C8000, capacity=capacity)

    def test_phase_lists_decode_at_pointers_and_deduplicate(self):
        self.streams[(0xBF, 2)] = self.streams[(0xA0, 0)]
        payload, pointers = self.pack()
        self.assertEqual(len(payload), 95 * 4)
        self.assertEqual(pointers[(0xBF, 2)], pointers[(0xA0, 0)])
        for key, raw in self.streams.items():
            start = pointers[key] - 0x8000
            self.assertEqual(payload[start:start + len(raw)], raw)

    def test_missing_stream_capacity_early_terminator_and_incomplete_triple_refused(self):
        del self.streams[(0xBF, 2)]
        with self.assertRaisesRegex(ValueError, 'explicitly'):
            self.pack()
        self.setUp()
        with self.assertRaisesRegex(ValueError, 'exceed'):
            self.pack(2)
        for raw in (b'\xFF\x01\x02\xFF', b'\x01\xFF', bytes(129 * 3) + b'\xFF'):
            self.streams[(0xBF, 2)] = raw
            with self.assertRaisesRegex(ValueError, 'triples'):
                self.pack()

    def test_maximum_list_and_explicit_empty_list_are_valid(self):
        self.streams[(0xA0, 0)] = bytes(128 * 3) + b'\xFF'
        self.streams[(0xBF, 2)] = b'\xFF'
        payload, pointers = self.pack()
        self.assertEqual(payload[pointers[(0xA0, 0)] - 0x8000 + 384], 255)
        self.assertEqual(payload[pointers[(0xBF, 2)] - 0x8000], 255)


class Revision3DirectoryEncodingTest(unittest.TestCase):
    def setUp(self):
        self.image = bytes(0x400000)
        self.entries = [(f.id, f.snes, 192) for f in N.current_table_layout(0x468000)]
        self.entries += [(100, 0x4C8000, 0x8000),
                         (200, 0x0B8000, 0x7E70), (201, 0x0C8000, 0x411F),
                         (202, 0x268000, 0x8000),
                         (300, 0x46C000, 0x2000), (301, 0x46B180, 5),
                         (400, 0x3D8000, 4096), (401, 0x3E8000, 4432),
                         (402, 0x3F8000, 4432), (403, 0x508000, 4432),
                         (404, 0x518000, 4432)]
        self.entries += [(210 + i, (0x48 + i) << 16 | 0x8000, 32768) for i in range(4)]

    def encode(self):
        return N.encode_revision3_directory(self.image, self.entries, tail_actor_bank=0x4C)

    def test_wire_encoding_header_crc_and_every_entry_crc(self):
        directory = self.encode()
        self.assertEqual(len(directory), 1024)
        self.assertEqual(directory[:8], b'OOSOW192')
        self.assertEqual(struct.unpack_from('<6HBBHI', directory, 8),
                         (3, 32, 896, 192, 192, 54, 0x4C, 0x0C, 384, len(self.image)))
        checked = bytearray(directory)
        crc, = struct.unpack_from('<I', checked, 28)
        checked[28:32] = bytes(4)
        self.assertEqual(crc, zlib.crc32(checked))
        self.assertEqual(directory[896:], bytes(128))
        for index, (entry_id, address, count) in enumerate(sorted(self.entries)):
            kind, _, stride = N.entry_spec(entry_id, 192)
            self.assertEqual(struct.unpack_from('<HHIHHI', directory, 32 + index * 16),
                             (entry_id, kind, address, count, stride,
                              zlib.crc32(self.image[N.pc(address):N.pc(address) + count * stride])))
        self.entries.reverse()
        self.assertEqual(self.encode(), directory)

    def test_overlap_wrong_source_pool_missing_record_and_truncation_refused(self):
        for change, message in (
                (lambda: self.entries.__setitem__(0, (1, 0x28F000, 192)), 'overlap'),
                (lambda: self.entries.__setitem__(40, (200, 0x0A8000, 0x7E70)), 'pool moved'),
                (lambda: self.entries.pop(), 'exactly54'),
                (lambda: setattr(self, 'image', bytes(0x200000)), 'candidate image')):
            self.setUp()
            change()
            with self.assertRaisesRegex(ValueError, message):
                self.encode()

    def installed_image(self):
        image = bytearray(self.image)
        image[0x140145] = 3
        directory = N.encode_revision3_directory(bytes(image), self.entries, tail_actor_bank=0x4C)
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = directory
        return bytes(image)

    def test_read_and_constants_never_emit_authored_payload(self):
        image = self.installed_image()
        capacity, bank, records = N.read_revision3_directory(image)
        self.assertEqual((capacity, bank, len(records)), (192, 0x4C, 54))
        text = N.reader_constants(image)
        self.assertIn('!LYRA_CURRENT_TABLE_area_size = $46A940', text)
        self.assertIn('!LYRA_CURRENT_ACTOR_BANK = $4C', text)
        self.assertIn('!LYRA_CURRENT_CODE_BASE = $46C000', text)
        self.assertFalse(any(line.startswith(('org ', 'db ', 'incbin ')) for line in text.splitlines()))
        self.assertEqual(N.reader_constants(bytes(0x220000)),
                         '; Ordinary160-map source path.\n!SPECIAL_OVERWORLD_NATIVE = 0\n')

    def test_corrupt_crc_magic_header_and_data_never_fall_back_to_legacy(self):
        baseline = self.installed_image()
        for offset in (N.DIRECTORY_PC, N.DIRECTORY_PC + 28, N.DIRECTORY_PC + 12, 0x230000):
            image = bytearray(baseline)
            image[offset] ^= 1
            with self.assertRaises(ValueError):
                N.reader_constants(bytes(image))

    def test_non_numeric_directory_order_is_accepted(self):
        image = bytearray(self.installed_image())
        directory = bytearray(image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE])
        directory[32:896] = b''.join(reversed([directory[i:i + 16] for i in range(32, 896, 16)]))
        directory[28:32] = bytes(4)
        struct.pack_into('<I', directory, 28, zlib.crc32(directory))
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = directory
        self.assertEqual(N.reader_constants(bytes(image)), N.reader_constants(self.installed_image()))

    def test_build_rejects_payload_mirror_or_call_changes(self):
        # Build-verification fixture supplies five actual four-byte call bindings.
        # Helper bodies are synthetic here: no engine or terrain proof is claimed.
        image = bytearray(self.image)
        image[0x140145] = 3
        sites = (0x02F59D, 0x02F5C8, 0x02F7E3, 0x02F80E, 0x09C4F0)
        for index, site in enumerate(sites):
            target = 0x46C000 + index * 4
            instruction = bytes([0x22 if index < 4 else 0x5C]) + target.to_bytes(3, 'little')
            image[N.pc(site):N.pc(site) + 4] = instruction
            struct.pack_into('<IIHBB', image, N.pc(0x46B180) + index * 16,
                             site, target, (20 + index % 2) if index < 4 else 16,
                             (1 if index < 2 else 2) if index < 4 else 4, 0)
            image[N.pc(0x46B180) + index * 16 + 12:N.pc(0x46B180) + index * 16 + 16] = instruction
        directory = N.encode_revision3_directory(bytes(image), self.entries, tail_actor_bank=0x4C)
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = directory
        baseline = bytes(image)
        N.verify_saved_payload(baseline, baseline)
        unrelated = bytearray(baseline)
        unrelated[0x2B000] ^= 1
        N.verify_saved_payload(baseline, bytes(unrelated))
        for offset, message in ((0x240000, 'payload'), (N.DIRECTORY_PC + 40, 'directory'),
                                (0x1794D, 'mirrors'), (N.pc(sites[0]), 'reader call')):
            edited = bytearray(baseline)
            edited[offset] ^= 1
            with self.assertRaisesRegex(ValueError, message):
                N.verify_saved_payload(baseline, bytes(edited))

    def test_cli_failure_keeps_rom_and_existing_generated_constants(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            rom = Path(temp) / 'saved.sfc'
            output = Path(temp) / 'constants.asm'
            image = bytearray(self.installed_image())
            image[0x230000] ^= 1
            rom.write_bytes(image)
            output.write_text('previous constants')
            result = subprocess.run([sys.executable, str(SOURCE), '--rom', str(rom),
                                     '--constants', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('CRC', result.stderr)
            self.assertEqual(rom.read_bytes(), bytes(image))
            self.assertEqual(output.read_text(), 'previous constants')

    def test_normal_build_refuses_unrequested_native_installation(self):
        with self.assertRaisesRegex(ValueError, 'unrequested'):
            N.verify_saved_payload(bytes(0x400000), self.installed_image())

    def test_old_revisions_and_native160_do_not_select_unimplemented_readers(self):
        for revision in (1, 2):
            image = bytearray(self.installed_image())
            struct.pack_into('<H', image, N.DIRECTORY_PC + 8, revision)
            with self.assertRaisesRegex(ValueError, 'revision3'):
                N.reader_constants(bytes(image))
        image = bytearray(self.image)
        image[0x140145] = 3
        entries = [(entry_id, address, 160 if entry_id <= 39 else count)
                   for entry_id, address, count in self.entries]
        directory = N.encode_revision3_directory(bytes(image), entries,
                                                tail_actor_bank=0x4C, capacity=160)
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = directory
        self.assertEqual(N.read_revision3_directory(bytes(image))[0], 160)
        with self.assertRaisesRegex(ValueError, '192 materialized'):
            N.reader_constants(bytes(image))


if __name__ == '__main__':
    unittest.main()
