# Maku Tree Progressive Dialogue — Threshold Approach

**Status:** IMPLEMENTED, UNTESTED (2026-02-07)

## Summary

The Maku Tree's `MakuTree_HasMetLink` routine uses a crystal-count threshold table via `SelectReactionMessage` (from `Core/progression.asm`). This replaced the original per-dungeon waterfall cascade, enabling non-linear dungeon order.

## Architecture

```
MakuTree_HasMetLink
  → Sets $00-$02 = pointer to MakuTreeReactionTable
  → JSL SelectReactionMessage (walks table, returns A/Y)
  → JSL Sprite_ShowSolicitedMessageIfPlayerFacing
  → JSL UpdateMapIcon (MapIcon = crystal_count + 1)
  → Sets OOSPROG bit 1
```

## Threshold Table

| Crystals | Message | Tone |
|----------|---------|------|
| 7 | $01CA | Endgame — seek Shrines |
| 5+ | $01C7 | Urgency — earth trembles |
| 3+ | $01C6 | Mid-game — deeper threat |
| 1+ | $01C5 | Early — calm encouragement |
| 0 | $0022 | Vanilla revisit |

## Files Changed

| File | Change |
|------|--------|
| `Sprites/NPCs/maku_tree.asm` | Replaced waterfall with threshold table |
| `Core/message.asm` | Encoded 4 new messages ($1C5, $1C6, $1C7, $1CA) |
| `Core/progression.asm` | Status comment updated (first consumer) |

## Testing Required

Set `$7EF37A` via Mesen2, talk to Maku Tree, verify correct message and MapIcon:

| $7EF37A | Count | Expected Msg | Expected MapIcon |
|---------|-------|--------------|------------------|
| $00 | 0 | $0022 | $01 |
| $01 | 1 | $01C5 | $02 |
| $15 | 3 | $01C6 | $04 |
| $1F | 5 | $01C7 | $06 |
| $7F | 7 | $01CA | $08 |

Also verify: OOSPROG bit 1 ($7EF3D6 & $02) set after talking.

## Supersedes

This plan replaces the original per-dungeon waterfall design. The old approach checked specific crystal bits (D7→D1) and gave "go here next" hints tied to dungeon names. The threshold approach is order-agnostic and gives the Maku Tree character-driven dialogue instead of GPS directions.
