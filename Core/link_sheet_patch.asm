; =========================================================
; Human Minish Cap Link 4BPP Sheet Override ($108000-$10EFFF)
;
; Emits the unified Minish Cap Link player graphics sheet
; (28,672 bytes = 28x8 16x16 cells) over vanilla bank $10
; ($108000 / PC 0x080000). Regenerated deterministically by
; Scripts/Generate/build_mc_link_sheet.py.
; =========================================================

pushpc
org $108000
MinishCapLinkSheet:
  incbin "Data/graphics/link/mc_link_sheet.4bpp"
assert pc() == $10F000, "Minish Cap Link sheet must be exactly $7000 (28,672) bytes"
pullpc
