; Book of Secrets Journal Menu

; ---------------------------------------------------------
; Journal Handler
; ---------------------------------------------------------

Journal_Handler:
{
  PHB : PHK : PLB
  SEP #$30  ; Ensure 8-bit A and X/Y for input handling

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
    LDA.b #$20 : STA.w $012F  ; Play page scroll sound
    LDA.b #$0A : STA.w $0207  ; Set delay
    JMP .exit

  .check_right
  ; Check for R button press
  LDA.b $F2 : BIT.b #$10 : BEQ .exit
    REP #$30
    JSR Journal_NextPage
    JSL Menu_DrawJournal
    SEP #$30
    LDA.b #$20 : STA.w $012F  ; Play page scroll sound
    LDA.b #$0A : STA.w $0207  ; Set delay

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

    ; Wrap logic for multiple lines (up to 9 lines supported)
    ; Row Width = $40 bytes (32 tiles * 2 bytes)
    ; Each line is 16 chars ($20 bytes), then skip $20 to next row

    CPY.w #$0020 : BNE .check_line_2
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_2
    CPY.w #$0060 : BNE .check_line_3
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_3
    CPY.w #$00A0 : BNE .check_line_4
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_4
    CPY.w #$00E0 : BNE .check_line_5
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_5
    CPY.w #$0120 : BNE .check_line_6
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_6
    CPY.w #$0160 : BNE .check_line_7
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_7
    CPY.w #$01A0 : BNE .check_line_8
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_8
    CPY.w #$01E0 : BNE .check_line_9
      TYA : CLC : ADC.w #$0020 : TAY
    .check_line_9

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
  ; === Chapter 0: A Hero is Born ===
  dl $7EF3C5 : db $02 : dw Entry_TheCall        ; GameState = $02 (Farore intro)
  dl $7EF3C6 : db $04 : dw Entry_CastAway       ; OOSPROG2 bit 2 (Kydrog intro)

  ; === Chapter 1: The Maku Tree ===
  dl $7EF3D4 : db $01 : dw Entry_MakuTree       ; MakuTreeQuest = $01
  dl $7EF3C7 : db $01 : dw Entry_FirstEssence   ; MapIcon = $01 (Mushroom Grotto)

  ; === Ocarina Quest Chain (HINT -> PROGRESS -> COMPLETE) ===
  dl $7EF3D7 : db $01 : dw Entry_MaskShop       ; SideQuestProg bit 0 (met salesman)
  dl $7EF3D7 : db $02 : dw Entry_CursedGirl     ; SideQuestProg bit 1 (found cucco)
  dl $7EF3D7 : db $08 : dw Entry_GotMushroom    ; SideQuestProg bit 3 (got mushroom)
  dl $7EF344 : db $02 : dw Entry_GotPowder      ; MagicPowder = $02
  dl $7EF3D8 : db $01 : dw Entry_CurseBroken    ; SideQuestProg2 bit 0 (ranch girl)
  dl $7EF3D8 : db $04 : dw Entry_SongLearned    ; SideQuestProg2 bit 2 (song taught)

  ; === Deku Mask Chain ===
  dl $7EF3D7 : db $04 : dw Entry_DyingDeku      ; SideQuestProg bit 2 (found deku)
  dl $7EF3D8 : db $10 : dw Entry_DekuFreed      ; SideQuestProg2 bit 4 (soul freed)
  dl $7EF349 : db $01 : dw Entry_DekuMask       ; DekuMask obtained

  ; === Dungeon Completions ===
  dl $7EF398 : db $01 : dw Entry_D1Complete     ; Scrolls bit 0 (Mushroom Grotto)
  dl $7EF398 : db $02 : dw Entry_D2Complete     ; Scrolls bit 1 (Tail Palace)
  dl $7EF398 : db $04 : dw Entry_D3Complete     ; Scrolls bit 2 (Kalyxo Castle)
  dl $7EF398 : db $08 : dw Entry_D4Complete     ; Scrolls bit 3 (Zora Temple)
  dl $7EF398 : db $10 : dw Entry_D5Complete     ; Scrolls bit 4 (Glacia Estate)
  dl $7EF398 : db $20 : dw Entry_D6Complete     ; Scrolls bit 5 (Goron Mines)
  dl $7EF398 : db $40 : dw Entry_D7Complete     ; Scrolls bit 6 (Dragon Ship)

  ; === Mask Collection ===
  dl $7EF347 : db $01 : dw Entry_ZoraMask       ; ZoraMask obtained
  dl $7EF358 : db $01 : dw Entry_WolfMask       ; WolfMask obtained
  dl $7EF348 : db $01 : dw Entry_BunnyHood      ; BunnyHood obtained

  ; === Other Side Quests ===
  dl $7EF39B : db $01 : dw Entry_BeanPlanted    ; MagicBeanProg bit 0 (planted)
  dl $7EF3D7 : db $10 : dw Entry_OldManQuest    ; SideQuestProg bit 4 (old man)
  dl $7EF3D7 : db $20 : dw Entry_GoronQuest     ; SideQuestProg bit 5 (goron)

  dw $0000 ; Terminator

; ---------------------------------------------------------
; Chapter 0: A Hero is Born
; ---------------------------------------------------------

Entry_TheCall:
  dw "THE_CALL________"
  dw "________________"
  dw "A_VOICE_CALLED__"
  dw "OUT_TO_ME..._IT_"
  dw "SAID_ACCEPT_THIS"
  dw "QUEST__HERO.____"
  dw $FFFF

Entry_CastAway:
  dw "CAST_AWAY_______"
  dw "________________"
  dw "KYDROG_TOOK_____"
  dw "FARORE_AND_CAST_"
  dw "ME_TO_THE_ABYSS."
  dw "FIND_MAKU_TREE._"
  dw $FFFF

; ---------------------------------------------------------
; Chapter 1: The Maku Tree
; ---------------------------------------------------------

Entry_MakuTree:
  dw "THE_MAKU_TREE___"
  dw "________________"
  dw "I_FOUND_THE_____"
  dw "MAKU_TREE._IMPA_"
  dw "AWAITS_IN_THE___"
  dw "HALL_OF_SECRETS."
  dw $FFFF

Entry_FirstEssence:
  dw "FIRST_ESSENCE___"
  dw "________________"
  dw "DARKNESS_LURKS__"
  dw "IN_THE_MUSHROOM_"
  dw "GROTTO_TO_THE___"
  dw "WEST.___________"
  dw $FFFF

; ---------------------------------------------------------
; Ocarina Quest Chain
; ---------------------------------------------------------

Entry_MaskShop:
  dw "MASK_SHOP_______"
  dw "________________"
  dw "A_SALESMAN_EAST_"
  dw "OF_VILLAGE_SELLS"
  dw "MASKS._HE_NEEDS_"
  dw "ME_TO_HAVE_AN___"
  dw "OCARINA._A_GIRL_"
  dw "AT_TOTO_RANCH___"
  dw "MIGHT_HELP._____"
  dw $FFFF

Entry_CursedGirl:
  dw "CURSED_GIRL_____"
  dw "________________"
  dw "A_GIRL_AT_TOTO__"
  dw "RANCH_IS_CURSED!"
  dw "SHE_HAS_BEEN____"
  dw "TURNED_INTO_A___"
  dw "CUCCO._MAGIC____"
  dw "POWDER_MIGHT____"
  dw "BREAK_THE_SPELL."
  dw $FFFF

Entry_GotMushroom:
  dw "STRANGE_MUSHROOM"
  dw "________________"
  dw "FOUND_A_STRANGE_"
  dw "MUSHROOM_IN_THE_"
  dw "WOODS._THE______"
  dw "POTION_SHOP_____"
  dw "MIGHT_WANT_THIS."
  dw $FFFF

Entry_GotPowder:
  dw "MAGIC_POWDER____"
  dw "________________"
  dw "THE_WITCH_MADE__"
  dw "POWDER_FROM_THE_"
  dw "MUSHROOM._IT_HAS"
  dw "TRANSFORMATIVE__"
  dw "POWER.__________"
  dw $FFFF

Entry_CurseBroken:
  dw "CURSE_BROKEN____"
  dw "________________"
  dw "THE_POWDER______"
  dw "BROKE_THE_CURSE!"
  dw "THE_RANCH_GIRL__"
  dw "GAVE_ME_HER_____"
  dw "OCARINA_AND_____"
  dw "TAUGHT_ME_THE___"
  dw "SONG_OF_STORMS._"
  dw $FFFF

Entry_SongLearned:
  dw "SONG_OF_HEALING_"
  dw "________________"
  dw "THE_MASK________"
  dw "SALESMAN_TAUGHT_"
  dw "ME_THE_SONG_OF__"
  dw "HEALING._IT_CAN_"
  dw "FREE_TROUBLED___"
  dw "SPIRITS_FROM____"
  dw "THEIR_PAIN._____"
  dw $FFFF

; ---------------------------------------------------------
; Deku Mask Chain
; ---------------------------------------------------------

Entry_DyingDeku:
  dw "DYING_DEKU______"
  dw "________________"
  dw "A_DEKU_SCRUB_IN_"
  dw "THE_WOODS_IS____"
  dw "WITHERING_AWAY._"
  dw "HIS_SPIRIT_SEEMS"
  dw "TROUBLED..._____"
  dw "PERHAPS_A_______"
  dw "HEALING_MELODY?_"
  dw $FFFF

Entry_DekuFreed:
  dw "DEKU_FREED______"
  dw "________________"
  dw "THE_SONG_FREED__"
  dw "THE_DEKUS_______"
  dw "TORTURED_SOUL.__"
  dw "HE_LEFT_BEHIND__"
  dw "A_MASK..._______"
  dw $FFFF

Entry_DekuMask:
  dw "DEKU_MASK_______"
  dw "________________"
  dw "WITH_THE_DEKU___"
  dw "MASK_I_CAN_TAKE_"
  dw "DEKU_FORM._THIS_"
  dw "WILL_HELP_ME____"
  dw "TRAVERSE_THE____"
  dw "SWAMPS_TO_______"
  dw "TAIL_PALACE.____"
  dw $FFFF

; ---------------------------------------------------------
; Dungeon Completions
; ---------------------------------------------------------

Entry_D1Complete:
  dw "GROTTO_CLEARED__"
  dw "________________"
  dw "THE_MUSHROOM____"
  dw "GROTTO_IS_FREE__"
  dw "OF_EVIL._I_FOUND"
  dw "THE_BOW_WITHIN._"
  dw $FFFF

Entry_D2Complete:
  dw "TAIL_PALACE_____"
  dw "________________"
  dw "MOLDORM_FALLS.__"
  dw "THE_ROCS_FEATHER"
  dw "GRANTS_ME_THE___"
  dw "GIFT_OF_FLIGHT._"
  dw $FFFF

Entry_D3Complete:
  dw "KALYXO_CASTLE___"
  dw "________________"
  dw "THE_CASTLE_IS___"
  dw "RECLAIMED._THE__"
  dw "MEADOW_BLADE____"
  dw "IS_MINE.________"
  dw $FFFF

Entry_D4Complete:
  dw "ZORA_TEMPLE_____"
  dw "________________"
  dw "THE_WATERS_ARE__"
  dw "PURIFIED._THE___"
  dw "HOOKSHOT_WILL___"
  dw "AID_MY_QUEST.___"
  dw $FFFF

Entry_D5Complete:
  dw "GLACIA_ESTATE___"
  dw "________________"
  dw "TWINROVA_IS_____"
  dw "DEFEATED._THE___"
  dw "FIRE_ROD_MELTS__"
  dw "ALL_OBSTACLES.__"
  dw $FFFF

Entry_D6Complete:
  dw "GORON_MINES_____"
  dw "________________"
  dw "THE_MINES_ARE___"
  dw "SAFE._THE_HAMMER"
  dw "BREAKS_THROUGH__"
  dw "ANY_BARRIER.____"
  dw $FFFF

Entry_D7Complete:
  dw "DRAGON_SHIP_____"
  dw "________________"
  dw "THE_ANCIENT_SHIP"
  dw "YIELDS_ITS______"
  dw "SECRET:_THE_____"
  dw "SOMARIA_ROD.____"
  dw $FFFF

; ---------------------------------------------------------
; Mask Collection
; ---------------------------------------------------------

Entry_ZoraMask:
  dw "ZORA_MASK_______"
  dw "________________"
  dw "THE_PRINCESS____"
  dw "GAVE_ME_A_MASK._"
  dw "I_CAN_BREATHE___"
  dw "UNDERWATER._____"
  dw $FFFF

Entry_WolfMask:
  dw "WOLF_MASK_______"
  dw "________________"
  dw "THE_WOLFOS______"
  dw "SPIRIT_IS_AT____"
  dw "PEACE._ITS_MASK_"
  dw "GRANTS_SPEED____"
  dw "AT_NIGHT._______"
  dw $FFFF

Entry_BunnyHood:
  dw "BUNNY_HOOD______"
  dw "________________"
  dw "THE_MASK________"
  dw "SALESMAN_SOLD___"
  dw "ME_A_BUNNY_HOOD."
  dw "I_CAN_RUN_______"
  dw "FASTER_NOW._____"
  dw $FFFF

; ---------------------------------------------------------
; Other Side Quests
; ---------------------------------------------------------

Entry_BeanPlanted:
  dw "MAGIC_BEAN______"
  dw "________________"
  dw "I_PLANTED_A_____"
  dw "MAGIC_BEAN._IT__"
  dw "NEEDS_WATER_AND_"
  dw "A_BEES_BLESSING."
  dw $FFFF

Entry_OldManQuest:
  dw "OLD_MAN_________"
  dw "________________"
  dw "AN_OLD_MAN_IS___"
  dw "LOST_IN_THE_____"
  dw "LAVA_LANDS._IF_I"
  dw "ESCORT_HIM_HOME_"
  dw "HE_MAY_REWARD___"
  dw "ME._____________"
  dw $FFFF

Entry_GoronQuest:
  dw "GORON_QUEST_____"
  dw "________________"
  dw "THE_GORON_NEEDS_"
  dw "5_ROCK_SIRLOINS_"
  dw "TO_OPEN_THE_____"
  dw "MINES._I_SHOULD_"
  dw "SEARCH_THE______"
  dw "MOUNTAINS.______"
  dw $FFFF

; ---------------------------------------------------------
; Background Drawing
; ---------------------------------------------------------

Menu_DrawJournal:
{
  PHB : PHK : PLB
  REP #$30

  ; Page selection logic:
  ; 0 -> First page background
  ; Last -> Last page background
  ; Else -> Middle page background

  LDA.l JournalState : AND.w #$00FF : BNE .not_first
    ; JournalState == 0, draw first page
    JSR Journal_DrawFirstPage
    BRA .draw_entry
  .not_first

  ; Check if this is the last page
  PHA
  JSR Journal_CountUnlocked : DEC A : STA.b $02
  PLA
  CMP.b $02 : BNE .middle
    ; This is the last page
    JSR Journal_DrawLastPage
    BRA .draw_entry
  .middle
    JSR Journal_DrawMiddlePage

  .draw_entry
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
