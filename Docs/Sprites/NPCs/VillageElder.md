# Village Elder

## Overview
The `village_elder.asm` file defines the behavior for the "Village Elder" NPC. This is a straightforward NPC whose primary function is to interact with Link through dialogue. The content of the dialogue is conditional, changing based on whether Link has previously met the elder, as tracked by a custom progression flag (`OOSPROG`).

## Main Logic (`Sprite_VillageElder_Main`)
This routine manages the Village Elder's interactions and dialogue flow:

*   **Animation**: Plays a specific animation (`%PlayAnimation(2,3,16)`).
*   **Player Collision**: Prevents Link from passing through the elder (`JSL Sprite_PlayerCantPassThrough`).
*   **Progression Check (`OOSPROG`)**: It checks the `OOSPROG` (Oracle of Secrets Progression) flag. Specifically, it checks if bit `$10` is set, which indicates that Link has already met the elder.
    *   **First Meeting**: If Link has not yet met the elder, it displays a solicited message (`%ShowSolicitedMessage($143)`). Upon dismissal of this message, it sets bit `$10` in `OOSPROG` to mark that Link has now met the elder.
    *   **Subsequent Meetings**: If Link has already met the elder, a different solicited message (`%ShowSolicitedMessage($019)`) is displayed.

```asm
Sprite_VillageElder_Main:
{
  %PlayAnimation(2,3,16)
  JSL Sprite_PlayerCantPassThrough
  REP #$30
  LDA.l OOSPROG : AND.w #$00FF
  SEP #$30
  AND.b #$10 : BNE .already_met
    %ShowSolicitedMessage($143) : BCC .no_message
      LDA.l OOSPROG : ORA.b #$10 : STA.l OOSPROG
    .no_message
    RTS

  .already_met
  %ShowSolicitedMessage($019)
  RTS
}
```

## Design Patterns
*   **Simple NPC Interaction**: The Village Elder provides basic dialogue interaction with Link.
*   **Quest Progression Tracking**: Utilizes a custom progression flag (`OOSPROG`) to track whether Link has met the elder, allowing for dynamic changes in dialogue based on game state.
*   **Player Collision**: Implements `JSL Sprite_PlayerCantPassThrough` to make the elder a solid object that Link cannot walk through.
