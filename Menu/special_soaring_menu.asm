; Reuses the bank2D frame, font, full-menu DMA and scroll/close state machine.
; No item cursor, equipment choice or saved song is changed by this list.
Menu_SoaringRequested:
{
  SEP #$30
  LDA.w $010C : CMP.b #$0B : BNE .no
  LDA.w $1AF0 : AND.b #$FE : CMP.b #$80 : BNE .no
  SEC : RTS
  .no
  CLC : RTS
}

Menu_DrawSoaring:
{
  JSR Menu_DrawBackground
  LDX.w #$001C
  .title
  LDA.w .title_text,X : STA.w $1000+menu_offset(6,8),X
  DEX #2 : BPL .title
  LDX.w #$000E
  .garrison
  LDA.w .garrison_text,X : STA.w $1000+menu_offset(11,10),X
  DEX #2 : BPL .garrison
  SEP #$30
  LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BNE .locked
  REP #$30
  LDX.w #$0004
  .sky
  LDA.w .sky_text,X : STA.w $1000+menu_offset(15,10),X
  DEX #2 : BPL .sky
  BRA .prompt
  .locked
  LDA.b #$80 : STA.w $1AF0
  REP #$30
  .prompt
  LDX.w #$001A
  .prompt_text
  LDA.w .prompt_labels,X : STA.w $1000+menu_offset(21,7),X
  DEX #2 : BPL .prompt_text
  SEP #$30
  LDA.w $1AF0 : AND.b #$01 : BEQ .first
  REP #$30
  LDX.w #menu_offset(15,7) : BRA .cursor
  .first
  REP #$30
  LDX.w #menu_offset(11,7)
  .cursor
  ; A small existing font colon marks the selected row.
  LDA.w #$256B : STA.w $1000,X
  RTS
  .title_text
  dw "SONG_OF_SOARING"
  .garrison_text
  dw "GARRISON"
  .sky_text
  dw "SKY"
  .prompt_labels
  dw "A:FLY___B:BACK"
}

Menu_SpecialSoaring:
{
  SEP #$30
  ; Cancel has priority; closing uses the ordinary menu animation.
  LDA.b $F4 : AND.b #$90 : BNE .cancel
  LDA.b $F6 : AND.b #$80 : BNE .select
  LDA.b $F4 : AND.b #$0F : BEQ .draw
  LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BNE .draw
  LDA.w $1AF0 : EOR.b #$01 : STA.w $1AF0
  LDA.b #$20 : STA.w $012F
  .draw
  JSR Menu_DrawSoaring
  SEP #$30
  LDA.b #$22 : STA.w $0116
  LDA.b #$01 : STA.b $17
  RTS
  .select
  LDA.w $1AF0 : ORA.b #$40 : STA.w $1AF0
  BRA .close
  .cancel
  STZ.w $1AF0
  .close
  LDA.b #$12 : STA.w $012F
  LDA.b #!MENU_STATE_SCROLL_UP : STA.w $0200
  RTS
}
