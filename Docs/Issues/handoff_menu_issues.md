# Handoff: Menu System Issues & L/R Swap Requirement

## Current Status
- **Journal Tilemap**: Still not updating correctly. The `$15` flag fix caused a regression (RHS menu break) and was reverted. The `$22` vs `$23` NMI flag investigation was inconclusive or caused input regressions.
- **Ocarina Selector**: Fixed by reordering `Menu_ItemCursorPositions` in `Menu/menu_select_item.asm`. This fix is preserved.
- **Input**: Input functionality is stable after reverting `$23` NMI flag.

## Requirement: Hookshot/Goldstar L/R Swap
The user requested a specific behavior for swapping the Hookshot and Goldstar items:
- **Context**: When the menu is **closed** (during gameplay).
- **Input**: Pressing **L** or **R** should toggle between the two items.
- **Current Implementation**: Only **R** works.
- **Failed Attempt**: Implementing `CheckNewLRButtonPress` caused a regression (or was part of a regression batch).
- **Future Direction**:
    1.  Implement a safe L/R check that doesn't interfere with other systems (possibly without clearing `$F6` aggressively).
    2.  Consider a submenu for Goldstar/Hookshot selection as an alternative or addition.

## Next Steps
1.  Investigate why `$15` flag breaks RHS menu (Quest Status).
2.  Find an alternative way to trigger Journal tilemap upload (maybe `$01` flag for NMI, or a specific buffer upload routine).
3.  Re-implement L/R swap for Goldstar safely.
