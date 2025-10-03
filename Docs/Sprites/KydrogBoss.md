# Kydrog Boss Sprite Analysis

## Overview
The `kydrog_boss` sprite (ID: `Sprite_KydrogBoss`, which is `$CB`) represents the main Kydrog boss. This boss features multiple phases, dynamic movement, and the ability to summon stalfos offspring. It's a complex encounter designed to challenge the player through varied attack patterns and phase transitions.

## Key Properties:
*   **Sprite ID:** `Sprite_KydrogBoss` (`$CB`)
*   **Description:** The main Kydrog boss, controlling its own movement, phases, and spawning stalfos offspring.
*   **Number of Tiles:** 11
*   **Health:** `00` (The boss's health is managed through `CheckForNextPhase` and `Sprite_KydrogBoss_CheckIfDead`, not directly by this property.)
*   **Damage:** `00` (Damage dealt to Link is likely handled by its attacks or spawned offspring.)
*   **Special Properties:**
    *   `!Boss = $01` (Correctly identified as a boss.)
    *   `!Shadow = 01` (Draws a shadow.)
    *   `!Hitbox = 03`

## Custom Variables:
*   `!ConsecutiveHits = $AC`: Tracks consecutive hits on the boss, influencing its behavior.
*   `!KydrogPhase = $7A`: Manages the current phase of the boss fight.
*   `!WalkSpeed = 10`: Defines the boss's walking speed.

## Main States/Actions (`Sprite_KydrogBoss_Main` Jump Table):
The boss's behavior is governed by a detailed state machine:
*   **`KydrogBoss_Init` (0x00):** Initial state, plays an "Arms Crossed" animation, and transitions to `KydrogBoss_WalkState` after an intro timer.
*   **`KydrogBoss_WalkState` (0x01):** The primary walking state. Manages phase transitions, handles damage, taunting, and determines the next walking direction (forward, backward, left, right) based on Link's position and proximity.
*   **`KydrogBoss_WalkForward` (0x02), `KydrogBoss_WalkLeft` (0x03), `KydrogBoss_WalkRight` (0x04), `KydrogBoss_WalkBackward` (0x05):** These states handle movement in specific directions, playing corresponding animations and executing core movement logic.
*   **`KydrogBoss_TakeDamage` (0x06):** Manages the boss taking damage. Increments `!ConsecutiveHits`, plays a damage animation, spawns stalfos offspring, and can trigger an ascend action.
*   **`KydrogBoss_TauntPlayer` (0x07):** Plays a taunting animation, handles damage, and transitions to `KydrogBoss_SummonStalfos`.
*   **`KydrogBoss_SummonStalfos` (0x08):** Plays a summoning animation, handles damage, spawns stalfos offspring, and can throw a bone projectile at Link.
*   **`KydrogBoss_Death` (0x09):** Handles the boss's death sequence, including killing spawned friends, playing a flickering animation, and despawning.
*   **`KydrogBoss_Ascend` (0x0A):** The boss ascends off-screen, increasing its `SprHeight` and spawning stalfos offspring. Transitions to `KydrogBoss_Descend`.
*   **`KydrogBoss_Descend` (0x0B):** The boss descends, tracking Link's position, decreasing its `SprHeight`, and spawning stalfos offspring. Transitions back to `KydrogBoss_WalkState`.
*   **`KydrogBoss_Abscond` (0x0C):** The boss moves away from Link, increasing its speed, and transitions back to `KydrogBoss_WalkState`.

## Initialization (`Sprite_KydrogBoss_Prep`):
*   Initializes `!KydrogPhase` to `00`.
*   Sets initial health to `$A0` (160 decimal).
*   Configures deflection (`SprDefl`), hitbox (`SprHitbox`), and bump damage (`SprBump`).
*   Sets `SprGfxProps` to not invincible.
*   Calls `JSR KydrogBoss_Set_Damage` to define its damage vulnerabilities.
*   Sets initial sprite speeds and `!Harmless = 00`.
*   Sets an intro timer (`SprTimerD = $80`).

## Death Check (`Sprite_KydrogBoss_CheckIfDead`):
*   Monitors `SprHealth, X`. If health is zero or negative, it triggers the boss's death sequence, setting `SprState = $04` (kill sprite boss style) and `SprAction = $09` (KydrogBoss_Death stage).

## Phase Management (`CheckForNextPhase`):
This routine dynamically manages the boss's phases based on its current health:
*   **Phase One (`!KydrogPhase = $00`):** Transitions to Phase Two when health drops below `$20`.
*   **Phase Two (`!KydrogPhase = $01`):** Transitions to Phase Three when health drops below `$20`. Resets health to `$80`, sets action to `KydrogBoss_WalkState`, and increments `SprFlash, X`.
*   **Phase Three (`!KydrogPhase = $02`):** Transitions to Phase Four when health drops below `$20`. Resets health to `$80`, sets action to `KydrogBoss_WalkState`.
*   **Phase Four (`!KydrogPhase = $03`):** Sets action to `KydrogBoss_WalkState`.

## Damage Table (`KydrogBoss_Set_Damage`):
*   Defines how KydrogBoss reacts to various attack types (Boomerang, Sword, Arrow, Bomb, etc.), stored in a damage properties table.

## Offspring Spawning (`RandomStalfosOffspring`, `Sprite_Offspring_Spawn`, `Sprite_Offspring_SpawnHead`):
*   **`RandomStalfosOffspring`:** Randomly spawns either a normal stalfos offspring (`Sprite_Offspring_Spawn`) or a stalfos head offspring (`Sprite_Offspring_SpawnHead`), with a limit of 4 active stalfos.
*   **`Sprite_Offspring_Spawn`:** Spawns a stalfos offspring (Sprite ID `$A7` or `$85`).
*   **`Sprite_Offspring_SpawnHead`:** Spawns a stalfos head offspring (Sprite ID `$7C` or `$02`).

## Attacks (`Kydrog_ThrowBoneAtPlayer`):
*   **`Kydrog_ThrowBoneAtPlayer`:** Spawns a bone projectile (Sprite ID `$A7`) that moves towards Link.

## Movement (`KydrogBoss_DoMovement`, `BounceBasedOnPhase`):
*   **`KydrogBoss_DoMovement`:** Handles damage checks, applies damage to Link on contact, flashes when damaged, and incorporates phase-based bouncing and stalfos spawning.
*   **`BounceBasedOnPhase`:** Adjusts the boss's bounce speed based on the current `!KydrogPhase`.

## Drawing (`Sprite_KydrogBoss_Draw`):
*   Uses standard OAM allocation routines.
*   Handles complex animation frames, x/y offsets, character data, properties, and sizes for drawing the boss.
*   Utilizes 16-bit operations (`REP #$30`, `SEP #$30`) for precise drawing calculations.

## Other Routines:
*   **`StopIfTooClose()` macro:** Prevents the boss from getting too close to Link.
*   **`Sprite_CheckIfFrozen`:** Checks if the sprite is frozen and unfreezes it after a timer.
*   **`GetNumberSpawnStalfos`:** Counts the number of active stalfos offspring.
*   **`SpawnSplash`:** Spawns a splash effect.
*   **`SpawnBossPoof`:** Spawns a boss poof effect.
*   **`HandleMovingSplash`:** Handles splash effects during movement.
*   **`SpawnMedallion` / `SpawnMedallionAlt`:** Spawns a medallion.

## Discrepancies/Notes:
*   The main boss's health is intricately managed through `SprHealth, X` and `!KydrogPhase`, requiring a clear understanding of their interplay.
*   The stalfos offspring are spawned using specific sprite IDs, which should be cross-referenced for full understanding.
*   Many hardcoded values for timers, speeds, and offsets could be replaced with named constants for improved readability and maintainability.
*   The code includes direct calls to sound effect functions (`JSL $0DBB8A`) and a commented-out call to `JSL $01F3EC` (Light Torch), which might be a leftover or an unimplemented feature.

## Hardcoded Activation Trigger:
*   As noted by the user, the activation trigger for KydrogBoss is hardcoded. Specifically, in the `WaitForPlayerToApproach` routine, the boss checks `LDA.b $20 : CMP #$08C8`. `$20` represents Link's Y position, and `$08C8` is a hardcoded Y-coordinate. This means the boss will only activate when Link reaches this specific Y-coordinate, making it difficult to relocate the boss to other overworld maps without modifying this value.