# Deku Leaf / Whirlpool

## Overview
The `deku_leaf.asm` file defines a versatile sprite (`!SPRID = Sprite_DekuLeaf`) that can function as two distinct in-game objects: the "Deku Leaf" and a "Whirlpool." Its specific behavior and visual representation are dynamically determined by the current `AreaIndex`, allowing it to serve different purposes in various locations.

## Sprite Properties
*   **`!SPRID`**: `Sprite_DekuLeaf` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `00` (Graphics are handled externally or as a background)
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `$0D`
*   **`!Persist`**: `01` (Continues to live off-screen)
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

## Main Structure (`Sprite_DekuLeaf_Long`)
This routine acts as a dispatcher for drawing, selecting `Sprite_Whirlpool_Draw` if `AreaIndex` is `$3D` (Whirlpool area), and `Sprite_DekuLeaf_Draw` otherwise. It also dispatches to the main logic if the sprite is active.

```asm
Sprite_DekuLeaf_Long:
{
  PHB : PHK : PLB
  LDA $8A : CMP.b #$3D : BEQ .whirlpool
    JSR Sprite_DekuLeaf_Draw
    JMP +
  .whirlpool
  JSR Sprite_Whirlpool_Draw
  +
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_DekuLeaf_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_DekuLeaf_Prep`)
This routine initializes the sprite upon spawning. If `AreaIndex` is `$3D` (Whirlpool area), it sets `SprAction, X` to `$01` (`Whirlpool_Main`), indicating its role as a whirlpool.

```asm
Sprite_DekuLeaf_Prep:
{
  PHB : PHK : PLB
  LDA $8A : CMP.b #$3D : BNE .not_whirlpool
    LDA.b #$01 : STA.w SprAction, X
  .not_whirlpool
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_DekuLeaf_Main`)
This routine manages the behavior of both the Deku Leaf and the Whirlpool through a jump table based on `SprAction, X`:

*   **`WaitForPlayer` (Deku Leaf)**: Plays an idle animation. It checks if Link is on the leaf (`JSR CheckIfPlayerIsOn`). If so, it sets a flag (`$71`) and, if Link is in Minish form, spawns a poof garnish. Otherwise, it clears the flag.
*   **`Whirlpool_Main`**: Plays an animation. If Link is on the whirlpool and the underwater flag (`$0AAB`) is set, it resets various Link state flags (`$55`, `$0AAB`, `$0351`, `$037B`, `$02B2`). If Link's state is not `$0B` (Mirror), it saves Link's coordinates and sets `GameMode` to `$23` to initiate a warp, similar to the Mirror effect.

```asm
Sprite_DekuLeaf_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw WaitForPlayer
  dw Whirlpool_Main

  WaitForPlayer:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 0, 10)

    JSR CheckIfPlayerIsOn : BCC +
      LDA.b #$01 : STA.b $71
      LDA.w $02B2 : CMP.b #$01 : BNE ++
        JSL Sprite_SpawnPoofGarnish
      ++
      RTS
    +
    STZ.b $71
    RTS
  }

  Whirlpool_Main:
  {
    %PlayAnimation(0, 2, 10)
    JSR CheckIfPlayerIsOn : BCC .not_on

    LDA $0AAB : BEQ .not_on

      STZ $55    ; Reset cape flag
      STZ $0AAB  ; Reset underwater flag
      STZ $0351  ; Reset ripple flag
      STZ $037B  ; Reset invincibility flag
      STZ $02B2  ; Reset mask flag

      LDA.b $10 : CMP.b #$0B : BEQ .exit
        LDA.b $8A : AND.b #$40 : STA.b $7B : BEQ .no_mirror_portal
          LDA.b $20 : STA.w $1ADF
          LDA.b $21 : STA.w $1AEF
          LDA.b $22 : STA.w $1ABF
          LDA.b $23 : STA.w $1ACF
        .no_mirror_portal
        LDA.b #$23

        #SetGameModeLikeMirror:
        STA.b $11
        STZ.w $03F8
        LDA.b #$01 : STA.w $02DB
        STZ.b $B0
        STZ.b $27 : STZ.b $28
        LDA.b #$14 : STA.b $5D

    .not_on
    .exit
    RTS
  }
}
```

## Drawing (`Sprite_DekuLeaf_Draw` and `Sprite_Whirlpool_Draw`)
Each object type has its own dedicated drawing routine. These routines handle OAM allocation and animation, and explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations. Each routine contains its own specific OAM data for rendering the respective object.

## Design Patterns
*   **Multi-Object Sprite (Conditional Drawing/Logic)**: A single sprite definition (`Sprite_DekuLeaf`) is used to represent two distinct objects (Deku Leaf and Whirlpool) based on `AreaIndex`, showcasing efficient resource utilization and varied functionality.
*   **Context-Sensitive Behavior**: The sprite's behavior changes entirely based on the `AreaIndex`, allowing it to function as a traversal item (Deku Leaf) or a warp point (Whirlpool), adapting to different game contexts.
*   **Player Interaction**: The Deku Leaf allows Link to stand on it for traversal, while the Whirlpool provides a warp mechanism, both offering unique forms of player interaction.
*   **Game State Manipulation**: The Whirlpool modifies various Link state flags to initiate a warp, demonstrating direct control over the player's game state during transitions.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
