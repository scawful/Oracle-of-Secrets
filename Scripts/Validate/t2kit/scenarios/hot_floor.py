"""Hot floor tile type $DE and thin ice (crumble tag $34) in D1 room $4A.

Every case expects the new behavior, so a ROM without it shows as FAIL.

  hot_normal    $DE cells north of Link; walk onto them (controller). Expect
                $07FFA0 (TileBehavior_HotFloor) and $07DDCA (TileBehavior_SpikeFloor)
                hits and a health drop.
  hot_airborne  Feather-equivalent hop in place, then $DE under Link while $5D == $02.
                Expect $07FFA0 hits with $5D == 2, no $07DDCA while airborne, no damage.
  thin_ice      $AE = $34 in room $4A; Link's 16 px foot cell S and the cell north of it
                (S-1) get an ice char. Standing still does not crack; stepping off cracks S
                ($0CCC) and about 40 frames later S and S-1 are pit ($01E9, $7F2000 = $20).
"""
import time

from t2kit.session import FRAME, LINK_Y, MODULE

FIXTURE = 'goron-mines-open'
CASES = ('hot_normal', 'hot_airborne', 'thin_ice')

HEALTH, STATE_5D, HEIGHT_24, JUMP_46, TAG1 = 0x7EF36D, 0x7E005D, 0x7E0024, 0x7E0046, 0x7E00AE
DMG_0373, IFRAMES, NO_DAMAGE = 0x7E0373, 0x7E031F, 0x7E037B
TILEMAP, ATTR, COLL = 0x7E2000, 0x7EFE00, 0x7F2000
HOT, SPIKE = 0x07FFA0, 0x07DDCA
BP_HOT = {HOT: 'TileBehavior_HotFloor', SPIKE: 'TileBehavior_SpikeFloor'}
CRUMBLE, CRACK, BREAK = 0x2C8675, 0x2CF8D8, 0x2CF931
BP_ICE = {CRUMBLE: 'CrumbleFloorTag_Main', CRACK: 'ThinIce_Track .slot (crack + fuse)', BREAK: 'ThinIce_Break'}
# LinkItem_JumpFeather's writes (Items/jump_feather.asm), no directional input.
FEATHER = ((0x7E005D, 2), (0x7E004D, 2), (0x7E0046, 0x20), (0x7E0029, 0x24), (0x7E02C7, 0x24),
           (0x7E0340, 8), (0x7E0067, 8), (0x7E0031, 0), (0x7E0030, 0), (0x7E0027, 0), (0x7E0028, 0))


def state(t):
    return {'frame_1A': t.r(FRAME), '5D': t.r(STATE_5D), '24': t.r(HEIGHT_24), '46': t.r(JUMP_46),
            'health': t.r(HEALTH), 'link': t.link()}


def walkable_up(t, cells):
    """Link's body (x+1..14, y+9..22) stays on walkable tiles for `cells` 16 px steps north."""
    tiles = t.tiles()
    x, y = t.link()
    return all(tiles.attr(x + dx, y - step + dy) in tiles.WALK
               for step in range(0, cells * 16 + 1, 4) for dx in (1, 14) for dy in (9, 22))


def enter(t):
    t.warp(0x26, room=0x4A, label='D1 Mushroom Grotto, room $4A')
    time.sleep(0.5)
    t.clear_enemies()


def set_cells(t, rows, cols, value, why):
    cells = [(tx, ty) for ty in rows for tx in cols]
    orig = {(tx, ty): t.r(COLL + ty * 64 + tx) for tx, ty in cells}
    t.fixture_collision(cells, value, why)
    return orig


def damage_on(t):
    t.invincible = False
    t.fixture_ram(NO_DAMAGE, 0, 'no-damage flag cleared')
    t.w(IFRAMES, 0)


def hot_normal(t):
    enter(t)
    t.check('north path walkable for 4 cells (fixture sanity)', walkable_up(t, 4), True)
    x, y = (v & 0x1FF for v in t.link())  # room-local px
    # 3 tile rows starting 16 px above Link's body top (y+9), as wide as his body.
    top = ((y + 9) >> 3) - 5
    set_cells(t, range(top, top + 3), range((x + 1) >> 3, ((x + 14) >> 3) + 1), 0xDE, 'hot floor')
    damage_on(t)
    h0 = t.r(HEALTH)
    t.screenshot('hot_normal_before')
    hits = []
    for _ in range(8):
        t.b.press_button('up', frames=10)
        hits += t.breaks(BP_HOT, timeout=0.35, keep={HOT: 3}, watch=state, limit=40)
        if t.hit(hits, SPIKE) and t.r(HEALTH) != h0:
            break
    time.sleep(0.6)
    h1 = t.r(HEALTH)
    t.result['breakpoint_hits'] = hits
    t.event('after walk', link=t.link(), health_before=h0, health_after=h1)
    t.screenshot('hot_normal_after')
    t.expect_breakpoint(hits, HOT, '$07FFA0 TileBehavior_HotFloor hit')
    t.expect_breakpoint(hits, SPIKE, '$07DDCA TileBehavior_SpikeFloor hit')
    t.check('health dropped', h1 < h0, True)


def hot_airborne(t):
    enter(t)
    damage_on(t)
    h0 = t.r(HEALTH)
    x, y = (v & 0x1FF for v in t.link())
    t.screenshot('hot_airborne_before')
    t.b.pause()
    for addr, value in FEATHER:
        t.w(addr, value)
    t.fixture('feather-equivalent hop in place: ' + ' '.join(f'${a & 0xFFFF:02X}={v:02X}' for a, v in FEATHER))
    orig = set_cells(t, range((y + 8) >> 3, ((y + 23) >> 3) + 1), range(x >> 3, ((x + 15) >> 3) + 1), 0xDE,
                     'hot floor under Link while airborne; restored before the landing')
    air = {}

    def landed():
        # Restore the floor just before the hop ends ($46 <= 6) so the landing is on normal
        # floor; damage on landing on hot floor is expected behavior, not this case.
        if 'land' in air or (t.r(STATE_5D) == 2 and t.r(JUMP_46) > 6):
            return 'land' in air
        was_paused = t.is_paused()
        t.b.pause()
        air['land'] = {'5D': t.r(STATE_5D), '46': t.r(JUMP_46), '24': t.r(HEIGHT_24), 'health': t.r(HEALTH),
                       'pending_0373': t.r(DMG_0373), 'frame': t.r(FRAME), 'was_paused_at_bp': was_paused}
        for (tx, ty), v in orig.items():
            t.w(COLL + ty * 64 + tx, v)
        t.b.resume()
        return True
    t.b.resume()
    hits = t.breaks(BP_HOT, timeout=0.5, keep={HOT: 10}, watch=state, limit=40, stop=landed)
    for _ in range(50):
        if landed():
            break
        time.sleep(0.02)
    time.sleep(0.5)
    h1 = t.r(HEALTH)
    t.result['breakpoint_hits'] = hits
    t.event('after hop', link=t.link(), health_before=h0, health_after=h1, landing=air.get('land'))
    t.screenshot('hot_airborne_after')
    t.check('$07FFA0 hit while $5D == 02', any(h['pc'] == f'${HOT:06X}' and h['5D'] == 2 for h in hits), True)
    t.check('$07DDCA hit while $5D == 02', any(h['pc'] == f'${SPIKE:06X}' and h['5D'] == 2 for h in hits), False)
    land = air.get('land') or {}
    t.check('restored before landing ($5D still 02 at restore)', land.get('5D'), 2)
    t.check('no pending damage at restore ($0373)', land.get('pending_0373'), 0)
    t.check('health unchanged', h1 == h0, True)


def thin_ice(t):
    enter(t)
    t.guard()
    t.fixture_ram(TAG1, 0x34, f'room $4A tag 1 ${t.r(TAG1):02X} -> $34 (crumble/thin ice; no entrance '
                              f'lands in a room with tag $34)')
    t.check('north path walkable for 4 cells (fixture sanity)', walkable_up(t, 4), True)
    x, y = t.link()
    fy, fx = (y + 16) & 0xFFF0, (x + 8) & 0xFFF0
    attrs = t.b.read_block(ATTR, 0x200)
    tm = t.b.read_block(TILEMAP, 0x2000)
    used = {(tm[i] | tm[i + 1] << 8) & 0x3FF for i in range(0, 0x2000, 2)}
    ice = [ch for ch in range(0x200) if attrs[ch] in (0x0E, 0x0F)]
    if ice:
        ch = ice[0]
        t.fixture(f'ice char ${ch:03X} (existing $7EFE00 attr ${attrs[ch]:02X})')
    else:
        ch = next(ch for ch in range(0x1FF, 0, -1) if ch not in used and attrs[ch] == 0)
        t.fixture_ram(ATTR + ch, 0x0E, f'unused char ${ch:03X} attr = $0E (ice) in $7EFE00')
    cells = [(fy, fx), (fy - 16, fx)]

    def tidx(cy, cx):
        return ((cx & 0x1F0) >> 2) + ((cy & 0x1F0) << 4)

    def cell(cy, cx):
        i = tidx(cy, cx)
        return {'tilemap': f'{t.r16(TILEMAP + i):04X}', 'coll': f'{t.r(COLL + (i >> 1)):02X}'}
    for cy, cx in cells:
        t.w16(TILEMAP + tidx(cy, cx), (t.r16(TILEMAP + tidx(cy, cx)) & 0xFC00) | ch)
    t.fixture(f'$7E2000 top-left word of 16 px cells {[(hex(cx), hex(cy)) for cy, cx in cells]} -> char '
              f'${ch:03X} (tilemap only; graphics unchanged until a crack)')
    t.screenshot('thin_ice_placed')
    stand = t.breaks(BP_ICE, timeout=0.3, watch=state)
    time.sleep(1.5)
    still = cell(*cells[0])
    t.check('tag $34 routine runs (CrumbleFloorTag_Main $2C8675 hit)', t.hit(stand, CRUMBLE), True)
    t.check('standing still: S tilemap unchanged', still['tilemap'] != '0CCC' and still['coll'] != '20', True)
    walk, start_y = [], t.r16(LINK_Y)
    for _ in range(12):
        t.b.press_button('up', frames=6)
        walk += t.breaks({CRACK: BP_ICE[CRACK], BREAK: BP_ICE[BREAK]}, timeout=0.15,
                         keep={CRACK: 2, BREAK: 2}, watch=state)
        if start_y - t.r16(LINK_Y) >= 50:
            break
    cracked = cell(*cells[0])
    t.screenshot('thin_ice_cracked')
    left = 2 - sum(h['pc'] == f'${BREAK:06X}' for h in walk)
    brk = t.breaks({BREAK: BP_ICE[BREAK]}, timeout=1.5, keep={BREAK: left}, watch=state) if left > 0 else []
    time.sleep(0.8)
    after = [cell(*c) for c in cells]
    t.event('after fuse', link=t.link(), S=after[0], S1=after[1], module=t.r(MODULE))
    t.screenshot('thin_ice_after_fuse')
    t.result['breakpoint_hits'] = {'stand': stand, 'walk': walk, 'break': brk}
    cracks = [h for h in walk if h['pc'] == f'${CRACK:06X}']
    breaks = [h for h in walk + brk if h['pc'] == f'${BREAK:06X}']
    t.check('crack started on step-off ($2CF8D8 hit)', bool(cracks), True)
    t.check('S cracked ($0CCC) after step-off', cracked['tilemap'] == '0CCC' or after[0]['tilemap'] == '01E9', True)
    t.check('ThinIce_Break ran ($2CF931 hit)', bool(breaks), True)
    for n, (ck, bk) in enumerate(zip(cracks, breaks)):
        frames = (bk['frame_1A'] - ck['frame_1A']) & 0xFF
        t.event(f'fuse {n}', frames=frames)
        t.check(f'fuse {n} crack -> break in 40 +/- 1 frames', abs(frames - 40) <= 1, True)
    t.check('S became pit (tilemap $01E9, $7F2000 = $20)', after[0] == {'tilemap': '01E9', 'coll': '20'}, True)
    t.check('S-1 became pit too', after[1] == {'tilemap': '01E9', 'coll': '20'}, True)


def run(t, case):
    {'hot_normal': hot_normal, 'hot_airborne': hot_airborne, 'thin_ice': thin_ice}[case](t)
