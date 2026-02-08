# Maku Tree Hint Cascade — Full D1–D6 Dispatch

## Summary

Wire the complete Maku Tree progressive hint system so that after each dungeon crystal is collected, the Maku Tree delivers the correct next-destination hint and advances the MapIcon. Currently only D1, D3, and D5 are checked — D2, D4, and D6 are missing from the waterfall.

## Current State

**File:** `Sprites/NPCs/maku_tree.asm` (lines 147–176)

The hint dispatch uses a top-down waterfall: check the highest crystal first, fall through to lower ones. Current checks:

```
D5 (Glacia Estate, $04)  → Message $1C7 → hints Shrine/Goron Mines
D3 (Kalyxo Castle, $40)  → Message $1C6 → hints Zora Temple
D1 (Mushroom Grotto, $01) → Message $1C5 → hints Mask Salesman
(default)                  → Message $22  → generic guidance
```

**Missing:** D2, D4, D6 have no hint entries. After completing D2, for example, the player gets the D1 hint again because the cascade falls through to the first matching check.

**MapIcon advancement:** Currently set to `$01` (Mushroom Grotto) on first meeting (line 125). No subsequent MapIcon updates after crystal collection.

## Proposed Changes

### Flag-to-Message Mapping Table

| Check Order | Dungeon | Crystal Flag | Crystal Bit | Message ID | MapIcon After | Hint Content |
|---|---|---|---|---|---|---|
| 1 | D6 Goron Mines | `!Crystal_D6_GoronMines` | `$02` | `$1CB` | `$07` (Dragon Ship) | Hints toward D7 / Pirate King |
| 2 | D5 Glacia Estate | `!Crystal_D5_GlaciaEstate` | `$04` | `$1C7` | `$06` (Goron Mines) | Hints toward Goron Mines |
| 3 | D4 Zora Temple | `!Crystal_D4_ZoraTemple` | `$20` | `$1C9` | `$05` (Glacia Estate) | Hints toward Glacia Estate / Twinrova |
| 4 | D3 Kalyxo Castle | `!Crystal_D3_KalyxoCastle` | `$40` | `$1C6` | `$04` (Zora Temple) | Hints toward Zora Temple |
| 5 | D2 Tail Palace | `!Crystal_D2_TailPalace` | `$10` | `$1C8` | `$03` (Kalyxo Castle) | Hints toward Kalyxo Castle |
| 6 | D1 Mushroom Grotto | `!Crystal_D1_MushroomGrotto` | `$01` | `$1C5` | `$02` (Tail Palace) | Hints toward Mask Salesman / Tail Palace |
| 7 | (none) | — | — | `$22` | `$01` (Mushroom Grotto) | Generic guidance |

**Note:** Message IDs `$1C8`, `$1C9`, `$1CB` need to be added to the dialogue table. `$1CA` is reserved in case D7 needs a post-clear Maku message (Shrine guidance).

### Waterfall Check Pattern

The dispatch checks crystals from highest (D6) to lowest (D1), branching to the appropriate message on the first match. This means the player always hears the hint for the *most recent* dungeon cleared:

```asm
.check_crystals
  LDA.l Crystals

  ; --- D6 check (highest priority) ---
  AND.b #!Crystal_D6_GoronMines : BEQ .check_d5
    %ShowSolicitedMessage($1CB)
    LDA.b #!MapIcon_D7_DragonShip
    STA.l MapIcon
    RTS

.check_d5
  LDA.l Crystals
  AND.b #!Crystal_D5_GlaciaEstate : BEQ .check_d4
    %ShowSolicitedMessage($1C7)
    LDA.b #!MapIcon_D6_GoronMines
    STA.l MapIcon
    RTS

.check_d4
  LDA.l Crystals
  AND.b #!Crystal_D4_ZoraTemple : BEQ .check_d3
    %ShowSolicitedMessage($1C9)
    LDA.b #!MapIcon_D5_GlaciaEstate
    STA.l MapIcon
    RTS

.check_d3
  LDA.l Crystals
  AND.b #!Crystal_D3_KalyxoCastle : BEQ .check_d2
    %ShowSolicitedMessage($1C6)
    LDA.b #!MapIcon_D4_ZoraTemple
    STA.l MapIcon
    RTS

.check_d2
  LDA.l Crystals
  AND.b #!Crystal_D2_TailPalace : BEQ .check_d1
    %ShowSolicitedMessage($1C8)
    LDA.b #!MapIcon_D3_KalyxoCastle
    STA.l MapIcon
    RTS

.check_d1
  LDA.l Crystals
  AND.b #!Crystal_D1_MushroomGrotto : BEQ .no_crystals
    %ShowSolicitedMessage($1C5)
    LDA.b #!MapIcon_D2_TailPalace
    STA.l MapIcon
    RTS

.no_crystals
  %ShowSolicitedMessage($22)
  RTS
```

### MapIcon Advancement

MapIcon is currently only set once (first meeting). The new system sets it on every Maku Tree visit, ensuring the world map always points to the next dungeon. This is idempotent — visiting the Maku Tree multiple times after the same dungeon just re-sets the same icon.

### Message Content Guidelines

Each hint should:
1. Acknowledge the dungeon just cleared (1 line)
2. Name or describe the next destination (1–2 lines)
3. Optionally hint at what's needed to access it (1 line)

Example for post-D2 ($1C8):
```
The second essence is safe
with me now. I sense a dark
presence in Kalyxo Castle
to the north.
```

## Affected Files

| File | Change |
|---|---|
| `Sprites/NPCs/maku_tree.asm` | Rewrite hint dispatch (lines 147–176) |
| `Core/symbols.asm` | Add message IDs $1C8, $1C9, $1CA, $1CB if not present |
| Dialogue table (external tool) | Write new messages for D2, D4, D6 hints |

## Open Questions

1. **D7 post-clear hint:** After D7 (Dragon Ship), should the Maku Tree hint toward Shrines, or does a cutscene handle the transition to the endgame? If a hint is needed, reserve `$1CA`.
2. **Crystal count helper:** Should the waterfall be replaced with a crystal-count routine that indexes into a table? See `progression_infrastructure.md` for the centralized approach.
3. **Repeat visit flavor:** Should the Maku Tree say something different on repeat visits vs. first visit after a new crystal? Current system is stateless (no "already told you" tracking).

## Dependencies

- `progression_infrastructure.md` — May replace the waterfall with a shared crystal-count indexing routine.
- Dialogue table tool — New message IDs must be authored and inserted.
