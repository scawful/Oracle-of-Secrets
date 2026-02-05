# Handoff: House Tag Crash Fix

## Status
The user is experiencing a crash (or hang/execution of undefined code) at address `$2C8328` (Bank `$2C`, offset `$8328`).
This corresponds to the entry point of `HouseTag_Main` in `Dungeons/custom_tag.asm`.

## The Problem
The crash likely stems from an uninitialized or corrupted `StoryState` variable (RAM address `$7C`).
1.  `HouseTag_Main` reads `StoryState`.
2.  It uses this value to index into a jump table: `ASL A : TAX : JSR (.jump_table, X)`.
3.  If `StoryState` contains any value other than `0`, `1`, or `2`, the code reads a pointer from garbage memory (past the end of the jump table) and jumps to an invalid address, causing a crash.
4.  Since `$7C` is a Direct Page address labeled `UNUSED_7C` in `ram.asm`, it is possible it contains random garbage on startup or is being clobbered by another routine using it as scratch space.

## Investigation Findings
*   **Crash Address:** `$2C8328` (Entry of `HouseTag_Main`).
*   **Code Context:**
    ```asm
    HouseTag_Main:
      LDA.w StoryState  ; potentially garbage
      ASL A : TAX
      JSR (.jump_table, X) ; jumps to doom if X is invalid
    ```
*   **Previous Fix:** We replaced a `JSL` to a sprite routine with this local JSR, which is correct architecture, but lacks input validation.

## Proposed Fix (Next Steps)

### 1. Sanitize `StoryState`
Modify `Dungeons/custom_tag.asm` to strictly validate `StoryState` before using it as an index.

**Plan:**
Update `HouseTag_Main` to:
```asm
HouseTag_Main:
{
  LDA.w StoryState
  CMP.b #$03 : BCC .valid_state
    ; If state is invalid (>= 3), force reset to 0 (Intro)
    LDA.b #$00 : STA.w StoryState
  .valid_state
  
  ASL A : TAX
  JSR (.jump_table, X)
  RTS
  ; ... table ...
}
```

### 2. (Optional) Relocate `StoryState`
If the crash persists, `$7C` might be too volatile (used as scratch by other ASM hacks or vanilla routines). Consider moving `StoryState` to a safer, saved location like `$7EF3C9` (if unused) or explicitly defining it in a known safe WRAM region (e.g., `$7E04B0+`).

## Files to Modify
*   `Dungeons/custom_tag.asm`

## Verification
*   Build with `./run.sh`.
*   The user should confirm the crash is gone when entering the house/starting the game.
