# Fast Travel and Test Setups (Save-Data Profiles)

Goal: iterate on Oracle of Secrets quickly without hunting through the world or relying on savestates.

These workflows modify the **active savefile mirror in WRAM** (`$7EF000-$7EF4FF`) plus a small amount of non-save convenience state (e.g. currently-selected ocarina song).

`save-data profile-apply` now runs as a transaction by default:
1. Apply profile writes.
2. Verify live WRAM readback.
3. Persist WRAMSAVE -> cart SRAM active slot.
4. Verify persisted SRAM values.

Volatile fields outside WRAMSAVE (for example `$7E030F` selected ocarina song) are still applied and verified live, but are explicitly reported as non-persistent.

## 1) Use Save-Data Profiles (Recommended)

Profiles are JSON loadouts under `Docs/Debugging/Testing/save_data_profiles/`.

List profiles:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-list
```

Apply a profile (auto-pauses/resumes the emulator, persists + verifies by default):
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-apply soaring_debug
```

WRAM-only apply (skip SRAM persistence):
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-apply soaring_debug --no-persist
```

Apply to all three SRAM slots while preserving each slot's own non-item state:
```bash
for s in 1 2 3; do
  MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data sync-from-sram --slot "$s"
  MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-apply all_items_no_progress --slot "$s"
done
```

Capture your current item/flag loadout into a new editable profile:
```bash
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py save-data profile-capture my_loadout --flags --only-nonzero
```

Current built-ins:
- `soaring_debug`: unlock Soaring + select it
- `zora_temple_debug`: convenience loadout for Zora Temple testing
- `all_items_no_progress`: full inventory/equipment without changing progression flags (crystals/pendants/game-state)

Notes:
- Ocarina progression byte is at `$7EF34C` (in the savefile mirror, persisted by default profile apply).
- Selected ocarina song is at `$7E030F` (WRAM-only, intentionally non-persistent).

### 1.1) Rapid Live-Playtest Loop (Build -> Load -> Travel)

Use this loop when actively iterating on OW rendering/sprite regressions and you need fast repositioning:

```bash
# 1) Build and validate
./scripts/build_rom.sh 168
python3 scripts/check_zscream_overlap.py

# 2) Load the fresh ROM in the running Mesen2 instance
python3 scripts/mesen2_client.py rom-load /Users/scawful/src/hobby/oracle-of-secrets/Roms/oos168x.sfc

# 3) Apply fast-travel test profile (transactional apply + persist + verify)
python3 scripts/mesen2_client.py save-data profile-apply soaring_debug

# 4) Verify expected values (Flute=4 persisted, selected song=3 live WRAM)
python3 scripts/mesen2_client.py mem-read 0x7EF34C --len 1
python3 scripts/mesen2_client.py mem-read 0x7E030F --len 1
python3 scripts/mesen2_client.py mem-read 0x034C --len 1 --memtype SRAM
```

Expected readback:
- `0x7EF34C: 04`
- `0x7E030F: 03`
- `0x00034C: 04` (slot 1 SRAM savefile byte for flute)

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
