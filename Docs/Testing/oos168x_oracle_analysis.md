# Oracle Static Analysis Report: oos168x.sfc

**Date:** 2026-01-29
**ROM:** `Roms/oos168x.sfc`
**Tool:** Oracle ROM Analyzer (yaze-debugger)

## Summary

| Category | Count | Severity |
|----------|-------|----------|
| Width-dependent stack imbalances | 691 | Error |
| MX flag mismatches | 182 | Error |
| Hook ABI issues | 122 | Error |
| Hook entry violations | 24 | Error |
| Potential hangs | 0 | — |
| Color issues | 0 | — |
| Hook state drift | 0 | — |

**Total diagnostics:** 1,019 errors, 2 warnings

## Critical Findings

### 1. `Oracle_UseImplicitRegIndexedLocalJumpTable` X-flag Mismatch (24 violations)

Every hook entry violation involves the same routine. Call sites enter with **X=8-bit** but the hook expects **X=16-bit**.

**Affected call sites (sample):**

| Call Address | Stack Depth |
|-------------|-------------|
| `$1DFD6E` | 216 |
| `$1AF5B0` | 168 |
| `$0DC999` | 167 |
| `$05FC42` | 174 |
| `$05FCDC` | 186 |
| `$1EF092` | 174 |
| `$870C19` | 162 |
| `$1E8EC8` | 179 |
| `$07160D` | 203 |
| `$05DF1C` | 0 |
| `$05EAB0` | 6 |
| `$0694F6` | 19 |
| `$06BCB9` | 7 |
| `$0CC44B` | 11 |
| `$0DDD3C` | varies |

**Root cause:** These call sites are running in 8-bit index mode (`REP #$10` / `SEP #$10` mismatch). The jump table routine uses X as a 16-bit index — if X is 8-bit, the high byte is zero and the table lookup reads the wrong entry, causing unpredictable branching.

**Fix pattern:** Ensure all call sites issue `REP #$10` before calling the jump table hook, or add a `REP #$10` guard at the hook entry point itself.

### 2. Width-Dependent Stack Imbalances (691 errors)

PHA/PLA and PHX/PLX pairs where the processor width flag differs between push and pull, causing 1-byte stack shifts.

**Examples:**

| Routine | Push Address | Pull Address | Flag | Push Width | Pull Width |
|---------|-------------|-------------|------|------------|------------|
| `$1DBA41` | `$05C22A` | `$1DBA86` | M | 8-bit | 16-bit |
| `$127035` | `$05CA36` | `$049951` | X | 8-bit | 16-bit |
| `$07D607` | `$07D5CD` | `$07D631` | M | 8-bit | 16-bit |

**Impact:** Each mismatch shifts the stack by 1 byte. On return (RTS/RTL), the CPU pops a corrupted return address, causing crashes or silent execution of wrong code.

**Note:** Many of these may be intentional (e.g., pushing 8-bit, pulling 16-bit to compose a value). The high count (691) suggests the analyzer is flagging cross-bank call chains where the width context changes legitimately. Manual triage recommended for routines near known crash sites.

### 3. Hook ABI Issues (122 errors)

Hooks called with unexpected accumulator/index register widths or stack depths. Subset of the broader MX mismatch category, specifically at Oracle hook boundaries.

### 4. Dynamic TCS Warnings (2 warnings)

Two instances of `TCS` (Transfer A to Stack Pointer) loading SP from RAM address `$1F0A`:
- At `$0082CE` (M=16, X=16, stk=261)
- At `$008329` (M=16, X=16, stk=191)

**Risk:** If `$1F0A` is corrupted, the stack pointer moves to an arbitrary location, causing immediate crash. These appear to be the game's stack reinitialization points (likely NMI or reset handler).

## Triage Priorities

### P0 — Likely Crash Causes
1. **Jump table X-flag mismatch**: 24 sites calling `Oracle_UseImplicitRegIndexedLocalJumpTable` with wrong index width. Any of these can cause an incorrect branch leading to a hang or crash.
2. **Stack imbalances near transition code**: Width mismatches in bank `$05`-`$07` routines (overworld/dungeon transition code) are the most likely source of black-screen bugs.

### P1 — Stability Risks
3. **Hook ABI violations**: 122 cases where Oracle hooks receive unexpected register state. May cause subtle data corruption even if they don't crash immediately.
4. **Dynamic TCS at `$1F0A`**: Verify this RAM location isn't written by Oracle code inadvertently.

### P2 — Audit
5. **691 stack imbalances**: Bulk triage needed. Filter by routines involved in known bug areas first. Many may be false positives from intentional width-switching patterns.

## Recommended Next Steps

1. **Instrument the jump table hook** with a `REP #$10` guard and re-test
2. **Cross-reference P0 addresses** with known crash savestates to identify which violations are actively triggering
3. **Run Poltergeist/Meadow analysis** on specific entry points (e.g., overworld transitions, dungeon loads) for deeper control-flow tracing
4. **Manual audit** of stack imbalances in banks `$05`-`$07` where transition logic lives
