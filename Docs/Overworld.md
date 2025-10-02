# Overworld Systems Analysis

## 1. Overview

The `Overworld/` directory contains all code and data related to the game's overworld, including rendering, transitions, time-based events, and custom features. The architecture is centered around `ZSCustomOverworld.asm` (ZSOW), a powerful data-driven system that replaces most of the vanilla game's hardcoded overworld logic.

The primary goal of the overworld code is to provide a flexible and expandable framework for creating a dynamic world. This is achieved by hooking into the original game's engine and replacing static logic with routines that read from configurable data tables in expanded ROM space.

## 2. Core Systems

These two systems form the backbone of the custom overworld engine.

### 2.1. `ZSCustomOverworld.asm` (ZSOW)

ZSOW is the heart of the overworld engine. It replaces vanilla logic for palettes, graphics, overlays, transitions, and sprite loading with a highly configurable, data-driven approach. Its behavior is defined by a large pool of data tables starting at `org $288000`.

**Key Responsibilities:**

*   **Data-Driven Configuration:** Reads from tables like `.MainPaletteTable`, `.OWGFXGroupTable`, and `.OverlayTable` to define the look and feel of each of the 160 overworld screens.
*   **Flexible Layouts:** Fixes vanilla transition bugs and adds support for non-standard area sizes (e.g., 2x1 "wide" and 1x2 "tall" areas) via custom camera boundary tables (`.ByScreen..._New`).
*   **Dynamic Sprite Loading:** Uses the `.Overworld_SpritePointers_state_..._New` tables to load different sprite sets based on the current game state (`$7EF3C5`), allowing enemy and NPC populations to change as the story progresses.
*   **Extensive Hooks:** Intercepts dozens of vanilla routines to apply its custom logic. Key hooks include `PreOverworld_LoadProperties_Interupt` (`$0283EE`) for loading area properties, `OverworldHandleTransitions` (`$02A9C4`) for screen transitions, and `LoadOverworldSprites_Interupt` (`$09C4C7`) for sprite loading.

### 2.2. `time_system.asm`

This system implements a full 24-hour day/night cycle, which is crucial for many of the game's puzzles and atmospheric effects.

**Key Features:**

*   **In-Game Clock:** Maintains the current time in SRAM (`Hours` at `$7EE000`, `Minutes` at `$7EE001`).
*   **Palette Modulation:** The `ColorSubEffect` routine dynamically modifies palettes written to CGRAM to simulate changing light levels. It uses lookup tables to determine the correct color subtraction values for each hour.
*   **Time-Based Events:** Includes logic for daily events (e.g., the Magic Bean side-quest) and handling time manipulation via the Song of Time.
*   **HUD Integration:** The `DrawClockToHud` routine displays the current time on the player's HUD.

## 3. Sub-Systems and Features

These files implement specific, modular overworld features.

### 3.1. `entrances.asm`

This file expands the vanilla entrance system, allowing for more complex and custom door behaviors.

*   It hooks the main entrance routine (`$1BBBF4`) to call `Overworld_UseEntrance`, which uses an expanded list of valid door tile types (`ValidDoorTypesExpanded`).
*   It contains the logic to check for follower restrictions and other entry conditions before transitioning the player to an interior map.

### 3.2. `overlays.asm`

This system manages complex, animated overlays for special entrances that are triggered on the overworld map, such as opening a dungeon.

*   It defines multi-frame animation sequences for events like the Zora Temple waterfall parting, the castle drawbridge lowering, and the Fortress of Secrets entrance opening.
*   Each animation is a state machine that uses a timer (`$C8`) and a frame counter (`$B0`) to step through a sequence of tile-drawing and screen-shaking routines.

### 3.3. `lost_woods.asm`

This implements the classic "repeating maze" puzzle for the Lost Woods (Area `$29`).

*   It hooks into the overworld transition logic to check if the player is exiting the Lost Woods screen.
*   It compares the player's exit direction against a correct, predefined sequence.
*   If the sequence is wrong, it manually manipulates the player and camera coordinates to loop them back to the same screen, creating the illusion of being lost.

### 3.4. `special_areas.asm`

This file enhances the functionality of vanilla "special overworld" areas (like the Master Sword grove), allowing them to be used as full-featured screens.

*   `Overworld_CheckForSpecialOverworldTrigger` checks if the player is interacting with a tile that should lead to a special area.
*   `LoadSpecialOverworld` is a critical function that sets up the unique properties for these areas, including camera boundaries, palettes, and GFX, by reading from its own set of data tables. This allows for more than the original game's limited number of special areas.

### 3.5. `custom_gfx.asm`

This file contains routines for loading custom graphics sheets into VRAM for specific overworld areas or events. The primary example is `CheckForChangeGraphicsNormalLoadBoat`, which loads custom boat graphics when the player is in area `$30`.

### 3.6. `world_map.asm`

This file contains significant modifications to the full-screen world map.

*   It replaces the vanilla icon drawing logic with custom routines (`DrawPowerPendant`, `DrawMasterSwordIcon`, etc.) to display the status of new quest items and dungeons.
*   It includes logic to display different icons based on Light World vs. Dark World and overall game progression (`OOSPROG`).
*   It implements custom DMA routines (`DMAOwMap`, `DMAOwMapGfx`) to load entirely new world map tilesets and graphics from expanded ROM (`$408000` and `$418000`).

## 4. System Interactions & Porting Status

Integrating ZSOW with existing custom systems is an ongoing effort. The status of these interactions is critical for development.

*   **Time System (Palette Modulation):** **Compatible.** The Time System's `LoadDayNightPaletteEffect` acts as a filter on all CGRAM writes. When ZSOW loads a new base palette for an area, the Time System intercepts the write and applies the day/night color subtraction automatically.

*   **Day/Night Sprites:** **Resolved.** The conflict where ZSOW's sprite loader bypassed the old day/night logic has been fixed. A `JSL CheckIfNight` call is now integrated directly into ZSOW's `LoadOverworldSprites_Interupt`. This allows ZSOW's sprite tables to correctly load different sprite sets for day and night by using adjacent game states (e.g., state 2 for day, state 3 for night).

*   **Lost Woods Puzzle:** **Direct Conflict.** The Lost Woods puzzle's transition override is currently incompatible with ZSOW's more complex transition handler. The `lost_woods.asm` code needs to be refactored into a subroutine that can be called from within `OverworldHandleTransitions` in `ZSCustomOverworld.asm`.

*   **Song of Storms (Overlays):** **Resolved.** The conflict where ZSOW would overwrite the rain overlay on screen transitions has been fixed. A new SRAM flag (`SRAM_StormsActive`) tracks the storm state, and a new routine, `HandleStormsOverlay`, is called every frame to enforce the rain overlay if the flag is active, ensuring it persists across transitions.

## 5. File Index

*   `ZSCustomOverworld.asm`: The core data-driven overworld engine. Manages palettes, GFX, overlays, transitions, and sprite loading.
*   `time_system.asm`: Manages the 24-hour clock, day/night palette effects, and time-based events.
*   `overworld.asm`: Main include file for the directory; contains various small patches.
*   `entrances.asm`: Handles logic for entering caves, houses, and dungeons from the overworld.
*   `overlays.asm`: Manages animated entrance sequences (e.g., waterfalls, drawbridges).
*   `lost_woods.asm`: Implements the Lost Woods maze puzzle.
*   `special_areas.asm`: Expands the functionality of special overworld areas like the Master Sword grove.
*   `custom_gfx.asm`: Routines for loading custom graphics for specific areas or objects.
*   `world_map.asm`: Code for the custom full-screen world map, including new icons and map graphics.
*   `HardwareRegisters.asm`: `struct` definitions for SNES hardware registers, used for context.
