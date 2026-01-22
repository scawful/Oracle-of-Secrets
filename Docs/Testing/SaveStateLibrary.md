# Save State Library

This library keeps curated save states for fast testing (room jumps, progress milestones, regression checks).

- **Binary state files (.mss / .srm)** live under `Roms/SaveStates/library/` (local only; `Roms/` is gitignored).
- **Manifest** lives at `Docs/Testing/save_state_library.json` (tracked).

## Common workflows

### Import a Mesen2 save state into the library

```bash
python3 scripts/state_library.py import \
  --id zt_water_gate_pre \
  --rom Roms/oos168x.sfc \
  --slot 1 \
  --description "Zora Temple room 0x27, pre-switch" \
  --tags dungeon,zora-temple,water-gate \
  --room 0x27 --module 0x07 --link-state 0x00
```

### Export a library state back to Mesen2

```bash
python3 scripts/state_library.py export --id zt_water_gate_pre --rom Roms/oos168x.sfc --slot 1
```

### Verify library

```bash
python3 scripts/state_library.py verify --rom Roms/oos168x.sfc
```

## Suggested state taxonomy

Use consistent IDs and tags to keep the library searchable:

- **overworld/start**: `ow_start_day0`
- **overworld/edge cases**: `ow_transition_lostwoods_west`
- **dungeon/entrance**: `d5_entrance`
- **dungeon/boss**: `d5_boss_ready`
- **feature-specific**: `zt_water_gate_pre`, `zt_water_gate_post`

## Metadata fields

You can add optional metadata via `--room`, `--area`, `--module`, `--link-state`, `--progress`, `--notes`.
These are stored in the manifest for quick reference.
