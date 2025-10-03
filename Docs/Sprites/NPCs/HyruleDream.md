# Hyrule Dream

## Overview
The Hyrule Dream sprite represents a special NPC that appears indoors and plays a role in a specific questline. It interacts with Link through dialogue and grants a unique "Dream" item, with its presence and actions tied to game progression.

## Sprite Properties
Explicit sprite properties (`!SPRID`, `!NbrTiles`, etc.) are not defined within this file. It is assumed that these properties are either inherited from a vanilla sprite ID or defined in a separate configuration file, as this file focuses on the sprite's behavior and drawing.

## Main Logic (`Sprite_HyruleDream_Main`)
This routine manages the Hyrule Dream's behavior through a state machine:

*   **`HyruleDream_Idle`**: The sprite plays an idle animation. When Link is within a certain proximity (`GetDistance8bit_Long`), it transitions to the `HyruleDream_Talk` state.
*   **`HyruleDream_Talk`**: The sprite continues its idle animation and displays a solicited message (`%ShowSolicitedMessage($01B3)`). Upon completion of the message, it transitions to `HyruleDream_GiveItem`.
*   **`HyruleDream_GiveItem`**: The sprite maintains its idle animation. After a timer (`SprTimerA, X`) expires, it grants Link the "Dream" item (`LDY #$12`, `JSL Link_ReceiveItem`), sets a flag (`$7EF410`) indicating the Dream has been obtained, and then despawns itself (`STZ.w SprState, X`).

```asm
Sprite_HyruleDream_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw HyruleDream_Idle
  dw HyruleDream_Talk
  dw HyruleDream_GiveItem

  HyruleDream_Idle:
  {
    %PlayAnimation(0,0,1)
    JSL GetDistance8bit_Long : CMP.b #$20 : BCS +
      INC.w SprAction, X
    +
    RTS
  }

  HyruleDream_Talk:
  {
    %PlayAnimation(0,0,1)
    %ShowSolicitedMessage($01B3) : BCC +
      INC.w SprAction, X
    +
    RTS
  }

  HyruleDream_GiveItem:
  {
    %PlayAnimation(0,0,1)
    LDA.w SprTimerA, X : BNE +
      LDY #$12 : JSL Link_ReceiveItem
      LDA.b #$01 : STA.l $7EF410
      STZ.w SprState, X
    +
    RTS
  }
}
```

## Initialization (`Sprite_HyruleDream_Prep`)
This routine initializes the Hyrule Dream sprite upon spawning. It sets `SprDefl, X` to `$80` (preventing despawning off-screen). Crucially, it checks the "Dream" flag (`$7EF410`). If Link has already obtained the Dream, the sprite immediately despawns (`STZ.w SprState, X`), ensuring it only appears once.

```asm
Sprite_HyruleDream_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.l $7EF410 : BNE +
    STZ.w SprState, X
  +
  PLB
  RTL
}
```

## Drawing (`Sprite_HyruleDream_Draw`)
The drawing routine handles OAM allocation and animation. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

```asm
Sprite_HyruleDream_Draw:
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
  db $00
  .nbr_of_tiles
  db 3
  .x_offsets
  dw -8, 8, -8, 8
  .y_offsets
  dw -8, -8, 8, 8
  .chr
  db $C0, $C2, $E0, $E2
  .properties
  db $3B, $7B, $3B, $7B
  .sizes
  db $02, $02, $02, $02
}
```

## Design Patterns
*   **NPC Interaction**: The sprite is designed to engage with the player through dialogue and the granting of a unique item, driving a specific questline.
*   **Quest Progression Integration**: The sprite's appearance and item-granting are directly tied to a flag (`$7EF410`) for the "Dream" item, ensuring it appears only once per playthrough.
*   **Conditional Spawning/Despawning**: The sprite dynamically despawns if Link has already obtained the "Dream" item, preventing redundant interactions.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
