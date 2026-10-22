"""Exact generated-write ownership; synthetic files only, no build or native run."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import check_zscream_overlap as Z
import lyra_native_loaders as L
import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_publisher as P


class ExactLyraOwnershipTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.folder = self.root / P.OUTPUT
        self.saved_path = self.root / 'saved.bin'
        self.rom = self.root / 'compiled.bin'
        self.symbols = self.root / 'compiled.sym'
        self.receipt = self.root / 'verified.json'
        self.ledger = self.root / 'ledger.json'
        self.ledger.write_bytes(b'current-authorized-ledger')
        saved = bytes(0x400000)
        self.saved_path.write_bytes(saved)
        writes = []
        for kind, pc, payload in (('runtime_table', 0x144000, b'TABLE'),
                                  ('a1_dictionary_group', 0x1F6720, b'PACKED'),
                                  ('a1_stream', 0x3D4206, b'STREAM')):
            writes.append(dict(kind=kind, pc=[pc, pc + len(payload)],
                               preimage_hex=saved[pc:pc + len(payload)].hex(),
                               payload_hex=payload.hex()))
        self.plan = dict(kind='lyra.ordinary_build_prepare.v1', selected=True,
                         project='selected.yaze', base_rom=str(self.saved_path), request='request.json',
                         ledger=str(self.ledger), current_ledger_sha256=R.sha(self.ledger.read_bytes()),
                         saved_rom_sha256=R.sha(saved), writes=writes, emitted_definitions=[],
                         targets=dict(native37='native37-target', a1='isolated-a1-target'),
                         inputs=[dict(path=str(p), sha256=R.sha(p.read_bytes()))
                                 for p in (self.saved_path, self.ledger)])
        compiled = bytearray(saved)
        for row in writes:
            compiled[slice(*row['pc'])] = bytes.fromhex(row['payload_hex'])
        self.rom.write_bytes(compiled)
        self.write_symbols([(0x144000, 'Data/Generated/lyra_project/runtime_data.asm'),
                            (0x1F6720, 'Data/Generated/lyra_project/runtime_data.asm')])
        for name, raw in P.render_outputs(self.plan).items():
            path = self.folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.native = dict(kind=P.PUBLICATION['compiled_reader_variant'], compiled_consumers_verified=True,
                           compiled_rom_sha256=R.sha(compiled), production_admission=False,
                           save_exit_policy='held', runtime_verified=False)
        self.data = dict(native37_verified=True, isolated_a1_verified=True, dictionary_verified=True,
                         legacy_tables_verified=30, native160_planes_sha256='readback-digest')
        self.proof = dict(self.data, kind='lyra.ordinary_build_verification.v1',
                          prepared_sha256=R.sha((self.folder / 'prepare.json').read_bytes()),
                          saved_rom_sha256=R.sha(saved), compiled_rom_sha256=R.sha(compiled),
                          symbols_sha256=R.sha(self.symbols.read_bytes()),
                          current_ledger_sha256=self.plan['current_ledger_sha256'], native_loaders=self.native,
                          production_maps=[], production_edge_ids=[], save_exit_policy='unchanged_held')
        self.write_proof()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(Z, 'REPO_ROOT', self.root).start()
        self.make_plan = mock.patch.object(P, 'make_plan', return_value=self.plan).start()
        self.native_verify = mock.patch.object(L, 'verify_native_loaders', return_value=self.native).start()
        self.data_verify = mock.patch.object(P, 'verify_data', return_value=self.data).start()

    def write_proof(self):
        self.receipt.write_bytes(P.encoded(self.proof))

    def write_symbols(self, rows):
        sources = list(dict.fromkeys(source for _, source in rows))
        lines = ['[labels]', '28:C000 Fixture', '[source files]']
        lines += [f'{index:04X} 00000000 {self.root / source}' for index, source in enumerate(sources)]
        lines += ['[addr-to-line mapping]']
        for number, (pc, source) in enumerate(rows, 1):
            snes = A.snes(pc)
            lines.append(f'{snes >> 16:02X}:{snes & 0xFFFF:04X} {sources.index(source):04X}:{number:04X}')
        self.symbols.write_text('\n'.join(lines) + '\n')

    def regions(self):
        return Z.lyra_owned_regions(self.receipt, self.rom, self.symbols, self.folder)

    def test_reconstructs_current_plan_and_rechecks_actual_consumers_and_data(self):
        self.assertEqual(self.regions(), (
            ('Data/Generated/lyra_project/runtime_data.asm', 0x144000, 0x144004),
            ('Data/Generated/lyra_project/runtime_data.asm', 0x1F6720, 0x1F6725)))
        self.make_plan.assert_called_once_with('selected.yaze', str(self.saved_path), 'request.json',
                                              ledger_path=str(self.ledger))
        self.assertEqual(self.native_verify.call_args.kwargs, {'ledger_path': str(self.ledger)})
        self.assertEqual(self.native_verify.call_args.args[:3],
                         (self.saved_path.read_bytes(), self.rom.read_bytes(), self.symbols.read_bytes()))
        self.assertEqual(self.data_verify.call_args.args[2], self.plan['writes'])
        self.assertEqual(self.data_verify.call_args.args[-2:], ('native37-target', 'isolated-a1-target'))

    def test_only_exact_source_and_write_extents_are_owned(self):
        rows = [(0x144000, 'Data/Generated/lyra_project/runtime_data.asm'),
                (0x144004, 'Data/Generated/lyra_project/runtime_data.asm'),
                (0x144005, 'Data/Generated/lyra_project/runtime_data.asm'),
                (0x1F6725, 'Data/Generated/lyra_project/runtime_data.asm'),
                (0x1F6726, 'Data/Generated/lyra_project/runtime_data.asm'),
                (0x144000, 'Foreign.asm'), (0x1F6720, 'Foreign.asm'),
                (0x3D4206, 'Data/Generated/lyra_project/runtime_data.asm')]
        self.write_symbols(rows)
        self.proof['symbols_sha256'] = R.sha(self.symbols.read_bytes())
        self.write_proof()
        ranges = [dict(start=0x140000, end=0x147FFF, name='tables'),
                  dict(start=0x1F0000, end=0x1FFFFF, name='dictionary'),
                  dict(start=0x3D0000, end=0x3DFFFF, name='not-an-owned-kind')]
        self.assertEqual(len(Z.check_overlaps(self.symbols, ranges)), len(rows))
        actual = Z.check_overlaps(self.symbols, ranges, verified_regions=self.regions())
        self.assertEqual([(r['pc'], r['source'].split(':')[0]) for r in actual],
                         [(f'0x{pc:06X}', source) for pc, source in rows[2:] if pc != 0x1F6725])

    def test_stale_receipt_identity_or_publication_scope_refuses(self):
        original = copy.deepcopy(self.proof)
        for update in ({'kind': 'lyra.unverified_inspection.v1'}, {'prepared_sha256': 'stale'},
                       {'saved_rom_sha256': 'stale'}, {'compiled_rom_sha256': 'stale'},
                       {'symbols_sha256': 'stale'}, {'current_ledger_sha256': 'stale'},
                       {'production_maps': [0xA1]}, {'production_edge_ids': [1]},
                       {'save_exit_policy': 'new'}):
            with self.subTest(update=update):
                self.proof = dict(original, **update)
                self.write_proof()
                with self.assertRaisesRegex(ValueError, 'ownership'):
                    self.regions()

    def test_changed_generated_files_or_inputs_refuse(self):
        for name in P.GENERATED_FILES:
            with self.subTest(name=name):
                path = self.folder / name
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'stale or changed'):
                    self.regions()
                path.write_bytes(original)
        self.ledger.write_bytes(b'foreign-owner')
        with self.assertRaisesRegex(ValueError, 'input changed'):
            self.regions()

    def test_native_inspection_and_actual_strict_verifier_refusal_cannot_authorize(self):
        self.proof['native_loaders'] = dict(self.native, compiled_consumers_verified=False)
        self.write_proof()
        with self.assertRaisesRegex(ValueError, 'Native loader receipt'):
            self.regions()
        self.native_verify.assert_not_called()
        self.proof['native_loaders'] = self.native
        self.write_proof()
        self.native_verify.side_effect = ValueError('Reviewed active consumer differs')
        with self.assertRaisesRegex(ValueError, 'Reviewed active consumer'):
            self.regions()
        self.data_verify.assert_not_called()

    def test_payload_or_preimage_mutation_refuses_even_with_updated_receipt_hashes(self):
        original = self.rom.read_bytes()
        corrupted = bytearray(original)
        corrupted[0x144000] ^= 1
        self.rom.write_bytes(corrupted)
        self.proof['compiled_rom_sha256'] = R.sha(corrupted)
        self.native['compiled_rom_sha256'] = R.sha(corrupted)
        self.write_proof()
        with self.assertRaisesRegex(ValueError, 'preimage, payload or extent'):
            self.regions()
        self.rom.write_bytes(original)
        self.proof['compiled_rom_sha256'] = R.sha(original)
        self.native['compiled_rom_sha256'] = R.sha(original)
        self.plan['writes'][0]['preimage_hex'] = 'FF' * 5
        for name, raw in P.render_outputs(self.plan).items():
            (self.folder / name).write_bytes(raw)
        self.proof['prepared_sha256'] = R.sha((self.folder / 'prepare.json').read_bytes())
        self.write_proof()
        with self.assertRaisesRegex(ValueError, 'preimage, payload or extent'):
            self.regions()

    def test_readback_receipt_and_inflight_input_mutation_refuse(self):
        self.data_verify.return_value = dict(self.data, dictionary_verified=False)
        with self.assertRaisesRegex(ValueError, 'data receipt'):
            self.regions()
        self.data_verify.return_value = self.data
        def mutate(*args):
            (self.folder / 'runtime_data.asm').write_bytes(b'changed during verification')
            return self.data
        self.data_verify.side_effect = mutate
        with self.assertRaisesRegex(ValueError, 'input changed'):
            self.regions()


class OverlapCliTest(unittest.TestCase):
    def test_lyra_arguments_require_paired_explicit_context(self):
        for args in (['--rom', 'missing.bin'], ['--lyra-verification', 'missing.json'],
                     ['--lyra-input', 'missing-folder']):
            with self.subTest(args=args):
                run = subprocess.run([sys.executable, str(Path(Z.__file__)), *args],
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, 2)
                self.assertIn('--lyra-verification and --rom are required together', run.stderr)

    def test_default_cli_still_refuses_generated_source_without_verified_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            symbols, reserved = path / 'fixture.sym', path / 'map.txt'
            symbols.write_text('[labels]\n28:C000 Fixture\n[source files]\n'
                '0000 00000000 Data/Generated/lyra_project/runtime_data.asm\n'
                '[addr-to-line mapping]\n28:C000 0000:0001\n')
            reserved.write_text('0x140000 - 0x147FFF: 1 Bank\n    editor tables\n')
            argv = [sys.executable, str(Path(Z.__file__)), '--symbols', str(symbols), '--map', str(reserved)]
            run = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn('1 unowned emission addresses', run.stdout)
            symbols.write_text(symbols.read_text().replace('Data/Generated/lyra_project/runtime_data.asm',
                                                           'Overworld/ZSCustomOverworld.asm'))
            run = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main()
