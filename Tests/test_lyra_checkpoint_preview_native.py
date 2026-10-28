"""Native driver startup controls; no socket or emulator is opened."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent/'native'))
import lyra_checkpoint_preview as L


class NativePreviewStartupTest(unittest.TestCase):
    def test_initial_debugger_read_precedes_the_pause_used_for_frame_stepping(self):
        episode = object.__new__(L.Episode)
        episode.a = SimpleNamespace(phase='home')
        episode.owner = mock.Mock()
        episode.result = {}
        episode.screenshot = mock.Mock()
        state = dict(debugger=False, paused=False)
        def read(address, count):
            if not state['debugger']:
                state.update(debugger=True, paused=False)
            return bytes(count)
        episode.b = mock.Mock()
        episode.b.read_block.side_effect = read
        def command(name, params=None):
            if name == 'BREAKPOINT':
                return dict(breakpoints=[])
            if name == 'PAUSE':
                state['paused'] = True
                return {}
            if name == 'STATE':
                return dict(paused=state['paused'])
            self.fail(name)
        episode.command = command
        def boot():
            read(0x7E0010, 1)
            self.assertTrue(state['paused'], 'Initial debugger read cleared the startup pause')
            return dict(module=7, room=0x104, checkpoint='0101000000')
        episode.boot = boot
        episode.run()
        self.assertTrue(episode.result['passed'])
        episode.b.read_block.assert_called_once_with(0x7E0000, 1)

    def test_inherited_damage_accepts_only_the_scene_gameplay_module(self):
        episode = object.__new__(L.LyraEpisode)
        state = dict(module=0x0B, sub=0, hp=48)
        episode.sample = mock.Mock(return_value=state)
        values = {0x7E0055: 0, 0x7E037B: 1, 0x7E0373: 0}
        episode.b = mock.Mock()
        episode.b.read_memory.side_effect = values.__getitem__
        def write(address, value):
            values[address] = value
            return True
        episode.b.write_memory.side_effect = write
        episode.command = mock.Mock(return_value=dict(paused=True))
        episode.wait = mock.Mock(return_value='gameover')
        episode.result = dict(writes=[])
        self.assertEqual(episode.damage(), 'gameover')
        self.assertEqual([(r['address'], r['value']) for r in episode.result['writes']],
                         [('7E037B', 0), ('7E0373', 48)])
        episode.b.write_memory.reset_mock()
        state['module'] = 0x09
        with self.assertRaisesRegex(RuntimeError, 'ordinary live outdoor gameplay'):
            episode.damage()
        episode.b.write_memory.assert_not_called()

    def test_recorded_special_world_entry_requires_native_module_0b(self):
        episode = object.__new__(L.LyraEpisode)
        episode.cache = bytes(50)
        episode.b = mock.Mock()
        episode.b.read_block.return_value = episode.cache
        episode.result = {}
        state = dict(module=0x0B, sub=0, indoors=0, map=0xA0,
                     x=256, y=2355, checkpoint='0101020001')
        episode.require_regional_destination(state)
        with self.assertRaisesRegex(RuntimeError, 'stable destination/native19px exit walk mismatch'):
            episode.require_regional_destination(dict(state, module=0x09))

    def test_waits_for_initialized_title_before_base_controller_boot(self):
        episode = object.__new__(L.LyraEpisode)
        episode.wait = mock.Mock()
        with mock.patch.object(L.Episode, 'boot', return_value='controller-boot') as boot:
            self.assertEqual(episode.boot(), 'controller-boot')
        predicate = episode.wait.call_args.args[0]
        self.assertFalse(predicate(dict(module=249, sub=225, indoors=6)))
        self.assertTrue(predicate(dict(module=0, sub=7, indoors=0)))
        self.assertFalse(predicate(dict(module=0, sub=7, indoors=1)))
        self.assertTrue(predicate(dict(module=0, sub=0, indoors=0)))
        self.assertEqual(episode.wait.call_args.kwargs['max_frames'], 1200)
        boot.assert_called_once()

    def test_bounded_startup_refusal_prevents_controller_boot(self):
        episode = object.__new__(L.LyraEpisode)
        episode.wait = mock.Mock(side_effect=RuntimeError('startup cap'))
        with mock.patch.object(L.Episode, 'boot') as boot:
            with self.assertRaisesRegex(RuntimeError, 'startup cap'):
                episode.boot()
        boot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
