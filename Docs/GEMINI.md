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
- **Build Script**: A `build.sh` script is provided to automate the build process. For detailed usage, see `Docs/AsarUsage.md`.
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

### 5.1. WRAM (Work RAM) Analysis

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

### 5.2. SRAM (Save RAM) Analysis

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

### 5.3. Symbols and Functions (`Core/symbols.asm`)

This file acts as a central header, defining constants and labels for memory addresses and functions to make the assembly code readable and maintainable.

*   **Function Pointers:** It provides labels for critical functions across different ROM banks (e.g., `Sprite_CheckDamageToPlayer`, `EnableForceBlank`), allowing for modular code.
*   **Memory Maps:** It contains the definitive memory maps for WRAM structures, most notably for sprites and ancillae.
*   **Readability:** Its primary purpose is to replace "magic numbers" (raw addresses) with human-readable labels, which is essential for a project of this scale.

## 8. Disassembly Analysis and Search Guide

This section provides a high-level analysis of key banks in the Link to the Past disassembly. Use this guide to quickly locate relevant code and understand the overall structure of the game.

### 6.1. Bank $00: Game Core & Main Loop

**File:** `ALTTP/bank_00.asm`
**Address Range:** `$008000` - `$00FFFF`

This bank is the heart of the game engine. It contains the initial `Reset` vector, the main game loop, interrupt handlers, and the primary game state machine.

#### Key Structures & Routines:

*   **`Reset:` (#_008000)**: The entry point of the game on boot. It initializes hardware registers, memory, and SRAM before jumping into the main game logic.
*   **`MainGameLoop:` (#_008034)**: The central loop of the game. It waits for the NMI flag (`$12`) to be set, then calls `Module_MainRouting` to execute the logic for the current game state.
*   **`Module_MainRouting:` (#_0080B5)**: This is the game's primary state machine. It reads the main game state index from `$10` and uses a jump table (`pool Module_MainRouting`) to jump to the appropriate module's logic. Understanding this table is key to understanding the game's flow.
    *   **Game State Index:** Stored in WRAM at `$7E0010`.
    *   **Example States:** `Module07_Underworld`, `Module09_Overworld`, `Module01_FileSelect`, etc.
*   **`Interrupt_NMI:` (#_0080C9)**: The Non-Maskable Interrupt handler. This runs every V-Blank (once per frame). It's responsible for:
    *   Handling music and sound effect updates.
    *   Reading joypad input (`NMI_ReadJoypads`).
    *   Calling `NMI_DoUpdates` to perform DMA transfers for graphics (backgrounds and sprites).
    *   Preparing sprite OAM data (`NMI_PrepareSprites`).
*   **`InitializeMemoryAndSRAM:` (#_0087C0)**: Clears WRAM and validates the three SRAM save files by checking for a magic number (`$55AA`).
*   **`SaveGameFile:` (#_00894A)**: Handles the logic for saving game progress to the correct SRAM slot.

#### Search Heuristics:

*   **To find game state logic:**
    1.  Identify the game state you're interested in (e.g., "playing in the overworld", "in the file select screen").
    2.  Search `bank_00.asm` for the `pool Module_MainRouting` table.
    3.  Find the corresponding module label (e.g., `Module09_Overworld`, `Module01_FileSelect`). This label is the entry point for that game state's main logic.
*   **To find per-frame update logic:**
    1.  Look inside the `Interrupt_NMI` routine in `bank_00.asm`.
    2.  Follow the calls to `NMI_DoUpdates` for graphics DMA, `NMI_ReadJoypads` for input, and the audio update logic at the start of the NMI.
*   **To find core initialization code:**
    1.  Start at the `Reset:` label in `bank_00.asm`.
    2.  Follow the `JSR`/`JSL` calls to see how memory, SRAM, and hardware are configured.

### 6.2. Bank $01: Dungeon Engine

**File:** `ALTTP/bank_01.asm`
**Address Range:** `$018000` - `$01FFFF`

This bank contains the engine responsible for loading, drawing, and managing all aspects of interior rooms (dungeons, houses, caves).

#### Key Structures & Routines:

*   **`Underworld_LoadRoom:` (#_01873A)**: The main entry point for loading a dungeon room. It orchestrates a sequence of operations to build the room from its component parts.
*   **Room Object Data:** The core of the dungeon engine is a set of tables that define how to draw room objects. The process is hierarchical:
    1.  **Room Header:** Contains pointers to lists of objects. `RoomData_ObjectDataPointers` points to this data for each room.
    2.  **Object Definition:** Each object in the list has a type and position. The type determines which drawing routine to use.
    3.  **`DrawObjects` Tables:** Located at the top of `bank_01.asm`, these tables are indexed by object ID and contain pointers to the object's raw tile data (`.type1_subtype_1_data_offset`) and the routine used to draw it (`.type1_subtype_1_routine`).
*   **`RoomDraw_DrawAllObjects:` (#_0188E4)**: Iterates through a list of objects for the current room and calls `RoomDraw_RoomObject` for each one.
*   **`RoomDraw_RoomObject:` (#_01893C)**: The main dispatcher for drawing a single object. It reads the object's ID, looks up the corresponding data and drawing routine in the `DrawObjects` tables, and executes it.
*   **`RoomDraw_DrawFloors:` (#_0189DC)**: Handles the drawing of the room's floor tilemap before objects are drawn.
*   **Doors:** Doors are a special object type handled by `RoomDraw_DoorObject` (#_018916), which uses the `DoorDrawRoutines` jump table.

#### Search Heuristics:

*   **To understand how a dungeon room is constructed:**
    1.  Start at `Underworld_LoadRoom` in `bank_01.asm`.
    2.  Follow the sequence of calls: `Underworld_LoadHeader` -> `RoomDraw_DrawFloors` -> `RoomDraw_DrawAllObjects`.
*   **To find the code for a specific dungeon object (e.g., a pushable block, a torch):**
    1.  Determine the object's ID.
    2.  Search the `.type1_subtype_..._data_offset` tables at the beginning of `bank_01.asm` for the object ID comment (e.g., `; 094 -`).
    3.  The label on that line (e.g., `obj0288-RoomDrawObjectData`) points to the object's tile data.
    4.  Look at the corresponding entry in the `.type1_subtype_..._routine` table to find the drawing routine (e.g., `RoomDraw_DownwardsFloor4x4_1to16`).
*   **To modify an object's appearance:** Find its data offset label (e.g., `obj0288`) and locate that data block within `bank_01.asm` to see the raw tilemap data.

### 6.3. Bank $02: Overworld & Transitions

**File:** `ALTTP/bank_02.asm`
**Address Range:** `$028000` - `$02FFFF`

This bank manages loading the overworld, transitioning between areas (e.g., underworld to overworld), and handling special game sequences like the intro and credits.

#### Key Structures & Routines:

*   **`Module05_LoadFile:` (#_028136)**: Handles the initial loading of a save file. It sets up default graphics, initializes Link's state, and determines whether to start in the light world or dark world, or to trigger a special scene.
*   **`Module06_UnderworldLoad:` (#_02821E)**: The primary module for transitioning into and loading a new underworld room. It loads the room entrance data, draws the room via `Underworld_LoadAndDrawRoom`, loads palettes, and initializes sprites.
*   **`Module08_OverworldLoad:` (#_0283BF)**: The primary module for loading the overworld. It determines which music and palettes to load based on the overworld area (`$8A`) and player status.
*   **`Module07_Underworld:` (#_0287A2)**: The main logic loop for when the player is in the underworld. It calls submodules based on the player's state (`$11`), such as normal player control (`Module07_00_PlayerControl`), screen transitions, or other room events.
*   **`Overworld_LoadAllPalettes_long:` (#_02811A)**: A key routine for loading the correct overworld palettes based on the current screen and game events.
*   **Transitions:** The bank is filled with logic for handling transitions.
    *   `LoadOverworldFromUnderworld`: Called by `Module08_OverworldLoad` to set up the overworld when exiting a cave or dungeon.
    *   `Underworld_TryScreenEdgeTransition`: Checks if Link is at the edge of a screen and initiates a room transition if so.

#### Search Heuristics:

*   **To find overworld loading logic:**
    1.  Start at `Module08_OverworldLoad` in `bank_02.asm`.
    2.  Examine the logic that checks the overworld area number (`$8A`) to see how different areas are handled.
*   **To find underworld gameplay logic:**
    1.  Start at `Module07_Underworld` in `bank_02.asm`.
    2.  Examine the `.submodules` jump table to see the different underworld states (player control, transitions, etc.). The value in `$11` determines which state is active.
*   **To trace a transition (e.g., cave exit):**
    1.  Find the code that sets the game module to `$08` (Overworld Load).
    2.  Look in `Module08_OverworldLoad` and follow the call to `LoadOverworldFromUnderworld`. This will show how screen data, palettes, and sprites are loaded for the overworld.
*   **To find palette loading code:** Search for `JSR`/`JSL` calls to `Overworld_LoadAllPalettes`, `Underworld_LoadPalettes`, or `OverworldPalettesLoader`. The code leading up to these calls will determine *which* palettes are loaded.

### 6.3.1. Bank $03: Tile32 Overworld Layout Data

### 6.3.2. Bank $04: Tile32 Overworld Layout Data, Dungeon Room Headers

### 6.4. Bank $07: Core Player (Link) Engine

**File:** `ALTTP/bank_07.asm`
**Address Range:** `$078000` - `$07FFFF`

This bank is dedicated entirely to the player character, Link. It contains his core state machine, which governs everything from movement and physics to item usage and interaction with the world.

#### Key Structures & Routines:

*   **`Link_Main:` (#_078000)**: The top-level entry point for all player logic, called every frame. Its primary job is to call the main state machine handler.
*   **`Link_ControlHandler:` (#_07807F)**: The heart of the player engine. This routine functions as a state machine dispatcher.
    *   **Critical WRAM:** It reads Link's current state from `$7E005D` (`LINKDO`). Changing this value will force Link into a different state.
    *   **Jump Table:** It uses the value of `LINKDO` to index a jump table (`pool Link_ControlHandler`) and execute the code for the current state.
*   **Player States (`LinkState_...`):** The bank is composed of many routines, each handling a specific state. Key states include:
    *   **`LinkState_Default` (#_078109):** The most common state. It handles walking, stopping, reading joypad input, and dispatching to sub-handlers for actions like `Link_HandleAPress` (talking, lifting), `Link_HandleYItem` (using items), and sword attacks.
    *   **`LinkState_Recoil` (#_0786B5):** Manages the knockback sequence when Link takes damage. It's a timer-based state that temporarily removes player control.
    *   **`LinkState_Dashing` (#_078063):** Handles the physics and animation for running with the Pegasus Boots.
    *   **`LinkState_Swimming` (#_078049):** Manages movement and actions while in the water.
    *   **`LinkState_Bunny` (#_0783A1):** A simplified state with restricted actions for when Link is a bunny. It also contains the logic to transform back.
    *   **`LinkState_ShowingOffItem` (#_07806B):** The "item get" pose, which temporarily freezes Link to show the player a new item.

#### Search Heuristics:

*   **To modify any core player action (walking, swimming, dashing):**
    1.  Find the corresponding state ID in the `pool Link_ControlHandler` jump table in `bank_07.asm`.
    2.  Go to the routine for that state (e.g., `LinkState_Default`, `LinkState_Swimming`).
    3.  Within that routine, look for calls to physics and collision handlers like `JSL Link_HandleVelocity` or `JSR Link_HandleCardinalCollision`.
*   **To change how an item is used:**
    1.  Start in `LinkState_Default` and find the call to `JSR Link_HandleYItem`. This routine is the dispatcher for all Y-button items.
*   **To add a new player state:**
    1.  Find an unused state ID (or create a new one).
    2.  Write a new `LinkState_...` routine to handle the logic for your new state.
    3.  Find the code that should trigger your new state and have it write the new state ID to `$7E005D` (`LINKDO`).
*   **To find where Link takes damage:** Search for code that writes a non-zero value to `$7E0373` (`HURTME`). The `Link_ControlHandler` will detect this at the start of the next frame and initiate the recoil state.

### 6.5. Bank $05: Specialized Sprite & Object Engine

**File:** `ALTTP/bank_05.asm`
**Address Range:** `$058000` - `$05FFFF`

This bank is a collection of code for unique, complex, and specialized sprites that do not fit the mold of standard, reusable enemy AI. If a sprite has a very specific, scripted, or multi-part behavior, its logic is likely located here.

#### Key Sprite Categories & Examples:

*   **Cutscene & Event Sprites:** These handle one-off story moments.
    *   `Sprite_62_MasterSword` (`#_0588C5`): Manages the entire Master Sword pedestal cutscene, including spawning the circling pendants, the light beams, and giving the item to the player.
*   **Minigame Sprites:** Contains the logic for entire minigames.
    *   `Sprite_65_ArcheryGame` (`#_0581FF`): Controls the archery minigame host, the moving targets, and the prize logic.
*   **Complex Environmental Sprites (Traps):**
    *   `Sprite_66_WallCannon...` (`#_058090`): The logic for wall-mounted cannons that fire projectiles in a set pattern.
    *   `Sprite_63_DebirandoPit` (`#_058531`): A sentient whirlpool/pit that attempts to drag Link in.
*   **Complex Enemy Sprites:**
    *   `Sprite_64_Debirando` (`#_05874D`): The monster that emerges from the Debirando Pit.
*   **Garnish & Effects:**
    *   `Sprite_SpawnSparkleGarnish` (`#_058008`): A function to spawn decorative sparkles around another sprite, often used for emphasis.

#### Search Heuristics:

*   When looking for the code for a unique, non-enemy sprite (like an NPC in a minigame, a cutscene object, or a complex trap), **check `bank_05.asm` first.**
*   Search for the sprite's name (e.g., "MasterSword", "ArcheryGame") or its hexadecimal ID (e.g., `Sprite_62`, `Sprite_65`) to find its main routine.
*   The code in this bank often involves state machines (`SprAction, X`) and timers (`SprTimerA, X`) to manage complex sequences of actions.

### 6.6. Bank $06: Main Sprite Engine & Helpers

**File:** `ALTTP/bank_06.asm`
**Address Range:** `$068000` - `$06FFFF`

This bank is arguably the most important for understanding enemy and object behavior, as it contains the **main sprite processing engine**. It also houses a vast library of shared subroutines used by sprites across the entire game.

#### Key Structures & Routines:

*   **`Sprite_Main:` (#_068328)**: This is the master sprite loop, called once per game frame. It iterates through all 16 sprite slots (from 15 down to 0), calling `Sprite_ExecuteSingle` for each one to process its logic.
*   **`Sprite_ExecuteSingle:` (#_0684E2)**: The state machine dispatcher for an individual sprite. It reads the sprite's current state from `$7E0DD0,X` (`SprState`) and uses a jump table to execute the appropriate logic (e.g., `SpriteModule_Active`, `SpriteModule_Die`, `SpriteModule_Stunned`).
*   **`SpriteModule_Initialize:` (#_06864D)**: This is the master initialization routine. When a sprite is first spawned (state `0x08`), this function is called. It contains a massive jump table that points to a specific `SpritePrep_...` routine for nearly every sprite type. This is where a sprite's unique properties like HP, damage, speed, and prize drops are configured.
*   **`SpriteModule_Active:`:** This routine (called from the `Sprite_ExecuteSingle` jump table) is the entry point for a sprite's main AI. It typically contains another jump table indexed by the sprite's ID (`$7E0E20,X`, `SprType`) that leads to the actual AI code (which may be in this bank or another).
*   **Helper & Utility Functions:** This bank is filled with common routines that sprites call via `JSR`/`JSL`.
    *   `Sprite_SpawnSecret` (`#_068264`): A crucial routine that determines the "secret" item that appears when you lift a bush or rock. It contains data tables for different prize packs.
    *   `Sprite_SpawnThrowableTerrain` (`#_06814B`): Spawns a liftable object (bush, rock) sprite.
    *   `CheckIfHitBoxesOverlap` (`#_0683E6`): A generic function to check for collision between two entities.
    *   `Sprite_TimersAndOAM` (`#_0683F2`): Handles decrementing sprite timers and allocating OAM slots for drawing.

#### Search Heuristics:

*   **To find any sprite's core AI:**
    1.  Find the sprite's ID (e.g., `0x6D` for a Rat).
    2.  Go to the `SpriteModule_Active` routine in this bank. You will likely find a jump table there.
    3.  Find the entry in the table corresponding to the sprite's ID. This will jump to the sprite's main AI logic, which could be in Bank $06 or another bank entirely.
*   **To find how a sprite is initialized (HP, damage, etc.):**
    1.  Find the sprite's ID.
    2.  Go to the `SpriteModule_Initialize` routine in this bank.
    3.  Find the sprite's ID in the large jump table to get the label for its `SpritePrep_...` routine. The code at that label sets the initial properties.
*   **To change what items drop from bushes/rocks:**
    1.  Locate the `Sprite_SpawnSecret` routine.
    2.  Examine the `.ID` table (`#_0681F4`) which maps a prize index to a sprite ID (e.g., Green Rupee, Heart, Bee). Modifying this table will change the drops.


### 6.7. Bank $08: Ancilla Engine

  **File:** `ALTTP/bank_08.asm`
  **Address Range:** `$088000` - `$08FFFF`
  **Description:** This bank is the engine for "Ancillae" (from ancillary). Ancillae are temporary, non-sprite objects, which are typically projectiles, particle effects, or other spawned entities. This includes
  everything from Link's sword beam and arrows to bomb explosions and magic spell effects.
#### Key Structures & Routines:

*   **`Ancilla_Main:` (#_088242)**: The top-level entry point for the ancilla engine, called once per frame from `Sprite_Main`.
*   **`Ancilla_ExecuteAll:` (#_08832B)**: The main loop for the engine. It iterates through all available ancilla slots and calls `Ancilla_ExecuteOne` for each active ancilla.
*   **`Ancilla_ExecuteOne:` (#_08833C)**: The core dispatcher for a single ancilla. It reads the ancilla's type ID from WRAM (`$7E0C4A,X`, `AnciType`) and uses it as an index into a large jump
 table (`.vectors` at `#_08837F`) to execute the logic for that specific type. This is the state machine for all projectiles and effects.
*   **Ancilla Logic Routines (`AncillaXX_...`):** The bulk of the bank consists of the individual routines for each ancilla type, for example:
*   `Ancilla02_FireRodShot`
*   `Ancilla05_Boomerang`
*   `Ancilla07_Bomb`
*   `Ancilla09_Arrow`
*   `Ancilla18_EtherSpell`
*   **Spawning Routines (`AncillaAdd_...`):** This bank contains many of the functions used to create new ancillae. These are called from other banks (e.g., Bank $07 when Link uses an item).
Examples include:
`AncillaAdd_FireRodShot` (`#_0880B3`)
*   `AncillaAdd_IceRodSparkle` (`#_0884C8`)
*   `AncillaAdd_Bomb` (`#_0884D0`)
*   `AncillaAdd_Arrow` (`#_0884D8`)
#### Search Heuristics:

*   **To find the logic for a specific projectile or effect:**
     1.  Determine the ancilla's ID (e.g., from the `AncillaObjectAllocation` table at `#_08806F`).
     2.  Find the main jump table in `Ancilla_ExecuteOne` (at `#_08837F`).
     3.  Look up the ancilla ID in the table to find the label for its logic routine (e.g., `Ancilla07_Bomb`).
*   **To find where a projectile is created:** Search the codebase for `JSL` calls to its corresponding `AncillaAdd_...` function (e.g., search for `AncillaAdd_Bomb` to see where bombs are
        spawned).
*   **To change the properties of a projectile (speed, graphics, etc.):** Go to its main logic routine (e.g., `Ancilla09_Arrow`) and look for where it sets its WRAM properties (`$0C2C` for
        X-speed, `$0C22` for Y-speed, etc.).

### 6.8. Bank $09: Ancilla Spawning & Item Logic

**File:** `ALTTP/bank_09.asm`
**Address Range:** `$098000` - `$09FFFF`

While Bank $08 contains the ancilla *execution* engine, Bank $09 contains the ancilla *creation* engine. This bank is a library of `AncillaAdd_...` functions that are called from all over the codebase to spawn projectiles and effects. It also handles the critical logic for giving items to the player.

#### Key Structures & Routines:

*   **Ancilla Spawning Functions (`AncillaAdd_...`):** This bank is primarily composed of these routines. Each one is responsible for finding an empty ancilla slot and initializing it with the correct properties for that type.
    *   `AncillaAdd_Bomb` (`#_09811F`)
    *   `AncillaAdd_Boomerang` (`#_09820F`)
    *   `AncillaAdd_HitStars` (`#_098024`)
*   **`AncillaAdd_ItemReceipt` (`#_0985E8`):** This is one of the most complex and important routines in the bank. It handles the entire process of giving an item to the player.
    *   It takes an item ID from `$02D8`.
    *   It looks up the item's properties (SRAM address, value to write, etc.) in a series of large tables.
    *   It writes the new value to the appropriate SRAM address to save the player's new item.
    *   It handles special cases for pendants, crystals, mail upgrades, and heart pieces.
    *   It calls `RefreshIcon_long` to update the HUD.

#### Search Heuristics:

*   **To find where any projectile or effect is created:** Search the codebase for a `JSL` to its corresponding `AncillaAdd_...` routine in this bank. For example, to see what spawns bombs, search for `JSL AncillaAdd_Bomb`.
*   **To change the properties of an item received by the player:**
    1.  Find the `AncillaAdd_ItemReceipt` routine.
    2.  Examine the large data tables starting at `#_098404`. These tables define everything about each obtainable item, including its graphics, its corresponding SRAM flag, and the value to write. Modifying these tables is the correct way to change item properties.

### 6.9. Bank $0A: World Map & Flute Menu Engine

**File:** `ALTTP/bank_0A.asm`
**Address Range:** `$0A8000` - `$0AFFFF`

This bank controls all full-screen map interfaces, including the overworld map viewable from the pause menu and the 8-point destination map used when playing the flute.

#### Key Structures & Routines:

*   **`Module0E_0A_FluteMenu` (`#_0AB730`):** The state machine for the flute destination selection menu. It handles loading the map graphics, drawing the numbered destination icons, processing player input to select a location, and initiating the duck transport sequence.
*   **`Module0E_07_OverworldMap` (`#_0AB98B`):** The state machine for the main overworld map screen. It handles player input for zooming in/out and panning the map.
*   **Mode 7 Graphics:** This bank makes heavy use of Mode 7 for rendering the world map. Routines like `WorldMap_LoadLightWorldMap` and `WorldMap_SetUpHDMA` are responsible for loading the map tile data and configuring the HDMA channels to perform the Mode 7 scaling and rotation effects.
*   **Map Icon Data:** The bank contains large tables of coordinates (`WorldMapIcon_posx_spr0`, etc.) that define where to draw the blinking squares and boss icons for each dungeon and story location on the map.

#### Search Heuristics:

*   **To change the flute warp destinations:**
    1.  Find the `FluteMenu_LoadSelectedScreen` routine.
    2.  This routine calls `FluteMenu_LoadTransport`, which contains a table of the screen indexes for each of the 8 flute spots. Modifying this table changes where the duck takes you.
*   **To change the location of map icons:** Find the `WorldMapIcon_posx_...` and `WorldMapIcon_posy_...` tables and adjust the coordinates for the desired icon.
*   **To modify map rendering:** Look at the `WorldMap_SetUpHDMA` routine and the `WorldMapHDMA_...` tables to understand how the Mode 7 background layers are configured.

### 6.10. Bank $0B: Overworld Environment & State Helpers

**File:** `ALTTP/bank_0B.asm`
**Address Range:** `$0B8000` - `$0BFFFF`

This is a smaller, miscellaneous bank containing important helper functions related to the overworld environment and player state transitions.

#### Key Structures & Routines:

*   **`Overworld_SetFixedColAndScroll` (`#_0BFE70`):** This crucial routine is called when loading an overworld screen. It sets the main background color (`$7EC500`) and fixed color (`$9C`) based on the current area. It contains a series of checks to determine the correct palette (e.g., normal, Dark World, Death Mountain, Lost Woods).
*   **`WallMaster_SendPlayerToLastEntrance` (`#_0BFFB7`):** This function is called when a Wall Master captures Link. It resets Link's state and moves him back to the entrance of the dungeon.
*   **`ResetSomeThingsAfterDeath` (`#_0BFFBF`)::** A helper function called after dying to clear various temporary player state variables.

#### Search Heuristics:

*   **To change the background color of an overworld area:** Modify the color values loaded in `Overworld_SetFixedColAndScroll`. The logic checks the overworld area ID in `$8A` to decide which color to use.
*   **To change what happens when captured by a Wall Master:** Find the `WallMaster_SendPlayerToLastEntrance` routine. This is the entry point for that entire sequence.

### 6.11. Bank $0C: Intro & Credits Sequence

**File:** `ALTTP/bank_0C.asm`
**Address Range:** `$0C8000` - `$0CFFFF`

This bank is dedicated to handling the game's pre-gameplay sequences: the entire introduction from boot-up to the title screen, and the end-game credits.

#### Key Structures & Routines:

*   **`Module00_Intro` (`#_0CC120`):** The main entry point for the entire intro sequence, called from the master game state machine in Bank $00. This routine itself acts as a state machine, using the sub-mode variable `$11` to step through the sequence.
*   **Intro Sequence:** The intro is a multi-step process orchestrated by the `Module00_Intro` jump table:
    1.  **Initialization:** `Intro_InitialInitialization` and `Intro_InitializeMemory` set up the screen and clear memory.
    2.  **Triforce Animation:** `Intro_InitializeTriforcePolyThread` and `Intro_HandleAllTriforceAnimations` manage the pseudo-3D spinning Triforce effect. This uses a special "polyhedral" engine that runs on an IRQ thread.
    3.  **Logo & Title:** `Intro_FadeLogoIn` displays the Nintendo logo, followed by `Intro_SwordStab` and `Intro_PopSubtitleCard` which handle the iconic "The Legend of Zelda" title and the sword animation.
    4.  **Transition:** The sequence ends by setting the main game mode (`$10`) to `0x14` (Attract Mode) to start the gameplay demos.
*   **Credits:** The bank also contains code for the credits sequence (`Credits_InitializePolyhedral`), which reuses some of the Triforce animation logic from the intro.

#### Search Heuristics:

*   **To modify any part of the game's opening cutscene:**
    1.  Start at the `Module00_Intro` jump table in `bank_0C.asm`.
    2.  The sub-mode in `$11` determines which part of the sequence is currently running. Follow the jump table to the routine for the part you want to change (e.g., `Intro_FadeLogoIn`).
*   **To change the timing of the intro sequence:** Look for the code that increments the sub-mode (`INC.b $11`). This is usually at the end of a state's logic (e.g., after a fade is complete). Changing when this happens will alter the pacing.
*   **To investigate the 3D Triforce effect:** Look at `TriforceInitializePolyhedralModule` and `Intro_AnimateTriforce`. This is complex code that interacts with IRQs and likely involves custom DMA to achieve the effect.

### 6.12. Bank $0D: Link Animation & OAM Data

**File:** `ALTTP/bank_0D.asm`
**Address Range:** `$0D8000` - `$0DFFFF`

This bank is not an engine with executable code, but rather a massive **graphical database** that defines every frame of Link's animation. The `LinkOAM_Main` routine (in Bank $00) reads from these tables every frame to construct Link's complete sprite from his body, head, shield, and weapon.

#### Key Structures & Routines:

This bank is almost entirely composed of large data tables.

*   **`LinkOAM_AnimationSteps` (`#_0D85FB`):** This is the master animation sequencer. It contains lists of frame indices for every action Link can perform (walking, running, swimming, lifting, swinging the sword, etc.), separated by direction.
*   **`LinkOAM_PoseData` (`#_0D8000`):** This table is indexed by the values from `LinkOAM_AnimationSteps`. Each entry defines a single animation frame, specifying which body parts to use and how to orient them (e.g., which head sprite, which body sprite, and flip properties).
*   **Equipment Tile Tables (`LinkOAM_WeaponTiles`, `LinkOAM_ShieldTiles`):** These tables map animation frames to the specific graphics tiles used for the sword, shield, and other items Link can hold.
*   **Equipment Offset Tables (`LinkOAM_SwordOffsetX/Y`, `LinkOAM_ShieldOffsetX/Y`, etc.):** These tables are crucial for positioning. For every frame of animation, they provide the precise X and Y offsets needed to draw the sword and shield relative to Link's body, creating the illusion that he is holding them correctly.
*   **`LinkOAM_ShadowTiles` (`#_0D85CF`):** Defines the graphics for Link's shadow and related effects like water splashes and tall grass movement.

#### Search Heuristics:

*   **To modify Link's appearance or animation:**
    1.  Identify the action you want to change (e.g., the walking animation).
    2.  Find the corresponding sequence in `LinkOAM_AnimationSteps`. The values are indices.
    3.  Use those indices to look up the frames in `LinkOAM_PoseData`. Modifying the values here will change which body parts are used for that frame.
*   **To change how Link holds his sword:**
    1.  Identify the animation frame you want to adjust (e.g., the third frame of the upward sword swing).
    2.  Find the index for that frame in the `LinkOAM_AnimationSteps` table.
    3.  Use that index to find the corresponding entries in the `LinkOAM_SwordOffsetX` and `LinkOAM_SwordOffsetY` tables. Changing these values will move where the sword is drawn for that frame.
*   **To change the graphics of the Master Sword itself:** Find the `LinkOAM_WeaponTiles` table. This table points to the actual tile numbers for the sword's graphics for each frame.

### 6.13. Bank $0E: Tile Properties & Credits Engine

**File:** `ALTTP/bank_0E.asm`
**Address Range:** `$0E8000` - `$0EFFFF`

This bank has two primary, unrelated functions. It serves as a data repository for fundamental game assets (font, tile properties), and it contains the entire engine for the end-game credits sequence.

#### Key Structures & Routines:

*   **Game Font:**
    *   `TheFont` (`#_0E8000`): This is the raw 2bpp graphical data for the game's main font, included as a binary file.

*   **Tile Property Tables:** These tables are critical for world interaction. They define the physical behavior of every map tile in the game.
    *   `OverworldTileTypes` (`#_0E9459`): A large table where each byte corresponds to a 16x16 map tile and defines its properties (e.g., solid, water, grass, pit, ledge).
    *   `UnderworldTileTypes` (`#_0E9659`): The equivalent table for all dungeon tilesets.
    *   `Underworld_LoadCustomTileTypes` (`#_0E942A`): A function that loads alternate sets of tile properties for dungeons that have unique behaviors (e.g., ice physics).

*   **Credits Sequence Engine:**
    *   `Module1A_Credits` (`#_0E986E`): The main entry point for the credits, called from the master game state machine. It functions as a state machine, using the sub-mode in `$11` to step through the entire credits sequence.
    *   **Sequence Data:** The routine uses a series of large tables to define each scene in the credits:
        *   `.vectors`: A jump table for the logic of each scene (e.g., `Credits_LoadNextScene_Overworld`, `Credits_ScrollScene_Underworld`).
        *   `Credits_ScrollScene.target_y/x`: Defines the target camera coordinates for each scene's scrolling motion.
        *   `Credits_PrepAndLoadSprites.vectors`: A jump table that points to sprite-loading routines for each scene, which in turn use position tables to place each character.

#### Search Heuristics:

*   **To change the behavior of a map tile (e.g., make a wall walkable):**
    1.  Identify the tile's graphical ID.
    2.  Find its corresponding entry in the `OverworldTileTypes` or `UnderworldTileTypes` tables.
    3.  Change the byte value to that of a tile with the desired properties (e.g., change a wall tile's value to a floor tile's value).
*   **To change the credits sequence:**
    1.  Go to the `Module1A_Credits` routine.
    2.  To change the order of scenes, modify the main `.vectors` jump table.
    3.  To change the camera movement, modify the `Credits_ScrollScene.target_y/x` tables.
    4.  To change which characters appear in a scene, find the corresponding `Credits_LoadSprites_...` routine and its associated position data tables.

### 6.14. Bank $0F: Miscellaneous Game Logic & Helpers

**File:** `ALTTP/bank_0F.asm`
**Address Range:** `$0F8000` - `$0FFFFF`

This bank is a collection of important, miscellaneous subroutines that support the main game engines. It handles specific states like player death and provides common utility functions that are called from many different parts of the codebase.

#### Key Structures & Routines:

*   **Player Death Sequence:**
    *   `PrepareToDie` (`#_0FFA6F`): This is called when Link's health reaches zero. It is responsible for resetting a large number of WRAM variables to their default state, effectively cleaning up Link's status before the death animation begins.
    *   `Link_SpinAndDie` (`#_0FF5C3`): This routine manages the entire visual and timed sequence of Link's death, including the spinning animation, the flashing, and the eventual transition to the "Game Over" screen.

*   **Engine Helpers:**
    *   `Ancilla_CheckForAvailableSlot` (`#_0FF577`): A critical support function for the Ancilla Engine. Before any projectile or effect can be spawned, this routine is called to find an empty slot in the ancilla memory table. It contains logic to limit the number of certain ancilla types on screen at once.
    *   `Sprite_CancelHookshot` (`#_0FF540`): A utility function to immediately terminate the hookshot, returning it to Link. This is used when Link is hit or other interrupting events occur.

*   **Interface Management:**
    *   `Interface_PrepAndDisplayMessage` (`#_0FFDAA`): A standard helper function used throughout the game to initiate a dialogue box. It saves the current game state and switches the main game `MODE` (`$10`) to `0x0E` (Interface), which passes control to the menu and text engine.

#### Search Heuristics:

*   **To modify the player death sequence:** The entry points are `PrepareToDie` and `Link_SpinAndDie`. Changes to the animation timing or visual effects would be made here.
*   **To change the number of a certain projectile allowed on screen:** Find where `Ancilla_CheckForAvailableSlot` is called before the `AncillaAdd_...` routine for that projectile. The value passed to it determines the limit.
*   **To find code that triggers a message box:** Search for `JSL Interface_PrepAndDisplayMessage`. The code immediately preceding it will be setting up the message ID to be displayed.

### 6.14.1. Bank $10-$18: Graphics Sheets for Link, Dungeon, Overworld, Sprites

### 6.14.2. Bank $19: Sound Data

### 6.15. Bank $1A: Miscellaneous Sprites & Cutscenes

**File:** `ALTTP/bank_1A.asm`
**Address Range:** `$1A8000` - `$1AFFFF`

This bank is a collection of miscellaneous sprite logic. It doesn't contain a single, unified engine but rather houses the code for a variety of unique sprites, NPCs, cutscene events, and environmental interactions that are too specific for the main sprite engine in Bank $06.

#### Key Structures & Routines:

*   **`Sprite_37_Waterfall` / `BatCrash`:** The cutscene logic for the bat that crashes into the Pyramid of Power, opening the entrance. It's initiated by a special waterfall sprite (`Sprite_37`) that dispatches to the `BatCrash` routine.
*   **`Sprite_Cukeman`:** The logic for the friendly green Zora who gives you the Zora Flippers, including its dialogue trigger logic.
*   **`Overworld_SubstituteAlternateSecret`:** A system that can dynamically replace the item found under a liftable rock/bush with an enemy or a different item based on various conditions like game state and number of sprites on screen.
*   **`SpriteDraw_Mothula`:** The complex drawing routine for the Mothula boss, which handles its multi-part body and wings.
*   **`Lanmola_SpawnShrapnel`:** A helper function for the Lanmola boss fight to spawn rock shrapnel when a segment is destroyed.
*   **`SpawnHammerWaterSplash`:** A utility to create a water splash effect when the hammer hits a water tile, used to reveal the entrance to the Waterfall of Wishing.
*   **Various NPC/Object Routines:** Includes logic for the Drunkard (`SpriteDraw_Drunkard`), the Race Game Lady (`SpriteDraw_RaceGameLady`), the Chicken Lady (`ChickenLady`), the Digging Game Guy (`SpritePrep_DiggingGameGuy`), and the pushable mantlepiece in Hyrule Castle (`Sprite_EE_CastleMantle`).

#### Search Heuristics:

*   To find the Pyramid of Power opening cutscene, search for `BatCrash` or `CreatePyramidHole`.
*   To find logic for unique NPCs not found in other banks (like the Cukeman or the Drunkard), check this bank.
*   To understand how secrets under rocks are sometimes replaced by enemies, analyze `Overworld_SubstituteAlternateSecret`.
*   For specific boss-related drawing or helper functions (like Mothula's drawing or Lanmola's shrapnel), this bank might contain the code if it's not in the main sprite banks.
*   To find the code that creates the splash when hammering the waterfall to reveal the cave, look for `SpawnHammerWaterSplash`.

### 6.16. Bank $1B: Overworld Interaction & Palettes

**File:** `ALTTP/bank_1B.asm`
**Address Range:** `$1B8000` - `$1BFFFF`

This bank is the heart of the overworld interaction system. It contains extensive data tables and logic that govern how the player transitions from the overworld to the underworld, as well as how items affect the environment. It manages all pits, doors, and item-based tile interactions like digging, hammering, and bombing. A significant portion of the bank is also dedicated to storing palette data for the entire game.

#### Key Structures & Routines:

*   **Entrance Data Tables:** A massive collection of tables at the start of the bank (`Overworld_EntranceScreens`, `Overworld_EntranceTileIndex`, `Overworld_Entrance_ID`) that define every entrance in the game, mapping overworld tile coordinates to specific underworld room IDs.
*   **`Overworld_UseEntrance`:** The primary routine called when Link interacts with a door tile. It uses the entrance tables to look up the destination and initiate the transition to the underworld.
*   **`Overworld_GetPitDestination`:** Determines where Link ends up when he falls into a hole in the overworld, using its own set of tables to map pit locations to specific entrances.
*   **`HandleItemTileAction_Overworld`:** The main dispatcher for when an item is used on an overworld tile. It checks the item used (shovel, powder, hammer) and the tile type to call the appropriate sub-handler.
*   **`OverworldData_HiddenItems`:** A huge database, organized by screen, that lists the location and type of every secret hidden under a liftable object or behind a bombable wall.
*   **`Overworld_RevealSecret`:** The function that consults the `OverworldData_HiddenItems` tables to determine what to spawn when a secret is uncovered.
*   **`PaletteData`:** A very large section containing hundreds of pre-defined 15-color palettes for sprites, Link's armor, UI elements, and backgrounds.
*   **`Palettes_Load_*` Routines:** A suite of functions that read from the `PaletteData` section and write the colors to CGRAM, such as `Palettes_Load_LinkArmorAndGloves`, `Palettes_Load_SpriteMain`, and `Palettes_Load_OWBGMain`.

#### Search Heuristics:

*   **To change where an overworld door leads:** Find its entry in the `Overworld_Entrance...` tables at the top of the bank.
*   **To modify what happens when an item is used on the ground:** Start at `HandleItemTileAction_Overworld`.
*   **To change the item under a specific bush:** Find the correct `OverworldData_HiddenItems_Screen_XX` table and modify the entry corresponding to that bush's coordinates.
*   **To change a sprite or armor color:** Find the correct palette in the `PaletteData` section and modify the desired color values.

### 6.16.1. Bank $1C: Text Data

### 6.17. Bank $1D: Advanced Sprite & Boss AI

**File:** `ALTTP/bank_1D.asm`
**Address Range:** `$1D8000` - `$1DFFFF`

This bank contains the specific, complex logic for many of the game's most iconic bosses and late-game enemies. While other banks manage the general sprite framework, this bank gives these characters their unique attack patterns and behaviors.

#### Key Structures & Routines:

*   **Ganon Fight:** A significant portion of the bank is dedicated to the final battle with Ganon. This includes logic for his different phases, spawning his phantom (`SpawnPhantomGanon`), his trident attack (`Sprite_GanonTrident`), and his fire bat attack (`Sprite_GanonBat`).
*   **Major Boss AI:** It contains the complete AI for several key dungeon bosses:
    *   **Moldorm** (`Sprite_09_Moldorm`): The boss of the Tower of Hera.
    *   **Vitreous** (`Sprite_BD_Vitreous`): The boss of Misery Mire, including its smaller eyeballs.
    *   **Trinexx** (`Sprite_CB_TrinexxRockHead`): The main logic for Trinexx, the boss of Turtle Rock, including its rock, fire, and ice heads.
    *   **Blind the Thief** (`Sprite_CE_Blind`): The boss of the Thieves' Town.
*   **Complex Enemies:** It also handles a variety of other challenging enemies:
    *   **Lynel** (`Sprite_D0_Lynel`): The powerful centaurs on Death Mountain.
    *   **Chain Chomp** (`Sprite_CA_ChainChomp`): The familiar enemy from the Mario series.
    *   **Pokey** (`Sprite_C7_Pokey`): The cactus enemy from the Desert Palace.
    *   **Swamola** (`Sprite_CF_Swamola`): The large, flying serpents in the Swamp of Evil.
*   **Shared Physics and Utilities:** The bank also includes many common helper routines for sprite physics, such as `Sprite_Move_XY_Bank1D`, `Sprite_BounceFromTileCollision`, and `Sprite_ApplyConveyor`.

#### Search Heuristics:

*   To modify the final battle, search for `Ganon` routines in this bank.
*   To alter the behavior of bosses like Moldorm, Vitreous, Trinexx, or Blind, their main AI routines are located here.
*   To change how late-game enemies like Lynels or Chain Chomps behave, find their corresponding `Sprite_...` routine in this bank.

### 6.18. Bank $1E: Advanced Sprite & Boss AI (Continued)

**File:** `ALTTP/bank_1E.asm`
**Address Range:** `$1E8000` - `$1EFFFF`

This bank is another major collection of advanced sprite and boss logic, complementing Bank $1D$. It contains the AI for some of the most mechanically complex bosses and enemies, as well as a master jump table (`SpriteModule_Active_Bank1E`) that dispatches to all the sprite routines housed within it.

#### Key Structures & Routines:

*   **Major Boss AI:** This bank is home to several major boss encounters:
    *   **Helmasaur King** (`Sprite_92_HelmasaurKing`): The complete AI for the Palace of Darkness boss, including its tail-wagging, fireballs, and mask-breaking mechanics.
    *   **Kholdstare** (`Sprite_A2_Kholdstare`): The Ice Palace boss, including the logic for its shell (`Sprite_A3_KholdstareShell`) and the falling ice (`Sprite_A4_FallingIce`) it summons.
    *   **Arrghus** (`Sprite_8C_Arrghus`): The boss of the Swamp Palace, which manages the main body and the smaller "Arrghi" that circle it (`Sprite_8D_Arrghi`).
    *   **Agahnim** (`Sprite_7A_Agahnim`): The logic for the wizard boss fight, including his ball lightning attack (`Sprite_7B_AgahnimBalls`).
*   **Complex Enemies:** It also defines the behavior for many memorable enemies:
    *   **Freezor** (`Sprite_A1_Freezor`): The invincible ice enemies from the Ice Palace.
    *   **Wizzrobe** (`Sprite_9B_Wizzrobe`): The teleporting magic-users.
    *   **Stalfos Knight** (`Sprite_91_StalfosKnight`): The large, bone-throwing skeletons.
*   **Key NPCs and Objects:**
    *   **Kiki the Monkey** (`Sprite_B6_Kiki`): The monkey who opens the Palace of Darkness.
    *   **Blind's Maiden** (`Sprite_B7_BlindMaiden`): The maiden who follows Link before revealing herself as the boss Blind.
    *   **Purple Chest** (`Sprite_B4_PurpleChest`): The special chest that follows Link until it can be opened by the smithy.

#### Search Heuristics:

*   To find the AI for bosses like Helmasaur King, Kholdstare, Arrghus, or Agahnim, search for their respective `Sprite_...` routines in this bank.
*   The master jump table at `SpriteModule_Active_Bank1E` provides a comprehensive list of all sprites managed by this bank and is a good starting point for investigation.
*   To modify the behavior of unique NPCs like Kiki or the maiden who becomes Blind, their logic is located here.

#### 6.19. Bank $1F: Dungeon Room Data

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

