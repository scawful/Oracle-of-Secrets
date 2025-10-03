# Farore

## Overview
Farore, the Oracle of Secrets, is a pivotal NPC sprite deeply integrated into the game's narrative and cutscene system. Her behavior is highly dynamic, adapting to the player's location (indoors/outdoors) and various game progression flags. She plays a crucial role in guiding the player and controlling cinematic sequences.

## Sprite Properties
*   **`!SPRID`**: `Sprite_Farore` (Custom symbol, likely a remapped vanilla ID)
*   **`!NbrTiles`**: `2`
*   **`!Harmless`**: `00` (Unusual for an NPC, might indicate specific interaction or placeholder)
*   **`!HVelocity`**: `00`
*   **`!Health`**: `0`
*   **`!Damage`**: `0`
*   **`!DeathAnimation`**: `00`
*   **`!ImperviousAll`**: `00`
*   **`!SmallShadow`**: `01`
*   **`!Shadow`**: `01`
*   **`!Palette`**: `0`
*   **`!Hitbox`**: `0`
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

## Main Structure (`Sprite_Farore_Long`)
This routine acts as a dispatcher, conditionally calling different drawing and main logic routines based on whether Link is `INDOORS`. This indicates that the `Farore` sprite ID is reused for a different entity (likely "Hyrule Dream") when indoors.

```asm
Sprite_Farore_Long:
{
  PHB : PHK : PLB
  LDA.b INDOORS : BEQ .outdoors
    JSR Sprite_HyruleDream_Draw
    JSL Sprite_CheckActive : BCC .SpriteIsNotActive
      JSR Sprite_HyruleDream_Main
      JMP .SpriteIsNotActive
  .outdoors
  JSR Sprite_Farore_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Farore_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Farore_Prep`)
This routine initializes Farore upon spawning. It sets `SprDefl, X` to `$80` to prevent despawning off-screen. It also includes conditional initialization based on `INDOORS` and a check for `$7EF300` (likely a flag for Farore's presence) to potentially despawn the sprite.

```asm
Sprite_Farore_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X ; Don't kill Farore when she goes off screen
  LDA.b INDOORS : BEQ .outdoors
    JSR Sprite_HyruleDream_Prep
    JMP .PlayIntro
  .outdoors
  LDA.l $7EF300 : BEQ .PlayIntro
    STZ.w SprState, X ; Kill the sprite
  .PlayIntro
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_Farore_Main`)
Farore's core behavior is managed by a complex state machine heavily involved in cutscenes and quest progression:

*   **`IntroStart`**: Initiates a cutscene (`InCutScene = 01`) and transitions to different states based on `STORY_STATE` (`$B6`).
*   **`MoveUpTowardsFarore`**: Controls Link's movement during a cutscene, slowing him down and moving him north. Transitions to `MoveLeftTowardsFarore` when Link reaches a certain Y-position.
*   **`MoveLeftTowardsFarore`**: Continues Link's controlled movement, moving him west. Stops auto-movement, sets a timer, and transitions to `WaitAndMessage`.
*   **`WaitAndMessage`**: Displays a message after a timer, applies speed towards the player, and transitions to `Farore_ProceedWithCutscene`.
*   **`Farore_ProceedWithCutscene`**: A transitional state that leads to `FaroreFollowPlayer` after a timer.
*   **`FaroreFollowPlayer`**: Farore follows Link, controlling his movement and updating various game state flags (`GAMESTATE`, `STORY_STATE`, rain sound). Transitions to `MakuArea_FaroreFollowPlayer`.
*   **`MakuArea_FaroreFollowPlayer`**: Farore continues to follow Link in the Maku Area.
*   **`MakuArea_FaroreWaitForKydrog`**: Farore waits in the Maku Area.

```asm
Sprite_Farore_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw IntroStart
  dw MoveUpTowardsFarore
  dw MoveLeftTowardsFarore
  dw WaitAndMessage
  dw Farore_ProceedWithCutscene
  dw FaroreFollowPlayer
  dw MakuArea_FaroreFollowPlayer
  dw MakuArea_FaroreWaitForKydrog

  ; 00
  IntroStart:
  {
    LDA #$01 : STA InCutScene
    LDA $B6 : CMP.b #$01 : BEQ .maku_area
              CMP.b #$02 : BEQ .waiting
      %GotoAction(1)
      RTS
    .maku_area
    %GotoAction(6)
    RTS

    .waiting
    %GotoAction(7)
    RTS
  }

  ; 01
  MoveUpTowardsFarore:
  {
    LDA.w WALKSPEED : STA.b $57 ; Slow Link down for the cutscene
    LDA.b #$08 : STA.b $49 ; Auto-movement north

    ; Link's Y Position - Y = 6C
    LDA.b $20 : CMP.b #$9C : BCC .linkistoofar
      %GotoAction(2)
    .linkistoofar
    %PlayAnimation(6, 6, 8) ; Farore look towards Link
    RTS
  }

  ; 02
  MoveLeftTowardsFarore:
  {
    ; Move Link Left
    LDA.w WALKSPEED : STA.b $57 ; Slow Link down for the cutscene
    LDA.b #$02 : STA.b $49

    ; Link's X position
    LDA.b $22 : CMP.b #$1A : BCS .linkistoofar
      STZ.b $49 ; kill automove
      LDA.b #$20
      STA.w SprTimerA, X ; set timer A to 0x10
      %PlayAnimation(0, 0, 8)
      %GotoAction(3)
    .linkistoofar
    RTS
  }

  ; 03
  WaitAndMessage:
  {
    %PlayAnimation(1, 2, 8)
    LDA.b #$15
    JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_MoveVert
    LDA.w SprTimerA, X : BNE +
      STZ $2F
      LDA #$00 : STA InCutScene
      ; "I am Farore, the Oracle of Secrets."
      %ShowUnconditionalMessage($0E)
      %GotoAction(4)
    +
    RTS
  }

  ; 04
  Farore_ProceedWithCutscene:
  {
    LDA.w SprTimerA, X : BNE ++
      %GotoAction(5)
    ++
    RTS
  }

  ; 05
  FaroreFollowPlayer:
  {
    LDA #$01 : STA InCutScene
    LDA.w WALKSPEED : STA.b $57 ; Slow Link down for the cutscene
    LDA.b #$08 : STA.b $49 ; Auto-movement north
    %PlayAnimation(3, 4, 8)

    LDA.b #$15
    JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_MoveVert

    LDA #$02 : STA $7EF3C5   ; (0 - intro, 1 - pendants, 2 - crystals)
    LDA #$05 : STA $012D ; turn off rain sound
    LDA #$01 : STA $B6 ; Set Story State
    JSL Sprite_LoadGfxProperties

    %GotoAction(6)
    RTS
  }

  ; 06
  MakuArea_FaroreFollowPlayer:
  {
    %PlayAnimation(3, 4, 8)

    LDA.b #$15
    JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_MoveVert

    %GotoAction(6)
    RTS
  }

  ; 07
  MakuArea_FaroreWaitForKydrog:
  {
    %PlayAnimation(5, 5, 8)
    RTS
  }
}
```

## Drawing (`Sprite_Farore_Draw`)
This routine handles OAM allocation and animation for Farore. It explicitly uses `REP #$20` and `SEP #$20` for 16-bit coordinate calculations.

```asm
Sprite_Farore_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
    db $00, $02, $04, $06, $08, $0A, $0C
  .nbr_of_tiles
    db 1, 1, 1, 1, 1, 1, 1
  .x_offsets
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, -1
  .y_offsets
    dw -8, 4
    dw -8, 4
    dw 4, -8
    dw -8, 4
    dw 4, -7
    dw -8, 4
    dw 4, -7
  .chr
    db $A8, $AA
    db $A8, $88
    db $AA, $A8
    db $8A, $8C
    db $8C, $8A
    db $8A, $AC
    db $AA, $86
  .properties
    db $3B, $3B
    db $3B, $7B
    db $3B, $3B
    db $3B, $3B
    db $7B, $3B
    db $3B, $3B
    db $3B, $7B
  .sizes
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
}
```

## Design Patterns
*   **Multi-Character Sprite (Conditional Drawing/Logic)**: The sprite ID is reused for "Hyrule Dream" when indoors, demonstrating a powerful technique for resource optimization and context-sensitive character representation.
*   **Cutscene Control**: Farore's logic is heavily integrated with cutscenes, controlling Link's movement, displaying messages, and managing game state transitions to create cinematic sequences.
*   **Quest Progression Integration**: The sprite's appearance and behavior are tied to `STORY_STATE` and other game flags, indicating its crucial role in advancing the narrative.
*   **Player Movement Manipulation**: During cutscenes, Farore's script directly controls Link's speed and auto-movement, ensuring precise choreography for story events.
*   **Global State Management**: Modifies `InCutScene`, `GAMESTATE`, `STORY_STATE`, and other global variables to reflect and control the current game context.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
