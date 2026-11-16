"""Process-tree containment tests using only owned Python subprocesses."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import lyra_process_containment as containment


class ProcessContainmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lyra-containment-')
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_environment_block_is_sorted_and_rejects_ambiguity(self):
        block = containment._windows_environment_block({'z': 'two', 'A': 'one'})
        self.assertEqual(block, 'A=one\0z=two\0\0')
        for invalid in ({'Path': 'one', 'PATH': 'two'}, {'bad=name': 'x'},
                        {'ok': 'bad\0value'}, {'': 'x'}, {'x': 1}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    containment._windows_environment_block(invalid)

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_contained_child_receives_explicit_unicode_environment(self):
        marker = self.root / 'environment.txt'
        environment = dict(os.environ)
        environment['LYRA_CONTAINMENT_TEST'] = 'snowman-\u2603'
        code = ('import os,pathlib; pathlib.Path(' + repr(str(marker)) +
                ').write_text(os.environ["LYRA_CONTAINMENT_TEST"], encoding="utf-8")')
        result = containment.run_contained([sys.executable, '-c', code],
                                           cwd=self.root, timeout=10,
                                           environment=environment)
        self.assertEqual(result, containment.ContainedResult(0, False))
        self.assertEqual(marker.read_text(encoding='utf-8'), 'snowman-\u2603')
        self.assertNotEqual(os.environ.get('LYRA_CONTAINMENT_TEST'), 'snowman-\u2603')

    @unittest.skipIf(os.name == 'nt', 'Windows has a supported containment primitive')
    def test_unsupported_platform_refuses_before_launch(self):
        marker = self.root / 'must-not-exist'
        code = f'from pathlib import Path; Path({str(marker)!r}).write_text("ran")'
        with self.assertRaises(containment.ContainmentUnavailable):
            containment.run_contained([sys.executable, '-c', code], cwd=self.root, timeout=3)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_child_exit_code_is_preserved(self):
        result = containment.run_contained([sys.executable, '-c', 'raise SystemExit(7)'],
                                           cwd=self.root, timeout=10)
        self.assertEqual(result, containment.ContainedResult(7, False))

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_waits_for_descendant_after_parent_exits(self):
        marker = self.root / 'descendant-finished'
        child = f'import time; from pathlib import Path; time.sleep(.6); Path({str(marker)!r}).write_text("done")'
        parent = f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}])'
        result = containment.run_contained([sys.executable, '-c', parent], cwd=self.root, timeout=10)
        self.assertEqual(result, containment.ContainedResult(0, False))
        self.assertEqual(marker.read_text(), 'done')

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_child_cannot_request_breakaway(self):
        marker = self.root / 'breakaway-refused'
        parent = (
            'import subprocess,sys\n'
            'from pathlib import Path\n'
            'try:\n'
            '    child = subprocess.Popen([sys.executable, "-c", "pass"], '
            'creationflags=0x01000000)\n'
            'except OSError as error:\n'
            f'    Path({str(marker)!r}).write_text(str(error.winerror))\n'
            'else:\n'
            '    child.wait()\n'
            '    raise SystemExit(9)\n'
        )
        result = containment.run_contained([sys.executable, '-c', parent], cwd=self.root, timeout=10)
        self.assertEqual(result, containment.ContainedResult(0, False))
        self.assertEqual(marker.read_text(), '5')  # ERROR_ACCESS_DENIED

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_timeout_terminates_owned_descendant(self):
        ready, late = self.root / 'child-ready', self.root / 'late-write'
        child = (f'import time; from pathlib import Path; Path({str(ready)!r}).write_text("ready"); '
                 f'time.sleep(4); Path({str(late)!r}).write_text("late")')
        parent = f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}])'
        result = containment.run_contained([sys.executable, '-c', parent], cwd=self.root, timeout=2)
        self.assertEqual(result, containment.ContainedResult(None, True))
        self.assertTrue(ready.exists(), 'descendant did not start before timeout')
        time.sleep(2.2)
        self.assertFalse(late.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_supervisor_death_terminates_owned_child(self):
        ready, late = self.root / 'supervisor-child-ready', self.root / 'supervisor-late-write'
        child = (f'import time; from pathlib import Path; Path({str(ready)!r}).write_text("ready"); '
                 f'time.sleep(2); Path({str(late)!r}).write_text("late")')
        supervisor = (
            'import sys; import lyra_process_containment as c; '
            f'c.run_contained([sys.executable,"-c",{child!r}], cwd={str(self.root)!r}, timeout=10)'
        )
        env = dict(os.environ, PYTHONPATH=str(Path(containment.__file__).resolve().parent),
                   PYTHONDONTWRITEBYTECODE='1')
        process = subprocess.Popen([sys.executable, '-c', supervisor], cwd=self.root, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(ready.exists(), 'contained child did not start')
            process.kill()
            process.communicate(timeout=10)
            time.sleep(2.2)
            self.assertFalse(late.exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)


if __name__ == '__main__':
    unittest.main()
