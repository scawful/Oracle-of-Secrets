# Octoboss Sprite Analysis

## Overview
The `octoboss` sprite (ID: `Sprite_Octoboss`, which is `$3C`) is a multi-phase boss, likely an octopus-like creature. It features a unique mechanic involving a "brother" Octoboss, and can summon stalfos offspring. The fight progresses through distinct phases including emergence, movement, taunting, ascending, submerging, and a surrender sequence.

## Key Properties:
*   **Sprite ID:** `Sprite_Octoboss` (`$3C`)
*   **Description:** A multi-phase boss with a "brother" Octoboss, capable of summoning stalfos and engaging in various movement and attack patterns.
*   **Number of Tiles:** 11
*   **Health:** `00` (Health is managed by `ReturnTotalHealth` and `CheckForNextPhase`, combining the health of both Octobosses.)
*   **Damage:** `00` (Damage dealt to Link is likely handled by its attacks or spawned offspring.)
*   **Special Properties:**
    *   `!Boss = $01` (Correctly identified as a boss.)
    *   `!Shadow = 01` (Draws a shadow.)
    *   `!Hitbox = 03`

## Custom Variables:
*   `!ConsecutiveHits = $AC`: Tracks consecutive hits on the boss.
*   `!KydrogPhase = $7A`: Tracks the current phase of the boss fight. (Note: This variable name is `KydrogPhase`, suggesting shared logic or a copy-paste from the Kydrog boss.)
*   `!WalkSpeed = 10`: Defines the boss's walking speed.
*   `BrotherSpr = $0EB0`: Stores the sprite index of the "brother" Octoboss.

## Main Logic Flow (`Sprite_Octoboss_Main` and `Sprite_Octoboss_Secondary`):
The Octoboss has two primary main routines, `Sprite_Octoboss_Main` and `Sprite_Octoboss_Secondary`, which are called based on `SprMiscF, X`. This suggests different forms or behaviors for the two Octobosses.

**`Sprite_Octoboss_Main` Jump Table (for the primary Octoboss):**
*   **`WaitForPlayerToApproach` (0x00):** Waits for Link to reach a specific Y-coordinate (`$08C8`) to trigger activation.
*   **`Emerge` (0x01):** Emerges from the water, preventing Link's movement.
*   **`EmergedShowMessage` (0x02):** Displays an introductory message.
*   **`SpawnAndAwakeHisBrother` (0x03):** Spawns a "brother" Octoboss (`Sprite_Octoboss` with `SprMiscF = $01`) and stores its ID in `BrotherSpr`.
*   **`WaitForBrotherEmerge` (0x04):** Waits for the brother to emerge and displays a message.
*   **`SpawnPirateHats` (0x05):** Spawns "boss poof" effects for both Octobosses, changes their frames, and spawns walls using `Overworld_DrawMap16_Persist` macros.
*   **`IdlePhase` (0x06):** Idles, can spawn fireballs, and checks total health (`ReturnTotalHealth`) to potentially trigger surrender.
*   **`PickDirection` (0x07):** Picks a random direction and speed for movement.
*   **`Moving` (0x08):** Moves around, handles boundary checks, spawns splash effects, and checks total health to potentially trigger surrender.
*   **`WaitMessageBeforeSurrender` (0x09):** Displays a surrender message (`$004A`), sets the brother's action, and transitions to `RemoveHat`.
*   **`RemoveHat` (0x0A):** Removes hats from both Octobosses with "boss poof" effects, displays a message (`$004B`), and transitions to `Submerge`.
*   **`Submerge` (0x0B):** Submerges, playing an animation and spawning a splash effect.
*   **`SubmergeWaitWall` (0x0C):** Submerges further, drawing walls using `Overworld_DrawMap16_Persist` macros.
*   **`EmergeWaitGiveItem` (0x0D):** Emerges, spawns a medallion (`SpawnMedallion`), and sets an SRAM flag.
*   **`SubmergeForeverKill` (0x0E):** Submerges completely, despawns, and allows Link to move again.

**`Sprite_Octoboss_Secondary` Jump Table (for the secondary/brother Octoboss, when `SprMiscF, X` is set):**
This routine largely mirrors `Sprite_Octoboss_Main` but includes specific states like `WaitDialog` and `Moving2`, suggesting slight behavioral differences.

## Initialization (`Sprite_Octoboss_Long` and `Sprite_Octoboss_Prep`):
*   **`Sprite_Octoboss_Long`:** Main entry point. Handles sprite initialization, including setting OAM properties, bulletproofing, frame, and palette values. It also checks for boss defeat and medallion spawning.
*   **`Sprite_Octoboss_Prep`:** Initializes `!KydrogPhase` to `00`, sets initial health (`$A0`), configures deflection, hitbox, bump damage, and calls `JSR KydrogBoss_Set_Damage` to set up the damage table. Sets initial sprite speeds and an intro timer.

## Health Management (`Sprite_Octoboss_CheckIfDead`, `ReturnTotalHealth`, `CheckForNextPhase`):
*   **`Sprite_Octoboss_CheckIfDead`:** Monitors `SprHealth, X`. If health is zero or negative, it triggers the boss's death sequence.
*   **`ReturnTotalHealth`:** Calculates the combined health of both Octobosses (`SprHealth, X` and `SprHealth, Y` of `BrotherSpr`).
*   **`CheckForNextPhase`:** Manages the boss's phases based on health thresholds, similar to the Kydrog boss.

## Offspring Spawning (`RandomStalfosOffspring`, `Sprite_Offspring_Spawn`, `Sprite_Offspring_SpawnHead`):
*   These routines are identical to those found in `kydrog_boss.asm`, spawning stalfos offspring.

## Attacks (`Chuchu_SpawnBlast`, `Mothula_SpawnBeams`, `Kydrog_ThrowBoneAtPlayer`):
*   **`Chuchu_SpawnBlast`:** Spawns a Chuchu blast projectile.
*   **`Mothula_SpawnBeams`:** Spawns beam projectiles.
*   **`Kydrog_ThrowBoneAtPlayer`:** Spawns a bone projectile (reused from Kydrog).

## Drawing (`Sprite_Octoboss_Draw`, `Sprite_Octoboss_Draw2`):
*   **`Sprite_Octoboss_Draw`:** Draws the primary Octoboss.
*   **`Sprite_Octoboss_Draw2`:** Draws the secondary/brother Octoboss.
*   Both use standard OAM allocation routines and handle complex animation frames, offsets, character data, properties, and sizes.

## Other Routines:
*   **`SpawnSplash`:** Spawns a splash effect.
*   **`SpawnBossPoof`:** Spawns a boss poof effect.
*   **`HandleMovingSplash`:** Handles splash effects during movement.
*   **`SpawnMedallion` / `SpawnMedallionAlt`:** Spawns a medallion.

## Discrepancies/Notes:
*   **Shared Variables/Code with Kydrog:** The extensive use of `!KydrogPhase`, `KydrogBoss_Set_Damage`, and `Kydrog_ThrowBoneAtPlayer` suggests significant code reuse or copy-pasting from the Kydrog boss. This could lead to unexpected interactions or make maintenance challenging if changes are made to one boss but not the other. Refactoring shared logic into common functions or macros would be beneficial.
*   **`Sprite_Octoboss_Secondary`:** The existence of a separate main routine for the "brother" Octoboss indicates that the two Octobosses might have slightly different behaviors or phases.

## Hardcoded Activation Trigger:
*   As noted by the user, the activation trigger for Octoboss is hardcoded. In the `WaitForPlayerToApproach` routine, the boss checks `LDA.b $20 : CMP #$08C8`. `$20` represents Link's Y position, and `$08C8` is a hardcoded Y-coordinate. This means the boss will only activate when Link reaches this specific Y-coordinate, making it difficult to relocate the boss to other overworld maps without modifying this value. This hardcoded dependency needs to be addressed for improved reusability.
