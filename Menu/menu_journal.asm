; Book of Secrets Journal Menu
; Journal States
JOURNAL_STATE_FIRST_PAGE  = $0000
JOURNAL_STATE_MIDDLE_PAGE = $0001
JOURNAL_STATE_LAST_PAGE   = $0002

Journal_Handler:
{
  PHB : PHK : PLB
  ; Check for L button press
  LDA.b $F6 : BIT.b #$20 : BEQ .check_right
    REP #$30
    JSR Journal_PrevPage
    JSL Menu_DrawJournal
    JSR Journal_DrawEntry
    BRA .draw_page
  
  .check_right
  ; Check for R button press
  LDA.b $F6 : BIT.b #$10 : BEQ .draw_page
    REP #$30
    JSR Journal_NextPage
    JSL Menu_DrawJournal
    JSR Journal_DrawEntry
  .draw_page
  SEP #$30
  PLB
  RTL
}

Journal_PrevPage:
{
  LDA.l JournalState 
  AND.w #$00FF : CMP.w #JOURNAL_STATE_FIRST_PAGE 
  BEQ .wrap_to_last
    DEC A
    STA.l JournalState
    RTS
  
  .wrap_to_last
  LDA.w #JOURNAL_STATE_LAST_PAGE
  STA.l JournalState
  RTS
}

Journal_NextPage:
{
  LDA.l JournalState 
  AND.w #$00FF : CMP.w #JOURNAL_STATE_LAST_PAGE 
  BEQ .wrap_to_first
    INC A
    STA.l JournalState
    RTS
  
  .wrap_to_first
  LDA.w #JOURNAL_STATE_FIRST_PAGE
  STA.l JournalState
  RTS
}

Journal_DrawEntry:
{
  REP #$30
  LDX.w #$0000
  LDY.w #$0000
  .loop
    LDA.w BookEntries, X : STA.w $1292, Y
    INY #2 : INX #2
  CPY.w #$001F : BCC .loop
  SEP #$30
  RTS
}

BookEntries:
  dw "THIS_IS_A_TEST__"
  dw "______________  "
  dw "______________  "

Menu_DrawJournal:
{
  PHB : PHK : PLB
  LDA.l JournalState
  ASL : TAX
  JSR (.page_drawers, X)
  SEP #$30
  PLB
  RTL

  .page_drawers
    dw Journal_DrawFirstPage
    dw Journal_DrawMiddlePage
    dw Journal_DrawLastPage
}

Journal_DrawFirstPage:
{
  REP #$30
  LDX.w #$FE

  .loop
    LDA.w .first_page_tilemap, X
    STA.w $1000, X
    LDA.w .first_page_tilemap+$100, X
    STA.w $1100, X
    LDA.w .first_page_tilemap+$200, X
    STA.w $1200, X
    LDA.w .first_page_tilemap+$300, X
    STA.w $1300, X
    LDA.w .first_page_tilemap+$400, X
    STA.w $1400, X
    LDA.w .first_page_tilemap+$500, X
    STA.w $1500, X
    LDA.w .first_page_tilemap+$600, X
    STA.w $1600, X
    LDA.w .first_page_tilemap+$700, X
    STA.w $1700, X
    DEX : DEX
  BPL .loop
  RTS

  .first_page_tilemap
    incbin "tilemaps/journal_begin.bin"
}

Journal_DrawMiddlePage:
{
  REP #$30
  LDX.w #$FE

  .loop
    LDA.w .middle_page_tilemap, X
    STA.w $1000, X
    LDA.w .middle_page_tilemap+$100, X
    STA.w $1100, X
    LDA.w .middle_page_tilemap+$200, X
    STA.w $1200, X
    LDA.w .middle_page_tilemap+$300, X
    STA.w $1300, X
    LDA.w .middle_page_tilemap+$400, X
    STA.w $1400, X
    LDA.w .middle_page_tilemap+$500, X
    STA.w $1500, X
    LDA.w .middle_page_tilemap+$600, X
    STA.w $1600, X
    LDA.w .middle_page_tilemap+$700, X
    STA.w $1700, X
    DEX : DEX
  BPL .loop

  RTS

  .middle_page_tilemap
    incbin "tilemaps/journal_mid.bin"
}

Journal_DrawLastPage:
{
  REP #$30
  LDX.w #$FE

  .loop
    LDA.w .last_page_tilemap, X
    STA.w $1000, X
    LDA.w .last_page_tilemap+$100, X
    STA.w $1100, X
    LDA.w .last_page_tilemap+$200, X
    STA.w $1200, X
    LDA.w .last_page_tilemap+$300, X
    STA.w $1300, X
    LDA.w .last_page_tilemap+$400, X
    STA.w $1400, X
    LDA.w .last_page_tilemap+$500, X
    STA.w $1500, X
    LDA.w .last_page_tilemap+$600, X
    STA.w $1600, X
    LDA.w .last_page_tilemap+$700, X
    STA.w $1700, X
  DEX : DEX
  BPL .loop

  RTS

  .last_page_tilemap
    incbin "tilemaps/journal_end.bin"
}

