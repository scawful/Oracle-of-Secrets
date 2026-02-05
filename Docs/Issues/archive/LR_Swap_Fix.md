# L/R Hookshot/Goldstar Swap Fix

**Status:** TESTED & VERIFIED
**Date Fixed:** 2026-01-21
**Date Tested:** 2026-01-21
**Files Modified:**
- `Masks/mask_routines.asm` (lines 1356-1382)
- `Items/goldstar.asm` (lines 1001-1019)

---

## Summary

Fixed the L/R button swap for Hookshot/Goldstar items during gameplay.

### Changes Made

1. **Added `CheckNewLButtonPress`** - New routine that mirrors `CheckNewRButtonPress` but checks L button (bit $20 of $F6)

2. **Fixed input clearing bug** - Changed `STZ $F6` to `AND #$EF/$DF` to only clear the specific button pressed, preventing regressions with other systems that also read `$F6`

3. **Updated `CheckForSwitchToGoldstar`** - Now checks both L and R buttons

4. **Fixed toggle logic** - Changed initial state handling so first press always switches to Goldstar (previously no visible change on first press)

### Before (broken)
```asm
CheckForSwitchToGoldstar:
  JSL CheckNewRButtonPress : BEQ .continue  ; Only R worked
  LDA.w GoldstarOrHookshot : CMP.b #$01 : BEQ .set_hookshot  ; Wrong toggle
  ...
```

### After (fixed)
```asm
CheckForSwitchToGoldstar:
  JSL CheckNewRButtonPress : BCS .do_swap
  JSL CheckNewLButtonPress : BEQ .continue  ; Now L also works
  .do_swap
  LDA.w GoldstarOrHookshot : CMP.b #$02 : BEQ .set_hookshot  ; Correct toggle
  ...
```

---

## Test Results

**Tested via Mesen2 Live Bridge on 2026-01-21**

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | R button swap | PASS | Swaps correctly |
| 2 | L button swap | PASS | Swaps correctly |
| 3 | Toggle logic | PASS | `0x00→0x02→0x01→0x02` cycle works |
| 4 | Rapid toggle | PASS | Multiple quick presses all register |

### Test Methodology

Used the new Mesen2 CLI bridge to:
1. Set `$7EF342 = 0x02` (give both items via write command)
2. Watch `$7E0739` for value changes
3. Press L/R buttons and observe toggle

**Observed values:**
```
[23:07:17] READ:0x7E0739=0x00 (0)   <- Initial state (hookshot default)
[23:07:25] READ:0x7E0739=0x02 (2)   <- First L/R press → Goldstar
[23:07:26] READ:0x7E0739=0x01 (1)   <- Second press → Hookshot
[23:07:26] READ:0x7E0739=0x02 (2)   <- Third press → Goldstar
```

---

## Key Memory Addresses

| Address | Name | Description |
|---------|------|-------------|
| `$7E00F6` | F6 | New button inputs (AXLR) - current frame only |
| `$7EF342` | Hookshot | SRAM: $01=hookshot, $02=has both hookshot+goldstar |
| `$7E0739` | GoldstarOrHookshot | Which is currently equipped: $01=hookshot, $02=goldstar |
| `$7E0202` | Menu cursor | Current menu selection (hookshot slot = $03) |

### Input Bits ($F6)
- Bit 4 ($10) = R button
- Bit 5 ($20) = L button
- Bit 6 ($40) = X button
- Bit 7 ($80) = A button

---

## Mesen2 Testing Commands

```bash
# Check if player has both items
./scripts/mesen_cli.sh read 0x7EF342  # Should be 0x02

# Set both items for testing
./scripts/mesen_cli.sh write 0x7EF342 0x02

# Check which is currently equipped
./scripts/mesen_cli.sh read 0x7E0739  # 0x01=hookshot, 0x02=goldstar

# Watch for changes
./scripts/mesen_cli.sh watch 0x7E0739

# Full L/R swap status
./scripts/mesen_cli.sh lrswap
```

---

## Regression Testing (TODO)

- [ ] Menu navigation still works (other systems reading $F6)
- [ ] Mask transformation still works (uses `CheckNewRButtonPress`)
- [ ] No stuck inputs or missed button presses

---

## Related Documentation

- `Docs/Agent/Mesen2_Testing_Guide.md` - Full testing guide for agents
- `scripts/mesen_cli.sh` - CLI tool for bridge interaction
- `scripts/mesen_live_bridge.lua` - Mesen2 Lua bridge script
