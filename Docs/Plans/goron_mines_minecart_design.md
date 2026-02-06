# Goron Mines — Minecart Track Design Plan

## Resolved Design Decisions (2026-02-05)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Crumble floor (0xD9) | Real pit drops | Makes cart mandatory — the signature B2 pressure mechanic. Pit table expansion is a separate/low-priority task. |
| Switches per room | One switch per room | Simple: one crystal toggles all D0-D3 tiles in the room simultaneously. |
| Express Lane (post-boss ride) | **Removed** | All dungeon endings use the same flow. No special post-boss track needed. |
| Tag 62 in room 0xB9 | NOP/unused | No conflict with tracks. Available for hooking later if needed. |
| Pit damage table | Check capacity separately | Don't block track work on pit table expansion. Handle as independent task if needed. |
| Holewarp Drop Ride (0x88→0xD8) | Deferred | Not in core scope — interesting set piece but not essential for the dungeon to feel complete. |

## Summary

Design proposals for expanding Goron Mines' minecart system from 4 functional tracks to a full dungeon-defining mechanic. The minecart code supports 32 tracks, switch-routed junctions, speed zones, cart-required shutters, and multi-room rides — most of which are coded but unused. This plan organizes ideas by floor and mechanic, with specific room assignments and track slot allocations.

**Goal:** Make the minecart the signature mechanic of Goron Mines the same way hookshot defines vanilla Swamp Palace or the cane defines Ice Palace. Every floor should escalate the mechanical complexity.

---

## Current State (as of 2026-02)

### What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| Cart movement (NESW) | Working | Speed `$20`, reads collision tiles every frame |
| Corner routing (B2-B5) | Working | Redirects based on approach direction |
| T-intersections (BB-BE) | Working | Player d-pad input at junction |
| 4-way junctions (B6) | Working | Full directional choice |
| Stop tiles (B7-BA) | Working | Directional, next press resumes |
| Room transitions | Working | Follower sprite handles door crossing |
| Track persistence | Working | `MinecartTrackRoom/X/Y` tables at `$0728/$0768/$07A8` |
| Custom collision overlay | Working | Per-room data at ROM `$258090` |

### What's Coded but Disabled

| Feature | Location | How to Enable |
|---------|----------|---------------|
| Switch corners (D0-D3) | `minecart.asm` collision handlers | Place SwitchTrack sprites (`$B0`) in rooms |
| Speed switch (`$36`) | Every move routine checks `LDA $36` | Set `$36` to nonzero (needs a trigger sprite/tag) |
| Cart-required shutters | Room tag hook at `$01CC14` (Tag 0x38) | **UNTESTED.** Set `!ENABLE_MINECART_CART_SHUTTERS = 1` in `Config/feature_flags.asm`. Assign Tag 0x38 to target rooms in yaze. Hook is feature-gated — when disabled, vanilla behavior remains. Guardrail: Tag 0x37 (Holes5) is already used by Minish shutters. Needs runtime test: shutter behavior with/without cart, no Crumble Floor regression, JML return path correct. |
| Cart lift/toss | Wait state handlers | Uncomment `JSR Minecart_HandleLiftAndToss` |

### Track Slot Usage (Starting Table)

This is the starting-room/coord table used only when a track has never been
initialized in RAM (`MinecartTrackRoom[track] == 0`). See
`Sprites/Objects/minecart.asm` (`Sprite_Minecart_Prep`).

Guardrail:
- `!ENABLE_MINECART_PLANNED_TRACK_TABLE` (toggle via `Config/feature_flags.asm`).

| Track | Subtype | Starting Room(s) | Status |
|-------|---------|------------------|--------|
| 0 | 0x00 | 0x98 (Entrance) | Active — tutorial straight line |
| 1 | 0x01 | 0x88 (Big Chest) | Active — horizontal at Y=26 |
| 2 | 0x02 | 0x87 (West Hall) | Active — T-junction layout |
| 3 | 0x03 | 0x88 (Big Chest) | Active — second cart in same room |
| 4-16 | 0x04-0x10 | See Track Slot Allocation (below) | Planned — rooms assigned; coords are **ESTIMATES** until sprites are placed |
| 17-31 | 0x11-0x1F | `$0000` | Reserved — self-disables if used |

### Room Track Object Counts (from z3ed)

| Room | Floor | Track Objects | Has Cart Sprite? | Notes |
|------|-------|---------------|-------------------|-------|
| 0x98 | F1 | 27 | Yes (Track 0) | Entrance, simple horizontal |
| 0x88 | F1 | 23 | Yes (Tracks 1,3) | Big Chest room, dual carts |
| 0x87 | F1 | 84 | Yes (Track 2) | West Hall, T-junction |
| 0x78 | F1 | 145 | No | Miniboss arena — massive grid |
| 0x77 | F1 | 48 | No | NW Hall |
| 0x79 | F1 | 25 | No | NE Hall |
| 0x89 | F1 | 54 | No | East Hall, holewarp to B2 |
| 0x97 | F1 | 38 | No | SW Hall, one-way shutter north |
| 0x99 | F1 | 0 | No | SE Hall |
| 0xA8 | B1 | 10 | No | B1 NW, shutters |
| 0xA9 | B1 | 0 | No | B1 NE, small key door |
| 0xB8 | B1 | 51 | No | B1 SW |
| 0xB9 | B1 | 46 | No | B1 SE, tag1=62 |
| 0x69 | B1 | 0 | No | B1 Side room |
| 0xD7 | B2 | 66 | No | B2 West, small key east |
| 0xD8 | B2 | 74 | No | Pre-Boss, Big Key north |
| 0xD9 | B2 | 37 | No | B2 Mid, crumble floor |
| 0xDA | B2 | 49 | No | B2 East, stair hub |
| 0xC8 | Boss | 0 | No | Boss arena, track-free |

**14 of 19 rooms have track tiles drawn. Only 3 rooms have functional cart sprites.**

---

## Dev Checklist (Build + Tooling + Runtime)

Feature isolation:
```bash
python3 scripts/set_feature_flags.py --list
python3 scripts/set_feature_flags.py --disable minecart_planned_track_table
python3 scripts/set_feature_flags.py --enable minecart_planned_track_table
python3 scripts/set_feature_flags.py --enable minecart_cart_shutters
python3 scripts/set_feature_flags.py --disable minecart_cart_shutters
```

Build:
```bash
./scripts/build_rom.sh 168
```

z3dk analyzer delta (baseline vs current):
```bash
# Create/update a baseline snapshot before making changes (do not commit ROMs)
cp -p Roms/oos168x.sfc Roms/oos168x_base.sfc

python3 ../z3dk/scripts/oracle_analyzer.py Roms/oos168x_base.sfc --hooks hooks.json --json > /tmp/oos_an_base.json
python3 ../z3dk/scripts/oracle_analyzer.py Roms/oos168x.sfc --hooks hooks.json --json > /tmp/oos_an_cur.json
python3 ../z3dk/scripts/oracle_analyzer_delta.py --baseline /tmp/oos_an_base.json --current /tmp/oos_an_cur.json --severity all
```
Notes:
- Keep analyzer JSON in `/tmp` (do not commit outputs).
- If a cart despawns instantly, check `Sprite_Minecart_Prep` coord sanity checks:
  track `MinecartTrackX/Y` must match the placed minecart sprite `SprCachedX/Y`.

Room sampling (Goron Mines focus):
- F1: `0x98`, `0x88`, `0x87`, `0x77`, `0x78`, `0x79`, `0x89`, `0x97`
- B1: `0xA8`, `0xB8`, `0xB9`
- B2: `0xD7`, `0xD8`, `0xD9`, `0xDA`

z3ed minecart audit (Goron Mines focus):
```bash
../yaze/scripts/z3ed dungeon-minecart-audit --rom Roms/oos168x.sfc --rooms 0x77,0xA8,0xB8,0xD8,0xD9,0xDA --only-matches
../yaze/scripts/z3ed dungeon-minecart-audit --rom Roms/oos168x.sfc --rooms 0x77,0xA8,0xB8,0xD8,0xD9,0xDA --only-issues
../yaze/scripts/z3ed dungeon-list-custom-collision --rom Roms/oos168x.sfc --room 0xD9 --nonzero
../yaze/scripts/z3ed dungeon-map --rom Roms/oos168x.sfc --room 0xD9
```

---

## Design Philosophy

### Three-Floor Escalation

| Floor | Theme | Mechanics Introduced | Mood |
|-------|-------|---------------------|------|
| **F1** | Tutorial & Exploration | Straight tracks, junctions, d-pad choice | Comfortable, curious |
| **B1** | Puzzle & Routing | Switch corners, dual-cart coordination | Cerebral, deliberate |
| **B2** | Gauntlet & Speed | Speed zones, crumble floors, cart-required doors | Tense, climactic |

### Design Principles

1. **Progressive complexity** — Each floor introduces exactly one new mechanic on top of the previous ones
2. **Dual-purpose rooms** — Rooms that serve combat first can become track puzzles after (e.g., miniboss grid)
3. **Cart is the key** — In B2, the cart isn't optional. Crumble floors and cart-gated shutters force riding
4. **Persistence matters** — Puzzles should exploit the fact that carts stay where you leave them
5. **Camera-friendly** — Track layouts should keep action within a single camera quadrant when possible (layout 7 rooms have the most space)

---

## Floor 1 — Tutorial & Exploration

### Room 0x98 (Entrance) — "First Ride" [Track 0, existing]

**Current:** Single horizontal track at Y=49, X=0 to X=52.

**Design intent:** Player's first encounter with a minecart. Straightforward.

**Refinement ideas:**
- The track currently ends at the east wall. Adding a **stop tile (B9 or BA)** near the north door would make the cart feel purposeful — "ride east, stop at the door, get off and go north"
- Consider a brief visual cue: a Goron NPC near the entrance who says something like "The old mine rails still work! Press B to ride"
- The track has no-floor segments (X=0-10) before floor segments (X=12-52). This could be a visual hint that the track extends further in that direction (into a wall = came from somewhere)

### Room 0x88 (Big Chest) — "Two Carts, Two Paths" [Tracks 1 & 3, existing]

**Current:** Two carts on the same horizontal line (Y=26), one at X=0x1160 and one at X=0x1100.

**Design intent:** Teach that multiple carts exist independently. One reaches the Big Chest, the other reaches... something else.

**Refinement ideas:**
- **Track 1 path:** Leads to the Big Chest alcove. Straightforward reward.
- **Track 3 path:** Leads toward the holewarp zone. If the player rides this one without knowing what's below, they fall to Pre-Boss (0xD8). This is a **trap-slash-shortcut** depending on how prepared the player is.
- Differentiate the two visually: Track 1 has floor tiles under it (safe), Track 3 has no-floor tiles near the holewarp (danger)
- The holewarp at 0x88→0xD8 could become a **deliberate cart drop** later in the game (see "Holewarp Drop Ride" below)

### Room 0x87 (West Hall) — "First Junction" [Track 2, existing]

**Current:** 84 track objects with horizontal lines at Y=26 and Y=34, vertical at X=44, T-junction at (44,26).

**Design intent:** First time the player must choose a direction at a junction.

**Refinement ideas:**
- The T-junction at (44,26) should offer a meaningful choice:
  - **Continue east:** Leads to a door connection (0x87↔0x88), progressing the critical path
  - **Go south (Y=34 line):** Leads to a dead-end stop tile near a chest or switch
- The shutter door north (double, connects to 0x77) could be visually teased from the cart — "I can see the door, but can I reach it by riding?"
- This room uses layout 7 (large), so there's plenty of space for track routing without camera issues

### Room 0x78 (Lanmolas Miniboss) — "Grid Unlock" [Track 9, NEW]

**Current:** 145 track objects forming a 5×3 grid. No cart sprite. Room has tag1=50 (holes for Lanmolas fight).

**Design intent:** After defeating Lanmolas, the holes seal and the track grid activates. A cart appears on a stop tile, and the player must navigate the grid to reach a reward.

**Proposed track layout:**
```
     X=8      X=20     X=31     X=42     X=54
      |        |        |        |        |
Y=18  +--------+--------4--------+--------+
      |        |        |        |        |
      |        |        |        |        |
Y=32  +--------+---[B6]-+--------+--------+
      |        |        |        |        |
      |        |        |        |        |
Y=46  +--------+--------+--------+--------+
                                          ^
                                       [CHEST]

Legend: [B6] = 4-way junction, 4 = T-intersection
        + = corner tile, - | = straight tiles
```

**Puzzle:**
- Cart starts at (8, 32) — left side, middle row
- Player must navigate to (54, 46) — bottom-right, where a chest sits behind a cart-only alcove
- The **4-way junction at (31, 32)** is the key decision point
- A wrong turn leads to a stop tile that loops back to the start
- Reward: a small key (needed for B1 progression)

**Track slot:** Track 9 (subtype 0x09), starts in room 0x78 at the left-middle stop tile

### Room 0x77 (NW Hall) — "Descent Gateway" [Track 4, NEW]

**Current:** 48 track objects. No cart. Staircase connection to 0xA8 (B1 NW).

**Design intent:** This room connects F1 to B1 via a staircase. Placing a cart here creates a **multi-room ride** that descends into the basement.

**Proposed layout:**
- Track runs vertically from the north end of the room toward the south stairwell
- Stop tile at the north end (player boards)
- Vertical straight tiles (B1) leading south
- Corner at the bottom turning east or west toward the staircase entrance
- When the cart hits the staircase door, the room transition fires and the ride continues in 0xA8

**Track slot:** Track 4, starts in room 0x77

### Room 0x89 (East Hall) — "The Mine Shaft" [Track 10, NEW]

**Current:** 54 track objects. No cart. Holewarp to 0xD7 (B2 West).

**Design intent:** A junction room where the player chooses between exploration (side chest) and a dangerous shortcut (holewarp to B2).

**Proposed layout:**
```
          NORTH (door to 0x79)
              |
    WEST ----[B6]---- EAST (stop + chest)
              |
          [HOLEWARP]
           to 0xD7
```

**Puzzle:**
- Cart starts on the west side (stop tile facing east)
- 4-way junction (B6) in the center
- **East:** Dead-end stop tile near a chest (rupees, consumable)
- **North:** Leads toward the door to 0x79 (NE Hall)
- **South:** Leads directly over the holewarp — one-way drop to B2 West (0xD7)
- No coming back from the south path! Player must decide

**Track slot:** Track 10, starts in room 0x89

### Room 0x79 (NE Hall) — "Optional Explorer Cart" [Track 14, NEW]

**Current:** 25 track objects. Kill room (tag1=4). Staircase to 0x69 (B1 Side).

**Design intent:** After clearing the kill room enemies, a cart appears for optional exploration.

**Proposed layout:**
- Short track with a T-intersection
- One path leads to the staircase entrance (0x69, B1 Side room access)
- Other path leads to a small alcove with a chest

**Track slot:** Track 14, starts in room 0x79

### Room 0x97 (SW Hall) — "One-Way Express" [Track 15, NEW]

**Current:** 38 track objects. One-way shutter north to 0x87. Staircase to 0xB8 (B1 SW).

**Design intent:** The one-way shutter mechanic is unique to this room. A cart could ride north through the shutter (one-way, can't come back), connecting to Track 2's network in 0x87.

**Proposed layout:**
- Cart starts near the south staircase entrance
- Vertical track heading north
- Passes through the one-way shutter
- Continues into 0x87 where it joins Track 2's T-junction network
- This is a **one-way convenience ride** — you can cart up but must walk back down

**Track slot:** Track 15, starts in room 0x97

---

## Floor B1 — Puzzle & Switch Routing

B1 introduces the **SwitchTrack mechanic** (collision tiles D0-D3, toggled by SwitchTrack sprite `$B0`). This is the floor where the minecart becomes a puzzle tool rather than just transportation.

### Mechanic Introduction: Switch Corners

**How they work (from `minecart.asm`):**
- D0 (Top-left switch) → when toggled, becomes D2 (Top-right) behavior
- D1 (Bottom-left switch) → when toggled, becomes D0 (Top-left) behavior
- D2 (Top-right switch) → when toggled, becomes D3 (Bottom-right) behavior
- D3 (Bottom-right switch) → when toggled, becomes D1 (Bottom-left) behavior

The SwitchTrack sprite (`$B0`) is the crystal switch that toggles all D0-D3 tiles in the room simultaneously. Hitting it with the sword changes which way switch corners route the cart.

### Room 0xA8 (B1 NW) — "Switch Tutorial" [Track 5, NEW]

**Current:** 10 track objects. Double shutter south to 0xB8. One-way shutter west. Staircase from 0x77 (F1 NW).

**Design intent:** First encounter with a switch corner. Simple, one-junction puzzle. Player arrives from the Switchback Descent (Track 4 from F1) or the staircase.

**Proposed layout:**
```
    FROM STAIRS (0x77)
          |
    [stop]---[D0]---[stop → exit south to 0xB8]
              |
         [stop → dead end]

    [crystal switch $B0 on floor]
```

**Puzzle:**
1. Player arrives in the room (by cart or on foot)
2. A cart sits on the north stop tile
3. Riding south, the cart hits a **switch corner (D0)** — in default position, it turns the cart west into a dead-end stop
4. Player gets off, hits the crystal switch on the floor
5. The D0 corner is now routed east instead
6. Player rides again — this time the cart goes east through the double shutter into 0xB8

**Teaching moment:** "Hit the switch, then ride." Simple, clear, repeatable.

**Track slot:** Track 5, starts in room 0xA8

### Room 0xB8 (B1 SW) — "Fork in the Mine" [Tracks 6 & 7, NEW]

**Current:** 51 track objects. Staircase from 0x97 (F1 SW). No current cart.

**Design intent:** First multi-cart room in B1. Two carts, two tracks, one exit. The player must figure out which cart to ride (and which switch position to use) to reach the exit.

**Proposed layout:**
```
    NORTH (from 0xA8 shutter)
         |
    [Track 6 stop]----[D1]----[exit east?]
                        |
    [crystal switch]   [D2]
                        |
    [Track 7 stop]----[D3]----[chest alcove]
         |
    (staircase to 0x97)
```

**Puzzle:**
- **Track 6** (north cart): In default switch position, rides to the east exit. In toggled position, loops back.
- **Track 7** (south cart): In default position, rides to a chest. In toggled position, rides to a different destination.
- The crystal switch affects both D1/D2/D3 corners simultaneously
- Player must figure out: "Which cart do I ride, and should the switch be on or off?"

**Key design point:** The two carts should NOT both lead to the exit in the same switch state. This forces the player to commit to one path.

**Track slots:** Track 6 and Track 7, both start in room 0xB8

### Room 0xB9 (B1 SE) — "Advanced Routing" [Track 8, NEW]

**Current:** 46 track objects. tag1=62. Door connection north to 0xA9.

**Design intent:** The culmination of B1's switch puzzles. A more complex layout with multiple switch corners and a T-intersection, requiring the player to plan their route before riding.

**Proposed layout:**
```
    NORTH (to 0xA9)
         |
    [T-int BB]----[D0]----[stop A → key chest]
         |          |
    [stop START]  [D2]
                    |
               [D1]----[stop B → exit south?]
                    |
               [dead end stop]
```

**Puzzle:**
- Cart starts on the west side
- First junction is a T-intersection (BB) — player can go north (to door) or east (into the switch maze)
- Going east enters a network of three switch corners (D0, D1, D2)
- In one switch state: path leads to a key chest (small key for the 0xA9→0xA8 lateral gate)
- In the other state: path leads to a dead end
- The crystal switch is reachable on foot from the T-intersection

**Track slot:** Track 8, starts in room 0xB9

---

## Floor B2 — Gauntlet & Speed

B2 is the climax. **Enable the speed switch (`$36`)** and **hook `RoomTag_ShutterDoorRequiresCart`** for this floor. The minecart is no longer optional — it's survival.

### Enable: Speed Switch Mechanic

**Implementation:**
- Add a speed crystal sprite (or repurpose a tag) that sets `$36 = 1` when activated
- Normal speed: `!MinecartSpeed = $20` (comfortable, F1/B1)
- Fast speed: `!DoubleSpeed = $30` (tense, B2)
- The speed could be zone-based (set by room tag) or player-triggered (hit a crystal for speed boost)

### Enable: Cart-Required Shutters

**Implementation:**
- Enable `!ENABLE_MINECART_CART_SHUTTERS = 1` (via `Config/feature_flags.asm` or `scripts/set_feature_flags.py`)
- Apply Tag `0x38` (Holes6) to rooms where doors should only open while Link is riding
- Runtime test: shutter stays closed without cart, opens when riding into tagged room, no regressions (Crumble Floor tag, Minish shutter tag)

### Room 0xDA (B2 East) — "Arrival Platform" [Track 11, NEW]

**Current:** 49 track objects. Staircase from 0x99 (F1 SE) and 0xA9 (B1 NE). Bombable wall west to 0xD9.

**Design intent:** Player arrives from upstairs. This is the entry point to the B2 gauntlet. A cart here starts the westbound ride through the entire basement.

**Proposed layout:**
```
    STAIRS (from F1/B1)
         |
    [stop START facing west]----[horiz straight]----[door to 0xD9]
                                      |
                               [stop → chest alcove]
```

**Puzzle:**
- Simple introduction to B2 — cart rides west toward 0xD9
- Side stop tile near a chest provides optional reward
- The bombable east wall of 0xD9 means the player might arrive here on foot first, discover the cart, then ride back through the bombable passage

**Track slot:** Track 11, starts in room 0xDA

### Room 0xD9 (B2 Mid) — "Crumble Floor Speedway" [Track 12, NEW]

**Current:** 37 track objects. tag1=3 (crumble floor), tag2=44. One-way shutters west and north. Bombable wall east to 0xDA.

**Design intent:** The crumble floor is the pressure mechanic. Without the cart, the floor collapses under Link. On the cart, Link rides safely above the crumble tiles. **This is the room that makes the cart mandatory.**

**Proposed layout:**
```
    [one-way shutter NORTH]
          |
    [vert straight over crumble]
          |
    EAST [horiz straight]----[D0 switch]----[horiz straight] WEST (to 0xD8)
    (from 0xDA)                    |
                             [vert → dead end]
```

**Puzzle:**
- Cart enters from the east (0xDA ride continuation)
- The track runs horizontally over crumble floor tiles
- A switch corner (D0) in the middle: default routes west to 0xD8 (correct path), toggled routes north into a dead end (and the one-way shutter means you can't easily go back)
- **Speed switch activation:** A speed crystal in this room sets `$36 = 1`. From this point forward, the cart moves at `$30` speed.
- The crumble floor creates urgency — even if you stop, you need to get moving again quickly or get off and walk on solid ground (but there might not be much solid ground)

**Track slot:** Track 12, starts in room 0xD9 (or continues from Track 11 via room transition)

### Room 0xD7 (B2 West) — "The Loop Back" [Track 13, NEW]

**Current:** 66 track objects. Small key door east to 0xD8. No cart.

**Design intent:** If the player takes a wrong turn in the B2 gauntlet, they end up here. A cart in this room lets them try again, but costs a small key to get back to 0xD8.

**Proposed layout:**
```
    [stop START]
         |
    [vert straight]
         |
    [corner]----[horiz straight]----[small key door to 0xD8]
```

**Also reachable via:** Holewarp from 0x89 (F1 East Hall). A player who dropped from the Mine Shaft lands here and can ride back to the critical path.

**Track slot:** Track 13, starts in room 0xD7

### Room 0xD8 (Pre-Boss) — "The Final Approach" [Track (continues from 12/13), possibly NEW Track 16]

**Current:** 74 track objects. Big Key door north to boss (0xC8). Small key door west to 0xD7. Receives holewarp from 0x88 (Big Chest).

**Design intent:** The most important room in the dungeon. The player must ride a cart to the Big Key door. **Cart-required shutter** mechanic gates the boss entrance.

**Proposed layout (using existing track schematic from GoronMines_Tracks.md):**
```
    [BIG KEY DOOR ← cart-required shutter]
              |
    Y=14  [horiz]----[D2 switch]----[horiz]
                         |
    Y=40  [horiz]----[corner]
              |
    Y=47  [T-int]----[horiz]
              |
    Y=54  [horiz]----[D1]----[horiz]----[stop → Big Key chest]
```

**Puzzle:**
1. Player enters from 0xD9 (east) on the cart
2. Track splits at a switch corner — need correct switch state to reach the Big Key chest
3. After getting the Big Key, ride a different cart or re-route to the north track
4. The north track leads to the Big Key door
5. **The Big Key door has `RoomTag_ShutterDoorRequiresCart`** — Link must be riding when approaching. The shutter opens, the cart passes through, and Link enters the boss arena

**Teaching payoff:** Everything the player learned (junctions, switches, speed) comes together in this one room.

**Track slot:** Track 16 (dedicated Pre-Boss cart), or continue from Track 12/13 via room transitions

---

## Special Set Pieces

### The "Holewarp Drop Ride" (0x88 → 0xD8)

**Concept:** The holewarp from Big Chest room to Pre-Boss becomes an intentional cart drop late in the game.

**Setup:**
- After a story trigger (defeating miniboss? finding a switch?), a new track segment appears in 0x88 leading toward the holewarp
- The track has no-floor tiles near the hole — visual danger cue
- Riding the cart off the edge triggers the holewarp
- The player lands in 0xD8 on a matching track segment with the cart auto-continuing

**Purpose:** Late-game shortcut for players who've already explored B1 and want to go straight to the boss approach. Feels dramatic and intentional rather than punitive.

**Gating:** This should NOT be available on first visit. A switch or SRAM flag could control whether this track section exists (or a SwitchTrack sprite could route the cart away from the hole until toggled).

### The "Switchback Descent" (F1 → B1 Multi-Room Ride)

**Concept:** A continuous cart ride spanning F1 and B1.

**Route:** 0x77 (F1 NW) → staircase → 0xA8 (B1 NW) → shutter → 0xB8 (B1 SW)

**Setup:**
- Track 4 starts in 0x77 on a northbound stop tile
- Vertical track heads south through the room
- Hits the staircase door — room transition fires, follower sprite handles the descent
- Emerges in 0xA8 on matching track segment
- Continues through the double shutter into 0xB8
- Arrives at a stop tile in 0xB8

**Player experience:** "I'm still riding! I just went down a floor on a minecart!" This is the memorable moment of the dungeon.

**Technical note:** The room transition follower system already supports this — it caches the track subtype and direction (`!MinecartTrackCache`, `!MinecartDirectionCache`) and spawns a new cart on the other side. The key is ensuring collision tiles align at door boundaries so the transition is seamless.

### ~~The "Express Lane" (Post-Boss Victory Ride)~~ — REMOVED

**Decision (2026-02-05):** Removed. All dungeon endings use the same flow (crystal → maiden → teleport out). A custom post-boss ride isn't needed and would be the only dungeon with a unique exit mechanic.

---

## Track Slot Allocation

### Proposed Assignments

| Track | Subtype | Starting Room | Floor | Purpose | Priority |
|-------|---------|---------------|-------|---------|----------|
| 0 | 0x00 | 0x98 (Entrance) | F1 | Tutorial straight line | Existing |
| 1 | 0x01 | 0x88 (Big Chest) | F1 | Big Chest access cart | Existing |
| 2 | 0x02 | 0x87 (West Hall) | F1 | First junction (T-int) | Existing |
| 3 | 0x03 | 0x88 (Big Chest) | F1 | Holewarp danger cart | Existing |
| 4 | 0x04 | 0x77 (NW Hall) | F1 | Switchback Descent start | High |
| 5 | 0x05 | 0xA8 (B1 NW) | B1 | Switch tutorial cart | High |
| 6 | 0x06 | 0xB8 (B1 SW) | B1 | Fork puzzle cart A | High |
| 7 | 0x07 | 0xB8 (B1 SW) | B1 | Fork puzzle cart B | Medium |
| 8 | 0x08 | 0xB9 (B1 SE) | B1 | Advanced routing puzzle | Medium |
| 9 | 0x09 | 0x78 (Miniboss) | F1 | Post-Lanmolas grid rider | Medium |
| 10 | 0x0A | 0x89 (East Hall) | F1 | Mine Shaft junction | Medium |
| 11 | 0x0B | 0xDA (B2 East) | B2 | B2 gauntlet start | High |
| 12 | 0x0C | 0xD9 (B2 Mid) | B2 | Crumble floor speedway | High |
| 13 | 0x0D | 0xD7 (B2 West) | B2 | Loop-back recovery | Medium |
| 14 | 0x0E | 0x79 (NE Hall) | F1 | Optional explorer cart | Low |
| 15 | 0x0F | 0x97 (SW Hall) | F1 | One-way express ride | Low |
| 16 | 0x10 | 0xD8 (Pre-Boss) | B2 | Final approach / boss gate | High |
| 17-31 | 0x11-0x1F | — | — | Reserved for future use | — |

**Summary:** 17 active tracks (4 existing + 13 new), 15 reserved. Express Lane (Track 17) removed.

### Priority Tiers

**Tier 1 — Core Experience (must-have for dungeon to feel complete):**
- Tracks 4-6: Switchback Descent + B1 switch tutorial + first fork puzzle
- Tracks 11-12: B2 gauntlet start + crumble speedway
- Track 16: Pre-Boss final approach
- Implement cart-required shutter door (needs a dedicated room tag; feature-gate the hook). Intended routine: `RoomTag_ShutterDoorRequiresCart`.

**Tier 2 — Enhanced Puzzles (significantly improves dungeon quality):**
- Tracks 7-8: Dual-cart B1 puzzles
- Track 9: Post-miniboss grid puzzle
- Track 10: Mine Shaft junction
- Track 13: B2 recovery loop
- Enable speed switch for B2

**Tier 3 — Polish & Flavor (nice-to-have):**
- Tracks 14-15: F1 optional exploration
- Holewarp Drop Ride set piece (deferred)
- Per-room camera origin positions

---

## Camera Origin Positions

### The Problem

The minecart calls `HandleIndoorCameraAndDoors` (`$07F42F`) every frame during movement. This is the vanilla indoor camera handler — it scrolls based on Link's position relative to room quadrant boundaries (`QUADH=$A9`, `QUADV=$AA`).

**Issues with fast cart movement:**
1. Speed `$20` is 32 pixels per frame — camera scroll may lag
2. Speed `$30` is 48 pixels per frame — will definitely outpace camera
3. Quadrant boundary crossings cause abrupt camera snaps
4. Layout 7 rooms (most F1/B2 rooms) have 4 quadrants, maximizing snap opportunities
5. Layout 6 rooms (0xD9, 0xDA) have compressed quadrants, less room for tracks

### Proposed Solution: Per-Room Camera Presets

**Approach:** Before the cart starts moving, set the camera scroll target to a position that keeps the entire track layout visible. This could be done in the minecart's wait-state handler.

**Rooms that need custom camera positions:**

| Room | Layout | Track Span | Suggested Camera Strategy |
|------|--------|------------|--------------------------|
| 0x78 | 7 | Full room grid | Lock to center quadrant — grid should fit in one camera view |
| 0x87 | 7 | Y=26 to Y=48 | Lock vertical to mid-room, let horizontal scroll |
| 0xD8 | 7 | Y=14 to Y=54 | May need to scroll — track spans most of the room height |
| 0xD9 | 6 | Compressed | Probably fits in one view naturally |
| 0xB8 | — | Unknown | Needs track layout design first |

**Technical approach options:**
1. **Fixed origin per room:** Store camera X/Y targets in a lookup table indexed by room. Set camera position when entering cart.
2. **Track-aware scrolling:** Modify the camera handler to look ahead along the track direction and pre-scroll.
3. **Zoom-out mode:** If ALTTP supports it, temporarily reduce the camera zoom for cart rides (unlikely without PPU hacks).

**Recommendation:** Option 1 (fixed origin per room) is simplest and most reliable. The camera snap when entering a cart is acceptable if the final position shows the full track.

---

## Z3ed / Yaze Integration Needs

### For Track Validation

1. **Collision map overlay:** Visualize which tiles in a room have collision values B0-BE / D0-D3. This confirms tracks are drawn correctly.
2. **Sprite placement view:** Show where minecart sprites (and SwitchTrack sprites) are placed relative to stop tiles. A cart on a non-stop tile is a bug.
3. **Track path tracer:** Given a starting tile and direction, simulate the cart's path through collision tiles and highlight the route. This is the single most useful tool for validating track designs.

### For Camera Tuning

4. **Quadrant boundary overlay:** Show the camera quadrant boundaries for a given room layout. This lets designers see where the camera will snap during a cart ride.
5. **Camera preview:** Simulate the camera view at different Link positions along a track. Shows what the player will actually see.

### For Door Alignment

6. **Transition boundary checker:** Verify that track tiles are correctly aligned at door boundaries between rooms. If room A has a horizontal track ending at the east wall and room B has one starting at the west wall, the Y positions must match.

---

## Implementation Order

### Phase 1: Enable Dead Code
1. Enable `!ENABLE_MINECART_CART_SHUTTERS = 1` and assign Tag `0x38` (Holes6) to a test room
2. Add a speed crystal sprite or tag that sets `$36`
3. Test both features in isolation before combining with track designs

### Phase 2: B2 Gauntlet (Highest Impact)
1. Place cart sprites in 0xDA, 0xD9, 0xD7 with new track subtypes
2. Update `minecart_tracks.asm` with starting positions for tracks 11-13, 16
3. Set up collision tiles for the B2 corridor routing
4. Apply cart-required shutter tag to 0xD8 north door (boss gate)
5. Place speed crystal in 0xD9

### Phase 3: B1 Switch Puzzles
1. Place SwitchTrack sprites (`$B0`) in rooms 0xA8, 0xB8, 0xB9
2. Set up switch corner collision tiles (D0-D3) in those rooms
3. Place cart sprites with tracks 5-8
4. Update `minecart_tracks.asm` starting positions

### Phase 4: F1 Exploration Carts
1. Place carts in 0x77, 0x78, 0x89 (tracks 4, 9, 10)
2. Refine existing tracks 0-3 with better stop tile placement
3. Optional: tracks 14, 15 for 0x79 and 0x97

### Phase 5: Set Pieces & Polish
1. Holewarp Drop Ride (0x88 → 0xD8)
2. Per-room camera origin positions
3. Final playtesting and balance

---

## Open Questions

1. ~~**Should the crumble floor in 0xD9 actually damage Link when not on the cart, or just make noise/visual cue?**~~ **RESOLVED:** Real pit drops. Makes cart mandatory.

2. **How many SwitchTrack sprites can exist in one room?** If only one, all D0-D3 tiles toggle together. If multiple, they could control independent sets (but the code may not support this). **Decision:** One switch per room for simplicity. Multiple-set control deferred.

3. ~~**Should the Express Lane be story-gated (post-boss flag) or always available?**~~ **RESOLVED:** Express Lane removed entirely. All dungeon endings use the same flow.

4. **Can the holewarp drop preserve cart state?** The holewarp handler may not carry the minecart follower data the same way door transitions do. Needs testing. **Status:** Deferred — Holewarp Drop Ride not in core scope.

5. ~~**What is tag1=62 in room 0xB9?**~~ **RESOLVED:** NOP/unused tag. No conflict with tracks. Available for hooking later.

---

## See Also

- [GoronMines_Map.md](GoronMines_Map.md) — Full room connectivity and current state
- [GoronMines_Tracks.md](GoronMines_Tracks.md) — Existing track tile layouts per room
- `Sprites/Objects/minecart.asm` — Minecart sprite implementation
- `Sprites/Objects/data/minecart_tracks.asm` — Track starting position tables
- `Dungeons/Collision/custom_collision.asm` — Per-room collision overlay system
- `Dungeons/custom_tag.asm` — Room tag handler (where ShutterDoorRequiresCart lives)
- `Core/ram.asm` — Camera quadrant variables (QUADH, QUADV, BSETH, BSETV)
