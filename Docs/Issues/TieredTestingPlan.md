# Tiered Testing Plan for Black Screen Bug

> NOTE (2026-01-24): oos168x/oos168_test2 save states are deprecated. Use patched oos168x states only; stale packs are archived under `Roms/SaveStates/library/_stale_oos_20260124`.

**Created:** 2026-01-24
**Status:** IN PROGRESS
**Context:** Mesen2 fork instability prevents deep debugging

---

## Problem Statement

The black screen bug has been receiving "theoretical fixes" from multiple agents without:
1. Capturing actual failure state
2. Verifying fixes against observed behavior
3. Running regression tests

The Mesen2 fork crashes, making automated state capture impossible.

---

## Tiered Verification Architecture

Instead of treating testing as one monolithic operation requiring the unstable fork, we use tiers:

### Tier 0: Build Verification ✅
**No emulator required**

```bash
./scripts/build_rom.sh 168
# Success: ROM compiles, no errors
# Output: Roms/oos168x.sfc
```

**Verification:**
- [ ] ROM assembles without errors
- [ ] Symbol file generated: `Roms/oos168x.sym`
- [ ] ROM size reasonable (~2MB)

### Tier 1: Static Analysis 🔍
**No emulator required**

Verify opcodes at hook addresses using hexdump.

**Key Opcodes:**
| Opcode | Meaning | Expected At |
|--------|---------|-------------|
| `8F` | STA.l (long absolute) | All $7EF3CC writes |
| `8D` | STA.w (absolute) | Would be WRONG |
| `E2 20` | SEP #$20 | Intraroom hook entry |
| `C2 20` | REP #$20 | Intraroom hook exit |

**Verification Script:**
```bash
# Find hook addresses from symbol file
grep -E "(CheckForFollowerInter|CheckForFollowerIntra)" Roms/oos168x.sym

# Example verification at address (convert to file offset):
# ROM address $02XXXX = file offset $XXXX + headerless adjustment
xxd -s $OFFSET -l 32 Roms/oos168x.sfc
```

**Static Checks:**
- [ ] `CheckForFollowerInterroomTransition` uses `8F` (STA.l) for $7EF3CC
- [ ] `CheckForFollowerIntraroomTransition` has `E2 20` (SEP #$20) at entry
- [ ] `CheckForFollowerIntraroomTransition` has `C2 20` (REP #$20) before RTL
- [ ] No `8D` (STA.w) to $7EF3CC in either hook

### Tier 2: Smoke Testing with Mesen2 OOS 👁️
**Uses /Applications/Mesen2 OOS.app**

Visual pass/fail only - no automation needed.

**ROM Target:** Use the patched ROM (`oos168x.sfc`) built from the current dev ROM (`oos168_test2.sfc`).

**Test Matrix:**

| Test Case | Location | Action | Expected | Result |
|-----------|----------|--------|----------|--------|
| OW→Cave | Any cave entrance | Walk in | Screen fades to black, fades in to cave | **BLOCKED** (no test2 entrance state) |
| OW→Dungeon | Graveyard entrance | Walk in | Spotlight effect, room loads | **BLOCKED** (no test2 entrance state) |
| OW→Building | Kakariko house | Walk in | Screen transition | **BLOCKED** (no test2 entrance state) |
| Dungeon Stairs (inter) | Any room change stairs | Walk on | New room loads | **BLOCKED** (no test2 stairs state) |
| Dungeon Stairs (intra) | Layer change stairs | Walk on | Same room, different layer | **BLOCKED** (no test2 stairs state) |
| Dungeon→OW | Dungeon exit | Walk out | Return to overworld | **PASS** (mode 0x07→0x09, INIDISP 0x00) |

**How to Test:**
1. Open `/Applications/Mesen.app`
2. Load `Roms/oos168x.sfc`
3. Either: Start new game, or load save state from `Roms/SaveStates/`
4. Navigate to test location
5. Perform action
6. Record PASS (screen fades in) or FAIL (black screen hangs)

### Tier 3: Automated State Capture 🤖
**Requires stable Mesen2 fork**

When the fork is working:

```bash
# Launch with socket server
python3 ~/.claude/skills/oracle-debugger/scripts/debugger.py session

# Commands:
# regression - run all tests
# reproduce "black screen" - try to reproduce
# states load <name> - load save state
```

### Tier 4: Deep Debugging 🔬
**Requires Mesen2 fork with all hooks**

For when we need P register tracing, MEM_BLAME, breakpoints:

```bash
# When fork is stable:
~/src/hobby/mesen2-oos/bin/osx-arm64/Release/Mesen
# Then connect via socket API
```

---

## Current Priority: Tier 1 + Tier 2

Since Mesen2 fork is unstable, focus on:

1. **Complete Tier 1 static analysis** - Verify assembled opcodes
2. **Complete Tier 2 smoke testing** - Visual confirmation with vanilla Mesen
3. **Document results** - Record pass/fail for each test case

---

## Fixes Applied (Unverified)

### 1. CheckForFollowerInterroomTransition
**File:** `Sprites/NPCs/followers.asm:948-963`
```asm
LDA.b #$0B : STA.l $7EF3CC    ; Changed from STA.w
LDA.b #$01 : STA.l $7E0F00, X ; Changed from STA.w
```

### 2. CheckForFollowerIntraroomTransition
**File:** `Sprites/NPCs/followers.asm:965-978`
```asm
STA.l $7EC007           ; Uses long addressing
SEP #$20                ; Switch to 8-bit mode
; ... logic ...
REP #$20                ; Restore 16-bit mode
RTL
```

---

## Failure Pattern Reference

From `zelda-debugger` skill documentation:

| GameMode | Submodule | INIDISP | Diagnosis |
|----------|-----------|---------|-----------|
| 0x06 | Any | 0x80 | Room load hung |
| 0x07 | 0x00 | 0x80 | Fade-in never triggered |
| 0x07 | 0x0F | 0x80 | LandingWipe stuck |
| 0x07 | 0x01 | 0x80 | Intraroom transition hung |
| 0x07 | 0x02 | 0x80 | Interroom transition hung |

---

## Reducing Verification Burden

### Problem
Every change requires:
1. Build ROM
2. Launch emulator
3. Navigate to location
4. Trigger transition
5. Observe/capture
6. Repeat for all locations

This is O(n × m) where n = changes, m = test locations.

### Solutions Applied

1. **Tier separation** - Don't need full debugging for every test
2. **Static verification first** - Catch many bugs without emulator
3. **Save state library** - Skip navigation, jump to test points
4. **Visual smoke tests** - Fast pass/fail without automation
5. **Pattern matrix** - If bug occurs, quickly identify category

---

## Next Steps

1. [ ] Run Tier 1: Static verify opcodes at hook addresses
2. [ ] Run Tier 2: Smoke test 6 transition scenarios
3. [ ] Document results in this file
4. [ ] If all pass → bug may be fixed
5. [ ] If any fail → capture Mode/Sub/INIDISP visually
6. [ ] Match failure to pattern matrix → identify root cause

---

## Session Log

### 2026-01-24 - Initial Analysis

**Mesen2 Fork Status:** Unstable, crashes on script execution
**Solution:** Tiered testing approach to work around instability
**Memory Graph:** Created `OracleTestingStrategy` and `OracleBlackScreenBug` entities

**Fixes in source code:**
- followers.asm has SEP/REP wrapper (lines 971, 976)
- followers.asm has long addressing (lines 952, 958, 969, 974)

### 2026-01-24 - Tier 1 Static Verification

**ROM Built:** `Roms/oos168x.sfc` (2.2MB, built 02:55)

**Symbol File Locations:**
```
2C:BF29 Oracle_CheckForFollowerInterroomTransition
2C:BF43 Oracle_CheckForFollowerIntraroomTransition
```

**Opcode Verification Results:**

| Check | Expected | Found | Status |
|-------|----------|-------|--------|
| STA.l $7EF3CC (8F CC F3 7E) | Present in hooks | ✅ 10+ occurrences | PASS |
| STA.w $F3CC (8D CC F3) | Should NOT exist | ✅ None found | PASS |
| STA.l $7EC007 (8F 07 C0 7E) | Present in intraroom | ✅ Multiple | PASS |
| SEP #$20 (E2 20) | Present after STA.l | ✅ Found at 0x6be0+0x0c | PASS |
| REP #$20 (C2 20) | Present before RTL | ✅ Found at 0x6bf0 | PASS |

**Conclusion:** Static verification PASSES. The assembled ROM uses correct:
1. Long addressing (8F opcode) for all $7EF3CC stores
2. SEP/REP wrapper for 8-bit/16-bit mode preservation
3. No incorrect short addressing (8D) to follower type

**Next Step:** Tier 2 smoke testing with vanilla Mesen.app

### 2026-01-24 - Tier 2 Automated Smoke (dev ROM attempt; superseded)

**ROM:** `Roms/oos168_test2.sfc` (dev ROM; superseded by patched target)
**Method:** Mesen2 socket API + input injection (no visual confirmation)
**Note:** No dedicated test2 save states exist. Used oos168x slot states as temporary entry points.

**Starting States Used (loaded into test2 ROM):**
- `oos168x_1` (Goron Desert) → OW→Cave attempt
- `oos168x_5` (Graveyard) → OW→Dungeon attempt
- `oos168x_4` (Ranch) → OW→Building attempt
- `oos168x_3` (Zora Temple Entrance) → Dungeon→OW attempt
- `oos168x_8` (Goron Mines) → Dungeon stairs attempt

**Results:**
- **Dungeon→OW:** PASS. Moving down from Zora Temple Entrance transitioned to Overworld (mode 0x07→0x09, indoors 1→0, INIDISP stayed 0x00).
- **OW→Cave / OW→Dungeon / OW→Building:** BLOCKED. Could not reach entrances with available states; inputs only moved Link within area.
- **Dungeon Stairs (inter/intra):** BLOCKED. No stair transition triggered from current dungeon state.
- **Black screen:** Not observed during automated attempts (INIDISP remained 0x00).

**Follow-ups:**
1. Capture **dev-based** entrance/stair save states (from the patched `oos168x.sfc` built on `oos168_test2.sfc`) and add to library.
2. Re-run Tier 2 on the patched ROM with those states to validate fade/transition behavior visually.

### 2026-01-24 - Tier 2 Test Launcher Created (Iteration 61)

**New Tool:** `scripts/campaign/tier2_test_launcher.py`

**Usage:**
```bash
# List all test scenarios
python -m scripts.campaign.tier2_test_launcher --list

# Run a specific scenario (launches Mesen with state)
python -m scripts.campaign.tier2_test_launcher --test ow_to_cave

# List all available save states
python -m scripts.campaign.tier2_test_launcher --list-states

# Launch with specific state
python -m scripts.campaign.tier2_test_launcher --state current_4
```

**Available Test Scenarios:**
| ID | Name | State | Expected |
|----|------|-------|----------|
| `ow_to_cave` | Overworld to Cave | current_1 | Fade out/in to cave |
| `ow_to_dungeon` | Overworld to Dungeon | current_3 | Spotlight, room loads |
| `ow_to_building` | Overworld to Building | current_1 | Screen transition |
| `dungeon_stairs_inter` | Dungeon Interroom Stairs | current_4 | New room loads |
| `dungeon_stairs_intra` | Dungeon Intraroom Stairs | current_7 | Layer changes |
| `dungeon_to_ow` | Dungeon to Overworld | current_4 | Return to overworld |

**Tests Added:** 48 tests in `test_tier2_launcher.py`

**Status:** Ready for manual verification
