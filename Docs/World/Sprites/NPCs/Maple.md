# Maple

## Overview
The `maple.asm` file defines the behavior for the NPC "Maple," a significant character involved in a branching "Dream" questline. Maple interacts with Link through extensive dialogue, offers explanations about game mechanics, and possesses the unique ability to put Link to sleep, triggering special dream sequences that advance the narrative and potentially grant rewards.

## Main Logic (`MapleHandler`)
This routine orchestrates Maple's complex interactions with Link, managing dialogue, quest progression, and the initiation of dream sequences.

*   **Player Collision**: Prevents Link from passing through Maple (`JSL Sprite_PlayerCantPassThrough`).
*   **`Maple_Idle`**: Displays a solicited message (`%ShowSolicitedMessage($01B3)`). Upon dismissal, it transitions to `Maple_HandleFirstResponse`. It also includes logic to set a flag (`$7EF351`) and a timer (`$012F`) for a specific event.
*   **`Maple_HandleFirstResponse`**: Processes Link's initial dialogue response (`$1CE8`), leading to different branches: `Maple_Idle`, `Maple_ExplainHut`, or `Maple_DreamOrExplain`.
*   **`Maple_DreamOrExplain`**: Displays an unconditional message (`%ShowUnconditionalMessage($01B4)`) and, based on Link's response, transitions to `Maple_ExplainPendants`, `Maple_CheckForPendant`, or back to `Maple_Idle`.
*   **`Maple_ExplainHut`**: Displays an unconditional message (`%ShowUnconditionalMessage($01B5)`) and returns to `Maple_Idle`.
*   **`Maple_ExplainPendants`**: Displays an unconditional message (`%ShowUnconditionalMessage($01B8)`) and returns to `Maple_Idle`.
*   **`Maple_CheckForPendant`**: Checks Link's collected Pendants (`Pendants` SRAM flag) and Dreams (`Dreams` SRAM flag) to determine if a new Dream is available. If so, it sets `CurrentDream`, displays a message (`%ShowUnconditionalMessage($01B6)`), and transitions to `Maple_PutLinkToSleep`. Otherwise, it transitions to `Maple_NoNewPendant`.
*   **`Maple_NoNewPendant`**: Displays an unconditional message (`%ShowUnconditionalMessage($01B7)`) and returns to `Maple_Idle`.
*   **`Maple_PutLinkToSleep`**: Calls `Sprite_PutLinkToSleep` to initiate the sleep sequence and then transitions to `Maple_HandleDreams`.
*   **`Maple_HandleDreams`**: After a timer (`SprTimerA, X`), calls `Link_HandleDreams` to process the dream sequence.

```asm
MapleHandler:
{
  %PlayAnimation(0,1,16)
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Maple_Idle
  dw Maple_HandleFirstResponse
  dw Maple_DreamOrExplain
  dw Maple_ExplainHut
  dw Maple_ExplainPendants
  dw Maple_CheckForPendant
  dw Maple_NoNewPendant
  dw Maple_PutLinkToSleep
  dw Maple_HandleDreams


  Maple_Idle:
  {
    %ShowSolicitedMessage($01B3) : BCC +
      INC.w SprAction, X
    +
    LDA.l $7EF351 : BEQ +
      LDA.b #$02 : STA.l $7EF351
      LDA.b #$1B : STA.w $012F
    +
    RTS
  }

  Maple_HandleFirstResponse:
  {
    LDA.w $1CE8 : CMP.b #$02 : BNE +
      STZ.w SprAction, X
      RTS
    +
    CMP.b #$01 : BNE .next_response
      LDA.b #$03 : STA.w SprAction, X
      RTS
    .next_response
    INC.w SprAction, X
    RTS
  }

  Maple_DreamOrExplain:
  {
    %ShowUnconditionalMessage($01B4)
    LDA.w $1CE8 : BEQ .check_for_pendant
                  CMP.b #$01 : BNE .another_time
      LDA.b #$04 : STA.w SprAction, X
      RTS
    .check_for_pendant
    LDA.b #$05 : STA.w SprAction, X
    RTS

    .another_time
    STZ.w SprAction, X
    RTS
  }

  Maple_ExplainHut:
  {
    %ShowUnconditionalMessage($01B5)
    STZ.w SprAction, X
    RTS
  }

  Maple_ExplainPendants:
  {
    %ShowUnconditionalMessage($01B8)
    STZ.w SprAction, X
    RTS
  }

  Maple_CheckForPendant:
  {
    ; Check for pendant
    LDA.l Pendants : AND.b #$04 : BNE .courage
    LDA.l Pendants : AND.b #$02 : BNE .power
    LDA.l Pendants : AND.b #$01 : BNE .wisdom
                     JMP .none
    .courage
    LDA.l Dreams : AND.b #$04 : BNE .power
      LDA.b #$02 : STA.w CurrentDream : BRA +
    .power
    LDA.l Dreams : AND.b #$02 : BNE .wisdom
      LDA.b #$01 : STA.w CurrentDream : BRA +
    .wisdom
    LDA.l Dreams : AND.b #$01 : BNE .none
      STZ.w CurrentDream
    +
    %ShowUnconditionalMessage($01B6)
    LDA.b #$07 : STA.w SprAction, X
    LDA.b #$40 : STA.w SprTimerA, X
    RTS
    .none
    INC.w SprAction, X
    RTS
  }

  Maple_NoNewPendant:
  {
    %ShowUnconditionalMessage($01B7)
    STZ.w SprAction, X
    RTS
  }

  Maple_PutLinkToSleep:
  {
    JSR Sprite_PutLinkToSleep
    INC.w SprAction, X
    RTS
  }

  Maple_HandleDreams:
  {
    LDA.w SprTimerA, X : BNE +
      JSR Link_HandleDreams
    +
    RTS
  }
}
```

## `Sprite_PutLinkToSleep`
This routine initiates a cinematic sleep sequence for Link. It adjusts Link's coordinates, sets his state to sleeping (`$5D = $16`), spawns a blanket ancilla, adjusts Link's OAM coordinates, and applies a blinding white palette filter to transition into a dream sequence.

```asm
Sprite_PutLinkToSleep:
{
  PHX
  LDA.b $20 : SEC : SBC.b #$14 : STA.b $20
  LDA.b $22 : CLC : ADC.b #$18 : STA.b $22

  LDA.b #$16 : STA.b $5D ; Set Link to sleeping
  LDA.b #$20 : JSL AncillaAdd_Blanket
  LDA.b $20 : CLC : ADC.b #$04 : STA.w $0BFA,X
  LDA.b $21 : STA.w $0C0E,X
  LDA.b $22 : SEC : SBC.b #$08 : STA.w $0C04,X
  LDA.b $23 : STA.w $0C18,X
  JSL PaletteFilter_StartBlindingWhite
  JSL ApplyPaletteFilter
  PLX
  RTS
}
```

## `Link_HandleDreams`
This routine manages the different dream sequences based on the `CurrentDream` variable. It sets specific bits in the `Dreams` SRAM flag and warps Link to a designated room using `Link_WarpToRoom`.

*   **`Dream_Wisdom`**: Sets bit `0` in `Dreams`, warps Link to a room, and sets `$EE` to `$01`.
*   **`Dream_Power`**: Sets bit `1` in `Dreams` and warps Link to a room.
*   **`Dream_Courage`**: Sets bit `2` in `Dreams` and warps Link to a room.

```asm
Link_HandleDreams:
{
  LDA.w CurrentDream
  JSL JumpTableLocal

  dw Dream_Wisdom
  dw Dream_Power
  dw Dream_Courage

  Dream_Wisdom:
  {
    LDA.l Dreams : ORA.b #%00000001 : STA.l Dreams
    LDX.b #$00
    JSR Link_WarpToRoom
    LDA.b #$01 : STA.b $EE
    RTS
  }

  Dream_Power:
  {
    LDA.l Dreams : ORA.b #%00000010 : STA.l Dreams
    LDX.b #$01
    JSR Link_WarpToRoom
    RTS
  }

  Dream_Courage:
  {
    LDA.l Dreams : ORA.b #%00000100 : STA.l Dreams
    LDX.b #$02
    JSR Link_WarpToRoom
    RTS
  }
}
```

## `Link_WarpToRoom`
This routine sets Link's state for warping, including setting his `LinkState` and room coordinates, and uses a `.room` data table to determine the target room for the warp.

## `Link_FallIntoDungeon`
This routine sets Link's state for falling into a dungeon, including setting the entrance ID and various state flags. It uses an `.entrance` data table to determine the target entrance.

## Vanilla Override
*   **`org $068C9C`**: Sets a byte to `$0F`, likely a minor adjustment to vanilla code.

## Design Patterns
*   **Complex Dialogue System**: Maple's interactions feature a highly branching and conditional dialogue system, where player choices and game progression influence the conversation flow and subsequent events.
*   **Quest Gating/Progression**: Maple is a central figure in a "Dream" questline, with her dialogue and actions dynamically adapting based on Link's collected Pendants and Dreams, guiding the player through a significant narrative arc.
*   **Player State Manipulation**: Maple possesses the unique ability to put Link to sleep, which triggers special dream sequences and warps him to different locations, creating immersive and story-rich transitions.
*   **Cinematic Sequences**: The `Sprite_PutLinkToSleep` routine orchestrates a cinematic effect, incorporating screen transitions, visual filters, and the spawning of ancillae to enhance the player's experience during dream initiations.
*   **Global State Management**: The sprite extensively modifies `Pendants`, `Dreams`, `CurrentDream`, and other global variables to meticulously track and influence quest progress, ensuring a consistent and evolving game world.
