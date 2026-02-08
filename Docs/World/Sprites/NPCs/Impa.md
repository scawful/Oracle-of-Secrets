# Impa (Zelda)

## Overview
The `impa.asm` file is not a complete sprite definition but rather a collection of routines and vanilla overrides that modify the behavior of the character Impa (or Zelda, as indicated by some labels). Its primary purpose is to manage spawn points and manipulate game state during critical events, likely cutscenes or key progression points within the game.

## Spawn Point Definitions
The file defines a WRAM address `SPAWNPT = $7EF3C8` for a spawn point flag, along with comments detailing various spawn point IDs:

*   `0x00` - Link's house
*   `0x01` - Sanctuary (Hall of Secrets)
*   `0x02` - Castle Prison
*   `0x03` - Castle Basement
*   `0x04` - Throne
*   `0x05` - Old man cave
*   `0x06` - Old man home

## `Impa_SetSpawnPointFlag`
This routine is responsible for setting a specific spawn point flag. It stores a value into `$7EF372` (likely the actual spawn point ID) and then sets bit `$04` in `$7EF3D6` (a custom progression flag), indicating that a particular event has occurred.

```asm
Impa_SetSpawnPointFlag:
{
  STA.l $7EF372
  LDA.l $7EF3D6 : ORA.b #$04 : STA.l $7EF3D6
  RTL
}
```

## Vanilla Overrides
This file extensively uses `pushpc`/`pullpc` blocks and `org` directives to inject custom code into specific vanilla routines, thereby altering the game's default behavior:

*   **`org $05EE46` (`Zelda_AtSanctuary`)**: Injects `JSL Impa_SetSpawnPointFlag`. This modification ensures that when Zelda (or Impa) is at the Sanctuary, a specific spawn point flag is set, influencing where Link might respawn or transition.
*   **`org $05EBCF`**: Modifies a comparison involving `$7EF359` (likely Link's Sword level) with `$05`. This is noted as a `TODO`, suggesting it's an incomplete or placeholder modification.
*   **`org $029E2E` (`Module15_0C`)**: Modifies an overlay that Impa activates after the intro sequence. It sets bit `$20` in `$7EF2A3` (likely an overlay control flag), potentially changing the visual environment.
*   **`org $05ED43` (`Zelda_BecomeFollower`)**: Prevents Impa from setting a spawn point by clearing `$02E4` and `$7EF3C8`. This suggests a custom handling of Impa's follower state.
*   **`org $05ED63`**: NOPs out 5 bytes, effectively disabling some vanilla code at this address.
*   **`org $05ED10` (`Zelda_ApproachHero`)**: NOPs out 5 bytes, preventing Impa from changing the game's background music or sound, indicating custom control over audio during this event.

## Design Patterns
*   **Vanilla Override**: This file is a prime example of how to extensively override vanilla code to integrate custom NPC behaviors and progression systems into an existing game.
*   **Quest Progression Tracking**: Utilizes custom progression flags (`$7EF3D6`) and spawn point flags (`$7EF372`, `$7EF3C8`) to meticulously track key events and the player's progress through the game's narrative.
*   **Game State Manipulation**: Directly modifies WRAM addresses to control various aspects of the game, such as visual overlays and audio, providing fine-grained control over the player's experience.
*   **Modular Code Injection**: The use of `org` directives allows for precise injection of custom routines into specific points of the vanilla codebase, enabling targeted modifications without disrupting unrelated functionality.
