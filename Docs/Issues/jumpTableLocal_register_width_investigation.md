# JumpTableLocal Register-Width Investigation

## Issue Summary

The hook at `$00878F` (`JumpTableLocal` + `$0E`) was flagged by z3dk oracle_analyzer as potentially unsafe due to 16-bit Y register. The concern was that `JumpTableLocal` ($008781) uses `PLY` which pops 1 byte when Y is 8-bit, but would cause stack underflow if Y is 16-bit (would pop 2 bytes).

## Investigation Findings

### Vanilla ALTTP Analysis

Examined the vanilla ALTTP disassembly (gigaleak source: `/Users/scawful/src/hobby/alttp-gigaleak/DISASM/jpdasm/bank_01.asm`) to determine register state at the hook site.

**Key Evidence:**

1. **Address $01889A** (`REP #$20`): Sets A to 16-bit mode
2. **Address $0188C9** (`.draw_next_torch`): Torch drawing loop begins
   - This is **14 bytes after** the `REP #$20` instruction
   - Loop continues until address $0188E1
3. **Address $0188E1** (`SEP #$30`): Exit point, sets A/X/Y to 8-bit

**Disassembly snippet:**
```asm
#_01889A: REP #$20    ; Set A to 16-bit

; ... (torch room detection code) ...

.draw_next_torch
#_0188C9: LDA.l $7EFB40,X    ; <-- Loop starts here (16-bit A)
#_0188CD: STA.b $08
#_0188CF: INX
#_0188D0: INX
#_0188D1: STX.b $BA
; ... (more torch drawing) ...
#_0188DF: BNE .draw_next_torch

.exit
#_0188E1: SEP #$30    ; Set A/X/Y to 8-bit
#_0188E3: RTL
```

**Important:** There is **NO** `REP #$10` or `REP #$30` between $01889A and $0188E1. The only register-width change is `REP #$20` (A only).

### Register State at Hook

**At address $00878F:**
- **A (Accumulator):** Could be 8-bit or 16-bit depending on caller
- **X (Index):** Could be 8-bit or 16-bit depending on caller
- **Y (Index):** Could be 8-bit or 16-bit depending on caller

**However:**
- The vanilla torch loop at $0188C9 operates in **16-bit A mode**
- X and Y register widths are **NOT explicitly set** in this routine
- They inherit whatever state was set by the caller

### z3dk Analyzer Findings

The z3dk analyzer correctly identified that:
1. Some callers might pass 16-bit Y to `JumpTableLocal`
2. `JumpTableLocal` uses `PLY` which pops 1 byte (8-bit) or 2 bytes (16-bit)
3. If Y is 16-bit, `PLY` pops 2 bytes, then `REP #$30` + `PLA` pops 2 more = 4 bytes total
4. But `PHY` only pushed 2 bytes (if Y was 16-bit), causing stack underflow

### Oracle Hook at $00878F

**Current hook:**
```asm
; $00878F (JumpTableLocal + $0E)
; @hook module=floor-puzzle, safe=true, entry-m=?, entry-x=?
org $00878F
    JSL FloorPuzzle_TorchCheck
    NOP
```

**Problem:** The hook is placed at an offset that might be reached with 16-bit Y, but the annotation claims `safe=true` without verifying register state.

## Conclusion

**The z3dk analyzer warning is VALID.**

The hook at $00878F (`JumpTableLocal` + $0E`) can be reached with 16-bit Y register. If this occurs:
1. Oracle code calls `JSL FloorPuzzle_TorchCheck`
2. `FloorPuzzle_TorchCheck` eventually calls `JumpTableLocal`
3. `JumpTableLocal` does `PLY` (pops 2 bytes if Y=16-bit)
4. Then `REP #$30` + `PLA` (pops 2 more bytes)
5. **Stack underflow** — pops 4 bytes total, but `PHY` only pushed 2

## Recommendations

1. **Add explicit register-width annotation** to the hook:
   ```asm
   ; @hook module=floor-puzzle, safe=false, entry-m=?, entry-x=?, entry-y=8, reason="JumpTableLocal requires 8-bit Y"
   ```

2. **Add register-width check** in `FloorPuzzle_TorchCheck`:
   ```asm
   FloorPuzzle_TorchCheck:
   {
       SEP #$10    ; Force X/Y to 8-bit before calling JumpTableLocal
       PHB : PHK : PLB
       ; ... rest of code ...
       PLB
       RTL
   }
   ```

3. **Document all callers** of `JumpTableLocal` to verify they set Y=8-bit:
   - `FloorPuzzle_TorchCheck` (Dungeons/floor_puzzle.asm)
   - Any other custom code that calls $008781

4. **Add z3dk analyzer rule** to enforce 8-bit Y at `JumpTableLocal` entry points

## Related Files

- Vanilla disassembly: `/Users/scawful/src/hobby/alttp-gigaleak/DISASM/jpdasm/bank_01.asm`
- Oracle hook: `Dungeons/floor_puzzle.asm` (line with `JSL FloorPuzzle_TorchCheck`)
- z3dk analyzer: `~/src/hobby/z3dk/scripts/oracle_analyzer.py`

## Status

- [x] Vanilla ALTTP register state verified
- [x] z3dk analyzer finding confirmed valid
- [ ] Hook annotation updated with correct entry-y requirement
- [ ] Fix implemented (SEP #$10 added to FloorPuzzle_TorchCheck)
- [ ] z3dk analyzer rule added for JumpTableLocal callers
