"""Current-save requests keep original controls and fail before publication."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import subprocess
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_project_prepare as Q
import lyra_project_publisher as P
import lyra_project_allocation as R
import lyra_project_composition as C
import lyra_project_admission as A
from lyra_historical_fixture import historical_ledger_path, historical_source_root

QUALIFICATION = ROOT / 'Roms/LyraProject/ordinary-lineage.json'


class CurrentRequestUnitTest(unittest.TestCase):
    def test_binding_expires_after_saved_input_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'saved.json'
            path.write_bytes(b'original')
            row = Q.bound(path)
            self.assertEqual(Q.read_bound(row), b'original')
            path.write_bytes(b'edited')
            with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                Q.read_bound(row)

    def test_assignment_preserves115_and_allocates_only_declared13_tail_ids(self):
        pairs = tuple((0x44C0 + i, (i + 1,) * 4) for i in range(115))
        with (mock.patch.object(Q.R, 'reservation_claim', return_value=(
                {'tile32_candidate_reservation': {'id_range': [0x44C0, 0x4540]}}, 'ledger')),
                mock.patch.object(Q.T32, 'ownership', return_value={'reserved_references': 0}),
                mock.patch.object(Q.A, 'read_tile32', return_value=(0, 0, 0, 0)),
                mock.patch.object(Q.C, '_missing', return_value=[(1,) * 4, (1000,) * 4])):
            assignment = Q.current_assignment(b'source', b'terrain', object(), pairs, Path('ledger'))
        self.assertEqual(assignment['frozen115'], [dict(tile32_id=i, quadrants=list(q)) for i, q in pairs])
        self.assertEqual(assignment['assignments'][-1], dict(tile32_id=0x4533, quadrants=[1000] * 4))
        self.assertEqual(assignment['new_definition_count'], 1)
        self.assertEqual(assignment['production_maps'], [])

    def test_assignment_refuses_capacity_and_occupied_ownership(self):
        pairs = tuple((0x44C0 + i, (i + 1,) * 4) for i in range(115))
        with (mock.patch.object(Q.R, 'reservation_claim', return_value=(
                {'tile32_candidate_reservation': {'id_range': [0x44C0, 0x4540]}}, 'ledger')),
                mock.patch.object(Q.T32, 'ownership', return_value={}),
                mock.patch.object(Q.A, 'read_tile32', return_value=(0, 0, 0, 0)),
                mock.patch.object(Q.C, '_missing', return_value=[(i,) * 4 for i in range(1000, 1014)])):
            with self.assertRaisesRegex(ValueError, '14 new definitions exceed 13'):
                Q.current_assignment(b'source', b'terrain', object(), pairs, Path('ledger'))
        with (mock.patch.object(Q.R, 'reservation_claim', return_value=({}, 'ledger')),
                mock.patch.object(Q.T32, 'ownership', side_effect=ValueError('occupied IDs'))):
            with self.assertRaisesRegex(ValueError, 'occupied IDs'):
                Q.current_assignment(b'source', b'terrain', object(), pairs, Path('ledger'))

    def test_publisher_dispatch_is_explicit_and_does_not_reinterpret_legacy_request(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            for name in ('rom', 'terrain'):
                (folder / name).write_bytes(b'fixture')
            project = folder / 'project.yaze'
            project.write_text('[files]\nrom_filename=rom\nlyra_terrain_file=terrain\n[rom]\nrole=dev\n')
            request = folder / 'request.json'
            request.write_bytes(P.encoded({'kind': Q.KIND}))
            with mock.patch.object(Q, 'current_plan', return_value={'current': True}) as plan:
                self.assertEqual(P.make_plan(project, folder / 'rom', request), {'current': True})
                plan.assert_called_once()
            request.write_bytes(P.encoded({'kind': 'unknown'}))
            with self.assertRaisesRegex(ValueError, 'eight historical input roles'):
                P.make_plan(project, folder / 'rom', request)
            request.write_bytes(b'[]')
            with self.assertRaisesRegex(ValueError, 'request must be an object'):
                P.make_plan(project, folder / 'rom', request)


@unittest.skipUnless(QUALIFICATION.exists(), 'Private qualification controls unavailable')
class SavedCurrentPreparationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roles = json.loads(QUALIFICATION.read_bytes())
        if not all(Path(p).exists() for p in cls.roles.values()):
            raise unittest.SkipTest('Exact private qualification controls unavailable')
        cls.historical_ledger = historical_ledger_path(cls)
        for module, name, value in ((R, 'LEDGER', cls.historical_ledger),
                                    (P, 'ROOT', historical_source_root(cls))):
            patch = mock.patch.object(module, name, value)
            patch.start()
            cls.addClassCleanup(patch.stop)
        cls.source = Path(cls.roles['saved_rom']).read_bytes()
        cls.observation = json.loads(Path(cls.roles['authoring_observation']).read_bytes())

    def saved_copy(self, folder):
        project = folder / 'copy.yaze'
        rom = folder / 'saved.sfc'
        terrain = folder / 'terrain.json'
        rom.write_bytes(self.source)
        terrain.write_bytes(Path(self.roles['terrain']).read_bytes())
        project.write_text('[files]\nrom_filename=saved.sfc\nlyra_terrain_file=terrain.json\n[rom]\nrole=dev\n')
        cli = folder / 'native-verifier'
        cli.write_bytes(b'private verifier fixture')
        return project, rom, terrain, cli

    def prepare(self, folder):
        project, rom, terrain, cli = self.saved_copy(folder)
        with mock.patch.object(Q.A, 'native_verify', return_value=self.observation):
            report = Q.prepare_request(project, cli, QUALIFICATION, folder / 'request')
        self.assertTrue(report['ready'], report['blockers'])
        return report, project, rom, terrain, cli

    def test_compatible_current_save_prepares_and_preserves_saved_native37(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            report, project, rom, terrain, cli = self.prepare(folder)
            before = {p: p.read_bytes() for p in (project, rom, terrain)}
            plan = P.prepare(folder / 'generated', project=project, base_rom=rom, request=report['request'])
            self.assertEqual(plan['targets']['native37'], Q.D.native_map_grid(self.source, 0x37))
            self.assertEqual(plan['native37_changed_blocks'], 0)
            self.assertEqual(plan['production_maps'], [])
            self.assertEqual(len(plan['current_assignment']['frozen115']), 115)
            self.assertEqual(len(plan['emitted_definitions']), 55)
            self.assertTrue(all(path.read_bytes() == raw for path, raw in before.items()))
            compiled = C.apply_writes(self.source, plan['writes'])
            self.assertEqual(compiled[0x128090:0x12E000], self.source[0x128090:0x12E000])

    def test_request_refuses_stale_inputs_assignment_scope_and_base(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            report, project, rom, terrain, cli = self.prepare(folder)
            request = Path(report['request'])
            original = json.loads(request.read_bytes())
            for key, value, error in (
                ('selected_maps', [0x37, 0xA1, 0xA2], 'exceeds isolated'),
                ('production_admission', True, 'exceeds isolated'),
                ('assignment', {}, 'assignment differs')):
                bad = dict(original, **{key: value})
                request.write_bytes(P.encoded(bad))
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, error):
                    P.make_plan(project, rom, request)
            request.write_bytes(P.encoded(original))
            other = folder / 'other.sfc'
            other.write_bytes(b'wrong source')
            with self.assertRaisesRegex(ValueError, 'project/base ROM differs'):
                P.make_plan(project, other, request)
            for path in (project, rom, terrain, cli, Path(original['inputs']['observation']['path'])):
                raw = path.read_bytes()
                path.write_bytes(raw + b' ')
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                    P.make_plan(project, rom, request)
                path.write_bytes(raw)

    def test_occupied_source_produces_report_without_request_or_native_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            project, rom, terrain, cli = self.saved_copy(folder)
            source = bytearray(rom.read_bytes())
            # One nonblank reserved packed byte is enough to invalidate ownership.
            source[A.TILE32_BASES[0] + 0x453D // 4 * 6] ^= 1
            rom.write_bytes(source)
            with mock.patch.object(Q.A, 'native_verify', side_effect=AssertionError('Must refuse before CLI')):
                report = Q.prepare_request(project, cli, QUALIFICATION, folder / 'refused')
            self.assertFalse(report['ready'])
            self.assertIn('TILE32_RESERVATION_REFUSED', [row['code'] for row in report['blockers']])
            self.assertFalse((folder / 'refused/request.json').exists())
            self.assertFalse((folder / 'refused/observation.json').exists())
            self.assertEqual(rom.read_bytes(), bytes(source))

    def test_failed_native_observation_produces_refusal_and_no_usable_request(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            project, rom, terrain, cli = self.saved_copy(folder)
            with mock.patch.object(Q.A, 'native_verify', side_effect=ValueError('missing graphics source')):
                report = Q.prepare_request(project, cli, QUALIFICATION, folder / 'refused')
            self.assertFalse(report['ready'])
            self.assertIn('missing graphics source', report['blockers'][0]['detail'])
            self.assertFalse((folder / 'refused/request.json').exists())

    def test_timeout_bytes_remain_a_machine_readable_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            project, rom, terrain, cli = self.saved_copy(folder)
            with mock.patch.object(Q.A, 'native_verify', side_effect=subprocess.TimeoutExpired(
                    'native-verifier', 120, stderr=b'graphics\xff')):
                report = Q.prepare_request(project, cli, QUALIFICATION, folder / 'refused')
            self.assertFalse(report['ready'])
            self.assertEqual(report['blockers'][0]['stderr'], 'graphics\ufffd')
            self.assertEqual(json.loads((folder / 'refused/report.json').read_bytes()), report)

    def test_failed_report_write_does_not_publish_request(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            project, rom, terrain, cli = self.saved_copy(folder)
            replace = P.os.replace

            def fail_report(source, target):
                if Path(target).name == 'report.json':
                    raise OSError('report destination unavailable')
                return replace(source, target)

            with mock.patch.object(Q.A, 'native_verify', return_value=self.observation), mock.patch.object(
                    P.os, 'replace', side_effect=fail_report):
                with self.assertRaisesRegex(OSError, 'report destination unavailable'):
                    Q.prepare_request(project, cli, QUALIFICATION, folder / 'failed')
            self.assertFalse((folder / 'failed/request.json').exists())

    def test_request_changed_during_compilation_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            report, project, rom, terrain, cli = self.prepare(folder)
            request = Path(report['request'])
            compile_plan = P.compile_saved_plan

            def changed(*args):
                result = compile_plan(*args)
                request.write_bytes(request.read_bytes() + b' ')
                return result

            with mock.patch.object(P, 'compile_saved_plan', side_effect=changed):
                with self.assertRaisesRegex(ValueError, 'input changed while preparing'):
                    P.make_plan(project, rom, request)

    def test_relocated_ledger_regions_do_not_authorize_hardcoded_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / 'ledger.json'
            for purpose in ('tables', 'code', 'streams'):
                ledger = json.loads(self.historical_ledger.read_bytes())
                claim = next(c for c in ledger['rom_candidate_reservations'] if c['id'] == R.CLAIM)
                region = next(r for r in claim['regions'] if r['purpose'] == purpose)
                region['pc'] = [0x3D6000, 0x3D6200]
                path.write_bytes(P.encoded(ledger))
                blockers = Q.resource_report(self.source, path)
                self.assertIn('ROM_RESERVATION_REFUSED', [r['code'] for r in blockers], purpose)

    def test_changed_original_controls_are_never_repinned(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            changed = dict(self.roles, frozen_assignment=self.roles['historical_ledger'])
            path = folder / 'wrong-qualification.json'
            path.write_bytes(P.encoded(changed))
            with self.assertRaisesRegex(ValueError, 'Original qualification controls differ'):
                Q.controls(path)


if __name__ == '__main__':
    unittest.main()
