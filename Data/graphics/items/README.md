# New item prototype graphics

Each menu icon is a 16×16 indexed PNG plus a 64-byte SNES 2bpp asset in
TL/TR/BL/BR order. Icon backgrounds use opaque black (index 3), matching the
existing menu icons. Indices 1 and 2 retain the colored artwork; reserved blank
tile `$07F` remains transparent (index 0). The existing menu palettes are used:
Garo 5, Bombchu 3, Switch Hook 1. No palette slots were added.

The icons were generated for this project and converted with nearest-neighbor
resizing and exact menu-color quantization. The mask image references the Garo
Master player sprite. Source prompts and conversion receipts are retained in AFS
at `scratchpad/handoffs/new_items_prototype_2026-10-18/icons` and
`scratchpad/handoffs/garo_mask_2026-10-18`.

The Garo player graphics in `Masks/gfx/garo_master.4bpp` and its palette were
extracted unchanged from **Garo Master by Herowho**, `garomaster.1.zspr`:
https://alttpr-assets.s3.us-east-2.amazonaws.com/garomaster.1.zspr

Source SHA-256:
`752ddbaa6641085b3c2d92afb4013243344b4a94b7140523733bda8735e5f7d7`.
The original file, metadata, palettes and extraction receipt remain in AFS.

`Data/graphics/menu_icons.json` records the twelve allocated blank tiles.
`Scripts/Generate/menu_icon_overrides.py` preserves all other pixels in the
three HUD sheets and keeps canonical blank tile `$07F` unchanged. It checks the
editable base's decoded sheet hashes before emitting the compressed overrides.
