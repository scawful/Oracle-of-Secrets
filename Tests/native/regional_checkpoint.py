#!/usr/bin/env python3
"""Attach-only native checkpoint lifecycle on an explicitly owned copied save.

The supervisor owns launch, heavy admission, isolated SRAM and shutdown. This
test uses controller input and one disclosed damage fixture; it never sets PC,
Link position, map, progression, checkpoint bytes or the native save selector.
The source-bound Goron destination is a runtime control, not Lyra route proof.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Episode:
    @property
    def gameplay_module(self):
        return 0x09

    def __init__(self, args, bridge):
        self.a, self.b = args, bridge
        self.deadline = time.monotonic() + 240
        self.result = dict(passed=False, phase=args.phase, cases=[], writes=[],
                           inputs=[], frame_advances=[], cleanup_errors=[])
        self.result['provenance'] = dict(rom=str(args.rom), rom_sha1=args.rom_sha1,
            rom_sha256=args.rom_sha256, socket=args.socket, pid=args.pid,
            owner=args.owner, owner_file=str(args.owner_file),
            status_file=str(args.status_file))

    def command(self, name, params=None):
        require(time.monotonic() < self.deadline, '240-second attach-test deadline')
        reply = self.b.send_command(name, params or {})
        require(reply.get('success'), f'{name} refused: {reply}')
        data = reply.get('data', {})
        return json.loads(data) if isinstance(data, str) and data.startswith('{') else data

    def owner(self):
        owner = json.loads(self.a.owner_file.read_text())
        require(owner['owner'] == self.a.owner and owner['token'] == self.a.token,
                'Native heavy lease changed')
        status = json.loads(self.a.status_file.read_text())
        require(int(status['pid']) == self.a.pid and status['socketPath'] == self.a.socket,
                'Owned status PID/socket changed')
        os.kill(self.a.pid, 0)
        info = self.b.get_rom_info()
        require(str(info.get('sha1', '')).lower() == self.a.rom_sha1,
                'Owned emulator ROM identity changed')

    def frames(self, count):
        self.owner()
        before = self.command('STATE')
        require(before['paused'], 'Frame stepping requires owned paused emulator')
        self.command('FRAME', {'count': str(count)})
        limit = time.monotonic() + 8
        while time.monotonic() < limit:
            after = self.command('STATE')
            if after['paused'] and after['frame'] >= before['frame'] + count:
                self.result['frame_advances'].append(dict(before=before['frame'],
                    after=after['frame'], requested=count))
                return
            time.sleep(.01)
        raise RuntimeError(f'Native frames did not complete: {before} -> {after}')

    def press(self, buttons, count=3):
        self.result['inputs'].append(dict(buttons=buttons, frames=count))
        self.command('INPUT', dict(buttons=buttons, frames='0', player='0'))
        self.frames(count)
        self.command('INPUT', dict(buttons='', frames='0', player='0'))
        self.frames(2)

    def sample(self):
        low = self.b.read_block(0x7E0000, 0x200)
        body = self.b.read_block(0x7E0400, 0xD0)
        saved = self.b.read_block(0x7EF300, 0xD0)
        require(len(low) == 0x200 and len(body) == 0xD0 and len(saved) == 0xD0,
                'Short native memory snapshot')
        word = lambda b, i: int.from_bytes(b[i:i+2], 'little')
        return dict(module=low[0x10], sub=low[0x11], indoors=low[0x1B],
                    map=low[0x8A], room=word(low, 0xA0),
                    x=word(low, 0x22), y=word(low, 0x20),
                    continue_marker=low[0x10A], entry=word(low, 0x10E),
                    dungeon=body[0xC], native_continue_hp=body[0xAA],
                    entrance_animation=body[0xC6], dungeon_tag_suppression=body[0xC7],
                    hp=saved[0x6D], checkpoint=saved[0xB4:0xB9].hex(),
                    spawn=saved[0xC8], world=saved[0xCA], progression=saved[0xC5],
                    menu_choice=low[0xB0])

    def wait(self, predicate, label, max_frames=1200):
        for _ in range(max_frames // 10 + 1):
            state = self.sample()
            if predicate(state):
                self.result['cases'].append(dict(name=label, state=state))
                return state
            self.frames(10)
        raise RuntimeError(f'{label}: exceeded {max_frames} frames; last={state}')

    def boot(self):
        for _ in range(90):
            state = self.sample()
            if state['module'] in (7, 9, 11):
                return self.wait(lambda s: s['module'] in (7, 9, 11) and s['sub'] == 0,
                                 'normal-native-file-load-completed')
            if state['module'] in (0, 1, 0x14):
                self.press('start')
            self.frames(10)
        raise RuntimeError('Cold boot did not reach gameplay through file-select input')

    def screenshot(self, name):
        data = self.command('SCREENSHOT')
        require(isinstance(data, str), 'Screenshot response is not encoded PNG data')
        png = base64.b64decode(data.strip('"'), validate=True)
        require(png.startswith(b'\x89PNG\r\n\x1a\n'), 'Screenshot response is not a PNG')
        path = self.a.output / (name + '.png')
        path.write_bytes(png)
        self.result.setdefault('screenshots', []).append(dict(path=str(path), sha256=sha(path)))

    def require_regional_destination(self, state):
        cache = self.b.read_block(0x7EC140, 0x32)
        require(len(cache) == 0x32 and cache[:2] == bytes.fromhex('3600') and
                cache[8:12] == bytes.fromhex('280e200d'), 'Regional source cache mismatch')
        # Native02AC8F walks down16 pixels, then adds3 at02ACAB before
        # returning to ordinary control. Cache Y is the pre-walk coordinate.
        require((state['module'], state['map'], state['x'], state['y']) ==
                (9, 0x36, 0xD20, 0xE28 + 0x13),
                f'Regional stable destination mismatch: {state}')

    def walk_to_anchor(self):
        for _ in range(96):
            state = self.sample()
            if state['checkpoint'] == '0101010001':
                self.result['cases'].append(dict(name='controller-walk-activated-anchor', state=state))
                return
            require(state['module'] == 9 and state['sub'] == 0 and
                    state['map'] == 0x36 and state['hp'] > 0,
                    f'Controller walk left admitted live area: {state}')
            dx, dy = 0xD20 - state['x'], 0xE28 - state['y']
            button = ('right' if dx > 0 else 'left') if dx else ('down' if dy > 0 else 'up') if dy else ''
            self.press(button, 1)
        raise RuntimeError(f'Controller walk did not activate anchor within96 steps: {self.sample()}')

    def damage(self):
        s = self.sample()
        require(s['module'] == self.gameplay_module and s['sub'] == 0 and s['hp'] > 0,
                'Damage fixture requires ordinary live outdoor gameplay')
        require(self.b.read_memory(0x7E0055) == 0, 'Cape active; refuse damage fixture')
        require(self.command('STATE')['paused'], 'Damage fixture requires paused CPU')
        # Queue ordinary Link_ControlHandler damage, which enters GameOver.
        # No PC/module/position/checkpoint manipulation is used.
        for address, value, reason in ((0x7E037B, 0, 'clear temporary invulnerability'),
                                       (0x7E0373, s['hp'], 'explicit lethal damage amount')):
            row = dict(address=f'{address:06X}', before=self.b.read_memory(address),
                       value=value, reason=reason)
            require(self.b.write_memory(address, value), 'Fixture write refused')
            require(self.b.read_memory(address) == value, 'Fixture write readback mismatch')
            self.result['writes'].append(row)
        return self.wait(lambda v: v['module'] == 0x12 and v['sub'] == 9,
                         'ordinary-damage-reached-native-gameover-choice')

    def choose_gameover(self, target):
        for _ in range(4):
            s = self.sample()
            require(s['module'] == 0x12 and s['sub'] == 9, 'GameOver choice is not active')
            if s['menu_choice'] == target:
                self.press('a')
                return
            self.press('select')
            self.frames(12)
        raise RuntimeError('Could not select native GameOver option')

    def regional(self):
        self.require_regional_destination(self.sample())
        self.walk_to_anchor()
        self.screenshot('activated-goron-control')
        self.press('left', 8)
        moved = self.sample()
        require((moved['x'], moved['y']) != (0xD20, 0xE28), 'Movement control did not leave anchor')
        self.damage()
        self.choose_gameover(0)
        s = self.wait(lambda v: v['module'] == 9 and v['sub'] == 0,
                      'native-death-continue-loaded-regional-checkpoint')
        self.require_regional_destination(s)
        require(s['checkpoint'] == '0101010001', 'Death lost activated checkpoint')
        self.screenshot('regional-continue')
        self.damage()
        self.choose_gameover(1)
        self.wait(lambda v: v['module'] in (0, 1, 0x14), 'native-save-quit-returned-to-title')
        ram = self.b.read_block(0, 8192, memtype='SnesSaveRam')
        require(len(ram) == 8192, 'Native SRAM readback incomplete')
        require(ram[:0x500] == ram[0xF00:0x1400], 'Native primary/backup mismatch')
        require(sum(int.from_bytes(ram[i:i+2], 'little') for i in range(0, 0x500, 2)) &
                0xFFFF == 0x5A5A, 'Native saved-file checksum invalid')
        require(ram[0x3B4:0x3B9].hex() == '0101010001', 'Native SRAM lost checkpoint')
        (self.a.output / 'native-saved-sram.srm').write_bytes(ram)
        # Same-ROM LOADROM flushes the emulator battery manager to its owned
        # save folder. Supervisor then verifies disk bytes and starts a NEW process.
        self.command('LOADROM', {'path': str(self.a.rom)})
        self.result['native_save_sha256'] = hashlib.sha256(ram).hexdigest()

    def run(self):
        self.owner()
        # The first debugger read can clear an earlier non-debugger pause.
        # PAUSE with a debugger is asynchronous, so confirm its completion.
        breakpoints = self.command('BREAKPOINT', {'action': 'list'})
        require(isinstance(breakpoints, dict) and
                isinstance(breakpoints.get('breakpoints'), list),
                'Breakpoint list response is not verified')
        require(not breakpoints['breakpoints'], 'Existing breakpoints: not an isolated session')
        self.command('PAUSE')
        pause_limit = time.monotonic() + 3
        while not self.command('STATE')['paused']:
            require(time.monotonic() < pause_limit, 'Owned CPU did not pause within 3 seconds')
            time.sleep(.01)
        s = self.boot()
        if self.a.phase == 'home':
            require(s['module'] == 7 and s['room'] == 0x104,
                    f'Old save without checkpoint did not reach real Home: {s}')
            require(s['checkpoint'] == '0101000000', 'Old-save checkpoint migration mismatch')
            self.screenshot('old-save-home')
        elif self.a.phase == 'regional':
            self.regional()
        else:
            self.require_regional_destination(s)
            require(s['checkpoint'] == '0101010001', 'Cold reopen lost native checkpoint bytes')
            self.screenshot('cold-reopened-regional')
        self.result['passed'] = True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('socket', 'owner', 'token', 'rom-sha1', 'rom-sha256'):
        p.add_argument('--' + field, required=True)
    for field in ('owner-file', 'status-file', 'rom', 'client-root', 'output'):
        p.add_argument('--' + field, required=True, type=Path)
    p.add_argument('--pid', required=True, type=int)
    p.add_argument('--phase', required=True, choices=('home', 'regional', 'reopen'))
    p.add_argument('--execute-fixtures', action='store_true')
    a = p.parse_args()
    require(a.execute_fixtures, 'Explicit copied-save fixture admission required')
    require('oos-rc-play' not in a.socket and 'oos-scawful-test' not in a.socket,
            'Protected emulator endpoint')
    require(sha(a.rom) == a.rom_sha256, 'Private ROM SHA256 changed')
    require(hashlib.sha1(a.rom.read_bytes()).hexdigest() == a.rom_sha1, 'ROM SHA1 mismatch')
    a.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    e = Episode(a, MesenBridge(a.socket, auto_reconnect=False, max_retries=0))
    try:
        e.run()
    except BaseException as error:
        e.result['passed'] = False
        e.result['error'] = repr(error)
        try:
            e.b.pause()
            e.result['failure_state'] = e.sample()
            e.result['failure_cpu'] = e.b.get_cpu_state()
            e.screenshot('failure')
        except BaseException as capture:
            e.result['capture_error'] = repr(capture)
    finally:
        for command in ('INPUT', 'PAUSE'):
            try:
                # Cleanup remains available after the test deadline; the
                # supervisor retains the lease until its process has exited.
                reply = e.b.send_command(command,
                    {'buttons': '', 'frames': '0'} if command == 'INPUT' else {}, timeout=2)
                require(reply.get('success'), f'Cleanup {command} refused')
            except BaseException as error:
                e.result['cleanup_errors'].append(repr(error))
        if sha(a.rom) != a.rom_sha256:
            e.result['cleanup_errors'].append('Private ROM changed')
        e.result['passed'] &= not e.result['cleanup_errors']
        e.result['source_sha256'] = sha(Path(__file__))
        (a.output / 'RESULT.json').write_text(json.dumps(e.result, indent=2) + '\n')
    print(json.dumps(dict(passed=e.result['passed'], output=str(a.output / 'RESULT.json'))))
    return 0 if e.result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
