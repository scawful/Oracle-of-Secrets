"""Kit masks are an opt-in for mapped static slot-6 cells, not animation."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gen_wall_profiles as profiles

class WallKitMaskSchemaTest(unittest.TestCase):
    def test_rejects_animation_wrong_slot_alias_and_unowned_mask(self):
        source=json.loads((profiles.KITS_DIR/'glacia_estate_timber.kit.json').read_text())
        changes=[lambda k:k['sheets'][1].update(high_palette_chars=['1B0']),
                 lambda k:k['sheets'][0].update(high_palette_chars=['0C1']),
                 lambda k:k['sheets'][1].update(high_palette_chars=['180','180']),
                 lambda k:k['sheets'][1].update(high_palette_chars=['182'])]
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(profiles,'KITS_DIR',Path(directory)):
            path=Path(directory)/'glacia_estate_timber.kit.json'
            for change in changes:
                kit=copy.deepcopy(source);change(kit);path.write_text(json.dumps(kit))
                with self.assertRaisesRegex(SystemExit,'high_palette_chars'):profiles.load_kits()
            path.write_text(json.dumps(source))
            self.assertEqual(len(profiles.load_kits()),1)

    def test_compiled_d4_fallback_and_state_room_refusal(self):
        data=bytearray(0x300000)
        data[0x8745:0x8751]=bytes.fromhex('22 00 80 50 EA EA EA EA EA EA EA EA')
        prefix=bytes.fromhex('AF A0 00 7E C9 25 00 F0 17 C9 26 00 F0 3A C9 37 00 F0 59')
        fallback=bytes.fromhex('BF 01 80 1F 85 B8 BF 00 80 1F 85 B7 6B')
        data[0x280000:0x280000+len(prefix+fallback)]=prefix+fallback
        self.assertEqual(profiles.room_object_table(data,[0xDB,0xCD]),0x1F8000)
        with self.assertRaisesRegex(ValueError,'state-specific'):
            profiles.room_object_table(data,[0x26])
        data[0x280000+len(prefix)+1]=2
        with self.assertRaisesRegex(ValueError,'disagree'):
            profiles.room_object_table(data,[0xDB])

    def test_final_glyph_guard_rejects_floor_door_animation_and_unowned_changes(self):
        import sheet_table
        for char,protected_floor,owned,ok in ((0x180,set(),True,True),
                                              (0x1AC,set(),True,False),
                                              (0x1B0,set(),True,False),
                                              (0x0EE,{0x0EE},True,False),
                                              (0x180,set(),False,False)):
            raw=bytearray(1536);raw[(char&63)*24]=1
            kit={'kit':'probe','rooms':[],'_cmap':{1:char} if owned else {},
                 'sheets':[{'slot':char>>6,'sheet':'F3','copy_of':'1D',
                            'decoded_sha256':hashlib.sha256(raw).hexdigest()}]}
            with mock.patch.object(profiles,'load_kits',return_value=[kit]), \
                 mock.patch.object(profiles,'floor_chars',return_value=protected_floor), \
                 mock.patch.object(profiles,'door_chars',return_value={0x1AC}), \
                 mock.patch.object(sheet_table,'ptr',side_effect=lambda data,sid:sid), \
                 mock.patch.object(sheet_table,'decomp',side_effect=lambda data,sid:(raw if sid==0xF3 else bytes(1536),0)):
                if ok:self.assertEqual(profiles.verify_kit_glyph_ownership(b'')['kit_sheets_checked'],1)
                else:
                    with self.assertRaisesRegex(ValueError,'protected/unowned'):
                        profiles.verify_kit_glyph_ownership(b'')

    def test_palette_only_mask_cannot_recolor_a_door_with_identical_3bpp(self):
        import sheet_table
        raw=bytes(1536)
        kit={'kit':'probe','rooms':[],'_cmap':{1:0x1AC},
             'sheets':[{'slot':6,'sheet':'F3','copy_of':'1D',
                        'high_palette_chars':['1AC'],
                        'decoded_sha256':hashlib.sha256(raw).hexdigest()}]}
        with mock.patch.object(profiles,'load_kits',return_value=[kit]), \
             mock.patch.object(profiles,'floor_chars',return_value=set()), \
             mock.patch.object(profiles,'door_chars',return_value={0x1AC}), \
             mock.patch.object(sheet_table,'ptr',return_value=0), \
             mock.patch.object(sheet_table,'decomp',return_value=(raw,0)):
            with self.assertRaisesRegex(ValueError,'protected/unowned'):
                profiles.verify_kit_glyph_ownership(b'')

    def test_generated_descriptor_reuses_selector_tables_and_preserves_class_count(self):
        asm=profiles.render()
        self.assertIn('db "WSR1"',asm)
        self.assertIn('dl WallSel_SlotSrc',asm)
        self.assertIn('dl WallSel_KitHighPalette',asm)
        for kit in profiles.load_kits():
            if kit['_row'] is not None:
                self.assertEqual(len(kit['classes']),24)

if __name__=='__main__':unittest.main()
