#!/usr/bin/env python3
"""Headless Mesen2 check for the small-key block (Dungeons/keyblock.asm).

Boots a copy of the ROM with a copied test SRAM, loads file 2 with controller
input, warps to D1 Mushroom Grotto (entrance $26, room $4A), walks north into
room $3A and pushes up into the key block at tile (31,34) from below.

Cases (one emulator boot each):
  no_key   $7EF36F = 0: the block must stay shut and the game must keep running.
  one_key  $7EF36F = 1: the key is spent, the block opens, and it is still open
           after Link walks out to room $4A and back in.

Exec breakpoints at $01EB8C (Object_KeyBlock), $01EBA6 (vanilla open path),
$01EBE1 (vanilla exit) and the two bad targets of the 2026-01-26 code
($01EBA0 RTS, $01EBA8 TSB/BRK) record which path ran.

Declared fixtures (result.json "fixtures"): the key count, the warp, room $4A's
north key door marked open in its save word (so no key is spent on it), room
$3A's chest/lock bits cleared if set, enemies deactivated on room entry, the
no-damage flag, and one collision patch in room $4A: the entrance half reaches
the north door only through a one-tile-high gap Link cannot walk through, so
tile rows 28-31 x cols 9-22 of $7F2000 are set to $00 (graphics unchanged).
Walking, door transitions and the push into the block are controller input.

  python3 Scripts/Validate/scenarios/keyblock_unlock.py --variant candidate \
      --case one_key --rom Roms/oos168x.sfc --srm <test.srm> --app <Mesen2 OOS.app> --out <dir>

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

MODULE, SUBMODULE, FRAME = 0x7E0010, 0x7E0011, 0x7E001A
LINK_Y, LINK_X, ROOM, DUNGEON = 0x7E0020, 0x7E0022, 0x7E00A0, 0x7E040C
KEYS, NO_DAMAGE = 0x7EF36F, 0x7E037B
DOOR_FLAGS, CHEST_FLAGS, CHEST_TILES = 0x7E0400, 0x7E0402, 0x7E06E0

ENTRANCE_D1 = 0x26
ROOM_ENTRY, ROOM_BLOCK = 0x4A, 0x3A
BLOCK_TILE = (31, 34)  # z3ed dungeon-list-objects: object $F98 in room $3A
CHEST_ATTRS = range(0x58, 0x60)

BREAKPOINTS = {0x01EB8C: 'Object_KeyBlock', 0x01EBA6: 'vanilla .open_big_key_lock',
               0x01EBE1: 'vanilla .cannot_open_big_key_lock', 0x01EBA0: 'old RTS (no key)',
               0x01EBA8: 'old BRA target (TSB/BRK)'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(pid: int) -> str:
    return subprocess.run(['ps', '-o', 'lstart=,command=', '-p', str(pid)], text=True,
                          capture_output=True, check=False).stdout.strip()


def room_origin(room):
    return (room & 0x0F) * 0x200, (room >> 4) * 0x200


class DungeonTiles:
    """Underworld collision for the current room: $7F2000 (layer 1) or $7F3000 (layer 2,
    when $EE is set), 64x64 tiles of 8 px. Same route rules as discord_quick_fixes.py."""
    WALK = tuple([0x00, 0x09, 0x1D, 0x22, 0x3D, 0x3E, 0x3F, 0x48, 0x4B] +
                 list(range(0x80, 0x90)) + list(range(0xA0, 0xB0)))

    def __init__(self, run):
        self.buf = run.b.read_block(0x7F3000 if run.r(0x7E00EE) else 0x7F2000, 0x1000)

    def attr(self, px, py):
        return self.buf[((py & 0x1FF) >> 3) * 64 + ((px & 0x1FF) >> 3)]

    def route(self, start, goal, bounds, nearest=False):
        """4 px BFS for Link's body (x+1..14, y+9..22) on walkable tiles; simplified waypoints."""
        x0, y0, x1, y1 = bounds

        def ok(x, y):
            return all(self.attr(x + dx, y + dy) in self.WALK for dx in (1, 14) for dy in (9, 22))
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


class Run:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        stamp = time.strftime('%Y%m%d-%H%M%S')
        self.out = Path(args.out) / f'{args.variant}-{args.case}-{stamp}-{uuid.uuid4().hex[:6]}'
        self.out.mkdir(parents=True)
        self.name = f'kb-{args.variant}-{uuid.uuid4().hex[:6]}'
        self.sock = Path(f'/tmp/mesen2-{self.name}.sock')
        self.pid = None
        self.pid_identity = None
        self.b = None
        self.bp_ids = {}
        self.result = {'variant': args.variant, 'case': args.case, 'out': str(self.out), 'fixtures': [],
                       'checks': [], 'events': [], 'state': 'running'}

    # -- bookkeeping -------------------------------------------------------
    def persist(self):
        (self.out / 'result.json').write_text(json.dumps(self.result, indent=1) + '\n')

    def event(self, name, **extra):
        self.result['events'].append({'t': round(time.time(), 2), 'name': name, **extra})
        self.persist()

    def fixture(self, text):
        self.result['fixtures'].append(text)
        self.persist()

    def check(self, name, observed, expected):
        ok = expected == 'record-only' or observed == expected
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

    def link(self):
        return [self.r16(LINK_X), self.r16(LINK_Y)]

    def sprites(self):
        out = []
        for i in range(16):
            if self.r(0x7E0DD0 + i) >= 9:
                out.append({'slot': i, 'id': f'{self.r(0x7E0E20 + i):02X}',
                            'x': self.r(0x7E0D10 + i) | self.r(0x7E0D30 + i) << 8,
                            'y': self.r(0x7E0D00 + i) | self.r(0x7E0D20 + i) << 8})
        return out

    def alive(self, label):
        """The game keeps running: frame counter advances, normal play module, and Link
        answers controller input (one step down, one step back up)."""
        f0 = self.r(FRAME)
        time.sleep(0.5)
        f1 = self.r(FRAME)
        cpu = self.b.get_cpu_state()
        y0 = self.r16(LINK_Y)
        self.press('down', 8)
        moved = self.r16(LINK_Y) - y0
        self.press('up', 8)
        state = {'frame_advanced': f0 != f1, 'module': self.r(MODULE), 'submodule': self.r(SUBMODULE),
                 'room': self.r16(ROOM), 'down_moved_px': moved, 'cpu': cpu}
        self.event(f'alive check: {label}', **state)
        return state['frame_advanced'] and state['module'] in (7, 9) and moved > 0

    # -- breakpoints -------------------------------------------------------
    def arm_breakpoints(self):
        for addr in BREAKPOINTS:
            self.bp_ids[addr] = self.b.add_breakpoint(addr, 'exec')
        self.event('breakpoints armed', ids={f'${a:06X}': i for a, i in self.bp_ids.items()})

    def is_paused(self):
        res = self.b.send_command('STATE')
        data = res.get('data', {}) if isinstance(res, dict) else {}
        return bool(isinstance(data, dict) and data.get('paused'))

    def collect_breaks(self, hits, timeout=0.6):
        """Record each break (PC, registers, top of stack), drop that breakpoint, resume."""
        end = time.time() + timeout
        while time.time() < end and len(hits) < 12:
            if not self.is_paused():
                time.sleep(0.02)
                continue
            cpu = self.b.get_cpu_state()
            pc = cpu.get('pc', cpu.get('PC'))
            pc = int(pc, 16) if isinstance(pc, str) else pc
            k = cpu.get('k', cpu.get('K', 0))
            k = int(k, 16) if isinstance(k, str) else (k or 0)
            full = pc if pc is not None and pc > 0xFFFF else ((k << 16) | (pc or 0))
            sp = cpu.get('sp', cpu.get('SP'))
            sp = int(sp, 16) if isinstance(sp, str) else sp
            stack = self.b.read_block(0x7E0000 + sp + 1, 8).hex(' ') if isinstance(sp, int) else None
            # Mesen also breaks when an exec breakpoint byte is fetched as an operand; such a
            # hit reports the PC of the instruction that contains it and is not a path step.
            armed = [a for a in self.bp_ids if full <= a < full + 4]
            exact = full in BREAKPOINTS
            hits.append({'pc': f'${full:06X}', 'exact': exact,
                         'label': BREAKPOINTS[full] if exact else
                         'operand fetch of ' + ', '.join(f'${a:06X}' for a in armed),
                         'cpu': cpu, 'stack_top': stack, 'keys': self.r(KEYS)})
            for a in ([full] if exact else armed):
                if self.bp_ids.get(a, -1) >= 0:
                    self.b.remove_breakpoint(self.bp_ids.pop(a))
            self.b.resume()
            end = time.time() + timeout
        return hits

    def clear_breakpoints(self):
        for addr in list(self.bp_ids):
            self.b.remove_breakpoint(self.bp_ids.pop(addr))
        if self.is_paused():
            self.b.resume()

    # -- lifecycle ---------------------------------------------------------
    def preflight(self):
        a = self.args
        self.rom = self.out / f'kb-{a.variant}.sfc'
        shutil.copy2(a.rom, self.rom)
        self.home = self.out / 'profile'
        (self.home / 'Saves').mkdir(parents=True)
        shutil.copy2(a.srm, self.home / 'Saves' / f'kb-{a.variant}.srm')
        self.result['rom'] = {'source': str(a.rom), 'sha256': sha(self.rom),
                              'bytes_01EB8C': self.rom.read_bytes()[0xEB8C:0xEBAC].hex(' ')}
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
        self.event('file 2 loaded (controller)', module=self.r(MODULE), room=self.r16(ROOM))

    # -- walking -----------------------------------------------------------
    def walk_to(self, tx, ty):
        """Controller input only: y then x, stopping when Link no longer moves."""
        for addr, target, pos, neg in ((LINK_Y, ty, 'down', 'up'), (LINK_X, tx, 'right', 'left')):
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

    def travel(self, goal, bounds, nearest=False):
        tiles = DungeonTiles(self)
        here = tuple(self.link())
        path = tiles.route(here, goal, bounds, nearest=nearest)
        if not path:
            raise RuntimeError(f'no route from {here} to {goal}')
        self.event('route', goal=list(goal), waypoints=path)
        for x, y in path[1:]:
            self.w(NO_DAMAGE, 1)
            at = self.walk_to(x, y)
            if abs(at[0] - x) > 6 or abs(at[1] - y) > 6:
                raise RuntimeError(f'walk stalled at {at} heading to {(x, y)}')
        self.event('walked (controller)', goal=list(goal), at=self.link())
        return self.link()

    def through_door(self, button, room, hold=24, tries=8):
        """Hold a direction until the room changes to `room` (controller)."""
        for _ in range(tries):
            self.w(NO_DAMAGE, 1)
            self.press(button, hold)
            self.wait_play(6)
            if self.r16(ROOM) == room:
                time.sleep(0.4)
                self.event(f'entered room ${room:02X} (controller)', at=self.link())
                return True
        return False

    # -- key block ---------------------------------------------------------
    def block_state(self):
        """Collision attributes under the block's 2x2 tiles, chest-tile slots and room flags."""
        tiles = DungeonTiles(self)
        ox, oy = room_origin(ROOM_BLOCK)
        bx, by = BLOCK_TILE[0] * 8, BLOCK_TILE[1] * 8
        attrs = [tiles.attr(bx + dx, by + dy) for dy in (0, 8) for dx in (0, 8)]
        slots = [self.r16(CHEST_TILES + 2 * i) for i in range(6)]
        return {'attrs': [f'{a:02X}' for a in attrs], 'closed': any(a in CHEST_ATTRS for a in attrs),
                'chest_slots': [f'{s:04X}' for s in slots], 'chest_flags_0402': f'{self.r16(CHEST_FLAGS):04X}',
                'save_room_3A': f'{self.r16(0x7EF000 + 2 * ROOM_BLOCK):04X}', 'keys': self.r(KEYS),
                'block_abs': [ox + bx, oy + by]}

    def lock_slot(self):
        """Index of the big-key-lock slot ($06E0,Y with bit 15 set) in room $3A."""
        for i in range(6):
            if self.r16(CHEST_TILES + 2 * i) & 0x8000:
                return i
        return None

    def clear_enemies(self, room):
        """Declared fixture: deactivate the room's enemies ($0DD0,X = 0). D1's $B1 enemies
        stand in the one-tile-wide corridors and stop the controller walk."""
        gone = [s for s in self.sprites()]
        for s in gone:
            self.w(0x7E0DD0 + s['slot'], 0)
        if gone:
            self.fixture(f'room ${room:02X}: enemies deactivated ($0DD0,X=0) {[(s["slot"], s["id"]) for s in gone]}')

    def push(self, button, label, tries=6):
        """Hold a direction into the block (controller) while recording breakpoint hits;
        if Object_KeyBlock is not reached by walking into it, press A (Link_PerformOpenChest)."""
        self.arm_breakpoints()
        hits = []
        for i in range(tries):
            self.w(NO_DAMAGE, 1)
            self.b.press_button(button if i < tries - 2 else 'a', frames=16)
            self.collect_breaks(hits, timeout=0.6)
            if len(hits) >= 2:
                break
        self.collect_breaks(hits, timeout=1.0)
        self.clear_breakpoints()
        self.result.setdefault('breakpoint_hits', {})[label] = hits
        self.event(f'{label} (controller)', hits=[h['pc'] + ' ' + h['label'] for h in hits])
        return hits

    def run_case(self):
        a = self.args
        want_keys = 1 if a.case == 'one_key' else 0
        save_3A, save_4A = 0x7EF000 + 2 * ROOM_BLOCK, 0x7EF000 + 2 * ROOM_ENTRY
        before = {'keys_36F': self.r(KEYS), 'save_room_3A': f'{self.r16(save_3A):04X}',
                  'save_room_4A': f'{self.r16(save_4A):04X}', 'd1_saved_keys_382': self.r(0x7EF382)}
        self.event('file 2 state before fixtures', **before)
        # Room $3A save bits 4-9 are its chest/lock flags; a set bit loads the block open.
        if self.r16(save_3A) & 0x03F0:
            self.w16(save_3A, self.r16(save_3A) & ~0x03F0, 'room $3A chest/lock bits cleared so the key block is shut')
        # Room $4A north key door (tile 30,4) is door bit $8000; opening it would spend the key.
        self.w16(save_4A, self.r16(save_4A) | 0x8000, 'room $4A north key door marked open (no key spent on it)')
        res = OracleCheats(self.b).warp_entrance(ENTRANCE_D1)
        self.fixture(f'warp_entrance 0x{ENTRANCE_D1:02X} (D1 Mushroom Grotto, room $4A)')
        self.event('warp entrance', response=res, dungeon=self.r(DUNGEON))
        if not self.wait_play(10) or self.r16(ROOM) != ROOM_ENTRY:
            raise RuntimeError(f'warp landed in room ${self.r16(ROOM):04X}')
        self.w(KEYS, want_keys, f'small keys = {want_keys}')
        self.clear_enemies(ROOM_ENTRY)
        self.event('room $4A', link=self.link(), doors_0400=f'{self.r16(DOOR_FLAGS):04X}')
        self.shot('room4A')
        # The entrance half of room $4A reaches the north half only through a one-tile-high
        # gap (tile row 31) that Link cannot walk through; open a 4x14 tile patch in the
        # collision map so the controller walk can reach the north door (graphics unchanged).
        for ty in range(28, 32):
            self.b.write_block(0x7F2000 + ty * 64 + 9, bytes(14))
        self.fixture('room $4A collision $7F2000 tile rows 28-31, cols 9-22 set to $00 (walk path to the north half)')
        ox, oy = room_origin(ROOM_ENTRY)
        self.travel((ox + 240, oy + 48), (ox + 16, oy + 16, ox + 480, oy + 480))
        self.shot('room4A_north_door')
        if not self.through_door('up', ROOM_BLOCK):
            raise RuntimeError(f'could not enter room $3A; in ${self.r16(ROOM):04X} at {self.link()}')
        self.clear_enemies(ROOM_BLOCK)
        st = self.block_state()
        slot = self.lock_slot()
        self.event('room $3A entered', link=self.link(), lock_slot=slot, **st)
        self.shot('room3A_entered')
        if not self.check('key block is shut on entry', st['closed'], True):
            return
        # Walk up the south corridor to just below the block, then push up into it.
        bx, by = st['block_abs']
        self.travel((bx, by + 12), (bx - 16, by, bx + 32, by + 200))
        self.event('below the key block (controller)', at=self.link(), keys=self.r(KEYS))
        self.shot('below_block')
        hits = self.push('up', 'push up into the block')
        time.sleep(1.0)
        self.shot('after_push')
        alive = self.alive('after the push')
        after = self.block_state()
        self.event('block after the push', link=self.link(), **after)
        self.check('Object_KeyBlock ran ($01EB8C hit)', any(h['pc'] == '$01EB8C' for h in hits), True)
        self.check('game keeps running after the push', alive, a.expect_alive)
        if not alive:
            self.result['crash'] = {'module': self.r(MODULE), 'room': self.r16(ROOM), 'cpu': self.b.get_cpu_state()}
            return
        exit_pc = [h['pc'] for h in hits if h['exact'] and h['pc'] != '$01EB8C']
        self.w(NO_DAMAGE, 1)
        self.press('up', 24)
        # Link's collision top is y+9: below by+7 means his body is inside the block's tiles.
        inside = self.r16(LINK_Y) < by + 7
        self.event('pressed up again (controller)', at=self.link(), block_bottom_limit=by + 7, inside_block=inside)
        if a.case == 'no_key':
            self.check('exit path', exit_pc[:1], ['$01EBE1'])
            self.check('block stays shut', after['closed'], True)
            self.check('keys stay 0', after['keys'], 0)
            self.check('Link cannot walk into the block', inside, False)
            return
        self.check('exit path', exit_pc[:1], ['$01EBA6'])
        self.check('key spent (1 -> 0)', after['keys'], 0)
        self.check('block open (no chest attrs under it)', after['closed'], False)
        lock_bit = 0x0100 << slot if slot is not None else 0
        self.check('$0402 lock bit set', bool(self.r16(CHEST_FLAGS) & lock_bit), True)
        self.check('Link walks into the opened block', inside, True)
        # Leave to room $4A through the south door and come back (controller).
        self.travel((bx, oy - 0x200 + 440), (bx - 16, by - 16, bx + 32, by + 200))
        if not self.through_door('down', ROOM_ENTRY):
            raise RuntimeError(f'could not return to room $4A; at {self.link()}')
        self.event('back in room $4A', save_room_3A=f'{self.r16(save_3A):04X}', keys=self.r(KEYS))
        self.shot('back_in_4A')
        self.clear_enemies(ROOM_ENTRY)
        if not self.through_door('up', ROOM_BLOCK):
            raise RuntimeError(f'could not re-enter room $3A; at {self.link()}')
        self.clear_enemies(ROOM_BLOCK)
        again = self.block_state()
        self.event('room $3A re-entered', link=self.link(), **again)
        self.shot('room3A_reentered')
        self.check('block still open after re-entry', again['closed'], False)
        self.check('keys still 0 after re-entry', again['keys'], 0)
        self.check('room $3A save word keeps the lock bit ($0010 << slot)',
                   bool(int(again['save_room_3A'], 16) & (0x0010 << (slot or 0))), True)
        self.check('$0402 lock bit set after re-entry', bool(self.r16(CHEST_FLAGS) & lock_bit), True)
        self.travel((bx, by + 12), (bx - 16, by, bx + 32, by + 200))
        hits = self.push('up', 'walk up through the opened block after re-entry')
        self.check('Object_KeyBlock not reached once open', any(h['pc'] == '$01EB8C' for h in hits), False)
        self.check('Link walks into the opened block after re-entry', self.r16(LINK_Y) < by + 7, True)
        self.check('keys still 0 at the end', self.r(KEYS), 0)
        self.shot('reentered_walked_through')

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
                self.result['error_context'] = {'module': self.r(MODULE), 'room': self.r16(ROOM),
                                                'link': self.link(), 'cpu': self.b.get_cpu_state()}
            except Exception:  # noqa: BLE001
                pass
        finally:
            if self.b:
                try:
                    self.clear_breakpoints()
                except Exception:  # noqa: BLE001
                    pass
            self.close()
            self.persist()
        failed = [c['name'] for c in self.result['checks'] if not c['matches_expectation']]
        self.result['passed'] = self.result['state'] == 'finished' and not failed
        self.persist()
        print(json.dumps({'out': str(self.out), 'state': self.result['state'], 'failed': failed}), flush=True)
        return 0 if self.result['passed'] else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--variant', required=True, help='label for the ROM (candidate, control)')
    p.add_argument('--case', required=True, choices=('no_key', 'one_key'))
    p.add_argument('--expect-crash', dest='expect_alive', action='store_false',
                   help='record a crash as the expected result (control ROM)')
    p.add_argument('--rom', required=True)
    p.add_argument('--srm', required=True)
    p.add_argument('--app', required=True)
    p.add_argument('--out', required=True)
    return Run(p.parse_args()).run()


if __name__ == '__main__':
    sys.exit(main())
