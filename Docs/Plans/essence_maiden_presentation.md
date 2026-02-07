# Essence & Maiden Presentation Improvements

## Summary

Refine the crystal maiden dialogue and essence collection text to strengthen the game's Oracle identity while working within existing mechanical and graphical constraints.\n+\n+Dialogue authoring is **not blocked**: edit `Core/messages.org` (and any associated message tables) and rebuild the ROM. yaze GUI support is a convenience item, not a dependency.

## Current State

### What Works

- **Crystal maidens deliver plot-critical lore** after each dungeon boss (D1-D7)
- **Three-layer lore system** is well-designed: maidens (long-form) + Maku Tree (guidance) + Gossip Stones (deep lore)
- **Maiden dialogue is already Oracle-specific** — covers Kalyxo history, Zora technology, Twinrova conspiracy, Goron alliance, endgame setup
- **Triforce icons in quest menu** are functional and compact given the full GFX tile sheet

### What Needs Work

- D1, D2, D6 maidens open with generic ALTTP-style "freed from Kydrog" language
- Essences are not named at collection time (no "You got the Whispering Vines!")
- Maiden dialogue predates Story Bible v2.0 — some details may be inconsistent (e.g., Ganondorf's origin, two-villain-track structure)
- Maku Tree cascade missing D2, D4, D6 entries (see `maku_tree_hint_cascade.md`)

## Planned Changes

### 1. Essence Collection Text (Priority: High)

Add named essence receipt text per dungeon. This is a text-only change — no graphics.

| Dungeon | Current Text | Proposed Text |
|---|---|---|
| D1 | (generic crystal receipt) | "You got the Whispering Vines! The essence of growth echoes through Mushroom Grotto." |
| D2 | (generic crystal receipt) | "You got the Celestial Veil! The essence of aspiration soars from Tail Palace." |
| D3 | (generic crystal receipt) | "You got the Crown of Shadows! The essence of authority stirs in Kalyxo Castle." |
| D4 | (generic crystal receipt) | "You got the Luminous Mirage! The essence of truth ripples from the Zora Temple." |
| D5 | (generic crystal receipt) | "You got the Ebon Ember! The essence of duality burns through Glacia Estate." |
| D6 | (generic crystal receipt) | "You got the Seismic Whisper! The essence of foundation trembles in the Goron Mines." |
| D7 | (generic crystal receipt) | "You got Demise's Thorn! The essence of endings pierces the Dragon Ship." |

**Constraint:** 32-character line width. The above may need trimming.

### 2. Maiden Identity Refinement (Priority: Medium)

Give D1, D2, and D6 maidens distinct identities instead of generic "freed" language.

| Dungeon | Current Opening | Proposed Identity |
|---|---|---|
| D1 | "I am finally freed from Kydrog's evil forces" | Forest keeper / grove guardian — "I tended these groves before the shadow came" |
| D2 | "I am finally freed from Kydrog's evil forces" | Tail Palace astronomer / priestess — "I once watched the stars from this observatory" |
| D6 | "I am finally freed from Kydrog's evil forces" | Goron trade liaison / mine keeper — "The Gorons trusted me to guard these depths" |

D3, D5 maidens already have strong identities (historian, Twinrova captive). D4 maiden identity is TBD — **important:** the Zora Princess is a mid-dungeon NPC who gives the Zora Mask, NOT the D4 maiden. The maiden appears post-boss and is a separate character (possibly another Zora, constrained by VRAM/sprite draw code).

### 3. Story Bible v2.0 Consistency Pass (Priority: Medium)

Review all 7 maiden dialogues against Story Bible v2.0 for:
- **Ganondorf origin:** Maiden dialogue should not commit to a specific timeline origin. Keep references vague ("an ancient evil," "a power older than Kydrog"). The in-game text is intentionally ambiguous.
- **Two-villain-track:** D5 maiden already hints at Twinrova's independence. Verify D1/D3 maidens don't contradict this structure.
- **Eon Abyss cosmology:** The Abyss is a pocket dimension formed by seal pressure. Maiden dialogue should not describe it as "an older world" or "first creation" (these conflict with established lore).

### 4. Maku Tree Cascade Completion (Priority: High)

Complete the Maku Tree hint dispatch for all 7 dungeons. Currently D1, D3, D5 are implemented; D2, D4, D6 are missing. This is an ASM change that does not require the message editor — see `maku_tree_hint_cascade.md` for the full waterfall pattern.

## Constraints & Blockers

### GFX Tile Sheet (Not Changing)

The menu GFX sheet is fully allocated with custom item icons, masks, fonts, and UI elements. Unique per-essence icons would require sacrificing existing graphics. The triforce triangle icons are compact and functional. **Decision: Keep triforce icons.**

### Yaze Message Editor (Blocking Dialogue Changes)

All maiden dialogue and essence collection text changes require editing the expanded message bin file. The yaze message editor needs infrastructure work to support saving the expanded bin alongside the ROM message table.

**Blocked items:**
- Essence collection text (items 1 above)
- Maiden identity rewrites (item 2 above)
- Story Bible consistency pass (item 3 above)

**Not blocked:**
- Maku Tree cascade (item 4 — pure ASM, uses existing message IDs)

### Ridoyie's Contributions

Ridoyie has offered to contribute maiden dialogue and world lore text. His contributions are blocked on the same message editor tooling. Once the editor supports expanded bin editing:
- Share current maiden dialogue (0x132-0x138) for his review
- His proposed lore beats (Kalyxo's cosmic importance, Eon Abyss nature) can be evaluated against Story Bible v2.0 cosmology
- Gossip Stones are the best vehicle for "optional deep lore" — direct him toward the 32-char line format

## Design Decisions (Settled)

| Question | Decision | Rationale |
|---|---|---|
| Unique essence menu icons? | No | GFX sheet full; triforce icons functional |
| Remove crystal maidens? | No | They deliver essential plot exposition |
| Add 8th essence to D8? | No | Fortress of Secrets is a pursuit dungeon, not a collection dungeon |
| Ganondorf's specific origin? | Keep ambiguous in-game | Endgame dialogue supports both ALTTP and OoT interpretations |
| Three-wish Triforce system? | Don't adopt | Creates more questions than answers; Twinrova seal fracture is cleaner |

## Affected Files

| File | Change | Blocked? |
|---|---|---|
| `Core/messages.org` | Essence receipt text, maiden dialogue rewrites | Yes (message editor) |
| `Core/message.asm` | Compiled from messages.org | Yes (message editor) |
| `Sprites/NPCs/maku_tree.asm` | Complete D2/D4/D6 hint cascade | No |
| `Core/symbols.asm` | New message IDs for D2/D4/D6 Maku hints | No |

## Dependencies

- `maku_tree_hint_cascade.md` — Maku Tree completion is independent and can proceed now
- `gossip_stone_additions.md` — Gossip Stones are a separate lore layer; no conflict
- `endgame_narrative_arc.md` — Ganondorf dialogue is already written and ambiguous
- `scholar_dialogue_rewrite.md` — Maiden lore must stay consistent with Scholar's exposition
- Yaze message editor (~/src/hobby/yaze/) — Expanded bin save support needed before dialogue edits
