#!/usr/bin/env python3
"""Headless Mesen2 check: a minecart on a stop tile starts in that stop's
direction after a staircase entry (Sprites/Objects/minecart.asm).

Sprite_Minecart_Prep picks the start direction from the stop tile under the
cart (B7 South, B8 North, B9 East, BA West). A spiral-stair entry (module
07/0E) runs Prep before the room's collision table ($7F2000) is built, so Prep
reads the previous room's tile and falls through to North. The fix reads the
stop tile again on the cart's first active frame (module 07/00).

Two cases, one emulator boot per ROM:
  1. stair   from a savestate in room $077's stair area, hold Up 120 frames to
             take the spiral stair to $0A8. Exec breakpoints on the four
             start-direction branches log every hit (PC, SPRTILE $0FA5, module).
             Track 5 cart at tile (14,44), stop B7:
               candidate: Prep goNorth (00, 07/0E), then goSouth (B7, 07/00);
                          SprMiscB = 2 (South)
               control:   Prep goNorth (00, 07/0E) only; SprMiscB = 0 (North)
  2. door    (optional) from a savestate in room $0D8, hold Right 60 frames
             into $0D9, then Left 60 frames back (edge entry, module 07/02).
             Track 16 cart at tile (14,14), stop B9: Prep goEast (B9, 07/02);
             action 0, SprMiscB = 1 (East) on both ROMs.

The ROM must contain the deep-floor carts (A8 track 5, D8 track 16); the RC
base gets them from the goron_routes deep-floor-carts recipe. Branch addresses
come from the .sym of the same build (control: Oracle_Sprite_Minecart_Prep_go*,
candidate: Oracle_Minecart_SetStartFromStopTile_go*).

  python3 Scripts/Validate/scenarios/minecart_stair_entry.py --variant candidate \
      --rom <built ROM + carts> --sym <same build .sym> --stair-state <077.mss> \
      [--door-state <0D8.mss>] [--srm <save>] --app <Mesen2 OOS.app> --out <dir>

Declared fixtures: the savestates, and invincibility $7E037B = 1 before each
input leg. Rules (agent_board.md): headless only, own profile and socket, stop
only the owned PID with SIGTERM, ROM copy named without "test" or "oos<digits>".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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

LAUNCHER = REPO / 'Scripts' / 'Mesen2' / 'mesen2_launch_instance.sh'

MODULE, SUBMODULE, ROOM, NO_DAMAGE, SPRTILE = 0x7E0010, 0x7E0011, 0x7E00A0, 0x7E037B, 0x7E0FA5
SPR_STATE, SPR_ID, SPR_ACTION, SPR_SUBTYPE = 0x7E0DD0, 0x7E0E20, 0x7E0D80, 0x7E0E30
SPR_MISCA, SPR_MISCB, SPR_MISCC = 0x7E0DA0, 0x7E0DB0, 0x7E0DE0
SPR_XL, SPR_XH, SPR_YL, SPR_YH = 0x7E0D10, 0x7E0D30, 0x7E0D00, 0x7E0D20
MINECART = 0xA3
DIRECTIONS = ('North', 'East', 'South', 'West')
LABELS = ('Oracle_Minecart_SetStartFromStopTile_go', 'Oracle_Sprite_Minecart_Prep_go')

EXPECT = {
    'stair: room after the stair': {'candidate': '0A8', 'control': '0A8'},
    'stair: Prep branch at 07/0E': {'candidate': 'goNorth/00', 'control': 'goNorth/00'},
    'stair: branch at 07/00 (first active frame)': {'candidate': 'goSouth/B7', 'control': None},
    'stair: track 5 cart SprMiscB': {'candidate': 2, 'control': 0},
    'door: room after re-entry': {'candidate': '0D8', 'control': '0D8'},
    'door: Prep branch at 07/02': {'candidate': 'goEast/B9', 'control': 'goEast/B9'},
    'door: track 16 cart action, SprMiscB': {'candidate': [0, 1], 'control': [0, 1]},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(pid: int) -> str:
    return subprocess.run(['/bin/ps', '-o', 'lstart=,command=', '-p', str(pid)], text=True,
                          capture_output=True, check=False).stdout.strip()


def branch_addresses(sym: Path) -> dict[int, str]:
    """The four start-direction branches of this build, from its WLA .sym."""
    found = {}
    for line in sym.read_text().splitlines():
        m = re.match(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$', line.strip())
        if m:
            found[m.group(3)] = int(m.group(1) + m.group(2), 16)
    for prefix in LABELS:
        names = [prefix + d for d in DIRECTIONS]
        if all(n in found for n in names):
            return {found[prefix + d]: 'go' + d for d in DIRECTIONS}
    raise RuntimeError(f'{sym}: no start-direction labels ({LABELS})')


class Run:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        stamp = time.strftime('%Y%m%d-%H%M%S')
        self.out = Path(args.out) / f'{args.variant}-{stamp}-{uuid.uuid4().hex[:6]}'
        self.out.mkdir(parents=True)
        self.name = f'mcs-{args.variant}-{uuid.uuid4().hex[:6]}'
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

    def no_damage(self):
        if not self.b.write_memory(NO_DAMAGE, 1):
            raise RuntimeError('write failed $7E037B')

    def wait_play(self, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                time.sleep(0.3)
                if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                    return True
            time.sleep(0.1)
        return False

    def paused(self):
        res = self.b.send_command('STATE')
        data = res.get('data', {}) if isinstance(res, dict) else {}
        return bool(isinstance(data, dict) and data.get('paused'))

    def carts(self):
        out = []
        for i in range(16):
            if self.r(SPR_STATE + i) and self.r(SPR_ID + i) == MINECART:
                out.append({'slot': i, 'track': self.r(SPR_SUBTYPE + i), 'state': self.r(SPR_STATE + i),
                            'action': self.r(SPR_ACTION + i), 'miscB': self.r(SPR_MISCB + i),
                            'facing_0DE0': self.r(SPR_MISCC + i), 'pending_0DA0': self.r(SPR_MISCA + i),
                            'x': self.r(SPR_XL + i) | self.r(SPR_XH + i) << 8,
                            'y': self.r(SPR_YL + i) | self.r(SPR_YH + i) << 8})
        return out

    def cart(self, track):
        hits = [c for c in self.carts() if c['track'] == track]
        return hits[0] if hits else None

    # -- breakpoint probe --------------------------------------------------
    def probe(self, button, frames, tail=6.0):
        """Hold BUTTON for FRAMES with exec breakpoints on the start-direction branches;
        log each hit and resume. Returns the hits."""
        ids = {addr: self.b.add_breakpoint(addr, 'exec') for addr in self.branches}
        hits = []
        try:
            self.no_damage()
            self.b.press_button(button, frames=frames, detach_debugger=False)
            end = time.time() + frames / 60 + 2.0
            while time.time() < end and len(hits) < 12:
                if not self.paused():
                    time.sleep(0.02)
                    continue
                cpu = self.b.get_cpu_state()
                pc = cpu.get('pc', cpu.get('PC', 0))
                pc = int(pc, 16) if isinstance(pc, str) else (pc or 0)
                k = cpu.get('k', cpu.get('K', 0))
                k = int(k, 16) if isinstance(k, str) else (k or 0)
                full = pc if pc > 0xFFFF else (k << 16) | pc
                x = cpu.get('x', cpu.get('X', 0))
                slot = (int(x, 16) if isinstance(x, str) else (x or 0)) & 0xFF
                hit = {'pc': f'${full:06X}', 'label': self.branches.get(full, 'other'),
                       'sprtile': f'{self.r(SPRTILE):02X}', 'module': f'{self.r(MODULE):02X}/{self.r(SUBMODULE):02X}',
                       'room': f'{self.r16(ROOM):03X}', 'slot': slot, 'track': self.r(SPR_SUBTYPE + slot)}
                hits.append(hit)
                self.event('break', **hit)
                self.b.resume()
                end = time.time() + tail
        finally:
            for bp in ids.values():
                if bp >= 0:
                    self.b.remove_breakpoint(bp)
            if self.paused():
                self.b.resume()
        return hits

    @staticmethod
    def branch_at(hits, module, track):
        hit = [h for h in hits if h['module'] == module and h['track'] == track and h['label'] != 'other']
        return f'{hit[0]["label"]}/{hit[0]["sprtile"]}' if hit else None

    # -- lifecycle ---------------------------------------------------------
    def preflight(self):
        a = self.args
        self.rom = self.out / f'mcs-{a.variant}.sfc'
        shutil.copy2(a.rom, self.rom)
        self.home = self.out / 'profile'
        (self.home / 'Saves').mkdir(parents=True)
        if a.srm:
            shutil.copy2(a.srm, self.home / 'Saves' / f'mcs-{a.variant}.srm')
            self.result['srm'] = {'source': str(a.srm), 'sha256': sha(Path(a.srm))}
        self.branches = branch_addresses(Path(a.sym))
        self.result['rom'] = {'source': str(a.rom), 'sha256': sha(self.rom)}
        self.result['sym'] = {'source': str(a.sym), 'sha256': sha(Path(a.sym))}
        self.result['branches'] = {f'${k:06X}': v for k, v in self.branches.items()}
        self.result['app'] = str(a.app)
        self.result['harness_sha256'] = sha(Path(__file__))
        self.fixture('invincibility $7E037B = 1 before each input leg')
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
        time.sleep(3)

    def close(self):
        if self.pid and identity(self.pid) == self.pid_identity:
            os.kill(self.pid, signal.SIGTERM)
            for _ in range(50):
                if identity(self.pid) != self.pid_identity:
                    self.result['emulator']['exited'] = True
                    break
                time.sleep(0.1)
        self.persist()

    def load(self, path, room):
        if not self.b.load_state(path=str(path)):
            raise RuntimeError(f'load_state failed: {path}')
        self.fixture(f'savestate {path} (sha256 {sha(Path(path))[:16]})')
        time.sleep(0.5)
        if not self.wait_play() or self.r16(ROOM) != room:
            raise RuntimeError(f'{path}: expected room {room:03X} in play, got {self.r16(ROOM):03X}')

    # -- cases -------------------------------------------------------------
    def stair_case(self):
        self.load(self.args.stair_state, 0x077)
        hits = self.probe('up', 120)
        self.wait_play()
        self.check('stair: room after the stair', f'{self.r16(ROOM):03X}')
        self.check('stair: Prep branch at 07/0E', self.branch_at(hits, '07/0E', 5))
        self.check('stair: branch at 07/00 (first active frame)', self.branch_at(hits, '07/00', 5))
        cart = self.cart(5)
        self.event('stair: track 5 cart', cart=cart)
        self.check('stair: track 5 cart SprMiscB', cart['miscB'] if cart else None)
        self.shot('stair_a8')

    def door_case(self):
        self.load(self.args.door_state, 0x0D8)
        self.no_damage()
        self.b.press_button('right', frames=60)
        time.sleep(1.5)
        if not self.wait_play() or self.r16(ROOM) != 0x0D9:
            raise RuntimeError(f'door: expected room 0D9, got {self.r16(ROOM):03X}')
        hits = self.probe('left', 60, tail=4.0)
        self.wait_play()
        self.check('door: room after re-entry', f'{self.r16(ROOM):03X}')
        self.check('door: Prep branch at 07/02', self.branch_at(hits, '07/02', 16))
        cart = self.cart(16)
        self.event('door: track 16 cart', cart=cart)
        self.check('door: track 16 cart action, SprMiscB', [cart['action'], cart['miscB']] if cart else None)
        self.shot('door_d8')

    def run(self):
        try:
            self.preflight()
            self.launch()
            self.stair_case()
            if self.args.door_state:
                self.door_case()
            self.result['state'] = 'finished'
        except Exception as exc:  # noqa: BLE001
            self.result['state'] = 'error'
            self.result['error'] = f'{type(exc).__name__}: {exc}'
            print('ERROR', self.result['error'], flush=True)
            try:
                self.shot('error')
                self.result['error_context'] = {'module': self.r(MODULE), 'room': f'{self.r16(ROOM):03X}',
                                                'carts': self.carts(), 'cpu': self.b.get_cpu_state()}
            except Exception:  # noqa: BLE001
                pass
        finally:
            self.close()
            self.persist()
        failed = [c['name'] for c in self.result['checks'] if not c['matches_expectation']]
        self.result['passed'] = self.result['state'] == 'finished' and not failed
        self.persist()
        print(json.dumps({'out': str(self.out), 'state': self.result['state'], 'failed': failed}), flush=True)
        return 0 if self.result['passed'] else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--variant', required=True, choices=('candidate', 'control'))
    p.add_argument('--rom', required=True, help='built ROM with the deep-floor carts')
    p.add_argument('--sym', required=True, help='WLA .sym from the same build')
    p.add_argument('--stair-state', required=True, help='savestate in room $077 below the stair to $0A8')
    p.add_argument('--door-state', help='savestate in room $0D8 at its east door to $0D9')
    p.add_argument('--srm', help='cart SRAM to place next to the ROM (optional)')
    p.add_argument('--app', required=True)
    p.add_argument('--out', required=True)
    return Run(p.parse_args()).run()


if __name__ == '__main__':
    sys.exit(main())
