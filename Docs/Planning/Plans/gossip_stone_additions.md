# Gossip Stone Additions — New Lore Messages

## Summary

Add new Gossip Stone messages that foreshadow key narrative elements: Kydrog as a failed Link, Twinrova's independent agenda, the Abyss's spirit-body property, and the priestess/Farore bloodline connection. Each message is mapped to a specific stone ID (GS01–GS12) with progression gating.

## Current State

### Gossip Stone Registry

Per Story Bible v2.0, there are 12 Gossip Stones (GS01–GS12) across the game world. They are categorized as Lore, Hints, or Warnings, and some are progression-gated (only reveal text after certain dungeons are completed).

**Known stone locations (from story_bible.md):**
- GS03: Zora Sanctuary (Lore, triggers after D4)
- GS06: Outside Kalyxo Castle (Lore, triggers after D3)
- GS12: Hall of Secrets (Lore, triggers after D7)

**Remaining stones (GS01, GS02, GS04, GS05, GS07–GS11):** Locations and messages TBD or partially assigned.

### Message System

Gossip Stones use the standard message display system. Each stone has a message ID tied to its sprite or tile interaction. Progression gating checks SRAM flags before displaying the message (shows a default "..." or generic text if the gate isn't met).

## Proposed Changes

### New Messages

#### 1. Kydrog-as-Failed-Link Hint
**Stone:** GS07 (proposed location: Forest area / near D1)
**Trigger:** After D3 (Kalyxo Castle)
**Gate:** `!Crystal_D3_KalyxoCastle`

```
They say a hero once came
to this island wearing
the garb of the forest
and bearing the mark of
courage.

He never left.
```

*Intent: "Garb of the forest, mark of courage" directly mirrors Link without naming him. The ominous "He never left" foreshadows Kydrog's fate. Placed near D1 so the player may revisit after D3 and discover it.*

#### 2. Twinrova Foreshadowing
**Stone:** GS05 (proposed location: Near Ranch / rural area)
**Trigger:** After D4 (Zora Temple)
**Gate:** `!Crystal_D4_ZoraTemple`

```
Beware twin flames that
do not serve the pirate
king. Their loyalty is
to a power older and
more patient than his.
```

*Intent: Establishes that Twinrova operates independently from Kydrog. "Older and more patient" = Ganondorf. Placed near the Ranch to connect with Ranch Girl's cursed silence (Twinrova's handiwork). Pre-D5 timing lets the player piece together the Glacia Estate connection.*

#### 3. Abyss Spirit-Body Property
**Stone:** GS08 (proposed location: Eon Abyss entrance / Shrine area)
**Trigger:** After first Shrine visit
**Gate:** `!Story_ShrineVisited` (or equivalent story flag)

```
In the realm beyond the
seal, the dead walk as
the living. Spirits take
form and flesh. What was
lost can be found... or
made anew.
```

*Intent: Explains the fundamental physics of the Eon Abyss — why ghosts have bodies there. "What was lost can be found" foreshadows Kydrog's physical dragon form and the Stalfos Form. "Made anew" hints at the mask transformations. Located at the Abyss entrance so the player reads it when first entering.*

#### 4. Priestess/Farore Bloodline Hint
**Stone:** GS09 (proposed location: Near a Shrine or sacred site)
**Trigger:** After D6 (Goron Mines)
**Gate:** `!Crystal_D6_GoronMines`

```
The woman who forged the
seal bore the blessing of
the golden goddesses in
her blood.

Her line endures.
```

*Intent: Connects the historical priestess to a living descendant. "Her line endures" = Farore is the priestess's descendant, which explains why Kydrog needs Farore specifically (to break the seal via bloodline resonance). Late-game gating ensures this feels like a revelation rather than early exposition.*

### Stone Assignment Summary

| Stone ID | Location | New Message? | Trigger Gate | Category |
|---|---|---|---|---|
| GS01 | TBD | — | — | — |
| GS02 | TBD | — | — | — |
| GS03 | Zora Sanctuary | Existing | After D4 | Lore |
| GS04 | TBD | — | — | — |
| GS05 | Near Ranch | **Twinrova foreshadowing** | After D4 | Warning |
| GS06 | Outside Kalyxo Castle | Existing | After D3 | Lore |
| GS07 | Forest / near D1 | **Kydrog-as-failed-Link** | After D3 | Lore |
| GS08 | Abyss entrance | **Spirit-body property** | After Shrine | Lore |
| GS09 | Near Shrine / sacred site | **Priestess bloodline** | After D6 | Lore |
| GS10 | TBD | — | — | — |
| GS11 | TBD | — | — | — |
| GS12 | Hall of Secrets | Existing | After D7 | Lore |

### Progression Gating Implementation

Each Gossip Stone's interaction routine should check the relevant SRAM flag:

```asm
; Example: GS07 (Kydrog hint, gated by D3 crystal)
GossipStone_07:
  LDA.l Crystals
  AND.b #!Crystal_D3_KalyxoCastle : BEQ .default
    %ShowSolicitedMessage($xxx)  ; Kydrog hint message
    RTS
  .default
    %ShowSolicitedMessage($yyy)  ; Generic "..." message
    RTS
```

If the NPC reaction framework from `progression_infrastructure.md` is implemented, Gossip Stones could use it instead of manual flag checks.

### Message ID Allocation

The 4 new messages need IDs. Proposed range: `$1D0`–`$1D3` (or wherever the next free block is in the dialogue table).

| Message ID | Content |
|---|---|
| `$1D0` | GS07 — Kydrog-as-failed-Link |
| `$1D1` | GS05 — Twinrova foreshadowing |
| `$1D2` | GS08 — Abyss spirit-body |
| `$1D3` | GS09 — Priestess bloodline |

## Affected Files

| File | Change |
|---|---|
| Dialogue table | Add 4 new messages ($1D0–$1D3) |
| Gossip Stone sprite/interaction code | Add progression gate checks per stone |
| `Core/sram.asm` | May need `!Story_ShrineVisited` flag if not existing |
| Overworld room data | Place GS07, GS08, GS09 if not already placed |
| `Core/symbols.asm` | Register new message IDs |

## Open Questions

1. **Exact stone locations:** GS07, GS08, GS09 locations are proposed but not finalized. Need to verify overworld map tile availability.
2. **GS05 location:** "Near Ranch" is vague. Should it be on the Ranch property, or on the path between Ranch and Glacia Estate (D5)?
3. **Default message:** Should un-triggered stones show "..." (silent), a generic "The stone hums softly," or nothing at all? Current convention TBD.
4. **Stone discovery:** Should Gossip Stones be always visible, or appear only after the player obtains a specific item (e.g., Mask of Truth equivalent)?
5. **Remaining stones:** GS01, GS02, GS04, GS10, GS11 are unassigned. Should they be reserved for future use or given generic lore messages now?

## Relationship to Crystal Maidens

Gossip Stones and crystal maidens serve **different lore layers** and should not duplicate content:

- **Crystal Maidens** (messages 0x132-0x138): Long-form plot exposition after each boss. Covers political history, technology, conspiracies. The player sees these once, in sequence.
- **Gossip Stones** (GS01-GS21): Short, cryptic, optional fragments. The player discovers these out of order through exploration. Best used for foreshadowing, atmosphere, and "maybe-true" deep lore.

**Rule:** If a maiden already covers a topic (e.g., D3 maiden explains Hyrule's occupation), the corresponding Gossip Stone should add texture or mystery, not repeat the same information.

## Cosmology Consistency

All Gossip Stone messages must align with Story Bible v2.0 cosmology:
- Kalyxo is a "remote island at a convergence point" — NOT the first creation of the Goddesses
- The Eon Abyss is a pocket dimension formed by Sacred Realm seal pressure — NOT a remnant of an older world
- Ganondorf's origin is intentionally ambiguous — stones may hint but should not commit to a specific timeline

## External Contributions

Ridoyie has offered to contribute world lore text for Gossip Stones. His contributions are:
- **UNBLOCKED** — yaze message editor + z3ed CLI both support expanded write path (commit `4b6a78ed`)
- **Format:** Must follow 32-char line width, 2-3 lines max, cryptic/poetic tone, first-person plural ("We") voice
- **Review needed:** His proposed cosmology lines conflict with established lore (see above). Direct him to the existing gossip_stones.md registry for tone/format reference.

## Dependencies

- `scholar_dialogue_rewrite.md` — The priestess lore in GS09 must be consistent with the Scholar's dialogue.
- `kydrog_mask_stalfos_form.md` — GS08's spirit-body message foreshadows the Stalfos Form.
- `endgame_narrative_arc.md` — GS05's Twinrova hint and GS07's Kydrog hint set up endgame revelations.
- `progression_infrastructure.md` — Gossip Stones can use the shared NPC reaction framework for gating.
- `essence_maiden_presentation.md` — Coordinates with maiden dialogue improvements.
