; Quest supplies use their own cursor ($020C), independent of the Y item and
; Equipment's $020B. No ownership or save-format changes. DBR = $2D.
Menu_Quest_Init:
{
  SEP #$30
  STZ.w $020C
  STZ.w $0207
  RTS
}

Menu_QuestScreen:
{
  SEP #$30
  LDA.w $020C : CMP.b #$06 : BCC .valid
  STZ.w $020C
.valid
  LDA.b $F4 : BIT.b #$10 : BEQ .no_start
    LDA.b #!MENU_STATE_INIT_SCROLL_DOWN : STA.w $0200
    RTS
.no_start
  ; Page-loop R is handled by Menu_Page3_StatsScreen. Other L/R routes
  ; return through the existing scroll-from state; A is reserved for Use.
  LDA.b $F6 : AND.b #$30 : BEQ .no_lr
    BIT.b #$20 : BEQ .right
    REP #$20
    LDA.w #$FFF8 : BRA .turn
.right
    REP #$20
    LDA.w #$0008
.turn
    STA.w MenuScrollHDirection
    SEP #$30
    LDA.b #!MENU_STATE_SCROLL_FROM : STA.w $0200
    LDA.b #$06 : STA.w $012F
    RTS
.no_lr
  LDA.b $F6 : BIT.b #$40 : BEQ .no_journal
if !ENABLE_MENU_HIDE_RINGS_JOURNAL_EARLY == 1
    JSR Menu_CheckJournalUnlocked : BCC .no_journal
endif
    LDA.b #!MENU_STATE_JOURNAL : STA.w $0200
    REP #$20
    LDA.w #$0000 : STA.l JournalState
    JSL Menu_DrawJournal
    SEP #$30
    LDA.b #$11 : STA.w $012F
    BRA .upload
.no_journal
  JSR Menu_Quest_Move
  ; The established food handlers dispatch on $020B. Restore Equipment's
  ; cursor afterward; the Quest page never changes the equipped Y item.
  LDA.w $020B : PHA
  LDA.w $020C : STA.w $020B
  JSR MagicBag_ConsumeItem
  PLA : STA.w $020B
  INC.w $0207
  JSR Menu_Quest_Draw
.upload
  LDA.b #$23 : STA.w $0116
  LDA.b #$01 : STA.b $17
  RTS
}

Menu_Quest_Move:
{
  LDA.b $F4 : AND.b #$0F : BEQ .done
  BIT.b #$03 : BNE .horizontal
  BIT.b #$04 : BEQ .up
  LDA.w $020C : CLC : ADC.b #$02 : CMP.b #$06 : BCC .store
  SEC : SBC.b #$06 : BRA .store
.up
  LDA.w $020C : CMP.b #$02 : BCS .subtract
  CLC : ADC.b #$06
.subtract
  SEC : SBC.b #$02 : BRA .store
.horizontal
  LDA.w $020C : EOR.b #$01
.store
  STA.w $020C
  LDA.b #$20 : STA.w $012F
.done
  RTS
}

Menu_Quest_Draw:
{
  JSR Menu_DrawBackground
  JSR Menu_DrawQuestStatus
  ; Reuse the existing location/name encoders, then move their output into
  ; the three-row header before drawing the essence ring over the old cells.
  JSR DrawLocationName
  LDX.w #$001E
.location
  LDA.w $12CC,X : STA.w $1000+menu_offset(10,6),X
  LDA.w #$3417 : STA.w $12CC,X
  DEX #2 : BPL .location
  JSR Menu_DrawCharacterName
  LDX.w #$000C
.name
  LDA.w $134C,X : STA.w $1000+menu_offset(11,6),X
  LDA.w #$3417 : STA.w $134C,X
  DEX #2 : BPL .name
  JSR Menu_DrawPlaytimeLabel
  LDX.w #$0008
.clock
  LDA.w $16A4,X : STA.w $1000+menu_offset(11,14),X
  DEX #2 : BPL .clock
  LDX.w #$000E
.label
  LDA.w .location_label,X : STA.w $1000+menu_offset(9,6),X
  DEX #2 : BPL .label

  JSR Menu_DrawHeartPieces
  LDA.l $7EF36B : AND.w #$00FF
  LDX.w #menu_offset(11,24)
  JSR Menu_Quest_Number3
  JSR Menu_Quest_Progress
  REP #$30
  JSR Menu_DrawBigKey
  REP #$30
  JSR Menu_DrawBigChestKey
  REP #$30
  LDA.w $040C : AND.w #$00FF : CMP.w #$00FF : BEQ .no_dungeon
  LDX.w #$000C
.dungeon
  LDA.w .dungeon_label,X : STA.w $1000+menu_offset(21,6),X
  DEX #2 : BPL .dungeon
.no_dungeon
  SEP #$30
  LDA.b #$7E : STA.b $0A
  LDY.b #$00
.supplies
  PHY
  REP #$30
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w Menu_Quest_Gfx,X : TAY
  LDA.w Menu_Quest_Pos,X : TAX
  LDA.w #$0001 : STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  JSR DrawMenuItem
  SEP #$30
  PLY : PHY
  LDA.w Menu_Quest_CountLow,Y : TAX
  LDA.l $7EF300,X
  REP #$30
  AND.w #$00FF : PHA
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w Menu_Quest_CountPos,X : TAX
  PLA : JSR Menu_Quest_Number3
  SEP #$30
  PLY
  INY : CPY.b #$06 : BCC .supplies

  LDA.w $020C : CMP.b #$06 : BCC .cursor_valid
  STZ.w $020C
.cursor_valid
  LDA.w $0207 : AND.b #$20 : BNE .no_cursor
  LDA.w $020C : ASL : TAX
  REP #$30
  LDA.w Menu_Quest_Pos,X : TAX
  LDA.w #$3060 : JSR Menu_Equipment_Bracket
.no_cursor
  REP #$30
  LDA.w $020C : AND.w #$00FF : ASL : TAX
  LDA.w .names,X : TAX
  LDY.w #$0000
.footer
  LDA.w $0000,X : STA.w $1692,Y
  INX #2 : INY #2 : CPY.w #$001C : BCC .footer
  SEP #$30
  RTS
.location_label
  dw "LOCATION"
.dungeon_label
  dw "DUNGEON"
.names
  dw .banana,.pineapple,.meat,.shell,.honey,.stick
.banana
  dw "A:_BANANAS____"
.pineapple
  dw "A:_PINEAPPLES_"
.meat
  dw "GORON:_5_MEAT_"
.shell
  dw "__SEASHELLS___"
.honey
  dw "A:_HONEYCOMBS_"
.stick
  dw "_DEKU_STICKS__"
}

; A=0..255, X=absolute tilemap offset, M/X=16. Three digits with leading
; spaces; unlike TimeLabels this covers every possible stored byte count.
Menu_Quest_Number3:
{
  LDY.w #$0000
.hundreds
  CMP.w #100 : BCC .hundreds_done
  SEC : SBC.w #100 : INY : BRA .hundreds
.hundreds_done
  STA.b $04
  TYA : STA.b $06 : BEQ .blank_hundred
  CLC : ADC.w #$2570 : BRA .hundred_tile
.blank_hundred
  LDA.w #$2417
.hundred_tile
  STA.w $1000,X
  LDA.b $04
  LDY.w #$0000
.tens
  CMP.w #10 : BCC .tens_done
  SEC : SBC.w #10 : INY : BRA .tens
.tens_done
  STA.b $04
  TYA : BNE .ten_digit
  LDA.b $06 : BEQ .blank_ten
  TYA
.ten_digit
  CLC : ADC.w #$2570 : BRA .ten_tile
.blank_ten
  LDA.w #$2417
.ten_tile
  STA.w $1002,X
  LDA.b $04 : CLC : ADC.w #$2570 : STA.w $1004,X
  RTS
}

Menu_Quest_Progress:
{
  SEP #$30
  LDY.b #$00
.essences
  PHY
  LDA.w .crystal_bits,Y : AND.l Crystals
  REP #$30
  AND.w #$00FF : BEQ .empty
  LDA.w #$3534 : BRA .triangle
.empty
  LDA.w #$3134
.triangle
  PHA
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w .crystal_pos,X : TAX
  PLA
  STA.w $1000,X : INC : STA.w $1002,X
  CLC : ADC.w #$000F
  STA.w $1040,X : INC : STA.w $1042,X
  SEP #$30
  PLY
  INY : CPY.b #$07 : BCC .essences
  LDY.b #$00
.pendants
  PHY
  LDA.w .pendant_bits,Y : AND.l Pendants
  REP #$30
  AND.w #$00FF : BEQ .unowned
  LDA.w #$0008
.unowned
  STA.b $04
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w .pendant_pos,X : PHA
  TYA : AND.w #$00FF : ASL #4 : CLC : ADC.b $04 : TAY
  PLX
  LDA.w .pendant_tiles,Y : STA.w $1000,X
  LDA.w .pendant_tiles+2,Y : STA.w $1002,X
  LDA.w .pendant_tiles+4,Y : STA.w $1040,X
  LDA.w .pendant_tiles+6,Y : STA.w $1042,X
  SEP #$30
  PLY
  INY : CPY.b #$03 : BCC .pendants
  REP #$30
  RTS
.crystal_bits
  db !Crystal_D1_MushroomGrotto,!Crystal_D2_TailPalace,!Crystal_D3_KalyxoCastle
  db !Crystal_D4_ZoraTemple,!Crystal_D5_GlaciaEstate,!Crystal_D6_GoronMines,!Crystal_D7_DragonShip
.crystal_pos
  dw menu_offset(12,10),menu_offset(13,14),menu_offset(16,15),menu_offset(19,12)
  dw menu_offset(19,8),menu_offset(16,5),menu_offset(13,6)
.pendant_bits
  db !Pendant_Wisdom,!Pendant_Power,!Pendant_Courage
.pendant_pos
  dw menu_offset(15,10),menu_offset(17,8),menu_offset(17,12)
.pendant_tiles
  dw $2504,$2505,$2514,$2515, $2502,$2503,$2512,$2513
  dw $253B,$253C,$A53B,$A53C, $3D3D,$3D3E,$BD3D,$BD3E
  dw $2521,$2522,$A521,$A522, $2D23,$2D24,$AD23,$AD24
}

Menu_Quest_Pos:
  dw menu_offset(8,15),menu_offset(8,20),menu_offset(12,15)
  dw menu_offset(12,20),menu_offset(16,15),menu_offset(16,20)
Menu_Quest_CountPos:
  dw menu_offset(14,18),menu_offset(14,23),menu_offset(18,18)
  dw menu_offset(18,23),menu_offset(22,18),menu_offset(22,23)
Menu_Quest_CountLow:
  db $8B,$8D,$8F,$91,$93,$95
Menu_Quest_Gfx:
  dw BananaGFX,PineappleGFX,RockMeatGFX,SeashellGFX,HoneycombGFX,DekuStickGFX
