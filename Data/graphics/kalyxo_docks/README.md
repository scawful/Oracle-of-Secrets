# Editable Kalyxo docks

Edit the pixels in [source.json](source.json) and the arrangement in [Data/overworld/kalyxo_docks.json](../../overworld/kalyxo_docks.json). The current set uses plain warm wood, the existing MAIN palette row3, and sixteen-pixel cells. Boats and house fronts can be added later as separate modular art and entrance work.

## Pixel source

Every named module has sixteen rows of sixteen palette indices. `.` or `0` means transparent source; `1–6` are wood colors. Index7 is the existing blue water. Native binding replaces transparent source pixels with7, so the green backdrop does not show through gaps. Keep the palette order unless the binding is deliberately changed.

[generated/preview.png](generated/preview.png) labels all32 modules. [generated/atlas.png](generated/atlas.png) contains their exact indexed pixels. The31 bound cells use **Map16 `$0FC0 + source id`**; IDs are stable, so preserve them when editing. `ladder_bottom` has source id`$1C` and remains unbound: `$0FDC` is not a usable native dock tile. `ladder_top` is only a static drawing, with no climbing behavior.

The generated manifest records each8×8 quadrant, its flip, and its collision intent. Pixel edits do not change collision automatically. The binder selects existing compatible slots; it refuses artwork that exceeds their capacity. Current usage is14 walk and11 solid art pieces, with the blank brace quadrant reusing native water.

## Grid source

The recipe writes four physical maps: docks`$30/$31`, Secret Beach`$32`, and Loom Beach`$33`. Dock placement still uses a **96×32 grid of16×16 cells**: `$30` at x0–31, `$31` at x32–63, and `$32` at x64–95. y0 is the top. `deck_rectangles` use inclusive `[left, top, right, bottom]` coordinates; the binder derives the outside rims and south-facing supports. `cargo` places named library cells on the deck. Change these fields to widen, shorten or move the fingers; do not edit generated Map16/Map32 data by hand.

The `native_placements` entries use **physical screen-local coordinates**, with x/y0–31 on `$32` or `$33`. They open a three-cell-wide grass core at y13–15, from Secret Beach x18–31 through Loom Beach x0–8, meeting the existing path at Loom x9–10. A grass margin at y16 and native tree caps at y17 keep the lower forest intact. The103 guarded replacements reuse existing grass and forest-edge Tile16 definitions; they add no CHR artwork. Each placement retains `old_tile16` so the binder refuses a changed source cell. Physical `$33` is the upper-left quadrant of the larger Loom Beach area, which contains the existing route to Link's house.

This describes the implemented recipe. Native traversal and transition acceptance are tracked separately from the editable grid.

[kalyxo_docks_binding.json](../../overworld/kalyxo_docks_binding.json) is generated output documenting the actual Map16 IDs, CHR slots and palette row. The recipe does not create boats, house entrances, doors or warps. Future facades need their own art, collision-compatible slots and explicit entrance placement.

## Regenerate in the isolated worktree

Set `DOCKS_PRIVATE_DIR` to a scratch directory outside the shared `Roms/`, containing a private copy named `base-e75690ad.sfc`. The binder requires the exact base SHA-256 `e75690add9200a8db00a44772b5aaf05c04284616ec8aaf9aa02919096ed14ac`. From the worktree root, run these two generators:

```sh
python3 Scripts/Generate/kalyxo_docks_art.py
python3 Scripts/Generate/kalyxo_docks_bind.py \
  --base "${DOCKS_PRIVATE_DIR:?set a private scratch directory}/base-e75690ad.sfc" \
  --out "$DOCKS_PRIVATE_DIR/docks-edited.sfc" \
  --receipt "$DOCKS_PRIVATE_DIR/docks-edited.json" \
  --write-assets
```

The first command regenerates the indexed atlas, labeled preview, native3bpp/4bpp payloads and manifest. The second creates a **new private ROM** and updates the graphics binaries and binding JSON in this isolated worktree. It refuses an existing ROM output; choose a new output filename for the next iteration. A successful recipe compile is not a patched game build or a native traversal check.

For a read-only freshness check, run `python3 Scripts/Generate/kalyxo_docks_art.py --check`. Review the regenerated art and private map render before integrating a layout change.
