# Maku Tree

## Overview
The Maku Tree sprite (`!SPRID = Sprite_MakuTree`) represents a significant NPC in the game, likely serving as a quest giver or a key character in the narrative. Its interactions are primarily dialogue-driven and tied to game progression, culminating in the granting of a Heart Container. Notably, its graphics are not handled by a conventional sprite drawing routine within this file, suggesting it might be a background element or drawn by a separate system.

## Sprite Properties
*   **`!SPRID`**: `Sprite_MakuTree` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `00` (Indicates graphics are handled externally or as a background)
*   **`!Harmless`**: `01`
*   **`!HVelocity`**: `00`
*   **`!Health`**: `0`
*   **`!Damage`**: `0`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `00`
*   **`!Shadow`**: `00`
*   **`!Palette`**: `0`
*   **`!Hitbox`**: `$0D`
*   **`!Persist`**: `00`
*   **`!Statis`**: `00`
*   **`!CollisionLayer`**: `00`
*   **`!CanFall`**: `00`
*   **`!DeflectArrow`**: `00`
*   **`!WaterSprite`**: `00`
*   **`!Blockable`**: `00`
*   **`!Prize`**: `0`
*   **`!Sound`**: `00`
*   **`!Interaction`**: `00`
*   **`!Statue`**: `00`
*   **`!DeflectProjectiles`**: `00`
*   **`!ImperviousArrow`**: `00`
*   **`!ImpervSwordHammer`**: `00`
*   **`!Boss`**: `00`

## Main Structure (`Sprite_MakuTree_Long`)
This routine primarily checks if the Maku Tree sprite is active and then dispatches to its main logic routine. The absence of a direct drawing call (`JSR Sprite_MakuTree_Draw`) here suggests its visual representation is managed outside of the standard sprite drawing pipeline.

```asm
Sprite_MakuTree_Long:
{
  PHB : PHK : PLB
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_MakuTree_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_MakuTree_Prep`)
This routine initializes the Maku Tree upon spawning. It sets `SprDefl, X` and includes logic to potentially play the "Maku Song" by checking a custom progression flag (`OOSPROG2`).

```asm
Sprite_MakuTree_Prep:
{
  PHB : PHK : PLB
  ; Play the Maku Song
  LDA.l OOSPROG2 : AND.b #$04 : BEQ +
    LDA.b #$03 : STA.w $012C
  +
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_MakuTree_Main`)
The Maku Tree's core behavior is managed by a state machine that guides its interaction with Link and quest progression.

*   **Player Collision**: Prevents Link from passing through the Maku Tree (`JSL Sprite_PlayerCantPassThrough`).
*   **`MakuTree_Handler`**: Checks the `MakuTreeQuest` flag to determine if Link has already met the Maku Tree, transitioning to `MakuTree_MeetLink` or `MakuTree_HasMetLink` accordingly.
*   **`MakuTree_MeetLink`**: When Link is close enough, the Maku Tree displays an unconditional message (`%ShowUnconditionalMessage($20)`), updates quest flags (`MakuTreeQuest`, `MapIcon`, `$7EF3D6`), and transitions to `MakuTree_SpawnHeartContainer`.
*   **`MakuTree_SpawnHeartContainer`**: Grants Link a Heart Container (`LDY #$3E : JSL Link_ReceiveItem`) and then transitions to `MakuTree_HasMetLink`.
*   **`MakuTree_HasMetLink`**: Displays a solicited message (`%ShowSolicitedMessage($22)`) and updates a progression flag (`$7EF3D6`) upon message dismissal.

```asm
Sprite_MakuTree_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw MakuTree_Handler
  dw MakuTree_MeetLink
  dw MakuTree_SpawnHeartContainer
  dw MakuTree_HasMetLink

  MakuTree_Handler:
  {
    ; Check the progress flags
    LDA.l MakuTreeQuest : AND.b #$01 : BNE .has_met_link
      %GotoAction(1)
      RTS
    .has_met_link
    %GotoAction(3)
    RTS
  }

  MakuTree_MeetLink:
  {
    JSL GetDistance8bit_Long : CMP #$28 : BCS .not_too_close
      %ShowUnconditionalMessage($20)
      LDA.b #$01 : STA.l MakuTreeQuest
      LDA.b #$01 : STA.l MapIcon ; Mushroom Grotto
      LDA.l $7EF3D6 : ORA.b #$02 : STA.l $7EF3D6
      %GotoAction(2)
    .not_too_close
    RTS
  }

  MakuTree_SpawnHeartContainer:
  {
    ; Give Link a heart container
    LDY #$3E : JSL Link_ReceiveItem
    %GotoAction(3)
    RTS
  }

  MakuTree_HasMetLink:
  {
    %ShowSolicitedMessage($22) : BCC .no_talk
      LDA.l $7EF3D6 : ORA.b #$02 : STA.l $7EF3D6
    .no_talk
    RTS
  }
}
```

## Drawing
There is no `Sprite_MakuTree_Draw` routine defined within this file. This strongly suggests that the Maku Tree's graphical representation is handled as a background element or by a separate drawing system, rather than as a conventional sprite with its own OAM data.

## Design Patterns
*   **Background/Static NPC**: The Maku Tree functions as a static NPC whose visual representation is likely integrated into the background, as evidenced by the absence of a dedicated sprite drawing routine.
*   **Quest Gating/Progression**: The Maku Tree's interactions are deeply tied to custom quest flags (`MakuTreeQuest`, `OOSPROG2`, `$7EF3D6`), controlling when Link can meet it, engage in dialogue, and receive rewards.
*   **Item Granting**: The Maku Tree serves as a source for a significant reward, granting Link a Heart Container upon meeting specific quest conditions.
*   **Player Collision**: Implements `Sprite_PlayerCantPassThrough` to make the Maku Tree a solid, impassable object in the game world.
*   **Dialogue-Driven Progression**: Dialogue (`%ShowUnconditionalMessage`, `%ShowSolicitedMessage`) is strategically used to advance the quest narrative and provide context to the player's journey.
