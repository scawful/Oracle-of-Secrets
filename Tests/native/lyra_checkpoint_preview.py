#!/usr/bin/env python3
"""Attach-only seeded A0 checkpoint death/SaveQuit/cold-reopen proof.

The supervisor owns launch, lease, copied battery, shutdown and disk readback.
Controller boot proves seeded entry only; it does not prove an earned Lyra route.
Only Episode.damage's existing0373/037B fixture writes are used.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

from regional_checkpoint import Episode, require, sha

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Scripts/Build'))
import checkpoint_registry as C
import lyra_project_prepare as Q

CHECKPOINT = '0101020001'


def read_checkpoint_plan(path, digest, source_digest):
    require(re.fullmatch('[0-9a-f]{64}', digest) is not None,
            'Checkpoint plan requires an exact SHA256')
    require(re.fullmatch('[0-9a-f]{64}', source_digest) is not None,
            'Source ROM requires an exact SHA256')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == digest, 'Checkpoint plan SHA256 changed')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate checkpoint-plan key: '+key)
            result[key] = value
        return result
    plan = json.loads(raw, object_pairs_hook=unique)
    require(type(plan) is dict and set(plan) == {
        'kind', 'scope', 'production_admission', 'epoch', 'bindings', 'entry', 'memberships'}
        and plan['kind'] == 'checkpoint.private_preview_plan.v1'
        and plan['scope'] == 'seeded_private_preview'
        and plan['production_admission'] is False
        and type(plan['epoch']) is int and plan['epoch'] == 1,
        'Expected the explicit epoch1 seeded private checkpoint plan')
    C._private_binding(plan['bindings'])
    require(plan['bindings']['source_rom_sha256'] == source_digest,
            'Checkpoint plan source ROM differs')
    for binding in (plan['bindings']['cache_source'], plan['bindings']['live']['save_receipt']):
        Q.read_bound(binding)
    entry = plan['entry']
    require(type(entry) is dict and set(entry) == {
        'key', 'domain', 'map_id', 'parent_map', 'native_affinity', 'region_key',
        'exit_cache_hex', 'cache_sha256'}, 'Malformed checkpoint destination')
    expected = dict(key=2, domain='SPECIAL', map_id=0xA0, parent_map=0xA0,
                    native_affinity=0, region_key=2)
    require(all(type(entry[k]) is type(v) and entry[k] == v for k,v in expected.items()),
            'This episode supports only the bound key2/SPECIAL/A0 region2 pilot')
    require(type(entry['exit_cache_hex']) is str and
            re.fullmatch('[0-9a-f]{100}', entry['exit_cache_hex']) is not None,
            'Checkpoint requires the complete50-byte cache')
    cache = bytes.fromhex(entry['exit_cache_hex'])
    require(hashlib.sha256(cache).hexdigest() == entry['cache_sha256'],
            'Checkpoint cache digest differs')
    # Reuse the maintained record ABI validator. This is structural validation,
    # not replacement for the supervisor's source/build/grant qualification.
    C.RegionalCheckpoint(2, C.Domain.SPECIAL, 0xA0, 2, 0xA0, 0, cache,
                         source_digest).pack(source_digest)
    require(plan['memberships'] == [dict(map_id=m, domain='SPECIAL', native_affinity=0,
                                       region_key=2) for m in (0xA0, 0xA1)],
            'Checkpoint membership differs from the explicit two-map pilot')
    require((int.from_bytes(cache[10:12], 'little'), int.from_bytes(cache[8:10], 'little'))
            == (256, 2336), 'This episode requires the reviewed A0 landing coordinates')
    return plan, cache


def validate_saved_sram(raw):
    require(len(raw) == 8192, 'Native SRAM readback incomplete')
    require(raw[:0x500] == raw[0xF00:0x1400], 'Native primary/backup mismatch')
    require(sum(int.from_bytes(raw[i:i+2], 'little') for i in range(0, 0x500, 2))
            & 0xFFFF == 0x5A5A, 'Native saved-file checksum invalid')
    require(raw[0x3B4:0x3B9].hex() == CHECKPOINT, 'Native SRAM lost Lyra checkpoint')


class LyraEpisode(Episode):
    @property
    def gameplay_module(self):
        # Native Module0B_OverworldSpecial shares Module09's dispatcher.
        return 0x0B

    def __init__(self, args, bridge, plan, cache):
        self.phase, self.plan, self.cache = args.phase, plan, cache
        # Reuse Episode.run's complete ownership/pause/boot path through its
        # regional extension point; preserve the actual CLI phase in evidence.
        route = copy.copy(args)
        route.phase = 'regional'
        super().__init__(route, bridge)
        self.result.update(phase=args.phase, scope='seeded_A0_A1_checkpoint_preview',
            seeded_entry_only=True, earned_ingress_verified=False,
            fresh_process_verified=False, disk_battery_verified=False)
        self.result['provenance'].update(checkpoint_plan=str(args.checkpoint_plan),
            checkpoint_plan_sha256=args.checkpoint_plan_sha256,
            source_rom_sha256=args.source_rom_sha256,
            checkpoint_bindings=plan['bindings'],
            lyra_driver_sha256=sha(Path(__file__)),
            regional_driver_sha256=sha(Path(__file__).with_name('regional_checkpoint.py')),
            registry_source_sha256=sha(Path(C.__file__)),
            battery_file=None if args.battery_file is None else str(args.battery_file))
        self.result['supervisor_checks_required'] = [
            'disk battery after confirmed process exit equals native-saved-sram.srm',
            'reopen uses a fresh process and the same native-saved battery']

    def command(self, name, params=None):
        # Inherited press issues INPUT before its frames ownership check.
        # Validate ownership before every command in this new episode as well.
        self.owner()
        return super().command(name, params)

    def boot(self):
        # Frame2 may still be in the native SPC handshake with random WRAM.
        # Advance normally to initialized title state before controller input.
        self.wait(lambda s: s['module'] in (0, 1, 0x14) and s['indoors'] == 0,
                  'cold-title-or-file-select-ready', max_frames=1200)
        return super().boot()

    def require_regional_destination(self, state):
        actual = self.b.read_block(0x7EC140, C.CACHE_BYTES)
        require(actual == self.cache, 'Lyra complete50-byte native cache mismatch')
        require((state['module'], state['sub'], state['indoors'], state['map'],
                 state['x'], state['y']) == (self.gameplay_module, 0, 0, 0xA0, 256, 2355),
                f'Lyra stable destination/native19px exit walk mismatch: {state}')
        require(state['checkpoint'] == CHECKPOINT, 'Lyra checkpoint state differs')
        self.result.setdefault('cache_checks', []).append(dict(
            cache_hex=actual.hex(), sha256=hashlib.sha256(actual).hexdigest(), state=state))

    def regional(self):
        self.require_regional_destination(self.sample())
        if self.phase == 'reopen':
            self.screenshot('cold-reopened-lyra-checkpoint')
            return
        self.screenshot('seeded-lyra-entry')
        before = self.sample()
        self.press('right', 16)
        moved = self.sample()
        require(moved['module'] == self.gameplay_module and moved['sub'] == 0 and moved['indoors'] == 0
                and moved['map'] == 0xA0 and moved['hp'] > 0
                and moved['x'] > before['x'] and moved['y'] == before['y'],
                f'Right16 movement did not stay on the admitted A0 floor: {moved}')
        self.press('left', 16)
        returned = self.sample()
        require(returned['module'] == self.gameplay_module and returned['sub'] == 0
                and returned['indoors'] == 0 and returned['map'] == 0xA0
                and returned['hp'] > 0 and returned['y'] == before['y']
                and abs(returned['x']-before['x']) < abs(moved['x']-before['x']),
                f'Left16 movement did not return toward the A0 landing: {returned}')
        self.result['cases'].append(dict(name='controller-right16-left16',
                                        before=before, moved=moved, returned=returned))
        self.damage()
        self.choose_gameover(0)
        state = self.wait(lambda s:s['module'] == self.gameplay_module and s['sub'] == 0,
                          'native-death-continue-loaded-lyra-checkpoint')
        self.require_regional_destination(state)
        self.screenshot('lyra-death-continue')
        self.damage()
        self.choose_gameover(1)
        self.wait(lambda s:s['module'] in (0, 1, 0x14),
                  'native-save-quit-returned-to-title')
        raw = self.b.read_block(0, 8192, memtype='SnesSaveRam')
        validate_saved_sram(raw)
        saved = self.a.output/'native-saved-sram.srm'
        saved.write_bytes(raw)
        self.result['native_save_sha256'] = sha(saved)
        self.result['native_saved_sram'] = str(saved)
        # Existing native control uses same-ROM LOADROM to flush its battery.
        # Actual disk comparison waits for the supervisor's confirmed shutdown.
        self.command('LOADROM', {'path': str(self.a.rom)})
        self.result['battery_flush_requested'] = True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('socket', 'owner', 'token', 'rom-sha1', 'rom-sha256',
                  'source-rom-sha256', 'checkpoint-plan-sha256'):
        p.add_argument('--'+field, required=True)
    for field in ('owner-file', 'status-file', 'rom', 'client-root', 'output', 'checkpoint-plan'):
        p.add_argument('--'+field, required=True, type=Path)
    p.add_argument('--battery-file', type=Path,
                   help='Record for supervisor post-exit comparison; attach test never reads/writes it')
    p.add_argument('--pid', required=True, type=int)
    p.add_argument('--phase', required=True, choices=('lyra', 'reopen'))
    p.add_argument('--execute-fixtures', action='store_true')
    a = p.parse_args(argv)
    require(a.execute_fixtures, 'Explicit copied-save fixture admission required')
    require('oos-rc-play' not in a.socket and 'oos-scawful-test' not in a.socket,
            'Protected emulator endpoint')
    require(sha(a.rom) == a.rom_sha256, 'Private ROM SHA256 changed')
    require(hashlib.sha1(a.rom.read_bytes()).hexdigest() == a.rom_sha1, 'ROM SHA1 mismatch')
    plan, cache = read_checkpoint_plan(a.checkpoint_plan, a.checkpoint_plan_sha256,
                                       a.source_rom_sha256)
    a.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    e = LyraEpisode(a, MesenBridge(a.socket, auto_reconnect=False, max_retries=0), plan, cache)
    try:
        e.run()
        # Recheck bound plan/source provenance after the native observation.
        read_checkpoint_plan(a.checkpoint_plan, a.checkpoint_plan_sha256, a.source_rom_sha256)
        for path, key in ((Path(__file__), 'lyra_driver_sha256'),
                          (Path(__file__).with_name('regional_checkpoint.py'), 'regional_driver_sha256'),
                          (Path(C.__file__), 'registry_source_sha256')):
            require(sha(path) == e.result['provenance'][key], 'Native test source changed: '+str(path))
        require(len(e.result['writes']) == (4 if a.phase == 'lyra' else 0)
                and all(row['address'] in ('7E0373', '7E037B') for row in e.result['writes']),
                'Unexpected fixture write count/address')
    except BaseException as error:
        e.result['passed'] = False
        e.result['error'] = repr(error)
        try:
            e.owner()  # Do not pause/capture a session whose ownership changed.
            e.b.pause()
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
            requested_frames=sum(row['requested'] for row in e.result['frame_advances']),
            fixture_writes=len(e.result['writes']),
            complete_cache_checks=len(e.result.get('cache_checks', [])))
        e.result['passed'] &= not e.result['cleanup_errors']
        e.result['source_sha256'] = sha(Path(__file__))
        (a.output/'RESULT.json').write_text(json.dumps(e.result, indent=2)+'\n')
    print(json.dumps(dict(passed=e.result['passed'], output=str(a.output/'RESULT.json'))))
    return 0 if e.result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
