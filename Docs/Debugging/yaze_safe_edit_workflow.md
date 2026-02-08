# Yaze Safe-Edit Workflow

A step-by-step workflow for safely editing dungeon room data (objects, sprites, collision) in yaze, with backup, diff, validation, and rollback at each stage.

**Use this workflow any time you edit the *base ROM* that `scripts/build_rom.sh` patches** (default: `Roms/oos<ver>_test2.sfc` when present, otherwise `Roms/oos<ver>.sfc`; override with `OOS_BASE_ROM`). ASM-only changes (which go through `build_rom.sh`) don't need this.

---

## 1. Pre-Edit Baseline

Before opening yaze, create a snapshot of the current ROM state.

```bash
# Copy the base ROM as a pre-edit baseline (example: 168)
cp Roms/oos168_test2.sfc Roms/oos168_test2_pre_edit.sfc

# Validate the baseline ROM
../yaze/scripts/z3ed rom-doctor --rom Roms/oos168_test2.sfc

# Optional: validate dungeon data for the rooms you plan to edit
../yaze/scripts/z3ed dungeon-doctor --room 0xA8 --rom Roms/oos168_test2.sfc
../yaze/scripts/z3ed dungeon-doctor --room 0xB8 --rom Roms/oos168_test2.sfc
```

Keep validation output in `/tmp` (do not commit logs/dumps).

---

## 2. Making Edits in Yaze

Open yaze, load the base ROM (example: `Roms/oos168_test2.sfc`), and make your edits (room objects, sprites, collision tiles, etc.).

**Rules while editing:**

- Edit **only the rooms you intend to change**. Don't save global tables unless you're sure that's what you want.
- If yaze has a "save room" vs "save all" option, prefer "save room" to minimize blast radius.
- Custom objects (ID 0x31, 0x32) won't render visually in yaze's canvas — their graphics are drawn by `CustomObjectHandler` at runtime, not by yaze's object renderer. You'll see blank tiles where track objects are. This is normal.
- OOS uses relocated dungeon data tables. If yaze shows unexpected graphics or palette errors, check the project config for graphics pointer overrides.

---

## 3. Post-Edit Validation

After saving in yaze, validate your changes before rebuilding.

### 3a. ROM Diff (What Changed?)

```bash
# Compare against the pre-edit baseline
../yaze/scripts/z3ed rom-compare --rom Roms/oos168_test2.sfc --baseline Roms/oos168_test2_pre_edit.sfc
```

**Check that:**
- Changes are in dungeon data regions (typically `$028000`-`$0B7FFF` for room headers/objects/sprites)
- No unexpected changes outside the rooms you edited
- The diff is reasonable in size (a few room edits = a few hundred bytes changed)

### 3b. Dungeon Data Validation

```bash
# Validate the rooms you edited
../yaze/scripts/z3ed dungeon-doctor --room 0xA8 --rom Roms/oos168_test2.sfc
../yaze/scripts/z3ed dungeon-doctor --room 0xB8 --rom Roms/oos168_test2.sfc

# Full ROM integrity check
../yaze/scripts/z3ed rom-doctor --rom Roms/oos168_test2.sfc
```

**Check for:**
- Object count didn't unexpectedly increase/decrease
- No sprite overflow warnings
- No room data corruption

### 3c. Graphics Validation (Optional)

```bash
# If you changed tileset-related data
../yaze/scripts/z3ed graphics-doctor --rom Roms/oos168_test2.sfc
```

---

## 4. Rebuild with ASM Patches

`scripts/build_rom.sh` copies a base ROM to `Roms/oos<ver>x.sfc` and then applies ASM patches.

Recommended workflow:
- Keep `Roms/oos<ver>.sfc` as your clean baseline.
- Use `Roms/oos<ver>_test2.sfc` as your editable base (this is the default base ROM when present).

Rebuild (example: 168):
```bash
./scripts/build_rom.sh 168
```

If you *accidentally* edited `Roms/oos168x.sfc` (the build output) instead of the base ROM, you can persist the edits by copying them into the base and rebuilding:
```bash
cp Roms/oos168x.sfc Roms/oos168_test2.sfc
./scripts/build_rom.sh 168
```

---

## 5. Runtime Verification

After rebuilding, test in the emulator:

```bash
# Launch the ROM
~/src/tools/emu-launch -m Roms/oos168x.sfc

# Or via Mesen2 with debug overlays
python3 scripts/mesen2_client.py ping
python3 scripts/mesen2_client.py run-state
```

**Test checklist:**
- [ ] Enter each edited room — no crash, no black screen
- [ ] Objects render correctly (track tiles visible)
- [ ] Sprites spawn in expected positions
- [ ] Door transitions work (enter/exit room)
- [ ] Collision behaves correctly (walk on tracks, fall in pits)
- [ ] No regressions in adjacent rooms

---

## 6. Rollback

If something went wrong:

```bash
# Restore the pre-edit base ROM (example: 168)
cp Roms/oos168_test2_pre_edit.sfc Roms/oos168_test2.sfc

# Rebuild clean
./scripts/build_rom.sh 168
```

---

## Known Risks

| Risk | Mitigation |
|------|------------|
| Custom objects (0x31/0x32) don't render in yaze | Normal — they render at runtime via `CustomObjectHandler`. Use z3ed to verify object data. |
| Global table saves affect other rooms | Use `rom-compare` to verify diff is scoped to target rooms only. Prefer "save room" over "save all" in yaze. |
| OOS relocated tables cause graphics glitches | Check yaze project config for graphics pointer overrides matching OOS's custom table locations. |
| Collision editor doesn't show custom tile types | Stop tiles (B7-BA), switch corners (D0-D3) exist as collision data but may display as unknown in yaze's UI. Verify via z3ed or runtime testing. |
| Build script overwrites oos168x.sfc | Always copy yaze edits to `oos168.sfc` (the base ROM) before rebuilding if you want them to persist. |

---

## Quick Reference

```bash
# Full safe-edit cycle (one-liner summary)
cp Roms/oos168_test2.sfc Roms/oos168_test2_pre_edit.sfc          # 1. Backup
# ... edit in yaze ...
../yaze/scripts/z3ed rom-compare --rom Roms/oos168_test2.sfc \
  --baseline Roms/oos168_test2_pre_edit.sfc                   # 3. Diff
../yaze/scripts/z3ed dungeon-doctor --room 0xA8 --rom Roms/oos168_test2.sfc  # 3. Validate
./scripts/build_rom.sh 168                                # 4. Rebuild
```
