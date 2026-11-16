"""Disposable generated-input fixtures; no Save, allocation or game admission."""
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import lyra_generated_inputs as generated
import lyra_project_publisher as publisher
import lyra_current_transfer as current
import asm_source
import generate_hooks_json as hooks
import generate_hack_manifest as manifest

ROOT = Path(__file__).resolve().parents[1]


class GeneratedInputsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.engine = self.root / 'engine'
        self.engine.mkdir()
        self.project = self.root / 'saved project.yaze'
        self.project.write_text('saved descriptor unchanged')
        self.candidate = (Path(str(self.project) + '.lyra-build-output') /
                          ('lyra-' + 'a' * 32) / 'oos168x.sfc')
        self.candidate.parent.mkdir(parents=True)
        self.folder = generated.private_folder(self.engine, self.project, self.candidate)
        self.environment = dict(OOS_LYRA_BUILD_CONTEXT='1', OOS_LYRA_PROJECT=str(self.project),
                                OOS_LYRA_CANDIDATE=str(self.candidate))
        self.env = mock.patch.dict(os.environ, self.environment)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.files = {
            'runtime_constants.asm': b'!LYRA_PROJECT_DATA_PRESENT = 1\n!LYRA_NATIVE_A1_ENABLED = 1\n',
            'runtime_data.asm': b'org $308000\nFixtureData:\ndb $42\n',
            'binaries/payload.bin': b'\x01\x02\x03',
        }
        self.set_marker()

    def set_marker(self):
        self.files['prepare.json'] = json.dumps(dict(
            kind='lyra.ordinary_build_prepare.v1', selected=True,
            generated_files={name: hashlib.sha256(raw).hexdigest()
                             for name, raw in self.files.items() if name != 'prepare.json'})).encode()

    def write(self):
        generated.write_private_outputs(self.folder, self.files)

    def entry(self):
        (self.engine / 'Oracle_main.asm').write_text(
            'if !LYRA_BUILD_CONTEXT == 1\n'
            'incsrc "!LYRA_GENERATED_ROOT/runtime_constants.asm"\n'
            'incsrc "!LYRA_GENERATED_ROOT/runtime_data.asm"\nendif\n')

    def test_private_writer_preserves_engine_and_saved_project(self):
        before = self.project.read_bytes()
        self.write()
        self.assertEqual(self.project.read_bytes(), before)
        self.assertEqual(list(self.engine.iterdir()), [])
        self.assertEqual(generated.selected_folder(self.engine), self.folder)
        self.assertEqual(generated.validate_prepared(self.folder)['selected'], True)
        self.assertEqual((self.folder / 'binaries/payload.bin').read_bytes(), b'\x01\x02\x03')
        with self.assertRaisesRegex(ValueError, 'fresh generation'):
            self.write()

    def test_private_writer_refuses_unavailable_anchored_platform(self):
        with mock.patch.object(os, 'supports_dir_fd', set()):
            with self.assertRaisesRegex(ValueError, 'anchored private writer unavailable'):
                self.write()
        self.assertFalse(self.folder.exists())

    def test_writer_failure_never_publishes_marker(self):
        original = os.rename
        count = 0
        def fail(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('injected write failure')
            return original(*args, **kwargs)
        # Capability identity is checked before the injected implementation.
        with mock.patch.object(os, 'rename', fail), \
             mock.patch.object(os, 'supports_dir_fd', {*os.supports_dir_fd, fail}):
            with self.assertRaisesRegex(OSError, 'injected write failure'):
                self.write()
        self.assertFalse((self.folder / 'prepare.json').exists())
        self.assertEqual(list(self.engine.iterdir()), [])

    def test_directory_swap_cannot_redirect_write_to_engine(self):
        shared = self.engine / 'shared'
        shared.mkdir()
        sentinel = shared / 'prepare.json'
        sentinel.write_bytes(b'preserve me')
        moved = self.folder.with_name('retained-original')
        original = os.rename
        swapped = False
        def swap(*args, **kwargs):
            nonlocal swapped
            result = original(*args, **kwargs)
            if not swapped:
                swapped = True
                original(self.folder, moved)
                self.folder.symlink_to(shared, target_is_directory=True)
            return result
        with mock.patch.object(os, 'rename', swap), \
             mock.patch.object(os, 'supports_dir_fd', {*os.supports_dir_fd, swap}):
            with self.assertRaisesRegex(ValueError, 'canonical paths'):
                self.write()
        self.assertEqual(sentinel.read_bytes(), b'preserve me')
        self.assertEqual(list(shared.iterdir()), [sentinel])
        self.assertFalse((moved / 'prepare.json').exists())

    def test_rejects_foreign_generation_and_path_aliases(self):
        with self.assertRaisesRegex(ValueError, 'private project generation'):
            generated.private_folder(self.engine, self.project, self.engine / 'Roms/oos168x.sfc')
        foreign = self.root / 'foreign.yaze'
        foreign.write_text('foreign')
        with self.assertRaisesRegex(ValueError, 'private project generation'):
            generated.private_folder(self.engine, foreign, self.candidate)
        alias = self.root / 'alias'
        alias.symlink_to(self.candidate.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'canonical paths'):
            generated.private_folder(self.engine, self.project, alias / self.candidate.name)

    def test_generated_payload_and_symlinks_fail_identity(self):
        self.write()
        payload = self.folder / 'binaries/payload.bin'
        payload.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'generated bytes changed'):
            generated.validate_prepared(self.folder)
        payload.unlink()
        outside = self.root / 'outside.bin'
        outside.write_bytes(b'\x01\x02\x03')
        payload.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'canonical paths'):
            generated.validate_prepared(self.folder)

    def test_scan_rejects_substitution_during_read(self):
        self.write()
        payload = self.folder / 'binaries/payload.bin'
        original = Path.read_bytes
        def changed(path):
            raw = original(path)
            if path == payload:
                payload.write_bytes(b'changed during scan')
            return raw
        with mock.patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(ValueError, 'changed during scan'):
                generated.validate_prepared(self.folder)

    def test_generated_closure_and_metadata_keep_actual_private_sources(self):
        self.write()
        self.entry()
        sources = asm_source.collect_reachable_asm_sources(self.engine)
        self.assertEqual(set(sources), {self.engine / 'Oracle_main.asm',
            self.folder / 'runtime_constants.asm', self.folder / 'runtime_data.asm'})
        self.assertEqual(manifest.collect_reachable_asm_sources(self.engine), sources)
        records = hooks.scan_hooks(self.engine, sources)
        self.assertEqual([r.source for r in records], [str(self.folder / 'runtime_data.asm') + ':1'])
        owned = manifest.scan_bank_ownership(self.engine, sources)
        self.assertIn(str(self.folder / 'runtime_data.asm'), json.dumps(owned))
        self.assertNotIn(str(self.engine / generated.LEGACY_OUTPUT), json.dumps(owned))

    def test_unbound_generated_include_and_escaping_nested_include_refuse(self):
        self.entry()
        self.files['runtime_data.asm'] = b'incsrc "outside.asm"\n'
        self.set_marker()
        self.write()
        (self.folder / 'outside.asm').write_text('org $308000\ndb $00\n')
        with self.assertRaisesRegex(asm_source.SourceGraphError, 'escapes repo root'):
            asm_source.collect_reachable_asm_sources(self.engine)
        (self.folder / 'runtime_data.asm').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'generated bytes changed'):
            asm_source.collect_reachable_asm_sources(self.engine)

    def test_current_publisher_requires_private_folder_after_existing_admission(self):
        plan = dict(kind='lyra.current_build_prepare.v1', selected=True, inputs=[])
        files = dict(self.files)
        marker = json.loads(files['prepare.json'])
        marker['terrain_plan'] = dict(target=dict(path=str(self.candidate)))
        files['prepare.json'] = json.dumps(marker).encode()
        with mock.patch.object(publisher, 'ROOT', self.engine), \
             mock.patch.object(publisher, 'make_plan', return_value=plan) as admission, \
             mock.patch.object(publisher, 'render_outputs', return_value=files):
            with self.assertRaisesRegex(ValueError, 'private generated inputs'):
                publisher.prepare(self.engine / generated.LEGACY_OUTPUT, project=self.project,
                                  base_rom=self.root / 'base.sfc', candidate=self.candidate)
            admission.assert_called_once()
            publisher.prepare(self.folder, project=self.project,
                              base_rom=self.root / 'base.sfc', candidate=self.candidate)
        self.assertTrue((self.folder / 'prepare.json').exists())
        self.assertEqual(list(self.engine.iterdir()), [])

    def test_selected_shell_guards_precede_engine_writes(self):
        build = self.engine / 'Scripts/Build/build_rom.sh'
        build.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'Scripts/Build/build_rom.sh', build)
        cases = (['--enable', 'test'], ['--persist-flags'], ['--profile', 'all-on'],
                 ['--reload'], ['--mesen-sync'])
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run(['bash', str(build), '168', *args],
                                        env=dict(os.environ, **self.environment),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse((self.engine / 'Roms').exists())
                self.assertFalse((self.engine / 'Config').exists())

    def test_orphan_selection_environment_refuses_before_any_write(self):
        build = self.engine / 'Scripts/Build/build_rom.sh'
        build.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'Scripts/Build/build_rom.sh', build)

        def snapshot():
            return {str(path.relative_to(self.root)):
                    (path.read_bytes() if path.is_file() else None)
                    for path in self.root.rglob('*')}

        before = snapshot()
        base = {key: value for key, value in os.environ.items()
                if not key.startswith('OOS_LYRA_')}
        selections = dict(OOS_LYRA_CANDIDATE=str(self.candidate),
                          OOS_LYRA_REQUEST=str(self.root / 'request.json'),
                          OOS_LYRA_BUILD_ID='a' * 32)
        # Every nonempty subset is malformed without a project. Exercise both
        # absent and empty project values, with and without mutation flags.
        for count in range(1, len(selections) + 1):
            for names in itertools.combinations(selections, count):
                for project in (None, ''):
                    for arguments in ([], ['--enable', 'fixture', '--persist-flags']):
                        with self.subTest(names=names, project=project, arguments=arguments):
                            environment = dict(base, **{key: selections[key] for key in names})
                            if project is not None:
                                environment['OOS_LYRA_PROJECT'] = project
                            result = subprocess.run(['bash', str(build), '168', *arguments],
                                                    env=environment, capture_output=True, text=True)
                            self.assertEqual(result.returncode, 1, result.stderr)
                            self.assertIn('Lyra selection inputs require OOS_LYRA_PROJECT', result.stderr)
                            self.assertEqual(snapshot(), before)

    def test_selected_shell_refuses_ambient_socket_without_connecting_or_writing(self):
        build = self.engine / 'Scripts/Build/build_rom.sh'
        build.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'Scripts/Build/build_rom.sh', build)
        before = {str(path.relative_to(self.root)):
                  (path.read_bytes() if path.is_file() else None) for path in self.root.rglob('*')}
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(0.05)
            address = '%s:%d' % listener.getsockname()
            for key in ('OOS_TEST_SOCKET', 'oos_test_socket', 'OoS_TeSt_SoCkEt'):
                with self.subTest(key=key):
                    environment = {name: value for name, value in os.environ.items()
                                   if name.upper() != 'OOS_TEST_SOCKET'}
                    environment.update(self.environment)
                    environment[key] = address
                    result = subprocess.run(['bash', str(build), '168'], env=environment,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn('cannot use ambient OOS_TEST_SOCKET', result.stderr)
                    self.assertEqual({str(path.relative_to(self.root)):
                                      (path.read_bytes() if path.is_file() else None)
                                      for path in self.root.rglob('*')}, before)
                    with self.assertRaises(TimeoutError):
                        listener.accept()

    def test_supervisor_suppresses_bytecode_before_local_imports(self):
        folder = self.engine / 'Scripts/Build'
        folder.mkdir(parents=True)
        wrapper = folder / 'authoring_bundle_build.py'
        shutil.copyfile(ROOT / 'Scripts/Build/authoring_bundle_build.py', wrapper)
        (folder / 'lyra_build_selection.py').write_text(
            'import sys\nassert sys.dont_write_bytecode\nraise SystemExit(0)\n')
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() not in ('PYTHONDONTWRITEBYTECODE', 'PYTHONPYCACHEPREFIX')}
        result = subprocess.run([sys.executable, str(wrapper)], env=environment,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(list(self.engine.rglob('__pycache__')))

    def test_noncanonical_selection_names_refuse_before_output(self):
        build = self.engine / 'Scripts/Build/build_rom.sh'
        build.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'Scripts/Build/build_rom.sh', build)
        base = {key: value for key, value in os.environ.items()
                if not key.upper().startswith('OOS_LYRA_')}
        for name in ('project', 'candidate', 'request', 'build_id', 'build_context'):
            for key in ('oos_lyra_' + name, 'OoS_LyRa_' + name):
                with self.subTest(key=key):
                    result = subprocess.run(['bash', str(build), '168'],
                        env=dict(base, **{key: 'foreign'}), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn('Noncanonical Lyra environment name', result.stderr)
                    self.assertFalse((self.engine / 'Roms').exists())
                    self.assertFalse((self.engine / 'Config').exists())

    def current_private_fixture(self, *, relative=False):
        # Only policy construction is mocked in these path/lifecycle fixtures.
        # verify_current_context still calls it and compares canonical rendered
        # bytes; the existing CurrentBuildTest exercises real rederivation.
        asset = self.root / 'external graphics.bin'
        asset.write_bytes(b'\x13\x57\x9b\xdf')
        legacy = self.engine / generated.LEGACY_OUTPUT
        legacy.mkdir(parents=True)
        (legacy / 'prepare.json').write_bytes(b'poison legacy marker: must never be read')
        (legacy / 'graphics_runtime_tables.asm').write_bytes(b'poison legacy graphics')
        patch = mock.patch.object(publisher, 'ROOT', self.engine)
        patch.start()
        self.addCleanup(patch.stop)
        asset_text = Path(os.path.relpath(asset, legacy)).as_posix() if relative else asset.as_posix()
        original_graphics = f'org $008000\n  incbin "{asset_text}" ; bound fixture asset\n'
        graphics_source = self.root / 'source-graphics.asm'
        graphics_source.write_text(original_graphics)
        graphics = current.verify_current_graphics_assets(original_graphics, [current.Q.bound(asset)],
                                               project=self.project, candidate=self.candidate)
        self.assertEqual(graphics_source.read_text(), original_graphics)
        self.assertIn(f'incbin "{asset.as_posix()}"', graphics)
        self.assertIn('; bound fixture asset', graphics)
        self.files['runtime_constants.asm'] = (
            b'!LYRA_PROJECT_DATA_PRESENT = 1\n!LYRA_NATIVE_A1_ENABLED = 0\n!LYRA_CURRENT_MODE = 1\n')
        self.files['runtime_data.asm'] = b'org $008010\ndb $42\n'
        self.files['graphics_runtime_tables.asm'] = graphics.encode()
        source = self.root / 'synthetic-source.bin'
        source.write_bytes(bytes(0x200000))
        prepared = dict(kind='lyra.current_build_prepare.v1', selected=True,
            project=str(self.project), base_rom=str(source), request=str(self.root / 'request.json'),
            ledger=str(self.root / 'ledger.json'), allocation_granted=True,
            producer_enforcement_verified=True, runtime_admission=True,
            saved_rom_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            inputs=[current.Q.bound(graphics_source), current.Q.bound(asset)],
            terrain_plan=dict(target=dict(path=str(self.candidate), size=0x400000,
                                          role='compiled_candidate')),
            generated_files={name: hashlib.sha256(raw).hexdigest()
                             for name, raw in self.files.items() if name != 'prepare.json'})
        self.files['prepare.json'] = publisher.encoded(prepared)
        plan = dict(kind='lyra.current_build_prepare.v1', current_files=self.files)
        self.write()
        return asset, legacy, prepared, plan

    def check_current_private_graphics(self, *, relative):
        asset, legacy, prepared, plan = self.current_private_fixture(relative=relative)
        self.entry()
        entry = self.engine / 'Oracle_main.asm'
        entry.write_text('lorom\n' + entry.read_text() +
                         'incsrc "!LYRA_GENERATED_ROOT/graphics_runtime_tables.asm"\n')
        original = Path.read_bytes
        def reject_legacy(path):
            if path.is_relative_to(legacy):
                raise AssertionError('legacy generated input was read')
            return original(path)
        with mock.patch.object(current, 'ordinary_plan', return_value=plan) as rederive, \
             mock.patch.object(Path, 'read_bytes', reject_legacy):
            self.assertEqual(current.verify_current_context(self.engine, prepared,
                             input_folder=self.folder), self.files)
            sources = asm_source.collect_reachable_asm_sources(self.engine)
            self.assertIn(self.folder / 'graphics_runtime_tables.asm', sources)
            rederive.assert_called_with(prepared['project'], prepared['base_rom'], prepared['request'],
                                        ledger_path=prepared['ledger'])
            assembler = shutil.which('asar')
            if not assembler:
                self.skipTest('asar unavailable for current-kind synthetic compile/readback')
            output = self.root / 'synthetic-assembled.bin'
            output.write_bytes(bytes(0x8000))
            result = subprocess.run([assembler, '--no-title-check', '-DLYRA_BUILD_CONTEXT=1',
                '-DLYRA_GENERATED_ROOT=' + str(self.folder), str(entry), str(output)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_bytes()[:4], asset.read_bytes())
            self.assertEqual(output.read_bytes()[0x10], 0x42)
            publisher.stage_current_candidate(self.folder, self.candidate)
            self.assertEqual(self.candidate.stat().st_size, 0x400000)

    def test_current_private_context_compiles_absolute_bound_graphics(self):
        self.check_current_private_graphics(relative=False)

    def test_current_private_context_compiles_relative_bound_graphics(self):
        self.check_current_private_graphics(relative=True)

    def test_current_private_context_rejects_wrong_folder_tamper_and_source_refusal(self):
        _, legacy, prepared, plan = self.current_private_fixture()
        with mock.patch.object(current, 'ordinary_plan', return_value=plan):
            with self.assertRaisesRegex(ValueError, 'folder differs'):
                current.verify_current_context(self.engine, prepared, input_folder=legacy)
            payload = self.folder / 'binaries/payload.bin'
            payload.write_bytes(b'tamper')
            with self.assertRaisesRegex(ValueError, 'generated bytes changed'):
                current.verify_current_context(self.engine, prepared, input_folder=self.folder)
        with mock.patch.object(current, 'ordinary_plan', side_effect=ValueError('source contract refused')):
            with self.assertRaisesRegex(ValueError, 'source contract refused'):
                current.verify_current_context(self.engine, prepared, input_folder=self.folder)
        self.assertFalse(self.candidate.exists())

    def test_graphics_rebase_preserves_legacy_source_and_rejects_missing_or_changed_asset(self):
        asset, legacy, _, _ = self.current_private_fixture()
        relative = Path(os.path.relpath(asset, legacy)).as_posix()
        graphics = f'  incbin "{relative}" ; preserve this comment\r\n'
        binding = current.Q.bound(asset)
        old_target = self.root / 'legacy-compiled.sfc'
        self.assertEqual(current.verify_current_graphics_assets(graphics, [binding],
                         project=self.project, candidate=old_target), graphics)
        expected = f'  incbin "{asset.as_posix()}" ; preserve this comment\r\n'
        self.assertEqual(current.verify_current_graphics_assets(graphics, [binding],
                         project=self.project, candidate=self.candidate), expected)
        asset.write_bytes(b'changed external graphics')
        with self.assertRaisesRegex(ValueError, 'changed'):
            current.verify_current_graphics_assets(graphics, [binding],
                                                   project=self.project, candidate=self.candidate)
        asset.unlink()
        with self.assertRaises(FileNotFoundError):
            current.verify_current_graphics_assets(graphics, [binding],
                                                   project=self.project, candidate=self.candidate)

    def test_graphics_rebase_rejects_unbound_unused_and_unrepresentable_paths(self):
        asset, _, _, _ = self.current_private_fixture()
        graphics = f'incbin "{asset.as_posix()}"\n'
        binding = current.Q.bound(asset)
        with self.assertRaisesRegex(ValueError, 'ASSETS_UNBOUND'):
            current.verify_current_graphics_assets(graphics, [],
                                                   project=self.project, candidate=self.candidate)
        with self.assertRaisesRegex(ValueError, 'Unused or missing'):
            current.verify_current_graphics_assets('; no incbin\n', [binding],
                                                   project=self.project, candidate=self.candidate)
        unsafe = self.root / 'unsafe{asset}.bin'
        unsafe.write_bytes(b'fixture')
        with self.assertRaisesRegex(ValueError, 'RELOCATION_UNSUPPORTED'):
            current.verify_current_graphics_assets(f'incbin "{unsafe.as_posix()}"\n', [current.Q.bound(unsafe)],
                                                   project=self.project, candidate=self.candidate)
        alias = self.root / 'alias-asset.bin'
        alias.symlink_to(asset)
        with self.assertRaisesRegex(ValueError, 'RELOCATION_UNSUPPORTED'):
            current.verify_current_graphics_assets(f'incbin "{alias.as_posix()}"\n', [binding],
                                                   project=self.project, candidate=self.candidate)

    def test_graphics_rebase_rechecks_bound_asset_after_rendering(self):
        asset, _, _, _ = self.current_private_fixture()
        binding = current.Q.bound(asset)
        original = current.Q.read_bound
        def mutate(row):
            raw = original(row)
            if row == binding:
                asset.write_bytes(b'changed during render')
            return raw
        with mock.patch.object(current.Q, 'read_bound', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed'):
                current.verify_current_graphics_assets(f'incbin "{asset.as_posix()}"\n', [binding],
                                                       project=self.project, candidate=self.candidate)

    @unittest.skipIf(os.name == 'nt', 'POSIX distinct backslash/control filenames required')
    def test_assembler_normalized_asset_aliases_cannot_replace_bound_bytes(self):
        self.current_private_fixture()
        for raw_name, normalized in (('graphics\\asset.bin', 'graphics/asset.bin'),
                                     ('graphics\x01asset.bin', 'graphicsasset.bin')):
            with self.subTest(raw_name=repr(raw_name)):
                bound = self.root / raw_name
                alias = self.root / normalized
                alias.parent.mkdir(parents=True, exist_ok=True)
                bound.write_bytes(b'authenticated original')
                alias.write_bytes(b'different normalized alias')
                self.assertNotEqual(bound, alias)
                self.assertNotEqual(bound.read_bytes(), alias.read_bytes())
                with self.assertRaisesRegex(ValueError, 'RELOCATION_UNSUPPORTED'):
                    current.verify_current_graphics_assets(f'incbin "{bound.as_posix()}"\n',
                        [current.Q.bound(bound)], project=self.project, candidate=self.candidate)
                self.assertFalse(self.candidate.exists())
                self.assertEqual(alias.read_bytes(), b'different normalized alias')

    @unittest.skipIf(os.name == 'nt', 'POSIX distinct backslash/control filenames required')
    def test_assembler_normalized_private_root_aliases_refuse_before_write(self):
        for raw_name, normalized in (('project\\alias.yaze', 'project/alias.yaze'),
                                     ('project\x01alias.yaze', 'projectalias.yaze')):
            with self.subTest(raw_name=repr(raw_name)):
                project = self.root / raw_name
                alias = self.root / normalized
                alias.parent.mkdir(parents=True, exist_ok=True)
                project.write_bytes(b'actual descriptor')
                alias.write_bytes(b'normalized alias descriptor')
                candidate = Path(str(project) + '.lyra-build-output') / ('lyra-' + 'b' * 32) / 'oos168x.sfc'
                with self.assertRaisesRegex(ValueError, 'unsupported Asar path characters'):
                    generated.private_folder(self.engine, project, candidate)
                self.assertFalse(candidate.parent.parent.exists())
                self.assertEqual(project.read_bytes(), b'actual descriptor')
                self.assertEqual(alias.read_bytes(), b'normalized alias descriptor')

    @unittest.skipIf(os.name == 'nt', 'POSIX control-character filenames required')
    def test_all_representable_ascii_control_path_bytes_are_rejected(self):
        for code in [*range(1, 32), 127]:
            with self.subTest(code=code):
                project = self.root / ('project' + chr(code) + '.yaze')
                project.write_bytes(b'descriptor')
                candidate = Path(str(project) + '.lyra-build-output') / ('lyra-' + 'c' * 32) / 'oos168x.sfc'
                with self.assertRaisesRegex(ValueError, 'unsupported Asar path characters'):
                    generated.private_folder(self.engine, project, candidate)
                self.assertFalse(candidate.parent.parent.exists())


    def test_synthetic_assembler_reads_private_include_with_spaces(self):
        self.files['runtime_data.asm'] = b'org $008000\nincbin "binaries/payload.bin"\n'
        self.set_marker()
        self.write()
        entry = self.engine / 'fixture.asm'
        entry.write_text('lorom\nincsrc "!LYRA_GENERATED_ROOT/runtime_data.asm"\n')
        assembler = shutil.which('asar')
        if not assembler:
            self.skipTest('asar unavailable for synthetic include check')
        # A disposable synthetic byte array, never a game ROM or saved project.
        output = self.root / 'synthetic.bin'
        output.write_bytes(bytes(0x8000))
        result = subprocess.run([assembler, '--no-title-check',
                                 '-DLYRA_GENERATED_ROOT=' + str(self.folder), str(entry), str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes()[:3], b'\x01\x02\x03')


if __name__ == '__main__':
    unittest.main()
