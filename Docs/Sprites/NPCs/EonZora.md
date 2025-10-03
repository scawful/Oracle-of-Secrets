# Eon Zora

## Overview
The Eon Zora is an NPC (Non-Player Character) sprite found in the Eon Abyss. Its behavior is characterized by random movement and context-sensitive dialogue that changes based on Link's current location within the game world.

## Sprite Properties
Explicit sprite properties (`!SPRID`, `!NbrTiles`, etc.) are not defined within this file. It is assumed that these properties are either inherited from a vanilla sprite ID or defined in a separate configuration file, as this file focuses on the sprite's behavior and drawing.

## Main Logic (`Sprite_EonZora_Main`)
This routine is the main entry point for the Eon Zora, executed every frame. It orchestrates the Zora's dialogue, movement, and animation.

*   **Dialogue**: Calls `EonZora_HandleDialogue` to manage interactions with the player.
*   **Movement**: Calls `EonZora_Walk` for random movement, followed by `JSL Sprite_Move` and `JSL Sprite_BounceFromTileCollision` for physical movement and collision handling.
*   **Directional Animations**: Uses a jump table to play specific animations based on the Zora's current direction (Forward, Left, Right, Back).

```asm
Sprite_EonZora_Main:
{
  JSR EonZora_HandleDialogue
  JSR EonZora_Walk

  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw EonZora_Forward
  dw EonZora_Left
  dw EonZora_Right
  dw EonZora_Back

  EonZora_Forward:
    %PlayAnimation(0,1,10)
    RTS
  EonZora_Left:
    %PlayAnimation(2,3,10)
    RTS
  EonZora_Right:
    %PlayAnimation(4,5,10)
    RTS
  EonZora_Back:
    %PlayAnimation(6,7,10)
    RTS
}
```

## Movement Routine (`EonZora_Walk`)
This routine controls the Eon Zora's random walking behavior. It uses a timer (`SprTimerA, X`) to periodically select a new random direction and update the sprite's `SprXSpeed, X` and `SprYSpeed, X`.

```asm
EonZora_Walk:
{
  LDA.w SprTimerA, X : BNE +
    JSL GetRandomInt : AND.b #$03 : STA.w SprAction, X : TAY
    LDA.w .speed_x, Y : STA.w SprXSpeed, X
    LDA.w .speed_y, Y : STA.w SprYSpeed, X
    LDA.b #$6A : STA.w SprTimerA, X
  +
  RTS

  .speed_x
  db 0, -4, 4, 0
  .speed_y
  db 4, 0, 0, -4
}
```

## Dialogue Handling (`EonZora_HandleDialogue`)
This routine manages the Eon Zora's dialogue, which is context-sensitive based on Link's current `AreaIndex`. It checks for specific `AreaIndex` values to display tailored messages. If no specific area matches, a default message is displayed, and interacting with it can randomly set the `FOUNDRINGS` global variable.

```asm
EonZora_HandleDialogue:
{
  LDA.w AreaIndex : CMP.b #$63 : BNE .not_wisdom
    %ShowSolicitedMessage($01AC)
    JMP ++
  .not_wisdom
  CMP.b #$5B : BNE .not_power
    %ShowSolicitedMessage($01AB)
    JMP ++
  .not_power
  CMP.b #$40 : BNE .not_pyramid
    %ShowSolicitedMessage($01AA)
    JMP ++
  .not_pyramid
  CMP.b #$70 : BNE .not_underwater
    %ShowSolicitedMessage($01AD)
    JMP ++
  .not_underwater
  CMP.b #$42 : BNE .not_portal
    %ShowSolicitedMessage($01AF)
    JMP ++
  .not_portal
  %ShowSolicitedMessage($01AE) : BCC .no_talk
    JSL GetRandomInt : AND.b #$06 : STA.l FOUNDRINGS
  .no_talk
  ++
  RTS
}
```

## Drawing (`Sprite_EonZora_Draw`)
The drawing routine handles OAM allocation and animation. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

```asm
Sprite_EonZora_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
  LDA .start_index, Y : STA $06

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $02, $04, $06, $08, $0A, $0C, $0D
  .nbr_of_tiles
  db 1, 1, 1, 1, 1, 1, 0, 0
  .x_offsets
  dw 0, 16
  dw 0, -16
  dw 0, 8
  dw 0, 8
  dw 0, -8
  dw 0, -8
  dw 0
  dw 0
  .y_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0
  dw 0
  .chr
  db $60, $62
  db $60, $62
  db $40, $41
  db $43, $44
  db $40, $41
  db $43, $44
  db $64
  db $64
  .properties
  db $39, $39
  db $79, $79
  db $39, $39
  db $39, $39
  db $79, $79
  db $79, $79
  db $39
  db $79
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02
  db $02
}
```

## Design Patterns
*   **Context-Sensitive Dialogue**: The NPC's dialogue dynamically changes based on Link's current `AreaIndex`, providing a rich and immersive storytelling experience tailored to the player's location.
*   **Random Movement**: The Zora exhibits random walking behavior, contributing to the environmental ambiance and making the world feel more alive.
*   **NPC Interaction**: Provides dialogue and has the potential to grant items (randomly setting `FOUNDRINGS`), adding an element of surprise and reward to player interactions.
*   **Animation-Driven Movement**: The sprite's movement states are directly tied to specific animations for each direction, ensuring visual consistency between its actions and appearance.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
