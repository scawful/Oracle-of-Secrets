
; ================================================
; use holes_0 tag routine

org $01CC00 ; holes_0 tag routine ; @hook module=Dungeons
JSL NewTagRoutine
RTS

pullpc
NewTagRoutine:
{
  ; check under link feet what tile he is standing on
  ; save somewhere in ram last tile we were on so it doesn't turn it back off
  ; kill room tag
  LDA.b $20 : CLC : ADC #$10 : AND.b #$F0 : STA.w $0224 ; y
  LDA.b $22 : CLC : ADC #$08 : AND.b #$F0 : STA.w $0225 ; x

  LDA.w $0224 : CMP.w $0226 : BNE .different_tile
    LDA.w $0225 : CMP.w $0227 : BNE .different_tile
      JMP .same_tile
  .different_tile

  ; do code here for tile code
  REP #$30

  LDA.w $22 : CLC : ADC.w #$0008 : AND.w #$01F0 : LSR #$02 : STA.b $00
  LDA.w $20 : CLC : ADC.w #$0010 : AND.w #$01F0 : ASL #$04 : CLC : ADC.b $00 : STA.b $06
  TAX

  LDA.l $7E2000, X : CMP.w #$0DED : BNE +
    JSR update_star_tile
    JSR SearchForEmptyStar
    BRA .done_update
  +
  LDA.l $7E2000, X : CMP.w #$0DEE : BNE +
    ;JSR SearchToRedStar
    JSR update_red_star_tile
    SEP #$30
    STZ.b $AE ; kill room tag!
    ;JSR update_empty_tile
    ;JSR SearchForEmptyStar
  +

  .done_update
  SEP #$30

  .same_tile

  LDA.w $0224 : STA.w $0226 ; Last Y
  LDA.w $0225 : STA.w $0227 ; Last X

  RTL
}


update_empty_tile:
{
  STZ.b $0E
  REP #$30
  JSR replace_tile_empty
  SEP #$30
  LDA.b #$01 : STA.b $14
  REP #$30
  RTS
}

update_star_tile:
{
  STZ.b $0E
  REP #$30
  JSR replace_tile_star
  SEP #$30
  LDA.b #$01 : STA.b $14
  LDA.b #$0C : STA.w $012F
  REP #$30
  RTS
}

update_red_star_tile:
{
  STZ.b $0E
  REP #$30
  JSR replace_red_tile_star
  SEP #$30
  LDA.b #$01 : STA.b $14
  LDA.b #$3C : STA.w $012E
  REP #$30
  RTS
}

replace_red_tile_star:
{
  LDX.w $1000
  LDA.w #$19EE : STA.w $1006, X
  LDA.w #$99EE : STA.w $100C, X
  LDA.w #$59EE : STA.w $1012, X
  LDA.w #$D9EE : STA.w $1018, X

  LDX.b $06
  LDA.w #$19EE : STA.l $7E2000, X
  LDA.w #$99EE : STA.l $7E2080, X
  LDA.w #$59EE : STA.l $7E2002, X
  LDA.w #$D9EE : STA.l $7E2082, X
  AND.w #$03FF : TAX
  LDA.l $7EFE00,X : AND.w #$00FF
  STA.b $08 : STA.b $09

  JMP replace_tile_continue
}


replace_tile_star:
{
  LDX.w $1000

  LDA.w #$0DEE
  STA.w $1006,X

  LDA.w #$8DEE
  STA.w $100C,X

  LDA.w #$4DEE
  STA.w $1012,X

  LDA.w #$CDEE
  STA.w $1018,X

  LDX.b $06

  LDA.w #$0DEE : STA.l $7E2000, X
  LDA.w #$8DEE : STA.l $7E2080, X
  LDA.w #$4DEE : STA.l $7E2002, X
  LDA.w #$CDEE : STA.l $7E2082, X

  AND.w #$03FF
  TAX

  LDA.l $7EFE00,X
  AND.w #$00FF
  STA.b $08
  STA.b $09

  JMP replace_tile_continue
}

replace_tile_empty:
{
  LDX.w $1000

  LDA.w #$0DED
  STA.w $1006,X

  LDA.w #$8DED
  STA.w $100C,X

  LDA.w #$4DED
  STA.w $1012,X

  LDA.w #$CDED
  STA.w $1018,X

  LDX.b $06
  LDA.w #$0DED : STA.l $7E2000, X
  LDA.w #$8DED : STA.l $7E2080, X
  LDA.w #$4DED : STA.l $7E2002, X
  LDA.w #$CDED : STA.l $7E2082, X

  AND.w #$03FF
  TAX

  LDA.l $7EFE00,X
  AND.w #$00FF
  STA.b $08
  STA.b $09

  replace_tile_continue:

  LDX.w $1000

  LDA.w #$0000
  JSR draw_one_corner
  STA.w $1002,X

  LDA.w #$0080
  JSR draw_one_corner
  STA.w $1008,X

  LDA.w #$0002
  JSR draw_one_corner
  STA.w $100E,X

  LDA.w #$0082
  JSR draw_one_corner
  STA.w $1014,X

  LDA.w #$0100
  STA.w $1004,X
  STA.w $100A,X
  STA.w $1010,X
  STA.w $1016,X

  LDA.w #$FFFF
  STA.w $101A,X

  TXA
  CLC
  ADC.w #$0018
  STA.w $1000

  RTS
}

; ---------------------------------------------------------

draw_one_corner:
{
  CLC
  ADC.b $06
  STA.b $0E

  AND.w #$0040

  LSR A
  LSR A
  LSR A
  LSR A

  XBA
  STA.b $08

  LDA.b $0E
  AND.w #$303F
  LSR A
  ORA.b $08
  STA.b $08

  LDA.b $0E
  AND.w #$0F80
  LSR A
  LSR A
  ORA.b $08
  XBA

  RTS
}

SearchForEmptyStar:
{
  LDX.w #$1FFE

  --
  LDA.l $7E2000, X : CMP.w #$0DED : BEQ .foundEmptyTile
  DEX : DEX
  BPL --
  ; all tiles were on
  SEP #$30
  LDA.w $0468 : BEQ +
  STZ.w $0468
  STZ.w $068E
  STZ.w $0690
  LDA.b #$05 : STA.b $11
  LDA.b #$25 : STA $012F
  STZ.b $AE ; kill room tag!
  LDA.b #$01 : STA $0466
  +
  BRA +
  .foundEmptyTile
  SEP #$30
  LDA.w $0468 : BNE +
  INC.w $0468
  STZ.w $068E
  STZ.w $0690
  LDA.b #$05 : STA.b $11
  +

  RTS
}

SearchToRedStar:
{
  LDX.w #$1FFE

  --
  LDA.l $7E2000, X : CMP.w #$0DEE : BEQ .foundStarTile
  DEX : DEX
  BPL --

  SEP #$30
  STZ.b $AE ; kill room tag!

  RTS

  .foundStarTile
  PHX
  STX.b $06
  JSR update_red_star_tile
  PLX
  BRA --
}

