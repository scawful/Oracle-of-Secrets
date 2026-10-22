#!/usr/bin/env python3
"""Explicit attach-only qualification for the ordinary native37/A1 image.

Root owns the heavy lane, cold boot, copied SRM, process lifetime and reopen.
This runner never launches/stops/resets an emulator, loads a savestate, sets PC,
or writes ROM/terrain/VRAM/CGRAM. --describe needs no files or live endpoint.
Live fixture operations require --execute-fixtures and explicit owner binding.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
CLIENT = Path('/Users/scawful/src/hobby/mesen2-oos/tools/oos_client')
SEED_SHA = 'f35b2cd4ecd010341ef8d02f089816044d11c68df01bda092e8ac02974d7f283'
HELPERS = ('FullHigh', 'FullLow', 'SubHigh', 'SubLow')
HOOKS = dict(zip(HELPERS, (0x02F59D, 0x02F5C8, 0x02F7E3, 0x02F80E)))
CASES = ('inspect', 'boot-file2', 'native37', 'a1-full', 'a1-sub-overlay',
         'route37', 'route-a1', 'legacy33', 'save-continue', 'reopen-check')
TAIL = {0x7EF4C5: 0x20, 0x7EF4DF: 0x40}
STORY = (0x3C5, 0x3C6, 0x3D6, 0x3D7, 0x37A, 0x374)
RAW_FULL_DONE = 0x02EECA  # JSR02F54A returned; native event overlays have not run.
RAW_FULL_GUARDS = (
    (0x02EEC5, 11, '0b338a3f13313fe4f6eb1dc9f7773321239ff710037f17e646412574000de5c0'),
    (0x02F54A, 83, 'd709aee8d1fe116fbbe08a41605a73e5dd9243defc827ab666ebe6cc654bd91f'),
    (0x02F5EA, 78, 'f8a647bbd7bf52dff59e190a5dcefdf750816d3d7b2c9ac356382359f70df00d'),
    (0x02F691, 314, '514148e9f9d46b6539f8de1673e95b4e5cd1b708f9f76a6fd5637e2a1f9f9dfb'),
)
ROUTES = {
    0x37: dict(grid_sha256='1940509bac037818464a357bf5c56077ae82603c512428b5fc03ef224e23f1a0',
               origin=(0xE00, 0xC00), start=(0xF00, 0xC38), walk_frames=8,
               dry=(32, 8, 35, 9), wall=(36, 8, 37, 9),
               dry_chr=(163, 162, 163, 162, 162, 163, 162, 163),
               dry_attrs=(0,) * 8,
               wall_chr=(99, 100, 71, 72)),
    0xA1: dict(grid_sha256='f07de0516711f9be4fcb3de919276d9886f1591acbeedef32e344c4fef25eb88',
               origin=(0x200, 0x800), start=(0x2C4, 0x8FC), walk_frames=12,
               dry=(24, 32, 28, 34), wall=(29, 32, 29, 34),
               dry_chr=(160, 160, 160, 160, 55, 160, 160, 160, 160, 6, 160, 160, 160, 160, 22),
               dry_attrs=(0x48, 0x48, 0x48, 0x48, 0, 0x48, 0x48, 0x48, 0x48, 0, 0x48, 0x48, 0x48, 0x48, 0),
               wall_chr=(35, 51, 0)),
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(data, algorithm='sha256'):
    return hashlib.new(algorithm, data).hexdigest()


def number(value):
    if isinstance(value, int):
        return value
    value = str(value).replace('$', '0x').replace(':', '')
    return int(value, 16) if not value.isdigit() or value.startswith('0x') else int(value)


def pc(address):
    require(address & 0x8000 and address >> 16 not in (0x7E, 0x7F), 'Invalid LoROM address')
    return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)


def symbols(text):
    """Only WLA labels; identical bridge aliases agree, conflicting ones refuse."""
    out, section = {}, None
    for line in text.splitlines():
        if line.startswith('['):
            section = line.strip()
        if section != '[labels]':
            continue
        m = re.fullmatch(r'([\da-fA-F]{2}):([\da-fA-F]{4})\s+(\S+)', line.strip())
        if m:
            name = m[3].removeprefix('Oracle_')
            if name.startswith('Lyra_'):
                address = int(m[1] + m[2], 16)
                require(name not in out or out[name] == address, f'Conflicting required label: {name}')
                out[name] = address
    return out


def candidate(rom, sym):
    require(len(rom) == 0x400000, 'Ordinary qualification requires the exact composed4MiB image')
    labels = symbols(sym.decode())
    for name in HELPERS:
        target = labels.get('Lyra_' + name)
        require(target is not None, f'Missing paired helper label: {name}')
        require(rom[pc(HOOKS[name]):pc(HOOKS[name]) + 4] == b'\x22' + target.to_bytes(3, 'little'),
                f'Actual native ingress does not call {name}')
        require(rom[pc(HOOKS[name]) + 4:pc(HOOKS[name]) + 12] == b'\xEA' * 8,
                f'Native {name} return span differs')
        returned = labels.get('Lyra_Fixture_' + name + 'Returned')
        require(returned == HOOKS[name] + 4, f'Unreviewed {name} returned label')
    for name in ('Lyra_Fixture_PreProfile', 'Lyra_Fixture_PreOverlaySelect'):
        require(name in labels, f'Missing native fixture boundary: {name}')
    require(labels['Lyra_Fixture_PreProfile'] == 0x02E58B, 'Unreviewed pre-profile fixture entry')
    require(rom[pc(0x02E58B):pc(0x02E58B) + 7] == bytes.fromhex('a9f8ff85ece230'),
            'Native pre-profile ABI differs')
    at = pc(labels['Lyra_Fixture_PreOverlaySelect'])
    require(rom[at:at + 3] == bytes.fromhex('e0ff00'), 'Pre-overlay boundary is not the M16 CPX#00FF')
    require(labels.get('Lyra_A1Descriptor') == 0xF8DFC0
            and rom[0x3C5FC0:0x3C5FCC] == b'LYR1\x01\xA1\x00\xA1' + b'\xA1' * 4,
            'Ordinary isolated A1 descriptor differs')
    require(rom[pc(0x008051):pc(0x008051) + 16] == bytes.fromhex('e61a201e8422b5800020fc85641280d3'),
            'Native pre-dispatch fixture boundary differs')
    for address, size, expected in RAW_FULL_GUARDS:
        require(digest(rom[pc(address):pc(address) + size]) == expected,
                f'Native full-decode completion/ABI differs at{address:06X}')
    sys.path.insert(0, str(REPO / 'Scripts/Build'))
    import lyra_project_admission as A
    import lyra_native_streams as N
    definitions = [A.read_tile32(rom, i) for i in range(0x4540)]
    return labels, A, N, definitions


def process_identity(pid):
    r = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'lstart=,comm='],
                       capture_output=True, text=True, check=False)
    require(r.returncode == 0 and r.stdout.strip(), 'Owned emulator PID is absent')
    return r.stdout.strip()


def checksum(block):
    return len(block) == 0x500 and sum(struct.unpack('<640H', block)) & 0xFFFF == 0x5A5A


class Runner:
    def __init__(self, args, bridge, rom, labels, decoder, streams, definitions):
        self.a, self.b, self.rom, self.labels = args, bridge, rom, labels
        self.decoder, self.streams, self.definitions = decoder, streams, definitions
        self.breakpoints = set()
        self.deadline = time.monotonic() + args.seconds
        self.pid_identity = process_identity(args.pid)
        self.report = dict(kind='lyra.ordinary_attach_native.v1', case=args.case,
                           passed=False, checks=[], writes=[], observations=[], cleanup_errors=[],
                           fixtures=[], source_sha256=digest(Path(__file__).read_bytes()),
                           rom_sha256=digest(rom), rom_sha1=digest(rom, 'sha1'),
                           symbols_sha256=digest(args.symbols.read_bytes()),
                           pid=args.pid, process_identity=self.pid_identity,
                           socket=args.socket, native_runtime_admission=False,
                           save_exit_destination_selected=False)
        self.dependencies = {p: digest(p.read_bytes()) for p in (
            REPO / 'Scripts/Build/lyra_project_admission.py', REPO / 'Scripts/Build/lyra_native_streams.py')}
        self.report['decoder_source_pins'] = {str(p): h for p, h in self.dependencies.items()}
        self.owned = False
        self.cleaning = False
        self.last_owner_check, self.last_info = 0.0, None

    def check_owner(self, force=False):
        require(self.cleaning or time.monotonic() < self.deadline, 'Bounded runner deadline exceeded')
        if not force and self.last_info is not None and time.monotonic() - self.last_owner_check < .25:
            return self.last_info
        require(process_identity(self.a.pid) == self.pid_identity, 'Owned PID identity changed')
        status = json.loads(self.a.status_file.read_text())
        require(status.get('pid') == self.a.pid and status.get('socketPath') == self.a.socket,
                'Explicit status/PID/socket binding changed')
        text = self.a.owner_file.read_text()
        try:
            owner = json.loads(text)['owner']
        except (ValueError, KeyError, TypeError):
            owner = next((s.split('=', 1)[1] for s in text.splitlines() if s.startswith('owner=')), text.strip())
        require(owner == self.a.owner, 'Heavy lane owner changed')
        info = self.b.get_rom_info()
        require(str(info.get('sha1', '')).lower() == digest(self.rom, 'sha1'), 'Loaded ROM SHA1 differs')
        self.last_owner_check, self.last_info = time.monotonic(), info
        return info

    def cmd(self, kind, **params):
        self.check_owner(force=kind not in ('STATE', 'SCREENSHOT', 'CAPABILITIES'))
        reply = self.b.send_command(kind, {k: str(v) for k, v in params.items()})
        require(reply.get('success'), f'{kind} refused: {reply.get("error", reply)}')
        return reply.get('data')

    def state(self):
        value = self.cmd('STATE')
        return json.loads(value) if isinstance(value, str) else value

    def paused(self):
        require(self.state().get('paused') is True, 'Root must supply a paused private emulator')

    def read(self, address, size, memtype='SnesMemory'):
        self.check_owner()
        data = bytes(self.b.read_block(address, size, memtype=memtype))
        require(len(data) == size, f'Short native read: {address:06X}/{size}')
        return data

    def value(self, address, size=1):
        return int.from_bytes(self.read(address, size), 'little')

    def cpu(self):
        self.check_owner()
        state = self.b.get_cpu_state()
        require(state and 'pc' in state and 'sp' in state, 'CPU state unavailable')
        return state

    def record(self, name, **evidence):
        self.report['checks'].append(dict(name=name, passed=True, **evidence))

    def input(self, buttons=''):
        self.cmd('INPUT', buttons=buttons, frames=0, player=0)

    def frames(self, count, buttons=''):
        require(1 <= count <= 120, 'Frame batch must be1..120')
        self.paused()
        self.input(buttons)
        before = number(self.state()['frame'])
        try:
            self.cmd('FRAME', count=count)
            until = min(self.deadline, time.monotonic() + 8)
            while time.monotonic() < until:
                state = self.state()
                after = number(state['frame'])
                if state.get('paused') and after >= before + count:
                    require(after <= before + count + 1, 'Unexpected frame overshoot')
                    self.report['observations'].append(dict(frames=count, before=before, after=after, buttons=buttons))
                    return
                time.sleep(.01)
            raise RuntimeError('Native FRAME completion timeout')
        finally:
            self.input('')

    def run_to(self, address):
        self.paused()
        self.check_owner(force=True)
        ident = self.b.add_breakpoint(address)
        require(type(ident) is int and ident >= 0, 'Owned breakpoint could not be installed')
        self.breakpoints.add(ident)
        try:
            started = time.monotonic()
            first = self.state()
            start_frame = number(first['frame'])
            progress = dict(kind='live_hook_wait', address=f'{address:06X}', start_frame=start_frame,
                            start_module=list(self.read(0x7E0010, 2)), outcome='waiting')
            self.report['observations'].append(progress)
            require(self.b.resume(), 'Native resume refused')
            until = min(self.deadline - 2, started + 30)  # Reserve owned pause acknowledgement time.
            last = first
            reason = 'wall_timeout'
            while time.monotonic() < until:
                last = self.state()
                elapsed_frames = number(last['frame']) - start_frame
                require(elapsed_frames >= 0, 'Native frame counter moved backwards')
                # CPU reads request GetDebugger(true); never use one to poll a
                # running emulator, because that would pause the native run.
                if last.get('paused') and elapsed_frames <= 240:
                    cpu = self.cpu()
                    if number(cpu['pc']) == address:
                        progress.update(outcome='hit', end_frame=number(last['frame']),
                                        end_module=list(self.read(0x7E0010, 2)),
                                        elapsed_frames=elapsed_frames, elapsed_seconds=time.monotonic() - started)
                        return cpu
                if elapsed_frames >= 240:
                    reason = 'native_frame_limit'
                    break
                time.sleep(.01)
            if time.monotonic() >= self.deadline - 2:
                reason = 'case_deadline'
            self.cleaning = True
            self.check_owner(force=True)
            require(self.b.pause(), 'Native hook timeout pause refused')
            pause_until = min(self.deadline, time.monotonic() + 2)
            while time.monotonic() < pause_until:
                last = self.state()
                if last.get('paused'):
                    cpu = self.cpu()
                    progress.update(outcome='timeout', reason=reason, end_frame=number(last['frame']),
                                    end_module=list(self.read(0x7E0010, 2)),
                                    elapsed_frames=number(last['frame']) - start_frame,
                                    elapsed_seconds=time.monotonic() - started, cpu=cpu)
                    raise RuntimeError(f'Live hook timeout: {address:06X}; reason={reason}; CPU={cpu}')
                time.sleep(.01)
            progress.update(outcome='pause_timeout', reason=reason, end_frame=number(last['frame']),
                            end_module=list(self.read(0x7E0010, 2)),
                            elapsed_frames=number(last['frame']) - start_frame,
                            elapsed_seconds=time.monotonic() - started)
            raise RuntimeError(f'Live hook timeout: {address:06X}; pause was not confirmed')
        finally:
            self.cleaning = True
            self.check_owner(force=True)
            require(self.b.remove_breakpoint(ident), 'Owned breakpoint removal failed')
            self.breakpoints.remove(ident)
            self.cleaning = False

    def write(self, address, value, width, reason):
        # Closed one-time setup fields only; no map buffers, graphics or code.
        words = {0x20, 0x22, 0x8A, 0xA0, 0xE0, 0xE2, 0xE6, 0xE8, 0x11E, 0x120,
                 0x122, 0x124, 0x40A, 0x618, 0x61A, 0x61C, 0x61E}
        singles = {0x10, 0x11, 0x13, 0x9B, 0xB0, 0x10A, 0x4AA, 0xFFF}
        allowed = (width == 2 and address - 0x7E0000 in words) or (
            width == 1 and (address - 0x7E0000 in singles or address in (0x7EF3CA, *TAIL, 0x7EF36D, 0x7E0373)))
        require(allowed and self.a.execute_fixtures, f'Forbidden fixture write: {address:06X}/{width}')
        self.paused()
        self.check_owner(force=True)
        before = self.read(address, width)
        for i, byte in enumerate(value.to_bytes(width, 'little')):
            require(self.b.write_memory(address + i, byte), 'Fixture byte write refused')
        require(self.value(address, width) == value, 'Fixture readback differs')
        self.report['writes'].append(dict(address=f'{address:06X}', width=width,
                                          before=before.hex(), value=value, reason=reason))

    def warp_setup(self, area):
        require(area in (0x36, 0x33), 'Only existing native36 and legacy33 warps are allowed')
        self.paused()
        from mesen2_client_lib.oracle_cheats import OracleCheats, hexint
        cheats = OracleCheats(self.b, root=REPO)
        row = next((r for r in cheats.warps['areas'] if hexint(r['area']) == area), None)
        require(row is not None, 'Native warp metadata missing')
        room = hexint(row['via_room'])
        require(not cheats._uses_cached_exit(room) and cheats._exit_area(room) == area,
                'Live native exit does not match existing warp metadata')
        require(self.value(0x7E0010) in (7, 9, 0x0B) and self.value(0x7E0011) == 0,
                'Native warp requires idle play')
        self.write(0x7E0013, 0x80, 1, 'declared native force-blank shadow')
        self.write(0x7E009B, 0, 1, 'declared native HDMA blanking shadow')
        self.frames(1)
        for address, value, width in ((0x7EF3CA, 0, 1), (0x7E0FFF, 0, 1),
                                     (0x7E00A0, room, 2), (0x7E010A, 0, 1),
                                     (0x7E04AA, 0, 1), (0x7E0011, 0, 1),
                                     (0x7E00B0, 0, 1), (0x7E0010, 8, 1)):
            self.write(address, value, width, f'declared existing area{area:02X} native Module08 bootstrap')
        self.report['fixtures'].append(dict(native_area=area, room=room, exit_index=row.get('exit_index')))

    def capture(self, name):
        self.paused()
        low = self.read(0x7E0000, 0x800)
        blobs = {'wram': low, 'field': self.read(0x7E2000, 8192),
                 'overlay': self.read(0x7E4000, 4096),
                 'vram': self.read(0, 32768, 'VRAM'), 'cgram': self.read(0, 512, 'CGRAM'),
                 'oam': self.read(0, 544, 'OAM')}
        self.check_owner()
        shot = self.b.screenshot()
        require(isinstance(shot, bytes) and shot.startswith(b'\x89PNG'), 'Native screenshot missing')
        blobs['png'] = shot
        for suffix, blob in blobs.items():
            (self.a.proof_dir / f'{name}.{suffix}').write_bytes(blob)
        evidence = dict(name=name, cpu=self.cpu(), module=list(low[0x10:0x12]),
                        area=int.from_bytes(low[0x8A:0x8C], 'little'),
                        full_map=int.from_bytes(low[0x40A:0x40C], 'little'),
                        x=int.from_bytes(low[0x22:0x24], 'little'),
                        y=int.from_bytes(low[0x20:0x22], 'little'), hp=self.value(0x7EF36D),
                        hashes={k: digest(v) for k, v in blobs.items()})
        self.report['observations'].append(evidence)
        return blobs, evidence

    def expected(self, area):
        tables = self.streams.POINTER_TABLES
        if area == 0xA1:
            # Ordinary A1 is read from the new192-row tables, never the old160-row tail.
            tables = tuple(self.decoder.snes(self.decoder.TABLE_START + next(
                row[6] for row in self.decoder.SPECS if row[0] == key))
                for key in ('map32_high', 'map32_low'))
        planes = [self.streams._plane(self.rom, area, t) for t in tables]
        grid = self.streams._native_grid([p[0] for p in planes], self.definitions)
        return b''.join(struct.pack('<32H', *row) for row in grid), planes

    def route_binding(self, area):
        route = ROUTES[area]
        raw = self.expected(area)[0]
        require(digest(raw) == route['grid_sha256'], 'Reviewed route grid differs from candidate')
        # Bind the actual Link reader, including its relocated atlas and low9 mask.
        require(self.rom[pc(0x008864):pc(0x008872)] == bytes.fromhex('bf0080bd850629ff01aabf59940e'),
                'Reviewed relocated collision reader differs')
        for attr, handler in ((0, 0xDE5B), (1, 0xDC50), (2, 0xDC50), (3, 0xDC50), (0x48, 0xDE67)):
            require(struct.unpack_from('<H', self.rom, pc(0x07DA2A) + attr * 2)[0] == handler,
                    'Reviewed dry/solid collision dispatch differs')
        grid = struct.unpack('<1024H', raw)
        groups = {}
        for name in ('dry', 'wall'):
            left, top, right, bottom = route[name]
            rows = []
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    tile = grid[y // 2 * 32 + x // 2]
                    quadrant = y % 2 * 2 + x % 2
                    chr_id = struct.unpack_from('<H', self.rom, 0x1E8000 + tile * 8 + quadrant * 2)[0] & 0x1FF
                    attr = self.rom[0x71459 + chr_id]
                    require(attr in ((0, 0x48) if name == 'dry' else (1, 2, 3)),
                            'Reviewed dry/solid quarter attribute differs')
                    rows.append(dict(cell8=[x, y], tile16=tile, quadrant=quadrant, chr_id=chr_id, attribute=attr))
            require(tuple(r['chr_id'] for r in rows) == route[name + '_chr'],
                    'Reviewed dry/solid quarter CHR differs')
            require(tuple(r['attribute'] for r in rows) == (
                route['dry_attrs'] if name == 'dry' else (1,) * len(rows)),
                    'Reviewed dry/solid exact quarter attributes differ')
            groups[name] = rows
        return dict(area=area, **route, quarters=groups)

    def route_case(self, area):
        binding = self.route_binding(area)
        parent, quadrant = (0x36, 1) if area == 0x37 else (0xA1, 0)
        require(self.value(0x7E040A, 2) == parent, 'Route requires its completed native full load')
        field = self.read(0x7E2000, 8192)
        actual = b''.join(field[y * 128 + quadrant * 64:y * 128 + quadrant * 64 + 64] for y in range(32))
        require(actual == self.expected(area)[0], 'Live route quadrant differs before position fixture')
        self.route_position(parent)
        before_cpu = self.cpu()
        original_xy = (self.value(0x7E0022, 2), self.value(0x7E0020, 2))
        for address, value in ((0x7E0022, binding['start'][0]), (0x7E0020, binding['start'][1])):
            self.write(address, value, 2, f'one-time same-loaded-map route{area:02X} Link position fixture')
        require(self.cpu() == before_cpu, 'Route RAM fixture changed CPU state')
        self.report['fixtures'].append(dict(kind='same_loaded_map_route_xy_only', binding=binding))
        self.frames(6)
        start = self.route_position(parent)
        require(abs(start[0] - binding['start'][0]) <= 2 and abs(start[1] - binding['start'][1]) <= 2,
                'Neutral route setup moved outside its reviewed start')
        self.capture(f'route{area:02X}-start')
        self.link_collision('Right', binding['dry_chr'], (0, 0x48))
        wall_x = binding['origin'][0] + binding['wall'][0] * 8
        trace = []
        self.report['observations'].append(dict(kind='route_controller_trace', area=area, trace=trace))

        def step(button):
            self.frames(1, button)
            point = (self.value(0x7E0022, 2), self.value(0x7E0020, 2), self.value(0x7EF36D))
            trace.append(dict(button=button, xyhp=point))
            self.route_position(parent)
            require(abs(point[1] - start[1]) <= 2 and point[2] == start[2],
                    'Route drifted vertically or native damage occurred')
            require(point[0] + 8 < wall_x, 'Link center crossed the reviewed solid boundary')
            return point

        for _ in range(binding['walk_frames']):
            dry = step('Right')
        require(dry[0] - start[0] >= 8, 'Controller did not walk at least8pixels on reviewed dry terrain')
        window = []
        for _ in range(32):
            blocked = step('Right')
            window = (window + [blocked])[-12:]
            held = (len(window) == 12 and max(p[0] for p in window) - min(p[0] for p in window) <= 1
                    and len({p[1] for p in window}) == 1)
            if held:
                break
        require(held, 'Right input did not reach12blocked frames in a1pixel band within32frames')
        self.link_collision('Right', binding['wall_chr'], (1, 2, 3), attempts=8)
        wall_sample = self.route_position(parent)
        require(min(p[0] for p in window) <= wall_sample[0] <= max(p[0] for p in window)
                and wall_sample[1:] == blocked[1:] and wall_sample[0] + 8 < wall_x,
                'Wall lookup moved outside the established blocked band')
        self.capture(f'route{area:02X}-blocked')
        for _ in range(8):
            escaped = step('Left')
        require(blocked[0] - escaped[0] >= 6, 'Left escape did not move at least6pixels after blocked Right')
        self.capture(f'route{area:02X}-escaped')
        self.record('reviewed dry walk, solid hold and escape', area=area, start=start, dry=dry,
                    blocked=blocked, escaped=escaped, blocked_frames=len(window), trace=trace,
                    blocked_x_band=[min(p[0] for p in window), max(p[0] for p in window)],
                    exact_body_stop_calibrated=False, qualification='bounded controller fixture; not natural route acceptance')
        self.input('')
        self.run_to(0x008056)
        for address, value in ((0x7E0022, original_xy[0]), (0x7E0020, original_xy[1])):
            self.write(address, value, 2, 'restore completed XY-only route fixture before the next native transition')
        self.record('route fixture position restored', xy=list(original_xy), boundary='008056')

    def route_position(self, parent):
        expected_module = 0x0B if parent == 0xA1 else 9
        require(self.value(0x7E0010) == expected_module and self.value(0x7E0011) == 0
                and self.value(0x7E040A, 2) == parent, 'Route left its native idle overworld module')
        return (self.value(0x7E0022, 2), self.value(0x7E0020, 2), self.value(0x7EF36D))

    def hooks(self, requested, effective, sub=False):
        for name, plane in zip(('SubHigh', 'SubLow') if sub else ('FullHigh', 'FullLow'), (0, 1)):
            entry = self.run_to(HOOKS[name])
            require(number(entry['x']) == requested * 3, f'{name} caller did not select requested map')
            require(number(entry['p']) & 0x30 == 0 and number(entry['d']) == 0,
                    f'{name} caller width/direct-page differs')
            done = self.run_to(self.labels['Lyra_Fixture_' + name + 'Returned'])
            pointer = self.value(0x7E00C8, 3)
            expected_pointer = self.expected(effective)[1][plane][1]
            require(pointer == expected_pointer, f'{name} did not bind the actual selected stream')
            require(all(number(done[k]) == number(entry[k]) for k in ('sp', 'x', 'y', 'd', 'dbr'))
                    and number(done['p']) & 0x7D == number(entry['p']) & 0x7D,
                    f'{name} caller ABI did not survive the actual JSL/RTL')
            require(number(done['a']) == pointer >> 8, f'{name} returned A differs from second pointer word')
            self.record(name, requested=requested, effective=effective, entry=entry, done=done,
                        pointer=f'{pointer:06X}')

    def full_case(self, area):
        self.warp_setup(0x36 if area == 0xA1 else area)
        if area == 0xA1:
            self.a1_fixture()
        targets = (area, area + 1, area + 8, area + 9)
        for target in targets:
            self.hooks(target, 0xA1 if area == 0xA1 else target)
        done = self.run_to(RAW_FULL_DONE)
        require(number(done['p']) & 0x30 == 0 and number(done['d']) == 0,
                'Native raw full-decode return ABI differs')
        blobs, _ = self.capture(f'native{area:02X}-decoded')
        for index, target in enumerate(targets):
            y0, x0 = divmod(index, 2)
            actual = b''.join(blobs['field'][(y0 * 32 + y) * 128 + x0 * 64:
                                           (y0 * 32 + y) * 128 + x0 * 64 + 64] for y in range(32))
            require(actual == self.expected(0xA1 if area == 0xA1 else target)[0],
                    f'Native quadrant{target:02X} differs from candidate')
            self.record('native raw decoded field quadrant', map_id=target, sha256=digest(actual),
                        boundary=f'{RAW_FULL_DONE:06X}', before_event_overlays=True)
        self.wait_play()
        settled, _ = self.capture(f'native{area:02X}-loaded')
        require(self.value(0x7E008A, 2) == self.value(0x7E040A, 2) == area,
                'Settled native full map identity differs')
        changes = [dict(x=i % 64, y=i // 64, decoded=a, settled=b)
                   for i, (a, b) in enumerate(zip(struct.unpack('<4096H', blobs['field']),
                                                 struct.unpack('<4096H', settled['field']))) if a != b]
        self.record('native post-decode world-state field changes', changes=changes,
                    qualification='reported separately from strict pre-overlay decoder comparison')
        if area == 0x36:
            expected_changes = [dict(x=x, y=y, decoded=0x076A, settled=tile) for x, y, tile in (
                (15, 31, 0x0797), (16, 31, 0x0787), (17, 31, 0x0791),
                (15, 32, 0x078A), (18, 32, 0x09C1), (14, 33, 0x09C1), (17, 33, 0x0789))]
            require(changes == expected_changes, 'Settled native36 field differs from the exact7Goron entrance changes')
            self.record('native36 exact settled Goron footprint', changes=changes)
        elif area == 0xA1:
            require(changes == [], 'Isolated A1 field changed after raw decode')
            self.record('isolated A1 settled field unchanged')
        self.appearance(area)
        self.observe_motion()

    def appearance(self, area):
        caches = {f'{a:06X}': self.read(a, n).hex()
                  for a, n in ((0x7E0AA0, 0x18), (0x7E04CB, 8), (0x7EC2F0, 16), (0x7E0600, 0x20))}
        if area == 0xA1:
            descriptor = self.rom[0x3C5FC0:0x3C6000]
            expected = dict(map_id=area, graphics_sheets=list(descriptor[12:20]),
                            main_palette=descriptor[20], palette_set=descriptor[21], animated_sheet=descriptor[22])
            require(self.value(0x7E0AA2) == 0x30 and self.value(0x7E0AA3) == 0,
                    'A1 native area/sprite graphics selector cache differs')
            require(self.value(0x7E0600, 2) == 0x800 and self.value(0x7E0604, 2) == 0x200,
                    'A1 native camera origin differs from the selected map')
        else:
            expected = self.streams.native_profile(self.rom, area)
        self.record('native appearance capture and profile caches', expected_profile=expected, caches=caches,
                    palette_or_art_injection=False, pixel_acceptance='root reviews captured native frames/CGRAM/VRAM')

    def a1_fixture(self):
        cpu = self.run_to(self.labels['Lyra_Fixture_PreProfile'])
        require(number(cpu['p']) & 0x20 == 0 and number(cpu['d']) == 0,
                'A1 pre-profile requires native M16/D0 entry')
        require(self.value(0x7E008A, 2) == self.value(0x7E040A, 2) == 0x36
                and self.value(0x7E00A0, 2) == 0x98 and self.value(0x7E0010) == 8,
                'A1 fixture did not reach the real room0098 native exit boundary')
        x, y = self.value(0x7E0022, 2), self.value(0x7E0020, 2)
        require(0xC00 <= x < 0xE00 and 0xC00 <= y < 0xE00,
                'Room0098 exit landing is outside the reviewed512px template')
        fields = {0x20: -0x400, 0x22: -0xA00, 0xE0: -0xA00, 0xE2: -0xA00,
                  0xE6: -0x400, 0xE8: -0x400, 0x11E: -0xA00, 0x120: -0xA00,
                  0x122: -0x400, 0x124: -0x400, 0x618: -0x400, 0x61A: -0x400,
                  0x61C: -0xA00, 0x61E: -0xA00}
        before = {offset: self.value(0x7E0000 + offset, 2) for offset in fields}
        require(all(0 <= before[offset] + delta <= 0xFFFF for offset, delta in fields.items()),
                'A1 geometry rebase would wrap')
        for offset, delta in fields.items():
            self.write(0x7E0000 + offset, before[offset] + delta, 2,
                       'one-time exit14 geometry rebase36(C00,C00) toA1(200,800)')
        for address in (0x7E008A, 0x7E040A):
            self.write(address, 0xA1, 2, 'one-time full A1 identity before native profile/camera readers')
        require(self.cpu() == cpu, 'A1 RAM fixture changed CPU state')
        self.report['fixtures'].append(dict(kind='A1_pre_profile', boundary=cpu,
            local_x=x - 0xC00, local_y=y - 0xC00, natural_entry=False))

    def overlay_selector_fixture(self):
        cpu = self.run_to(self.labels['Lyra_Fixture_PreOverlaySelect'])
        require(number(cpu['p']) & 0x30 == 0 and number(cpu['d']) == 0,
                'Pre-FF selector requires M16/X16/D0')
        require(number(cpu['x']) == 0x94 and self.value(0x7E00A0, 2) == 0x181,
                'Expected declared existing under-bridge selector94 from room0181 fixture')
        stack = self.read(0x7E0000 + number(cpu['sp']) + 1, 24)
        # Installed source API: LuaApi::SetState -> Serializer::ReadMapFormat
        # updates only supplied keys; cpu.x is the normalized SnesCpu X key.
        code = "local s=emu.getState(); assert(s['cpu.x']~=nil); emu.setState({['cpu.x']=0xA1})"
        self.cmd('EXEC_LUA', code=base64.b64encode(code.encode()).decode())
        after = self.cpu()
        require(number(after['x']) == 0xA1, 'Installed one-shot X fixture API did not take effect')
        require(all(after[k] == cpu[k] for k in cpu if k != 'x')
                and self.read(0x7E0000 + number(cpu['sp']) + 1, 24) == stack,
                'Selector fixture changed another register/PC/stack')
        self.report['fixtures'].append(dict(kind='one_shot_overlay_X_only', before=cpu, after=after,
            code=code, persistent_callbacks=False, natural_overlay=False,
            native_selector_before=0x94, selected_stream_fixture=0xA1))

    def sub_case(self):
        self.wait_play()
        require('Lyra_Fixture_OverlayRestored' in self.labels,
                'Missing candidate-bound post-overlay restoration label')
        require(self.value(0x7E008A, 2) == self.value(0x7E040A, 2) == 0xA1,
                'A1 sub-overlay requires completed A1 full-load')
        fields = (0x8A, 0x84, 0x88, 0x86, 0x418, 0x410, 0x416)
        self.write(0x7E0013, 0x80, 1, 'blank before native overlay loader')
        self.write(0x7E009B, 0, 1, 'disable HDMA shadow before native overlay loader')
        self.frames(1)
        dispatch = self.run_to(0x008056)
        require(number(dispatch['p']) & 0x30 == 0x30 and number(dispatch['d']) == 0,
                'Overlay setup requires native pre-dispatch M8/X8/D0 boundary')
        before = {o: self.value(0x7E0000 + o, 2) for o in fields}
        previous_room = self.value(0x7E00A0, 2)
        self.write(0x7E00A0, 0x181, 2,
                   'one-time existing under-bridge overlay selector path; A1 normally has no overlay')
        self.report['fixtures'].append(dict(kind='existing_under_bridge_overlay_branch',
            boundary='008056', previous_room=previous_room, fixture_room=0x181, natural_overlay=False))
        self.write(0x7E0011, 1, 1, 'declared existing Module08 sub1 overlay path')
        self.write(0x7E0010, 8, 1, 'declared native overlay lifecycle fixture')
        self.overlay_selector_fixture()
        self.hooks(0xA1, 0xA1, sub=True)
        self.run_to(self.labels['Lyra_Fixture_OverlayRestored'])
        require(all(self.value(0x7E0000 + o, 2) == value for o, value in before.items()),
                'Native overlay caller did not restore field/scroll state')
        blobs, _ = self.capture('a1-sub-overlay-restored')
        actual = b''.join(blobs['overlay'][y * 128:y * 128 + 64] for y in range(32))
        require(actual == self.expected(0xA1)[0], 'Native sub-overlay output differs from A1 candidate grid')
        self.write(0x7E00A0, previous_room, 2, 'restore pre-fixture room after native overlay caller restoration')
        self.record('native A1 sub-overlay and caller restoration', sha256=digest(actual))
        self.wait_play()

    def boot_file2(self):
        require(self.a.seed_srm is not None, 'Controller cold boot requires the pinned source SRM argument')
        for _ in range(60):
            if self.value(0x7E0010) == 1:
                break
            self.frames(6, 'Start')
            self.frames(24)
        else:
            raise RuntimeError('Cold boot did not reach file select')
        for _ in range(6):
            if self.value(0x7E00C8) == 1:
                break
            self.frames(4, 'Down')
            self.frames(20)
        require(self.value(0x7E00C8) == 1, 'Controller could not select existing file2')
        for _ in range(30):
            self.frames(8, 'Start')
            self.frames(24)
            if self.value(0x7E0010) in (7, 9, 0x0B) and self.value(0x7E0011) == 0:
                self.capture('controller-file2-loaded')
                self.record('existing file2 controller boot', seed_sha256=SEED_SHA)
                return
        raise RuntimeError('Existing file2 failed to reach stable play')

    def wait_play(self):
        for _ in range(120):
            if self.value(0x7E0010) in (7, 9, 0x0B) and self.value(0x7E0011) == 0:
                self.record('native idle play', module=self.value(0x7E0010))
                return
            self.frames(2)
        raise RuntimeError('Native load failed to reach idle play within240frames')

    def observe_motion(self):
        before = self.capture('before-controller')[1]
        self.link_collision('Right')
        self.frames(12, 'Right')
        after = self.capture('after-controller')[1]
        self.report['observations'].append(dict(kind='bounded_controller_observation',
            before=[before['x'], before['y'], before['hp']], after=[after['x'], after['y'], after['hp']],
            qualification='position/damage observation only; use explicit route37/route-a1 for reviewed dry/solid cells'))
        self.record('controller batch completed without ROM or palette injection')

    def link_collision(self, button, allowed_chr=None, allowed_attrs=None, attempts=1):
        require(self.rom[pc(0x07DC2A):pc(0x07DC2A) + 4] == bytes.fromhex('222e8800')
                and self.rom[pc(0x00886E):pc(0x00886E) + 4] == bytes.fromhex('bf59940e'),
                'Actual native Link collision reader differs')
        self.input(button)
        require(1 <= attempts <= 8, 'Link collision sampling must be1..8real caller invocations')
        for attempt in range(attempts):
            self.run_to(0x07DC2A)
            at = self.run_to(0x00886E)
            chr_id = number(at['x'])
            require(chr_id <= 0x1FF, 'Native collision index exceeds low9CHR mask')
            loaded = self.run_to(0x008872)
            require(number(loaded['a']) & 0xFF == self.rom[0x71459 + chr_id],
                    'Actual native Link collision attribute differs from candidate table')
            attr = number(loaded['a']) & 0xFF
            selected = ((allowed_chr is None or chr_id in allowed_chr)
                        and (allowed_attrs is None or attr in allowed_attrs))
            self.record('live Link collision lookup', entry=at, loaded=loaded, chr_id=chr_id,
                        raw_attribute=attr, attempt=attempt + 1, selected_reviewed_quarter=selected)
            if selected:
                return
        raise RuntimeError('Bounded live Link lookups missed reviewed route CHR/attribute')

    def private_srm(self):
        require(self.a.private_srm is not None, 'Event proof requires root-owned copied SRM path')
        root = self.a.owned_home.resolve() / 'Saves'
        require(self.a.private_srm.resolve().is_relative_to(root), 'Private SRM must be within owned home/Saves')
        require(self.a.private_srm.stem == self.a.rom.stem, 'Copied SRM basename must match loaded private ROM')
        return self.a.private_srm.read_bytes()

    def event_check(self):
        require(self.a.event_reference is not None, 'Reopen proof requires prior native save reference')
        reference = json.loads(self.a.event_reference.read_text())
        require(reference.get('rom_sha256') == digest(self.rom), 'Event reference belongs to a different candidate')
        save = self.read(0x7EF000, 0x500)
        require(save[0x4E0] == 0xA1 and all(save[a - 0x7EF000] == v for a, v in TAIL.items()),
                'Saved event sentinels/version do not survive current file load')
        require(save[0x280:0x340].hex() == reference['legacy_hex'], 'Reopened legacy event/item bytes changed')
        require(save[0x4C0:0x4E1].hex() == reference['tail_hex']
                and [save[o] for o in STORY] == reference['story'], 'Reopened full tail or story fields changed')
        disk = self.private_srm()
        require(len(disk) == 8192, 'Unexpected private SRM shape')
        main, mirror = disk[0x500:0xA00], disk[0x1400:0x1900]
        require(main == mirror and checksum(main), 'Slot2 mirror/checksum differs')
        require(main[0x4C0:0x4E1] == save[0x4C0:0x4E1], 'Disk/live saved tail differs')
        require(digest(disk[0:0x500] + disk[0xF00:0x1400]) == reference['slot1_sha256']
                and digest(disk[0xA00:0xF00] + disk[0x1900:0x1E00]) == reference['slot3_sha256'],
                'Another SRM slot changed')
        self.record('existing tail events persisted', srm_sha256=digest(disk),
                    tail_hex=save[0x4C0:0x4E1].hex(), legacy_sha256=digest(save[0x280:0x340]))

    def save_continue(self):
        require(self.value(0x7E0010) == 9 and self.value(0x7E0011) == 0
                and self.value(0x7E008A, 2) == 0x33,
                'Save & Continue requires the existing ordinary legacy33 control, not the A1 fixture')
        disk = self.private_srm()
        require(len(disk) == 8192, 'Private SRM shape differs')
        legacy = self.read(0x7EF280, 0xC0)
        story = [self.value(0x7EF000 + o) for o in STORY]
        require(self.value(0x7EF4E0) == 0xA1, 'Existing load must have initialized the tail version')
        for address, value in TAIL.items():
            self.write(address, value, 1, 'same declared existing A5/BF event sentinels; no acquisition claim')
        tail = self.read(0x7EF4C0, 0x21)
        self.write(0x7EF36D, 1, 1, 'same bounded death fixture: health1, damage remains active')
        self.write(0x7E0373, 8, 1, 'same pending native damage8 fixture')
        for _ in range(240):
            if self.value(0x7E0010) == 0x12:
                break
            self.frames(4)
        require(self.value(0x7E0010) == 0x12, 'Native damage did not reach death module')
        for _ in range(120):
            if self.value(0x7E0011) >= 9:
                break
            self.frames(15)
        require(self.value(0x7E00B0) == 0, 'Existing death menu default is not Save & Continue')
        for _ in range(60):
            if self.value(0x7E0010) in (7, 9, 0x0B) and self.value(0x7E0011) == 0:
                break
            self.frames(6, 'Start' if self.value(0x7E0010) == 0x12 else '')
            self.frames(18)
        self.wait_play()
        require(self.read(0x7EF280, 0xC0) == legacy, 'Continue changed legacy event/item extension bytes')
        require(self.read(0x7EF4C0, 0x21) == tail
                and [self.value(0x7EF000 + o) for o in STORY] == story,
                'Native Save & Continue lost tail events/version')
        reference = dict(rom_sha256=digest(self.rom), legacy_hex=legacy.hex(), tail_hex=tail.hex(), story=story,
                         slot1_sha256=digest(disk[0:0x500] + disk[0xF00:0x1400]),
                         slot3_sha256=digest(disk[0xA00:0xF00] + disk[0x1900:0x1E00]),
                         qualification='native Save & Continue live retention; root closes/reopens same profile to flush/prove disk')
        (self.a.proof_dir / 'EVENT_REFERENCE.json').write_text(json.dumps(reference, indent=2) + '\n')
        self.capture('after-native-save-continue')
        self.record('existing Save & Continue retained events', reference='EVENT_REFERENCE.json',
                    cold_reopen_pending=True, new_save_exit_destination=False)

    def execute(self):
        self.check_owner()
        self.paused()
        require(not self.b.list_breakpoints(), 'Foreign breakpoints: shared debugger session refused')
        cheats = self.cmd('CHEAT', action='list')
        entries = cheats.get('cheats') if isinstance(cheats, dict) else cheats
        require(isinstance(entries, list) and not entries, 'Unexpected cheat codes; native damage/input qualification refused')
        self.owned = True
        self.input('')
        if self.a.case == 'inspect':
            self.capture('inspect')
        elif self.a.case in ('native37', 'legacy33'):
            self.full_case(0x36 if self.a.case == 'native37' else 0x33)
        elif self.a.case == 'boot-file2':
            self.boot_file2()
        elif self.a.case == 'a1-full':
            self.full_case(0xA1)
        elif self.a.case == 'a1-sub-overlay':
            self.sub_case()
        elif self.a.case in ('route37', 'route-a1'):
            self.route_case(0x37 if self.a.case == 'route37' else 0xA1)
        elif self.a.case == 'save-continue':
            self.save_continue()
        elif self.a.case == 'reopen-check':
            self.event_check()
        self.report['passed'] = True


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--describe', action='store_true')
    p.add_argument('--validate', action='store_true', help='Offline candidate binding check; no socket')
    p.add_argument('--case', choices=CASES, default='inspect')
    for name in ('rom', 'symbols', 'proof-dir', 'status-file', 'owner-file', 'owned-home', 'private-srm', 'seed-srm', 'event-reference'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--socket')
    p.add_argument('--pid', type=int)
    p.add_argument('--owner')
    p.add_argument('--rom-sha256')
    p.add_argument('--symbols-sha256')
    p.add_argument('--client-root', type=Path, default=CLIENT)
    p.add_argument('--seconds', type=int, default=180)
    p.add_argument('--execute-fixtures', action='store_true')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.describe:
        print(json.dumps(dict(cases=CASES, attach_only=True, launches=False, sets_pc=False,
            pending=['candidate live qualification and bounded route/body calibration'],
            live_requirements=['explicit socket/PID/status/owner', 'candidate ROM/symbol SHA256',
                               'native paired helper+Returned labels and actual JSL ingress']), indent=2))
        return 0
    require(args.rom and args.symbols and args.rom_sha256 and args.symbols_sha256,
            'Explicit ROM/symbol files and SHA256 pins are required')
    rom, sym = args.rom.read_bytes(), args.symbols.read_bytes()
    require(digest(rom) == args.rom_sha256.lower(), 'Candidate ROM SHA256 differs')
    require(digest(sym) == args.symbols_sha256.lower(), 'Candidate symbol SHA256 differs')
    binding = candidate(rom, sym)
    if args.validate:
        probe = Runner.__new__(Runner)
        probe.rom, probe.labels, probe.decoder, probe.streams, probe.definitions = rom, *binding
        routes = [probe.route_binding(area) for area in ROUTES]
        print(json.dumps(dict(validated=True, rom_sha256=digest(rom), labels=binding[0], routes=routes), indent=2))
        return 0
    require(args.socket and args.pid and args.pid > 0 and args.status_file and args.owner_file
            and args.owner and args.owned_home and args.proof_dir, 'Explicit root-owned session binding required')
    require(not any(s in args.socket for s in ('oos-rc-play', 'oos-scawful-test')), 'User instance refused')
    defaults = (Path.home() / 'Documents/Mesen2', Path.home() / 'Library/Application Support/Mesen2',
                Path.home() / '.config/Mesen2')
    require(not any(args.owned_home.resolve().is_relative_to(p) for p in defaults), 'User/default Mesen profile refused')
    require(1 <= args.seconds <= 600, 'Runner deadline must be1..600seconds')
    require(args.case == 'inspect' or args.execute_fixtures, 'Live fixtures require --execute-fixtures')
    if args.seed_srm:
        require(digest(args.seed_srm.read_bytes()) == SEED_SHA, 'Cold-boot seed SRM pin differs')
    args.proof_dir.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    try:
        runner = Runner(args, bridge, rom, *binding)
    except BaseException as error:
        (args.proof_dir / 'RESULT.json').write_text(json.dumps(dict(
            passed=False, error=repr(error), attached=False, rom_sha256=digest(rom)), indent=2) + '\n')
        raise
    try:
        runner.execute()
    except BaseException as error:
        runner.report['passed'] = False
        runner.report['error'] = repr(error)
    finally:
        if runner.owned:
            try:
                runner.cleaning = True
                runner.check_owner(force=True)
                runner.input('')
                require(bridge.pause(), 'Could not leave owned process paused')
                for ident in list(runner.breakpoints):
                    require(bridge.remove_breakpoint(ident), 'Owned breakpoint cleanup failed')
                    runner.breakpoints.remove(ident)
            except BaseException as error:
                runner.report['cleanup_errors'].append(repr(error))
        for path, expected in ((args.rom, args.rom_sha256), (args.symbols, args.symbols_sha256),
                               *runner.dependencies.items(),
                               *(([(args.seed_srm, SEED_SHA)]) if args.seed_srm else [])):
            if digest(path.read_bytes()) != expected.lower():
                runner.report['cleanup_errors'].append(f'Input changed: {path}')
        runner.report['passed'] = runner.report['passed'] and not runner.report['cleanup_errors']
        (args.proof_dir / 'RESULT.json').write_text(json.dumps(runner.report, indent=2) + '\n')
    print(json.dumps(dict(passed=runner.report['passed'], result=str(args.proof_dir / 'RESULT.json'))))
    return 0 if runner.report['passed'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(json.dumps(dict(passed=False, error=str(error))), file=sys.stderr)
        raise SystemExit(2)
