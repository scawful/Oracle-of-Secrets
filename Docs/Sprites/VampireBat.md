# Vampire Bat Mini-Boss Sprite Analysis

## Overview
The `vampire_bat` sprite is a mini-boss, a specialized enemy that utilizes the generic Keese sprite ID (`$11`) but differentiates its behavior through `SprSubtype = 02`. It features more complex movement patterns and attacks compared to a standard Keese, including ascending, flying around, descending, and spawning other Keese.

## Key Properties:
*   **Sprite ID:** `0x11` (Custom Keese Subtype 02)
*   **Description:** A mini-boss variant of the Keese, with enhanced movement and attack capabilities.
*   **Number of Tiles:** 8 (Inherited from the base Keese sprite.)
*   **Health:** `32` (decimal, set in `Sprite_Keese_Prep` based on subtype.)
*   **Damage:** `00` (Damage dealt to Link is likely handled by its attacks.)
*   **Special Properties:**
    *   `!Boss = 00` (Not marked as a boss, but functions as a mini-boss/special enemy.)
    *   `!Shadow = 01` (Draws a shadow.)

## Main Logic Flow (`Sprite_VampireBat_Main`):
The Vampire Bat's behavior is governed by a state machine:
*   **`VampireBat_Idle` (0x00):** Waits for Link to approach within a specified distance (`$24`). Transitions to `VampireBat_Ascend`.
*   **`VampireBat_Ascend` (0x01):** Plays an ascending animation, increases its `SprHeight` to `$50`, and randomly spawns a Fire Keese (`Sprite_SpawnFireKeese`). Transitions to `VampireBat_FlyAround`.
*   **`VampireBat_FlyAround` (0x02):** Plays a flying animation, moves towards Link (`Sprite_ProjectSpeedTowardsPlayer`), and randomly selects new directions (`Sprite_SelectNewDirection`). Transitions to `VampireBat_Descend` after a timer.
*   **`VampireBat_Descend` (0x03):** Plays a descending animation, decreases its `SprHeight` until it's on the ground, and randomly uses `Sprite_Twinrova_FireAttack`. Transitions back to `VampireBat_Idle` after a timer.

## Initialization (from `Sprite_Keese_Prep` in `keese.asm`):
The Vampire Bat does not have its own `_Prep` routine and relies on the generic `Sprite_Keese_Prep` routine in `keese.asm`. When `SprSubtype = 02`:
*   `SprHealth` is set to `$20` (32 decimal).
*   `SprDefl` is set to `$80`.
*   `SprTimerC` is set to `$30`.

## Drawing (`Sprite_VampireBat_Draw`):
*   This routine is called from `Sprite_Keese_Long` in `keese.asm` when `SprSubtype = 02`.
*   Uses standard OAM allocation routines.
*   Handles animation frames, x/y offsets, character data, properties, and sizes specific to the Vampire Bat's appearance.

## Attack Spawning (`Sprite_SpawnFireKeese`, `Sprite_SpawnIceKeese`):
*   **`Sprite_SpawnFireKeese`:** Spawns a Keese sprite (`$11`) with `SprSubtype = $01` (Fire Keese).
*   **`Sprite_SpawnIceKeese`:** Spawns a Keese sprite (`$11`) with `SprSubtype = $00` (Ice Keese).

## Interactions:
*   **Damage:** Responds to damage from Link, including flashing and bouncing from tile collisions.
*   **Attacks:** Can spawn Fire Keese and utilize `Sprite_Twinrova_FireAttack` (a shared attack function).

## Discrepancies/Notes:
*   **Shared Sprite ID:** The Vampire Bat efficiently reuses the generic Keese sprite ID (`$11`), with `SprSubtype = 02` serving as the primary differentiator for its unique behavior.
*   **Health Management:** Its health is configured within the generic `Sprite_Keese_Prep` routine based on its subtype.
*   **Code Reuse:** It reuses `Sprite_Twinrova_FireAttack`, demonstrating efficient code sharing across different boss/mini-boss sprites.
*   **Hardcoded Values:** Many numerical values for timers, speeds, and offsets are hardcoded. Replacing these with named constants would improve readability and maintainability.
