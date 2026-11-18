; Quest displays progression: the essence ring (pendants in its centre) on the right, and
; on the left the Moon Pearl, heart pieces and a 2x2 block of passive gear (shield,
; glove, boots, flippers). Supplies live on Equipment; the area name heads the Map page.
; No ownership or save-format changes. DBR = $2D.
if !ENABLE_MENU_MAP_TRAVEL == 1
  !QuestPearlCol = menu_offset(0,3)     ; absolute (9,7)
  !QuestCountCol = menu_offset(6,9)     ; absolute (11,9-11), under the hearts at (9,10)
else
  !QuestPearlCol = menu_offset(0,2)
  !QuestCountCol = menu_offset(6,23)
endif

Menu_Quest_Init:
{
  SEP #$30
  STZ.w $0207
if !ENABLE_MENU_MAP_TRAVEL == 1
  JSL QuestSongs_Init                ; pick the song cursor ($020B)
endif
  RTS
}

Menu_QuestScreen:
{
  SEP #$30
if !ENABLE_MENU_MAP_TRAVEL == 1
  ; A/Y on a learned song binds it to the Ocarina (consumes A).
  JSL QuestSongs_Frame : BCS .no_journal
endif
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
    JSR Menu_CheckJournalUnlocked : BCC .no_journal
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
  ; v4: no area name here (it heads the Map page) and no LINK/clock footer.
  ; Clear the 14 footer cells so a previous page's footer text never shows.
  LDX.w #$001A
.clear_footer
  LDA.w #$2417 : STA.w $1692,X
  DEX #2 : BPL .clear_footer

  JSR Menu_DrawHeartPieces
  LDA.l $7EF36B : AND.w #$00FF
  LDX.w #!QuestRow+!QuestCountCol   ; under the heart-piece container
  JSR Menu_Quest_Number3
  JSR Menu_Quest_Progress
  JSR Menu_Quest_Gear
if !ENABLE_MENU_MAP_TRAVEL == 1
  ; The dungeon row (map, big chest key, big key, treasure) is on the Map page.
  REP #$30
  JSR Menu_DrawMusicNotes            ; bottom row: the six songs
  JSL QuestSongs_DrawCursor          ; bracket + footer song name
else
  REP #$30
  JSR Menu_DrawBigKey
  REP #$30
  JSR Menu_DrawBigChestKey
endif
  SEP #$30
  RTS
}

; Quest left side (OoT gear-box style): the Moon Pearl and heart pieces on
; the top row, below them a 2x2 block of the passive gear the player
; cannot select (shield, glove, boots, flippers); Equipment keeps the swords,
; tunic, masks and rings. With the four-page menu the six songs take the
; bottom row and the dungeon row moves to the Map page. Without it the bottom
; row is Pearl | map, big chest key, big key, treasure | hearts.
Menu_Quest_Gear:
{
  SEP #$30
  LDA.b #$7E : STA.b $0A
  LDA.l $7EF357 : BEQ .pearl_variant
  LDA.b #$01
.pearl_variant
  STA.w MenuItemValueSpoof
  REP #$30
  LDA.w #MenuItemValueSpoof
  LDX.w #!QuestRow+!QuestPearlCol
  LDY.w #MoonPearlGFX
  JSR DrawMenuItem
  SEP #$30
  LDY.b #$00
.gear
  PHY
  LDA.w .gear_slot,Y : JSR Menu_Quest_GearVariant
  STA.w MenuItemValueSpoof
  REP #$30
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w .gear_gfx,X : TAY
  LDA.w .gear_pos,X : TAX
  LDA.w #MenuItemValueSpoof
  JSR DrawMenuItem
  SEP #$30
  PLY
  INY : CPY.b #$04 : BCC .gear
  RTS
.gear_slot
  db $13,$0F,$10,$11                    ; shield, glove, boots, flippers
; DrawMenuItem offsets (absolute minus 4,4): (13,7) (13,10) / (16,7) (16,10)
.gear_pos
  dw menu_offset(9,3),menu_offset(9,6),menu_offset(12,3),menu_offset(12,6)
.gear_gfx
  dw ShieldGFX,PowerGloveGFX,PegasusBootsGFX,FlippersGFX
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
if !ENABLE_EQUIPMENT_MENU == 1
  JSL Tunic_WornVariant : BRA .done  ; worn colour 0-2 -> variants 1-3
else
  CMP.b #$03 : BCS .none
  INC : BRA .done                    ; SRAM 0-2 -> green/blue/red variants 1-3
endif
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
  INY : CPY.b #$08 : BCC .essences
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
  db !Crystal_D8_Sky
; Ring clockwise D1..D8 from the top, 12 columns wide (cols 14-25, right of
; the gear block), mirror-symmetric about cols 19-20;
; Tests/test_quest_essence_layout.py guards the footprint. Absolute tilemap
; offsets, 2x2 each.
.crystal_pos
  dw menu_offset(10,19),menu_offset(11,23),menu_offset(14,24),menu_offset(17,23)
  dw menu_offset(18,19),menu_offset(17,15),menu_offset(14,14),menu_offset(11,15)
.pendant_bits
  db !Pendant_Wisdom,!Pendant_Power,!Pendant_Courage
; Pendants form a triangle in the ring centre: Power on top, Wisdom
; bottom-left, Courage bottom-right (table order Wisdom, Power, Courage).
.pendant_pos
  dw menu_offset(15,17),menu_offset(13,19),menu_offset(15,21)
; Unowned = the owned tiles in palette 4, the grey of the unowned crystal
; ($3134), so v4 needs no outline art ($104/$105/$114/$115/$13B/$13C/
; $121/$122 stay only for the legacy quest_icons.tilemap page).
.pendant_tiles
  dw $3102,$3103,$3112,$3113, $2502,$2503,$2512,$2513
  dw $313D,$313E,$B13D,$B13E, $3D3D,$3D3E,$BD3D,$BD3E
  dw $3123,$3124,$B123,$B124, $2D23,$2D24,$AD23,$AD24
}
