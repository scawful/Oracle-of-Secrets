#!/usr/bin/env python3
"""Headless Mesen2 checks for the 2026-10-08 Discord quick fixes.

Boots a copy of the ROM with a copied test SRAM, loads file 2 with controller
input, then exercises each fix with real button presses. Item equips, magic,
song selection and a few positions are written to RAM as declared fixtures
(listed in result.json). Run once with the candidate ROM and once with the
unpatched control ROM: each check records the observation and whether it
matches the expectation for that variant.

  python3 Scripts/Validate/scenarios/discord_quick_fixes.py \
      --variant candidate --rom Roms/oos168x.sfc --srm <test.srm> --app <Mesen2 OOS.app> --out <dir>

Rules this follows (agent_board.md): headless only, own isolated profile and
socket, stop only the owned PID with SIGTERM, ROM copy named without "test"
or "oos<digits>".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'Scripts' / 'Mesen2'))
from mesen2_client_lib.bridge import MesenBridge  # noqa: E402
from mesen2_client_lib.oracle_cheats import OracleCheats  # noqa: E402

LAUNCHER = REPO / 'Scripts' / 'Mesen2' / 'mesen2_launch_instance.sh'

MODULE, SUBMODULE, AREA = 0x7E0010, 0x7E0011, 0x7E008A
LINK_Y, LINK_X, FACING = 0x7E0020, 0x7E0022, 0x7E002F
SONG_FLAG, TIME_SPEED, STORM = 0x7E00FE, 0x7EE002, 0x7EE00E
Y_SLOT, Y_ITEM, CUR_SONG, SAVED_SONG, SONGS = 0x7E0202, 0x7E0303, 0x7E030F, 0x7EF3AB, 0x7EF34C
BEAN, MAGIC, BOW, ARROWS, PORTAL_OWNED = 0x7EF39B, 0x7EF36E, 0x7EF340, 0x7EF377, 0x7EF3A6

SPR_STATE, SPR_ID, SPR_SUB = 0x7E0DD0, 0x7E0E20, 0x7E0E30
SPR_XL, SPR_XH, SPR_YL, SPR_YH = 0x7E0D10, 0x7E0D30, 0x7E0D00, 0x7E0D20
ANC_TYPE, ANC_XL, ANC_XH, ANC_YL, ANC_YH = 0x7E0C4A, 0x7E0C04, 0x7E0C18, 0x7E0BFA, 0x7E0C0E

BEAN_VENDOR, PORTAL, DEFLECTED_ARROW = 0x07, 0x03, 0x1B


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(pid: int) -> str:
    out = subprocess.run(['ps', '-o', 'lstart=,command=', '-p', str(pid)], text=True,
                         capture_output=True, check=False).stdout.strip()
    return out


class Run:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        stamp = time.strftime('%Y%m%d-%H%M%S')
        self.out = Path(args.out) / f'{args.variant}-{stamp}-{uuid.uuid4().hex[:6]}'
        self.out.mkdir(parents=True)
        self.name = f'dqf-{args.variant}-{uuid.uuid4().hex[:6]}'
        self.sock = Path(f'/tmp/mesen2-{self.name}.sock')
        self.pid = None
        self.pid_identity = None
        self.b = None
        self.result = {'variant': args.variant, 'out': str(self.out), 'fixtures': [], 'checks': [],
                       'events': [], 'state': 'running'}

    # -- bookkeeping -------------------------------------------------------
    def persist(self):
        (self.out / 'result.json').write_text(json.dumps(self.result, indent=1) + '\n')

    def event(self, name, **extra):
        self.result['events'].append({'t': round(time.time(), 2), 'name': name, **extra})
        self.persist()

    def fixture(self, text):
        self.result['fixtures'].append(text)
        self.persist()

    def check(self, name, observed, expected_by_variant):
        expected = expected_by_variant[self.args.variant]
        ok = expected == 'record-only' or observed == expected
        self.result['checks'].append({'name': name, 'observed': observed, 'expected': expected,
                                      'matches_variant_expectation': ok})
        self.persist()
        print(('PASS ' if ok else 'FAIL ') + name, observed, flush=True)
        return ok

    def shot(self, label):
        png = self.b.screenshot()
        if png:
            path = self.out / f'{len(self.result["events"]):03d}_{label}.png'
            path.write_bytes(png)
            self.event('screenshot', label=label, path=str(path))

    # -- memory / input ----------------------------------------------------
    def r(self, addr):
        return self.b.read_memory(addr) & 0xFF

    def r16(self, addr):
        return self.r(addr) | self.r(addr + 1) << 8

    def w(self, addr, value, why=None):
        if not self.b.write_memory(addr, value & 0xFF):
            raise RuntimeError(f'write failed ${addr:06X}')
        if why:
            self.fixture(f'${addr:06X}={value:02X} ({why})')

    def w16(self, addr, value, why=None):
        self.w(addr, value & 0xFF)
        self.w(addr + 1, value >> 8)
        if why:
            self.fixture(f'${addr:06X}={value:04X} ({why})')

    def press(self, button, frames=4):
        if not self.b.press_button(button, frames=frames):
            raise RuntimeError(f'press failed: {button}')
        time.sleep((frames + 6) / 60)

    def wait_play(self, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                time.sleep(0.3)
                if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                    return True
            time.sleep(0.1)
        return False

    def sprites(self):
        out = []
        for i in range(16):
            if self.r(SPR_STATE + i) < 9:
                continue
            out.append({'slot': i, 'id': self.r(SPR_ID + i), 'sub': self.r(SPR_SUB + i),
                        'x': self.r(SPR_XL + i) | self.r(SPR_XH + i) << 8,
                        'y': self.r(SPR_YL + i) | self.r(SPR_YH + i) << 8})
        return out

    def ancillae(self):
        return [{'slot': i, 'type': self.r(ANC_TYPE + i),
                 'x': self.r(ANC_XL + i) | self.r(ANC_XH + i) << 8,
                 'y': self.r(ANC_YL + i) | self.r(ANC_YH + i) << 8}
                for i in range(10) if self.r(ANC_TYPE + i)]

    def equip(self, slot, item, label):
        self.w(Y_SLOT, slot)
        self.w(Y_ITEM, item)
        self.fixture(f'equip {label}: $0202={slot:02X} $0303={item:02X}')

    def select_song(self, song):
        self.w(CUR_SONG, song)
        self.w(SAVED_SONG, song)
        self.fixture(f'song {song} selected ($030F/$7EF3AB)')

    # -- lifecycle ---------------------------------------------------------
    def preflight(self):
        a = self.args
        self.rom = self.out / f'dqf-{a.variant}.sfc'
        shutil.copy2(a.rom, self.rom)
        self.home = self.out / 'profile'
        (self.home / 'Saves').mkdir(parents=True)
        shutil.copy2(a.srm, self.home / 'Saves' / f'dqf-{a.variant}.srm')
        self.result['rom'] = {'source': str(a.rom), 'sha256': sha(self.rom)}
        self.result['srm'] = {'source': str(a.srm), 'sha256': sha(Path(a.srm))}
        self.result['app'] = str(a.app)
        self.fixture(f'test SRAM {Path(a.srm).name}, file 2')
        self.persist()

    def launch(self):
        cmd = ['taskpolicy', '-b', 'nice', '-n', '10', 'bash', str(LAUNCHER), '--headless',
               '--no-copy-settings', '--no-save-settings', '--no-seed-project-states', '--no-state-set',
               '--no-register', '--instance', self.name, '--home', str(self.home), '--socket', str(self.sock),
               '--rom', str(self.rom), '--app', str(self.args.app)]
        with (self.out / 'launch.log').open('w') as log:
            subprocess.run(cmd, cwd=REPO, stdout=log, stderr=log, check=True, timeout=40)
        for _ in range(80):
            if self.sock.exists():
                break
            time.sleep(0.25)
        if not self.sock.exists():
            raise RuntimeError('socket did not appear')
        pids = subprocess.run(['lsof', '-t', str(self.sock)], text=True, capture_output=True).stdout.split()
        owned = [int(p) for p in pids if p.isdigit() and str(self.rom) in identity(int(p))]
        if len(owned) != 1:
            raise RuntimeError(f'cannot identify the owned emulator: {pids}')
        self.pid = owned[0]
        self.pid_identity = identity(self.pid)
        self.b = MesenBridge(str(self.sock))
        info = self.b.get_rom_info()
        self.result['emulator'] = {'pid': self.pid, 'socket': str(self.sock), 'rom_info': info}
        self.persist()

    def close(self):
        if self.pid and identity(self.pid) == self.pid_identity:
            os.kill(self.pid, signal.SIGTERM)
            for _ in range(50):
                if identity(self.pid) != self.pid_identity:
                    self.result['emulator']['exited'] = True
                    break
                time.sleep(0.1)
        self.persist()

    def boot_file2(self):
        time.sleep(5)
        for _ in range(20):
            if self.r(MODULE) == 1:
                break
            self.press('start', 6)
            time.sleep(0.7)
        for _ in range(4):
            if self.r(0x7E00C8) == 1:
                break
            self.press('down', 4)
            time.sleep(0.4)
        for _ in range(30):
            if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                break
            self.press('start', 8)
            time.sleep(0.6)
        if not self.wait_play():
            raise RuntimeError('file 2 did not reach play')
        self.event('file 2 loaded', module=self.r(MODULE), room=self.r16(0x7E00A0), songs=self.r(SONGS))

    def warp(self, area):
        res = OracleCheats(self.b).warp_area(area)
        self.fixture(f'warp_area 0x{area:02X}')
        self.event('warp', area=f'{area:02X}', response=res)
        if not res.get('ok') or not self.wait_play():
            raise RuntimeError(f'warp to 0x{area:02X} failed: {res}')
        time.sleep(0.5)

    # -- checks ------------------------------------------------------------
    def check_time_speed(self):
        """Fix 1: time speed recovers when SongFlag is cleared during the Song of Time."""
        self.w(SONGS, 5, 'all four songs learned')
        self.equip(13, 0x08, 'Ocarina')
        self.select_song(4)
        time.sleep(0.2)
        self.press('y', 4)
        time.sleep(0.6)
        self.event('song of time played', song_flag=self.r(SONG_FLAG), speed=self.r(TIME_SPEED))
        self.check('song of time sets SongFlag 2 and speed 0 (real Y press)',
                   [self.r(SONG_FLAG), self.r(TIME_SPEED)], {'candidate': [2, 0], 'control': [2, 0], 'previous': [2, 0]})
        # A listener (Zora Princess before the fix) or Save & Quit clears the flag early.
        self.w(SONG_FLAG, 0, 'SongFlag cleared mid-song, as a song listener does')
        time.sleep(0.5)
        self.check('time speed after SongFlag cleared early', self.r(TIME_SPEED),
                   {'candidate': 0x3F, 'control': 0x00, 'previous': 0x3F})
        self.w(TIME_SPEED, 0x3F)
        self.w(SONG_FLAG, 0)

    def check_storms_area00(self):
        """Fix 4: Song of Storms in area $00 summons rain and waters a planted bean once."""
        self.warp(0x00)
        vendors = [s for s in self.sprites() if s['id'] == BEAN_VENDOR]
        self.event('area 00 sprites', sprites=self.sprites())
        if vendors:
            self.w(BEAN, 0x01, 'bean planted, not watered')
        self.equip(13, 0x08, 'Ocarina')
        self.select_song(2)
        self.w(STORM, 0)
        time.sleep(0.2)
        self.press('y', 4)
        time.sleep(1.5)
        self.shot('storms_area00')
        # Control: the old presence check reads leftover scratch $00, so it may or may not
        # find "the vendor" and summon rain; the candidate passes the ID and always does.
        self.check('Song of Storms in area 00 summons rain ($7EE00E)', self.r(STORM),
                   {'candidate': 1, 'control': 'record-only', 'previous': 1})
        if vendors:
            self.check('bean watered bit $04 after Song of Storms', self.r(BEAN) & 0x04,
                       {'candidate': 0x04, 'control': 0x00})
        else:
            self.event('bean vendor not loaded in area 00; watering not exercised')
        if self.r(STORM):
            self.press('y', 4)  # dismiss
            time.sleep(1.5)

    # -- Portal Rod arrows ---------------------------------------------------
    # Ranch ($00) landing is (200,99). Live tile attributes (and a no-portal arrow
    # shot from (252,112), which flies to y ~206) show an open column at x 248-280
    # from y 112. Portals survive only on tile attributes $00/$48. Portal offsets:
    # facing down = Link + (0,31), right = (+20,0), left = (-20,0); the first press
    # is blue. Arrows shot down travel at about x = Link + 4. An arrow entering blue
    # exits 16 px below orange; entering orange, 16 px right of blue.

    def portal_setup(self):
        self.warp(0x00)
        self.w(MAGIC, 0x80, 'full magic')
        self.w(PORTAL_OWNED, 1, 'Portal Rod owned')
        self.w(BOW, 2, 'bow with arrows')
        self.w(ARROWS, 30, '30 arrows')

    def walk_to(self, tx, ty):
        """Controller input only: y then x, stopping when Link no longer moves."""
        for axis, target, addr, pos, neg in (('y', ty, LINK_Y, 'down', 'up'), ('x', tx, LINK_X, 'right', 'left')):
            for _ in range(60):
                cur = self.r16(addr)
                delta = target - cur
                if abs(delta) <= 1:
                    break
                frames = max(1, min(8, int(abs(delta) / 1.5)))
                self.b.press_button(pos if delta > 0 else neg, frames=frames)
                time.sleep((frames + 4) / 60)
                if self.r16(addr) == cur:
                    break
        at = [self.r16(LINK_X), self.r16(LINK_Y)]
        self.event('walked (controller)', target=[tx, ty], at=at)
        return at

    def fire_portal(self, facing, label):
        self.equip(0x19, 0x0D, 'Portal Rod')
        self.w(FACING, facing, f'face {label}')
        time.sleep(0.2)
        self.press('y', 4)
        time.sleep(1.5)
        portals = [s for s in self.sprites() if s['id'] == PORTAL]
        self.event(f'portal fired facing {label}', portals=portals,
                   blue_slot=self.r(0x7E0632), orange_slot=self.r(0x7E0633), link=[self.r16(LINK_X), self.r16(LINK_Y)])
        return portals

    def shoot_down_traced(self):
        """Fire one arrow down with Y while paused, then step 90 frames recording every ancilla."""
        self.equip(1, 0x03, 'Bow')
        self.w(FACING, 2, 'face down')
        time.sleep(0.2)
        self.b.pause()
        try:
            self.b.press_button('y', frames=6)
            frames = []
            for f in range(90):
                self.b.run_frames(1)
                frames.append({'f': f, 'ancillae': self.ancillae(),
                               'deflected': [i for i in range(16) if self.r(SPR_STATE + i)
                                             and self.r(SPR_ID + i) == DEFLECTED_ARROW]})
        finally:
            self.b.resume()
        return frames

    def arrow_trace(self, frames, name):
        """Follow the first arrow slot. Shots are straight down (at most ~9 px/frame), so a
        teleport is any sideways step over 2 px or a vertical step over 12 px."""
        slot = next((a['slot'] for x in frames for a in x['ancillae'] if a['type'] == 0x09), None)
        track = [{'f': x['f'], **a} for x in frames for a in x['ancillae'] if a['slot'] == slot]
        jumps = [{'frame': cur['f'], 'from': [prev['x'], prev['y']], 'to': [cur['x'], cur['y']], 'type': cur['type']}
                 for prev, cur in zip(track, track[1:])
                 if abs(cur['x'] - prev['x']) > 2 or abs(cur['y'] - prev['y']) > 12]
        summary = {'slot': slot, 'track': track, 'jumps': jumps,
                   'deflected': any(x['deflected'] for x in frames),
                   'types': sorted({t['type'] for t in track})}
        self.result.setdefault('portal_traces', {})[name] = summary
        self.persist()
        return summary

    @staticmethod
    def flying_beyond(track, y, after_frame=-1):
        """Arrow is still a flying arrow ($09) at or below y. $0A (stopped) is terminal,
        so a later $09 frame means it never stopped before getting there."""
        return any(t['type'] == 0x09 and t['y'] >= y and t['f'] > after_frame for t in track)

    def check_portal_lone(self):
        """One portal only: the arrow ignores it (no move, no deflection) and keeps flying."""
        self.portal_setup()
        self.walk_to(252, 112)
        portals = self.fire_portal(2, 'down')
        if len(portals) != 1:
            raise RuntimeError(f'expected one portal, saw {portals}')
        p = portals[0]
        t = self.arrow_trace(self.shoot_down_traced(), 'lone')
        self.shot('portal_lone')
        self.check('lone portal: arrow moved', bool(t['jumps']),
                   {'candidate': False, 'control': 'record-only', 'previous': 'record-only'})
        # Control moves the arrow to unused slot 0's coordinates before deflecting it there,
        # so its $1B sprite may die off-screen before a sample: record only.
        self.check('lone portal: deflected-arrow sprite', t['deflected'],
                   {'candidate': False, 'control': 'record-only', 'previous': False})
        self.check('lone portal: arrow still flying ($09) 40 px past the portal',
                   not t['jumps'] and self.flying_beyond(t['track'], p['y'] + 40),
                   {'candidate': True, 'control': False, 'previous': 'record-only'})

    def check_portal_stale(self):
        """Pair placed, Link moves, a third shot dismisses both: the orange index is stale."""
        self.portal_setup()
        self.walk_to(252, 112)
        self.fire_portal(2, 'down')            # blue at (252,143)
        first = self.fire_portal(4, 'left')    # orange at (232,112)
        if len(first) != 2:
            raise RuntimeError(f'expected a portal pair, saw {first}')
        old_orange = next(s for s in first if s['sub'] == 1)
        self.walk_to(264, 112)
        portals = self.fire_portal(2, 'down')  # dismisses both; new blue at (264,143)
        stale = self.r(0x7E0633)
        self.event('stale counterpart', orange_index=stale, state=self.r(SPR_STATE + stale) if stale < 16 else None,
                   id=self.r(SPR_ID + stale) if stale < 16 else None, old_orange=old_orange)
        if len(portals) != 1 or portals[0]['sub'] != 2:
            raise RuntimeError(f'expected one new blue portal, saw {portals}')
        p = portals[0]
        t = self.arrow_trace(self.shoot_down_traced(), 'stale')
        to_stale = any(abs(j['to'][0] - old_orange['x']) <= 4 for j in t['jumps'])
        self.shot('portal_stale')
        self.check('stale counterpart: arrow moved to the dismissed orange', to_stale,
                   {'candidate': False, 'control': 'record-only', 'previous': True})
        self.check('stale counterpart: deflected-arrow sprite', t['deflected'],
                   {'candidate': False, 'control': True, 'previous': False})
        self.check('stale counterpart: arrow still flying ($09) 40 px past the portal',
                   not t['jumps'] and self.flying_beyond(t['track'], p['y'] + 40),
                   {'candidate': True, 'control': False, 'previous': False})

    def check_portal_pair(self):
        """Two valid portals on open ground: the arrow exits 16 px below orange and keeps flying."""
        self.portal_setup()
        self.walk_to(252, 116)   # y 116: orange's tile row is 112 (grass), not the 104 cliff row
        self.fire_portal(2, 'down')              # blue at (252,147)
        portals = self.fire_portal(6, 'right')   # orange at (272,116)
        if len(portals) != 2:
            raise RuntimeError(f'expected a portal pair, saw {portals}')
        orange = next(s for s in portals if s['sub'] == 1)
        t = self.arrow_trace(self.shoot_down_traced(), 'pair')
        # Exit = orange + (0,16), plus at most one frame of downward travel.
        exit_jump = next((j for j in t['jumps'] if j['to'][0] == orange['x']
                          and 16 <= j['to'][1] - orange['y'] <= 16 + 9), None)
        self.shot('portal_pair')
        self.check('valid pair: arrow moved to 16 px below orange', bool(exit_jump),
                   {'candidate': True, 'control': False, 'previous': True})
        self.check('valid pair: deflected-arrow sprite', t['deflected'],
                   {'candidate': False, 'control': True, 'previous': False})
        self.check('valid pair: arrow still flying ($09) 40 px past the exit',
                   bool(exit_jump) and self.flying_beyond(t['track'], exit_jump['to'][1] + 40, exit_jump['frame']),
                   {'candidate': True, 'control': False, 'previous': False})

    def run(self):
        try:
            self.preflight()
            self.launch()
            self.boot_file2()
            for name in self.args.checks:
                try:
                    getattr(self, f'check_{name}')()
                except Exception as exc:  # keep going; record the failed check
                    self.result['checks'].append({'name': name, 'error': f'{type(exc).__name__}: {exc}',
                                                  'matches_variant_expectation': False})
                    self.shot(f'error_{name}')
                    print('ERROR', name, exc, flush=True)
            ok = all(c.get('matches_variant_expectation') for c in self.result['checks'])
            self.result['state'] = 'passed' if ok else 'failed'
        except BaseException as exc:
            self.result['state'] = 'failed'
            self.result['error'] = f'{type(exc).__name__}: {exc}'
        finally:
            self.close()
        print(json.dumps({'state': self.result['state'], 'out': str(self.out)}))
        return self.result['state'] == 'passed'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--variant', choices=('candidate', 'control', 'previous'), required=True,
                    help='previous = the first PR #133 build (af973aa2), before the portal guard')
    ap.add_argument('--rom', type=Path, required=True)
    ap.add_argument('--srm', type=Path, required=True)
    ap.add_argument('--app', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--checks', nargs='+', default=['time_speed', 'storms_area00'])
    sys.exit(0 if Run(ap.parse_args()).run() else 1)


if __name__ == '__main__':
    main()
