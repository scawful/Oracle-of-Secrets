# Fortune Teller

## Overview
The `fortune_teller.asm` file is not a complete sprite definition but rather a set of routines and data that override and extend the behavior of the vanilla Fortune Teller NPC. Its primary function is to provide highly context-sensitive messages to Link, offering guidance or commentary based on his current inventory, collected items, and overall game progression.

## Vanilla Overrides
This file directly modifies existing vanilla code related to the Fortune Teller:

*   **`org $0DC829`**: Overrides the `FortuneTellerMessage` data table, which contains the message IDs that the Fortune Teller can display.
*   **`org $0DC849`**: Overrides the `FortuneTeller_PerformPseudoScience` routine, which is the core logic for determining and displaying messages.

## `FortuneTellerMessage` Data Table
This table stores a sequence of byte values, each representing a message ID. These IDs correspond to specific dialogue options that the Fortune Teller can present to Link.

```asm
org $0DC829
FortuneTellerMessage:
.low
#_0DC829: db $EA ; MESSAGE 00EA
#_0DC82A: db $EB ; MESSAGE 00EB
#_0DC82B: db $EC ; MESSAGE 00EC
#_0DC82C: db $ED ; MESSAGE 00ED
#_0DC82D: db $EE ; MESSAGE 00EE
#_0DC82E: db $EF ; MESSAGE 00EF
#_0DC82F: db $F0 ; MESSAGE 00F0
#_0DC830: db $F1 ; MESSAGE 00F1
#_0DC831: db $F6 ; MESSAGE 00F6
#_0DC832: db $F7 ; MESSAGE 00F7
#_0DC833: db $F8 ; MESSAGE 00F8
#_0DC834: db $F9 ; MESSAGE 00F9
#_0DC835: db $FA ; MESSAGE 00FA
#_0DC836: db $FB ; MESSAGE 00FB
#_0DC837: db $FC ; MESSAGE 00FC
#_0DC838: db $FD ; MESSAGE 00FD

.high
#_0DC839: db $00
; ... (rest of the table)
```

## `FortuneTeller_PerformPseudoScience` Routine
This routine is the central logic for the custom Fortune Teller. It dynamically selects which message to display to Link based on a series of checks against his inventory and various game progression flags stored in SRAM.

*   **Initializations**: Performs some initial state manipulations (`STZ.w $0DC0,X`, `INC.w $0D80,X`, `STZ.b $03`).
*   **Progression Check (`$7EF3D6`)**: Determines a base message category based on a custom progression flag.
*   **Extensive Item and Game State Checks**: The routine then proceeds through a series of conditional checks, each corresponding to a specific item or game event. For example, it checks for:
    *   `$7EF344` (Mushroom/Powder)
    *   `$7EF37A` (Crystals, specifically if Tail Palace is beaten)
    *   `$7EF355` (Boots)
    *   `$7EF356` (Flippers)
    *   `$7EF345` (Fire Rod)
    *   `$7EF37B` (Magic Upgrade)
    *   `$7EF354` (Glove)
    *   `$7EF358` (Wolf Mask)
    *   `$7EF3C9` (Smithy Rescued flag)
    *   `$7EF352` (Cape)
    *   `$7EF354` (Titans Mitt)
    *   `$7EF359` (Sword level)
*   **Message Display**: Based on these checks, it calls `FortuneTeller_PrepareNextMessage` with the appropriate message index and then `FortuneTeller_DisplayMessage` to show the message to the player.

```asm
FortuneTeller_PerformPseudoScience:
#_0DC849: STZ.w $0DC0,X
#_0DC84C: INC.w $0D80,X
#_0DC84F: STZ.b $03
#_0DC851: LDA.l $7EF3D6
#_0DC855: CMP.b #$02
#_0DC857: BCS .map_icon_past_pendants
#_0DC859: STZ.b $00
#_0DC85B: STZ.b $01
#_0DC85D: JMP.w FortuneTeller_DisplayMessage

.map_icon_past_pendants
#_0DC860: LDA.l $7EF344
#_0DC864: BNE .have_shroom_or_powder
#_0DC866: LDA.b #$02
#_0DC868: JSR FortuneTeller_PrepareNextMessage
#_0DC86B: BCC .have_shroom_or_powder
#_0DC86D: JMP.w FortuneTeller_DisplayMessage

; ... (rest of the conditional item checks)
```

## Design Patterns
*   **Vanilla Override**: This file exemplifies how to directly modify and extend the behavior of existing vanilla NPCs through targeted code injection.
*   **Context-Sensitive Dialogue**: The Fortune Teller's messages are highly dynamic and personalized, adapting to Link's current inventory and game progression. This creates a more engaging and responsive NPC interaction.
*   **Quest Progression Tracking**: The routine extensively utilizes SRAM flags and item possession checks to track Link's progress through various quests and milestones, influencing the dialogue provided.
*   **Modular Message System**: The use of `FortuneTeller_PrepareNextMessage` and `FortuneTeller_DisplayMessage` allows for a structured and modular approach to managing and displaying NPC dialogue.
