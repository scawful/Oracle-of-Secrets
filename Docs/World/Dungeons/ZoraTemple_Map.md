# Zora Temple - Dungeon Map & Design Assessment

**Dungeon ID:** D4
**Entrance IDs:** 0x25, 0x4E
**OW Screen:** 0x1E
**Entrance Room:** 0x28
**ALTTP Equivalent:** Thieves' Town
**Essence:** Luminous Mirage (Reflection, truth beneath surfaces)
**Blockset:** 1 (water-themed) | **Palette:** 9
**Floors:** F1 (single floor, 15 rooms)
**Boss:** TBD
**Dungeon Item:** Zora Mask (mid-dungeon, from Zora Princess)

---

## Narrative Design

### Theme
Deception, manufactured conflict, reconciliation. The Zora Temple reveals that Kydrog engineered the Sea Zora / River Zora schism to prevent the Zoras from sealing his portals.

**This is the first major lore revelation dungeon.**

### Story Beats (Intended Flow)
1. Meet Zora Baby at entrance (explains temple, becomes follower)
2. Navigate water puzzles; Zora Baby triggers water gate/dam events
3. Find conspiracy evidence (forged letters, stolen armor)
4. Get Big Key, reach Princess's chamber
5. Play Song of Healing → receive **Zora Mask** (dive ability)
6. Use Zora Mask dive to complete remaining dungeon
7. Defeat boss, Crystal Maiden appears (separate character from Princess)
8. **Revelation:** River Zoras were framed; Kydrog's pirates wore stolen scales

### Key NPCs
| NPC | Sprite | Role | Room(s) |
|-----|--------|------|---------|
| **Zora Baby** | 0x39 (Locksmith) | Follower, triggers water switches | Entrance → follows Link |
| **Zora Princess** | Zora dispatcher (room 0x105) | Mid-dungeon quest NPC, gives Zora Mask | 0x105 (boss chamber variant) |
| **D4 Crystal Maiden** | Standard maiden | Post-boss lore delivery | Post-boss |

### Post-Dungeon Rewards
- **Song of Storms** at Zora Falls → unlocks waterfall secret (Blue Tunic)
- Zora NPC dialogue updates to intermediate reconciliation state

---

## Dungeon Grid Layout

Room IDs mapped to their grid positions (row = high nibble, col = low nibble):

```
                Col4    Col5    Col6    Col7    Col8
Row 0:                          0x06
Row 1:                          0x16            0x18
Row 2:                  0x25    0x26    0x27    0x28*
Row 3:          0x34    0x35    0x36    0x37    0x38
Row 4:          0x44    0x45    0x46
```
`* = Entrance`

---

## Room-by-Room Characterization

Data source: `z3ed dungeon-list-objects` + `dungeon-doctor` (ROM: meadow_alpha.sfc, 2026-02-07)

### Row 0: Top Floor

#### Room 0x06 — Boss Arena (Water)
| Metric | Value |
|--------|-------|
| Objects | 16 |
| Sprites | 14 (highest in dungeon, tied with 0x35) |
| Doors | **NONE** — accessed only by stairs from 0x16 |
| Water | 4x deep water (0xC8) covering most of the room |
| Key Objects | Walls (0x3F/0x40/0x79/0x7A), room patterns (0xF81) |
| **Role** | **Boss arena.** Doorless, high sprite count, deep water pool. The boss fight likely takes place in/over water. |

### Row 1: Upper Gallery

#### Room 0x16 — Upper Gallery
| Metric | Value |
|--------|-------|
| Objects | 97 |
| Sprites | 7 |
| Doors | 18 total: 4x N (→0x06 area), W/E doors in lower half |
| Water | 6x shallow water (0xC0) in multiple pools |
| Key Objects | Floor edges (0xE7×8), decorations (0x135×5), room borders (0xFAF×9) |
| **Role** | **Gallery/transition room.** North doors lead toward boss arena (0x06). Large multi-section room with shallow water pools and decorative elements. Feels like a grand hall. |

#### Room 0x18 — Silent Corridor
| Metric | Value |
|--------|-------|
| Objects | 44 |
| Sprites | **0** (only room with zero sprites besides 0x25) |
| Doors | 6 total: 2x N, plus locked doors (0x010A, 0x0108, 0x010B) |
| Water | 3x deep (0xC8) + 4x shallow (0xC0) |
| Key Objects | Walls forming narrow passages, water channels |
| **Role** | **Locked corridor.** Zero enemies — pure navigation with locked doors. Contains small key doors that gate access. The silence makes this atmospheric. Connects to entrance (0x28) via south. |

### Row 2: Main Floor (Entrance Level)

#### Room 0x25 — Water Grate Chamber
| Metric | Value |
|--------|-------|
| Objects | **0** |
| Sprites | **0** |
| Doors | None in object data (connectivity via room transitions) |
| Water | Collision-only (ASM-defined, not object-placed) |
| WaterGateStates | **Bit 1** — 168 collision tiles, 3-row swim mask |
| **Role** | **Water grate room.** Zora Baby switch #2. Room geometry defined entirely by ASM collision system, not by standard room objects. Connects east to 0x26. |

#### Room 0x26 — Central Hub
| Metric | Value |
|--------|-------|
| Objects | 80 |
| Sprites | 12 (second highest in Row 2) |
| Doors | **23 total** — N, S, E, W exits. Extremely high door count. |
| Water | 4x deep (0xC8) + 9x shallow (0xC0) = 13 total water objects |
| Key Objects | Floor tiles (0x06×3), walls, room borders (0xFAF×5) |
| **Role** | **Central hub.** The dungeon's crossroads. Connects to almost every direction: N→0x16, E→0x27, S→0x36, W→0x25. 23 doors means this room has many sub-sections and internal passages. High sprite count suggests combat encounters in the hub. |

#### Room 0x27 — Water Gate Chamber
| Metric | Value |
|--------|-------|
| Objects | 103 |
| Sprites | 7 |
| Doors | 4: N×2, W×1, E×1 |
| Water | 1x waterfall (0xC4) + 2x shallow (0xC0) |
| WaterGateStates | **Bit 0** — 239 collision tiles, 4-row swim mask + vertical channels |
| Key Objects | Floor patterns (0x69×10, 0x22×8), pillars (0x88×6), water overlay tiles (0xC3×4), locked passages (0x11C×4) |
| **Role** | **Water gate room.** Zora Baby switch #1. The first significant puzzle. Waterfall object suggests visible water flow. Connects W→0x26 (hub), E→0x28 (entrance). |

#### Room 0x28 — Entrance
| Metric | Value |
|--------|-------|
| Objects | 91 |
| Sprites | 5 |
| Doors | **20 total** — N, S, W exits + many internal passages |
| Water | 2x deep (0xC8) + 8x shallow (0xC0) = 10 water objects |
| Key Objects | Floor tiles (0x22×5), decorations (0xC5×4, 0xD9×4, 0xC9×4), big key door (0x010C) |
| Locked Doors | Small key (0x0108, 0x0109, 0x010A, 0x010B), **Big key (0x010C)** |
| **Role** | **Dungeon entrance.** Complex multi-section room. Contains a BIG KEY DOOR internally — this gates a shortcut or side area from the entrance. Zora Baby (sprite 0x39) likely spawns here. Connects N→0x18, W→0x27, S→0x38. |

### Row 3: Middle Depths

#### Room 0x34 — Waterfall Descent
| Metric | Value |
|--------|-------|
| Objects | 91 |
| Sprites | 6 |
| Doors | 21 total: N, S, E, W + many internal |
| Stairs | **2** (0x005E) — connects to lower rooms |
| Water | 4x waterfall (0xC4) + 8x shallow (0xC0) = 12 water objects |
| Key Objects | Torches/pillars (0xD1×8, 0xD9×5), floor patterns (0xDE×8), pits (0x89×7) |
| **Role** | **Waterfall descent.** Waterfalls, torches, and pits create a multi-level feeling. Stairs connect down to 0x44 (isolated torch room). Heavy water presence. Connects E→0x35, S→0x44 (via stairs). Western portion has large shallow water pools. |

#### Room 0x35 — Stairwell Gauntlet
| Metric | Value |
|--------|-------|
| Objects | 86 |
| Sprites | **14** (tied highest with 0x06) |
| Doors | 13: N, S, W, E exits |
| Stairs | **9** (0x005E) — most stairs in any room! |
| Water | 6x shallow (0xC0) |
| Key Objects | Torches (0xD1×14!), pits (0x89×6), room borders (0xFAF×9) |
| **Role** | **Stairwell gauntlet.** The dungeon's major vertical connectivity node. 9 stairs connect this room to multiple other areas. 14 sprites + 14 torches = combat arena with environmental hazards. This is where you prove yourself before accessing deeper areas. Connects N→0x25, E→0x36, W→0x34, S→0x45. |

#### Room 0x36 — The Great Water Maze
| Metric | Value |
|--------|-------|
| Objects | **159** (most in dungeon by far) |
| Sprites | 11 |
| Doors | **34** (most in dungeon!) — N, S, W, E + many locked |
| Stairs | 2 (0x0077 — holes/drops on east side) |
| Water | **17x deep (0xC8) + 2x shallow (0xC0) = 19 water objects** |
| Locked Doors | Extensive: small key (0x0108-0x010B) + big key (0x010C-0x010F) |
| Key Objects | Floor tiles (0x22×9), walls (0x63/64×7 each, 0x79/7A×8 each), floor gaps (0x03×8), room borders (0xFAF×8) |
| **Role** | **THE signature puzzle room.** An intricate water maze with 34 doors creating a labyrinth of flooded passages. Deep water dominates — the Zora Mask dive ability would transform navigation here. Both small key and big key doors present. This is where the dungeon's complexity peaks. Connects N→0x26, W→0x35, E→0x37, S→0x46 (via stairs/drops). |

#### Room 0x37 — Central Chamber
| Metric | Value |
|--------|-------|
| Objects | 99 |
| Sprites | 10 |
| Doors | 20: N, S, E + many internal + locked |
| Stairs | 3 (0x005E) |
| Water | 5x shallow (0xC0) |
| Locked Doors | Small key doors (0x0108-0x010B) in pairs |
| Key Objects | Floor patterns (0x69×7, 0x22×6), decorations (0xC5×5, 0xD9×5) |
| **Role** | **Central chamber / puzzle room.** Moderate complexity with locked passages gating exploration. Decorative elements suggest this is an important room narratively. Stairs connect to other areas. Connects W→0x36, E→0x38. Good candidate for **conspiracy evidence placement** (forged letters). |

#### Room 0x38 — Water Corridors
| Metric | Value |
|--------|-------|
| Objects | 55 |
| Sprites | 7 |
| Doors | 10: N, S, W exits |
| Water | **10x deep (0xC8) + 4x shallow (0xC0) = 14 water objects** (most water-dense per object) |
| Key Objects | Walls forming narrow channels (0x79/7A×5 each), room borders (0xFAF×4) |
| **Role** | **Water corridors.** Narrow passages with extensive water. The highest water-to-object ratio of any room. Navigation requires swimming. Connects N→0x28 (entrance), W→0x37. This is the eastern water route. |

### Row 4: Lower Depths

#### Room 0x44 — Isolated Torch Chamber
| Metric | Value |
|--------|-------|
| Objects | 33 |
| Sprites | 7 |
| Doors | **NONE** — accessed only by stairs from 0x34 |
| Water | 4x shallow (0xC0) — large open water pools |
| Key Objects | Torches (0xD1×8), pits (0x89×6), floor patterns (0xDE×5), room borders (0xFAF×4), decorations (0x88×2, 0x134×2) |
| **Role** | **Isolated challenge room.** Doorless, accessed by stairs. Torches + pits + enemies = puzzle-combat encounter. The shallow water pools, torches, and pits create an atmospheric arena. Good candidate for **stolen armor evidence**. |

#### Room 0x45 — Lower Connector
| Metric | Value |
|--------|-------|
| Objects | 69 |
| Sprites | 11 |
| Doors | 11: W, E, S exits |
| Water | 6x shallow (0xC0) |
| Key Objects | Floor tiles (0x22×12), room borders (0xFAF×6), pits (0x89×4) |
| **Role** | **Lower connector.** Links the bottom row together. Floor tile-heavy room with combat encounters. Connects N→0x35, E→0x46, W→0x44 (area). |

#### Room 0x46 — Lower Maze
| Metric | Value |
|--------|-------|
| Objects | **108** (third highest) |
| Sprites | 5 |
| Doors | **32** (second highest!) — N, S + extensive internal locked doors |
| Stairs | 3 (2x 0x0077 holes + 1x 0x005E) |
| Water | 10x deep (0xC8) + 2x shallow (0xC0) = 12 water objects |
| Locked Doors | Small key (0x0108-0x010B) + **Big key (0x010C-0x010F)** |
| Key Objects | Walls forming maze passages, floor gaps, water pools |
| **Role** | **Lower maze.** Mirror of 0x36 above but deeper. Complex locked maze with big key doors. This is likely where the **Big Key** is found or where it's needed. Connects N→0x36, W→0x45. |

---

## Room Connectivity Map

```
                    ┌─────────┐
                    │  0x06   │ ← Boss Arena (no doors, stairs from 0x16)
                    │ 14 spr  │
                    └────▲────┘
                         │stairs
                    ┌────┴────┐              ┌─────────┐
                    │  0x16   │              │  0x18   │
                    │ Gallery │              │Corridor │
                    └────┬────┘              └────┬────┘
                         │S                       │S
              ┌──────────┼──────────┐             │
              │          │          │             │
         ┌────┴──┐  ┌───┴────┐  ┌──┴───┐  ┌────┴────┐
         │ 0x25  │──│ 0x26   │──│ 0x27 │──│  0x28*  │
         │ Grate │W │  Hub   │E │ Gate │E │Entrance │
         └───────┘  └───┬────┘  └──────┘  └────┬────┘
                        │S                      │S
    ┌────────┐  ┌───────┼───────────────────────┤
    │        │  │       │                       │
┌───┴────┐┌──┴──┴──┐┌───┴──────┐┌─────────┐┌───┴────┐
│ 0x34   ││ 0x35   ││  0x36    ││  0x37   ││ 0x38   │
│Waterfl ││Stair(9)││WATER MAZE││ Central ││ Water  │
│        ││14 spr  ││159 obj   ││  Chamber││Corridor│
└───┬────┘└───┬────┘└───┬──────┘└────┬────┘└────────┘
    │stairs   │S        │S/stairs    │
┌───┴────┐┌───┴────┐┌───┴────┐
│ 0x44   ││ 0x45   ││ 0x46   │
│Isolated││ Lower  ││ Lower  │
│(no door)│Connect ││  Maze  │
└────────┘└────────┘└────────┘
```

### Connection Summary

| From | N | S | E | W | Stairs To |
|------|---|---|---|---|-----------|
| 0x28* | 0x18 | 0x38 | — | 0x27 | — |
| 0x27 | ? | — | 0x28 | 0x26 | — |
| 0x26 | 0x16 | 0x36 | 0x27 | 0x25 | — |
| 0x25 | — | — | 0x26 | — | — |
| 0x18 | ? | 0x28 | — | — | — |
| 0x16 | 0x06 | 0x26 | — | — | stairs→0x06 |
| 0x06 | — | — | — | — | from 0x16 |
| 0x34 | ? | 0x44 | 0x35 | — | stairs→0x44 |
| 0x35 | 0x25 | 0x45 | 0x36 | 0x34 | **9 stairs** |
| 0x36 | 0x26 | 0x46 | 0x37 | 0x35 | 2 drops |
| 0x37 | 0x27 | ? | 0x38 | 0x36 | 3 stairs |
| 0x38 | 0x28 | — | — | 0x37 | — |
| 0x44 | — | — | — | — | from 0x34 |
| 0x45 | 0x35 | — | 0x46 | 0x44? | — |
| 0x46 | 0x36 | — | — | 0x45 | 3 stairs |

### Locked Door Inventory

**Small key doors (0x0108-0x010B):**
- Room 0x18: 3 locked doors
- Room 0x28: 4 locked doors (entrance!)
- Room 0x36: ~12 locked doors (water maze)
- Room 0x37: ~8 locked doors
- Room 0x46: ~12 locked doors (lower maze)

**Big key doors (0x010C-0x010F):**
- Room 0x28: 1 big key door (inside entrance — gates a shortcut?)
- Room 0x36: multiple big key doors
- Room 0x46: multiple big key doors

**Shutter doors (0x0104-0x0107):**
- Room 0x26: present (kill-all-enemies to open)
- Room 0x28: present
- Room 0x34: present
- Room 0x35: present
- Room 0x37: present

---

## Water Mechanics (Signature System)

### Architecture

The water gate/dam system is D4's equivalent of D6's minecarts — the signature mechanic. It involves:

1. **Zora Baby follower** detects water switch sprites (type 0x04 or 0x21) via `ZoraBaby_CheckForWaterGateSwitch`
2. Baby stands on switch → sets `$0642 = 1` (water gate tag)
3. Vanilla `RoomTag_OperateWaterFlooring` plays fill animation
4. `WaterGate_FillComplete_Hook` ($01F3D2) applies collision data
5. SRAM persistence at `$7EF411` remembers state across room re-entry

### Active Water Rooms

| Room | Mechanic | Collision Tiles | SRAM Bit | Status |
|------|----------|-----------------|----------|--------|
| 0x27 | Water gate (fill) | 239 tiles (4-row swim mask + vertical channels) | Bit 0 | Hook installed, UNTESTED |
| 0x25 | Water grate (open) | 168 tiles (3-row swim mask) | Bit 1 | Hook installed, UNTESTED |

### Water Presence Across All Rooms

Water is the dungeon's dominant visual and mechanical element:

| Room | Deep (0xC8) | Shallow (0xC0) | Waterfall (0xC4) | Total | Character |
|------|-------------|----------------|------------------|-------|-----------|
| 0x06 | 4 | — | — | 4 | Boss pool |
| 0x16 | — | 6 | — | 6 | Gallery pools |
| 0x18 | 3 | 4 | — | 7 | Flooded corridor |
| 0x25 | — | — | — | 0* | ASM-only collision |
| 0x26 | 4 | 9 | — | 13 | Hub waterways |
| 0x27 | — | 2 | 1 | 3 | Waterfall gate |
| 0x28 | 2 | 8 | — | 10 | Entrance canals |
| 0x34 | — | 8 | 4 | 12 | Waterfalls |
| 0x35 | — | 6 | — | 6 | Combat pools |
| 0x36 | **17** | 2 | — | **19** | **Water maze** |
| 0x37 | — | 5 | — | 5 | Chamber pools |
| 0x38 | **10** | 4 | — | **14** | Water corridors |
| 0x44 | — | 4 | — | 4 | Arena pools |
| 0x45 | — | 6 | — | 6 | Connector |
| 0x46 | 10 | 2 | — | 12 | Lower maze |

**Total: 50 deep water + 66 shallow + 5 waterfall = 121 water objects across 15 rooms.**

### Collision Data Layout

**Room 0x27 (Water Gate):**
```
Vertical channel: Y=15, X=40-47 (8 tiles)
Vertical channel: Y=31, X=40-46 (7 tiles)
Main swim area:   Y=41-44, X=5-60 (56 tiles/row x 4 rows = 224 tiles)
Total: 239 tiles → collision type $08 (deep water)
```

**Room 0x25 (Water Grate):**
```
Swim area: Y=45-47, X=5-60 (56 tiles/row x 3 rows)
Total: 168 tiles → collision type $08
```

**Critical offset:** Collision placed 2-3 tiles BELOW visual water (vanilla TileDetect adds +20px Y).

### Feature Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `!ENABLE_WATER_GATE_HOOKS` | **1** | Water fill completion hook at $01F3D2 |
| `!ENABLE_WATER_GATE_ROOMENTRY_RESTORE` | **0** | Room-entry persistence (disabled — caused blackout bug) |
| `!ENABLE_WATER_GATE_OVERLAY_REDIRECT` | **1** | Custom overlay data for water segments |

### Known Bug: Room-Entry Persistence Disabled

`ENABLE_WATER_GATE_ROOMENTRY_RESTORE` is OFF because the old torch-loop hook at `$0188DF` corrupted WRAM during dungeon transitions (GameMode → 0x35 pattern). The fix moved persistence to `CustomRoomCollision` at `$01B95B`, but this needs runtime validation before re-enabling. See `Docs/Debugging/Issues/dungeon_transition_blackout.md`.

**Impact:** Water state is NOT preserved when re-entering rooms 0x25/0x27. Player must re-trigger the switch each visit until persistence is enabled and validated.

---

## Zora Baby Follower Integration

### Current State

The Zora Baby follower (sprite 0x39, follower type 0x09) has a complete 7-state machine:

| State | Action | Description |
|-------|--------|-------------|
| 0 | `LockSmith_Chillin` | Idle, shows message 0x107, detects Link collision |
| 1 | `ZoraBaby_FollowLink` | Enters follower mode ($7EF3CC = 0x09) |
| 2 | `ZoraBaby_OfferService` | "I can help!" dialogue (0x109), follow/stay choice |
| 3 | `ZoraBaby_RespondToAnswer` | Yes → follow (0x10C), No → reject (0x10A) |
| 4 | `ZoraBaby_AgreeToWait` | Confirmation dialogue (0x10B) |
| 5 | `ZoraBaby_PullSwitch` | Standing on water switch, message 0x107 |
| 6 | `ZoraBaby_PostSwitch` | **Empty** (SEP #$30; RTS) |

### Water Switch Detection (Every Frame)

```
ZoraBaby_GlobalBehavior:
  → ZoraBaby_CheckForWaterGateSwitch (sprite type $04, ±9 X / ±18 Y)
  → ZoraBaby_CheckForWaterSwitchSprite (sprite type $21, same thresholds)
  If on switch: face up, set SprGfx=$0D, set $0642=1, goto PullSwitch
```

### Integration Gaps

**The Zora Baby works mechanically but is not integrated into the dungeon's puzzle flow:**

1. **Only 2 rooms use water switches** (0x25 and 0x27). The baby's switch-pulling ability is exercised twice in a 15-room dungeon.

2. **No narrative progression through the dungeon.** The baby says the same message (0x107) at the entrance AND when pulling switches. No dialogue reflects dungeon progress, discoveries, or emotional beats.

3. **No interaction with the conspiracy evidence.** Story beats 3 (forged letters, stolen armor) have no room assignments or dialogue triggers.

4. **Baby doesn't react to the Princess.** The baby is described as the Princess's attendant (`followers.asm` line 29), but there's no state change when the Princess is found.

5. **Water mechanics are isolated.** Rooms 0x25 and 0x27 have water systems, but they're not connected to the dungeon's critical path in a visible way. The player doesn't know WHY they need to fill water — the baby should explain.

6. **PostSwitch state is empty.** State 6 (`ZoraBaby_PostSwitch`) does nothing — this is where the baby could react to the water filling, celebrate, give a hint about where to go next.

---

## Proposed Critical Path

Based on room connectivity and locked door placement:

```
1. ENTER at 0x28 (Entrance)
   └─ Meet Zora Baby, recruit as follower

2. Go WEST to 0x27 (Water Gate)
   └─ Baby pulls water switch #1 → water fills, opens passage
   └─ Baby says: "The ancient gates respond to our touch!"

3. Go WEST to 0x26 (Central Hub)
   └─ Hub room, multiple paths open. Baby: "The elders gathered here..."

4. Go WEST to 0x25 (Water Grate)
   └─ Baby pulls water switch #2 → grate opens, new path available

5. Go SOUTH from Hub to 0x36 (Great Water Maze)
   └─ Navigate water-filled maze. Baby: "Stay close, the currents are strong"
   └─ Find SMALL KEYS within maze

6. Go EAST to 0x37 (Central Chamber)
   └─ Find CONSPIRACY EVIDENCE: forged letters
   └─ Baby: "Those symbols... that's not Zora writing. Someone forged these!"

7. Descend via stairs to 0x46 (Lower Maze)
   └─ Navigate locked passages, find BIG KEY

8. Return UP, go to 0x34 (Waterfall Descent)
   └─ Descend stairs to 0x44 (Isolated Torch Chamber)
   └─ Find stolen Zora scale armor
   └─ Baby: "That armor... it belongs to the Sea Zora Guard!"

9. Access Princess chamber (room 0x105, separate access)
   └─ Baby: "Princess! You're alive!"
   └─ Play Song of Healing → receive ZORA MASK (dive ability)

10. Use Zora Mask to navigate deep water in 0x36/0x38
    └─ Reach GALLERY (0x16)

11. Go NORTH to 0x06 (Boss Arena)
    └─ Baby: "Whatever corrupted this temple... it's in there."
    └─ BOSS FIGHT in deep water arena

12. Crystal Maiden appears with lore revelation
```

---

## Zora Baby Dungeon Journey (Proposed Dialogue)

To make the baby a true companion, add **progression-gated dialogue** (6-7 new messages):

| # | Trigger | Room | Baby Dialogue | Purpose | Msg ID |
|---|---------|------|--------------|---------|--------|
| 1 | Enter dungeon | 0x28 | "This is the sacred temple... The elders sealed it long ago. Stay close to me." | Establish companionship | TBD |
| 2 | First water switch | 0x27 | "Stand back! These ancient gates... they respond to Zora touch!" | Teach mechanic | TBD |
| 3 | After water fills | 0x27 | "The way is open! I knew we could do this together!" | Reward feedback | PostSwitch |
| 4 | Hub room | 0x26 | "I remember stories about this place... the Zora elders would gather here for council." | World-building | TBD |
| 5 | Find forged letters | 0x37 | "Those markings... that's NOT Zora writing! Someone forged these letters!" | Plot revelation | TBD |
| 6 | Find stolen armor | 0x44 | "That armor bears the Sea Zora Guard crest... How did it get down here?" | Deepen mystery | TBD |
| 7 | Near boss | 0x16/0x06 | "Whatever corrupted this temple... I can feel it beyond that darkness." | Tension build | TBD |

**Implementation path:**
1. Encode messages in `Core/message.asm` (expanded range, unblocked)
2. Add room-ID check to `ZoraBaby_GlobalBehavior` or `LockSmith_Chillin` for room-gated dialogue
3. Fill `ZoraBaby_PostSwitch` with contextual reaction (currently empty `SEP #$30; RTS`)
4. Add SRAM progress flag for evidence-found triggers

---

## Zora Princess Integration

### Current State

The Zora Princess (dispatched via `zora.asm` when ROOM = 0x105) has a 4-state machine:

| State | Description | Message |
|-------|-------------|---------|
| 0 | WaitForLink | 0xC5 — initial plea |
| 1 | CheckForSongOfHealing | Waits for SongFlag |
| 2 | ThanksMessage | 0xC6 — death/revelation |
| 3 | GiveZoraMask | Item 0x0F, sets $7EF302 |

### Integration Assessment

- **Functional:** Mask granting works, despawn flag works
- **Missing dialogue:** Messages 0xC5 and 0xC6 need authoring to match the conspiracy revelation narrative
- **TODO in source:** "Enhance 0xC6 dialogue with conspiracy revelation" and "Add Zora Baby reaction state after revelation"
- **Room 0x105** is outside the D4 room range — this is a separate underworld room, possibly accessed from an overworld entrance

### Zora Mask Origin Plan

`Docs/Planning/Plans/zora_mask_origin.md` describes an alternative Zora Mask origin involving a River Zora ghost named Lura. This conflicts with the current Princess-gives-mask flow. **Decision needed:** Which origin story is canonical?

---

## What Needs to Happen (Priority Order)

### Phase 0: Visual Room Audit (STILL NEEDED)

z3ed `dungeon-list-sprites` is not implemented. Object data gives us room structure but NOT sprite placement. We still need to **see** what's in each room to confirm:
- Where sprite 0x39 (Zora Baby) is placed
- Where water switch sprites (0x04 / 0x21) are placed
- Enemy types and positions
- Chest contents

**Options:**
1. **Mesen2:** Load save state in each D4 room, screenshot
2. **yaze GUI:** Open each room in dungeon editor
3. **z3ed:** Wait for `dungeon-list-sprites` implementation (Codex in progress)

### Phase 1: Fill PostSwitch + Room Dialogue (LOW effort, HIGH impact)

1. Fill `ZoraBaby_PostSwitch` with contextual reaction dialogue
2. Add room-ID gating to baby dialogue (check `$A0` for current room)
3. Encode 6-7 new messages in `Core/message.asm`
4. **Unblocked** — message editor is functional

### Phase 2: Place Conspiracy Evidence (MEDIUM effort, needs dungeon editor)

1. Designate room 0x37 for forged letters (pedestal/table sprite)
2. Designate room 0x44 for stolen armor (chest or floor item)
3. Add evidence-found SRAM flags
4. Wire baby dialogue to evidence flags

### Phase 3: Add Water Switches to More Rooms (MEDIUM effort)

Expand the baby's switch-pulling from 2 rooms to 4-5:
- Room 0x36 (Water Maze): Lower/raise water levels to change passable routes
- Room 0x38 (Water Corridors): Open a sluice gate
- Room 0x34 (Waterfall): Redirect waterfall flow

### Phase 4: Enable and Test Room-Entry Persistence

Re-enable `!ENABLE_WATER_GATE_ROOMENTRY_RESTORE` and validate:
1. Fill water in 0x27 → leave → return → water still filled
2. Open grate in 0x25 → leave → return → grate still open
3. D1-D7 regression — no blackouts on any dungeon transitions

---

## Affected Files

| File | Role | Status |
|------|------|--------|
| `Sprites/NPCs/followers.asm` | Zora Baby follower + water switch detection | Complete, working |
| `Sprites/NPCs/zora_princess.asm` | Princess NPC, Zora Mask grant | Complete, dialogue TBD |
| `Sprites/NPCs/zora.asm` | Zora variant dispatcher | Complete |
| `Dungeons/Collision/water_collision.asm` | Water fill/drain collision system | Complete, UNTESTED |
| `Config/feature_flags.asm` | Water gate feature toggles | Active |
| `Core/message.asm` | Dialogue entries | Needs new baby progression messages |
| `Dungeons/dungeons.asm` | Hook installation | Installed |
| `Core/sram.asm` | WaterGateStates ($7EF411) | Defined |

## Related Documents

- `Docs/Planning/Plans/zora_mask_origin.md` — Alternative Zora Mask origin story (River Zora ghost)
- `Docs/Debugging/Issues/dungeon_transition_blackout.md` — Blackout bug root cause and fix
- `Docs/Debugging/Issues/WaterCollision_Handoff.md` — Water collision technical spec
- `Docs/World/Lore/dungeon_narratives.md` — D4 narrative design
- `Docs/Debugging/Testing/save_data_profiles/zora_temple_debug.json` — Debug loadout

## Open Questions (Updated)

1. ~~Room connectivity~~ **ANSWERED** — Full connectivity map derived from door object positions (see above)
2. **Zora Baby spawn room** — Still unknown. Likely 0x28 (entrance) but needs sprite listing confirmation.
3. **Water switch placement** — Still unknown. Are sprites 0x04/0x21 actually placed in rooms 0x25 and 0x27?
4. **Zora Mask origin** — Princess gives it (current code) vs River Zora ghost (zora_mask_origin.md). Which is canonical?
5. **Boss identity** — TBD. Given the deep water boss arena (0x06, 14 sprites), a water-themed boss fits. Perhaps a corrupted Sea Zora guardian or a mirror/illusion creature matching the "truth beneath surfaces" essence.
6. ~~Big Key and small key locations~~ **PARTIALLY ANSWERED** — Big key doors found in rooms 0x28, 0x36, 0x46. Big Key likely found in 0x46 (Lower Maze) based on door patterns.
7. **Conspiracy evidence rooms** — Proposed: 0x37 (forged letters), 0x44 (stolen armor). Needs sprite/item placement.
8. **Room 0x105** — Is this inside D4 or a separate overworld access point for the Princess?
9. **Room 0x06 access** — How does the player reach the boss arena from 0x16? Stairs, but where exactly?
10. **Room 0x35's 9 stairs** — Where do they all lead? This is the dungeon's most connected vertical node.
