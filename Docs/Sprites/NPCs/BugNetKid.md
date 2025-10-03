# Bug Net Kid (Sick Kid)

## Overview
The Bug Net Kid, also referred to as the Sick Kid, is an NPC sprite that plays a role in a quest involving the "Song of Healing" and the acquisition of the Boots (referred to as Bug Net in the comments). This sprite is implemented by overriding vanilla game code to introduce custom interactions and progression.

## Vanilla Overrides
This sprite extensively uses `pushpc`/`pullpc` blocks and `org` directives to inject custom logic into existing vanilla routines. This approach allows for modifying the behavior of a vanilla NPC without creating a new sprite ID.

*   **`org $068D7F`**: Overrides the vanilla `SpritePrep_SickKid` routine.
*   **`org $06B962`**: Overrides a routine related to the kid's resting state (`BugNetKid_Resting`).
*   **`org $06B9C6`**: Overrides a routine responsible for granting the item (`BugNetKid_GrantBugNet`).

## `SickKid_CheckForSongOfHealing`
This routine is a core component of the Bug Net Kid's logic. It checks if the "Song of Healing" has been played by examining a `SongFlag` (likely a WRAM address like `$7E001F`). If the song has been played, it updates internal sprite state variables (`$0D80, X`, `$02E4`) and clears the `SongFlag`.

```asm
SickKid_CheckForSongOfHealing:
{
  LDA.b SongFlag : CMP.b #$01 : BNE .no_song
    INC $0D80, X
    INC $02E4
    STZ.b SongFlag
  .no_song
  RTL
}
```

## `SpritePrep_SickKid` (Initialization)
This routine is executed when the Sick Kid sprite is initialized. It checks an SRAM flag (`$7EF355`) to determine if Link has already obtained the Boots. If so, it sets `$0D80, X` to `$03`. It also increments `SprBulletproof, X`, making the kid invulnerable to attacks.

```asm
SpritePrep_SickKid:
{
  LDA.l $7EF355 : BEQ .no_boots
    LDA.b #$03 : STA $0D80, X
  .no_boots
  INC.w SprBulletproof, X
  RTS
}
```

## `BugNetKid_Resting` (Main Logic)
This routine controls the kid's behavior when not actively granting an item. It checks for player preoccupation and damage, and crucially, calls `SickKid_CheckForSongOfHealing`. If Link has not yet received the Boots, it displays a solicited message to the player.

```asm
BugNetKid_Resting:
{
  JSL Sprite_CheckIfPlayerPreoccupied : BCS .dont_awaken
    JSR Sprite_CheckDamageToPlayer_same_layer : BCC .dont_awaken
      JSL SickKid_CheckForSongOfHealing
        LDA.l $7EF355
        CMP.b #$01 : BCC .no_boots
  .dont_awaken
  RTS

    .no_boots
    LDA.b #$04
    LDY.b #$01
    JSL Sprite_ShowSolicitedMessageIfPlayerFacing
    RTS
}
```

## `BugNetKid_GrantBugNet` (Item Granting)
This routine is responsible for giving Link the Boots. It sets the item ID (`LDY.b #$4B`), clears a flag (`$02E9`), calls `JSL Link_ReceiveItem` to add the item to Link's inventory, and updates internal sprite state variables (`$0D80, X`, `$02E4`).

```asm
BugNetKid_GrantBugNet:
{
  ; Give Link the Boots
  LDY.b #$4B
  STZ $02E9
  PHX
  JSL Link_ReceiveItem
  PLX
  INC $0D80, X
  STZ $02E4
  RTS
}
```

## Design Patterns
*   **Vanilla Override**: This sprite is a prime example of overriding vanilla game code to introduce new NPC interactions and quest elements without creating entirely new sprite definitions.
*   **Quest/Item Gating**: The sprite's behavior and the ability to receive the Boots are directly tied to specific game progression flags, such as the `SongFlag` and the SRAM flag for the Boots (`$7EF355`).
*   **NPC Interaction**: The sprite interacts with the player by displaying messages and granting a key item, driving forward a specific questline.
*   **Global Flags and SRAM Usage**: Utilizes global WRAM flags (`$02E4`, `SongFlag`) and SRAM (`$7EF355`) to maintain and track the state of the quest across game sessions.
