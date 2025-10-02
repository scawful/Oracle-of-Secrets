# Ice Block System (`Sprites/Objects/ice_block.asm`)

## Overview

This file contains the logic for the pushable ice block sprite. It's a statue-like object that, when pushed by Link, slides in one direction until it collides with a wall, another object, or a switch.

## Key Functionality

- **Pushing Mechanics:** When Link makes contact, the block's `SprMiscA` register stores Link's facing direction. A timer (`SprTimerA`) is used to confirm the push, after which the block is set in motion.
- **Sliding:** Once pushed, the block moves at a constant velocity until a collision is detected.
- **Collision:** The block stops moving when it collides with a wall (detected via `SprCollision`) or another sprite (handled in `Statue_BlockSprites`). It also stops when it hits a specific switch tile.
- **State Management:** The sprite uses `SprMisc` registers to track its state, such as whether it's currently being pushed (`SprMiscC`) or is in motion (`SprMiscB`).

## Analysis & Areas for Improvement

The ice block is a classic Zelda puzzle element, but its current implementation suffers from over-sensitivity and unpredictable behavior, leading to frustration for beta testers. The goal is to achieve a "Pokémon-style" grid-based sliding puzzle feel, requiring intentional pushes and predictable movement.

### Current Problems:
- **Over-sensitivity:** The block initiates movement on simple hitbox overlap with Link, leading to accidental pushes.
- **Unpredictable Direction:** Link's slight movements or diagonal contact can result in the block sliding in unintended directions.
- **Non-grid-aligned movement:** The block does not snap to a grid, making its stopping positions feel imprecise.

### Proposed Improvements:

#### 1. Intent-Based Push Mechanics (Addressing Sensitivity & Direction)
The current `JSL Sprite_CheckDamageToPlayerSameLayer` is too broad. It will be replaced with a more robust system:

- **Directional Alignment Check:** A new subroutine (`IceBlock_CheckLinkPushAlignment`) will be implemented. This routine will verify that Link is:
    - Directly adjacent to the ice block.
    - Facing the ice block (e.g., if Link is facing right, the block must be to his right).
    - Aligned within a small pixel tolerance (e.g., +/- 4 pixels) on the non-pushing axis (e.g., for a horizontal push, Link's Y-coordinate must be close to the block's Y-coordinate).
- **Push Confirmation Timer:** Instead of an immediate push, a short timer (e.g., 10-15 frames) will be introduced. Link must maintain the correct directional alignment and contact for this duration to confirm an intentional push. If contact or alignment is broken, the timer resets.
- **Locked Direction:** Once a push is confirmed, the block's movement direction will be locked to a single cardinal direction (horizontal or vertical) until it collides with an obstacle.

#### 2. Predictable Movement & Stopping (Grid Alignment)
- **Grid Snapping on Push:** When a push is confirmed, the ice block's coordinates (`SprX, SprY`) will be snapped to the nearest 8-pixel grid boundary before movement begins. This ensures that all slides start and end cleanly on the game's tile grid.

#### 3. Code Refactoring & Readability (General Improvements)
While implementing the above, the following existing suggestions from the previous analysis will also be applied:

- **Use `subroutine` for All Code Blocks:** Convert all major logical blocks within `Sprites/Objects/ice_block.asm` into proper `subroutine`s for better scope management and readability.
- **Replace Magic Numbers with Constants:** Define named constants for all hardcoded values (speeds, timers, tile IDs, alignment tolerances) to improve code clarity and maintainability.
- **Refactor `Sprite_ApplyPush`:** Convert the `Sprite_ApplyPush` routine to use a lookup table for setting `SprXSpeed` and `SprYSpeed` based on the determined push direction. This will make the code more compact and easier to modify.
- **Clarify `Statue_BlockSprites`:** Rename this routine to `IceBlock_HandleSpriteToSpriteCollision` and add detailed comments to explain its logic, especially concerning sprite-to-sprite collision and recoil calculations.

## Deeper Analysis: Sprite Solidity and Link's Collision

To understand why the ice block is not solid, we need to look at both the sprite's properties and Link's collision detection code.

### Sprite Property Analysis

Several flags in the sprite's RAM data structure control its physical properties. These are the most relevant for solidity:

*   **`!Statue = 01` Property:** In the sprite's header, `!Statue = 01` is set. This is a high-level property that should be translated into one or more of the low-level RAM flags by the `%Set_Sprite_Properties` macro when the sprite is initialized.

*   **`SprDefl` (`$0CAA`):** This is the "Sprite Deflection" register and appears to be critical.
    *   **Bit 2 (`$04`):** The `Core/symbols.asm` file labels this the "pushable interaction flag". Although the comment says it's "Never queried," this is highly suspect and is the most likely candidate for enabling pushable-statue physics.
    *   **Our Bug:** Our previous attempts to modify `Sprite_IceBlock_Prep` either cleared this register entirely (`STZ.w SprDefl, X`) or left it alone, both of which resulted in Link walking through the block. This indicates that this register's value is crucial and must be set correctly, likely by the engine's default property loading routines. Our code was interfering with this.

*   **`SprHitbox` (`$0F60`):** This register contains the `I` (Ignore Collisions) bit.
    *   **Bit 7 (`$80`):** If this bit is set, the sprite will ignore all collisions with Link. We must ensure our code does not accidentally set this bit.

### Link's Collision Logic (Hypothesis)

The core of Link's interaction with the world is handled in `bank_07.asm`.

*   **`Link_HandleCardinalCollision` (`JSR` at `#_0782C2`):** This is the key function that processes Link's movement against solid objects. A full analysis is pending a complete reading of `bank_07.asm`, but we can hypothesize its behavior.
    *   **Hypothesis:** This routine likely loops through all active sprites on screen. For each sprite, it checks a combination of flags (e.g., `SprDefl`, `SprHitbox`) to determine if the sprite is solid. If it is, it performs a bounding box check. If Link's next position would overlap with a solid sprite, his movement is halted. The fact that Link walks through the ice block proves that the block is not being flagged as solid correctly.

### Revised Troubleshooting Plan

Based on this deeper analysis, the plan is to work *with* the game engine's properties, not against them.

1.  **Analyze `Link_HandleCardinalCollision`:** The top priority is to find and fully analyze this function in `bank_07.asm` to understand exactly which sprite flags it checks to identify a solid, pushable object.
2.  **Analyze `SpritePrep_LoadProperties`:** Understand how the `%Set_Sprite_Properties` macro and the subsequent `JSL SpritePrep_LoadProperties` function translate the `!Statue = 01` property into RAM flags. This will reveal the correct default values for a statue.
3.  **Correct `Sprite_IceBlock_Prep`:** With the knowledge from the steps above, write a definitive `Sprite_IceBlock_Prep` routine that correctly initializes all necessary flags (`SprDefl`, etc.) for a pushable statue, without overriding engine defaults.
4.  **Verify Solidity:** Build and test to confirm Link collides with the block.
5.  **Re-evaluate Push Logic:** Once the block is solid, re-evaluate the push initiation logic, which uses `JSL Sprite_CheckDamageToPlayerSameLayer`. If it still fails, we will have a solid object to debug against, which is a much better state.
