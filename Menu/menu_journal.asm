; Book of Secrets Journal Menu

; ---------------------------------------------------------
; Journal Handler
; ---------------------------------------------------------

Journal_Handler:
{
  PHB : PHK : PLB

  ; Check timer
  LDA.w $0207 : BEQ .process_input
    DEC.w $0207
    JMP .exit
  .process_input

  ; Check for L button press (using F2 for continuous poll with timer)
  LDA.b $F2 : BIT.b #$20 : BEQ .check_right
    REP #$30
    JSR Journal_PrevPage
    JSL Menu_DrawJournal
    SEP #$30
    LDA.b #$0A : STA.w $0207 ; Set delay
    JMP .exit
  
  .check_right
  ; Check for R button press
  LDA.b $F2 : BIT.b #$10 : BEQ .exit
    REP #$30
    JSR Journal_NextPage
    JSL Menu_DrawJournal
    SEP #$30
    LDA.b #$0A : STA.w $0207 ; Set delay

  .exit
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
  AND.w #$00FF : BEQ .wrap_to_last
    DEC A
    STA.l JournalState
    RTS
  
  .wrap_to_last
  ; Find total count to wrap to last
  JSR Journal_CountUnlocked
  DEC A
  STA.l JournalState
  RTS
}

Journal_NextPage:
{
  LDA.l JournalState 
  AND.w #$00FF : INC A : STA.b $00
  
  ; Check if next page exists
  LDA.b $00
  JSR Journal_GetNthEntry
  CPX.w #$0000 : BEQ .wrap_to_first
    LDA.b $00
    STA.l JournalState
    RTS
  
  .wrap_to_first
  LDA.w #$0000
  STA.l JournalState
  RTS
}

; ---------------------------------------------------------
; Entry Logic
; ---------------------------------------------------------

; Input: A = Index (N)
; Output: X = Text Pointer (or 0 if not found)
Journal_GetNthEntry:
{
  PHA
  LDY.w #$0000 ; Master List Index
  
  .loop
    ; Check if we reached end of list
    LDA.w Journal_MasterList, Y : BEQ .end_of_list
    
    ; Check Flag
    ; Format: dd dd dd mm (Address Long, Mask)
    ; But we can't indirect long easily without setup.
    ; Let's read address to $00.
    
    LDA.w Journal_MasterList, Y : STA.b $02
    LDA.w Journal_MasterList+2, Y : STA.b $04 ; Get mask in low byte of $04
    
    SEP #$20
    ; $04 = Bank, $05 = Mask (from 16-bit read above)

    PHB
    LDA.b $04 : PHA : PLB       ; Set DB to address bank
    LDA.b ($02)                 ; Load flag value at address
    PLB                         ; Restore original data bank

    AND.w Journal_MasterList+3, Y  ; Apply mask (A is 8-bit, addr is 16-bit)
    ; Wait, 16-bit read of +2 gets Bank and Mask.
    ; $02-$03 = Addr Low
    ; $04 = Bank
    ; $05 = Mask
    ; The AND above reads from ROM directly.
    
    BEQ .locked
      ; Unlocked
      PLA : DEC A : PHA ; Decrement target index
      BMI .found
    
    .locked
    REP #$20
    TYA : CLC : ADC.w #$0006 : TAY ; Next Entry (4 bytes header + 2 bytes ptr = 6)
    BRA .loop
    
  .found
    REP #$20
    PLA ; Clean stack
    LDA.w Journal_MasterList+4, Y : TAX
    RTS
    
  .end_of_list
    REP #$20
    PLA ; Clean stack
    LDX.w #$0000
    RTS
}

Journal_CountUnlocked:
{
  LDY.w #$0000 ; Master List Index
  LDA.w #$0000 : STA.b $06 ; Counter
  
  .loop
    LDA.w Journal_MasterList, Y : BEQ .done
    
    ; Check Flag
    LDA.w Journal_MasterList, Y : STA.b $02
    LDA.w Journal_MasterList+2, Y : STA.b $04
    
    SEP #$20
    PHB                         ; Save current data bank
    LDA.b $04 : PHA : PLB       ; Set DB to address bank
    LDA.b ($02)                 ; Load flag value
    PLB                         ; Restore original data bank
    AND.w Journal_MasterList+3, Y  ; Apply mask (A is 8-bit, addr is 16-bit)
    BEQ .locked
      REP #$20
      INC.b $06

    .locked
    REP #$20
    TYA : CLC : ADC.w #$0006 : TAY
    BRA .loop
    
  .done
    LDA.b $06
    RTS
}

; ---------------------------------------------------------
; Entry Drawing
; ---------------------------------------------------------

Journal_DrawEntry:
{
  REP #$30
  LDA.l JournalState : AND.w #$00FF
  JSR Journal_GetNthEntry
  STX.b $00 ; Store Text Pointer
  
  CPX.w #$0000 : BNE .valid
    ; Draw "Empty" if no entry found (shouldn't happen with correct logic)
    RTS
  .valid

  LDX.w #$0000 ; Text Offset
  LDY.w #$0000 ; VRAM Offset
  
  .loop
    PHY ; Save VRAM offset
    TXY ; Y = Text Offset
    LDA ($00), Y ; Read word from text
    PLY ; Restore VRAM offset
    
    CMP.w #$FFFF : BEQ .done ; Check for terminator
    
    STA.w $1292, Y ; Write to VRAM buffer (Row 1)
    
    INY #2 ; Next VRAM word
    INX #2 ; Next Text word
    
    ; Wrap logic for multiple lines
    ; Line 1 ends at $1292 + $20 (32 bytes) = $12B2?
    ; Let's just assume the text includes padding or we handle newlines?
    ; Simplified: The text data is pre-formatted to 16 chars per line.
    ; We just copy linear data to linear VRAM.
    ; But VRAM is linear in rows? Yes, usually.
    ; However, to jump to next line in tilemap we need to add stride.
    ; Row Width = $40 bytes (32 tiles * 2 bytes).
    ; If we write 16 chars (32 bytes), we need to skip 32 bytes to reach next line.
    
    CPY.w #$0020 : BNE .check_line_2
      TYA : CLC : ADC.w #$0020 : TAY ; Skip to next line start
    .check_line_2
    CPY.w #$0060 : BNE .check_line_3 ; End of Line 2 ($20 + $40 = $60)
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_3
    
    BRA .loop
    
  .done
  SEP #$30
  RTS
}

; ---------------------------------------------------------
; Data Tables
; ---------------------------------------------------------

; Format: Address(3), Mask(1), TextPtr(2) = 6 bytes
Journal_MasterList:
  dl $7EF3D6 : db $02 : dw Entry_QuestStart ; OOSPROG bit 1 (Quest Start)
  dl $7EF3D6 : db $10 : dw Entry_MetElder   ; OOSPROG bit 4 (Met Elder)
  dl $7EF3C6 : db $04 : dw Entry_MakuTree   ; OOSPROG2 bit 2 (Maku Tree)
  dw $0000 ; Terminator

Entry_QuestStart:
  dw "Quest_Started___"
  dw "Find_the_3_gems_"
  dw "to_save_Hyrule__"
  dw $FFFF

Entry_MetElder:
  dw "Spoke_to_Elder__"
  dw "He_mentioned_a__"
  dw "missing_girl____"
  dw $FFFF

Entry_MakuTree:
  dw "Met_Maku_Tree___"
  dw "He_needs_his____"
  dw "memory_back_____"
  dw $FFFF

; ---------------------------------------------------------
; Background Drawing
; ---------------------------------------------------------

Menu_DrawJournal:
{
  PHB : PHK : PLB
  REP #$30
  
  ; Logic to choose background based on page number?
  ; For now just cycle them 1-2-3-1-2-3
  LDA.l JournalState : AND.w #$00FF
  CLC : ADC.b #$01 ; Make 1-based?
  ; Modulo 3?
  ; Simple:
  ; 0 -> First
  ; Last -> Last
  ; Else -> Middle
  
  ; But we don't know which is last without counting.
  ; Let's just use First for 0, Last for Last, Middle for others.
  
  LDA.l JournalState : AND.w #$00FF : BEQ .first
  
  PHA
  JSR Journal_CountUnlocked : DEC A : STA.b $02
  PLA
  CMP.b $02 : BEQ .last
  
  BRA .middle

  .first
    JSR Journal_DrawFirstPage
    BRA .exit
  .last
    JSR Journal_DrawLastPage
    BRA .exit
  .middle
    JSR Journal_DrawMiddlePage
  .exit
  
  JSR Journal_DrawEntry

  SEP #$30
  PLB
  RTL
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