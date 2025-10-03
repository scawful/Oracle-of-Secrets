# Goron

## Overview
The Goron sprite (`!SPRID = $F2`) is a versatile NPC implementation that can represent two distinct Goron characters: the "Kalyxo Goron" and the "Eon Goron." Their specific behaviors and appearances are determined by the global `WORLDFLAG` and the current `AreaIndex`. These Gorons primarily serve as interactive NPCs, engaging Link through dialogue and potentially triggering game events.

## Sprite Properties
*   **`!SPRID`**: `$F2` (Vanilla sprite ID, likely for a generic NPC)
*   **`!NbrTiles`**: `04`
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `00`
*   **`!Damage`**: `00`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `00`
*   **`!Hitbox`**: `02`
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

## Main Structure (`Sprite_Goron_Long`)
This routine acts as a dispatcher, selecting the appropriate drawing routine based on the `WORLDFLAG` (Kalyxo Goron if `0`, Eon Goron otherwise). It also handles shadow drawing and dispatches to the main logic if the sprite is active.

```asm
Sprite_Goron_Long:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ .kalyxo
    JSR Sprite_EonGoron_Draw
    JMP +
  .kalyxo
  JSR Sprite_KalyxoGoron_Draw
  +
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Goron_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Goron_Prep`)
This routine initializes the Goron upon spawning. It sets `SprDefl, X` to `$80`. The initial `SprAction, X` is determined by `WORLDFLAG` and `AreaIndex`. For Eon Gorons, it can randomly set their initial action to `EonGoron_Main`, `EonGoron_Sing`, or `EonGoron_Punch`. For Kalyxo Gorons, it checks a specific flag (`$7EF280, X`) to set their initial action to `KalyxoGoron_Main` or `KalyxoGoron_MinesOpened`.

```asm
Sprite_Goron_Prep:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BEQ +
    LDA.w AreaIndex : CMP.b #$55 : BNE .not_sing
      LDA.b #$04 : STA.w SprAction, X
    .not_sing
    JSL GetRandomInt : AND.b #$01 : BEQ .rand
      LDA.b #$05 : STA.w SprAction, X
      JMP ++
    .rand
    LDA.b #$03 : STA.w SprAction, X
    JMP ++
  +
  PHX
  LDX $8A
  LDA.l $7EF280, X : CMP.b #$20 : BEQ +++
    PLX
    STZ.w SprAction, X
  ++
  PLB
  RTL
  +++
  PLX
  LDA.b #$02 : STA.w SprAction, X
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_Goron_Main`)
This routine manages the various states and behaviors of both Kalyxo and Eon Gorons.

*   **Player Collision**: Prevents Link from passing through the Goron (`Sprite_PlayerCantPassThrough`).
*   **`KalyxoGoron_Main`**: Displays messages (`%ShowSolicitedMessage`) based on the `RockMeat` item count. Can transition to `KalyxoGoron_OpenMines` under certain conditions.
*   **`KalyxoGoron_OpenMines`**: Plays an animation, sets a flag (`$04C6`) to open mines, and transitions to `KalyxoGoron_MinesOpened`.
*   **`KalyxoGoron_MinesOpened`**: Plays an animation.
*   **`EonGoron_Main`**: Plays an animation and displays a message.
*   **`EonGoron_Sing`**: Plays a singing animation and displays a message.
*   **`EonGoron_Punch`**: Plays a punching animation and displays a message.

```asm
Sprite_Goron_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw KalyxoGoron_Main
  dw KalyxoGoron_OpenMines
  dw KalyxoGoron_MinesOpened
  dw EonGoron_Main
  dw EonGoron_Sing
  dw EonGoron_Punch

  KalyxoGoron_Main:
  {
    LDA.l RockMeat : BEQ +
                     CMP.b #$05 : BCC ++
                     %ShowSolicitedMessage($01A9) : BCC +++
                     INC.w SprAction, X
                     +++
                     RTS
    +
    %ShowSolicitedMessage($01A7)
    RTS
    ++
    %ShowSolicitedMessage($01A8)
    RTS
  }

  KalyxoGoron_OpenMines:
  {
    %PlayAnimation(1,1,10)
    LDA.b #$04 : STA $04C6
    INC.w SprAction, X
    RTS
  }

  KalyxoGoron_MinesOpened:
  {
    %PlayAnimation(1,1,10)
    RTS
  }

  EonGoron_Main:
  {
    %PlayAnimation(0, 1, 10)
    %ShowSolicitedMessage($01B0)
    RTS
  }

  EonGoron_Sing:
  {
    %PlayAnimation(2, 3, 10)
    %ShowSolicitedMessage($01B2)
    RTS
  }

  EonGoron_Punch:
  {
    %PlayAnimation(4, 5, 10)
    %ShowSolicitedMessage($01B1)
    RTS
  }
}
```

## Drawing (`Sprite_KalyxoGoron_Draw` and `Sprite_EonGoron_Draw`)
Both drawing routines handle OAM allocation and animation for their respective Goron types. They explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations.

## Design Patterns
*   **Multi-Character NPC (Conditional Drawing/Logic)**: A single sprite definition is used to represent two distinct Goron characters (Kalyxo and Eon) based on `WORLDFLAG`, demonstrating efficient resource utilization and context-sensitive character representation.
*   **Quest Progression Integration**: The Gorons' dialogue and actions are tied to game state (e.g., `RockMeat` item count, `AreaIndex`), indicating their role in advancing the narrative and triggering specific events like opening mines.
*   **Conditional Behavior**: Extensive use of conditional logic based on `WORLDFLAG` and `AreaIndex` allows for dynamic changes in the Goron's role, dialogue, and actions.
*   **NPC Interaction**: Provides rich interaction with the player through dialogue (`%ShowSolicitedMessage`) and can trigger game events.
*   **Player Collision**: Implements `Sprite_PlayerCantPassThrough` to make the NPC a solid object that Link cannot walk through.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
