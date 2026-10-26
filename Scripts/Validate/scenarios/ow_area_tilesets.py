#!/usr/bin/env python3
"""Headless Mesen2 check of !ENABLE_OW_AREA_TILESETS (Overworld/area_tilesets.asm).

candidate = flag on. The four OverworldTileTypes reads use the WRAM copy at
$7FD000, and every overworld area load refills it (ROM table + the area
profile's tile type ranges) and DMAs the profile's sheets.
control = flag off (the old hardcoded boat load in Overworld/custom_gfx.asm).

One emulator boot, file 2 of the given save:
  1. file load       candidate: copy == expected for the load area.
  2. warp $38        VRAM $5800/$A000 hold gfx/boat.bin/boat2.bin (both builds);
                     candidate: copy == ROM table + --expect-types ranges.
  2b. door exit      file 2 loads indoors: candidate fills the copy with $01,
                     then Link walks out (Overworld_LoadMusicIfNeeded path).
  3. --transition    walk east from the $33 warp into $3D (scroll transition;
                     the discord_quick_fixes.py whirlpool route), then back
                     west: the copy follows each area, no boat sheets. A diag
                     build with $3D in --profile-areas changes types on the way.
  4. warp $33        VRAM $5800 is not boat.bin; candidate: copy == ROM table.
  5. solid copy      fixture: 512 x $01 into $7FD000; Link pushes down, left,
                     right. candidate: no movement; control: moves. Re-warp $33:
                     both move again.
  6. assisted reset reset; file 2 again; helper warp if indoors.
                     This is reset/reload plus assisted warp, not save/reopen.

--lifecycle-only instead performs actual Save & Quit, cold-process file load
from game-written SRAM, and death/Continue. See FIX_REVIEW_REQUEST.md for the
bounded reviewed episode. No helper warp may follow the cold launch.
  7. presence        every EXPECT check for the variant ran (scroll checks only
                     with --transition; file load or door exit, whichever ran).

Declared fixtures (result.json "fixtures"): test SRAM file 2, area warps, the
no-damage flag during walks, the $7FD000 writes.

  MESEN2_OOS_ROOT=~/src/hobby/mesen2-oos python3 Scripts/Validate/scenarios/ow_area_tilesets.py \
      --variant candidate --rom Roms/oos168x.sfc --srm <file.srm> --app <Mesen2 OOS.app> --out <dir>

Rules this follows (agent_board.md): headless only, own isolated profile and
socket, stop only the owned PID with SIGTERM.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goron_heartpiece_flag as gh  # noqa: E402
from goron_heartpiece_flag import OracleCheats, OverworldTiles  # noqa: E402

REPO = gh.REPO
INDOORS, AREA, NO_DAMAGE = gh.INDOORS, gh.AREA, gh.NO_DAMAGE

COPY = 0x7FD000  # AreaTileset_TileTypes
ROM_TYPES = 0x0E9459  # OverworldTileTypes
BOAT_AREAS = (0x30, 0x38)  # profile 1 in AreaTileset_AreaProfile; the old boat code's areas
BOAT, NORMAL, EAST_OF_NORMAL = 0x38, 0x33, 0x3D
EAST_EDGE = (2528, 3752)  # $33 east edge; discord_quick_fixes.py check_whirlpool
NORMAL_BOUNDS = (0x0600, 0x0C00, 0x09F0, 0x0FE8)  # large area $33; discord_quick_fixes.py check_whirlpool
SHEETS = ((0x5800, REPO / 'Overworld' / 'gfx' / 'boat.bin'),  # VRAM word $2C00
          (0xA000, REPO / 'Overworld' / 'gfx' / 'boat2.bin'))  # VRAM word $5000

EXPECT = {
    'file load: copy == expected': {'candidate': True},
    'door exit: copy == expected': {'candidate': True},
    'warp $38: VRAM $5800 == boat.bin': {'candidate': True, 'control': True},
    'warp $38: VRAM $A000 == boat2.bin': {'candidate': True, 'control': True},
    'warp $38: copy == expected': {'candidate': True},
    'scroll $33->$3D: VRAM $5800 == boat.bin': {'candidate': False, 'control': False},
    'scroll $33->$3D: copy == expected': {'candidate': True},
    'scroll $3D->$33: VRAM $5800 == boat.bin': {'candidate': False, 'control': False},
    'scroll $3D->$33: copy == expected': {'candidate': True},
    'warp $33: VRAM $5800 == boat.bin': {'candidate': False, 'control': False},
    'warp $33: copy == expected': {'candidate': True},
    'solid copy: Link moved': {'candidate': False, 'control': True},
    're-warp $33: copy == expected': {'candidate': True},
    're-warp $33: Link moved': {'candidate': True, 'control': True},
    'reopen: copy == expected': {'candidate': True},
    'reopen: Link moved': {'candidate': True, 'control': True},
}


class Run(gh.Run):
    def __init__(self, args):
        super().__init__(args)
        data = Path(args.rom).read_bytes()
        o = ((ROM_TYPES >> 16) & 0x7F) * 0x8000 + (ROM_TYPES & 0x7FFF)
        self.rom_types = data[o:o + 0x200]
        self.profile_types = bytearray(self.rom_types)
        # control: the old boat code only knows $30/$38
        self.profile_areas = args.profile_areas if args.variant == 'candidate' else BOAT_AREAS
        for first, values in args.expect_types:
            self.profile_types[first:first + len(values)] = values

    def preflight(self):
        super().preflight()
        self.result['harness_sha256'] = gh.sha(Path(__file__))
        self.result['expect_types'] = [f'{f:03X}:{v.hex()}' for f, v in self.args.expect_types]
        self.result['profile_areas'] = [f'{a:02X}' for a in self.profile_areas]
        self.persist()

    def check(self, name, observed, expected=None):
        if expected is None:
            expected = EXPECT[name].get(self.args.variant)
        if expected is None:
            return True  # copy checks: the control build has no copy
        ok = observed == expected
        self.result['checks'].append({'name': name, 'observed': observed, 'expected': expected,
                                      'matches_expectation': ok})
        self.persist()
        print(('PASS ' if ok else 'FAIL ') + name, observed, flush=True)
        return ok

    def require(self, name, observed, expected=True):
        if not self.check(name, observed, expected):
            raise RuntimeError(f'{name}: expected {expected!r}, got {observed!r}')

    def wait_state(self, name, predicate, seconds=20):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            state = (self.r(gh.MODULE), self.r(gh.SUBMODULE), self.r(INDOORS), self.r(AREA))
            if state != last:
                self.event(name, state=list(state))
                last = state
            if predicate(state):
                return state
            time.sleep(0.1)
        raise RuntimeError(f'{name} timed out after {seconds}s: {last}')

    def lifecycle_copy(self, label):
        # No warp, movement or other repair before this snapshot.
        state = (self.r(gh.MODULE), self.r(gh.SUBMODULE), self.r(INDOORS), self.r(AREA))
        self.require(f'{label}: outdoor play area40', state, (9, 0, 0, 0x40))
        got = self.copy()
        (self.out / f'{label}-types.bin').write_bytes(got)
        self.event(f'{label}: first outdoor snapshot', state=list(state),
                   copy_sha256=hashlib.sha256(got).hexdigest())
        if self.args.variant == 'candidate':
            self.require(f'{label}: live types', got == self.rom_types)
        self.shot(label)

    def lifecycle(self):
        """Fixture-only: game owns save, load and Continue dispatch."""
        self.warp(0x40, 'initial outdoor save fixture, before lifecycle boundary')
        self.lifecycle_boundary = True
        self.w(0x7EF3CA, 0x40, 'SavedWorld: outdoor Module05 branch, room20 exit -> area40')
        # A saved marker distinguishes the newly written file from the input SRAM.
        marker = (self.r16(0x7EF360) + 1) % 999
        self.w(0x7EF360, marker & 255, 'rupee save marker low')
        self.w(0x7EF361, marker >> 8, 'rupee save marker high')
        before = bytes(self.b.read_block(0, 0x2000, memtype='sram'))
        self.require('input SRAM read length', len(before), 0x2000)
        self.press('select', 1)
        self.wait_state('save menu', lambda q: q[:2] == (0x0E, 0x0B))
        # RenderText needs time to finish drawing before accepting a choice.
        time.sleep(1)
        for _ in range(4):
            if self.r16(0x7E1CE8) == 1:
                break
            self.press('down', 1)
            time.sleep(0.2)
        self.require('Save & Quit menu choice', self.r16(0x7E1CE8), 1)
        self.press('a', 1)
        self.wait_state('Save & Quit reaches title', lambda q: q[0] == 0, 25)
        saved = bytes(self.b.read_block(0, 0x2000, memtype='sram'))
        self.require('saved SRAM read length', len(saved), 0x2000)
        self.require('game changed SRAM', saved != before)
        (self.out / 'input-sram.bin').write_bytes(before)
        # File2's primary/backup 0x500-byte records and checksum are game-produced.
        for offset in (0x500, 0x1400):
            record = saved[offset:offset + 0x500]
            self.require(f'slot2 {offset:04X} checksum',
                         sum(int.from_bytes(record[i:i+2], 'little') for i in range(0, 0x500, 2)) & 0xFFFF,
                         0x5A5A)
            self.require(f'slot2 {offset:04X} marker', int.from_bytes(record[0x360:0x362], 'little'), marker)
            self.require(f'slot2 {offset:04X} SavedWorld', record[0x3CA], 0x40)
        artifact = self.out / 'game-written.srm'
        artifact.write_bytes(saved)
        old_pid = self.pid
        self.close()
        self.require('first process exited', gh.identity(old_pid) != self.pid_identity)
        disk = self.home / 'Saves' / f'gh-{self.args.variant}.srm'
        self.require('flushed disk SRAM equals game SRAM', disk.read_bytes() == saved)
        self.result['saved_sram'] = {'path': str(artifact), 'sha256': gh.sha(artifact)}
        self.result['first_emulator'] = self.result['emulator']
        self.result['cold_reload_uses_game_written_sram'] = True
        self.persist()
        self.pid = None
        self.b = None
        (self.out / 'launch.log').rename(self.out / 'first-launch.log')
        self.launch()  # Same isolated profile, fresh process; no preflight/reseed.
        self.require('cold process differs', self.pid != old_pid)
        self.boot_file2()
        self.lifecycle_copy('cold-load')
        self.require('cold-load saved marker', self.r16(0x7EF360), marker)
        # Pending damage is a declared fixture; Link_ControlHandler performs death.
        # No module/submodule, PC, spawn, Continue choice or loader writes.
        self.w(NO_DAMAGE, 0, 'enable actual damage processing')
        self.w(0x7E0055, 0, 'cape off for damage processing')
        for addr in range(0x7EF35C, 0x7EF360):
            self.w(addr, 0, 'no bottled fairy revival')
        self.w(0x7EF36D, 8, 'one heart before lethal pending damage')
        self.w(0x7E0373, 8, 'pending damage consumed by Link_ControlHandler')
        self.wait_state('actual Game Over menu', lambda q: q[:2] == (0x12, 9), 30)
        self.fill_copy('stale collision during Game Over; Continue must refill')
        # B0=2 is Continue without saving (09F5DA); select cycles 0,1,2.
        for _ in range(3):
            if self.r(0x7E00B0) == 2:
                break
            self.press('select', 1)
            time.sleep(0.25)
        self.require('Continue choice', self.r(0x7E00B0), 2)
        self.press('start', 1)
        self.wait_state('Continue outdoor play', lambda q: q[:3] == (9, 0, 0), 25)
        self.lifecycle_copy('continue')
        self.require('Continue positive health', self.r(0x7EF36D) > 0)

    # -- reads -------------------------------------------------------------
    def copy(self):
        return bytes(self.b.read_block(COPY, 0x200))

    def check_copy(self, label):
        area = self.r(AREA)
        expected = self.profile_types if area in self.profile_areas else self.rom_types
        got = self.copy()
        diff = [f'{i:03X}:{got[i]:02X}/{expected[i]:02X}' for i in range(0x200) if got[i] != expected[i]]
        self.event(f'{label}: copy', area=f'{area:02X}', profile=int(area in self.profile_areas),
                   differs=diff[:16], differ_count=len(diff),
                   ranges_applied=[f'{f:03X}:{v.hex()}' for f, v in self.args.expect_types
                                   if area in self.profile_areas])
        self.check(f'{label}: copy == expected', not diff)

    def vram(self, addr, size):
        out = b''
        for off in range(0, size, 0x800):
            out += bytes(self.b.read_block(addr + off, 0x800, memtype='vram'))
        return out

    def check_sheets(self, label, only_first=False):
        for addr, path in SHEETS[:1] if only_first else SHEETS:
            want = path.read_bytes()
            self.check(f'{label}: VRAM ${addr:04X} == {path.name}', self.vram(addr, len(want)) == want)

    # -- movement ----------------------------------------------------------
    def warp(self, area, why):
        if getattr(self, 'lifecycle_boundary', False):
            raise RuntimeError('helper warp forbidden after lifecycle boundary')
        res = OracleCheats(self.b).warp_area(area)
        self.fixture(f'warp_area 0x{area:02X} ({why})')
        self.event('warp', why=why, response=res)
        if not res.get('ok') or not self.wait_play():
            raise RuntimeError(f'warp to 0x{area:02X} failed: {res}')
        time.sleep(0.5)

    def moved(self):
        """Push down, left, right for 12 frames each; True if Link moved 4 px or more."""
        start = self.link()
        for button in ('down', 'left', 'right'):
            self.b.write_memory(NO_DAMAGE, 1)
            self.press(button, 12)
            at = self.link()
            if abs(at[0] - start[0]) + abs(at[1] - start[1]) >= 4:
                self.event('moved', button=button, start=start, at=at)
                return True
        self.event('did not move', start=start, at=self.link())
        return False

    def fill_copy(self, why):
        if not self.b.write_block(COPY, bytes([0x01]) * 0x200):
            raise RuntimeError('write to $7FD000 failed')
        self.fixture(f'$7FD000-$7FD1FF = $01 ({why})')

    def walk_route(self, goal, bounds):
        """gh.Run.travel with other bounds: OverworldTiles route, controller walk; on a
        stall, block 24 px ahead and re-plan (up to 4 times)."""
        blocked = []
        for _ in range(5):
            here = tuple(self.link())
            path = OverworldTiles(self, self.rom).route(here, goal, bounds, blocked=blocked)
            self.event('route', goal=list(goal), waypoints=path, blocked=[list(b) for b in blocked])
            if not path:
                return False
            for x, y in path[1:]:
                self.b.write_memory(NO_DAMAGE, 1)
                at = self.walk_to(x, y)
                if abs(at[0] - x) > 6 or abs(at[1] - y) > 6:
                    dx, dy = (x > at[0]) - (x < at[0]), (y > at[1]) - (y < at[1])
                    cx, cy = at[0] + 8 + dx * 20, at[1] + 16 + dy * 20
                    blocked.append((cx - 12, cy - 12, cx + 12, cy + 12))
                    self.event('walk stalled; re-planning', at=at, heading=[x, y])
                    break
            else:
                return True
        return False

    def cross(self, button, target):
        for _ in range(40):
            self.b.write_memory(NO_DAMAGE, 1)
            self.press(button, 8)
            if self.r(AREA) == target:
                break
        if self.r(AREA) != target or not self.wait_play():
            return False
        time.sleep(0.5)
        return True

    def transition(self):
        if not self.walk_route(EAST_EDGE, NORMAL_BOUNDS):
            self.event('transition skipped: no route to the east edge of $33', link=self.link())
            return
        if not self.cross('right', EAST_OF_NORMAL):
            self.event('transition skipped: east crossing failed', link=self.link(), area=f'{self.r(AREA):02X}')
            return
        self.event('scrolled east (controller)', link=self.link(), area=f'{self.r(AREA):02X}')
        self.shot('scroll_east')
        self.check_sheets('scroll $33->$3D', only_first=True)
        self.check_copy('scroll $33->$3D')
        if not self.cross('left', NORMAL):
            self.event('transition back skipped: west crossing failed', link=self.link())
            return
        self.event('scrolled west (controller)', link=self.link(), area=f'{self.r(AREA):02X}')
        self.shot('scroll_west')
        self.check_sheets('scroll $3D->$33', only_first=True)
        self.check_copy('scroll $3D->$33')

    def door_exit(self):
        """Walk out of the file 2 start room with controller input."""
        if self.args.variant == 'candidate':
            self.fill_copy('stale copy before the door exit')
        for _ in range(30):
            if not self.r(INDOORS):
                break
            self.b.write_memory(NO_DAMAGE, 1)
            self.press('down', 8)
        if self.r(INDOORS) or not self.wait_play():
            self.event('door exit skipped: still indoors', link=self.link())
            return
        time.sleep(0.5)
        self.event('door exit (controller)', area=f'{self.r(AREA):02X}', link=self.link())
        self.shot('door_exit')
        self.check_copy('door exit')

    # -- case --------------------------------------------------------------
    def run_case(self):
        if self.args.lifecycle_only:
            self.lifecycle()
            return
        self.event('file load', indoors=self.r(INDOORS), area=f'{self.r(AREA):02X}', link=self.link())
        indoors = self.r(INDOORS)
        if indoors:
            self.door_exit()
        else:
            self.check_copy('file load')

        self.warp(BOAT, 'boat profile area')
        self.shot('warp_38')
        self.check_sheets('warp $38')
        self.check_copy('warp $38')

        self.warp(NORMAL, 'profile 0 area')
        self.shot('warp_33')
        self.check_sheets('warp $33', only_first=True)
        self.check_copy('warp $33')
        if self.args.transition:
            self.transition()
            self.warp(NORMAL, 'back to the $33 landing')

        before = self.copy()
        self.fill_copy('every char solid')
        self.check('solid copy: Link moved', self.moved())
        if self.args.variant == 'control':
            self.b.write_block(COPY, before)
            self.fixture('$7FD000-$7FD1FF restored (control)')
        self.warp(NORMAL, 'reload after the solid copy')
        self.check_copy('re-warp $33')
        self.check('re-warp $33: Link moved', self.moved())

        self.fill_copy('dirty copy before reset')
        if not self.b.reset():
            raise RuntimeError('reset failed')
        time.sleep(1.0)
        self.event('assisted reset, not save/reopen', copy_all_01=self.copy() == bytes([0x01]) * 0x200)
        self.boot_file2()
        if self.r(INDOORS):
            self.event('reopen: file 2 loads indoors; warp to $33')
            self.warp(NORMAL, 'reopen lands indoors')
        self.shot('reopen')
        self.check_copy('reopen')
        self.check('reopen: Link moved', self.moved())

        skip = {'file load: copy == expected' if indoors else 'door exit: copy == expected'}
        if not self.args.transition:
            skip |= {name for name in EXPECT if name.startswith('scroll ')}
        ran = {c['name'] for c in self.result['checks']}
        missing = sorted(name for name, by in EXPECT.items()
                         if self.args.variant in by and name not in skip and name not in ran)
        self.check('presence: expected checks missing', missing, [])


def ranges(text):
    out = []
    for item in filter(None, text.split(',')):
        first, values = item.split(':')
        out.append((int(first, 16), bytes.fromhex(values)))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--variant', required=True, choices=('candidate', 'control'))
    p.add_argument('--rom', required=True)
    p.add_argument('--srm', required=True)
    p.add_argument('--app', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--expect-types', type=ranges, default=[],
                   help='tile type ranges of the --profile-areas in the ROM, e.g. 000:0200,1F8:0102 (hex)')
    p.add_argument('--profile-areas', type=lambda t: tuple(int(a, 16) for a in t.split(',')),
                   default=BOAT_AREAS, help='areas whose copy gets the --expect-types ranges (hex), default 30,38')
    p.add_argument('--lifecycle-only', action='store_true',
                   help='actual Save & Quit, cold outdoor load, death/Continue; review required before run')
    p.add_argument('--transition', action='store_true', help='also walk $33 -> $3D -> $33')
    return Run(p.parse_args()).run()


if __name__ == '__main__':
    sys.exit(main())
