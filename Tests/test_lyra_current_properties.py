"""Saved native selector lowering; no storage or runtime admission."""
import copy
from dataclasses import replace
import unittest

from test_lyra_gameplay_area_plan import document
import lyra_native_loaders as L


class CurrentPropertyRowsTest(unittest.TestCase):
    def test_saved_selectors_and_four_music_phases_are_exact_at_both_tail_ends(self):
        doc = copy.deepcopy(document())
        for area in (0xA0, 0xBF):
            prop = doc.properties[area-0xA0]
            prop.update(graphics_sheets=[255,1,2,3,4,5,6,7], main_palette=7,
                        palette_set=254, animated_sheet=255, message_id=0x1234,
                        sprite_graphics=[23]*3, sprite_palettes=[15]*3, music=[0x10,0x20,0x30,0x40])
        rows = L.current_property_rows(doc)
        for area in (0xA0, 0xBF):
            self.assertEqual(rows[area], dict(gfx=[255,1,2,3,4,5,6,7], main_palette=7,
                palette_set=254, animated=255, sign_text=0x1234, special_sprite_gfx=23,
                special_sprite_palettes=15, music_dark_special=0x10,
                music_phase0=0x10, music_phase1=0x20, music_phase2=0x30, music_phase3=0x40))
        self.assertEqual(set(rows), set(range(0xA0,0xC0)))
        self.assertEqual(rows[0xA1]['special_sprite_gfx'], 0)
        rows[0xA0]['gfx'][0] = 0
        self.assertEqual(doc.properties[0]['graphics_sheets'][0], 255)

    def test_unrepresentable_special_phase_selectors_refuse_instead_of_flattening(self):
        for field in ('sprite_graphics','sprite_palettes'):
            doc = copy.deepcopy(document())
            doc.properties[0][field] = [1,2,1]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'PHASE_SELECTOR_UNSUPPORTED'):
                L.current_property_rows(doc)

    def test_malformed_models_refuse_without_byte_masking_or_missing_key_fallbacks(self):
        for field,value in (('graphics_sheets',[False]*8),('graphics_sheets',[256]*8),
                            ('music',[1]*3),('sprite_graphics',[-2]*3),
                            ('main_palette',True),('message_id',65536),('animated_sheet',-1)):
            doc = copy.deepcopy(document())
            doc.properties[0][field] = value
            with self.subTest(field=field,value=value), self.assertRaisesRegex(ValueError, 'PROPERTY_MODEL_INVALID'):
                L.current_property_rows(doc)
        with self.assertRaisesRegex(ValueError,'PROPERTY_MODEL_INVALID'):
            L.current_property_rows(replace(document(),properties=None))


if __name__ == '__main__':
    unittest.main()
