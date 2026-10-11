#!/usr/bin/env python3
"""Headless Mesen2 check: the Kalyxo Goron stays in mines-open state after the
area $36 heart piece is collected (Sprites/NPCs/goron.asm Sprite_Goron_Prep).

Area $36 (Garo Desert) keeps two bits in its overworld flag byte $7EF2B6:
$20 = mines overlay open (Overworld/overlays.asm), $40 = heart piece taken
(vanilla HeartSetFlagOverworld, $05EFF7). Sprite_Goron_Prep chooses the
Goron's first action from that byte: 2 (KalyxoGoron_MinesOpened) when the
mines are open, else 0 (KalyxoGoron_Main: asks for Rock Meat and, with 5,
replays KalyxoGoron_OpenMines).

One emulator boot per ROM, file 2 of the mines-open test save:
  1. flag $20 alone   warp to area $36; the Goron must start in action 2.
  2. heart piece      walk to the heart piece at (3104,3584) with controller
                      input and collect it, so vanilla code ORs $40 into
                      $7EF2B6 (if the walk fails, $40 is ORed in as a declared
                      fixture); warp to area $36 again (fresh sprite load).
                      candidate: action 2; control: action 0.
  3. talk             walk next to the Goron, face it, press A.
                      candidate: no text; control: message $01A9 (Rock Meat).

Declared fixtures (result.json "fixtures"): the area warps, the no-damage
flag, the clock hour if the run starts at night (the Goron is only in the
day sprite list), and the $40 write if the heart piece is not reached.

  python3 Scripts/Validate/scenarios/goron_heartpiece_flag.py --variant candidate \
      --rom Roms/oos168x.sfc --srm <test-goron-mines-open.srm> --app <Mesen2 OOS.app> --out <dir>

Rules this follows (agent_board.md): headless only, own isolated profile and
socket, stop only the owned PID with SIGTERM, ROM copy named without "test"
or "oos<digits>".
"""
from __future__ import annotations

import argparse
import collections
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

MODULE, SUBMODULE, INDOORS, AREA, WORLDFLAG = 0x7E0010, 0x7E0011, 0x7E001B, 0x7E008A, 0x7E0FFF
LINK_Y, LINK_X, FACING, NO_DAMAGE = 0x7E0020, 0x7E0022, 0x7E002F, 0x7E037B
MESSAGE_ID, MINES_SEQUENCE = 0x7E1CF0, 0x7E04C6
HOURS = 0x7EE000  # TimeState.Hours; Oracle_CheckIfNight: night = Hours >= $12 or < $06
AREA_FLAG = 0x7EF2B6  # $7EF280 + area $36
GAME_STATE, ROCK_MEAT, HEART_PIECES = 0x7EF3C5, 0x7EF38F, 0x7EF36B
SPR_STATE, SPR_ID, SPR_ACTION = 0x7E0DD0, 0x7E0E20, 0x7E0D80
SPR_XL, SPR_XH, SPR_YL, SPR_YH = 0x7E0D10, 0x7E0D30, 0x7E0D00, 0x7E0D20

AREA_ID = 0x36
BEACH_CAVE_END = 0x1B  # room $ED; door on area $36 at (32,448) next to the heart piece ledge
GORON, HEART_PIECE = 0xF2, 0xEB
HEART_POS = (3104, 3584)  # z3ed overworld-list-sprites --screen 0x36: $EB, day and night lists
AREA_BOUNDS = (3072 + 8, 3072 + 8, 4096 - 24, 4096 - 32)
ACTIONS = {0: 'KalyxoGoron_Main', 1: 'KalyxoGoron_OpenMines', 2: 'KalyxoGoron_MinesOpened'}

EXPECT = {
    'flag $20: Goron action': {'candidate': 2, 'control': 2},
    'flag $60: Goron action': {'candidate': 2, 'control': 0},
    'talk: message shown': {'candidate': False, 'control': True},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(pid: int) -> str:
    return subprocess.run(['/bin/ps', '-o', 'lstart=,command=', '-p', str(pid)], text=True,
                          capture_output=True, check=False).stdout.strip()


class OverworldTiles:
    """Tile attribute of any pixel in the loaded overworld area (WRAM map16 at $7E2000 ->
    ROM map16 -> tile table -> attribute) and a 4 px BFS route for Link's body.
    Same as Scripts/Validate/scenarios/discord_quick_fixes.py."""
    WALK = (0x00, 0x48)

    def __init__(self, run, rom: Path):
        data = rom.read_bytes()

        def pc(snes):
            return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)

        def long_at(snes):
            o = pc(snes)
            return data[o + 1] | data[o + 2] << 8 | data[o + 3] << 16
        self.data = data
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

    def route(self, start, goal, bounds, blocked=()):
        x0, y0, x1, y1 = bounds

        def ok(x, y):
            if any(bx0 <= x + 14 and x + 1 <= bx1 and by0 <= y + 22 and y + 9 <= by1
                   for bx0, by0, bx1, by1 in blocked):
                return False
            return all(self.attr(x + dx, y + dy) in self.WALK for dx in (1, 14) for dy in (9, 22))
        start = (start[0] // 4 * 4, start[1] // 4 * 4)
        goal = (goal[0] // 4 * 4, goal[1] // 4 * 4)
        prev, queue = {start: None}, collections.deque([start])
        while queue:
            c = queue.popleft()
            if c == goal:
                path = []
                while c:
                    path.append(c)
                    c = prev[c]
                path.reverse()
                return [p for i, p in enumerate(path) if i in (0, len(path) - 1) or
                        not (path[i - 1][0] == p[0] == path[i + 1][0] or path[i - 1][1] == p[1] == path[i + 1][1])]
            for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4)):
                n = (c[0] + dx, c[1] + dy)
                if n not in prev and x0 <= n[0] <= x1 and y0 <= n[1] <= y1 and ok(*n):
                    prev[n] = c
                    queue.append(n)
        return None


class Run:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        stamp = time.strftime('%Y%m%d-%H%M%S')
        self.out = Path(args.out) / f'{args.variant}-{stamp}-{uuid.uuid4().hex[:6]}'
        self.out.mkdir(parents=True)
        self.name = f'gh-{args.variant}-{uuid.uuid4().hex[:6]}'
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

    def check(self, name, observed):
        expected = EXPECT[name][self.args.variant]
        ok = observed == expected
        self.result['checks'].append({'name': name, 'observed': observed, 'expected': expected,
                                      'matches_expectation': ok})
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
            self.fixture(f'${addr:06X}={value & 0xFF:02X} ({why})')

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

    def link(self):
        return [self.r16(LINK_X), self.r16(LINK_Y)]

    def sprites(self):
        out = []
        for i in range(16):
            if self.r(SPR_STATE + i):
                out.append({'slot': i, 'id': self.r(SPR_ID + i), 'state': self.r(SPR_STATE + i),
                            'action': self.r(SPR_ACTION + i),
                            'x': self.r(SPR_XL + i) | self.r(SPR_XH + i) << 8,
                            'y': self.r(SPR_YL + i) | self.r(SPR_YH + i) << 8})
        return out

    def find(self, sprite_id):
        hits = [s for s in self.sprites() if s['id'] == sprite_id]
        return hits[0] if hits else None

    def flags(self):
        return {'area_flag_2B6': f'{self.r(AREA_FLAG):02X}', 'heart_pieces_36B': self.r(HEART_PIECES),
                'rock_meat_38F': self.r(ROCK_MEAT), 'game_state_3C5': self.r(GAME_STATE),
                'worldflag': self.r(WORLDFLAG), 'hours': self.r(HOURS), 'area': f'{self.r(AREA):02X}'}

    # -- lifecycle ---------------------------------------------------------
    def preflight(self):
        a = self.args
        self.rom = self.out / f'gh-{a.variant}.sfc'
        shutil.copy2(a.rom, self.rom)
        self.home = self.out / 'profile'
        (self.home / 'Saves').mkdir(parents=True)
        shutil.copy2(a.srm, self.home / 'Saves' / f'gh-{a.variant}.srm')
        self.result['rom'] = {'source': str(a.rom), 'sha256': sha(self.rom)}
        self.result['srm'] = {'source': str(a.srm), 'sha256': sha(Path(a.srm))}
        self.result['app'] = str(a.app)
        self.result['harness_sha256'] = sha(Path(__file__))
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
        self.result['emulator'] = {'pid': self.pid, 'socket': str(self.sock), 'rom_info': self.b.get_rom_info()}
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
        self.event('file 2 loaded (controller)', module=self.r(MODULE), **self.flags())

    # -- movement ----------------------------------------------------------
    def warp(self, why):
        if not 0x06 <= self.r(HOURS) < 0x12:
            self.w(HOURS, 0x08, 'clock to 08:00; the Goron is only in the day sprite list')
        res = OracleCheats(self.b).warp_area(AREA_ID)
        self.fixture(f'warp_area 0x{AREA_ID:02X} ({why})')
        self.event('warp', why=why, response=res)
        if not res.get('ok') or not self.wait_play():
            raise RuntimeError(f'warp to 0x{AREA_ID:02X} failed: {res}')
        time.sleep(0.8)

    def walk_to(self, tx, ty, order='yx'):
        """Controller input only, one axis then the other, stopping when Link no longer moves."""
        legs = {'y': (LINK_Y, ty, 'down', 'up'), 'x': (LINK_X, tx, 'right', 'left')}
        for axis in order:
            addr, target, pos, neg = legs[axis]
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
        return self.link()

    def travel(self, goal, stop=None):
        """Plan on tile attributes and walk with controller input. Sprites are not in the
        tile map: on a stall, block 24 px ahead and re-plan (up to 4 times).
        stop(): optional early-exit test checked after each leg."""
        blocked = []
        for _ in range(5):
            here = tuple(self.link())
            path = OverworldTiles(self, self.rom).route(here, goal, AREA_BOUNDS, blocked=blocked)
            if not path:
                self.event('no route', at=list(here), goal=list(goal), blocked=[list(b) for b in blocked])
                return False
            self.event('route', goal=list(goal), waypoints=path, blocked=[list(b) for b in blocked])
            for x, y in path[1:]:
                self.b.write_memory(NO_DAMAGE, 1)
                at = self.walk_to(x, y)
                if stop and stop():
                    return True
                if abs(at[0] - x) > 6 or abs(at[1] - y) > 6:
                    dx, dy = (x > at[0]) - (x < at[0]), (y > at[1]) - (y < at[1])
                    cx, cy = at[0] + 8 + dx * 20, at[1] + 16 + dy * 20
                    blocked.append((cx - 12, cy - 12, cx + 12, cy + 12))
                    self.event('walk stalled; re-planning', at=at, heading=[x, y])
                    break
            else:
                self.event('walked (controller)', goal=list(goal), at=self.link())
                return True
        return False

    def clear_text(self, rounds=16):
        for _ in range(rounds):
            if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                return True
            self.press('a', 4)
            time.sleep(0.4)
        return self.wait_play(5)

    # -- steps -------------------------------------------------------------
    def goron_action(self, label):
        goron = self.find(GORON)
        self.event(f'{label}: sprites after area load', sprites=self.sprites(), **self.flags())
        self.shot(label.replace(' ', '_').replace('$', ''))
        if goron is None:
            raise RuntimeError(f'{label}: no Goron ($F2) loaded in area $36; sprites {self.sprites()}')
        action = goron['action']
        self.event(f'{label}: Goron', slot=goron['slot'], action=action, action_name=ACTIONS.get(action),
                   at=[goron['x'], goron['y']])
        return goron, action

    def leave_cave(self):
        """Walk down out of the Beach Cave End room onto its area $36 ledge (controller)."""
        res = OracleCheats(self.b).warp_entrance(BEACH_CAVE_END)
        self.fixture(f'warp_entrance 0x{BEACH_CAVE_END:02X} (Beach Cave End; its door opens onto the heart piece ledge)')
        self.event('warp entrance', response=res, link=self.link())
        if not self.wait_play(10) or not self.r(INDOORS):
            raise RuntimeError(f'cave warp failed: {res}')
        for _ in range(12):
            self.b.write_memory(NO_DAMAGE, 1)
            self.press('down', 16)
            if not self.r(INDOORS):
                break
        if not self.wait_play(10) or self.r(INDOORS) or self.r(AREA) != AREA_ID:
            raise RuntimeError(f'did not walk out onto area $36: indoors {self.r(INDOORS)} area {self.r(AREA):02X}')
        time.sleep(0.5)
        self.event('left the cave onto area $36 (controller)', link=self.link(), **self.flags())

    def collect_heart_piece(self):
        """The heart piece is on a walled ledge outside Beach Cave End, not reachable from
        the mines plaza. Overworld sprites spawn as the camera reaches them, so look after."""
        before = self.r(HEART_PIECES)
        self.leave_cave()
        picked = lambda: bool(self.r(AREA_FLAG) & 0x40) or self.r(MODULE) not in (7, 9) or self.r(SUBMODULE) != 0  # noqa: E731
        hx, hy = HEART_POS
        reached = self.travel((hx, hy - 12), stop=picked)
        self.event('near the heart piece', reached=reached, link=self.link(), heart=self.find(HEART_PIECE),
                   **self.flags())
        # Step onto the heart piece from a few sides until the pickup starts.
        for tx, ty in ((hx, hy - 4), (hx - 6, hy - 8), (hx + 6, hy - 8), (hx, hy + 4)):
            if picked():
                break
            self.b.write_memory(NO_DAMAGE, 1)
            self.walk_to(tx, ty)
        for _ in range(30):
            if self.r(AREA_FLAG) & 0x40:
                break
            time.sleep(0.1)
        self.shot('heart_piece_touched')
        self.clear_text()
        taken = bool(self.r(AREA_FLAG) & 0x40)
        self.event('heart piece after pickup attempt', reached=reached, taken=taken, link=self.link(),
                   heart_pieces_before=before, **self.flags())
        return taken

    def talk_to_goron(self, goron):
        """Stand just north of the Goron, push down against it, press A while holding down
        (vanilla Sprite_ShowSolicitedMessage $05E1A7 needs body contact, facing and a new
        A press). $1CF0 is written on every call of that routine, before those checks, so a
        cleared $1CF0 that turns $01A9 shows KalyxoGoron_Main ran even without a text box.
        Also records $04C6 (the mines-opening sequence that KalyxoGoron_OpenMines starts)."""
        gx, gy = goron['x'], goron['y']
        ok = self.travel((gx, gy - 20))
        self.walk_to(gx, gy - 18, order='xy')
        self.w(MESSAGE_ID, 0)
        self.w(MESSAGE_ID + 1, 0)
        self.fixture('$7E1CF0 word cleared before the A press (message id probe)')
        shown, tries = False, []
        # North first, then the sides and south (Link walks around with controller input).
        for push, spot, order in (('down', (gx, gy - 18), 'xy'), ('right', (gx - 18, gy - 4), 'xy'),
                                  ('left', (gx + 18, gy - 4), 'xy'), ('up', (gx, gy + 12), 'xy')):
            if push != 'down':
                self.walk_to(spot[0], gy - 24, order='yx')
                self.walk_to(*spot, order=order)
            for _ in range(2):
                self.b.write_memory(NO_DAMAGE, 1)
                self.press(push, 8)
                at, facing = self.link(), self.r(FACING)
                self.press(f'{push},a', 3)
                time.sleep(0.3)
                shown = self.r(MODULE) == 0x0E
                tries.append({'push': push, 'at': at, 'facing': facing, 'module': self.r(MODULE)})
                if shown:
                    break
            if shown:
                break
        msg = self.r16(MESSAGE_ID)
        self.shot('talk')
        self.event('talk (controller)', route_ok=ok, tries=tries, goron=[gx, gy],
                   module=self.r(MODULE), message_id=f'{msg:04X}', text_shown=shown)
        self.clear_text()
        time.sleep(1.0)
        after = self.find(GORON)
        self.event('after talk', goron=after, mines_sequence_04C6=self.r(MINES_SEQUENCE), module=self.r(MODULE),
                   **self.flags())
        self.shot('after_talk')
        return shown, msg

    def run_case(self):
        before = self.flags()
        self.result['save_state_before'] = before
        if before['area_flag_2B6'] != '20':
            raise RuntimeError(f'file 2 area $36 flag is {before["area_flag_2B6"]}, expected 20')
        # 1. Mines open, heart piece not taken.
        self.w(NO_DAMAGE, 1, 'no damage (refreshed before each walking leg)')
        self.warp('first load with flag $20')
        _, action = self.goron_action('flag $20')
        self.check('flag $20: Goron action', action)
        # 2. Take the heart piece with controller input (vanilla code sets bit $40).
        taken = self.collect_heart_piece()
        self.result['heart_piece_by_controller'] = taken
        if not taken:
            self.w(AREA_FLAG, self.r(AREA_FLAG) | 0x40, 'heart piece not reached: bit $40 set by hand')
        self.event('area flag before reload', **self.flags())
        self.warp('reload after the heart piece')
        if self.find(HEART_PIECE):
            self.event('note: heart piece sprite loaded again although bit $40 is set')
        goron, action = self.goron_action('flag $60')
        self.result['area_flag_at_reload'] = f'{self.r(AREA_FLAG):02X}'
        self.check('flag $60: Goron action', action)
        # 3. What the player sees: talk to the Goron.
        shown, msg = self.talk_to_goron(goron)
        self.result['talk'] = {'text_shown': shown, 'message_id': f'{msg:04X}'}
        self.check('talk: message shown', shown)

    def run(self):
        try:
            self.preflight()
            self.launch()
            self.boot_file2()
            self.run_case()
            self.result['state'] = 'finished'
        except Exception as exc:  # noqa: BLE001
            self.result['state'] = 'error'
            self.result['error'] = f'{type(exc).__name__}: {exc}'
            print('ERROR', self.result['error'], flush=True)
            try:
                self.shot('error')
                self.result['error_context'] = {'module': self.r(MODULE), 'link': self.link(),
                                                'flags': self.flags(), 'cpu': self.b.get_cpu_state()}
            except Exception:  # noqa: BLE001
                pass
        finally:
            self.close()
            self.persist()
        failed = [c['name'] for c in self.result['checks'] if not c['matches_expectation']]
        self.result['passed'] = self.result['state'] == 'finished' and not failed
        self.persist()
        print(json.dumps({'out': str(self.out), 'state': self.result['state'], 'failed': failed,
                          'heart_piece_by_controller': self.result.get('heart_piece_by_controller')}), flush=True)
        return 0 if self.result['passed'] else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--variant', required=True, choices=('candidate', 'control'))
    p.add_argument('--rom', required=True)
    p.add_argument('--srm', required=True)
    p.add_argument('--app', required=True)
    p.add_argument('--out', required=True)
    return Run(p.parse_args()).run()


if __name__ == '__main__':
    sys.exit(main())
