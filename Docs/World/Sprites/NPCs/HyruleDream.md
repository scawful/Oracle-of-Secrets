# Hyrule Dream

## Overview
`Sprites/NPCs/hyrule_dream.asm` defines a static indoor pose sprite. Prep picks a pose from the current room, and Main only sets the animation frame. The file has no dialogue, no item grant, and no write to `$7EF410`.

`$7EF410` is the `Dreams` bitfield (`Core/sram.asm:387`), which Maple (`Sprites/NPCs/maple.asm`) owns. Farore's INDOORS path calls this sprite (`farore.asm:87-91`, `:105-107`).

## Sprite Properties
No `!SPRID`, `!NbrTiles`, or other property values are defined in this file.

## Prep (`Sprite_HyruleDream_Prep`)
Source: `hyrule_dream.asm:1-13`. Prep only sets `SprAction`, from the current room (`ROOM`):

*   `$51` (King): `SprAction` = 1.
*   `$60` (Soldier): `SprAction` = 2.
*   Any other room: `SprAction` = 0 (Zelda).

## Main (`Sprite_HyruleDream_Main`)
Source: `hyrule_dream.asm:15-38`. The jump table has three states. Each state only writes `SprFrame`:

| SprAction | State | SprFrame |
| --- | --- | --- |
| 0 | `Zelda_Idle` | 0 |
| 1 | `King_Idle` | 1 |
| 2 | `Soldier_Idle` | 2 |

There are no timers, messages, or other state changes.

## Drawing (`Sprite_HyruleDream_Draw`)
Source: `hyrule_dream.asm:40-119`. Three frames are drawn:

*   `.start_index` `$00`, `$03`, `$07`, with `.nbr_of_tiles` 2, 3, 2 (`:96-99`).
*   Tile graphics come from `.chr` (`:108-111`) and `.properties` `$39` / `$79` (`:112-115`). All tile sizes are `$02` (`:116-119`).
*   Tiles that would fall off-screen are moved out of view to `$F0` (`:62-74`).

## Design Notes
*   The pose is set once in Prep, by room, and is not changed later.
*   Farore's indoor path uses this sprite (see Overview).
*   Per code, runtime unverified.
