# Narrative Plan: Technical Feasibility Assessment

**Status:** Active Analysis
**Date:** 2026-01-22
**Related:** `~/.claude/plans/oracle-narrative-lockdown.md`, `~/.claude/plans/jiggly-spinning-newt.md`

---

## Executive Summary

The Oracle of Secrets codebase has a **robust, modular system** for NPCs, dialogue, and story progression. The narrative plans outlined in the lockdown and Zora conflict documents are **technically feasible** with moderate effort. This document maps each narrative element to its technical implementation requirements.

---

## System Capabilities

### What Already Exists

| Capability | Implementation | Complexity |
|------------|----------------|------------|
| **NPC dialogue** | `%ShowSolicitedMessage()` / `%ShowUnconditionalMessage()` | ✅ Easy |
| **Choice branches** | `$1CE8` register + `[CH2I]`/`[CH3]` control codes | ✅ Easy |
| **Conditional dialogue** | SRAM flag checks in state handlers | ✅ Easy |
| **Item grants** | `Link_ReceiveItem` with item index | ✅ Easy |
| **Follower system** | 14 follower types in `followers.asm` | ✅ Exists |
| **Song triggers** | `SongFlag` register (see Zora Princess) | ✅ Easy |
| **Cutscene control** | `SprAction` state machine + timers | ✅ Moderate |
| **Multi-NPC variants** | `SprSubtype` + handler dispatch (see zora.asm) | ✅ Moderate |
| **Area-based dialogue** | `AreaIndex` checks (see eon_zora.asm) | ✅ Easy |

### Message ID Allocation

**Current highest ID:** `0x1BB` (Piratian Friendly Hint)

**Available ranges for new content:**
| Range | Suggested Use |
|-------|---------------|
| `0x1C0-0x1CF` | River Zora NPCs (East Kalyxo) |
| `0x1D0-0x1DF` | Reconciliation scene dialogue |
| `0x1E0-0x1EF` | Sky Shrine / Observatory |
| `0x1F0-0x1FF` | Sea Shrine / Eon Zora Elder |
| `0x200-0x20F` | Kydrog endgame dialogue (Kydreeok, death scene) |
| `0x210-0x21F` | Dark Link expanded dialogue |
| `0x220-0x22F` | Farore post-D7 exposition |
| `0x230-0x23F` | Gossip Stones (Kydrog backstory, Zora lore) |

---

## Narrative Element Feasibility

### 1. Kydrog Backstory & Death Scene

**Plan:** Kydrog as fallen knight, imperial tool, bitter death scene
**Technical Requirement:** Enhanced dialogue at D7, Fortress, and Lava Lands

| Element | Status | Implementation |
|---------|--------|----------------|
| D7 defeat dialogue | 🟡 Needs update | Modify message `0x21` or add new sequence |
| Kydreeok pre-fight | ⚪ New | Add state in `kydreeok.asm` |
| Death scene | ⚪ New | Add state + messages `0x200+` |
| Fortress collapse trigger | 🔶 Complex | Needs map transition code |

**Files to modify:**
- `Sprites/Bosses/kydrog.asm` - D7 dialogue states
- `Sprites/Bosses/kydreeok.asm` - Final boss dialogue states
- `Core/messages.org` - New dialogue entries

**Complexity:** 🟡 Moderate - Dialogue is straightforward, collapse sequence needs map work

---

### 2. Dark Link Enhanced Role

**Plan:** Knight's rejected heroism, mid-boss at Fortress
**Technical Requirement:** Pre-fight and post-fight dialogue states

| Element | Status | Implementation |
|---------|--------|----------------|
| Current implementation | ✅ Exists | Messages `0x13E`, `0x16F`, `0x170` |
| Pre-fight dialogue | 🟡 Partial | Message `0x13E` exists ("Dark Link Intro") |
| Post-fight revelation | 🟡 Needs expand | Add messages `0x210+` |

**Complexity:** 🟢 Easy - Existing framework, just add dialogue

---

### 3. Farore Post-D7 Exposition

**Plan:** Farore reveals truth about Ganondorf, guides to Master Sword
**Technical Requirement:** New NPC state at Hall of Secrets

| Element | Status | Implementation |
|---------|--------|----------------|
| Farore sprite | ✅ Exists | `farore.asm` has 7 action states |
| Post-rescue state | ⚪ New | Add action state 8+ for Hall of Secrets |
| Exposition dialogue | ⚪ New | Messages `0x220+` |
| Conditional spawn | 🟡 Modify | Check `$7EF3??` for D7 completion |

**Files to modify:**
- `Sprites/NPCs/farore.asm` - Add post-rescue states
- `Core/messages.org` - Exposition dialogue

**Complexity:** 🟡 Moderate - State machine expansion

---

### 4. Zora Conflict Resolution

**Plan:** D4 revelation → East Kalyxo reconciliation → Side content unlock

#### D4: Zora Princess Enhancement

| Element | Status | Implementation |
|---------|--------|----------------|
| Current sprite | ✅ Exists | `zora_princess.asm` - 4 states |
| Song of Healing trigger | ✅ Exists | `SongFlag` check works |
| Enhanced dialogue | 🟡 Modify | Update message `0xC6` |
| Post-revelation state | ⚪ New | Add states for Zora Baby reaction |

**Complexity:** 🟢 Easy - Mostly dialogue updates

#### Zora Baby D4 Integration

| Element | Status | Implementation |
|---------|--------|----------------|
| Zora Baby follower | ✅ Exists | Follower type `0x09` |
| D4 dungeon presence | 🔶 Design needed | Place in dungeon maps |
| Dialogue reactions | ⚪ New | Add messages for revelation |

**Complexity:** 🟡 Moderate - Follower placement in dungeon is design work

#### East Kalyxo River Zora Village

| Element | Status | Implementation |
|---------|--------|----------------|
| Region maps | ⚪ New | Need map design (0x90-0x9B) |
| River Zora NPCs | ⚪ New | Need sprite variant |
| Reconciliation scene | ⚪ New | Multi-message sequence |
| Elder NPC | ⚪ New | New sprite or reuse existing |

**River Zora sprite options:**
1. **Reuse ALTTP enemy sprite** - Already in vanilla, need to make it friendly
2. **Create new draw routine** - In `zora.asm`, add `Sprite_RiverZora_Draw`
3. **Palette swap existing** - Modify `SprSubtype` to select different properties

**Complexity:** 🟠 Moderate-High - Needs new map work + sprite variant

---

### 5. Sky Shrine & Observatory

**Plan:** Post-D7 weather mechanics, dream sequence showing Ganondorf

| Element | Status | Implementation |
|---------|--------|----------------|
| Sky Island maps | 🔶 Exists? | Maps 0x84-87, 0x8C-8F allocated |
| Weather system | ⚪ New | Need Song of Storms toggle |
| Cloud platforms | 🔶 Complex | Tile collision changes per weather |
| Dream sequence | 🟡 Partial | Dream system exists (`$7EF410`) |
| Observatory NPC | ⚪ New | Crystal lens interaction |

**Weather mechanics challenge:**
The plan calls for clouds that solidify/vaporize based on weather. This requires:
1. Tile type that changes collision based on flag
2. Song of Storms to toggle the flag
3. Visual tile swap or overlay

**Complexity:** 🔴 High - Weather-conditional collision is new ground

---

### 6. Sea Shrine & Eon Zora Elder

**Plan:** Elder guides to Sea Shrine, reveals portal magic history

| Element | Status | Implementation |
|---------|--------|----------------|
| Eon Zora Elder sprite | ✅ Exists | `eon_zora_elder.asm` - 3 states |
| Elder dialogue | ⚪ New | Messages `0x1F0+` |
| Sea Shrine location | 🔶 Map exists | Map 0x79 referenced |
| Vision sequence | 🟡 Use dreams | Mirror dream system |

**Files to modify:**
- `Sprites/NPCs/eon_zora_elder.asm` - Add dialogue states
- `Core/messages.org` - Elder lore dialogue

**Complexity:** 🟢 Easy - Mostly dialogue, existing sprites

---

### 7. Korok Minigame

**Plan:** 10 Koroks hidden in East Kalyxo, rupee + heart piece rewards

| Element | Status | Implementation |
|---------|--------|----------------|
| Korok sprite | ✅ Exists | `korok.asm` - 3 variants (Makar, Hollo, Rown) |
| Hide-and-seek mechanic | 🟡 Design | Sprite placement + collection counter |
| Reward system | 🟡 Modify | SRAM counter for found Koroks |
| Milestone checks | ⚪ New | Check counter, grant rewards |

**Implementation approach:**
- Use `SprSubtype` to differentiate 10 Korok instances
- SRAM bitfield for which Koroks found
- NPC that checks counter and grants rewards

**Complexity:** 🟡 Moderate - System design, not hard technically

---

### 8. Intro Cutscene ALTTP Mirror

**Plan:** Mirror ALTTP intro beats, establish Ganondorf/Knight backstory

| Element | Status | Implementation |
|---------|--------|----------------|
| Attract scene system | ✅ Exists | `attract_scenes.asm` |
| Current intro | ✅ Exists | Messages `0x112-0x115` |
| ALTTP-style narration | 🟡 Modify | Update attract scene messages |
| Visual beats | 🔶 Design | Need graphics for silhouettes |

**Files to modify:**
- `Core/messages.org` - Intro narration (0x112-0x115)
- `Dungeons/attract_scenes.asm` - Scene flow

**Complexity:** 🟡 Moderate - Dialogue is easy, graphics need work

---

## Risk Assessment

### Low Risk ✅
- All dialogue additions/modifications
- Existing NPC state expansions
- Gossip Stone content
- Dream sequences (system exists)

### Moderate Risk 🟡
- Follower placement in dungeons
- New NPC variants (River Zora)
- Korok collection system
- Fortress collapse → Lava Lands transition

### High Risk 🔴
- Weather-conditional collision (Sky Islands)
- New region maps (East Kalyxo full design)
- Attract scene graphics overhaul

---

## Recommended Implementation Order

1. **Dialogue First** - All message content can be written before code
2. **Existing NPC Expansion** - Farore, Dark Link, Kydrog dialogue states
3. **Zora Princess Enhancement** - D4 is early game, test narrative flow
4. **Eon Zora Elder Expansion** - Low risk, high narrative value
5. **Korok System** - Moderate complexity, self-contained
6. **East Kalyxo Region** - Requires map work, save for later
7. **Sky Islands Weather** - High complexity, optional enhancement

---

## Open Technical Questions

1. **Fortress collapse sequence** - How to transition from D8 boss room to ruins/caves? Need map event system or cutscene warp.

2. **River Zora sprite** - New graphics or palette swap? Affects Eon Abyss "corrupted" River Zoras too.

3. **Weather system scope** - Is this Sky Islands only, or should it affect other areas? Scope creep risk.

4. **Ganondorf fight implementation** - Plan says "if implemented" - what's the current sprite status?

5. **Message ID allocation** - Should we reserve ranges now or allocate as needed?

---

## Summary

| Category | Feasibility | Effort |
|----------|-------------|--------|
| **Dialogue/Story** | ✅ Fully feasible | Low-Medium |
| **NPC Behavior** | ✅ Mostly feasible | Medium |
| **New Regions** | 🟡 Feasible with work | High |
| **Weather Mechanics** | 🟠 Feasible but complex | Very High |
| **Ganondorf Boss** | ❓ Unknown (sprite work) | Unknown |

The narrative vision is **achievable** with the existing codebase. The main bottlenecks are:
1. Map design for East Kalyxo
2. Weather system complexity for Sky Islands
3. Sprite work if Ganondorf fight is desired

Most story content can proceed in parallel with these blockers.
