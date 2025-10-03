# Leever

## Overview
The Leever sprite is a custom implementation that overrides the vanilla Leever behavior (`Sprite_71_Leever`). It features distinct states for being underground, emerging, attacking, and digging back down, with randomized timers controlling its transitions.

## Vanilla Override
This custom Leever implementation hooks into the vanilla sprite ID $71. It uses a custom flag at `$0FFF` to determine whether to execute its custom logic (`Sprite_Leever_Long`) or fall back to the original vanilla Leever behavior (`Sprite_71_Leever`).

```asm
pushpc

Sprite_71_Leever =  $06CBA2

org $069365 : dw Sprite_71_Leever_Alt

Sprite_71_Leever_Alt:
{
  LDA.w $0FFF : BEQ +
    JSL Sprite_Leever_Long
    JMP ++
  +
  JSR Sprite_71_Leever
  ++
  RTS
}
assert pc() <= $06A5C0

pullpc
```

## Sprite Properties
Explicit sprite properties (`!SPRID`, `!Health`, etc.) are not defined within this file, suggesting it either inherits vanilla properties for sprite ID $71 or these are defined in a separate configuration file.

## Main Structure (`Sprite_Leever_Long`)
This routine is the main entry point for the custom Leever logic, executed every frame. It handles bank setup, conditional drawing (skipping drawing when underground), and dispatches to the main logic if the sprite is active.

```asm
Sprite_Leever_Long:
{
  PHB : PHK : PLB
  LDA.w SprAction, X : BEQ +
    JSR Sprite_Leever_Draw
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Leever_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Movement Routine (`Sprite_Leever_Move`)
A shared routine for handling the Leever's movement, including applying speed towards the player, moving the sprite, and bouncing off tiles.

```asm
Sprite_Leever_Move:
{
  JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  RTS
}
```

## Main Logic & State Machine (`Sprite_Leever_Main`)
The Leever's core behavior is managed by a state machine with four distinct states:

*   **`Leever_Underground`**: The Leever moves underground. After a timer (`SprTimerA`) expires, it transitions to `Leever_Emerge`.
*   **`Leever_Emerge`**: The Leever plays a backwards animation as it emerges. After a randomized timer, it transitions to `Leever_Attack`.
*   **`Leever_Attack`**: The Leever plays an attack animation, checks for damage to/from Link, and moves. After a timer, it transitions to `Leever_Dig`.
*   **`Leever_Dig`**: The Leever plays an animation as it digs back into the ground. After a randomized timer, it transitions back to `Leever_Underground`.

```asm
Sprite_Leever_Main:
{
  JSL Sprite_DamageFlash_Long
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Leever_Underground
  dw Leever_Emerge
  dw Leever_Attack
  dw Leever_Dig

  Leever_Underground:
  {
    LDA.w SprTimerA, X : BNE +
      LDA.b #$40 : STA.w SprTimerA, X
      INC.w SprAction, X
    +
    LDA.b #$10
    JSR Sprite_Leever_Move
    RTS
  }

  Leever_Emerge:
  {
    %PlayAnimBackwards(3, 2, 10)
    LDA.w SprTimerA, X : BNE +
      JSL GetRandomInt
      AND.b #$3F
      ADC.b #$A0
      STA.w $0DF0,X
      INC.w SprAction, X
      STZ.w SprXSpeed, X : STZ.w SprYSpeed, X
    +
    RTS
  }

  Leever_Attack:
  {
    %PlayAnimation(0, 1, 10)
    LDA.w SprTimerA, X : BNE +
      LDA.b #$7F : STA.w SprTimerA, X
      INC.w SprAction, X
    +
    PHX
    JSL Sprite_CheckIfRecoiling
    JSL Sprite_CheckDamageToPlayerSameLayer
    JSL Sprite_CheckDamageFromPlayer
    PLX
    LDA.b #$0C
    JSR Sprite_Leever_Move
    RTS
  }

  Leever_Dig:
  {
    %PlayAnimation(2, 3, 10)
    LDA.w SprTimerA, X : BNE +
      JSL GetRandomInt
      AND.b #$1F
      ADC.b #$40
      STA.w $0DF0,X
      STZ.w SprAction, X
    +
    LDA.b #$08
    JSR Sprite_Leever_Move
    RTS
  }
}
```

## Drawing (`Sprite_Leever_Draw`)
The drawing routine handles OAM allocation and animation. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations.

```asm
Sprite_Leever_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08


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
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
  db $00, $01, $02, $03
  .nbr_of_tiles
  db 0, 0, 0, 0
  .x_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  .y_offsets
  dw 0
  dw 0
  dw 0
  dw 0
  .chr
  db $C4
  db $C6
  db $C2
  db $C0
  .properties
  db $33
  db $33
  db $33
  db $33
  .sizes
  db $02
  db $02
  db $02
  db $02
}
```

## Design Patterns
*   **Vanilla Override**: Explicitly overrides a vanilla sprite's behavior, demonstrating how to replace existing game logic with custom implementations.
*   **Conditional Logic**: Uses a custom flag (`$0FFF`) to dynamically switch between vanilla and custom behaviors, offering flexibility in game design.
*   **Emerging/Digging State Machine**: Implements a robust state machine to manage the Leever's characteristic emerging from and digging back into the ground, with randomized timers for unpredictable transitions.
*   **Animation Control**: Utilizes `%PlayAnimBackwards` for specific animation effects, such as the Leever emerging from the ground.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, essential for accurate sprite rendering.
