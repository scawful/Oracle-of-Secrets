# Oracle of Secrets - Sprite Catalog

**Last Updated:** 2026-01-23
**Status:** Complete (initial pass)

This document catalogs all custom sprites, their technical status, and known issues.

## Summary

| Category | Total Files | Done | Needs Work | Placeholder |
|----------|-------------|------|------------|-------------|
| Bosses | 12 | 9 | 3 | 0 |
| Enemies | 16 | 9 | 7 | 1 |
| NPCs | 26 | 21 | 4 | 1 |
| Objects | 8 | 8 | 0 | 0 |
| **Total** | **62** | **47** | **14** | **2** |

**Key Issues to Address:**
- Prober logic bugs (Booki, Darknut, guards) - needs vanilla probe research
- Kydreeok AI overhaul needed
- Lanmola + Minecart performance conflict
- Eon Zora Elder missing dialogue handler
- Maku Tree needs progress dialogue expansion

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ Done | Functional, no known issues |
| ⚠️ Needs Work | Has bugs or incomplete features |
| 🔲 Placeholder | Stub or not yet implemented |

---

## Bosses (14 files)

| Sprite | Status | Location | Vanilla Base | Notes |
|--------|--------|----------|--------------|-------|
| **Arrghus** | ✅ Done | D4 (Zora Temple) | Vanilla Arrghus | Tweaked with lasers |
| **Dark Link** | ✅ Done | D8 (Temporal Pyramid) | All Hallows Eve | Custom asset, works well |
| **King Dodongo** | ✅ Done | D6 (Goron Mines) | Helmasaur reskin | Graphics swap |
| **Kydreeok** | ⚠️ Needs Work | D7 (Dragon Ship) | Custom | Boring fight, needs attacks/AI overhaul |
| **Kydrog Boss** | ✅ Done | D7 (Dragon Ship) | Custom | Solid, fun fight |
| **Kydrog NPC** | ✅ Done | Various cutscenes | Custom | Could free slot later |
| **Lanmola** | ⚠️ Problematic | D6 (Goron Mines) | Vanilla Lanmola | Causes lag with minecart, may need rework |
| **Manhandla** | ✅ Done | D1 (Mushroom Grotto) | Custom two-phase | User's custom boss, well-designed |
| **Octoboss** | ⚠️ Needs Fix | D2 (Tail Palace) | Custom | Camera offset hardcoded wrong |
| **Twinrova** | ✅ Done | D5 (Glacia Estate) | Custom | User's custom, MVP+ quality |
| **Vampire Bat** | ✅ Done | D1 miniboss | Custom | Reusable for other dungeons |
| **Wolfos** | ✅ Functional | Overworld night | Custom | Night-only spawn, gives mask reward |

### Boss Technical Notes

- **All Hallows Eve assets** (Dark Link, Poltergeist) are proven and stable
- **Kydreeok** is the main boss needing AI/attack overhaul
- **Lanmola + Minecart** lag issue may require choosing one or the other
- **Octoboss** camera fix is likely a simple coordinate adjustment

---

## Enemies (16 files)

| Sprite | Status | Location | Vanilla Base | Notes |
|--------|--------|----------|--------------|-------|
| **Anti Kirby** | ✅ Done | Eon Abyss | Custom | Sucks Link in, steals hat, fun mechanic |
| **Booki** | ⚠️ Needs Work | Overworld night | Custom | Distance check works, but can "see" through walls. Night-only |
| **Business Scrub** | ✅ Done | Kalyxo overworld | Custom | Deflect/barrier mechanic works well |
| **Custom Guard** | 🔲 Placeholder | Castle prison | TBD | For story sequence |
| **Darknut** | ⚠️ Needs Work | Dungeons | Custom | Alert via damage only; probe doesn't signal parent |
| **Eon Scrub** | ✅ Done | Eon Abyss | 8-bit variant | Merge candidate with Business Scrub |
| **Goriya** | ⚠️ Needs Polish | Various | Custom | Sluggish boomerang/AI |
| **Helmet Chuchu** | ✅ Done | Dungeons | Custom | Hookshot removes helmet, good design |
| **Keese** | ⚠️ Mostly Done | Various | Vanilla base | Fire/ice variants uncertain, shares handler with Vampire Bat |
| **Leever** | ✅ Needs Review | Desert/beach | Vanilla base | Collision handling may need review |
| **Octorok** | ⚠️ Issues | Both worlds | Vanilla + 8-bit | 8-bit draw wrong, needs routine split |
| **Pols Voice** | ✅ Done | Dungeons | Custom | Simple, functional |
| **Poltergeist** | ✅ Done | Haunted areas | All Hallows Eve | Proven asset |
| **Puffstool** | ✅ MVP | Forest areas | Custom | Could polish but functional |
| **Sea Urchin** | ✅ Done | Water areas | Custom | Works in both worlds |
| **Thunder Ghost** | ⚠️ Attack Buggy | Fields/mountains | 16-bit Kalyxo | Thunder attack needs work |

### Enemy Technical Notes

#### Prober Logic System
⚠️ **Needs Research** - Vanilla probe doesn't signal the way we assumed:
- **Booki:** Using distance check (works, sees through walls)
- **Darknut:** Alert via damage only, probe spawns but doesn't trigger chase
- **Custom Guard:** Will need proper implementation
- **See:** Priority 1 section below for research plan

#### 8-bit vs 16-bit Draw Routines
Some sprites need separate draw routines for different areas:
- **Octorok:** Needs split (8-bit Abyss vs 16-bit Kalyxo)
- **Eon Scrub:** Could merge with Business Scrub using draw routine switch
- **Pattern:** World flag check → branch to appropriate draw routine

#### Day/Night Spawning
Working examples exist:
- **Wolfos:** Night-only spawn (functional)
- **Booki:** Night-only spawn (has other bugs)
- Could document and reuse this pattern

---

## NPCs (26 files)

### Story-Critical NPCs

| Sprite | Status | Location | Role | Notes |
|--------|--------|----------|------|-------|
| **Farore** | ✅ Functional | Hall of Secrets, Intro | Oracle of Secrets, main quest giver | 8 states for intro cutscene, TODO: post-rescue states |
| **Maku Tree** | ⚠️ Needs Work | Hall of Secrets | Quest hub, essence tracker | Gives heart container, sets MapIcon. TODO: OoA/OoS-style progress dialogue |
| **Impa** | ✅ Done | Intro sequence | Replaces Zelda as intro guide | ROM hooks extend vanilla behavior, follower system |
| **Zora Princess** | ✅ Done | D4 (Zora Temple) | Gives Zora Mask, Schism reveal | Part of Zora dispatcher, room 0x105 detection |
| **Ranch Girl** | ✅ Done | Ranch | Cucco→Human transformation, gives Ocarina | Magic Powder triggers transformation |
| **Village Elder** | ✅ Done | Wayward Village | Tutorial NPC, sets OOSPROG bit 4 | Progress-based dialogue |

### Zora NPCs

| Sprite | Status | Location | Vanilla Base | Notes |
|--------|--------|----------|--------------|-------|
| **Zora (Dispatcher)** | ✅ Done | Various | Custom | Routes to 4 variants via ROOM/WORLDFLAG/SprSubtype |
| **Sea Zora** | ✅ Done | Kalyxo waters | Default variant | Head tracks player, 3 dialogue states |
| **Eon Zora** | ✅ Done | Eon Abyss | WORLDFLAG=1 variant | Location-based dialogue, random ring drops |
| **Eon Zora Elder** | ⚠️ Incomplete | S1 (Sea Shrine) | SprSubtype=1 | TODO: dialogue handler (messages 0x1F0+) |

### Vendor/Service NPCs

| Sprite | Status | Location | Service | Notes |
|--------|--------|----------|---------|-------|
| **Bean Vendor** | ✅ Done | Various | Sells Magic Beans (10 rupees) | Complex: planting, bee pollination, flower ride. Also contains Village Elder subtype |
| **Bottle Vendor** | ✅ Done | Village shop | Sells Milk (30 rupees) | Simple shop sprite |
| **Mask Salesman** | ✅ Done | Tail Pond | Teaches Song of Healing, sells masks | 11 states, Bunny Hood (100r), Stone Mask (850r) |
| **Vasu** | ✅ Done | Ring shop | Ring appraisal | "I am Error" easter egg on subtype 1 |
| **Tingle** | ✅ Done | Overworld | Sells dungeon maps (7 maps) | 200 rupees each |
| **Fortune Teller** | ✅ Done | Village | Progress-based hints | Checks Crystals, OOSPROG for dialogue |
| **Mermaid** | ✅ Done | Various | 3-in-1: Mermaid, Maple, Librarian | Librarian has scroll translation system |

### Race/Tribe NPCs

| Sprite | Status | Location | Vanilla Base | Notes |
|--------|--------|----------|--------------|-------|
| **Goron** | ✅ Done | Both worlds | Custom | Kalyxo: Rock Meat quest (5 needed). Eon: Lore with singing/punching |
| **Korok** | ✅ Functional | Forest areas | Custom | 3 visual variants (Makar, Hollo, Rown). TODO: minigame tracking, unique dialogue |
| **Piratian** | ✅ Done | Various | Custom | Dual behavior: friendly (peacetime) / aggressive (hostile) |
| **Deku Scrub** | ✅ Done | Forest, Eon Abyss | Custom | Multi-variant: Withering Deku (Deku Mask via Song of Healing), Butler, Princess |

### Guide/Helper NPCs

| Sprite | Status | Location | Role | Notes |
|--------|--------|----------|------|-------|
| **Eon Owl** | ✅ Done | Eon Abyss | Warp points, Song of Soaring | Two-in-one with Kaepora Gaebora (subtype 1) |
| **Village Dog** | ✅ Done | Both worlds | Ambient, special dialogue | Minish Mask / Wolf Mask interactions |
| **Bug Net Kid** | ✅ Done | Village | Gives Boots | Requires Song of Healing |

### Followers

| Sprite | Status | Location | Role | Notes |
|--------|--------|----------|------|-------|
| **Zora Baby** | ✅ Done | D4 area | Pull switches, become follower | Part of followers.asm |
| **Old Man** | ✅ Done | Mountain | Gives Goldstar hookshot upgrade | Part of followers.asm |
| **Minecart Follower** | ✅ Done | D6 transitions | Link rides minecart | Handles room transitions |
| **Kiki** | ✅ Modified | Forest | Vanilla Kiki with modifications | Part of followers.asm |

### Dream/Cutscene NPCs

| Sprite | Status | Location | Role | Notes |
|--------|--------|----------|------|-------|
| **Hyrule Dream Zelda** | ✅ Done | Dream sequence | Memory scene | Part of hyrule_dream.asm |
| **Hyrule Dream King** | ✅ Done | Dream sequence | Memory scene | Part of hyrule_dream.asm |
| **Hyrule Dream Soldier** | ✅ Done | Dream sequence | Memory scene | Part of hyrule_dream.asm |

### NPC Technical Notes

#### Multi-Variant Dispatcher Pattern
Several NPCs use a dispatcher pattern that routes to different behaviors:
- **Zora:** Routes via ROOM (0x105=Princess), WORLDFLAG, SprSubtype
- **Bean Vendor:** Contains Village Elder as subtype
- **Mermaid:** Routes to Mermaid/Maple/Librarian via SprSubtype
- **Deku Scrub:** Routes to Withering/Butler/Princess via SprSubtype and AreaIndex

#### Common Patterns Across NPCs
- **Song of Healing:** Used by Mask Salesman (teaches), Deku Scrub (Deku Mask), Bug Net Kid (Boots)
- **WORLDFLAG routing:** Zora, Goron, Village Dog, Piratian
- **Progress-based dialogue:** Fortune Teller, Maku Tree, Village Elder
- **SideQuestProg flags:** Korok minigame, trading sequence tracking

#### Files Needing Attention
| File | Issue | Priority |
|------|-------|----------|
| eon_zora_elder.asm | Missing dialogue handler | Medium |
| maku_tree.asm | Needs progress dialogue expansion | Medium |
| farore.asm | Needs post-rescue states | Medium |
| korok.asm | TODO: minigame tracking system | Low |

---

## Objects (8 files)

| Sprite | Status | Location | Purpose | Notes |
|--------|--------|----------|---------|-------|
| **Collectible** | ✅ Done | Various | Multi-item: Pineapple, Seashell, Sword/Shield, Rock Sirloin | AreaIndex routing (0x58=sword, 0x4B=sirloin) |
| **Deku Leaf** | ✅ Done | Forest, Water | Platform + Whirlpool portal | Two modes: leaf ride (cape flag) + whirlpool warp |
| **Mine Switch** | ✅ Done | D6 (Goron Mines) | Lever toggle + Speed switch | SwitchRam array tracks on/off state |
| **Pedestal** | ✅ Done | Temples | Song of Zora + Book interaction | Zora Temple (0x1E), Goron Desert (0x36), Fortress (0x5E) |
| **Portal Sprite** | ✅ Done | Various | Blue/Orange portal warp system | Works in dungeons and overworld, tile collision rejection |
| **Switch Track** | ✅ Done | D6 (Goron Mines) | Rotating track for minecart | Reads tile IDs (0xD0-0xD3), state from SwitchRam |
| **Minecart** | ✅ Done | D6 (Goron Mines) | Rideable minecart puzzle system | Complex: track persistence, room transitions, switch tiles, corners |
| **Ice Block** | ✅ Done | D5 (Glacia Estate) | Pushable sliding puzzle block | Direction locking, switch detection, grid snapping |

### Object Technical Notes

#### Minecart System (D6)
The minecart system is sophisticated and spans multiple files:
- **minecart.asm:** Main cart logic, track memory, room transitions
- **switch_track.asm:** Visual track indicators that rotate based on SwitchRam state
- **mineswitch.asm:** Lever switches to toggle track state
- **followers.asm:** Minecart Follower for cross-room persistence

Track tiles (0xB0-0xBE, 0xD0-0xD3) define movement behavior:
- Corners auto-turn the cart
- Intersections allow player input
- Stops halt the cart
- Switches change direction based on lever state

#### Portal System
The portal sprite implements a Portal-style warp mechanic:
- Blue/Orange portals alternate on spawn
- Works in both dungeons and overworld
- Rejects invalid placement (tile collision check)
- Handles camera and scroll boundaries

#### Collectible Multi-Item Pattern
Single sprite handles 4 different collectibles via AreaIndex:
- Default: Pineapple (increments Pineapples counter)
- Default: Seashell (increments Seashells counter)
- Area 0x58: Sword/Shield (intro sequence, checks $7EF359)
- Area 0x4B: Rock Sirloin (requires power gloves, increments RockMeat)

---

## Technical Patterns to Address

### Priority 1: Prober Logic Refactor

**⚠️ NEEDS RESEARCH (2026-01-23)**

#### Problem

The vanilla probe system does NOT set `SprTimerD` on the parent sprite. Initial implementation was based on incorrect assumptions.

#### Vanilla System (Research Needed)

The vanilla guard detection uses `Sprite_SpawnProbeAlways_long` at `$05C66E`:
- Spawns invisible sprite ID `$41` as probe
- Probe checks `CheckTileSolidity` as it travels toward Link
- Wall hit → despawn without alert
- Link contact → **sets parent's STATE**, not a timer

**Key Variables (need verification):**
- `$0DB0,X` - Probe parent sprite ID (parent slot + 1)
- `$0F60,X` - Probe lifetime timer (starts at `$40`)
- `$0D80,X` - Guard STATE (3 = chase) - this is what probe sets, NOT `SprTimerD`

#### Current State

- **Booki:** Reverted to distance check (works, but sees through walls)
- **Darknut:** Uses probe but detection is via damage, not probe contact
- **Helper routines:** `Sprite_SpawnProbeWithCooldown` exists but doesn't solve the signaling issue

#### Next Steps

1. Study vanilla `Probe` routine at `$05C15D` to find how it signals parent
2. Determine if Oracle sprites can use `$0D80,X` (SprAction) like vanilla guards
3. Or implement custom raycast with tile collision checking

### Priority 2: 8-bit/16-bit Draw Routine System
- Document the pattern
- Apply to: Octorok, Scrubs
- Consider macro or include for reuse

### Priority 3: Day/Night Spawn Conditions
- Document working Wolfos implementation
- Create reusable pattern
- Apply to: Booki (after other bugs fixed), future night creatures

### Priority 4: Multi-Variant Dispatcher Pattern
Document and standardize the dispatcher approach used by:
- Zora (ROOM/WORLDFLAG/SprSubtype routing)
- Mermaid (SprSubtype routing to 3 variants)
- Deku Scrub (SprSubtype + AreaIndex routing)
- Collectible (AreaIndex routing to 4 item types)

### Priority 5: Progress-Based Dialogue System
Create reusable macros for NPCs that change dialogue based on:
- Crystals bitfield (dungeon completion)
- OOSPROG bitfield (story progress)
- SideQuestProg flags (side quest completion)
- MapIcon (current objective)

### Priority 6: Follower System Documentation
The followers.asm file contains complex cached position/animation code:
- Document position caching mechanism
- Standardize follower initialization
- Create template for new followers

---

## Graphics & VRAM Notes

*To be filled in after yaze/z3ed analysis:*
- Graphics group assignments
- VRAM slot usage
- Vanilla sprite replacements
- Sheet requirements

---

## Related Documents

- `Docs/Planning/narrative_design_master_plan.md` - Story context for sprites
- `Docs/Lore/dungeon_narratives.md` - Where bosses appear
- `Core/messages.org` - Sprite dialogue (if any)
