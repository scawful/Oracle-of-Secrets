# Scholar Dialogue Rewrite — Kalyxo Scholar (Message $7E)

## Summary

Rewrite the Kalyxo Scholar's dialogue (message $7E) to align with Story Bible v2.0. The Scholar is an NPC in Kalyxo Town who provides lore exposition about the Eon Abyss, the Shrines, and the ancient seal. The rewrite introduces the "spirits take physical form" property of the Abyss and references the historical priestess who sealed Kydrog.

## Current State

**Message ID:** `$7E`
**NPC:** Kalyxo Scholar — a bookish townsperson who has studied the island's history.

The current dialogue (if implemented) is either placeholder or reflects pre-v2.0 lore. Key lore points that need updating per Story Bible v2.0:

- The Eon Abyss is a parallel realm where spirits manifest physically
- The Shrines serve as dimensional anchors that reinforce the seal
- Something ancient is imprisoned — the Scholar suspects but doesn't name Kydrog directly
- Seal pressure has been building (dimensional thin spots appearing)
- A priestess from Kalyxo's past performed the original sealing

## Proposed Changes

### Lore Beats to Cover

1. **Seal pressure origin** — The barrier between realms is weakening
2. **Dimensional thin spots** — Visible phenomena the Scholar has observed
3. **Shrines as anchors** — Three Shrines reinforce the seal
4. **Something ancient imprisoned** — Vague reference to what's sealed away
5. **Spirits take physical form** — The Abyss's fundamental property
6. **Historical priestess** — A woman of great power sealed the entity long ago

### Dialogue Draft (32-char line width)

**First visit (Message $7E):**
```
Ah, a scholar recognizes
another seeker of truth.

The old texts speak of a
realm beyond our own...
the Eon Abyss, they call
it. A place where spirits
walk as flesh and bone.

Three Shrines on this isle
anchor a seal placed long
ago by a priestess of
extraordinary power.

She bound something ancient
within that realm. Something
that should not walk free.

But the seal weakens. I
have seen thin spots in
the air where the worlds
almost touch. Be wary.
```

**Character count verification:**
- Line 1: `Ah, a scholar recognizes` = 24 ✓
- Line 2: `another seeker of truth.` = 24 ✓
- Longest line: `it. A place where spirits` = 25 ✓
- All lines ≤ 32 characters ✓

**Post-Shrine visit (alternate, if progression-gated):**
```
You have visited a Shrine?
The seal responds to those
with courage in their heart.

The priestess who forged
the seal... the texts say
she carried a bloodline
blessed by the goddesses.

Perhaps that is why the
Shrines respond to you.
```

### Tone and Intent

The Scholar serves as the player's primary **lore exposition NPC** for the Abyss mechanics. Key narrative goals:

- **Establish the Abyss rules early** — "spirits walk as flesh and bone" explains why Ganondorf, Kydrog, Dark Link, and the Stalfos Form all function physically in the Abyss
- **Foreshadow the priestess/Farore connection** — The "bloodline blessed by the goddesses" hints at why Kydrog needs Farore specifically (she's the priestess's descendant)
- **Create unease** — The seal weakening is the inciting incident; the Scholar confirms it's observable
- **Never name Kydrog** — The Scholar calls it "something ancient," preserving the mystery

## Affected Files

| File | Change |
|---|---|
| Dialogue table (external tool) | Rewrite message $7E content |
| Dialogue table (external tool) | Possibly add post-Shrine variant (new message ID) |
| NPC sprite placement | Verify Scholar NPC is placed in Kalyxo Town (may already exist) |

## Open Questions

1. **Is message $7E already authored?** — The codebase search found no reference to message $7E in ASM files. It may exist only in the dialogue data table or may be unimplemented. Verify in the dialogue editor.
2. **Progression gating:** Should the Scholar have a post-Shrine alternate? If so, a new message ID is needed (and the NPC ASM needs a flag check to switch).
3. **Scholar sprite:** Is this a unique sprite or a reskinned vanilla NPC? If new, check `Sprites/registry.csv` for slot availability.
4. **Multiple visits:** Should repeated visits cycle through different lore topics, or always show the same text?

## Dependencies

- `gossip_stone_additions.md` — The priestess/Farore bloodline hint appears in both the Scholar dialogue and a Gossip Stone. Ensure consistency.
- `endgame_narrative_arc.md` — The "spirits take physical form" rule established here pays off in the endgame.
- Story Bible v2.0 (`Docs/Lore/story_bible.md`) — Primary lore source.
