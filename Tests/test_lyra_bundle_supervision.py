"""Bundle-to-supervisor contract using owned temporary files and fake children."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import authoring_bundle_build as bundle
import lyra_build_selection as selection
import lyra_process_containment as containment


class BundleSupervisionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bundle-supervisor-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project.yaze'
        self.project.write_text('[files]\nlyra_terrain_file=terrain.json\n')
        self.engine = self.root / 'project'
        self.script = self.engine / 'Scripts/Build/build_rom.sh'
        self.script.parent.mkdir(parents=True)
        self.script.write_text('# synthetic build; never executed\n')
        (self.script.parent / 'lyra_project_publisher.py').write_text('# fixture validator\n')
        self.request = self.root / 'request.json'
        self.request.write_text('{}')
        self.candidate = (Path(str(self.project) + '.lyra-build-output')
                          / ('lyra-' + '1' * 32) / 'oos168x.sfc')
        self.candidate.parent.mkdir(parents=True, exist_ok=True)
        self.target = dict(OOS_BASE_ROM=str(self.root / 'base.sfc'),
                           OOS_LYRA_PROJECT=str(self.project),
                           OOS_LYRA_REQUEST=str(self.request),
                           OOS_LYRA_CANDIDATE=str(self.candidate))
        self.project_lock = Path(str(self.project) + '.lyra-build-project.lock')
        self.engine_lock = self.engine / '.lyra-build-engine.lock'
        self.selector = Path(str(self.project) + '.lyra-build-latest.json')
        # Fake children below model the existing Windows staging backend.
        # Actual Darwin refusal has its own control rather than bypassing its gate.
        self.staged_platform = mock.patch.object(selection, 'platform', 'win32')
        self.staged_platform.start()
        self.addCleanup(self.staged_platform.stop)

    def build_selected(self):
        return bundle.build_project(self.project, request=self.request, candidate=self.candidate)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS staged admission required')
    def test_darwin_supervisor_refuses_unadmitted_graph_before_launch(self):
        import lyra_macos_process_group as macos
        with mock.patch.object(selection, 'platform', 'darwin'), \
             mock.patch.object(macos, '_run_fixture_group') as run, \
             mock.patch.object(bundle, 'prepared_environment') as resolve:
            with self.assertRaisesRegex(containment.ContainmentUnavailable, 'No audited'):
                self.build_selected()
            run.assert_not_called()
            resolve.assert_not_called()
        self.assertFalse(self.candidate.exists())
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())
        self.assertFalse((self.engine / 'Roms').exists())

    def fake_prepare(self, argv, *, cwd, timeout, environment):
        self.child_environment = environment
        if 'resolve-target' not in argv:
            self.assertEqual(argv[1:], [str(self.script), '168'])
        self.assertEqual(cwd, self.root)
        self.assertTrue(self.project_lock.exists() and self.engine_lock.exists())
        return (argv, environment)

    def fake_success(self, environment):
        self.candidate.write_bytes(b'fake build')
        (self.candidate.parent / 'oos168x.build.json').write_text(
            json.dumps({'root': str(self.engine),
                        'lyra_attempt': {'build_id': environment['OOS_LYRA_BUILD_ID']}}))
        return containment.ContainedResult(0, False)

    def fake_validate(self, project, request, candidate, receipt):
        return dict(kind=selection.KIND, project=str(project), generation=1,
                    operation_id='fixture', request=str(request), candidate=str(candidate),
                    build_receipt={'path': str(receipt), 'sha256': '0' * 64},
                    build_id=json.loads(Path(receipt).read_text())['lyra_attempt']['build_id'])

    def patches(self, runner):
        def run(argv, environment):
            if 'resolve-target' in argv:
                return containment.ContainedResult(0, False)
            return runner(environment)
        return (mock.patch.object(bundle, 'prepared_environment', return_value=self.target),
                mock.patch.object(containment, 'prepare_contained', side_effect=self.fake_prepare),
                mock.patch.object(containment, '_run_windows', side_effect=run),
                mock.patch.object(selection, 'validate', side_effect=self.fake_validate))

    def automatic_patches(self, first_result=0, change_project=False):
        preparer = self.engine / 'Scripts/Build/lyra_project_prepare.py'
        preparer.write_text('# synthetic preparation; never executed by these mocks\n')
        self.auto_calls = []
        def prepare(argv, *, cwd, timeout, environment):
            self.assertTrue(self.project_lock.exists() and self.engine_lock.exists())
            self.assertEqual(cwd, self.root)
            return (argv, environment)
        def run(argv, environment):
            self.auto_calls.append((argv, dict(environment)))
            request = Path(environment['OOS_LYRA_REQUEST'])
            candidate = Path(environment['OOS_LYRA_CANDIDATE'])
            if len(self.auto_calls) == 1:
                self.assertIn('--auto-ordinary', argv)
                if change_project:
                    self.project.write_text('[files]\nlyra_terrain_file=changed.json\n')
                if first_result:
                    return containment.ContainedResult(first_result, False)
                request.parent.mkdir(parents=True)
                request.write_text('{}')
            else:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_bytes(b'fake build')
                (candidate.parent / 'oos168x.build.json').write_text(json.dumps({
                    'root': str(self.engine),
                    'lyra_attempt': {'build_id': environment['OOS_LYRA_BUILD_ID']}}))
            return containment.ContainedResult(0, False)
        def resolve(project, config, engine, *, request, candidate):
            return dict(OOS_BASE_ROM=str(self.root / 'base.sfc'),
                        OOS_LYRA_PROJECT=str(project), OOS_LYRA_REQUEST=str(request),
                        OOS_LYRA_CANDIDATE=str(candidate))
        return (mock.patch.object(bundle, 'prepared_environment', side_effect=resolve),
                mock.patch.object(containment, 'prepare_contained', side_effect=prepare),
                mock.patch.object(containment, '_run_windows', side_effect=run),
                mock.patch.object(selection, 'validate', side_effect=self.fake_validate))

    @unittest.skipIf(os.name == 'nt', 'Publisher admission is tested on the host')
    def test_prepared_environment_resolves_saved_paths_without_source_planner(self):
        import lyra_project_publisher as publisher
        self.project.write_text('[rom]\nrole=dev\n[files]\nrom_filename=base.sfc\n'
                                'lyra_terrain_file=terrain.json\n')
        (self.root / 'base.sfc').write_bytes(b'fixture')
        (self.root / 'terrain.json').write_text('{}')
        with mock.patch.object(publisher, 'resolve_current_target') as planner:
            result = bundle.prepared_environment(self.project, None, self.engine,
                                                 request=self.request, candidate=self.candidate)
        planner.assert_not_called()
        self.assertEqual(result['OOS_BASE_ROM'], str(self.root / 'base.sfc'))
        self.assertEqual(result['OOS_LYRA_REQUEST'], str(self.request))
        self.assertEqual(result['OOS_LYRA_CANDIDATE'], str(self.candidate))

    def test_automatic_build_prepares_then_publishes_same_generation(self):
        before = self.project.read_bytes()
        a, b, c, d = self.automatic_patches()
        with a, b, c, d:
            self.assertEqual(bundle.build_project(self.project), 0)
        self.assertEqual(len(self.auto_calls), 2)
        first, second = (row[1] for row in self.auto_calls)
        self.assertEqual(self.auto_calls[0][0][1], '-B')
        for environment in (first, second):
            self.assertEqual(environment['PYTHONDONTWRITEBYTECODE'], '1')
            self.assertFalse(any(key.upper() in ('PYTHONPYCACHEPREFIX', 'OOS_TEST_SOCKET') for key in environment))
        for key in ('OOS_LYRA_PROJECT', 'OOS_LYRA_BUILD_ID',
                    'OOS_LYRA_REQUEST', 'OOS_LYRA_CANDIDATE'):
            self.assertEqual(first[key], second[key])
        saved = json.loads(self.selector.read_text())
        self.assertEqual(saved['request'], first['OOS_LYRA_REQUEST'])
        self.assertEqual(saved['candidate'], first['OOS_LYRA_CANDIDATE'])
        self.assertEqual(saved['build_id'], first['OOS_LYRA_BUILD_ID'])
        self.assertEqual(self.project.read_bytes(), before)
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_desktop_engine_uses_saved_binding_and_explicit_producer(self):
        self.engine = self.root / 'separate engine'
        self.script = self.engine / 'Scripts/Build/build_rom.sh'
        self.script.parent.mkdir(parents=True)
        self.script.write_text('# fixture build\n')
        (self.engine / 'Oracle_main.asm').write_text('; fixture\n')
        (self.engine / 'Core').mkdir()
        self.engine_lock = self.engine / '.lyra-build-engine.lock'
        self.project.write_text('[files]\nlyra_terrain_file=terrain.json\n'
                                f'code_folder={self.engine / "Core"}\n')
        identity_dir = tempfile.TemporaryDirectory(prefix='producer-identity-')
        self.addCleanup(identity_dir.cleanup)
        producer = Path(identity_dir.name).resolve() / 'producer identity.json'
        producer.write_text('{}')
        before = self.project.read_bytes()
        a, b, c, d = self.automatic_patches()
        with (mock.patch.object(bundle, '__file__', str(self.script.parent / 'authoring_bundle_build.py')),
              a, b, c, d):
            # The actual module path must exist so resolve(strict=True) can bind it.
            (self.script.parent / 'authoring_bundle_build.py').write_text('# fixture\n')
            self.assertEqual(bundle.build_project(self.project, engine=self.engine,
                                                  producer_identity=producer), 0)
        command = self.auto_calls[0][0]
        self.assertEqual(command[command.index('--producer-identity') + 1], str(producer))
        self.assertEqual(command[command.index('--validate-build-engine') + 1], str(self.engine))
        self.assertEqual(self.auto_calls[1][0][1:], [str(self.script), '168'])
        self.assertEqual(self.project.read_bytes(), before)
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_desktop_engine_rejects_foreign_project_or_supervisor_before_child(self):
        self.engine = self.root / 'desktop-engine'
        script_dir = self.engine / 'Scripts/Build'
        script_dir.mkdir(parents=True)
        supervisor = script_dir / 'authoring_bundle_build.py'
        supervisor.write_text('# fixture\n')
        (script_dir / 'build_rom.sh').write_text('# fixture\n')
        (self.engine / 'Oracle_main.asm').write_text('; fixture\n')
        (self.engine / 'Core').mkdir()
        foreign = self.root / 'foreign-engine'
        (foreign / 'Core').mkdir(parents=True)
        (foreign / 'Oracle_main.asm').write_text('; foreign\n')
        self.project.write_text('[files]\nlyra_terrain_file=terrain.json\n'
                                f'code_folder={foreign / "Core"}\n')
        with (mock.patch.object(bundle, '__file__', str(supervisor)),
              mock.patch.object(containment, 'prepare_contained') as start):
            with self.assertRaisesRegex(ValueError, 'different engine'):
                bundle.build_project(self.project, engine=self.engine)
            start.assert_not_called()
        self.project.write_text('[files]\nlyra_terrain_file=terrain.json\n'
                                f'code_folder={self.engine / "Core"}\n')
        with mock.patch.object(containment, 'prepare_contained') as start:
            with self.assertRaisesRegex(ValueError, 'supervisor source'):
                bundle.build_project(self.project, engine=self.engine)
            start.assert_not_called()
        self.assertFalse(self.project_lock.exists())
        self.assertFalse((self.engine / '.lyra-build-engine.lock').exists())

    def test_automatic_refusal_never_starts_build_or_publishes(self):
        a, b, c, d = self.automatic_patches(first_result=7)
        with a as resolve, b, c, d as validate:
            self.assertEqual(bundle.build_project(self.project), 7)
        self.assertEqual(len(self.auto_calls), 1)
        resolve.assert_not_called()
        validate.assert_not_called()
        self.assertEqual(json.loads(self.selector.read_text())['kind'], selection.PENDING_KIND)
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_automatic_changed_save_never_starts_build(self):
        a, b, c, d = self.automatic_patches(change_project=True)
        with a as resolve, b, c, d as validate:
            self.assertEqual(bundle.build_project(self.project), 2)
        self.assertEqual(len(self.auto_calls), 1)
        resolve.assert_not_called()
        validate.assert_not_called()
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_actual_windows_automatic_children_share_attempt_identity(self):
        preparer = self.engine / 'Scripts/Build/lyra_project_prepare.py'
        preparer.write_text('''import os
from pathlib import Path
request = Path(os.environ["OOS_LYRA_REQUEST"])
request.parent.mkdir(parents=True)
request.write_text("{}")
''')
        self.script.write_text('''import json, os
from pathlib import Path
candidate = Path(os.environ["OOS_LYRA_CANDIDATE"])
candidate.parent.mkdir(parents=True, exist_ok=True)
candidate.write_bytes(b"fake build")
(candidate.parent / "oos168x.build.json").write_text(json.dumps({
    "root": __ENGINE__,
    "lyra_attempt": {"build_id": os.environ["OOS_LYRA_BUILD_ID"]}}))
'''.replace('__ENGINE__', repr(str(self.engine))))
        def resolve(project, config, engine, *, request, candidate):
            return dict(OOS_BASE_ROM=str(self.root / 'base.sfc'),
                        OOS_LYRA_PROJECT=str(project), OOS_LYRA_REQUEST=str(request),
                        OOS_LYRA_CANDIDATE=str(candidate))
        with mock.patch.object(bundle, 'prepared_environment', side_effect=resolve), \
             mock.patch.object(bundle.shutil, 'which', return_value=sys.executable), \
             mock.patch.object(selection, 'validate', side_effect=self.fake_validate):
            self.assertEqual(bundle.build_project(self.project), 0)
        selected = json.loads(self.selector.read_text())
        self.assertTrue(Path(selected['request']).is_file())
        receipt = json.loads((Path(selected['candidate']).parent / 'oos168x.build.json').read_text())
        self.assertEqual(selected['build_id'], receipt['lyra_attempt']['build_id'])
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_selected_build_passes_owned_id_and_publishes_matching_receipt(self):
        with mock.patch.dict(os.environ, {'OOS_LYRA_BUILD_ID': 'stale',
                                         'oos_lyra_candidate': '/foreign'}):
            a, b, c, d = self.patches(self.fake_success)
            with a as resolve, b, c, d:
                self.assertEqual(self.build_selected(), 0)
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(self.child_environment['OOS_LYRA_PROJECT'], str(self.project))
        self.assertNotEqual(self.child_environment['OOS_LYRA_BUILD_ID'], 'stale')
        self.assertNotIn('oos_lyra_candidate', self.child_environment)
        selector = json.loads(self.selector.read_text())
        self.assertEqual(selector['build_id'], self.child_environment['OOS_LYRA_BUILD_ID'])
        self.assertEqual(selector['candidate'], str(self.candidate))
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_failed_build_does_not_publish_and_releases_locks(self):
        a, b, c, d = self.patches(lambda environment: containment.ContainedResult(7, False))
        with a, b, c, d as validate:
            self.assertEqual(self.build_selected(), 7)
        validate.assert_not_called()
        self.assertEqual(json.loads(self.selector.read_text())['kind'], selection.PENDING_KIND)
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_timed_out_build_does_not_publish_and_releases_locks(self):
        a, b, c, d = self.patches(lambda environment: containment.ContainedResult(None, True))
        with a, b, c, d as validate:
            self.assertEqual(self.build_selected(), 124)
        validate.assert_not_called()
        self.assertEqual(json.loads(self.selector.read_text())['kind'], selection.PENDING_KIND)
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    @unittest.skipIf(os.name == 'nt', 'Windows has contained Build support')
    def test_unadmitted_platform_refuses_before_starting_a_child(self):
        with mock.patch.object(bundle, 'prepared_environment', return_value=self.target):
            with self.assertRaises(containment.ContainmentUnavailable):
                self.build_selected()
        self.assertFalse(self.candidate.exists())
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    @unittest.skipIf(os.name == 'nt', 'This shell fixture uses the host Bash path')
    def test_real_receipt_writer_receives_supervisor_build_id(self):
        source = Path(bundle.__file__).resolve().parent
        base = Path(self.target['OOS_BASE_ROM'])
        base.write_bytes(b'fake base')
        script = '''set -euo pipefail
repo_root="$1"; rom_dir="$2"; base_rom="$3"; version=168
feat_profile=fixture; feat_enable=; feat_disable=; persist_flags=0; asar_bin=fixture
source "$4"
receipt_tool="$5"
init_build_receipt
trap - EXIT
'''

        def run_receipt(environment):
            subprocess.run(['bash', '-c', script, 'fixture', str(self.engine),
                            str(self.candidate.parent), str(base),
                            str(source / 'build_checks.sh'), str(source / 'build_receipt.py')],
                           cwd=self.root, env=environment, capture_output=True, text=True, check=True)
            self.candidate.write_bytes(b'fake build')
            return containment.ContainedResult(0, False)

        a, b, c, d = self.patches(run_receipt)
        with a, b, c, d:
            self.assertEqual(self.build_selected(), 0)
        receipt = json.loads((self.candidate.parent / 'oos168x.build.json').read_text())
        self.assertEqual(receipt['lyra_attempt']['build_id'],
                         self.child_environment['OOS_LYRA_BUILD_ID'])
        self.assertEqual(json.loads(self.selector.read_text())['build_id'],
                         receipt['lyra_attempt']['build_id'])

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_actual_windows_child_gets_owned_id(self):
        self.script.write_text('''import json, os
from pathlib import Path
candidate = Path(os.environ["OOS_LYRA_CANDIDATE"])
candidate.write_bytes(b"fake build")
(candidate.parent / "oos168x.build.json").write_text(json.dumps({
    "root": __ENGINE__,
    "lyra_attempt": {"build_id": os.environ["OOS_LYRA_BUILD_ID"]}}))
'''.replace('__ENGINE__', repr(str(self.engine))))
        with mock.patch.object(bundle, 'prepared_environment', return_value=self.target), \
             mock.patch.object(bundle.shutil, 'which', return_value=sys.executable), \
             mock.patch.object(selection, 'validate', side_effect=self.fake_validate):
            self.assertEqual(self.build_selected(), 0)
        receipt = json.loads((self.candidate.parent / 'oos168x.build.json').read_text())
        self.assertEqual(json.loads(self.selector.read_text())['build_id'],
                         receipt['lyra_attempt']['build_id'])
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_uncertain_child_preserves_both_locks(self):
        def uncertain(environment):
            raise containment.ContainmentUncertain('fixture child not confirmed stopped')
        a, b, c, d = self.patches(uncertain)
        with a, b, c, d, self.assertRaises(containment.ContainmentUncertain):
            self.build_selected()
        self.assertTrue(self.project_lock.exists() and self.engine_lock.exists())

    def test_selection_change_under_lock_does_not_start_child(self):
        changed = dict(self.target, OOS_LYRA_REQUEST=str(self.root / 'changed.json'))
        with mock.patch.object(bundle, 'prepared_environment', return_value=changed), \
             mock.patch.object(containment, 'prepare_contained', return_value=()) as prepare, \
             mock.patch.object(containment, '_run_windows',
                               return_value=containment.ContainedResult(0, False)) as run:
            self.assertEqual(self.build_selected(), 2)
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(run.call_count, 1)
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_rejected_source_validator_never_starts_selected_build(self):
        with mock.patch.object(bundle, 'prepared_environment') as resolve, \
             mock.patch.object(containment, 'prepare_contained', return_value=()) as prepare, \
             mock.patch.object(containment, '_run_windows',
                               return_value=containment.ContainedResult(7, False)) as run:
            self.assertEqual(self.build_selected(), 7)
        resolve.assert_not_called()
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(run.call_count, 1)
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    @unittest.skipIf(os.name == 'nt', 'Publisher admission is tested on the host')
    def test_detached_selection_keeps_saved_project_target_unchanged(self):
        import lyra_project_publisher as publisher
        import lyra_current_transfer as transfer
        self.project.write_text('[files]\nlyra_terrain_file=terrain.json\n'
                                '[build]\nbuild_target=old-output.sfc\n')
        self.request.write_text(json.dumps({'kind': transfer.KIND}))
        prepared = {'current_source_profile': {'selected_source': {'root': str(self.engine)}},
                    'terrain_plan': {'target': {'path': str(self.candidate)}}}
        plan = {'kind': 'lyra.current_build_prepare.v1', 'selected': True,
                'current_files': {'prepare.json': json.dumps(prepared).encode()}}
        before = self.project.read_bytes()
        with (mock.patch.object(publisher, 'ROOT', self.engine),
              mock.patch.object(publisher, 'project_context',
                                return_value=(self.project, self.root / 'rom',
                                              self.root / 'terrain', self.request)),
              mock.patch.object(publisher, 'make_plan', return_value=plan)):
            target = bundle.current_environment(self.project, None, self.engine,
                                                request=self.request, candidate=self.candidate)
            self.assertEqual(target['OOS_LYRA_REQUEST'], str(self.request))
            self.assertEqual(target['OOS_LYRA_CANDIDATE'], str(self.candidate))
            with self.assertRaisesRegex(ValueError, 'CURRENT_BUILD_OUTPUT_MISMATCH'):
                bundle.current_environment(self.project, None, self.engine,
                                           request=self.request, candidate=self.engine / 'Roms/other/oos168x.sfc')
        self.assertEqual(self.project.read_bytes(), before)
        self.assertFalse(self.candidate.exists())

    def test_ordinary_to_selected_project_change_never_starts_child(self):
        self.project.write_text('[files]\nlyra_terrain_file=\n')
        begin = selection.begin_project_build

        def changed_before_lock(project, engine):
            self.project.write_text('[files]\nlyra_terrain_file=terrain.json\n')
            return begin(project, engine)

        with mock.patch.object(selection, 'begin_project_build', side_effect=changed_before_lock), \
             mock.patch.object(containment, 'prepare_contained') as prepare:
            with self.assertRaisesRegex(ValueError, 'Saved project changed'):
                bundle.build_project(self.project)
        prepare.assert_not_called()
        self.assertFalse(self.project_lock.exists() or self.engine_lock.exists())

    def test_replaced_project_symlink_never_builds_the_old_target(self):
        self.project.write_text('[files]\nlyra_terrain_file=\n')
        alias_dir = self.root / 'alias'
        alias_dir.mkdir()
        alias = alias_dir / 'project.yaze'
        try:
            alias.symlink_to(self.project)
        except OSError as error:
            self.skipTest(f'file symlinks unavailable: {error}')
        begin = selection.begin_project_build

        def replace_before_lock(project, engine):
            replacement = alias_dir / 'replacement.yaze'
            replacement.write_bytes(self.project.read_bytes())
            os.replace(replacement, alias)
            return begin(project, engine)

        with mock.patch.object(selection, 'begin_project_build', side_effect=replace_before_lock), \
             mock.patch.object(containment, 'prepare_contained') as prepare:
            with self.assertRaisesRegex(ValueError, 'Locked project differs'):
                bundle.build_project(alias)
        prepare.assert_not_called()
        self.assertFalse(Path(str(alias) + '.lyra-build-project.lock').exists())
        self.assertFalse(self.engine_lock.exists())


@unittest.skipUnless(sys.platform == 'darwin', 'macOS profile guardian required')
class MacProfileBundleTest(unittest.TestCase):
    def setUp(self):
        from test_lyra_macos_process_group import MacOracleProfileTest
        self.fixture = MacOracleProfileTest('test_same_guardian_runs_two_fixed_stages_with_bound_environment')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def build(self):
        f = self.fixture
        return bundle.build_project(f.project, macos_profile=f.profile_path,
                                    macos_profile_sha256=f.profile_binding['sha256'])

    def test_automatic_profile_retains_locks_through_both_guardians_and_publication(self):
        f = self.fixture
        project_before = f.project.read_bytes(); receipt_before = f.receipt.read_bytes()
        observed = []
        import lyra_macos_process_group as macos
        run = macos.run_oracle_build
        def capture(prepared):
            self.assertTrue(Path(str(f.project) + '.lyra-build-project.lock').exists())
            self.assertTrue((f.engine / '.lyra-build-engine.lock').exists())
            observed.append(prepared)
            return run(prepared)
        with mock.patch.object(macos, 'run_oracle_build', side_effect=capture), \
             mock.patch.object(selection, 'validate', side_effect=BundleSupervisionTest.fake_validate.__get__(self)):
            self.assertEqual(self.build(), 0)
        self.assertEqual(len(observed), 2)
        self.assertLess(observed[1]['timeout'], observed[0]['timeout'])
        self.assertEqual(observed[0]['environment']['OOS_LYRA_BUILD_ID'],
                         observed[1]['environment']['OOS_LYRA_BUILD_ID'])
        selector = json.loads(Path(str(f.project) + '.lyra-build-latest.json').read_text())
        self.assertEqual(selector['candidate'], observed[1]['environment']['OOS_LYRA_CANDIDATE'])
        self.assertEqual(selector['request'], observed[0]['environment']['OOS_LYRA_REQUEST'])
        self.assertEqual(f.project.read_bytes(), project_before)
        self.assertEqual(f.receipt.read_bytes(), receipt_before)
        self.assertFalse(Path(str(f.project) + '.lyra-build-project.lock').exists())
        self.assertFalse((f.engine / '.lyra-build-engine.lock').exists())
        self.assertFalse((f.engine / 'Roms').exists())

    def test_profile_preparation_failure_never_starts_build_or_publishes_success(self):
        f = self.fixture
        f.preparer.write_text('raise SystemExit(19)\n'); f.refresh_profile()
        self.assertEqual(self.build(), 19)
        self.assertFalse((f.home / 'build.json').exists())
        selector = json.loads(Path(str(f.project) + '.lyra-build-latest.json').read_text())
        self.assertEqual(selector['kind'], selection.PENDING_KIND)
        self.assertFalse(Path(str(f.project) + '.lyra-build-project.lock').exists())

    def test_ambient_profile_cannot_admit_build(self):
        f = self.fixture
        with mock.patch.dict(os.environ, {'OOS_MACOS_BUILD_PROFILE': str(f.profile_path),
                                         'OOS_MACOS_BUILD_PROFILE_SHA256': f.profile_binding['sha256']}):
            with self.assertRaisesRegex(containment.ContainmentUnavailable, 'No audited'):
                bundle.build_project(f.project)
        self.assertFalse((f.home / 'prepare.json').exists())

    def test_profile_tool_change_between_stages_refuses_build(self):
        f = self.fixture
        import lyra_macos_process_group as macos
        run = macos.run_oracle_build
        def change_after_preparation(prepared):
            result = run(prepared)
            f.asar.write_text('#!/bin/sh\nexit 92\n')
            return result
        with mock.patch.object(macos, 'run_oracle_build', side_effect=change_after_preparation):
            with self.assertRaisesRegex(containment.ContainmentUnavailable, 'bound file changed'):
                self.build()
        self.assertFalse((f.home / 'build.json').exists())
        self.assertFalse(Path(str(f.project) + '.lyra-build-project.lock').exists())

    def test_profile_uncertainty_retains_both_locks_without_success_selector(self):
        f = self.fixture
        import lyra_macos_process_group as macos
        with mock.patch.object(macos, 'run_oracle_build', side_effect=containment.ContainmentUncertain('fixture uncertainty')):
            with self.assertRaises(containment.ContainmentUncertain): self.build()
        self.assertTrue(Path(str(f.project) + '.lyra-build-project.lock').exists())
        self.assertTrue((f.engine / '.lyra-build-engine.lock').exists())
        selector = json.loads(Path(str(f.project) + '.lyra-build-latest.json').read_text())
        self.assertEqual(selector['kind'], selection.PENDING_KIND)


if __name__ == '__main__':
    unittest.main()
