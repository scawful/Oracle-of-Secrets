# Release Candidate Content Checklist

**Created:** 2026-02-12
**Last assessed:** 2026-07-24 (code/static readback reconciliation; full runtime
sweep pending)
**Reference:** `release_2026_definition.md` (RC gate criteria)
**Purpose:** Track what content is needed before declaring RC. This is the "what's missing" list.

---

## RC Gate (from release_2026_definition.md)

> All dungeons playable end-to-end, final dungeon sequence, full narrative, pass full regression suite.

---

## Dungeon Playability

| Dungeon | Rooms | Boss | Item | Connectivity | Playable? | Top Blocker |
|---------|-------|------|------|-------------|-----------|-------------|
| D1 Mushroom Grotto | Assumed OK | Assumed OK | Assumed OK | Assumed OK | **Unverified** | Runtime test needed |
| D2 Tail Palace | Assumed OK | Assumed OK | Assumed OK | Assumed OK | **Unverified** | Runtime test needed |
| D3 Kalyxo Castle | Phase A done | Partial | Unknown | Partial | **No** | Disassembly + yaze |
| D4 Zora Temple | 16 assessed | Arrghus coded | Unknown | Partial | **No** | 3 unconverted rooms, water gate untested |
| D5 Glacia Estate | 19 exist | Twinrova **coded** | Fire Rod **unverified** | **Unmapped** | **No** | Room connectivity unmapped; 5/19 stale labels |
| D6 Goron Mines | 4 flagged | Unknown | Unknown | Unknown | **No** | Minecart track placement |
| D7 Dragon Ship | 17 mapped | Kydrog combat code exists; runtime unverified | Somaria **unverified** | **Good** (20 doors, 6 stairs) | **No** | Rescue scaffold exists but defaults OFF and lacks maiden/warp/NPC/endgame flow |
| D8 Fortress | Unknown | Dark Link mid-boss | Unknown | Unknown | **Unknown** | Needs full assessment |
| S1 Shrine of Wisdom | 7 exist | None | Flippers | Partial | **No** | Source-patched/read back as 0x39; runtime pickup unverified |
| S2 Shrine of Power | 7 rooms mapped in `dungeons.json` | **None (by design)** | Power Glove | Good (mapped set) | **No** | Source-patched/read back as 0x3A; runtime pickup and lava collision unverified |
| S3 Shrine of Courage | 8 rooms (4 mapped in `dungeons.json`) | **No boss code** (Vaati designed, not implemented) | Mirror Shield | **Partial** | **No** | Remaining rooms not modeled (0x07/0x16/0x23/0x26); Vaati reward path not implemented; entrance shared with D8 |

### Critical Cross-Dungeon Issue: Pendant Reward Alignment

| Shrine | Expected Pendant | Reward Source | Current Evidence | Remaining Gate |
|--------|------------------|---------------|------------------|----------------|
| S1 Wisdom | 0x39 (Wisdom) | Chest room 0x7A | Source patch + z3ed readback: 0x39 | Runtime pickup/progression |
| S2 Power | 0x3A (Power) | Chest room 0x73 | Source patch + z3ed readback: 0x3A | Runtime pickup/progression |
| S3 Courage | 0x38 (Courage) | Vaati boss clear | Not implemented | Implement and runtime-verify Vaati reward |

`Core/patches.asm` reproducibly patches room 0x7A to 0x39 and room 0x73
to 0x3A. `z3ed dungeon-list-chests` readback confirms those values in the
current patched ROM; runtime pickup/progression remains unverified. S3's Vaati
reward remains unimplemented.

### Room Ownership Conflict: S2 vs S3 — RESOLVED 2026-02-13

Rooms 0x33, 0x43, 0x53, 0x63 belong to **Shrine of Courage (S3)** per ROM and user decision.

**Corrections applied:**
- `oracle_room_labels.json`: Relabeled 0x33/0x43/0x53/0x63 from "Shrine of Power" to "Shrine of Courage"
- `location_registry.json`: Fixed shrine_courage rooms (removed 0x17, added 0x63)
- `ShrineofCourage.md` / `ShrineofPower.md`: Updated with room lists and issues
- `Dungeons.md`: Status corrected from "Complete" to Beta/Stub

**Still needs manual fix:**
- `dungeons.json`: SOC still needs the remaining rooms (0x07/0x16/0x23/0x26) modeled with connectivity.
- Lanmolas in room 0x33 is a vanilla leftover — not the intended S3 boss (Vaati).
- S3 entrance conflict remains (shared 0x0C with Fortress of Secrets).

### D7 Victory Pipeline (Biggest Narrative Gap)

A feature-gated partial scaffold exists, defaults OFF, and is incomplete:
1. `KydrogBoss_Death` calls `KydrogBoss_Death_FaroreRescueScaffold` only
   when `!ENABLE_D7_FARORE_RESCUE_SEQUENCE == 1`.
2. `KydrogBoss_ApplyFaroreRescueProgression` sets the D7 crystal bit and
   `GameState_FaroreRescued` late in the death timer.
3. The scaffold uses temporary message 0x138; the
   crystal-maiden/cutscene/warp handoff is not implemented or runtime-verified.
4. Post-rescue Hall of Secrets Farore states are not implemented.
5. The endgame/credits transition is not wired or runtime-verified.

---

## Narrative Content

### Core Story NPCs (must work for RC)

| NPC | Dialogue | Logic | Runtime Tested |
|-----|----------|-------|----------------|
| Maku Tree | 4 crystal-threshold messages | SelectReactionMessage wired | NOT TESTED |
| Impa | Multiple states | Spawn point flag works | Partially |
| Kydrog | Intro dialogue exists | Warp + banishment works | Partially |
| Farore | Follower dialogue exists | Follower state machine | Partially |
| Village Elder | 2 messages, post-D1 hint draft | Flag setter confirmed | NOT TESTED |
| Mask Salesman | Ocarina + Song of Healing | Complete | Assumed working |
| Deku Scrub | Withered + soul freed | Complete | Assumed working |
| Ranch Girl | Restored dialogue | Complete | Assumed working |
| Zora Princess | Base dialogue + conspiracy reveal | Working | Needs expansion |

### Quest NPCs (needed for RC)

| NPC | Dialogue Status | Assigned To |
|-----|----------------|-------------|
| Goron Elder | **In ROM (expanded)** (0x1E0-0x1E4, 5 msgs) | Imported into `Core/message.asm`; runtime validation pending |
| Windmill Guy | **In ROM (expanded)** (0x1D5-0x1D8, 4 msgs) | Imported into `Core/message.asm`; runtime validation pending |
| Zora Baby (D4 follower) | 5 messages exist (0x108-0x10C) | Verify sufficient |
| Bean Vendor | **In ROM (expanded)** (0x1E8-0x1EA, 3 msgs) | Imported into `Core/message.asm`; runtime validation pending |
| River Zora Elder | **In ROM (expanded)** (0x1E5-0x1E7, 3 msgs) | Imported into `Core/message.asm`; runtime validation pending |
| Cartographer | **In ROM (expanded)** (0x1EB-0x1EF, 5 msgs) | Imported into `Core/message.asm`; runtime validation pending |
| Koroks (10) | **In ROM (expanded)** (0x1F0-0x1F9, 10 msgs) | Imported into `Core/message.asm`; runtime validation pending |
| Maiden Upgrades (3) | **Drafted (vanilla bank)** (0x132/0x133/0x137) | Bundle delivered; vanilla-bank import still pending |

**Dialogue import status (2026-02-22):**
- Expanded: 30 authored messages from 6 bundles are in `Core/message.asm` (`$1D5-$1F9`) plus 10 continuity placeholders in `$1D2-$1F9`.
- Vanilla: maiden upgrades (3 messages) still pending import/apply.

### Content That Can Wait (Post-RC)

| Content | Reason |
|---------|--------|
| Cartographer dialogue | Side quest, not progression-critical |
| Korok lore fragments | Side content in optional area |
| River Zora Elder reconciliation | Post-D6 side content |
| Dream sequences (all 5) | Polish — story works without them |
| Gossip stones (all 21) | Ambient lore, not gating |
| Maiden identity upgrades | Current generic text is functional |

---

## Progression Systems

| System | Status | Test Method |
|--------|--------|-------------|
| Crystal collection (7 dungeons) | Partial; D7 setter exists only in an OFF-by-default, unverified scaffold | Mesen2 SRAM injection |
| GetCrystalCount | Complete, untested | Maku Tree test |
| UpdateMapIcon | Complete, untested | Maku Tree test |
| SelectReactionMessage | Complete, untested | Maku Tree test |
| D4 Water Gate hooks | Enabled, untested | D1-D7 regression suite |
| Minecart system | Feature-gated OFF | Needs track placement first |
| Song of Healing triggers | Implemented | Manual test |
| Mask transformations | Designed | Unknown impl status |

---

## What Must Be True for RC

1. Player can reach and complete all 8 dungeons (D1-D8) in some order
2. Player can reach and complete all 3 shrines (S1-S3) and forge Master Sword
3. Final boss sequence is reachable and completable
4. No hardlocks in the critical path
5. All progression-critical NPCs have real dialogue (not placeholders)
6. Crystal count properly tracks and gates content
7. Full regression suite passes

---

## Biggest Unknowns (Updated 2026-02-13)

1. ~~D5, D7, S1-S3 have not been assessed~~ **DONE** — assessed 2026-02-13, results above
2. **No current-ROM end-to-end dungeon verification is recorded**
3. **Progression helpers are untested** — the foundation of NPC dialogue gating
4. **Final boss sequence** — Kydreeok → Temporal Pyramid → Ganondorf three-phase — implementation status unclear
5. **Mask transformation mechanics** — designed but implementation status unknown
6. **D7 Farore rescue pipeline** — scaffold exists but post-D7 sequence remains incomplete
7. **Pendant reward validation is incomplete** — S1/S2 source patches and readback are correct, but runtime pickup is unverified; S3 Vaati reward path is missing
8. **S3 Shrine of Courage** — no dungeons.json entry, no boss code, shares entrance with D8, room conflict with S2
9. **D8 Fortress of Secrets** — still needs full assessment (rooms, boss, connectivity)
