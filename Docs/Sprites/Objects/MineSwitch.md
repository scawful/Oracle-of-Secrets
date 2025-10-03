# Mine Switch

## Overview
The Mine Switch sprite (`!SPRID = Sprite_Mineswitch`) is an interactive puzzle element, typically found in the Goron Mines. It functions as a lever-style switch that Link can activate by attacking it, altering the state of minecart tracks or other game elements. This sprite supports both a regular on/off switch and a speed-controlling switch, with its behavior and appearance changing based on its current state.

## Sprite Properties
*   **`!SPRID`**: `Sprite_Mineswitch` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `02`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `01`
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
*   **`!CanFall`**: `01`
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

## Main Structure (`Sprite_LeverSwitch_Long`)
This routine handles the Mine Switch's drawing and dispatches to its main logic if the sprite is active.

```asm
Sprite_LeverSwitch_Long:
{
  PHB : PHK : PLB
  JSR Sprite_LeverSwitch_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_LeverSwitch_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_LeverSwitch_Prep`)
This routine initializes the Mine Switch upon spawning. It sets `SprDefl, X` to `0`. It retrieves the switch's on/off state from `SwitchRam`, indexed by `SprSubtype, X`, and sets `SprAction, X` and `SprFrame, X` accordingly. It also sets `SprTileDie, X` to `0` and `SprBulletproof, X` to `0`.

```asm
Sprite_LeverSwitch_Prep:
{
  PHB : PHK : PLB

  LDA.b #$00 : STA.w SprDefl, X

  ; Get the subtype of the switch so that we can get its on/off state.
  LDA.w SprSubtype, X : TAY

  LDA.w SwitchRam, Y : STA.w SprAction, X : STA.w SprFrame, X
  LDA.b #$00 : STA.w SprTileDie, X
  STZ.w SprBulletproof, X

  PLB
  RTL
}
```

## Constants
*   **`SwitchRam = $0230`**: A WRAM address that stores the state (on/off) of each individual switch, indexed by its `SprSubtype`.

## Main Logic & State Machine (`Sprite_LeverSwitch_Main`)
This routine manages the Mine Switch's behavior through a jump table, supporting different types of switches:

*   **Player Collision**: Prevents Link from passing through the switch (`JSL Sprite_PlayerCantPassThrough`).
*   **`SwitchOff`**: Plays an animation. If Link attacks it (`JSL Sprite_CheckDamageFromPlayer`) and a timer (`SprTimerA, X`) allows, it plays a sound (`$25`), turns the switch on (`STA.w SwitchRam, Y` to `01`), sets a timer, and transitions to `SwitchOn`.
*   **`SwitchOn`**: Plays an animation. If Link attacks it and a timer allows, it plays a sound (`$25`), turns the switch off (`STA.w SwitchRam, Y` to `00`), sets a timer, and transitions to `SwitchOff`.
*   **`SpeedSwitchOff`**: Plays an animation. If Link attacks it, it plays a sound (`$25`), sets `$36` to `01` (likely a global speed flag for minecarts), and transitions to `SpeedSwitchOn`.
*   **`SpeedSwitchOn`**: Plays an animation. If Link attacks it, it plays a sound (`$25`), clears `$36`, and transitions to `SpeedSwitchOff`.

```asm
Sprite_LeverSwitch_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw SwitchOff
  dw SwitchOn
  dw SpeedSwitchOff
  dw SpeedSwitchOn

  SwitchOff:
  {
    %PlayAnimation(0,0,4)
    LDA.w SprTimerA, X : BNE .NoDamage
      JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
        LDA #$25 : STA $012F

        ; Get the subtype of the switch so that we can get its on/off state.
        LDA.w SprSubtype, X : TAY

        ; Turn the switch on.
        LDA #$01 : STA.w SwitchRam, Y
        LDA #$10 : STA.w SprTimerA, X
        %GotoAction(1)
    .NoDamage
    RTS
  }

  SwitchOn:
  {
    %PlayAnimation(1,1,4)
    LDA.w SprTimerA, X : BNE .NoDamage
      JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
        LDA #$25 : STA $012F

        ; Get the subtype of the switch so that we can get its on/off state.
        LDA.w SprSubtype, X : TAY
        
        ; Turn the switch off.
        LDA #$00 : STA.w SwitchRam, Y
        LDA #$10 : STA.w SprTimerA, X
        %GotoAction(0)
    .NoDamage
    RTS
  }

  SpeedSwitchOff:
  {
    %PlayAnimation(0,0,4)
    JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
      LDA.b #$25 : STA $012F
      LDA.b #$01 : STA $36
      %GotoAction(3)
    .NoDamage
    RTS
  }

  SpeedSwitchOn:
  {
    %PlayAnimation(1,1,4)
    JSL Sprite_CheckDamageFromPlayer : BCC .NoDamage
      LDA #$25 : STA $012F
      STZ.w $36
      %GotoAction(2)
    .NoDamage
    RTS
  }
}
```

## Drawing (`Sprite_LeverSwitch_Draw`)
This routine handles OAM allocation and animation for the Mine Switch. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations, ensuring accurate sprite rendering.

## Design Patterns
*   **Interactive Puzzle Element**: The Mine Switch is a key interactive puzzle element that Link can activate by attacking it, triggering changes in the game environment.
*   **State-Based Behavior**: The switch has distinct "on" and "off" states, with different animations and effects, providing clear visual feedback to the player.
*   **Subtype-Driven State**: The `SprSubtype` is used to index into `SwitchRam`, allowing each individual switch to maintain its own independent state, enabling complex puzzle designs with multiple switches.
*   **Speed Control**: The "Speed Switch" variant directly controls a global speed flag (`$36`), likely affecting the speed of minecarts or other moving objects, adding another layer of interaction to the minecart system.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
