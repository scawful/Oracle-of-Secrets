# Village Elder

## Overview
The `village_elder.asm` file defines the Village Elder NPC. Per code (runtime unverified), its post-D1 branch shows message `$1CB` (the Ranch Girl hint) and does not write `MapIcon`. The Tail Pond marker is set by the Ranch Girl Ocarina receipt (`ranch_girl.asm:83`). Whether `$1CB` matches the 2026-09-02 canon ruling is not checked here (scawful's call).

## Main Logic (`Sprite_VillageElder_Main`)
This routine manages the Village Elder's interactions and dialogue flow:

*   **Animation**: Plays a specific animation (`%PlayAnimation(2,3,16)`).
*   **Player Collision**: Prevents Link from passing through the elder (`JSL Sprite_PlayerCantPassThrough`).
*   **Progression Check (`OOSPROG`)**: It checks the `OOSPROG` (Oracle of Secrets Progression) flag. Specifically, it checks if bit `$10` is set, which indicates that Link has already met the elder.
    *   **First Meeting**: If Link has not yet met the elder, it displays a solicited message (`%ShowSolicitedMessage($143)`). Upon dismissal of this message, it sets bit `$10` in `OOSPROG` to mark that Link has now met the elder.
    *   **Post-D1 Hint** (per code, runtime unverified): If the D1 crystal is set, the D2 crystal is clear, `Flute` is 0, and the `ElderGuideStage` low nibble is less than 1, it shows message `$1CB` as a solicited message. When that message completes, it sets the `ElderGuideStage` low nibble to `1`. Otherwise it shows `$019`. It does not write `MapIcon`.
    *   **Subsequent Meetings**: Otherwise, a different solicited message (`%ShowSolicitedMessage($019)`) is displayed.

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

## Messages

| Message ID | Usage | Status | Text Source |
| --- | --- | --- | --- |
| `0x143` | First meeting | Present | `Core/messages.org` |
| `0x1CB` | Ranch Girl hint (post-D1) | Present | `Data/dialogue/expanded_messages.json` (id 62) |
| `0x019` | Already met | Present | `Core/messages.org` |

**Message 0x143 (current):**
```
Welcome, young one, to this
Village of Wayward, for which
I am the mayor.
Rumor has it that the Oracle of
Secrets has been kidnapped.
This is truly a terrible fate.
To truly take on the forces of
Kydrog, you will need to return
to the abyss for strength...
There is a gate, left by my
ancestors in the mountains. I
will mark the spot on your map.
```

**Message 0x019 (current):**
```
If you defeat Kydrog, the
island will be free to prosper
once again.
Go, seek the Essences!
```

## Notes / TODO
- Add progress-based dialogue updates keyed to main quest milestones.
- Decide if Elder should reference fortune teller/scroll revelations and align message IDs accordingly.

## Design Patterns
*   **Simple NPC Interaction**: The Village Elder provides basic dialogue interaction with Link.
*   **Quest Progression Tracking**: Utilizes a custom progression flag (`OOSPROG`) to track whether Link has met the elder, allowing for dynamic changes in dialogue based on game state.
*   **Player Collision**: Implements `JSL Sprite_PlayerCantPassThrough` to make the elder a solid object that Link cannot walk through.
