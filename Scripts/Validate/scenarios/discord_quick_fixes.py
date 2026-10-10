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
MASK, LINK_GFX, UNDERWATER, ZORA_MASK, BOUND_MASK = 0x7E02B2, 0x7E00BC, 0x7E0AAB, 0x7EF347, 0x7EF3A8
LINK_PALETTE = 0x7EC6E0  # WRAM CGRAM mirror, sprite palette 7 ($7EC500 + $1E0)

SPR_STATE, SPR_ID, SPR_SUB = 0x7E0DD0, 0x7E0E20, 0x7E0E30
SPR_XL, SPR_XH, SPR_YL, SPR_YH = 0x7E0D10, 0x7E0D30, 0x7E0D00, 0x7E0D20
ANC_TYPE, ANC_XL, ANC_XH, ANC_YL, ANC_YH = 0x7E0C4A, 0x7E0C04, 0x7E0C18, 0x7E0BFA, 0x7E0C0E

BEAN_VENDOR, PORTAL, DEFLECTED_ARROW, WHIRLPOOL = 0x07, 0x03, 0x1B, 0x77


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(pid: int) -> str:
    out = subprocess.run(['ps', '-o', 'lstart=,command=', '-p', str(pid)], text=True,
                         capture_output=True, check=False).stdout.strip()
    return out


class TileRoute:
    """4 px BFS route for Link's body over a tile-attribute grid (subclasses define attr)."""
    WALK = (0x00, 0x48)

    def attr(self, px, py):
        raise NotImplementedError

    def route(self, start, goal, bounds, walk=None, nearest=False, blocked=()):
        """4 px BFS for Link's body (x+1..14, y+9..22) on walkable tiles; simplified waypoints.
        nearest=True: path to the reachable cell closest to goal instead of goal itself."""
        import collections
        walk = walk or self.WALK
        x0, y0, x1, y1 = bounds

        def ok(x, y):
            if any(bx0 <= x + 14 and x + 1 <= bx1 and by0 <= y + 22 and y + 9 <= by1
                   for bx0, by0, bx1, by1 in blocked):
                return False
            return all(self.attr(x + dx, y + dy) in walk for dx in (1, 14) for dy in (9, 22))
        start = (start[0] // 4 * 4, start[1] // 4 * 4)
        goal = (goal[0] // 4 * 4, goal[1] // 4 * 4)
        prev, queue, best = {start: None}, collections.deque([start]), start

        def path_to(c):
            path = []
            while c:
                path.append(c)
                c = prev[c]
            path.reverse()
            return [p for i, p in enumerate(path) if i in (0, len(path) - 1) or
                    not (path[i - 1][0] == p[0] == path[i + 1][0] or path[i - 1][1] == p[1] == path[i + 1][1])]
        while queue:
            c = queue.popleft()
            if abs(c[0] - goal[0]) + abs(c[1] - goal[1]) < abs(best[0] - goal[0]) + abs(best[1] - goal[1]):
                best = c
            if c == goal:
                return path_to(c)
            for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4)):
                n = (c[0] + dx, c[1] + dy)
                if n not in prev and x0 <= n[0] <= x1 and y0 <= n[1] <= y1 and ok(*n):
                    prev[n] = c
                    queue.append(n)
        return path_to(best) if nearest and best != start else None


class OverworldTiles(TileRoute):
    """Tile attribute of any pixel in the loaded overworld area: WRAM map16 ($7E2000) ->
    ROM map16 -> tile table -> attribute. Ported from the AFS route harness (p00nav.OWGrid)."""

    def __init__(self, run, rom: Path):
        self.r = run
        data = rom.read_bytes()

        def pc(snes):
            return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)

        def long_at(snes):
            o = pc(snes)
            return data[o + 1] | data[o + 2] << 8 | data[o + 3] << 16
        self.data, self.pc = data, pc
        self.map16, self.tiles = pc(long_at(0x008864)), pc(long_at(0x00886E))
        self.v0708, self.v070A = run.r16(0x7E0708), run.r16(0x7E070A)
        self.v070C, self.v070E = run.r16(0x7E070C), run.r16(0x7E070E)
        self.buf = run.b.read_block(0x7E2000, 0x2000)

    def attr(self, px, py):
        x8 = px >> 3
        off = ((((py - self.v0708) & self.v070A) << 3) | ((x8 - self.v070C) & self.v070E)) & 0x1FFF
        m = self.buf[off] | self.buf[off + 1] << 8
        o = self.map16 + ((m << 2) | ((py & 8) >> 2) | (x8 & 1)) * 2
        if o + 1 >= len(self.data):
            return 0x01
        return self.data[self.tiles + ((self.data[o] | self.data[o + 1] << 8) & 0x1FF)]


class DungeonTiles(TileRoute):
    """Underworld collision for the current room: $7F2000 (layer 1) or $7F3000 (layer 2,
    when $EE is set), 64x64 tiles of 8 px. Ported from the AFS route harness (p00nav.UWGrid)."""
    WALK = tuple([0x00, 0x09, 0x1D, 0x22, 0x3D, 0x3E, 0x3F, 0x48, 0x4B] +
                 list(range(0x80, 0x90)) + list(range(0xA0, 0xB0)))

    def __init__(self, run):
        self.buf = run.b.read_block(0x7F3000 if run.r(0x7E00EE) else 0x7F2000, 0x1000)

    def attr(self, px, py):
        return self.buf[((py & 0x1FF) >> 3) * 64 + ((px & 0x1FF) >> 3)]


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

    # -- Zora Princess --------------------------------------------------------
    def check_princess(self):
        """Only the Song of Healing frees the Zora Princess; the Song of Time keeps running."""
        self.w(0x7EF302, 0, 'Zora Mask quest not done, so the princess loads')
        res = OracleCheats(self.b).warp_entrance(0x45)
        self.fixture('warp_entrance 0x45 (Zora Princess House, room $105)')
        self.event('warp entrance', response=res)
        self.wait_play(10)
        time.sleep(1.0)
        found = [i for i in range(16) if self.r(SPR_STATE + i) >= 9 and self.r(0x7E0ED0 + i) == 1]
        if not found:
            raise RuntimeError(f'no Zora Princess (SprMiscG=1) in room $105: {self.sprites()}')
        i = found[0]
        px, py = self.r(SPR_XL + i) | self.r(SPR_XH + i) << 8, self.r(SPR_YL + i) | self.r(SPR_YH + i) << 8
        action = lambda: self.r(0x7E0D80 + i)
        self.event('princess', slot=i, x=px, y=py, action=action(),
                   link=[self.r16(LINK_X), self.r16(LINK_Y)], camera_y=self.r16(0x7E00E8))
        # Room $105 places her at local (96,64), behind the north door (local y 288); from the
        # entrance Link cannot reach her to talk. Her song check has no distance test, so set
        # the post-talk state directly. The control run shows whether her code runs off-screen.
        self.w(0x7E0D80 + i, 1, 'princess action 1 (waiting for a song): unreachable from the entrance')
        # Off-screen sprites do not run (first control run stayed [2,1]); move her onto the
        # empty throne in view so CheckForSongOfHealing executes.
        tx, ty = self.r16(0x7E00E2) + 128, self.r16(0x7E00E8) + 96
        self.w(SPR_XL + i, tx & 0xFF, f'princess moved onto the throne in view ({tx},{ty})')
        self.w(SPR_XH + i, tx >> 8)
        self.w(SPR_YL + i, ty & 0xFF)
        self.w(SPR_YH + i, ty >> 8)
        time.sleep(0.5)
        self.shot('princess_on_throne')
        self.w(SONGS, 5, 'all four songs learned')
        self.equip(13, 0x08, 'Ocarina')
        self.select_song(4)
        time.sleep(0.2)
        self.press('y', 4)
        time.sleep(2.6)  # flute animation ($03F0 = $80 frames) must end before the next song
        self.shot('princess_song_of_time')
        self.check('Song of Time beside the princess: [SongFlag, princess action]', [self.r(SONG_FLAG), action()],
                   {'candidate': [2, 1], 'control': [0, 2], 'previous': [2, 1]})
        self.select_song(1)
        time.sleep(0.2)
        self.press('y', 4)
        time.sleep(2.6)
        self.shot('princess_song_of_healing')
        self.check('Song of Healing frees her (action >= 2)', action() >= 2,
                   {'candidate': True, 'control': 'record-only', 'previous': True})
        self.check('time speed back to $3F after the Healing song', self.r(TIME_SPEED),
                   {'candidate': 0x3F, 'control': 'record-only', 'previous': 0x3F})

    # -- Zora Mask whirlpool ($3D) --------------------------------------------
    def travel(self, goal, bounds, nearest=False, grid=None):
        """Plan on tile attributes and walk with controller input. Sprites (NPCs, signs)
        are not in the tile map: on a stall, block 24 px ahead and re-plan (up to 4 times)."""
        blocked = []
        for _ in range(5):
            tiles = grid() if grid else OverworldTiles(self, self.rom)
            here = (self.r16(LINK_X), self.r16(LINK_Y))
            path = tiles.route(here, goal, bounds, nearest=nearest, blocked=blocked)
            if not path:
                raise RuntimeError(f'no route from {here} to {goal} (blocked {blocked})')
            self.event('route', goal=list(goal), waypoints=path, blocked=[list(b) for b in blocked])
            for x, y in path[1:]:
                self.b.write_memory(0x7E037B, 1)
                at = self.walk_to(x, y)
                if abs(at[0] - x) > 6 or abs(at[1] - y) > 6:
                    dx, dy = (x > at[0]) - (x < at[0]), (y > at[1]) - (y < at[1])
                    cx, cy = at[0] + 8 + dx * 20, at[1] + 16 + dy * 20
                    blocked.append((cx - 12, cy - 12, cx + 12, cy + 12))
                    self.event('walk stalled; re-planning', at=at, heading=[x, y])
                    break
            else:
                return path[-1]
        raise RuntimeError(f'walk to {goal} kept stalling: {blocked}')

    def clear_text(self):
        for _ in range(12):
            if self.r(MODULE) != 0x0E:
                return
            self.press('a', 4)
            time.sleep(0.4)
        self.wait_play(5)

    def check_whirlpool(self):
        """Zora Mask through the $3D whirlpool: Link's sprite bank and palette are reset."""
        self.fixture('$7E037B=1 (no damage) refreshed before each walking leg')
        self.warp(0x33)  # Loom Beach; $3D has no warp-table entry
        self.travel((2528, 3752), (0x0600, 0x0C00, 0x09F0, 0x0FE8))
        self.press('right', 48)
        self.wait_play(12)
        if self.r(AREA) != 0x3D:
            raise RuntimeError(f'expected area 0x3D after crossing, in 0x{self.r(AREA):02X}')
        self.event('crossed into 3D (controller)', x=self.r16(LINK_X), y=self.r16(LINK_Y))
        normal_palette = self.b.read_block(LINK_PALETTE, 32).hex()
        pool_x, pool_y = 0x0A00 + 386, 0x0E00 + 290
        try:
            self.travel((pool_x, pool_y), (0x0A00, 0x0E00, 0x0BF0, 0x0FE8), nearest=True)
        except RuntimeError as exc:  # the water edge stops Link short of the pool
            dist = abs(self.r16(LINK_X) - pool_x) + abs(self.r16(LINK_Y) - pool_y)
            if dist > 64:
                raise
            self.event('stopped at the water edge near the whirlpool', distance=dist, detail=str(exc)[:120])
        time.sleep(0.5)
        pools = [s for s in self.sprites() if s['id'] == WHIRLPOOL]
        self.event('area 3D sprites', sprites=self.sprites(), link_palette=normal_palette)
        self.shot('near_whirlpool')
        if not pools:
            raise RuntimeError('no whirlpool sprite active near Link')
        # The dock NPC ($F0) talks on contact; page its text away and step back first.
        self.clear_text()
        self.walk_to(self.r16(LINK_X) - 24, self.r16(LINK_Y) - 8)
        self.clear_text()
        self.w(ZORA_MASK, 1, 'Zora Mask owned')
        self.w(BOUND_MASK, 2, 'Zora Mask bound to R (mask_binding.asm, 2 = Zora)')
        self.press('r', 4)
        time.sleep(2.0)
        self.clear_text()
        self.check('Zora Mask worn before the whirlpool [mask, gfx]', [self.r(MASK), self.r(LINK_GFX)],
                   {'candidate': [2, 0x36], 'control': [2, 0x36], 'previous': [2, 0x36]})
        pool = pools[0]
        # Controller only from here: step off the dock into the water (Link swims, $5D=$04),
        # swim onto the whirlpool, press Y to dive (zora_mask.asm sets $0AAB).
        for _ in range(12):
            if self.r(0x7E005D) == 0x04:
                break
            self.press('right' if self.r16(LINK_X) < pool['x'] else 'down', 8)
            time.sleep(0.3)
        self.event('swimming', state_5D=self.r(0x7E005D), at=[self.r16(LINK_X), self.r16(LINK_Y)])
        self.walk_to(pool['x'], pool['y'])
        # Step the dive and warp frame by frame: mask, sprite bank and palette per frame,
        # a screenshot every 8 frames, to catch a transient wrong ("white") Link.
        self.b.pause()
        warp_frames = []
        try:
            self.b.press_button('y', frames=4)
            for f in range(160):
                self.b.run_frames(1)
                pal = self.b.read_block(LINK_PALETTE, 32).hex()
                warp_frames.append({'f': f, 'mod': self.r(MODULE), 'sub': self.r(SUBMODULE), 'area': self.r(AREA),
                                    'mask': self.r(MASK), 'gfx': self.r(LINK_GFX), 'pal': pal[:24]})
                if f % 8 == 0:
                    png = self.b.screenshot()
                    if png:
                        (self.out / f'warp_f{f:03d}.png').write_bytes(png)
        finally:
            self.b.resume()
        self.result['warp_frames'] = [x for i, x in enumerate(warp_frames) if i == 0 or
                                      {k: v for k, v in x.items() if k != 'f'} !=
                                      {k: v for k, v in warp_frames[i - 1].items() if k != 'f'}]
        self.persist()
        self.event('whirlpool trigger', module=self.r(MODULE), sub=self.r(SUBMODULE))
        time.sleep(4.0)
        self.wait_play(12)
        self.shot('after_whirlpool')
        after = self.b.read_block(LINK_PALETTE, 32).hex()
        self.event('after whirlpool', area=f'{self.r(AREA):02X}', world=self.r(0x7E0FFF), mask=self.r(MASK),
                   gfx=self.r(LINK_GFX), link_palette=after, x=self.r16(LINK_X), y=self.r16(LINK_Y))
        self.check('whirlpool warp happened (area changed or Link moved)', self.r(AREA) != 0x3D or
                   abs(self.r16(LINK_X) - pool['x']) + abs(self.r16(LINK_Y) - pool['y']) > 32,
                   {'candidate': True, 'control': True, 'previous': True})
        mismatch = [x['f'] for x in warp_frames if x['mask'] == 0 and x['gfx'] == 0x36]
        self.event('warp frames with mask 0 but the Zora sprite bank $36', count=len(mismatch),
                   first=mismatch[:1], last=mismatch[-1:])
        self.check('whirlpool warp: Link drawn with the Zora bank after the mask flag is cleared', bool(mismatch),
                   {'candidate': False, 'control': True, 'previous': False})
        self.check('after the whirlpool [area, mask, gfx] (Dark World GBC form)',
                   [self.r(AREA), self.r(MASK), self.r(LINK_GFX)],
                   {'candidate': [0x7D, 6, 0x3B], 'control': [0x7D, 6, 0x3B], 'previous': [0x7D, 6, 0x3B]})

    # -- Zora Princess, natural path (Codex follow-up 2026-10-09) ----------------
    def gate_step(self, category, name, ok, **observed):
        """Record one natural-path step; the caller stops at the first failure."""
        self.result.setdefault('gate_steps', []).append({'category': category, 'step': name, 'ok': bool(ok), **observed})
        self.persist()
        print(('ok   ' if ok else 'STOP ') + f'[{category}] {name}', observed, flush=True)
        if not ok:
            self.shot('gate_stop_' + ''.join(c if c.isalnum() else '_' for c in name)[:40])
        return bool(ok)

    def page_text(self, rounds=16):
        for _ in range(rounds):
            if self.r(MODULE) != 0x0E:
                return
            self.press('a', 4)
            time.sleep(0.45)

    def princess_natural_path(self):
        """Returns the first failed step name, or None. No princess action or position writes."""
        before = {'quest_302': self.r(0x7EF302), 'zora_mask_347': self.r(ZORA_MASK),
                  'bigkey_366': self.r(0x7EF366), 'bigkey_367': self.r(0x7EF367)}
        self.event('file 2 state before fixtures', **before)
        self.w(0x7EF302, 0, 'pre-quest: Zora Mask quest not done (file 2 has finished it)')
        self.w(ZORA_MASK, 0, 'pre-quest: Zora Mask not owned')
        if not before['bigkey_366'] & 0x10:
            self.w(0x7EF366, before['bigkey_366'] | 0x10, 'Big Key for dungeon $16 ($7EF366 bit $10, DungeonMask $0010)')
        else:
            self.event('Big Key bit for dungeon $16 already owned by file 2')
        res = OracleCheats(self.b).warp_entrance(0x45)
        self.fixture('warp_entrance 0x45 (Zora Princess House, room $105)')
        self.event('warp entrance', ok=res.get('ok'), dungeon=self.r(0x7E040C))
        self.wait_play(10)
        time.sleep(1.0)
        found = [i for i in range(16) if self.r(SPR_STATE + i) >= 9 and self.r(SPR_ID + i) == 0xB8]
        pos = lambda i: (self.r(SPR_XL + i) | self.r(SPR_XH + i) << 8, self.r(SPR_YL + i) | self.r(SPR_YH + i) << 8)
        if not self.gate_step('gate/progression', 'princess loaded at her authored position (2656,8256)',
                              bool(found) and pos(found[0]) == (2656, 8256),
                              found=[(i, pos(i), self.r(0x7E0D80 + i)) for i in found], dungeon=self.r(0x7E040C)):
            return 'princess loaded at her authored position (2656,8256)'
        i = found[0]
        action = lambda: self.r(0x7E0D80 + i)
        dungeon = lambda: DungeonTiles(self)
        # Lower compartment (entrance) -> north Big Key door at tile (14,36), local (112,288).
        try:
            at = self.travel((2672, 8484), (2576, 8480, 2800, 8688), nearest=True, grid=dungeon)
        except RuntimeError as exc:
            self.gate_step('room navigation', 'walk to the north door', False, error=str(exc)[:160])
            return 'walk to the north door'
        self.gate_step('room navigation', 'walk to the north door', True, at=[self.r16(LINK_X), self.r16(LINK_Y)])
        y0 = self.r16(LINK_Y)
        for _ in range(8):
            self.press('up', 24)
            time.sleep(0.3)
            if self.r(MODULE) == 0x0E:
                break
            self.wait_play(6)
            if self.r16(LINK_Y) < 8192 + 280:
                break
        if self.r(MODULE) == 0x0E:
            msg = self.r16(0x7E1CF0)
            self.gate_step('gate/progression', 'Big Key door opens', False, message=hex(msg))
            return 'Big Key door opens'
        self.wait_play(8)
        if not self.gate_step('gate/progression', 'through the Big Key door into the upper compartment',
                              self.r16(LINK_Y) < 8192 + 280, y_before=y0, y_after=self.r16(LINK_Y)):
            return 'through the Big Key door into the upper compartment'
        try:
            self.travel((2656, 8280), (2584, 8224, 2740, 8432), nearest=True, grid=dungeon)
        except RuntimeError as exc:
            self.event('stopped short of the princess', detail=str(exc)[:160])
        lx, ly = self.r16(LINK_X), self.r16(LINK_Y)
        px, py = pos(i)
        if not self.gate_step('room navigation', 'reach the princess (within 24 px)',
                              abs(lx - px) <= 24 and abs(ly - py) <= 32, link=[lx, ly], princess=[px, py]):
            return 'reach the princess (within 24 px)'
        attempts = []
        for hold in (10, 16, 24):  # close the gap (she blocks Link), then A
            self.press('up' if ly > py else 'down', hold)
            time.sleep(0.2)
            self.press('a', 4)
            time.sleep(0.8)
            talked = self.r(MODULE) == 0x0E or action() == 1
            attempts.append({'hold_frames': hold, 'link': [self.r16(LINK_X), self.r16(LINK_Y)], 'facing': self.r(FACING),
                             'module': self.r(MODULE), 'message': hex(self.r16(0x7E1CF0)), 'action': action()})
            self.page_text()
            self.wait_play(6)
            if talked or action() == 1:
                break
        if not self.gate_step('interaction', 'talking reaches action 1 (waiting for a song)', action() == 1,
                              action=action(), attempts=attempts):
            return 'talking reaches action 1 (waiting for a song)'
        self.w(SONGS, 5, 'all four songs learned (file 2 knows two)')
        self.equip(13, 0x08, 'Ocarina')
        self.select_song(4)
        time.sleep(0.2)
        self.press('y', 4)
        time.sleep(2.6)
        if not self.gate_step('interaction', 'Song of Time leaves her waiting', action() == 1 and self.r(SONG_FLAG) == 2,
                              action=action(), song_flag=self.r(SONG_FLAG)):
            return 'Song of Time leaves her waiting'
        self.select_song(1)
        time.sleep(0.2)
        self.press('y', 4)
        time.sleep(1.0)
        if not self.gate_step('interaction', 'Song of Healing frees her (action >= 2)', action() >= 2 or
                              self.r(0x7EF302) == 1, action=action()):
            return 'Song of Healing frees her (action >= 2)'
        for _ in range(30):  # thanks message $C6, then the item receipt
            self.page_text(4)
            if self.r(ZORA_MASK) and self.r(0x7EF302) == 1:
                break
            time.sleep(0.5)
        self.page_text()
        self.shot('princess_mask_granted')
        if not self.gate_step('grant', 'Zora Mask granted ($7EF347 owned, $7EF302 = 1)',
                              self.r(ZORA_MASK) != 0 and self.r(0x7EF302) == 1,
                              mask_347=self.r(ZORA_MASK), quest_302=self.r(0x7EF302), princess_state=self.r(SPR_STATE + i)):
            return 'Zora Mask granted ($7EF347 owned, $7EF302 = 1)'
        return None

    def check_princess_gate(self):
        first_fail = self.princess_natural_path()
        self.check('princess natural path: first failed step', first_fail,
                   {'candidate': None, 'control': 'Song of Time leaves her waiting', 'previous': None})

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
