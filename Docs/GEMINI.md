# Gemini Development Guidelines for Oracle of Secrets

This document outlines the established coding conventions, architectural patterns, and best practices observed in the Oracle of Secrets project. Adhering to these guidelines will ensure consistency and maintainability.

## 1. SNES 65816 Processor Basics

### 1.1. Architecture Overview

The 65816 is an 8/16-bit microprocessor used in the Super Nintendo Entertainment System (SNES). It operates in two modes: emulation mode (6502-compatible, 8-bit) and native mode (65816, 16-bit). The SNES typically runs in native mode.

### 1.2. Key Registers

- **A (Accumulator):** The primary register for data manipulation. Its size (8-bit or 16-bit) is controlled by the M flag in the Processor Status Register.
- **X, Y (Index Registers):** Used for addressing memory. Their size (8-bit or 16-bit) is controlled by the X flag in the Processor Status Register.
- **S (Stack Pointer):** Points to the current top of the stack.
- **D (Direct Page Register):** Used for direct page addressing, allowing faster access to the first 256 bytes of each bank.
- **DB (Data Bank Register):** Specifies the current 64KB data bank for memory accesses.
- **PB (Program Bank Register):** Specifies the current 64KB program bank for instruction fetches.
- **P (Processor Status Register):** A crucial 8-bit register containing various flags:
    - **N (Negative):** Set if the result of an operation is negative.
    - **V (Overflow):** Set if an arithmetic overflow occurs.
    - **M (Memory/Accumulator Select):** Controls the size of the A register (0=16-bit, 1=8-bit).
    - **X (Index Register Select):** Controls the size of the X and Y registers (0=16-bit, 1=8-bit).
    - **D (Decimal Mode):** Enables BCD arithmetic (rarely used in SNES development).
    - **I (IRQ Disable):** Disables interrupt requests.
    - **Z (Zero):** Set if the result of an operation is zero.
    - **C (Carry):** Used for arithmetic operations and bit shifts.

### 1.3. Processor Status Register (P) Manipulation

- **`SEP #$20` (or `SEP #$30`):** Sets the M flag (and X flag if $30 is used) to 1, switching A (and X/Y) to 8-bit mode.
- **`REP #$20` (or `REP #$30`):** Resets the M flag (and X flag if $30 is used) to 0, switching A (and X/Y) to 16-bit mode.
- **Importance:** Mismatched M/X flags between calling and called routines are a common cause of crashes (BRKs) or unexpected behavior. Always ensure the P register is in the expected state for a given routine, or explicitly set it.

### 1.4. Memory Mapping

- The SNES has a 24-bit address space, allowing access to up to 16MB of ROM/RAM.
- **Banks:** Memory is organized into 256 banks of 64KB each.
- **Direct Page (Bank 00):** The first 256 bytes of bank 00 (`$0000-$00FF`) are special and can be accessed quickly using direct page addressing (when D=0).
- **WRAM (Work RAM):** Located in banks $7E-$7F. This is where most game variables and temporary data are stored.
- **SRAM (Save RAM):** Typically located in banks $70-$7D, used for saving game progress.

## 2. Asar Best Practices

### 2.1. `pushpc`/`pullpc` and `org`

- **Guideline:** While `pushpc`/`pullpc` is good for isolating small, targeted patches, extreme care must be taken. Patches that use `org` to place new code into freespace (e.g., `org $2B8000`) have a dependency on their location within the file. Moving these `org` blocks can break the ROM by changing the memory layout.
- **Rationale:** The order of `incsrc` and `org` directives determines the final ROM layout. Moving a freespace `org` block to a central `patches.asm` file changes this order and will likely cause errors. Simple, single-line patches that modify existing vanilla code can often be moved, but larger blocks of new code should remain in their contextually relevant files.

### 2.2. Scoping and Style

- **Guideline:** The established code style uses labels followed by `{}` brackets to define scope for new blocks of logic. This convention must be followed. The `subroutine`/`endsubroutine` keywords are explicitly *not* to be used in this project.
- **Rationale:** The `subroutine`/`endsubroutine` keywords are not used in this project. Maintaining a consistent style is crucial for readability.

### 2.3. Data Organization

- **Guideline:** For complex, related data (like sprite state or system configurations), use `struct`. For jump tables or data arrays, use `table`.
- **Rationale:** These directives make data structures explicit and readable. They replace confusing pointer arithmetic and manual offset calculations with clear, named accessors, which is less error-prone.

### 2.4. Define Constants for Magic Numbers

- **Guideline:** Avoid hardcoding numerical values. Use `!` or `define()` to create named constants for RAM/SRAM addresses, item IDs, sprite states, tile IDs, etc.
- **Rationale:** This makes the code self-documenting and significantly easier to maintain and debug.

### 2.5. Opcode Size Suffixes (.b, .w, .l)

`asar` can often infer operand sizes, but relying on this can lead to bugs when the processor state (M and X flags) is not what you expect. To write robust, readable, and safe code, you should use explicit size suffixes.

- **`.b` (byte):** Forces an 8-bit operation. Use this when you are certain you are working with a single byte.
    - Example: `LDA.b $7E0010` will correctly load a single byte into the accumulator, regardless of the M flag's state.
- **`.w` (word):** Forces a 16-bit operation. Use this when working with two bytes (a word).
    - Example: `LDA.w $7E0022` will load a 16-bit value. This is essential for correctness if the M flag is 1 (8-bit mode).
- **`.l` (long):** Forces a 24-bit operation, typically for addresses in `JML` or `JSL`.
    - Example: `JSL.l SomeRoutineInAnotherBank`

**Golden Rule:** A mismatch between the M/X flags and the intended operation size is a primary cause of crashes. When in doubt, wrap your code in `REP`/`SEP` to explicitly set the processor state, and use size suffixes to make your intent clear to both the assembler and future developers.

## 3. Project-Specific Conventions

### 3.1. File & Directory Structure

- The project is well-organized by functionality (`Core`, `Items`, `Sprites`, `Overworld`, etc.). New code should be placed in the appropriate directory.
- Central include files (e.g., `all_items.asm`, `all_sprites.asm`) are used to aggregate modules. This is a good pattern to continue.

### 3.2. Patch Management

- **Revised Guideline:** Only small, simple patches that modify a few bytes of vanilla code should be considered for centralization in `Core/patches.asm`. Any patch that defines new functions or data in freespace should remain in its original file to preserve context and memory layout.

### 3.3. Debugging

- The `!DEBUG` flag and `%print_debug()` macro in `Util/macros.asm` should be used for all build-time logging. This allows for easy enabling/disabling of diagnostic messages.

### 3.4. Referencing Vanilla Code (`usdasm`)

- When hooking or modifying vanilla code, it is essential to understand the original context. The `usdasm` disassembly is the primary reference for this.
- To find the original code for a patch at a given address (e.g., `$07A3DB`), you can search for the SNES address in the `usdasm` files (e.g., `#_07A3DB:`).

## 4. Build Process and ROM Management

- **Clean ROM**: The clean, unmodified "The Legend of Zelda: A Link to the Past" ROM should be placed at `Roms/oos169.sfc`. This path is included in `.gitignore`, so the ROM file will not be committed to the repository.
- **Build Script**: A `build.sh` script is provided to automate the build process. For detailed usage, see `Docs/General/AsarUsage.md`.
- **Workflow**: The build script creates a fresh copy of the clean ROM and applies the `Oracle_main.asm` patch to it using `asar`.
- **Important**: Never apply patches directly to `Roms/oos169.sfc`. Always use the build script to create a new, patched ROM. This ensures the clean ROM remains untouched for future builds.

## 5. Debugging Tips for BRKs and Crashes

When encountering unexpected crashes (often indicated by a `BRK` instruction in emulators), especially after modifying code, consider the following:

- **Processor Status Register (P) Mismatch:** This is a very common cause. If a routine expects 8-bit accumulator/index registers (M=1, X=1) but is called when they are 16-bit (M=0, X=0), or vice-versa, memory accesses and arithmetic operations will be incorrect, leading to crashes. Always verify the M and X flags before and after calling/returning from routines, especially those in different banks or that you've modified.
    - **Check `PHD`/`PLD`, `PHB`/`PLB`, `PHK`/`PLK`:** These instructions save/restore the Direct Page, Data Bank, and Program Bank registers, respectively. Ensure they are used correctly when switching banks or contexts.
    - **Check `PHA`/`PLA`, `PHX`/`PLX`, `PHY`/`PLY`:** These save/restore the accumulator and index registers. Ensure they are balanced.
    - **Check `PHP`/`PLP`:** These save/restore the entire Processor Status Register. Use them when a routine needs a specific P state and you want to restore the caller's state afterwards.

- **Stack Corruption:** JSL/JSR push the return address onto the stack. If a called routine pushes too much data onto the stack without popping it, or if the stack pointer (`S`) is corrupted, the return address can be overwritten, leading to a crash when `RTL`/`RTS` is executed.
    - **`JSR`/`RTS` vs `JSL`/`RTL` Mismatch:** This is a critical and common error.
        - `JSR` (Jump to Subroutine) pushes a 2-byte return address. It **must** be paired with `RTS` (Return from Subroutine), which pulls 2 bytes.
        - `JSL` (Jump to Subroutine Long) pushes a 3-byte return address (including the bank). It **must** be paired with `RTL` (Return from Subroutine Long), which pulls 3 bytes.
    - Using `RTL` with `JSR` (or `RTS` with `JSL`) will corrupt the stack and almost certainly lead to a crash. Always verify that your subroutine calls and returns are correctly paired.
    - **Balance Pushes and Pops:** Every `PHA`, `PHX`, `PHY`, `PHP` should ideally have a corresponding `PLA`, `PLX`, `PLY`, `PLP` within the same routine.
    - **Bank Switching with Stack:** Be extremely careful when performing bank switches (`PHB`/`PLB`, `PHK`/`PLK`) around stack operations, as the stack is in WRAM (bank $7E/$7F).

- **Incorrect Bank Setup:** When calling a routine in a different bank using `JSL`, ensure the Program Bank (PB) and Data Bank (DB) registers are correctly set for the target routine and restored for the calling routine.

- **Memory Overwrites:** A bug in one part of the code might be writing to an unexpected memory location, corrupting data or code that is used later.
    - **Use an Emulator Debugger:** Step through the code instruction by instruction, paying close attention to register values and memory contents. Set breakpoints at the point of the crash and work backward.
    - **Memory Watchpoints:** Some emulators allow setting watchpoints that trigger when a specific memory address is read or written. This can help pinpoint where corruption occurs.

- **Off-by-One Errors/Table Bounds:** Accessing data outside the bounds of an array or table can lead to reading garbage data or overwriting other parts of memory.

- **Unintended Side Effects:** A routine might modify a register or memory location that a calling routine expects to remain unchanged. Always document what registers a routine clobbers.

- **Debugging Strategy:**
    1.  **Isolate the Problem:** Try to narrow down the exact code change that causes the crash. Revert changes one by one if necessary.
    2.  **Use `print_debug`:** Strategically place `%print_debug()` macros to output register values or memory contents at critical points in the code. This can help track the flow and identify unexpected values.
    3.  **Emulator Debugger:** Learn to use your emulator's debugger effectively. Step-by-step execution, register viewing, and memory inspection are invaluable tools.
    4.  **Check `usdasm`:** Always cross-reference with the `usdasm` disassembly to understand the original vanilla code and how your hooks are interacting with it.



## 6. Verification Policy

- **Bugs and Features:** Never mark a bug fix or feature implementation as `DONE` until it has been thoroughly tested and verified in an emulator. This ensures stability and prevents regressions.


## 7. Memory and Symbol Analysis

This section details the layout and purpose of critical memory regions (WRAM and SRAM) and the symbol definition files that give them context.

### 7.1. WRAM (Work RAM) Analysis

Work RAM (WRAM) holds the active, volatile state of the entire game. The following are some of the most critical variables for understanding real-time game logic.

*   **Direct Page & Scrap (`$7E0000` - `$7E000F`):** A highly volatile scratchpad for temporary, single-frame calculations.
*   **Main Game State (`$7E0010` - `$7E001F`):**
    *   `MODE` (`$7E0010`): The primary game state variable (Overworld, Underworld, Menu, etc.). This dictates which main module is executed each frame.
    *   `INDOORS` (`$7E001B`): A flag (`0x01` for indoors, `0x00` for outdoors) controlling environmental factors.
*   **Link's State (`$7E0020`+):** A large block containing the player's immediate state.
    *   `POSX`/`POSY`/`POSZ`: Link's 16-bit absolute coordinates.
    *   `LINKDO` (`$7E005D`): Link's personal state machine variable (walking, swimming, lifting, etc.), used by the player engine in Bank $07.
    *   `IFRAMES` (`$7E031F`): Invincibility frame timer after taking damage.
*   **Area & Room State (`$7E008A` - `$7E00AF`):**
    *   `OWSCR` (`$7E008A`): The current Overworld screen ID.
    *   `ROOM` (`$7E00A0`): The current Underworld room ID.
*   **Sprite and Ancilla Data (`$7E0D00+`):** `Core/symbols.asm` maps the data structures for all sprites and ancillae (projectiles, effects). Key variables include `SprState` (state machine), `SprType` (ID), `SprHealth`, and coordinates. This is fundamental to all NPC and enemy logic.
*   **Oracle of Secrets Custom WRAM (`$7E0730+`):** A custom region for new features. Notable variables include `GoldstarOrHookshot` and `FishingOrPortalRod`, used to manage the state of new custom items.

### 7.2. SRAM (Save RAM) Analysis

SRAM stores the player's save file, including long-term progression and inventory. `Core/sram.asm` reveals significant customization for Oracle of Secrets.

#### Vanilla ALTTP Save Data:
*   **Inventory:** `Bow` (`$7EF340`), `Bombs` (`$7EF343`), `Sword` (`$7EF359`), `Shield` (`$7EF35A`).
*   **Player Status:** `Rupees` (`$7EF360`), `MAXHP` (`$7EF36C`), `CURHP` (`$7EF36D`).
*   **Progression:** `Pendants` (`$7EF374`), `Crystals` (`$7EF37A`), `GAMESTATE` (`$7EF3C5`).

#### Oracle of Secrets (OOS) Custom SRAM Data:
This highlights the major new features of the hack.
*   **New Items & Masks:** `ZoraMask` (`$7EF347`), `BunnyHood` (`$7EF348`), `DekuMask` (`$7EF349`), `RocsFeather` (`$7EF34D`), etc. These introduce major new player abilities.
*   **New Progression System:**
    *   `OOSPROG` (`$7EF3D6`): A primary bitfield for major quest milestones unique to OOS.
    *   `Dreams` (`$7EF410`): A new collectible concept.
*   **New Collectibles & Side-Quests:** A block from `$7EF38B` holds new items like `Bananas`, `Seashells`, and `Honeycomb`. `MagicBeanProg` (`$7EF39B`) tracks a new multi-day side-quest.

### 7.3. Symbols and Functions (`Core/symbols.asm`)

This file acts as a central header, defining constants and labels for memory addresses and functions to make the assembly code readable and maintainable.

*   **Function Pointers:** It provides labels for critical functions across different ROM banks (e.g., `Sprite_CheckDamageToPlayer`, `EnableForceBlank`), allowing for modular code.
*   **Memory Maps:** It contains the definitive memory maps for WRAM structures, most notably for sprites and ancillae.
*   **Readability:** Its primary purpose is to replace "magic numbers" (raw addresses) with human-readable labels, which is essential for a project of this scale.

## 8. Disassembly Analysis and Search Guide

This section provides a high-level analysis of key banks in the Link to the Past disassembly. Use this guide to quickly locate relevant code and understand the overall structure of the game.

### 8.1. Bank $00: Game Core & Main Loop

**File:** `ALTTP/bank_00.asm`
**Address Range:** `$008000` - `$00FFFF`
**Summary:** The heart of the game engine. Contains the main game loop, interrupt handlers, and the primary game state machine.

#### Key Structures & Routines:
*   **`Reset:` (#_008000)**: Game entry point on boot.
*   **`MainGameLoop:` (#_008034)**: Central loop, calls `Module_MainRouting`.
*   **`Module_MainRouting:` (#_0080B5)**: Primary state machine dispatcher. Reads `MODE` (`$7E0010`) and uses `pool Module_MainRouting` to jump to the correct game module.
*   **`Interrupt_NMI:` (#_0080C9)**: Runs every frame. Handles input (`NMI_ReadJoypads`), graphics DMA (`NMI_DoUpdates`), and sprite preparation (`NMI_PrepareSprites`).

#### Search Heuristics:
*   **Game Module Logic (Overworld, Underworld, Menus):** Search `bank_00.asm` for the `pool Module_MainRouting` jump table. The labels (e.g., `Module09_Overworld`) are the entry points for each game state, determined by WRAM `$7E0010` (`MODE`).
*   **Per-Frame Logic:** Search `bank_00.asm` for `Interrupt_NMI:`. Key routines called from here are `NMI_ReadJoypads` (input) and `NMI_DoUpdates` (graphics DMA).
*   **Initialization Logic:** Start at the `Reset:` label in `bank_00.asm` and trace `JSR`/`JSL` calls to routines like `InitializeMemoryAndSRAM`.

### 8.2. Bank $01: Dungeon Engine

**File:** `ALTTP/bank_01.asm`
**Address Range:** `$018000` - `$01FFFF`
**Summary:** Responsible for loading, drawing, and managing all aspects of interior rooms (dungeons, houses, caves).

#### Key Structures & Routines:
*   **`Underworld_LoadRoom:` (#_01873A)**: Main entry point for loading a dungeon room.
*   **`DrawObjects` Tables:** A set of tables at the top of the bank defining object graphics and drawing routines.
*   **`RoomDraw_DrawAllObjects:` (#_0188E4)**: Iterates through a room's object list.
*   **`RoomDraw_RoomObject:` (#_01893C)**: Main dispatcher for drawing a single object based on its ID.

#### Search Heuristics:
*   **Room Construction Logic:** In `bank_01.asm`, start at `Underworld_LoadRoom` and trace the call sequence: `Underworld_LoadHeader` -> `RoomDraw_DrawFloors` -> `RoomDraw_DrawAllObjects`.
*   **Specific Dungeon Object Code:** To find an object's drawing code, search the `.type1_subtype_..._routine` tables at the start of `bank_01.asm` for the object's ID. The corresponding label is the drawing routine. To find its tile data, search the `.type1_subtype_..._data_offset` tables.

### 8.3. Bank $02: Overworld & Transitions

**File:** `ALTTP/bank_02.asm`
**Address Range:** `$028000` - `$02FFFF`
**Summary:** Manages loading the overworld, transitioning between areas, and handling special game sequences.

#### Key Structures & Routines:
*   **`Module06_UnderworldLoad:` (#_02821E)**: Primary module for transitioning into and loading an underworld room.
*   **`Module08_OverworldLoad:` (#_0283BF)**: Primary module for loading the overworld.
*   **`Module07_Underworld:` (#_0287A2)**: Main logic loop for when the player is in the underworld. Dispatches to submodules based on WRAM `$11`.

#### Search Heuristics:
*   **Overworld Loading:** Start at `Module08_OverworldLoad` in `bank_02.asm`. Logic checks WRAM `$8A` (overworld area number) to determine behavior.
*   **Underworld Gameplay:** Start at `Module07_Underworld` in `bank_02.asm`. Examine the `.submodules` jump table to see the different states, determined by WRAM `$11`.
*   **Transition Logic:** Search for code that sets the game `MODE` (`$10`) to `$08` (Overworld Load) or `$06` (Underworld Load) to find the start of a transition.

### 8.4. Bank $03: Tile32 Overworld Layout Data

### 8.5. Bank $04: Tile32 Overworld Layout Data, Dungeon Room Headers

### 8.6. Bank $07: Core Player (Link) Engine

**File:** `ALTTP/bank_07.asm`
**Address Range:** `$078000` - `$07FFFF`
**Summary:** Contains Link's core state machine, governing movement, physics, item usage, and interactions.

#### Key Structures & Routines:
*   **`Link_Main:` (#_078000)**: Top-level entry point for all player logic.
*   **`Link_ControlHandler:` (#_07807F)**: The heart of the player engine. A state machine dispatcher that reads `LINKDO` (`$7E005D`) and jumps via the `pool Link_ControlHandler` table.
*   **`LinkState_Default` (#_078109):** The most common state, handling walking and dispatching to action sub-handlers like `Link_HandleYItem`.

#### Search Heuristics:
*   **Player Action Logic (walking, swimming):** In `bank_07.asm`, search for `pool Link_ControlHandler`. The state ID is from WRAM `$7E005D` (`LINKDO`). Find the label for the desired state (e.g., `LinkState_Default`) to locate its main routine.
*   **Player Physics/Collision:** Within a player state routine, search for calls to `JSL Link_HandleVelocity` (physics) and `JSR Link_HandleCardinalCollision` (collision).
*   **Y-Button Item Logic:** In `LinkState_Default`, search for the call to `JSR Link_HandleYItem`.
*   **Player Damage Logic:** Search for writes to WRAM `$7E0373` (`HURTME`).

### 8.7. Bank $05: Specialized Sprite & Object Engine

**File:** `ALTTP/bank_05.asm`
**Address Range:** `$058000` - `$05FFFF`
**Summary:** Code for unique, complex, and scripted sprites that do not fit the standard enemy AI model (e.g., cutscene sprites, minigame hosts, complex traps).

#### Search Heuristics:
*   **Unique/Non-Enemy Sprites:** When looking for a unique sprite (minigame, cutscene object, complex trap), check `bank_05.asm` first.
*   **Finding Sprite Logic:** Search for the sprite's name (e.g., "MasterSword") or its hexadecimal ID (e.g., `Sprite_62`) to find its main routine.

### 8.8. Bank $06: Main Sprite Engine & Helpers

**File:** `ALTTP/bank_06.asm`
**Address Range:** `$068000` - `$06FFFF`
**Summary:** Contains the main sprite processing engine and a vast library of shared helper subroutines used by sprites game-wide.

#### Key Structures & Routines:
*   **`Sprite_Main:` (#_068328)**: The master sprite loop that iterates through all 16 sprite slots.
*   **`Sprite_ExecuteSingle:` (#_0684E2)**: The state machine dispatcher for an individual sprite, reading `SprState` (`$7E0DD0,X`).
*   **`SpriteModule_Initialize:` (#_06864D)**: Master initialization routine. Contains a massive jump table pointing to a specific `SpritePrep_...` routine for nearly every sprite type.
*   **`Sprite_SpawnSecret` (`#_068264`):** Determines the "secret" item that appears under a liftable bush or rock.

#### Search Heuristics:
*   **Sprite Initialization (HP, damage, etc.):** In `bank_06.asm`, go to `SpriteModule_Initialize`. Find the sprite's ID in the large jump table to get the label for its `SpritePrep_...` routine.
*   **Sprite Core AI:** In `bank_06.asm`, go to `SpriteModule_Active`. Find the sprite's ID in its jump table to find the entry point to its main AI logic (which may be in another bank).
*   **Bush/Rock Item Drops:** Locate the `Sprite_SpawnSecret` routine and examine the `.ID` table at `#_0681F4` to see the prize mappings.

### 8.9. Bank $08: Ancilla Engine

**File:** `ALTTP/bank_08.asm`
**Address Range:** `$088000` - `$08FFFF`
**Summary:** The engine for "Ancillae" (projectiles, particle effects, etc.). Contains the execution logic for entities like arrows, bombs, and magic spells.

#### Search Heuristics:
*   **Projectile/Effect Logic:** In `bank_08.asm`, find the main jump table in `Ancilla_ExecuteOne` (at `#_08837F`). Look up the ancilla's ID in this table to find the label for its logic routine (e.g., `Ancilla07_Bomb`).
*   **Projectile Properties (speed, graphics):** Go to the ancilla's main logic routine (e.g., `Ancilla09_Arrow`) and look for writes to its WRAM properties (e.g., `$0C2C` for X-speed).

### 8.10. Bank $09: Ancilla Spawning & Item Logic

**File:** `ALTTP/bank_09.asm`
**Address Range:** `$098000` - `$09FFFF`
**Summary:** Contains the ancilla *creation* engine (a library of `AncillaAdd_...` functions) and the critical logic for giving items to the player.

#### Search Heuristics:
*   **Projectile/Effect Creation:** To find where a projectile is created, search the codebase for `JSL` calls to its corresponding `AncillaAdd_...` function in this bank (e.g., `JSL AncillaAdd_Bomb`).
*   **Item "Get" Properties:** To change the properties of an item the player receives, find the `AncillaAdd_ItemReceipt` routine and examine the large data tables starting at `#_098404`.

### 8.11. Bank $0A: World Map & Flute Menu Engine

**File:** `ALTTP/bank_0A.asm`
**Address Range:** `$0A8000` - `$0AFFFF`
**Summary:** Controls all full-screen map interfaces (pause menu map, flute destination map).

#### Search Heuristics:
*   **Flute Warp Destinations:** In `bank_0A.asm`, find the `FluteMenu_LoadTransport` routine. The table within it maps the 8 flute spots to screen indexes.
*   **Map Icon Locations:** Search for the `WorldMapIcon_posx_...` and `WorldMapIcon_posy_...` tables to adjust icon coordinates.

### 8.12. Bank $0B: Overworld Environment & State Helpers

**File:** `ALTTP/bank_0B.asm`
**Address Range:** `$0B8000` - `$0BFFFF`
**Summary:** Miscellaneous helper functions related to the overworld environment and player state.

#### Search Heuristics:
*   **Overworld Area Palette:** To change the background color of an overworld area, modify the color values loaded in `Overworld_SetFixedColAndScroll`. The logic checks WRAM `$8A` to decide which color to use.
*   **Wall Master Capture:** To change what happens when captured, find the `WallMaster_SendPlayerToLastEntrance` routine.

### 8.13. Bank $0C: Intro & Credits Sequence

**File:** `ALTTP/bank_0C.asm`
**Address Range:** `$0C8000` - `$0CFFFF`
**Summary:** Handles the game's intro and end-game credits sequences.

#### Search Heuristics:
*   **Intro/Credits Scene Logic:** Start at the `Module00_Intro` or `Module1A_Credits` jump tables. The sub-mode in WRAM `$11` determines which part of the sequence is running. Follow the jump table to the routine for the scene you want to change.

### 8.14. Bank $0D: Link Animation & OAM Data

**File:** `ALTTP/bank_0D.asm`
**Address Range:** `$0D8000` - `$0DFFFF`
**Summary:** A massive graphical database defining every frame of Link's animation. It is not executable code.

#### Search Heuristics:
*   **Link's Animation Sequence:** To modify an animation, find the action in `LinkOAM_AnimationSteps`. The values are indices into the `LinkOAM_PoseData` table, which defines the body parts for each frame.
*   **Link's Item Positioning:** To change how Link holds an item, find the animation frame index in `LinkOAM_AnimationSteps` and use it to find the corresponding entries in the `LinkOAM_SwordOffsetX/Y` or `LinkOAM_ShieldOffsetX/Y` tables.

### 8.15. Bank $0E: Tile Properties & Credits Engine

**File:** `ALTTP/bank_0E.asm`
**Address Range:** `$0E8000` - `$0EFFFF`
**Summary:** Contains fundamental game assets (font, tile properties) and the credits engine.

#### Search Heuristics:
*   **Tile Behavior (e.g., making a wall walkable):** Identify the tile's graphical ID and find its entry in the `OverworldTileTypes` or `UnderworldTileTypes` tables. Change its byte value to match a tile with the desired properties.
*   **Custom Tile Physics (e.g., ice):** Search for the `Underworld_LoadCustomTileTypes` function to see how alternate tile property sets are loaded for specific dungeons.

### 8.16. Bank $0F: Miscellaneous Game Logic & Helpers

**File:** `ALTTP/bank_0F.asm`
**Address Range:** `$0F8000` - `$0FFFFF`
**Summary:** A collection of important miscellaneous subroutines, including player death and dialogue box initiation.

#### Search Heuristics:
*   **Player Death Sequence:** The entry points are `PrepareToDie` and `Link_SpinAndDie`.
*   **Dialogue Box Trigger:** Search for `JSL Interface_PrepAndDisplayMessage`. The code immediately preceding it sets up the message ID to be displayed.

### 8.17. Bank $10-$18: Graphics Sheets for Link, Dungeon, Overworld, Sprites

### 8.18. Bank $19: Sound Data

### 8.19. Bank $1A: Miscellaneous Sprites & Cutscenes

**File:** `ALTTP/bank_1A.asm`
**Address Range:** `$1A8000` - `$1AFFFF`
**Summary:** Logic for a variety of unique sprites, NPCs, and cutscene events that are too specific for the main sprite engine.

#### Search Heuristics:
*   **Pyramid of Power Opening:** Search for `BatCrash` or `CreatePyramidHole`.
*   **Waterfall of Wishing Splash:** Search for `SpawnHammerWaterSplash`.
*   **Secret Item Substitution:** To understand how items under rocks are sometimes replaced by enemies, analyze `Overworld_SubstituteAlternateSecret`.

### 8.20. Bank $1B: Overworld Interaction & Palettes

**File:** `ALTTP/bank_1B.asm`
**Address Range:** `$1B8000` - `$1BFFFF`
**Summary:** The heart of the overworld interaction system. Manages all entrances, pits, and item-based tile interactions (digging, bombing). Also contains a very large store of palette data.

#### Search Heuristics:
*   **Overworld Entrances:** To change where a door leads, find its entry in the `Overworld_Entrance...` tables at the top of the bank.
*   **Hidden Item Locations:** To change the item under a specific bush, find the correct `OverworldData_HiddenItems_Screen_XX` table and modify the entry for that bush's coordinates.
*   **Sprite/Armor Colors:** To change a color, find the correct palette in the `PaletteData` section and modify the desired color values.

### 8.21. Bank $1C: Text Data

### 8.22. Bank $1D & $1E: Advanced Sprite & Boss AI

**Files:** `ALTTP/bank_1D.asm`, `ALTTP/bank_1E.asm`
**Summary:** These banks contain the specific, complex AI for most of the game's major bosses and late-game enemies (Ganon, Moldorm, Trinexx, Helmasaur King, Kholdstare, Agahnim, etc.).

#### Search Heuristics:
*   **Boss/Enemy AI:** To modify a specific boss or advanced enemy, search for its `Sprite_...` routine in these two banks (e.g., `Sprite_92_HelmasaurKing` in bank $1E).
*   **Sprite Dispatch Table:** The jump table at `SpriteModule_Active_Bank1E` in `bank_1E.asm` provides a comprehensive list of all sprites managed by that bank and is a good starting point for investigation.

### 8.23. Bank $1F: Dungeon Room Data

## 9. ZScream expanded feature ROM map

> **Last Updated:** 02/28/2025
> **Note:** All addresses are in PC format unless otherwise stated.
> **Note:** Some features are supported in yaze (yet another zelda3 editor) but not all.

ZScream reserves:
- All space up to **1.5MB** (`0x150000`)
- An additional **3 banks** at the end of the 2.0MB range (`0x1E8000` to `0x1FFFFF`)

### Bank Allocation Overview

| Address Range         | Size      | Purpose/Contents                                   |
|---------------------- |---------- |----------------------------------------------------|
| `0x100000 - 0x107FFF` | 1 Bank    | *(Unused?)*                                        |
| `0x108000 - 0x10FFFF` | 1 Bank    | Title screen data, Dungeon map data                |
| `0x110000 - 0x117FFF` | 1 Bank    | Default room header location                       |
|                       |           | (Old dungeon object data expansion, now moved)     |
| `0x118000 - 0x11FFFF` | 1 Bank    | (Old dungeon object data expansion, now moved)     |
| `0x120000 - 0x127FFF` | 1 Bank    | Expanded overlay data                              |
| `0x128000 - 0x12FFFF` | 1 Bank    | Custom collision data                              |
| `0x130000 - 0x137FFF` | 1 Bank    | Overworld map data overflow                        |
| `0x138000 - 0x13FFFF` | 1 Bank    | Expanded dungeon object data                       |
| `0x140000 - 0x147FFF` | 1 Bank    | Custom overworld data                              |
| `0x148000 - 0x14FFFF` | 1 Bank    | Expanded dungeon object data                       |
| `0x1E0000 - 0x1E7FFF` | 1 Bank    | Custom ASM patches                                 |
| `0x1E8000 - 0x1EFFFF` | 1 Bank    | Expanded Tile16 space                              |
| `0x1F0000 - 0x1FFFFF` | 2 Banks   | Expanded Tile32 space                              |