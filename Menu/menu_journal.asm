; Book of Secrets Journal Menu
; Journal States
JOURNAL_STATE_FIRST_PAGE  = $0000
JOURNAL_STATE_MIDDLE_PAGE = $0001
JOURNAL_STATE_LAST_PAGE   = $0002

; ---------------------------------------------------------
; Journal Handler
; ---------------------------------------------------------

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

; ---------------------------------------------------------
; Page Navigation
; ---------------------------------------------------------

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

; ---------------------------------------------------------
; Entry Drawing
; ---------------------------------------------------------

Journal_DrawEntry:
{
  REP #$30
  ; Calculate pointer to the text based on JournalState (Page #)
  ; Entry = JournalEntries[JournalState]
  LDA.l JournalState : AND.w #$00FF : ASL : TAX
  LDA.w JournalEntries, X : STA.b $00 ; Store pointer in $00 (Direct Page)

  LDX.w #$0000 ; Text Offset
  LDY.w #$0000 ; VRAM Offset
  
  .loop
    ; Read from Indirect Address ($00) + Y (offset)
    ; We need to be careful with addressing.
    ; $00 is 16-bit pointer. We need to read from Bank 2D (current bank).
    ; LDA ($00), Y works if Y is index.
    ; But our X is the text offset index, Y is VRAM index.
    ; Let's swap registers.
    
    PHY ; Save VRAM offset
    TXY ; Y = Text Offset
    LDA ($00), Y ; Read word from text table
    PLY ; Restore VRAM offset
    
    STA.w $1292, Y ; Write to VRAM buffer
    
    INY #2 ; Next VRAM word
    INX #2 ; Next Text word
    
  CPY.w #$0060 ; Copy 3 lines (32 bytes * 3 approx? No, original was $1F bytes -> 16 chars/1 line)
               ; Original loop: CPY #$001F. That's 32 bytes (16 chars).
               ; The BookEntries had 3 lines defined but the loop only did 1 line?
               ; Original:
               ; .loop
               ;   LDA.w BookEntries, X : STA.w $1292, Y
               ;   INY #2 : INX #2
               ; CPY.w #$001F : BCC .loop
               ; Yes, it only copied the first line ($00 to $1E).
               ; We should probably copy more lines.
               ; Let's copy 6 lines ($60 bytes? No, $1F is 31. So 16 chars * 2 bytes = 32 bytes = $20)
               ; Let's copy 3 lines = $60 bytes.
               
  CPY.w #$0060 : BCC .loop
  
  SEP #$30
  RTS
}

; ---------------------------------------------------------
; Data Tables
; ---------------------------------------------------------

JournalEntries:
  dw Entry_Page1
  dw Entry_Page2
  dw Entry_Page3

Entry_Page1:
  dw "QUEST_LOG:_I____"
  dw "Must_find_the___"
  dw "missing_girl____"

Entry_Page2:
  dw "QUEST_LOG:_II___"
  dw "The_Mushroom_is_"
  dw "key_to_the_woods"

Entry_Page3:
  dw "QUEST_LOG:_III__"
  dw "Zora_River_flows"
  dw "from_the_north__"

; ---------------------------------------------------------
; Background Drawing
; ---------------------------------------------------------

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