; =========================================================
; Graphics sheet pointer table, relocated and expanded.
;
; Vanilla keeps three parallel $DF-entry arrays (bank, high, low) at
; $00:CF80 / $00:D05F / $00:D13E, directly followed by code, so the table
; cannot grow in place. The arrays are rebuilt here with $100 rows (global
; IDs $00..$FE; $FF stays the "use default" sentinel) at the top of bank $23,
; and the eight vanilla reader sequences call the helpers below.
;
; Rows $00..$DE are copied from the base ROM table, so base-ROM edits (yaze)
; carry over. sheet_overrides.asm rewrites its rows in these arrays, so it
; must be included AFTER this file.
; Rows $DF..$FF point at an empty LC-LZ2 stream until a sheet claims them.
; New IDs $DF..$FE must be 3bpp LC-LZ2 (2bpp and raw sheets are keyed by
; number in the loaders).
;
; Sprite sheets use the same arrays at index = relative ID + $73.
;
; Helper ABI: M=8 and X/Y=8 on entry, Y = sheet ID, result in DP, X and Y
; preserved, P restored. DB does not matter (long addressing), except that
; GfxSheet_GetPtr_SprCA needs DB=$00 for its selector and may change Y.
; =========================================================

!GfxSheet_Rows = $100
!GfxSheet_SprOffset = $73

pushpc

org $23FC00
GfxSheet_Helpers:

macro GfxSheetCopy(lo, hi, bk, off)
  LDA.l GfxSheet_Low+<off>,X  : STA.b <lo>
  LDA.l GfxSheet_High+<off>,X : STA.b <hi>
  LDA.l GfxSheet_Bank+<off>,X : STA.b <bk>
endmacro

; Y = sprite-relative sheet ID -> $00-$02 (low, high, bank).
GfxSheet_GetPtr_Spr:
{
  PHP : SEP #$30 : PHX : REP #$10
  TYX
  %GfxSheetCopy($00, $01, $02, !GfxSheet_SprOffset)
  SEP #$10 : PLX : PLP
  RTL
}

; Y = sprite-relative sheet ID -> $C8-$CA (Decompress_sprite_arbitrary).
; This is the single owner of the $00E772 site. Sheet selection (Abyss
; Stalfos, Eon Owl arrival) runs first through Oracle_SpriteSheet_Select
; (Sprites/Enemies/abyss_variants.asm), which may change Y and requires
; DB=$00 as the vanilla caller provides. Y is preserved only when no
; selector is compiled in; otherwise it is the selected sheet on exit.
GfxSheet_GetPtr_SprCA:
{
  if !ENABLE_EON_OWL_ONE_SHOT == 1 || !ENABLE_ABYSS_STALFOS_SHEET == 1
    JSL Oracle_SpriteSheet_Select
  endif
  PHP : SEP #$30 : PHX : REP #$10
  TYX
  %GfxSheetCopy($C8, $C9, $CA, !GfxSheet_SprOffset)
  SEP #$10 : PLX : PLP
  RTL
}

; Y = background sheet ID -> $C8-$CA (Decompress_background_arbitrary).
GfxSheet_GetPtr_BgCA:
{
  PHP : SEP #$30 : PHX : REP #$10
  TYX
  %GfxSheetCopy($C8, $C9, $CA, 0)
  SEP #$10 : PLX : PLP
  RTL
}

; Sprite-relative sheet 0 -> $00-$02 (LoadDefaultGraphics, no index).
GfxSheet_GetPtr_Default:
{
  PHP : SEP #$20
  LDA.l GfxSheet_Low+!GfxSheet_SprOffset  : STA.b $00
  LDA.l GfxSheet_High+!GfxSheet_SprOffset : STA.b $01
  LDA.l GfxSheet_Bank+!GfxSheet_SprOffset : STA.b $02
  PLP
  RTL
}

; Empty LC-LZ2 stream (same bytes as the vanilla filler sheets).
GfxSheet_EmptyStream:
  db $E7, $FF, $00, $E5, $FF, $00, $FF

assert pc() <= $23FD00, "Gfx sheet helpers overran the pointer arrays"

org $23FD00
GfxSheet_Bank:
  !i = 0
  while !i < $DF
    db read1($00CF80+!i)
    !i #= !i+1
  endwhile
  while !i < !GfxSheet_Rows
    db GfxSheet_EmptyStream>>16
    !i #= !i+1
  endwhile
GfxSheet_High:
  !i = 0
  while !i < $DF
    db read1($00D05F+!i)
    !i #= !i+1
  endwhile
  while !i < !GfxSheet_Rows
    db GfxSheet_EmptyStream>>8
    !i #= !i+1
  endwhile
GfxSheet_Low:
  !i = 0
  while !i < $DF
    db read1($00D13E+!i)
    !i #= !i+1
  endwhile
  while !i < !GfxSheet_Rows
    db GfxSheet_EmptyStream
    !i #= !i+1
  endwhile
assert pc() == $240000, "Gfx sheet pointer arrays must end at the bank boundary"

; ---------------------------------------------------------
; Reader sites. Each vanilla sequence loaded three pointer bytes with
; LDA.w abs,Y; the JSL below replaces that sequence and the rest of the
; span is NOP padding so the following vanilla instruction is unmoved.
; ---------------------------------------------------------
padbyte $EA

; LoadItemGFX_sheet0 (Y = 0). Vanilla also stored the bank to $05.
org $00D53B ; @hook module=Core name=GfxSheet_LoadItemGFX_sheet0 kind=jsl target=GfxSheet_GetPtr_Spr expected_m=8 expected_x=8
  JSL GfxSheet_GetPtr_Spr
  LDA.b $02 : STA.b $05
  pad $00D54C

; LoadDefaultGraphics (fixed sheet, no index).
org $00E2D8 ; @hook module=Core name=GfxSheet_LoadDefaultGraphics kind=jsl target=GfxSheet_GetPtr_Default expected_m=8
  JSL GfxSheet_GetPtr_Default
  pad $00E2E7

; Graphics_LoadChrHalfSlot. Vanilla also stored the bank to $05.
org $00E462 ; @hook module=Core name=GfxSheet_LoadChrHalfSlot kind=jsl target=GfxSheet_GetPtr_Spr expected_m=8 expected_x=8
  JSL GfxSheet_GetPtr_Spr
  LDA.b $02 : STA.b $05
  pad $00E473

; LoadCommonSprites, first sequence (Y = $0AA4).
org $00E6BA ; @hook module=Core name=GfxSheet_LoadCommonSprites_a kind=jsl target=GfxSheet_GetPtr_Spr expected_m=8 expected_x=8
  JSL GfxSheet_GetPtr_Spr
  pad $00E6C9

; LoadCommonSprites, second sequence (Y = 6).
org $00E72E ; @hook module=Core name=GfxSheet_LoadCommonSprites_b kind=jsl target=GfxSheet_GetPtr_Spr expected_m=8 expected_x=8
  JSL GfxSheet_GetPtr_Spr
  pad $00E73D

; Decompress_sprite_arbitrary. The BRA Decompress at $00E781 is unchanged.
org $00E772 ; @hook module=Core name=GfxSheet_DecompressSprite kind=jsl target=GfxSheet_GetPtr_SprCA expected_m=8 expected_x=8
  JSL GfxSheet_GetPtr_SprCA
  pad $00E781

; Decompress_background_arbitrary. Falls through into Decompress at $00E79E.
org $00E78F ; @hook module=Core name=GfxSheet_DecompressBackground kind=jsl target=GfxSheet_GetPtr_BgCA expected_m=8 expected_x=8
  JSL GfxSheet_GetPtr_BgCA
  pad $00E79E

pullpc
