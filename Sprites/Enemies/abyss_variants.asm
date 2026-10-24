; =========================================================
; Abyss enemy variants (scawful 2026-10-23)
;   Stalfos ($A7): indoor Abyss rooms load sprite sheet $23 (graphics $96),
;     an Ages-style copy of sheet $1F, and draw one 16x16 cell per frame.
;   Zora ($55 swimming, $56 walking): Abyss Zoras use OAM palette 4.
; World test: SavedWorld ($7EF3CA) is set before any sheet load or sprite prep.
; =========================================================

if !ENABLE_EON_OWL_ONE_SHOT == 1 || !ENABLE_ABYSS_STALFOS_SHEET == 1
; Sprite-sheet selector for the $00E772 reader (Decompress_sprite_arbitrary).
; The only caller is GfxSheet_GetPtr_SprCA (Core/gfx_sheet_table.asm), which
; owns the $00E772 site and calls this once before its pointer lookup. Nothing
; else hooks $00E772.
;
; ABI: JSL, RTL. Entry M=8, X=8, DB=$00 (inherited from the vanilla caller),
;   Y = sprite-relative sheet ID, DP $00-$02 = decompress destination.
; Exit: Y = sheet ID to load. A, N and Z are clobbered; X, DB, DP and the M/X
;   widths are preserved. $7EC2FC is rewritten only by the Eon Owl swap.
; LoadSpriteGraphics keeps the original sheet ID on the stack for its 3bpp
; expansion test, so a swapped sheet expands like the one it replaces.
SpriteSheet_Select:
{
  if !ENABLE_ABYSS_STALFOS_SHEET == 1
    ; Sheet $1F is only ever in slot 0; spriteset $09 uses it outdoors.
    ; The $7EC2FC cache keeps $1F, so cache reloads take this path again.
    CPY.b #$1F : BNE .not_stalfos
    LDA.l SavedWorld : BEQ .not_stalfos
    LDA.b $1B : BEQ .not_stalfos
      LDY.b #$23
    .not_stalfos
  endif
  if !ENABLE_EON_OWL_ONE_SHOT == 1
    JSL EonOwl_ArrivalSheet
  endif
  RTL
}
endif

if !ENABLE_ABYSS_STALFOS_SHEET == 1
; SpriteDraw_Stalfos entry (JSL from $1E914B/$1E9202). Displaced:
; LDA.w $0E10,X : BNE $0DC217. $0E10,X suppresses the draw on both worlds.
pushpc
org $0DC21C ; @hook module=Sprites name=StalfosDraw_Gate kind=jml target=StalfosDraw_Gate expected_m=8
  JML StalfosDraw_Gate
  NOP
assert pc() == $0DC221
pullpc

StalfosDraw_Gate:
{
  LDA.w $0E10,X : BNE .suppress
  LDA.l SavedWorld : BEQ .vanilla
  LDA.b $1B : BEQ .vanilla
  PHB : PHK : PLB
  LDA.b #$00 : XBA
  LDA.w $0DC0,X
  REP #$20
  ASL #3 : ADC.w #AbyssStalfos_Groups : STA.b $08
  SEP #$20
  LDA.b #$01 : STA.b $06 : STZ.b $07
  JSL Sprite_DrawMultiple_quantity_preset
  JSL Sprite_DrawShadow
  PLB
  RTL

  .suppress
  JML $0DC217 ; SpriteDontDraw_Stalfos: prep OAM coords, RTL
  .vanilla
  JML $0DC221
}

; One 16x16 entry per $0DC0,X frame. Sheet $23 cells: $00/$02 walk,
; $04 arms out, $06 collapsed. Bones ($2F/$3F) are unchanged.
AbyssStalfos_Groups:
  dw 0, 0 : db $00, $00, $00, $02 ; 0-3 walk
  dw 0, 0 : db $02, $00, $00, $02
  dw 0, 0 : db $00, $00, $00, $02
  dw 0, 0 : db $02, $00, $00, $02
  dw 0, 0 : db $00, $00, $00, $02 ; 4-7 side walk (front-facing art)
  dw 0, 0 : db $02, $00, $00, $02
  dw 0, 0 : db $00, $00, $00, $02
  dw 0, 0 : db $02, $00, $00, $02
  dw 0, 0 : db $04, $00, $00, $02 ; 8-9 jump
  dw 0, 0 : db $04, $40, $00, $02
  dw 0, 0 : db $06, $00, $00, $02 ; 10-11 collapsed
  dw 0, 0 : db $06, $40, $00, $02
endif

if !ENABLE_ABYSS_ZORA_PALETTE == 1
; SpritePrep_SwimmingZora: LDA #$40 : STA $0DF0,X, then falls into
; SpritePrep_Geldman at $068FA7.
pushpc
org $068FA2 ; @hook module=Sprites name=AbyssZora_SwimPrep kind=jsl target=AbyssZora_SwimPrep expected_m=8
  JSL AbyssZora_SwimPrep
  NOP
assert pc() == $068FA7
pullpc

; SpritePrep_WalkingZora: LDA #$60 : STA $0DF0,X : RTS.
pushpc
org $068FC9 ; @hook module=Sprites name=AbyssZora_WalkPrep kind=jsl target=AbyssZora_WalkPrep expected_m=8
  JSL AbyssZora_WalkPrep
  RTS
assert pc() == $068FCE
pullpc

; Prep runs with DB=$06 after the property load wrote $0F50,X.
; The Zora fireball ($55) spawns without prep and keeps its palette.
AbyssZora_SwimPrep:
{
  LDA.b #$40 : STA.w $0DF0,X
  BRA AbyssZora_SetPalette
}

AbyssZora_WalkPrep:
{
  LDA.b #$60 : STA.w $0DF0,X
}

AbyssZora_SetPalette:
{
  LDA.l SavedWorld : BEQ .done
  LDA.w $0F50,X : AND.b #$F1 : ORA.b #$08 : STA.w $0F50,X ; palette 4
  .done
  RTL
}
endif
