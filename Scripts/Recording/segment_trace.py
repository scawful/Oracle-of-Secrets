#!/usr/bin/env python3
"""Cut an enrich_movie.py trace into per-edge segments and a route library.

Input is the folder enrich_movie.py wrote (trace.jsonl, transitions.jsonl, states/,
summary.json). A segment runs from one settled location to the next. A location is
settled when the module is a gameplay module (Dungeon $07, Overworld $09, Special OW $0B);
load modules, menus and text keep the current segment open and show up as events.

Writes, into --out (default <trace>/segments):

  <n>_<from>__<to>/start.mss     savestate at the first row of the segment
  <n>_<from>__<to>/inputs.txt    the movie's Input.txt rows for the segment
  <n>_<from>__<to>/runs.json     pad held runs: [{"buttons": [...], "frames": n}, ...]
  <n>_<from>__<to>/waypoints.json Link x/y every --waypoint-step rows in gameplay modules
  <n>_<from>__<to>/events.json   module, HP, rupee, form and progress-flag changes
  <n>_<from>__<to>/requires.json progress fields at the first row
  <n>_<from>__<to>/end.json      location, fields and deltas at the last row
  route_library.json             nodes and edges; each edge lists its segments

--library merges the edges into an existing route_library.json instead (several traces).
Rows: start.mss is the state before the segment's first row (row 0: the movie's own savestate); replaying inputs.txt rows first..last from
it reproduces end.json on the same ROM (rom_sha1). Offline; starts no emulator.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

SCHEMA = 'oos-route-library-v1'
GAMEPLAY = {0x07, 0x09, 0x0B}
KEYS = 'ABXYLRSTUDLR'
BUTTONS = ('A', 'B', 'X', 'Y', 'L', 'R', 'Select', 'Start', 'Up', 'Down', 'Left', 'Right')
FLAGS = ('game_state', 'oosprog', 'oosprog2', 'sidequest', 'crystals', 'pendants', 'intro_state',
         'max_health', 'link_form')
REQUIRES = FLAGS + ('health', 'magic', 'rupees')


def location(r: dict) -> str:
    return f"room-{r['room']:03X}" if r['indoors'] else f"area-{r['area']:02X}"


def buttons(pad: str | None) -> list[str]:
    if not pad:
        return []
    return [BUTTONS[i] for i, c in enumerate(pad[:12]) if c != '.']


def runs(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        b = buttons(r['pad'])
        if out and out[-1]['buttons'] == b:
            out[-1]['frames'] += 1
        else:
            out.append({'row': r['row'], 'buttons': b, 'frames': 1})
    return out


def events(rows: list[dict], prev: dict | None) -> list[dict]:
    out = []
    for r in rows:
        if prev is not None:
            if r['module'] != prev['module']:
                out.append({'row': r['row'], 'type': 'module', 'from': prev['module'], 'to': r['module']})
            if r['module'] in GAMEPLAY and prev['module'] in GAMEPLAY and location(r) != location(prev):
                out.append({'row': r['row'], 'type': 'location', 'from': location(prev), 'to': location(r)})
            for k in ('health', 'rupees') + FLAGS:
                if r[k] != prev[k]:
                    out.append({'row': r['row'], 'type': k, 'from': prev[k], 'to': r[k]})
        prev = r
    return out


def movie_state(summary: dict, dest: Path) -> None:
    """Row 0 starts from the savestate embedded in the movie, when it has one."""
    movie = Path(summary.get('movie') or '')
    if movie.is_file():
        with zipfile.ZipFile(movie) as z:
            if 'SaveState.mss' in z.namelist():
                dest.write_bytes(z.read('SaveState.mss'))


def input_rows(summary: dict) -> list[str] | None:
    movie = Path(summary.get('movie') or '')
    if not movie.is_file():
        return None
    with zipfile.ZipFile(movie) as z:
        return [line for line in z.read('Input.txt').decode(errors='replace').splitlines() if line.startswith('|')]


def cut(trace: list[dict]) -> list[tuple[int, int, str, str]]:
    """Return (first, last, from, to) row ranges, without overlap.

    A boundary is the first row that shows a new settled location. enrich_movie.py saw a key
    change on that row and saved the state before the next row, so the next segment starts
    one row after the boundary; the boundary row ends the previous segment.
    """
    bounds = []
    here = None
    for r in trace:
        if r['module'] not in GAMEPLAY:
            continue
        loc = location(r)
        # title/file select before the first settled location is its own 'start' segment
        if (here is None and r['row'] > 0) or (here is not None and loc != here):
            bounds.append(r['row'])
        here = loc
    segs = []
    first = 0
    src = location(trace[0]) if trace[0]['module'] in GAMEPLAY else 'start'
    for b in bounds:
        segs.append((first, b, src, location(trace[b])))
        first, src = b + 1, location(trace[b])
    if first <= trace[-1]['row']:
        segs.append((first, trace[-1]['row'], src, 'end'))
    return segs


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('trace', type=Path, help='folder written by enrich_movie.py')
    p.add_argument('--out', type=Path, help='segments folder (default: <trace>/segments)')
    p.add_argument('--library', type=Path, help='route_library.json to merge into (default: <out>/route_library.json, replaced)')
    p.add_argument('--waypoint-step', type=int, default=8)
    p.add_argument('--overwrite', action='store_true')
    a = p.parse_args()

    tdir = a.trace.resolve()
    summary = json.loads((tdir / 'summary.json').read_text())
    if not summary.get('ok'):
        print(f'error: trace not ok: {summary.get("error")}', file=sys.stderr)
        return 1
    trace = [json.loads(line) for line in (tdir / 'trace.jsonl').open()]
    if not trace:
        print('error: empty trace', file=sys.stderr)
        return 1
    # savestate taken after row N ran = state before row N+1
    states = {}
    for line in (tdir / 'transitions.jsonl').open():
        ev = json.loads(line)
        if ev.get('state'):
            states[ev['row'] + 1] = tdir / ev['state']
    if [r['row'] for r in trace] != list(range(len(trace))):
        print('error: trace rows are not 0..N in order', file=sys.stderr)
        return 1
    inputs = input_rows(summary)
    out = (a.out or tdir / 'segments').resolve()
    if out.exists():
        if not a.overwrite:
            print(f'error: {out} exists (pass --overwrite)', file=sys.stderr)
            return 1
        shutil.rmtree(out)
    out.mkdir(parents=True)

    rom_sha1 = summary.get('rom_sha1')
    made = []
    for n, (first, last, src, dst) in enumerate(cut(trace)):
        rows = trace[first:last + 1]
        start_row, end_row = rows[0]['row'], rows[-1]['row']
        d = out / f'{n:03d}_{src}__{dst}'
        d.mkdir()
        state = states.get(start_row)
        if start_row == 0:
            movie_state(summary, d / 'start.mss')
        elif state and state.is_file():
            shutil.copy2(state, d / 'start.mss')
        if inputs is not None:
            (d / 'inputs.txt').write_text('\n'.join(inputs[start_row:end_row + 1]) + '\n')
        (d / 'runs.json').write_text(json.dumps(runs(rows), indent=0) + '\n')
        way = [{'row': r['row'], 'loc': location(r), 'x': r['link_x'], 'y': r['link_y']}
               for i, r in enumerate(rows) if r['module'] in GAMEPLAY and (i % a.waypoint_step == 0 or i == len(rows) - 1)]
        (d / 'waypoints.json').write_text(json.dumps(way, separators=(',', ':')) + '\n')
        prev = trace[first - 1] if first else None
        (d / 'events.json').write_text(json.dumps(events(rows, prev), indent=0) + '\n')
        (d / 'requires.json').write_text(json.dumps({k: rows[0][k] for k in REQUIRES}, indent=1) + '\n')
        end = {'row': end_row, 'loc': location(rows[-1]), 'module': rows[-1]['module'],
               'link_x': rows[-1]['link_x'], 'link_y': rows[-1]['link_y'],
               'fields': {k: rows[-1][k] for k in REQUIRES},
               'delta': {k: rows[-1][k] - rows[0][k] for k in ('health', 'rupees', 'magic') if rows[-1][k] != rows[0][k]}}
        (d / 'end.json').write_text(json.dumps(end, indent=1) + '\n')
        made.append({'from': src, 'to': dst, 'dir': str(d), 'rows': [start_row, end_row], 'frames': len(rows),
                     'has_state': (d / 'start.mss').is_file(), 'has_inputs': inputs is not None,
                     'rom_sha1': rom_sha1, 'movie_sha256': summary.get('movie_sha256')})

    lib_path = (a.library or out / 'route_library.json').resolve()
    lib = {'schema': SCHEMA, 'nodes': [], 'edges': []}
    if a.library and lib_path.is_file():
        lib = json.loads(lib_path.read_text())
    edges = {(e['from'], e['to']): e for e in lib['edges']}
    for s in made:
        e = edges.setdefault((s['from'], s['to']), {'from': s['from'], 'to': s['to'], 'segments': []})
        same = (s['movie_sha256'], s['rows'])
        e['segments'] = [x for x in e['segments'] if (x.get('movie_sha256'), x['rows']) != same] + [s]
    lib['edges'] = sorted(edges.values(), key=lambda e: (e['from'], e['to']))
    lib['nodes'] = sorted({x for e in lib['edges'] for x in (e['from'], e['to'])} - {'start', 'end'})
    lib_path.write_text(json.dumps(lib, indent=1) + '\n')
    print(json.dumps({'segments': len(made), 'edges': len(lib['edges']), 'nodes': len(lib['nodes']),
                      'missing_state': sum(not s['has_state'] for s in made), 'out': str(out), 'library': str(lib_path)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
