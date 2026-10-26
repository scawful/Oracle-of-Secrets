"""Tests for the non-emulator parts of Scripts/Validate/t2kit.

Fixture registry, verdict table, heavy lock context manager (pointed at a
temporary lock path), ROM copy naming and the route finder. No Mesen, no AFS.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

VALIDATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VALIDATE))

from t2kit import DungeonTiles, load_fixture, load_registry, rect, room_origin  # noqa: E402
from t2kit import lock as t2lock  # noqa: E402
from t2kit.fixtures import sha256  # noqa: E402
from t2kit.report import failed_checks, outcome, table, verdict  # noqa: E402
from t2kit.session import safe_name  # noqa: E402


def result(passed, failed=0, state='complete', error=None):
    checks = [{'name': f'ok {i}', 'matches_expectation': True} for i in range(2)]
    checks += [{'name': f'bad {i}', 'matches_expectation': False} for i in range(failed)]
    out = {'passed': passed, 'state': state, 'checks': checks}
    if error:
        out['error'] = error
    return out


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.srm = self.root / 'save.srm'
        self.srm.write_bytes(b'\x00' * 0x2000)
        self.reg = self.root / 'fixtures.json'
        self.write({'save': {'path': str(self.srm), 'sha256': sha256(self.srm), 'file_slot': 2,
                             'contains': 'test save'}})

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        self.reg.write_text(json.dumps(data))

    def test_load_and_verify(self):
        fx = load_fixture('save', registry=self.reg)
        self.assertEqual((fx.path, fx.file_slot), (self.srm, 2))

    def test_unknown_name(self):
        with self.assertRaises(KeyError):
            load_fixture('missing', registry=self.reg)

    def test_missing_key_and_bad_slot(self):
        self.write({'save': {'path': 'x', 'sha256': 'y', 'file_slot': 2}})
        with self.assertRaisesRegex(ValueError, 'missing'):
            load_registry(self.reg)
        self.write({'save': {'path': 'x', 'sha256': 'y', 'file_slot': 4, 'contains': ''}})
        with self.assertRaisesRegex(ValueError, 'file_slot'):
            load_registry(self.reg)

    def test_hash_mismatch_and_srm_override(self):
        other = self.root / 'other.srm'
        other.write_bytes(b'\x01' * 0x2000)
        with self.assertRaisesRegex(ValueError, 'sha256'):
            load_fixture('save', srm=other, registry=self.reg)
        copy = self.root / 'copy.srm'
        copy.write_bytes(self.srm.read_bytes())
        self.assertEqual(load_fixture('save', srm=copy, registry=self.reg).path, copy)

    def test_missing_file(self):
        self.srm.unlink()
        with self.assertRaises(FileNotFoundError):
            load_fixture('save', registry=self.reg)

    def test_shipped_registry_is_valid(self):
        reg = load_registry()
        self.assertIn('goron-mines-open', reg)
        for fx in reg.values():
            self.assertEqual(len(fx.sha256), 64)


class ReportTest(unittest.TestCase):
    def test_outcome(self):
        self.assertEqual(outcome(None), '-')
        self.assertEqual(outcome(result(True)), 'PASS')
        self.assertEqual(outcome(result(False, failed=2)), 'FAIL (2)')
        self.assertEqual(outcome(result(False, state='error', error='boom')), 'ERROR')

    def test_verdict(self):
        ok, bad = result(True), result(False, failed=1)
        self.assertEqual(verdict(None, ok), 'not run')
        self.assertEqual(verdict(ok, None), 'pass')
        self.assertEqual(verdict(bad, None), 'FAIL')
        self.assertEqual(verdict(ok, ok), 'pass (control also passes)')
        self.assertEqual(verdict(ok, bad), 'pass (control fails)')
        self.assertEqual(verdict(bad, ok), 'REGRESSION (control passes)')
        self.assertEqual(verdict(bad, bad), 'FAIL (control also fails)')

    def test_table(self):
        rows = [{'case': 'a', 'candidate': result(True), 'control': result(False, failed=1)},
                {'case': 'b', 'candidate': result(True), 'control': None}]
        self.assertEqual(table(rows).splitlines(), [
            '| case | candidate | control | verdict |',
            '|---|---|---|---|',
            '| a | PASS | FAIL (1) | pass (control fails) |',
            '| b | PASS | - | pass |'])

    def test_failed_checks(self):
        self.assertEqual(failed_checks(None), [])
        self.assertEqual(failed_checks(result(False, failed=1, error='boom')), ['bad 0', 'boom'])


class LockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hl = t2lock.heavy_lock_module()
        self.saved = (self.hl.LOCK, self.hl.ARCHIVE)
        self.hl.LOCK = Path(self.tmp.name) / 'oos-heavy.lock'
        self.hl.ARCHIVE = Path(self.tmp.name) / 'reclaimed'

    def tearDown(self):
        self.hl.LOCK, self.hl.ARCHIVE = self.saved
        self.tmp.cleanup()

    def test_acquire_and_release(self):
        with t2lock.heavy_lock('t2kit-test', 'unit test', wait=0) as token:
            self.assertTrue(token)
            self.assertTrue(self.hl.LOCK.exists())
        self.assertFalse(self.hl.LOCK.exists())

    def test_release_on_exception(self):
        with self.assertRaises(RuntimeError):
            with t2lock.heavy_lock('t2kit-test', 'unit test', wait=0):
                raise RuntimeError('scenario failed')
        self.assertFalse(self.hl.LOCK.exists())

    def test_timeout_when_held(self):
        other = self.hl.acquire('other-agent', 'holding', pid=os.getppid(), wait=0)
        self.assertTrue(other)
        try:
            with self.assertRaises(t2lock.LockTimeout):
                with t2lock.heavy_lock('t2kit-test', 'unit test', wait=0, poll=0.01):
                    pass
            self.assertTrue(self.hl.LOCK.exists())
        finally:
            self.hl.release(other)


class HelperTest(unittest.TestCase):
    def test_safe_name(self):
        for name in ('keyblock-test-candidate', 'oos168x', 'T2-TEST-oos9'):
            got = safe_name(name)
            self.assertNotRegex(got, r'(?i)test|oos\d')

    def test_rect_and_origin(self):
        self.assertEqual(rect(1, 2, 2, 3), [(1, 2), (2, 2), (1, 3), (2, 3)])
        self.assertEqual(room_origin(0x4A), (0x1400, 0x800))

    def test_route_around_a_wall(self):
        buf = bytearray(64 * 64)
        for ty in range(0, 10):  # wall at tile column 8, rows 0-9; open below
            buf[ty * 64 + 8] = 0x01
        tiles = DungeonTiles(bytes(buf))
        path = tiles.route((16, 16), (96, 16), (0, 0, 200, 200))
        self.assertEqual(path[0], (16, 16))
        self.assertEqual(path[-1], (96, 16))
        self.assertGreater(max(y for _, y in path), 16)  # went under the wall
        self.assertIsNone(tiles.route((16, 16), (96, 16), (0, 0, 60, 60)))
        near = tiles.route((16, 16), (96, 16), (0, 0, 60, 60), nearest=True)
        # Closest reachable cell: body right edge (x+14) stops before the wall at px 64.
        self.assertEqual(near[-1], (48, 16))


if __name__ == '__main__':
    unittest.main()
