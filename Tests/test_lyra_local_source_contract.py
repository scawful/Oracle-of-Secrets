"""One local seed has exact source closure, never historical authority."""
import copy
import json
from pathlib import Path
import unittest
from unittest import mock

import lyra_current_transfer as X
import test_lyra_current_source_contract as fixtures


FLAGS = ('allocation_granted', 'publication_authorized',
         'producer_enforcement_verified', 'ordinary_build_ready', 'runtime_admission')
SEED = '0d1b0b49837ea7443b61aebc567b0cff93d0d0d6'
V2 = 'lyra_local_snapshot_c0_0d1b0b49_v2'
V2_PATHS = {
    'Scripts/Build/oracle_ordinary_build.py',
    'Scripts/Mesen2/mesen2_launch_instance.sh',
    'Scripts/Mesen2/yaze_dedicated_profile.py',
    'Scripts/Mesen2/yaze_dedicated_session.py',
}


class LocalSourceIdentityTest(unittest.TestCase):
    def test_v2_identity_requires_the_same_exact_seed(self):
        value = dict(engine_head=SEED, base_head=SEED,
                     ledger=dict(source_set='lyra_local_snapshot_c0_0d1b0b49_v2'))
        self.assertTrue(X._is_local_snapshot_source_set(value))
        for pair in ((SEED, '1'*40), ('1'*40, SEED), ('1'*40, '1'*40)):
            with self.subTest(pair=pair), self.assertRaisesRegex(
                    ValueError, 'CURRENT_LOCAL_SOURCE_SEED_MISMATCH'):
                X._is_local_snapshot_source_set(dict(value, engine_head=pair[0], base_head=pair[1]))

    def test_v2_exact_membership_preserves_v1_and_rejects_ambiguous_additions(self):
        self.assertEqual(X.LOCAL_SNAPSHOT_V2_SOURCE_SET, V2)
        self.assertEqual(set(X.LOCAL_SNAPSHOT_V2_ADDITIONAL_SOURCES), V2_PATHS)
        seed_paths = {f'fixture/seed-{index:03}.asm' for index in range(242)}
        raw = ('\0'.join(sorted(seed_paths)) + '\0').encode()
        root = Path('/fixed-source-membership-fixture')
        with mock.patch.object(X, '_git', return_value=raw) as command:
            v1 = X._local_snapshot_source_paths(root)
            command.assert_called_once_with(root, 'ls-tree', '-r', '--name-only', '-z', SEED)
            self.assertEqual(v1, seed_paths | set(X.LOCAL_SNAPSHOT_ADDITIONAL_SOURCES))
            self.assertEqual(len(v1), 303)
            v2 = X._local_snapshot_source_paths(root, source_set=V2)
            self.assertEqual(v2, v1 | V2_PATHS)
            self.assertEqual(len(v2), 307)
            context = dict(root=str(root), bindings=[])
            with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
                X._validate_local_snapshot_source_paths(context, sorted(v2))
            with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_SET_UNSUPPORTED'):
                X._local_snapshot_source_paths(root, source_set='unknown-local-set')
            for additions in (tuple(V2_PATHS) + (sorted(V2_PATHS)[0],),
                              tuple(sorted(V2_PATHS)[:-1]) + (sorted(v1)[0],)):
                with self.subTest(additions=additions), mock.patch.object(
                        X, 'LOCAL_SNAPSHOT_V2_ADDITIONAL_SOURCES', additions):
                    with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_V2_MEMBERSHIP_CHANGED'):
                        X._local_snapshot_source_paths(root, source_set=V2)
            with mock.patch.object(X, '_git', return_value=raw.split(b'\0', 1)[1]):
                with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_V2_MEMBERSHIP_CHANGED'):
                    X._local_snapshot_source_paths(root, source_set=V2)

    def test_production_identity_is_exact_and_not_a_historical_alias(self):
        self.assertEqual(X.LOCAL_SNAPSHOT_HEAD, SEED)
        value = dict(engine_head=SEED, base_head=SEED,
                     ledger=dict(source_set=X.LOCAL_SNAPSHOT_SOURCE_SET))
        self.assertTrue(X._is_local_snapshot_source_set(value))
        for pair in ((SEED, '1'*40), ('1'*40, SEED), ('1'*40, '1'*40)):
            with self.subTest(pair=pair), self.assertRaisesRegex(
                    ValueError, 'CURRENT_LOCAL_SOURCE_SEED_MISMATCH'):
                X._is_local_snapshot_source_set(dict(value, engine_head=pair[0], base_head=pair[1]))
        for name in (X.RESIDENT_SOURCE_SET, X.HIDDEN_STREAMS_SOURCE_SET,
                     X.PERSISTENT_REWARD_SOURCE_SET, X.SAVE_ADMISSION_SOURCE_SET,
                     X.BOM_ADMISSION_SOURCE_SET, 'unknown-local-set'):
            self.assertFalse(X._is_local_snapshot_source_set(
                dict(value, ledger=dict(source_set=name))))


class LocalSourceContractTest(unittest.TestCase):
    def setUp(self):
        self.host = fixtures.CurrentSourceContractTest()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.fixture = self.host.fixture
        self.root = self.fixture.root
        self.seed = self.fixture.head
        self.seed_ledger = self.host.value['ledger']['engine_ledger_sha256']
        # The source validator and Git lineage are real. Only the fixture's
        # newly created seed identity substitutes for the production C0 pin;
        # LocalSourceIdentityTest independently exercises that exact pin.
        patch = mock.patch.object(X, 'LOCAL_SNAPSHOT_HEAD', self.seed)
        patch.start()
        self.addCleanup(patch.stop)
        self.paths = X._local_snapshot_source_paths(self.root)
        for name in self.paths:
            path = self.root / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('; Inactive source binding fixture; never executed.\n')
        self.ledger_path = self.root / 'Config/allocation_ownership.json'
        self.ledger = json.loads(self.ledger_path.read_bytes())
        self.name = X.LOCAL_SNAPSHOT_SOURCE_SET
        self.ledger['source_sets'][self.name] = 'Truthful local seed plus owned fixture additions'
        for name in self.paths - {'Config/allocation_ownership.json'}:
            self.ledger['sources'][self.name + ':' + name] = dict(
                source_set=self.name, path=name, sha256=X.R.sha((self.root / name).read_bytes()))
        self.host.value.update(engine_head=self.seed, base_head=self.seed)
        self.host.value['ledger'].update(source_set=self.name, engine_ledger_sha256=self.seed_ledger)
        self.rebind()

    def rebind(self):
        self.ledger_path.write_bytes(X.P.encoded(self.ledger))
        # Explicit source paths only, including the ledger but never the ROM,
        # saved descriptor, contract file or evidence outside this fixture.
        self.fixture.git('add', '--', *sorted(self.paths))
        self.fixture.git('commit', '--allow-empty', '-qm', 'Owned local source fixture')
        self.fixture.head = self.fixture.git('rev-parse', 'HEAD').strip()
        self.fixture.refresh_proposal_source()
        self.host.review = self.fixture.review()
        self.host.value['ledger']['sha256'] = X.Q.bound(self.ledger_path)['sha256']
        self.host.write()

    def test_complete_local_set_reaches_existing_resident_origin_gate_without_authority(self):
        profile = self.host.profile()
        self.assertEqual({Path(row['path']).relative_to(self.root).as_posix()
                          for row in profile['current_source_bindings']}, self.paths)
        for name in FLAGS:
            self.assertIs(profile[name], False)
        source, document = self.host.inputs()
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_ORIGIN_UNBOUND'):
            X.current_resident_inputs(profile, source, document,
                dict(inspection=None, graphics_catalog=None, graphics_policy=None))
        self.assertFalse(self.host.case.candidate.exists())

    def test_every_required_path_extra_duplicate_and_new_include_refuse(self):
        context = self.host.review['selected_source']
        paths = sorted(self.paths)
        X._validate_local_snapshot_source_paths(context, paths)
        for name in paths:
            with self.subTest(omitted=name), self.assertRaisesRegex(
                    ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
                X._validate_local_snapshot_source_paths(context, [p for p in paths if p != name])
        for altered in (paths + ['Overworld/unselected.asm'], paths + [paths[0]]):
            with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
                X._validate_local_snapshot_source_paths(context, altered)
        changed = dict(context, bindings=context['bindings'] + [
            dict(path=str(self.root/'Overworld/newly-reachable.asm'), sha256='0'*64)])
        with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
            X._validate_local_snapshot_source_paths(changed, paths)

    def test_truthfully_committed_missing_and_extra_ledger_rows_refuse(self):
        key = self.name + ':Overworld/lyra_resident_resources.asm'
        row = self.ledger['sources'].pop(key)
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
            self.host.profile()
        self.ledger['sources'][key] = row
        path = self.root/'Overworld/unselected.asm'
        path.write_text('; Extra committed source is still outside the local set.\n')
        self.ledger['sources'][self.name+':Overworld/unselected.asm'] = dict(
            source_set=self.name, path='Overworld/unselected.asm', sha256=X.R.sha(path.read_bytes()))
        self.fixture.git('add', '--', 'Overworld/unselected.asm')
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
            self.host.profile()

    def test_stale_then_rehashed_uncommitted_compiler_refuses(self):
        name = 'Scripts/Build/lyra_native_loaders.py'
        path = self.root/name
        path.write_bytes(path.read_bytes()+b'; Changed but not committed.\n')
        with self.assertRaisesRegex(ValueError, 'source-set consumer changed'):
            self.host.profile()
        self.ledger['sources'][self.name+':'+name]['sha256'] = X.R.sha(path.read_bytes())
        self.ledger_path.write_bytes(X.P.encoded(self.ledger))
        self.fixture.git('add', '--', 'Config/allocation_ownership.json')
        self.fixture.git('commit', '-qm', 'Only rehash ledger; leave compiler outside commit')
        self.fixture.head = self.fixture.git('rev-parse', 'HEAD').strip()
        self.fixture.refresh_proposal_source()
        self.host.review = self.fixture.review()
        self.host.value['ledger']['sha256'] = X.Q.bound(self.ledger_path)['sha256']
        self.host.write()
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_SET_ENGINE_MISMATCH'):
            self.host.profile()

    def test_seed_ledger_authority_and_unrelated_selected_lineage_refuse(self):
        original = copy.deepcopy(self.host.value)
        for name in FLAGS:
            self.host.value = copy.deepcopy(original)
            self.host.value[name] = True
            self.host.write()
            with self.subTest(flag=name), self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_CONTRACT_UNGRANTED'):
                self.host.profile()
        self.host.value = copy.deepcopy(original)
        self.host.value['ledger']['engine_ledger_sha256'] = '0'*64
        self.host.write()
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_ENGINE_LEDGER_MISMATCH'):
            self.host.profile()
        self.host.value = original
        self.host.write()
        # A second parentless commit with identical current files is not C0's
        # descendant. It must fail even though every source hash still matches.
        self.fixture.git('checkout', '--orphan', 'unrelated-local-fixture')
        self.fixture.git('add', '--', *sorted(self.paths))
        self.fixture.git('commit', '-qm', 'Unrelated owned fixture root')
        self.fixture.head = self.fixture.git('rev-parse', 'HEAD').strip()
        self.fixture.refresh_proposal_source()
        self.host.review = self.fixture.review()
        with self.assertRaises((ValueError, X.subprocess.CalledProcessError)):
            self.host.profile()

    def test_unknown_set_and_local_hidden_stream_authority_remain_refused(self):
        profile = self.host.profile()
        contract = copy.deepcopy(self.host.value)
        with self.assertRaisesRegex(ValueError, 'HIDDEN_STREAM_SOURCE_SET_REQUIRED'):
            X._hidden_streams_reservation(contract, self.ledger)
        old = self.name
        name = 'unknown-local-set'
        self.ledger['source_sets'][name] = 'Unknown local fixture set'
        for key, row in list(self.ledger['sources'].items()):
            if row['source_set'] == old:
                self.ledger['sources'][name+':'+row['path']] = dict(row, source_set=name)
        self.host.value['ledger']['source_set'] = name
        self.rebind()
        profile = self.host.profile()
        source, document = self.host.inputs()
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_SOURCE_SET_REQUIRED'):
            X.current_resident_inputs(profile, source, document,
                dict(inspection=None, graphics_catalog=None, graphics_policy=None))


class LocalSourceV2ContractTest(LocalSourceContractTest):
    """Reuse all source/lineage/authority controls with a real307-path Git set."""
    def setUp(self):
        super().setUp()
        # Build a disposable303-path seed without weakening the production
        # cardinality check. The existing real Git fixture stays isolated.
        names = set(self.fixture.git('ls-tree', '-r', '--name-only', 'HEAD').splitlines())
        missing = 303 - len(names | set(X.LOCAL_SNAPSHOT_ADDITIONAL_SOURCES))
        self.assertGreater(missing, 0)
        fillers = [f'Overworld/source-v2-fixture-{index:03}.asm' for index in range(missing)]
        for name in fillers:
            (self.root / name).write_text('; Inactive owned source-membership fixture.\n')
        self.fixture.git('add', '--', *fillers)
        self.fixture.git('commit', '-qm', 'Owned303-path local seed fixture')
        self.seed = self.fixture.git('rev-parse', 'HEAD').strip()
        patch = mock.patch.object(X, 'LOCAL_SNAPSHOT_HEAD', self.seed)
        patch.start()
        self.addCleanup(patch.stop)
        self.seed_ledger = X.Q.bound(self.ledger_path)['sha256']
        self.host.value.update(engine_head=self.seed, base_head=self.seed)
        self.host.value['ledger']['engine_ledger_sha256'] = self.seed_ledger
        self.name = V2
        self.paths = X._local_snapshot_source_paths(self.root, source_set=self.name)
        self.assertEqual(len(self.paths), 307)
        old_rows = copy.deepcopy(self.ledger['sources'])
        self.ledger['source_sets'][self.name] = 'Owned local v2 fixture; no authority'
        for name in self.paths - {'Config/allocation_ownership.json'}:
            path = self.root / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# Bound runtime fixture; never executed.\n')
            self.ledger['sources'][self.name+':'+name] = dict(
                source_set=self.name, path=name, sha256=X.R.sha(path.read_bytes()))
        self.assertTrue(all(self.ledger['sources'][key] == row for key, row in old_rows.items()))
        self.host.value['ledger']['source_set'] = self.name
        self.rebind()

    def test_every_required_path_extra_duplicate_and_new_include_refuse(self):
        context = self.host.review['selected_source']
        paths = sorted(self.paths)
        X._validate_local_snapshot_source_paths(context, paths, source_set=V2)
        for name in paths:
            with self.subTest(omitted=name), self.assertRaisesRegex(
                    ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
                X._validate_local_snapshot_source_paths(
                    context, [p for p in paths if p != name], source_set=V2)
        for altered in (paths + ['Overworld/unselected.asm'], paths + [paths[0]]):
            with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
                X._validate_local_snapshot_source_paths(context, altered, source_set=V2)
        changed = dict(context, bindings=context['bindings'] + [
            dict(path=str(self.root/'Overworld/newly-reachable.asm'), sha256='0'*64)])
        with self.assertRaisesRegex(ValueError, 'CURRENT_LOCAL_SOURCE_SET_INCOMPLETE'):
            X._validate_local_snapshot_source_paths(changed, paths, source_set=V2)

    def test_each_new_runtime_requires_unchanged_committed_bytes(self):
        for name in sorted(V2_PATHS):
            with self.subTest(runtime=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b'# Uncommitted runtime change.\n')
                with self.assertRaisesRegex(ValueError, 'source-set consumer changed'):
                    self.host.profile()
                self.ledger['sources'][self.name+':'+name]['sha256'] = X.R.sha(path.read_bytes())
                self.ledger_path.write_bytes(X.P.encoded(self.ledger))
                self.fixture.git('add', '--', 'Config/allocation_ownership.json')
                self.fixture.git('commit', '-qm', 'Rehash but do not commit runtime fixture')
                self.fixture.head = self.fixture.git('rev-parse', 'HEAD').strip()
                self.fixture.refresh_proposal_source()
                self.host.review = self.fixture.review()
                self.host.value['ledger']['sha256'] = X.Q.bound(self.ledger_path)['sha256']
                self.host.write()
                with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_SET_ENGINE_MISMATCH'):
                    self.host.profile()
                path.write_bytes(original)
                self.ledger['sources'][self.name+':'+name]['sha256'] = X.R.sha(original)
                self.rebind()
                self.host.profile()


if __name__ == '__main__':
    unittest.main()
