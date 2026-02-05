# Zora Mask Origin — Heroic River Zora Backstory

## Summary

Establish the narrative origin of the Zora Mask through a condensed Heroic River Zora backstory. A River Zora sacrificed herself to save a kidnapped Zora child in the Zora Temple (D4), and the Song of Healing transforms her lingering spirit into the mask. This uses existing Zora NPC dialogue slots — no new NPCs or sprites.

## Current State

### Zora NPC System (`Sprites/NPCs/zora.asm`)

**Variants (lines 51–86):**
| Variant        | Trigger        | SprMiscG | Context             |
|----------------|----------------|----------|---------------------|
| Sea Zora       | Default        | 0        | Overworld beach NPC |
| Zora Princess  | Room $0105     | 1        | D4 related          |
| Eon Zora       | WORLDFLAG = 1  | 2        | Abyss version       |
| Eon Zora Elder | SprSubtype = 1 | 3        | Abyss elder         |

**Existing dialogue messages:**
| ID     | Usage                                  | Current Content       |
|--------|----------------------------------------|-----------------------|
| `$1A4` | Sea Zora default (facing forward)      | Generic sea dialogue  |
| `$1A5` | Sea Zora alternative (facing sideways) | Generic sea dialogue  |
| `$1A6` | Post-D4 (Crystal bit $20 set)          | Post-dungeon reaction |

### Zora Mask Item
**File:** `Masks/zora_mask.asm`
- Item address: `$7EF347`
- Form ID: `$02` (in `$02B2`)
- Abilities: Swimming, underwater diving
- Menu position: Row 4, column 2

### Song of Healing
Per `kydrog_mask_stalfos_form.md`, the Song of Healing is used post-Kydreeok to create the Kydrog Mask. If it exists as a reusable mechanic, the Zora Mask origin uses the same song — establishing the Song of Healing → Mask creation pattern *before* the endgame, so it feels natural when it recurs with Kydrog.

## Proposed Changes

### Narrative: The Heroic River Zora

**Backstory (not all told in-game — this is the full context):**

A River Zora named **Lura** (name optional, may go unnamed) was a guardian of the freshwater tributaries feeding into the Zora Temple. Unlike the hostile River Zora common in Hyrule, Lura was one of the rare benevolent ones — a protector of Zora children who played in the shallow streams.

When the Zora Temple fell under dark influence, a Zora child was trapped inside. Lura entered the temple alone to rescue the child. She succeeded — the child escaped — but Lura was caught in the temple's collapsing seal and drowned in the flooding chambers.

Her spirit lingered in the temple, unable to pass on. The Song of Healing releases her grief and condenses it into the Zora Mask — a transformation that carries her swimming prowess and water affinity.

### Dialogue Rewrite Plan

The backstory is told through **existing dialogue slots**, rewritten to carry the narrative:

#### Sea Zora (Default, $1A4) — Before D4

```
The temple beneath the
falls has been sealed for
as long as I remember.

They say a River Zora
went inside long ago to
save a child who wandered
too deep. She never came
back out.
```

*Intent: Plants the seed of the River Zora story before the player enters D4. "She never came back out" creates a small mystery.*

#### Sea Zora (Alt, $1A5) — Before D4

```
River Zora and Sea Zora
do not often see eye to
eye. But that one...

She had more courage than
most. Even we remember
her.
```

*Intent: Establishes the River/Sea Zora divide and that Lura was exceptional. "Even we remember her" from a Sea Zora is high praise, implying cross-cultural respect.*

#### Sea Zora (Post-D4, $1A6) — After Zora Temple cleared

```
You cleared the temple?
Then you must have felt
it... a presence in the
deepest chamber.

A spirit that would not
rest. If you carry the
Song of Healing, perhaps
you could ease her grief.
```

*Intent: Directs the player to return to the temple's deepest room with the Song of Healing. This is the trigger for the mask creation sequence.*

### Mask Creation Sequence

**Location:** Zora Temple, deepest chamber (post-D4, on return visit)

**Trigger:** Player enters the room with the Song of Healing in inventory (or after learning it from a prior event).

**Sequence:**

```
1. Room is flooded (water level high, blue palette)
2. A ghostly Zora sprite appears at the room's center
   (reuse Zora NPC sprite with translucent palette)
3. Proximity trigger: ghost faces Link

4. Ghost dialogue:
   "The child... is the
    child safe?"

5. Link nods (auto-animation)

6. Ghost dialogue:
   "...Thank you.
    I can rest now."

7. Prompt: "Play the Song
   of Healing? ▶ Yes  No"

8. Song plays (same SFX as Kydrog sequence)
9. Ghost dissolves into light
10. Light condenses into mask
11. "You got the Zora Mask!"
    Item receipt fanfare
```

**If the player visits before having the Song of Healing:**
```
The spirit of a Zora
lingers here. She seems
trapped by grief.

Perhaps a healing melody
could set her free.
```
*This acts as a hint without blocking progress — the player can return later.*

### Dialogue Flow by Progression

| Stage | Sea Zora ($1A4/$1A5) | Post-D4 ($1A6) | Temple Ghost |
|---|---|---|---|
| Before D4 | Plants River Zora story | N/A | N/A |
| After D4, no Song | Same | "Felt a presence... Song of Healing" | "Perhaps a healing melody..." |
| After D4, with Song | Same | Same | Full mask creation sequence |
| After mask obtained | Same (or new "She is at peace" line) | "Her spirit is at peace now" | Ghost gone, room empty |

### Song of Healing Acquisition

**Open design question:** When does the player learn the Song of Healing?

**Option A — Before D4 (enables Zora Mask first):**
The Ocarina item or a specific NPC teaches the Song before D4. The Zora Mask is obtainable as soon as D4 is cleared. This establishes the Song → Mask pattern early, making the Kydrog sequence feel like a natural callback.

**Option B — After D4 but before endgame:**
A post-D4 event (Maku Tree? NPC quest?) teaches the Song. The Zora Mask is a reward for returning to the temple. This creates a "revisit old dungeon" moment.

**Option C — Contextual only:**
The Song isn't a learned item — it triggers automatically in specific scenes (Zora Temple ghost, Kydreeok post-fight). Simpler to implement but less player agency.

**Recommendation:** Option A or B, as the Song of Healing → Mask pattern is a core mechanic that benefits from being established before the endgame climax.

## Affected Files

| File | Change |
|---|---|
| Dialogue table | Rewrite messages $1A4, $1A5, $1A6 |
| Dialogue table | Add ghost dialogue (new message IDs for temple ghost lines) |
| Zora Temple room data | Add ghost sprite placement in deepest chamber (post-D4 flag) |
| `Sprites/NPCs/zora.asm` | Add post-mask-obtained dialogue branch (check Zora Mask item address) |
| `Core/sram.asm` | May need `!Story_ZoraMaskObtained` flag or check item address directly |
| Song of Healing implementation | Depends on acquisition design (Option A/B/C above) |

## Open Questions

1. **Song of Healing acquisition timing:** See Options A/B/C above. This affects the entire mask creation pipeline.
2. **Ghost sprite:** Reuse Zora NPC sprite with palette hack (translucent), or does this need a dedicated ghost sprite? Palette hack is simpler and thematic.
3. **Named or unnamed:** Should the River Zora be named "Lura" in dialogue, or remain unnamed ("a River Zora," "she")? Unnamed is simpler and more mythic; named adds emotional weight.
4. **Post-mask Sea Zora dialogue:** Should the Sea Zora have a new line acknowledging the ghost is at peace? This requires a 4th dialogue branch (check Zora Mask item flag).
5. **River/Sea Zora lore:** Is the River/Sea Zora divide established elsewhere in the game, or is this the only place it comes up? If it's new lore, it needs to feel natural, not expository.

## Dependencies

- `kydrog_mask_stalfos_form.md` — Song of Healing is shared between Zora Mask and Kydrog Mask sequences. The Zora Mask sequence should happen first chronologically to establish the pattern.
- `scholar_dialogue_rewrite.md` — If the Scholar mentions the Zora Temple or its history, ensure consistency with Lura's story.
- `progression_infrastructure.md` — Zora NPC dialogue branches can use the shared reaction framework once implemented.
