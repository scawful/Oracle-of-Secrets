# Fast Travel and Test Setups (Save-Data Profiles)

Goal: iterate on Oracle of Secrets quickly without hunting through the world or relying on savestates.

These workflows modify the **active savefile mirror in WRAM** (`$7EF000-$7EF4FF`) plus a small amount of non-save convenience state (e.g. currently-selected ocarina song).

Why WRAM? ALTTP-style save data is staged in WRAM while playing; patching WRAM is safe and immediate, and you can persist it by doing an in-game save.

## 1) Use Save-Data Profiles (Recommended)

Profiles are JSON loadouts under `Docs/Debugging/Testing/save_data_profiles/`.

List profiles:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-list
```

Apply a profile (auto-pauses/resumes the emulator):
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-apply soaring_debug
```

Capture your current item/flag loadout into a new editable profile:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-capture my_loadout --flags --only-nonzero
```

Current built-ins:
- `soaring_debug`: unlock Soaring + select it
- `zora_temple_debug`: convenience loadout for Zora Temple testing

Notes:
- Ocarina progression byte is at `$7EF34C` (in the savefile mirror).
- Selected ocarina song is at `$7E030F` (WRAM, not persisted unless you save/restore it yourself).

## 2) Save-Data Snapshot Library (Like Savestates, But For Save Variables)

You can snapshot/restore the full savefile block (`$7EF000-$7EF4FF`) into the repo library `Roms/SaveData/library/` with a manifest at `Docs/Debugging/Testing/save_data_library.json`.

Save the current save-data block:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data lib-save "zora temple pre-darkroom" -t zora-temple -t debug
```

List entries:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data lib-list
```

Restore an entry into WRAM:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data lib-load <entry_id>
```

After restoring: do an in-game save if you want it persisted into actual SRAM.

## 2.1) `.srm` Import/Export + Hot Reload (Cart SRAM)

USDASM `SaveGameFile` writes the active save block (`$7EF000-$7EF4FF`) into cart SRAM and computes the inverse checksum at `$7EF4FE`.

Dump the cartridge SRAM (8192 bytes) to a `.srm`:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data srm-dump /tmp/oos.srm
```

Load a `.srm` into the emulator, and hot-load the active save slot into WRAM (immediate effect):
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data srm-load /tmp/oos.srm --hot
```

Persist your current WRAM save variables into cart SRAM (main + mirror copies) without going through in-game menus:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data sync-to-sram
```

If you've been patching items/flags and want a consistent checksum:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data repair-checksum
```

## 3) When To Use Savestates Anyway

Use SRAM-first unlocks to make the in-game world traversal itself fast:
- apply a save-data profile (items/flags)
- then create a single "one action away" seed in the **state library** for deterministic repro (blackouts, hooks, etc.)

This keeps your primary save "real" while still enabling deterministic agent testing.

## 4) About `warp` (Not A Replacement)

The CLI includes `warp`, but **cross-area warps are not supported by default** (the ROM-integrated warp handler is not currently active).

- Same-area teleport is safe:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py warp --area 0x40 --x 0x02E8 --y 0x0213
```

- Cross-area warp will refuse unless you pass `--force` (unsafe) or `--rom` (requires a ROM feature that is not enabled by default).
