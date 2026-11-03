#!/usr/bin/env python3
"""Replay a Mesen input movie (.mmo) headless and write a per-frame trace.

scawful records a movie in the play window (File > Movies > Record). This script
replays it on a private headless Mesen2-OOS instance (own home, socket, ROM copy)
through the socket MOVIE command and writes, into --out:

  trace.jsonl      one record per movie row: row, pad, joypad bytes, telemetry fields
  transitions.jsonl one record per module/area/room change, with its savestate path
  states/          savestates at row 0 and at every transition
  summary.json     movie, ROM, app, frame count, transition count, verdict

The ROM must be the one the movie names (GameSettings.txt SHA1). The app must
support the socket MOVIE command (mesen2-oos fe433885 or later).
Stops only the emulator PID it launched, with SIGTERM.

Each trace record is read after its row's frame ran. `pad` is that row's movie input;
the game's joypad mirrors (`joy`, $F0-$F6) show it one row later (NMI reads the pad).
Speed is about 50 rows/s, so one hour of play takes about 70 minutes to enrich.
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
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'Scripts' / 'Mesen2'))
from mesen2_client_lib.bridge import MesenBridge  # noqa: E402

LAUNCHER = REPO / 'Scripts' / 'Mesen2' / 'mesen2_launch_instance.sh'
SCHEMA = 'oos-movie-trace-v1'

# name: (address, width). Same addresses as mesen2-oos tools/oos_client/oos_telemetry.py FIELDS.
FIELDS = {
    'frame': (0x7E001A, 1),
    'module': (0x7E0010, 1), 'submodule': (0x7E0011, 1), 'indoors': (0x7E001B, 1),
    'area': (0x7E008A, 1), 'room_layout': (0x7E00A0, 1), 'room': (0x7E048E, 2),
    'link_x': (0x7E0022, 2), 'link_y': (0x7E0020, 2), 'link_dir': (0x7E002F, 1),
    'link_state': (0x7E005D, 1), 'link_form': (0x7E02B2, 1),
    'health': (0x7EF36D, 1), 'max_health': (0x7EF36C, 1), 'magic': (0x7EF36E, 1),
    'rupees': (0x7EF360, 2), 'game_state': (0x7EF3C5, 1), 'oosprog': (0x7EF3D6, 1),
    'oosprog2': (0x7EF3C6, 1), 'sidequest': (0x7EF3D7, 1),
    'crystals': (0x7EF37A, 1), 'pendants': (0x7EF374, 1), 'intro_state': (0x7EF39E, 1),
}
# Joypad mirrors: $F0/$F2 held, $F4/$F6 newly pressed.
JOY = {'held_hi': 0x7E00F0, 'held_lo': 0x7E00F2, 'new_hi': 0x7E00F4, 'new_lo': 0x7E00F6}
LOW = (0x7E0000, 0x500)   # covers $00-$FF, $02B2, $048E
SRAM = (0x7EF300, 0x120)  # covers $7EF300-$7EF41F
# Module/area/room changes; a change opens a new segment for segment_trace.py.
KEYS = ('module', 'indoors', 'area', 'room')


def sha(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def identity(pid: int) -> str:
    return subprocess.run(['ps', '-o', 'lstart=,command=', '-p', str(pid)], text=True,
                          capture_output=True, check=False).stdout.strip()


def movie_meta(mmo: Path) -> dict:
    with zipfile.ZipFile(mmo) as z:
        settings = z.read('GameSettings.txt').decode(errors='replace')
        rows = sum(1 for line in z.read('Input.txt').decode(errors='replace').splitlines() if line.startswith('|'))
        has_state = 'SaveState.mss' in z.namelist()
    meta = {'rows': rows, 'has_savestate': has_state}
    for line in settings.splitlines():
        key, _, value = line.partition(' ')
        if key in ('SHA1', 'GameFile', 'MesenVersion'):
            meta[key.lower()] = value.strip()
    return meta


class Enricher:
    def __init__(self, a: argparse.Namespace):
        self.a = a
        self.out = a.out
        self.name = f'enrich-{uuid.uuid4().hex[:6]}'
        self.home = self.out / 'home'
        self.sock = Path(f'/tmp/mesen2-{self.name}.sock')
        self.pid = None
        self.pid_id = None
        self.b = None
        self.summary: dict = {'schema': SCHEMA, 'movie': str(a.movie), 'app': str(a.app) if a.app else None}

    def write_summary(self) -> None:
        (self.out / 'summary.json').write_text(json.dumps(self.summary, indent=1) + '\n')

    def send(self, t: str, timeout: float = 10.0, **p) -> dict:
        return self.b.send_command(t, {k: str(v) for k, v in p.items()}, timeout=timeout)

    def movie(self, **p) -> dict:
        r = self.send('MOVIE', **p)
        if not r.get('success'):
            raise RuntimeError(f"MOVIE {p.get('action')}: {r.get('error')}")
        d = r.get('data')
        return json.loads(d) if isinstance(d, str) else d

    def launch(self, rom: Path) -> None:
        cmd = ['taskpolicy', '-b', 'nice', '-n', '10', 'bash', str(LAUNCHER), '--headless',
               '--no-copy-settings', '--no-save-settings', '--no-seed-project-states', '--no-state-set',
               '--no-register', '--instance', self.name, '--home', str(self.home), '--socket', str(self.sock),
               '--rom', str(rom)]
        if self.a.app:
            cmd += ['--app', str(self.a.app)]
        with (self.out / 'launch.log').open('w') as log:
            subprocess.run(cmd, cwd=REPO, stdout=log, stderr=log, check=True, timeout=40)
        for _ in range(80):
            if self.sock.exists():
                break
            time.sleep(0.25)
        if not self.sock.exists():
            raise RuntimeError('socket did not appear')
        pids = subprocess.run(['lsof', '-t', str(self.sock)], text=True, capture_output=True).stdout.split()
        owned = [int(p) for p in pids if p.isdigit() and str(rom) in identity(int(p))]
        if len(owned) != 1:
            raise RuntimeError(f'cannot identify the owned emulator: {pids}')
        self.pid = owned[0]
        self.pid_id = identity(self.pid)
        self.b = MesenBridge(str(self.sock))
        self.summary['emulator'] = {'pid': self.pid, 'socket': str(self.sock)}

    def close(self) -> None:
        if self.pid and identity(self.pid) == self.pid_id:
            os.kill(self.pid, signal.SIGTERM)
            for _ in range(50):
                if identity(self.pid) != self.pid_id:
                    break
                time.sleep(0.1)
            self.summary['emulator']['exited'] = identity(self.pid) != self.pid_id

    def read(self) -> tuple[dict, bytes, bytes]:
        # MOVIE is not in the BATCH allowlist, so status is its own call.
        st = self.movie(action='status')
        cmds = [{'type': 'READBLOCK', 'addr': f'0x{LOW[0]:06X}', 'len': str(LOW[1])},
                {'type': 'READBLOCK', 'addr': f'0x{SRAM[0]:06X}', 'len': str(SRAM[1])}]
        r = self.send('BATCH', commands=json.dumps(cmds))
        data = r.get('data')
        data = json.loads(data) if isinstance(data, str) else data
        res = (data or {}).get('results', [])
        if len(res) != 2 or not all(x.get('success') for x in res):
            raise RuntimeError(f'BATCH read failed: {r}')
        low, sram = (bytes.fromhex(str(x['data']).strip('"')) for x in res)
        if len(low) != LOW[1] or len(sram) != SRAM[1]:
            raise RuntimeError(f'short READBLOCK: {len(low)}, {len(sram)}')
        return st, low, sram

    @staticmethod
    def field(addr: int, width: int, low: bytes, sram: bytes) -> int:
        base, buf = (LOW[0], low) if addr < SRAM[0] else (SRAM[0], sram)
        off = addr - base
        return int.from_bytes(buf[off:off + width], 'little')

    def wait_step(self, prev_frame: int) -> tuple[dict, bytes, bytes]:
        deadline = time.time() + 30
        while time.time() < deadline:
            st = self.movie(action='status')
            if st['paused'] and (st['frame'] > prev_frame or not st['playing']):
                return self.read()
            time.sleep(0.002)
        raise RuntimeError(f'frame did not advance past {prev_frame}')

    def savestate(self, row: int, rec: dict) -> str:
        loc = f"r{rec['room']:03X}" if rec['indoors'] else f"a{rec['area']:02X}"
        path = self.out / 'states' / f"{row:07d}_m{rec['module']:02X}_{loc}.mss"
        r = self.send('SAVESTATE', path=str(path), allow_external='true')
        if not r.get('success'):
            raise RuntimeError(f"SAVESTATE {path}: {r.get('error')}")
        return str(path.relative_to(self.out))

    def run(self) -> bool:
        a = self.a
        meta = movie_meta(a.movie)
        rom_sha1 = sha(a.rom, 'sha1')
        self.summary.update(movie_sha256=sha(a.movie, 'sha256'), movie_meta=meta,
                            rom=str(a.rom), rom_sha1=rom_sha1)
        if meta.get('sha1', '').lower() != rom_sha1:
            raise RuntimeError(f"ROM SHA1 {rom_sha1} != movie SHA1 {meta.get('sha1')} ({meta.get('gamefile')})")
        if self.out.exists():
            if not a.overwrite:
                raise RuntimeError(f'{self.out} exists (pass --overwrite)')
            shutil.rmtree(self.out)
        (self.home / 'Saves').mkdir(parents=True)
        (self.out / 'states').mkdir()
        rom = self.out / 'replay.sfc'
        shutil.copy2(a.rom, rom)
        self.write_summary()
        self.launch(rom)
        if 'MOVIE' not in json.dumps(self.send('HELP')):
            raise RuntimeError('app has no socket MOVIE command; pass --app with a mesen2-oos build that has it')
        if a.speed is not None:
            self.send('SPEED', multiplier=a.speed)
        self.movie(action='play', path=str(a.movie), pause='true')
        deadline = time.time() + 15
        while True:
            st = self.movie(action='status')
            if st['paused'] or time.time() > deadline:
                break
            time.sleep(0.01)
        if not (st['playing'] and st['paused'] and st['input_row'] == 0):
            raise RuntimeError(f'movie did not start paused at row 0: {st}')

        t0 = time.monotonic()
        prev_key = None
        rows = transitions = 0
        limit = a.max_frames or meta['rows']
        with (self.out / 'trace.jsonl').open('w') as trace, (self.out / 'transitions.jsonl').open('w') as trans:
            while st['playing'] and rows < limit:
                row = st['input_row']
                frame = st['frame']
                self.send('FRAME', count=1)
                st, low, sram = self.wait_step(frame)
                rec = {'row': row, 'pad': st['pad1'] if st['playing'] else None}
                rec['joy'] = {k: self.field(v, 1, low, sram) for k, v in JOY.items()}
                rec.update({k: self.field(addr, w, low, sram) for k, (addr, w) in FIELDS.items()})
                trace.write(json.dumps(rec, separators=(',', ':')) + '\n')
                rows += 1
                key = tuple(rec[k] for k in KEYS)
                if key != prev_key:
                    ev = {'row': row, 'from': dict(zip(KEYS, prev_key)) if prev_key else None,
                          'to': dict(zip(KEYS, key)), 'link_x': rec['link_x'], 'link_y': rec['link_y']}
                    if st['playing']:
                        ev['state'] = self.savestate(row + 1, rec)
                    trans.write(json.dumps(ev, separators=(',', ':')) + '\n')
                    transitions += 1
                    prev_key = key
                if rows % 3600 == 0:
                    print(f'row {rows}/{meta["rows"]} transitions {transitions}', flush=True)
        elapsed = time.monotonic() - t0
        complete = rows >= meta['rows'] or not st['playing']
        self.summary.update(rows_traced=rows, transitions=transitions, complete=complete,
                            seconds=round(elapsed, 1), rows_per_s=round(rows / elapsed, 1) if elapsed else None)
        return complete or bool(a.max_frames)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('movie', type=Path, help='recorded .mmo')
    p.add_argument('--rom', type=Path, required=True, help='ROM the movie was recorded on (SHA1 checked)')
    p.add_argument('--out', type=Path, help='output folder (default: <movie>.trace next to the movie)')
    p.add_argument('--app', type=Path, help='Mesen2 OOS.app with the socket MOVIE command')
    p.add_argument('--speed', type=float, default=0, help='SPEED multiplier (0 = max, default)')
    p.add_argument('--max-frames', type=int, help='stop after this many rows')
    p.add_argument('--overwrite', action='store_true')
    a = p.parse_args()
    a.movie = a.movie.resolve()
    a.rom = a.rom.resolve()
    a.out = (a.out or a.movie.with_suffix('.trace')).resolve()
    e = Enricher(a)
    ok = False
    try:
        ok = e.run()
    except Exception as exc:  # report and still stop the owned emulator
        e.summary['error'] = repr(exc)
        print(f'error: {exc}', file=sys.stderr)
    finally:
        e.close()
        shutil.rmtree(e.home, ignore_errors=True)
        (a.out / 'replay.sfc').unlink(missing_ok=True)
        e.summary['ok'] = ok
        if a.out.exists():
            e.write_summary()
    print(json.dumps({k: e.summary.get(k) for k in ('ok', 'rows_traced', 'transitions', 'complete',
                                                   'rows_per_s', 'error')}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
