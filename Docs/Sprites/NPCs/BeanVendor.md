# Bean Vendor

## Overview
The Bean Vendor is an NPC (Non-Player Character) sprite designed for player interaction, primarily through dialogue. It features a simple state machine to manage its idle and talking behaviors.

## Sprite Properties
*   **`!SPRID`**: `$00` (Vanilla sprite ID, likely overridden)
*   **`!NbrTiles`**: `08`
*   **`!Harmless`**: `01` (Indicates the sprite is harmless to Link)
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `01` (Indicates the sprite is impervious to all attacks)
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `01`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `00`
*   **`!Persist`**: `00`
*   **`!Statis`**: `00`
*   **`!CollisionLayer`**: `00`
*   **`!CanFall`**: `00`
*   **`!DeflectArrow`**: `00`
*   **`!WaterSprite`**: `00`
*   **`!Blockable`**: `00`
*   **`!Prize`**: `00`
*   **`!Sound`**: `00`
*   **`!Interaction`**: `00`
*   **`!Statue`**: `00`
*   **`!DeflectProjectiles`**: `00`
*   **`!ImperviousArrow`**: `00`
*   **`!ImpervSwordHammer`**: `00`
*   **`!Boss`**: `00`

## Main Structure (`Sprite_BeanVendor_Long`)
This routine is the main entry point for the Bean Vendor, executed every frame. It handles drawing, shadow rendering, and dispatches to the main logic if the sprite is active.

```asm
Sprite_BeanVendor_Long:
{
  PHB : PHK : PLB
  JSR Sprite_BeanVendor_Draw
  JSL Sprite_DrawShadow

  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_BeanVendor_Main
  .SpriteIsNotActive

  PLB
  RTL
}
```

## Initialization (`Sprite_BeanVendor_Prep`)
This routine runs once when the Bean Vendor is spawned. It initializes `SprDefl, X`, `SprTimerC, X`, `SprNbrOAM, X`, and `SprPrize, X`.

```asm
Sprite_BeanVendor_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #$30 : STA.w SprTimerC, X
  LDA.b #$03 : STA.w SprNbrOAM, X
  LDA.b #$03 : STA.w SprPrize, X
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_BeanVendor_Main`)
The Bean Vendor's core behavior is managed by a state machine with `BeanVendor_Idle` and `BeanVendor_Talk` states.

*   **`BeanVendor_Idle`**: The vendor plays an idle animation. When Link is nearby (`GetDistance8bit_Long`), it transitions to the `BeanVendor_Talk` state.
*   **`BeanVendor_Talk`**: The vendor plays a talking animation and displays a message using `JSL Interface_PrepAndDisplayMessage`. Once the message is dismissed, it transitions back to the `BeanVendor_Idle` state.

```asm
Sprite_BeanVendor_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw BeanVendor_Idle
  dw BeanVendor_Talk

  BeanVendor_Idle:
  {
    %PlayAnimation(0,1,15)
    JSL GetDistance8bit_Long : CMP.b #$20 : BCS +
      INC.w SprAction, X
    +
    RTS
  }

  BeanVendor_Talk:
  {
    %PlayAnimation(2,3,8)
    JSL Interface_PrepAndDisplayMessage : BCC +
      STZ.w SprAction, X
    +
    RTS
  }
}
```

## Drawing (`Sprite_BeanVendor_Draw`)
The drawing routine handles OAM allocation and animation. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations.

```asm
Sprite_BeanVendor_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08
  LDA.w SprMiscB, X : STA $09

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

  ; If SprMiscA != 0, then use 4th sheet
  LDA.b $09 : BEQ +
    LDA .chr_2, X : STA ($90), Y
    JMP ++
  +
  LDA .chr, X : STA ($90), Y
  ++
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $01, $03, $04, $06, $08
  .nbr_of_tiles
  db 0, 1, 0, 1, 1, 0
  .x_offsets
  dw 0
  dw -4, 4
  dw 0
  dw -4, 4
  dw -4, 4
  dw 0
  .y_offsets
  dw 0
  dw 0, 0
  dw 0
  dw 0, 0
  dw 0, 0
  dw 0
  .chr
  db $80
  db $A2, $A2
  db $82
  db $84, $84
  db $A4, $A4
  db $A0
  .chr_2
  db $C0
  db $E2, $E2
  db $C2
  db $C4, $C4
  db $E4, $E4
  db $E0
  .properties
  db $35
  db $35, $75
  db $35
  db $35, $75
  db $35, $75
  db $35
  .sizes
  db $02
  db $02, $02
  db $02
  db $02, $02
  db $02, $02
  db $02
}
```

## Design Patterns
*   **NPC Interaction**: The sprite is designed to engage with the player through dialogue, triggered by proximity.
*   **State Machine**: Employs a simple state machine to manage its `Idle` and `Talk` behaviors, ensuring appropriate animations and actions based on player interaction.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
