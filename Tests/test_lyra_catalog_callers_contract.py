"""Cut02 source-set checks through maintained validation and source composition.

The composer uses the existing synthetic reader/table fixture and an explicitly
labelled graphics source fixture. These are host source checks, not saved project,
resource, assembler, CPU or publication qualification.
"""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_current_transfer as X
import lyra_project_publisher as P
import test_lyra_current_native_loaders as reader_fixtures


FROZEN = '6e7e5f15d555dffb9f4b3d8807595c9e3f13305f'
SOURCE_SET = 'lyra_current_catalog_callers_02'
FROZEN_SET = 'lyra_current_full32_port_01'
LEDGER = 'Config/allocation_ownership.json'
CONTRACT = 'Config/lyra_current_source_contract.json'
FLAGS = ('allocation_granted', 'producer_enforcement_verified',
         'publication_authorized', 'ordinary_build_ready', 'runtime_admission',
         'rom_written')


def frozen_bytes(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', FROZEN + ':' + path])


def raw_member(text, key):
    """Keep the exact declaration/record spelling, indentation and value bytes."""
    matches = list(re.finditer(r'(?m)^    ' + re.escape(json.dumps(key)) + r':\s*', text))
    if len(matches) != 1:
        raise AssertionError('Expected exactly one ledger member: ' + key)
    match = matches[0]
    _, end = json.JSONDecoder().raw_decode(text, match.end())
    return text[match.start():end].encode()


class CatalogCallersContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen_ledger_raw = frozen_bytes(LEDGER)
        cls.frozen_ledger = json.loads(cls.frozen_ledger_raw)
        cls.frozen_contract = json.loads(frozen_bytes(CONTRACT))
        # This calls the maintained pure table planner with the labelled host
        # source/origins/32-tail fixture. It writes no generated files or ROM.
        reader_fixtures.CurrentNativeLoaderTests.setUpClass()
        cls.table_plan = reader_fixtures.CurrentNativeLoaderTests.plan

    def setUp(self):
        self.ledger_raw = (ROOT / LEDGER).read_bytes()
        self.ledger = json.loads(self.ledger_raw)
        self.contract = json.loads((ROOT / CONTRACT).read_bytes())
        self.records = [row for row in self.ledger['sources'].values()
                        if row['source_set'] == SOURCE_SET]

    def bound_contract(self):
        contract = copy.deepcopy(self.contract)
        contract['ledger']['sha256'] = P.R.sha(self.ledger_raw)
        return contract

    def composable_contract(self):
        contract = self.bound_contract()
        # Host fixture graphics origin only; the canonical origin stays null.
        contract['origins']['graphics'] = dict(pc=[0x300000, 0x307000],
            snes=[0x608000, 0x60F000], source_binding=dict(
                path=str(ROOT / 'Overworld/custom_gfx.asm'),
                sha256=P.R.sha((ROOT / 'Overworld/custom_gfx.asm').read_bytes())))
        return contract

    def compose(self, contract):
        graphics = '; Host graphics source fixture for cut02 source-set composition.\n'
        report = dict(current_mode=True, parent_count=192,
            source_contract_sha256=P.R.sha(P.encoded(contract)),
            generated_sha256=P.R.sha(graphics.encode()),
            graphics_origin_snes=[0x608000, 0x60F000])
        return P.render_current_source_outputs(self.table_plan, contract=contract,
            graphics_source=graphics, graphics_report=report)

    def test_child_exact_ledger_and_all27_consumers_validate_and_compose_unselected(self):
        self.assertEqual(self.contract['ledger']['source_set'], SOURCE_SET)
        self.assertEqual(len(self.records), 27)
        old_paths = {row['path'] for row in self.frozen_ledger['sources'].values()
                     if row['source_set'] == FROZEN_SET}
        self.assertEqual({row['path'] for row in self.records}, old_paths)
        bindings = P.validate_current_source_set(self.bound_contract())
        self.assertEqual(len(bindings), 28)
        self.assertEqual(bindings[0], dict(path=str(ROOT / LEDGER), sha256=P.R.sha(self.ledger_raw)))
        self.assertEqual({row['path']: row['sha256'] for row in bindings[1:]},
                         {str(ROOT / row['path']): row['sha256'] for row in self.records})
        files = self.compose(self.composable_contract())
        prepared = json.loads(files['prepare.json'])
        self.assertEqual(prepared['source_bindings'], bindings)
        self.assertIs(prepared['selected'], False)
        for key in FLAGS:
            self.assertIs(prepared[key], False, key)
        self.assertIn(b'!LYRA_CURRENT_MODE = 1', files['runtime_constants.asm'])
        self.assertIn(b'!LYRA_NATIVE_A1_ENABLED = 0', files['runtime_constants.asm'])

    def test_frozen_ledger_and_frozen_source_set_refuse_the_changed_child(self):
        stale = copy.deepcopy(self.frozen_contract)
        stale['ledger']['sha256'] = P.R.sha(self.frozen_ledger_raw)
        with self.assertRaisesRegex(ValueError, 'Current source-set ledger changed'):
            P.validate_current_source_set(stale)
        stale['ledger']['sha256'] = P.R.sha(self.ledger_raw)
        with self.assertRaisesRegex(ValueError, 'Current source-set consumer changed: '):
            P.validate_current_source_set(stale)

    def test_real_selected_consumer_mutation_refuses_validation_and_composition(self):
        contract = self.composable_contract()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            # Copy only the selected27 consumer/resource files and exact ledger;
            # neither validator nor composer is replaced by a test double.
            for row in self.records:
                target = root / row['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / row['path']).read_bytes())
            (root / LEDGER).write_bytes(self.ledger_raw)
            contract['origins']['graphics']['source_binding']['path'] = str(
                root / 'Overworld/custom_gfx.asm')
            with mock.patch.object(P, 'ROOT', root):
                self.assertEqual(len(P.validate_current_source_set(contract)), 28)
                self.assertIs(json.loads(self.compose(contract)['prepare.json'])['selected'], False)
                consumer = root / 'Overworld/custom_gfx.asm'
                consumer.write_bytes(consumer.read_bytes() + b'\n; stale selected-consumer probe\n')
                for operation in (lambda: P.validate_current_source_set(contract),
                                  lambda: self.compose(contract)):
                    with self.assertRaisesRegex(ValueError,
                            'Current source-set consumer changed: Overworld/custom_gfx.asm'):
                        operation()

    def test_frozen_full32_and_bg_declarations_and_records_remain_byte_identical(self):
        old_text = self.frozen_ledger_raw.decode()
        new_text = self.ledger_raw.decode()
        for source_set in (FROZEN_SET, 'current_bg128'):
            self.assertEqual(raw_member(new_text, source_set), raw_member(old_text, source_set))
            old = {key: row for key, row in self.frozen_ledger['sources'].items()
                   if row['source_set'] == source_set}
            new = {key: row for key, row in self.ledger['sources'].items()
                   if row['source_set'] == source_set}
            self.assertEqual(new, old)
            for key in old:
                self.assertEqual(raw_member(new_text, key), raw_member(old_text, key), key)

    def test_actual_canonical_null_ledger_and_origins_still_refuse(self):
        self.assertEqual(self.contract['ledger']['source_set'], SOURCE_SET)
        self.assertIsNone(self.contract['ledger']['sha256'])
        self.assertTrue(all(value is None for value in self.contract['origins'].values()))
        self.assertTrue(all(value is None for value in self.contract['native_readers'].values()))
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_LEDGER_UNBOUND'):
            P.validate_current_source_set(self.contract)
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_LEDGER_UNBOUND'):
            X.validate_current_source_contract({}, ROOT / 'unused-project', ROOT / 'unused-rom')
        # Binding only the exact ledger still cannot supply a graphics origin.
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_ORIGIN_UNBOUND: graphics'):
            self.compose(self.bound_contract())


if __name__ == '__main__':
    unittest.main()
