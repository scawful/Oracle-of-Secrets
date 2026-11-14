"""Bundle adapter bindings; the real compiler is never launched by these tests."""
import importlib.util
import hashlib
import json
import subprocess
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('authoring_bundle_build',
    Path(__file__).resolve().parents[1] / 'authoring_bundle_build.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


class AuthoringBundleBuildTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'authoring bundle with spaces'
        self.root.mkdir()
        self.root = self.root.resolve()
        self.code = self.root / 'current engine'
        script = self.code / 'Scripts/Build/build_rom.sh'
        script.parent.mkdir(parents=True)
        script.write_text('# fixture compiler; never executed\n')
        self.rom = self.root / 'saved editing rom'
        self.rom.write_bytes(b'actual saved ROM fixture')
        self.target = self.code / 'Roms/oos178x.sfc'
        self.project = self.root / 'project.yaze'
        self.text = ('[files]\ncode_folder=current engine\n'
            'rom_filename=saved editing rom\nrom_backup_folder=backups\n'
            'output_folder=current engine/Roms\nlyra_terrain_file=\n'
            'hack_manifest_file=current engine/Roms/hack_manifest.json\n'
            'lyra_build_request_file=\nnative_save_producer_file=transfer/producer.json\n'
            'native_save_transfer_proof_file=transfer/proof.json\n'
            '[rom]\nexpected_hash=unchanged-identity\nwrite_policy=block\n'
            '[build]\nbuild_target=current engine/Roms/oos178x.sfc\n'
            'output_folder=current engine/Roms\n')
        self.project.write_text(self.text)
        self.env = dict(YAZE_PROJECT_FILE=str(self.project),
            YAZE_PROJECT_CODE_FOLDER=str(self.code), YAZE_PROJECT_ROM=str(self.rom),
            YAZE_PROJECT_OUTPUT=str(self.target),
            YAZE_NATIVE_SAVE_RECEIPT='current committed receipt',
            YAZE_NATIVE_SAVE_CONTEXT='current save context',
            OOS_Z3ED_BIN='matching producer CLI')

    def invoke(self, exit_code=0, *, cli_args=None, **features):
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(
                B.subprocess, 'run', return_value=SimpleNamespace(returncode=exit_code)) as run:
            result = (B.build_project(self.project, **features) if cli_args is None else
                      B.main(['--project', str(self.project), *cli_args]))
        return result, run

    def test_cli_profile_b_forwards_exact_168_command_and_preserves_controls(self):
        self.text = self.text.replace('oos178x.sfc', 'oos168x.sfc')
        self.project.write_text(self.text)
        self.target = self.code / 'Roms/oos168x.sfc'
        self.env['YAZE_PROJECT_OUTPUT'] = str(self.target)
        enabled = ('d8_boss,d3_prison_sequence,minecart_cart_shutters,'
                   'ocarina_song_tint,ow_aux_extension')
        result, run = self.invoke(19, cli_args=[
            '--enable', enabled, '--disable', 'kalyxo_docks_profile'])
        self.assertEqual(result, 19)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], [
            'bash', str(self.code / 'Scripts/Build/build_rom.sh'), '168',
            '--enable', enabled, '--disable', 'kalyxo_docks_profile'])
        self.assertEqual(run.call_args.kwargs['cwd'], self.root)
        self.assertFalse(run.call_args.kwargs['check'])
        forwarded = run.call_args.kwargs['env']
        for key, value in self.env.items():
            self.assertEqual(forwarded[key], value)
        self.assertNotIn('OOS_BASE_ROM', forwarded)
        self.assertEqual(forwarded['OOS_MANIFEST_ROOT'], str(self.root))
        self.assertEqual(forwarded['OOS_MANIFEST_OUTPUT'],
                         str(self.target.with_suffix('.manifest.json')))
        self.assertEqual(self.project.read_text(), self.text)
        self.assertEqual(self.rom.read_bytes(), b'actual saved ROM fixture')

    def test_cli_default_and_empty_selections_keep_original_child_command(self):
        for args in ([], ['--enable', '', '--disable', '']):
            with self.subTest(args=args):
                result, run = self.invoke(cli_args=args)
                self.assertEqual(result, 0)
                self.assertEqual(run.call_args.args[0], [
                    'bash', str(self.code / 'Scripts/Build/build_rom.sh'), '178'])
        _, run = self.invoke(enable='', disable='')
        self.assertEqual(run.call_args.args[0][-1], '178')

    def test_api_csv_passes_feature_spelling_and_overlap_to_compiler(self):
        # The compiler discovers feature names and already defines precedence.
        # Keep these as literal argv values, with no registry or shell parsing.
        enabled = 'future-feature,ENABLE_D8_BOSS;literal'
        result, run = self.invoke(2, enable=enabled, disable='d8_boss')
        self.assertEqual(result, 2)
        self.assertEqual(run.call_args.args[0][-4:], [
            '--enable', enabled, '--disable', 'd8_boss'])

    def test_saved_page_tile16_opt_in_selects_experimental_compiler_build(self):
        for value in ('true', '1', 'yes', ' true '):
            with self.subTest(value=value):
                self.project.write_text(
                    self.text + f'[feature_flags]\nexperimental_page_tile16={value}\n')
                result, run = self.invoke(cli_args=[
                    '--enable', 'sky_overworld_graphics', '--disable', 'kalyxo_docks_profile'])
                self.assertEqual(result, 0)
                self.assertEqual(run.call_args.args[0], [
                    'bash', str(self.code / 'Scripts/Build/build_rom.sh'), '178',
                    '--enable', 'sky_overworld_graphics',
                    '--disable', 'kalyxo_docks_profile', '--experimental-page-tile16'])

    def test_absent_or_other_page_tile16_values_keep_ordinary_build(self):
        for section in ('', '[feature_flags]\nexperimental_page_tile16=false\n',
                        '[feature_flags]\nexperimental_page_tile16=True\n',
                        '[feature_flags]\nexperimental_page_tile16=\n',
                        '[feature_flags]\nload_custom_overworld=true\n'):
            with self.subTest(section=section):
                self.project.write_text(self.text + section)
                result, run = self.invoke()
                self.assertEqual(result, 0)
                self.assertEqual(run.call_args.args[0], [
                    'bash', str(self.code / 'Scripts/Build/build_rom.sh'), '178'])

    def test_page_tile16_opt_in_cannot_bypass_saved_input_admission(self):
        self.project.write_text(self.text + '[feature_flags]\nexperimental_page_tile16=true\n')
        self.env['YAZE_PROJECT_ROM'] = str(self.root / 'foreign')
        with mock.patch('sys.stderr', new_callable=io.StringIO) as errors:
            result, run = self.invoke(cli_args=[])
        self.assertEqual(result, 2)
        self.assertIn('YAZE_PROJECT_ROM differs', errors.getvalue())
        run.assert_not_called()

    def test_cli_feature_selection_cannot_bypass_saved_input_admission(self):
        self.env['YAZE_PROJECT_ROM'] = str(self.root / 'foreign')
        with mock.patch('sys.stderr', new_callable=io.StringIO) as errors:
            result, run = self.invoke(cli_args=['--enable', 'd8_boss'])
        self.assertEqual(result, 2)
        self.assertIn('YAZE_PROJECT_ROM differs', errors.getvalue())
        run.assert_not_called()
        self.assertEqual(self.project.read_text(), self.text)
        self.assertEqual(self.rom.read_bytes(), b'actual saved ROM fixture')

    def test_cli_feature_selection_cannot_bypass_manifest_admission(self):
        self.env['OOS_MANIFEST_OUTPUT'] = str(self.code / 'Roms/hack_manifest.json')
        with mock.patch('sys.stderr', new_callable=io.StringIO) as errors:
            result, run = self.invoke(cli_args=['--disable', 'kalyxo_docks_profile'])
        self.assertEqual(result, 2)
        self.assertIn('OOS_MANIFEST_OUTPUT differs', errors.getvalue())
        run.assert_not_called()

    def test_cli_feature_option_requires_a_value_before_adapter_runs(self):
        with mock.patch.object(B, 'build_project') as build, \
                mock.patch('sys.stderr', new_callable=io.StringIO), \
                self.assertRaises(SystemExit) as error:
            B.main(['--project', str(self.project), '--enable'])
        self.assertEqual(error.exception.code, 2)
        build.assert_not_called()

    def test_current_bindings_delegate_exact_rom_and_version_preserving_controls(self):
        result, run = self.invoke(7)
        self.assertEqual(result, 7)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ['bash', str(self.code / 'Scripts/Build/build_rom.sh'), '178'])
        self.assertEqual(kwargs['cwd'], self.root)
        self.assertFalse(kwargs['check'])
        env = kwargs['env']
        for key, value in self.env.items():
            self.assertEqual(env[key], value)
        self.assertNotIn('OOS_BASE_ROM', env)
        self.assertEqual(env['OOS_MANIFEST_ROOT'], str(self.root))
        self.assertEqual(env['OOS_MANIFEST_OUTPUT'],
                         str(self.target.with_suffix('.manifest.json')))
        self.assertEqual(env['OOS_BACKUP_ROOT'], str(self.root / 'backups'))
        self.assertEqual(self.project.read_text(), self.text)
        self.assertEqual(self.rom.read_bytes(), b'actual saved ROM fixture')

    def test_direct_project_invocation_derives_same_paths_without_environment(self):
        self.env.clear()
        _, run = self.invoke()
        self.assertEqual(run.call_args.kwargs['env']['YAZE_PROJECT_ROM'], str(self.rom))
        self.assertEqual(run.call_args.args[0][-1], '178')

    def test_sibling_descriptor_keeps_bound_source_namespace_and_controls(self):
        original = self.project
        sibling = self.root.parent / 'saved descriptor with spaces'
        sibling.mkdir()
        self.project = sibling / 'saved-native.yaze'
        moved = self.text.replace('current engine',
                                 os.path.relpath(self.code, sibling))
        moved = moved.replace('rom_filename=saved editing rom',
            'rom_filename=' + os.path.relpath(self.rom, sibling))
        moved = moved.replace('rom_backup_folder=backups',
            'rom_backup_folder=' + os.path.relpath(self.root / 'backups', sibling))
        self.project.write_text(moved)
        self.env['YAZE_PROJECT_FILE'] = str(self.project)
        for explicit in (False, True):
            with self.subTest(explicit_namespace=explicit):
                if explicit:
                    self.env['OOS_MANIFEST_ROOT'] = str(self.root)
                _, run = self.invoke()
                forwarded = run.call_args.kwargs['env']
                self.assertEqual(forwarded['OOS_MANIFEST_ROOT'], str(self.root))
                self.assertTrue(self.code.is_relative_to(Path(forwarded['OOS_MANIFEST_ROOT'])))
                self.assertTrue(self.rom.is_relative_to(Path(forwarded['OOS_MANIFEST_ROOT'])))
                self.assertEqual(run.call_args.kwargs['cwd'], sibling)
                for key, value in self.env.items():
                    self.assertEqual(forwarded[key], value)
                self.assertNotIn('OOS_BASE_ROM', forwarded)
                self.assertEqual(forwarded['OOS_MANIFEST_OUTPUT'],
                                 str(self.target.with_suffix('.manifest.json')))
        self.assertEqual(original.read_text(), self.text)
        self.assertEqual(self.project.read_text(), moved)
        self.assertEqual(self.rom.read_bytes(), b'actual saved ROM fixture')

    def test_rom_inside_source_uses_source_namespace(self):
        nested = self.code / 'editing.sfc'
        nested.write_bytes(self.rom.read_bytes())
        self.project.write_text(self.text.replace('rom_filename=saved editing rom',
                                                 'rom_filename=current engine/editing.sfc'))
        self.env['YAZE_PROJECT_ROM'] = str(nested)
        _, run = self.invoke()
        self.assertEqual(run.call_args.kwargs['env']['OOS_MANIFEST_ROOT'], str(self.code))

    def test_manifest_namespace_conflicts_and_unrelated_rom_refuse_before_child(self):
        for namespace in (self.root.parent, self.code, self.root / 'foreign'):
            with self.subTest(namespace=namespace), mock.patch.dict(os.environ,
                    dict(self.env, OOS_MANIFEST_ROOT=str(namespace)), clear=True), \
                    mock.patch.object(B.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'OOS_MANIFEST_ROOT differs'):
                    B.build_project(self.project)
                run.assert_not_called()
        unrelated = self.root.parent / 'unrelated.sfc'
        unrelated.write_bytes(b'foreign owner ROM')
        self.project.write_text(self.text.replace('rom_filename=saved editing rom',
                                                 'rom_filename=' + str(unrelated)))
        self.env['YAZE_PROJECT_ROM'] = str(unrelated)
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(B.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'ROM must belong to the source namespace'):
                B.build_project(self.project)
            run.assert_not_called()

    def test_filesystem_root_cannot_be_manifest_namespace(self):
        self.project.write_text(self.text.replace('code_folder=current engine',
                                                 'code_folder=/').replace(
            'rom_filename=saved editing rom', 'rom_filename=/editing.sfc').replace(
            'current engine/Roms', '/Roms'))
        self.env.update(YAZE_PROJECT_CODE_FOLDER='/', YAZE_PROJECT_ROM='/editing.sfc',
                        YAZE_PROJECT_OUTPUT='/Roms/oos178x.sfc')
        # Supply only the preceding file-existence precondition; no root files
        # are created and the compiler must remain uncalled.
        with mock.patch.object(Path, 'is_file', return_value=True), \
                mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(B.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'never the filesystem root'):
                B.build_project(self.project)
            run.assert_not_called()

    def test_legacy_sidecar_and_request_refuse_before_child(self):
        for key in ('lyra_terrain_file', 'lyra_build_request_file'):
            self.project.write_text(self.text.replace(key + '=\n', key + '=legacy.json\n'))
            with self.subTest(key=key), mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(B.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'legacy ' + key):
                    B.build_project(self.project)
                run.assert_not_called()

    def test_stale_project_environment_cannot_select_different_inputs(self):
        for key in ('YAZE_PROJECT_FILE', 'YAZE_PROJECT_CODE_FOLDER',
                    'YAZE_PROJECT_ROM', 'YAZE_PROJECT_OUTPUT'):
            env = dict(self.env, **{key: str(self.root / 'different')})
            with self.subTest(key=key), mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(B.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, key + ' differs'):
                    B.build_project(self.project)
                run.assert_not_called()

    def test_legacy_environment_refuses_without_rewriting_project(self):
        for key in ('YAZE_LYRA_TERRAIN_FILE', 'OOS_LYRA_PROJECT', 'OOS_LYRA_REQUEST'):
            with self.subTest(key=key), mock.patch.dict(os.environ,
                    dict(self.env, **{key: 'legacy'}), clear=True):
                with self.assertRaisesRegex(ValueError, 'legacy ' + key):
                    B.build_project(self.project)
        self.assertEqual(self.project.read_text(), self.text)

    def test_target_placement_cannot_claim_unrelated_or_alias_output(self):
        for target in ('output/other.sfc', 'current engine/Roms/other.sfc'):
            self.project.write_text(self.text.replace(
                'current engine/Roms/oos178x.sfc', target))
            self.env.pop('YAZE_PROJECT_OUTPUT', None)
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'Build target must'):
                self.invoke()
        self.project.write_text(self.text)
        self.target.parent.mkdir()
        self.target.hardlink_to(self.rom)
        with self.assertRaisesRegex(ValueError, 'aliases'):
            self.invoke()

    def test_explicit_base_must_still_match_saved_rom(self):
        other = self.root / 'foreign source'
        other.write_bytes(b'foreign')
        self.env['OOS_BASE_ROM'] = str(other)
        with self.assertRaisesRegex(ValueError, 'OOS_BASE_ROM differs'):
            self.invoke()
        self.env['OOS_BASE_ROM'] = str(self.rom)
        _, run = self.invoke()
        self.assertEqual(run.call_args.kwargs['env']['OOS_BASE_ROM'], str(self.rom))

    def test_missing_script_and_mismatched_output_folder_refuse(self):
        script = self.code / 'Scripts/Build/build_rom.sh'
        script.unlink()
        with self.assertRaisesRegex(ValueError, 'build script is missing'):
            self.invoke()
        script.write_text('# restored fixture\n')
        self.project.write_text(self.text.replace('output_folder=current engine/Roms',
                                                  'output_folder=foreign'))
        with self.assertRaisesRegex(ValueError, 'output_folder differs'):
            self.invoke()

    def test_foreign_compiled_manifest_override_refuses_before_child(self):
        self.env['OOS_MANIFEST_OUTPUT'] = str(self.code / 'Roms/hack_manifest.json')
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(B.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'OOS_MANIFEST_OUTPUT differs'):
                B.build_project(self.project)
            run.assert_not_called()

    def test_compiled_manifest_aliases_cannot_overwrite_policy_or_receipts(self):
        policy = self.code / 'Roms/hack_manifest.json'
        policy.parent.mkdir()
        policy.write_text('saved editor policy')
        manifest = self.target.with_suffix('.manifest.json')
        for kind in ('symlink', 'hardlink'):
            if kind == 'symlink':
                manifest.symlink_to(policy)
            else:
                manifest.hardlink_to(policy)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError,
                    'Compiled manifest must'):
                self.invoke()
            self.assertEqual(policy.read_text(), 'saved editor policy')
            manifest.unlink()
        self.env['OOS_BUILD_RECEIPT'] = str(manifest)
        with self.assertRaisesRegex(ValueError, 'aliases project policy or saved inputs'):
            self.invoke()
        self.env.pop('OOS_BUILD_RECEIPT')
        self.project.write_text(self.text.replace(
            'hack_manifest_file=current engine/Roms/hack_manifest.json',
            'hack_manifest_file=current engine/Roms/oos178x.manifest.json'))
        with self.assertRaisesRegex(ValueError, 'aliases project policy or saved inputs'):
            self.invoke()


    def source_graphics_fixture(self, *, d4=False):
        generate = Path(B.__file__).resolve().parents[1] / 'Generate'
        sys.path.insert(0, str(generate))
        try:
            import sheet_overrides as sheets
            import sheet_codec as codec
            import sheet_table as table
            import lz2
        finally:
            sys.path.pop(0)
        self.sheets, self.codec = sheets, codec
        self.spec_path = self.code / (sheets.D4_SPEC if d4 else sheets.SPEC)
        self.art = self.code / 'Data/graphics/gEB.txt'
        self.art.parent.mkdir(parents=True)
        self.grid = [[6] * 128 for _ in range(32)]
        self.art.write_text(codec.grid_to_text(self.grid))
        self.source_spec = dict(schema_version=2, start='0x40D000', capacity=12288,
            encoding='lz2', sheets=[dict(global_sheet='0xEB', source='gEB.txt',
                decoded_sha256=hashlib.sha256(codec.grid_to_sheet(self.grid)).hexdigest(),
                flag='ENABLE_SKY_OVERWORLD_GRAPHICS', why='source Save workflow fixture')])
        (self.code / 'Util').mkdir()
        (self.code / 'Config').mkdir()
        (self.code / 'Util/macros.asm').write_text(
            '!ENABLE_SOURCE_SPRITE_SHEETS = 1\n!ENABLE_D4_ZORA_REDESIGN = ' + str(int(d4)) +
            '\n!ENABLE_SKY_OVERWORLD_GRAPHICS = 1\n')
        (self.code / 'Oracle_main.asm').write_text('RTL\n')
        world = self.code / 'Overworld/world_map'
        world.mkdir(parents=True)
        for name in ('LwMapTileset.bin', 'LwMapGfx.bin'):
            (world / name).write_bytes(b'')
        (self.art.parent / 'd4_zora').mkdir()
        (self.art.parent / 'd4_zora/frames.asm').write_text('; native D4 frame fixture\n')
        rom = bytearray(0x400000)
        stream = lz2.stored(bytes(1536))
        rom[0x10000:0x10000 + len(stream)] = stream
        for g in range(223):
            for address, value in ((table.TBL_BANK, 0x82), (table.TBL_HIGH, 0x80), (table.TBL_LOW, 0)):
                rom[table.pc(address) + g] = value
        self.rom.write_bytes(rom)
        self.output = self.code / (sheets.D4_OUTPUT if d4 else sheets.OUTPUT)
        self.saved_graphics_spec()

    def saved_graphics_spec(self):
        self.source_spec['sheets'][0]['decoded_sha256'] = hashlib.sha256(
            self.codec.grid_to_sheet(self.grid)).hexdigest()
        for name in (self.sheets.SPEC, self.sheets.D4_SPEC):
            (self.code / name).write_text(json.dumps(self.source_spec))
        self.project.write_text(self.text + '[graphics_sheets]\nsource_spec=' +
            self.spec_path.relative_to(self.code).as_posix() + '\nsource_spec_sha1=' +
            hashlib.sha1(self.spec_path.read_bytes()).hexdigest() + '\n')

    def prepare_graphics(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            return B.prepare_source_graphics(self.project, self.rom, compiler_root=self.code)

    def test_source_save_refreshes_stale_generated_bytes_for_both_canonical_specs(self):
        # Real codec/generator inputs and output: edit+saved spec must reach the
        # compressed stream and pointer include before the ordinary check.
        for d4 in (False, True):
            if d4:
                # Reuse the same fixture with current build flags selecting D4.
                self.spec_path = self.code / self.sheets.D4_SPEC
                (self.code / 'Util/macros.asm').write_text(
                    '!ENABLE_SOURCE_SPRITE_SHEETS = 1\n!ENABLE_D4_ZORA_REDESIGN = 1\n!ENABLE_SKY_OVERWORLD_GRAPHICS = 1\n')
                self.output = self.code / self.sheets.D4_OUTPUT
                self.saved_graphics_spec()
            else:
                self.source_graphics_fixture()
            self.assertEqual(self.prepare_graphics(), 0)
            before = {str(p.relative_to(self.output)): p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
            self.grid[0][0] ^= 1
            self.art.write_text(self.codec.grid_to_text(self.grid))
            self.saved_graphics_spec()
            spec, items = self.sheets.build(self.spec_path, self.rom, self.code)
            frames = (self.code / 'Data/graphics/d4_zora/frames.asm').read_bytes() if d4 else None
            expected = self.sheets.generated_files(items, frames)
            self.assertTrue(any(before.get(str(name)) != value for name, value in expected.items()))
            check_command = [sys.executable, '-B', str(Path(self.sheets.__file__)),
                '--root', str(self.code), '--base-rom', str(self.rom),
                '--rom-role', 'editable_base', '--check', '--respect-flags']
            stale = subprocess.run(check_command, capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn('stale generated sprite sheets:', stale.stderr)
            rom_before = self.rom.read_bytes()
            self.assertEqual(self.prepare_graphics(), 0)
            self.assertTrue(all((self.output / name).read_bytes() == value for name, value in expected.items()))
            self.assertEqual(self.rom.read_bytes(), rom_before)
            checked = subprocess.run(check_command, capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_current_or_unselected_graphics_never_publish_generated_files(self):
        self.source_graphics_fixture()
        self.prepare_graphics()
        with mock.patch.object(self.sheets, 'write_outputs') as publish:
            self.assertEqual(self.prepare_graphics(), 0)
            flags = self.code / 'Util/macros.asm'
            flags.write_text(flags.read_text().replace('SOURCE_SPRITE_SHEETS = 1', 'SOURCE_SPRITE_SHEETS = 0'))
            self.assertEqual(self.prepare_graphics(), 0)
            self.project.write_text(self.text)  # Main's unselected source context.
            self.assertEqual(self.prepare_graphics(), 0)
            publish.assert_not_called()

    def test_nested_generated_parent_symlink_refuses_before_external_write(self):
        self.source_graphics_fixture()
        self.output.mkdir(parents=True)
        external = self.root / 'external generated files'
        external.mkdir()
        sentinel = external / 'gEB_sky_overworld_graphics.bin'
        sentinel.write_bytes(b'preserve external stream')
        (self.output / 'sheets').symlink_to(external, target_is_directory=True)
        before = {p.name: p.read_bytes() for p in external.iterdir()}
        with mock.patch.object(self.sheets, 'write_outputs') as publish:
            with self.assertRaisesRegex(ValueError, 'destination redirects'):
                self.prepare_graphics()
            publish.assert_not_called()
        self.assertEqual({p.name: p.read_bytes() for p in external.iterdir()}, before)
        self.assertFalse((self.output / 'sheet_overrides.asm').exists())

    def test_source_graphics_binding_refusals_happen_before_publication(self):
        self.source_graphics_fixture()
        self.prepare_graphics()
        original = self.project.read_text()
        variants = [
            ('source_spec_sha1=', 'source_spec_sha1=stale', 'SHA1'),
            ('source_spec=Data/graphics/source_sprite_sheets.json', 'source_spec=../foreign.json', 'canonical'),
            ('code_folder=current engine', 'code_folder=foreign', 'YAZE_PROJECT_CODE_FOLDER differs'),
            ('rom_filename=saved editing rom', 'rom_filename=foreign.sfc', 'YAZE_PROJECT_ROM differs')]
        with mock.patch.object(self.sheets, 'write_outputs') as publish:
            for old, new, error in variants:
                with self.subTest(error=error):
                    self.project.write_text(original.replace(old, new))
                    with self.assertRaisesRegex(ValueError, error):
                        self.prepare_graphics()
            self.project.write_text(original)
            with mock.patch.dict(os.environ, self.env, clear=True), self.assertRaisesRegex(ValueError, 'actual compiler root'):
                B.prepare_source_graphics(self.project, self.rom, compiler_root=self.root)
            foreign = self.root / 'foreign.sfc'
            foreign.write_bytes(self.rom.read_bytes())
            with mock.patch.dict(os.environ, self.env, clear=True), self.assertRaisesRegex(ValueError, 'base ROM differs'):
                B.prepare_source_graphics(self.project, foreign, compiler_root=self.code)
            (self.code / 'Util/macros.asm').write_text('!ENABLE_SOURCE_SPRITE_SHEETS = 1\n!ENABLE_D4_ZORA_REDESIGN = 1\n')
            with self.assertRaisesRegex(ValueError, 'current build flags'):
                self.prepare_graphics()
            publish.assert_not_called()

    def test_shell_preparation_failure_remains_one_required_check_and_skips_check_command(self):
        build = Path(B.__file__).with_name('build_rom.sh').read_text()
        function = build[build.index('check_source_sprite_sheets() {'):]
        function = function[:function.index('\nrun_check source_sprite_sheets')]
        checks = Path(B.__file__).with_name('build_checks.sh')
        script = ('source "$1"\nrecord_check() { :; }\n' + function + '\n' +
            'python3() { if [[ " $* " == *" --prepare-source-graphics "* ]]; then return 37; '
            'else printf "%s" "$*" > "$fixture_dir/check-command"; return 41; fi; }\n'
            'repo_root="$2"; fixture_dir="$2"; base_rom="$2/base"; YAZE_PROJECT_FILE="$2/project"\n'
            'run_check source_sprite_sheets 1 check_source_sprite_sheets\n')
        result = subprocess.run(['bash', '-c', script, 'fixture', str(checks), str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertIn('required=1', result.stderr)
        self.assertFalse((self.root / 'check-command').exists())
        prepared = script.replace('then return 37;', 'then return 0;')
        result = subprocess.run(['bash', '-c', prepared, 'fixture', str(checks), str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 41, result.stderr)
        self.assertIn('--check --respect-flags', (self.root / 'check-command').read_text())
        ordinary = script.replace('YAZE_PROJECT_FILE="$2/project"', 'YAZE_PROJECT_FILE=')
        result = subprocess.run(['bash', '-c', ordinary, 'fixture', str(checks), str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 41, result.stderr)
        self.assertIn('--check --respect-flags', (self.root / 'check-command').read_text())
        self.assertEqual(build.count('run_check source_sprite_sheets 1'), 1)


if __name__ == '__main__':
    unittest.main()
