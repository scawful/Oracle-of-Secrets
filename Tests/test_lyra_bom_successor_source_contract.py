"""Source59 BOM wrapper successor: source evidence only, no runtime grant."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

from lyra_source_snapshots import read_snapshot, staged_source_set
import test_lyra_current_source_contract as source_fixtures

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_current_transfer as X
import lyra_project_publisher as P

SOURCE58_HEAD = '766660b0494b40b2cfd813ac21f4c82ad4540eb8'
SOURCE_SET = 'lyra_current_bom_wrapper_admission_59'
PREVIOUS_LEDGER_DIGEST = 'dde13c41303ba60ae0e7acea5cfc020cf1a0395099090b7bd93b08bcd054f2e2'
AUTHORITY_FLAGS = ('allocation_granted', 'publication_authorized',
                   'producer_enforcement_verified', 'ordinary_build_ready',
                   'runtime_admission')


def value_digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class BomSuccessorSourceContractTest(unittest.TestCase):
    def setUp(self):
        self.ledger_raw = (ROOT / 'Config/allocation_ownership.json').read_bytes()
        self.ledger = json.loads(self.ledger_raw)
        self.contract = json.loads(
            (ROOT / 'Config/lyra_current_source_contract.json').read_bytes())

    def test_successor_preserves_prior_ledger_and_ungranted_authority(self):
        previous = copy.deepcopy(self.ledger)
        previous['source_sets'].pop(SOURCE_SET)
        previous['sources'] = {key: row for key, row in previous['sources'].items()
                               if row['source_set'] != SOURCE_SET}
        self.assertEqual(len(previous['source_sets']), 41)
        self.assertEqual(len(previous['sources']), 1478)
        self.assertEqual(value_digest(previous), PREVIOUS_LEDGER_DIGEST)
        prior_contract = json.loads(read_snapshot(
            SOURCE58_HEAD, 'Config/lyra_current_source_contract.json'))
        for value in (self.contract, prior_contract):
            value['ledger'].pop('source_set')
            value['ledger'].pop('sha256')
        self.assertEqual(self.contract, prior_contract)
        for key in AUTHORITY_FLAGS:
            self.assertIs(self.contract[key], False, key)

    def test_successor_binds_complete_same_paths_and_actual_bytes(self):
        self.assertEqual(self.contract['ledger']['source_set'], SOURCE_SET)
        self.assertEqual(X.BOM_ADMISSION_SOURCE_SET, SOURCE_SET)
        self.assertEqual(self.contract['ledger']['sha256'],
                         hashlib.sha256(self.ledger_raw).hexdigest())
        current = {row['path']: row for row in self.ledger['sources'].values()
                   if row['source_set'] == SOURCE_SET}
        prior = {row['path']: row for row in self.ledger['sources'].values()
                 if row['source_set'] == X.SAVE_ADMISSION_SOURCE_SET}
        self.assertEqual(len(current), 72)
        self.assertEqual(set(current), set(prior))
        self.assertEqual({path for path in current
                          if current[path]['sha256'] != prior[path]['sha256']},
                         {'Scripts/Build/authoring_bundle_build.py',
                          'Scripts/Build/lyra_current_transfer.py'})
        bindings = P.validate_current_source_set(self.contract)
        self.assertEqual(len(bindings), 73)
        for path, row in current.items():
            self.assertEqual(self.ledger['sources'][SOURCE_SET + ':' + path], row)
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                             row['sha256'], path)

    def test_changed_successor_wrapper_still_refuses(self):
        with staged_source_set(ROOT, self.ledger_raw, SOURCE_SET, None) as root:
            with mock.patch.object(P, 'ROOT', root):
                self.assertEqual(len(P.validate_current_source_set(self.contract)), 73)
                wrapper = root / 'Scripts/Build/authoring_bundle_build.py'
                wrapper.write_bytes(wrapper.read_bytes() + b'\n# changed fixture\n')
                with self.assertRaisesRegex(ValueError,
                                            'Current source-set consumer changed'):
                    P.validate_current_source_set(self.contract)

    def test_successor_preserves_exact_source56_e3_reservation(self):
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

    def test_successor_uses_full_completeness_guard_and_rejects_missing_consumer(self):
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
