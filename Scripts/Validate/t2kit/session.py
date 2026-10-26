"""One headless Mesen2 episode: own instance and socket, a ROM copy, a copied SRAM,
file load by controller input, declared fixtures, checks and result.json.

Extracted from Scripts/Validate/scenarios/keyblock_unlock.py. Rules it keeps
(agent_board.md): headless only, own isolated profile and socket, stop only the
owned PID with SIGTERM, ROM copy named without "test" or "oos<digits>", every
injected state declared in result.json "fixtures".
"""
from __future__ import annotations

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

from .dungeon import DungeonTiles

REPO = Path(__file__).resolve().parents[3]
LAUNCHER = REPO / 'Scripts' / 'Mesen2' / 'mesen2_launch_instance.sh'
KIT_DIR = Path(__file__).resolve().parent
DEFAULT_APPS = (
    os.environ.get('OOS_T2_APP', ''),
    str(Path.home() / 'src/hobby/mesen2-oos-spc-current/bin/staged/spc-restore-70390092/Mesen2 OOS.app'),
    '/Applications/Mesen2 OOS.app',
)

MODULE, SUBMODULE, FRAME = 0x7E0010, 0x7E0011, 0x7E001A
LINK_Y, LINK_X, ROOM, DUNGEON = 0x7E0020, 0x7E0022, 0x7E00A0, 0x7E040C
NO_DAMAGE, FILE_CURSOR = 0x7E037B, 0x7E00C8
PLAY_MODULES = (7, 9)


class ScenarioError(RuntimeError):
    """The scenario could not reach the state it tests (route, door, warp)."""


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def kit_sha() -> str:
    h = hashlib.sha256()
    for p in sorted(KIT_DIR.glob('*.py')):
        h.update(p.name.encode() + b'\0' + p.read_bytes())
    return h.hexdigest()


def safe_name(text: str) -> str:
    """Instance/ROM copy names must not contain "test" or "oos<digits>" (launcher rules)."""
    text = re.sub(r'[^A-Za-z0-9_-]+', '-', text)
    return re.sub(r'(?i)test|oos\d', 'x', text)


def default_app() -> str | None:
    return next((a for a in DEFAULT_APPS if a and Path(a).is_dir()), None)


def identity(pid: int) -> str:
    return subprocess.run(['ps', '-o', 'lstart=,command=', '-p', str(pid)], text=True,
                          capture_output=True, check=False).stdout.strip()


def _bridge_classes():
    """MesenBridge and OracleCheats from the sibling mesen2-oos checkout (lazy: unit tests skip it)."""
    if not os.environ.get('MESEN2_OOS_ROOT'):
        for parent in REPO.parents:
            if (parent / 'mesen2-oos' / 'tools' / 'oos_client').is_dir():
                os.environ['MESEN2_OOS_ROOT'] = str(parent / 'mesen2-oos')
                break
    sys.path.insert(0, str(REPO / 'Scripts' / 'Mesen2'))
    from mesen2_client_lib.bridge import MesenBridge
    from mesen2_client_lib.oracle_cheats import OracleCheats
    return MesenBridge, OracleCheats


class Session:
    """`t` in a scenario. Construct, then `execute(fn, case)` boots, runs fn(t, case),
    stops the emulator and returns the result dict."""

    def __init__(self, rom, srm, out, scenario='t2', variant='candidate', case='default', file_slot=2,
                 app=None, fixture_name=None, scenario_file=None, invincible=True):
        self.src_rom, self.src_srm = Path(rom), Path(srm)
        self.app = app or default_app()
        if not self.app:
            raise FileNotFoundError('no Mesen2 OOS.app found; pass --app or set OOS_T2_APP')
        self.file_slot = file_slot
        self.invincible = invincible
        stamp = time.strftime('%Y%m%d-%H%M%S')
        self.out = Path(out) / f'{variant}-{case}-{stamp}-{uuid.uuid4().hex[:6]}'
        self.out.mkdir(parents=True)
        self.tag = safe_name(f'{scenario}-{variant}')
        self.name = safe_name(f't2-{scenario[:12]}-{variant}-{uuid.uuid4().hex[:6]}')
        self.sock = Path(f'/tmp/mesen2-{self.name}.sock')
        self.pid = self.pid_identity = self.b = None
        self._guard_declared = False
        self.bp_ids, self.bp_labels = {}, {}
        self.result = {'scenario': scenario, 'variant': variant, 'case': case, 'out': str(self.out),
                       'fixture': fixture_name, 'fixtures': [], 'checks': [], 'events': [], 'state': 'running',
                       'kit_sha256': kit_sha()}
        if scenario_file:
            self.result['scenario_sha256'] = sha(scenario_file)

    # -- bookkeeping -------------------------------------------------------
    def persist(self):
        (self.out / 'result.json').write_text(json.dumps(self.result, indent=1) + '\n')

    def event(self, name, **extra):
        self.result['events'].append({'t': round(time.time(), 2), 'name': name, **extra})
        self.persist()

    def fixture(self, text):
        """Declare injected state (anything not reached by controller input)."""
        self.result['fixtures'].append(text)
        self.persist()

    def check(self, name, observed, expected):
        ok = expected == 'record-only' or observed == expected
        self.result['checks'].append({'name': name, 'observed': observed, 'expected': expected,
                                      'matches_expectation': ok})
        self.persist()
        print(('PASS ' if ok else 'FAIL ') + name, observed, flush=True)
        return ok

    def screenshot(self, label):
        png = self.b.screenshot()
        if png:
            path = self.out / f'{len(self.result["events"]):03d}_{label}.png'
            path.write_bytes(png)
            self.event('screenshot', label=label, path=str(path))

    shot = screenshot

    # -- memory ------------------------------------------------------------
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
        self.w(addr + 1, (value >> 8) & 0xFF)
        if why:
            self.fixture(f'${addr:06X}={value & 0xFFFF:04X} ({why})')

    def fixture_ram(self, addr, value, why, width=1):
        """Write RAM/SRAM mirror state and declare it."""
        (self.w16 if width == 2 else self.w)(addr, value, why)

    def fixture_collision(self, cells, tile_type, why, base=0x7F2000):
        """Set collision cells (tx, ty) of the current room's map ($7F2000 layer 1) to
        `tile_type`. Graphics stay unchanged; the next room load rebuilds the map."""
        rows = {}
        for tx, ty in cells:
            rows.setdefault(ty, []).append(tx)
        for ty, txs in sorted(rows.items()):
            txs.sort()
            start = prev = txs[0]
            for tx in txs[1:] + [None]:
                if tx is not None and tx == prev + 1:
                    prev = tx
                    continue
                self.b.write_block(base + ty * 64 + start, bytes([tile_type]) * (prev - start + 1))
                if tx is not None:
                    start = prev = tx
        ys = sorted(rows)
        xs = sorted({tx for txs in rows.values() for tx in txs})
        self.fixture(f'room ${self.r16(ROOM):02X} collision ${base:06X} {len(list(cells))} cells '
                     f'(rows {ys[0]}-{ys[-1]}, cols {xs[0]}-{xs[-1]}) = ${tile_type:02X} ({why})')

    def expect_ram(self, addr, value, name=None, width=1):
        observed = self.r16(addr) if width == 2 else self.r(addr)
        return self.check(name or f'${addr:06X} == {value:#x}', observed, value)

    # -- input ---------------------------------------------------------------
    def press(self, button, frames=4):
        if not self.b.press_button(button, frames=frames):
            raise RuntimeError(f'press failed: {button}')
        time.sleep((frames + 6) / 60)

    def guard(self):
        """Re-assert the no-damage flag before an input leg (declared on first use).
        A scenario that tests damage sets `t.invincible = False`."""
        if not self.invincible:
            return
        if not self._guard_declared:
            self.fixture(f'no-damage ${NO_DAMAGE:06X}=1 before each input leg')
            self._guard_declared = True
        self.w(NO_DAMAGE, 1)

    def wait_play(self, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            if self.r(MODULE) in PLAY_MODULES and self.r(SUBMODULE) == 0:
                time.sleep(0.3)
                if self.r(MODULE) in PLAY_MODULES and self.r(SUBMODULE) == 0:
                    return True
            time.sleep(0.1)
        return False

    def link(self):
        return [self.r16(LINK_X), self.r16(LINK_Y)]

    def tiles(self):
        """Current room's collision map (DungeonTiles)."""
        return DungeonTiles.read(self)

    def room(self):
        return self.r16(ROOM)

    def sprites(self):
        out = []
        for i in range(16):
            if self.r(0x7E0DD0 + i) >= 9:
                out.append({'slot': i, 'id': f'{self.r(0x7E0E20 + i):02X}',
                            'x': self.r(0x7E0D10 + i) | self.r(0x7E0D30 + i) << 8,
                            'y': self.r(0x7E0D00 + i) | self.r(0x7E0D20 + i) << 8})
        return out

    def clear_enemies(self):
        """Declared fixture: deactivate the room's active sprites ($0DD0,X = 0)."""
        gone = self.sprites()
        for s in gone:
            self.w(0x7E0DD0 + s['slot'], 0)
        if gone:
            self.fixture(f'room ${self.room():02X}: enemies deactivated ($0DD0,X=0) '
                         f'{[(s["slot"], s["id"]) for s in gone]}')

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
                 'room': self.room(), 'down_moved_px': moved, 'cpu': cpu}
        self.event(f'alive check: {label}', **state)
        return state['frame_advanced'] and state['module'] in PLAY_MODULES and moved > 0

    # -- movement ------------------------------------------------------------
    def warp(self, entrance, room=None, label=''):
        """Declared fixture: OracleCheats.warp_entrance, then wait for play (and `room`)."""
        res = self._cheats(self.b).warp_entrance(entrance)
        self.fixture(f'warp_entrance 0x{entrance:02X}' + (f' ({label})' if label else ''))
        self.event('warp entrance', response=res, dungeon=self.r(DUNGEON))
        if not self.wait_play(10) or (room is not None and self.room() != room):
            raise ScenarioError(f'warp 0x{entrance:02X} landed in room ${self.room():04X}')

    def warp_area(self, area, label=''):
        res = self._cheats(self.b).warp_area(area)
        self.fixture(f'warp_area 0x{area:02X}' + (f' ({label})' if label else ''))
        self.event('warp area', response=res)
        if not self.wait_play(10):
            raise ScenarioError(f'warp_area 0x{area:02X} did not reach play')

    def walk_to(self, tx, ty):
        """Controller input only, straight line: y then x, stopping when Link no longer moves."""
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

    def travel(self, goal, bounds, nearest=False, slack=6):
        """Route over the room's collision map (DungeonTiles BFS), then walk each leg."""
        here = tuple(self.link())
        path = DungeonTiles.read(self).route(here, goal, bounds, nearest=nearest)
        if not path:
            raise ScenarioError(f'no route from {here} to {goal}')
        self.event('route', goal=list(goal), waypoints=path)
        for x, y in path[1:]:
            self.guard()
            at = self.walk_to(x, y)
            if abs(at[0] - x) > slack or abs(at[1] - y) > slack:
                raise ScenarioError(f'walk stalled at {at} heading to {(x, y)}')
        self.event('walked (controller)', goal=list(goal), at=self.link())
        return self.link()

    def through_door(self, button, room, hold=24, tries=8):
        """Hold a direction until the room changes to `room` (controller)."""
        for _ in range(tries):
            self.guard()
            self.press(button, hold)
            self.wait_play(6)
            if self.room() == room:
                time.sleep(0.4)
                self.event(f'entered room ${room:02X} (controller)', at=self.link())
                return
        raise ScenarioError(f'could not enter room ${room:02X}; in ${self.room():04X} at {self.link()}')

    # -- breakpoints ---------------------------------------------------------
    def is_paused(self):
        res = self.b.send_command('STATE')
        data = res.get('data', {}) if isinstance(res, dict) else {}
        return bool(isinstance(data, dict) and data.get('paused'))

    def arm(self, breakpoints, log=True):
        """Exec breakpoints {addr: label}."""
        for addr, label in breakpoints.items():
            self.bp_ids[addr] = self.b.add_breakpoint(addr, 'exec')
            self.bp_labels[addr] = label
        if log:
            self.event('breakpoints armed', ids={f'${a:06X}': i for a, i in self.bp_ids.items()})

    def disarm(self):
        for addr in list(self.bp_ids):
            self.b.remove_breakpoint(self.bp_ids.pop(addr))
        if self.is_paused():
            self.b.resume()

    def collect_breaks(self, hits, timeout=0.6, watch=None, limit=12, keep=None, stop=None):
        """While armed: record each break (PC, registers, top of stack, `watch` state), resume.
        A breakpoint is dropped after its first hit, or after keep[addr] hits. `watch` is
        {name: addr} or a function t -> dict. `stop()` returning true ends collection."""
        end = time.time() + timeout
        while time.time() < end and len(hits) < limit:
            if stop and stop():
                break
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
            exact = full in self.bp_labels
            state = watch(self) if callable(watch) else {n: self.r(a) for n, a in (watch or {}).items()}
            hits.append({'pc': f'${full:06X}', 'exact': exact,
                         'label': self.bp_labels[full] if exact else
                         'operand fetch of ' + ', '.join(f'${a:06X}' for a in armed),
                         'cpu': cpu, 'stack_top': stack, **state})
            if exact:
                done = sum(h['pc'] == f'${full:06X}' for h in hits) >= (keep or {}).get(full, 1)
                drop = [full] if done else []
            else:
                drop = armed
            for a in drop:
                if self.bp_ids.get(a, -1) >= 0:
                    self.b.remove_breakpoint(self.bp_ids.pop(a))
            self.b.resume()
            end = time.time() + timeout
        return hits

    def breaks(self, breakpoints, timeout=0.6, **kw):
        """Arm, collect for `timeout` s of quiet (collect_breaks options), disarm. Returns hits."""
        self.arm(breakpoints, log=False)
        try:
            return self.collect_breaks([], timeout=timeout, **kw)
        finally:
            self.disarm()

    def record_breaks(self, breakpoints, presses, label, frames=16, stop_after=None, watch=None):
        """Arm `breakpoints`, press each button of `presses` (held `frames`) while recording
        exact-PC hits, then disarm. Each breakpoint records its first hit only."""
        self.arm(breakpoints)
        hits = []
        for button in presses:
            self.guard()
            self.b.press_button(button, frames=frames)
            self.collect_breaks(hits, timeout=0.6, watch=watch)
            if stop_after and len(hits) >= stop_after:
                break
        self.collect_breaks(hits, timeout=1.0, watch=watch)
        self.disarm()
        self.result.setdefault('breakpoint_hits', {})[label] = hits
        self.event(f'{label} (controller)', hits=[h['pc'] + ' ' + h['label'] for h in hits])
        return hits

    @staticmethod
    def hit(hits, addr):
        return any(h['pc'] == f'${addr:06X}' and h['exact'] for h in hits)

    def expect_breakpoint(self, hits, addr, name=None, expected=True):
        return self.check(name or f'${addr:06X} hit', self.hit(hits, addr), expected)

    # -- lifecycle -----------------------------------------------------------
    def _preflight(self):
        self.rom = self.out / f'{self.tag}.sfc'
        shutil.copy2(self.src_rom, self.rom)
        self.home = self.out / 'profile'
        (self.home / 'Saves').mkdir(parents=True)
        shutil.copy2(self.src_srm, self.home / 'Saves' / f'{self.tag}.srm')
        self.result['rom'] = {'source': str(self.src_rom), 'sha256': sha(self.rom)}
        self.result['srm'] = {'source': str(self.src_srm), 'sha256': sha(self.src_srm)}
        self.result['app'] = str(self.app)
        self.fixture(f'SRAM {self.src_srm.name}, file {self.file_slot}')
        self.persist()

    def _launch(self):
        bridge, self._cheats = _bridge_classes()
        cmd = ['taskpolicy', '-b', 'nice', '-n', '10', 'bash', str(LAUNCHER), '--headless',
               '--no-copy-settings', '--no-save-settings', '--no-seed-project-states', '--no-state-set',
               '--no-register', '--instance', self.name, '--home', str(self.home), '--socket', str(self.sock),
               '--rom', str(self.rom), '--app', str(self.app)]
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
        self.b = bridge(str(self.sock))
        self.result['emulator'] = {'pid': self.pid, 'socket': str(self.sock), 'rom_info': self.b.get_rom_info()}
        self.persist()

    def _load_file(self):
        """Title -> file select -> file `file_slot` -> play, by controller input."""
        time.sleep(5)
        for _ in range(20):
            if self.r(MODULE) == 1:
                break
            self.press('start', 6)
            time.sleep(0.7)
        for _ in range(4):
            if self.r(FILE_CURSOR) == self.file_slot - 1:
                break
            self.press('down', 4)
            time.sleep(0.4)
        for _ in range(30):
            if self.r(MODULE) in PLAY_MODULES and self.r(SUBMODULE) == 0:
                break
            self.press('start', 8)
            time.sleep(0.6)
        if not self.wait_play():
            raise RuntimeError(f'file {self.file_slot} did not reach play')
        self.event(f'file {self.file_slot} loaded (controller)', module=self.r(MODULE), room=self.room())

    def close(self):
        if self.pid and identity(self.pid) == self.pid_identity:
            os.kill(self.pid, signal.SIGTERM)
            for _ in range(50):
                if identity(self.pid) != self.pid_identity:
                    self.result['emulator']['exited'] = True
                    break
                time.sleep(0.1)
        self.persist()

    def boot(self):
        self._preflight()
        self._launch()
        self._load_file()

    def execute(self, fn, case):
        """Boot, run fn(self, case), always stop the owned emulator. Returns the result dict."""
        try:
            self.boot()
            fn(self, case)
            self.result['state'] = 'finished'
        except Exception as exc:  # noqa: BLE001
            self.result['state'] = 'error'
            self.result['error'] = f'{type(exc).__name__}: {exc}'
            print('ERROR', self.result['error'], flush=True)
            try:
                self.screenshot('error')
                self.result['error_context'] = {'module': self.r(MODULE), 'room': self.room(),
                                                'link': self.link(), 'cpu': self.b.get_cpu_state()}
            except Exception:  # noqa: BLE001
                pass
        finally:
            if self.b:
                try:
                    self.disarm()
                except Exception:  # noqa: BLE001
                    pass
            self.close()
        failed = [c['name'] for c in self.result['checks'] if not c['matches_expectation']]
        self.result['passed'] = self.result['state'] == 'finished' and not failed
        self.persist()
        print(json.dumps({'out': str(self.out), 'state': self.result['state'], 'failed': failed}), flush=True)
        return self.result
