"""Native driver startup controls; no socket or emulator is opened."""
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent/'native'))
import lyra_checkpoint_preview as L


class NativePreviewStartupTest(unittest.TestCase):
    def test_waits_for_initialized_title_before_base_controller_boot(self):
        episode = object.__new__(L.LyraEpisode)
        episode.wait = mock.Mock()
        with mock.patch.object(L.Episode, 'boot', return_value='controller-boot') as boot:
            self.assertEqual(episode.boot(), 'controller-boot')
        predicate = episode.wait.call_args.args[0]
        self.assertFalse(predicate(dict(module=249, sub=225, indoors=6)))
        self.assertFalse(predicate(dict(module=0, sub=1, indoors=0)))
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
