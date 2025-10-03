# Piratian

## Overview
The Piratian sprite (`!SPRID = $0E`) represents an NPC that initially behaves in a friendly manner, engaging Link through dialogue and moving randomly. However, it possesses an "aggro" system, becoming hostile and attacking Link if provoked. A unique aspect of this sprite is its dynamic health scaling, which adjusts based on Link's current Sword level.

## Sprite Properties
*   **`!SPRID`**: `$0E` (Vanilla sprite ID, likely for a generic NPC)
*   **`!NbrTiles`**: `02`
*   **`!Harmless`**: `00` (Initially harmful, but `Sprite_Piratian_Friendly` suggests otherwise)
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00` (Dynamically set in `_Prep`)
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
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

## Main Structure (`Sprite_Piratian_Long`)
This routine handles the Piratian's drawing, shadow rendering, and dispatches to its main logic if the sprite is active.

```asm
Sprite_Piratian_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Piratian_Draw
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Piratian_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Piratian_Prep`)
This routine initializes the Piratian upon spawning. Its health (`SprHealth, X`) is dynamically set based on Link's current Sword level (`$7EF359`), providing a form of difficulty scaling. `SprMiscA, X` is initialized to `0` (likely an aggro flag), and a specific bit of `SprNbrOAM, X` is set, potentially for drawing behavior.

```asm
Sprite_Piratian_Prep:
{
  PHB : PHK : PLB
  LDA.l $7EF359 : TAY
  LDA.w .health, Y : STA.w SprHealth, X
  STZ.w SprMiscA, X
  LDA.w SprNbrOAM, X : ORA.b #$80 : STA.w SprNbrOAM, X
  PLB
  RTL

  .health
    db $08, $0A, $0C, $0F
}
```

## Main Logic & State Machine (`Sprite_Piratian_Main`)
This routine orchestrates the Piratian's movement and animation, calling `Sprite_Piratian_Move` and then dispatching to various animation states based on `SprAction, X`.

*   **`Piratian_MoveDown` / `Up` / `Left` / `Right`**: Each state plays a specific walking animation.
*   **`SkullHead`**: Plays a specific animation, likely when the Piratian is defeated or in a particular state.

```asm
Sprite_Piratian_Main:
{
  JSR Sprite_Piratian_Move

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Piratian_MoveDown
  dw Piratian_MoveUp
  dw Piratian_MoveLeft
  dw Piratian_MoveRight
  dw SkullHead

  Piratian_MoveDown:
  {
    %PlayAnimation(0,1,16)
    RTS
  }

  Piratian_MoveUp:
  {
    %PlayAnimation(2,3,16)
    RTS
  }

  Piratian_MoveLeft:
  {
    %PlayAnimation(4,5,16)
    RTS
  }

  Piratian_MoveRight:
  {
    %PlayAnimation(6,7,16)
    RTS
  }

  SkullHead:
  {
    %PlayAnimation(8,9,16)
    RTS
  }
}
```

## Movement and Interaction (`Sprite_Piratian_Move`)
This routine handles the Piratian's movement, collision, damage reactions, and implements its "aggro" system.

*   **Random Movement**: If `SprTimerA, X` is `0`, the Piratian randomly selects a new direction (`Sprite_SelectNewDirection`) and updates its animation state (`SprAction, X`).
*   **Physics & Collision**: Moves the sprite (`JSL Sprite_MoveXyz`), handles tile collision (`JSL Sprite_BounceFromTileCollision`), damage flash (`JSL Sprite_DamageFlash_Long`), and interaction with thrown sprites (`JSL ThrownSprite_TileAndSpriteInteraction_long`).
*   **Aggro Logic**: If the Piratian takes damage from Link (`JSL Sprite_CheckDamageFromPlayer`), it sets `SprMiscA, X` to `01` (aggro flag), changes its drawing behavior (`SprNbrOAM, X`), sets timers, and begins to attack Link (`Sprite_ProjectSpeedTowardsPlayer`, `Sprite_CheckDamageToPlayer`).
*   **Friendly Behavior**: If not in an aggro state, it calls `Sprite_Piratian_Friendly` for dialogue interaction.

```asm
Sprite_Piratian_Move:
{
  LDA.w SprTimerA, X : BNE +
    JSL Sprite_SelectNewDirection
    TYA
    CMP.b #$03 : BCC ++
      SEC : SBC.b #$03
    ++
    STA.w SprAction, X
  +

  JSL Sprite_MoveXyz
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_DamageFlash_Long
  JSL ThrownSprite_TileAndSpriteInteraction_long

  JSL Sprite_CheckDamageFromPlayer : BCC .no_dano
    LDA.b #$01 : STA.w SprMiscA, X
    LDA.w SprNbrOAM, X : AND.b #$7F : STA.w SprNbrOAM, X
    %SetTimerA($60)
    %SetTimerF($20)
  .no_dano

  LDA.w SprMiscA, X : BEQ .no_aggro
    LDA.b #$10 : STA.w SprTimerA, X
    LDA.b #$08
    JSL Sprite_ProjectSpeedTowardsPlayer
    JSL Sprite_CheckDamageToPlayer
    JMP .return
  .no_aggro

  JSR Sprite_Piratian_Friendly
  .return
  RTS
}
```

## Friendly Interaction (`Sprite_Piratian_Friendly`)
This routine handles the Piratian's friendly dialogue. If `SprTimerD, X` is `0`, it displays a message on contact (`%ShowMessageOnContact($01BB)`). Upon message dismissal, it sets `SprTimerD, X` to `$FF`.

## Drawing (`Sprite_Piratian_Draw`)
The drawing routine uses the `%DrawSprite()` macro to render the Piratian's graphics based on defined OAM data tables.

## Design Patterns
*   **Dynamic Health Scaling**: The Piratian's health is dynamically adjusted based on Link's current Sword level, providing a form of adaptive difficulty.
*   **Aggro System**: The Piratian features an "aggro" system where it transitions from a friendly, dialogue-based NPC to a hostile enemy if Link attacks it, adding depth to interactions.
*   **Random Movement**: The Piratian moves randomly, contributing to its NPC-like behavior and making its movements less predictable.
*   **NPC Interaction**: The Piratian can be interacted with through dialogue when in its friendly state, offering context or hints.
*   **Conditional Behavior**: The sprite's behavior changes significantly based on its "friendly" or "aggro" state, demonstrating complex state management.
*   **16-bit OAM Calculations**: Although `%DrawSprite()` is used, the underlying drawing routines likely utilize `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
