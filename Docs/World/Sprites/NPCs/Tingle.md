# Tingle

## Overview
Tingle (`Sprites/NPCs/tingle.asm`) is the map salesman. He sells the seven dungeon maps in sequence. `TingleId` (`$7EF397`) is the next map index (0-7). `TingleMaps` (`$7EF396`) is the purchased-maps bitfield (`Core/sram.asm:446-447`). Rupees are at `$7EF360`. The player response byte is `$1CE8` (0 = yes, nonzero = no).

## Sprite Properties
Values from the header (`tingle.asm:51-77`). Every property not listed is `00`.

*   **`!SPRID`**: `$22`
*   **`!NbrTiles`**: `03`
*   **`!Harmless`**: `01`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!Hitbox`**: `02`
*   **`!Prize`**: `00`
*   **`!Boss`**: `00`

## Main Structure (`Sprite_Tingle_Long`)
Source: `tingle.asm:81-91`. It draws Tingle (`Sprite_Tingle_Draw`) and the shadow (`Sprite_DrawShadow`). It runs `Sprite_Tingle_Main` only when `Sprite_CheckActive` returns carry set.

## Initialization (`Sprite_Tingle_Prep`)
Source: `tingle.asm:93-99`. Prep is empty apart from the `PHB`/`PLB` wrapper.

## State Machine (`Sprite_Tingle_Main`)
Source: `tingle.asm:101-217`. `Sprite_Tingle_Main` runs `Sprite_PlayerCantPassThrough`, then dispatches on `SprAction`. Per code, runtime unverified.

| SprAction | Routine | Behaviour |
| --- | --- | --- |
| 0 | `Tingle_Forward` (`:114-119`) | Plays animation `(0,0,10)`, then `Sprite_Tingle_TrackPlayer`. |
| 1 | `Tingle_Right` (`:121-126`) | Plays animation `(1,1,10)`, then `Sprite_Tingle_TrackPlayer`. |
| 2 | `Tingle_Left` (`:128-133`) | Plays animation `(2,2,10)`, then `Sprite_Tingle_TrackPlayer`. |
| 3 | `Tingle_MapPrompt` (`:135-163`) | If `$1CE8` is nonzero, goes to 5. Otherwise shows the offer message for `TingleId` (see Messages), then goes to 4 when `TingleId` is not 7, or to 0 when it is 7. |
| 4 | `Tingle_MapSales` (`:165-191`) | If `$1CE8` is nonzero, goes to 5. Otherwise, if rupees are at least the cost for `TingleId`, subtracts the cost, ORs the map bit into `TingleMaps` (see the Bitfield note), increments `TingleId`, shows `$018E`, and sets SprAction to 0. If rupees are short, shows `$018F` and sets SprAction to 0. |
| 5 | `Tingle_PlayerSaidNo` (`:211-216`) | Shows `$0198`; sets SprAction to 0. |

## Tracking (`Sprite_Tingle_TrackPlayer`)
Source: `tingle.asm:219-236`.

*   Shows solicited greeting `$018D`. If Link talks, sets SprAction to 3 (`Tingle_MapPrompt`).
*   Otherwise it turns Tingle: `Sprite_IsBelowPlayer` returning 0 sets SprAction to 0. Otherwise `Sprite_IsToRightOfPlayer` nonzero sets SprAction to 1, and zero sets it to 2.

## Map Table
Costs are in `.cost` (`tingle.asm:193-200`). Offer messages are in `.message_ids` (`:154-162`).

| TingleId | Map | Cost (rupees) | Offer message |
| --- | --- | --- | --- |
| 0 | Map 0 | 50 | `$0191` |
| 1 | Map 1 | 75 | `$0192` |
| 2 | Map 2 | 100 | `$0193` |
| 3 | Map 3 | 80 | `$0194` |
| 4 | Map 4 | 90 | `$0195` |
| 5 | Map 5 | 60 | `$0196` |
| 6 | Map 6 | 120 | `$0197` |

When `TingleId` is 7 (all maps sold), the offer message is `$0190`.

## Messages

| ID | Use |
| --- | --- |
| `$018D` | Greeting (solicited, from `Sprite_Tingle_TrackPlayer`) |
| `$018E` | Map purchased |
| `$018F` | Not enough rupees |
| `$0190` | All maps sold (offer slot when `TingleId` is 7) |
| `$0191`-`$0197` | Offers for `TingleId` 0-6 |
| `$0198` | Player declined |

## Bitfield (per code, runtime unverified)
`Tingle_MapSales` sets `Y` = `2 * TingleId` (`ASL`). That index reads the word `.cost` correctly. It also reads the byte table `.dungeon` (`tingle.asm:201-208`) at the same offset, so the bit ORed into `TingleMaps` is `.dungeon[2 * TingleId]`:

*   TingleId 0: `$01`.
*   TingleId 1: `$04`. TingleId 2: `$10`. TingleId 3: `$40`.
*   TingleId 4-6: bytes past the end of the table.

The header comments expect `$01`, `$02`, `$04`, `$08`, `$10`, `$20`, `$40`. This mismatch is not fixed here; it is a code change for a separate item.

## Flags

| Address | Use |
| --- | --- |
| `$7EF360` | Rupees (read and decremented) |
| `$7EF396` | `TingleMaps` (purchased-maps bitfield) |
| `$7EF397` | `TingleId` (next map index) |
| `$1CE8` | Player response (0 = yes) |

## Draw
Source: `tingle.asm:238-312`. There are three animation frames (`.start_index` `$00`, `$02`, `$04`), each drawn as two tiles.
