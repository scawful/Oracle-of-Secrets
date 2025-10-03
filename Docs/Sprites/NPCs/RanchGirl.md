# Ranch Girl

## Overview
The `ranch_girl.asm` file defines the behavior for the "Ranch Girl" NPC, who is involved in a "Chicken Easter Egg" quest. This character plays a crucial role in granting Link the Ocarina and teaching him a song. Her behavior is implemented as a vanilla override, modifying the existing `ChickenLady` routine.

## Vanilla Overrides
This file directly modifies the vanilla `ChickenLady` routine at `org $01AFECF` to inject custom logic for the Ranch Girl's interactions.

## `RanchGirl_Message`
This routine handles the dialogue displayed by the Ranch Girl. It checks Link's Ocarina status (`$7EF34C`).

*   If Link already possesses the Ocarina, it displays message `$010E`.
*   Otherwise, it displays message `$017D` and sets `SprMiscD, X` to `$01`, indicating the start of the Ocarina quest.

```asm
RanchGirl_Message:
{
  LDA $7EF34C : CMP.b #$01 : BCS .has_ocarina
    %ShowUnconditionalMessage($017D)
    LDA #$01 : STA.w SprMiscD, X
    RTL
  .has_ocarina
  %ShowUnconditionalMessage($010E)
  RTL
}
```

## `RanchGirl_TeachSong`
This routine is responsible for teaching Link a song (specifically the "Song of Storms") and granting him the Ocarina. It checks the Ocarina quest flag (`SprMiscD, X`) and Link's current Ocarina status (`$7EF34C`).

*   If the conditions are met, it plays the "Song of Storms" sound, gives Link the Ocarina (`LDY #$14`, `JSL Link_ReceiveItem`), and sets `$7EF34C` to `$01`.

```asm
RanchGirl_TeachSong:
{
  LDA.w SprMiscD, X : CMP.b #$01 : BNE .not_started
  LDA $10 : CMP.b #$0E : BEQ .running_dialog
  LDA $7EF34C : CMP.b #$01 : BCS .has_song

  ; Play the song of storms
  LDA.b #$2F
  STA.w $0CF8
  JSL $0DBB67 ;  Link_CalculateSFXPan
  ORA.w $0CF8
  STA $012E ; Play the song learned sound

  ; Give Link the Ocarina
  LDY #$14
  ; Clear the item receipt ID
  STZ $02E9
  PHX
  JSL Link_ReceiveItem
  PLX

  LDA #$01 : STA $7EF34C ; The item gives 02 by default, so decrement that for now

  .not_started
  .running_dialog
  .has_song
  LDA.b $1A : LSR #4 : AND.b #$01 : STA.w $0DC0,X

  RTL
}
```

## `ChickenLady` (Vanilla Override)
This is the main entry point for the Ranch Girl's custom behavior, overriding the vanilla `ChickenLady` routine. It sets `SprMiscC, X` to `$01`, calls vanilla drawing and activity check routines, and then executes `RanchGirl_Message` and `RanchGirl_TeachSong`.

```asm
org $01AFECF
ChickenLady:
{
  JSR .main
  RTL

  .main
  LDA.b #$01 : STA.w SprMiscC, X

  JSL SpriteDraw_RaceGameLady
  JSR Sprite_CheckIfActive_Bank1A

  LDA.w SprTimerA, X : CMP.b #$01 : BNE .no_message
    JSL RanchGirl_Message
  .no_message
  JSL RanchGirl_TeachSong
  .return
  RTS
}
```

## Design Patterns
*   **Vanilla Override**: This file directly modifies a vanilla routine (`ChickenLady`) to implement custom NPC behavior, demonstrating a common ROM hacking technique.
*   **Quest Gating/Progression**: The Ranch Girl's dialogue and the granting of the Ocarina are tied to Link's possession of the Ocarina and the state of the Ocarina quest, integrating her into the game's progression system.
*   **Item Granting**: The Ranch Girl serves as a source for the Ocarina, a key item in the game.
*   **Game State Manipulation**: Directly modifies `$7EF34C` (Ocarina flag) and `SprMiscD, X` (quest flag) to track and influence game state.
