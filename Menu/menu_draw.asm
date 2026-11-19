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

; Quest Pearl/hearts anchor row and the dungeon row (map, big chest key,
; big key, treasure), as DrawMenuItem row offsets (absolute row minus 4).
; With the four-page menu the passive 2x2 gear sits at top-left, Pearl and
; hearts below it (Menu_Quest_Gear), the six songs on the Quest bottom row
; (Menu_DrawMusicNotes), and the dungeon row sits on the Map page under the
; Map cell (MenuMapTravel_Draw). Without it the dungeon row is on the Quest
; bottom row between Pearl and hearts.
if !ENABLE_MENU_MAP_TRAVEL == 1
  !QuestRow = menu_offset(13,0)         ; absolute row 17, below the 2x2 passive gear block
  !DungeonRow = menu_offset(11,0)       ; Map & Spoils page, absolute row 15
else
  !QuestRow = menu_offset(17,0)
  !DungeonRow = !QuestRow
endif

Menu_DrawHeartPieces:
{
if !ENABLE_MENU_MAP_TRAVEL == 1
  !QuestHeart = $1000+!QuestRow+menu_offset(4,10)  ; Quest lower-left row, beside the Pearl: absolute (17,10)
else
  !QuestHeart = $1000+!QuestRow+menu_offset(4,24)  ; Quest bottom row, right end
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
  JSL Ocarina_SongLearned_Long : BCC .unlearned
  INC : BRA .variant                    ; variant = song + 1
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
; long to place its full-size 4x4 C4 cursor. Four-page menu: Quest row 21,
; cols 6, 9, 13, 17, 21, 24 (4x4 cursor rows 20..23: clear of D5 and border).
.positions
if !ENABLE_MENU_MAP_TRAVEL == 1
  dw menu_offset(17,2),menu_offset(17,5),menu_offset(17,9)
  dw menu_offset(17,13),menu_offset(17,17),menu_offset(17,20)
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
if !ENABLE_MENU_MAP_TRAVEL == 1
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

  ; Option A grid: rows [11,14,17,20] -> DrawMenuItem rows [7,10,13,16]
  ;                cols [6,9,12,15,18,24] -> DrawMenuItem cols [2,5,8,11,14,20]
  ; Row 1 (row 11): Bow, Boomerang, Hookshot, Bombs, Bombchu | Bottle 1

  LDA.w #$7EF340
  LDX.w #menu_offset(7,2)
  LDY.w #BowsGFX
  JSR DrawMenuItem

  LDA.w #$7EF341
  LDX.w #menu_offset(7,5)
  LDY.w #BoomsGFX
  JSR DrawMenuItem

  LDA.l $7EF342 : AND.w #$00FF : BEQ .no_hookshot
if !ENABLE_GOLDSTAR_CELL == 1
    LDY.w #HookGFX
    CMP.w #$0002 : BNE .hook_icon_ready
      LDY.w #.switch_hook_gfx
    .hook_icon_ready
    LDA.w #$0001
else
    LDA.w GoldstarOrHookshot : BNE .spoof_hookshot
      LDA #$0001 ; No goldstar, but hookshot
    .spoof_hookshot
    LDY.w #HookGFX
endif
    STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
    LDX.w #menu_offset(7,8)
    JSR DrawMenuItem
    BRA .no_hookshot
  .switch_hook_gfx
    dw $24F5, $34F6, $24C0, $24F5 ; Switch Hook (gold prong + red grip)
  .no_hookshot

  LDA.l $7EF343
  AND.w #$00FF : CMP.w #$00 : BEQ .no_bomb
    LDA.w #$0001
    STA.w MenuItemValueSpoof
    LDA.w #MenuItemValueSpoof
    LDX.w #menu_offset(7,11)
    LDY.w #BombsGFX
    JSR DrawMenuItem
  .no_bomb

if !ENABLE_GOLDSTAR_CELL == 1
  LDA.l BombchuOwned : AND.w #$00FF : CMP.w #$0001 : BEQ .bombchuowned_value
    LDA.w #$0000
  .bombchuowned_value
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(7,14)
  LDY.w #BombchuGFX
  JSR DrawMenuItem
endif

  LDA.w #$7EF35C
  LDX.w #menu_offset(7,20)
  LDY.w #BottlesGFX
  JSR DrawMenuItem

  ; Row 2 (row 14): Hammer, Powder, Fire Rod, Ice Rod, Goldstar | Bottle 2

  LDA.w #$7EF34B
  LDX.w #menu_offset(10,2)
  LDY.w #HammerGFX
  JSR DrawMenuItem

  LDA.w #$7EF344
  LDX.w #menu_offset(10,5)
  LDY.w #PowderGFX
  JSR DrawMenuItem

  LDA.w #$7EF345
  LDX.w #menu_offset(10,8)
  LDY.w #Fire_rodGFX
  JSR DrawMenuItem

  LDA.w #$7EF346
  LDX.w #menu_offset(10,11)
  LDY.w #Ice_rodGFX
  JSR DrawMenuItem

if !ENABLE_GOLDSTAR_CELL == 1
  LDA.w #GoldstarOwned&$FFFF
  LDX.w #menu_offset(10,14)
  LDY.w #HookGFX+8
  JSR DrawMenuItem
endif

  LDA.w #$7EF35D
  LDX.w #menu_offset(10,20)
  LDY.w #BottlesGFX
  JSR DrawMenuItem

  ; Row 3 (row 17): Lamp, Book, Somaria, Byrna, Gust Jar | Bottle 3

  LDA.w #$7EF34A
  LDX.w #menu_offset(13,2)
  LDY.w #LampGFX
  JSR DrawMenuItem

  LDA.l $7EF34E : AND.w #$00FF : CMP.w #$00 : BEQ .no_book
    LDA.w #$01 : STA.w ShortSpoof : LDA.w #ShortSpoof
    LDX.w #menu_offset(13,5)
    LDY.w #BookGFX
    JSR DrawMenuItem
  .no_book

  LDA.w #$7EF350
  LDX.w #menu_offset(13,8)
  LDY.w #SomariaGFX
  JSR DrawMenuItem

if !ENABLE_GOLDSTAR_CELL == 1
  LDA.l ByrnaOwned : AND.w #$00FF : CMP.w #$0001 : BEQ .byrna_value
    LDA.w #$0000
  .byrna_value
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,11)
  LDY.w #ByrnaGFX
  JSR DrawMenuItem

  LDA.l SwitchHookOwned : AND.w #$00FF : CMP.w #$0001 : BEQ .gustjar_value
    LDA.w #$0000
  .gustjar_value
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(13,14)
  LDY.w #GustJarGFX
  JSR DrawMenuItem
endif

  LDA.w #$7EF35E
  LDX.w #menu_offset(13,20)
  LDY.w #BottlesGFX
  JSR DrawMenuItem

  ; Row 4 (row 20): Ocarina, Feather, Fishing Rod, Mirror, Portal Rod | Bottle 4

  LDA.l $7EF34C : AND.w #$00FF : CMP.w #$0000 : BEQ .no_ocarina
    ; Ocarina owned, no song learned ($7EF34C = 1): grey icon (entry 7).
    SEP #$20
    JSL Ocarina_ValidSong_Long          ; 0 = no learned song (Epona bit counts)
    REP #$20
    AND.w #$00FF : BNE .ocarina_has_songs
      LDA.w #$0007 : BRA .spoof_ocarina
    .ocarina_has_songs
    LDA.w $030F : AND.w #$00FF : BNE .spoof_ocarina
      LDA #$0001 ; Multi-songs not unlocked yet
    .spoof_ocarina

    STA.w ShortSpoof : LDA.w #ShortSpoof
    LDX.w #menu_offset(16,2)
    LDY.w #OcarinaGFX
    JSR DrawMenuItem
  .no_ocarina

  LDA.w #$7EF34D
  LDX.w #menu_offset(16,5)
  LDY.w #JumpFeatherGFX
  JSR DrawMenuItem

  LDA.l $7EF351 : AND.w #$00FF : CMP.w #$00 : BEQ .no_rods
    LDA.w #$0001 ; this cell is only the Fishing Rod
    STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
    LDX.w #menu_offset(16,8)
    LDY.w #FishingRodGFX
    JSR DrawMenuItem
  .no_rods

  LDA.w #$7EF353
  LDX.w #menu_offset(16,11)
  LDY.w #MirrorGFX
  JSR DrawMenuItem

  ; Portal Rod: Row 4 Col 5 (bottom-right tool); logical ID stays $19.
  LDA.w #PortalRodOwned&$FFFF
  LDX.w #menu_offset(16,14)
  LDY.w #PortalRodGFX
  JSR DrawMenuItem

  LDA.w #$7EF35F
  LDX.w #menu_offset(16,20)
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

  JSL Tunic_GetWorn                  ; worn colour, not defense
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
      JSR Menu_OracleTreasureOwned : LDA $02 : BEQ .noTreasureYet
        SEP #$30
        LDA.b #$7E : STA.b $0A
        REP #$30

        LDA.w #$01
        STA.w ShortSpoof
        LDA.w #ShortSpoof
if !ENABLE_MENU_MAP_TRAVEL == 1
        LDX.w #!DungeonRow+menu_offset(0,20) ; Map & Spoils page: Chest at (15,24)
else
        LDX.w #!DungeonRow+menu_offset(0,17) ; dungeon row, 4th
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
if !ENABLE_MENU_MAP_TRAVEL == 1
      LDX.w #!DungeonRow+menu_offset(0,17) ; Map & Spoils page: BigKey at (15,21)
else
      LDX.w #!DungeonRow+menu_offset(0,13) ; dungeon row, 3rd
endif
      LDY.w #BigKeyGFX
      JSR DrawMenuItem

    .dontHaveBigKey
  .notInPalace

if !ENABLE_MENU_MAP_TRAVEL == 0
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
      LDX.w #!DungeonRow+menu_offset(0,5) ; dungeon row, 1st
      LDY.w #MapGFX
      JSR DrawMenuItem

    .dontHaveMap
  .notInPalaceAgain
endif
  RTS
}

; =========================================================

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
  db $56 ; $14 S1 Shrine of Wisdom: Flippers, shrine keeper Zora in room $09A (item $1E)
  db $42 ; $16 D4 Zora Temple: Hookshot, room $036 (item $0A)
  db $50 ; $18 D7 Dragon Ship: Cane of Somaria, room $0B3 (item $15)
  db $5B ; $1A D8 Fortress of Secrets: Red Mail, room $05C (item $23)
  ; Owned when the SRAM byte is at least this value (0 = no treasure).
  .value
  db $03, $00, $01, $01, $00, $01, $01, $01, $02, $01, $01, $01, $01, $02
}

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
if !ENABLE_MENU_MAP_TRAVEL == 1
      LDX.w #!DungeonRow+menu_offset(0,14) ; Map & Spoils page: ChestKey at (15,18)
else
      LDX.w #!DungeonRow+menu_offset(0,9) ; dungeon row, 2nd
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
if !MENU_DROP_RING_BOX == 0
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
  ; No ring owned: leave the three equipped-ring slots as frame background.
  JSR Menu_CheckRingsUnlocked : BCS .rings_unlocked
    RTS
  .rings_unlocked
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

if !MENU_DROP_RING_BOX == 0
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
    ; Clear all 12 perimeter tiles of C4 cursor box
    LDA.w #$3417
    STA.w $1108, X : STA.w $110A, X : STA.w $110C, X : STA.w $110E, X
    STA.w $1148, X : STA.w $114E, X
    STA.w $1188, X : STA.w $118E, X
    STA.w $11C8, X : STA.w $11CA, X : STA.w $11CC, X : STA.w $11CE, X
    BRA .done

  .no_delete
  ; Cursor C4 active selection: crisp Gold ($34) L-brackets on the 4 corners.
  ; On Items page, Menu_Bindings_DrawMarkers layers the Green Y / Blue X thin
  ; rounded frames + corner badges and preserves badges under active hover.
  LDA.w #$353F : STA.w $1108, X ; TL gold L-bracket
  LDA.w #$753F : STA.w $110E, X ; TR (H-flip)
  LDA.w #$B53F : STA.w $11C8, X ; BL (V-flip)
  LDA.w #$F53F : STA.w $11CE, X ; BR (HV-flip)

  .done
  SEP #$20
  RTS
}
