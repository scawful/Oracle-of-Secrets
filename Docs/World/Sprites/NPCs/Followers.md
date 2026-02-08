# Followers

## Overview
The `followers.asm` file is a comprehensive collection of routines and data structures that implement a sophisticated follower system within Oracle of Secrets. It manages various NPC types, including the Zora Baby, Old Man, Kiki, and a Minecart, each with unique behaviors, interactions, and integration into the game world. This file heavily utilizes vanilla overrides to inject custom logic and expand upon existing game mechanics.

## Follower Data Memory Locations
This section defines various WRAM addresses used to store and cache follower-related data, enabling complex interactions and animations:

*   **`FollowerYL`, `FollowerYH`, `FollowerXL`, `FollowerXH`, `FollowerZ`, `FollowerLayer`**: Stores position (Y, X, Z coordinates) and layer information for followers, with a cache for 20 steps of animation and movement.
*   **`FollowerHeadOffset`, `FollowerHeadOffsetH`, `FollowerBodyOffset`, `FollowerBodyOffsetH`**: Stores offsets for follower head and body graphics, used to adjust their appearance based on direction (e.g., facing Link).
*   **`Flwhgfxt`, `Flwhgfxth`, `Flwhgfxb`, `Flwhgfxbh`, `Flwbgfxt`, `Flwbgfxth`, `Flwbgfxb`, `Flwbgfxbh`**: Graphics data for follower head and body.
*   **`Flwanimir`**: Index for reading follower animation steps.
*   **`FollowerHook`**: Flag indicating when a follower is being used with the Hookshot.
*   **`FollowerHookI`**: Caches `FLWANIMIW` when Hookshotting is finished.
*   **`FLWGRABTIME`**: Countdown timer preventing followers from being immediately regrabbed after being dropped.
*   **`FLWANIMIW`**: Index for writing follower animation steps.
*   **`FollowCacheYL`, `FollowCacheYH`, `FollowCacheXL`, `FollowCacheXH`**: Cache of follower properties in SRAM.

## `Follower_WatchLink`
This routine adjusts a follower's head and body graphics offsets to make them turn and face Link, providing a more interactive and responsive NPC presence.

## Zora Baby Follower
The Zora Baby follower is a key NPC involved in specific puzzles and interactions, particularly with water switches.

*   **`ZoraBaby_RevertToSprite`**: This routine spawns a `Sprite 0x39 Locksmith` (which is the Zora Baby sprite) and initializes its properties based on the follower's cached data. It sets `SprBulletproof`, `SprAction`, and `SprTimerB`, and clears relevant follower flags.
*   **`CheckForZoraBabyTransitionToSprite`**: Checks if the Zora Baby is currently a follower (`$7EF3CC = $09`). If Link is standing on a star tile (`$0114 = $3B`), it calls `ZoraBaby_RevertToSprite` to transition the follower back into a regular sprite. If Link is outdoors, it clears the follower flag.
*   **`CheckForZoraBabyFollower`**: A utility routine to check if the Zora Baby is currently a follower.
*   **`UploadZoraBabyGraphicsPrep`**: Prepares the graphics for the Zora Baby, setting `$7EF3CC` to `$09` and calling `LoadFollowerGraphics`.
*   **`ZoraBaby_CheckForWaterSwitchSprite`**: Checks for the presence of a `Sprite 0x21` (Water Gate Switch) and determines if the Zora Baby is positioned on top of it.
*   **`ZoraBaby_CheckForWaterGateSwitch`**: Checks for a `Sprite 0x04` (Water Gate Switch) and performs a precise coordinate check to see if the Zora Baby is on top of it.
*   **`ZoraBaby_GlobalBehavior`**: This is the main behavior routine for the Zora Baby. It makes the Zora Baby act as a barrier (`Sprite_BehaveAsBarrier`), makes it watch Link (`Follower_WatchLink`), and handles interactions like being lifted (`Sprite_CheckIfLifted`) and thrown (`ThrownSprite_TileAndSpriteInteraction_long`). Crucially, it detects if the Zora Baby is on a water switch and triggers the `ZoraBaby_PullSwitch` state.

### Zora Baby Vanilla Overrides
*   **`org $09AA5E`**: Injects `JSL CheckForZoraBabyFollower` to enable the Zora Baby's swaying animation.
*   **`org $09A19C`**: Injects `JSL CheckForZoraBabyTransitionToSprite` for follower basic movement.
*   **`org $09A902`**: Sets the Zora Baby follower's palette to blue.
*   **`org $09A8CF`**: Sets the Zora Baby character data offset.
*   **`org $06BD9C`**: Defines the Zora Baby Sprite Idle OAM data.
*   **`org $068D59` (`SpritePrep_Locksmith`)**: Overrides the `SpritePrep_Locksmith` routine. It makes the Zora Baby bulletproof, prevents spawning if already following, and calls `UploadZoraBabyGraphicsPrep`.
*   **`org $06BCAC` (`Sprite_39_ZoraBaby`)**: Overrides `Sprite_39_Locksmith`. This is the main state machine for the Zora Baby, including states like `LockSmith_Chillin` (idle), `ZoraBaby_FollowLink`, `ZoraBaby_OfferService`, `ZoraBaby_RespondToAnswer`, `ZoraBaby_AgreeToWait`, `ZoraBaby_PullSwitch`, and `ZoraBaby_PostSwitch`. These states manage dialogue, following behavior, and interaction with switches.

## Old Man Follower
This section includes logic for the Old Man follower, particularly concerning his spawning conditions and item interactions.

*   **`OldMan_ExpandedPrep`**: Prevents the Old Man sprite from spawning in his home room if Link already has him as a follower.

### Old Man Vanilla Overrides
*   **`org $1EE9FF`**: Modifies the item given by the Old Man to be the Goldstar Hookshot upgrade.
*   **`org $1BBD3C`**: Modifies `FindEntrance` for the Old Man.
*   **`org $02D98B`**: Modifies `Underworld_LoadEntrance` for the Old Man.
*   **`org $1EE8F1` (`SpritePrep_OldMan`)**: Overrides `SpritePrep_OldMan`. It makes the Old Man bulletproof, uses `OldMan_ExpandedPrep`, checks for the Lv2 Hookshot, and sets `$7EF3CC` to `$04` (Old Man follower) before calling `LoadFollowerGraphics`.
*   **`org $09A4C8` (`Follower_HandleTriggerData`)**: This is a large data block defining trigger coordinates and messages for various followers, including the Old Man, Zelda, and Blind Maiden.

## Kiki Follower
This section contains logic for the Kiki follower, focusing on her reaction to Link's health.

*   **`Kiki_CheckIfScared`**: If Link's health is low and Kiki is flashing, she will run away from him.

### Kiki Vanilla Overrides
*   **`org $09A1C6`**: Injects `JSL Kiki_CheckIfScared` to implement Kiki's fear behavior.
*   **`org $1EE2E9` (`Kiki_WalkOnRoof`)**: Defines speed data for Kiki walking on a roof.
*   **`org $1EE576` (`Kiki_HopToSpot`)**: Defines target coordinates for Kiki to hop to a spot.
*   **`org $1EE5E9` (`Kiki_WalkOnRoof_Ext`)**: Defines step and timer data for Kiki's extended roof walk.

## Minecart Follower
This section details the implementation of the Minecart follower, including its drawing, transition, and Link's interaction with it.

*   **`FollowerDraw_CalculateOAMCoords`**: A helper routine to calculate OAM coordinates for followers.
*   **`MinecartFollower_Top` / `MinecartFollower_Bottom`**: Drawing routines for the top and bottom halves of the Minecart follower.
*   **`Minecart_AnimDirection`**: Data for Minecart animation direction.
*   **`MinecartFollower_TransitionToSprite`**: Transitions the Minecart follower back into a regular sprite.
*   **`DrawMinecartFollower`**: The main drawing routine for the Minecart follower, which also handles its transition to a sprite if Link is in the cart and not in a submodule.
*   **`FollowerDraw_CachePosition`**: Caches the follower's position for drawing, adjusting coordinates relative to Link.
*   **`CheckForMinecartFollowerDraw`**: Checks if the Minecart follower should be drawn.
*   **`CheckForFollowerInterroomTransition` / `CheckForFollowerIntraroomTransition`**: Handles transitions for followers between rooms and within rooms.
*   **`LinkState_Minecart`**: Defines Link's behavior when he is in a Minecart, including movement, collision, and animation.
*   **`TileBehavior_TL_Long` / `TileBehavior_StopLeft_Long`**: Tile behaviors for Minecart tracks.

### Minecart Vanilla Overrides
*   **`org $07A5F7`**: Injects `JSL LinkState_Minecart` to control Link's state when in a Minecart.
*   **`org $07D938`**: Defines Minecart Track tile types.
*   **`org $09A41F`**: Injects `JSL CheckForMinecartFollowerDraw`.
*   **`org $028A5B`**: Injects `JSL CheckForFollowerInterroomTransition`.
*   **`org $0289BF`**: Injects `JSL CheckForFollowerIntraroomTransition`.

## Design Patterns
*   **Multi-Purpose File**: This file serves as a central repository for various follower-related logic, demonstrating how to manage diverse NPC behaviors within a single module.
*   **Follower System**: Implements a robust and flexible follower system with features like position caching, animation, and complex interaction logic.
*   **Vanilla Overrides**: Extensive use of `org` directives to modify vanilla sprite behaviors and integrate custom follower logic, showcasing advanced ROM hacking techniques.
*   **Context-Sensitive Behavior**: Follower behavior dynamically changes based on game state, player actions, and environmental factors (e.g., Zora Baby on water switch, Old Man's spawning conditions, Kiki's fear of low-health Link).
*   **Cutscene Integration**: Some followers (like the Zora Baby) are involved in cutscene-like sequences, demonstrating how to choreograph NPC actions within narrative events.
*   **Item Gating/Progression**: The Old Man's appearance and item offerings are tied to the player's possession of specific items (e.g., Lv2 Hookshot), integrating followers into the game's progression system.
*   **Player State Manipulation**: Routines like `LinkState_Minecart` directly control Link's movement and animation when interacting with followers, providing a seamless player experience.
*   **16-bit OAM Calculations**: Explicitly uses `REP #$20` and `SEP #$20` for precise 16-bit OAM calculations in drawing routines, ensuring accurate sprite rendering.
