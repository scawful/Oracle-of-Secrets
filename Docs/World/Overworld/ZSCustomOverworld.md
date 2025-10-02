# ZScream Custom Overworld (`Overworld/ZSCustomOverworld.asm`)

## 1. Overview

ZSCustomOverworld is a powerful and extensive system that replaces large parts of the vanilla *A Link to the Past* overworld engine. Its primary purpose is to remove hardcoded behaviors and replace them with a data-driven approach, allowing for a highly customizable overworld.

Instead of relying on hardcoded logic for palettes, graphics, and layouts, ZSCustomOverworld reads this information from a large pool of data tables located in expanded ROM space (starting at `$288000`). These tables are designed to be edited by the ZScream overworld editor.

## 2. Key Features

- **Custom Palettes & Colors:** Assign a unique main palette and background color to every overworld screen.
- **Custom Graphics:** Assign custom static tile graphics (GFX groups) and animated tile sets to each area.
- **Custom Overlays:** Add or remove subscreen overlays (like rain, fog, and clouds) on a per-area basis.
- **Flexible Layouts:** Fixes vanilla bugs related to screen transitions and adds support for new area sizes, such as 2x1 "wide" and 1x2 "tall" areas, in addition to the standard 1x1 and 2x2.
- **Expanded Special Worlds:** Allows the normally limited "special world" areas (like the Master Sword grove) to be used as full-featured overworld screens.

## 3. Core Architecture: Data Tables

The system's flexibility comes from a large data pool starting at `org $288000`. Key tables include:

- **`.BGColorTable`:** A table of 16-bit color values for the background of each overworld screen.
- **`.EnableTable`:** A series of flags to enable or disable specific features of ZSCustomOverworld, such as custom palettes or overlays.
- **`.MainPaletteTable`:** An index (`$00` to `$05`) into the game's main overworld palette sets for each screen.
- **`.MosaicTable`:** A bitfield for each screen to control mosaic transitions on a per-direction basis.
- **`.AnimatedTable`:** The GFX sheet ID for animated tiles for each screen.
- **`.OverlayTable`:** The overlay ID (e.g., `$9F` for rain) for each screen. `$FF` means no overlay.
- **`.OWGFXGroupTable`:** A large table defining the 8 GFX group sheets to be loaded for each overworld screen.
- **`.Overworld_ActualScreenID_New`:** A table that defines the "parent" screen for multi-screen areas (e.g., for a 2x2 area, all four screens point to the top-left screen's ID).
- **`.ByScreen..._New` Tables:** Four tables (`ByScreen1` for right, `2` for left, `3` for down, `4` for up) that define the camera boundaries for screen transitions. These are crucial for supporting non-standard area sizes.
- **`.Overworld_SpritePointers_state_..._New` Tables:** These tables define which sprite set to load for each overworld area based on the game state (`state_0` for the intro, `state_1` for post-Agahnim 1, `state_2` for post-Ganon). This allows for different enemy and NPC populations as the story progresses.

## 4. Key Hooks & Functions

ZSCustomOverworld replaces dozens of vanilla routines. Some of the most critical hooks are:

- `org $0283EE` (**`PreOverworld_LoadProperties_Interupt`**):
  - **Original:** `Overworld_LoadProperties`. This function loads music, palettes, and GFX when transitioning from a dungeon/house to the overworld.
  - **New Logic:** The ZS version is heavily modified to read from the custom data tables for palettes and GFX instead of using hardcoded logic. It also removes hardcoded music changes for certain exits.

- `org $02C692` (**`Overworld_LoadAreaPalettes`**):
  - **Original:** A routine to load overworld palettes.
  - **New Logic:** Reads the main palette index from the `.MainPaletteTable` instead of using a hardcoded value.

- `org $02A9C4` (**`OverworldHandleTransitions`**):
  - **Original:** The main logic for handling screen-to-screen transitions on the overworld.
  - **New Logic:** This is one of the most heavily modified sections. The new logic uses the custom tables (`.ByScreen...`, `.Overworld_ActualScreenID_New`, etc.) to handle transitions between areas of different sizes, fixing vanilla bugs and allowing for new layouts.

- `org $02AF58` (**`Overworld_ReloadSubscreenOverlay_Interupt`**):
  - **Original:** Logic for loading subscreen overlays.
  - **New Logic:** Reads the overlay ID from the `.OverlayTable` instead of using hardcoded checks for specific areas (like the Misery Mire rain).

- `org $09C4C7` (**`LoadOverworldSprites_Interupt`**):
    - **Original:** `LoadOverworldSprites`. This function determines which sprites to load for the current overworld screen.
    - **New Logic:** The ZS version reads from the `.Overworld_SpritePointers_state_..._New` tables based on the current game state (`$7EF3C5`) to get a pointer to the correct sprite set for the area. This allows for dynamic sprite populations.

## 5. Configuration

- **`!UseVanillaPool`:** A flag that, when set to 1, forces the system to use data tables that mimic the vanilla game's behavior. This is useful for debugging.
- **`!Func...` Flags:** A large set of individual flags that allow for enabling or disabling specific hooks. This provides granular control for debugging and compatibility testing.

## 6. Analysis & Future Work: Sprite Loading

The `LoadOverworldSprites_Interupt` hook at `org $09C4C7` is a critical component that requires further investigation to support dynamic sprite sets, such as those needed for a day/night cycle.

- **Identified Conflict:** The current ZScream implementation for sprite loading conflicts with external logic that attempts to swap sprite sets based on in-game conditions (e.g., time of day). The original hook's design, which calls `JSL.l Sprite_OverworldReloadAll`, can lead to recursive loops and stack overflows if not handled carefully.

- **Investigation Goal:** The primary goal is to modify `LoadOverworldSprites_Interupt` to accommodate multiple sprite sets for a single area. The system needs to be able to check a condition (like whether it is currently night) and then select the appropriate sprite pointer, rather than relying solely on the static `state_..._New` tables.

- **Technical Challenges:** A previous attempt to integrate this functionality was reverted due to build system issues where labels from other modules (like `Oracle_CheckIfNight16Bit`) were not visible to `ZSCustomOverworld.asm`. A successful solution will require resolving these cross-module dependencies and carefully merging the day/night selection logic with ZScream's existing data-driven approach to sprite loading.
