"""Initial native data lowering; fixtures do not qualify a production ROM."""
import importlib.util
import hashlib
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
        with self.assertRaisesRegex(ValueError, 'revision3'):
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
        image = bytearray(0x400000)
        # Synthetic instruction fixtures, not a runnable game. The independent
        # canonical-ROM census covers actual installed source operands.
        for entry_id, address, offset in (
                tuple((400, address, offset) for address, offset in N.TILE16_LONG_READERS)
                + N.TILE32_LONG_READERS):
            at = N.pc(address)
            image[at - 1] = 0xBF
            image[at:at + 3] = (N.CURRENT_DICTIONARIES[entry_id] + offset).to_bytes(3, 'little')
        for address in N.TILE16_BANK_READERS:
            at = N.pc(address)
            image[at - 1:at + 1] = bytes([0xA9, 0x3D])
        for address, offset in N.TILE16_WORD_READERS:
            at = N.pc(address)
            image[at - 1] = 0xB9
            image[at:at + 2] = (0x8000 + offset).to_bytes(2, 'little')
        self.image = bytes(image)
        self.entries = [(f.id, f.snes, 192) for f in N.current_table_layout(0x468000)]
        self.entries += [(100, 0x4C8000, 0x8000),
                         (200, 0x0B8000, 0x7E70), (201, 0x0C8000, 0x411F),
                         (202, 0x268000, 0x8000),
                         (300, 0x46C000, 0x2000), (301, 0x46B180, 5),
                         (400, 0x3D8000, 4096), (401, 0x038000, 4432),
                         (402, 0x048000, 4432), (403, 0x3E8000, 4432),
                         (404, 0x3F8000, 4432)]
        self.entries += [(210 + i, (0x48 + i) << 16 | 0x8000, 32768) for i in range(4)]

    def encode(self):
        return N.encode_revision3_directory(self.image, self.entries, tail_actor_bank=0x4C)

    def test_wire_encoding_header_crc_and_every_entry_crc(self):
        directory = self.encode()
        # Golden bytes generated by the unchanged 3b78774c producer.
        self.assertEqual(hashlib.sha256(directory).hexdigest(),
                         'd6e950f1495f991b33e2b78c68e7477bb955e40d37d947e3b30dc70d7cd5048b')
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
        self.assertIn('!LYRA_CURRENT_MAP16_DEFINITIONS = $3D8000', text)
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
        # Record order is not a table ABI, but its raw directory CRC changes.
        def table_constants(data):
            return [line for line in N.reader_constants(data).splitlines()
                    if not line.startswith('!SPECIAL_OVERWORLD_DIRECTORY_CRC')]
        self.assertEqual(table_constants(bytes(image)), table_constants(self.installed_image()))
        self.assertIn(f'!SPECIAL_OVERWORLD_DIRECTORY_CRC = ${zlib.crc32(directory[:28] + bytes(4) + directory[32:]):08X}',
                      N.reader_constants(bytes(image)))

    def test_reader_source_refuses_other_code_reservations(self):
        self.entries = [(entry_id, 0x528000 if entry_id == 300 else address, count)
                        for entry_id, address, count in self.entries]
        with self.assertRaisesRegex(ValueError, 'selected ROM reservations'):
            N.reader_constants(self.installed_image())

    def test_reader_source_refuses_dictionary_relocation_or_operand_mismatch(self):
        baseline = self.installed_image()
        sites = [(N.pc(address), 3) for address, _ in N.TILE16_LONG_READERS]
        sites += [(N.pc(address), 3) for _, address, _ in N.TILE32_LONG_READERS]
        sites += [(N.pc(address), 1) for address in N.TILE16_BANK_READERS]
        sites += [(N.pc(address), 2) for address, _ in N.TILE16_WORD_READERS]
        self.assertEqual(len(sites), 56)
        for at, width in sites:
            for changed in (at - 1, at + width - 1):
                with self.subTest(operand_pc=at, changed_pc=changed):
                    image = bytearray(baseline)
                    image[changed] ^= 1
                    with self.assertRaises(ValueError):
                        N.reader_constants(bytes(image))
        self.entries = [(entry_id, 0x508000 if entry_id == 401 else address, count)
                        for entry_id, address, count in self.entries]
        with self.assertRaisesRegex(ValueError, 'dictionary ID401'):
            N.reader_constants(self.installed_image())

    def test_dictionary_readers_accept_mapped_fast_rom_aliases(self):
        image = bytearray(self.installed_image())
        for _, address, _ in (
                tuple((400, address, offset) for address, offset in N.TILE16_LONG_READERS)
                + N.TILE32_LONG_READERS):
            image[N.pc(address) + 2] |= 0x80
        for address in N.TILE16_BANK_READERS:
            image[N.pc(address)] |= 0x80
        self.assertIn('!SPECIAL_OVERWORLD_NATIVE = 1', N.reader_constants(bytes(image)))

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
        for address in (0x02F6AC, 0x008865, 0x02FD28, 0x02FE1C):
            edited = bytearray(baseline)
            edited[N.pc(address)] ^= 1
            with self.assertRaises(ValueError):
                N.verify_saved_payload(baseline, bytes(edited))
        for offset, message in ((0x240000, 'payload'), (N.DIRECTORY_PC + 40, 'directory'),
                                (0x1794D, 'mirrors'), (N.pc(sites[0]), 'reader call')):
            edited = bytearray(baseline)
            edited[offset] ^= 1
            with self.assertRaisesRegex(ValueError, message):
                N.verify_saved_payload(baseline, bytes(edited))
        # Relocated property CRCs remain valid if assembly changes only the
        # original slots. Native readers would nevertheless see the overwrite.
        for name, address, rows, _, stride in N.CURRENT_TABLE_SPECS:
            if name in ('map32_high', 'map32_low'):
                continue
            with self.subTest(native_family=name):
                edited = bytearray(baseline)
                edited[N.pc(address) + rows * stride - 1] ^= 1
                with self.assertRaisesRegex(ValueError, 'saved native prefix'):
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

    def test_initial_import_and_cli_refuse_existing_or_aliased_rom_data(self):
        import os
        import subprocess
        import tempfile
        image = self.installed_image()
        with self.assertRaisesRegex(ValueError, 'must not be regenerated'):
            N.lower_tables(image, {}, table_base=0x468000, legacy_roles=[255] * 160)
        broken = bytearray(image)
        broken[N.DIRECTORY_PC] ^= 1
        with self.assertRaises(ValueError):
            N.lower_tables(bytes(broken), {}, table_base=0x468000, legacy_roles=[255] * 160)
        with tempfile.TemporaryDirectory() as temp:
            rom = Path(temp) / 'saved.sfc'
            output = Path(temp) / 'constants.asm'
            rom.write_bytes(image)
            os.link(rom, output)
            result = subprocess.run([sys.executable, str(SOURCE), '--rom', str(rom),
                                     '--constants', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('must not overwrite', result.stderr)
            self.assertEqual(rom.read_bytes(), image)

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


class Revision4AppearanceDirectoryTest(unittest.TestCase):
    def setUp(self):
        fixture = Revision3DirectoryEncodingTest()
        fixture.setUp()
        self.image = bytearray(fixture.image)
        self.image[0x140145] = 3
        # Synthetic storage only: these addresses grant no production allocation.
        self.entries = fixture.entries + list(N.initial_appearance_entries(192))
        self.flags_pc = N.pc(N.APPEARANCE_FLAGS_BASE)
        self.colors_pc = N.pc(N.APPEARANCE_PALETTES_BASE)
        for page in range(0xA0, 0xC0):
            self.image[self.flags_pc + page] = 1
        for page, color in ((0xB0, 0x1234), (0xB8, 0x1234),
                            (0xB1, 0x4321), (0xB9, 0x4321)):
            self.image[self.flags_pc + page] = 3
            struct.pack_into('<H', self.image, self.colors_pc + (page - 0x80) * 256, color)

    def encode(self, capacity=192):
        entries = [(entry_id, address, capacity if entry_id <= 39 or entry_id == 410 else rows)
                   for entry_id, address, rows in self.entries]
        return N.encode_revision4_directory(bytes(self.image), entries,
                                            tail_actor_bank=0x4C, capacity=capacity)

    def installed(self):
        image = bytearray(self.image)
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = self.encode()
        return bytes(image)

    def test_explicit_revision4_shape_and_dormant_page_palette_round_trip(self):
        self.image[self.flags_pc + 0xB1] = 1  # Keep raw colors when override clears.
        image = self.installed()
        raw = image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE]
        self.assertEqual(struct.unpack_from('<6HBBH', raw, 8),
                         (4, 32, 928, 192, 192, 56, 0x4C, 0x1C, 384))
        self.assertEqual(raw[928:], bytes(96))
        capacity, bank, records = N.read_native_directory(image)
        self.assertEqual((capacity, bank, len(records)), (192, 0x4C, 56))
        for page, color in ((0xB0, 0x1234), (0xB8, 0x1234),
                            (0xB1, 0x4321), (0xB9, 0x4321)):
            self.assertEqual(struct.unpack_from('<H', image,
                self.colors_pc + (page - 0x80) * 256)[0], color)
        with self.assertRaisesRegex(ValueError, 'requires the installed revision3'):
            N.read_revision3_directory(image)

    def test_authoring_storage_cannot_publish_as_legacy_runnable_output(self):
        image = self.installed()
        for action in (lambda: N.reader_constants(image),
                       lambda: N.verify_saved_payload(image, image)):
            with self.assertRaisesRegex(ValueError, 'requires resident resource compilation'):
                action()

    def test_invalid_flags_colors_overlap_and_missing_records_are_rejected(self):
        for offset, value, message in ((self.flags_pc + 0xB0, 2, 'appearance flags'),
                                       (self.flags_pc + 0xB0, 4, 'appearance flags'),
                                       (self.flags_pc + 0x7F, 1, 'appearance flags'),
                                       (self.colors_pc + 1, 0x80, 'BGR555')):
            with self.subTest(offset=offset, value=value):
                before = self.image[offset]
                self.image[offset] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.encode()
                self.image[offset] = before
        self.entries[-1] = (411, N.APPEARANCE_FLAGS_BASE, 64)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.encode()
        self.setUp()
        self.entries.pop()
        with self.assertRaisesRegex(ValueError, 'exactly56'):
            self.encode()

    def test_invalid_directory_and_palette_crc_never_fall_back(self):
        baseline = self.installed()
        for offset in (N.DIRECTORY_PC, N.DIRECTORY_PC + 8,
                       N.DIRECTORY_PC + 21, self.colors_pc):
            image = bytearray(baseline)
            image[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                N.read_native_directory(bytes(image))

    def test_160_source_has_no_tail_flags_but_retains_dormant_storage(self):
        self.image[self.flags_pc + 160:self.flags_pc + 192] = bytes(32)
        directory = self.encode(capacity=160)
        image = bytearray(self.image)
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = directory
        capacity, _, records = N.read_native_directory(bytes(image))
        self.assertEqual(capacity, 160)
        self.assertEqual(records[410][1], 160)
        self.assertEqual(records[411][1], 64)
        with self.assertRaisesRegex(ValueError, 'requires resident resource compilation'):
            N.reader_constants(bytes(image))


if __name__ == '__main__':
    unittest.main()
