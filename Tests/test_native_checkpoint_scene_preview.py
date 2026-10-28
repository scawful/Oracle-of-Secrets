"""Ferry/Sky scene driver host controls; no socket, emulator, ROM or WRAM write."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent/'native'))
import native_checkpoint_scene_preview as N

C, T, Q = N.C, N.T, N.Q
SOURCE = hashlib.sha256(b'saved source').hexdigest()
TRANSFER = hashlib.sha256(b'transfer').hexdigest()
DOCUMENT = hashlib.sha256(b'document').hexdigest()
MAPS = {2: ('SPECIAL', 0xA0, (0xA0, 0xA1)), 3: ('LIGHT', 0x30, (0x30, 0x31)), 4: ('SPECIAL', 0x87, (0x87,))}
DERIVED = {3: dict(stable_after_walk=[768, 3443]), 4: dict(stable_after_walk=[3728, 259])}


def cache(key, fill=0):
    parent = MAPS[key][1]
    return parent.to_bytes(2, 'little') + bytes([fill])*10 + parent.to_bytes(2, 'little') + bytes([fill])*36


def sram(checkpoint):
    raw = bytearray(8192)
    raw[0x3B4:0x3B9] = bytes.fromhex(checkpoint)
    total = sum(int.from_bytes(raw[i:i+2], 'little') for i in range(0, 0x4FE, 2))
    raw[0x4FE:0x500] = ((0x5A5A - total) & 0xFFFF).to_bytes(2, 'little')
    raw[0xF00:0x1400] = raw[:0x500]
    return bytes(raw)


class SceneWorld:
    """Real files and pins for one synthetic v2 plan; heavy derivations are mocked."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.caches = {key: cache(key, key) for key in MAPS}
        self.derivation = dict(self.caches)
        self.native_calls = []
        receipt = self.write('receipt.json', dict(artifacts=[dict(role='project', path=str(self.folder/'project.yaze'))]))
        self.write('geometry.asm', b'; geometry\n')
        self.packet = dict(kind='lyra.joint_art_packet.v1', source_rom_sha256=SOURCE, generation=4,
            operation_id='op-4', transfer_id=TRANSFER,
            sheets=[dict(stream=Q.bound(self.write('sheet.bin', b'\x01'*32)))],
            ferry=dict(types=Q.bound(self.write('types.bin', bytes([0, 2, 8]*29+[0, 2]))),
                       graphics=Q.bound(self.write('gfx.bin', b'\x00'*0xB20))))
        self.live = dict(generation=4, operation_id='op-4', save_receipt=Q.bound(receipt),
                         inputs=dict(rom=dict(path='/saved/rom', sha256=SOURCE)))
        self.landings = {3: dict(key=3, clear_radius=1), 4: dict(key=4, clear_radius=1)}
        self.plan = None

    def write(self, name, value):
        path = self.folder/name
        path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
        return path

    def build(self):
        bindings = dict(source_rom_sha256=SOURCE, document_sha256=DOCUMENT, transfer_id=TRANSFER,
            live={k: self.live[k] for k in ('generation', 'operation_id', 'save_receipt')},
            selected_pair=[0xA0, 0xA1],
            cache_source=Q.bound(self.write('a0-landing.json',
                dict(geometry_source=Q.bound(self.folder/'geometry.asm')))),
            joint_art=Q.bound(self.write('packet.json', self.packet)),
            native_landings=[Q.bound(self.write(f'landing-{k}.json', self.landings[k])) for k in (3, 4)])
        entries, members = [], []
        for key, (domain, parent, maps) in MAPS.items():
            raw = self.caches[key]
            entries.append(dict(key=key, domain=domain, map_id=parent, parent_map=parent, native_affinity=0,
                                region_key=key, exit_cache_hex=raw.hex(), cache_sha256=hashlib.sha256(raw).hexdigest()))
            members += [dict(map_id=m, domain=domain, native_affinity=0, region_key=key) for m in maps]
        self.plan = dict(kind=C.PREVIEW_PLAN_V2, scope='seeded_private_preview', production_admission=False,
                         epoch=1, bindings=bindings, entries=entries, memberships=members)
        return self

    def save(self, raw=None):
        raw = raw if raw is not None else json.dumps(self.plan).encode()
        path = self.folder/'plan.json'
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def native_cache(self, image, landing, binding):
        self.native_calls.append((image, landing, binding))
        return self.derivation[landing['key']], DERIVED[landing['key']]

    def read(self, key=3, source=SOURCE, raw=None):
        path, digest = self.save(raw)
        with mock.patch.object(T, '_live', return_value=self.live) as live, \
                mock.patch.object(C, 'native_preview_cache', side_effect=self.native_cache):
            result = N.read_scene_plan(path, digest, source, key, b'candidate')
        live.assert_called_once_with(self.folder/'project.yaze')
        return result


class ReadScenePlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.world = SceneWorld(self.tmp.name).build()

    def tearDown(self):
        self.tmp.cleanup()

    def refuse(self, pattern, error=RuntimeError, **kwargs):
        # Driver refusals raise RuntimeError; registry/pin validators raise ValueError.
        with self.assertRaisesRegex(error, pattern):
            self.world.read(**kwargs)

    def test_accepts_exact_v2_plan_for_keys_3_and_4_with_candidate_derivation(self):
        for key in (3, 4):
            self.world.native_calls.clear()
            plan, raw, derived = self.world.read(key=key)
            self.assertEqual(raw, self.world.caches[key])
            self.assertEqual(derived, DERIVED[key])
            self.assertEqual([e['key'] for e in plan['entries']], [2, 3, 4])
            self.assertEqual([call[1]['key'] for call in self.world.native_calls], [3, 4])
            for image, _, binding in self.world.native_calls:
                self.assertEqual(image, b'candidate')
                self.assertEqual(binding, dict(source_rom_sha256=SOURCE, transfer_id=TRANSFER, generation=4,
                    operation_id='op-4', joint_art=plan['bindings']['joint_art'],
                    ferry_types=self.world.packet['ferry']['types']))

    def test_only_native_keys_3_and_4_are_selectable(self):
        for key in (2, 5, True, '3', None):
            with self.subTest(key=key):
                self.refuse('Only native scene keys3/4', key=key)

    def test_plan_digest_source_and_duplicate_keys_refuse(self):
        path, digest = self.world.save()
        with self.assertRaisesRegex(RuntimeError, 'requires an exact SHA256'):
            N.read_scene_plan(path, digest.upper(), SOURCE, 3, b'candidate')
        with self.assertRaisesRegex(RuntimeError, 'plan SHA256 changed'):
            N.read_scene_plan(path, hashlib.sha256(b'other').hexdigest(), SOURCE, 3, b'candidate')
        self.refuse('Scene source ROM differs', source=hashlib.sha256(b'other source').hexdigest())
        raw = json.dumps(self.world.plan).encode()
        duplicate = raw.replace(b'"epoch": 1', b'"epoch": 1, "epoch": 1')
        self.refuse('Duplicate scene-plan/artifact key: epoch', raw=duplicate)

    def test_plan_header_must_be_epoch1_seeded_private_v2(self):
        for name, change in (('v1 kind', dict(kind='checkpoint.private_preview_plan.v1')),
                             ('scope', dict(scope='production')), ('admitted', dict(production_admission=True)),
                             ('epoch2', dict(epoch=2)), ('epoch bool', dict(epoch=True)), ('extra', dict(extra=1))):
            with self.subTest(name):
                self.world.plan.update(change)
                self.refuse('Expected the explicit epoch1 seeded private v2 plan')
                self.world.build()

    def test_rebound_live_save_refuses(self):
        for name, change in (('generation', dict(generation=5)), ('operation', dict(operation_id='op-5')),
                             ('receipt', dict(save_receipt=dict(path='/other', sha256=SOURCE))),
                             ('rom', dict(inputs=dict(rom=dict(path='/saved/rom', sha256=TRANSFER))))):
            with self.subTest(name):
                original = copy.deepcopy(self.world.live)
                self.world.live.update(change)
                self.refuse('Scene plan differs from the live native Save/source')
                self.world.live = original
        path, digest = self.world.save()
        with mock.patch.object(T, '_live', side_effect=ValueError('CURRENT_SAVE_CONTEXT_REQUIRED')), \
                self.assertRaisesRegex(ValueError, 'CURRENT_SAVE_CONTEXT_REQUIRED'):
            N.read_scene_plan(path, digest, SOURCE, 3, b'candidate')

    def test_receipt_must_bind_exactly_one_project(self):
        for artifacts in ([], [dict(role='project', path='/a'), dict(role='project', path='/b')]):
            with self.subTest(count=len(artifacts)):
                receipt = self.world.write('receipt.json', dict(artifacts=artifacts))
                self.world.live['save_receipt'] = Q.bound(receipt)
                self.world.build()
                self.refuse('Native Save must bind exactly one project')

    def test_changed_pinned_artifact_refuses(self):
        for name in ('packet.json', 'landing-4.json', 'a0-landing.json', 'geometry.asm', 'types.bin'):
            with self.subTest(name):
                self.world.build()
                path, digest = self.world.save()
                target = self.world.folder/name
                original = target.read_bytes()
                target.write_bytes(original+b' ')
                with mock.patch.object(T, '_live', return_value=self.world.live), \
                        mock.patch.object(C, 'native_preview_cache', side_effect=self.world.native_cache), \
                        self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                    N.read_scene_plan(path, digest, SOURCE, 3, b'candidate')
                target.write_bytes(original)

    def test_packet_identity_and_ferry_payload_refuse(self):
        cases = (('kind', 'kind', 'lyra.joint_art_packet.v0', 'Save/transfer binding differs'),
                 ('transfer', 'transfer_id', DOCUMENT, 'Save/transfer binding differs'),
                 ('generation', 'generation', 3, 'Save/transfer binding differs'),
                 ('generation bool', 'generation', True, 'Save/transfer binding differs'),
                 ('source', 'source_rom_sha256', DOCUMENT, 'Save/transfer binding differs'))
        for name, field, value, pattern in cases:
            with self.subTest(name):
                original = copy.deepcopy(self.world.packet)
                self.world.packet[field] = value
                self.world.build()
                self.refuse(pattern)
                self.world.packet = original
        for name, data in (('short types', bytes(88)), ('bad type', bytes([3])+bytes(88))):
            with self.subTest(name):
                self.world.packet['ferry']['types'] = Q.bound(self.world.write('types.bin', data))
                self.world.build()
                self.refuse('Scene ferry type/graphics payload differs')
        self.world.packet['ferry']['types'] = Q.bound(self.world.write('types.bin', bytes(89)))
        self.world.packet['ferry']['graphics'] = Q.bound(self.world.write('gfx.bin', bytes(0xB1F)))
        self.world.build()
        self.refuse('Scene ferry type/graphics payload differs')

    def test_landing_order_key_and_radius_refuse(self):
        self.world.build()
        self.world.plan['bindings']['native_landings'].reverse()
        self.refuse('Scene native landing key/order/radius differs')
        for change in (dict(clear_radius=2), dict(clear_radius=True), dict(key=5)):
            with self.subTest(change):
                self.world.landings[4] = dict(dict(key=4, clear_radius=1), **change)
                self.world.build()
                self.refuse('Scene native landing key/order/radius differs')
        self.world.plan['bindings']['native_landings'].pop()
        self.refuse('one landing per native key', ValueError)

    def test_entries_must_stay_exact_keys_2_3_4(self):
        def change(index, **fields):
            self.world.build()
            self.world.plan['entries'][index].update(fields)
        for index, fields, pattern in (
                (1, dict(map_id=0x31), 'exceeds the approved preview'),
                (1, dict(domain='SPECIAL'), 'exceeds the approved preview'),
                (2, dict(region_key=3), 'exceeds the approved preview'),
                (2, dict(native_affinity=0x40), 'exceeds the approved preview'),
                (0, dict(map_id=0xA1), 'exceeds the approved preview'),
                (1, dict(extra=1), 'Malformed scene checkpoint entry'),
                (2, dict(exit_cache_hex='00'*49), 'exactly50 bytes'),
                (2, dict(exit_cache_hex=cache(4, 0xAB).hex().upper()), 'exactly50 bytes'),
                (2, dict(cache_sha256=hashlib.sha256(b'x').hexdigest()), 'Scene cache SHA256 differs')):
            with self.subTest(index=index, fields=fields):
                change(index, **fields)
                self.refuse(pattern)
        self.world.build()
        self.world.plan['entries'].pop(0)
        self.refuse('must keep exactly keys2/3/4')

    def test_plan_cache_must_equal_candidate_native_derivation_for_every_native_key(self):
        for mismatch in (3, 4):
            for selected in (3, 4):
                with self.subTest(mismatch=mismatch, selected=selected):
                    self.world.derivation = dict(self.world.caches)
                    self.world.derivation[mismatch] = cache(mismatch, 0xEE)
                    self.refuse('Scene cache differs from candidate-native derivation', key=selected)
        self.world.derivation = dict(self.world.caches)
        self.world.caches[3] = cache(3, 0x55)[:12] + (0x31).to_bytes(2, 'little') + cache(3, 0x55)[14:]
        self.world.build()
        self.refuse('cache physical map disagrees', ValueError)

    def test_memberships_must_be_exact(self):
        for name, mutate in (
                ('reordered', lambda m: m.reverse()),
                ('extra map', lambda m: m.append(dict(map_id=0x32, domain='LIGHT', native_affinity=0, region_key=3))),
                ('missing sky', lambda m: m.pop()),
                ('bool affinity', lambda m: m[2].update(native_affinity=False)),
                ('dark domain', lambda m: m[4].update(domain='DARK'))):
            with self.subTest(name):
                self.world.build()
                mutate(self.world.plan['memberships'])
                self.refuse('Scene membership exceeds the explicit preview')


class SavedCheckpointTest(unittest.TestCase):
    def test_checkpoint_bytes_are_schema_epoch_key_regional(self):
        plan = dict(epoch=1)
        self.assertEqual(N.checkpoint_bytes(plan, 3), '0101030001')
        self.assertEqual(N.checkpoint_bytes(plan, 4), '0101040001')

    def test_saved_sram_requires_mirror_checksum_and_selected_checkpoint(self):
        good = sram('0101040001')
        N.validate_saved_sram(good, '0101040001')
        with self.assertRaisesRegex(RuntimeError, 'lost selected scene checkpoint'):
            N.validate_saved_sram(good, '0101030001')
        with self.assertRaisesRegex(RuntimeError, 'readback incomplete'):
            N.validate_saved_sram(good[:-1], '0101040001')
        backup = bytearray(good); backup[0xF10] ^= 1
        with self.assertRaisesRegex(RuntimeError, 'primary/backup mismatch'):
            N.validate_saved_sram(bytes(backup), '0101040001')
        both = bytearray(good); both[0x10] ^= 1; both[0xF10] ^= 1
        with self.assertRaisesRegex(RuntimeError, 'checksum invalid'):
            N.validate_saved_sram(bytes(both), '0101040001')


def state(key, **fields):
    x, y = DERIVED[key]['stable_after_walk']
    value = dict(module=9, sub=0, indoors=0, map=MAPS[key][1], world=0, x=x, y=y, hp=24,
                 checkpoint=N.checkpoint_bytes(dict(epoch=1), key))
    value.update(fields)
    return value


class SceneEpisodeTest(unittest.TestCase):
    def episode(self, key=3, phase='live', output=None):
        e = object.__new__(N.SceneEpisode)
        e.a = argparse.Namespace(rom=Path('/private/candidate.sfc'), output=Path(output or '/nonexistent'))
        e.b = mock.Mock()
        e.phase, e.key, e.scene = phase, key, C.NATIVE_PREVIEW[key]
        e.derived, e.cache = DERIVED[key], cache(key, key)
        e.checkpoint = N.checkpoint_bytes(dict(epoch=1), key)
        e.result = dict(cases=[], writes=[])
        e.owner = mock.Mock()
        parent = MAPS[key][1].to_bytes(2, 'little')
        e.b.read_block.side_effect = lambda address, count, **kw: {0x7EC140: e.cache, 0x7E040A: parent}[address]
        return e

    def test_command_scope_and_live_same_rom_flush_only(self):
        with mock.patch.object(N.LyraEpisode, 'command', return_value='ok') as parent:
            live = self.episode()
            for name in ('STATE', 'FRAME', 'INPUT', 'SCREENSHOT', 'BREAKPOINT', 'PAUSE'):
                self.assertEqual(live.command(name), 'ok')
            self.assertEqual(live.command('LOADROM', {'path': '/private/candidate.sfc'}), 'ok')
            for name in ('WRITE', 'SETPC', 'SAVESTATE', 'LOADSTATE', 'RESET'):
                with self.assertRaisesRegex(RuntimeError, 'outside scene preview scope'):
                    live.command(name)
            with self.assertRaisesRegex(RuntimeError, 'Only live same-ROM battery flush'):
                live.command('LOADROM', {'path': '/private/other.sfc'})
            with self.assertRaisesRegex(RuntimeError, 'Only live same-ROM battery flush'):
                self.episode(phase='reopen').command('LOADROM', {'path': '/private/candidate.sfc'})
        self.assertEqual(parent.call_count, 7)

    def test_reopen_phase_never_damages(self):
        with mock.patch.object(N.LyraEpisode, 'damage', return_value='gameover') as parent:
            reopen = self.episode(phase='reopen')
            with self.assertRaisesRegex(RuntimeError, 'Reopen phase is read-only'):
                reopen.damage()
            parent.assert_not_called()
            self.assertEqual(self.episode().damage(), 'gameover')

    def test_destination_requires_complete_cache_parent_walk_and_checkpoint(self):
        for key in (3, 4):
            e = self.episode(key)
            e.require_regional_destination(state(key))
            self.assertEqual(e.result['cache_checks'][0]['sha256'], hashlib.sha256(e.cache).hexdigest())
            for field, value in (('y', state(key)['y']-1), ('x', state(key)['x']+16), ('map', 0x31),
                                 ('world', 0x40), ('module', 7), ('indoors', 1),
                                 ('checkpoint', '0101020001')):
                with self.subTest(key=key, field=field):
                    with self.assertRaisesRegex(RuntimeError, 'destination/19px walk/checkpoint mismatch'):
                        e.require_regional_destination(state(key, **{field: value}))
        e = self.episode(4)
        e.cache = cache(4, 0xEE)
        e.b.read_block.side_effect = lambda address, count, **kw: {0x7EC140: cache(4, 4), 0x7E040A: b'\x87\x00'}[address]
        with self.assertRaisesRegex(RuntimeError, 'complete50-byte native cache mismatch'):
            e.require_regional_destination(state(4))
        e = self.episode(4)
        e.b.read_block.side_effect = lambda address, count, **kw: {0x7EC140: e.cache, 0x7E040A: b'\x87\x01'}[address]
        with self.assertRaisesRegex(RuntimeError, 'runtime parent mismatch'):
            e.require_regional_destination(state(4))

    def test_reopen_only_checks_destination_and_screenshots(self):
        e = self.episode(4, phase='reopen')
        e.sample = mock.Mock(return_value=state(4))
        for name in ('screenshot', 'press', 'damage', 'choose_gameover', 'wait', 'command'):
            setattr(e, name, mock.Mock())
        e.regional()
        e.screenshot.assert_called_once_with('cold-reopened-scene-checkpoint')
        for name in ('press', 'damage', 'choose_gameover', 'wait', 'command'):
            getattr(e, name).assert_not_called()
        self.assertEqual(len(e.result['cache_checks']), 1)

    def live_episode(self, folder, moved_dx=6, returned_dx=1, saved=None):
        e = self.episode(3, output=folder)
        base = state(3)
        e.sample = mock.Mock(side_effect=[base, base, state(3, x=base['x']+moved_dx),
                                          state(3, x=base['x']+returned_dx)])
        for name in ('screenshot', 'press', 'damage', 'choose_gameover', 'command'):
            setattr(e, name, mock.Mock())
        e.wait = mock.Mock(side_effect=[base, state(3, module=1)])
        raw = saved if saved is not None else sram(e.checkpoint)
        e.b.read_block.side_effect = lambda address, count, **kw: (
            raw if kw.get('memtype') == 'SnesSaveRam' else
            {0x7EC140: e.cache, 0x7E040A: b'\x30\x00'}[address])
        return e

    def test_live_lifecycle_moves_dies_continues_saves_and_flushes_same_rom(self):
        with tempfile.TemporaryDirectory() as folder:
            e = self.live_episode(folder)
            e.regional()
            self.assertEqual([c.args for c in e.press.call_args_list], [('right', 8), ('left', 8)])
            self.assertEqual([c.args for c in e.choose_gameover.call_args_list], [(0,), (1,)])
            self.assertEqual(e.damage.call_count, 2)
            self.assertIs(e.wait.call_args_list[0].args[0].__func__, N.SceneEpisode.ordinary)
            e.command.assert_called_once_with('LOADROM', {'path': '/private/candidate.sfc'})
            self.assertEqual(len(e.result['cache_checks']), 2)
            self.assertEqual(e.result['native_save_sha256'],
                             hashlib.sha256(sram(e.checkpoint)).hexdigest())
            self.assertTrue(e.result['battery_flush_requested'])

    def test_live_lifecycle_refuses_bad_movement_or_lost_saved_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            for moved, returned, pattern in ((0, 0, 'Right8 left'), (17, 1, 'Right8 left'),
                                             (6, 6, 'Left8 did not return')):
                with self.subTest(moved=moved, returned=returned):
                    e = self.live_episode(folder, moved, returned)
                    with self.assertRaisesRegex(RuntimeError, pattern):
                        e.regional()
                    e.damage.assert_not_called()
            e = self.live_episode(folder, saved=sram('0101020001'))
            with self.assertRaisesRegex(RuntimeError, 'lost selected scene checkpoint'):
                e.regional()
            e.command.assert_not_called()

    def test_ordinary_requires_scene_parent_world_hp_and_checkpoint(self):
        e = self.episode(4)
        self.assertTrue(e.ordinary(state(4)))
        for field, value in (('hp', 0), ('map', 0xA0), ('world', 0x40), ('sub', 1), ('checkpoint', '0101030001')):
            with self.subTest(field=field):
                self.assertFalse(e.ordinary(state(4, **{field: value})))


class FakeEpisode:
    writes = []

    def __init__(self, args, bridge, plan, cache, derived):
        self.a, self.b = args, mock.Mock()
        self.b.send_command.return_value = dict(success=True)
        here = Path(N.__file__)
        self.result = dict(passed=False, inputs=[], frame_advances=[], cleanup_errors=[],
                           writes=list(self.writes), provenance=dict(
                scene_driver_sha256=N.sha(here), lyra_driver_sha256=N.sha(here.with_name('lyra_checkpoint_preview.py')),
                regional_driver_sha256=N.sha(here.with_name('regional_checkpoint.py')),
                registry_source_sha256=N.sha(Path(C.__file__)), transfer_source_sha256=N.sha(Path(T.__file__))))

    def owner(self):
        pass

    def run(self):
        self.result['passed'] = True


class MainContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.rom = root/'candidate.sfc'
        self.rom.write_bytes(b'candidate rom')
        client = root/'client/mesen2_client_lib'
        client.mkdir(parents=True)
        (client/'__init__.py').write_text('')
        (client/'bridge.py').write_text('class MesenBridge:\n    def __init__(self, *a, **k):\n        pass\n')
        self.root = root
        self.saved_modules = {k: v for k, v in sys.modules.items() if k.startswith('mesen2_client_lib')}

    def tearDown(self):
        for name in [k for k in sys.modules if k.startswith('mesen2_client_lib')]:
            del sys.modules[name]
        sys.modules.update(self.saved_modules)
        self.tmp.cleanup()

    def argv(self, phase='live', output='out', socket='/tmp/owned.sock', execute=True, rom_sha256=None):
        image = self.rom.read_bytes()
        args = ['--socket', socket, '--owner', 'root', '--token', 't', '--pid', '1',
                '--rom-sha1', hashlib.sha1(image).hexdigest(),
                '--rom-sha256', rom_sha256 or hashlib.sha256(image).hexdigest(),
                '--source-rom-sha256', SOURCE, '--checkpoint-plan-sha256', SOURCE,
                '--owner-file', str(self.root/'owner'), '--status-file', str(self.root/'status'),
                '--rom', str(self.rom), '--client-root', str(self.root/'client'),
                '--output', str(self.root/output), '--checkpoint-plan', str(self.root/'plan.json'),
                '--key', '4', '--phase', phase]
        return args + (['--execute-fixtures'] if execute else [])

    def test_admission_refusals_happen_before_plan_or_output(self):
        with mock.patch.object(N, 'read_scene_plan') as reader:
            for argv, pattern in ((self.argv(execute=False), 'Explicit copied-save fixture admission'),
                                  (self.argv(socket='/tmp/oos-rc-play.sock'), 'Protected emulator endpoint'),
                                  (self.argv(socket='/tmp/oos-scawful-test.sock'), 'Protected emulator endpoint'),
                                  (self.argv(rom_sha256=SOURCE), 'Private ROM SHA256 changed')):
                with self.subTest(pattern=pattern), self.assertRaisesRegex(RuntimeError, pattern):
                    N.main(argv)
            reader.assert_not_called()
        self.assertFalse((self.root/'out').exists())
        with self.assertRaises(SystemExit), mock.patch('sys.stderr'):
            N.main(self.argv()[:-3]+['--key', '2', '--phase', 'live', '--execute-fixtures'])

    def run_main(self, phase, writes, output):
        FakeEpisode.writes = writes
        with mock.patch.object(N, 'read_scene_plan', return_value=({}, b'', {})) as reader, \
                mock.patch.object(N, 'SceneEpisode', FakeEpisode), \
                mock.patch('builtins.print'):
            code = N.main(self.argv(phase=phase, output=output))
        self.assertEqual(reader.call_count, 2)
        self.assertEqual(reader.call_args.args[3:], (4, self.rom.read_bytes()))
        return code, json.loads((self.root/output/'RESULT.json').read_text())

    def test_only_inherited_damage_writes_are_accepted(self):
        damage = [dict(address='7E037B'), dict(address='7E0373')]*2
        code, result = self.run_main('live', damage, 'live-ok')
        self.assertEqual((code, result['passed'], result['counts']['fixture_writes']), (0, True, 4))
        for name, phase, writes in (('extra WRAM', 'live', damage[:3]+[dict(address='7E0010')]),
                                    ('short', 'live', damage[:2]),
                                    ('reopen write', 'reopen', damage[:1])):
            with self.subTest(name):
                code, result = self.run_main(phase, writes, 'out-'+name.replace(' ', '-'))
                self.assertEqual((code, result['passed']), (1, False))
                self.assertIn('Unexpected scene fixture writes', result['error'])
        code, result = self.run_main('reopen', [], 'reopen-ok')
        self.assertEqual((code, result['passed']), (0, True))


@unittest.skipUnless(os.environ.get('OOS_SCENE_PREVIEW_PLAN') and os.environ.get('OOS_SCENE_PREVIEW_CANDIDATE')
                     and os.environ.get('YAZE_NATIVE_SAVE_CONTEXT'),
                     'Set OOS_SCENE_PREVIEW_PLAN, OOS_SCENE_PREVIEW_CANDIDATE and YAZE_NATIVE_SAVE_CONTEXT '
                     'for the genuine v2 plan/Save/candidate reproduction')
class GenuineScenePlanTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(os.environ['OOS_SCENE_PREVIEW_PLAN'])
        self.raw = self.path.read_bytes()
        self.plan = json.loads(self.raw)
        self.source = self.plan['bindings']['source_rom_sha256']
        self.image = Path(os.environ['OOS_SCENE_PREVIEW_CANDIDATE']).read_bytes()

    def test_candidate_reproduces_plan_caches_for_keys_3_and_4(self):
        digest = hashlib.sha256(self.raw).hexdigest()
        entries = {e['key']: e for e in self.plan['entries']}
        for key in (3, 4):
            plan, raw, derived = N.read_scene_plan(self.path, digest, self.source, key, self.image)
            self.assertEqual(raw.hex(), entries[key]['exit_cache_hex'])
            self.assertEqual(derived['cache_sha256'], entries[key]['cache_sha256'])
            self.assertEqual(derived['stable_after_walk'],
                             [derived['world_pixel'][0], derived['world_pixel'][1]+19])
        with self.assertRaisesRegex(RuntimeError, 'Scene source ROM differs'):
            N.read_scene_plan(self.path, digest, hashlib.sha256(b'other').hexdigest(), 3, self.image)

    def test_genuine_plan_with_altered_scene_cache_refuses(self):
        plan = copy.deepcopy(self.plan)
        entry = plan['entries'][2]
        raw = bytearray.fromhex(entry['exit_cache_hex'])
        raw[20] ^= 1
        entry.update(exit_cache_hex=raw.hex(), cache_sha256=hashlib.sha256(raw).hexdigest())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'altered.json'
            path.write_bytes(json.dumps(plan).encode())
            with self.assertRaisesRegex(RuntimeError, 'Scene cache differs from candidate-native derivation'):
                N.read_scene_plan(path, hashlib.sha256(path.read_bytes()).hexdigest(), self.source, 4, self.image)


if __name__ == '__main__':
    unittest.main()
