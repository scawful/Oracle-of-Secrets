#!/usr/bin/env python3
"""Attach-only seeded ferry/Sky checkpoint lifecycle; supervisor owns launch.

This observes a disclosed copied-SRAM entry, not an earned transport route.
Compiled source/grants/admission and post-exit disk/fresh-PID checks belong to
its supervisor. Only inherited Episode.damage's0373/037B writes are permitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from lyra_checkpoint_preview import LyraEpisode
from regional_checkpoint import require, sha

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Scripts/Build'))
import checkpoint_registry as C
import lyra_current_transfer as T
import lyra_project_prepare as Q


def json_object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate scene-plan/artifact key: '+key)
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    require(type(value) is dict, 'Expected a scene-plan/artifact object')
    return value


def read_scene_plan(path, digest, source_digest, key, candidate):
    """Recheck Save/artifact identity and candidate-native cache consistency.

    This is not a replacement for bind_private_preview or compiled readback.
    A0 remains an unexecuted supervisor-qualified record in the same v2 plan.
    """
    require(type(key) is int and key in (3, 4), 'Only native scene keys3/4 are supported')
    for value in (digest, source_digest):
        require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value),
                'Scene plan/source requires an exact SHA256')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == digest, 'Scene checkpoint plan SHA256 changed')
    plan = json_object(raw)
    require(set(plan) == {'kind', 'scope', 'production_admission', 'epoch', 'bindings',
                         'entries', 'memberships'} and plan['kind'] == C.PREVIEW_PLAN_V2
            and plan['scope'] == 'seeded_private_preview'
            and plan['production_admission'] is False
            and type(plan['epoch']) is int and plan['epoch'] == 1,
            'Expected the explicit epoch1 seeded private v2 plan')
    bindings = plan['bindings']
    C._private_binding_v2(bindings)
    require(bindings['source_rom_sha256'] == source_digest, 'Scene source ROM differs')
    receipt = json_object(Q.read_bound(bindings['live']['save_receipt']))
    projects = [r for r in receipt.get('artifacts', []) if r.get('role') == 'project']
    require(len(projects) == 1, 'Native Save must bind exactly one project')
    # Maintained native Save validator rehashes actual saved inputs/producer
    # and checks the live completion receipt; do not trust a plan's gen/op.
    live = T._live(Path(projects[0]['path']))
    require(all(live.get(name) == bindings['live'][name]
                for name in ('generation', 'operation_id', 'save_receipt'))
            and live['inputs']['rom']['sha256'] == source_digest,
            'Scene plan differs from the live native Save/source')
    a0_landing = json_object(Q.read_bound(bindings['cache_source']))
    Q.read_bound(a0_landing['geometry_source'])
    packet = json_object(Q.read_bound(bindings['joint_art']))
    require(packet.get('kind') == 'lyra.joint_art_packet.v1'
            and packet.get('source_rom_sha256') == source_digest
            and type(packet.get('generation')) is int
            and packet['generation'] == live['generation']
            and packet.get('operation_id') == live['operation_id']
            and packet.get('transfer_id') == bindings['transfer_id'],
            'Scene packet Save/transfer binding differs')
    for sheet in packet['sheets']:
        Q.read_bound(sheet['stream'])
    types = Q.read_bound(packet['ferry']['types'])
    graphics = Q.read_bound(packet['ferry']['graphics'])
    require(len(types) == 89 and set(types) <= {0, 2, 8} and len(graphics) == 0xB20,
            'Scene ferry type/graphics payload differs')
    binding = dict(source_rom_sha256=source_digest, transfer_id=bindings['transfer_id'],
        generation=live['generation'], operation_id=live['operation_id'],
        joint_art=bindings['joint_art'], ferry_types=packet['ferry']['types'])
    caches, derived = {}, {}
    for scene_key, pin in zip(C.NATIVE_PREVIEW, bindings['native_landings']):
        landing = json_object(Q.read_bound(pin))
        require(type(landing.get('key')) is int and landing['key'] == scene_key
                and type(landing.get('clear_radius')) is int and landing['clear_radius'] == 1,
                'Scene native landing key/order/radius differs')
        caches[scene_key], derived[scene_key] = C.native_preview_cache(candidate, landing, binding)
    require(type(plan['entries']) is list and len(plan['entries']) == 3,
            'Scene v2 plan must keep exactly keys2/3/4')
    expected_members = []
    for entry_key, entry in zip((2, 3, 4), plan['entries']):
        require(type(entry) is dict and set(entry) == {'key', 'domain', 'map_id', 'parent_map',
            'native_affinity', 'region_key', 'exit_cache_hex', 'cache_sha256'},
            'Malformed scene checkpoint entry')
        spec = C.NATIVE_PREVIEW.get(entry_key)
        domain, parent, maps = ((C.Domain.SPECIAL, 0xA0, (0xA0, 0xA1)) if spec is None
                               else (spec['domain'], spec['parent'], spec['maps']))
        expected = dict(key=entry_key, domain=domain.name, map_id=parent,
                        parent_map=parent, native_affinity=0, region_key=entry_key)
        require(all(type(entry[k]) is type(v) and entry[k] == v for k,v in expected.items()),
                'Scene key/domain/map/parent/region exceeds the approved preview')
        require(type(entry['exit_cache_hex']) is str and
                re.fullmatch('[0-9a-f]{100}', entry['exit_cache_hex']),
                'Scene cache must contain exactly50 bytes')
        cache = bytes.fromhex(entry['exit_cache_hex'])
        require(entry['cache_sha256'] == hashlib.sha256(cache).hexdigest(),
                'Scene cache SHA256 differs')
        C.RegionalCheckpoint(entry_key, domain, parent, entry_key, parent, 0,
                             cache, source_digest).pack(source_digest)
        if spec is not None:
            require(cache == caches[entry_key], 'Scene cache differs from candidate-native derivation')
        expected_members += [dict(map_id=m, domain=domain.name, native_affinity=0,
                                  region_key=entry_key) for m in maps]
    require(plan['memberships'] == expected_members and
            all(type(m[k]) is int for m in plan['memberships']
                for k in ('map_id', 'native_affinity', 'region_key')),
            'Scene membership exceeds the explicit preview')
    return plan, caches[key], derived[key]


def checkpoint_bytes(plan, key):
    return (C.SavedCheckpoint(C.SCHEMA, plan['epoch'], key).encode()
            + bytes([C.ResumeIntent.REGIONAL])).hex()


def validate_saved_sram(raw, checkpoint):
    require(len(raw) == 8192, 'Native SRAM readback incomplete')
    require(raw[:0x500] == raw[0xF00:0x1400], 'Native primary/backup mismatch')
    require(sum(int.from_bytes(raw[i:i+2], 'little') for i in range(0, 0x500, 2))
            & 0xFFFF == 0x5A5A, 'Native saved-file checksum invalid')
    require(raw[0x3B4:0x3B9].hex() == checkpoint, 'Native SRAM lost selected scene checkpoint')


class SceneEpisode(LyraEpisode):
    @property
    def gameplay_module(self):
        return {3: 0x09, 4: 0x0B}[self.key]

    def __init__(self, args, bridge, plan, cache, derived):
        super().__init__(args, bridge, plan, cache)
        self.key, self.scene = args.key, C.NATIVE_PREVIEW[args.key]
        self.derived = derived
        self.checkpoint = checkpoint_bytes(plan, args.key)
        self.result.update(scope=self.scene['scope'], checkpoint_key=self.key,
                           scene_derivation=derived, compiled_verification_by_supervisor=True)
        self.result['provenance']['scene_driver_sha256'] = sha(Path(__file__))
        self.result['provenance']['transfer_source_sha256'] = sha(Path(T.__file__))

    def command(self, name, params=None):
        require(name in ('STATE', 'FRAME', 'INPUT', 'SCREENSHOT', 'BREAKPOINT', 'PAUSE', 'LOADROM'),
                'Command outside scene preview scope')
        if name == 'LOADROM':
            require(self.phase == 'live' and params == {'path': str(self.a.rom)},
                    'Only live same-ROM battery flush is permitted')
        return super().command(name, params)

    def sample(self):
        self.owner()
        return super().sample()

    def damage(self):
        require(self.phase == 'live', 'Reopen phase is read-only')
        self.owner()
        return super().damage()

    def require_regional_destination(self, state):
        self.owner()
        cache = self.b.read_block(0x7EC140, C.CACHE_BYTES)
        parent = self.b.read_block(0x7E040A, 2)
        require(cache == self.cache, 'Scene complete50-byte native cache mismatch')
        require(len(parent) == 2 and int.from_bytes(parent, 'little') == self.scene['parent'],
                'Scene runtime parent mismatch')
        x, y = self.derived['stable_after_walk']
        require((state['module'], state['sub'], state['indoors'], state['map'],
                 state['world'], state['x'], state['y'], state['checkpoint']) ==
                (self.gameplay_module, 0, 0, self.scene['parent'], 0, x, y, self.checkpoint),
                f'Scene native destination/19px walk/checkpoint mismatch: {state}')
        self.result.setdefault('cache_checks', []).append(dict(
            cache_hex=cache.hex(), sha256=hashlib.sha256(cache).hexdigest(), state=state))

    def regional(self):
        self.require_regional_destination(self.sample())
        if self.phase == 'reopen':
            self.screenshot('cold-reopened-scene-checkpoint')
            return
        self.screenshot('seeded-scene-entry')
        before = self.sample()
        self.press('right', 8)
        moved = self.sample()
        require(self.ordinary(moved) and 0 < moved['x']-before['x'] <= 16
                and moved['y'] == before['y'], f'Right8 left the qualified scene floor: {moved}')
        self.press('left', 8)
        returned = self.sample()
        require(self.ordinary(returned) and returned['y'] == before['y']
                and abs(returned['x']-before['x']) < moved['x']-before['x'],
                f'Left8 did not return toward the scene anchor: {returned}')
        self.result['cases'].append(dict(name='controller-right8-left8',
                                        before=before, moved=moved, returned=returned))
        self.damage()
        self.choose_gameover(0)
        state = self.wait(self.ordinary, 'native-death-continue-loaded-scene-checkpoint')
        self.require_regional_destination(state)
        self.screenshot('scene-death-continue')
        self.damage()
        self.choose_gameover(1)
        self.wait(lambda s:s['module'] in (0, 1, 0x14), 'native-save-quit-returned-to-title')
        self.owner()
        raw = self.b.read_block(0, 8192, memtype='SnesSaveRam')
        validate_saved_sram(raw, self.checkpoint)
        saved = self.a.output/'native-saved-sram.srm'
        saved.write_bytes(raw)
        self.result.update(native_saved_sram=str(saved), native_save_sha256=sha(saved))
        self.command('LOADROM', {'path': str(self.a.rom)})
        self.result['battery_flush_requested'] = True

    def ordinary(self, state):
        return (state['module'] == self.gameplay_module and state['sub'] == 0 and state['indoors'] == 0
                and state['map'] == self.scene['parent'] and state['hp'] > 0
                and state['world'] == 0 and state['checkpoint'] == self.checkpoint)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('socket', 'owner', 'token', 'rom-sha1', 'rom-sha256',
                 'source-rom-sha256', 'checkpoint-plan-sha256'):
        p.add_argument('--'+name, required=True)
    for name in ('owner-file', 'status-file', 'rom', 'client-root', 'output', 'checkpoint-plan'):
        p.add_argument('--'+name, required=True, type=Path)
    p.add_argument('--pid', required=True, type=int)
    p.add_argument('--key', required=True, type=int, choices=(3, 4))
    p.add_argument('--phase', required=True, choices=('live', 'reopen'))
    p.add_argument('--battery-file', type=Path, help='Supervisor-owned post-exit disk comparison only')
    p.add_argument('--execute-fixtures', action='store_true')
    a = p.parse_args(argv)
    require(a.execute_fixtures, 'Explicit copied-save fixture admission required')
    require('oos-rc-play' not in a.socket and 'oos-scawful-test' not in a.socket,
            'Protected emulator endpoint')
    image = a.rom.read_bytes()
    require(hashlib.sha256(image).hexdigest() == a.rom_sha256, 'Private ROM SHA256 changed')
    require(hashlib.sha1(image).hexdigest() == a.rom_sha1, 'Private ROM SHA1 changed')
    plan, cache, derived = read_scene_plan(a.checkpoint_plan, a.checkpoint_plan_sha256,
                                         a.source_rom_sha256, a.key, image)
    a.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    e = SceneEpisode(a, MesenBridge(a.socket, auto_reconnect=False, max_retries=0), plan, cache, derived)
    try:
        e.run()
        read_scene_plan(a.checkpoint_plan, a.checkpoint_plan_sha256, a.source_rom_sha256, a.key, image)
        for path, pin in ((Path(__file__), 'scene_driver_sha256'),
                          (Path(__file__).with_name('lyra_checkpoint_preview.py'), 'lyra_driver_sha256'),
                          (Path(__file__).with_name('regional_checkpoint.py'), 'regional_driver_sha256'),
                          (Path(C.__file__), 'registry_source_sha256'), (Path(T.__file__), 'transfer_source_sha256')):
            require(sha(path) == e.result['provenance'][pin], 'Native source changed: '+str(path))
        require(len(e.result['writes']) == (4 if a.phase == 'live' else 0)
                and all(r['address'] in ('7E0373', '7E037B') for r in e.result['writes']),
                'Unexpected scene fixture writes')
    except BaseException as error:
        e.result.update(passed=False, error=repr(error))
        try:
            e.owner()
            e.command('PAUSE')
            e.result['failure_state'] = e.sample()
            e.result['failure_cpu'] = e.b.get_cpu_state()
            e.screenshot('failure')
        except BaseException as capture:
            e.result['capture_error'] = repr(capture)
    finally:
        for name in ('INPUT', 'PAUSE'):
            try:
                e.owner()
                reply = e.b.send_command(name, {'buttons': '', 'frames': '0', 'player': '0'}
                                         if name == 'INPUT' else {}, timeout=2)
                require(reply.get('success'), f'Cleanup {name} refused')
            except BaseException as error:
                e.result['cleanup_errors'].append(repr(error))
        try:
            require(sha(a.rom) == a.rom_sha256, 'Private ROM changed')
        except BaseException as error:
            e.result['cleanup_errors'].append(repr(error))
        e.result['counts'] = dict(controller_presses=len(e.result['inputs']),
            frame_requests=len(e.result['frame_advances']),
            requested_frames=sum(r['requested'] for r in e.result['frame_advances']),
            fixture_writes=len(e.result['writes']), complete_cache_checks=len(e.result.get('cache_checks', [])))
        e.result['passed'] &= not e.result['cleanup_errors']
        e.result['source_sha256'] = sha(Path(__file__))
        (a.output/'RESULT.json').write_text(json.dumps(e.result, indent=2)+'\n')
    print(json.dumps(dict(passed=e.result['passed'], output=str(a.output/'RESULT.json'))))
    return 0 if e.result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
