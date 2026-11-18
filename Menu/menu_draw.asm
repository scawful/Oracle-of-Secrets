; =========================================================
;  Tilemap Menu background

; This function is bled into via the previous menu.asm file.
Menu_DrawBackground:
{
  REP #$30
  LDX.w #$FE ; $1700-17FF

  .loop
    LDA.w menu_frame, X
    STA.w $1000, X
    LDA.w menu_frame+$100, X
    STA.w $1100, X
    LDA.w menu_frame+$200, X
    STA.w $1200, X
    LDA.w menu_frame+$300, X
    STA.w $1300, X
    LDA.w menu_frame+$400, X
    STA.w $1400, X
    LDA.w menu_frame+$500, X
    STA.w $1500, X
    LDA.w menu_frame+$600, X
    STA.w $1600, X
    LDA.w menu_frame+$700, X
    STA.w $1700, X

    DEX : DEX
  BPL .loop

  RTS
}

; =========================================================
;  Menu Item Draw Routine
;  Credit to Kan

DrawMenuItem:
{
  STA.b $08
  STY.b $00

  LDA.b [$08] : AND.w #$00FF : BNE .not_zero
    LDY.w #NothingGFX
    BRA .draw

  .not_zero

  DEC

  ASL : ASL : ASL
  ADC.b $00
  TAY

  .draw
  LDA.w $0000,Y : STA.w $1108,X
  LDA.w $0002,Y : STA.w $110A,X
  LDA.w $0004,Y : STA.w $1148,X
  LDA.w $0006,Y : STA.w $114A,X

  RTS
}

; =========================================================
;  Quest Icons Tilemap Draw Routine

Menu_DrawQuestIcons:
{
  LDX.w #$10

  .loop
    LDA.l quest_icons, X : STA.w $1364, X
    LDA.l quest_icons+$10, X : STA.w $13A4, X
    LDA.l quest_icons+$20, X : STA.w $13E4, X
    LDA.l quest_icons+$30, X : STA.w $1424, X
    LDA.l quest_icons+$40, X : STA.w $1464, X
    LDA.l quest_icons+$50, X : STA.w $14A4, X
    LDA.l quest_icons+$60, X : STA.w $14E4, X
    DEX : DEX : BPL .loop

  LDA.w #$20F5 : STA.w $13B4 : STA.w $13F4 : STA.w $1474 : STA.w $14B4

  RTS
}

; =========================================================

Menu_DrawTriforceIcons:
{
  LDA.l $7EF37A
  LDX.w #$3534
  LDY.w #$3544

if !ENABLE_MENU_AUDIT_FIXES == 1
  ; Crystals in D1-D7 order (menu audit 2026-09-28). The award ORs
  ; RoomTagPrizeChecks[$040C/2] ($02A1A4, vanilla bytes in oos168.sfc), so
  ; the bits are D6 D1 D5 D7 D2 D4 D3 (Core/sram.asm !Crystal_*). Slots:
  ; top row $1366/$136A/$136E = D1-D3, bottom row $13E4/$13E8/$13EC/$13F0
  ; = D4-D7 (left to right); each triangle's lower half is +$40.
  LSR : BCC +   ; bit 0 $01 D6 -> bottom row, 3rd
    STX.w $13EC : INX : STX.w $13EE : DEX
    STY.w $142C : INY : STY.w $142E : DEY
  +

  LSR : BCC +   ; bit 1 $02 D1 -> top row, 1st
    STX.w $1366 : INX : STX.w $1368 : DEX
    STY.w $13A6 : INY : STY.w $13A8 : DEY
  +

  LSR : BCC +   ; bit 2 $04 D5 -> bottom row, 2nd
    STX.w $13E8 : INX : STX.w $13EA : DEX
    STY.w $1428 : INY : STY.w $142A : DEY
  +

  LSR : BCC +   ; bit 3 $08 D7 -> bottom row, 4th
    STX.w $13F0 : INX : STX.w $13F2 : DEX
    STY.w $1430 : INY : STY.w $1432 : DEY
  +

  LSR : BCC +   ; bit 4 $10 D2 -> top row, 2nd
    STX.w $136A : INX : STX.w $136C : DEX
    STY.w $13AA : INY : STY.w $13AC : DEY
  +

  LSR : BCC +   ; bit 5 $20 D4 -> bottom row, 1st
    STX.w $13E4 : INX : STX.w $13E6 : DEX
    STY.w $1424 : INY : STY.w $1426 : DEY
  +

  LSR : BCC +   ; bit 6 $40 D3 -> top row, 3rd
    STX.w $136E : INX : STX.w $1370 : DEX
    STY.w $13AE : INY : STY.w $13B0 : DEY
  +
else
  LSR : BCC +
    STX.w $1366 : INX : STX.w $1368 : DEX
    STY.w $13A6 : INY : STY.w $13A8 : DEY
  +

  LSR : BCC +
    STX.w $136A : INX : STX.w $136C : DEX
    STY.w $13AA : INY : STY.w $13AC : DEY
  +

  LSR : BCC +
    STX.w $136E : INX : STX.w $1370 : DEX
    STY.w $13AE : INY : STY.w $13B0 : DEY
  +

  LSR : BCC +
    STX.w $13E4 : INX : STX.w $13E6 : DEX
    STY.w $1424 : INY : STY.w $1426 : DEY
  +

  LSR : BCC +
    STX.w $13E8 : INX : STX.w $13EA : DEX
    STY.w $1428 : INY : STY.w $142A : DEY
  +

  LSR : BCC +
    STX.w $13EC : INX : STX.w $13EE : DEX
    STY.w $142C : INY : STY.w $142E : DEY
  +

  LSR : BCC +
    STX.w $13F0 : INX : STX.w $13F2 : DEX
    STY.w $1430 : INY : STY.w $1432 : DEY
  +
endif

  RTS
}

; =========================================================

Menu_DrawPendantIcons:
{
  LDA.l $7EF374

  ; Power
  LSR : BCC +
    LDX.w #$2502 : STX.w $14A4 : INX : STX.w $14A6
    LDX.w #$2512 : STX.w $14E4 : INX : STX.w $14E6
  +

  LSR : BCC +
    LDX.w #$3D3D : STX.w $14AA : INX : STX.w $14AC
    LDX.w #$BD3D : STX.w $14EA : INX : STX.w $14EC
  +

  ; Wisdom
  LSR : BCC +
    LDX.w #$2D23 : STX.w $14B0 : INX : STX.w $14B2
    LDX.w #$AD23 : STX.w $14F0 : INX : STX.w $14F2
  +

  RTS
}

; =========================================================

; V H O P P P T T    T T T T T T T T <- tile format
; V = Vertical Flip
; H = Horizontal Flip
; O = Priority
; P = Palette 0 to 7
; T = Tile (which is normally called C for Character) 0 to 1023
; E000 is T = 0
; E100 would be T = 16

; Quest top row (Pearl ... hearts) and the dungeon row (map, big chest key,
; big key, treasure), as DrawMenuItem row offsets (absolute row minus 4).
; With the four-page menu the songs take the Quest bottom row
; (Menu_DrawMusicNotes), Pearl and hearts the top-left (Menu_Quest_Gear), and the dungeon
; row sits on the Map page under the Map cell (MenuMapTravel_Draw). Without
; it the dungeon row is on the Quest bottom row between Pearl and hearts.
if !ENABLE_MENU_MAP_TRAVEL == 1
  !QuestRow = menu_offset(5,0)          ; absolute row 9, first panel row under the frame border
  !DungeonRow = menu_offset(13,0)       ; Map page, absolute row 17
else
  !QuestRow = menu_offset(17,0)
  !DungeonRow = !QuestRow
endif

Menu_DrawHeartPieces:
{
if !ENABLE_EQUIPMENT_MENU == 1
if !ENABLE_MENU_MAP_TRAVEL == 1
  !QuestHeart = $1000+!QuestRow+menu_offset(4,10)  ; Quest top row, beside the Pearl: absolute (9,10)
else
  !QuestHeart = $1000+!QuestRow+menu_offset(4,24)  ; Quest bottom row, right end
endif
else
  !QuestHeart = $149E
endif
  ; Empty heart container
  LDX.w #$2484 : STX.w !QuestHeart ; top left
  LDX.w #$6484 : STX.w !QuestHeart+2 ; top right
  LDX.w #$2485 : STX.w !QuestHeart+$40 ; bottom left
  LDX.w #$6485 : STX.w !QuestHeart+$42 ; bottom right

  LDA.l $7EF36B
  AND.w #$00FF
  CMP.w #3 : BEQ .top_right
    CMP.w #1 : BEQ .top_left
      BCS .bottom_left
        RTS

  .top_right
  LDX.w #$64AD : STX.w !QuestHeart+2

  .bottom_left
  LDX.w #$24AE : STX.w !QuestHeart+$40

  .top_left
  LDX.w #$24AD : STX.w !QuestHeart
  RTS
}

; =========================================================

Menu_DrawMusicNotes:
{
  SEP #$30
  LDA.b #$7E : STA.b $0A
  JSL UpdateFluteSong_Long
  LDY.b #$00
.notes
  PHY
  TYX : LDA.l Menu_SongOrder,X          ; Y = slot, A = song in it
if !ENABLE_EPONA_SONG == 1
  JSL Ocarina_SongLearned_Long : BCC .unlearned
  INC : BRA .variant                    ; variant = song + 1
else
  INC : CMP.l $7EF34C : BCC .variant : BEQ .variant
endif
.unlearned
  LDA.b #$01
.variant
  STA.w MusicNoteValue
  REP #$30
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w .positions,X : TAX
  LDA.w #MusicNoteValue
  LDY.w #QuarterNoteGFX
  JSR DrawMenuItem
  SEP #$30
  PLY : INY : CPY.b #$06 : BCC .notes
  REP #$30
  RTS
; DrawMenuItem offsets; QuestSongs_DrawCursor (bank $2B) reads this table
; long to place its bracket. Four-page menu: Quest bottom row (absolute 21).
.positions
if !ENABLE_MENU_MAP_TRAVEL == 1
  dw menu_offset(17,3),menu_offset(17,6),menu_offset(17,9)
  dw menu_offset(17,13),menu_offset(17,16),menu_offset(17,19)
else
  dw menu_offset(9,3),menu_offset(9,6),menu_offset(9,9)
  dw menu_offset(9,13),menu_offset(9,16),menu_offset(9,19)
endif
}

; Song order on the row (slot -> song) and its inverse (song - 1 -> slot).
; Song numbers ($030F, SavedOcarinaSong) are unchanged; only the row order
; follows the quest: Epona's Song comes with the Ocarina (beat 10), then
; Healing, Storms, Soaring, Time and Secrets in the teacher-count order.
; QuestSongs_* (bank $2B) read both tables long.
Menu_SongOrder:
if !ENABLE_MENU_MAP_TRAVEL == 1 && !ENABLE_EPONA_SONG == 1
  db 6,1,2,3,4,5
Menu_SongSlot:
  db 1,2,3,4,5,0
else
  db 1,2,3,4,5,6
Menu_SongSlot:
  db 0,1,2,3,4,5
endif

; =========================================================

DrawYItems:
{
  SEP #$30
  JSL UpdateFluteSong_Long
  LDA.b #$7E : STA.b $0A ; Set up the bank of our indirect address
  REP #$30

  LDA.w #$7EF340
  LDX.w #menu_offset(7,3)
  LDY.w #BowsGFX
  JSR DrawMenuItem

  LDA.w #$7EF341
  LDX.w #menu_offset(7,6)
  LDY.w #BoomsGFX
  JSR DrawMenuItem

  LDA.l $7EF342 : AND.w #$00FF : CMP.w #$0000 : BEQ .no_hookshot
if !ENABLE_GOLDSTAR_CELL == 1
    LDA.w #$0001
else
    LDA.w GoldstarOrHookshot : BNE .spoof_hookshot
      LDA #$0001 ; No goldstar, but hookshot
    .spoof_hookshot
endif

    STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
    LDX.w #menu_offset(7,9)
    LDY.w #HookGFX
    JSR DrawMenuItem
  .no_hookshot

  LDA.l $7EF343
  AND.w #$00FF : CMP.w #$00 : BEQ .no_bomb
    LDA.w #$0001
    STA.w MenuItemValueSpoof
    LDA.w #MenuItemValueSpoof
    LDX.w #menu_offset(7,13)
    LDY.w #BombsGFX
    JSR DrawMenuItem
  .no_bomb

  LDA.w #$7EF344
  LDX.w #menu_offset(7,16)
  LDY.w #PowderGFX
  JSR DrawMenuItem

  LDA.w #$7EF35C
  LDX.w #menu_offset(7,19)
  LDY.w #BottlesGFX
  JSR DrawMenuItem

  ; Row 2 -------------------------------------------------

  LDA.w #$7EF34B
  LDX.w #menu_offset(10,3)
  LDY.w #HammerGFX
  JSR DrawMenuItem

  LDA.w #$7EF34A
  LDX.w #menu_offset(10,6)
  LDY.w #LampGFX
  JSR DrawMenuItem

  LDA.w #$7EF345
  LDX.w #menu_offset(10,9)
  LDY.w #Fire_rodGFX
  JSR DrawMenuItem

  LDA.w #$7EF346
  LDX.w #menu_offset(10,13)
  LDY.w #Ice_rodGFX
  JSR DrawMenuItem

  LDA.w #$7EF353
  LDX.w #menu_offset(10,16)
  LDY.w #MirrorGFX
  JSR DrawMenuItem

  LDA.w #$7EF35D
  LDX.w #menu_offset(10,19)
  LDY.w #BottlesGFX
  JSR DrawMenuItem

  ; Row 3 -------------------------------------------------

  LDA.l $7EF34C : AND.w #$00FF : CMP.w #$0000 : BEQ .no_ocarina
if !ENABLE_MENU_OCARINA_BLANK_SLOT == 1
    ; Ocarina owned, no song learned ($7EF34C = 1): grey icon (entry 7).
if !ENABLE_EPONA_SONG == 1
    SEP #$20
    JSL Ocarina_ValidSong_Long          ; 0 = no learned song (Epona bit counts)
    REP #$20
    AND.w #$00FF : BNE .ocarina_has_songs
else
    CMP.w #$0002 : BCS .ocarina_has_songs
endif
      LDA.w #$0007 : BRA .spoof_ocarina
    .ocarina_has_songs
    LDA.w $030F : AND.w #$00FF : BNE .spoof_ocarina
else
    LDA.w $030F : BNE .spoof_ocarina
endif
      LDA #$0001 ; Multi-songs not unlocked yet
    .spoof_ocarina

    STA.w ShortSpoof : LDA.w #ShortSpoof
    LDX.w #menu_offset(13,3)
    LDY.w #OcarinaGFX
    JSR DrawMenuItem
  .no_ocarina

  LDA.l $7EF34E : AND.w #$00FF : CMP.w #$00 : BEQ .no_book
    LDA.w #$01 : STA.w ShortSpoof : LDA.w #ShortSpoof
    LDX.w #menu_offset(13,6)
    LDY.w #BookGFX
    JSR DrawMenuItem
  .no_book

  LDA.w #$7EF350
  LDX.w #menu_offset(13,9)
  LDY.w #SomariaGFX
  JSR DrawMenuItem

  ; LDA.w #$7EF351
  LDA.l $7EF351 : AND.w #$00FF : CMP.w #$00 : BEQ .no_rods
if !ENABLE_PORTAL_ROD_CELL == 1
    LDA.w #$0001 ; this cell is only the Fishing Rod
else
    LDA.w FishingOrPortalRod
    INC A
endif
    STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
if !ENABLE_GOLDSTAR_CELL == 1
    LDX.w #menu_offset(16,6)
else
    LDX.w #menu_offset(13,13)
endif
    LDY.w #FishingRodGFX
    JSR DrawMenuItem
  .no_rods
if !ENABLE_GOLDSTAR_CELL == 1
  LDA.l ByrnaOwned : AND.w #$00FF : CMP.w #$0001 : BEQ .byrna_value
    LDA.w #$0000
  .byrna_value
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,13)
  LDY.w #ByrnaGFX
  JSR DrawMenuItem
endif

  LDA.w #$7EF34D
  LDX.w #menu_offset(13,16)
  LDY.w #JumpFeatherGFX
  JSR DrawMenuItem

  LDA.w #$7EF35E
  LDX.w #menu_offset(13,19)
  LDY.w #BottlesGFX
  JSR DrawMenuItem

  ; Row 4 -------------------------------------------------

if !ENABLE_MENU_PAGE3 == 0
  ; Masks. With !ENABLE_MENU_PAGE3 they are on page 3 (menu_page3.asm).
  LDA.w #$7EF349
  LDX.w #menu_offset(16,3)
  LDY.w #DekuMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF347
  LDX.w #menu_offset(16,6)
  LDY.w #ZoraMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF358
  LDX.w #menu_offset(16,9)
  LDY.w #WolfMaskGFX
  JSR DrawMenuItem

  LDA.w #$7EF348
  LDX.w #menu_offset(16,13)
  LDY.w #BunnyHoodGFX
  JSR DrawMenuItem

  LDA.w #$7EF352
  LDX.w #menu_offset(16,16)
  LDY.w #StoneMaskGFX
  JSR DrawMenuItem
endif

if !ENABLE_PORTAL_ROD_CELL == 1
  ; Portal Rod: row 4, fifth cell with the custom grid; logical ID stays $19.
  LDA.w #PortalRodOwned&$FFFF
if !ENABLE_GOLDSTAR_CELL == 1
  LDX.w #menu_offset(16,16)
else
  LDX.w #menu_offset(16,3)
endif
  LDY.w #PortalRodGFX
  JSR DrawMenuItem
endif

if !ENABLE_GOLDSTAR_CELL == 1
  LDA.w #GoldstarOwned&$FFFF
  LDX.w #menu_offset(16,3)
  LDY.w #HookGFX+8
  JSR DrawMenuItem

  LDA.l SwitchHookOwned : AND.w #$00FF : CMP.w #$0001 : BEQ .switchhookowned_value
    LDA.w #$0000
  .switchhookowned_value
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(16,9)
  LDY.w #SwitchHookGFX
  JSR DrawMenuItem

  LDA.l BombchuOwned : AND.w #$00FF : CMP.w #$0001 : BEQ .bombchuowned_value
    LDA.w #$0000
  .bombchuowned_value
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(16,13)
  LDY.w #BombchuGFX
  JSR DrawMenuItem
endif

  LDA.w #$7EF35F
  LDX.w #menu_offset(16,19)
  LDY.w #BottlesGFX
  JSR DrawMenuItem

  RTS
}

; =========================================================

Menu_DrawQuestItems:
{
  SEP #$30
  LDA.b #$7E : STA.b $0A
  REP #$30

  LDA.w #$7EF359
  LDX.w #menu_offset(14,2)
  LDY.w #SwordGFX
  JSR DrawMenuItem

  LDA.w #$7EF35A
  LDX.w #menu_offset(14,5)
  LDY.w #ShieldGFX
  JSR DrawMenuItem

if !ENABLE_EQUIPMENT_MENU == 1
  JSL Tunic_GetWorn                  ; worn colour, not defense
else
  LDA.l $7EF35B
endif
  INC
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(14,8)
  LDY.w #TunicGFX
  JSR DrawMenuItem

  LDA.w #$7EF354
  LDX.w #menu_offset(17,2)
  LDY.w #PowerGloveGFX
  JSR DrawMenuItem

  LDA.w #$7EF356
  LDX.w #menu_offset(17,5)
  LDY.w #FlippersGFX
  JSR DrawMenuItem

  LDA.w #$7EF355
  LDX.w #menu_offset(17,8)
  LDY.w #PegasusBootsGFX
  JSR DrawMenuItem

  LDA.w #$7EF357
  LDX.w #menu_offset(17,11)
  LDY.w #MoonPearlGFX
  JSR DrawMenuItem

  RTS
}

; =========================================================

Menu_DrawBigKey:
{
  LDA $040C : AND.w #$00FF : CMP.w #$00FF : BEQ .notInPalace
    LSR A : TAX
    ; Check if we have the big key in this palace
    LDA $7EF366

    .locateBigKeyFlag

    ASL A : DEX : BPL .locateBigKeyFlag : BCC .dontHaveBigKey
if !ENABLE_TRUTHFUL_CONTROLS == 1
      JSR Menu_OracleTreasureOwned : LDA $02 : BEQ .noTreasureYet
else
      JSR CheckPalaceItemPossession : LDA $02 : BEQ .noTreasureYet
endif
        SEP #$30
        LDA.b #$7E : STA.b $0A
        REP #$30

        LDA.w #$01
        STA.w ShortSpoof
        LDA.w #ShortSpoof
if !ENABLE_EQUIPMENT_MENU == 1
        LDX.w #!DungeonRow+menu_offset(0,17) ; dungeon row, 4th
else
        LDX.w #menu_offset(11,8)
endif
        LDY.w #TreasureChestGFX
        JSR DrawMenuItem

      .noTreasureYet

      SEP #$30
      LDA.b #$7E : STA.b $0A
      REP #$30

      LDA.w #$01
      STA.w ShortSpoof
      LDA.w #ShortSpoof
      ; Draw the big key (or big key with chest if we've gotten the treasure) icon
if !ENABLE_EQUIPMENT_MENU == 1
      LDX.w #!DungeonRow+menu_offset(0,13) ; dungeon row, 3rd
else
      LDX.w #menu_offset(11,2)
endif
      LDY.w #BigKeyGFX
      JSR DrawMenuItem

    .dontHaveBigKey
  .notInPalace

  LDA $040C : AND.w #$00FF : CMP.w #$00FF : BEQ .notInPalaceAgain
    LSR A : TAX
    ; Check if we have the map in this dungeon
    LDA $7EF368

    .locateMapFlag

    ASL A : DEX : BPL .locateMapFlag : BCC .dontHaveMap
      LDA.w #$01
      STA.w ShortSpoof
      LDA.w #ShortSpoof
      ; Draw the big key (or big key with chest if we've gotten the treasure) icon
if !ENABLE_EQUIPMENT_MENU == 1
      LDX.w #!DungeonRow+menu_offset(0,5) ; dungeon row, 1st
else
      LDX.w #menu_offset(11,11)
endif
      LDY.w #MapGFX
      JSR DrawMenuItem

    .dontHaveMap
  .notInPalaceAgain
  RTS
}

; =========================================================

if !ENABLE_TRUTHFUL_CONTROLS == 1
; Quest page treasure icon: is this dungeon's treasure owned?
; Replaces the vanilla palace table below (Eastern = Bow, Desert = Glove, ...),
; which does not match Oracle's dungeons. Treasure = the dungeon's big-chest item
; in RoomData_ChestItems ($01:E96E); S2's Power Glove is in a small chest (its
; big chest holds the pendant). Owned = the receipt's SRAM byte
; ($09:84E8/$09:8580) reaches the receipt value. Dungeon IDs: bank $0F entrance
; table (Docs/Technical/Dungeon_Tables_Expansion.md section 4).
; Out: $02 = 1 when owned, else 0; $03 = 0. Exits with SEP #$30, as the vanilla
; routine. Keeps DBR.
Menu_OracleTreasureOwned:
{
  PHB : PHK : PLB
  SEP #$30
  STZ.b $02 : STZ.b $03
  LDA.w $040C : LSR A : CMP.b #(.value-.sram) : BCS .done
  TAY
  LDA.w .value, Y : BEQ .done            ; no treasure for this ID
  LDX.w .sram, Y
  LDA.l $7EF300, X
  CPX.b #SwitchHookOwned&$FF : BEQ .switch_hook
  CMP.w .value, Y : BCC .done            ; equipment keeps minimum-level checks
  BRA .owned
  .switch_hook
  CMP.b #$01 : BNE .done                ; match the Switch Hook engine boolean
  .owned
    INC.b $02
  .done
  PLB
  RTS

  ; Index = $040C / 2. Low byte of the $7EF3xx SRAM address.
  .sram
  db $5A ; $00 S3 Shrine of Courage: Mirror Shield, room $053 (item $06)
  db $00 ; $02 none (spawn points)
  db SwitchHookOwned&$FF ; $04 D8 Sky Tower: Switch Hook (candidate receipt $4D)
  db $54 ; $06 S2 Shrine of Power: Power Glove, room $074 (item $1B)
  db $00 ; $08 none (Final Boss Route)
  db $4D ; $0A D2 Tail Palace: Roc's Feather, room $07F (item $21)
  db $40 ; $0C D1 Mushroom Grotto: Bow, room $02A (item $0B)
  db $4B ; $0E D6 Goron Mines: Hammer, room $088 (item $09)
  db $59 ; $10 D3 Kalyxo Castle: sword level 2, room $056 (item $01)
  db $45 ; $12 D5 Glacia Estate: Fire Rod, room $0CC (item $07)
  db $00 ; $14 none (S1 Shrine of Wisdom: Flippers are a Sea Zora gift; pendant in room $09A)
  db $42 ; $16 D4 Zora Temple: Hookshot, room $036 (item $0A)
  db $50 ; $18 D7 Dragon Ship: Cane of Somaria, room $0B3 (item $15)
  db $5B ; $1A D8 Fortress of Secrets: Red Mail, room $05C (item $23)
  ; Owned when the SRAM byte is at least this value (0 = no treasure).
  .value
  db $03, $00, $01, $01, $00, $01, $01, $01, $02, $01, $00, $01, $01, $02
}
endif

; $06EEB6-$06EEDB LOCAL
CheckPalaceItemPossession:
{
  SEP #$30
  LDA $040C : LSR A
  JSL JumpTableLocal
  dw .no_item
  dw .no_item
  dw .bow
  dw .power_glove
  dw .no_item
  dw .hookshot
  dw .hammer
  dw .cane_of_somaria
  dw .fire_rod
  dw .blue_mail
  dw .moon_pearl
  dw .titans_mitt
  dw .mirror_shield
  dw .red_mail
}

; ==========================================================

; *$6EEDC-$6EEE0 JUMP LOCATION
.pool_CheckPalaceItemPossession:
{
  .failure

  STZ $02
  STZ $03
  RTS

  .bow

  LDA $7EF340

  .no_item
  .compare

  BEQ .failure

  .success

  LDA.b #$01 : STA $02
               STZ $03
  RTS

  .power_glove

  LDA $7EF354 : BRA .compare

  .hookshot

  LDA $7EF342 : BRA .compare

  .hammer

  LDA $7EF34B : BRA .compare

  .cane_of_somaria

  LDA $7EF350 : BRA .compare

  .fire_rod

  LDA $7EF345 : BRA .compare

  .blue_mail

  LDA $7EF35B : BRA .compare

  .moon_pearl

  LDA $7EF357 : BRA .compare

  .titans_mitt

  LDA $7EF354 : DEC A : BRA .compare

  .mirror_shield

  LDA $7EF35A : CMP.b #$03 : BEQ .success
  STZ $02
  STZ $03
  RTS

  .red_mail

  LDA $7EF35B : CMP.b #$02 : BEQ .success
  STZ $02
  STZ $03
  RTS
}

; *$6EF39-$6EF66 LOCAL
Menu_DrawBigChestKey:
{
  LDA $040C : AND.w #$00FF : CMP.w #$00FF : BEQ .notInPalace
    LSR A : TAX
    LDA $7EF364
    .locateCompassFlag

    ASL A : DEX : BPL .locateCompassFlag
                  BCC .dontHaveCompass
      SEP #$30
      LDA.b #$7E : STA.b $0A
      REP #$30

      LDA.w #$01
      STA.w ShortSpoof
      LDA.w #ShortSpoof
if !ENABLE_EQUIPMENT_MENU == 1
      LDX.w #!DungeonRow+menu_offset(0,9) ; dungeon row, 2nd
else
      LDX.w #menu_offset(11, 5)
endif
      LDY.w #BigChestKeyGFX
      JSR DrawMenuItem
    .dontHaveCompass
  .notInPalace
  RTS
}


Menu_DrawSongMenu:
{
  REP #$30
  LDX.w #$FE ; $1700-17FF

  .loop
    LDA.w .magic_bag_tilemap, X
    STA.w $1000, X
    LDA.w .magic_bag_tilemap+$100, X
    STA.w $1100, X
    LDA.w .magic_bag_tilemap+$200, X
    STA.w $1200, X
    LDA.w .magic_bag_tilemap+$300, X
    STA.w $1300, X
    LDA.w .magic_bag_tilemap+$400, X
    STA.w $1400, X
    LDA.w .magic_bag_tilemap+$500, X
    STA.w $1500, X
    LDA.w .magic_bag_tilemap+$600, X
    STA.w $1600, X
    LDA.w .magic_bag_tilemap+$700, X
    STA.w $1700, X

    DEX : DEX
  BPL .loop
  RTS

  .magic_bag_tilemap
    incbin "tilemaps/song_menu.tilemap"
}

Menu_DrawMagicBag:
{
  REP #$30
  LDX.w #$FE ; $1700-17FF

  .loop
    LDA.w .magic_bag_tilemap, X
    STA.w $1000, X
    LDA.w .magic_bag_tilemap+$100, X
    STA.w $1100, X
    LDA.w .magic_bag_tilemap+$200, X
    STA.w $1200, X
    LDA.w .magic_bag_tilemap+$300, X
    STA.w $1300, X
    LDA.w .magic_bag_tilemap+$400, X
    STA.w $1400, X
    LDA.w .magic_bag_tilemap+$500, X
    STA.w $1500, X
    LDA.w .magic_bag_tilemap+$600, X
    STA.w $1600, X
    LDA.w .magic_bag_tilemap+$700, X
    STA.w $1700, X

    DEX : DEX
  BPL .loop
  RTS

  .magic_bag_tilemap
    incbin "tilemaps/magic_bag.tilemap"
}

; Used by the Ring Box (state $09) and the M1 page 3 layout only.
if !MENU_DROP_RING_BOX == 0 || !ENABLE_MENU_PAGE3_LAYOUT_A == 0
Menu_DrawRingBox:
{
  REP #$30
  LDX.w #$FE ; $1700-17FF

  .loop
    LDA.w .ring_box_tilemap, X
    STA.w $1000, X
    LDA.w .ring_box_tilemap+$100, X
    STA.w $1100, X
    LDA.w .ring_box_tilemap+$200, X
    STA.w $1200, X
    LDA.w .ring_box_tilemap+$300, X
    STA.w $1300, X
    LDA.w .ring_box_tilemap+$400, X
    STA.w $1400, X
    LDA.w .ring_box_tilemap+$500, X
    STA.w $1500, X
    LDA.w .ring_box_tilemap+$600, X
    STA.w $1600, X
    LDA.w .ring_box_tilemap+$700, X
    STA.w $1700, X

    DEX : DEX
  BPL .loop
  SEP #$30
  RTS

  .ring_box_tilemap
    incbin "tilemaps/ring_box.tilemap"
}
endif

Menu_DrawMagicRings:
{
if !ENABLE_ONE_RING == 1
  ; One ring (scawful 2026-09-28): the Quest page shows no rings. The worn
  ; ring is the red bracket on page 3; r21-22 c17-26 keep the frame tiles.
  RTS
else
if !ENABLE_MENU_HIDE_RINGS_JOURNAL_EARLY == 1
  ; No ring owned: leave the three equipped-ring slots as frame background.
  JSR Menu_CheckRingsUnlocked : BCS .rings_unlocked
    RTS
  .rings_unlocked
endif
  LDA.l RingSlot1 : AND.w #$00FF : CMP.w #$0001 : BCC .no_attack
    BRA .draw_storms
  .no_attack
  LDA.w #$0001
  .draw_storms
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(17,14)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.l RingSlot2 : AND.w #$00FF : CMP.w #$0001 : BCC .no_defense
    BRA .draw_defense
  .no_defense
  LDA.w #$0001
  .draw_defense
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(17,17)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.l RingSlot3 : AND.w #$00FF : CMP.w #$0001 : BCC .no_luck
    BRA .draw_luck
  .no_luck
  LDA.w #$0001
  .draw_luck
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(17,20)
  LDY.w #RingGFX
  JSR DrawMenuItem

  RTS
endif
}

if !MENU_DROP_RING_BOX == 0 || !ENABLE_MENU_PAGE3_LAYOUT_A == 0
Menu_DrawMagicRingsInBox:
{
  SEP #$30
  LDA.b #$7E : STA.b $0A ; Set up the bank of our indirect address
  REP #$30

  LDA.l MAGICRINGS : AND.w #$00FF : BIT.w #$0020 : BEQ .no_attack
    LDA.w #$0002 : BRA +
  .no_attack
  LDA.w #$0001
  +
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(9,7)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.l MAGICRINGS : AND.w #$00FF : BIT.w #$0010 : BEQ .no_defense
    LDA.w #$0003 : BRA +
  .no_defense
  LDA.w #$0001
  +
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(9,11)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.l MAGICRINGS : AND.w #$00FF : BIT.w #$0008 : BEQ .no_steadfast
    LDA.w #$0004 : BRA +
  .no_steadfast
  LDA.w #$0001
  +
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(9,15)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.l MAGICRINGS : AND.w #$00FF : BIT.w #$0004 : BEQ .no_light
    LDA.w #$0005 : BRA +
  .no_light
  LDA.w #$0001
  +
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,7)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.l MAGICRINGS : AND.w #$00FF : BIT.w #$0002 : BEQ .no_blast
    LDA.w #$0006 : BRA +
  .no_blast
  LDA.w #$0001
  +
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,11)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.l MAGICRINGS : AND.w #$00FF : BIT.w #$0001 : BEQ .no_heart
    LDA.w #$0007 : BRA +
  .no_heart
  LDA.w #$0001
  +
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,15)
  LDY.w #RingGFX
  JSR DrawMenuItem

  SEP #$30

  RTS
}
endif

Menu_DrawMagicItems:
{
  SEP #$30
  LDA.b #$7E : STA.b $0A ; Set up the bank of our indirect address
  REP #$30

  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(9,7)
  LDY.w #BananaGFX
  JSR DrawMenuItem

  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(9,11)
  LDY.w #PineappleGFX
  JSR DrawMenuItem

  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(9,15)
  LDY.w #RockMeatGFX
  JSR DrawMenuItem

  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,7)
  LDY.w #SeashellGFX
  JSR DrawMenuItem

  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,11)
  LDY.w #HoneycombGFX
  JSR DrawMenuItem

  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,15)
  LDY.w #DekuStickGFX
  JSR DrawMenuItem

  RTS
}

Menu_DrawCursor:
{
  LDA.b #$20 : BIT.w $0207
  REP #$20
  BEQ .no_delete
    ; Delete cursor
    LDA.w #$20F5
    STA.w $1108, X : STA.w $1148, X
    STA.w $114E, X : STA.w $110E, X
    STA.w $11C8, X : STA.w $1188, X
    STA.w $118E, X : STA.w $11CE, X
    BRA .done

  .no_delete
  ; 2-item HUD layout: one gray selector on every item (scawful 2026-11-15:
  ; "a gray main selector"); green/blue belong to the Y/X marks only.

  ; Normal cursor (palette 1 - default blue/white)
  LDA.w #$3060 : STA.w $1108, X ; corner
  LDA.w #$3070 : STA.w $1148, X
  LDA.w #$7060 : STA.w $110E, X ; corner
  LDA.w #$7070 : STA.w $114E, X
  LDA.w #$3070 : STA.w $1188, X
  LDA.w #$B060 : STA.w $11C8, X ; corner
  LDA.w #$7070 : STA.w $118E, X
  LDA.w #$F060 : STA.w $11CE, X ; corner

  .done
  SEP #$20
  RTS
}
