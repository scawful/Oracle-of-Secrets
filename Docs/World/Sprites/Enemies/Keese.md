# Keese

## Overview
The Keese sprite (`!SPRID = $11`) is a versatile enemy that encompasses multiple variations: Ice Keese, Fire Keese, and Vampire Bat. Its behavior is dynamically determined by its `SprSubtype`.

## Subtypes
*   `00` - Ice Keese
*   `01` - Fire Keese
*   `02` - Vampire Bat

## Sprite Properties
*   **`!SPRID`**: `$11` (Vanilla sprite ID for Keese/Vampire Bat)
*   **`!NbrTiles`**: `08`
*   **`!Harmless`**: `00`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00` (Dynamically set in `_Prep` based on subtype)
*   **`!Damage`**: `00` (Damage is handled by projectiles or specific attack logic)
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
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
*   **`!Prize`**: `00` (Dynamically set in `_Prep` based on subtype)
*   **`!Sound`**: `00`
*   **`!Interaction`**: `00`
*   **`!Statue`**: `00`
*   **`!DeflectProjectiles`**: `00`
*   **`!ImperviousArrow`**: `00`
*   **`!ImpervSwordHammer`**: `00`
*   **`!Boss`**: `00`

## Main Structure (`Sprite_Keese_Long`)
This routine dispatches to different drawing and main logic routines based on the sprite's `SprSubtype`.

```asm
Sprite_Keese_Long:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : CMP.b #$02 : BEQ +
    JSR Sprite_Keese_Draw
    JSL Sprite_DrawShadow
    JSL Sprite_CheckActive : BCC .SpriteIsNotActive
      JSR Sprite_Keese_Main
    .SpriteIsNotActive
    JMP ++
  +
  JSR Sprite_VampireBat_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC ++
    JSR Sprite_VampireBat_Main
  ++
  PLB
  RTL
}
```

## Initialization (`Sprite_Keese_Prep`)
This routine initializes sprite properties upon spawning, including health and prize, based on its subtype.

```asm
Sprite_Keese_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #$30 : STA.w SprTimerC, X
  LDA.w SprSubtype, X : CMP.b #$02 : BNE +
    LDA.b #$20 : STA.w SprHealth, X
    BRA ++
  +
  LDA.b #$03 : STA.w SprNbrOAM, X
  LDA.b #$03 : STA.w SprPrize, X
  ++
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_Keese_Main`)
The Keese's behavior is managed by a state machine with `Keese_Idle` and `Keese_FlyAround` states.

*   **`Keese_Idle`**: The sprite remains stationary until Link is within a certain distance, then transitions to `Keese_FlyAround`.
*   **`Keese_FlyAround`**: The Keese flies around, plays an animation, checks for collisions with Link and tiles, and can initiate an attack. It uses `GetRandomInt` for varied movement and `Sprite_ProjectSpeedTowardsPlayer` to move towards Link.

```asm
Sprite_Keese_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Keese_Idle
  dw Keese_FlyAround

  Keese_Idle:
  {
    STZ.w SprFrame, X
    ; Wait til the player is nearby then fly around
    LDA.w SprTimerC, X : BEQ .move
    JSL GetDistance8bit_Long : CMP.b #$20 : BCS +
      .move
      INC.w SprAction, X
      JSL GetRandomInt
      STA.w SprTimerA, X
    +
    RTS
  }

  Keese_FlyAround:
  {
    %PlayAnimation(0,5,8)
    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_CheckDamageFromPlayer : BCC +
      JSL ForcePrizeDrop_long
    +
    JSL Sprite_DamageFlash_Long
    JSL Sprite_BounceFromTileCollision

    JSL GetRandomInt : AND.b #$3F : BNE +
      LDA.b #$10 : STA.w SprTimerC, X
    +
    JSR Sprite_Keese_Attack

    LDA.w SprTimerA, X : AND.b #$10 : BNE +
      LDA.b #$40
      JSL Sprite_ProjectSpeedTowardsPlayer
    +

    JSL Sprite_SelectNewDirection
    JSL Sprite_Move

    LDA.w SprTimerA, X : BNE +
      STZ.w SprAction, X
    +
    RTS
  }
}
```

## Attack Logic (`Sprite_Keese_Attack`)
This routine handles the Keese's attack, which varies by subtype:

*   **Ice Keese (`SprSubtype = 0`)**: Spawns sparkle garnish and a blind laser trail.
*   **Fire Keese (`SprSubtype = 1`)**: Utilizes `Sprite_Twinrova_FireAttack`.

```asm
Sprite_Keese_Attack:
{
  LDA.w SprTimerC, X : BEQ +
    LDA.w SprSubtype, X : BEQ ++
      JSL Sprite_Twinrova_FireAttack
      JMP +
    ++
    JSL Sprite_SpawnSparkleGarnish
    JSL BlindLaser_SpawnTrailGarnish
  +
  RTS
}
```

## Drawing (`Sprite_Keese_Draw`)
The drawing routine handles OAM allocation, animation, and palette adjustments based on the sprite's subtype. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations.

```asm
Sprite_Keese_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08
  LDA.w SprMiscB, X : STA $09
  LDA.w SprSubtype, X : CMP.b #$01 : BNE +
    LDA.b #$0A : EOR $08 : STA $08
  +

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
*   **Subtype-based Behavior**: The sprite uses `SprSubtype` to implement distinct behaviors and appearances for Ice Keese, Fire Keese, and Vampire Bat, all under a single `!SPRID`.
*   **Dynamic Property Initialization**: Health and prize values are set dynamically during the `_Prep` routine based on the sprite's subtype.
*   **Conditional Drawing and Palette**: The drawing routine adjusts the sprite's palette and potentially its graphics based on its subtype, allowing for visual differentiation.
*   **Randomized Movement**: Utilizes `GetRandomInt` to introduce variability in movement patterns, making the enemy less predictable.
*   **Projectile Attacks**: Implements different projectile attacks based on subtype, showcasing varied offensive capabilities.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, which is crucial for accurate sprite rendering.
