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

### Authoring Pipeline (Do This Before Adding New Puzzles)

The minecart engine is collision-tile driven: carts read tile attributes (`Sprite_GetTileAttr`) and dispatch on minecart collision tiles (`$B0-$BE`, `$D0-$D3`, stops `$B7-$BA`). That means the content pipeline must keep **room collision data** consistent, or carts will look "broken" even when the engine is fine.

**Pipeline for a room you want to activate:**

1. **Generate or update track collision** from rail objects (Object `0x31`) using z3ed:
   - Prefer dry-run first.
2. **Ensure stop tiles exist** (`$B7-$BA`) at intended spawn/parking points.
3. **Place minecart sprites on stop tiles.**
   - The minecart prep routine derives starting direction **only** from the stop tile under the cart.
4. **Run `dungeon-minecart-audit`** and fix any remaining invariants before doing runtime playtests.

**Important note on audit fields:** `track_object_subtypes` reported by z3ed are the **Object 0x31 size/subtype bytes**, not "track IDs". Do not treat "minecart sprite subtype not referenced by track objects" as a correctness requirement for runtime; the real authoring invariants are collision tiles + stops + cart placement.

### Track Authoring Contract (Engine Requirements)

These constraints are implied by `Sprites/Objects/minecart.asm`. If any are false, carts will despawn or behave “wrong” even when the room art looks correct.

1. **Rooms with rails or carts must have custom minecart collision data.**
   - If `has_custom_collision_data=false`, carts cannot dispatch on `$B0-$BE/$D0-$D3` tile IDs.
2. **Every placed cart must sit on a stop tile (`$B7-$BA`).**
   - `Sprite_Minecart_Prep` derives the initial direction from the stop tile under the cart.
3. **Track IDs are stateful and coordinate-validated.**
   - Track state lives in `MinecartTrackRoom/X/Y` (`$0728/$0768/$07A8`).
   - If the cart sprite's coords do not match the stored coords, the sprite is killed in `_Prep`.
4. **If a track has never been initialized, its starting room/coords must match the placed cart.**
   - Update `Sprites/Objects/data/minecart_tracks.asm` (or the planned track table) to match the intended starting stop tile.
5. **Door transitions must be aligned at the boundary.**
   - If a cart ride is meant to pass through a doorway, collision tiles must line up so the transition is seamless.

Implication: before “improving puzzles”, we first make these invariants true in each targeted room.

### Minecart Collision Tile IDs (Quick Reference)

This is the collision tile vocabulary the minecart logic dispatches on (`Sprites/Objects/minecart.asm`).

- `$B0-$B1`: straight track tiles (orientation determined by how collision is authored)
- `$B2`: corner (top-left)
- `$B3`: corner (bottom-left)
- `$B4`: corner (top-right)
- `$B5`: corner (bottom-right)
- `$B6`: 4-way intersection (D-pad choice)
- `$BB`: T-junction (north)
- `$BC`: T-junction (south)
- `$BD`: T-junction (east)
- `$BE`: T-junction (west)
- `$B7-$BA`: stop tiles (also used to derive initial direction in `_Prep`)
  - `$B7` -> depart south
  - `$B8` -> depart north
  - `$B9` -> depart east
  - `$BA` -> depart west
- `$D0-$D3`: switch corners (toggled by SwitchTrack sprite `0xB0`)

### Stop Tile Placement Guidelines

- **Every cart spawn must sit on a stop tile** (`$B7-$BA`). This is required for `_Prep` to set a sane initial direction.
- Use stops as “checkpoints”:
  - wrong routes should end at a stop that is close to where the player can retry (short recovery).
- For intended multi-room rides:
  - align track collision at door boundaries and validate transitions in runtime.
  - if continuity is flaky, convert the boundary into a deliberate “stop at the door, then re-board” beat (still feels good if downtime is minimal).

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

| Room | Floor | Track Objects | Total Objects | Sprites | Has Cart? | Audit Status |
|------|-------|---------------|---------------|---------|-----------|-------------|
| 0x98 | F1 | 27 | — | — | Yes (Track 0) | Active |
| 0x88 | F1 | 23 | — | — | Yes (Tracks 1,3) | Active |
| 0x87 | F1 | 84 | — | — | Yes (Track 2) | Active |
| 0x78 | F1 | 145 | — | — | No | Not audited |
| 0x77 | F1 | 48 | — | — | No | Not audited |
| 0x79 | F1 | 25 | — | — | No | Not audited |
| 0x89 | F1 | 54 | — | — | No | Not audited |
| 0x97 | F1 | 38 | — | — | No | Not audited |
| 0x99 | F1 | 0 | — | — | No | Empty |
| **0xA8** | **B1** | **10** | **83** | **12** | **Yes (A3 subtype 2)** | **FLAGGED — not on stop tile; subtype mismatch (2 vs {6})** |
| 0xA9 | B1 | 0 | — | — | No | Empty |
| **0xB8** | **B1** | **51** | **132** | **7** | **No** | **FLAGGED — missing stop tiles (B7-BA); cart sprites missing** |
| 0xB9 | B1 | 46 | — | — | No | Not audited |
| 0x69 | B1 | 0 | — | — | No | Empty |
| 0xD7 | B2 | 66 | — | — | No | Not audited |
| **0xD8** | **B2** | **73** | **156** | **7** | **Yes x2 (A3 subtypes 1,3)** | **FLAGGED — carts not on stop tiles (B7-BA)** |
| 0xD9 | B2 | 37 | — | — | No | Not audited |
| **0xDA** | **B2** | **49** | **100** | **11** | **Yes (A3 subtype 2)** | **FLAGGED — not on stop tile; subtype mismatch (2 vs {6,7,9,11,12})** |
| 0xC8 | Boss | 0 | — | — | No | Empty |

**14 of 19 rooms have track tiles drawn.**

**Audit update (2026-02-13):**
- `dungeon-minecart-audit` over the 15 track-start rooms (`0x98,0x88,0x87,0x77,0xA8,0xB8,0xB9,0x78,0x89,0xDA,0xD9,0xD7,0x79,0x97,0xD8`) reports **13/15 with custom collision data** and **2/15 without** (`0x78`, `0x79`).
- `minecart_tracks.asm` start-position table now resolves to valid stop tiles for **13/17 tracks** (tracks `0-5,8,10-13,15-16`).
- The remaining **4/17 tracks are intentionally blocked** by missing room prerequisites:
  - `6,7` -> room `0xB8` has no stop tiles (`B7-B9`).
  - `9,14` -> rooms `0x78`/`0x79` have no custom collision data.

This means the coordinate-table cleanup is accurate for all currently eligible tracks, but not all 17 tracks are runtime-ready yet.

**Verification rerun (2026-02-13 PM, post-track-table edits):**
- Command: `../yaze/scripts/z3ed dungeon-minecart-audit --rom Roms/oos168x.sfc --rooms 0x98,0x88,0x87,0x77,0xA8,0xB8,0xB9,0x78,0x89,0xDA,0xD9,0xD7,0x79,0x97,0xD8 --only-issues`
- Result: `10/15` rooms still emit issues.
- Hard blockers confirmed: `0x78` and `0x79` still have no custom collision data; `0xB8` still has no stop tiles.
- Placement blockers confirmed: `0xA8`, `0x89`, `0xDA`, and `0xD8` have minecart sprites not on stop tiles.
- Accuracy note: claims like "all 17 tracks verified and ready" are incorrect for current ROM state.

**Immediate next work:**
1. Place/reposition minecart sprites for the verified-track rooms (focus tracks `4,5,8,10,11,12,13,15,16`).
2. Author custom collision data for rooms `0x78` and `0x79`.
3. Add stop tiles (`B7-B9`) in room `0xB8` and then finalize tracks `6` and `7`.
4. Add switch-corner tiles (`D0-D3`) + `SwitchTrack` sprites where switch routing is intended.

The detailed per-room writeups below focus on the originally investigated subset (`0xA8`, `0xB8`, `0xD8`, `0xDA`). Add similar writeups for `0x78`, `0x79`, and `0x89` once we decide which rooms are in-scope for near-term activation.

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

Audit snapshot (2026-02-07, ROM copy: `/tmp/oos168x_minecart_audit_20260207.sfc`, sha256: `afff5b8b5ee70b883a2c9992da17e141dc60fc287d9cfdf838257c97adb4ff33`):

**Rooms with content-breaking issues (z3ed `dungeon-minecart-audit --only-issues`):**
- Missing custom collision data (cannot work): `0x78`, `0x79`
- No stop tiles: `0xB8`
- Carts not placed on stop tiles: `0x89`, `0xA8`, `0xD8`, `0xDA`

**Rooms emitted as "issues" due only to subtype bookkeeping (likely non-blocking):**
- `0x87`, `0x88`, `0x97` (reported "minecart sprite subtype not referenced by track objects")

**Invariant:** Inactive carts determine their starting direction only from the stop tile
under them (see `Sprites/Objects/minecart.asm` `Sprite_Minecart_Prep`). If no stop tile
matches, behavior defaults to "north" (`Minecart_WaitVert`), which often looks like a
broken cart.

#### Room 0xA8 (B1 NW) — Track 5 planned

| Data Point | Value | Issue? |
|-----------|-------|--------|
| Total objects | 83 | OK |
| Track objects (0x0031) | 10 | Low — only vertical strip at x=14, y=44..62 (size=6) |
| Total sprites (doctor) | 12 | OK |
| Minecart sprite (0xA3) | Present (x=7, y=24, subtype=2) | ISSUE: not on a stop tile; subtype mismatch vs track objects `{6}` |
| Stop tiles (B7-BA) | 8 (`0xB7` at x=13-16, y=44-45) | ISSUE: stops exist, but none under the cart |
| Switch corners (D0-D3) | Missing (0) | Needed for planned switch tutorial puzzle |
| SwitchTrack sprite (0xB0) | Missing (0) | Needed for planned switch tutorial puzzle |
| Track object layout | Vertical column at x=14, y=44 to y=62 | Only 10 tiles, all same x — a single N-S segment |

**Track objects detail (x=14 column):**
```
y=44 size=6, y=46 size=6, y=48 size=6, y=50 size=6, y=52 size=6
y=54 size=6, y=56 size=6, y=58 size=6, y=60 size=6, y=62 size=6
```

**Assessment:** Room has minimal rail objects (10), but it already has custom collision
data (including stop tiles) and a minecart sprite. The current blockers are alignment:
the cart is not placed on a stop tile, and its subtype (`2`) does not match the room's
track-object subtype set (`{6}`) or the planned track ID (`5`).

**Fix plan:**
1. Place the cart on an existing stop tile:
   - Current cart tile position: `(14,48)` (x=7,y=24).
   - Existing stops: `0xB7` at `x=13-16, y=44-45`.
   - Likely fix: move the cart to `y=22` (tile_y=44) so it lands on the `0xB7` cluster.
2. Align track IDs:
   - Planned: Track `5`.
   - Current room rails: subtype `{6}`.
   - Current cart: subtype `2`.
   - Decide the intended track index for this room and update both the cart subtype and all track-object subtypes to match.
3. Re-run `dungeon-minecart-audit` until the room has no `on_stop_tile` and subtype-mismatch issues.
4. Only after alignment is correct, implement the planned switch tutorial (SwitchTrack sprite `$B0` + D0 switch corners), then validate runtime in Mesen2.

---

#### Room 0xB8 (B1 SW) — Tracks 6 & 7 planned

| Data Point | Value | Issue? |
|-----------|-------|--------|
| Total objects | 132 | High — dense room |
| Track objects (0x0031) | 51 | Good coverage |
| Total sprites (doctor) | 7 | OK |
| Minecart sprite (0xA3) | Not placed | ISSUE: no carts present |
| Stop tiles (B7-BA) | 0 | ISSUE: collision has track tiles, but no stop tiles exist |
| Switch corners (D0-D3) | Missing (0) | Needed for planned fork puzzle |
| SwitchTrack sprite (0xB0) | Missing (0) | Needed for planned fork puzzle |
| Track object layout | Full horizontal row at y=51, x=14..62 (size 7-10) | Single E-W line |

**Track objects detail (y=51 row, all size=7 except x=14 size=10, x=16 size=7):**
```
x=14..16..18..20..22..24..26..28..30..32..34..36..38..40..42..44..46..48..50..52..54..56..58..60..62
25 objects at y=51 (continuous east-west rail across room bottom)
```

Plus: y=0..45 vertical tracks at x=14 (26 objects, size=1, covering y=0 to y=49) forming
a full N-S corridor on the left side. Total coverage: L-shaped track network.

**Assessment:** Track infrastructure is substantial — a full east-west rail at y=51 and a
full north-south rail at x=14 forming an L. But no switch corners (D0-D3), no stop tiles
(B7-BA), and no cart sprites. The design doc calls for dual-cart fork puzzle with D1/D2/D3
corners.

**Fix plan:**
1. Add stop tiles (B7-BA) at intended cart spawn/parking points (no stop tiles currently exist in this room).
2. Place 2 minecart sprites (0xA3) on stop tiles, using subtypes 6 and 7.
3. Place/verify SwitchTrack sprite (0xB0) for the crystal-switch routing.
4. Add switch corner collision (D1, D2, D3) at junction points to form the fork puzzle.
5. Connect the L-shaped rails via corners to create the intended fork layout.
6. Update track table X/Y for Tracks 6 & 7 after final sprite placement.

---

#### Room 0xD8 (B2 Pre-Boss) — Track 16 planned (ROM currently has carts subtypes 1 & 3)

| Data Point | Value | Issue? |
|-----------|-------|--------|
| Total objects | 156 | Very high — most complex room |
| Track objects (0x0031) | 73 | Excellent coverage |
| Total sprites (doctor) | 7 | OK |
| Minecart sprites (0xA3) | Present x2 (subtypes 3 at x=22,y=27; 1 at x=8,y=7) | ISSUE: neither is on a stop tile |
| Stop tiles (B7-BA) | 16 (B9 at x=14,y=13-16; BA at x=52-53,y=13-16; BA at x=56,y=53-56) | ISSUE: no stop tile under either cart |
| Switch corners (D0-D3) | Missing (0) | Needed for planned boss-gate routing puzzle |
| SwitchTrack sprite (0xB0) | Missing (0) | Needed for planned boss-gate routing puzzle |

**Track objects detail — 3 distinct track networks:**

**Network 1 — Horizontal at y=14 (east-west, upper room):**
```
x=13,15 (size=7), x=17,19..35 (size=0, single tiles), x=37,39,41,43,45,47,49,51,52 (size=7)
~30 objects spanning x=13 to x=52 — full-width horizontal rail
```

**Network 2 — Vertical at x=33, y=40..47 (mid-room connector):**
```
y=40 size=3, y=42 size=1, y=44 size=1, y=45 size=1, y=47 size=0
5 objects — short vertical segment connecting upper and lower networks
```

**Network 3 — Horizontal at y=54 + y=40 (lower room):**
```
y=54: x=17(size=4), x=19..37(size=0), x=39..55(size=7) — ~25 objects
y=40: x=0..31(size=0) + x=19,21..31(size=0) — ~22 objects
```

Plus: y=47 horizontal segment, y=49/51/52 vertical at x=17 connecting y=47 to y=54.

**Assessment:** This room has the most elaborate track network in D6 — 73 objects forming
3 horizontal lines at y=14, y=40, and y=54 connected by vertical segments. The design doc
calls for a D1/D2 switch-routed puzzle leading to the Big Key chest (y=54 area) and then
north to the boss gate (y=14 area). Track rails exist and stop tiles exist, and the two
minecart sprites are present, but neither cart is placed on a stop tile so they will not
spawn into a stable waiting state.

**Fix plan:**
1. Put both carts on stop tiles (B7-BA):
   - Cart A: tile `(16,14)` (x=8,y=7) is close to the existing `0xB9` stop at `(14,14)`. Likely fix: move the cart left by 1 (x=8 -> x=7).
   - Cart B: tile `(44,54)` (x=22,y=27) currently has no stop tile under it. Either paint a stop tile under it, or move it to the existing `0xBA` stop column at `x=56, y=53-56`.
2. Re-run `dungeon-minecart-audit` until both carts report `on_stop_tile=true`.
3. Decide whether these carts should remain Track 1/3 (holewarp drop ride) or be migrated to the planned Track 16 puzzle; adjust cart subtypes and rail subtypes accordingly.
4. Place/verify SwitchTrack sprite(s) and add switch corners (D1, D2) for route selection.
5. Apply Tag 0x38 (cart-required shutter) to the boss door only after enabling `!ENABLE_MINECART_CART_SHUTTERS` and runtime-testing the tag return path.
6. Update track table X/Y for Track 16 after final sprite placement.

---

#### Room 0xDA (B2 East) — Track 11 planned

| Data Point | Value | Issue? |
|-----------|-------|--------|
| Total objects | 100 | Moderate |
| Track objects (0x0031) | 49 | Good coverage |
| Total sprites (doctor) | 11 | OK |
| Minecart sprite (0xA3) | Present (x=26, y=6, subtype=2) | ISSUE: not on a stop tile; subtype mismatch vs track objects `{6,7,9,11,12}` |
| Stop tiles (B7-BA) | 4 (`0xB7` at x=51-54, y=10) | ISSUE: cart tile is `(52,12)` (x=26,y=6); likely move to `y=5` (tile_y=10) |
| Switch corners (D0-D3) | Missing (0) | Optional for this room |
| SwitchTrack sprite (0xB0) | Missing (0) | Optional for this room |

**Track objects detail — 3 track networks:**

**Network 1 — U-shaped in upper half:**
```
Horizontal y=8: x=0..22 (14 objects, size=7) — full-width rail
Vertical x=22: y=8..24 (8 objects, size=6/9/11/12) — right-side descent
Horizontal y=16: x=22..52 (18 objects, size=7/11/12) — mid-level rail
Vertical x=52: y=10..16 (4 objects, size=6) — connector
Horizontal y=24: x=0..22 (13 objects, size=7) — bottom horizontal
```

**Network 2 — Isolated vertical at x=22, y=8-24:**
Part of Network 1's U-shape — connects y=8 to y=24 via right-side corridor.

**Assessment:** Track infrastructure forms a large U-shaped circuit in the upper half of
the room (y=8 to y=24). Lower half (y=40-56) has lava/pit area with no tracks. This room
already has stop tiles and a minecart sprite, but the cart is not placed on a stop tile
and its subtype (`2`) does not match the room's rail subtypes (which include the planned
Track `11`).

**Fix plan:**
1. Move the cart onto an existing stop tile (current cart tile `(52,12)`; stops at `x=51-54, y=10`).
   - Likely fix: move the cart to `y=5` (tile_y=10).
2. Align track IDs:
   - Planned: Track `11`.
   - Current cart: subtype `2`.
   - Rails already include subtype `11`, so the simplest path is to change the cart subtype to `11`.
3. Re-run `dungeon-minecart-audit` until the cart reports `on_stop_tile=true` and no subtype-mismatch issue.
4. Update track table X/Y for Track 11 after final sprite placement.

---

#### Summary: Per-Room Fix Priority

| Room | Tracks | Track Objects | Cart | Stop Tiles | Switch Corners | Switch Sprite | Fix Effort |
|------|--------|---------------|------|------------|----------------|---------------|------------|
| 0xA8 | 5 | 10 (minimal) | Present (broken) | Present (8, cart not on one) | Missing (0; planned D0) | Missing (0; SwitchTrack 0xB0) | **Heavy** — track ID + stop alignment, then switch tutorial |
| 0xB8 | 6,7 | 51 (good L-shape) | Missing | Missing | Missing (0; planned D1-D3) | Missing (0; SwitchTrack 0xB0) | **Heavy** — add stops + carts + puzzle routing |
| 0xD8 | 16 | 73 (3 networks) | Present x2 (broken; subtypes 1,3) | Present (16, carts not on one) | Missing (0; planned D1,D2) | Missing (0; SwitchTrack 0xB0) | **Heavy** — most complex routing + decide track IDs |
| 0xDA | 11 | 49 (U-shape) | Present (broken) | Present (4, cart not on one) | Missing (0) | Missing (0; SwitchTrack 0xB0) | **Moderate** — stop + subtype alignment |

**All 4 rooms:** Track rail objects (0x0031) exist and form viable networks. Room `0xB8`
is missing stop tiles and carts. Rooms `0xA8`, `0xD8`, and `0xDA` already have stop tiles
and minecart sprites, but the carts are not placed on stop tiles (and in `0xA8`/`0xDA`
there is also a cart-subtype mismatch vs rail subtypes). These are still not playable as
intended minecart puzzles until placement/subtype alignment is fixed.

**Blocking dependency:** Moving/adding cart sprites (0xA3) and placing SwitchTrack sprites
(0xB0) requires the yaze sprite editor. Stop tiles (B7-BA) and switch corners (D0-D3) are
collision data that can potentially be set via the custom collision overlay in ASM
(`$258090`), but are most safely edited in yaze's dungeon editor.

**Recommended order:** 0xDA (simplest) → 0xA8 (tutorial) → 0xB8 (dual-cart) → 0xD8 (boss gate)

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

### Layout Improvement Pass (v2) — Make It Play Better

The structure and set pieces are good. The main improvements needed are about readability, fewer frustrating dead-ends, and reducing camera snap disorientation during faster rides.

**v2 goals:**
- Reduce “rode the cart and nothing happened” moments:
  - carts always start on stop tiles
  - stops exist at intended boarding/parking points
- Keep critical decisions legible:
  - introduce switch corners in a single-purpose tutorial room before combining them with multi-cart forks
- Keep most required rides within 1-2 camera quadrants where possible.

**Near-term v2 priorities (by player impact):**
- **B2 gauntlet clarity:** `0xDA -> 0xD9 -> 0xD8` should read as one continuous “commit to the ride” sequence, with short failure recovery.
- **B1 fork readability:** `0xA8` and `0xB8` should be solvable after one failure without long on-foot resets.
- **F1 optionality:** exploration carts should reward curiosity without trapping the player into long backtracks.

**Implementation approach:**
- Fix invariants first (custom collision, stops, cart placement, starting table alignment).
- Then adjust collision topology (junction placement, switch corners, stop placement) to match the intended puzzle beats.

### v2 Critical Path Walkthrough (Minecart-Forward)

This is the intended “teach -> combine -> climax” experience for Goron Mines once layouts are tightened.

1. **F1: Teach the controls and basic vocabulary**
   - `0x98`: ride + stop near an obvious exit (board/disembark loop).
   - `0x87`: first “choose a direction” junction with an obvious reward branch.
2. **F1 -> B1: First “wow” moment**
   - `0x77 -> 0xA8 -> 0xB8`: continuous descent ride (or near-continuous with minimal downtime).
   - Player learns “switch corners exist” in `0xA8` before being asked to solve the fork in `0xB8`.
3. **B1: Puzzles that feel deliberate**
   - `0xA8`: 1-switch tutorial, short recovery.
   - `0xB8`: fork room, one main path cart and one reward cart.
   - `0xB9`: optional/late “advanced routing” (should not be required to understand the rest of the dungeon).
4. **B2: Climax**
   - `0xDA`: safe staging, then commit.
   - `0xD9`: crumble floor + speed (or pseudo-speed) creates pressure.
   - `0xD8`: “everything comes together” room: Big Key access + cart-required boss gate.

**v2 recovery rule:** Wrong rides should usually return you to a stop that is within 1 room and 1 camera quadrant of where you can retry.

---

## Floor 1 — Tutorial & Exploration

### Room 0x98 (Entrance) — "First Ride" [Track 0, existing]

**Current:** Single horizontal track at Y=49, X=0 to X=52.

**Design intent:** Player's first encounter with a minecart. Straightforward.

**Refinement ideas:**
- The track currently ends at the east wall. Adding a **stop tile (B9 or BA)** near the north door would make the cart feel purposeful — "ride east, stop at the door, get off and go north"
- Consider a brief visual cue: a Goron NPC near the entrance who says something like "The old mine rails still work! Press B to ride"
- The track has no-floor segments (X=0-10) before floor segments (X=12-52). This could be a visual hint that the track extends further in that direction (into a wall = came from somewhere)
- v2: make the first ride end at an obvious actionable place (door, chest alcove, or a switch), not just “ride into a wall”.

### Room 0x88 (Big Chest) — "Two Carts, Two Paths" [Tracks 1 & 3, existing]

**Current:** Two carts on the same horizontal line (Y=26), one at X=0x1160 and one at X=0x1100.

**Design intent:** Teach that multiple carts exist independently. One reaches the Big Chest, the other reaches... something else.

**Refinement ideas:**
- **Track 1 path:** Leads to the Big Chest alcove. Straightforward reward.
- **Track 3 path:** Leads toward the holewarp zone. If the player rides this one without knowing what's below, they fall to Pre-Boss (0xD8). This is a **trap-slash-shortcut** depending on how prepared the player is.
- Differentiate the two visually: Track 1 has floor tiles under it (safe), Track 3 has no-floor tiles near the holewarp (danger)
- The holewarp at 0x88→0xD8 could become a **deliberate cart drop** later in the game (see "Holewarp Drop Ride" below)
- v2: avoid “early accidental boss-route” frustration:
  - keep Track 3 as a shortcut, but gate it behind a late trigger (switch/state) or force an intentional commit (stop tile + clear warning before the drop).

### Room 0x87 (West Hall) — "First Junction" [Track 2, existing]

**Current:** 84 track objects with horizontal lines at Y=26 and Y=34, vertical at X=44, T-junction at (44,26).

**Design intent:** First time the player must choose a direction at a junction.

**Refinement ideas:**
- The T-junction at (44,26) should offer a meaningful choice:
  - **Continue east:** Leads to a door connection (0x87↔0x88), progressing the critical path
  - **Go south (Y=34 line):** Leads to a dead-end stop tile near a chest or switch
- The shutter door north (double, connects to 0x77) could be visually teased from the cart — "I can see the door, but can I reach it by riding?"
- This room uses layout 7 (large), so there's plenty of space for track routing without camera issues
- v2: make the reward branch short and readable:
  - one “reward stop” that returns you to the junction with minimal on-foot backtrack.

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

**v2 improvements (recommended):**
- Consider shrinking the grid to a **3x3 decision grid** instead of 5x3:
  - the current concept is strong but likely too wide to read at minecart speed
- Put the **goal (chest alcove)** in camera view of the key decision junction so the player can route visually.
- Keep punishment short:
  - exactly 1 fail loop that returns to the start stop tile (avoid multiple dead-end stops).

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

**v2 improvements (recommended):**
- Ensure the boarding stop is in the same camera quadrant as the staircase exit so the player sees “board -> descend”.
- Add 1 optional parking stop (1-tile spur) with a small reward to teach that stops can be used intentionally.

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

**v2 improvements (recommended):**
- Make the holewarp branch an intentional choice:
  - place the south stop immediately adjacent to the drop so it reads as “commit to the fall”.
- Ensure the exploration chest branch is solvable with **junction choice only** (no switch logic needed).

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

**v2 improvements (recommended):**
- Keep this room single-purpose:
  - exactly 1 switch corner that blocks the exit in the default state
  - crystal switch reachable without leaving camera view
- Add a “parking stop” right before the switch corner so the player can dismount and hit the switch without walking across the room.

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

**v2 improvements (recommended):**
- Reduce cognitive load by making one cart clearly the **main path** and one cart clearly the **reward path**:
  - main path cart is nearest the `0xA8` arrival
  - reward cart is nearest the staircase so it feels optional
- Avoid “both carts lead to nothing” states:
  - at least one cart/switch state should always return to a neutral stop (short recovery).
- Keep the switch effect legible:
  - one switch state corresponds to “left route”, the other to “right route” (don’t hide it behind multiple corners).

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

**v2 improvements (recommended):**
- Treat `0xDA` as the “breather” before B2 speed:
  - cart starts here at normal speed
  - player can safely dismount and see the gauntlet entry before committing
- Place the optional chest stop so it does not force a full reset to resume the main ride.

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

**v2 improvements (recommended):**
- Keep the “wrong switch state” punishment short:
  - wrong route should lead to a stop that returns you to the entry point, not to a long on-foot backtrack.
- If speed is enabled here, add at least one straightaway before the first decision so the player acclimates.

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

**v2 improvements (recommended):**
- Make the boss approach “two-step readable”:
  1. one ride gets the Big Key (or positions you to reach it)
  2. one ride takes you to the boss door (cart-required shutter)
- Keep all required switch interactions in the same camera quadrant as the relevant junction.

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

### Phase 0: Fix Authoring Invariants (Before New Puzzles)

Goal: make the existing rooms *actually runnable* so iteration isn’t fighting despawns/invalid states.

1. For each in-scope room, ensure custom collision exists (minecart tiles present).
2. Ensure every cart is placed on a stop tile (`$B7-$BA`).
3. If a cart is moved to a new start stop, update `Sprites/Objects/data/minecart_tracks.asm` so first-load `_Prep` does not kill it.
4. Re-run validation until clean:
   - `z3ed dungeon-minecart-audit --only-issues` (must be empty for targeted rooms)
5. Only after Phase 0 is true should we start layering switch corners, multi-cart forks, speed zones, and cart-required shutters.

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
