"""Offline preparation controls; no ROM publication, assembly or emulator."""
import copy
import hashlib
import importlib.util
import json
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

    def test_spill_refuses_a_changed_editable_source_preimage(self):
        image = bytearray(self.source)
        image[N.RESIDENT_SPILL_PC] = 1
        self.source = bytes(image)
        self.preimage = self.source[self.origin:self.origin+self.capacity]
        with self.assertRaisesRegex(ValueError, 'SPILL_PREIMAGE_CHANGED'):
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

    def compiled_fixture(self, *, experimental_page_tile16=False):
        """Synthetic assembly transaction; not an engine execution fixture."""
        image = bytearray(self.source)
        _, _, entries = N.read_native_directory(self.source,
            experimental_page_tile16=experimental_page_tile16)
        at, size = entries[300]
        symbols = dict(Lyra_CurrentNativeCodeStart=at,
                       Lyra_CurrentNativeCodeEnd=at + size)
        for start, end, lower, _ in B.RUNTIME_CODE_EXTENTS:
            symbols[start], symbols[end] = lower, lower + 0x100
            image[N.pc(lower):N.pc(lower) + 0x100] = b'\x6B' * 0x100
        for index, (site, name, size) in enumerate(B.RESIDENT_READER_HOOKS):
            symbols.setdefault(name, N.RESIDENT_WORD_CODE_BASE + index * 4)
            target = symbols[name]
            raw = b'\x22' + target.to_bytes(3, 'little') + b'\xEA' * (size - 4)
            first = N.pc(site)
            image[first:first + size] = raw
        prepared = (B.prepare_native_compilation(self.source, self.exported,
            data_pc=self.origin, capacity=self.capacity, preimage=self.preimage,
            experimental_page_tile16=True) if experimental_page_tile16 else self.prepare())
        for write in prepared['resource_writes']:
            first = write['pc']
            image[first:first + len(write['after'])] = write['after']
        # Exact existing Overworld/overworld.asm intro ambience policy.
        for map_id in (0x13, 0x14, 0x1B, 0x1C, 0x23, 0x24, 0x2B, 0x2C):
            first = N.pc(0x02C303 + map_id)
            image[first] = (self.source[first] & 0x0F) | 0x50
        return bytes(image), symbols

    def test_intro_ambience_compiler_exception_is_exact_and_reported(self):
        source = bytearray(self.source)
        for index, map_id in enumerate((0x13, 0x14, 0x1B, 0x1C, 0x23, 0x24, 0x2B, 0x2C)):
            source[N.pc(0x02C303 + map_id)] = 0x10 | (index + 1)
        self.source = bytes(source)
        self.exported = self.fixture.make_export(self.source)
        compiled, symbols = self.compiled_fixture()
        result = B.verify_revision4_compiled_output(self.source, self.exported, compiled, symbols)
        transforms = result['compiler_owned_prefix_transforms']
        self.assertEqual([row['map_id'] for row in transforms],
                         [0x13, 0x14, 0x1B, 0x1C, 0x23, 0x24, 0x2B, 0x2C])
        self.assertFalse(result['native_prefixes_preserved'])
        self.assertTrue(result['native_prefixes_preserved_except_compiler_owned_fields'])
        for row in transforms:
            self.assertEqual(row['snes'], 0x02C303 + row['map_id'])
            self.assertEqual(row['before'], self.source[row['pc']])
            self.assertEqual(row['after'], (row['before'] & 0x0F) | 0x50)
        first = N.pc(0x02C316)
        # A changed low music nibble, omitted policy, wrong high nibble or an
        # extra nearby silence mask must all refuse, even during first sealing.
        for at, value in ((first, compiled[first] ^ 1),
                          (first, self.source[first]),
                          (first, (compiled[first] & 0x0F) | 0x60),
                          (N.pc(0x02C315), (self.source[N.pc(0x02C315)] & 0x0F) | 0x50)):
            with self.subTest(at=at, value=value):
                image = bytearray(compiled)
                image[at] = value
                with self.assertRaisesRegex(ValueError, 'NATIVE_PREFIX_CHANGED:music_phase0'):
                    B.plan_revision4_compiled_seal(self.source, self.exported, bytes(image), symbols,
                                                  allow_stale_directory=True)

    def test_compiled_seal_requires_explicit_first_pass_and_exact_final_descriptor(self):
        compiled, symbols = self.compiled_fixture()
        clean = B.verify_revision4_compiled_output(self.source, self.exported, compiled, symbols)
        self.assertFalse(clean['needed_reassembly'])
        self.assertEqual(clean['resident_reader_hook_count'], 20)
        image = bytearray(compiled)
        image[N.pc(N.CODE_BASE)] ^= 1
        compiled = bytes(image)
        before = bytes(compiled)
        with self.assertRaisesRegex(ValueError, 'DIRECTORY_SEAL_MISMATCH'):
            B.verify_revision4_compiled_output(self.source, self.exported, compiled, symbols)
        seal = B.plan_revision4_compiled_seal(self.source, self.exported, compiled, symbols,
                                            allow_stale_directory=True)
        self.assertTrue(seal['needed_reassembly'])
        self.assertTrue(seal['first_pass_stale_directory_accepted'])
        self.assertNotEqual(seal['reader_code']['before_sha256'], seal['reader_code']['after_sha256'])
        self.assertEqual(compiled, before)
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = seal['directory_bytes']
        final = B.verify_revision4_compiled_output(self.source, self.exported, bytes(image), symbols)
        self.assertFalse(final['needed_reassembly'])
        self.assertFalse(final['runtime_admission'])
        image[N.DIRECTORY_PC + 1000] ^= 1
        with self.assertRaisesRegex(ValueError, 'DIRECTORY_SEAL_MISMATCH'):
            B.plan_revision4_compiled_seal(self.source, self.exported, bytes(image), symbols,
                                          allow_stale_directory=True)

    def test_compilation_refuses_saved_payload_binding_prefix_and_mirror_changes(self):
        compiled, symbols = self.compiled_fixture()
        _, _, entries = N.read_native_directory(self.source)
        for at, error in ((N.pc(entries[400][0]), 'SAVED_PAYLOAD_CHANGED:ID400'),
                          (N.pc(entries[301][0]), 'SAVED_PAYLOAD_CHANGED:ID301'),
                          (N.pc(0x02F59D), 'READER_CALL_CHANGED'),
                          (N.pc(0x288000), 'NATIVE_PREFIX_CHANGED:bg_color'),
                          (0x1794D, 'POINTER_MIRROR_CHANGED')):
            with self.subTest(at=at):
                image = bytearray(compiled)
                image[at] ^= 1
                with self.assertRaisesRegex(ValueError, error):
                    B.verify_revision4_compiled_output(self.source, self.exported, bytes(image), symbols)

    def test_compilation_refuses_reader_padding_target_remaining_operand_and_bad_extents(self):
        compiled, symbols = self.compiled_fixture()
        for at, error in ((N.pc(0x02FE1B) + 4, 'READER_HOOK_MISMATCH'),
                          (N.pc(0x02F456) + 1, 'READER_HOOK_MISMATCH'),
                          (N.pc(N.TILE16_BANK_READERS[0]), 'bank reader disagrees')):
            with self.subTest(at=at):
                image = bytearray(compiled)
                image[at] ^= 1
                with self.assertRaisesRegex(ValueError, error):
                    B.verify_revision4_compiled_output(self.source, self.exported, bytes(image), symbols)
        for name, value, error in (
                ('Lyra_CurrentNativeCodeEnd', symbols['Lyra_CurrentNativeCodeEnd'] + 1, 'READER_EXTENT_MISMATCH'),
                ('Lyra_ResidentAtlasCodeEnd', N.RESIDENT_WORD_CODE_LIMIT + 1, 'RUNTIME_EXTENT_MISMATCH'),
                ('Lyra_ResidentFull0', N.RESIDENT_WORD_CODE_LIMIT, 'TARGET_OUTSIDE_KERNEL')):
            with self.subTest(symbol=name):
                changed = dict(symbols, **{name: value})
                with self.assertRaisesRegex(ValueError, error):
                    B.verify_revision4_compiled_output(self.source, self.exported, compiled, changed)
        missing = dict(symbols)
        del missing['SpecialPaletteAdaptersEnd']
        with self.assertRaisesRegex(ValueError, 'REQUIRED_SYMBOL_MISSING'):
            B.verify_revision4_compiled_output(self.source, self.exported, compiled, missing)

    def test_compilation_checks_resource_payloads_and_every_unclaimed_resource_byte(self):
        compiled, symbols = self.compiled_fixture()
        writes = self.prepare()['resource_writes']
        claimed = {at for row in writes for at in range(row['pc'], row['pc'] + len(row['after']))}
        gap = next(at for at in range(self.origin, self.origin + self.capacity) if at not in claimed)
        for at, error in ((writes[0]['pc'], 'COMPILED_RESOURCE_CHANGED'),
                          (gap, 'RESOURCE_GAP_CHANGED')):
            with self.subTest(at=at):
                image = bytearray(compiled)
                image[at] ^= 1
                with self.assertRaisesRegex(ValueError, error):
                    B.verify_revision4_compiled_output(self.source, self.exported, bytes(image), symbols)

    def test_d4_hole_is_not_atlas_owned_but_spill_gaps_remain_protected(self):
        compiled, symbols = self.compiled_fixture()
        prepared = self.prepare()
        hole_first, hole_end = N.RESIDENT_DATA_EXCLUDED_PC[0]
        for row in prepared['emission']['placements']:
            self.assertTrue(row['pc'][1] <= hole_first or row['pc'][0] >= hole_end)
        image = bytearray(compiled)
        image[hole_first] ^= 1  # D4 has its own source/compile validation.
        B.verify_revision4_compiled_output(self.source, self.exported, bytes(image), symbols)
        image[hole_end] ^= 1
        with self.assertRaisesRegex(ValueError, 'RESOURCE_GAP_CHANGED'):
            B.verify_revision4_compiled_output(self.source, self.exported, bytes(image), symbols)



class ExperimentalNativeBuildTest(unittest.TestCase):
    def setUp(self):
        self.legacy = NativeBuildPreparationTest()
        self.legacy.setUp()
        self.fixture = F.ExperimentalPageTile16ResourcesTest()
        self.fixture.setUp()
        self.fixture.fixture.source = self.legacy.source
        self.fixture.fixture.exported = self.legacy.exported
        self.source, self.exported = self.fixture.install(self.fixture.rows, authoring=True)

    def prepare(self, **kwargs):
        args = dict(data_pc=N.RESIDENT_DATA_PC, capacity=N.RESIDENT_DATA_CAPACITY,
            preimage=self.source[N.RESIDENT_DATA_PC:
                N.RESIDENT_DATA_PC + N.RESIDENT_DATA_CAPACITY],
            experimental_page_tile16=True)
        args.update(kwargs)
        return B.prepare_native_compilation(self.source, self.exported, **args)

    def test_default_and_revision4_alias_refuse_experimental_without_activation(self):
        args = dict(data_pc=N.RESIDENT_DATA_PC, capacity=N.RESIDENT_DATA_CAPACITY,
                    preimage=self.source[N.RESIDENT_DATA_PC:
                        N.RESIDENT_DATA_PC + N.RESIDENT_DATA_CAPACITY])
        for function in (B.prepare_revision4_compilation, B.prepare_native_compilation):
            with self.subTest(function=function.__name__), self.assertRaisesRegex(
                    ValueError, 'Ordinary Build requires'):
                function(self.source, self.exported, **args)
        with self.assertRaisesRegex(ValueError, 'Ordinary Build requires'):
            N.reader_constants(self.source)
        with self.assertRaisesRegex(ValueError, 'EXPERIMENTAL_ADMISSION_INVALID'):
            self.prepare(experimental_page_tile16=1)

    def test_authenticated413_binding_and_visual_abi_retain_provenance_and_refusals(self):
        result = self.prepare()
        binding = result['semantic_source_contract']
        count, bank, entries = N.read_native_directory(self.source,
            experimental_page_tile16=True)
        address, rows = entries[413]
        raw = self.source[N.pc(address):N.pc(address) + rows * 12]
        self.assertEqual((binding['revision'], binding['capacity'], binding['table_id'],
                          binding['kind'], binding['rows_snes'], binding['count'], binding['stride']),
                         (5, 192, 413, 10, address, rows, 12))
        self.assertEqual(binding['payload_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(binding['payload_crc32'], zlib.crc32(raw))
        self.assertEqual(binding['populated_rows'], 2)
        self.assertEqual(binding['consumer_bindings']['SPECIAL_OVERWORLD_SEMANTIC_ROWS'], address)
        self.assertIsNone(binding['consumer_bindings']['SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE'])
        self.assertIsNone(binding['consumer_bindings']['SPECIAL_OVERWORLD_SEMANTIC_CODE_END'])
        self.assertEqual(result['resource_plan']['schema'], F.R.EXPERIMENTAL_PLAN_SCHEMA)
        self.assertEqual(result['resident_abi']['experimental_source']['page_tile16_definitions_sha256'],
                         binding['payload_sha256'])
        for key in ('runtime_admission', 'publication_authorized', 'ordinary_build_ready',
                    'allocation_granted', 'full_residency_ready'):
            self.assertFalse(result[key])
        self.assertNotIn('SEMANTIC_ENABLED = 1', result['constants_asm'])
        self.assertEqual(result, self.prepare())

    def test_declared413_capacity_is_reported_without_new_allocation(self):
        self.source, self.exported = self.fixture.install(
            self.fixture.rows, count=2730, authoring=True)
        result = self.prepare()
        binding = result['semantic_source_contract']
        self.assertEqual((binding['count'], binding['populated_rows'], binding['stride']),
                         (2730, 2, 12))
        self.assertFalse(binding['allocation_granted'])
        self.assertIsNone(binding['consumer_bindings']['SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE'])

    def test_explicit_code_reseal_preserves413_412_and_every_saved_payload(self):
        capacity, bank, entries = N.read_native_directory(self.source,
            experimental_page_tile16=True)
        at, size = entries[300]
        before = self.source[N.pc(at):N.pc(at) + size]
        changed = bytes([before[0] ^ 1]) + before[1:]
        result = self.prepare(reader_code_replacement=B.ReaderCodeReplacement(
            hashlib.sha256(before).hexdigest(), changed))
        image = bytearray(self.source)
        for row in result['source_reseal_writes']:
            image[row['pc']:row['pc'] + len(row['after'])] = row['after']
        self.assertEqual(N.read_native_directory(bytes(image), experimental_page_tile16=True),
                         (capacity, bank, entries))
        for key, (address, rows) in entries.items():
            if key == 300:
                continue
            first, length = N.pc(address), rows * N.entry_spec(key, capacity, 5)[2]
            self.assertEqual(image[first:first + length], self.source[first:first + length], key)
        self.assertTrue(result['reexport_required_after_reseal'])
        # The original export cannot be relabelled/rehashed to admit the changed source.
        self.source = bytes(image)
        with self.assertRaisesRegex(ValueError, 'EXPORT_SOURCE_MISMATCH'):
            self.prepare()

    def test_rehashed_tampered413_metadata_rows_and_wrong_export_schema_refuse(self):
        original = copy.deepcopy(self.exported)
        for field, value in (('count', 3), ('stride', 8), ('sha256', '0' * 64)):
            exported = copy.deepcopy(original['native_source'])
            exported['page_tile16_definitions'][field] = value
            self.exported = self.fixture.fixture.seal(exported)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'PAGE_TILE16_SOURCE_MISMATCH'):
                self.prepare()
        exported = copy.deepcopy(original['native_source'])
        exported['page_tile16_definitions']['rows'][0]['words'][0] ^= 1
        self.exported = self.fixture.fixture.seal(exported)
        with self.assertRaisesRegex(ValueError, 'PAGE_TILE16_SOURCE_MISMATCH'):
            self.prepare()
        exported = copy.deepcopy(original['native_source'])
        exported['schema'] = F.R.SOURCE_SCHEMA
        self.exported = self.fixture.fixture.seal(exported)
        with self.assertRaisesRegex(ValueError, 'EXPORT_SOURCE_MISMATCH'):
            self.prepare()

    def test_compiled_sealer_is_revision_aware_and_preserves_required413(self):
        self.legacy.source, self.legacy.exported = self.source, self.exported
        compiled, symbols = self.legacy.compiled_fixture(experimental_page_tile16=True)
        _, _, entries = N.read_native_directory(self.source, experimental_page_tile16=True)
        image = bytearray(compiled)
        image[N.pc(entries[300][0])] ^= 1
        compiled = bytes(image)
        with self.assertRaisesRegex(ValueError, 'DIRECTORY_SEAL_MISMATCH'):
            B.verify_native_compiled_output(self.source, self.exported, compiled, symbols,
                                           experimental_page_tile16=True)
        first = B.plan_native_compiled_seal(self.source, self.exported, compiled, symbols,
            allow_stale_directory=True, experimental_page_tile16=True)
        image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = first['directory_bytes']
        final = B.verify_native_compiled_output(self.source, self.exported, bytes(image), symbols,
                                                experimental_page_tile16=True)
        self.assertFalse(final['needed_reassembly'])
        self.assertFalse(final['runtime_admission'])
        self.assertEqual(final['semantic_source_contract']['table_id'], 413)
        # Even a permitted stale directory never waives any saved payload byte.
        for key in (400, 410, 411, 412, 413):
            bad = bytearray(compiled)
            bad[N.pc(entries[key][0])] ^= 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, f'SAVED_PAYLOAD_CHANGED:ID{key}'):
                B.plan_native_compiled_seal(self.source, self.exported, bytes(bad), symbols,
                    allow_stale_directory=True, experimental_page_tile16=True)
        with self.assertRaisesRegex(ValueError, 'Ordinary Build requires'):
            B.plan_revision4_compiled_seal(self.source, self.exported, compiled, symbols)

    def test_missing413_crc_and_resident_overlap_refuse_without_writes(self):
        original = self.source
        _, _, entries = N.read_native_directory(original, experimental_page_tile16=True)
        image = bytearray(original)
        image[N.pc(entries[413][0]) + 4] ^= 1
        self.source = bytes(image)
        with self.assertRaisesRegex(ValueError, 'CRC'):
            self.prepare()
        image = bytearray(original)
        count = struct.unpack_from('<H', image, N.DIRECTORY_PC + 18)[0]
        record = next(N.DIRECTORY_PC + 32 + index * 16 for index in range(count)
            if struct.unpack_from('<H', image, N.DIRECTORY_PC + 32 + index * 16)[0] == 413)
        struct.pack_into('<H', image, record, 414)
        self.source = bytes(image)
        with self.assertRaises(ValueError):
            self.prepare()
        self.fixture.address = 0x4E8000  # Synthetic occupied resident interval.
        self.source, self.exported = self.fixture.install(self.fixture.rows, authoring=True)
        with self.assertRaisesRegex(ValueError, 'OVERLAPS_SAVED_PAYLOAD'):
            self.prepare()

    def test_legacy_pinned_preparation_and_opt_in_v1_are_byte_identical(self):
        expected = '300084904066624eb22e08de5c19b39ff516f26ef735735b3917e6e318a0a4df'
        old = self.legacy.prepare()
        raw = json.dumps(old, sort_keys=True, separators=(',', ':'),
                         default=lambda value: dict(bytes_hex=value.hex())).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
        result = B.prepare_native_compilation(self.legacy.source, self.legacy.exported,
            data_pc=self.legacy.origin, capacity=self.legacy.capacity,
            preimage=self.legacy.preimage, experimental_page_tile16=True)
        self.assertEqual(old, result)

if __name__ == '__main__':
    unittest.main()
