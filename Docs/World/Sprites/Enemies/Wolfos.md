# Wolfos Mini-Boss Sprite Analysis

## Overview
The `wolfos` sprite (ID: `Sprite_Wolfos`, which is `$A9`) functions as a mini-boss or special enemy. It engages Link in combat with various movement and attack patterns. A key aspect of this sprite is its integration into a mask quest, where it can be subdued and, under specific conditions, grants Link the Wolf Mask.

## Key Properties:
*   **Sprite ID:** `Sprite_Wolfos` (`$A9`)
*   **Description:** A mini-boss/special enemy that fights Link and is part of a mask quest.
*   **Number of Tiles:** 4
*   **Health:** `30` (decimal)
*   **Damage:** `00` (Damage dealt to Link is likely handled by its attacks.)
*   **Special Properties:**
    *   `!Boss = 00` (Not marked as a boss, but functions as a mini-boss/special enemy.)
    *   `!ImperviousArrow = 01` (Impervious to arrows.)

## Custom Variables/Macros:
*   `WolfosDialogue = SprMiscD`: Stores a flag to control Wolfos dialogue.
*   `Wolfos_AnimateAction = SprMiscE`: Stores the current animation action.
*   `AttackForward()`, `AttackBack()`, `WalkRight()`, `WalkLeft()`, `AttackRight()`, `AttackLeft()`, `Subdued()`, `GrantMask()`, `Dismiss()`: Macros for setting `SprAction` and `Wolfos_AnimateAction`, improving code clarity.
*   `!NormalSpeed = $08`, `!AttackSpeed = $0F`: Constants for movement speeds.

## Main Logic Flow (`Sprite_Wolfos_Main`):
The Wolfos's behavior is governed by a state machine:
*   **`Wolfos_AttackForward` (0x00), `Wolfos_AttackBack` (0x01), `Wolfos_WalkRight` (0x02), `Wolfos_WalkLeft` (0x03), `Wolfos_AttackRight` (0x04), `Wolfos_AttackLeft` (0x05):** These states manage the Wolfos's movement and attacks. They call `Wolfos_Move` and can randomly trigger attack actions with increased speed and temporary imperviousness.
*   **`Wolfos_Subdued` (0x06):** In this state, the Wolfos stops moving, displays dialogue (`$23`), and waits for Link to play the Song of Healing (`SongFlag = $01`). If the song is played, it transitions to `Wolfos_GrantMask`.
*   **`Wolfos_GrantMask` (0x07):** Displays the Wolfos mask graphic, shows a message (`$10F`), grants Link the `WolfMask` item, and transitions to `Wolfos_Dismiss`.
*   **`Wolfos_Dismiss` (0x08):** Stops moving, kills the sprite, and clears Link's `BRANDISH` flag.

## Initialization (`Sprite_Wolfos_Prep`):
*   Checks if Link is outdoors (`$1B`). If so, it further checks if the Wolfos has already been defeated (`$7EF303 = $01`). If defeated, the sprite is killed to prevent respawning.
*   Sets initial timers (`SprTimerA = $40`, `SprTimerC = $40`).
*   Configures deflection properties (`SprDefl = $82`, making it impervious to arrows).
*   Sets `SprNbrOAM = $08` and initializes `SprMiscG, X` and `SprMiscE, X` to `0`.

## Defeat Check (`Sprite_Wolfos_CheckIfDefeated`):
*   Checks if Link is outdoors. If `SprHealth, X` drops below `$04`, the Wolfos is considered "defeated."
*   Upon defeat, it sets `SprAction = $06` (Wolfos_Subdued), `SprState = $09` (normal state, avoiding a full death animation), refills its health to `$40`, and clears `WolfosDialogue`. This indicates pacification rather than outright killing.

## Movement (`Wolfos_Move`, `Wolfos_DecideAction`, `Wolfos_MoveAction_Basic`, `Wolfos_MoveAction_CirclePlayer`, `Wolfos_MoveAction_Dodge`):
*   **`Wolfos_Move`:** Handles damage flash, checks damage from player, prevents player from passing through, bounces from tile collision, checks for recoiling, moves the sprite, and calls `Wolfos_DecideAction`.
*   **`Wolfos_DecideAction`:** Determines the Wolfos's next movement action based on timers and random chance. It uses a jump table to select between `Wolfos_MoveAction_Basic`, `Wolfos_MoveAction_CirclePlayer`, and `Wolfos_MoveAction_Dodge`.
*   **`Wolfos_MoveAction_Basic`:** Basic movement towards or away from Link based on distance.
*   **`Wolfos_MoveAction_CirclePlayer`:** Attempts to circle the player.
*   **`Wolfos_MoveAction_Dodge`:** Dodges by applying speed towards the player.

## Animation (`Sprite_Wolfos_Animate`):
*   This routine is called from `Sprite_Wolfos_Main`.
*   It uses `Wolfos_AnimateAction` (stored in `SprMiscE, X`) to determine which animation to play.
*   It has separate animation routines for `AttackForward`, `AttackBack`, `WalkRight`, `WalkLeft`, `AttackRight`, `AttackLeft`, and `Subdued`.
*   It also spawns sparkle garnishes (`JSL Sprite_SpawnSparkleGarnish`).

## Drawing (`Sprite_Wolfos_Draw`):
*   Uses standard OAM allocation routines.
*   Handles animation frames, x/y offsets, character data, properties, and sizes for drawing the Wolfos.
*   Includes a special frame for the Wolf Mask (`$CC`) when granting the item.

## Discrepancies/Notes:
*   **Mask Quest Integration:** The Wolfos is directly integrated into a mask quest, where playing the Song of Healing subdues it and leads to receiving the Wolf Mask.
*   **Health Refill on Defeat:** When defeated, its health is refilled to `$40`, and its state is set to `Wolfos_Subdued`, indicating it's not truly killed but rather pacified.
*   **Hardcoded Values:** Many numerical values for timers, speeds, and offsets are hardcoded. Replacing these with named constants would improve readability and maintainability.
*   **`JSL Link_ReceiveItem`:** This is a standard function for giving items to Link.
*   **`JSL Sprite_SpawnSparkleGarnish`:** This is a generic garnish spawning function.
