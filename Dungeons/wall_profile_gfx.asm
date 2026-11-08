; =========================================================
; Wall-profile selector graphics sheet (flag !ENABLE_WALL_PROFILE_SELECTOR,
; generated !WALLSEL_GFX == 1). Global scope; included from Oracle_main.asm
; after Core/gfx_sheet_table.asm.
;
; Sheet !WALLSEL_GFX_SHEET is a new 3bpp LC-LZ2 stream (built by
; Scripts/Generate/gen_wall_profiles.py build). Only the private blockset
; row !WALLSEL_GFX_BLOCKSET loads it; no shared sheet is edited.
; The stream owns $44F000-$44FFFF (upper half of the selector slot).
; =========================================================
if not(defined("GfxSheet_TableDone"))
  error "wall_profile_gfx.asm must follow Core/gfx_sheet_table.asm"
endif
assert !WALLSEL_GFX_SHEET >= $DF && !WALLSEL_GFX_SHEET < !GfxSheet_Rows, "gfx sheet must be a spare row"
; read1() sees the base ROM here, not the relocated table, so the "row is
; still the empty stream" check runs after the build (RESULT.md proof 1).

pushpc
org $44F000
WallSel_GfxSheet:
  incbin !WALLSEL_GFX_SLOT3_BIN
WallSel_GfxSheet_End:
assert pc() <= $450000, "WallSel gfx sheet exceeded $44F000-$44FFFF"

assert GfxSheet_Bank == $23FD00 && GfxSheet_High == $23FE00 && GfxSheet_Low == $23FF00, "gfx sheet arrays moved"
assert !WALLSEL_GFX_SHEET == $FE, "row literals below assume sheet $FE"
org $23FDFE ; @hook module=Dungeons kind=data protected_size=1
  db WallSel_GfxSheet>>16
org $23FEFE ; @hook module=Dungeons kind=data protected_size=1
  db WallSel_GfxSheet>>8
org $23FFFE ; @hook module=Dungeons kind=data protected_size=1
  db WallSel_GfxSheet
pullpc
