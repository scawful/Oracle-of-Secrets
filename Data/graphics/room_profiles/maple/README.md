# Maple GBC room profile

Editable native sheets and palette for room `$00F`, entrance `$68`, groups3/3.
The existing room objects, collision, bed/wake positions and sprite graphics are
retained. The bed uses the existing32x40 drawing and native repeated/mirrored
cells. Drawer stands use mirrored halves of the16x32 source dresser.

`profile.json` pins the base and the eight decoded original sheets.
`slot_*.txt` are128x32 indexed authoring grids,64tiles per sheet, indices0..7.
`provenance.json` identifies the LA rip, exact source hash and changed tile roles.
These are actual tile assets; no pixels from the generated concept preview are
included. The source rip is Link's Awakening, not an Oracle-specific asset claim.

The first sample changes47 graphic cells. Existing wall and bookshelf outlines
are simplified; the bed, stands, floor and vessel incorporate native8x8 source
crops. Palette rows2/3/5/7 provide warm wood, pale bedding, lavender rug and pink
surround. The native environment OBJ palette source remains unchanged.

Compile into a new directory, inspect the diff, and replace this owned generated
package deliberately. Existing output is verified without replacement:

```sh
python3 Scripts/Generate/room_graphics.py \
  Data/graphics/room_profiles/maple/profile.json --base-rom Roms/oos168.sfc \
  --out-dir Data/graphics/room_profiles/maple/generated --check
```

`Dungeons/room_graphics.asm` binds the compressed sheets and180-byte palette.
`ENABLE_MAPLE_ROOM_GRAPHICS=0` is the diagnostic control. The compiler's bundle
is intentionally marked unbound: the standalone compiler does not install the
ASM. The included bed/stand/bookshelf pattern streams describe the current
footprints; this runtime uses the existing object patterns, not those streams.

Native animation overwrites VRAM byte`$7600..$79FF` (tile indices`$1B0..$1CF`).
Those cells remain unchanged and are checked against live animation source data
by `Tests/native/maple_room_graphics.py`. Normal entrance/dream-return loads are
supported; new interior door/stair connections require additional validation.
