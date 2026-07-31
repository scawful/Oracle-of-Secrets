# Dungeon data sources

`custom_collision.json` is the canonical, tracked source for Oracle's
editor-authored dungeon custom collision. The unpatched base ROM remains the
edit target; `oos168x.sfc` is disposable build output and must never be edited.

The build validates both the JSON format and the effective nonzero collision
maps in the selected base ROM before generating tables or invoking Asar. A
mismatch fails closed with the affected room.

## Current provenance

The source was recovered and read back on 2026-07-31 from the existing local
ROM state:

- source: 18 rooms, 2,491 nonzero tiles
- source SHA-256:
  `af221afd9226b4d321155135899a5208cc86badac58f7f1af195a725495e49bc`
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
