# D6 Goron Mines — Layout Improvement Ideas

Brainstormed 2026-02-13 from collision audit + dungeon_viz.py review.
These are ideas for later, not immediate work items.

---

## 1. Room 0xD8 (Pre-Boss) — Move carts onto existing stops

The room already has 16 stop tiles and 73 track objects. The layout is
fine. Neither cart sits on a stop tile so both despawn on load.

```
  Cart A at (8,7)  — no stop     Move to (14,14) — B9 stop exists
  Cart B at (22,27) — no stop    Move to (56,53) — BA stop exists
```

Effort: trivial (sprite editor only, no collision changes).

---

## 2. Room 0xB8 (B1 Fork) — Add stop tiles to existing L-track

Has 51 track objects forming an L (vertical left + horizontal bottom)
but literally zero stop tiles. No cart can function.

```
  S  <-- add stop (north end of vertical)
  |
  |
  |
  +--------S------  <-- add stop (east end of horizontal)
```

Two stops makes this a rideable track. Place one cart at the north stop
(Track 6).

Effort: small (collision editor to add B7/BA tiles, then sprite placement).

---

## 3. Room 0xA8 (B1 Switch) — Extend track into a T for switch tutorial

Currently just a tiny vertical strip (10 track objects). The switch
tutorial concept needs at least one branch with a switch corner.

```
  S---D0---S (exit east to 0xB8)
       |
       S (dead end)

  [crystal switch on floor nearby]
```

Hit switch, ride again, different exit. Teaches the switch-corner
mechanic in isolation before the player reaches 0xB8's fork puzzle.

Effort: medium (extend collision, add D0 tile, place SwitchTrack sprite).

---

## 4. Rooms 0x78 & 0x79 — Author custom collision data

Both rooms have track objects drawn but zero custom collision in the ROM
(bank $A5 pointer table has no data for these rooms). Nothing works
until collision is authored in yaze's dungeon editor.

- 0x78 (Miniboss): 145 track objects forming a grid. Post-Lanmolas
  reward puzzle. Needs collision + stops + cart.
- 0x79 (NE Hall): 25 track objects. Optional explorer cart. Needs
  collision + stops + cart.

Effort: medium (editor work to author collision, then sprite placement).

---

## 5. Room 0x99 (SE Hall) — Give it purpose

Most underutilized room in D6. Almost empty — no tracks, sparse objects.
Could become a shortcut hub with a short track and reward chest, or
connect to the holewarp path down to B1/B2.

Effort: low priority, design TBD.

---

## Priority Order

| # | Room | Action | Effort |
|---|------|--------|--------|
| 1 | 0xD8 | Move 2 carts onto stops | Trivial |
| 2 | 0xB8 | Add 2 stop tiles | Small |
| 3 | 0xA8 | Extend track + add switch corner | Medium |
| 4 | 0x78/79 | Author custom collision | Medium |
| 5 | 0x99 | Add track content | Low priority |

Items 1-2 unblock 3 more working carts with almost no work.
Item 3 gives the switch tutorial. Everything else is polish.

---

See also:
- `Docs/Planning/Plans/goron_mines_minecart_design.md` — full design doc
- `Sprites/Objects/data/minecart_tracks.asm` — track starting tables
- `scripts/dungeon_viz.py` — ASCII room visualizer
