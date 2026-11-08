# render_review_sheet.py

Read-only review sheet for a dungeon room proposal. It renders the room with the
graphics of the entrance the player actually uses, so wall and floor art match the
game, and puts before/after, contact crops, plane views and a self-check on one PNG.

It never writes a ROM or project. It runs the existing z3ed `dungeon-render`
(yaze 352456580 or later for `--graphics-entrance`); it is not a second renderer.

## Outputs (in `--out`)

- `sheet.png`: title + graphics provenance, BEFORE and AFTER at 1x with callouts
  (lower floor, upper floor, mouth, arrival), a 2x crop per `--contact`, derived
  BG1/BG2 plane views when `.tiles.json` is given, a native panel when `--native`
  is given, the auto metric, and the reviewer's self-check sentence.
- `manifest.json`: sha256 of every input (ROM, z3ed, PNGs, tiles), render mode,
  graphics entrance (room, blockset, camera), rendered main blockset and sheets,
  binding status, callouts, native offsets and match scores, auto metric, self-check.

## Graphics modes

| `--graphics-entrance` | Entrance leads into `--room`? | z3ed flag | manifest mode |
|---|---|---|---|
| not given | - | none (header default) | `header_default` |
| given | yes | `--entrance` | `direct_entrance` |
| given | no | `--graphics-entrance` | `inherited_entrance` |

Header default is only wrong where z3ed's entrance inference misses (on oos168x:
room 0x011 via 0x81 and room 0x056 via 0x79). Always pass the entrance the route uses.

## Binding pre-rendered previews

Private RAM-edit previews (for example `render-memory` output) arrive as PNG plus
`.tiles.json`. Pass them with `--before-png/--after-png` and `--bind before` plus
`--rom <preview base>`: the script re-renders that image's room from the ROM with
the chosen entrance and records `BOUND` only on a 0-pixel difference. A
pre-rendered sheet without a successful bind says `UNBOUND`.

## Limits

- BG1/BG2 views are derived from tile words and per-layer collision in
  `.tiles.json`, not per-layer pixel renders. z3ed has no per-layer output.
- The auto metric is a luminance step between the `lower` and `upper` callouts
  (threshold 20, fixed before any control). It is a hint; the self-check sentence,
  written after a person or agent looks at the sheet, is the verdict.
- A CPU render is not proof of native planes or runtime selectors. Native match
  needs `--native` with a captured frame (HUD rows skipped, offset searched +/-24 px).

## Controls (2026-11-08)

1. Wrong graphics: room 0x011, `--graphics-entrance 0x81 --before-header --native
   <frame>`. Entrance render matches native 99.6%; header default 71.4%.
2. Readability: Glacia CD preview 03 bound to entrance 0x34 (0 px); auto metric
   `LUMA_STEP_ABSENT`, self-check "No" (flat basin).

## Example

```bash
python3 Scripts/Rooms/render_review_sheet.py --room 0xCD --rom <base.sfc> \
  --graphics-entrance 0x34 --before-png CD-control.png --before-tiles CD-control.tiles.json \
  --after-png CD-preview03.png --after-tiles CD-preview03.tiles.json --bind before \
  --callout lower:13,47 --callout upper:10,24:basin --callout mouth:12,37:stair \
  --callout arrival:9,4:spiral --contact stair:12,37 --out review-cd03
```

Callout and contact coordinates are 8x8 tile units (0-63) in the 512x512 room image.
Run the sheet once, look at it, then rerun with `--self-check "<one sentence>"`.

Test: `python3 -m unittest Tests.test_render_review_sheet`.
