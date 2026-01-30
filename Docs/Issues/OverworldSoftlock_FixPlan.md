# Overworld / Dungeon Black Screen Softlock — Fix Plan
Date: 2026-01-30
Updated: 2026-01-30 (session 5 — Phase 1 complete, no resolution; shifting to module isolation)
Status: **ACTIVE** — Phase 1 exhausted, **Module Isolation** is next step

## Summary

After 5 sessions of static analysis and targeted fixes, the softlock remains reproducible.
The crash mechanism is SP corruption from `$01xx` → `$0Dxx`, triggered by a width-mismatched
PLY/PLA that causes RTL to jump to garbage code, which hits TCS with bad A.

**Key insight (session 5):** These are long-standing ABI patterns. The code worked until recently,
so the root cause is a **recent change**, not a fundamental design flaw. Static analysis fixes
(PHP/PLP hardening) are correct defensive improvements but do not address the regression.
**Module isolation** — disabling features to identify the guilty module — is the correct next step.

See `Docs/General/DevelopmentGuidelines.md` Section 2.6 for module isolation infrastructure.

**Eliminated vector:** Direct write to `$7E1F0A` (POLYSTACKL) — write watch showed no
rogue writes during repro (per `RootCause_Investigation_Handoff.md:88`).

**Remaining vectors:**
- **(a)** Vanilla TCS reached with corrupt A (P-state leak from Oracle hook)
- **(b)** Stack overflow/underflow from unbalanced push/pull

**Critical observation:** Sessions 1-3 fixed low-impact bugs. The highest-impact width
mismatches identified by `oracle_analyzer.py` were **never fixed**. This plan addresses
them systematically.

---

## Phase 1: Fix Unfixed High-Impact Width Mismatches

### Context

The crash chain runs through bank 06:
```
$06:8361 (HUD_ClockDisplay, P=0x31 X=8-bit)
  → $06:84E2 (Sprite_ExecuteSingle, P=0x30 X=8-bit)
  → $06:84F0 (JSL JumpTableLocal, P=0xB0 X=8-bit)
  → $00:8781 (JumpTableLocal — PLY pops 1 byte instead of 2)
  → RTL to garbage → JSL $1D66CC → TCS with A=2727 → black screen
```

All priority fixes below are in or near this crash chain.

### Fix 1.1: HUD_Update Hook Exit (P0 — HIGHEST PRIORITY)

**Problem:** `HUD_Update` hook exit has **56 unbalanced PHP/PLP** and 4 unbalanced PHD/PLD.
This runs **every single frame** and is directly in the crash chain.

**Files to examine:**
- Find the hook target for `HUD_Update` in `hooks.json` (lines 3910-3916, 4131-4137)
- The source file implementing the HUD_Update hook
- Verify every code path has matched PHP/PLP pairs

**Fix pattern:**
```asm
; At hook entry:
PHP              ; Save caller's P register
REP #$30         ; Set known state (16-bit M/X) or SEP as needed
; ... Oracle HUD code ...
PLP              ; Restore caller's P register exactly
RTL
```

**Verify:** Every branch/exit path must hit PLP before RTL. Count PHP vs PLP on all paths.

**Build & test:** `./scripts/build_rom.sh 168` then load save state 1 (overworld) and 2 (dungeon).

### Fix 1.2: HUD_UpdateItemBox Hook Exit (P0)

**Problem:** 60 unbalanced PHP/PLP, 6 unbalanced PHD/PLD. Also every-frame.

**Files:** Hook target from `hooks.json` line 5616-5622.

**Same fix pattern as 1.1.**

### Fix 1.3: Oracle_Ancilla_CheckDamageToSprite (P1)

**Problem:** PHA at `$06ECC8` pushes 2 bytes (M=16-bit), but PLA at `$06ACF1` pulls 1 byte
(M=8-bit). This affects **14 occurrences across 8 sprite routines** in bank 06.

**Files to examine:**
- Source file containing `Oracle_Ancilla_CheckDamageToSprite`
- Source file containing `Oracle_Sprite_CheckIfLifted` (where the mismatched PLA lives)
- All 8 affected sprite routines listed in RootCause.md:55-62

**Fix approach:** Ensure M-flag width is consistent at each PHA/PLA pair:
```asm
; Option A: Force width before push/pull
REP #$20         ; M=16-bit
PHA
; ... code ...
REP #$20         ; M=16-bit (ensure match)
PLA

; Option B: Use explicit 2-byte operations
PEA $0000        ; Always pushes 2 bytes regardless of M
; ... code ...
PLA : PLA         ; Pull 2 bytes explicitly (if M=8-bit)
```

**Affected routines (fix all):**
1. `Oracle_Sprite_TransmuteToBomb` — 3 imbalances
2. `Oracle_Sprite_CheckIfLifted` — 2 imbalances
3. `Oracle_Sprite_CheckDamageToPlayer_same_layer` — 1 imbalance
4. `Oracle_Sprite_BumpDamageGroups` — 1 imbalance
5. `Oracle_ApplyRumbleToSprites` — 2 imbalances
6. `Oracle_SpriteDraw_Locksmith` — 1 imbalance
7. `Oracle_ForcePrizeDrop_long` — 2 imbalances
8. `Oracle_Ancilla_CheckDamageToSprite` — origin of the mismatch

### Fix 1.4: Oracle_ApplyRumbleToSprites (P1)

**Problem:** Called from `Overworld_Entrance` (`$1BC1C3`) with PHA(M=16)/PLA(M=8).
This runs during overworld gameplay — directly relevant to State 1 (overworld softlock).

**Files:** Source for `Oracle_ApplyRumbleToSprites` at `$068142`/`$068189`.

### Fix 1.5: ActivateSubScreen (P2)

**Problem:** PHB/PLB imbalance — 3 pushes vs 6 pulls. Stack underflow during screen transitions.

**Files:** Hook target from `hooks.json` line 242-248.

### Fix 1.6: Oracle_Sprite_DrawMultiple_quantity_preset (P2)

**Problem:** PHX(X=16)/PLX(X=8) at `$05DF7A`. Width mismatch in sprite drawing.

### Phase 1 Results (Session 5)

**All Phase 1 fixes applied. Neither bug was resolved.**

Fixes applied:
- Fix 1.1: HUD_Update PHP/PLP (`Menu/menu_hud.asm`) — ✅ applied, ❌ did not fix
- Fix 1.1b: SpriteActiveExp_MainLong PHP/PLP (`Core/sprite_new_table.asm`) — ✅ applied, ❌ did not fix
- Fix 1.2: N/A (HUD_UpdateItemBox is a JSR within HUD_Update, covered by Fix 1.1)
- Fix 1.3-1.6: Root causes are in vanilla ROM, not Oracle source. Addressed via sprite dispatch wrapper.

Width imbalances reduced from 413 → 401. Fixes are correct but did not resolve the regression.

---

## Phase 1B: Module Isolation (CURRENT — highest priority)

**Rationale:** The code worked until recently. Static analysis finds hundreds of long-standing
ABI patterns, but fixing them hasn't resolved the crash. The root cause is a specific recent
change, not a fundamental design flaw. Disabling modules identifies which one introduced it.

**Infrastructure:** `Util/macros.asm` has `!DISABLE_*` flags. `Oracle_main.asm` wraps each
module include with conditionals. See `Docs/General/DevelopmentGuidelines.md` Section 2.6.

### Isolation Protocol

1. Set `!DISABLE_<MODULE> = 1` in `Util/macros.asm`
2. Build: `./scripts/build_rom.sh 168`
3. If build fails with undefined symbols, note the dependency and try disabling the dependent module too (or add a stub to `Core/symbols.asm`)
4. Test save state 1 (overworld) and save state 2 (dungeon)
5. Record result: bug reproduces or not
6. Re-enable module, try next one

### Recommended Order (safest first)

| Step | Disable | Expected Impact | Hooks Removed |
|------|---------|-----------------|---------------|
| 1 | Masks | Transformation forms unavailable | 51 |
| 2 | Music | No custom music | 9 |
| 3 | Menu | No custom HUD/journal (vanilla UI persists) | 66 |
| 4 | Items | No custom items (vanilla items persist) | 64 |
| 5 | Patches | No vanilla behavior fixes | ~20 |
| 6 | Sprites | No custom NPCs/bosses | 76 |
| 7 | Dungeon | No custom dungeon logic | 115 |
| 8 | Overworld | No custom overworld (breaks gameplay) | 180 |

### After Identifying the Guilty Module

Once a module is found that resolves the crash when disabled:
1. Re-enable the module
2. Bisect within the module by commenting out individual `incsrc` lines in its `all_*.asm`
3. Narrow to the specific file, then the specific hook/routine
4. Apply targeted fix

---

## Phase 2: ZSCustomOverworld NMI Audit

**Rationale:** `ZSCustomOverworld.asm` (171KB, global namespace) has NMI module variables
at lines 71-76 (`NewNMISource1/Target1`). ZSOW interacts with NMI and runs outside the
Oracle namespace. If its NMI interaction corrupts register state, that could explain the crash.

**Steps:**
1. Read `Overworld/ZSCustomOverworld.asm:60-100` for NMI variable definitions
2. Search for all NMI-related writes in ZSOW (STA to NMI addresses)
3. Check if ZSOW modifies any addresses near `$7E1F0A` (POLYSTACKL region)
4. Verify ZSOW hooks preserve P register at entry/exit
5. Check ZSOW's `LoadOverworldSpritesLong` hook — it's at `$09C4AC` and loads sprites during overworld, directly in the State 1 path

**Delegate to:** `asm-expert` subagent with full ZSOW context.

---

## Phase 3: Git Bisect (Nov 22 Window)

**Rationale:** Instability appeared between Nov 22 and Jan 26. Three high-risk commits:

| Commit | Description | Risk |
|--------|-------------|------|
| `8b23049` | Menu rewrite (2010 lines, AI-generated) | HIGH |
| `93bd42b` | Time system refactor (1279 lines) | HIGH |
| `d41dcda` | ZSOW v3 port | MEDIUM |

**Automated bisect (recommended):** Requires Mesen2 running with ROM loaded and socket. After each step the script builds the ROM; reload the ROM in Mesen2 before the next run.

```bash
cd ~/src/hobby/oracle-of-secrets
git bisect start HEAD <last-known-good-commit>
git bisect run python3 scripts/bisect_softlock.py
```

**Manual steps:**
```bash
cd ~/src/hobby/oracle-of-secrets
git log --oneline 8b23049^..HEAD | head -30  # See commit range

# Test each suspect commit:
git stash  # Save current work
git checkout 8b23049^  # Before menu rewrite
./scripts/build_rom.sh 168
# Test in emulator with save states

git checkout 93bd42b^  # Before time system
./scripts/build_rom.sh 168
# Test again

git checkout d41dcda^  # Before ZSOW v3
./scripts/build_rom.sh 168
# Test again

git checkout -  # Return to current
git stash pop
```

**Goal:** Identify which commit introduced the instability. Then diff that commit's changes
against current to narrow the search to specific routines.

---

## Phase 4: Dynamic Capture (Fallback)

If Phase 1-3 don't resolve the bug, runtime debugging is guaranteed to find it.

```bash
cd ~/src/hobby/oracle-of-secrets

# Strategy 1: SP range breakpoint (fastest if supported)
python3 scripts/repro_stack_corruption.py --strategy sp_range --output /tmp/blame_report.json

# Strategy 2: Polling (guaranteed, slower)
python3 scripts/repro_stack_corruption.py --strategy polling --frames 600 --output /tmp/blame_report.json
```

**After capturing blame PC:**
1. `z3ed rom-resolve-address --address=<PC> --rom=Roms/oos168x.sfc`
2. `python3 ~/src/hobby/yaze/scripts/ai/code_graph.py callers <routine>`
3. Apply fix and verify

---

## Phase 5: Comprehensive Hook ABI Sweep

Audit all 709 hooks for P register preservation:
```bash
python3 ~/src/hobby/z3dk/scripts/oracle_analyzer.py \
  --rom Roms/oos168x.sfc \
  --check-hooks \
  --find-mx \
  --find-width-imbalance \
  --output /tmp/full_hook_audit.json
```

Focus on bank 06 hooks first (sprite/HUD path), then expand outward.

---

## Key Files Reference

| File | Role |
|------|------|
| `Docs/Issues/OverworldSoftlock_RootCause.md` | Detailed mechanism + static findings |
| `Docs/Issues/OverworldSoftlock_Handoff.md` | Session 1-3 history |
| `Docs/Issues/OverworldSoftlock_FixPlan.md` | **THIS FILE** — active fix plan |
| `Docs/Issues/width_imbalance_report_20260130.json` | 413 width imbalances |
| `hooks.json` | Hook registry (709 entries) |
| `scripts/repro_stack_corruption.py` | Dynamic repro script |
| `z3dk/scripts/oracle_analyzer.py` | Static analyzer |
| `Core/ram.asm:5286` | POLYSTACKL = $7E1F0A definition |
| `Overworld/ZSCustomOverworld.asm:71-76` | ZSOW NMI variables |

## Tooling Commands

```bash
# Build
./scripts/build_rom.sh 168

# Static analysis
python3 ~/src/hobby/z3dk/scripts/oracle_analyzer.py --rom Roms/oos168x.sfc --check-hooks --find-mx --find-width-imbalance

# Dynamic repro
python3 scripts/repro_stack_corruption.py --strategy auto --output /tmp/blame_report.json

# Symbol resolution
z3ed rom-resolve-address --address=<ADDR> --rom=Roms/oos168x.sfc

# Call graph
python3 ~/src/hobby/yaze/scripts/ai/code_graph.py callers <label>
```
