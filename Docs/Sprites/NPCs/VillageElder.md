# Village Elder

## Overview
The `village_elder.asm` file defines the behavior for the "Village Elder" NPC. This NPC provides early guidance and now delivers a post-D1 hint about the Mask Salesman, which also sets a Tail Pond map marker. Dialogue is conditional based on story flags and progression bits.

## Main Logic (`Sprite_VillageElder_Main`)
This routine manages the Village Elder's interactions and dialogue flow:

*   **Animation**: Plays a specific animation (`%PlayAnimation(2,3,16)`).
*   **Player Collision**: Prevents Link from passing through the elder (`JSL Sprite_PlayerCantPassThrough`).
*   **Progression Check (`OOSPROG`)**: It checks the `OOSPROG` (Oracle of Secrets Progression) flag. Specifically, it checks if bit `$10` is set, which indicates that Link has already met the elder.
    *   **First Meeting**: If Link has not yet met the elder, it displays a solicited message (`%ShowSolicitedMessage($143)`). Upon dismissal of this message, it sets bit `$10` in `OOSPROG` to mark that Link has now met the elder.
    *   **Post-D1 Hint** (untested): If D1 is complete and D2 is not, it displays the Mask Shop hint (`$177`), sets `MapIcon` to Tail Pond, and sets `ElderGuideStage` low nibble to `1`.
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
| `0x177` | Mask Shop hint (post-D1) | Present | `Core/messages.org` |
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
