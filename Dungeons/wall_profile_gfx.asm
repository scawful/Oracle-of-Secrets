; =========================================================
; Wall-profile selector graphics kits (flag !ENABLE_WALL_PROFILE_SELECTOR,
; generated !WALLSEL_GFX == 1). Global scope; included from Oracle_main.asm
; after Core/gfx_sheet_table.asm.
;
; Dungeons/Data/kits/kits.asm (built by Scripts/Generate/gen_wall_profiles.py
; build from Dungeons/Data/kits/*.kit.json) writes each kit's private
; blockset row, private palette and new 3bpp LC-LZ2 sheet streams
; ($458000-$45EFFF), and points spare global sheet rows at the streams.
; No shared sheet, row or palette is edited.
; =========================================================
if not(defined("GfxSheet_TableDone"))
  error "wall_profile_gfx.asm must follow Core/gfx_sheet_table.asm"
endif
; read1() sees the base ROM here, not the relocated table, so the "row is
; still the empty stream" check runs after the build (RESULT.md proof 1).

incsrc "Dungeons/Data/kits/kits.asm"
