# Oracle ABI Standard (Long Entry)

## Goal
Reduce false positives in ABI analysis and enforce a consistent contract for
long-entry routines that normalize M/X and preserve caller state.

## Naming convention
If a routine name includes:
- `*_Long`
- `*_LongEntry`
- `*FullLongEntry`

…it is treated as a **long-entry routine**. Tooling assumes the callee is
responsible for setting/normalizing M/X and preserving caller state.

## Inline annotations (optional)
Add a comment near the hook or label:
- `; @abi long_entry` → mark as long-entry
- `; @abi m8x8` / `; @abi m16x8` / `; @abi m8x16` / `; @abi m16x16` → expected entry M/X
- `; @no_return` → mark non-returning hook (skip ABI exit checks)

These are parsed by `scripts/generate_hooks_json.py` and emitted into `hooks.json`
as `abi_class`, `expected_m`, `expected_x`, or `skip_abi`.

## Required prologue/epilogue
Use the macros below to make the contract explicit and Asar-compatible:

```
OOS_LongEntry
  ; (optional) REP/SEP as needed inside the routine
...
OOS_LongExit
```

## Tooling integration
- `hooks.json` entries now include `abi_class: "long_entry"` when the name
  matches the pattern above.
- `z3dk` treats `long_entry` targets as self-normalizing, and will **skip**
  caller M/X mismatch warnings for those targets.

## Notes
- Long-entry routines should use `SEP/REP` internally as needed.
- `OOS_LongEntry`/`OOS_LongExit` preserve P and DB so caller state is restored.
- This standard is backwards-compatible with Asar (pure macro expansion).

## Patch Hooks: "Width-Transparent" Contract (Non-Long-Entry)
Not all hooks jump to a long-entry routine. Some hooks replace 2-8 bytes of
vanilla code and then return into vanilla at a specific address that expects a
specific `P` state (especially M/X width).

Rules:
- If you patch a callsite that is inside a known-width region (e.g. after `SEP #$20`,
  or before `CPX.b` / `CPY.b` / `CMP.b`), your hook must **exit** with that same
  width expectation.
- For "inline" patch hooks that resume vanilla immediately, prefer being
  *width-transparent*: `PHP` on entry, do your temporary `SEP/REP` work, `PLP`
  before returning, and if needed, explicitly re-assert the required width
  (`SEP #$30` or `REP #$30`) that vanilla expects at the resume address.

Practical guideline:
- If the next vanilla instruction uses an 8-bit immediate compare (`CPX.b`, `CPY.b`,
  `CMP.b`), ensure you return with M/X=8 to avoid immediate-length desync.
