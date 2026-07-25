# Save State Library (Current)

Purpose: keep a curated set of save states for fast repro and regression testing.

## What Is Tracked
- **Manifest (tracked):** `Docs/Debugging/Testing/save_state_library.json`
- **Binary `.mss` files (local only):** `Roms/SaveStates/library/` (gitignored)

## Golden Path (Socket API)
All supported workflows go through `python3 Scripts/Mesen2/mesen2_client.py`.

Popup workflow (macOS):
```bash
python3 Scripts/Debug/oos_state_popup.py --instance <mesen-instance> --theme dark --layout compact --font-size 18
```
This gives you:
- live metadata summary (mode/area/room/story flags/last loaded state)
- metadata prompts when capturing a state
- click actions (apply profile, crystal preset, warp, sync to SRAM, trusted seed mapping)
- one-click scenario macros (Maku threshold prep, D4 water gate prep, D6 prep)
- larger menu/UI text via `--font-size` (example: `--font-size 18`)
- theme control via `--theme dark|light|system`
- operator layout via `--layout compact` (macro-first)

### Keyboard Shortcuts (built-in)
- `Ctrl+R`: refresh metadata
- `Ctrl+S`: sync WRAMSAVE -> SRAM
- `Ctrl+Shift+C`: capture state
- `Ctrl+P`: apply selected profile
- `Ctrl+W`: warp to selected location
- `Ctrl+L`: clear log
- `Ctrl+1..5`: run macro buttons from `oos_ui_macros.json` (default bindings)

### Macro Profiles (JSON-driven)
- File: `Docs/Debugging/Testing/oos_ui_macros.json`
- You can change labels, shortcuts, order, and steps without editing Python.
- Supported step actions:
  - `apply_profile` with `profile`
  - `setflag` with `flag` + `value`
  - `sync_sram`
  - `fly` with `location`
  - `frame` with `frames`

## Trust Contract (New)
- Launching an emulator instance no longer auto-seeds legacy slot files.
- Named debug sessions (`Scripts/Build/oos-session.sh`) only load IDs from
  `Docs/Debugging/Testing/trusted_state_seeds.json`.
- Trusted task seeds must be:
  - `status: "canon"`
  - `captured_by: "human"`

### List, Load, Inspect
```bash
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py library
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py lib-info <state_id> --json
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py lib-load <state_id>
```

### Start An Isolated Session (No Slot Seeding)
```bash
Scripts/Mesen2/mesen2_launch_instance.sh --instance oos-yourname-debug --owner yourname --source manual
```

Use `--seed-project-states` only when you intentionally need legacy F-key slot
files.

### Capture A Repro Seed (Draft Entry)
```bash
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py smart-save 5
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py lib-save "Zora Temple blackout repro" -t dungeon -t blackout -t repro
```

### Promote To Canon + Regression Guardrail
```bash
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py lib-verify <state_id> --by scawful
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py lib-verify-all
```

### Mark A State As Human-Captured Canon
```bash
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py lib-save "Maku base seed" --captured-by human -t progression -t maku
MESEN2_AUTO_ATTACH=1 python3 Scripts/Mesen2/mesen2_client.py lib-verify <state_id> --by scawful
```

Then set the task mapping in:

- `Docs/Debugging/Testing/trusted_state_seeds.json`

Or use the helper:

```bash
python3 Scripts/set_trusted_state_seed.py maku <state_id>
```

## Notes
- If a state was captured on an older ROM build, use the in-game cache reload hotkey if needed: `L + R + Select + Start`.
- Use `python3 Scripts/Mesen2/mesen2_client.py` for all state library operations.
