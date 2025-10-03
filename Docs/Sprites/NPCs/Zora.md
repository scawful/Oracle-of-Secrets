# Zora (Generic Sea Zora Handler)

## Overview
The `zora.asm` file serves as a centralized handler for various Zora NPCs within the game. It acts as a dispatcher, directing execution to specific drawing and main logic routines for the Zora Princess, Eon Zora, Eon Zora Elder, and a generic Sea Zora. This dynamic dispatch is based on the current `ROOM`, `WORLDFLAG`, and `SprSubtype`, allowing for a single sprite definition to manage a diverse cast of Zora characters.

## Main Structure (`Sprite_Zora_Long`)
This routine is a complex dispatcher that determines which Zora variant to draw and process based on several game state variables:

*   **Zora Princess**: If the current `ROOM` is `$0105`, it calls `Sprite_ZoraPrincess_Draw` and sets `SprMiscG, X` to `$01`.
*   **Eon Zora**: If `WORLDFLAG` is not `0`, it calls `Sprite_EonZora_Draw`, `Sprite_DrawShadow`, and sets `SprMiscG, X` to `$02`.
*   **Eon Zora Elder**: If `SprSubtype, X` is not `0` (and not the Princess or Eon Zora), it calls `Sprite_EonZoraElder_Draw` and sets `SprMiscG, X` to `$03`.
*   **Generic Sea Zora**: Otherwise, it calls `Sprite_Zora_Draw`, `Sprite_DrawShadow`, and sets `SprMiscG, X` to `0`.
*   After drawing, it calls `Sprite_CheckActive` and then `Sprite_Zora_Handler` if the sprite is active.

```asm
Sprite_Zora_Long:
{
  PHB : PHK : PLB

  ; Check what Zora we are drawing
  REP #$30
  LDA.w ROOM : CMP.w #$0105 : BNE .not_princess
    SEP #$30
    JSR Sprite_ZoraPrincess_Draw
    LDA.b #$01 : STA.w SprMiscG, X
    JMP +
  .not_princess
  LDA.w WORLDFLAG : AND.w #$00FF : BEQ .eon_draw
    SEP #$30
    JSR Sprite_EonZora_Draw
    JSL Sprite_DrawShadow
    LDA.b #$02 : STA.w SprMiscG, X
    JMP +
  .eon_draw
  SEP #$30
  LDA.w SprSubtype, X : BNE .special_zora
    JSR Sprite_Zora_Draw
    JSL Sprite_DrawShadow
    STZ.w SprMiscG, X
    JMP +
  .special_zora
  JSR Sprite_EonZoraElder_Draw
  LDA.b #$03 : STA.w SprMiscG, X
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Zora_Handler
  .SpriteIsNotActive

  PLB
  RTL
}
```

## Initialization (`Sprite_Zora_Prep`)
This routine is empty, indicating that custom initialization for the Zora handler is minimal or handled by the individual Zora sprite routines.

## Main Logic Dispatcher (`Sprite_Zora_Handler`)
This routine dispatches to the appropriate main logic routine for the specific Zora variant based on the value of `SprMiscG, X`:

*   `$01`: Calls `Sprite_ZoraPrincess_Main`
*   `$00`: Calls `Sprite_Zora_Main` (Generic Sea Zora)
*   `$02`: Calls `Sprite_EonZora_Main`
*   `$03`: Calls `Sprite_EonZoraElder_Main`

```asm
Sprite_Zora_Handler:
{
  LDA.w SprMiscG, X
  CMP.b #$01 : BNE .not_princess
    JSR Sprite_ZoraPrincess_Main
    RTS
  .not_princess

  JSL JumpTableLocal

  dw Sprite_Zora_Main
  dw Sprite_ZoraPrincess_Main
  dw Sprite_EonZora_Main
  dw Sprite_EonZoraElder_Main
}
```

## `Sprite_Zora_Main` (Generic Sea Zora)
This routine defines the behavior for a generic Sea Zora NPC.

*   **Head Tracking**: Calls `Zora_TrackHeadToPlayer` to make the Zora face Link.
*   **Player Collision**: Prevents Link from passing through the Zora (`JSL Sprite_PlayerCantPassThrough`).
*   **Dialogue**: Calls `Zora_HandleDialogue` for context-sensitive dialogue interactions.
*   **Animation**: Uses a jump table for animation states: `Zora_Forward`, `Zora_Right`, `Zora_Left`, each playing a specific animation.

```asm
Sprite_Zora_Main:
{
  JSR Zora_TrackHeadToPlayer
  JSL Sprite_PlayerCantPassThrough

  JSR Zora_HandleDialogue

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Zora_Forward
  dw Zora_Right
  dw Zora_Left

  Zora_Forward:
  {
    %PlayAnimation(0,0,10)
    RTS
  }

  Zora_Right:
  {
    %PlayAnimation(1,1,10)
    RTS
  }

  Zora_Left:
  {
    %PlayAnimation(1,1,10)
    RTS
  }
}
```

## `Zora_TrackHeadToPlayer`
This routine makes the Zora face Link by setting `SprAction, X` to `0` (forward) or `1` (right/left) based on Link's horizontal position relative to the Zora.

## `Zora_HandleDialogue`
This routine handles context-sensitive dialogue for the generic Sea Zora. It checks the `Crystals` SRAM flag (specifically bit `$20`) to determine if a certain crystal has been collected. Based on this and the Zora's `SprAction, X`, it displays different solicited messages (`$01A6`, `$01A5`, or `$01A4`).

## Drawing (`Sprite_Zora_Draw`)
This routine handles OAM allocation and animation for the generic Sea Zora. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

```asm
Sprite_Zora_Draw:
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
  db $00, $02, $04
  .nbr_of_tiles
  db 1, 1, 1
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  .y_offsets
  dw -8, 0
  dw -8, 0
  dw -8, 0
  .chr
  db $DE, $EE
  db $DC, $EC
  db $DC, $EC
  .properties
  db $35, $35
  db $35, $35
  db $75, $75
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
}
```

## Design Patterns
*   **Centralized NPC Handler**: This file acts as a central dispatcher for multiple Zora-type NPCs (Zora Princess, Eon Zora, Eon Zora Elder, and generic Sea Zora), demonstrating efficient management of diverse character behaviors from a single entry point.
*   **Multi-Character Sprite (Conditional Drawing/Logic)**: A single sprite ID is used to represent various Zora characters, with their specific drawing and main logic routines dynamically selected based on game state variables like `ROOM`, `WORLDFLAG`, and `SprSubtype`.
*   **Context-Sensitive Dialogue**: The generic Sea Zora's dialogue changes based on collected crystals and its current `SprAction`, providing dynamic and responsive interactions with the player.
*   **Player Collision**: Implements `JSL Sprite_PlayerCantPassThrough` to make the Zora NPCs solid objects that Link cannot walk through.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
