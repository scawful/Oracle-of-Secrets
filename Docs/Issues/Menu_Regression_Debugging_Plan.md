# Menu Regression Debugging Plan
## Oracle of Secrets - Stability Analysis

*Generated: 2026-01-21*
*Based on git history analysis (30 commits, 12 menu-specific since Nov 2025)*

---

## Executive Summary

The menu system has undergone significant refactoring with 12+ commits since November 2025. Analysis of the git history reveals **5 distinct bug categories** that have caused regressions. This plan provides a systematic approach to debugging current issues and preventing future regressions.

---

## 1. Identified Bug Categories from Git History

### Category A: P Register (Processor Status) Mismatches
**Commits:** `8b23049`, `791ebaf`

| Symptom | Root Cause | Fix Pattern |
|---------|------------|-------------|
| Crashes, corrupted data | Missing `SEP #$30` after JSL/JSR | Add explicit mode setting at routine entry |
| Wrong values loaded | 16-bit vs 8-bit mode confusion | Always verify M/X flags after bank changes |

**Files Affected:**
- `Menu/menu.asm`: `Menu_RefreshQuestScreen`, `Menu_ScrollFrom`, `Menu_DrawRingPrompt`
- `Menu/menu_journal.asm`: Multiple routines

**Debug Strategy:**
```
1. Search for all JSL/JSR calls
2. Verify P register state at each call site
3. Check return paths for mode restoration
4. Use Mesen2 debugger to trace P register through menu operations
```

### Category B: Stack Corruption
**Commits:** `8b23049`

| Symptom | Root Cause | Fix Pattern |
|---------|------------|-------------|
| Random crashes | Missing PHB/PLB pairs | Audit all bank-switching routines |
| Wrong return address | Unbalanced stack operations | Verify push/pull symmetry |

**Specific Instance:**
- `Journal_CountUnlocked`: Missing `PHB` caused stack corruption

**Debug Strategy:**
```
1. Grep for all PHB/PLB, PHA/PLA, PHX/PLX patterns
2. Verify matching pairs in each routine
3. Check for early returns that skip cleanup
4. Monitor SP register in Mesen2 for unexpected changes
```

### Category C: VRAM Upload Index Corruption
**Commits:** `8b23049`, `3ceab24`

| Symptom | Root Cause | Fix Pattern |
|---------|------------|-------------|
| IrisSpotlight crash ($00F361) | Errant writes to $0116/$17 | Remove/guard VRAM index modifications |
| Tilemap not updating | Wrong NMI flags ($15, $17, $22, $23) | Use correct flag combinations |

**Key Memory Locations:**
- `$0116/$0117`: VRAM upload index (DO NOT modify in menu code)
- `$15`: Palette/refresh flag
- `$17`: NMI upload flag
- `$22/$23`: NMI control flags

**Debug Strategy:**
```
1. Set write breakpoints on $0116, $0117 in Mesen2
2. Trace which code paths modify these
3. Verify NMI flag usage matches vanilla expectations
4. Test flag combinations: $15=1, $17=1 for standard menu refresh
```

### Category D: Data Table Misalignment
**Commits:** `3ceab24`

| Symptom | Root Cause | Fix Pattern |
|---------|------------|-------------|
| Wrong item selected | `Menu_ItemCursorPositions` vs `Menu_AddressIndex` mismatch | Realign table entries |
| Ocarina selector broken | Table index off-by-one | Verify all parallel arrays match |

**Critical Tables (menu_select_item.asm:1-80):**
- `Menu_ItemIndex`: Function dispatch
- `Menu_AddressIndex`: SRAM addresses
- `Menu_ItemCursorPositions`: Screen positions

**Debug Strategy:**
```
1. Print/dump all three tables side-by-side
2. Verify each row has matching item semantics
3. Test each item slot systematically
4. Add assertions for table bounds
```

### Category E: Signed vs Unsigned Comparison Bugs
**Commits:** `791ebaf`

| Symptom | Root Cause | Fix Pattern |
|---------|------------|-------------|
| Menu wrap-around broken | Using unsigned compare on potentially negative values | Use BEQ/BPL for signed, BCS/BCC for unsigned |
| Infinite loops | Wrong boundary condition | Verify comparison semantics |

**Specific Fix:**
```asm
; WRONG (unsigned - treats $FE as 254 >= 1)
CMP #$01 : BCS .boundary

; CORRECT (signed - treats $FE as -2)
CMP #$01 : BEQ .boundary
         : BPL .boundary
```

**Debug Strategy:**
```
1. Audit all CMP instructions near loop boundaries
2. Identify variables that can go negative (cursor positions)
3. Verify comparison branch type matches intended semantics
```

---

## 2. Current Known Issues (from handoff_menu_issues.md)

### Issue 1: Journal Tilemap Not Updating
**Status:** Partially fixed, regressions noted
**Investigation Path:**
1. Check `$15` flag setting in `Menu_Journal`
2. Verify `$22` vs `$23` NMI flag doesn't cause input regression
3. Test alternative: manual buffer upload routine

### Issue 2: L/R Goldstar/Hookshot Swap
**Status:** Only R works
**Investigation Path:**
1. Locate `CheckNewLRButtonPress` implementation
2. Check if `$F6` clearing interferes with other systems
3. Consider submenu approach as alternative

### Issue 3: RHS Menu (Quest Status) Break with $15 Flag
**Status:** Needs investigation
**Investigation Path:**
1. Trace what `$15` flag triggers in NMI
2. Check if Quest Status screen has conflicting VRAM needs
3. Test with Mesen2 NMI logging

---

## 3. Systematic Debugging Workflow

### Phase 1: Triage (Mesen2 + Lua)
```lua
-- scripts/menu_debug.lua
-- Set breakpoints on known problem areas
emu.addMemoryCallback(function()
  print("VRAM index modified at " .. emu.getState().cpu.pc)
end, emu.callbackType.write, 0x0116, 0x0117)

-- Log P register state at menu entry
emu.addMemoryCallback(function()
  local state = emu.getState()
  print("Menu entry P=" .. string.format("%02X", state.cpu.ps))
end, emu.callbackType.exec, 0x2D8000) -- Menu_Entry address
```

### Phase 2: Regression Test Matrix

| Test Case | Steps | Expected | Actual | Commit |
|-----------|-------|----------|--------|--------|
| Open menu | Press Start | Menu displays | | |
| Navigate up | D-pad up | Cursor moves up | | |
| Navigate down | D-pad down | Cursor moves down | | |
| Navigate wrap | Press up at top | Wraps to bottom | | |
| Select item | Press A on item | Item equips | | |
| Open journal | Press X | Journal opens | | |
| Open rings | Press Y | Ring menu opens | | |
| Close menu | Press B | Returns to game | | |
| L/R swap | Press L during gameplay | Swaps Hookshot/Goldstar | | |
| Quest status | Press R in menu | Quest screen shows | | |

### Phase 3: Git Bisect for Regressions
```bash
# If a specific regression is identified
cd ~/src/hobby/oracle-of-secrets
git bisect start
git bisect bad HEAD
git bisect good 8b23049  # Last known good commit
# Build and test at each step
```

---

## 4. File-by-File Audit Checklist

### menu.asm (23KB)
- [ ] Verify all `JSR` return paths restore P register
- [ ] Check `Menu_Entry` dispatch table bounds
- [ ] Audit `$0116/$0117` writes
- [ ] Verify NMI flag usage ($15, $17, $22, $23)

### menu_select_item.asm (8.3KB)
- [ ] Verify table alignment (3 parallel arrays)
- [ ] Check signed/unsigned comparisons in navigation
- [ ] Audit loop termination conditions
- [ ] Test boundary wrap behavior

### menu_journal.asm (17KB)
- [ ] Verify PHB/PLB pairs in all routines
- [ ] Check `$15` flag usage for tilemap refresh
- [ ] Audit `Journal_CountUnlocked` stack operations

### menu_text.asm (13KB)
- [ ] Verify VRAM write addresses
- [ ] Check for mode mismatches in string routines

### menu_draw.asm (19KB)
- [ ] Audit OAM/VRAM upload routines
- [ ] Check palette upload timing

### menu_hud.asm (14KB)
- [ ] Verify FloorIndicator doesn't overflow (commit 1c19788)
- [ ] Check Song of Storms integration

---

## 5. Automated Verification (CI)

The repo has `.github/workflows/test-rom.yml` and `scripts/verify_boot.lua`. Extend with:

```yaml
# Add menu regression tests
- name: Menu Regression Tests
  run: |
    # Build ROM
    ./scripts/build_rom.sh
    # Run menu test script
    mesen --lua scripts/menu_regression_test.lua output.sfc
```

**Recommended Test Script Structure:**
```lua
-- scripts/menu_regression_test.lua
local tests = {
  {name="menu_open", fn=test_menu_open},
  {name="navigate_all", fn=test_navigate_all_items},
  {name="journal_open", fn=test_journal_open},
  {name="wrap_around", fn=test_cursor_wrap},
}
```

---

## 6. Priority Order for Investigation

1. **P1 - Crashes:** Any crash/freeze takes priority
   - Stack corruption
   - VRAM index corruption
   - Infinite loops

2. **P2 - Input Regressions:** Menu becomes unusable
   - Navigation broken
   - Selection broken
   - Exit broken

3. **P3 - Visual Bugs:** Menu works but looks wrong
   - Tilemap not updating
   - Wrong items displayed
   - Palette issues

4. **P4 - Feature Bugs:** Specific features don't work
   - L/R swap
   - Journal entries
   - Ring display

---

## 7. Quick Reference: Key Addresses

| Address | Purpose | Safe to Modify? |
|---------|---------|-----------------|
| `$0116-$0117` | VRAM upload index | NO |
| `$0200` | Menu module state | YES |
| `$0202` | Menu cursor position | YES |
| `$020C` | Stats screen cursor | YES |
| `$15` | Palette/refresh flag | CAREFUL |
| `$17` | NMI upload flag | CAREFUL |
| `$F6` | Input state | CAREFUL |
| `$7EF340+` | Item SRAM addresses | READ ONLY |

---

## Next Steps

1. Build ROM and run existing tests
2. Execute Phase 1 triage with Mesen2
3. Document any new findings in `Docs/Issues/`
4. Create targeted fixes with single-purpose commits
5. Update regression test matrix after each fix
