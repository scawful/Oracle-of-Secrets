# Overworld / Dungeon Black Screen Softlock — Root Cause
Date: 2026-01-29
Updated: 2026-01-30
Status: **INVESTIGATING** — static analysis leads exhausted; dynamic capture required
Correction (2026-01-30): Save state 1 = overworld softlock; save state 2 = file-load dungeon freeze (tracked separately).

## Root cause first (do not paper over)

**Do not** add defensive REP #$30 (or similar) at every JumpTableLocal call site. That hides the symptom and makes the real bug harder to find. The goal is to identify the **single instruction or hook** that corrupts P (leaving X=8-bit) or SP (or writes `$7E1F0A`), then fix that one place. Use **dynamic capture** (repro script with write watch on `$7E1F0A`, SP polling, or module isolation) to get the exact PC; then fix the root cause there. For alternative strategies (fix JumpTableLocal once, TCS conditional breakpoint, git bisect, NMI validation), see [OverworldSoftlock_Investigation_Alternatives.md](OverworldSoftlock_Investigation_Alternatives.md). For concrete, hands-on options (play-and-log, one fix, golden path, on-screen debug, savestate checklist, community ask, compare builds, feature freeze), see [OverworldSoftlock_LessCerebralOptions.md](OverworldSoftlock_LessCerebralOptions.md).

## Session 3 Results (2026-01-30): Static Fixes Did NOT Resolve Crashes

Three bugs were found and fixed via static analysis. All are real bugs, but **none resolved the overworld softlock or dungeon freeze**:

| # | Fix | File | Lines | Result |
|---|-----|------|-------|--------|
| 1 | `SEP #$30` → `SEP #$20` in sprite dispatch | `Core/sprite_new_table.asm` | 37, 67 | Built + tested, crash persists |
| 2 | PHP/REP #$30 wrapper for `JSL $00FC62` | `Overworld/time_system.asm` | 122-126 | Built + tested, crash persists |
| 3 | `JMP .continue` after `.max_N` PLA cases | `Menu/menu.asm` | 764-766 | Built + tested, crash persists |

**Conclusion:** The SP corruption source is NOT any of the statically-identified M/X mismatches or stack imbalances examined so far. The root cause requires **dynamic runtime capture** — watching SP or `$7E1F0A` at the moment of corruption to identify the exact instruction.

**Recommended next step:** See [OverworldSoftlock_Plan.md](OverworldSoftlock_Plan.md) for paths (hands-on, dynamic capture, module isolation, bisect). For capture commands: run `repro_stack_corruption.py --strategy polling` or see `OverworldSoftlock_Handoff.md`.

## Mechanism (confirmed)

JumpTableLocal at `$00:8781` uses PLY to pull the 2-byte return address (Y-low, Y-high)
from the JSL return address on the stack. When X/Y index registers are in **8-bit mode**
(P bit 4 set), PLY pops only **1 byte** instead of 2. This leaves the stack misaligned
by 1 byte, and the subsequent RTL returns to a corrupted address.

**Observed corruption chain:**
```
JSL ret=0684F3 to=008781  P=B0 (X=8-bit)
  → PLY pops 1 byte instead of 2
  → RTL returns to corrupted address ($83:A607 → $83:A66D)
  → JSL $1D66CC (WRAM mirror, invalid code)
  → SP jumps to $2727 via TCS with A=2727
  → Main loop never reached, NMI repeats → black screen
```

## Static Analysis Findings (2026-01-30)

### Width-Dependent Stack Imbalance Analysis

New `find_width_dependent_stack_imbalance()` function in `oracle_analyzer.py` detected
**413 width-dependent stack imbalances** where push/pull pairs operate at different
register widths across call paths.

**Highest-impact patterns:**

| Push Address | Pull Address | Push Width | Pull Width | Flag | Routines Affected |
|-------------|-------------|-----------|-----------|------|-------------------|
| `$06ECC8` (`Oracle_Ancilla_CheckDamageToSprite+17`) | `$06ACF1` (`Oracle_Sprite_CheckIfLifted+741`) | M=16-bit (2B) | M=8-bit (1B) | M | 8 sprite routines |
| `$043519` (`Oracle_RomToPaletteBuffer+79253`) | `$0401C8` (`Oracle_RomToPaletteBuffer+66116`) | X=16-bit (2B) | X=8-bit (1B) | X | 4 routines |
| `$1BC1C3` (`Overworld_Entrance+1487`) | `$068142`/`$068189` (`Oracle_ApplyRumbleToSprites`) | M=16-bit (2B) | M=8-bit (1B) | M | 3+ routines |
| `$1AE24A` / `$1AE488` | Twinrova Draw/Check | M=8→16 (1→2B) | M=16-bit | M | Oracle_Sprite_Twinrova (4) |

**Bank 06 sprite routines with width imbalances** (most likely crash chain contributors):
- `Oracle_Sprite_TransmuteToBomb` — 3 PHA(16-bit)/PLA(8-bit) imbalances
- `Oracle_Sprite_CheckIfLifted` — 2 imbalances
- `Oracle_Sprite_CheckDamageToPlayer_same_layer` — 1 imbalance
- `Oracle_Sprite_BumpDamageGroups` — 1 imbalance
- `Oracle_ApplyRumbleToSprites` — 2 PHA(16-bit)/PLA(8-bit) imbalances
- `Oracle_SpriteDraw_Locksmith` — 1 imbalance
- `Oracle_ForcePrizeDrop_long` — 2 imbalances

### M/X Mismatch Analysis

**181 JSL M/X flag mismatches** found between callers and callees. Key patterns:
- Multiple callers invoke `Oracle_Overworld_DrawMap16_Persist` with M=8/X=8, but the routine expects M=16/X=16 (6 call sites from `$3489D5`-`$348A07`)
- `Oracle_UpdateGbcPalette` called with M=8/X=8 from 3+ sites, expects M=16/X=16
- `Oracle_Sparkle_PrepOAMFromRadial` called with M=8/X=8, expects M=16/X=16
- `Oracle_HUD_Update` called with M=16, expects M=8

### Hook ABI Issues

**98 hook ABI issues** including:
- `HUD_Update` exit: 56 unbalanced PHP/PLP, 4 unbalanced PHD/PLD
- `HUD_UpdateItemBox` exit: 60 unbalanced PHP/PLP, 6 unbalanced PHD/PLD
- `ActivateSubScreen` exit: PHB/PLB imbalance (3 pushes vs 6 pulls)

### TCS (Transfer to SP) Sites

Only **2 genuine TCS instructions** exist as code (both in NMI handler):
- `$0082CE`: `TSC:TAX:LDA $1F0A:TCS` — SP swap to NMI stack
- `$008329`: `TSC:TAX:LDA $1F0A:TCS` — SP restore from NMI stack

Both load SP from `$7E1F0A`. If `$7E1F0A` is corrupted, SP will be wrong.
All other 0x1B bytes in the ROM are data, not code.

The reset TCS at `$008026` (`LDA #$01FF : TCS`) is safe.

## Exact PC that corrupts the stack

**Update 2026-01-30 (file load → Link's house freeze):**

- Break at `JumpTableLocal` (`$00:8781`) with `P=0xB0` (X=8-bit), `SP=0x01EB`, `DBR=0x06`.
- Stack return address shows caller `0x0684F0` (`JSL JumpTableLocal`) with return `0x0684F3`.
- This confirms `JumpTableLocal` is invoked with X=8-bit, which is **expected** for its stack math.

**Conclusion:** This capture does **not** identify the SP corruption instruction. Root cause remains: find the instruction that sends SP into the `0x0Dxx` page.

**Still to isolate:** which Oracle routine leaves SP corrupted. P-log shows recent X-flag set events at:
- `$01:D825` (`SEP #$30`, WarpTag_Return path)
- `$0D:AA18` / `$0D:A857` (`LinkOAM_DrawShadow` paths)
- `$00:F423` (`PaletteFilter_StartBlindingWhite` path)

## Next Steps

### Dynamic Capture (Track B)

Updated `repro_stack_corruption.py` now supports 4 strategies:
1. **`sp_range`**: Conditional breakpoint `SP >= 0x0200` (best: catches moment of corruption)
2. **`tcs`**: Breakpoints at NMI TCS sites, reads `$7E1F0A` to check for corrupt SP source
3. **`breakpoint`**: Exec breakpoint at crash site `$83:A66D` (post-corruption)
4. **`polling`**: Frame-by-frame SP polling with trace capture (slowest but guaranteed)

Run with:
```bash
cd ~/src/hobby/oracle-of-secrets
python3 scripts/repro_stack_corruption.py --strategy auto --output /tmp/blame_report.json
```

Or force polling for guaranteed capture:
```bash
python3 scripts/repro_stack_corruption.py --strategy polling --frames 600 --output /tmp/blame_report.json
```

The script now captures TRACE (500 instructions) on hit and auto-analyzes the trace
to find the exact instruction where SP left the `$01xx` page.

### Prioritized Fix Candidates

Based on static analysis, these routines should be investigated first:

1. **`Oracle_Ancilla_CheckDamageToSprite`** (`$06ECC8`): PHA with M=16-bit, paired with PLA at M=8-bit in sprite routines — 14 occurrences across 8 routines
2. **`Overworld_Entrance`** (`$1BC1C3`): PHA with M=16-bit, paired with PLA at M=8-bit in `Oracle_ApplyRumbleToSprites`
3. **`Oracle_Sprite_DrawMultiple_quantity_preset`** (`$05DF7A`): PHX with X=16-bit, PLX at X=8-bit
4. **`Oracle_Link_Initialize`** (`$030CC8`): PHY with X=16-bit, PLY at X=8-bit

### Fix Pattern

For each identified routine, wrap with explicit width restore:
```asm
; At hook entry
PHP           ; Save P register (including M/X flags)
SEP #$30      ; Set known state (8-bit M/X) OR REP #$30 for 16-bit
; ... Oracle code ...
PLP           ; Restore caller's M/X flags
RTL
```

## Isolation test results

- Patching `$06:8361` to vanilla `JSL $09B06E` did **not** fix the issue (PC still lands at $1D66CE).
- ColorBgFix PHP/PLP is a **partial mitigation only**.
- The corruption source is upstream of both hooks.

## P register corruption chain

The X flag becomes 8-bit somewhere upstream of JumpTableLocal. Known observations:

| Address | Routine | P value | X flag |
|---------|---------|---------|--------|
| `$06:8361` | Oracle.HUD_ClockDisplay | `0x31` | 8-bit |
| `$06:84E2` | Sprite_ExecuteSingle | `0x30` | 8-bit |
| `$06:84F0` | JSL JumpTableLocal | `0xB0` | 8-bit |
| `$00:8781` | JumpTableLocal | `0xB0` | 8-bit |

## Static analysis integration

JumpTableLocal is registered in `hooks.json` with `expected_x: 16`. The build pipeline
runs `oracle_analyzer.py --check-hooks --find-mx --find-width-imbalance` and flags:
- Any JSL to $008781 where the caller has X=8-bit
- Width-dependent push/pull pairs (PHA/PLA, PHX/PLX, PHY/PLY) where M/X differs

New CLI flag: `--find-width-imbalance`

## Investigation Pivot (2026-01-30): AI-Assisted Code as Primary Suspect

The static analysis flagged generic width mismatches across the ROM, but the **actual instability
correlates with AI-agent-assisted commits from November 2025 – January 2026**. Three systems were
heavily modified during this window:

### Timeline of Suspect Commits

| Date | Commit | Description | Risk |
|------|--------|-------------|------|
| Nov 22 | `8b23049` | Fix menu crashes (Claude Code) — 2010-line rewrite | **HIGH** — Categories A-E regressions documented |
| Nov 22 | `93bd42b` | Refactor Time System — 1279-line rewrite | **HIGH** — Rewrote RunClock, TimeState struct |
| Nov 22 | `d41dcda` | Fix ZSOW Day/Night sprites — moved ZSOW include, added CheckIfNight | **MEDIUM** — Changed include order + sprite loading hook |
| Nov 22 | `ad2c00c` | Fix ColorSubEffect regression | Fixup for 93bd42b |
| Nov 22 | `2b504d9` | Fix Time System BG color tinting | Fixup for 93bd42b |
| Jan 24 | `93bd42b` related fixes | Additional Time System/ZSOW fixes | Cascade |
| Jan 26 | `d2dbf43` | Campaign: SPC timeout, main loop patch, sprite docs | **MEDIUM** — raw byte patch + SPC hook (since reverted) |

### Suspect 1: Time System Refactor (`93bd42b`)

`HUD_ClockDisplay` at `$06:8361` is **directly in the P register crash chain** (P=0x31, X=8-bit).
The Nov 22 refactor rewrote all 1279 lines of `time_system.asm`. Current code has PHP/PLP wrapper,
but the refactor changed all WRAM addresses from raw `$7EE0xx` to `TimeState.xxx` struct fields.

Key concern: `RunClock` calls multiple subroutines that do JSL to vanilla routines
(`$00FC62 Sprite_LoadGraphicsProperties`, `$09B06E Garnish_ExecuteUpperSlots_long`).
If any of these return with different M/X than expected, the PHP/PLP at HUD_ClockDisplay
entry/exit is the only protection.

### Suspect 2: Menu Refactor (`8b23049`)

This commit (explicitly AI-generated, "Generated with Claude Code") introduced **5 documented
regression categories**:
- **A**: P register mismatches (missing SEP #$30 after JSL/JSR)
- **B**: Stack corruption (missing PHB/PLB in Journal_CountUnlocked)
- **C**: VRAM upload index corruption ($0116/$0117 writes)
- **D**: Data table misalignment
- **E**: Signed/unsigned comparison bugs

See `Docs/Debugging/Issues/Menu_Regression_Debugging_Plan.md` for full analysis.

### Suspect 3: ZSCustomOverworld v3 Port

The v2→v3 migration (`d41dcda`) changed `LoadOverworldSprites_Interupt` from reading
`$7EF3C5` (SRAM game state) to calling `JSL Oracle_CheckIfNight`. Analysis shows
this call is **technically correct** (8-bit TAY zeroes high byte on 65816), but the
`CheckIfNight16Bit` variant is dead code (both hook sites commented out during port).

The ZSOW include was also moved from before the `namespace Oracle` block to after it.
This changes the assembly order which could affect label resolution and bank placement.

### Suspect 4: ROM Base Image

Build script prefers `oos168_test2.sfc` (ZScream v3 edited, Nov 16) over `oos168.sfc`.
ROM diff analysis shows:
- **Bank $28**: Only 1 byte different (intentional edit at `$28:8284`)
- **Banks $29-$2A**: Identical (clean)
- **Banks $3E-$3F**: ~970 tile data diffs (expected from ZScream editing)
- **Total**: 11,061 byte diffs across 2MB ROM

**Conclusion: No data corruption detected.** Differences are consistent with normal editing.

### Eliminated Suspects

| Suspect | Status | Reason |
|---------|--------|--------|
| `$008034` main loop raw bytes | **CLEAR** — matches vanilla ALTTP exactly | Bytes disassemble to standard NMI wait + debug block |
| `SPC_Upload_WithTimeout` | **CLEAR** — since reverted | Stack balance correct; PHP/PLP paired; removed from HEAD |
| `oos168_test2.sfc` data corruption | **CLEAR** | Only 1 byte diff in bank $28, consistent with intentional edit |
| `CheckIfNight` P register flow | **CLEAR** | 65816 TAY in 8-bit mode zeroes high byte; phaseOffset index is valid |

## References

- Plan (next steps): `Docs/Debugging/Issues/OverworldSoftlock_Plan.md`
- Action plan (historical): `Docs/Debugging/Issues/OverworldSoftlock_ActionPlan.md`
- Handoff: `Docs/Debugging/Issues/OverworldSoftlock_Handoff.md`
- Menu regression plan: `Docs/Debugging/Issues/Menu_Regression_Debugging_Plan.md`
- Evidence ledger: `~/.context/scratchpad/overworld_softlock_evidence_20260128.md`
- Regression test: `tests/regression/stack_corruption.json`
- Repro script: `scripts/repro_stack_corruption.py`
- Static analyzer: `~/src/hobby/z3dk/scripts/oracle_analyzer.py`
- Baseline analysis: `/tmp/oracle_analysis_baseline.json`
- Width imbalance report: `/tmp/width_imbalance_report.json`
