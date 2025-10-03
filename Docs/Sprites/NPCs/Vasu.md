# Vasu / Error

## Overview
The `vasu.asm` file defines the behavior for a multi-character NPC sprite that can represent either "Vasu," the ring appraiser, or a special "Error" sprite. The specific character displayed and its interactions are determined by `SprSubtype, X`. Vasu offers a service to appraise rings, with conditional dialogue and transactions based on Link's inventory and rupee count.

## Sprite Properties
*   **`!SPRID`**: `Sprite_Vasu` (Custom symbol, likely a remapped vanilla ID)
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
*   **`!Hitbox`**: `09`
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

## Main Structure (`Sprite_Vasu_Long`)
This routine acts as a dispatcher for drawing, selecting `Sprite_Vasu_Draw` for Vasu (`SprSubtype, X = 0`) or `Sprite_Error_Draw` for the Error sprite. It also handles shadow drawing and dispatches to the main logic if the sprite is active.

```asm
Sprite_Vasu_Long:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : BNE +
    JSR Sprite_Vasu_Draw
    JMP ++
  +
    JSR Sprite_Error_Draw
  ++
  JSL Sprite_DrawShadow
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Vasu_Main
  .SpriteIsNotActive
  PLB
  RTL
}
```

## Initialization (`Sprite_Vasu_Prep`)
This routine initializes the sprite upon spawning. It sets `SprDefl, X` to `$80`. If the sprite is Vasu (`SprSubtype, X = 0`), it sets `SprAction, X` to `$04`.

```asm
Sprite_Vasu_Prep:
{
  PHB : PHK : PLB
  LDA.b #$80 : STA.w SprDefl, X
  LDA.w SprSubtype, X : BEQ +
    LDA.b #$04 : STA.w SprAction, X
  +
  PLB
  RTL
}
```

## Main Logic & State Machine (`Sprite_Vasu_Main`)
This routine manages the various states and interactions for both Vasu and the Error sprite.

*   **Player Collision**: Prevents Link from passing through (`JSL Sprite_PlayerCantPassThrough`).
*   **`Vasu_Idle`**: Plays an animation and displays a solicited message (`%ShowSolicitedMessage($00A9)`). Upon message dismissal, it transitions to `Vasu_MessageHandler`.
*   **`Vasu_MessageHandler`**: Plays an animation and processes Link's choice (`MsgChoice`). It can lead to `Vasu_AppraiseRing`, `Vasu_ExplainRings` (displays message `$00AA` and returns to `Vasu_Idle`), or return to `Vasu_Idle` if Link chooses "nevermind."
*   **`Vasu_AppraiseRing`**: Plays an animation. Checks `FOUNDRINGS` (SRAM flag for found rings). If no rings are found, it displays a message (`%ShowUnconditionalMessage($00AD)`) and returns to `Vasu_Idle`. If rings are found, it checks `MAGICRINGS` (SRAM flag for owned rings). If Link has no rings yet, it offers the first appraisal for free (`%ShowUnconditionalMessage($00AB)`). Otherwise, it checks for 20 rupees (`$7EF360`). If Link has enough, it deducts the rupees, updates `MAGICRINGS` by ORing with `FOUNDRINGS`, and transitions to `Vasu_RingAppraised`. If not enough rupees, it displays a message (`%ShowUnconditionalMessage($0189)`) and returns to `Vasu_Idle`.
*   **`Vasu_RingAppraised`**: Plays an animation, displays a message (`%ShowUnconditionalMessage($00AC)`), and returns to `Vasu_Idle`.
*   **`Error_Idle`**: Plays an animation and displays a solicited message (`%ShowSolicitedMessage($0121)`) "I am Error." Upon message dismissal, it randomly sets `FOUNDRINGS`.

```asm
Sprite_Vasu_Main:
{
  JSL Sprite_PlayerCantPassThrough

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Vasu_Idle
  dw Vasu_MessageHandler
  dw Vasu_AppraiseRing
  dw Vasu_RingAppraised

  dw Error_Idle

  Vasu_Idle:
  {
    %PlayAnimation(0,1,20)
    %ShowSolicitedMessage($00A9) : BCC .didnt_talk
      %GotoAction(1)
    .didnt_talk
    RTS
  }

  Vasu_MessageHandler:
  {
    %PlayAnimation(0,1,20)
    LDA.w MsgChoice : BEQ .appraise_rings
         CMP.b #$01 : BEQ .explain_rings
      ; Player said nevermind.
      %GotoAction(0)
      RTS
    .explain_rings
    %ShowUnconditionalMessage($00AA)
    %GotoAction(0)
    RTS
    .appraise_rings
    LDA.b #$40 : STA.w SprTimerB, X
    %GotoAction(2)
    RTS
  }

  Vasu_AppraiseRing:
  {
    %PlayAnimation(0,1,20)

    ; Check if the player has found any rings to appraise
    REP #$30
    LDA.l FOUNDRINGS
    AND.w #$00FF
    SEP #$30
    BEQ .no_rings
      ; Check if the player has any rings, if not give them one for free
      LDA.l MAGICRINGS : BEQ .no_rings_yet
        REP #$20
        LDA.l $7EF360
        CMP.w #$14 ; 20 rupees
        SEP #$30
        BCC .not_enough_rupees

          REP #$20
          LDA.l $7EF360
          SEC
          SBC.w #$14 ; Subtract 20 rupees
          STA.l $7EF360
          SEP #$30

          JMP .appraise_me

        .not_enough_rupees
          %ShowUnconditionalMessage($0189) ; 'You don't have enough rupees!'
          %GotoAction(0)
          RTS

      .no_rings_yet
      %ShowUnconditionalMessage($00AB) ; 'First one is free!'
      JMP .appraise_me

    .no_rings
    %ShowUnconditionalMessage($00AD) ; 'You don't have any rings!'
    %GotoAction(0)
    RTS

    .appraise_me
    ; Check the found rings and set the saved rings
    ; Get the bit from found rings and set it in MAGICRINGS
    LDA.l FOUNDRINGS
    ORA.l MAGICRINGS
    STA.l MAGICRINGS

    %GotoAction(3)

    RTS
  }

  Vasu_RingAppraised:
  {
    %PlayAnimation(0,1,20)
    %ShowUnconditionalMessage($00AC) ; 'Come back later for more appraisals!'

    %GotoAction(0)
    RTS
  }

  Error_Idle:
  {
    %PlayAnimation(0,1,24)
     ; "I am Error"
    %ShowSolicitedMessage($0121) : BCC +
      JSL GetRandomInt : AND.b #$06 : STA.l FOUNDRINGS
    +
    RTS
  }
}
```

## Drawing (`Sprite_Vasu_Draw` and `Sprite_Error_Draw`)
Both drawing routines handle OAM allocation and animation for their respective characters. They explicitly use `REP #$20` and `SEP #$20` for 16-bit coordinate calculations. Each routine contains its own specific OAM data for rendering the character.

## Design Patterns
*   **Multi-Character Sprite (Conditional Drawing/Logic)**: A single sprite definition (`Sprite_Vasu`) is used to represent two distinct characters (Vasu and the "Error" sprite) based on `SprSubtype`, showcasing efficient resource utilization and varied visual appearances.
*   **Shop/Service System**: Vasu implements a service where he appraises rings for a fee (or for free the first time), integrating a transactional element into NPC interactions.
*   **Quest Gating/Progression**: Vasu's interactions are conditional on Link having found rings (`FOUNDRINGS`) and his rupee count, ensuring that the appraisal service is available only when relevant.
*   **Conditional Transactions**: The appraisal process involves checking Link's rupee count and deducting the cost, simulating a real in-game economy.
*   **Player Choice and Branching Dialogue**: Link's choices (`MsgChoice`) directly influence the flow of conversation, leading to different outcomes and information from Vasu.
*   **Item Management**: Vasu interacts with `FOUNDRINGS` and `MAGICRINGS` (SRAM flags) to manage Link's ring collection, updating his inventory based on appraisals.
*   **Easter Egg/Hidden Content**: The "Error" sprite, with its unique dialogue, likely serves as an Easter egg or a placeholder for debugging, adding a touch of humor or mystery.
*   **16-bit OAM Calculations**: Demonstrates explicit use of `REP #$20` and `SEP #$20` for precise 16-bit OAM coordinate calculations, crucial for accurate sprite rendering.
