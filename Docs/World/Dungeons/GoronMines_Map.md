# Goron Mines - Dungeon Map

**Dungeon ID:** D6
**Entrance IDs:** 0x27
**OW Screen:** 0x36
**Boss:** King Dodongo (King Helmasaur reskin)
**Dungeon Item:** Hammer, Fire Shield
**Big Chest:** Room 0x88
**Miniboss:** Lanmolas in Room 0x78
**Entrance Room:** 0x98
**Blockset:** 4 (Goron Mines tileset)
**Palette:** 7

---

## Grid Map (from ROM data)

```
         col 5   col 6   col 7   col 8   col 9   col A
row 6:                   [69]
                          (B1 Side)

row 7:   [77]    [78]    [79]
          NW      MINI    NE
          |       |       |
row 8:  [87]----[88]----[89]
          W.Hall  BIG     E.Hall
          |       |       |
row 9:  [97]---[98*]----[99]
          SW      ENTER   SE
                  |       |
row A:          [A8]----[A9]
                  B1 NW   B1 NE
                  |       |
row B:          [B8]    [B9]
                  B1 SW   B1 SE
                          ···
row C:          [C8B]
                  BOSS
                  |
row D:  [D7]---[D8]----[D9]----[DA]
          B2 W   PRE-B   B2 Mid  B2 E

Legend: * = Entrance, B = Boss, | / -- = door, ··· = gap
```

---

## Floor Layout

### F1 (Main Level) - 3x3 Grid

| Room | Name | Obj | Tracks | Layout | Tags | Locked Doors |
|------|------|-----|--------|--------|------|--------------|
| 0x77 | NW Hall | 137 | 48 | 7 | - | - |
| 0x78 | Lanmolas Miniboss | 155 | 145 | 7 | tag1=50 (holes) | - |
| 0x79 | NE Hall | 91 | 25 | 7 | tag1=4 (kill room) | - |
| 0x87 | West Hall | 214 | 84 | 7 | tag1=22 | Shutter N (double) |
| 0x88 | Big Chest | 127 | 23 | 7 | - | Small Key S |
| 0x89 | East Hall | 122 | 54 | 7 | - | - |
| 0x97 | SW Hall | 89 | 38 | 5 | tag1=23 | Shutter N (one-way up) |
| 0x98 | **Entrance** | 86 | 27 | 4 | tag1=52 | Small Key N |
| 0x99 | SE Hall | 94 | - | 4 | - | - |

### B1 (Basement 1) - 2x2 + side

| Room | Name | Obj | Tracks | Layout | Tags | Locked Doors |
|------|------|-----|--------|--------|------|--------------|
| 0x69 | B1 Side | 65 | - | - | tag1=52 | - |
| 0xA8 | B1 NW | 83 | 10 | - | tag1=47, tag2=4 (shutters) | Shutter W (one-way), Shutter S (double) |
| 0xA9 | B1 NE | 99 | - | - | tag1=8 (together warp) | Small Key W, Shutter N (double) |
| 0xB8 | B1 SW | 132 | 51 | - | - | - |
| 0xB9 | B1 SE | 153 | 46 | - | tag1=62 | - |

### B2 (Basement 2 + Boss) - linear

| Room | Name | Obj | Tracks | Layout | Tags | Locked Doors |
|------|------|-----|--------|--------|------|--------------|
| 0xC8 | **Boss** (King Dodongo) | 13 | - | 0 | tag1=37 | Shutter S (double) |
| 0xD7 | B2 West | 154 | 66 | 7 | - | Small Key E |
| 0xD8 | Pre-Boss | 156 | 74 | 7 | tag1=6 | **Big Key N**, Small Key W |
| 0xD9 | B2 Mid | 97 | 37 | 6 | tag1=3 (crumble floor), tag2=44 | Shutter W (one-way), Shutter N (one-way), Bombable E |
| 0xDA | B2 East | 100 | 49 | 6 | tag1=23 | - |

---

## Connectivity Graph

### Door Connections (14 total)

| From | To | Type | Notes |
|------|----|------|-------|
| 0x77 <-> 0x87 | S/N | Normal | F1 west column |
| 0x78 <-> 0x88 | S/N | Normal | F1 center column |
| 0x79 <-> 0x89 | S/N | Normal | F1 east column |
| 0x87 <-> 0x88 | E/W | Normal | F1 middle row |
| 0x88 <-> 0x89 | E/W | Normal (Lower) | F1 middle row |
| 0x88 <-> 0x98 | S/N | **Small Key** | F1 center vertical gate |
| 0x89 <-> 0x99 | S/N | Normal | F1 east column |
| 0x97 <-> 0x98 | E/W | Normal | F1 bottom row |
| 0x97 -> 0x87 | N | One-way shutter | Can go up, not back down |
| 0x98 <-> 0xA8 | S/N | Normal | F1 -> B1 |
| 0x98 <-> 0x99 | E/W | Normal (Lower) | F1 bottom row |
| 0xA8 -> 0xB8 | S | Double shutter | Gated |
| 0xA9 <-> 0xB9 | S/N | Normal | B1 east column |
| 0xA9 -> 0xA8 | W | **Small Key** | B1 lateral gate |
| 0xA9 -> 0x99 | N | Double shutter | B1 -> F1 |
| 0xC8 <-> 0xD8 | S/N | Double shutter | Boss gate |
| 0xD7 <-> 0xD8 | E/W | **Small Key** | B2 approach |
| 0xD8 <-> 0xD9 | E/W | Normal | B2 corridor |
| 0xD9 <-> 0xDA | E/W | Bombable | Secret connection |

### Staircase Connections (5 inter-floor)

| From | To | Notes |
|------|----|-------|
| 0x77 <-> 0xA8 | F1 NW -> B1 NW | Western descent |
| 0x79 <-> 0x69 | F1 NE -> B1 Side | Side room access |
| 0x97 <-> 0xB8 | F1 SW -> B1 SW | Southwest descent |
| 0x99 <-> 0xDA | F1 SE -> B2 East | **Skip B1 entirely** |
| 0xA9 <-> 0xDA | B1 NE -> B2 East | B1 to B2 shortcut |

### Holewarp Falls (4 one-way drops)

| From | To | Significance |
|------|----|-------------|
| 0x88 -> 0xD8 | Big Chest -> Pre-Boss | **Major shortcut / trap** |
| 0x89 -> 0xD7 | East Hall -> B2 West | Eastern drop to B2 |
| 0x97 -> 0xB8 | SW Hall -> B1 SW | Southwest pit |
| 0x98 -> 0xB9 | Entrance -> B1 SE | Entrance pit trap |

---

## Key & Lock Sequence

**Required keys:** 3 Small Keys + 1 Big Key

| Gate | Location | Unlocks |
|------|----------|---------|
| Small Key 1 | 0x98 N -> 0x88 | Entrance to Big Chest room |
| Small Key 2 | 0xA9 W -> 0xA8 | B1 NE to B1 NW lateral |
| Small Key 3 | 0xD7 E -> 0xD8 | B2 West to Pre-Boss |
| **Big Key** | 0xD8 N -> 0xC8 | Pre-Boss to Boss |

**Bombable:** 0xD9 E -> 0xDA (secret shortcut in B2)

---

## Minecart Track System

### Track Coverage

14 of 19 rooms contain track objects. The minecart is the dungeon's signature mechanic.

| Density | Rooms | Track Count |
|---------|-------|-------------|
| **Extreme** | 0x78 (Miniboss) | 145 tracks |
| **Heavy** | 0x87 (W.Hall) | 84 tracks |
| **Heavy** | 0xD8 (Pre-Boss), 0xD7 (B2 W) | 74, 66 |
| **Medium** | 0x89, 0xB8, 0xDA, 0x77, 0xB9 | 54, 51, 49, 48, 46 |
| **Light** | 0x97, 0xD9, 0x98, 0x79, 0x88, 0xA8 | 38, 37, 27, 25, 23, 10 |
| **None** | 0xC8, 0x69, 0xA9, 0x99, 0x78(??) | 0 |

### Defined Tracks (from `minecart_tracks.asm`)

Only **4 tracks** are currently defined with starting positions:

| Track | Subtype | Starting Room | Starting X | Starting Y | Notes |
|-------|---------|---------------|------------|------------|-------|
| 0 | 0x00 | 0x98 (Entrance) | 0x1190 | 0x1380 | Main entrance cart |
| 1 | 0x01 | 0x88 (Big Chest) | 0x1160 | 0x10C9 | Big Chest room cart |
| 2 | 0x02 | 0x87 (West Hall) | 0x1300 | 0x1100 | West Hall cart |
| 3 | 0x03 | 0x88 (Big Chest) | 0x1100 | 0x10D0 | Second cart in Big Chest |
| 4-31 | 0x04+ | 0x89 (East Hall) | 0x1300 | 0x1100 | **PLACEHOLDER / UNUSED** |

Tracks 4-31 all share identical starting positions pointing at 0x89 — these are **uninitialized placeholder entries**, not real tracks.

### Collision Tile Reference

The minecart reads custom collision tiles (set via `custom_collision.asm`) to determine routing:

| Tile ID | Type | Behavior |
|---------|------|----------|
| 0xB0 | Horizontal straight | Cart passes through horizontally |
| 0xB1 | Vertical straight | Cart passes through vertically |
| 0xB2 | Top-left corner | Redirects based on approach direction |
| 0xB3 | Bottom-left corner | Redirects based on approach direction |
| 0xB4 | Top-right corner | Redirects based on approach direction |
| 0xB5 | Bottom-right corner | Redirects based on approach direction |
| 0xB6 | 4-way intersection | Player chooses direction (d-pad input) |
| 0xB7 | Stop (facing south) | Cart stops, next press goes south |
| 0xB8 | Stop (facing north) | Cart stops, next press goes north |
| 0xB9 | Stop (facing east) | Cart stops, next press goes west (reversed) |
| 0xBA | Stop (facing west) | Cart stops, next press goes east (reversed) |
| 0xBB | North T-intersection | Player can choose (limited by approach) |
| 0xBC | South T-intersection | Player can choose (limited by approach) |
| 0xBD | East T-intersection | Player can choose (limited by approach) |
| 0xBE | West T-intersection | Player can choose (limited by approach) |
| 0xD0-D3 | Switch corners | Dynamic routing via SwitchTrack sprite |

### Camera During Cart Rides

The minecart calls `HandleIndoorCameraAndDoors` ($07F42F) every frame during movement. This is the vanilla indoor camera handler — it scrolls the camera based on Link's position relative to room quadrant boundaries.

**No custom origin positions are set for minecart rides.** The camera follows the standard quadrant-based scrolling, which can cause issues when:
- The cart moves faster than the camera can track
- The cart crosses quadrant boundaries
- The cart approaches room edges during door transitions

---

## Room Layout Analysis

The `layout` value determines room dimensions and camera scrolling quadrant behavior:

| Layout | Meaning | Rooms Using |
|--------|---------|-------------|
| 0 | Full single-screen room | 0xC8 (Boss) |
| 4 | Standard 4-quadrant room | 0x98, 0x99 |
| 5 | Mixed quadrant (asymmetric) | 0x97 |
| 6 | Compressed quadrants | 0xD9, 0xDA |
| 7 | Large standard room | 0x77, 0x78, 0x87, 0x88, 0x89, 0xD7, 0xD8 |

Most track-heavy rooms use **layout 7** (large standard), which gives the most space for track routing. B2 rooms 0xD9 and 0xDA use layout 6 (compressed), which may constrain track designs in those rooms.

---

## Current State Assessment

### What Works
- Core F1 3x3 grid is fully connected and navigable
- 4 minecart tracks are functional with starting positions
- Custom collision tiles are defined for all track piece types
- Track routing logic (corners, intersections, stops, switches) is complete
- Room-to-room transitions with the follower sprite work
- Track persistence across room visits (via `MinecartTrackRoom` tables)

### What's Incomplete

**Track System:**
- Only 4 of 32 possible tracks are defined; tracks 4-31 are placeholders
- Many track-heavy rooms (0xD7, 0xD8, 0xD9, 0xDA, 0xB8) have track *objects* drawn but may lack corresponding minecart *sprites* placed on stop tiles
- The speed switch feature (`$36` fast speed check) is noted as "un-implemented"
- `RoomTag_ShutterDoorRequiresCart` is coded but commented out (not hooked)
- The cart lift/toss system exists but is disabled in the wait states

**Camera / Origin Positions:**
- No custom camera origin positions for minecart rides
- The camera relies entirely on vanilla `HandleIndoorCameraAndDoors`
- Fast cart movement (speed=0x20) across layout 7 rooms may outpace camera scroll
- No per-room camera adjustment for optimal track viewing
- Quadrant boundary crossings during cart rides are unhandled

**Track Puzzle Gaps:**
- No SwitchTrack sprites (`$B0`) placed in rooms despite switch tile support in code
- T-intersections and 4-way junctions need player placement to be meaningful puzzles
- B2 corridor (0xD7-0xDA) has tracks but no documented puzzle structure

### Opportunities

1. **Fill remaining track slots (4-31)** for B1 and B2 rooms
2. **Place SwitchTrack sprites** to create routing puzzles
3. **Add custom camera origins** per room to keep track layouts centered on screen
4. **Use z3ed** to visualize collision maps and validate track tile placement
5. **Hook `RoomTag_ShutterDoorRequiresCart`** for rooms that should only open while riding
6. **Enable the speed switch** mechanic for a fast/slow track dynamic

---

## See Also

- [GoronMines_Tracks.md](GoronMines_Tracks.md) - Detailed track tile layouts per room
- [Progression_Analysis.md](Progression_Analysis.md) - Cross-dungeon progression
- `Sprites/Objects/minecart.asm` - Minecart sprite source
- `Sprites/Objects/data/minecart_tracks.asm` - Track starting position tables
- `Dungeons/Collision/custom_collision.asm` - Custom collision system
- `Dungeons/Collision/CollisionTablesExpanded.asm` - Blockset 4 collision tables
