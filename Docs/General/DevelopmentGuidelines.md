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

*   **`org` for New Code and Data:** Use `org $XXXXXX` to place larger blocks of new code or data into designated free space banks. The `incsrc` order in `Oracle_main.asm` is critical when using `org`, as it directly determines the final ROM layout. Moving `org` blocks or changing the `incsrc` order can lead to memory conflicts or incorrect addressing.
*   **`pushpc`/`pullpc` for Targeted Patches:** Use `pushpc`/`pullpc` for small, targeted modifications to existing vanilla code or data. This directive temporarily changes the program counter, allowing a small patch to be inserted at a specific address without affecting the surrounding `org` context. Files like `Core/patches.asm` and `Util/item_cheat.asm` extensively use `pushpc`/`pullpc` for this purpose.
*   **Scoping:** Use labels followed by `{}` to define local scopes for new logic blocks. This is the established convention, and `subroutine`/`endsubroutine` are not used.
*   **Data Structures:** Use `struct` for complex, related data (e.g., sprite state) and `table` for jump tables or data arrays. This improves readability and reduces errors from manual offset calculations.
*   **Constants:** Use `!` or `define()` to create named constants for RAM/SRAM addresses, item IDs, sprite states, and other "magic numbers." This makes the code self-documenting and easier to maintain.

### 2.4. Namespace Architecture

Oracle of Secrets uses a mixed namespace architecture to organize code and manage symbol visibility:

*   **`Oracle` Namespace:** Most custom code is placed within the `namespace Oracle { }` block. This includes Items, Menu, Masks, Time System, and most custom features.
*   **ZScream (No Namespace):** The `ZSCustomOverworld` system operates outside any namespace, as it needs to hook directly into vanilla bank addresses.
*   **Cross-Namespace Calling:** When Oracle code needs to call ZScream functions, or vice versa, proper exports must be defined:

```asm
// In ZScream file:
LoadOverworldSprites_Interupt:
{
    ; ... ZScream code ...
    RTL
}

// Export to Oracle namespace:
namespace Oracle
{
    Oracle_LoadOverworldSprites_Interupt = LoadOverworldSprites_Interupt
}
```

*   **Bridge Functions:** When ZScream needs to call Oracle code, use a bridge function pattern:

```asm
// Oracle implementation:
namespace Oracle
{
    CheckIfNight:
        ; Main implementation
        RTL
}

// Bridge function (no namespace):
ZSO_CheckIfNight:
{
    JSL Oracle_CheckIfNight  ; Can call INTO Oracle
    RTL
}

// Export bridge:
namespace Oracle
{
    Oracle_ZSO_CheckIfNight = ZSO_CheckIfNight
}
```

**Important:** Always use the `Oracle_` prefix when calling exported functions from within the Oracle namespace. See `Docs/World/Overworld/ZSCustomOverworldAdvanced.md` Section 5 for detailed examples.

### 2.5. Processor State Management

The 65816 processor has critical flags (M and X) that control register sizes:

*   **M Flag (bit 5):** Controls Accumulator size (0=16-bit, 1=8-bit)
*   **X Flag (bit 4):** Controls Index register size (0=16-bit, 1=8-bit)

**Best Practices:**

1. **Initialize at function entry:**
   ```asm
   MyFunction:
       PHP              ; Save caller's state
       SEP #$30         ; Set to known 8-bit state
       ; ... your code ...
       PLP              ; Restore caller's state
       RTL
   ```

2. **Be explicit about sizes:**
   ```asm
   REP #$20         ; A = 16-bit
   LDA.w #$1234     ; Load 16-bit value
   
   SEP #$20         ; A = 8-bit
   LDA.b #$12       ; Load 8-bit value only
   ```

3. **Document function requirements:**
   ```asm
   ; Function: CalculateOffset
   ; Inputs: A=16-bit (offset), X=8-bit (index)
   ; Outputs: A=16-bit (result)
   ; Status: Returns with P unchanged (uses PHP/PLP)
   ```

4. **Cross-namespace calls:** Be especially careful when calling between Oracle and ZScream code, as they may use different processor states.

See `Docs/General/Troubleshooting.md` Section 3 for common processor state issues and solutions.

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

*   **`BRK` Instructions:** A `BRK` instruction indicates a crash. This is often caused by:
    *   Jumping to invalid memory (uninitialized ROM, data instead of code)
    *   P-register mismatch (e.g., calling a 16-bit routine when in 8-bit mode)
    *   Stack corruption (unbalanced push/pop, JSR/JSL vs RTS/RTL mismatch)
    *   Return without matching call (RTL executed without previous JSL)
    
*   **P-Register Mismatches:** Always ensure the M and X flags of the processor status register are in the correct state before calling a routine. Use `SEP` and `REP` to switch between 8-bit and 16-bit modes as needed.

*   **Stack Corruption:** Ensure push/pop operations are balanced and that JSR is paired with RTS (2 bytes) while JSL is paired with RTL (3 bytes). Never mix them.

*   **Namespace Visibility:** If you get "label not found" errors, verify:
    *   Label is exported with `Oracle_` prefix
    *   File is included in correct build order in `Oracle_main.asm`
    *   Namespace block is properly closed

*   **Memory Conflicts:** If you get "overwrote some code" warnings:
    *   Check for overlapping `org` directives
    *   Use `assert pc() <= $ADDRESS` to protect boundaries
    *   Review ROM map in Section 6 for available space

**For comprehensive troubleshooting guidance, see `Docs/General/Troubleshooting.md` which covers:**
- BRK crash debugging with emulator tools
- Stack corruption patterns
- Processor status register issues
- Cross-namespace calling problems
- Memory conflicts and bank collisions
- Graphics/DMA timing issues
- ZScream-specific problems

### 5.2. Debugging Tools

*   **Mesen-S (Recommended):** The most powerful SNES debugger with:
    *   Execution breakpoints with conditions
    *   Memory watchpoints (read/write/execute)
    *   Stack viewer
    *   Event viewer (NMI/IRQ timing)
    *   Live memory updates
    
*   **BSNES-Plus:** Cycle-accurate emulator with:
    *   Memory editor with search
    *   Tilemap and VRAM viewers
    *   Debugger with disassembly

*   **`!DEBUG` Flag:** The `!DEBUG` flag in `Util/macros.asm` can be used to enable or disable build-time logging.

*   **`%print_debug()` Macro:** This macro can be used to print debug messages and register values during assembly. It is an invaluable tool for tracing code execution and identifying issues.

*   **Breadcrumb Tracking:** Add markers to narrow down crash locations:
    ```asm
    LDA.b #$01 : STA.l $7F5000  ; Breadcrumb 1
    JSL SuspiciousFunction
    LDA.b #$02 : STA.l $7F5000  ; Breadcrumb 2
    ; After crash, check $7F5000 to see which breadcrumb was reached
    ```

*   **Vanilla Disassembly:** The ALTTP disassembly in `ALTTP/` is the primary reference for the original game's code. Use it to understand the context of vanilla routines that are being hooked or modified.

### 5.3. Debugging Checklist

When encountering an issue:

1. ✅ Check error message carefully - Asar errors are usually precise
2. ✅ Verify namespace - Is label prefixed correctly?
3. ✅ Check stack balance - Equal push/pop counts?
4. ✅ Verify processor state - REP/SEP correct for operation?
5. ✅ Check memory bounds - Assertions in place?
6. ✅ Test in Mesen-S first - Best debugger for SNES
7. ✅ Use breadcrumbs - Narrow down crash location
8. ✅ Check build order - Files included in correct order?
9. ✅ Review recent changes - Compare with known working version
10. ✅ Read vanilla code - Understand what you're hooking

## 6. ROM Map & Memory Layout

Oracle of Secrets utilizes the ZScream expanded ROM map, providing significant additional space for new code and data. The allocation of custom code and data within these banks is managed through `org` directives in the assembly files. The `incsrc` order in `Oracle_main.asm` is crucial, as it dictates the final placement of these blocks in the ROM.

Here is a detailed overview of the custom ROM bank allocations:

| Bank (Hex) | Address Range (PC) | Purpose / Contents                                     | Defining File(s)                      |
|------------|--------------------|--------------------------------------------------------|---------------------------------------|
| $20        | `$208000` - `$20FFFF` | Expanded Music                                         | `Music/all_music.asm`                 |
| $21-$27    |                    | ZScream Reserved                                       |                                       |
| $28        | `$288000` - `$28FFFF` | ZSCustomOverworld data and code                        | `Overworld/ZSCustomOverworld.asm`     |
| $29-$2A    |                    | ZScream Reserved                                       |                                       |
| $2B        | `$2B8000` - `$2BFFFF` | Items                                                  | `Items/all_items.asm`                 |
| $2C        | `$2C8000` - `$2CFFFF` | Underworld/Dungeons                                    | `Dungeons/dungeons.asm`               |
| $2D        | `$2D8000` - `$2DFFFF` | Menu                                                   | `Menu/menu.asm`                       |
| $2E        | `$2E8000` - `$2EFFFF` | HUD                                                    | `Menu/menu.asm`                       |
| $2F        | `$2F8000` - `$2FFFFF` | Expanded Message Bank                                  | `Core/message.asm`                    |
| $30        | `$308000` - `$30FFFF` | Sprites                                                | `Sprites/all_sprites.asm`             |
| $31        | `$318000` - `$31FFFF` | Sprites                                                | `Sprites/all_sprites.asm`             |
| $32        | `$328000` - `$32FFFF` | Sprites                                                | `Sprites/all_sprites.asm`             |
| $33        | `$338000` - `$33FFFF` | Moosh Form Gfx and Palette                             | `Masks/all_masks.asm`                 |
| $34        | `$348000` - `$34FFFF` | Time System, Custom Overworld Overlays, Gfx            | `Masks/all_masks.asm`                 |
| $35        | `$358000` - `$35FFFF` | Deku Link Gfx and Palette                              | `Masks/all_masks.asm`                 |
| $36        | `$368000` - `$36FFFF` | Zora Link Gfx and Palette                              | `Masks/all_masks.asm`                 |
| $37        | `$378000` - `$37FFFF` | Bunny Link Gfx and Palette                             | `Masks/all_masks.asm`                 |
| $38        | `$388000` - `$38FFFF` | Wolf Link Gfx and Palette                              | `Masks/all_masks.asm`                 |
| $39        | `$398000` - `$39FFFF` | Minish Link Gfx                                        | `Masks/all_masks.asm`                 |
| $3A        | `$3A8000` - `$3AFFFF` | Mask Routines, Custom Ancillae (Deku Bubble)           | `Masks/all_masks.asm`                 |
| $3B        | `$3B8000` - `$3BFFFF` | GBC Link Gfx                                           | `Masks/all_masks.asm`                 |
| $3C        |                    | Unused                                                 |                                       |
| $3D        |                    | ZS Tile16                                              |                                       |
| $3E        |                    | LW ZS Tile32                                           |                                       |
| $3F        |                    | DW ZS Tile32                                           |                                       |
| $40        | `$408000` - `$40FFFF` | LW World Map                                           | `Overworld/overworld.asm`             |
| $41        | `$418000` - `$41FFFF` | DW World Map                                           | `Overworld/overworld.asm`             |
| Patches    | Various            | Targeted modifications within vanilla ROM addresses    | `Core/patches.asm`, `Util/item_cheat.asm` |

For a more detailed breakdown of the ROM map, refer to the `ZS ROM MAP.txt` file in the `Core/` directory, and `Docs/Core/MemoryMap.md` for a comprehensive overview of all custom memory regions.

---

## 7. Documentation

The following documents have been generated by analyzing the codebase and project files. They serve as key references for understanding the project's architecture and gameplay systems.

*   **`Docs/Core/MemoryMap.md`:** A comprehensive map of all custom WRAM and SRAM variables, including repurposed vanilla blocks. See [MemoryMap.md](../Core/MemoryMap.md) for details.

*   **`Docs/Core/Ram.md`:** High-level overview of WRAM and SRAM usage with verified custom variables. See [Ram.md](../Core/Ram.md) for details.

*   **`Docs/World/Overworld/ZSCustomOverworldAdvanced.md`:** Advanced technical guide for ZScream integration, including hook architecture, sprite loading system, cross-namespace integration, and performance considerations. See [ZSCustomOverworldAdvanced.md](../World/Overworld/ZSCustomOverworldAdvanced.md) for details.

*   **`Docs/General/Troubleshooting.md`:** Comprehensive troubleshooting guide covering BRK crashes, stack corruption, processor state issues, namespace problems, memory conflicts, and graphics issues. See [Troubleshooting.md](Troubleshooting.md) for details.

*   **`Docs/QuestFlow.md`:** A detailed guide to the main story and side-quest progression, including trigger conditions and progression flags. See [QuestFlow.md](../QuestFlow.md) for details.

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
