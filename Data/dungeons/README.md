# Dungeon data sources

`custom_collision.json` is the canonical, tracked source for Oracle's
editor-authored dungeon custom collision. The unpatched base ROM remains the
edit target; `oos168x.sfc` is disposable build output and must never be edited.

The build validates both the JSON format and every explicit collision record
in the selected base ROM before generating tables or invoking Asar. An encoded
`$00` is a floor override, distinct from an absent record. A mismatch fails
closed with the affected room. The build does not import or regenerate this
JSON. Collision editing/export tools must preserve explicit floor records;
older nonzero-only tools do not satisfy this contract.

## Current provenance

Room `$27`'s western ladder approach uses two `$F5` fill markers at offsets
`$0A1A/$0A1B`, replacing redundant `$08` overrides. Dry collision remains native;
the generated reservoir table fills 224 cells instead of 222. The exact base
patch is `Data/rom_patches/zora27_west_ladder_fill_current8d_2026-10-27.json`.

- source: 20 rooms, 3,191 explicit tiles (3,095 nonzero and 96 floor tiles)
- source SHA-256:
  `36777aaa2e344f9f70fba85a7700cd51f515d569a72affddf9d6abf4994e9d2f`
- matching private edit base SHA-256:
  `88e542598b11755f631947aa6c581b2e5fd1f70a5a4454c03d4d5c9919751e2c`

The recipe reads current base SHA-256
`8d6157840e402f98d5c4b1d61da90be072531fa661bc1608ae0eeab1b898e721`.
Its schema-2 tool defaults to dry-run and creates exclusive private outputs only
with `--write-output`; it never changes the input. The recipe's source pin names
the preserved pre-fold candidate (HEAD `8b004e65` plus diff `08581f85`), not the
folded PR head. The historical e756 recipe remains in branch history.

Shared-base application remains pending scawful's approval. After that decision,
scawful's apply step copies the qualified private image to the shared base.
The source must be built with its matching base; the validator rejects the
unmigrated shared base.

The preceding safe-rails source is retained as history:

The 2026-10-18 Goron Mines safe-rails fix (scawful: "Safe rails first: fix the 313 derail
tiles in the 7 rooms, no layout change.") gives every lane tile of a plain straight rail
piece in rooms `$77`, `$89`, `$97`, `$98`, `$B9`, `$D7` and `$D8` an explicit straight:
`$B0` on horizontal pieces and `$B1` on vertical ones (313 cells). There the drawn rail's
default `$BB`/`$BC` T-junction collision could turn a cart off the rail. Existing cells,
objects and sprites are unchanged (AFS recipe
`handoffs/goron_mines_redesign_2026-10-18/safe_rails/recipe/apply_safe_rails.py`).

- source: 20 rooms, 3,191 explicit tiles (3,095 nonzero and 96 floor tiles)
- source SHA-256:
  `13342cd4fc8f719e6c502ada53225dd55df8dcd73f299db02fd42b1288c85514`
- matching edit base SHA-256 (base `aea93a28` plus the safe-rails recipe):
  `c602022261d4d93e7d18f9abbd1f80f3ab2705b55a35dd57e7f2bdc6f7aeea6c`

The 2026-10-18 Goron Mines `$87`/`$77` redesign is retained as history (scawful's picks:
"2. Lever steers (Recommended)", "A. Wall + main deck chest (Recommended)", "Piece of
Heart (Recommended)"). It lets the cart ride from room `$87` north into room `$77`. Room `$87`'s (44,6) stop becomes a
`$B1` rail. Room `$77` gains the switch tile `$D0` at (44,38), under its lever-set switch track,
and 69 straight-rail cells on the cart's paths. The same change edits `$77`'s objects, sprites
and chest record and two other small-key sources in the base ROM (AFS recipe
`handoffs/cart_087_077_2026-10-18/recipe_v2/apply_087_077_v2.py`).

- source: 20 rooms, 2,878 explicit tiles (2,782 nonzero and 96 floor tiles)
- source SHA-256:
  `f8692c1f7fb7ccd31b79394685030fa896d57c485599647f5733c25a0c50799e`
- matching edit base SHA-256 (base `4505fe0a` plus the v2 recipe):
  `aea93a2823d982eeff366c4e8c00d5a16254880e272200075872e8af1ba565f8`

The 2026-10-12 approved Shrine of Power restore is retained as history. It kept
all prior room entries and restored rooms `$83` and `$84` from their surviving
original streams.
Room `$83` has 74 explicit floor cells and 12 `$FF` cells; room `$84` has two
`$08` cells. Room `$74`'s 22 floor cells were already present in the ROM and
are now represented in the source without changing that room's ROM data.

- source: 20 rooms, 2,808 explicit tiles (2,712 nonzero and 96 floor tiles)
- source SHA-256:
  `a7715d48f4bc86664bfa2145f78c18bd019c6d499121a2416db231e4d72ed7e8`
- matching restored beta edit-base SHA-256:
  `6f2d0a42af02388d8d3d5f0f9cf20fc83c3eb3a541732b8da482da1fb09497ec`

The prior nonzero-only September synchronization is retained as history:

- source: 17 rooms, 2,698 nonzero tiles
- source SHA-256:
  `04f5370953be0d299bc8d2fb589e9253eb811994596665d818936cbf46eebf99`
- matching base ROM SHA-256:
  `41fa52b81d63b7e6d0405a8df5a80882e1d9eb26bda4e038148ddc27dee3a096`

The original 2026-07-31 recovery evidence is retained for history:

- pre-recovery base ROM SHA-256:
  `d289b2408c3ccc312abeadf274f04f475106034fcab8ebff3f307fd229db4799`
- recovered patched ROM SHA-256:
  `fc234d88edeaed676a9cca14f319847dccc172caa11b45894c95953dd9ff9b0f`
- the effective base/patched drift was limited to rooms `0x27`, `0xA8`, and
  `0xB8`; the other 15 tracked room maps already matched
- importing this source into a copy of that base produced SHA-256
  `b13ef69ede313756dcf560bf0f993663d68d0365609f2c20dcdec2c17f31f7b9`

These ROM hashes are recovery evidence, not permanent build requirements. The
tracked JSON and validator are the durable contract.

## Safe base-ROM synchronization

First check whether synchronization is needed:

```bash
python3 Scripts/Generate/validate_custom_collision_source.py \
  --root . --rom Roms/oos168.sfc
```

If that succeeds, **stop**. Do not import an already-matching source. The
current yaze writer appends freshly encoded blobs for every listed room instead
of reclaiming the previous blobs. This source encodes 7,545 bytes per write;
the proven recovered base has 14,112 bytes free after its first import, so
unnecessary repeated imports can exhaust the collision bank.

If validation reports expected source drift, use a freshly built `z3ed` from a
yaze worktree that contains transactional persistence commit `39c4b5a08` or a
descendant. Set `YAZE_ROOT` explicitly; do not rely on whichever binary a
different checkout's wrapper happens to select.

```bash
YAZE_ROOT=/absolute/path/to/current/yaze-worktree
git -C "$YAZE_ROOT" merge-base --is-ancestor 39c4b5a08 HEAD || {
  echo "ERROR: selected yaze source predates transactional collision saves" >&2
  exit 1
}
(cd "$YAZE_ROOT" && cmake --preset mac-ai && \
  cmake --build --preset mac-ai --target z3ed -j 8)

Z3ED="$YAZE_ROOT/build/presets/mac-ai/bin/Debug/z3ed"
test -x "$Z3ED"
```

Run the no-write preflight and inspect its machine-readable result:

```bash
"$Z3ED" dungeon-import-custom-collision-json \
  --rom Roms/oos168.sfc \
  --in Data/dungeons/custom_collision.json \
  --dry-run \
  --report /tmp/oos-custom-collision-import.json \
  --format json
jq -e '.status == "success" and .mode == "dry-run"' \
  /tmp/oos-custom-collision-import.json
```

Before touching the canonical base, prove the selected binary's persistence,
required-backup, and readback behavior on a disposable copy:

```bash
rehearsal_dir="$(mktemp -d /tmp/oos-collision-sync.XXXXXX)"
cp -p Roms/oos168.sfc "$rehearsal_dir/oos168.sfc"
before="$(shasum -a 256 "$rehearsal_dir/oos168.sfc" | awk '{print $1}')"
"$Z3ED" dungeon-import-custom-collision-json \
  --rom "$rehearsal_dir/oos168.sfc" \
  --in Data/dungeons/custom_collision.json \
  --format json
after="$(shasum -a 256 "$rehearsal_dir/oos168.sfc" | awk '{print $1}')"
test "$before" != "$after"
find "$rehearsal_dir" -maxdepth 1 \
  -name 'oos168.sfc_backup_*' -print -quit | grep -q .
python3 Scripts/Generate/validate_custom_collision_source.py \
  --root . --rom "$rehearsal_dir/oos168.sfc"
"$Z3ED" dungeon-export-custom-collision-json \
  --rom "$rehearsal_dir/oos168.sfc" \
  --all \
  --out "$rehearsal_dir/readback.json" \
  --format json
cmp Data/dungeons/custom_collision.json "$rehearsal_dir/readback.json"
```

Only after every rehearsal check succeeds, perform the one required write to
the unpatched base. Write mode is the default when `--dry-run` is absent; the
transaction creates a required backup and atomically saves the ROM.

```bash
"$Z3ED" dungeon-import-custom-collision-json \
  --rom Roms/oos168.sfc \
  --in Data/dungeons/custom_collision.json \
  --format json

# Reopen/read back and prove exact source parity before doing anything else.
"$Z3ED" dungeon-export-custom-collision-json \
  --rom Roms/oos168.sfc \
  --all \
  --out /tmp/oos-custom-collision-readback.json \
  --format json
cmp Data/dungeons/custom_collision.json \
  /tmp/oos-custom-collision-readback.json
python3 Scripts/Generate/validate_custom_collision_source.py \
  --root . --rom Roms/oos168.sfc
```

The pre-sync `oos168x.sfc` is stale disposable output whose raw collision-bank
packing no longer matches the synchronized base. GM-005 intentionally compares
those raw bytes, so archive the old output by moving it out of the canonical
name before the first rebuild. Do not edit it and do not use
`OOS_ALLOW_EDIT_OVERWRITE=1` to bypass this recovery step.

```bash
if [[ -f Roms/oos168x.sfc ]]; then
  archive_dir="$HOME/Documents/OracleOfSecrets/Roms"
  mkdir -p "$archive_dir"
  stamp="$(date +%Y%m%d-%H%M%S)"
  mv Roms/oos168x.sfc \
    "$archive_dir/oos168x_pre-collision-source-sync_${stamp}.sfc"
fi
Scripts/Build/build_rom.sh 168
```

Never add `--replace-all --force` to the normal synchronization flow. That mode
clears unlisted rooms and is reserved for an explicitly reviewed destructive
replacement.

## Updating the source

After deliberate collision edits to the unpatched base, export to a temporary
file first, inspect the diff, and only then replace the tracked source:

```bash
"$Z3ED" dungeon-export-custom-collision-json \
  --rom Roms/oos168.sfc \
  --all \
  --out /tmp/custom_collision.json \
  --format json
diff -u Data/dungeons/custom_collision.json /tmp/custom_collision.json
cp /tmp/custom_collision.json Data/dungeons/custom_collision.json
python3 Scripts/Generate/validate_custom_collision_source.py \
  --root . --rom Roms/oos168.sfc
```
