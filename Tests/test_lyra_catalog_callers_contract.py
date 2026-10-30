"""Current source-set checks retain cut01/02 and require a profile at composition.

The loose reader/table and graphics fixtures are deliberately refused by the
composer. Real common-profile composition lives in test_lyra_current_composer_binding.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

import lyra_source_snapshots as snapshots

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_current_transfer as X
import lyra_project_publisher as P
import test_lyra_current_native_loaders as reader_fixtures


FROZEN = '6e7e5f15d555dffb9f4b3d8807595c9e3f13305f'
SOURCE_SET = 'lyra_current_gameplay_areas_05'
ACTOR_SET = 'lyra_current_actor_resources_04'
COMPOSER_SET = 'lyra_current_composer_binding_03'
FROZEN_SET = 'lyra_current_full32_port_01'
CALLERS_SET = 'lyra_current_catalog_callers_02'
CALLERS_HEAD = '80fb34a9e70fe0dd7d32b5b47baf00d2033e4a85'
LEDGER = 'Config/allocation_ownership.json'
CONTRACT = 'Config/lyra_current_source_contract.json'


def frozen_bytes(path):
    return snapshots.read_snapshot(FROZEN, path)


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
        cls.callers_ledger_raw = snapshots.read_snapshot(CALLERS_HEAD, LEDGER)
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
        graphics = '; Loose host graphics source fixture; no verified profile.\n'
        report = dict(current_mode=True, parent_count=192,
            source_contract_sha256=P.R.sha(P.encoded(contract)),
            generated_sha256=P.R.sha(graphics.encode()),
            graphics_origin_snes=[0x608000, 0x60F000])
        return P.render_current_source_outputs(self.table_plan, contract=contract,
            graphics_source=graphics, graphics_report=report)

    def test_previous_composer_declaration_and27_pins_remain_verbatim(self):
        members = [COMPOSER_SET] + [key for key, row in self.ledger['sources'].items()
                                   if row['source_set'] == COMPOSER_SET]
        self.assertEqual(len(members), 28)
        # Exact declaration/record bytes from the green c6ef36e0 parent.
        retained = b'\n'.join(raw_member(self.ledger_raw.decode(), key) for key in members)
        self.assertEqual(hashlib.sha256(retained).hexdigest(),
                         'a3cae98e16be902cff4ef82d5ec84030644de0202aca0677a2477ff4a68ec539')

    def test_previous_actor_declaration_and31_pins_remain_verbatim(self):
        members = [ACTOR_SET] + [key for key, row in self.ledger['sources'].items()
                                if row['source_set'] == ACTOR_SET]
        self.assertEqual(len(members), 32)
        retained = b'\n'.join(raw_member(self.ledger_raw.decode(), key) for key in members)
        self.assertEqual(hashlib.sha256(retained).hexdigest(),
                         'da1cf33ca25ba62f063c2bd14151406d96eca9ef022abe94d6c4b49e0cae7a8e')

    def test_child_exact_ledger_and_all33_consumers_validate_but_need_profile_to_compose(self):
        self.assertEqual(self.contract['ledger']['source_set'], SOURCE_SET)
        self.assertEqual(len(self.records), 33)
        old_paths = {row['path'] for row in self.frozen_ledger['sources'].values()
                     if row['source_set'] == FROZEN_SET}
        resources = {'Overworld/gfx/kalyxo_docks_slot3.bin', 'Overworld/gfx/kalyxo_docks_bg.bin',
                     'Overworld/gfx/lyra_sky_tower_87.bin', 'Overworld/gfx/lyra_stepped_fort_83.bin'}
        readers = {'Scripts/Build/lyra_project_terrain.py', 'Scripts/Build/lyra_project_admission.py'}
        self.assertEqual({row['path'] for row in self.records}, old_paths | resources | readers)
        bindings = P.validate_current_source_set(self.bound_contract())
        self.assertEqual(len(bindings), 34)
        self.assertEqual(bindings[0], dict(path=str(ROOT / LEDGER), sha256=P.R.sha(self.ledger_raw)))
        self.assertEqual({row['path']: row['sha256'] for row in bindings[1:]},
                         {str(ROOT / row['path']): row['sha256'] for row in self.records})
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_PROFILE_REQUIRED'):
            self.compose(self.composable_contract())

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
            # Copy only the selected consumer/resource files and exact ledger;
            # neither validator nor composer is replaced by a test double.
            for row in self.records:
                target = root / row['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / row['path']).read_bytes())
            (root / LEDGER).write_bytes(self.ledger_raw)
            contract['origins']['graphics']['source_binding']['path'] = str(
                root / 'Overworld/custom_gfx.asm')
            with mock.patch.object(P, 'ROOT', root):
                self.assertEqual(len(P.validate_current_source_set(contract)), 34)
                with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_PROFILE_REQUIRED'):
                    self.compose(contract)
                consumer = root / 'Overworld/custom_gfx.asm'
                consumer.write_bytes(consumer.read_bytes() + b'\n; stale selected-consumer probe\n')
                for operation in (lambda: P.validate_current_source_set(contract),
                                  lambda: self.compose(contract)):
                    with self.assertRaisesRegex(ValueError,
                            'Current source-set consumer changed: Overworld/custom_gfx.asm'):
                        operation()

    def test_frozen_full32_and_bg_declarations_and_records_remain_byte_identical(self):
        new_text = self.ledger_raw.decode()
        for source_set, raw in ((FROZEN_SET, self.frozen_ledger_raw),
                                ('current_bg128', self.frozen_ledger_raw),
                                (CALLERS_SET, self.callers_ledger_raw)):
            old_text = raw.decode()
            old_ledger = json.loads(raw)
            self.assertEqual(raw_member(new_text, source_set), raw_member(old_text, source_set))
            old = {key: row for key, row in old_ledger['sources'].items()
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
        # Binding only the exact ledger cannot supply a verified source profile.
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_PROFILE_REQUIRED'):
            self.compose(self.bound_contract())


class SourceSnapshotIntegrityTest(unittest.TestCase):
    def test_all17_pinned_snapshots_load_without_git_or_network(self):
        self.assertEqual(len(snapshots.SNAPSHOT_KEYS), 17)
        with mock.patch('subprocess.check_output', side_effect=AssertionError('Unexpected Git call')):
            for commit, path in snapshots.SNAPSHOT_KEYS:
                with self.subTest(commit=commit, path=path):
                    raw = snapshots.read_snapshot(commit, path)
                    self.assertEqual(snapshots.read_snapshot_text(commit, path).encode('utf-8'), raw)

    def test_changed_compressed_snapshot_refuses_before_comparison(self):
        commit, path = snapshots.SNAPSHOT_KEYS[0]
        pin = snapshots._PINS[(commit, path)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / (pin['git_blob'] + '.gz')).write_bytes(b'changed fixture')
            with mock.patch.object(snapshots, '_FIXTURE_ROOT', root):
                with self.assertRaisesRegex(ValueError, 'snapshot compressed bytes changed'):
                    snapshots.read_snapshot(commit, path)

    def test_unpinned_commit_or_path_refuses(self):
        commit, path = snapshots.SNAPSHOT_KEYS[0]
        for key in ((commit[:8], path), (commit, '../' + path),
                    ('0' * 40, path), (commit, 'unlisted-source.asm')):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'Unpinned Lyra source snapshot'):
                    snapshots.read_snapshot(*key)


if __name__ == '__main__':
    unittest.main()
