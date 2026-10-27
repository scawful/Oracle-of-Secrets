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
