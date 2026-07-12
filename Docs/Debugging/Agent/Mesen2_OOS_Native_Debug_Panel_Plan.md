# Mesen2-OOS Native Debug Panel Plan

Status: Proposed
Owner: Oracle debugging workflow
Target: `~/src/hobby/mesen2-oos` (Mesen2 fork), integrated in emulator window

---

## Goal

Implement a **native, hideable debug panel** directly in the Mesen2-OOS app window:

- rendered **above the game viewport**
- available during normal playtesting
- hide/show instantly without leaving the emulator
- usable as the main surface for Oracle test setup and state capture metadata

This replaces external popup-style control surfaces for the primary workflow.

---

## UX Requirements (Locked)

1. Panel is part of the Mesen2-OOS window, not a separate app/dialog.
2. Panel sits at the top of the emulator content area ("above the game").
3. Panel is hideable/toggleable at all times with a single hotkey.
4. Hidden state is clean: full game viewport visible and interactive.
5. Expanded state shows:
   - live game/debug metadata
   - state capture metadata inputs
   - actionable debug controls
   - macro buttons
6. Font/UI scale must be readable for live testing (larger defaults than stock Mesen menus).

---

## Target Interaction Model

### Panel Visibility States

- `Hidden`: no panel chrome; game has full focus.
- `Collapsed`: thin top strip (status + quick actions + expand button).
- `Expanded`: full debug panel area above viewport.

### Suggested Defaults

- Startup default: `Collapsed`.
- Toggle key: `F8` (single key).
- Expand/collapse: `F7` or chevron button in strip.
- Persist state in settings (per profile).

---

## Panel Content (v1)

### 1) Live Context

- Mode/submode, indoors/outdoors, area/room, frame, paused/running
- Link position/state/form
- HP/magic/rupees
- Story/progression fields (`GameState`, `OOSPROG`, crystal/pendant values)
- Last state load info

### 2) State Capture

- Label input
- Tags input
- Verify-now toggle + verifier field
- Optional "map to trusted seed task" selector
- Capture button

### 3) Quick Actions

- Apply save-data profile
- Set crystal preset
- Set `GameState`
- Warp/fly destination
- Sync WRAMSAVE -> SRAM
- Refresh metadata

### 4) Macro Deck

- Macro buttons loaded from JSON profile
- Primary macros visually emphasized
- Display shortcut per macro

### 5) Session Log

- Small rolling action log
- Clear + copy actions

---

## JSON-Driven Macro Profiles

Use a JSON macro schema (same logical model as current external UI) so flow changes do not require C# code edits.

Initial supported actions:

- `apply_profile`
- `setflag`
- `sync_sram`
- `fly`
- `frame`

Validation rules:

- Strict key validation at startup
- Bad profiles disable macro section with visible error (no silent failure)

---

## Keyboard Shortcuts

Global shortcuts (active when panel open; do not trigger while text field is focused):

- `F8` toggle hidden/collapsed
- `F7` collapse/expand
- `Ctrl+R` refresh metadata
- `Ctrl+S` sync SRAM
- `Ctrl+Shift+C` capture state
- `Ctrl+1..9` macro buttons

---

## Technical Integration Plan (Mesen2-OOS)

## Phase 0 - UI Shell Placement

- Add a top-level panel container in the main emulator window layout.
- Keep game renderer below it.
- Wire visibility state machine (`Hidden/Collapsed/Expanded`).

Deliverable: panel exists and can hide/show above viewport.

## Phase 1 - Data Binding

- Add a `OracleDebugPanelViewModel` bound to existing emulator/debug state.
- Update metadata fields on timer or event ticks.
- Ensure updates are lightweight and non-blocking.

Deliverable: live context fields update while game runs.

## Phase 2 - Action Wiring

- Route panel actions to existing internal command surfaces (same backend used by socket tools).
- Implement command execution wrapper with:
  - success/error toast/status line
  - action log entry

Deliverable: profile/setflag/warp/sync/capture actions work in-panel.

## Phase 3 - Macro System

- Load macro JSON from configurable path.
- Validate schema and bind buttons dynamically.
- Execute macro step sequences with visible progress.

Deliverable: one-click scenario setup macros.

## Phase 4 - Polish + Accessibility

- Larger default fonts and scaling controls.
- Theme consistency with app (dark/light/system).
- Improve spacing/hierarchy for operator use.
- Add copy/export for session log.

Deliverable: release-ready UX.

---

## File/Component Targets (Expected)

Exact paths depend on current Mesen2-OOS tree; expected components:

- Main emulator window layout (host container for top panel)
- New debug panel view (`OracleDebugPanel.axaml` or equivalent)
- New panel view model (`OracleDebugPanelViewModel.cs`)
- Command dispatcher/service adapter
- Settings persistence for panel visibility/size/theme

If the project still uses structures like:

- `UI/Windows/...`
- `UI/ViewModels/...`

place the new panel alongside existing Oracle diagnostics tooling.

---

## Performance/Safety Constraints

- No frame hitching from UI refresh.
- No blocking calls on UI thread.
- Action failures must be explicit (status/error), not silent.
- Hidden mode must not intercept gameplay input.
- Panel must not mutate state unless a user action is explicit.

---

## Acceptance Criteria

1. Panel appears in Mesen2-OOS window above the game.
2. `F8` instantly hides/shows panel with correct input focus behavior.
3. Core metadata is visible and updates during gameplay.
4. Capture flow supports metadata entry and trusted seed mapping.
5. Quick actions and macros run successfully end-to-end.
6. Macro profiles are editable via JSON without recompiling.
7. UI text is comfortably readable at default scale.
8. No measurable gameplay regressions while panel is hidden.

---

## Test Plan

1. Visibility:
   - hidden/collapsed/expanded transitions while running and paused
2. Focus:
   - gameplay controls still work when hidden
   - shortcuts ignored while typing in input fields
3. Data correctness:
   - compare panel metadata with socket CLI diagnostics
4. Actions:
   - run each quick action once
5. Macros:
   - run all defaults; validate resulting state
   - break JSON intentionally; confirm graceful error handling
6. Performance:
   - observe frame pacing with panel hidden and expanded

---

## Risks

- UI architecture differences in current Mesen2-OOS branch may require adapting container strategy.
- Command pathway duplication can drift if not centralized.
- Input focus conflicts if shortcut routing is not scoped carefully.

Mitigation: keep one command service shared by socket and panel pathways; add focused shortcut guards.

---

## Next Step

Start with **Phase 0 + Phase 1** in `mesen2-oos`: create the top panel container and bind read-only live metadata before wiring any mutating actions.
