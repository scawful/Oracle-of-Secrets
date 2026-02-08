# Kydreeok Head Sprite Analysis

## Overview
The `kydreeok_head` sprite (ID: `Sprite_KydreeokHead`, which is `$CF`) is a child sprite of the main `Kydreeok` boss. It represents one of the multi-headed boss's individual heads, possessing independent movement, attack patterns, and damage handling. Its primary role is to move, rotate, and attack Link, contributing to the overall boss encounter.

## Key Properties:
*   **Sprite ID:** `Sprite_KydreeokHead` (`$CF`)
*   **Description:** Child sprite of the Kydreeok boss, responsible for individual head behavior.
*   **Number of Tiles:** 7
*   **Health:** `$C8` (200 decimal) - This high health value indicates it's a significant component of the boss fight.
*   **Damage:** `00` (Damage is likely applied through its spawned attacks.)
*   **Special Properties:**
    *   `!Boss = 00` (Not marked as a boss itself, as it's a component of a larger boss.)
    *   `!Hitbox = 09`

## Subtypes:
The `SprSubtype, X` register is crucial for differentiating the heads and their behavior:
*   **Subtype `$00`:** Controls the "Left Head" via `Neck1_Control`.
*   **Subtype `$01`:** Controls the "Right Head" via `Neck2_Control`.
This allows the same sprite ID to manage multiple distinct heads.

## Main States/Actions (`Sprite_KydreeokHead_Main` Jump Table):
The head's behavior is governed by a state machine:
*   **`KydreeokHead_ForwardAnim` (0x00):** Default state, plays forward animation, handles damage, performs rotational movement, and randomly attacks. Transitions to other directional states based on Link's position.
*   **`KydreeokHead_RightAnim` (0x01):** Plays right-facing animation, handles damage, rotation, and attacks.
*   **`KydreeokHead_LeftAnim` (0x02):** Plays left-facing animation, handles damage, rotation, and attacks.
*   **`KydreeokHead_FarRight` (0x03):** Plays far-right animation, moves towards Link, handles damage, rotation, and attacks.
*   **`KydreeokHead_FarLeft` (0x04):** Plays far-left animation, moves towards Link, handles damage, rotation, and attacks.
*   **`KydreeokHead_SummonFire` (0x05):** Moves towards Link, checks damage, and utilizes `JSL Sprite_Twinrova_FireAttack` to deal damage. The head sprite is then killed after a timer.

## Initialization (`Sprite_KydreeokHead_Prep`):
*   Sets initial health to `$FF` (255 decimal), though the `!Health` property is `$C8`. This discrepancy might be overridden by the parent `Kydreeok` sprite or is a temporary value.
*   Sets `SprBump = $09` (bump damage type).
*   Initializes `SprMiscE, X` to `0`.

## Drawing (`Sprite_KydreeokHead_Draw`):
*   Uses standard OAM allocation routines.
*   The main drawing routine calls `JMP Sprite_KydreeokHead_DrawNeck`, indicating that the neck segments are drawn after the head.
*   Includes logic for flashing when damaged.

## Neck Control (`KydreeokHead_NeckControl`, `Neck1_Control`, `Neck2_Control`, `Sprite_KydreeokHead_DrawNeck`, `DrawNeckPart`):
This is a sophisticated system for managing the multi-segmented neck:
*   `KydreeokHead_NeckControl` dispatches to `Neck1_Control` (for the left head) or `Neck2_Control` (for the right head) based on `SprSubtype, X`.
*   `Neck1_Control` and `Neck2_Control` manage the movement and positioning of three neck segments, ensuring they follow the head while maintaining specific distances.
*   `Sprite_KydreeokHead_DrawNeck` and `DrawNeckPart` handle the rendering of these segments.

## Movement and Rotation (`KydreeokHead_RotationMove`, `RotateHeadUsingSpeedValues`, `MoveWithBody`):
*   **`KydreeokHead_RotationMove`:** Generates random speeds, dispatches to neck control, moves with the main body, and applies rotational movement.
*   **`RotateHeadUsingSpeedValues`:** Uses sine/cosine tables (`XSpeedSin`, `YSpeedSin`) to apply smooth rotational movement.
*   **`MoveWithBody`:** Ensures the head's position is correctly offset and relative to the main `Kydreeok` boss, adjusting for left or right heads.

## Attacks (`RandomlyAttack`, `KydreeokHead_SummonFire`):
*   **`RandomlyAttack`:** Randomly spawns a fire-based projectile (which is actually the `Sprite_KydreeokHead` itself entering the `SummonFire` state).
*   **`KydreeokHead_SummonFire`:** This state is entered when a fire projectile is spawned. It moves towards Link and uses `JSL Sprite_Twinrova_FireAttack` to deal damage, after which the head sprite is killed.

## Key Macros/Functions Used:
*   `%Set_Sprite_Properties`, `%GotoAction`, `%StartOnFrame`, `%PlayAnimation`, `%MoveTowardPlayer`
*   `JSL JumpTableLocal`, `JSL Sprite_CheckDamageFromPlayer`, `JSL Sprite_CheckDamageToPlayer`, `JSL Sprite_DamageFlash_Long`
*   `JSL GetRandomInt`, `JSL Sprite_MoveLong`, `JSL Sprite_IsToRightOfPlayer`
*   `JSL Sprite_SpawnDynamically`, `JSL Sprite_SetSpawnedCoords`
*   `JSL Sprite_Twinrova_FireAttack`, `JSL Fireball_SpawnTrailGarnish`
*   `JSR GetDistance8bit`

## Discrepancies/Notes:
*   The `!Health` property is `$C8`, but `Sprite_KydreeokHead_Prep` sets `SprHealth, X` to `$FF`. This needs clarification.
*   The reuse of `JSL Sprite_Twinrova_FireAttack` for Kydreeok's head is an example of code reuse, but it's important to ensure it fits the thematic design of Kydreeok.
*   The neck control system is quite intricate, highlighting advanced sprite design.
*   Several hardcoded addresses for `JSL` calls could be replaced with named labels for better maintainability.
