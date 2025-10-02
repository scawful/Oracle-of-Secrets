# Time System (`Overworld/time_system.asm`)

## Overview

This system manages the in-game clock, day/night cycle, and associated palette effects. It runs continuously, updating the time and adjusting visual elements like the sky color and sprite palettes based on the current hour.

## Key Functionality

- **Clock:** A 24-hour clock is maintained in SRAM (`Hours` at `$7EE000`, `Minutes` at `$7EE001`).
- **Palette Modulation:** The core of the system is `ColorSubEffect`, which subtracts values from the red, green, and blue components of palettes based on the time of day, using lookup tables.
- **Time-Based Events:** The system checks for daily events (like the Magic Bean quest) and handles time manipulation effects (like the Song of Time).
- **HUD Display:** It includes logic to draw the current time to the HUD.

## Analysis & Areas for Improvement

The time system is functional but could be significantly improved in terms of structure, readability, and maintainability.

### 1. Move Patches to `Core/patches.asm`

- **Observation:** The file contains numerous `org` patches that modify vanilla game logic to hook in the time system.
- **Suggestion:** Relocate all `org` blocks to the centralized `Core/patches.asm` file. This is the most important cleanup step.
- **Benefit:** This will separate the new system's implementation from the act of patching it into the original code, making both parts easier to understand and manage.

### 2. Use a `struct` for Time-Related Variables

- **Observation:** Time-related variables are defined as individual labels pointing to SRAM addresses (e.g., `Hours`, `Minutes`, `TimeSpeed`, `!BlueVal`).
- **Suggestion:** Group these related variables into a single `struct`.

  *Example:*
  ```asm
  struct TimeState
    Hours     db
    Minutes   db
    TimeSpeed db
    ; ... other vars ...
    BlueVal   dw
    GreenVal  dw
    RedVal    dw
  endstruct

  ; Then access with:
  LDA TimeState.Hours, X
  ```
- **Benefit:** This provides a clear, high-level definition of the data structure, improves readability, and makes it easier to manage memory layout.

### 3. Use `subroutine` for Code Blocks

- **Observation:** The file consists of many large, labeled blocks of code (e.g., `RunClock`, `DrawClockToHud`, `ColorSubEffect`).
- **Suggestion:** Convert these blocks to use `subroutine`/`endsubroutine`.
- **Benefit:** This clearly defines the scope of each piece of logic, makes labels within them local by default, and improves overall code structure.

### 4. Refactor Large Subroutines

- **Observation:** `RunClock` is a very large and complex subroutine with multiple responsibilities and deep nesting.
- **Suggestion:** Break `RunClock` into smaller, more focused subroutines.
  - `TimeSystem_CheckCanRun`: A subroutine to check the game state (`$10`, `$11`) and decide if the clock should tick.
  - `TimeSystem_IncrementTime`: A subroutine to handle the core logic of incrementing minutes and hours.
  - `TimeSystem_UpdatePalettes`: A subroutine to call the palette update logic when the hour changes.
- **Benefit:** Smaller, single-purpose functions are easier to read, debug, and maintain.

### 5. Replace Magic Numbers with Constants

- **Observation:** The code is replete with hardcoded values for time, palettes, and game states.
- **Suggestion:** Define constants for these values using `!` or `define()`.

  *Example:*
  ```asm
  !TIME_SPEED_NORMAL = $3F
  !GAME_STATE_OVERWORLD = $09

  LDA.b #!TIME_SPEED_NORMAL : STA.l TimeSpeed
  LDA $10 : CMP #!GAME_STATE_OVERWORLD : BEQ .overworld
  ```
- **Benefit:** Makes the code self-documenting and reduces the risk of errors when modifying these values.
