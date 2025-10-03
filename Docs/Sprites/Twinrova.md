# Twinrova Boss Sprite Analysis

## Overview
The `twinrova` sprite (ID: `Sprite_Twinrova`, which is `$CE`) is a complex, multi-phase boss designed to override the vanilla Blind and Blind Maiden sprites. It features a dramatic transformation from Blind Maiden into Twinrova, followed by alternating phases where Twinrova switches between Koume (fire) and Kotake (ice) forms, each possessing distinct attacks and environmental interactions.

## Key Properties:
*   **Sprite ID:** `Sprite_Twinrova` (`$CE`)
*   **Description:** A multi-phase boss that transforms from Blind Maiden, then alternates between fire (Koume) and ice (Kotake) forms.
*   **Number of Tiles:** 6
*   **Health:** `00` (Health is managed by `Sprite_Twinrova_CheckIfDead` and phase transitions.)
*   **Damage:** `00` (Damage dealt to Link is likely handled by its attacks.)
*   **Special Properties:**
    *   `!Boss = 01` (Correctly identified as a boss.)
    *   `!Shadow = 01` (Draws a shadow.)
    *   `!Hitbox = 03`
    *   `!CollisionLayer = 01` (Checks both layers for collision.)

## Custom Variables/Macros:
*   `!AnimSpeed = 8`: Defines the animation speed for various states.
*   `Twinrova_Front()`, `Twinrova_Back()`, `Twinrova_Ready()`, `Twinrova_Attack()`, `Show_Koume()`, `Show_Kotake()`, `Twinrova_Hurt()`: Macros for playing specific animations, enhancing code readability.
*   `$AC`: A RAM address used to store the current attack type (Fire or Ice).

## Main Logic Flow (`Sprite_Twinrova_Main`):
The boss's behavior is governed by a detailed state machine:
*   **`Twinrova_Init` (0x00):** Initial state. Displays an introductory message and transitions to `Twinrova_MoveState`.
*   **`Twinrova_MoveState` (0x01):** The core movement and phase management state. It checks `SprHealth, X` to determine if Twinrova is in Phase 1 (single entity) or Phase 2 (alternating forms).
    *   **Phase 1:** Twinrova moves around, randomly spawning Fire/Ice Keese, or preparing Fire/Ice attacks.
    *   **Phase 2:** Twinrova alternates between `Twinrova_KoumeMode` (fire) and `Twinrova_KotakeMode` (ice) forms.
*   **`Twinrova_MoveForwards` (0x02), `Twinrova_MoveBackwards` (0x03):** Handles movement using `Sprite_FloatTowardPlayer` and `Sprite_CheckTileCollision`.
*   **`Twinrova_PrepareAttack` (0x04):** Prepares either a Fire or Ice attack based on the value in `$AC`.
*   **`Twinrova_FireAttack` (0x05):** Executes a Fire attack. Restores floor tiles, uses `JSL Sprite_Twinrova_FireAttack` (a shared function for the actual attack), and randomly releases fireballs (`ReleaseFireballs`).
*   **`Twinrova_IceAttack` (0x06):** Executes an Ice attack using `JSL Sprite_Twinrova_IceAttack` (a shared function).
*   **`Twinrova_Hurt` (0x07):** Manages Twinrova taking damage. Plays a hurt animation and, after a timer, determines whether to dodge or retaliate with a fire or ice attack.
*   **`Twinrova_KoumeMode` (0x08):** Koume (fire) form. Spawns pit hazards (`AddPitHazard`), falling tiles (`Ganon_SpawnFallingTilesOverlord`), and fireballs (`Sprite_SpawnFireball`). Uses `RageModeMove` for dynamic movement.
*   **`Twinrova_KotakeMode` (0x09):** Kotake (ice) form. Can spawn lightning (`JSL $1DE612`) and uses `RageModeMove` for dynamic movement.
*   **`Twinrova_Dead` (0x0A):** Handles Twinrova's death sequence, killing all spawned friends and playing a hurt animation.

## Initialization (`Sprite_Twinrova_Prep`):
*   Checks for the presence of the Blind Maiden (`$7EF3CC = $06`). If the Maiden is present, Twinrova is killed, indicating that Twinrova spawns *from* the Blind Maiden.
*   Sets initial health to `$5A` (90 decimal).
*   Configures deflection (`SprDefl = $80`), bump damage (`SprBump = $04`), and ensures Twinrova is not invincible.
*   Configures Blind Boss startup parameters and initializes various timers and `SprMisc` variables.

## Death Check (`Sprite_Twinrova_CheckIfDead`):
*   Monitors `SprHealth, X`. If health is zero or negative, it triggers the boss's death sequence, setting `SprState = $04` (kill sprite boss style) and `SprAction = $0A` (Twinrova_Dead stage).

## Movement (`RageModeMove`, `DoRandomStrafe`, `VelocityOffsets`):
*   **`RageModeMove`:** A sophisticated routine for dynamic, floaty movement. It randomly determines a movement mode (predictive movement towards player, random strafe, random dodge, stay in place) based on timers and probabilities. It also handles evasive actions.
*   **`DoRandomStrafe`:** Generates random strafing movement.
*   **`VelocityOffsets`:** A table defining X and Y speed offsets for movement.

## Environmental Interactions (`Twinrova_RestoreFloorTile`, `RestoreFloorTile`, `AddPitHazard`, `Ganon_SpawnFallingTilesOverlord`):
*   **`Twinrova_RestoreFloorTile` / `RestoreFloorTile`:** Restores floor tiles, likely after they have been modified by an attack.
*   **`AddPitHazard`:** Adds a pit hazard to the floor.
*   **`Ganon_SpawnFallingTilesOverlord`:** Spawns falling tiles (reused from Ganon's mechanics).

## Drawing (`Sprite_Twinrova_Draw`):
*   Uses standard OAM allocation routines.
*   Handles complex animation frames, x/y offsets, character data, properties, and sizes for drawing Twinrova.
*   Utilizes 16-bit operations for precise drawing calculations.

## Graphics Transfer (`ApplyTwinrovaGraphics`):
*   Handles DMA transfer of graphics data (`twinrova.bin`) to VRAM.

## Attack Spawning (`Fireball_Configure`, `ReleaseFireballs`, `Sprite_SpawnFireKeese`, `Sprite_SpawnIceKeese`, `JSL Sprite_SpawnFireball`, `JSL $1DE612` (Sprite_SpawnLightning)):
*   Twinrova can spawn various projectiles and enemies, including fireballs, Fire Keese, Ice Keese, and lightning.

## Blind Maiden Integration:
Twinrova's fight is deeply integrated with the Blind Maiden mechanics:
*   **`Follower_BasicMover`:** This routine is hooked to check if the follower is the Blind Maiden, triggering the transformation to Twinrova.
*   **`Follower_CheckBlindTrigger`:** Checks if the Blind Maiden follower is within a specific trigger area.
*   **`Blind_SpawnFromMaiden`:** This is the core routine for the transformation. It applies Twinrova graphics, sets Twinrova's initial state and position based on the Maiden's, and sets various timers and properties.
*   **`SpritePrep_Blind_PrepareBattle`:** This routine is overridden to handle Twinrova's prep or to despawn if a room flag is set.

## Discrepancies/Notes:
*   **Health Management:** The `!Health` property is `00`. The boss's health is managed by `Sprite_Twinrova_CheckIfDead` and phase transitions.
*   **Code Reuse:** There is extensive code reuse from other sprites/bosses (e.g., `Sprite_Twinrova_FireAttack` is also used by KydreeokHead, `Ganon_SpawnFallingTilesOverlord` in Koume mode, `Sprite_SpawnFireKeese`/`Sprite_SpawnIceKeese` in MoveState). This is an efficient practice but requires careful management to ensure thematic consistency and avoid unintended side effects.
*   **Hardcoded Addresses:** Several `JSL` calls are to hardcoded addresses (e.g., `JSL $1DE612` for lightning). These should ideally be replaced with named labels for better maintainability.
*   **Blind Maiden Overrides:** The boss heavily relies on overriding vanilla Blind Maiden behavior, which is a common ROM hacking technique but requires careful understanding of the original game's code.
*   **`TargetPositions`:** This table is defined but appears unused in the provided code.
