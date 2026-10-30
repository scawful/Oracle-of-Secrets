"""Saved native selector lowering; no storage or runtime admission."""
import copy
from dataclasses import replace
import json
from types import SimpleNamespace
import unittest
from unittest import mock

from test_lyra_gameplay_area_plan import document
from test_lyra_project_terrain import fixture, profile
import lyra_native_loaders as L
import lyra_project_terrain as T
import lyra_project_admission as A


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


def schema6():
    data = fixture()
    data.update(schema_version=6,gameplay_areas=[])
    for row in data['maps']:
        row['authoring']['properties'].update(T.RUNTIME_PROPERTY_DEFAULTS)
    return data


class CurrentRuntimePropertiesTest(unittest.TestCase):
    def parse(self,data):
        bindings = {row['map_id']:tuple(row['authoring']['asset_bindings']) for row in data['maps']
                    if row['authoring']['asset_bindings'] != ['', '', '']}
        return T.parse_terrain_document(json.dumps(data),profile(),expected_asset_bindings=bindings,
                                        allow_authoring_drafts=True)

    def test_schema6_values_survive_without_assigning_unselected_area_layout(self):
        data = schema6()
        auth = data['maps'][0]['authoring']
        auth['properties'].update(mosaic=9,subscreen_overlay=0xBF,area_specific_bg_color=0x51E8)
        auth['asset_bindings'] = ['a'*64,'b'*64,'c'*64]
        doc = self.parse(data)
        self.assertEqual(doc.properties[0],auth['properties'])
        self.assertEqual(A.gameplay_area_plan(doc)['status'],'UNASSIGNED')
        source = bytearray(0x200000)
        for at in (0x140140,0x140142,0x140144):
            source[at] = 1
        at = A.pc(0x288000)+0x3A*2
        source[at:at+2] = b'\x34\x12'
        rows = L.current_property_rows(doc,source=bytes(source))
        self.assertEqual({k:rows[0xA0][k] for k in ('mosaic','overlay','bg_color')},
                         dict(mosaic=9,overlay=0xBF,bg_color=0x51E8))
        self.assertEqual(rows[0xBF]['bg_color'],0x1234)
        self.assertEqual(rows[0xBF]['overlay'],255)
        self.assertIn(dict(code='UNSUPPORTED_RUNTIME_PROPERTIES',map_id=0xA0),
                      A.consumer_blockers(doc,[0xA0],()))
        self.assertEqual(A.consumer_blockers(doc,[0xA0],(),current_source=True),[])

    def test_invalid_or_missing_native_properties_and_legacy_injection_refuse(self):
        for field,value in (('mosaic',16),('mosaic',False),('subscreen_overlay',192),
                            ('subscreen_overlay',True),('subscreen_overlay',65535),
                            ('area_specific_bg_color',0x8000),('area_specific_bg_color',False)):
            data = schema6()
            data['maps'][0]['authoring']['properties'][field] = value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                self.parse(data)
        for field in T.RUNTIME_PROPERTY_DEFAULTS:
            data = schema6()
            del data['maps'][0]['authoring']['properties'][field]
            with self.assertRaisesRegex(ValueError,'map properties'):
                self.parse(data)
        data = schema6()
        data['schema_version'] = 5
        data['gameplay_areas'] = [dict(parent_map_id=0xA0,size='small',maps=[0xA0])]
        with self.assertRaisesRegex(ValueError,'map properties'):
            self.parse(data)

    def test_exact_source_and_enabled_global_features_are_required_without_global_writes(self):
        data = schema6()
        data['maps'][0]['authoring']['properties']['mosaic'] = 1
        data['maps'][0]['authoring']['asset_bindings'] = ['a'*64]*3
        doc = self.parse(data)
        with self.assertRaisesRegex(ValueError,'RUNTIME_SOURCE_REQUIRED'):
            L.current_property_rows(doc)
        source = bytes(0x200000)
        with self.assertRaisesRegex(ValueError,'NATIVE_FEATURE_DISABLED: mosaic'):
            L.current_property_rows(doc,source=source)
        self.assertEqual(source,bytes(0x200000))
        for parser in (A.relocated_table_payloads,A.relocated_table_plan):
            with self.assertRaisesRegex(ValueError,'no saved runtime property consumer'):
                parser(b'',doc,SimpleNamespace(maps=[]),())
            with self.assertRaisesRegex(ValueError,'no saved runtime property consumer'):
                parser(b'',None,SimpleNamespace(maps=[SimpleNamespace(properties=doc.properties[0])]),())

    def test_legacy_document_property_shape_and_identity_are_unchanged(self):
        legacy = document()
        self.assertTrue(all(set(prop) == T.PROPERTY_KEYS for prop in legacy.properties))
        self.assertFalse(any('mosaic' in row for row in L.current_property_rows(legacy).values()))


class CurrentRuntimePropertyComposerTest(unittest.TestCase):
    def setUp(self):
        import test_lyra_current_transfer as fixtures
        from test_lyra_current_composer_binding import ComposerFixture
        from test_lyra_project_admission import observation
        import lyra_current_transfer as X
        prepare = fixtures.CurrentSaveTransferTest.prepare
        def prepare_schema6(case,**kwargs):
            data = json.loads(case.terrain.read_bytes())
            data.update(schema_version=6,gameplay_areas=[])
            for row in data['maps']:
                row['authoring']['properties'].update(T.RUNTIME_PROPERTY_DEFAULTS)
            case.terrain.write_bytes(X.P.encoded(data))
            case.inputs['terrain'] = X.Q.bound(case.terrain)
            case.save['artifacts'] = case.artifacts(case.inputs)
            case.receipt.write_bytes(X.P.encoded(case.save))
            case.proof.clear()
            case.proof.update(observation(case.rom.read_bytes(),data)[1])
            case.proof['terrain_sha256'] = X.R.sha(case.terrain.read_bytes())
            return prepare(case,**kwargs)
        with mock.patch.object(fixtures.CurrentSaveTransferTest,'prepare',prepare_schema6):
            self.f = ComposerFixture(self)

    def test_bound_schema6_properties_compose_and_foreign_runtime_rows_refuse(self):
        prepared = json.loads(self.f.compose()['prepare.json'])
        self.assertEqual(prepared['gameplay_area_plan']['status'],'UNASSIGNED')
        self.assertFalse(prepared['selected'])
        for field,value in (('mosaic',1),('overlay',0xBF),('bg_color',0x51E8)):
            before = copy.deepcopy(self.f.rows)
            self.f.rows[0xB6][field] = value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'COMPOSER_PROPERTIES_MISMATCH'):
                self.f.compose(table_plan=self.f.tables())
            self.f.rows = before

    def test_runtime_property_edits_retire_bound_document_identity(self):
        import lyra_current_transfer as X
        doc = copy.deepcopy(self.f.document)
        doc.properties[0]['mosaic'] = 1
        with self.assertRaisesRegex(ValueError,'PROFILE_STALE'):
            X.verify_current_native_source_profile(self.f.profile,self.f.source,doc)


if __name__ == '__main__':
    unittest.main()
