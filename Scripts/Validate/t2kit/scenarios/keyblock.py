"""Small-key block (Dungeons/keyblock.asm), D1 room $3A, block at tile (31,34).

Port of Scripts/Validate/scenarios/keyblock_unlock.py onto t2kit. Same route,
fixtures and checks; every case expects the fixed behavior, so a control ROM
that crashes shows as FAIL.

  no_key   $7EF36F = 0: the block stays shut and the game keeps running.
  one_key  $7EF36F = 1: the key is spent, the block opens, and it is still
           open after Link walks out to room $4A and back in.
"""
import time

from t2kit import room_origin, rect

FIXTURE = 'goron-mines-open'
CASES = ('no_key', 'one_key')

KEYS, LINK_Y = 0x7EF36F, 0x7E0020
CHEST_FLAGS, CHEST_TILES = 0x7E0402, 0x7E06E0
ENTRANCE_D1, ROOM_ENTRY, ROOM_BLOCK = 0x26, 0x4A, 0x3A
SAVE_3A, SAVE_4A = 0x7EF000 + 2 * ROOM_BLOCK, 0x7EF000 + 2 * ROOM_ENTRY
BLOCK_TILE = (31, 34)  # z3ed dungeon-list-objects: object $F98 in room $3A
CHEST_ATTRS = range(0x58, 0x60)
KEYBLOCK = 0x01EB8C
BREAKPOINTS = {KEYBLOCK: 'Object_KeyBlock', 0x01EBA6: 'vanilla .open_big_key_lock',
               0x01EBE1: 'vanilla .cannot_open_big_key_lock', 0x01EBA0: 'old RTS (no key)',
               0x01EBA8: 'old BRA target (TSB/BRK)'}
# Walk into the block four times, then press A twice (Link_PerformOpenChest).
PUSH = ['up'] * 4 + ['a'] * 2


def block_state(t):
    """Collision attributes under the block's 2x2 tiles, lock slot and room flags."""
    tiles = t.tiles()
    ox, oy = room_origin(ROOM_BLOCK)
    bx, by = BLOCK_TILE[0] * 8, BLOCK_TILE[1] * 8
    attrs = [tiles.attr(bx + dx, by + dy) for dy in (0, 8) for dx in (0, 8)]
    slots = [t.r16(CHEST_TILES + 2 * i) for i in range(6)]
    return {'attrs': [f'{a:02X}' for a in attrs], 'closed': any(a in CHEST_ATTRS for a in attrs),
            'lock_slot': next((i for i, s in enumerate(slots) if s & 0x8000), None),
            'save_room_3A': t.r16(SAVE_3A), 'keys': t.r(KEYS), 'block_abs': (ox + bx, oy + by)}


def push(t, label):
    return t.record_breaks(BREAKPOINTS, PUSH, label, stop_after=2, watch={'keys': KEYS})


def run(t, case):
    # Room $3A save bits 4-9 are its chest/lock flags; a set bit loads the block open.
    if t.r16(SAVE_3A) & 0x03F0:
        t.fixture_ram(SAVE_3A, t.r16(SAVE_3A) & ~0x03F0, 'room $3A chest/lock bits cleared', width=2)
    # Room $4A north key door is door bit $8000; opening it would spend the key.
    t.fixture_ram(SAVE_4A, t.r16(SAVE_4A) | 0x8000, 'room $4A north key door marked open', width=2)
    t.warp(ENTRANCE_D1, room=ROOM_ENTRY, label='D1 Mushroom Grotto, room $4A')
    t.fixture_ram(KEYS, 1 if case == 'one_key' else 0, 'small keys')
    t.clear_enemies()
    # The entrance half reaches the north door only through a one-tile-high gap.
    t.fixture_collision(rect(9, 28, 22, 31), 0x00, 'walk path to the north half')
    ox, oy = room_origin(ROOM_ENTRY)
    t.travel((ox + 240, oy + 48), (ox + 16, oy + 16, ox + 480, oy + 480))
    t.through_door('up', ROOM_BLOCK)
    t.clear_enemies()
    st = block_state(t)
    t.screenshot('room3A_entered')
    if not t.check('key block is shut on entry', st['closed'], True):
        return
    bx, by = st['block_abs']
    below = (bx - 16, by, bx + 32, by + 200)
    t.travel((bx, by + 12), below)
    hits = push(t, 'push up into the block')
    time.sleep(1.0)
    t.screenshot('after_push')
    alive = t.alive('after the push')
    after = block_state(t)
    t.expect_breakpoint(hits, KEYBLOCK, 'Object_KeyBlock ran ($01EB8C hit)')
    if not t.check('game keeps running after the push', alive, True):
        return
    exit_pc = [h['pc'] for h in hits if h['exact'] and h['pc'] != f'${KEYBLOCK:06X}']
    t.guard()
    t.press('up', 24)
    # Link's collision top is y+9: below by+7 means his body is inside the block's tiles.
    inside = t.r16(LINK_Y) < by + 7
    if case == 'no_key':
        t.check('exit path', exit_pc[:1], ['$01EBE1'])
        t.check('block stays shut', after['closed'], True)
        t.check('keys stay 0', after['keys'], 0)
        t.check('Link cannot walk into the block', inside, False)
        return
    slot = st['lock_slot']
    lock_bit = 0x0100 << slot if slot is not None else 0
    t.check('exit path', exit_pc[:1], ['$01EBA6'])
    t.check('key spent (1 -> 0)', after['keys'], 0)
    t.check('block open (no chest attrs under it)', after['closed'], False)
    t.check('$0402 lock bit set', bool(t.r16(CHEST_FLAGS) & lock_bit), True)
    t.check('Link walks into the opened block', inside, True)
    # Leave to room $4A through the south door and come back (controller).
    t.travel((bx, oy - 0x200 + 440), (bx - 16, by - 16, bx + 32, by + 200))
    t.through_door('down', ROOM_ENTRY)
    t.clear_enemies()
    t.through_door('up', ROOM_BLOCK)
    t.clear_enemies()
    again = block_state(t)
    t.screenshot('room3A_reentered')
    t.check('block still open after re-entry', again['closed'], False)
    t.check('keys still 0 after re-entry', again['keys'], 0)
    t.check('room $3A save word keeps the lock bit ($0010 << slot)',
            bool(again['save_room_3A'] & (0x0010 << (slot or 0))), True)
    t.check('$0402 lock bit set after re-entry', bool(t.r16(CHEST_FLAGS) & lock_bit), True)
    t.travel((bx, by + 12), below)
    hits = push(t, 'walk up through the opened block after re-entry')
    t.expect_breakpoint(hits, KEYBLOCK, 'Object_KeyBlock not reached once open', expected=False)
    t.check('Link walks into the opened block after re-entry', t.r16(LINK_Y) < by + 7, True)
    t.check('keys still 0 at the end', t.r(KEYS), 0)
