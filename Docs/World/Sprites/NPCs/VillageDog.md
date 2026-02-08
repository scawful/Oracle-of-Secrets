# Village Dog / Eon Dog

## Overview
The `village_dog.asm` file defines the behavior for two distinct dog NPCs: the "Village Dog" and the "Eon Dog." Their appearance and behavior are dynamically determined by the global `WORLDFLAG`. These dogs exhibit random movement, react to Link's proximity, can be lifted and thrown, and offer context-sensitive dialogue based on Link's current form.

## Sprite Properties
*   **`!SPRID`**: `Sprite_VillageDog` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `08`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `01`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `09`
*   **`!Persist`**: `01` (Continues to live off-screen)
*   **`!Statis`**: `00`
*   **`!CollisionLayer`**: `01` (Checks both layers for collision)
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

## Main Structure (`Sprite_VillageDog_Long`)
This routine acts as a dispatcher for drawing, selecting `Sprite_VillageDog_Draw` for the Village Dog (`WORLDFLAG = 0`) or `Sprite_EonDog_Draw` for the Eon Dog. It also handles shadow drawing and dispatches to the main logic if the sprite is active.

```asm
Sprite_VillageDog_Long:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ .village
    JSR Sprite_EonDog_Draw
    JMP +
  .village
  JSR Sprite_VillageDog_Draw
  +
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_VillageDog_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_VillageDog_Prep`)
This routine initializes the dog upon spawning. If it's an Eon Dog (`WORLDFLAG` is not `0`), it sets `SprAction, X` to `$07` and `SprTimerA, X` to `$40`.

```asm
Sprite_VillageDog_Prep:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ .village
    LDA.b #$07 : STA.w SprAction, X
    LDA.b #$40 : STA.w SprTimerA, X
  .village
  PLB
  RTL
}
```

## `HandleTossedDog`
This routine manages the vertical movement of a dog that has been tossed. If `SprHeight, X` is not `0`, it decrements it, simulating gravity.

## `LiftOrTalk`
This routine determines whether Link can lift the dog or engage in dialogue. It checks Link's current form (`$02B2`). If Link is in Wolf or Minish form, it calls `ShowMessageIfMinish`. Otherwise, it checks if the dog is lifted (`JSL Sprite_CheckIfLifted`) and handles interactions with thrown sprites (`JSL ThrownSprite_TileAndSpriteInteraction_long`).

## Main Logic & State Machine (`Sprite_VillageDog_Main`)
This routine manages the various states and behaviors of both Village Dogs and Eon Dogs.

*   **`Dog_Handler`**: Plays a sitting animation, calls `HandleTossedDog`, and if Link is nearby, sets a timer and transitions to `Dog_LookLeftAtLink` or `Dog_LookRightAtLink`. It also calls `LiftOrTalk`.
*   **`Dog_LookLeftAtLink` / `Dog_LookRightAtLink`**: Plays an animation of the dog looking towards Link. After a timer, it transitions to `Dog_MoveLeftTowardsLink` or `Dog_MoveRightTowardsLink`.
*   **`Dog_MoveLeftTowardsLink` / `Dog_MoveRightTowardsLink`**: Plays a walking animation, calls `HandleTossedDog`, and if Link is nearby, transitions to `Dog_WagTailLeft` or `Dog_WagTailRight`. It handles tile collisions, applies speed towards Link, and calls `LiftOrTalk`. After a timer, it returns to `Dog_Handler`.
*   **`Dog_WagTailLeft` / `Dog_WagTailRight`**: Plays a wagging tail animation, calls `LiftOrTalk` and `HandleTossedDog`. After a timer, it returns to `Dog_Handler`.
*   **`EonDog_Handler` / `EonDog_Right`**: These states are specific to the Eon Dog, playing animations and calling `EonDog_Walk`.

```asm
Sprite_VillageDog_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw Dog_Handler              ; 00
  dw Dog_LookLeftAtLink       ; 01
  dw Dog_LookRightAtLink      ; 02
  dw Dog_MoveLeftTowardsLink  ; 03
  dw Dog_MoveRightTowardsLink ; 04
  dw Dog_WagTailLeft          ; 05
  dw Dog_WagTailRight         ; 06

  dw EonDog_Handler           ; 07
  dw EonDog_Right             ; 08

  ; 0
  Dog_Handler:
  {
    %PlayAnimation(8,8,8) ; Sitting
    JSR HandleTossedDog
    LDA $0309 : AND #$03 : BNE .lifting
      LDA #$20 : STA.w SprTimerD, X
      JSL Sprite_IsToRightOfPlayer : TYA : BEQ .walk_right
        %GotoAction(1)
        JMP .lifting
      .walk_right
      %GotoAction(2)
      .lifting
      JSR LiftOrTalk
    JSL Sprite_Move
    RTS
  }

  ; 01
  Dog_LookLeftAtLink:
  {
    %PlayAnimation(9,9,8)
    JSR HandleTossedDog
    LDA.w SprTimerD, X : BNE +
      ; Load the timer for the run
      LDA.b #$60 : STA.w SprTimerD, X
      %GotoAction(3)
    +
    RTS
  }

  ; 02
  Dog_LookRightAtLink:
  {
    %PlayAnimation(10,10,8)
    JSR HandleTossedDog
    LDA.w SprTimerD, X : BNE +
      ; Load the timer for the run
      LDA.b #$60 : STA.w SprTimerD, X
      %GotoAction(4)
    +
    RTS
  }

  ; 03
  Dog_MoveLeftTowardsLink:
  {
    %PlayAnimation(2,4,6)
    JSR HandleTossedDog
    ; Check if the dog is near link, then wag the tail
    JSR CheckIfPlayerIsNearby : BCC +
      %GotoAction(5)
    +

    ; Check for collision
    JSL Sprite_CheckTileCollision
    LDA $0E70, X : BEQ .no_collision
      %GotoAction(0)
    .no_collision

    LDA.b #$0A
    JSL Sprite_ApplySpeedTowardsPlayer
    STZ $06 : STZ $07
    JSL Sprite_MoveLong

    JSR LiftOrTalk

    LDA.w SprTimerD, X : BNE +
      %GotoAction(0)
    +
    RTS
  }

  ; 04
  Dog_MoveRightTowardsLink:
  {
    %PlayAnimation(5,7,6)
    JSR HandleTossedDog
    JSR CheckIfPlayerIsNearby : BCC +
      %GotoAction(6)
    +

    ; Check for collision
    JSL Sprite_CheckTileCollision
    LDA $0E70, X : BEQ .no_collision
      %GotoAction(0)
    .no_collision

    LDA.b #$0A
    JSL Sprite_ApplySpeedTowardsPlayer
    STZ $06 : STZ $07
    JSL Sprite_MoveLong
    JSR LiftOrTalk

    LDA.w SprTimerD, X : BNE ++
      %GotoAction(0)
    ++
    RTS
  }

  ; 05
  Dog_WagTailLeft:
  {
    %PlayAnimation(0,1, 8)
    JSR LiftOrTalk
    JSR HandleTossedDog
    LDA.w SprTimerD, X : BNE +
      %GotoAction(0)
    +
    RTS
  }

  ; 06
  Dog_WagTailRight:
  {
    %PlayAnimation(11,12,8)
    JSR LiftOrTalk
    JSR HandleTossedDog
    LDA.w SprTimerD, X : BNE +
      %GotoAction(0)
    +
    RTS
  }

  EonDog_Handler:
  {
    %PlayAnimation(0,1,8)
    JSR EonDog_Walk
    RTS
  }

  EonDog_Right:
  {
    %PlayAnimation(2,3,8)
    JSR EonDog_Walk
    RTS
  }
}
```

## `EonDog_Walk`
This routine handles the Eon Dog's random movement. It moves the sprite (`JSL Sprite_MoveLong`), handles tile collision (`JSL Sprite_BounceFromTileCollision`), and after a timer, randomly selects a new direction and updates its speed and action.

## `CheckIfPlayerIsNearby`
This routine checks if Link is within a specific rectangular area around the dog, returning with the carry flag set if true.

## `ShowMessageIfMinish`
This routine displays a context-sensitive message based on Link's current form (`$02B2`). If Link is in Minish form, it displays message `$18`; otherwise, it displays message `$1B`.

## Drawing (`Sprite_VillageDog_Draw` and `Sprite_EonDog_Draw`)
Both drawing routines handle OAM allocation and animation for their respective dog types. They explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations. Each routine contains its own specific OAM data for rendering the character.

## Design Patterns
*   **Multi-Character NPC (Conditional Drawing/Logic)**: A single sprite definition (`Sprite_VillageDog`) is used to represent two distinct dog characters (Village Dog and Eon Dog) based on `WORLDFLAG`, showcasing efficient resource utilization and varied visual appearances.
*   **Random Movement**: The dogs exhibit random movement patterns, contributing to the environmental ambiance and making their movements less predictable.
*   **Player Interaction**: The dogs can be lifted and thrown (`LiftOrTalk`), and they react to Link's presence by looking at him and wagging their tails, adding to the interactive elements of the game world.
*   **Conditional Dialogue**: The `ShowMessageIfMinish` routine provides context-sensitive dialogue based on Link's current form, enhancing the narrative and player experience.
*   **Player Collision**: Implements `Sprite_PlayerCantPassThrough` to make the dogs solid objects that Link cannot walk through.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
