#!/usr/bin/env python3
"""Headless Mesen2 checks for the Portal Rod bolt (shot portals).

Boots a copy of the ROM with a copied test SRAM, loads file 2, warps into an
underworld entrance, and casts the Portal Rod with the Y button. A Python model
of PortalShot_Fly (Items/portal_rod.asm) runs on the room's live collision map
to pick test spots and predict the exact landing position; the emulator result
must match it.

Cases:
  pit   blue bolt crosses >=32 px of pit and lands beyond it; an orange bolt
        lands on the near side within camera span; Link walks into orange and warps across the pit.
  wall  bolt stops at a wall; the portal opens on the last safe floor before it.
  fizzle bolt flies over pit to maximum range with no safe floor; no portal,
        magic returns to the pre-cast value, the next cast keeps the same color.

  python3 Scripts/Validate/scenarios/portal_shot.py --rom Roms/oos168x.sfc \
      --srm <test.srm> --app <Mesen2 OOS.app> --out <dir> [--scan] [--entrance 0x..]

--scan visits every underworld entrance and lists the rooms that have each case.
Rules: headless only, own isolated profile and socket, stop only the owned PID.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault('MESEN2_OOS_ROOT', str(Path.home() / 'src' / 'hobby' / 'mesen2-oos'))
_spec = importlib.util.spec_from_file_location('dqf', HERE / 'discord_quick_fixes.py')
dqf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dqf)

LINK_Y, LINK_X, FACING, MAGIC = dqf.LINK_Y, dqf.LINK_X, dqf.FACING, dqf.MAGIC
SPR_STATE, SPR_ID = dqf.SPR_STATE, dqf.SPR_ID
SPR_ACTION, SPR_MISC_A, SPR_MISC_B, SPR_MISC_C = 0x7E0D80, 0x7E0DA0, 0x7E0DB0, 0x7E0DE0
PORTAL, SHOT_ACTION, SELECTOR = 0x03, 7, 0x7E0FA6
GBC_FLAG, MASK_FORM = 0x7E0FFF, 0x7E02B2

# Mirrors Items/portal_rod.asm PortalShot_Fly.
SPEED, RANGE = 3, 96
PASS = (0x00, 0x08, 0x09, 0x20, 0x40, 0x48)
SAFE = (0x00, 0x48)
PIT = 0x20
LEAD_X, LEAD_Y = (8, 8, 1, 14), (9, 22, 16, 16)
MIN_DIST = (20, 32, 20, 20)
# Portal_CheckWarpContext refuses an off-camera target; with Link on orange the camera
# edge sits ~120 px (X) / ~104 px (Y) from him, so keep the planned pair within this
# per-axis span (cases8: a 159 px pair never warped).
WARP_SPAN = (112, 96)
SAFE_PROBES = list(zip((0, 1, 8, 14, 1, 8, 14, 1, 8, 14), (0, 9, 9, 9, 16, 16, 16, 22, 22, 22)))
STEP = ((0, -1), (0, 1), (-1, 0), (1, 0))  # up, down, left, right
FACING_OF = (0, 2, 4, 6)
OPPOSITE = (1, 0, 3, 2)
NAMES = ('up', 'down', 'left', 'right')


def fly(attr, x, y, d):
    """Return (outcome, landing, frames, pit_px, stop_attr). outcome: land-wall, land-range, fizzle."""
    dist, found, pit_px, frames = 0, None, 0, 0
    while True:
        x, y = x + STEP[d][0] * SPEED, y + STEP[d][1] * SPEED
        dist += SPEED
        frames += 1
        lead = attr(x + LEAD_X[d], y + LEAD_Y[d])
        if lead not in PASS:
            return ('land-wall' if found else 'fizzle', found, frames, pit_px, lead)
        if lead == PIT:
            pit_px += SPEED
        if dist >= MIN_DIST[d] and all(attr(x + dx, y + dy) in SAFE for dx, dy in SAFE_PROBES):
            found = (x, y)
        if dist >= RANGE:
            return ('land-range' if found else 'fizzle', found, frames, pit_px, lead)


GAP_MIN = 24  # coordinator 2026-11-12: case (a) needs a real 3-4 tile pit between cell and landing


def path_attrs(attr, x, y, d, land, every=8):
    """Lead-probe attribute every `every` px from the cast cell to the landing."""
    out, px, py = [], x, y
    while (px, py) != tuple(land):
        px, py = px + STEP[d][0], py + STEP[d][1]
        if abs(px - x) + abs(py - y) in range(0, 1000, every) or (px, py) == tuple(land):
            out.append({'at': [px, py], 'lead': f'{attr(px + LEAD_X[d], py + LEAD_Y[d]):02X}'})
    return out


def gap_px(attr, x, y, d, land):
    """Longest run (px) between cell and landing where Link's whole body width is over a pit."""
    cross = [(LEAD_X[d], r) for r in (9, 16, 22)] if d >= 2 else [(c, LEAD_Y[d]) for c in (1, 8, 14)]
    best = run = 0
    px, py = x, y
    while (px, py) != tuple(land):
        px, py = px + STEP[d][0], py + STEP[d][1]
        if all(attr(px + cx, py + cy) == PIT for cx, cy in cross):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


class ShotRun(dqf.Run):
    # -- room model --------------------------------------------------------
    def grid(self):
        return dqf.DungeonTiles(self)

    def reachable(self, tiles, start, limit=1500):
        """4 px BFS over cells Link's body can stand on (same body box as TileRoute.route)."""
        def ok(x, y):
            return all(tiles.attr(x + dx, y + dy) in tiles.WALK for dx in (1, 14) for dy in (9, 22))
        start = (start[0] // 4 * 4, start[1] // 4 * 4)
        base_x, base_y = start[0] & ~0x1FF, start[1] & ~0x1FF
        seen, queue, order = {start}, collections.deque([start]), []
        while queue and len(order) < limit:
            c = queue.popleft()
            order.append(c)
            for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4)):
                n = (c[0] + dx, c[1] + dy)
                if n not in seen and base_x <= n[0] < base_x + 0x1F0 and base_y <= n[1] < base_y + 0x1F0 and ok(*n):
                    seen.add(n)
                    queue.append(n)
        return order

    def find_cases(self, tiles, cells):
        """First reachable cell (BFS order = nearest) for each case."""
        found = {}
        for x, y in cells:
            # Cast only from plain floor away from the entry door: LinkItem_PortalRod ignores Y
            # while $6C (doorway) is set, and in $059 it stayed set 24 px inside the door (cases11/12).
            if not all(tiles.attr(x + dx, y + dy) in SAFE for dx, dy in SAFE_PROBES):
                continue
            if abs(x - cells[0][0]) + abs(y - cells[0][1]) < 32:
                continue
            for d in range(4):
                out, land, frames, pit_px, stop = fly(tiles.attr, x, y, d)
                if 'pit' not in found and out.startswith('land') and gap_px(tiles.attr, x, y, d, land) >= GAP_MIN:
                    for bd in (OPPOSITE[d],) + tuple(e for e in range(4) if e not in (d, OPPOSITE[d])):
                        back = fly(tiles.attr, x, y, bd)
                        if back[0].startswith('land') and abs(land[0] - back[1][0]) <= WARP_SPAN[0] \
                                and abs(land[1] - back[1][1]) <= WARP_SPAN[1]:
                            found['pit'] = dict(cell=[x, y], dir=d, land=list(land), pit_px=pit_px,
                                                back_dir=bd, back_land=list(back[1]))
                            break
                if 'wall' not in found and out == 'land-wall' and pit_px == 0:
                    found['wall'] = dict(cell=[x, y], dir=d, land=list(land), stop_attr=stop)
                if 'fizzle' not in found and out == 'fizzle' and pit_px >= RANGE - MIN_DIST[d]:
                    found['fizzle'] = dict(cell=[x, y], dir=d, pit_px=pit_px)
            if len(found) == 3:
                break
        return found

    def entrances(self):
        warps = dqf.OracleCheats(self.b).warps
        # Overworld areas $40+ are the Eon Abyss, where Link is the GBC form; skip them.
        return [e for e in warps['entrances'] if int(e['room'], 16) < 0x200
                and e.get('area') is not None and int(str(e['area']), 16) < 0x40
                and int(str(e['id']), 16) >= int(self.args.scan_from, 16)]

    def enter(self, eid):
        res = dqf.OracleCheats(self.b).warp_entrance(eid)
        self.fixture(f'warp_entrance {eid}')
        if not res.get('ok', True) or not self.wait_play():
            raise RuntimeError(f'entrance {eid} did not reach play: {res}')
        time.sleep(0.5)
        if self.r(0x7E001B) != 1:
            raise RuntimeError(f'entrance {eid} is not indoors')
        return res

    def assert_minish_link(self, where):
        gbc, form = self.r(GBC_FLAG), self.r(MASK_FORM)
        ok = gbc == 0 and form != 6
        self.result['checks'].append({'name': f'Minish Cap Link at {where}', 'observed': {'$0FFF': gbc, '$02B2': form},
                                      'expected': '$0FFF==0 and $02B2!=6', 'matches_variant_expectation': ok})
        self.persist()
        if not ok:
            raise RuntimeError(f'not Minish Cap Link at {where}: $0FFF={gbc} $02B2={form}')

    # -- casting -----------------------------------------------------------
    def rod_ready(self, magic):
        self.equip(0x19, 0x0D, 'Portal Rod')
        self.w(dqf.PORTAL_OWNED, 1, 'Portal Rod owned')
        self.w(MAGIC, magic, f'magic {magic:02X}')
        self.w(0x7EF37B, 0, 'full magic cost')

    def portals(self):
        out = []
        for s in self.sprites():
            if s['id'] == PORTAL:
                i = s['slot']
                s.update(action=self.r(SPR_ACTION + i), color=self.r(SPR_MISC_A + i) & 1)
                out.append(s)
        return out

    def cast(self, d, label, flight_frames):
        """Face d, press Y while paused, step frames; save in-flight and landed frames."""
        self.w(FACING, FACING_OF[d], f'face {NAMES[d]} ({label})')
        self.shot(f'{label}_before_cast')
        magic_before = self.r(MAGIC)
        self.b.pause()
        trace = []
        try:
            self.b.press_button('y', frames=2)
            for f in range(flight_frames + 40):
                self.b.run_frames(1)
                bolts = [p for p in self.portals() if p['action'] == SHOT_ACTION]
                trace.append({'f': f, 'frame_counter': self.r(0x7E001A), 'magic': self.r(MAGIC), 'bolts': bolts,
                              'portals': [p for p in self.portals() if p['action'] != SHOT_ACTION]})
                if f == max(4, flight_frames // 2):
                    self.shot(f'{label}_bolt_in_flight')
        finally:
            self.b.resume()
        time.sleep(0.3)
        self.shot(f'{label}_after_cast')
        flew = [t for t in trace if t['bolts']]
        self.result.setdefault('traces', {})[label] = {'magic_before': magic_before, 'frames_with_bolt': len(flew),
                                                       'first': flew[0] if flew else None,
                                                       'last': flew[-1] if flew else None, 'end': trace[-1]}
        self.persist()
        return magic_before, trace

    def go_to(self, cell, label):
        at = self.walk_to(*cell)
        if abs(at[0] - cell[0]) > 2 or abs(at[1] - cell[1]) > 2:
            # The room model ignores pots and other object blockers; the case tests the bolt,
            # not the route, so place Link on the planned cell and record it.
            self.fixture(f'{label}: walk stopped at {at} (object in the way); placed Link at {cell}')
            self.w16(LINK_X, cell[0], f'{label}: Link X')
            self.w16(LINK_Y, cell[1], f'{label}: Link Y')
            time.sleep(0.3)
            at = [self.r16(LINK_X), self.r16(LINK_Y)]
            if at != list(cell):
                raise RuntimeError(f'{label}: could not place Link at {cell}: {at}')
        return at

    # -- cases -------------------------------------------------------------
    def case_room(self, eid, name):
        self.enter(eid)
        self.assert_minish_link(f'{name} entry {eid}')
        # Room enemies knock Link off the planned cell between casts (cases6: an enemy on the
        # $098 rail pushed him into the pit). The cases test the bolt, so clear them.
        for s in self.sprites():
            if s['id'] != PORTAL:
                self.w(SPR_STATE + s['slot'], 0, f"{name}: clear sprite {s['id']:02X} slot {s['slot']}")
        tiles = self.grid()
        start = [self.r16(LINK_X), self.r16(LINK_Y)]
        spot = self.find_cases(tiles, self.reachable(tiles, start)).get(name)
        self.event(f'{name} plan', entrance=eid, room=f'{self.r16(0x7E00A0):03X}', start=start, spot=spot)
        if not spot:
            raise RuntimeError(f'entrance {eid} has no {name} spot')
        self.go_to(spot['cell'], name)
        if self.r(0x7E006C):
            raise RuntimeError(f'{name}: Link is in a doorway ($6C={self.r(0x7E006C):02X}); the rod cannot fire here')
        # Re-plan from where Link actually stands (the walk can end 1 px off).
        x, y = self.r16(LINK_X), self.r16(LINK_Y)
        return tiles, spot, x, y

    def check_pit(self, eid):
        tiles, spot, x, y = self.case_room(eid, 'pit')
        out, land, frames, pit_px, _ = fly(tiles.attr, x, y, spot['dir'])
        if not (out.startswith('land') and pit_px >= 32):
            raise RuntimeError(f'pit spot changed after the walk: {out} {pit_px}')
        gap = gap_px(tiles.attr, x, y, spot['dir'], land)
        self.event('pit bolt path', cell=[x, y], landing=list(land), gap_px=gap,
                   attrs=path_attrs(tiles.attr, x, y, spot['dir'], land))
        self.check('pit: a full-body pit gap of 3+ tiles lies between the cell and the landing',
                   gap >= GAP_MIN, {'candidate': True})
        self.rod_ready(0x80)
        self.cast(spot['dir'], 'pit_blue', frames)
        p = self.portals()
        self.check('pit: blue portal opens at the predicted spot past the pit',
                   [[s['x'], s['y'], s['action']] for s in p], {'candidate': [[land[0], land[1], 1]]})
        # Link can drift after the first cast; predict the second bolt from where he stands now.
        bx, by = self.r16(LINK_X), self.r16(LINK_Y)
        back = fly(tiles.attr, bx, by, spot['back_dir'])
        self.event('pit orange plan', link=[bx, by], outcome=back[0], land=list(back[1]))
        self.cast(spot['back_dir'], 'pit_orange', back[2])
        p = self.portals()
        orange = [s for s in p if s['action'] == 2]
        self.check('pit: orange portal opens at the planned spot',
                   [[s['x'], s['y']] for s in orange], {'candidate': [list(back[1])]})
        self.shot('pit_portal_pair_open')
        before = [self.r16(LINK_X), self.r16(LINK_Y)]
        # cases13: walk_to kept walking toward the orange x after the warp fired and moved
        # Link 39 px off the blue. Step toward the orange in short presses like a player and
        # stop on the first step that puts Link near the blue (the warp) or that stalls.
        toward = NAMES[spot['back_dir']]
        self.event('pit warp context', link=before,
                   cam=[self.r16(0x7E00E2), self.r16(0x7E00E8)], pages=[self.r(0x7E0021), self.r(0x7E0023)],
                   blue=land, orange=list(back[1]))
        steps, stall, prev = [], 0, before
        for _ in range(60):
            self.press(toward, 2)
            cur = [self.r16(LINK_X), self.r16(LINK_Y)]
            steps.append(cur)
            if abs(cur[0] - land[0]) <= 16 and abs(cur[1] - land[1]) <= 16:
                break
            stall = stall + 1 if cur == prev else 0
            if stall >= 4:
                break
            prev = cur
        self.event('pit warp steps', steps=steps)
        self.wait_play(6)
        time.sleep(0.6)
        after = [self.r16(LINK_X), self.r16(LINK_Y)]
        self.shot('pit_after_warp')
        self.event('pit warp', before=before, after=after, blue=land)
        self.check('pit: Link warps across the pit to the blue portal',
                   abs(after[0] - land[0]) <= 16 and abs(after[1] - land[1]) <= 16,
                   {'candidate': True})

    def check_wall(self, eid):
        tiles, spot, x, y = self.case_room(eid, 'wall')
        out, land, frames, _, stop = fly(tiles.attr, x, y, spot['dir'])
        if out != 'land-wall':
            raise RuntimeError(f'wall spot changed after the walk: {out}')
        self.rod_ready(0x80)
        self.cast(spot['dir'], 'wall', frames)
        p = self.portals()
        self.check('wall: portal opens on the last safe floor before the wall',
                   [[s['x'], s['y'], s['action']] for s in p], {'candidate': [[land[0], land[1], 1]]})
        d = spot['dir']
        gap = abs((x + STEP[d][0] * SPEED * frames) - land[0]) + abs((y + STEP[d][1] * SPEED * frames) - land[1])
        # "Last safe floor before the wall": the landing passes all 10 safe probes and every
        # bolt step after it, up to the stop, fails them (exact, from the live collision map).
        def safe(px, py):
            return all(tiles.attr(px + dx, py + dy) in SAFE for dx, dy in SAFE_PROBES)
        sx, sy = x + STEP[d][0] * SPEED * frames, y + STEP[d][1] * SPEED * frames
        between, (px, py) = [], land
        while (px, py) != (sx, sy):
            px, py = px + STEP[d][0] * SPEED, py + STEP[d][1] * SPEED
            between.append({'at': [px, py], 'safe': safe(px, py)})
        self.event('wall last-safe rule', landing=list(land), stop=[sx, sy], gap=gap, steps_after_landing=between)
        self.check('wall: landing is the last safe step before the stop',
                   safe(*land) and not any(b['safe'] for b in between), {'candidate': True})
        self.event('wall stop', stop_attr=f'{stop:02X}', landing=land, gap=gap)

    def check_fizzle(self, eid):
        tiles, spot, x, y = self.case_room(eid, 'fizzle')
        out, _, frames, pit_px, _ = fly(tiles.attr, x, y, spot['dir'])
        if out != 'fizzle':
            raise RuntimeError(f'fizzle spot changed after the walk: {out}')
        self.rod_ready(0x40)
        selector = self.r(SELECTOR)
        magic_before, trace = self.cast(spot['dir'], 'fizzle', frames)
        low = min(t['magic'] for t in trace)
        self.check('fizzle: the bolt flew (sprite seen in action 7)',
                   any(t['bolts'] for t in trace), {'candidate': True})
        self.check('fizzle: magic was spent during flight', low < magic_before, {'candidate': True})
        self.check('fizzle: magic returns to the pre-cast value', self.r(MAGIC), {'candidate': magic_before})
        self.check('fizzle: no portal opened', self.portals(), {'candidate': []})
        self.check('fizzle: color selector unchanged', self.r(SELECTOR), {'candidate': selector})
        self.event('fizzle', pit_px=pit_px, magic_before=magic_before, magic_low=low)

    # -- scan --------------------------------------------------------------
    def scan(self):
        rows = []
        only = {int(i, 16) for i in self.args.scan_ids.split(',')} if self.args.scan_ids else None
        for e in self.entrances():
            if only is not None and int(str(e['id']), 16) not in only:
                continue
            try:
                self.enter(e['id'])
                tiles = self.grid()
                start = [self.r16(LINK_X), self.r16(LINK_Y)]
                found = self.find_cases(tiles, self.reachable(tiles, start))
                minish = self.r(GBC_FLAG) == 0 and self.r(MASK_FORM) != 6
                rows.append({'id': e['id'], 'name': e['name'], 'room': f'{self.r16(0x7E00A0):03X}',
                             'start': start, 'minish_link': minish, **found})
                print(e['id'], e['name'], sorted(found), 'minish' if minish else 'GBC', flush=True)
                if self.args.probe:
                    px, py, pd, lx, ly = (int(v) for v in self.args.probe.split(','))
                    pa = path_attrs(tiles.attr, px, py, pd, (lx, ly))
                    self.event('probe path', entrance=e['id'], gap_px=gap_px(tiles.attr, px, py, pd, (lx, ly)), attrs=pa)
                    print('  probe EE', self.r(0x7E00EE), 'room', f'{self.r16(0x7E00A0):03X}', 'link',
                          [self.r16(LINK_X), self.r16(LINK_Y)], ' '.join(f"{a['at'][0]}:{a['lead']}" for a in pa), flush=True)
                    for base in (0x7F2000, 0x7F3000):
                        buf = self.b.read_block(base, 0x1000)
                        row = ((py + LEAD_Y[pd]) & 0x1FF) >> 3
                        print(f'  {base:06X} row {row} cols 8-39', buf[row * 64 + 8: row * 64 + 40].hex(' '), flush=True)
                if 'pit' in found:
                    sp = found['pit']
                    sp['gap_px'] = gap_px(tiles.attr, *sp['cell'], sp['dir'], sp['land'])
                    sp['attrs'] = path_attrs(tiles.attr, *sp['cell'], sp['dir'], sp['land'])
                    print('  pit', sp['cell'], NAMES[sp['dir']], sp['land'], 'gap', sp['gap_px'],
                          ' '.join(a['lead'] for a in sp['attrs']), flush=True)
            except Exception as exc:
                rows.append({'id': e['id'], 'name': e['name'], 'error': str(exc)})
                print(e['id'], 'ERROR', exc, flush=True)
            self.result['scan'] = rows
            self.persist()

    def run(self):
        try:
            self.preflight()
            self.launch()
            self.boot_file2()
            self.assert_minish_link('file 2 load')
            if self.args.scan:
                self.scan()
            for name, eid in (('pit', self.args.pit), ('wall', self.args.wall), ('fizzle', self.args.fizzle)):
                if not eid:
                    continue
                try:
                    getattr(self, f'check_{name}')(eid)
                except Exception as exc:
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
    ap.add_argument('--rom', type=Path, required=True)
    ap.add_argument('--srm', type=Path, required=True)
    ap.add_argument('--app', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--scan', action='store_true', help='list rooms with each case')
    ap.add_argument('--pit', help='entrance id for the pit case')
    ap.add_argument('--wall', help='entrance id for the wall case')
    ap.add_argument('--fizzle', help='entrance id for the fizzle case')
    ap.add_argument('--probe', help='x,y,dir,landx,landy: log lead-probe attrs on that path in each scanned room')
    ap.add_argument('--scan-ids', help='comma list of entrance ids to scan (hex)')
    ap.add_argument('--scan-from', default='0x00', help='first entrance id to scan')
    args = ap.parse_args()
    args.variant = 'candidate'
    sys.exit(0 if ShotRun(args).run() else 1)


if __name__ == '__main__':
    main()
