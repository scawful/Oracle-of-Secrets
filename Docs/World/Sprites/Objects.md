# Objects Analysis

This document provides an analysis of the object sprites found in the `Sprites/Objects/` directory. These sprites are typically interactive elements of the environment rather than enemies.

## File Overview

| Filename | Sprite ID(s) | Description |
|---|---|---|
| `collectible.asm` | `$52` | A generic collectible sprite that can represent a Pineapple, Seashell, Sword/Shield, or Rock Sirloin. |
| `deku_leaf.asm` | `Sprite_DekuLeaf` | A Deku Leaf platform that Link can stand on. Also used for whirlpools. |
| `ice_block.asm` | `$D5` | A pushable ice block used in puzzles. |
| `minecart.asm` | `Sprite_Minecart` (`$A3`) | A rideable minecart used for transportation puzzles in dungeons. |
| `mineswitch.asm` | `Sprite_Mineswitch` | A lever switch that can be hit to change the state of other objects, like minecart tracks. |
| `pedestal.asm` | (Hooks `$1EE05F`) | Logic for the magic pedestals where Link can read text with the Book of Mudora. |
| `portal_sprite.asm` | `Sprite_Portal` | The blue and orange portals created by the Portal Rod. |
| `switch_track.asm` | `Sprite_SwitchTrack` (`$B0`) | The visual component of a switchable minecart track, which rotates when a lever is hit. |

## Detailed Object Analysis

### `collectible.asm`
- **Sprite ID:** `$52`
- **Summary:** This is a versatile sprite that acts as a world collectible. Its behavior and appearance are determined by its `SprAction` state, which is set during prep.
- **Key Logic:**
    - **`Sprite_Collectible_Prep`:** Checks the current map (`$8A`) to determine what the sprite should be. For example, on map `$58` (intro), it becomes the sword and shield.
    - **`Sprite_Collectible_Main`:** The main state machine. On contact with the player (`Sprite_CheckDamageToPlayer`), it increments the corresponding counter in SRAM (e.g., `Pineapples`, `Seashells`) or grants an item (`Link_ReceiveItem`) and then despawns itself.

### `ice_block.asm`
- **Sprite ID:** `$D5`
- **Summary:** A block that slides on icy floors when pushed by Link. It is used for puzzles.
- **Key Logic:**
    - **Pushing:** When Link is in contact (`Sprite_CheckDamageToPlayerSameLayer`), the `Sprite_ApplyPush` routine gives the block velocity based on the direction Link is facing.
    - **Sliding:** The block continues to move in that direction (`Sprite_Move`) until it hits a wall (`Sprite_CheckTileCollision`) or another object.
    - **Switch Interaction:** `Sprite_IceBlock_CheckForSwitch` checks if the block is on top of a floor switch tile. If so, it sets a flag (`$0642`) to activate the switch and stops moving.

### `minecart.asm` / `switch_track.asm` / `mineswitch.asm`
- **Sprite IDs:** `Sprite_Minecart` (`$A3`), `Sprite_SwitchTrack` (`$B0`), `Sprite_Mineswitch`
- **Summary:** This is a complex system of three interconnected sprites that create minecart puzzles.
- **Key Logic:**
    - **`Sprite_Minecart`:**
        - The player can press B to enter the cart (`Minecart_WaitHoriz`/`Vert`). This sets the `!LinkInCart` flag and attaches the player.
        - The cart moves along a path defined by custom tile types (`$B0`-`$BE`).
        - At intersections (`$B6`, etc.), it reads player input (`$F0`) to determine which way to turn (`CheckForPlayerInput`).
        - At corners (`$B2`-`$B5`), it automatically turns (`CheckForCornerTiles`).
        - At dynamic switch tracks (`$D0`-`$D3`), it checks the state of the corresponding `Sprite_Mineswitch` to determine its path (`HandleDynamicSwitchTileDirections`).
        - At dungeon transitions, it converts into a follower sprite (`MinecartFollower_TransitionToSprite`) to persist between rooms.
    - **`Sprite_SwitchTrack`:** This is a purely visual sprite. Its frame is set based on the on/off state of its corresponding `Mineswitch`, which is stored in `SwitchRam`.
    - **`Sprite_Mineswitch`:** This is a lever. When hit by the player, it toggles its state in the `SwitchRam` array, which is then read by the `SwitchTrack` and `Minecart` sprites.

### `portal_sprite.asm`
- **Sprite ID:** `Sprite_Portal`
- **Summary:** This sprite handles the logic for the portals created by the Portal Rod.
- **Key Logic:**
    - **Spawning:** Two portals can exist at once: one blue and one orange. The `StateHandler` determines which type to create based on the `$7E0FA6` flag.
    - **Warping:** When Link overlaps with a portal (`CheckIfHitBoxesOverlap`), it triggers a warp. The destination is the location of the *other* portal, whose coordinates are stored in RAM (`BluePortal_X/Y`, `OrangePortal_X/Y`).
    - **Dismissal:** The `CheckForDismissPortal` routine despawns the oldest portal when a third one is created.
    - **Invalid Placement:** `RejectOnTileCollision` prevents portals from being placed on invalid surfaces like walls and despawns the sprite if they are.
