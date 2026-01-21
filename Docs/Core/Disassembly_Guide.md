# Disassembly Analysis and Search Guide

This document provides a high-level analysis of key banks in the Link to the Past disassembly. Use this guide to quickly locate relevant code and understand the overall structure of the game.

## 1. Bank $00: Game Core & Main Loop

**File:** `ALTTP/bank_00.asm`
**Address Range:** `$008000` - `$00FFFF`
**Summary:** The heart of the game engine. Contains the main game loop, interrupt handlers, and the primary game state machine.

### Key Structures & Routines:
*   **`Reset:` (#_008000)**: Game entry point on boot.
*   **`MainGameLoop:` (#_008034)**: Central loop, calls `Module_MainRouting`.
*   **`Module_MainRouting:` (#_0080B5)**: Primary state machine dispatcher. Reads `MODE` (`$7E0010`) and uses `pool Module_MainRouting` to jump to the correct game module.
*   **`Interrupt_NMI:` (#_0080C9)**: Runs every frame. Handles input (`NMI_ReadJoypads`), graphics DMA (`NMI_DoUpdates`), and sprite preparation (`NMI_PrepareSprites`).

### Search Heuristics:
*   **Game Module Logic (Overworld, Underworld, Menus):** Search `bank_00.asm` for the `pool Module_MainRouting` jump table. The labels (e.g., `Module09_Overworld`) are the entry points for each game state, determined by WRAM `$7E0010` (`MODE`).
*   **Per-Frame Logic:** Search `bank_00.asm` for `Interrupt_NMI:`. Key routines called from here are `NMI_ReadJoypads` (input) and `NMI_DoUpdates` (graphics DMA).
*   **Initialization Logic:** Start at the `Reset:` label in `bank_00.asm` and trace `JSR`/`JSL` calls to routines like `InitializeMemoryAndSRAM`.

## 2. Bank $01: Dungeon Engine

**File:** `ALTTP/bank_01.asm`
**Address Range:** `$018000` - `$01FFFF`
**Summary:** Responsible for loading, drawing, and managing all aspects of interior rooms (dungeons, houses, caves).

### Key Structures & Routines:
*   **`Underworld_LoadRoom:` (#_01873A)**: Main entry point for loading a dungeon room.
*   **`DrawObjects` Tables:** A set of tables at the top of the bank defining object graphics and drawing routines.
*   **`RoomDraw_DrawAllObjects:` (#_0188E4)**: Iterates through a room's object list.
*   **`RoomDraw_RoomObject:` (#_01893C)**: Main dispatcher for drawing a single object based on its ID.

### Search Heuristics:
*   **Room Construction Logic:** In `bank_01.asm`, start at `Underworld_LoadRoom` and trace the call sequence: `Underworld_LoadHeader` -> `RoomDraw_DrawFloors` -> `RoomDraw_DrawAllObjects`.
*   **Specific Dungeon Object Code:** To find an object's drawing code, search the `.type1_subtype_..._routine` tables at the start of `bank_01.asm` for the object's ID. The corresponding label is the drawing routine. To find its tile data, search the `.type1_subtype_..._data_offset` tables.

## 3. Bank $02: Overworld & Transitions

**File:** `ALTTP/bank_02.asm`
**Address Range:** `$028000` - `$02FFFF`
**Summary:** Manages loading the overworld, transitioning between areas, and handling special game sequences.

### Key Structures & Routines:
*   **`Module06_UnderworldLoad:` (#_02821E)**: Primary module for transitioning into and loading an underworld room.
*   **`Module08_OverworldLoad:` (#_0283BF)**: Primary module for loading the overworld.
*   **`Module07_Underworld:` (#_0287A2)**: Main logic loop for when the player is in the underworld. Dispatches to submodules based on WRAM `$11`.

### Search Heuristics:
*   **Overworld Loading:** Start at `Module08_OverworldLoad` in `bank_02.asm`. Logic checks WRAM `$8A` (overworld area number) to determine behavior.
*   **Underworld Gameplay:** Start at `Module07_Underworld` in `bank_02.asm`. Examine the `.submodules` jump table to see the different states, determined by WRAM `$11`.
*   **Transition Logic:** Search for code that sets the game `MODE` (`$10`) to `$08` (Overworld Load) or `$06` (Underworld Load) to find the start of a transition.

## 4. Bank $07: Core Player (Link) Engine

**File:** `ALTTP/bank_07.asm`
**Address Range:** `$078000` - `$07FFFF`
**Summary:** Contains Link's core state machine, governing movement, physics, item usage, and interactions.

### Key Structures & Routines:
*   **`Link_Main:` (#_078000)**: Top-level entry point for all player logic.
*   **`Link_ControlHandler:` (#_07807F)**: The heart of the player engine. A state machine dispatcher that reads `LINKDO` (`$7E005D`) and jumps via the `pool Link_ControlHandler` table.
*   **`LinkState_Default` (#_078109):** The most common state, handling walking and dispatching to action sub-handlers like `Link_HandleYItem`.

### Search Heuristics:
*   **Player Action Logic (walking, swimming):** In `bank_07.asm`, search for `pool Link_ControlHandler`. The state ID is from WRAM `$7E005D` (`LINKDO`). Find the label for the desired state (e.g., `LinkState_Default`) to locate its main routine.
*   **Player Physics/Collision:** Within a player state routine, search for calls to `JSL Link_HandleVelocity` (physics) and `JSR Link_HandleCardinalCollision` (collision).
*   **Y-Button Item Logic:** In `LinkState_Default`, search for the call to `JSR Link_HandleYItem`.
*   **Player Damage Logic:** Search for writes to WRAM `$7E0373` (`HURTME`).

## 5. Bank $05: Specialized Sprite & Object Engine

**File:** `ALTTP/bank_05.asm`
**Address Range:** `$058000` - `$05FFFF`
**Summary:** Code for unique, complex, and scripted sprites that do not fit the standard enemy AI model (e.g., cutscene sprites, minigame hosts, complex traps).

### Search Heuristics:
*   **Unique/Non-Enemy Sprites:** When looking for a unique sprite (minigame, cutscene object, complex trap), check `bank_05.asm` first.
*   **Finding Sprite Logic:** Search for the sprite's name (e.g., "MasterSword") or its hexadecimal ID (e.g., `Sprite_62`) to find its main routine.

## 6. Bank $06: Main Sprite Engine & Helpers

**File:** `ALTTP/bank_06.asm`
**Address Range:** `$068000` - `$06FFFF`
**Summary:** Contains the main sprite processing engine and a vast library of shared helper subroutines used by sprites game-wide.

### Key Structures & Routines:
*   **`Sprite_Main:` (#_068328)**: The master sprite loop that iterates through all 16 sprite slots.
*   **`Sprite_ExecuteSingle:` (#_0684E2)**: The state machine dispatcher for an individual sprite, reading `SprState` (`$7E0DD0,X`).
*   **`SpriteModule_Initialize:` (#_06864D)**: Master initialization routine. Contains a massive jump table pointing to a specific `SpritePrep_...` routine for nearly every sprite type.
*   **`Sprite_SpawnSecret` (`#_068264`):** Determines the "secret" item that appears under a liftable bush or rock.

### Search Heuristics:
*   **Sprite Initialization (HP, damage, etc.):** In `bank_06.asm`, go to `SpriteModule_Initialize`. Find the sprite's ID in the large jump table to get the label for its `SpritePrep_...` routine.
*   **Sprite Core AI:** In `bank_06.asm`, go to `SpriteModule_Active`. Find the sprite's ID in its jump table to find the entry point to its main AI logic (which may be in another bank).
*   **Bush/Rock Item Drops:** Locate the `Sprite_SpawnSecret` routine and examine the `.ID` table at `#_0681F4` to see the prize mappings.

## 7. Bank $08: Ancilla Engine

**File:** `ALTTP/bank_08.asm`
**Address Range:** `$088000` - `$08FFFF`
**Summary:** The engine for "Ancillae" (projectiles, particle effects, etc.). Contains the execution logic for entities like arrows, bombs, and magic spells.

### Search Heuristics:
*   **Projectile/Effect Logic:** In `bank_08.asm`, find the main jump table in `Ancilla_ExecuteOne` (at `#_08837F`). Look up the ancilla's ID in this table to find the label for its logic routine (e.g., `Ancilla07_Bomb`).
*   **Projectile Properties (speed, graphics):** Go to the ancilla's main logic routine (e.g., `Ancilla09_Arrow`) and look for writes to its WRAM properties (e.g., `$0C2C` for X-speed).

## 8. Bank $09: Ancilla Spawning & Item Logic

**File:** `ALTTP/bank_09.asm`
**Address Range:** `$098000` - `$09FFFF`
**Summary:** Contains the ancilla *creation* engine (a library of `AncillaAdd_...` functions) and the critical logic for giving items to the player.

### Search Heuristics:
*   **Projectile/Effect Creation:** To find where a projectile is created, search the codebase for `JSL` calls to its corresponding `AncillaAdd_...` function in this bank (e.g., `JSL AncillaAdd_Bomb`).
*   **Item "Get" Properties:** To change the properties of an item the player receives, find the `AncillaAdd_ItemReceipt` routine and examine the large data tables starting at `#_098404`.

## 9. Bank $0A: World Map & Flute Menu Engine

**File:** `ALTTP/bank_0A.asm`
**Address Range:** `$0A8000` - `$0AFFFF`
**Summary:** Controls all full-screen map interfaces (pause menu map, flute destination map).

### Search Heuristics:
*   **Flute Warp Destinations:** In `bank_0A.asm`, find the `FluteMenu_LoadTransport` routine. The table within it maps the 8 flute spots to screen indexes.
*   **Map Icon Locations:** Search for the `WorldMapIcon_posx_...` and `WorldMapIcon_posy_...` tables to adjust icon coordinates.

## 10. Bank $0B: Overworld Environment & State Helpers

**File:** `ALTTP/bank_0B.asm`
**Address Range:** `$0B8000` - `$0BFFFF`
**Summary:** Miscellaneous helper functions related to the overworld environment and player state.

### Search Heuristics:
*   **Overworld Area Palette:** To change the background color of an overworld area, modify the color values loaded in `Overworld_SetFixedColAndScroll`. The logic checks WRAM `$8A` to decide which color to use.
*   **Wall Master Capture:** To change what happens when captured, find the `WallMaster_SendPlayerToLastEntrance` routine.

## 11. Bank $0C: Intro & Credits Sequence

**File:** `ALTTP/bank_0C.asm`
**Address Range:** `$0C8000` - `$0CFFFF`
**Summary:** Handles the game's intro and end-game credits sequences.

### Search Heuristics:
*   **Intro/Credits Scene Logic:** Start at the `Module00_Intro` or `Module1A_Credits` jump tables. The sub-mode in WRAM `$11` determines which part of the sequence is running. Follow the jump table to the routine for the scene you want to change.

## 12. Bank $0D: Link Animation & OAM Data

**File:** `ALTTP/bank_0D.asm`
**Address Range:** `$0D8000` - `$0DFFFF`
**Summary:** A massive graphical database defining every frame of Link's animation. It is not executable code.

### Search Heuristics:
*   **Link's Animation Sequence:** To modify an animation, find the action in `LinkOAM_AnimationSteps`. The values are indices into the `LinkOAM_PoseData` table, which defines the body parts for each frame.
*   **Link's Item Positioning:** To change how Link holds an item, find the animation frame index in `LinkOAM_AnimationSteps` and use it to find the corresponding entries in the `LinkOAM_SwordOffsetX/Y` or `LinkOAM_ShieldOffsetX/Y` tables.

## 13. Bank $0E: Tile Properties & Credits Engine

**File:** `ALTTP/bank_0E.asm`
**Address Range:** `$0E8000` - `$0EFFFF`
**Summary:** Contains fundamental game assets (font, tile properties) and the credits engine.

### Search Heuristics:
*   **Tile Behavior (e.g., making a wall walkable):** Identify the tile's graphical ID and find its entry in the `OverworldTileTypes` or `UnderworldTileTypes` tables. Change its byte value to match a tile with the desired properties.
*   **Custom Tile Physics (e.g., ice):** Search for the `Underworld_LoadCustomTileTypes` function to see how alternate tile property sets are loaded for specific dungeons.

## 14. Bank $0F: Miscellaneous Game Logic & Helpers

**File:** `ALTTP/bank_0F.asm`
**Address Range:** `$0F8000` - `$0FFFFF`
**Summary:** A collection of important miscellaneous subroutines, including player death and dialogue box initiation.

### Search Heuristics:
*   **Player Death Sequence:** The entry points are `PrepareToDie` and `Link_SpinAndDie`.
*   **Dialogue Box Trigger:** Search for `JSL Interface_PrepAndDisplayMessage`. The code immediately preceding it sets up the message ID to be displayed.

## 15. Bank $1A: Miscellaneous Sprites & Cutscenes

**File:** `ALTTP/bank_1A.asm`
**Address Range:** `$1A8000` - `$1AFFFF`
**Summary:** Logic for a variety of unique sprites, NPCs, and cutscene events that are too specific for the main sprite engine.

### Search Heuristics:
*   **Pyramid of Power Opening:** Search for `BatCrash` or `CreatePyramidHole`.
*   **Waterfall of Wishing Splash:** Search for `SpawnHammerWaterSplash`.
*   **Secret Item Substitution:** To understand how items under rocks are sometimes replaced by enemies, analyze `Overworld_SubstituteAlternateSecret`.

## 16. Bank $1B: Overworld Interaction & Palettes

**File:** `ALTTP/bank_1B.asm`
**Address Range:** `$1B8000` - `$1BFFFF`
**Summary:** The heart of the overworld interaction system. Manages all entrances, pits, and item-based tile interactions (digging, bombing). Also contains a very large store of palette data.

### Search Heuristics:
*   **Overworld Entrances:** To change where a door leads, find its entry in the `Overworld_Entrance...` tables at the top of the bank.
*   **Hidden Item Locations:** To change the item under a specific bush, find the correct `OverworldData_HiddenItems_Screen_XX` table and modify the entry for that bush's coordinates.
*   **Sprite/Armor Colors:** To change a color, find the correct palette in the `PaletteData` section and modify the desired color values.

## 17. Bank $1D & $1E: Advanced Sprite & Boss AI

**Files:** `ALTTP/bank_1D.asm`, `ALTTP/bank_1E.asm`
**Summary:** These banks contain the specific, complex AI for most of the game's major bosses and late-game enemies (Ganon, Moldorm, Trinexx, Helmasaur King, Kholdstare, Agahnim, etc.).

### Search Heuristics:
*   **Boss/Enemy AI:** To modify a specific boss or advanced enemy, search for its `Sprite_...` routine in these two banks (e.g., `Sprite_92_HelmasaurKing` in bank $1E).
*   **Sprite Dispatch Table:** The jump table at `SpriteModule_Active_Bank1E` in `bank_1E.asm` provides a comprehensive list of all sprites managed by that bank and is a good starting point for investigation.
