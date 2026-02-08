# Save State Library (Current)

Purpose: keep a curated set of save states for fast repro and regression testing.

## What Is Tracked
- **Manifest (tracked):** `Docs/Debugging/Testing/save_state_library.json`
- **Binary `.mss` files (local only):** `Roms/SaveStates/library/` (gitignored)

## Golden Path (Socket API)
All supported workflows go through `python3 scripts/mesen2_client.py`.

### List, Load, Inspect
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py library
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-info <state_id> --json
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-load <state_id>
```

### Capture A Repro Seed (Draft Entry)
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py smart-save 5
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-save "Zora Temple blackout repro" -t dungeon -t blackout -t repro
```

### Promote To Canon + Regression Guardrail
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-verify <state_id> --by scawful
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py lib-verify-all
```

## Notes
- If a state was captured on an older ROM build, use the in-game cache reload hotkey if needed: `L + R + Select + Start`.
- Use `python3 scripts/mesen2_client.py` for all state library operations.
