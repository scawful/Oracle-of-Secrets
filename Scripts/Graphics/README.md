# Indexed sprite poses

`sprite_pose.js` turns a self-contained JSON recipe into indexed poses, individual
PNGs, a contact sheet, and a labelled segment atlas. It uses Node's standard
library. It does not read a ROM or write game assets.

## First preview

Run from the repository root with Node 18 or newer. The output directory must be
new, and its parent must already exist.

```sh
node Scripts/Graphics/sprite_pose.js --help
node Scripts/Graphics/sprite_pose.js \
  --recipe Scripts/Graphics/examples/tiny.recipe.json \
  --out /tmp/sprite-pose-tiny-v1
```

The tiny example is 6×5, with four palette entries and transparent index 2.
Index 0 remains an opaque color. This demonstrates that dimensions, colors and
transparency belong to the recipe.

```sh
node Scripts/Graphics/sprite_pose.js \
  --recipe Scripts/Graphics/examples/ganondorf-three-pose.recipe.json \
  --out /tmp/sprite-pose-ganondorf-v1
```

The second recipe reproduces the three approved Ganondorf poses exactly. It
contains its original indexed source, all rectangle definitions, transforms,
clips, ankle repairs, protected feet, and expected pixel hashes. It has no
external art-file or AFS dependency.

Outputs are `source.png`, `pose-<name>.png`, `contact.png`, `atlas.png`, and
`poses.json`. Individual PNGs retain transparent pixels and square integer
scaling. The JSON retains the palette indices and reports actual placements,
source/destination anchors, clipping counts, ownership and pixel hashes.

`--scale 1..32` changes preview size. Add `--gif` only when a sequence GIF is
wanted and `ffmpeg` is already on `PATH`. Nothing is installed. Sequence ticks
are nominal; GIF delays have format-level rounding. Existing output directories
and input files are never overwritten, and there is no force flag.

## Make a recipe for another sprite

1. Copy the tiny recipe to a new JSON file. Set `width`, `height`, `palette`,
   `transparentIndex`, and the row-major flat `pixels` array from the original
   indexed sprite. Keep an unchanged `base` pose.
2. Define anatomical rectangles and inspect `atlas.png` before animating. Every
   opaque source pixel must have one owner. Split shared trim or seams explicitly
   so cloth motion cannot move armor or a face segment cannot retain a shoulder.
3. Add a small set of named poses using integer cluster offsets or destinations.
   Reuse those poses when reversing the motion. Inspect `contact.png` and record
   any local join repairs in the recipe.
4. Protect anchors that must stay fixed. After visual approval, record each
   approved pose's `pixelSha256` under `expectedPixelSha256`. Replaying that recipe
   then fails if a pixel changes.

This tool exports authoring arrays. Tile packing, draw tables and runtime timing
remain separate integration work.

## Source and rectangle contract

| Field | Meaning |
|---|---|
| `schema` | Required version `1`; other or missing versions fail. |
| `width`, `height` | Positive integers, at most 1,048,576 source pixels total. |
| `palette` | 1–256 RGB triplets, each channel an integer 0–255. |
| `transparentIndex` | Palette entry treated as transparent; it need not be zero. |
| `pixels` | Exactly `width * height` valid palette indices, row by row. |

Each entry in `segments` has an `id`, a rectangle `[x,y,width,height]`, and an
optional integer `priority`, `label`, `anchor`, or destination `clip` rectangle.
Coordinates are zero-based and half-open: `x <= pixelX < x+width` and
`y <= pixelY < y+height`. Segment and clip rectangles must fit the canvas.
An `anchor` is a source coordinate reference, not an extra transform.

Overlapping rectangles are allowed. A higher priority owns the original opaque
pixel. The later listed segment wins equal-priority ties. Transparent cells have
no owner. Every opaque source pixel must be covered. The atlas grays the complete
source and colors only the pixels exclusively owned by each segment.

`layerOrder`, when present, must name every segment exactly once. It controls
destination occlusion independently of source ownership. All clusters are
extracted from the immutable original first. Each output starts transparent, so
a moved arm cannot leave its original shoulder behind. Later layers paint over
earlier layers; transparent source cells never erase another layer.

## Pose contract

`poses` maps names to objects. Each pose may have a `default` transform and
named overrides under `segments`. Supported transform fields are:

| Field | Meaning |
|---|---|
| `dx`, `dy` | Integer offsets from the segment's source rectangle; default zero. |
| `to` | Absolute destination `[x,y]` for the source rectangle's top-left. Use on a named segment instead of its own `dx`/`dy`. |
| `rotation` | `0` or `180`, rotating within the source rectangle; no scaling. |
| `clip` | Explicit destination rectangle authorizing discarded pixels outside it. Overrides the segment's clip. |
| `repairs` | Pose-level `{x,y,index,reason}` entries, applied after clusters. |

Example:

```json
{
  "default": {"dx": 0, "dy": -1},
  "segments": {
    "foot_left": {"dx": 0, "dy": 0},
    "hand_right": {"to": [25, 7], "rotation": 180}
  },
  "repairs": [{"x": 11, "y": 31, "index": 4, "reason": "ankle join"}]
}
```

Absent an explicit clip, a transformed pixel outside the canvas fails. A clip
discards pixels outside its rectangle before writing. Repairs must use valid
canvas coordinates and palette indices. Unknown segments and transform fields
fail rather than silently ignoring a typo.

| Validation/timing field | Meaning |
|---|---|
| `baselinePose` | Named pose that must replay the source pixel array exactly. |
| `protectedRegions` | Array of `{rect, poses?}` checked against original source after all transforms and repairs; omitted `poses` means every pose. Changes fail. |
| `expectedPixelSha256` | Optional pose/hash map; SHA256 of one byte per palette index, independent of JSON formatting or metadata. |
| `sequence` | Optional `{pose,ticks}` steps using already named poses. |
| `tickRate` | Integer ticks per second, default 60. Timing is author-defined, not inferred from game code. |

## Focused verification

```sh
quiet-build -- node --test Tests/graphics/sprite_pose.test.js
```

Tests replay all three approved pixel hashes, a different-size/nonzero-transparent
fixture, overlap priorities, destination layers, old-shoulder removal, clips,
repairs, protected regions, input immutability, PNG palette/transparency and CLI
output safety. No emulator, ROM build, package installation or image service is
required.

## Normalize a raster source

`normalize_sprite.py` accepts a PNG and a target JSON file. It uses Pillow;
there is no ROM access, tile packing, dithering, or art generation.

```sh
python3 Scripts/Graphics/normalize_sprite.py --source input.png --spec target.json --out new-normalized
```

The output directory must be new. It contains `indexed.png` (mode **P**, palette
index 0 transparent) and `report.json`. Each source box has its original color
counts, sampled color-to-index counts, size change, maximum RGB Euclidean error,
colors above `close_match_error`, and indexed-pixel SHA256. Resizing is NEAREST.
Palette ties use the order in `allowed_indices`. Alpha below 192 becomes index0;
`alpha_threshold` can explicitly change that cutoff. No color index is masked
or silently truncated to fit 3bpp or 4bpp.

```json
{
  "bpp": 3,
  "palette": "palette.hex.json",
  "cell_size": [16, 24],
  "columns": 1,
  "close_match_error": 32,
  "boxes": [
    {"id": "idle", "source_box": [0, 0, 128, 192], "allowed_indices": [1, 2, 3, 4, 5, 6, 7]}
  ]
}
```

`source_box` is half-open `[x,y,width,height]`, measured in source pixels. Each
box resizes to `cell_size` and is placed in row order. `palette` is relative to
the spec: a `.bin` file of little-endian BGR555 words, or a JSON array of
`"#RRGGBB"`/`"RRGGBB"` strings. Hex colors round to BGR555 and back, matching the
retained `prepare_sources.py` converter. A palette exceeding the target depth,
a high bit in a BGR555 word, or an invalid allowed index is an error.

## Describe frames and states with a rig

An optional `rig` object extends the existing schema1 recipe. Existing recipes
keep their old behavior. Run the portable non-boss fixture without any ROM,
absolute input path, or boss-specific dependency:

```sh
node Scripts/Graphics/sprite_pose.js --recipe Scripts/Graphics/examples/non-boss.rig.recipe.json --out new-rig --gif
node --test Tests/graphics/sprite_pose.test.js Tests/graphics/sprite_rig.test.js
python3 Tests/graphics/normalize_sprite_test.py
```

A rig has `schema:1`, `frames`, `states`, and an indexed `reference` image with
`name` and `source` provenance. Use a native-size Link extraction for actual art
comparisons. The portable fixture deliberately uses a synthetic 1x2 reference.
Optional `reference.feet` controls its baseline; otherwise the bottom row does.

Each named frame chooses exactly one input: `pose` (an evaluated recipe pose),
`pixels` (a same-canvas indexed array), or `alias_of` (another rig frame). Aliases
inherit pixels and metadata; cycles and missing names fail. Alias names remain
visible in the contact sheet and GIF. Metadata can be overridden explicitly.

Every resolved frame must provide:

- `parts`: unique IDs with `kind`, a half-open `[x,y,width,height]` rectangle and
  an optional rectangle-sized 0/1 mask. Kinds are `head`, `hair`, `face`, `arms`,
  `cape`, `armor`, `weapon`, `projectile`, `shadow`, and `unknown`. Use `unknown`
  for unresolved pixels. Every opaque pixel needs at least one classification;
  nested labels such as face within head may overlap.
- `anchor`, `feet`, `hand`, `projectile_origin`: integer `[x,y]` points, or `null`
  when unknown. `feet` aligns each contact image with the reference. Projectile
  origins may lie beyond the visible canvas.
- `hurtbox`: `[x,y,width,height]`, or `null` when unknown. This is source geometry,
  not an editor/gameplay change. It may extend beyond the visible art; it is
  never clipped to make a guessed box fit.

A state has `source` provenance and an ordered `sequence` of `{frame,ticks}`.
`notes` can describe phase inputs, conditional exits and unbounded holds. Keep
those conditions explicit: a bounded source timer window does not establish
that every runtime visit reaches its end. The engine does not infer ASM timing.
The existing recipe `tickRate` (default60) controls ticks. A state is limited to
36000 ticks/4096 steps, the rig to256 frames/128 states, and each rendered sheet
to the existing16777216-pixel budget. Split large recipes before rendering.

Each state produces `state-NAME-1x.png`, `state-NAME-4x.png` and labelled4x cells.
With `--gif`, an existing ffmpeg makes `state-NAME.gif` from those cells at the
specified ticks; nothing is installed. GIF delays have10ms precision, so a60Hz
sequence uses alternating10/20ms delays. JSON retains exact ticks. The original
pose/atlas outputs and optional original sequence GIF remain available.

The accepted Normalize+rig replay and first Ganondorf/Ganon rigs are retained
in AFS `scratchpad/handoffs/art_pipeline_unified_2026-11-02/codex-normalize-rig-20261102/`.
They preserve source SHA256s, exact Ganondorf replay, source timer windows,
Link comparison pixels, contact sheets and GIF timing receipts. These are
read-only art/tooling fixtures; no new game art, tile allocation, ASM, AI, ROM
write, native behavior or merge is implied.
