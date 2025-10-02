# Dungeons & Indoor Areas

This document details the various systems and enhancements for dungeons and other indoor areas found within the `Dungeons/` directory. These systems provide a framework for creating unique puzzles, mechanics, and environmental behaviors that go far beyond the vanilla game's capabilities.

## 1. Overview

The code in this directory can be broadly categorized into three main areas:
1.  **Custom Room Tags:** New, scriptable room behaviors that can be assigned to any room to create special events or puzzles.
2.  **Enhanced Mechanics & Objects:** Modifications or additions to existing dungeon elements like spikes, doors, and enemy stats.
3.  **Advanced Collision & Object Rendering:** A powerful, layered system for defining tile collision and drawing complex, multi-tile objects.

## 2. Custom Room Tags

Room "tags" are a vanilla mechanic that allows a room to have special properties (e.g., a kill room, a room with shutter doors). This project expands on this by hooking into the tag processing routines to add new, custom behaviors.

### Floor Puzzle (`floor_puzzle.asm`)

-   **Hook:** Replaces Tag `0x00` (`holes_0`).
-   **Functionality:** Implements a "light all the tiles" puzzle. When Link steps on a special "off" tile (`$0DED`), it transforms into an "on" tile (`$0DEE`) and plays a sound. The system then checks if any "off" tiles remain.
    -   If all tiles are on, it opens the room's shutter doors (`$0468`) and plays the secret sound.
    -   If the player steps on a tile that is already "on", it can trigger a kill room effect (`STZ.b $AE`).

### Crumble Floor (`crumblefloor_tag.asm`)

-   **Hook:** Replaces Tag `0x03` (`holes_3`).
-   **Functionality:** Creates floors that crumble away after being walked on.
    -   It tracks the tile Link is currently standing on.
    -   If he steps on a specific "crumble" tile (`$0C62` or `$0C63`), the code replaces it with a cracked tile and then a pit tile, spawning a falling tile visual effect (`Garnish 03`).
    -   This is designed for creating temporary paths or "don't stop running" challenges.

### Positional Warp (`together_warp_tag.asm`)

-   **Hook:** Replaces Tag `0x08` (`Holes8`).
-   **Functionality:** Changes the room's warp destination based on the player's position. It divides the room into four quadrants and sets the target room index based on which quadrant the player is in when they trigger a warp (e.g., by falling in a pit). This allows a single room to lead to four different destinations.

### Minish Shutter Door (`custom_tag.asm`)

-   **Hook:** Replaces Tag `0x05` (`Holes5`).
-   **Functionality:** Creates a shutter door that only opens if the player is in Minish Form (`!CurrentMask == 0x05`). If the condition is met, it opens the door and plays the corresponding sound effect.

### Intro Cutscene (`custom_tag.asm`)

-   **Hook:** Replaces Tag `0x39` (`Holes7`).
-   **Functionality:** This tag is repurposed to control the game's opening cutscene in Link's house. It's a state machine that handles:
    1.  Displaying the initial telepathic message from Farore.
    2.  Gradually lighting up the screen.
    3.  Waking Link from his bed and giving control to the player.
    4.  Setting the `GameState` flags to permanently prevent the "Uncle" sprite from appearing in the house again.

## 3. Dungeon Mechanics & Objects

### Key Blocks (`keyblock.asm`)

-   **Functionality:** Replaces the vanilla "prison door" object with a lock block that requires a small key.
-   **Implementation:** It hooks the object's interaction routine (`$01EB8C`). Before running the vanilla code to open the door, it checks the player's small key count (`$7EF36F`). If the player has one or more keys, it decrements the count and opens the block. If not, the block remains solid.

### Spike Block Subtypes (`spike_subtype.asm`)

-   **Functionality:** Expands the vanilla spike block (trap) to allow for different speeds and directions.
-   **Implementation:** It hooks the sprite preparation routine for the spike block (`$0691D7`). It reads the sprite's subtype value and uses it as an index into two tables, `speedValuesH` and `speedValuesV`, to set its horizontal and vertical speed. This allows for placing spikes that move vertically or at various speeds, configured directly in the sprite editor.

## 4. Advanced Collision System

The project features a powerful, three-tiered system for handling tile collision, offering immense flexibility.

### Layer 1: Global Collision Patches (`GlobalCollisionTables.asm`)

-   **Purpose:** To make baseline changes to the game's default tile behaviors.
-   **Implementation:** This file contains a series of `org` patches that directly overwrite data in the vanilla global tile property tables located in ROM bank `$0E`. These tables define the default physical properties of every 16x16 tile in the game (e.g., solid, water, pit, stairs).

### Layer 2: Tileset-Specific Collision (`CollisionTablesExpanded.asm`)

-   **Purpose:** To allow the same tile graphic to have different behaviors in different dungeons (e.g., a normal floor tile that becomes slippery in an ice dungeon).
-   **Implementation:** It hooks the dungeon tile attribute loading routine (`$0E942A`). The new routine, `Dungeon_LoadCustomTileAttr`, checks the current dungeon's tileset ID (`$0AA2`) and loads an entire set of custom tile properties from a group of tables. This allows, for example, "Glacia Estate" (`group0B`) to have unique ice physics while "Goron Mines" (`group04`) has its own set of properties for minecart tracks.

### Layer 3: Per-Room Custom Collision (`custom_collision.asm`)

-   **Purpose:** To provide the highest level of granularity by defining collision on a room-by-room basis, overriding all other rules.
-   **Implementation:** The `CustomRoomCollision` routine hooks the room loading process (`$01B95B`). It uses the current room ID (`$A0`) to look up a pointer in a table at `$258090`. If a pointer exists for the current room, it reads a block of custom collision data and writes it directly to the active collision map in WRAM (`$7E2000+`). This is used for creating unique and complex room layouts that would be impossible with the standard grid-based tile system.

## 5. Custom Object Handler (`Dungeons/Objects/object_handler.asm`)

-   **Purpose:** To render complex, multi-tile dungeon objects that are not sprites and cannot be created with the vanilla object system.
-   **Implementation:** This system hooks the vanilla object drawing routine for several reserved object IDs (e.g., `$31`, `$32`, `$54`). When the game attempts to draw one of these objects, the custom handler (`CustomObjectHandler`) is called instead.
-   **Data-Driven:** The handler reads the object's properties and looks up its corresponding graphical data from a series of `.bin` files included from the `Dungeons/Objects/Data/` directory. It then manually draws the object tile by tile. This is used to render things like minecart tracks, custom boss parts (`KydreeokBody`), and detailed scenery like the `IceFurnace`.

## 6. Miscellaneous Patches

-   **`enemy_damage.asm`:** Contains `org` patches that directly modify enemy property tables to change their bump damage values.
-   **`house_walls.asm`:** Contains `org` patches that modify tilemap data for house walls, likely for cosmetic changes.
-   **`attract_scenes.asm`:** Modifies the game's "attract mode" (the gameplay demos on the title screen) to create custom scenes that take place in dungeon environments.
