# Oracle of Secrets Development Guidelines

## 1. Introduction

This document outlines the established coding conventions, architectural patterns, and best practices for the Oracle of Secrets project. Adhering to these guidelines is crucial for maintaining code quality, consistency, and long-term maintainability.

The Oracle of Secrets is a large-scale ROM hack of "The Legend of Zelda: A Link to the Past" for the Super Nintendo. It is built using the `asar` assembler and features a highly modular and data-driven architecture. The project's core philosophy is to replace hardcoded vanilla logic with flexible, data-driven systems, allowing for easier expansion and modification.

## 2. Core Architecture

### 2.1. Game State Management

The game's main loop and state management are handled in `bank_00.asm`. The `Module_MainRouting` routine acts as the primary state machine, using a jump table to execute the logic for the current game state (e.g., Overworld, Underworld, Menu).

### 2.2. Memory Management

The project makes extensive use of both WRAM and SRAM to store custom data and game state.

*   **WRAM (Work RAM):** Located at `$7E0000`, WRAM holds the game's volatile state. A custom region starting at `$7E0730` is reserved for new features, including the Time System, Mask System, and custom item states.
*   **SRAM (Save RAM):** Located at `$7EF000`, SRAM stores the player's save data. The save format has been significantly expanded to accommodate new items, progress flags (`OOSPROG`), and new item data.

### 2.3. Assembly Best Practices (`asar`)

To ensure modern and maintainable assembly code, the project adheres to the following `asar` best practices:

*   **`pushpc`/`pullpc` vs. `org`:** Use `pushpc`/`pullpc` for small, targeted patches. For larger blocks of new code, use `org` to place them in designated free space banks. Avoid using `org` to modify existing vanilla code directly, as this can lead to conflicts.
*   **Scoping:** Use labels followed by `{}` to define local scopes for new logic blocks. This is the established convention, and `subroutine`/`endsubroutine` are not used.
*   **Data Structures:** Use `struct` for complex, related data (e.g., sprite state) and `table` for jump tables or data arrays. This improves readability and reduces errors from manual offset calculations.
*   **Constants:** Use `!` or `define()` to create named constants for RAM/SRAM addresses, item IDs, sprite states, and other "magic numbers." This makes the code self-documenting and easier to maintain.

## 3. Key Custom Systems

Oracle of Secrets introduces several major custom systems that form the foundation of the hack.

### 3.1. `ZSCustomOverworld`

`ZSCustomOverworld` is a data-driven system for managing the overworld. It is configured via a series of tables located at `org $288000` in `Overworld/ZSCustomOverworld.asm`. This system controls:

*   **Palettes:** Day/night and seasonal palette transitions.
*   **Graphics:** Custom graphics sets for different areas.
*   **Overlays:** Data-driven overlays for weather effects and other visual enhancements.
*   **Layouts:** Custom tile arrangements and area layouts.

### 3.2. Time System

The Time System, implemented in `Overworld/time_system.asm`, provides a full day/night cycle. It interacts closely with `ZSCustomOverworld` to manage palette changes and other time-of-day effects.

### 3.3. Mask System

The Mask System, located in the `Masks/` directory, allows Link to transform into different forms with unique abilities. The core transformation logic is handled by the `Link_TransformMask` routine. Each mask has its own file (e.g., `deku_mask.asm`, `zora_mask.asm`) that defines its specific behavior and abilities. The system uses custom WRAM to store the current mask and its state.

### 3.4. Custom Menu & HUD

The `Menu/` directory contains a completely new menu and HUD system. This includes:

*   A two-page menu for items and quest status.
*   A custom item layout and drawing routines.
*   A detailed quest status screen with new icons and text.
*   A custom HUD with a new magic meter and layout.

### 3.5. Custom Items

The `Items/` directory contains the implementation for all new items, such as the Goldstar, Portal Rod, and Ocarina songs. These items often have complex interactions with the player state machine and other game systems.

### 3.6. Sprite Engine

While the main sprite engine from the original game is still used (`bank_06.asm`), Oracle of Secrets introduces a custom sprite system for managing complex sprite behaviors and interactions. The `Sprites/` directory contains the code for all new custom sprites, including NPCs, enemies, and bosses.
`Core/sprite_functions.asm`, `Core/sprite_macros.asm`, `Core/sprite_new_table.asm` and `Sprites/all_sprites.asm` contain the overriden sprite logic and includes for all custom sprites.

## 4. Coding Standards & Style

### 4.1. File and Directory Structure

The project is organized into a modular directory structure. New code should be placed in the appropriate directory based on its functionality (e.g., new items in `Items/`, new sprites in `Sprites/`).

### 4.2. Naming Conventions

*   **Labels:** Use descriptive, CamelCase names for labels (e.g., `LinkState_Swimming`, `Menu_DrawItemName`).
*   **Variables:** Use uppercase for constants (`!CONSTANT_NAME`) and CamelCase for RAM/SRAM variables (`VariableName`).
*   **Macros:** Use CamelCase for macro names (`%MacroName()`).

### 4.3. Commenting

Comments should be used to explain the *why* behind a piece of code, not the *what*. For complex logic, a brief explanation of the algorithm or purpose is helpful. Avoid excessive or obvious comments.

### 4.4. Macros

Macros are used extensively to simplify common tasks and improve code readability. When creating new macros, follow the existing style and ensure they are well-documented.

## 5. Debugging

### 5.1. Common Issues

*   **`BRK` Instructions:** A `BRK` instruction indicates a crash. This is often caused by a P-register mismatch (e.g., calling a 16-bit routine when in 8-bit mode) or a corrupted stack.
*   **P-Register Mismatches:** Always ensure the M and X flags of the processor status register are in the correct state before calling a routine. Use `SEP` and `REP` to switch between 8-bit and 16-bit modes as needed.

### 5.2. Debugging Tools

*   **`!DEBUG` Flag:** The `!DEBUG` flag in `Util/macros.asm` can be used to enable or disable build-time logging.
*   **`%print_debug()` Macro:** This macro can be used to print debug messages and register values during assembly. It is an invaluable tool for tracing code execution and identifying issues.
*   **Emulator Debuggers:** Use an emulator with a robust debugger (e.g., Geiger's Snes9x) to step through code, set breakpoints, and inspect memory.
*   **`usdasm`:** The `usdasm` disassembly is the primary reference for the original game's code. Use it to understand the context of vanilla routines that are being hooked or modified.

## 6. ROM Map & Memory Layout

Oracle of Secrets uses the ZScream expanded ROM map, which provides additional space for new code and data. The following is a brief overview of the key bank allocations:

*   **`$2B8000+`:** Free space for new code and data.
*   **`$288000+`:** `ZSCustomOverworld` configuration tables.
*   **`$7E0730+`:** Custom WRAM region for new features.
*   **`$7EF3D6+`:** Custom SRAM region for new progress flags and item data.

For a more detailed breakdown of the ROM map, refer to the `ZS ROM MAP.txt` file in the `Core/` directory.

---

## 7. Documentation

The following documents have been generated by analyzing the codebase and project files. They serve as key references for understanding the project's architecture and gameplay systems.

*   **`Docs/MemoryMap.md`:** A comprehensive map of all custom WRAM and SRAM variables. See [MemoryMap.md](MemoryMap.md) for details.

*   **`Docs/QuestFlow.md`:** A detailed guide to the main story and side-quest progression, including trigger conditions and progression flags. See [QuestFlow.md](QuestFlow.md) for details.

*   **`Docs/SpriteCreationGuide.md`:** A step-by-step tutorial for creating a new custom sprite using the project's frameworks and conventions. See [SpriteCreationGuide.md](SpriteCreationGuide.md) for details.

*   **`Docs/Menu.md`:** A detailed analysis of the custom menu and HUD systems. See [Menu.md](Menu.md) for details.

*   **`Docs/Items.md`:** A detailed guide to the custom and modified items in the game. See [Items.md](Items.md) for details.

*   **`Docs/Music.md`:** A guide to the custom music tracks and sound effects, including how to add new audio. See [Music.md](Music.md) for details.

*   **`Docs/Masks.md`:** A comprehensive overview of the Mask System, including each mask's abilities and implementation details. See [Masks.md](Masks.md) for details.

*   **`Docs/Dungeons.md`:** A breakdown of all dungeons, including layouts, enemy placements, and puzzle solutions. See [Dungeons.md](Dungeons.md) for details.

*   **`Docs/Overworld.md`:** An analysis of the overworld systems, including `ZSCustomOverworld`, the time system, and other custom features. See [Overworld.md](Overworld.md) for details.

*   **`Docs/NPCs.md`:** An analysis of the various NPC sprites. See [NPCs.md](NPCs.md) for details.

*   **`Docs/Bosses.md`:** An analysis of the custom boss sprites. See [Bosses.md](Bosses.md) for details.

*   **`Docs/Objects.md`:** An analysis of interactive object sprites. See [Objects.md](Objects.md) for details.

*   **`Docs/Overlord.md`:** An analysis of the Overlord sprite system. See [Overlord.md](Overlord.md) for details.
