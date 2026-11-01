"""Build wrapper admission controls using disposable, non-ROM inputs."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import authoring_bundle_build as bundle
import lyra_project_publisher as publisher


class BundleAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.engine = self.root / 'project'
        script = self.engine / 'Scripts' / 'Build' / 'build_rom.sh'
        script.parent.mkdir(parents=True)
        script.write_text('# fixture: subprocess must be mocked\n')
        (self.root / 'input.bin').write_bytes(b'fixture')
        (self.root / 'terrain.json').write_text('{}')
        self.descriptor = self.root / 'fixture.yaze'

    def write_project(self, request='', terrain='terrain.json'):
        self.descriptor.write_text(
            '[rom]\nrole=dev\n[files]\nrom_filename=input.bin\n'
            f'lyra_terrain_file={terrain}\nlyra_build_request_file={request}\n'
        )

    def test_missing_request_stops_before_build(self):
        self.write_project()
        with mock.patch.object(bundle.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'lyra_build_request_file'):
                bundle.build_project(self.descriptor)
        run.assert_not_called()

    def test_unrecognized_request_stops_before_build(self):
        (self.root / 'request.json').write_text('{}')
        self.write_project(request='request.json')
        with mock.patch.object(bundle.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'CURRENT_BUILD_REQUEST_REQUIRED'):
                bundle.build_project(self.descriptor)
        run.assert_not_called()

    def test_wrong_reviewed_engine_stops_before_build(self):
        self.write_project()
        wrong_engine = self.root / 'other-engine'
        wrong_engine.mkdir()
        target = {'engine': str(wrong_engine), 'base_rom': 'ignored',
                  'request': 'ignored', 'candidate': 'ignored'}
        with (mock.patch.object(publisher, 'resolve_current_target', return_value=target),
              mock.patch.object(bundle.subprocess, 'run') as run):
            with self.assertRaisesRegex(ValueError, 'differs from this bundled build engine'):
                bundle.build_project(self.descriptor)
        run.assert_not_called()

    def test_native_build_does_not_inherit_lyra_selection(self):
        self.write_project(terrain='')
        inherited = {key: 'stale-selection' for key in (
            'OOS_LYRA_PROJECT', 'OOS_LYRA_REQUEST',
            'OOS_LYRA_BUILD_CONTEXT', 'OOS_LYRA_CANDIDATE')}
        with (mock.patch.dict(os.environ, inherited),
              mock.patch.object(bundle.subprocess, 'run', return_value=mock.Mock(returncode=7)) as run):
            self.assertEqual(bundle.build_project(self.descriptor), 7)
        environment = run.call_args.kwargs['env']
        self.assertTrue(inherited.keys().isdisjoint(environment))
        self.assertEqual(environment['OOS_BASE_ROM'], 'rom')
        self.assertEqual(run.call_args.kwargs['cwd'], self.root)


if __name__ == '__main__':
    unittest.main()
