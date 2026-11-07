"""Current bootstrap transaction controls; no assembler or ROM publication."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import special_overworld_initial_bootstrap as B
import lyra_native_loaders as N

spec = importlib.util.spec_from_file_location('bootstrap_directory_fixture',
    Path(__file__).with_name('test_lyra_native_loaders.py'))
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


class InitialBootstrapTest(unittest.TestCase):
    def setUp(self):
        f = F.Revision4AppearanceDirectoryTest()
        f.setUp()
        self.image = bytearray(f.image)
        self.entries = list(f.entries) + [N.initial_authoring_entry(192)]
        raw = N.authoring_metadata.encode(dict(next_placement_id=1, placements=[]), 192)
        at = N.pc(N.AUTHORING_METADATA_BASE)
        self.image[at:at + len(raw)] = raw
        self.symbols = {'Lyra_CurrentNativeCodeStart': N.CODE_BASE,
            'Lyra_CurrentNativeCodeEnd': N.CODE_BASE + 0x2000,
            'LyraCall_CurrentActors': 0x09C4F0,
            'Lyra_LoadCurrentSprites': N.CODE_BASE + 16}
        rows = []
        for i, (site, name, table, kind, _) in enumerate(B._CALLS):
            target = N.CODE_BASE + i * 4
            self.symbols[name] = target
            call = b'\x22' + target.to_bytes(3, 'little')
            at = N.pc(site)
            self.image[at:at + 12] = call + b'\xEA' * 8
            rows.append(struct.pack('<IIHBB', site, target, table, kind, 0) + call)
        call = b'\x5C' + self.symbols['Lyra_LoadCurrentSprites'].to_bytes(3, 'little')
        at = N.pc(0x09C4F0)
        self.image[at:at + 4] = call
        rows.append(struct.pack('<IIHBB', 0x09C4F0,
            self.symbols['Lyra_LoadCurrentSprites'], 16, 4, 0) + call)
        at = N.pc(N.BINDINGS_BASE)
        self.image[at:at + 80] = b''.join(rows)
        self.seal()
        source = bytearray(self.compiled)
        source[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = bytes(N.DIRECTORY_SIZE)
        for site, _, _, _, pointer in B._CALLS:
            at = N.pc(site)
            source[at:at + 12] = (b'\xBF' + pointer.to_bytes(3, 'little')
                + b'\x85\xC8\xBF' + (pointer + 1).to_bytes(3, 'little') + b'\x85\xC9')
        at = N.pc(0x09C4F0)
        source[at:at + 4] = b'\xBF\x38\x94\x28'
        self.source = bytes(source)
        self.files = {name: b'; synthetic current source\n' for name in B._ENGINE_FILES}
        self.receipt = dict(finish=dict(exit_code=0, stage='complete', required_gaps=[]),
            checks=[dict(name=name, required=True, status='passed', exit_code=0)
                    for name in sorted(B._REQUIRED_CHECKS)], artifacts={},
            snapshots=dict(pre_assembly=dict(files={name: dict(sha256=B._sha(raw))
                         for name, raw in self.files.items()})))
        self.bind()

    def seal(self):
        self.image[N.DIRECTORY_PC:N.DIRECTORY_PC + N.DIRECTORY_SIZE] = N.encode_revision4_directory(
            bytes(self.image), self.entries, tail_actor_bank=0x4C)
        self.image[0x7FD5] = 0x20
        self.image[0x7FDC:0x7FE0] = b'\xFF\xFF\0\0'
        checksum = sum(self.image) & 0xFFFF
        struct.pack_into('<HH', self.image, 0x7FDC, checksum ^ 0xFFFF, checksum)
        self.compiled = bytes(self.image)

    def bind(self):
        self.symbols_raw = ('[labels]\n' + '\n'.join(
            f'{value >> 16:02X}:{value & 65535:04X} {name}'
            for name, value in self.symbols.items()) + '\n').encode()
        self.receipt['artifacts'] = {name: dict(sha256=B._sha(raw), size=len(raw))
            for name, raw in [('symbols', self.symbols_raw), ('output_rom', self.compiled)]}

    def prepare(self):
        return B.prepare_initial_bootstrap(self.source, self.compiled,
            symbols_raw=self.symbols_raw, build_receipt=self.receipt,
            current_source_files=self.files)

    def test_complete_minimal_recipe_is_pure_and_not_runnable(self):
        before = (self.source, self.compiled, copy.deepcopy(self.receipt))
        r = self.prepare()
        self.assertEqual(len(r['patches']), 7)
        self.assertEqual(r['directory301']['count'], 5)
        self.assertEqual(r['directory300']['count'], 0x2000)
        self.assertFalse(r['complete_image'])
        self.assertFalse(r['runtime_qualified'])
        self.assertFalse(r['allocation_granted'])
        for p in r['patches']:
            self.assertEqual(self.source[p['pc']:p['pc'] + len(bytes.fromhex(p['before_hex']))],
                             bytes.fromhex(p['before_hex']))
        self.assertEqual(before, (self.source, self.compiled, self.receipt))

    def test_two_mib_source_keeps_original_identity_and_pads_only_in_memory(self):
        self.source = self.source[:0x200000]
        result = self.prepare()
        self.assertEqual(result['source_rom_sha256'], B._sha(self.source))
        self.assertEqual(result['padded_source_sha256'], B._sha(self.source.ljust(0x400000, b'\0')))
        self.assertEqual(len(self.source), 0x200000)
        self.assertTrue(any(p['reason'] == 'directory300_reader_body'
                            and not any(bytes.fromhex(p['before_hex']))
                            for p in result['patches']))

    def test_stale_current_source_refuses(self):
        self.files['Overworld/time_system.asm'] += b'changed'
        with self.assertRaisesRegex(ValueError, 'STALE_SOURCE_BINDING'):
            self.prepare()

    def test_receipt_cannot_rebind_changed_artifact(self):
        self.compiled = bytes([self.compiled[0] ^ 1]) + self.compiled[1:]
        with self.assertRaisesRegex(ValueError, 'ARTIFACT_HASH_MISMATCH'):
            self.prepare()

    def test_wrong_symbol_extent_refuses_even_with_matching_symbol_hash(self):
        self.symbols['Lyra_CurrentNativeCodeEnd'] += 1
        self.bind()
        with self.assertRaisesRegex(ValueError, 'READER_EXTENT'):
            self.prepare()

    def test_changed_native_terrain_preimage_refuses(self):
        source = bytearray(self.source)
        source[N.pc(0x02F59D) + 4] ^= 1
        self.source = bytes(source)
        with self.assertRaisesRegex(ValueError, 'TERRAIN_PREIMAGE'):
            self.prepare()

    def test_compiled_padding_and_actor_preimage_refuse(self):
        self.image[N.pc(0x02F59D) + 4] = 0
        self.seal()
        self.bind()
        with self.assertRaisesRegex(ValueError, 'COMPILED_CALL'):
            self.prepare()
        self.setUp()
        source = bytearray(self.source)
        source[N.pc(0x09C4F0)] = 0
        self.source = bytes(source)
        with self.assertRaisesRegex(ValueError, 'ACTOR_PREIMAGE'):
            self.prepare()

    def test_incomplete_build_and_unknown_dictionary_refuse(self):
        self.receipt['checks'].pop()
        with self.assertRaisesRegex(ValueError, 'BUILD_NOT_COMPLETE'):
            self.prepare()
        self.setUp()
        source = bytearray(self.source)
        source[N.pc(N.TILE16_LONG_READERS[0][0])] ^= 1
        self.source = bytes(source)
        with self.assertRaisesRegex(ValueError, 'dictionary reader operand'):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
