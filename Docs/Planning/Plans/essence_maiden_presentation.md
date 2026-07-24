# Essence & Maiden Presentation Improvements

## Summary

Refine the crystal maiden dialogue and essence collection text to strengthen
the game's Oracle identity while working within existing mechanical and
graphical constraints.

Dialogue authoring is **not blocked**. For vanilla IDs `$000-$18C`, preserve
the change in a committed `Data/dialogue/*.json` bundle, import it into the
editable base ROM (`Roms/oos168.sfc`) with yaze or z3ed, then close/reopen and
read it back before rebuilding. The gitignored ROM edit alone is not durable.
`Core/messages.org` is documentation only, not a build input. Expanded IDs
`$18D+` remain ASM-owned in `Core/message.asm`.

## Current State

### What Works

- **Crystal maiden text exists for D1-D7**, but delivery is runtime-unverified
  and the OFF-by-default D7 rescue scaffold does not complete the maiden flow
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

### Expanded Message Workflow (AVAILABLE)

Expanded message IDs `$18D+` live in ASM-owned bank `$2F`. Direct editor or
CLI writes to those IDs are not durable because the next ASM build replaces
the bank. Dialogue authoring remains **unblocked** through the ASM source.

**Expanded-message workflow:**
1. Edit the matching entry in `Core/message.asm`.
2. Rebuild with `Scripts/Build/build_rom.sh 168`.
3. Reopen or reload `Roms/oos168x.sfc` for inspection and testing; do not edit
   the patched ROM directly.

**Ready to author:**
- Essence collection text (items 1 above)
- Maiden identity rewrites (item 2 above)
- Story Bible consistency pass (item 3 above)

### Ridoyie's Contributions

Ridoyie has offered to contribute maiden dialogue and world lore text. Tooling is now available:
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

| File | Change | Status |
|---|---|---|
| `Data/dialogue/*.json` | Committed source artifact for vanilla-message changes | Ready to author |
| `Roms/oos168.sfc` | Import target for vanilla-message bundles; close/reopen/read back before rebuilding | Ready to author |
| `Core/messages.org` | Documentation/reference only; keep annotations synchronized with verified ROM text | Not a build input |
| `Core/message.asm` | ASM source for expanded message IDs `$18D+` | Ready to author |
| `Sprites/NPCs/maku_tree.asm` | Threshold-based dialogue | Done (UNTESTED) |
| `Core/symbols.asm` | Message IDs | Done |

## Dependencies

- `maku_tree_hint_cascade.md` — Maku Tree threshold dialogue done, needs runtime testing
- `gossip_stone_additions.md` — Gossip Stones are a separate lore layer; no conflict
- `endgame_narrative_arc.md` — Ganondorf dialogue is already written and ambiguous
- `scholar_dialogue_rewrite.md` — Maiden lore must stay consistent with Scholar's exposition
