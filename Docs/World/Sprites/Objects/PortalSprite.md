# Portal Sprite

## Overview
The Portal sprite (`!SPRID = Sprite_Portal`) implements a sophisticated two-way warping system within the game. It allows Link to instantly travel between designated Blue and Orange portals, which can be placed in both dungeons and the overworld. This sprite features complex logic for portal activation, collision detection with Link, and seamless management of Link's state during warps.

## Sprite Properties
*   **`!SPRID`**: `Sprite_Portal` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `01`
*   **`!Harmless`**: `00`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `00`
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

## Main Structure (`Sprite_Portal_Long`)
This routine handles the Portal's drawing and dispatches to its main logic if the sprite is active.

```asm
Sprite_Portal_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Portal_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Portal_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Portal_Prep`)
This routine initializes the Portal upon spawning. It sets `SprDefl, X` to `0` (ensuring persistence outside the camera view), modifies `SprHitbox, X` properties, sets `SprTileDie, X` to `0`, and makes the portal bulletproof (`SprBulletproof, X` to `$FF`).

```asm
Sprite_Portal_Prep:
{
  PHB : PHK : PLB
  ; Persist outside of camera
  LDA #$00 : STA.w SprDefl, X
  LDA.w SprHitbox, X : AND.b #$C0 : STA.w SprHitbox, X
  STZ.w SprTileDie, X
  LDA.b #$FF : STA.w SprBulletproof, X
  PLB
  RTL
}
```

## Portal Data Memory Locations
*   **`BluePortal_X`, `BluePortal_Y`, `OrangePortal_X`, `OrangePortal_Y`**: WRAM addresses storing the X and Y coordinates of the Blue and Orange portals, respectively.
*   **`BlueActive`, `OrangeActive`**: Flags indicating whether the Blue and Orange portals are currently active.
*   **`OrangeSpriteIndex`, `BlueSpriteIndex`**: Store the sprite indices of the Orange and Blue portals.

## Main Logic & State Machine (`Sprite_Portal_Main`)
This routine manages the various states and behaviors of the portals, including their creation, activation, and warping functionality.

*   **`StateHandler`**: Calls `CheckForDismissPortal` and `RejectOnTileCollision`. It then checks `$7E0FA6` (likely a flag indicating which portal is being spawned). If `$7E0FA6` is `0`, it sets up an Orange Portal (stores coordinates, sets `SprSubtype, X` to `01`, and transitions to `OrangePortal`). Otherwise, it sets up a Blue Portal (stores coordinates, sets `SprSubtype, X` to `02`, and transitions to `BluePortal`).
*   **`BluePortal` / `OrangePortal`**: Plays an animation. It checks if Link has been warped (`$11` compared to `$2A`). It then checks for overlap with Link's hitbox (`CheckIfHitBoxesOverlap`). If Link overlaps, it determines if Link is in a dungeon or overworld (`$1B`) and transitions to the appropriate warp state (`BluePortal_WarpDungeon`, `OrangePortal_WarpDungeon`, `BluePortal_WarpOverworld`, `OrangePortal_WarpOverworld`).
*   **`BluePortal_WarpDungeon` / `OrangePortal_WarpDungeon`**: Warps Link's coordinates (`$20`, `$22`), sets camera scroll boundaries, stores the other portal's coordinates, sets its `SprTimerD, X`, sets `$11` to `$14`, and returns to the respective portal state.
*   **`BluePortal_WarpOverworld` / `OrangePortal_WarpOverworld`**: Warps Link's coordinates (`$20`, `$22`), sets camera scroll boundaries, applies Link's movement to the camera (`JSL ApplyLinksMovementToCamera`), stores the other portal's coordinates, sets its `SprTimerD, X`, sets `$5D` to `$01`, and returns to the respective portal state.

```asm
Sprite_Portal_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw StateHandler
  dw BluePortal
  dw OrangePortal

  dw BluePortal_WarpDungeon
  dw OrangePortal_WarpDungeon

  dw BluePortal_WarpOverworld
  dw OrangePortal_WarpOverworld

  StateHandler:
  {
    JSR CheckForDismissPortal
    JSR RejectOnTileCollision

    LDA $7E0FA6 : BNE .BluePortal
      LDA #$01 : STA $0307
      TXA : STA.w OrangeSpriteIndex
      LDA.w SprY, X : STA.w OrangePortal_X
      LDA.w SprX, X : STA.w OrangePortal_Y
      LDA.b #$01 : STA.w SprSubtype, X
      %GotoAction(2)
      RTS
    .BluePortal
    LDA #$02 : STA $0307
    TXA : STA.w BlueSpriteIndex
    LDA.w SprY, X : STA.w BluePortal_X
    LDA.w SprX, X : STA.w BluePortal_Y
    LDA.b #$02 : STA.w SprSubtype, X
    %GotoAction(1)
    RTS
  }

  BluePortal:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,1,8)

    LDA $11 : CMP.b #$2A : BNE .not_warped_yet
      STZ $11
    .not_warped_yet
    CLC

    LDA.w SprTimerD, X : BNE .NoOverlap
      JSL Link_SetupHitBox
      JSL $0683EA          ; Sprite_SetupHitbox_long
      JSL CheckIfHitBoxesOverlap : BCC .NoOverlap
      CLC
      LDA $1B : BEQ .outdoors
      %GotoAction(3) ; BluePortal_WarpDungeon
    .NoOverlap
    RTS

    .outdoors
    %GotoAction(5) ; BluePortal_WarpOverworld
    RTS
  }

  OrangePortal:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,8)
    LDA $11 : CMP.b #$2A : BNE .not_warped_yet
      STZ $11
    .not_warped_yet
    CLC
    LDA.w SprTimerD, X : BNE .NoOverlap
    JSL Link_SetupHitBox
    JSL $0683EA          ; Sprite_SetupHitbox_long

    JSL CheckIfHitBoxesOverlap : BCC .NoOverlap
    CLC
    ; JSL $01FF28 ; Player_CacheStatePriorToHandler

    LDA $1B : BEQ .outdoors
      %GotoAction(4) ; OrangePortal_WarpDungeon
      .NoOverlap
      RTS

    .outdoors
    %GotoAction(6) ; OrangePortal_WarpOverworld
    RTS
  }

  BluePortal_WarpDungeon:
  {
    LDA $7EC184 : STA $20
    LDA $7EC186 : STA $22

    LDA $7EC188 : STA $0600
    LDA $7EC18A : STA $0604
    LDA $7EC18C : STA $0608
    LDA $7EC18E : STA $060C

    PHX
    LDA.w OrangeSpriteIndex : TAX
    LDA #$40 : STA.w SprTimerD, X
    LDA.w SprY,                X : STA $7EC184
    STA.w BluePortal_Y
    LDA.w SprX,                X : STA $7EC186
    STA.w BluePortal_X
    PLX

    LDA #$14 : STA $11
    %GotoAction(1) ; Return to BluePortal
    RTS
  }

  OrangePortal_WarpDungeon:
  {
    LDA $7EC184 : STA $20
    LDA $7EC186 : STA $22

    ; Camera Scroll Boundaries
    LDA $7EC188 : STA $0600 ; Small Room North
    LDA $7EC18A : STA $0604 ; Small Room South
    LDA $7EC18C : STA $0608 ; Small Room West
    LDA $7EC18E : STA $060C ; Small Room South

    PHX
    LDA.w BlueSpriteIndex : TAX
    LDA #$40 : STA.w SprTimerD, X
    LDA.w SprY,                X : STA $7EC184
    STA.w OrangePortal_Y
    LDA.w SprX,                X : STA $7EC186
    STA.w OrangePortal_X
    PLX

    LDA #$14 : STA $11
    %GotoAction(2) ; Return to OrangePortal
    RTS
  }

  BluePortal_WarpOverworld:
  {
    LDA.w OrangePortal_X : STA $20
    LDA.w OrangePortal_Y : STA $22
    LDA $7EC190 : STA $0610
    LDA $7EC192 : STA $0612
    LDA $7EC194 : STA $0614
    LDA $7EC196 : STA $0616

    JSL ApplyLinksMovementToCamera

    PHX ; Infinite loop prevention protocol
    LDA.w OrangeSpriteIndex : TAX
    LDA #$40 : STA.w SprTimerD, X

    PLX
    LDA #$01 : STA $5D
    ;LDA #$2A : STA $11
    %GotoAction(1) ; Return to BluePortal
    RTS
  }

  OrangePortal_WarpOverworld:
  {
    LDA.w BluePortal_X : STA $20
    LDA.w BluePortal_Y : STA $22
    LDA $7EC190 : STA $0610
    LDA $7EC192 : STA $0612
    LDA $7EC194 : STA $0614
    LDA $7EC196 : STA $0616

    JSL ApplyLinksMovementToCamera

    PHX
    LDA.w BlueSpriteIndex : TAX
    LDA #$40 : STA.w SprTimerD, X
    PLX

    LDA #$01 : STA $5D
    ;LDA #$2A : STA $11

    %GotoAction(2) ; Return to BluePortal
    RTS
  }
}
```

## Helper Routines
*   **`CheckForDismissPortal`**: Checks a ticker (`$06FE`). If it exceeds `02`, it despawns the active portals (Blue and Orange) and decrements the ticker. Otherwise, it increments the ticker. This ticker needs to be reset during room and map transitions.
*   **`RejectOnTileCollision`**: Checks for tile collision. If a portal is placed on an invalid tile (tile attribute `0` or `48`), it despawns the portal, plays an error sound (`SFX2.3C`), and decrements the ticker (`$06FE`).

## Drawing (`Sprite_Portal_Draw`)
This routine handles OAM allocation and animation for the Portal. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

## Design Patterns
*   **Two-Way Warping System**: Implements a complex two-way portal system that allows Link to instantly travel between two designated points, enhancing exploration and puzzle design.
*   **Context-Sensitive Warping**: Portals can intelligently warp Link between dungeons and the overworld, adapting to the current game context and providing seamless transitions.
*   **Persistent Portal Locations**: Portal coordinates are stored in WRAM, allowing them to be placed and remembered across game sessions, enabling dynamic puzzle setups.
*   **Link State Management**: Modifies Link's coordinates, camera boundaries, and game mode during warps, ensuring a smooth and consistent player experience during transitions.
*   **Collision Detection**: Utilizes `CheckIfHitBoxesOverlap` to accurately detect when Link enters a portal, triggering the warp sequence.
*   **Error Handling**: Includes logic to dismiss portals if they are placed on invalid tiles, preventing game-breaking scenarios and providing feedback to the player.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
