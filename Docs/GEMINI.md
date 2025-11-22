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

**Practical Example:**
```asm
; INCORRECT: Size mismatch causes corruption
REP #$20        ; A = 16-bit
LDA.w #$1234    ; A = $1234

SEP #$20        ; A = 8-bit now
LDA.w #$1234    ; ERROR: Assembler generates LDA #$34, $12 becomes opcode!

; CORRECT: Match processor state to operation
REP #$20        ; A = 16-bit
LDA.w #$1234    ; A = $1234

SEP #$20        ; A = 8-bit
LDA.b #$12      ; Load only 8-bit value
```

**Best Practice:**
```asm
MyFunction:
    PHP              ; Save caller's processor state
    SEP #$30         ; Set to known 8-bit state
    ; ... your code here ...
    PLP              ; Restore caller's processor state
    RTL
```

See `Docs/General/Troubleshooting.md` Section 3 for comprehensive processor state troubleshooting.

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

- **Guideline:** Hooks and patches should be placed logically near the code they relate to, not centralized in `Core/patches.asm`. This improves code organization, maintainability, and context preservation.
- **Rationale:** When a hook modifies vanilla behavior to add custom functionality, placing the hook in the same file as the custom implementation keeps related code together. This makes it easier to understand the complete feature, debug issues, and maintain the codebase.
- **Exception:** Only truly generic, cross-cutting patches that don't belong to any specific feature should be considered for `Core/patches.asm`.

### 3.3. Debugging

- The `!DEBUG` flag and `%print_debug()` macro in `Util/macros.asm` should be used for all build-time logging. This allows for easy enabling/disabling of diagnostic messages.

### 3.4. Referencing Vanilla Code (`usdasm`)

- When hooking or modifying vanilla code, it is essential to understand the original context. The `usdasm` disassembly is the primary reference for this.
- To find the original code for a patch at a given address (e.g., `$07A3DB`), you can search for the SNES address in the `usdasm` files (e.g., `#_07A3DB:`).
- **Vanilla labels are not included by default.** The `usdasm` project is a reference, not part of the build. If you need to call a vanilla routine, you must find its implementation in the disassembly and explicitly copy or recreate it within the `Oracle of Secrets` source, giving it a new label (e.g., inside the `Oracle` namespace).
- **Disassembly files are for reference only.** Never modify any files within the `usdasm` directory. All changes must be made within the `Oracle of Secrets` project files.

### 3.5. Namespacing

- **Guideline:** The majority of the *Oracle of Secrets* codebase is organized within an `Oracle` namespace, as defined in `Oracle_main.asm`. However, some modules, notably `ZSCustomOverworld.asm`, are included *outside* of this namespace.
- **Interaction:** To call a function that is inside the `Oracle` namespace from a file that is outside of it (like `ZSCustomOverworld.asm`), you must prefix the function's label with `Oracle_`. For example, to call the `CheckIfNight16Bit` function (defined inside the namespace), you must use `JSL Oracle_CheckIfNight16Bit`.
- **Rationale:** The build process correctly resolves these `Oracle_` prefixed labels to their namespaced counterparts (e.g., `Oracle.CheckIfNight16Bit`). Do not add the `Oracle_` prefix to the original function definition; it is only used by the calling code outside the namespace.

**Practical Example - Oracle to ZScream:**
```asm
// In ZScream file (no namespace):
LoadOverworldSprites_Interupt:
{
    ; ZScream code here
    RTL
}

// Export to Oracle namespace:
namespace Oracle
{
    Oracle_LoadOverworldSprites_Interupt = LoadOverworldSprites_Interupt
}

// Now Oracle code can call it:
namespace Oracle
{
    MyFunction:
        JSL Oracle_LoadOverworldSprites_Interupt  ; Use prefix!
        RTL
}
```

**Practical Example - ZScream to Oracle (Bridge Pattern):**
```asm
// Oracle implementation:
namespace Oracle
{
    CheckIfNight:
        LDA.l $7EE000  ; Check time system
        ; ... logic ...
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

// ZScream hook can use it:
org $09C4C7
LoadOverworldSprites_Hook:
    JSL Oracle_ZSO_CheckIfNight  ; Bridge function
```

For comprehensive namespace troubleshooting and advanced patterns, see:
- `Docs/World/Overworld/ZSCustomOverworldAdvanced.md` Section 5 (Cross-Namespace Integration)
- `Docs/General/Troubleshooting.md` Section 5 (Cross-Namespace Calling)
- `Docs/General/DevelopmentGuidelines.md` Section 2.4 (Namespace Architecture)

### 3.6. Safe Hooking and Code Injection

When modifying vanilla game logic, it is critical to never edit the disassembly files in `ALTTP/` or `usdasm/` directly. Instead, use the following safe hooking method to inject custom code.

- **1. Identify a Target and Free Space:**
  - Locate the exact address in the vanilla code you want to modify (the "hook point").
  - Identify a free bank or region in the ROM to place your new, expanded code.

- **2. Choose the Appropriate File for Your Hook:**
  - **Feature-Specific Hooks:** Place hooks in the same file as the custom implementation they enable. For example, if you're adding a new item feature in `Items/magic_ring.asm`, place the vanilla hook in that same file.
  - **Module-Specific Hooks:** For hooks that modify core game systems (sprite engine, player engine, etc.), place them in the relevant module file within the `Core/` directory.
  - **Generic Patches:** Only place truly generic, cross-cutting modifications in `Core/patches.asm` (e.g., fixes to vanilla bugs, performance optimizations).
  - **Rationale:** Co-locating hooks with their implementations improves code organization, makes features self-contained, and provides better context for future maintenance.

- **3. Write the Hook:**
  - Use `pushpc` and `pullpc` to isolate your patch.
  - Use `org` to navigate to the target address in the vanilla code.
  - At the target address, overwrite the original instruction(s) with a `JSL` (or `JMP`) to your new custom routine in free space.
  - **Crucially, ensure your `JSL`/`JMP` instruction and any necessary `NOP`s perfectly replace the original instruction(s) byte-for-byte.** A `JSL` is 4 bytes. If you overwrite an instruction that is only 2 bytes, you must add `NOP` instructions to fill the remaining 2 bytes to avoid corrupting the subsequent instruction.

- **4. Implement the Custom Routine:**
  - In a `freedata` block (or using `org` with a free space address), write your new routine in the same file as the hook.
  - **Preserve Overwritten Code:** The first thing your new routine must do is execute the exact vanilla instruction(s) that you overwrote with your `JSL`. This is essential to maintain the original game's behavior.
  - After preserving the original logic, add your new custom code.
  - End your routine with an `RTL` (to return from a `JSL`) or `RTS` (to return from a `JSR`).

- **Example (Feature-Specific Hook):**
  ```asm
  ; In Items/magic_ring.asm

  ; 1. Place the new, expanded logic in a free bank.
  org $348000
  MagicRing_CustomEffect:
  {
    ; 2. First, execute the original instruction(s) that were overwritten.
    LDA.b #$01         ; Example: Original instruction was LDA #$01 (2 bytes)
    STA.w $0DD0,X      ; Example: Original instruction was STA $0DD0,X (3 bytes)

    ; 3. Now, add your new custom logic for the magic ring.
    LDA.l MagicRing    ; Check if player has magic ring
    BEQ .no_ring
      LDA.b #$FF       ; Apply ring's special effect
      STA.w $1234,X
    .no_ring

    ; 4. Return to the vanilla code.
    RTL
  }

  ; 5. Hook placement: In the same file, near the feature implementation
  pushpc
  org $05C227 ; Target address in vanilla sprite damage routine
  JSL MagicRing_CustomEffect ; JSL is 4 bytes.
  NOP ; Fill the 5th byte since we overwrote two instructions (2+3=5 bytes)
  pullpc
  ```

- **Example (Core System Hook):**
  ```asm
  ; In Core/sprite_engine_hooks.asm (or similar)

  org $348100
  CustomSprite_DeathHandler:
  {
    ; Preserve original death logic
    LDA.w SprHealth, X
    BNE .not_dead
      ; Original vanilla death code here
      JSL Sprite_SpawnDeathAnimation
    .not_dead
    
    ; Add custom death effects for Oracle sprites
    LDA.w SprType, X
    CMP.b #CustomSpriteID : BNE .skip_custom
      JSR CustomSprite_SpecialDeath
    .skip_custom
    
    RTL
  }

  ; Hook in same file
  pushpc
  org $068450
  JSL CustomSprite_DeathHandler
  pullpc
  ```

## 4. Build Process and ROM Management

- **Clean ROM**: The clean, unmodified "The Legend of Zelda: A Link to the Past" ROM should be placed at `Roms/oos169.sfc`. This path is included in `.gitignore`, so the ROM file will not be committed to the repository.
- **Build Script**: A `build.sh` script is provided to automate the build process. For detailed usage, see `Docs/General/AsarUsage.md`.
- **Workflow**: The build script creates a fresh copy of the clean ROM and applies the `Oracle_main.asm` patch to it using `asar`.
- **Important**: Never apply patches directly to `Roms/oos169.sfc`. Always use the build script to create a new, patched ROM. This ensures the clean ROM remains untouched for future builds.

## 5. Debugging Tips for BRKs and Crashes

When encountering unexpected crashes (often indicated by a `BRK` instruction in emulators), especially after modifying code, consider the following:

**For comprehensive debugging guidance with step-by-step procedures, see `Docs/General/Troubleshooting.md`.**

### 5.1. Most Common Causes

- **Processor Status Register (P) Mismatch:** This is a very common cause. If a routine expects 8-bit accumulator/index registers (M=1, X=1) but is called when they are 16-bit (M=0, X=0), or vice-versa, memory accesses and arithmetic operations will be incorrect, leading to crashes.

**Example:**
```asm
; BAD: Size mismatch
REP #$20        ; A = 16-bit
JSL Function    ; Function expects 8-bit!

; Inside Function:
SEP #$20        ; Sets 8-bit mode
LDA.b #$FF
STA.w $1234     ; Only stores $FF, not $00FF!
RTL             ; ← Doesn't restore caller's 16-bit mode

; GOOD: Preserve state
Function:
    PHP         ; Save caller's state
    SEP #$20    ; Set to 8-bit
    LDA.b #$FF
    STA.w $1234
    PLP         ; Restore caller's state
    RTL
```

- **Stack Corruption:** JSL/JSR push the return address onto the stack. If a called routine pushes too much data onto the stack without popping it, or if the stack pointer (`S`) is corrupted, the return address can be overwritten, leading to a crash when `RTL`/`RTS` is executed.
    - **`JSR`/`RTS` vs `JSL`/`RTL` Mismatch:** This is a critical and common error.
        - `JSR` (Jump to Subroutine) pushes a 2-byte return address. It **must** be paired with `RTS` (Return from Subroutine), which pulls 2 bytes.
        - `JSL` (Jump to Subroutine Long) pushes a 3-byte return address (including the bank). It **must** be paired with `RTL` (Return from Subroutine Long), which pulls 3 bytes.

**Example:**
```asm
; BAD: Mismatched call/return
MainFunction:
    JSL SubFunction  ; Pushes 3 bytes ($02 $C4 $09)
    
SubFunction:
    ; ... code ...
    RTS  ; ← ERROR: Only pops 2 bytes! Stack corrupted!

; GOOD: Matched call/return
MainFunction:
    JSL SubFunction  ; Pushes 3 bytes
    
SubFunction:
    ; ... code ...
    RTL  ; ← Correct: Pops 3 bytes
```

### 5.2. Debugging Tools

- **Mesen-S (Recommended):** The most powerful SNES debugger:
    - Set breakpoints with conditions: `A == #$42`
    - Memory watchpoints: `[W]$7E0730` (break on write)
    - Stack viewer to trace call history
    - Event viewer for NMI/IRQ timing
    - Break on BRK automatically

**Quick Mesen-S Workflow:**
1. Enable "Break on BRK" in Debugger settings
2. When crash occurs, check Stack viewer
3. Read return addresses to trace call history
4. Set breakpoint before suspected crash location
5. Step through code examining registers

- **Breadcrumb Tracking:**
```asm
; Add markers to narrow down crash location
LDA.b #$01 : STA.l $7F5000  ; Breadcrumb 1
JSL SuspiciousFunction
LDA.b #$02 : STA.l $7F5000  ; Breadcrumb 2
JSL AnotherFunction
LDA.b #$03 : STA.l $7F5000  ; Breadcrumb 3

; After crash, check $7F5000 in memory viewer
; If value is $02, crash occurred in AnotherFunction
```

### 5.3. Common Error Patterns

**Pattern 1: Jumping to $000000 (BRK)**
- Cause: Corrupted jump address or return address
- Debug: Check stack contents, verify JSL/JSR is called before RTL/RTS

**Pattern 2: Infinite Loop / Freeze**
- Cause: Forgot to increment module/submodule, infinite recursion
- Debug: Check that `$10` (module) or `$11` (submodule) is incremented

**Pattern 3: Wrong Graphics / Corrupted Screen**
- Cause: DMA during active display, wrong VRAM address
- Debug: Ensure graphics updates only during NMI or Force Blank

### 5.4. Cross-Reference Documentation

For specific debugging scenarios:
- **BRK Crashes:** `Docs/General/Troubleshooting.md` Section 2
- **Stack Corruption:** `Docs/General/Troubleshooting.md` Section 3  
- **Processor State Issues:** `Docs/General/Troubleshooting.md` Section 4
- **Namespace Problems:** `Docs/General/Troubleshooting.md` Section 5
- **Memory Conflicts:** `Docs/General/Troubleshooting.md` Section 6
- **Graphics Issues:** `Docs/General/Troubleshooting.md` Section 7
- **ZScream-Specific:** `Docs/General/Troubleshooting.md` Section 8



### 5.5. Recent Debugging Insights

During recent development and bug-fixing tasks, several critical patterns and debugging insights have emerged:

-   **Processor Status Mismatch (M/X flags) and BRK (`$00` opcode):**
    -   A common cause of crashes is calling a routine expecting a different processor mode (e.g., 16-bit Accumulator) than the current CPU state (e.g., 8-bit Accumulator).
    -   Specifically, if an `AND.w #$00FF` instruction is encountered while the A-register is in 8-bit mode (`SEP #$20` active), the assembler may generate `29 FF 00`. The CPU will execute `29 FF` (AND immediate byte), and then interpret the trailing `00` as a `BRK` instruction, leading to a crash.
    -   **Resolution:** Always explicitly set the processor state (`REP #$30` for 16-bit, `SEP #$30` for 8-bit) at the entry of routines that depend on a specific mode, and consider `PHP`/`PLP` for state preservation if the routine needs to temporarily change modes or be called from various contexts.

-   **Input Polling Registers for Continuous Actions:**
    -   For features requiring continuous input (e.g., holding a button to navigate in a menu or turn pages), use the joypad register that tracks **all pressed buttons** (`$F2` / `JOY1B_ALL`).
    -   Avoid using registers that only signal **new button presses** (`$F6` / `JOY1B_NEW`), as these will only trigger an action for a single frame, making continuous interaction impossible.
    -   **Resolution:** Pair `$F2` checks with a delay timer (`$0207` in our context) to prevent rapid-fire actions.

-   **VRAM Update Flags (`$0116`, `$15`, `$17`) for Menu Graphics:**
    -   The variable `$0116` acts as a crucial trigger for the vanilla NMI handler (`NMI_DoUpdates`) to perform VRAM updates. **Bit 0 of `$0116` must be set (`$01`, or part of `$21`, `$23`, `$25`, etc.)** for standard tilemap and OAM buffer uploads to occur. Values like `$22` (where bit 0 is clear) may be ignored by the vanilla NMI handler for general VRAM updates.
    -   The `$15` flag (often referred to as the Palette/Refresh flag) should often be set alongside `$17` (NMI module selection) to ensure consistent and complete VRAM refreshes, especially for full-screen updates.
    -   **Resolution:** When a menu state needs to update its tilemap or OAM visually, ensure `$0116` has bit 0 set, and consider setting `$15` for comprehensive refreshes.

-   **Data Table Mismatches (Logical vs. Visual Indexing):**
    -   In UI-heavy features (like inventory or submenus), a misalignment between a table defining the *logical order* of items (e.g., `Menu_AddressIndex`) and a table defining their *visual positions* (e.g., `Menu_ItemCursorPositions`) can lead to subtle bugs.
    -   **Symptom:** A cursor might appear in the wrong place, or attempting to clear a cursor from one item might inadvertently clear another, resulting in visual artifacts.
    -   **Resolution:** Rigorously align item indices across all related data tables, ensuring a 1:1 mapping between logical item order and visual screen coordinates.

-   **Custom NMI Handlers and Vanilla System Integration:**
    -   Be aware that extensive custom systems (like ZScream's overworld graphics streaming) may replace or heavily modify vanilla NMI routines. These custom handlers might be designed to process their *own* DMA requests and could potentially ignore standard vanilla flags (`$0116`, `$15`) or input registers.
    -   **Symptom:** Standard game elements (like menus) may fail to update graphics or respond to input if the custom NMI handler does not explicitly integrate or defer to the vanilla update logic.
    -   **Resolution:** If a custom NMI handler is in place, it must either pass control to the vanilla NMI handler when appropriate (e.g., when the game is in a menu state), or manually replicate the necessary vanilla update logic (e.g., checking `$0116` and initiating DMA for menu buffers).

## 6. Verification Policy

- **Bugs and Features:** Never mark a bug fix or feature implementation as `DONE` until it has been thoroughly tested and verified in an emulator. This ensures stability and prevents regressions.


## 7. Memory and Symbol Analysis

This section details the layout and purpose of critical memory regions (WRAM and SRAM) and the symbol definition files that give them context.

**For comprehensive memory documentation, see:**
- `Docs/Core/MemoryMap.md` - Complete WRAM/SRAM map with verified custom variables
- `Docs/Core/Ram.md` - High-level overview of memory usage
- `Docs/General/Troubleshooting.md` Section 6 - Memory conflict resolution

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

## 8. Documentation Reference

This section provides a comprehensive overview of all available documentation files, organized by category. These documents serve as key references for understanding the project's architecture, gameplay systems, and development practices.

### 8.1. Core System Documentation

*   **`Docs/Core/MemoryMap.md`:** Complete WRAM and SRAM memory map with verified custom variables. Documents all custom memory regions from `$7E0730+` (WRAM) and OOS-specific SRAM including `$7EF3D6` (OOSPROG), `$7EF38A+` (collectibles block), and `$7EF410` (Dreams). Essential reference for any code that accesses RAM.

*   **`Docs/Core/Ram.md`:** High-level overview of WRAM and SRAM usage patterns with descriptions of custom variable purposes.

*   **`Docs/Core/Link.md`:** Documentation of Link's state machine, player mechanics, and control handlers.

*   **`Docs/Core/SystemInteractions.md`:** Documentation of core game systems and their interactions.

### 8.2. Development Guidelines

*   **`Docs/General/DevelopmentGuidelines.md`:** Comprehensive development guidelines covering architecture patterns, memory management, assembly best practices, coding standards, and debugging strategies. Expands on concepts in this GEMINI.md file with detailed examples and rationale. **Required reading for all contributors.**

*   **`Docs/General/Troubleshooting.md`:** Comprehensive troubleshooting guide with step-by-step debugging procedures. Covers:
    - BRK crashes and stack traces
    - Stack corruption patterns (JSL/JSR vs RTL/RTS mismatches)
    - Processor status register issues (M/X flag problems)
    - Cross-namespace calling problems
    - Memory conflicts and bank collisions
    - Graphics/DMA timing issues
    - ZScream-specific problems
    - Debugging with Mesen-S and BSNES-Plus

*   **`Docs/General/AsarUsage.md`:** Best practices for using the Asar assembler and the build script system. Covers `org` vs `pushpc`/`pullpc`, ROM management, and build workflow.

### 8.3. Creation Guides

*   **`Docs/Guides/SpriteCreationGuide.md`:** Comprehensive 878-line tutorial for creating custom sprites from scratch. Covers:
    - File setup and bank organization
    - Sprite properties (23 configurable flags with memory addresses)
    - Initialization with 60+ WRAM variables documented
    - Main logic with 30+ macros and 20+ core functions
    - OAM drawing system with tile format specifications
    - Testing procedures and debugging strategies
    - Common issues and solutions
    - 10 advanced patterns:
      1. State Machines (Booki example)
      2. Multi-part Sprites (Kydreeok boss)
      3. Guard/Defense Mechanics (Darknut)
      4. Shared Logic (Goriya variations)
      5. Complex Boss Mechanics
      6. NPC Interactions (Followers)
      7. Interactive Objects (Minecart)
      8. Environmental Awareness
      9. Advanced AI Patterns
      10. Cross-System Integration
    - Real examples from Booki, Darknut, Kydreeok, Goriya, Followers, and Minecart sprites

*   **`Docs/Guides/QuestFlow.md`:** Detailed guide to main story and side-quest progression, including trigger conditions, progression flags, and quest dependencies.

### 8.4. World System Documentation

*   **`Docs/World/Overworld/ZSCustomOverworld.md`:** Basic guide to the ZScream custom overworld system and its data tables.

*   **`Docs/World/Overworld/ZSCustomOverworldAdvanced.md`:** Advanced technical documentation for ZScream integration. **Critical for modifying overworld behavior.** Covers:
    - Internal hook architecture (38+ vanilla routine replacements)
    - Hook execution order during screen transitions
    - Memory management and state tracking (Bank $28 data pool)
    - Graphics loading pipeline with frame-by-frame analysis
    - Sprite loading system deep dive
    - Cross-namespace integration patterns (Oracle ↔ ZScream)
    - Performance considerations and optimization strategies
    - Adding custom features to the overworld system
    - Debugging ZScream-specific issues

*   **`Docs/World/Overworld/TimeSystem.md`:** Documentation of the day/night cycle system implementation.

*   **`Docs/World/Dungeons/Dungeons.md`:** Breakdown of dungeon systems, layouts, enemy placements, and puzzle mechanics.

### 8.5. Feature System Documentation

*   **`Docs/Features/Menu/Menu.md`:** Analysis of the custom menu and HUD systems, including two-page menu layout and item drawing routines.

*   **`Docs/Features/Items/Items.md`:** Guide to custom and modified items, including implementation details for Goldstar, Portal Rod, Ocarina, and others.

*   **`Docs/Features/Music/Music.md`:** Guide to custom music tracks, sound effects, and adding new audio.

*   **`Docs/Features/Masks/Masks.md`:** Comprehensive overview of the Mask System, including transformation mechanics and each mask's abilities.

### 8.6. Sprite Documentation

Each sprite category has both an overview document and individual files for specific sprites:

*   **`Docs/Sprites/NPCs.md`:** Overview of NPC sprite system with links to individual NPC documentation in `Docs/Sprites/NPCs/` (BeanVendor, DekuScrub, EonOwl, Farore, Followers, Impa, Korok, Maple, MaskSalesman, Tingle, Vasu, ZoraPrincess, etc.)

*   **`Docs/Sprites/Bosses.md`:** Overview of boss sprite system with links to individual boss documentation in `Docs/Sprites/Bosses/` (DarkLink, Kydreeok, Manhandla, etc.)

*   **`Docs/Sprites/Enemies/`:** Individual documentation for enemy sprites (AntiKirby, Booki, BusinessScrub, Darknut, Goriya, Keese, Leever, Octorok, PolsVoice, Wolfos, etc.)

*   **`Docs/Sprites/Objects.md`:** Overview of interactive object sprites with documentation in `Docs/Sprites/Objects/` (Collectible, DekuLeaf, IceBlock, Minecart, Pedestal, PortalSprite, etc.)

*   **`Docs/Sprites/Overlords.md`:** Analysis of the Overlord sprite system used for environmental effects and multi-screen management.

## 9. Disassembly Analysis and Search Guide

This section provides a high-level analysis of key banks in the Link to the Past disassembly. Use this guide to quickly locate relevant code and understand the overall structure of the game.

### 9.1. Bank $00: Game Core & Main Loop

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

### 9.2. Bank $01: Dungeon Engine

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

### 9.3. Bank $02: Overworld & Transitions

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

### 9.4. Bank $03: Tile32 Overworld Layout Data

### 9.5. Bank $04: Tile32 Overworld Layout Data, Dungeon Room Headers

### 9.6. Bank $07: Core Player (Link) Engine

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

### 9.7. Bank $05: Specialized Sprite & Object Engine

**File:** `ALTTP/bank_05.asm`
**Address Range:** `$058000` - `$05FFFF`
**Summary:** Code for unique, complex, and scripted sprites that do not fit the standard enemy AI model (e.g., cutscene sprites, minigame hosts, complex traps).

#### Search Heuristics:
*   **Unique/Non-Enemy Sprites:** When looking for a unique sprite (minigame, cutscene object, complex trap), check `bank_05.asm` first.
*   **Finding Sprite Logic:** Search for the sprite's name (e.g., "MasterSword") or its hexadecimal ID (e.g., `Sprite_62`) to find its main routine.

### 9.8. Bank $06: Main Sprite Engine & Helpers

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

### 9.9. Bank $08: Ancilla Engine

**File:** `ALTTP/bank_08.asm`
**Address Range:** `$088000` - `$08FFFF`
**Summary:** The engine for "Ancillae" (projectiles, particle effects, etc.). Contains the execution logic for entities like arrows, bombs, and magic spells.

#### Search Heuristics:
*   **Projectile/Effect Logic:** In `bank_08.asm`, find the main jump table in `Ancilla_ExecuteOne` (at `#_08837F`). Look up the ancilla's ID in this table to find the label for its logic routine (e.g., `Ancilla07_Bomb`).
*   **Projectile Properties (speed, graphics):** Go to the ancilla's main logic routine (e.g., `Ancilla09_Arrow`) and look for writes to its WRAM properties (e.g., `$0C2C` for X-speed).

### 9.10. Bank $09: Ancilla Spawning & Item Logic

**File:** `ALTTP/bank_09.asm`
**Address Range:** `$098000` - `$09FFFF`
**Summary:** Contains the ancilla *creation* engine (a library of `AncillaAdd_...` functions) and the critical logic for giving items to the player.

#### Search Heuristics:
*   **Projectile/Effect Creation:** To find where a projectile is created, search the codebase for `JSL` calls to its corresponding `AncillaAdd_...` function in this bank (e.g., `JSL AncillaAdd_Bomb`).
*   **Item "Get" Properties:** To change the properties of an item the player receives, find the `AncillaAdd_ItemReceipt` routine and examine the large data tables starting at `#_098404`.

### 9.11. Bank $0A: World Map & Flute Menu Engine

**File:** `ALTTP/bank_0A.asm`
**Address Range:** `$0A8000` - `$0AFFFF`
**Summary:** Controls all full-screen map interfaces (pause menu map, flute destination map).

#### Search Heuristics:
*   **Flute Warp Destinations:** In `bank_0A.asm`, find the `FluteMenu_LoadTransport` routine. The table within it maps the 8 flute spots to screen indexes.
*   **Map Icon Locations:** Search for the `WorldMapIcon_posx_...` and `WorldMapIcon_posy_...` tables to adjust icon coordinates.

### 9.12. Bank $0B: Overworld Environment & State Helpers

**File:** `ALTTP/bank_0B.asm`
**Address Range:** `$0B8000` - `$0BFFFF`
**Summary:** Miscellaneous helper functions related to the overworld environment and player state.

#### Search Heuristics:
*   **Overworld Area Palette:** To change the background color of an overworld area, modify the color values loaded in `Overworld_SetFixedColAndScroll`. The logic checks WRAM `$8A` to decide which color to use.
*   **Wall Master Capture:** To change what happens when captured, find the `WallMaster_SendPlayerToLastEntrance` routine.

### 9.13. Bank $0C: Intro & Credits Sequence

**File:** `ALTTP/bank_0C.asm`
**Address Range:** `$0C8000` - `$0CFFFF`
**Summary:** Handles the game's intro and end-game credits sequences.

#### Search Heuristics:
*   **Intro/Credits Scene Logic:** Start at the `Module00_Intro` or `Module1A_Credits` jump tables. The sub-mode in WRAM `$11` determines which part of the sequence is running. Follow the jump table to the routine for the scene you want to change.

### 9.14. Bank $0D: Link Animation & OAM Data

**File:** `ALTTP/bank_0D.asm`
**Address Range:** `$0D8000` - `$0DFFFF`
**Summary:** A massive graphical database defining every frame of Link's animation. It is not executable code.

#### Search Heuristics:
*   **Link's Animation Sequence:** To modify an animation, find the action in `LinkOAM_AnimationSteps`. The values are indices into the `LinkOAM_PoseData` table, which defines the body parts for each frame.
*   **Link's Item Positioning:** To change how Link holds an item, find the animation frame index in `LinkOAM_AnimationSteps` and use it to find the corresponding entries in the `LinkOAM_SwordOffsetX/Y` or `LinkOAM_ShieldOffsetX/Y` tables.

### 9.15. Bank $0E: Tile Properties & Credits Engine

**File:** `ALTTP/bank_0E.asm`
**Address Range:** `$0E8000` - `$0EFFFF`
**Summary:** Contains fundamental game assets (font, tile properties) and the credits engine.

#### Search Heuristics:
*   **Tile Behavior (e.g., making a wall walkable):** Identify the tile's graphical ID and find its entry in the `OverworldTileTypes` or `UnderworldTileTypes` tables. Change its byte value to match a tile with the desired properties.
*   **Custom Tile Physics (e.g., ice):** Search for the `Underworld_LoadCustomTileTypes` function to see how alternate tile property sets are loaded for specific dungeons.

### 9.16. Bank $0F: Miscellaneous Game Logic & Helpers

**File:** `ALTTP/bank_0F.asm`
**Address Range:** `$0F8000` - `$0FFFFF`
**Summary:** A collection of important miscellaneous subroutines, including player death and dialogue box initiation.

#### Search Heuristics:
*   **Player Death Sequence:** The entry points are `PrepareToDie` and `Link_SpinAndDie`.
*   **Dialogue Box Trigger:** Search for `JSL Interface_PrepAndDisplayMessage`. The code immediately preceding it sets up the message ID to be displayed.

### 9.17. Bank $10-$18: Graphics Sheets for Link, Dungeon, Overworld, Sprites

### 9.18. Bank $19: Sound Data

### 9.19. Bank $1A: Miscellaneous Sprites & Cutscenes

**File:** `ALTTP/bank_1A.asm`
**Address Range:** `$1A8000` - `$1AFFFF`
**Summary:** Logic for a variety of unique sprites, NPCs, and cutscene events that are too specific for the main sprite engine.

#### Search Heuristics:
*   **Pyramid of Power Opening:** Search for `BatCrash` or `CreatePyramidHole`.
*   **Waterfall of Wishing Splash:** Search for `SpawnHammerWaterSplash`.
*   **Secret Item Substitution:** To understand how items under rocks are sometimes replaced by enemies, analyze `Overworld_SubstituteAlternateSecret`.

### 9.20. Bank $1B: Overworld Interaction & Palettes

**File:** `ALTTP/bank_1B.asm`
**Address Range:** `$1B8000` - `$1BFFFF`
**Summary:** The heart of the overworld interaction system. Manages all entrances, pits, and item-based tile interactions (digging, bombing). Also contains a very large store of palette data.

#### Search Heuristics:
*   **Overworld Entrances:** To change where a door leads, find its entry in the `Overworld_Entrance...` tables at the top of the bank.
*   **Hidden Item Locations:** To change the item under a specific bush, find the correct `OverworldData_HiddenItems_Screen_XX` table and modify the entry for that bush's coordinates.
*   **Sprite/Armor Colors:** To change a color, find the correct palette in the `PaletteData` section and modify the desired color values.

### 9.21. Bank $1C: Text Data

### 9.22. Bank $1D & $1E: Advanced Sprite & Boss AI

**Files:** `ALTTP/bank_1D.asm`, `ALTTP/bank_1E.asm`
**Summary:** These banks contain the specific, complex AI for most of the game's major bosses and late-game enemies (Ganon, Moldorm, Trinexx, Helmasaur King, Kholdstare, Agahnim, etc.).

#### Search Heuristics:
*   **Boss/Enemy AI:** To modify a specific boss or advanced enemy, search for its `Sprite_...` routine in these two banks (e.g., `Sprite_92_HelmasaurKing` in bank $1E).
*   **Sprite Dispatch Table:** The jump table at `SpriteModule_Active_Bank1E` in `bank_1E.asm` provides a comprehensive list of all sprites managed by that bank and is a good starting point for investigation.

### 9.23. Bank $1F: Dungeon Room Data

## 10. ZScream Expanded ROM Map

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

## 11. Oracle of Secrets Specific Guidelines for Gemini

To ensure accurate and consistent modifications within the Oracle of Secrets project, adhere to the following guidelines regarding memory management and code placement:

- **Understand `incsrc` Order:** The order of `incsrc` directives in `Oracle_main.asm` is paramount. It dictates the final ROM layout, especially for code and data placed using `org`. Always consult `Oracle_main.asm` and `Docs/Core/MemoryMap.md` to understand the current memory allocation before introducing new `org` directives.

- **`org` for New Features:** When implementing new features that require significant code or data, use `org $XXXXXX` to place them in an appropriate free bank. Refer to the detailed memory map in `Docs/Core/MemoryMap.md` and the `Oracle_main.asm` comment for available and designated banks. If a new bank is needed, ensure it does not conflict with existing allocations or ZScream reserved space.

- **`pushpc`/`pullpc` for Patches:** For small, targeted modifications to vanilla code or data (e.g., changing a few bytes, hooking a jump), use `pushpc`/`pullpc`. These directives are ideal for non-intrusive patches that don't require a dedicated bank. Examine `Core/patches.asm` and `Util/item_cheat.asm` for examples of this usage.

- **Consult Memory Map:** Before any code modification involving `org` or `pushpc`/`pullpc`, always cross-reference with `Docs/Core/MemoryMap.md` and the `Oracle_main.asm` comment to prevent memory conflicts and ensure proper placement.

- **Prioritize Existing Conventions:** Mimic the existing style and structure of the codebase. If a new feature is similar to an existing one, follow its implementation pattern, including how it manages memory.

- **Avoid Arbitrary `org`:** Never use `org` without a clear understanding of the target address and its implications for the overall ROM layout. Unplanned `org` directives can lead to crashes or unexpected behavior.
