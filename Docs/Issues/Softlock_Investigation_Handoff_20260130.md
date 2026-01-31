# Softlock Investigation Handoff — 2026-01-30

## Status: UNRESOLVED — Static analysis exhausted, dynamic capture needed

---

## Two Distinct Crashes

| ID | Trigger | Observable |
|----|---------|------------|
| **State 1** | Overworld gameplay (seconds in) | Black screen, SP leaves $01xx |
| **State 2** | Load save slot 2 → dungeon entry | Freeze on room load, SP=$0D06 DBR=$0x50 |

Both share the same terminal mechanism: SP corruption → NMI handler loads bad SP from $7E1F0A via TCS → PHK/PLB pulls garbage → permanent black screen.

## What Has Been Ruled Out

| Hypothesis | Result | Session |
|------------|--------|---------|
| HUD_ClockDisplay ($068361) | NOT root cause. PHP/PLP protected, subroutines clean. Patching to vanilla did NOT fix crash. | 2026-01-30 |
| ColorBgFix PHA/PLA width mismatch | Defensive fix applied (REP #$20 before PHA). Did NOT fix State 1 or State 2. Left as correctness hardening. | 2026-01-30 |
| NMI hooks (Player2JoypadReturn, NMI_UpdateChr_Bg2HalfAndAnimated) | All examined hooks are stack-balanced. | 2026-01-30 |
| Menu_Exit REP #$20 leak | Caught by Menu_Entry's SEP #$20 — not the cause. | 2026-01-30 |
| $7E1F0A MEM_WATCH | Showed ZERO writes — bank 00 mirror addressing ($001F0A) not captured by $7E1F0A watch. | 2026-01-29 |
| TCS breakpoint at $0082CE | Mesen2 crashed during monitoring — inconclusive. | 2026-01-29 |

## Key Evidence

- **SP polling capture (State 2):** Corruption first seen at frame 35, PC=0x0085FE.
- **Stack blame (State 2):** 64 writes from bank $02 module loading, last at PC=$0287E9 (PHA at SP=$01FC).
- **Static analyzer:** 401 width-dependent stack imbalances, 422 errors total. Most are in vanilla ROM bank 06 sprite routines — Oracle doesn't assemble these, but does call into them.
- **$06ACF1:** PLA byte exists in patched ROM but NOT in vanilla USDASM. Concrete Oracle-introduced regression candidate.
- **November 22 commits:** 3 large AI-assisted rewrites (menu, time system, ZSOW v3 port) — most likely introduction window.

## Recommended Next Steps (Priority Order)

### 1. Module Isolation (Fastest path to narrowing)

Use `Config/module_flags.asm` to disable modules one at a time, rebuild, test both states:

```
Priority: SPRITES → MASKS → OVERWORLD → MENU → ITEMS → MUSIC
```

If disabling SPRITES eliminates the crash, root cause is in sprite code. Then re-enable sprite files individually to narrow further.

```bash
# Example: disable sprites
python3 scripts/set_module_flags.py --disable SPRITES
SKIP_TESTS=1 ./scripts/build_rom.sh 168
# Test against save states 1 and 2
```

### 2. MEM_WATCH on $001F0A (Bank 00 Mirror)

Previous watch on $7E1F0A missed writes because NMI uses bank 00 addressing. Set watch on $001F0A instead:

```bash
python3 scripts/mesen2_client.py mem-watch --addr 0x001F0A --size 2
```

### 3. Stack Blame on $01FC-$01FE

The last known good SP write was at $01FC. Set write breakpoints on the stack page boundary to catch the corruption moment:

```bash
python3 scripts/mesen2_client.py breakpoint --type write --addr 0x01FC --size 4
```

### 4. Investigate $06ACF1

The PLA at $06ACF1 exists in the patched ROM but not vanilla. This is a concrete byte-level difference in the sprite crash chain:

```bash
python3 scripts/mesen2_client.py disassemble --addr 0x06ACD0 --count 40
```

Identify which Oracle patch relocated code to this address.

### 5. Git Bisect Against November 22

If module isolation doesn't narrow it:

```bash
git bisect start HEAD <commit-before-nov-22>
git bisect run python3 scripts/bisect_softlock.py
```

Three suspect commits: `8b23049` (menu), `93bd42b` (time system), `d41dcda` (ZSOW v3 port).

## Files to Read First

| File | Why |
|------|-----|
| `Docs/Issues/Opus_Softlock_Analysis_20260130.md` | Full codebase review and architecture analysis |
| `Docs/Issues/Width_Imbalance_Fix_Spec.md` | The 4 highest-impact width mismatches (items 1-4) |
| `Docs/Issues/Mesen2_Breakpoints_and_State2_Freeze_Handoff.md` | State 2 breakpoint results, SP polling data |
| `Docs/Issues/OverworldSoftlock_RootCause.md` | Original root cause analysis |
| `Config/module_flags.asm` | Module isolation flags (all currently enabled) |
| `Overworld/time_system.asm:516` | ColorBgFix with applied defensive fix |

## Save States for Repro

- **State 1 (OW):** `/Users/scawful/Documents/Mesen2/SaveStates/oos168x_1.mss`
- **State 2 (UW):** `/Users/scawful/Documents/Mesen2/SaveStates/oos168x_2.mss`

## Applied But Ineffective Fixes (Keep in ROM)

1. **ColorBgFix REP #$20** (`time_system.asm:518-526`) — Forces M=16 before PHA. Correctness hardening, not a fix.

## Architecture Notes

- ZSCustomOverworld.asm (171KB) operates in **global scope** while everything else is namespaced as `Oracle`. P-register contracts at these boundaries are fragile.
- NMI uses a polyhedral stack swap: TSC/TAX saves main SP, LDA $1F0A/TCS loads NMI SP, STX $1F0A saves main SP for later restore. Corruption of $1F0A = corrupted main SP on NMI exit.
- Sprite dispatch (`sprite_new_table.asm`) correctly forces SEP #$30 before dispatch, but individual sprite routines may have internal width mismatches.
