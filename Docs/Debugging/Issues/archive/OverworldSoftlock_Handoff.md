# Overworld / Dungeon Black Screen Softlock — Handoff
Date: 2026-01-28
Updated: 2026-01-30 (session 3 — static fixes exhausted, dynamic capture required)
Owner (next): whoever picks up with mesen2-oos agent tooling

## Status (short)

- **Status (2026-01-30):** Softlock still reproducible after 5 rounds of static-analysis-guided fixes. Root cause **NOT yet identified**. All static leads have been investigated and either fixed or eliminated. **Module isolation (feature disabling) is the next step.**
- Two separate bugs: **State 1** = overworld softlock, **State 2** = file-load dungeon freeze.
- Crash chain mechanism confirmed: SP corrupts → NMI reads wrong DBR → dispatch jumps to WRAM → black screen.
- The missing piece: **what instruction corrupts SP?** No static analysis approach has found it.

## What was tried and did NOT fix the bugs

### Session 5 fixes (2026-01-30) — PHP/PLP hardening, NONE RESOLVED EITHER BUG

| Fix | File | What it fixed | Why it didn't help |
|-----|------|---------------|-------------------|
| PHP/PLP wrapper on `HUD_Update` entry + `.ignore_health` alternate entry | `Menu/menu_hud.asm:39,93,189` | HUD_Update was leaking P state to vanilla caller every frame. Both entry points (full + skip-hearts) now save/restore P. | Real ABI bug but HUD_Update runs in bank $2E, not in the bank $06 crash chain. The P leak likely didn't propagate to sprite dispatch. |
| PHP/PLP wrapper on `SpriteActiveExp_MainLong` and `Sprite_PrepExp_Long` | `Core/sprite_new_table.asm:16,20,46,50` | All custom Oracle sprite dispatches now preserve caller's P register. Prevents any sprite from leaking X=8-bit back to vanilla sprite loop. | Reduced width imbalances from 413 → 401. Correct defensive fix but did NOT resolve the observed crashes — the P leak path may not be the crash trigger. |

**Key insight:** These are long-standing ABI patterns. The code worked until recently, so the root cause is a *recent change*, not a fundamental design flaw. **Module isolation (disabling features) is the correct next strategy.**

### Session 3 fixes (2026-01-30) — ALL TESTED, NONE RESOLVED EITHER BUG

| Fix | File | What it fixed | Why it didn't help |
|-----|------|---------------|-------------------|
| `SEP #$30` → `SEP #$20` in both sprite dispatch tables | `Core/sprite_new_table.asm:37,67` | Prevented X=8-bit leak to vanilla sprite loop | Every custom sprite dispatch was setting X=8-bit, which should have caused JumpTableLocal PLY to pop 1 byte instead of 2. **Fix is correct but did not resolve the observed crashes.** Either the crash path doesn't go through JumpTableLocal, or X gets restored elsewhere before PLY. |
| PHP/REP #$30 wrapper around `JSL $00FC62` | `Overworld/time_system.asm:122-126` | Sprite_LoadGraphicsProperties was called with M=8/X=8 instead of M=16/X=16 | Real bug (every other caller wraps this), but runs on overworld only — not in dungeon load path. Didn't fix either crash. |
| `JMP .continue` after each `.max_N` PLA in Menu_SongMenu | `Menu/menu.asm:764-766` | PHA/PLA fall-through stack corruption in song menu | Only triggers when navigating the song menu. Not on the crash path for either bug. |

### Earlier fixes (sessions 1-2) — also insufficient

| Fix | Status | Notes |
|-----|--------|-------|
| `Oracle_ColorBgFix` PHP/PLP wrapper | Partial mitigation only | Corruption source is upstream |
| `$06:8361` patch to vanilla JSL | Did NOT fix | PC still lands at $1D66CE |
| `SPC_Upload_WithTimeout` | Reverted | Stack balance was correct |
| `$008034` main loop raw bytes | Cleared | Matches vanilla ALTTP exactly |

## What we know

### Confirmed facts
1. SP jumps from `$01xx` to `$0Dxx` page at some point during gameplay
2. NMI handler at `$0082CE` does `LDA $1F0A : TCS` — if `$7E1F0A` is corrupt, SP goes wrong
3. Oracle code has **zero TCS/TXS instructions** — corruption must come from:
   - (a) Vanilla TCS reached with corrupt A (P-state leak from Oracle hook), OR
   - (b) Stack overflow from unbalanced push/pull, OR
   - (c) Direct write to stack page memory
4. `JumpTableLocal` ($008781) X=8-bit theory was plausible but **fix did not resolve the crash**
5. HUD_ClockDisplay at `$06:8361` is in the P register chain (P=0x31, X=8-bit) but fixing its callees didn't help

### Static analysis summary (informational, not actionable)
- 413 width-dependent stack imbalances detected
- 181 JSL M/X flag mismatches
- 98 hook ABI issues
- These are real issues but none has been confirmed as the crash cause

### Eliminated suspects

| Suspect | Status | Reason |
|---------|--------|--------|
| `sprite_new_table.asm` SEP #$30 | Fixed, did NOT resolve crash | X=8-bit leak was real but not the crash path |
| `TimeSystem_CheckCanRun` JSL $00FC62 | Fixed, did NOT resolve crash | M/X mismatch was real but not fatal |
| `Menu_SongMenu` PHA/PLA fall-through | Fixed, did NOT resolve crash | Stack corruption only in song menu navigation |
| `$008034` main loop patch | Cleared | Vanilla ALTTP bytes, since reverted |
| `SPC_Upload_WithTimeout` | Cleared | Stack balanced, since reverted |
| `oos168_test2.sfc` data corruption | Cleared | Only 1 intentional byte diff in bank $28 |
| `CheckIfNight` P register flow | Cleared | 65816 TAY zeroes high byte correctly |
| `Oracle_ColorBgFix` | Partial mitigation | Not root cause; corruption is upstream |

## What to do next — DYNAMIC CAPTURE (mandatory)

Static analysis has been exhausted. The next agent **must** use runtime debugging to catch SP corruption in the act.

### Strategy 1: Automated repro script (recommended)
```bash
cd ~/src/hobby/oracle-of-secrets
python3 scripts/repro_stack_corruption.py --strategy auto --output /tmp/blame_report.json
```
Supports 4 strategies: `sp_range` (SP >= 0x0200), `tcs` (breakpoint at NMI TCS sites), `breakpoint` (crash site), `polling` (frame-by-frame SP check). The `auto` mode tries them in order.

### Strategy 2: Manual MEM_WATCH + BLAME
```bash
# Watch the stack pointer save location ($7E1F0A) for writes
python3 scripts/mesen2_client.py mem-watch add 0x7E1F0A --size 2 --depth 500
python3 scripts/mesen2_client.py load 1
# Play until crash, then:
python3 scripts/mesen2_client.py mem-blame --addr 0x7E1F0A
```

### Strategy 3: SP polling (guaranteed but slow)
```bash
python3 scripts/repro_stack_corruption.py --strategy polling --frames 600 --output /tmp/blame_report.json
```
Advances 1 frame at a time, reads CPU state, checks if SP left `$01xx` page. Guaranteed to catch the corruption frame.

### Strategy 4: Conditional breakpoint on SP range
Use the repro script with `--strategy sp_range` (or `breakpoint`) for SP-range or crash-site breakpoints; or load state and run manually:
```bash
python3 scripts/mesen2_client.py load 1
python3 scripts/mesen2_client.py run --frames 600 --pause-after false
# Then check CPU/SP: python3 scripts/mesen2_client.py cpu
```
For full trace capture on hit, use `repro_stack_corruption.py --strategy auto`.

### After capturing the blame PC:
1. Resolve symbol: `z3ed rom-resolve-address --address=<PC> --rom=Roms/oos168x.sfc`
2. Map call chain: `python3 ~/src/hobby/yaze/scripts/ai/code_graph.py callers <routine>`
3. Cross-reference with z3dk: `python3 ~/src/hobby/z3dk/scripts/oracle_analyzer.py --rom Roms/oos168x.sfc --check-hooks --find-mx`
4. Apply fix and verify with regression test

## Alternative investigation angles

If dynamic capture proves difficult, consider these approaches:

### 1. Binary bisect via git
The instability appeared between Nov 22 and Jan 26. Bisect the commits:
```bash
git bisect start HEAD <last-known-good-commit>
# Build each candidate, test in emulator
./scripts/build_rom.sh 168
```
Key commits to test: `8b23049` (menu rewrite), `93bd42b` (time system), `d41dcda` (ZSOW v3 port).

### 2. Diff the assembled ROM against a known-good version
If an older ROM exists that doesn't crash, binary diff the bank $06 area (sprite/HUD hooks) to find what changed.

### 3. Watch $7E1F0A directly
Instead of watching the stack, watch the NMI SP save location `$7E1F0A`. Only vanilla NMI code writes here. If it becomes corrupt, something is overwriting WRAM directly — not a stack push/pull issue.

### 4. Audit all Oracle hooks that return to vanilla code
Focus on hooks where Oracle code runs and then returns control to vanilla. If any hook exits without restoring P register (M/X flags), the vanilla code downstream may misinterpret register widths. Key hooks:
- `$06:8361` (HUD_ClockDisplay) — every frame
- `$06:FFF8` (NewMainSprFunction) — every sprite tick
- `$06:8EB9` (NewSprPrepFunction) — sprite init
- All hooks in `hooks.json` (1000+ entries)

### 5. Narrow down which bug to focus on
State 1 (overworld) and State 2 (dungeon load) may have **different root causes**. Pick one and solve it completely before attempting the other.

## Tooling reference

| Tool | Location | Purpose |
|------|----------|---------|
| `repro_stack_corruption.py` | `scripts/` | Automated repro with 4 strategies |
| `mesen2_client.py` | `scripts/` | Socket API wrapper |
| `oracle_analyzer.py` | `z3dk/scripts/` | Static analysis (hooks, M/X, width imbalances) |
| `oracle_debugger/` | `scripts/oracle_debugger/` | Unified debugging orchestrator |
| `z3ed` | `yaze/build_ai/bin/Debug/` | Symbol resolution |
| `sentinel.py` | `yaze/scripts/ai/` | Softlock watchdog |
| `crash_dump.py` | `yaze/scripts/ai/` | Post-mortem analysis |
| `code_graph.py` | `yaze/scripts/ai/` | Call graph analysis |

## Required setup
- Build from `Roms/oos168_test2.sfc` → load `Roms/oos168x.sfc` in Mesen2 fork
- Use isolated Mesen2 home + socket (`MESEN2_SOCKET_PATH`)
- Rebuild mesen2-oos after pulling: `cd ~/src/hobby/mesen2-oos && make`
- Save states: slot 1 = overworld softlock, slot 2 = dungeon freeze

## Key files

| File | Role |
|------|------|
| `Docs/Debugging/Issues/OverworldSoftlock_RootCause.md` | Detailed mechanism + static findings |
| `Docs/Debugging/Issues/OverworldSoftlock_ActionPlan.md` | Original action plan |
| `Docs/Debugging/Issues/Menu_Regression_Debugging_Plan.md` | Menu bug categories (separate) |
| `~/.context/scratchpad/overworld_softlock_evidence_20260128.md` | Evidence ledger |
| `scripts/repro_stack_corruption.py` | Dynamic repro script |
| `z3dk/scripts/oracle_analyzer.py` | Static analyzer |
| `hooks.json` | Hook registry (1000+ entries) |
| `tests/regression/stack_corruption.json` | Regression test definition |

## Updates (2026-01-30)
- Custom sprite dispatch now forces X/Y to 8-bit before jumping into sprite routines
  (`Core/sprite_new_table.asm`) to match JumpTableLocal stack math expectations.
- Hook expectations for JumpTableLocal updated to X=8 in `scripts/generate_hooks_json.py`
  and `z3dk/scripts/oracle_analyzer.py` to reduce false positives and align with vanilla.
- Reminder: do not wrap `JSL JumpTableLocal` with `PHP/PLP` — it shifts the stack and
  breaks the return-address pointer math.
