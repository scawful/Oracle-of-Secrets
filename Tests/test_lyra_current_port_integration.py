"""Current-engine source composition checks; no assembler or CPU execution."""
import json
import os
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

from lyra_source_snapshots import read_snapshot_text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import asm_source as S
import generate_hack_manifest as H
import lyra_project_publisher as P
import lyra_current_transfer as X
import lyra_native_loaders as L
import test_lyra_current_native_loaders as reader_fixtures


def statements(text, defines):
    result = []
    for _, line, _ in S._iter_active_lines(text.splitlines(), defines):
        line = line.split(';', 1)[0].strip()
        line = re.sub(r'^(?:[A-Za-z_][\w.]*|\.[\w]+):\s*', '', line)
        if not line or line in ('{', '}') or re.match(r'^[!\w.]+\s*(?:#=|=)', line):
            continue
        if line.startswith('assert '):
            continue
        result.extend(part.strip() for part in line.split(':') if part.strip())
    return result


class CurrentPortIntegrationTest(unittest.TestCase):
    def test_ordinary_context_is_disabled_and_has_original_source_domain(self):
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV:'0'}):
            defines = S._load_global_defines(ROOT)
            self.assertEqual([defines[n] for n in ('LYRA_CURRENT_MODE', 'LYRA_PROJECT_DATA_PRESENT',
                'PROJECT_BG128_ENABLED', 'PROJECT_BG128_RESTORE_BOUND')], [0, 0, 0, 0])
            paths = H.collect_reachable_asm_sources(ROOT)
        self.assertEqual(len(paths), 174)
        self.assertNotIn(ROOT / 'Overworld/lyra_native_loaders.asm', paths)
        self.assertNotIn(ROOT / 'Overworld/project_bg_palette.asm', paths)
        self.assertNotIn(ROOT / 'Overworld/graphics_runtime.asm', paths)

    def test_disabled_shared_instructions_match_exact_current_engine(self):
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV:'0'}):
            defines = S._load_global_defines(ROOT)
        for name in ('Overworld/ZSCustomOverworld.asm', 'Overworld/time_system.asm',
                     'Overworld/lost_woods.asm', 'Overworld/custom_gfx.asm',
                     'Overworld/goron_checkpoint.asm', 'Masks/mask_routines.asm'):
            with self.subTest(path=name):
                original = read_snapshot_text('c19cf98873c0d409043b1d59016633f415b72dba', name)
                self.assertEqual(statements((ROOT/name).read_text(), defines), statements(original, defines))

    def test_current_callers_have_separate_direction_and_backdrop_boundaries(self):
        zs = (ROOT/'Overworld/ZSCustomOverworld.asm').read_text()
        self.assertIn('JSL Lyra_ReadByScreen : CLC : ADC.b $84 : STA.b $84', zs)
        self.assertIn('JSL Lyra_ReadMosaic', zs)
        time = (ROOT/'Overworld/time_system.asm').read_text()
        self.assertIn('LDA.b $8A : AND.w #$00FF\nLyra_CurrentBackdropLegacy:', time)
        self.assertIn('CMP.b #!LYRA_CURRENT_END : BCC .notSpecialOverworld', zs)

    def test_current_and_bg_source_pins_match_actual_composition(self):
        ledger = json.loads((ROOT/'Config/allocation_ownership.json').read_bytes())
        contract = json.loads((ROOT/'Config/lyra_current_source_contract.json').read_bytes())
        source_set = contract['ledger']['source_set']
        self.assertEqual(source_set, 'lyra_current_stage_receipt_19')
        records = [r for r in ledger['sources'].values() if r['source_set']==source_set]
        self.assertEqual(len(records), 40)
        for row in records:
            self.assertEqual(P.R.sha((ROOT/row['path']).read_bytes()), row['sha256'], row['path'])
        claim, = [r for r in ledger['claims'] if r['id']=='ProjectBGPaletteNativeUnderlay']
        # The unchanged BG underlay keeps its frozen source05 provenance.
        self.assertTrue(all(key.startswith('lyra_current_gameplay_areas_05:') for key in claim['provenance']))

    def test_actual_contract_and_review_still_refuse_before_output(self):
        contract = json.loads((ROOT/'Config/lyra_current_source_contract.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_LEDGER_UNBOUND'):
            X.validate_current_source_contract({}, ROOT/'unused-project', ROOT/'unused-rom')
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_LEDGER_UNBOUND'):
            P.validate_current_source_set(contract)
        self.assertTrue(all(v is None for v in contract['origins'].values()))

    def test_loose_component_plan_cannot_compose_without_verified_current_profile(self):
        reader_fixtures.CurrentNativeLoaderTests.setUpClass()
        table_plan = reader_fixtures.CurrentNativeLoaderTests.plan
        contract = json.loads((ROOT/'Config/lyra_current_source_contract.json').read_bytes())
        contract['ledger']['sha256'] = P.R.sha((ROOT/'Config/allocation_ownership.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_PROFILE_REQUIRED'):
            P.render_current_source_outputs(table_plan, contract=contract,
                graphics_source='; loose host fixture\n', graphics_report={})


if __name__ == '__main__':
    unittest.main()
