# Collectible Sprites (Pineapple, Seashell, Sword/Shield, Rock Sirloin)

## Overview
The Collectible sprite (`!SPRID = $52`) is a versatile implementation designed to represent various collectible items within the game, including Pineapples, Seashells, the starting Sword/Shield, and Rock Sirloin. Its specific appearance and behavior are dynamically determined by the `SprAction, X` state and the current `AreaIndex`, allowing for context-sensitive item placement and interaction.

## Sprite Properties
*   **`!SPRID`**: `$52` (Vanilla sprite ID, likely for a generic collectible)
*   **`!NbrTiles`**: `03`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
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

## Main Structure (`Sprite_Collectible_Long`)
This routine acts as a dispatcher for drawing, selecting the appropriate drawing routine based on the `AreaIndex`:

*   If `AreaIndex` is `$58` (Intro Sword area), it calls `Sprite_SwordShield_Draw`.
*   If `AreaIndex` is `$4B` (Lupo Mountain area), it calls `Sprite_RockSirloin_Draw`.
*   Otherwise, it calls `Sprite_Pineapple_Draw`.
*   It also handles shadow drawing and dispatches to the main logic if the sprite is active.

```asm
Sprite_Collectible_Long:
{
  PHB : PHK : PLB

  LDA.b $8A : CMP.b #$58 : BNE .not_intro_sword
    JSR Sprite_SwordShield_Draw
    BRA +
  .not_intro_sword
  LDA.b $8A : CMP.b #$4B : BNE .not_lupo_mountain
    JSR Sprite_RockSirloin_Draw
    BRA +
  .not_lupo_mountain
  JSR Sprite_Pineapple_Draw
  +
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive
  BCC .SpriteIsNotActive

  JSR Sprite_Collectible_Main

  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Collectible_Prep`)
This routine initializes the collectible sprite upon spawning, with conditional logic based on the `AreaIndex`:

*   **Intro Sword**: If `AreaIndex` is `$58`, it checks Link's Sword flag (`$7EF359`). If Link already has the Sword, the sprite despawns. It also sets `SprAction, X` to `$02` (SwordShield).
*   **Rock Sirloin**: If `AreaIndex` is `$4B`, it sets `SprAction, X` to `$03` (RockSirloin).

```asm
Sprite_Collectible_Prep:
{
  PHB : PHK : PLB

  ; Don't spawn the sword if we have it.
  LDA.b $8A : CMP.b #$58 : BNE .not_intro_sword
    LDA.l $7EF359 : BEQ +
      STZ.w SprState, X
    +
    LDA.b #$02 : STA.w SprAction, X
  .not_intro_sword
  LDA.b $8A : CMP.b #$4B : BNE .not_lupo_mountain
    LDA.b #$03 : STA.w SprAction, X
  .not_lupo_mountain

  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_Collectible_Main`)
This routine manages the behavior of various collectible items through a jump table based on `SprAction, X`:

*   **`Pineapple`**: Moves the sprite (`JSL Sprite_Move`). If Link touches it (`JSL Sprite_CheckDamageToPlayer`), it increments the `Pineapples` custom item count and despawns the sprite.
*   **`Seashell`**: Similar to Pineapple, but increments the `Seashells` custom item count.
*   **`SwordShield`**: Plays an animation, moves the sprite. If Link touches it, it grants Link the Sword (`LDY.b #$00`, `JSL Link_ReceiveItem`) and despawns the sprite.
*   **`RockSirloin`**: Moves the sprite. It checks Link's Glove flag (`$7EF354`). If Link has the Glove, it checks for player contact. If touched, it handles interaction with thrown sprites (`JSL ThrownSprite_TileAndSpriteInteraction_long`), increments the `RockMeat` custom item count, and despawns the sprite.

```asm
Sprite_Collectible_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw Pineapple
  dw Seashell
  dw SwordShield
  dw RockSirloin

  Pineapple:
  {
    JSL Sprite_Move
    JSL Sprite_CheckDamageToPlayer : BCC +
      LDA.l Pineapples : INC A : STA.l Pineapples
      STZ.w SprState, X
    +
    RTS
  }

  Seashell:
  {
    JSL Sprite_Move
    JSL Sprite_CheckDamageToPlayer : BCC +
      LDA.l Seashells : INC A : STA.l Seashells
      STZ.w SprState, X
    +
    RTS
  }

  SwordShield:
  {
    %PlayAnimation(0,0,1)
    JSL Sprite_Move
    JSL Sprite_CheckDamageToPlayer : BCC +
      LDY.b #$00 : STZ $02E9
      JSL Link_ReceiveItem
      STZ.w SprState, X
    +
    RTS
  }

  RockSirloin:
  {
    JSL Sprite_Move
    LDA.l $7EF354 : BEQ .do_you_even_lift_bro
      JSL Sprite_CheckDamageToPlayer : BCC +
        JSL ThrownSprite_TileAndSpriteInteraction_long
        LDA.l RockMeat : INC A : STA.l RockMeat
        STZ.w SprState, X
    +
    .do_you_even_lift_bro
    RTS
  }

}
```

## Drawing (`Sprite_Pineapple_Draw`, `Sprite_SwordShield_Draw`, `Sprite_RockSirloin_Draw`)
Each collectible type has its own dedicated drawing routine. These routines handle OAM allocation and animation, and explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations. Each routine contains its own specific OAM data for rendering the respective item.

## Design Patterns
*   **Multi-Item Collectible**: A single sprite definition (`!SPRID = $52`) is used to represent multiple distinct collectible items, with their specific appearance and behavior determined by `SprAction, X` and `AreaIndex`. This allows for efficient reuse of sprite slots for various in-game items.
*   **Context-Sensitive Spawning/Drawing**: The sprite's initial appearance and drawing routine are dynamically selected based on the `AreaIndex`, enabling specific items to appear in designated locations within the game world.
*   **Item Granting**: Collectibles grant items to Link upon contact, directly influencing his inventory and progression.
*   **Quest Progression Integration**: The Sword/Shield collectible despawns if Link already possesses the Sword, and the Rock Sirloin requires Link to have the Glove to interact with it, integrating these items into the game's quest and progression systems.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
