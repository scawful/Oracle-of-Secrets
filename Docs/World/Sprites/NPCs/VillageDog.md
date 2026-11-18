# Village Dog / Eon Dog

## Overview
The `village_dog.asm` file defines the behavior for two distinct dog NPCs: the "Village Dog" and the "Eon Dog." Their appearance and behavior are dynamically determined by the global `WORLDFLAG`. These dogs exhibit random movement, react to Link's proximity, can be lifted and thrown, and offer context-sensitive dialogue based on Link's current form.

## Sprite Properties
*   **`!SPRID`**: `Sprite_VillageDog` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `05` (up to 4 body OAM tiles + 1 shadow tile)
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
This routine initializes the dog upon spawning. If it's an Eon Dog (`WORLDFLAG` is not `0`), it sets `SprAction, X` to `$07` and `SprTimerA, X` to `$40`. In the Village (`WORLDFLAG == 0`), it staggers each dog's initial idle pose/timer (`SprMiscD, X`, `SprTimerD, X`) and rolls outdoor Overworld (`$1B == 0`) stray coat variation via `SprMiscG, X` (`$08` = OAM Palette 7 golden-cream coat, overridden whenever `SprSubtype, X != 0` by `RichardDog_PaletteMask`).

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

## `LiftOrTalk` & `VillageDog_FormInteractLong` (`Sprites/NPCs/village_animals.asm`)
This routine determines whether Link can lift the dog or engage in dialogue. It checks Link's current form (`$02B2`):
*   **Human (`$00`) / other non-animal forms**: Calls `JSL Sprite_CheckIfLifted` so Link can pick the dog up (`Dog_Tossed` owns `ThrownSprite_TileAndSpriteInteraction_long` once airborne so grounded hops in `SprHeight` never trigger false throw physics).
*   **Wolf (`$03`)**: In `Dog_Handler`, approaching within `40px` (`$28`) triggers an immediate friendly pack tail-wag (`Action $05/$06`); pressing `A` while facing calls `VillageDog_FormInteractLong`, showing `!Dog_MsgWolf` (`!RichardDog_MsgWolf` when `SprSubtype != 0`).
*   **Minish (`$05`)**: In `Dog_MoveCommon`, approaches gently at speed `$08` and stops wider (`$18` = `24px`); pressing `A` while facing shows `!Dog_MsgMinish`.

`Sprites/NPCs/village_animals.asm` also hosts the companion multi-form hooks for Wayward Village Cuccos (`$0B` via `$06:F244`) and peaceful indoor Wayward Village Rats (`$6D` via `$05:A8CE`, scoped to rooms `$0102`, `$0103`, `$0104`, `$0106`, `$0107`, `$0119`, `$011F` when `$1B != 0` and `$0FFF == 0`, preserving dungeon/cave rats untouched).

## Main Logic & State Machine (`Sprite_VillageDog_Main`)
This routine manages the various states and behaviors of both Village Dogs and Eon Dogs.

*   **`Dog_Handler` (`00`)**: Calm idle state driven by `SprMiscD` (sit, head-tilt left/right, or short gentle stroll stopped on tile collision). When resting cooldown `SprTimerC == 0` and Link approaches within `88px` (`Dog_NearPlayer`), hops (`SprHeight = 4`) and perks up into `Dog_LookLeftAtLink` (`01`) or `Dog_LookRightAtLink` (`02`) chosen by `Sprite_IsToRightOfPlayer`. Calls `LiftOrTalk`.
*   **`Dog_LookLeftAtLink` / `Dog_LookRightAtLink` (`01`/`02`)**: Hold look pose (`SprFrame = 9/10`), allow `LiftOrTalk`, then transition into `Dog_MoveLeftTowardsLink` (`03`) / `Dog_MoveRightTowardsLink` (`04`).
*   **`Dog_MoveLeftTowardsLink` / `Dog_MoveRightTowardsLink` (`03`/`04`)**: Trot at speed `$0C` toward Link while dynamically flipping `03 <-> 04` from `SprXSpeed` sign so circling Link never causes moonwalking. Enters `Dog_WagTailLeft`/`Right` (`05`/`06`) within `22px` or settles back to calm `00` with `SprTimerC` rest cooldown on collision/timeout.
*   **`Dog_WagTailLeft` / `Dog_WagTailRight` (`05`/`06`)**: Wag tail via `Dog_PlayAnim`, continuously re-orienting toward Link via `Sprite_IsToRightOfPlayer`, allowing `LiftOrTalk`, then settling into calm idle with `SprTimerC` cooldown.
*   **`EonDog_Handler` / `EonDog_Right` (`07`/`08`)**: Specific to the Eon Dog (`WORLDFLAG != 0`), calling `EonDog_Walk`.
*   **`Dog_Tossed` (`09`)**: Airborne throw arc via `ThrownSprite_TileAndSpriteInteraction_long`; on landing, settles into `Dog_WagTailLeft` (`05`) or `Dog_WagTailRight` (`06`) based on Link's relative X position.
*   **`Dog_HappyDance` (`0A`)**: Triggered for grounded Village Dogs (`SprAction < 7`) in Overworld mode `$09` within `96px` on a fresh Ocarina song cast (`$03F0 == $80`, `$3A & $40 != 0`, non-Wolf `$02B2 != $03`, leaving `SongFlag` and `SprTimerF` untouched). Plays fast tail-wag frames facing Link with a triangle-wave hop in `SprHeight` via `SprMiscF`, then rests via `SprTimerC`.

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

## `Dog_NearPlayer` & `Dog_PlayAnim`
*   **`Dog_NearPlayer` & `VillageDog_CalmIdleLong`**: Shared 16-bit box proximity check (`|Link - SprCached| < A` on both axes) in Bank `$31`, used for the Ocarina radius (`$60`), idle perk-up (`$58`), and approach-to-wag stop (`$16`). The cold calm-idle/stroll routine (`VillageDog_CalmIdleLong`) emits into the Bank `$2C` tail via `%VillageDog_EmitBank2C()` in `Sprites/all_sprites.asm` to balance Bank `$31` and Bank `$2C` headroom.
*   **`Dog_PlayAnim`**: Shared 8-slot animation helper (`SprTimerB, X`), clamping `SprFrame` into `[start, end]` immediately on Left/Right transitions.

## Form Dialogue Dispatch (`VillageDog_FormInteractLong`)
Replaces the former Bank `$31` `ShowMessageIfMinish` tail and lives in `Sprites/NPCs/village_animals.asm` (Bank `$2B`). Uses `Animal_SolicitedTalk` so Minish Link (`$02B2 == $05`), Wolf Link (`$02B2 == $03`, distinguishing stray dogs vs Richard `SprSubtype != 0`), Cuccos (`$0B`), and indoor Library Rats (`$6D`) each route cleanly through placeholder message IDs (`!Dog_MsgMinish`, `!Dog_MsgWolf`, `!RichardDog_MsgWolf`, `!Cucco_MsgMinish`, `!Cucco_MsgWolf`, `!Rat_MsgMinish`, `!Rat_MsgWolf`).

## Drawing (`Sprite_VillageDog_Draw` and `Sprite_EonDog_Draw`)
Both drawing routines handle OAM allocation and animation for their respective dog types. They explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations. Each routine contains its own specific OAM data for rendering the character.

## Design Patterns
*   **Multi-Character NPC (Conditional Drawing/Logic)**: A single sprite definition (`Sprite_VillageDog`) is used to represent two distinct dog characters (Village Dog and Eon Dog) based on `WORLDFLAG`, showcasing efficient resource utilization and varied visual appearances.
*   **Random Movement**: The dogs exhibit random movement patterns, contributing to the environmental ambiance and making their movements less predictable.
*   **Player Interaction**: The dogs can be lifted and thrown (`LiftOrTalk`), and they react to Link's presence by looking at him and wagging their tails, adding to the interactive elements of the game world.
*   **Conditional Dialogue**: The `ShowMessageIfMinish` routine provides context-sensitive dialogue based on Link's current form, enhancing the narrative and player experience.
*   **Player Collision**: Implements `Sprite_PlayerCantPassThrough` to make the dogs solid objects that Link cannot walk through.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
