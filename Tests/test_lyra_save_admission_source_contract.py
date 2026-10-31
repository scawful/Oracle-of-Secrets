"""Source58 restores current custody without rewriting historical authority.

Baseline digests are normalized JSON from committed df335c85 (ledger/config
unchanged from a7ad0b59). Tests never need those commits in a shallow checkout.
The small admission fixture uses its own temporary Git repository and the real
current-source validator; it does not assemble or admit a runtime candidate.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

from lyra_source_snapshots import staged_source_set
import test_lyra_current_source_contract as source_fixtures

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_current_transfer as X
import lyra_project_publisher as P


SOURCE_SET = 'lyra_current_save_admission_diagnostics_58'
BASELINE_LEDGER_VALUE_SHA256 = (
    '0a36cd0a58f8d600ea92a040f01a1785b769ae420cb7471192778f598568a3d8')
BASELINE_CONTRACT_PROJECTION_SHA256 = (
    '0baebfafb92b7cf8fc72e9cd353c7e803abb4071916319d8eaf5062102428c30')
SELECTED_INTAKE_HEAD = 'a7ad0b593b933218a5a9ef4b8760796531d5f9f4'
SELECTED_ENGINE_LEDGER_SHA256 = (
    '31cb74db34f0e105219b4f60795f4ccd2f22b233e8738cb4bdaace8bc23db8f6')
AUTHORITY_FLAGS = ('allocation_granted', 'publication_authorized',
                   'producer_enforcement_verified', 'ordinary_build_ready',
                   'runtime_admission')


def value_digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class SaveAdmissionSourceContractTest(unittest.TestCase):
    def setUp(self):
        self.ledger_raw = (ROOT / 'Config/allocation_ownership.json').read_bytes()
        self.ledger = json.loads(self.ledger_raw)
        self.contract = json.loads(
            (ROOT / 'Config/lyra_current_source_contract.json').read_bytes())

    def test_canonical_successor_binds_all72_current_consumers(self):
        self.assertEqual(X.SAVE_ADMISSION_SOURCE_SET, SOURCE_SET)
        self.assertEqual(self.contract['ledger']['source_set'], SOURCE_SET)
        current = {row['path']: row for row in self.ledger['sources'].values()
                   if row['source_set'] == SOURCE_SET}
        previous = {row['path']: row for row in self.ledger['sources'].values()
                    if row['source_set'] == X.PERSISTENT_REWARD_SOURCE_SET}
        self.assertEqual(len(current), 72)
        self.assertEqual(set(current), set(previous))
        self.assertNotIn('Tests/test_lyra_save_admission_source_contract.py', current)
        self.assertEqual({path for path in current
                          if current[path]['sha256'] != previous[path]['sha256']},
                         {'Scripts/Build/lyra_current_transfer.py',
                          'Scripts/Graphics/compile_runtime_graphics.py',
                          'Scripts/Generate/tests/test_authoring_project_bundle.py',
                          'Tests/test_lyra_current_transfer.py'})
        bindings = P.validate_current_source_set(self.contract)
        self.assertEqual(len(bindings), 73)
        self.assertEqual({row['path']: row['sha256'] for row in bindings[1:]},
                         {str(ROOT / path): row['sha256']
                          for path, row in current.items()})
        for path, row in current.items():
            self.assertEqual(set(row), {'source_set', 'path', 'sha256'})
            self.assertEqual(self.ledger['sources'][SOURCE_SET + ':' + path], row)
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                             row['sha256'], path)

    def test_all_historical_ledger_values_and_contract_authority_are_preserved(self):
        previous = copy.deepcopy(self.ledger)
        previous['source_sets'].pop(SOURCE_SET)
        previous['sources'] = {
            key: row for key, row in previous['sources'].items()
            if row['source_set'] != SOURCE_SET}
        # This covers every old source description/record (including55/56/57),
        # claim, table, reservation and policy without copying the large ledger.
        self.assertEqual(len(previous['source_sets']), 40)
        self.assertEqual(len(previous['sources']), 1406)
        self.assertEqual(value_digest(previous), BASELINE_LEDGER_VALUE_SHA256)
        self.assertEqual(self.contract['engine_head'], SELECTED_INTAKE_HEAD)
        self.assertEqual(self.contract['base_head'], SELECTED_INTAKE_HEAD)
        self.assertEqual(self.contract['ledger']['engine_ledger_sha256'],
                         SELECTED_ENGINE_LEDGER_SHA256)
        projection = copy.deepcopy(self.contract)
        projection['ledger'].pop('sha256')
        projection['ledger'].pop('source_set')
        # Permit only this explicit lineage correction. Normalize those three
        # asserted values to their old metadata before checking the unchanged
        # baseline digest, so unrelated contract changes still fail.
        projection['engine_head'] = '8b004e65efacbd0777121c49a36f09a43759c922'
        projection['base_head'] = 'c19cf98873c0d409043b1d59016633f415b72dba'
        projection['ledger']['engine_ledger_sha256'] = (
            '6bc162723d33d3589b076cbc7726fc6022d73732f2f5cecf75c9952098d485d6')
        self.assertEqual(value_digest(projection),
                         BASELINE_CONTRACT_PROJECTION_SHA256)
        self.assertEqual(self.contract['ledger']['sha256'],
                         hashlib.sha256(self.ledger_raw).hexdigest())
        for key in AUTHORITY_FLAGS:
            self.assertIs(self.contract[key], False, key)
        self.assertEqual(self.contract['status'], 'proposed')
        self.assertEqual(self.contract['scope'], 'source_review_only')

    def test_changed_current_consumer_refuses_in_owned_staged_source(self):
        with staged_source_set(ROOT, self.ledger_raw, SOURCE_SET, None) as root:
            with mock.patch.object(P, 'ROOT', root):
                self.assertEqual(len(P.validate_current_source_set(self.contract)), 73)
                consumer = root / 'Scripts/Build/lyra_current_transfer.py'
                consumer.write_bytes(consumer.read_bytes() + b'\n# changed fixture\n')
                with self.assertRaisesRegex(ValueError,
                                            'Current source-set consumer changed'):
                    P.validate_current_source_set(self.contract)

    def test_source58_preserves_exact_source56_e3_reservation(self):
        source_id = X.HIDDEN_STREAMS_SOURCE_SET + ':Overworld/lyra_native_loaders.asm'
        bound = self.ledger['sources'][source_id]
        with staged_source_set(ROOT, self.ledger_raw, SOURCE_SET, None) as root:
            contract = copy.deepcopy(self.contract)
            # The selected contract records its original Mac checkout. Bind
            # the same historical bytes to this owned fixture on every host.
            contract['origins']['hidden_streams']['source_binding']['path'] = str(
                root / bound['path'])
            with mock.patch.object(P, 'ROOT', root):
                claim = X._hidden_streams_reservation(contract, self.ledger)
                self.assertEqual(claim['provenance'], [source_id])
                self.assertEqual(claim['binding']['source'], source_id)
                self.assertEqual((claim['base'], claim['size']), (0xE38000, 0x8000))
                changed = copy.deepcopy(self.ledger)
                next(row for row in changed['claims']
                     if row['id'] == X.HIDDEN_STREAMS_CLAIM)['base'] += 1
                with self.assertRaisesRegex(ValueError, 'HIDDEN_STREAM_RESERVATION_MISMATCH'):
                    X._hidden_streams_reservation(contract, changed)
                changed_contract = copy.deepcopy(contract)
                changed_contract['origins']['hidden_streams']['pc'][1] -= 1
                with self.assertRaisesRegex(ValueError, 'HIDDEN_STREAM_ORIGIN_UNBOUND'):
                    X._hidden_streams_reservation(changed_contract, self.ledger)

    def test_source58_uses_full_completeness_guard_and_rejects_missing_consumer(self):
        host = source_fixtures.CurrentSourceContractTest()
        host.setUp()
        self.addCleanup(host.doCleanups)
        fixture = host.fixture
        ledger_path = fixture.root / 'Config/allocation_ownership.json'
        ledger = json.loads(ledger_path.read_bytes())
        base = {row['path'] for row in ledger['sources'].values()
                if row['source_set'] == 'lyra_ferry_visual_boundary_53'}
        complete = base | set(X.RESIDENT_ADDITIONAL_SOURCES)
        for relative in set(X.RESIDENT_ADDITIONAL_SOURCES) - base:
            path = fixture.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('; Inactive owned source-contract fixture.\n')
        ledger['source_sets'][SOURCE_SET] = 'Owned complete admission fixture'
        for relative in complete:
            ledger['sources'][SOURCE_SET + ':' + relative] = dict(
                source_set=SOURCE_SET, path=relative,
                sha256=X.R.sha((fixture.root / relative).read_bytes()))
        host.value['ledger']['source_set'] = SOURCE_SET

        def bind_committed_ledger():
            ledger_path.write_bytes(X.P.encoded(ledger))
            fixture.commit()
            fixture.head = fixture.git('rev-parse', 'HEAD').strip()
            fixture.refresh_proposal_source()
            host.review = fixture.review()
            host.value.update(engine_head=fixture.head, base_head=fixture.head)
            digest = X.Q.bound(ledger_path)['sha256']
            host.value['ledger'].update(sha256=digest, engine_ledger_sha256=digest)
            host.write()

        bind_committed_ledger()
        profile = host.profile()
        for key in AUTHORITY_FLAGS:
            self.assertIs(profile[key], False, key)
        source, document = host.inputs()
        # Source58 may use the resident constructor, but it still needs the
        # same independently bound resident origins as its predecessors.
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_ORIGIN_UNBOUND'):
            X.current_resident_inputs(profile, source, document,
                dict(inspection=None, graphics_catalog=None, graphics_policy=None))
        # Rebind a truthful committed but incomplete set. Only the existing
        # full-set check can reject the omitted inactive consumer at this point.
        omitted = 'Overworld/lyra_resident_resources.asm'
        ledger['sources'].pop(SOURCE_SET + ':' + omitted)
        bind_committed_ledger()
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_SOURCE_SET_INCOMPLETE'):
            host.profile()
        self.assertFalse(host.case.candidate.exists())


if __name__ == '__main__':
    unittest.main()
