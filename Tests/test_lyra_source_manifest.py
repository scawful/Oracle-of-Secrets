"""Portable manifest proof using a disposable Git source and copied files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import lyra_source_manifest as manifest


class PortableSourceManifestTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lyra-source-manifest-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.checkout = self.root / 'checkout'
        self.checkout.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        self.git('init', '-q')
        (self.checkout / 'src').mkdir()
        (self.checkout / 'src/engine.asm').write_bytes(b'original engine\n')
        (self.checkout / 'src/data.bin').write_bytes(b'original data\0')
        self.git('add', 'src/engine.asm', 'src/data.bin')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'fixture source')
        self.head = self.git('rev-parse', 'HEAD').decode().strip()
        self.paths = ['src/engine.asm', 'src/data.bin']
        self.raw = manifest.create_for_checkout(self.checkout, self.head, self.paths)
        self.trusted = hashlib.sha256(self.raw).hexdigest()
        self.snapshot = self.root / 'exported-project'
        self.snapshot.mkdir()
        shutil.copytree(self.checkout / 'src', self.snapshot / 'src')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.checkout), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env).stdout

    def verify(self, raw=None, trusted=None, head=None, paths=None):
        return manifest.verify_snapshot(self.snapshot, self.raw if raw is None else raw,
            trusted_sha256=self.trusted if trusted is None else trusted,
            engine_head=self.head if head is None else head,
            source_closure=self.paths if paths is None else paths)

    def test_git_bound_manifest_verifies_relocated_copy_without_git(self):
        self.assertFalse((self.snapshot / '.git').exists())
        result = self.verify()
        self.assertEqual(result['engine_head'], self.head)
        self.assertEqual(result['files_verified'], 2)
        self.assertEqual(result['manifest_sha256'], self.trusted)

    def test_edited_copy_and_self_modified_manifest_are_refused(self):
        (self.snapshot / 'src/engine.asm').write_bytes(b'changed engine\n')
        with self.assertRaisesRegex(ValueError, 'differs from reviewed manifest'):
            self.verify()
        document = json.loads(self.raw)
        document['files'][1]['sha256'] = '0' * 64
        changed = (json.dumps(document, sort_keys=True, separators=(',', ':')) + '\n').encode()
        with self.assertRaisesRegex(ValueError, 'trusted authority'):
            self.verify(raw=changed)

    def test_wrong_revision_or_incomplete_closure_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'identity or canonical'):
            self.verify(head='f' * 40)
        with self.assertRaisesRegex(ValueError, 'complete source closure'):
            self.verify(paths=['src/engine.asm'])
        with self.assertRaisesRegex(ValueError, 'case-conflicting'):
            self.verify(paths=['src/engine.asm', 'src/ENGINE.asm'])
        with self.assertRaisesRegex(ValueError, 'noncanonical'):
            self.verify(paths=['src/../outside'])

    def test_changed_checkout_cannot_create_a_committed_manifest(self):
        (self.checkout / 'src/engine.asm').write_bytes(b'uncommitted change')
        with self.assertRaisesRegex(ValueError, 'differs from selected commit'):
            manifest.create_for_checkout(self.checkout, self.head, self.paths)

    @unittest.skipIf(os.name == 'nt', 'Git symlink creation requires Windows privileges')
    def test_committed_symlink_cannot_be_replaced_with_regular_file(self):
        link = self.checkout / 'src/link'
        link.symlink_to('target')
        self.git('add', 'src/link')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'symlink fixture')
        head = self.git('rev-parse', 'HEAD').decode().strip()
        link.unlink()
        link.write_bytes(b'target')
        with self.assertRaisesRegex(ValueError, 'unique regular file'):
            manifest.create_for_checkout(self.checkout, head, ['src/link'])

    @unittest.skipIf(os.name == 'nt', 'Windows does not expose POSIX executable bits')
    def test_executable_mode_change_is_refused(self):
        path = self.snapshot / 'src/engine.asm'
        path.chmod(path.stat().st_mode | 0o111)
        with self.assertRaisesRegex(ValueError, 'executable mode differs'):
            self.verify()

    def test_change_to_earlier_file_during_scan_is_refused(self):
        read_source = manifest._read_source
        changed = False
        def change_during_scan(root, relative, *, mode):
            nonlocal changed
            content = read_source(root, relative, mode=mode)
            if relative == 'src/engine.asm' and not changed:
                changed = True
                (self.snapshot / 'src/data.bin').write_bytes(b'changed after read')
            return content
        with mock.patch.object(manifest, '_read_source', side_effect=change_during_scan):
            with self.assertRaisesRegex(ValueError, 'differs from reviewed manifest'):
                self.verify()

    def test_symlink_in_snapshot_is_refused(self):
        path = self.snapshot / 'src/engine.asm'
        path.unlink()
        try:
            path.symlink_to(self.checkout / 'src/engine.asm')
        except OSError as error:
            self.skipTest(f'symlink unavailable: {error}')
        with self.assertRaisesRegex(ValueError, 'escaped the engine or uses a symlink'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
