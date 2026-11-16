"""Pure settings checks: no profile or emulator files are read or written."""
import json
import unittest

import yaze_dedicated_profile as profile


class DedicatedProfileTest(unittest.TestCase):
    def test_new_profile_clears_shared_save_redirects_and_preserves_input(self):
        source = {'Input': {'Controller': 'user-controller'},
                  'Preferences': {'OverrideSaveDataFolder': True,
                                  'SaveDataFolder': '/shared/saves',
                                  'overridesavestatefolder': True,
                                  'savestatefolder': '/shared/states',
                                  'Theme': 'Dark'}}
        raw = json.dumps(source).encode()
        result = json.loads(profile.prepare_settings(raw))
        self.assertEqual(json.loads(raw), source)
        self.assertEqual(result['Input'], source['Input'])
        self.assertEqual(result['Preferences']['Theme'], 'Dark')
        self.assertFalse(result['Preferences']['OverrideSaveDataFolder'])
        self.assertEqual(result['Preferences']['SaveDataFolder'], '')
        self.assertFalse(result['Preferences']['OverrideSaveStateFolder'])
        self.assertEqual(result['Preferences']['SaveStateFolder'], '')
        self.assertNotIn('overridesavestatefolder', result['Preferences'])
        self.assertNotIn('savestatefolder', result['Preferences'])

    def test_rejects_ambiguous_or_invalid_settings(self):
        for raw in (b'{}', b'{"Input":{},"Preferences":[]}',
                    b'{"Input":{},"Preferences":{"SaveDataFolder":"a",'
                    b'"savedatafolder":"b"}}',
                    b'{"Input":{},"Preferences":{},"Preferences":{}}',
                    b'{"Input":{},"Preferences":{},"x":NaN}',
                    b'{"Input":{},"Preferences":{},"x":1e999}', b'\xff'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    profile.prepare_settings(raw)

    def test_existing_profile_is_checked_without_rewriting_or_switching_saves(self):
        safe = b'{"Input":{},"Preferences":{"OverrideSaveDataFolder":false,"SaveDataFolder":"/old/path","Theme":"Dark"}}'
        self.assertIsNone(profile.verify_existing_settings(safe))
        self.assertIn(b'/old/path', safe)
        for unsafe in (
                b'{"Input":{},"Preferences":{"OverrideSaveDataFolder":true}}',
                b'{"Input":{},"Preferences":{"OverrideSaveStateFolder":true}}',
                b'{"Input":{},"Preferences":{"OverrideSaveDataFolder":"false"}}',
                b'{"Input":{},"Preferences":{"overridesavedatafolder":false}}',
                b'{"Input":{},"Preferences":{},"x":1e999}'):
            with self.subTest(raw=unsafe):
                with self.assertRaises(ValueError):
                    profile.verify_existing_settings(unsafe)


if __name__ == '__main__':
    unittest.main()
