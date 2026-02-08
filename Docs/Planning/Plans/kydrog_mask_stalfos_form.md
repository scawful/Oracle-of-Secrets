# Kydrog Mask & Stalfos Form — Post-Kydreeok Design

## Summary

After defeating Kydreeok (the dragon boss), a Song of Healing sequence triggers Kydrog's redemption. His spirit condenses into the **Kydrog Mask**, which grants Link the **Stalfos Form** — a combat-oriented transformation with bone-based abilities. This document covers the full sequence from boss death to form availability, including Kydrog's act of severing the Sacred Realm–Abyss connection.

## Current State

### Boss: Kydreeok
**Files:** `Sprites/Bosses/kydreeok.asm`, `Sprites/Bosses/kydreeok_head.asm`
- Multi-head dragon boss with $C8 (200) HP per head
- States: Start → StageControl → Move → Dead → Flying
- Head respawn mechanic (lines 108–121)
- Final Boss music ($1F) on entry

### Form System
**File:** `Masks/mask_routines.asm`, various `Masks/*.asm`
- `!CurrentMask` at `$02B2` — current form ID
- Existing forms: Link (0), Deku (1), Zora (2), Wolf (3), Bunny Hood (4), Minish (5), GBC (6), Moosh (7)
- **Next available ID: 8 (Stalfos Form)**
- Transform routine: `Link_TransformMask` (mask_routines.asm line 302)
- Palette swap: `Palette_ArmorAndGloves` (mask_routines.asm line 97)

### Menu Slots
**File:** `Menu/menu_select_item.asm`
- Row 4 currently: Deku, Zora, Wolf, Bunny Hood, Stone Mask
- Item addresses: Deku=$7EF349, Zora=$7EF347, Wolf=$7EF358, Bunny=$7EF348, Stone=$7EF352
- **Kydrog Mask needs an available item address slot**

### GFX Source
Poltergeist sprite hack contains Stalfos-style GFX that can be adapted. File: `Sprites/Enemies/poltergeist.asm` — has bone/skeletal animation frames.

## Proposed Changes

### 1. Song of Healing Trigger Sequence

**Trigger condition:** Kydreeok death state completes (all heads HP = 0, boss enters final Dead state).

**Sequence choreography:**

```
1. Kydreeok death animation plays (existing)
2. Screen dims (INIDISP fade to ~$05)
3. Dragon form dissolves — sprite swap to Kydrog human spirit
4. Kydrog spirit hovers, facing Link
5. Dialogue box: Kydrog speaks his redemption lines
6. Prompt appears: "Play the Song of Healing? ▶ Yes  No"
7. If Yes: Song of Healing melody plays (SFX or short music cue)
8. Kydrog spirit animation: arms spread, light emanates
9. World state change: screen flash + rumble (Abyss connection severed)
10. Spirit condenses into mask — item get fanfare
11. "You got the Kydrog Mask!" item receipt sequence
12. Fade to post-boss room / warp out
```

**If No (or B-cancel):** Prompt re-appears after brief Kydrog dialogue urging Link. The player cannot leave without completing the sequence (boss room is sealed). This prevents soft-locking progression.

### 2. Kydrog Redemption Dialogue

**Pre-Song dialogue (32-char width):**
```
...Link.

I remember now. The green
of the forest. The weight
of a sword on my back.

I was like you, once.
Before the Abyss took
everything I was.

The connection between
this realm and the Sacred
Realm... I can sever it.

But I need your help.
Play the Song of Healing.
Let me do this one
last thing.
```

**Post-Song dialogue (during severing):**
```
The thread is cut.

He can no longer retreat
to the Sacred Realm when
his power fails him.

You will face him with
no safety net. And
neither will he.

Take this mask. What I
was... it may yet serve
what you must become.
```

### 3. Kydrog Mask Item

| Property | Value |
|---|---|
| Item address | TBD (needs free slot in `$7EF340`–`$7EF35F` range) |
| Form ID | `$08` (Stalfos Form) |
| Menu position | Row 4, column 6 (after Stone Mask) or replace Stone Mask |
| GFX tile | Skull mask icon (needs 16x16 item graphic) |
| Equip behavior | Same as other masks — select in menu, press Y to transform |

### 4. Stalfos Form Abilities

| Ability | Input | Description |
|---|---|---|
| **Bone Sword** | B button | Extended reach melee, slightly slower than Link's sword |
| **Bone Cast** (Y ability) | Y button | Throws a bone projectile in an arc — candidate ability, TBD |
| **Undead Resilience** | Passive | Takes half damage from dark/shadow enemies |
| **Abyss Affinity** | Passive | No damage from Abyss floor hazards |
| **Weakness** | Passive | Takes double damage from fire/light sources |

**Y Ability — Bone Cast (Candidate):**
The primary Y ability throws a bone in a parabolic arc (like boomerang trajectory but with gravity). Hits enemies for moderate damage. Could be used for puzzle switches at range. This is a candidate — alternatives include a ground-pound bone slam or a temporary bone shield.

### 5. Form System Integration

**New constant in `Core/sram.asm`:**
```asm
!Mask_Stalfos = $08
```

**New file:** `Masks/stalfos_form.asm`
- Transform animation (Link → skeleton sprite swap)
- B-button override (bone sword)
- Y-button override (bone cast)
- Passive damage modifiers
- Palette: grey/bone white

**Integration points:**
- `Masks/mask_routines.asm` — Add case `$08` to `Palette_ArmorAndGloves` and `Link_TransformMask`
- `Menu/menu_select_item.asm` — Add Kydrog Mask to Row 4
- `Core/sram.asm` — Define item address for Kydrog Mask
- `Items/sword_collect.asm` — No change (Stalfos Form has its own weapon)

### 6. World State Change — Abyss Severing

When Kydrog severs the Sacred Realm–Abyss connection:

**Mechanical effects:**
- Set SRAM flag: `!Story_AbyssSevered` (new flag in OOSPROG2)
- Ganondorf can no longer retreat to the Sacred Realm (narrative only — affects endgame dialogue)
- Eon Abyss visual change: sky color shifts from purple to dark red (palette swap on Abyss overworld areas)
- NPCs in the Abyss react (see `progression_infrastructure.md` for NPC reaction framework)

**Flag usage:**
```asm
!Story_AbyssSevered = $xx  ; bit in OOSPROG2 ($7EF3C6)
```

This flag gates:
- Ganondorf's final boss dialogue (references losing his escape route)
- Post-Kydreeok Gossip Stone messages
- Abyss overworld palette swap

## Affected Files

| File | Change |
|---|---|
| `Sprites/Bosses/kydreeok.asm` | Add post-death sequence hook (after Dead state) |
| `Masks/stalfos_form.asm` | **New file** — Stalfos Form implementation |
| `Masks/mask_routines.asm` | Add Stalfos case to palette and transform routines |
| `Core/sram.asm` | Add `!Mask_Stalfos`, `!Story_AbyssSevered`, item address |
| `Menu/menu_select_item.asm` | Add Kydrog Mask to menu grid |
| `Sprites/Enemies/poltergeist.asm` | Reference for GFX extraction (no code changes) |
| Dialogue table | Kydrog redemption dialogue, Song of Healing prompt |
| Overworld palette data | Abyss sky color change post-severing |

## Open Questions

1. **Y ability finalization:** Bone Cast (projectile arc) vs. Bone Slam (ground-pound AoE) vs. Bone Shield (temporary invulnerability). Needs gameplay testing.
2. **Song of Healing mechanic:** Is this a dedicated item (like the Ocarina), or a contextual prompt that only appears in this cutscene? If the Song exists as a usable item, it could be reused for the Zora Mask origin sequence (see `zora_mask_origin.md`).
3. **Item slot availability:** Need to verify a free address in the `$7EF340`–`$7EF35F` range. The Stone Mask at `$7EF352` may be the candidate if it's being cut.
4. **Stalfos Form GFX:** The poltergeist hack has skeletal frames, but a full Link-sized Stalfos sprite sheet may need custom pixel work. How much can be reused vs. drawn fresh?
5. **Form restriction zones:** Should Stalfos Form be blocked in certain areas (e.g., towns where NPCs would react negatively)?

## Dependencies

- `endgame_narrative_arc.md` — Kydrog's redemption is the climax of the Kydreeok fight; endgame dialogue references the severing.
- `zora_mask_origin.md` — If Song of Healing is a reusable mechanic, both masks use it.
- `gossip_stone_additions.md` — Post-severing Gossip Stone messages reference the world state change.
- `progression_infrastructure.md` — NPC reaction framework for post-severing dialogue changes.
