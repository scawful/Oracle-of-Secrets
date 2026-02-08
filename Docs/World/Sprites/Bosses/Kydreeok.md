# Kydreeok Sprite Analysis

## Overview
The `kydreeok` sprite (ID: `Sprite_Kydreeok`, which is `$7A`) represents the main Kydreeok boss. It orchestrates the entire boss fight, including spawning and managing its child head sprites (`kydreeok_head`), controlling its own movement phases, and handling its overall defeat. This is a multi-headed boss where the heads are separate sprites.

## Key Properties:
*   **Sprite ID:** `Sprite_Kydreeok` (`$7A`)
*   **Description:** The main Kydreeok boss, controlling the overall fight and its child heads.
*   **Number of Tiles:** 8
*   **Health:** `00` (The boss's health is managed through its child heads and custom logic, not directly by this sprite's `!Health` property.)
*   **Damage:** `00` (Damage dealt to Link is likely handled by its heads or custom logic.)
*   **Special Properties:**
    *   `!Boss = 01` (This sprite is correctly identified as a boss.)
    *   `!Hitbox = $07`

## Main States/Actions (`Sprite_Kydreeok_Main` Jump Table):
The boss's behavior is divided into several phases:
*   **`Kydreeok_Start` (0x00):** Initial state. Applies graphics and palette, prevents Link from passing through, and transitions to `Kydreeok_StageControl` after a timer. Stores its own sprite index in `Kydreeok_Id`.
*   **`Kydreeok_StageControl` (0x01):** Manages the boss's movement stage, setting velocities and checking boundaries.
*   **`Kydreeok_MoveXandY` (0x02):** Moves the boss in both X and Y directions towards Link, checking boundaries and handling damage.
*   **`Kydreeok_MoveXorY` (0x03):** Moves the boss in either X or Y direction towards Link, checking boundaries and handling damage.
*   **`Kydreeok_KeepWalking` (0x04):** Continues walking, with a random chance to transition to a flying state.
*   **`Kydreeok_Dead` (0x05):** Handles the boss's death sequence, including visual effects (flickering, explosions) and eventually despawning the sprite.
*   **`Kydreeok_Flying` (0x06):** The boss enters a flying state, moving towards Link at a set height, checking boundaries and handling damage.

## Initialization (`Sprite_Kydreeok_Prep`):
*   Sets initial timers and movement speeds.
*   Caches its own origin position.
*   **Spawns its child heads:** Calls `JSR SpawnLeftHead` and `JSR SpawnRightHead`. A `SpawnCenterHead` routine is commented out, suggesting a potential for a three-headed boss.
*   Initializes neck offsets to zero.
*   Applies a custom palette (`JSR ApplyPalette`).
*   Sets the boss theme music.

## Death and Respawn Logic (`Sprite_Kydreeok_CheckIfDead`, `MaybeRespawnHead`):
*   **`Sprite_Kydreeok_CheckIfDead`:** This crucial routine checks the state of its child heads (`Offspring1_Id`, `Offspring2_Id`). If both heads are defeated, it triggers a "dead" phase, changes its graphics, respawns both heads, and then transitions to the `Kydreeok_Dead` state. This indicates a multi-phase boss where heads can be temporarily defeated.
*   **`MaybeRespawnHead`:** Randomly respawns a head if its corresponding child sprite is dead, adding a dynamic challenge to the fight.

## Head Spawning (`SpawnLeftHead`, `SpawnRightHead`):
*   These routines spawn `Sprite_KydreeokHead` (`$CF`) sprites.
*   They assign `SprSubtype` to the spawned heads (`$00` for left, `$01` for right), allowing the child sprites to differentiate their behavior.
*   They store the IDs of the spawned heads in global variables (`Offspring1_Id`, `Offspring2_Id`).
*   They set the initial position of the heads relative to the main boss and initialize neck segment coordinates.

## Movement (`MoveBody`, `StopIfOutOfBounds`):
*   **`MoveBody`:** Manages the main body's movement, calling `JSL Sprite_Move` and updating background scrolling based on its movement. It reuses logic from `Trinexx_MoveBody`.
*   **`StopIfOutOfBounds`:** Prevents the boss from moving beyond screen boundaries. It also subtly adjusts the neck positions when hitting a boundary, creating a visual "pushing" effect.

## Palette Management (`ApplyPalette`, `ApplyEndPalette`):
*   **`ApplyPalette`:** Sets the initial palette for the boss.
*   **`ApplyEndPalette`:** Sets a different palette, likely for a defeated state or phase change.

## Graphics Transfer (`ApplyKydreeokGraphics`):
*   Handles DMA transfer of graphics data (`kydreeok.bin`, `kydreeok_phase2.bin`) to VRAM, allowing for different graphical appearances across phases.

## Global Variables for Neck Control:
*   `LeftNeck1_X` to `LeftNeck3_Y`, `RightNeck1_X` to `RightNeck3_Y`: Global RAM addresses used to store the coordinates of the neck segments, enabling the heads to track them.
*   `Kydreeok_Id`: Stores the sprite index of the main Kydreeok boss.
*   `Offspring1_Id`, `Offspring2_Id`: Store the sprite indices of the spawned heads.

## Discrepancies/Notes:
*   The `!Health` and `!Damage` properties are `00`, confirming that the boss's health and damage are managed through its heads (`Sprite_KydreeokHead`) and custom logic within `Sprite_Kydreeok_CheckIfDead`.
*   The `Sprite_Kydreeok_CheckIfDead` routine clearly defines a multi-phase fight where the heads can be defeated, respawned, and ultimately lead to the main boss's defeat.
*   The commented-out `SpawnCenterHead` suggests a potential for a three-headed Kydreeok that was either removed or is an unimplemented feature.
*   Reusing movement logic from `Trinexx_MoveBody` is efficient but should be considered for unique boss feel.
*   Hardcoded addresses for `JSL` calls could be replaced with named labels for better maintainability.
