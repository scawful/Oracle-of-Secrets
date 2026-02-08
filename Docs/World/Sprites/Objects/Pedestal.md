# Pedestal (Magic Pedestal Plaque)

## Overview
The `pedestal.asm` file defines the custom behavior for a "Magic Pedestal" sprite, which is an interactive object that responds to Link's actions. This implementation overrides a vanilla pedestal plaque sprite (`Sprite_B3_PedestalPlaque`) to trigger specific game events based on Link's inventory, input, and the current `AreaIndex`.

## Vanilla Overrides
*   **`org $1EE05F`**: Injects `JSL CheckForBook` into the `Sprite_B3_PedestalPlaque` routine. This means the custom logic defined in `CheckForBook` will execute when the vanilla pedestal plaque sprite is processed.

## `CheckForBook`
This routine is the primary entry point for the custom pedestal logic. It checks several conditions to determine if Link is interacting with the pedestal in a specific way:

*   **Link's Action**: Checks `$2F` (Link's current action/state).
*   **Player Contact**: Checks for damage to player (`JSL Sprite_CheckDamageToPlayer`), which in this context likely means Link is in contact with the pedestal.
*   **Item Held**: Checks if Link is holding a specific item (`$0202` compared to `$0F`, which likely corresponds to a book item).
*   **Player Input**: Checks if Link is pressing the Y button (`BIT.b $F4`).
*   **State Manipulation**: If Link is holding the book and pressing Y, it sets `$0300` to `0`, `$037A` to `$20`, and `$012E` to `0` (these are likely related to Link's animation or state changes).
*   **Event Trigger**: Calls `JSR PedestalPlaque` to execute area-specific logic.

```asm
CheckForBook:
{
  LDA.b $2F : BNE .exit
    JSL Sprite_CheckDamageToPlayer : BCC .exit
      LDA.w $0202 : CMP.b #$0F : BNE .not_holding_book
        LDY.b #$01 : BIT.b $F4 : BVS .not_pressing_y
      .not_holding_book
        LDY.b #$00
        .not_pressing_y
        CPY.b #$01 : BNE .no_book_pose
          STZ.w $0300
          LDA.b #$20
          STA.w $037A
          STZ.w $012E
        .no_book_pose
      JSR PedestalPlaque
  .exit
  LDA.b AreaIndex : CMP.b #$30
  RTL
}
```

## `PedestalPlaque`
This routine contains the area-specific logic for the pedestal, triggering different events based on the current `AreaIndex`:

*   **Zora Temple (`AreaIndex = $1E`)**: Checks a flag (`$7EF29E` bit `$20`) and `SongFlag` (`$03`). If specific conditions are met (e.g., a certain event has not occurred and a particular song has been played), it sets `$04C6` to `$01` (likely a flag to open a gate or trigger an event) and clears `SongFlag`.
*   **Goron Desert (`AreaIndex = $36`)**: No specific logic defined in this file.
*   **Fortress Secrets (`AreaIndex = $5E`)**: No specific logic defined in this file.

```asm
PedestalPlaque:
{
  LDA.b AreaIndex : CMP.b #$1E : BEQ .zora_temple
                    CMP.b #$36 : BEQ .goron_desert
                    CMP.b #$5E : BEQ .fortress_secrets
                      JMP .return
  .zora_temple

    LDA.l $7EF29E : AND.b #$20 : BNE .return
      LDA.b SongFlag : CMP.b #$03 : BNE .return
        LDA.b #$01 : STA $04C6
        STZ.b SongFlag
        JMP .return
  .goron_desert

  .fortress_secrets

  .return
  RTS
}
```

## Design Patterns
*   **Vanilla Override**: This file directly modifies the vanilla pedestal plaque sprite to implement custom interactive behavior, demonstrating how to integrate new puzzle mechanics into existing game elements.
*   **Context-Sensitive Interaction**: The pedestal responds specifically when Link is holding a particular item (a book) and pressing a button, creating a unique and logical interaction for puzzle solving.
*   **Quest Progression Integration**: The pedestal triggers events based on the `AreaIndex` and various game state flags (e.g., `SongFlag`, `$7EF29E`), indicating its role in advancing specific quests and unlocking new areas.
*   **Game State Manipulation**: Directly modifies WRAM addresses (`$04C6`, `SongFlag`) to trigger game events, such as opening gates or clearing flags, which are crucial for puzzle resolution and progression.
