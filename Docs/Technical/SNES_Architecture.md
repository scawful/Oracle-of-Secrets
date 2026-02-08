# SNES 65816 Processor Basics

**Last Verified:** UNKNOWN (needs audit)
**Primary Sources:** Mixed (ROM/disassembly/runtime/sheets)
**Confidence:** UNKNOWN (needs audit)

## Verification
| Area | Evidence | Last Verified | Notes |
| --- | --- | --- | --- |
| Document | Needs audit | UNKNOWN | Added verification framework |


## 1. Architecture Overview

The 65816 is an 8/16-bit microprocessor used in the Super Nintendo Entertainment System (SNES). It operates in two modes: emulation mode (6502-compatible, 8-bit) and native mode (65816, 16-bit). The SNES typically runs in native mode.

## 2. Key Registers

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

## 3. Processor Status Register (P) Manipulation

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

See `Docs/Debugging/Guides/Troubleshooting.md` Section 3 for comprehensive processor state troubleshooting.

## 4. Memory Mapping

- The SNES has a 24-bit address space, allowing access to up to 16MB of ROM/RAM.
- **Banks:** Memory is organized into 256 banks of 64KB each.
- **Direct Page (Bank 00):** The first 256 bytes of bank 00 (`$0000-$00FF`) are special and can be accessed quickly using direct page addressing (when D=0).
- **WRAM (Work RAM):** Located in banks $7E-$7F. This is where most game variables and temporary data are stored.
- **SRAM (Save RAM):** Typically located in banks $70-$7D, used for saving game progress.
