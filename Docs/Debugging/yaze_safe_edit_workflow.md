# Yaze Safe-Edit Workflow

A step-by-step workflow for safely editing dungeon room data (objects, sprites, collision) in yaze, with backup, diff, validation, and rollback at each stage.

**Use this workflow any time you edit the *base ROM* that
`Scripts/Build/build_rom.sh` patches** (default: `Roms/oos<ver>.sfc`;
override with `OOS_BASE_ROM`). ASM-only changes that go through the build
script do not need a separate yaze save.

---

## 1. Pre-Edit Baseline

Before opening yaze, create a snapshot of the current ROM state.

```bash
# Copy the base ROM as a pre-edit baseline (example: 168)
cp Roms/oos168.sfc Roms/oos168_pre_edit.sfc

# Validate the baseline ROM
../yaze/scripts/z3ed rom-doctor --rom Roms/oos168.sfc

# Optional: validate dungeon data for the rooms you plan to edit
../yaze/scripts/z3ed dungeon-doctor --room 0xA8 --rom Roms/oos168.sfc
../yaze/scripts/z3ed dungeon-doctor --room 0xB8 --rom Roms/oos168.sfc
```

Keep validation output in `/tmp` (do not commit logs/dumps).

---

## 2. Making Edits in Yaze

Open `Oracle-of-Secrets.yaze`, not the ROM or the patched output directly. The
project must resolve its editable target to `Roms/oos168.sfc`, its build target
to `Roms/oos168x.sfc`, and its guarded-save manifest to
`Roms/hack_manifest.json`.

`Roms/hack_manifest.json` is generated and intentionally untracked. After a
fresh checkout, or if the manifest is missing, bootstrap it by rebuilding once
from the standard editable ROM before opening yaze:

```bash
./Scripts/Build/build_rom.sh 168
```

The build prefers `Roms/oos168.sfc`, refreshes `Roms/oos168x.sfc`, and records
the exact dev/patched hashes in the generated manifest. Do not reuse an older
patched output as proof of build provenance.

Before editing, verify the project bundle from the yaze checkout:

```bash
../yaze/build/presets/mac-ai/bin/Debug/z3ed project-bundle-verify \
  --project Oracle-of-Secrets.yaze --check-rom-hash --format=json
```

**Rules while editing:**

- Edit **only the rooms you intend to change**. Don't save global tables unless you're sure that's what you want.
- Keep autosave, Dungeon Maps, and Graphics Sheet saving disabled for the
  current OOS daily-driver profile.
- If yaze has a "save room" vs "save all" option, prefer "save room" to minimize blast radius.
- Custom objects (ID 0x31, 0x32) won't render visually in yaze's canvas — their graphics are drawn by `CustomObjectHandler` at runtime, not by yaze's object renderer. You'll see blank tiles where track objects are. This is normal.
- OOS uses relocated dungeon data tables. If yaze shows unexpected graphics or palette errors, check the project config for graphics pointer overrides.

---

## 3. Post-Edit Validation

After saving in yaze, validate your changes before rebuilding.

### 3a. ROM Diff (What Changed?)

```bash
# Compare against the pre-edit baseline
../yaze/scripts/z3ed rom-compare --rom Roms/oos168.sfc --baseline Roms/oos168_pre_edit.sfc
```

**Check that:**
- Changes are in dungeon data regions (typically `$028000`-`$0B7FFF` for room headers/objects/sprites)
- No unexpected changes outside the rooms you edited
- The diff is reasonable in size (a few room edits = a few hundred bytes changed)

### 3b. Dungeon Data Validation

```bash
# Validate the rooms you edited
../yaze/scripts/z3ed dungeon-doctor --room 0xA8 --rom Roms/oos168.sfc
../yaze/scripts/z3ed dungeon-doctor --room 0xB8 --rom Roms/oos168.sfc

# Full ROM integrity check
../yaze/scripts/z3ed rom-doctor --rom Roms/oos168.sfc
```

**Check for:**
- Object count didn't unexpectedly increase/decrease
- No sprite overflow warnings
- No room data corruption

### 3c. Graphics Validation (Optional)

```bash
# If you changed tileset-related data
../yaze/scripts/z3ed graphics-doctor --rom Roms/oos168.sfc
```

---

## 4. Rebuild with ASM Patches

`Scripts/Build/build_rom.sh` copies a base ROM to `Roms/oos<ver>x.sfc`, applies
ASM patches, and regenerates `Roms/hack_manifest.json` with current ROM hashes
and hook ownership.

Recommended workflow:
- Keep `Roms/oos<ver>.sfc` as your clean baseline.
- Use `Roms/oos<ver>.sfc` as your editable base (this is the default base ROM when present).

Rebuild (example: 168):
```bash
./Scripts/Build/build_rom.sh 168
```

Never copy `Roms/oos168x.sfc` over the editable base. If the patched output was
edited accidentally, discard it, restore the base from a known backup, and
reapply only the intended edits through the project or verified `z3ed`
commands.

---

## 5. Runtime Verification

After rebuilding, test in the emulator:

```bash
# Launch the ROM
~/src/tools/emu-launch -m Roms/oos168x.sfc

# Or via Mesen2 with debug overlays
python3 Scripts/Mesen2/mesen2_client.py health
python3 Scripts/Mesen2/mesen2_client.py run-state
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
cp Roms/oos168_pre_edit.sfc Roms/oos168.sfc

# Rebuild clean
./Scripts/Build/build_rom.sh 168
```

---

## Known Risks

| Risk | Mitigation |
|------|------------|
| Custom objects (0x31/0x32) don't render in yaze | Normal — they render at runtime via `CustomObjectHandler`. Use z3ed to verify object data. |
| Global table saves affect other rooms | Use `rom-compare` to verify diff is scoped to target rooms only. Prefer "save room" over "save all" in yaze. |
| OOS relocated tables cause graphics glitches | Check yaze project config for graphics pointer overrides matching OOS's custom table locations. |
| Collision editor doesn't show custom tile types | Stop tiles (B7-BA), switch corners (D0-D3) exist as collision data but may display as unknown in yaze's UI. Verify via z3ed or runtime testing. |
| Tool accidentally writes to oos168x.sfc | Open `Oracle-of-Secrets.yaze`; its `write_policy=block` protects the build target. All edits and writes must target `oos168.sfc`. |

---

## Quick Reference

```bash
# Full safe-edit cycle (one-liner summary)
cp Roms/oos168.sfc Roms/oos168_pre_edit.sfc          # 1. Backup
# ... edit in yaze ...
../yaze/scripts/z3ed rom-compare --rom Roms/oos168.sfc \
  --baseline Roms/oos168_pre_edit.sfc                   # 3. Diff
../yaze/scripts/z3ed dungeon-doctor --room 0xA8 --rom Roms/oos168.sfc  # 3. Validate
./Scripts/Build/build_rom.sh 168                          # 4. Rebuild
```
