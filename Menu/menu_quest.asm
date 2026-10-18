; Quest displays progression and passive gear. Supplies live on Equipment.
; No ownership or save-format changes. DBR = $2D.
Menu_Quest_Init:
{
  SEP #$30
  STZ.w $0207
  RTS
}

Menu_QuestScreen:
{
  SEP #$30
  LDA.b $F6 : BIT.b #$80 : BNE .close
  LDA.b $F4 : BIT.b #$10 : BEQ .no_start
.close
    LDA.b #!MENU_STATE_INIT_SCROLL_DOWN : STA.w $0200
    RTS
.no_start
  ; Page-loop R is handled by Menu_Page3_StatsScreen. Other L/R routes
  ; return through the existing scroll-from state; A closes this passive page.
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
  JSR Menu_Quest_Draw
.upload
  LDA.b #$23 : STA.w $0116
  LDA.b #$01 : STA.b $17
  RTS
}

Menu_Quest_Draw:
{
  JSR Menu_DrawBackground
  JSR Menu_DrawQuestStatus
  ; Reuse the location/name encoders. The location stands alone above the
  ; progression ring; the footer holds seven name cells and the five-cell clock.
  JSR DrawLocationName
  LDX.w #$001E
.location
  LDA.w $12CC,X : STA.w $1000+menu_offset(9,6),X
  LDA.w #$3417 : STA.w $12CC,X
  DEX #2 : BPL .location
  JSR Menu_DrawPlaytimeLabel
  LDX.w #$0010
.clear_label
  LDA.w #$2417 : STA.w $1692,X
  DEX #2 : BPL .clear_label
  JSR Menu_DrawCharacterName
  LDX.w #$000C
.name
  LDA.w $134C,X : STA.w $1692,X
  LDA.w #$3417 : STA.w $134C,X
  DEX #2 : BPL .name

  JSR Menu_DrawHeartPieces
  LDA.l $7EF36B : AND.w #$00FF
  LDX.w #menu_offset(23,22)
  JSR Menu_Quest_Number3
  JSR Menu_Quest_Progress
  JSR Menu_Quest_Gear
  REP #$30
  JSR Menu_DrawBigKey
  REP #$30
  JSR Menu_DrawBigChestKey
  SEP #$30
  RTS
}

Menu_Quest_Gear:
{
  REP #$30
  LDX.w #$0006
.gear_label
  LDA.w .gear,X : STA.w $1000+menu_offset(12,19),X
  DEX #2 : BPL .gear_label
  SEP #$30
  LDA.b #$7E : STA.b $0A
  LDY.b #$00
.icons
  PHY
  TYA : CLC : ADC.b #$0F : JSR Menu_Quest_GearVariant
  STA.w MenuItemValueSpoof
  REP #$30
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w .gfx,X : TAY
  LDA.w .pos,X : TAX
  LDA.w #MenuItemValueSpoof
  JSR DrawMenuItem
  SEP #$30
  PLY
  INY : CPY.b #$06 : BCC .icons

  LDA.l $7EF357 : BEQ .pearl_variant
  LDA.b #$01
.pearl_variant
  STA.w MenuItemValueSpoof
  REP #$30
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(17,15) ; absolute (19,21), beside heart pieces
  LDY.w #MoonPearlGFX
  JSR DrawMenuItem
  REP #$30
  RTS
.gear
  dw "GEAR"
.pos
  dw menu_offset(9,14),menu_offset(9,17),menu_offset(9,20)
  dw menu_offset(13,14),menu_offset(13,17),menu_offset(13,20)
.gfx
  dw PowerGloveGFX,PegasusBootsGFX,FlippersGFX,SwordGFX,ShieldGFX,TunicGFX
}

; A = valid gear slot 15-20, 8-bit A/X/Y; clobbers X, preserves Y.
; Explicit SRAM offsets avoid treating Pearl/Wolf Mask as sword/shield.
Menu_Quest_GearVariant:
{
  SEC : SBC.b #$0F : TAX
  PHX
  LDA.w .address,X : TAX
  LDA.l $7EF300,X
  PLX
  CPX.b #$05 : BEQ .tunic
  CPX.b #$03 : BEQ .sword
  CPX.b #$04 : BEQ .shield
  CMP.b #$00 : BEQ .done
  CPX.b #$00 : BNE .boolean
  CMP.b #$03 : BCC .done
  LDA.b #$02 : BRA .done             ; preserve the glove's two variants
.boolean
  LDA.b #$01 : BRA .done
.sword
  CMP.b #$05 : BCC .done             ; 0 absent; 1-4 owned; $FF at smiths
  BRA .none
.shield
  CMP.b #$04 : BCC .done             ; 0 absent; 1-3 owned
  BRA .none
.tunic
  CMP.b #$03 : BCS .none
  INC : BRA .done                    ; SRAM 0-2 -> green/blue/red variants 1-3
.none
  LDA.b #$00
.done
  RTS
.address
  db $54,$55,$56,$59,$5A,$5B          ; glove, boots, flippers, sword, shield, tunic
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
  LDA.w #$2934 : BRA .triangle
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
  dw menu_offset(12,10),menu_offset(13,14),menu_offset(16,15),menu_offset(20,12)
  dw menu_offset(20,8),menu_offset(16,5),menu_offset(13,6)
.pendant_bits
  db !Pendant_Wisdom,!Pendant_Power,!Pendant_Courage
.pendant_pos
  dw menu_offset(15,10),menu_offset(17,8),menu_offset(17,12)
.pendant_tiles
  dw $2504,$2505,$2514,$2515, $2502,$2503,$2512,$2513
  dw $253B,$253C,$A53B,$A53C, $3D3D,$3D3E,$BD3D,$BD3E
  dw $2521,$2522,$A521,$A522, $2D23,$2D24,$AD23,$AD24
}
