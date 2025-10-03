# Tingle

## Overview
The Tingle sprite (`!SPRID = Sprite_Tingle`) implements the iconic map salesman character. Tingle's primary function is to sell a map to Link, with his interactions and dialogue flow being conditional on Link's rupee count and whether the map has already been purchased.

## Sprite Properties
*   **`!SPRID`**: `Sprite_Tingle` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `02`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `01` (Impervious to all attacks)
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `01`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `02`
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

## Main Structure (`Sprite_Tingle_Long`)
This routine handles Tingle's drawing, shadow rendering, and dispatches to his main logic if the sprite is active.

```asm
Sprite_Tingle_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Tingle_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Tingle_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Tingle_Prep`)
This routine is empty, indicating that Tingle requires no custom initialization upon spawning.

## Main Logic & State Machine (`Sprite_Tingle_Main`)
Tingle's core behavior is managed by a state machine that facilitates a dialogue and transaction flow for selling a map.

*   **Player Collision**: Prevents Link from passing through Tingle (`JSL Sprite_PlayerCantPassThrough`).
*   **`Tingle_Idle`**: Plays an animation. Checks if Link has already bought the map (`$7EF3D6` bit `$01`). If so, it transitions to `Tingle_AlreadyBoughtMap`. Otherwise, it displays a solicited message (`%ShowSolicitedMessage($01A4)`) asking if Link wants to buy a map. Based on Link's response (`$1CE8`), it transitions to `Tingle_BuyMap` or `Tingle_PlayerSaidNo`.
*   **`Tingle_BuyMap`**: Plays an animation. Checks if Link has enough rupees (`$7EF360`). If sufficient, it deducts the rupees, sets the map bought flag (`$7EF3D6` bit `$01`), displays a confirmation message (`%ShowUnconditionalMessage($01A5)`), and transitions to `Tingle_AlreadyBoughtMap`. If rupees are insufficient, it transitions to `Tingle_NotEnoughMoney`.
*   **`Tingle_PlayerSaidNo`**: Plays an animation, displays a message (`%ShowUnconditionalMessage($01A6)`), and returns to `Tingle_Idle`.
*   **`Tingle_AlreadyBoughtMap`**: Plays an animation, displays a message (`%ShowUnconditionalMessage($01A3)`) confirming the map has been bought, and returns to `Tingle_Idle`.
*   **`Tingle_NotEnoughMoney`**: Plays an animation, displays a message (`%ShowUnconditionalMessage($029)`) about insufficient funds, and returns to `Tingle_Idle`.

```asm
Sprite_Tingle_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Tingle_Idle
  dw Tingle_BuyMap
  dw Tingle_PlayerSaidNo
  dw Tingle_AlreadyBoughtMap
  dw Tingle_NotEnoughMoney

  ; 0x00
  Tingle_Idle:
  {
    %PlayAnimation(0, 1, 16)
    ; Player has already bought the map
    LDA.l $7EF3D6 : AND.b #$01 : BNE .already_bought_map

    %ShowSolicitedMessage($01A4) : BCC .didnt_converse
      LDA $1CE8 : BEQ .buy_map

      ; Player said no
      %GotoAction(2)
      RTS

    .buy_map
    %GotoAction(1)
    RTS

    .already_bought_map
    %GotoAction(3)
    RTS

    .didnt_converse
    RTS
  }

  ; 0x01
  Tingle_BuyMap:
  {
    %PlayAnimation(0, 1, 16)
    REP #$20
    LDA.l $7EF360 : CMP.w #$0064 ; 100 rupees
    SEP #$30
    BCC .not_enough_money

      ; Deduct rupees
      REP #$20
      LDA.l $7EF360
      SEC : SBC.w #$0064
      STA.l $7EF360
      SEP #$30

      ; Set map bought flag
      LDA.l $7EF3D6 : ORA.b #$01 : STA.l $7EF3D6

      %ShowUnconditionalMessage($01A5)
      %GotoAction(3)
      RTS

    .not_enough_money
    %GotoAction(4)
    RTS
  }

  ; 0x02
  Tingle_PlayerSaidNo:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($01A6)
    %GotoAction(0)
    RTS
  }

  ; 0x03
  Tingle_AlreadyBoughtMap:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($01A3)
    %GotoAction(0)
    RTS
  }

  ; 0x04
  Tingle_NotEnoughMoney:
  {
    %PlayAnimation(0, 1, 16)
    %ShowUnconditionalMessage($029)
    %GotoAction(0)
    RTS
  }
}
```

## Drawing (`Sprite_Tingle_Draw`)
The drawing routine handles OAM allocation and animation. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

```asm
Sprite_Tingle_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
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
  db $00, $04
.nbr_of_tiles
  db 3, 3
.x_offsets
  dw -4, 12, 0, 0
  dw 4, -12, 0, 0
.y_offsets
  dw -8, -8, 0, -11
  dw -8, -8, 0, -10
.chr
  db $82, $84, $A0, $80
  db $82, $84, $A0, $80
.properties
  db $39, $39, $39, $39
  db $79, $79, $79, $39
.sizes
  db $02, $02, $02, $02
  db $02, $02, $02, $02

}
```

## Design Patterns
*   **Shop System**: Tingle implements a basic shop system for selling a map, including price checks and rupee deduction, providing a functional in-game vendor.
*   **Quest Gating/Progression**: The availability of the map and Tingle's dialogue are conditional on whether Link has already purchased the map (`$7EF3D6` bit `$01`), ensuring a logical progression of events.
*   **Conditional Transactions**: The process of buying the map involves checking Link's rupee count and deducting the cost upon a successful purchase, simulating a real in-game economy.
*   **Player Choice and Branching Dialogue**: Link's responses (`$1CE8`) to Tingle's inquiries directly influence the flow of conversation and the available options, leading to a personalized interaction.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
