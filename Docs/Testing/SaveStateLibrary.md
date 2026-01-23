# Save State Library

This library keeps curated save states for fast testing (room jumps, progress milestones, regression checks).

- **Binary state files (.mss / .srm)** live under `Roms/SaveStates/library/` (local only; `Roms/` is gitignored).
- **Manifest** lives at `Docs/Testing/save_state_library.json` (tracked).

## Common workflows

### Reload runtime caches after loading a state

If a save state was captured on an older ROM build, reload pointers/tables before testing:

- **Hotkey:** `L + R + Select + Start`
- **Effect:** Rebuilds message pointer table (dialog dictionaries) + reloads sprite graphics properties (and overworld/underworld sprite list based on `INDOORS`)

### Save-state sets (10-slot packs)

Use sets to keep **groups of 10 states** that can be swapped into Mesen slots quickly.
By default, sets must define exactly 10 slots (use `--allow-partial` if you really need an incomplete pack).

Create/update a set:

```bash
python3 scripts/state_library.py set-create \
  --set ow_baseline \
  --description "Overworld sanity checks" \
  --slot 1:ow_start_day0 \
  --slot 2:ow_transition_lostwoods_west \
  --slot 3:ow_transition_western_gate \
  --slot 4:ow_lava_island \
  --slot 5:ow_broken_bridge \
  --slot 6:ow_swamp_exit \
  --slot 7:ow_ruins_gate \
  --slot 8:ow_mountain_pass \
  --slot 9:ow_beach_entry \
  --slot 10:ow_market_gate
```

Apply a set to Mesen slots (swap current pack):

```bash
python3 scripts/state_library.py set-apply --set ow_baseline --rom Roms/oos168x.sfc --force
```

List or inspect sets:

```bash
python3 scripts/state_library.py set-list
python3 scripts/state_library.py set-show --set ow_baseline
```

Optional SRM pairing (for consistent SRAM):

```bash
python3 scripts/state_library.py set-create \
  --set zt_water_gate \
  --slot 1:zt_water_gate_pre \
  --slot 2:zt_water_gate_post \
  --srm-id zt_water_gate_pre
```

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

To auto-fill room/link metadata from the live bridge:

```bash
./scripts/mesen_cli.sh state > /tmp/oos_state.json
python3 scripts/state_library.py import \
  --id zt_water_gate_pre \
  --rom Roms/oos168x.sfc \
  --slot 1 \
  --description "Zora Temple room 0x27, pre-switch" \
  --tags dungeon,zora-temple,water-gate \
  --state-json /tmp/oos_state.json
```

`--state-json` currently fills module, room, area, Link state/position, indoors flag, progress bytes (dungeon/side quest), and the current reinit status bits (if present).

### Capture directly from a live Mesen2 session

For now, use a **pre-saved** slot or state file (until `wait-save` is implemented in the CLI).

```bash
# Save manually first (Mesen UI or CLI)
./scripts/mesen_cli.sh savestate ~/Documents/Mesen2/SaveStates/oos168x_1.mss

# Import without triggering a save
python3 scripts/state_library.py capture \
  --id zt_water_gate_pre \
  --rom Roms/oos168x.sfc \
  --state ~/Documents/Mesen2/SaveStates/oos168x_1.mss \
  --description "Zora Temple room 0x27, pre-switch" \
  --tags dungeon,zora-temple,water-gate \
  --no-save
```

Skip triggering a savestate (use an existing slot or state file):

```bash
python3 scripts/state_library.py capture \
  --id zt_water_gate_pre \
  --rom Roms/oos168x.sfc \
  --slot 1 \
  --no-save
```

### Capture an entire 10-slot set

Provide slot/id mapping (recommended for new sets):

```bash
python3 scripts/state_library.py capture-set \
  --set ow_baseline \
  --rom Roms/oos168x.sfc \
  --slot 1:ow_start_day0 \
  --slot 2:ow_transition_lostwoods_west \
  --slot 3:ow_transition_western_gate \
  --slot 4:ow_lava_island \
  --slot 5:ow_broken_bridge \
  --slot 6:ow_swamp_exit \
  --slot 7:ow_ruins_gate \
  --slot 8:ow_mountain_pass \
  --slot 9:ow_beach_entry \
  --slot 10:ow_market_gate
```

**Note:** `capture-set` currently assumes slot files already exist (until `wait-save` is implemented).

Reuse an existing set mapping (captures all slots already listed in the manifest):

```bash
python3 scripts/state_library.py capture-set \
  --set ow_baseline \
  --rom Roms/oos168x.sfc
```

Capture a new set using a different set as the mapping source:

```bash
python3 scripts/state_library.py capture-set \
  --set ow_baseline_2026_01_22 \
  --from-set ow_baseline \
  --rom Roms/oos168x.sfc
```

Per-slot metadata (JSON/YAML) for descriptions/tags/overrides:

```json
{
  "set": { "description": "Overworld sanity checks (January refresh)" },
  "slots": {
    "1": { "description": "Start day 0", "tags": ["overworld", "start"], "label": "Start", "location": "Overworld 0x00" },
    "2": { "id": "ow_transition_lostwoods_west", "tags_extra": ["transition"], "summary": "Lost Woods gate" },
    "3": { "skip": true }
  },
  "ids": {
    "ow_market_gate": { "tags": ["overworld", "market"], "notes": "NPC crowd" }
  }
}
```

```bash
python3 scripts/state_library.py capture-set \
  --set ow_baseline \
  --rom Roms/oos168x.sfc \
  --slot-meta Docs/Testing/ow_baseline_meta.json
```

### Guided capture workflow (interactive)

Create a plan file with entries, then run:

```bash
./scripts/capture_workflow.py --plan Docs/Testing/ow_baseline_plan.json
```

**Planned:** `--snapshot` once `snapshot` is implemented in `mesen_cli.sh`.

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

You can add optional metadata via `--room`, `--area`, `--module`, `--link-state`, `--progress`, `--notes`, `--label`, `--location`, `--summary`, or `--state-json`.
These are stored in the manifest for quick reference.

Optional media snapshots (helpful for visual verification):

```bash
python3 scripts/state_library.py capture \
  --id zt_water_gate_pre \
  --rom Roms/oos168x.sfc \
  --slot 1 \
  --snapshot
```

**Planned:** `--snapshot` depends on `mesen_cli.sh snapshot` (not yet implemented). For now, use `state-json` + `screenshot` manually and attach paths in the manifest.

## Automation roadmap

- Add `wait-save` to the bridge/CLI so `capture`/`capture-set` can auto-save reliably.
- Add `snapshot` (state-json + screenshot) to the CLI for one-call captures.
- Update `capture_workflow.py` to use `wait-save` + `snapshot` once available.
