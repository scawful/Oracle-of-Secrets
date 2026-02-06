# JumpTableLocal Register-Width Contract

## Summary

`JumpTableLocal` (vanilla at `$008781`) requires **8-bit index registers (X/Y)** on entry (`X` flag set in `P`).

This is not a "nice to have". The routine uses `PLY` **before** it forces `REP #$30`, so the size of the `PLY`
depends on the incoming X/Y width. If X/Y are 16-bit, `PLY` pops 2 bytes and the stack math breaks.

This doc exists because register-width leaks into `$008781` are a common root cause for "black screen / jump into
garbage" failures. z3dk is correct to flag call sites that reach `$008781` with `X=16-bit`.

## Vanilla Disassembly (USDASM)

From `~/src/hobby/usdasm/bank_00.asm`:

```asm
JumpTableLocal:
#_008781: STY.b $03
#_008783: PLY
#_008784: STY.b $00
#_008786: REP #$30
#_00878D: PLA
#_00878E: STA.b $01
...
#_008799: JML.w [$0000]
```

Key point: `PLY` happens while X/Y width is still whatever the caller left it as.

## Failure Mode (What Goes Wrong)

If X/Y are 16-bit on entry:

- `STY.b $03` stores 2 bytes (clobbers `$03-$04`).
- `PLY` pops 2 bytes (but the dispatch sequence expects the routine to consume stack bytes in a very specific way).
- After `REP #$30`, `PLA` pops 2 more bytes.
- Net effect: stack becomes misaligned and the computed jump target is garbage, which typically manifests as a hard
  lock or black screen.

## Oracle Guidance

- Before any `JSL JumpTableLocal` where you cannot prove X/Y are already 8-bit, do `SEP #$10` first.
- Prefer fixing the *single* width leak that changed X/Y, rather than sprinkling defensive width changes everywhere.
- For runtime validation in Mesen2-OOS, you can set a conditional P breakpoint:
  - Break if X/Y are NOT 8-bit at `$008781`:
    - `python3 scripts/mesen2_client.py p-assert 0x008781 0x10 --mask 0x10`
