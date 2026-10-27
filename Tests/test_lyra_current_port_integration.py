"""Current-engine source composition checks; no assembler or CPU execution."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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
                original = subprocess.check_output(['git', '-C', str(ROOT), 'show',
                    'c19cf98873c0d409043b1d59016633f415b72dba:'+name]).decode()
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
        records = [r for r in ledger['sources'].values() if r['source_set']=='lyra_current_full32_port_01']
        self.assertGreaterEqual(len(records), 25)
        for row in records:
            self.assertEqual(P.R.sha((ROOT/row['path']).read_bytes()), row['sha256'], row['path'])
        claim, = [r for r in ledger['claims'] if r['id']=='ProjectBGPaletteNativeUnderlay']
        self.assertTrue(all(key.startswith('lyra_current_full32_port_01:') for key in claim['provenance']))

    def test_actual_contract_and_review_still_refuse_before_output(self):
        contract = json.loads((ROOT/'Config/lyra_current_source_contract.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_LEDGER_UNBOUND'):
            X.validate_current_source_contract({}, ROOT/'unused-project', ROOT/'unused-rom')
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_LEDGER_UNBOUND'):
            P.validate_current_source_set(contract)
        self.assertTrue(all(v is None for v in contract['origins'].values()))

    def test_source_composer_binds_graphics_and_inactive_source_without_authority(self):
        reader_fixtures.CurrentNativeLoaderTests.setUpClass()
        table_plan = reader_fixtures.CurrentNativeLoaderTests.plan
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root/'Config').mkdir()
            consumer = root/'inactive.asm'
            consumer.write_text('nop\n')
            ledger = dict(source_sets={'current':'owned host fixture'}, sources={'current:inactive.asm':
                dict(source_set='current', path='inactive.asm', sha256=P.R.sha(consumer.read_bytes()))})
            raw = P.encoded(ledger)
            (root/'Config/allocation_ownership.json').write_bytes(raw)
            contract = json.loads((ROOT/'Config/lyra_current_source_contract.json').read_bytes())
            contract['ledger'].update(source_set='current', sha256=P.R.sha(raw))
            contract['origins']['graphics'] = dict(snes=[0x608000, 0x60F000])
            graphics = '; owned host graphics source\n'
            report = dict(current_mode=True, parent_count=192, source_contract_sha256=P.R.sha(P.encoded(contract)),
                generated_sha256=P.R.sha(graphics.encode()), graphics_origin_snes=[0x608000, 0x60F000])
            with mock.patch.object(P, 'ROOT', root):
                files = P.render_current_source_outputs(table_plan, contract=contract,
                    graphics_source=graphics, graphics_report=report)
                prepared = json.loads(files['prepare.json'])
                self.assertFalse(prepared['selected'])
                self.assertFalse(prepared['runtime_admission'])
                self.assertFalse(prepared['rom_written'])
                self.assertIn(b'!LYRA_CURRENT_MODE = 1', files['runtime_constants.asm'])
                self.assertIn(b'!PROJECT_BG128_ENABLED = 0', files['runtime_constants.asm'])
                self.assertEqual(files['graphics_runtime_tables.asm'], graphics.encode())
                with self.assertRaisesRegex(ValueError, 'matching192-row graphics'):
                    P.render_current_source_outputs(table_plan, contract=contract,
                        graphics_source=graphics+'changed', graphics_report=report)
                consumer.write_text('changed\n')
                with self.assertRaisesRegex(ValueError, 'consumer changed'):
                    P.render_current_source_outputs(table_plan, contract=contract,
                        graphics_source=graphics, graphics_report=report)


if __name__ == '__main__':
    unittest.main()
