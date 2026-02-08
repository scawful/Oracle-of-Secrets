# Oracle of Secrets Development Guidelines

## 1. Introduction

This document outlines the established coding conventions, architectural patterns, and best practices for the Oracle of Secrets project. Adhering to these guidelines is crucial for maintaining code quality, consistency, and long-term maintainability.

The Oracle of Secrets is a large-scale ROM hack of "The Legend of Zelda: A Link to the Past" for the Super Nintendo. It is built using the `asar` assembler and features a highly modular and data-driven architecture. The project's core philosophy is to replace hardcoded vanilla logic with flexible, data-driven systems, allowing for easier expansion and modification.

NOTE: Vanilla disassembly is external. In this workspace, JP gigaleak disassembly lives under `../alttp-gigaleak/DISASM/jpdasm/`. If you generate a US `usdasm` export for address parity, it lives under `../alttp-gigaleak/DISASM/usdasm/`. Adjust paths if your setup differs.

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

See `Docs/Debugging/Guides/Troubleshooting.md` Section 3 for common processor state issues and solutions.

### 2.6. Module Isolation System

Oracle of Secrets supports selectively disabling entire feature modules at assembly time. This is primarily used for **bug isolation** — when a regression appears, disabling modules one at a time via binary search identifies which module introduced the problem.

#### Configuration

Module disable flags live in `Util/macros.asm`:

```asm
!DISABLE_MUSIC     = 0   ; Music/all_music.asm (Bank $20)
!DISABLE_OVERWORLD = 0   ; Overworld/overworld.asm + ZSCustomOverworld.asm (Banks $28, $40-$41)
!DISABLE_DUNGEON   = 0   ; Dungeons/dungeons.asm (Bank $2C)
!DISABLE_SPRITES   = 0   ; Sprites/all_sprites.asm (Banks $30-$32)
!DISABLE_MASKS     = 0   ; Masks/all_masks.asm (Banks $33-$3B)
!DISABLE_ITEMS     = 0   ; Items/all_items.asm (Bank $2B)
!DISABLE_MENU      = 0   ; Menu/menu.asm (Banks $2D-$2E)
!DISABLE_PATCHES   = 0   ; Core/patches.asm (vanilla ROM address patches)
```

Set a flag to `1` to exclude that module from assembly. The build output will print `*** MODULE DISABLED ***` for each excluded module.

#### Usage

```bash
# 1. Edit Util/macros.asm — set !DISABLE_MASKS = 1
# 2. Rebuild
./scripts/build_rom.sh 168
# 3. Test in emulator — does the bug reproduce?
# 4. Repeat: re-enable, disable next module
```

#### Module Inventory

| Module | Flag | Hooks | Banks | What It Does |
|--------|------|-------|-------|--------------|
| Music | `!DISABLE_MUSIC` | 9 | $20 | Custom BGM, expanded song table |
| Overworld | `!DISABLE_OVERWORLD` | 180 | $28, $40-$41 | World map, transitions, camera, overlays, ZSCustomOverworld |
| Dungeon | `!DISABLE_DUNGEON` | 115 | $2C | Underworld logic, floor puzzles, key blocks, warp tags |
| Sprites | `!DISABLE_SPRITES` | 76 | $30-$32 | Custom NPCs, bosses, enemies, sprite dispatch table |
| Masks | `!DISABLE_MASKS` | 51 | $33-$3B | Transformation forms (Deku, Zora, Wolf, Bunny, Minish), GFX |
| Items | `!DISABLE_ITEMS` | 64 | $2B | Custom items (fishing rod, portal rod, ocarina, magic rings) |
| Menu | `!DISABLE_MENU` | 66 | $2D-$2E | HUD, item box, quest journal, song menu |
| Patches | `!DISABLE_PATCHES` | ~20 | Various | Targeted vanilla ROM fixes (NPC behavior, sprite prep, etc.) |

#### Dependencies

Disabling a module may cause assembly errors if other modules reference its symbols. Known cross-module dependencies:

| Module | Depends On | Symbols Referenced |
|--------|------------|--------------------|
| Sprites | Items | `ForcePrizeDrop_long`, damage class tables |
| Masks | Sprites, Core | Sprite state addresses, ancilla routines |
| Items | Sprites | `Sprite_TransmuteToBomb`, sprite spawn routines |
| Menu | Items | Item address index tables, bottle content |
| Dungeon | Sprites | Sprite prep pointers, enemy behavior |

If a dependency error occurs, either:
1. **Disable both modules** (the depending and depended-on module)
2. **Add a stub** — define the missing symbol as a no-op address in `Core/symbols.asm`

#### Recommended Isolation Order

For binary search, disable in order of decreasing isolation safety (least likely to cause dependency errors):

1. **Masks** — most self-contained, transformation GFX + routines
2. **Music** — fully standalone
3. **Menu** — HUD/journal, vanilla UI still works without it
4. **Items** — custom items disabled, vanilla items still work
5. **Patches** — targeted vanilla fixes, low risk
6. **Sprites** — custom sprite dispatch, may break NPC interactions
7. **Dungeon** — underworld hooks, breaks dungeon gameplay
8. **Overworld** — world map + camera, breaks overworld gameplay

#### Core (Always Included)

These files are always assembled regardless of module flags:

| File | Purpose |
|------|---------|
| `Util/macros.asm` | Assembly macros, flags, logging |
| `Core/structs.asm` | Data structure definitions |
| `Core/ram.asm` | Vanilla WRAM/SRAM address definitions |
| `Core/link.asm` | Link state and movement hooks |
| `Core/sram.asm` | Save RAM layout and access |
| `Core/symbols.asm` | Vanilla routine addresses (used by all modules) |
| `Core/message.asm` | Expanded dialogue system (Bank $2F) |

These form the minimum viable Oracle ROM. Disabling all optional modules produces a ROM with vanilla gameplay plus the Core hooks, SRAM layout, and message system.

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

**For comprehensive troubleshooting guidance, see `Docs/Debugging/Guides/Troubleshooting.md` which covers:**
- BRK crash debugging with emulator tools
- Stack corruption patterns
- Processor status register issues
- Cross-namespace calling problems
- Memory conflicts and bank collisions
- Graphics/DMA timing issues
- ZScream-specific problems

### 5.2. Debugging Tools

**Agent rule:** For any agent-driven debugging or automation, use only the Mesen2 OOS fork. Other emulators listed here are for human reference only unless explicitly authorized.

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

For a more detailed breakdown of the ROM map, refer to the `ZS ROM MAP.txt` file in the `Core/` directory, and `Docs/Technical/Core/MemoryMap.md` for a comprehensive overview of all custom memory regions.

---

## 7. Documentation

The following documents have been generated by analyzing the codebase and project files. They serve as key references for understanding the project's architecture and gameplay systems.

*   **`Docs/Technical/Core/MemoryMap.md`:** A comprehensive map of all custom WRAM and SRAM variables, including repurposed vanilla blocks. See [MemoryMap.md](../Core/MemoryMap.md) for details.

*   **`Docs/Technical/Core/Ram.md`:** High-level overview of WRAM and SRAM usage with verified custom variables. See [Ram.md](../Core/Ram.md) for details.

*   **`Docs/World/Overworld/ZSCustomOverworldAdvanced.md`:** Advanced technical guide for ZScream integration, including hook architecture, sprite loading system, cross-namespace integration, and performance considerations. See [ZSCustomOverworldAdvanced.md](../World/Overworld/ZSCustomOverworldAdvanced.md) for details.

*   **`Docs/Debugging/Guides/Troubleshooting.md`:** Comprehensive troubleshooting guide covering BRK crashes, stack corruption, processor state issues, namespace problems, memory conflicts, and graphics issues. See [Troubleshooting.md](Troubleshooting.md) for details.

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
