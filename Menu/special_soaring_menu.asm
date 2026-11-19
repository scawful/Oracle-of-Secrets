; Reuses the bank2D frame, font, full-menu DMA and scroll/close state machine.
; No item cursor, equipment choice or saved song is changed by this list.
Menu_SoaringRequested:
{
  SEP #$30
  LDA.w $010C : CMP.b #$0B : BNE .no
  LDA.w $1AF0 : AND.b #$F8 : CMP.b #$80 : BNE .no
  SEC : RTS
  .no
  CLC : RTS
}

; M8/X8 -> returns A = max selectable row index (5 if Sky learned, else 4).
Menu_SoaringMaxRow:
{
  LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BNE .no_sky
  LDA.b #$05 : RTS
  .no_sky
  LDA.b #$04 : RTS
}

Menu_DrawSoaring:
{
  JSR Menu_DrawBackground
  ; Title (row 6, col 8)
  LDX.w #$001C
  .title
  LDA.w .title_text,X : STA.w $1000+menu_offset(6,8),X
  DEX #2 : BPL .title

  ; Prompt (row 22, col 9)
  LDX.w #$001A
  .prompt_text
  LDA.w .prompt_labels,X : STA.w $1000+menu_offset(22,9),X
  DEX #2 : BPL .prompt_text

  ; Determine visible row count and clamp cursor if Sky is locked.
  SEP #$30
  JSR Menu_SoaringMaxRow : STA.b $00
  LDA.w $1AF0 : AND.b #$07
  CMP.b $00 : BCC .cursor_ok : BEQ .cursor_ok
    LDA.b #$80 : STA.w $1AF0
  .cursor_ok

  ; Stream-draw destination rows 0..$00 at rows 10, 12, 14, 16, 18, [20].
  ; Each entry in .rows is [byte_len, word chars...]; row stride is $0080 (2 rows).
  REP #$30
  LDA.w #.rows : STA.b $04
  LDA.w #menu_offset(10,10) : STA.b $02
  SEP #$20
  LDA.b #$00 : STA.b $01
  .row_loop
    REP #$20
    LDA ($04) : TAY
    INC.b $04 : INC.b $04
    LDX.b $02
    .char_loop
      LDA ($04) : STA.w $1000,X
      INC.b $04 : INC.b $04
      INX #2
      DEY #2 : BNE .char_loop
    LDA.b $02 : CLC : ADC.w #$0080 : STA.b $02
    SEP #$20
    LDA.b $01 : CMP.b $00 : BEQ .draw_cursor
    INC : STA.b $01
    BRA .row_loop

  .draw_cursor
  LDA.w $1AF0 : AND.b #$07
  REP #$30
  AND.w #$00FF : XBA : LSR            ; row * $0080
  CLC : ADC.w #menu_offset(10,7) : TAX
  ; A small existing font colon marks the selected row (col 7).
  LDA.w #$256B : STA.w $1000,X
  RTS

  .title_text
  dw "SONG_OF_SOARING"
  .rows
  dw 16 : dw "GARRISON"
  dw 20 : dw "ZORA_COAST"
  dw 20 : dw "DEKU_GROVE"
  dw 22 : dw "GORON_COAST"
  dw 24 : dw "COURAGE_ISLE"
  dw 6  : dw "SKY"
  .prompt_labels
  dw "A:FLY___B:BACK"
}

Menu_SpecialSoaring:
{
  SEP #$30
  ; Cancel has priority; closing uses the ordinary menu animation.
  LDA.b $F4 : AND.b #$90 : BNE .cancel
  JSR Menu_SoaringMaxRow : STA.b $00
  LDA.w $1AF0 : AND.b #$07
  CMP.b $00 : BCC + : BEQ +
    LDA.b #$00
  +
  TAX
  LDA.b $F6 : AND.b #$80 : BNE .select
  LDA.b $F4 : AND.b #$0A : BNE .prev ; Up ($08) or Left ($02)
  LDA.b $F4 : AND.b #$05 : BNE .next ; Down ($04) or Right ($01)
  TXA : ORA.b #$80 : STA.w $1AF0
  BRA .draw
  .prev
  DEX : BPL .moved
    LDX.b $00 : BRA .moved
  .next
  INX : CPX.b $00 : BCC .moved : BEQ .moved
    LDX.b #$00
  .moved
  TXA : ORA.b #$80 : STA.w $1AF0
  LDA.b #$20 : STA.w $012F
  .draw
  JSR Menu_DrawSoaring
  SEP #$30
  LDA.b #$22 : STA.w $0116
  LDA.b #$01 : STA.b $17
  RTS
  .select
  TXA : ORA.b #$C0 : STA.w $1AF0
  BRA .close
  .cancel
  STZ.w $1AF0
  .close
  LDA.b #$12 : STA.w $012F
  LDA.b #!MENU_STATE_SCROLL_UP : STA.w $0200
  RTS
}
