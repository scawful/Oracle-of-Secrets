# Octorok

## Overview
The Octorok sprite (`!SPRID = $08`) is a complex enemy implementation that supports both land-based and water-based variations. It features dynamic behavior, including transformation between forms, distinct movement patterns, and projectile attacks.

## Sprite Properties
*   **`!SPRID`**: `$08` (Vanilla sprite ID for Octorok)
*   **`!NbrTiles`**: `05`
*   **`!Harmless`**: `00`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00` (Health is likely set dynamically or is vanilla)
*   **`!Damage`**: `00` (Damage is likely from projectiles)
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00` (Shadow is drawn conditionally in `_Long`)
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

## Main Structure (`Sprite_Octorok_Long`)
This routine acts as a dispatcher, determining whether to execute Land Octorok or Water Octorok logic based on `SprSubtype`.

```asm
Sprite_Octorok_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Octorok_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    LDA.w SprSubtype, X : BEQ +
      JSL Sprite_DrawWaterRipple
      JSR Sprite_WaterOctorok_Main
      JMP ++
    +
    JSL Sprite_DrawShadow
    JSR Sprite_Octorok_Main
    ++
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Octorok_Prep`)
This routine is currently empty, indicating that initial setup is minimal or handled by vanilla routines.

## Land Octorok Main Logic (`Sprite_Octorok_Main`)
This routine handles the behavior of a land-based Octorok, including movement and potential transformation into a Water Octorok.

*   **Movement**: Calls `Sprite_Octorok_Move` for general movement.
*   **Transformation**: Checks the tile type the Octorok is on. If it's a water tile, the Octorok transforms into a Water Octorok by setting `SprSubtype, X` to `01`.
*   **Directional States**: Uses a jump table to manage animations for moving in different directions (Down, Up, Left, Right).

```asm
Sprite_Octorok_Main:
{
  JSR Sprite_Octorok_Move

  ; TILETYPE 08
  LDA.l $7FF9C2,X : CMP.b #$08 : BEQ .water_tile
    ; TILETYPE 09
    CMP.b #$09 : BNE .not_water_tile
  .water_tile
    LDA.b #$01 : STA.w SprSubtype, X
    STZ.w SprAction, X
    STZ.w SprMiscG, X
    RTS
  .not_water_tile

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Octorok_MoveDown
  dw Octorok_MoveUp
  dw Octorok_MoveLeft
  dw Octorok_MoveRight

  Octorok_MoveDown:
  {
    %PlayAnimation(0,1,10)
    RTS
  }

  Octorok_MoveUp:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,10)
    RTS
  }

  Octorok_MoveLeft:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,10)
    RTS
  }

  Octorok_MoveRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6,7,10)
    RTS
  }
}
```

## Octorok Movement (`Sprite_Octorok_Move`)
This shared routine handles the Octorok's general movement, damage reactions, and tile collision.

*   **Damage & Collision**: Handles damage flash (`Sprite_DamageFlash_Long`), movement (`Sprite_Move`), and checks for damage to/from Link.
*   **Directional Logic**: Sets the sprite's action based on its direction (`SprMiscC, X`).
*   **Tile Collision**: Detects tile collisions and changes the Octorok's direction accordingly.
*   **Barrage Logic**: Contains logic related to a potential projectile barrage (`octorok_used_barrage`).

```asm
Sprite_Octorok_Move:
{
  JSL Sprite_DamageFlash_Long
  JSL Sprite_Move
  JSL Sprite_CheckDamageFromPlayer
  JSL Sprite_CheckDamageToPlayer

  ; Set the SprAction based on the direction
  LDA.w SprMiscC, X : AND.b #$03 : TAY
  LDA.w .direction, Y : STA.w SprAction, X

  LDA.w SprMiscF, X : AND.b #$01 : BNE .octorok_used_barrage
    LDA.w SprMiscC, X : AND.b #$02 : ASL A : STA.b $00
    INC.w SprDelay, X
    LDA.w SprDelay, X
    LSR A
    LSR A
    LSR A
    AND.b #$03
    ORA.b $00
    STA.w SprGfx, X

    LDA.w SprTimerA, X : BNE .wait
      INC.w SprMiscF,X

      LDY.w SprType,X
      LDA.w .timer-8,Y : STA.w SprTimerA,X

      RTS

  .wait
  LDY.w SprMiscC, X

  LDA.w .speed_x, Y : STA.w SprXSpeed, X
  LDA.w .speed_y, Y : STA.w SprYSpeed, X

  JSL Sprite_CheckTileCollision
  LDA.w $0E70, X : BEQ .no_collision
    LDA.w SprMiscC,X : EOR.b #$01 : STA.w SprMiscC,X
    BRA .exit
  .no_collision
  RTS

  .octorok_used_barrage
  STZ.w SprXSpeed, X : STZ.w SprYSpeed,X
  LDA.w SprTimerA, X : BNE Octorock_ShootEmUp
    INC.w SprMiscF, X
    LDA.w SprMiscC, X
    PHA
    JSL GetRandomInt : AND.b #$3F : ADC.b #$30 : STA.w SprTimerA, X
    AND.b #$03 : STA.w SprMiscC, X
    PLA
    CMP.w SprMiscC, X : BEQ .exit
      EOR.w SprMiscC, X : BNE .exit
        LDA.b #$08 : STA.w SprTimerB,X
  .exit
  RTS

  .direction
    db   3,   2,   0,   1

  .speed_x
    db  24, -24,   0,   0

  .speed_y
    db   0,   0,  24, -24

  .timer
    db  60, 128, 160, 128
}
```

## Octorok Projectile Logic (`Octorock_ShootEmUp`)
This routine determines the Octorok's shooting behavior, allowing for both single-shot and four-way attacks.

```asm
Octorock_ShootEmUp:
{
  ; Use SprMiscD as a flag to shoot 4 ways for awhile before going back to single shot

  LDA.w SprMiscD, X : BEQ .continue
    LDA.w SprTimerD, X : BNE .four_ways
      LDA.b #$01 : STA.w SprMiscD, X
  .continue
  JSL GetRandomInt : AND.b #$1F : BNE .single_shot
  .four_ways
    LDA.b #$01 : STA.w SprMiscD, X
    LDA.b #$20 : STA.w SprTimerD, X
    JSR Octorok_Shoot4Ways
    RTS
  .single_shot
  JSR Octorok_ShootSingle
  RTS
}
```

## Water Octorok Main Logic (`Sprite_WaterOctorok_Main`)
This routine governs the behavior of a water-based Octorok, including its attack patterns and states.

*   **Attack**: Calls `Sprite_WaterOctorok_Attack`.
*   **Facing Directions**: Uses a jump table to manage animations for facing different directions (Down, Up, Left, Right) and a hidden state.

```asm
Sprite_WaterOctorok_Main:
{
  JSR Sprite_WaterOctorok_Attack

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaterOctorok_FaceDown
  dw WaterOctorok_FaceUp
  dw WaterOctorok_FaceLeft
  dw WaterOctorok_FaceRight
  dw WaterOctorok_FaceHidden

  WaterOctorok_FaceDown:
  {
    %PlayAnimation(0,1,10)
    RTS
  }

  WaterOctorok_FaceUp:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,10)
    RTS
  }

  WaterOctorok_FaceLeft:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,10)
    RTS
  }

  WaterOctorok_FaceRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6,7,10)
    RTS
  }

  WaterOctorok_FaceHidden:
  {
    %StartOnFrame(8)
    %PlayAnimation(8,8,10)
    RTS
  }
}
```

## Water Octorok Attack Logic (`Sprite_WaterOctorok_Attack`)
This routine manages the Water Octorok's attack states, including hiding, emerging, attacking, and re-hiding.

*   **States**: Uses `SprMiscG, X` as a state machine for `WaterOctorok_Hidden`, `WaterOctorok_PoppingUp`, `WaterOctorok_Attacking`, and `WaterOctorok_Hiding`.
*   **`WaterOctorok_Hidden`**: Remains hidden until Link is within a certain distance, then transitions to `WaterOctorok_PoppingUp`.
*   **`WaterOctorok_PoppingUp`**: Emerges from the water, faces Link, and then transitions to `WaterOctorok_Attacking`.
*   **`WaterOctorok_Attacking`**: Shoots a single projectile (`Octorok_ShootSingle`) after a timer, then transitions to `WaterOctorok_Hiding`.
*   **`WaterOctorok_Hiding`**: Hides back in the water and transitions to `WaterOctorok_Hidden`.

```asm
Sprite_WaterOctorok_Attack:
{
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckDamageToPlayer

  LDA.w SprMiscG, X
  JSL JumpTableLocal

  dw WaterOctorok_Hidden
  dw WaterOctorok_PoppingUp
  dw WaterOctorok_Attacking
  dw WaterOctorok_Hiding

  WaterOctorok_Hidden:
  {
    LDA.w SprTimerA, X : BEQ +
      RTS
    +

    JSL GetDistance8bit_Long
    CMP.b #$40 : BCC .not_close_enough ; LD < 64
      INC.w SprMiscG, X
      %SetTimerA($10)
    .not_close_enough
    RTS
  }

   WaterOctorok_PoppingUp:
   {
     JSL Sprite_CheckDamageFromPlayer
     LDA.w SprTimerA, X : BNE +
       INC.w SprMiscG, X
       %SetTimerA($20)
       JSL Sprite_DirectionToFacePlayer
       ; LDA.w SprMiscC, X : AND.b #$03 : TAY
       ; LDA.w Sprite_Octorok_Move_direction, Y : STA.w SprAction, X
     +
     RTS
   }

   WaterOctorok_Attacking:
   {
     JSL Sprite_CheckDamageFromPlayer
     LDA.w SprTimerA, X : BNE +
       INC.w SprMiscG, X
       %SetTimerA($10)
       RTS
     +
     JSR Octorok_ShootSingle
     RTS
   }

   WaterOctorok_Hiding:
   {
     LDA.w SprTimerA, X : BNE +
       LDA.b #$04 : STA.w SprAction, X
       STZ.w SprMiscG, X
       %SetTimerA($40)
     +
     RTS
   }
}
```

## Projectile Spawning (`Octorok_ShootSingle`, `Octorok_Shoot4Ways`, `Octorok_SpawnRock`)
These routines handle the spawning and animation of Octorok projectiles.

*   **`Octorok_ShootSingle`**: Manages the animation and timing for shooting a single rock projectile.
*   **`Octorok_Shoot4Ways`**: Manages the animation, timing, and direction changes for shooting rock projectiles in four cardinal directions.
*   **`Octorok_SpawnRock`**: Spawns a rock projectile (sprite ID `$0C`) with specific initial offsets and speeds based on the Octorok's current direction.

```asm
Octorok_ShootSingle:
{
  LDA.w SprTimerA, X : CMP.b #$1C : BNE .bide_time
    PHA
    JSR Octorok_SpawnRock
    PLA
  .bide_time
  LSR #3
  TAY
  LDA.w .mouth_anim_step, Y : STA.w SprMiscB, X
  RTS

  .mouth_anim_step
    db $00, $02, $02, $02
    db $01, $01, $01, $00
    db $00, $00, $00, $00
    db $02, $02, $02, $02
    db $02, $01, $01, $00
}

Octorok_Shoot4Ways:
{
  LDA.w SprTimerA, X
  PHA
  CMP.b #$80 : BCS .animate
    AND.b #$0F : BNE .delay_turn
    PHA
    LDY.w SprMiscC, X
    LDA.w .next_direction, Y : STA.w SprMiscC, X
    PLA
    .delay_turn
    CMP.b #$08 : BNE .animate
      JSR Octorok_SpawnRock
  .animate
  PLA
  LSR #4
  TAY
  LDA.w .mouth_anim_step, Y : STA.w SprMiscB, X
  RTS

  .next_direction
    db $02, $03, $01, $00

  .mouth_anim_step
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $01, $00
}

Octorok_SpawnRock:
{
  LDA.b #$07 : JSL SpriteSFX_QueueSFX2WithPan
  LDA.b #$0C : JSL Sprite_SpawnDynamically : BMI .fired_a_blank
    PHX

    LDA.w SprMiscC,X
    TAX

    LDA.b $00 : CLC : ADC.w .offset_x_low,X : STA.w SprX,Y
    LDA.b $01 : ADC.w .offset_x_high,X : STA.w SprXH,Y
    LDA.b $02 : CLC : ADC.w .offset_y_low,X : STA.w SprY,Y
    LDA.b $03 : ADC.w .offset_y_high,X : STA.w SprYH,Y

    LDA.w SprMiscC,Y
    TAX

    LDA.w .rock_speed_x,X : STA.w SprXSpeed,Y
    LDA.w .rock_speed_y,X : STA.w SprYSpeed,Y

    PLX
  .fired_a_blank
  RTS

  .offset_x_low
    db  12, -12,   0,   0

  .offset_x_high
    db   0,  -1,   0,   0

  .offset_y_low
    db   4,   4,  12, -12

  .offset_y_high
    db   0,   0,   0,  -1

  .rock_speed_x
    db  44, -44,   0,   0

  .rock_speed_y
    db   0,   0,  44, -44
}
```

## Drawing (`Sprite_Octorok_Draw`)
The drawing routine handles OAM allocation, animation, and palette adjustments. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations.

```asm
Sprite_Octorok_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash : STA $08

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =========================================================

  .start_index
  db $00, $01, $02, $03, $04, $05, $06, $07, $08
  .nbr_of_tiles
  db 0, 0, 0, 0, 0, 0, 0, 0, 0
  .chr
  db $80
  db $80
  db $82
  db $82
  db $A0
  db $A2
  db $A0
  db $A2
  db $AA ; Water Octorok
  .properties
  db $0D
  db $4D
  db $0D
  db $4D
  db $0D
  db $0D
  db $4D
  db $4D
  db $3D ; Water Octorok
}
```

## Design Patterns
*   **Subtype-based Behavior**: The Octorok utilizes `SprSubtype` to implement distinct behaviors for Land and Water Octoroks, including different main logic routines and conditional drawing (shadow vs. water ripple).
*   **Dynamic Transformation**: A Land Octorok can dynamically transform into a Water Octorok if it moves onto a water tile, showcasing a unique environmental interaction.
*   **Complex State Machines**: Both Land and Water Octoroks employ intricate state machines to manage their movement, attack patterns, and emerging/hiding behaviors, making them engaging enemies.
*   **Projectile Attacks**: The Octorok can perform both single-shot and four-way projectile attacks, adding variety to its offensive capabilities.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering and positioning.
