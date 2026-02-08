# Manhandla / Big Chuchu Sprite Analysis

## Overview
The `manhandla` sprite (ID: `Sprite_Manhandla`, which is `$88`) is a multi-phase boss. It begins as Manhandla, a multi-headed plant-like enemy, and upon the defeat of its individual heads, it transforms into a Big Chuchu. This design creates a dynamic and evolving boss encounter.

## Key Properties:
*   **Sprite ID:** `Sprite_Manhandla` (`$88`)
*   **Description:** A multi-phase boss that transforms from Manhandla to Big Chuchu.
*   **Number of Tiles:** 3
*   **Health:** `00` (Health is managed by its spawned heads in the first phase and then by its own `SprHealth` in the second phase.)
*   **Damage:** `00` (Damage dealt to Link is likely handled by its heads or spawned projectiles.)
*   **Special Properties:**
    *   `!Boss = 01` (Correctly identified as a boss.)
    *   `!DeathAnimation = 01` (Indicates custom death handling rather than a standard animation.)
    *   `!Hitbox = 00`

## Custom Variables:
*   `Offspring1_Id`, `Offspring2_Id`, `Offspring3_Id`: Global variables used to track the sprite indices of the spawned Manhandla heads.

## Main States/Actions (`Sprite_Manhandla_Main` Jump Table):
The boss's behavior is governed by a detailed state machine across its phases:
*   **`Manhandla_Intro` (0x00):** Initial state. Spawns the three Manhandla heads (`SpawnLeftManhandlaHead`, `SpawnRightManhandlaHead`, `SpawnCenterMandhandlaHead`) and transitions to `Manhandla_Body`.
*   **`Manhandla_FrontHead` (0x01), `Manhandla_LeftHead` (0x02), `Manhandla_RightHead` (0x03):** These states are likely executed by the individual Manhandla head child sprites, managing their movement, damage, and contact with Link.
*   **`BigChuchu_Main` (0x04):** The primary state for the Big Chuchu phase. Handles movement, damage, and can spawn Chuchu blasts.
*   **`Flower_Flicker` (0x05):** A transitional state that flickers the background (BG2) and spawns a new `Sprite_Manhandla` (with `SprSubtype = $08`, representing the Big Chuchu head) after a timer, as part of the transformation.
*   **`Manhandla_Body` (0x06):** The main state for the Manhandla body. Handles movement, damage, updates the positions of its spawned heads, and can spawn Mothula beams.
*   **`BigChuchu_Emerge` (0x07):** Manages the emergence animation of the Big Chuchu.
*   **`BigChuchu_Flower` (0x08):** A state for the Big Chuchu, possibly related to its visual appearance or an attack.
*   **`BigChuchu_Dead` (0x09):** Handles the death sequence of the Big Chuchu.
*   **`ChuchuBlast` (0x0A):** Manages the movement and damage of the spawned Chuchu blast projectile.

## Initialization (`Sprite_Manhandla_Prep`):
*   Sets initial movement speeds and enables BG1 movement.
*   Configures deflection properties (`SprDefl = $80`).
*   Sets initial health to `$80`.
*   Initializes `SprAction, X` based on `SprSubtype, X`.

## Phase Transition and Death Check (`Sprite_Manhandla_CheckForNextPhaseOrDeath`):
This critical routine orchestrates the boss's transformation:
*   It checks if all three Manhandla heads (`Offspring1_Id`, `Offspring2_Id`, `Offspring3_Id`) are dead.
*   If all heads are defeated, it triggers the transition to the Big Chuchu phase:
    *   Sets `SprMiscD, X = $01` (phase flag).
    *   Refills health (`SprHealth = $40`).
    *   Adjusts OAM entries (`SprNbrOAM = $08`).
    *   Sets `SprAction = $07` (BigChuchu_Emerge).
*   It also manages the Big Chuchu's defeat, transitioning to `BigChuchu_Dead` when its health drops below `$04`.

## Head Spawning (`SpawnLeftManhandlaHead`, `SpawnRightManhandlaHead`, `SpawnCenterMandhandlaHead`):
*   These routines spawn `Sprite_Manhandla` (`$88`) sprites as child heads.
*   They assign specific `SprSubtype` values (`$03` for left, `$02` for right, `$01` for center) to differentiate the heads.
*   They store the IDs of the spawned heads in global variables (`Offspring1_Id`, `Offspring2_Id`, `Offspring3_Id`).
*   They set the initial position, health, and properties for each head.

## Head Positioning (`SetLeftHeadPos`, `SetRightHeadPos`, `SetCenterHeadPos`):
*   These routines dynamically calculate and set the positions of the spawned heads relative to the main Manhandla body.

## Movement (`Sprite_Manhandla_Move`, `Manhandla_StopIfOutOfBounds`):
*   **`Sprite_Manhandla_Move`:** The core movement logic for the Manhandla body, utilizing a jump table for `StageControl`, `MoveXandY`, `MoveXorY`, and `KeepWalking` states.
*   **`Manhandla_StopIfOutOfBounds`:** Prevents the boss from moving beyond predefined screen boundaries.

## Attacks (`Chuchu_SpawnBlast`, `Mothula_SpawnBeams`):
*   **`Chuchu_SpawnBlast`:** Spawns a Chuchu blast projectile (Sprite ID `$88` with `SprSubtype = $0A`).
*   **`Mothula_SpawnBeams`:** Spawns beam projectiles (Sprite ID `$89`), called from `Manhandla_Body`.

## Drawing (`Sprite_Manhandla_Draw`, `Sprite_BigChuchu_Draw`):
*   **`Sprite_Manhandla_Draw`:** Renders the Manhandla body and its heads.
*   **`Sprite_BigChuchu_Draw`:** Renders the Big Chuchu form.
*   Both utilize standard OAM allocation routines and handle animation frames, offsets, character data, properties, and sizes.

## Graphics and Palette (`ApplyManhandlaGraphics`, `ApplyManhandlaPalette`):
*   **`ApplyManhandlaGraphics`:** Handles DMA transfer of graphics data (`manhandla.bin`) to VRAM.
*   **`ApplyManhandlaPalette`:** Sets the custom palette for Manhandla.

## Discrepancies/Notes:
*   The `!Health` property is `00`, indicating that the boss's health is managed by its heads in the first phase and then by its own `SprHealth` in the Big Chuchu phase.
*   The `Sprite_Manhandla` ID (`$88`) is efficiently reused for the main boss, its heads, and the Chuchu blast projectile, with `SprSubtype` differentiating their roles.
*   The reuse of `Mothula_SpawnBeams` for Manhandla is an example of code reuse.
*   Hardcoded values for timers, speeds, and offsets could be replaced with named constants for improved readability and maintainability.
*   A commented-out `org` for `Sprite_DoTheDeath#PrepareEnemyDrop.post_death_stuff` suggests potential modifications to the death routine.
