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
    LDA.w quest_icons, X 
    STA.w $1364, X 
    LDA.w quest_icons+$10, X 
    STA.w $13A4, X 
    LDA.w quest_icons+$20, X 
    STA.w $13E4, X 
    LDA.w quest_icons+$30, X 
    STA.w $1424, X 
    LDA.w quest_icons+$40, X 
    STA.w $1464, X 
    LDA.w quest_icons+$50, X 
    STA.w $14A4, X 
    LDA.w quest_icons+$60, X 
    STA.w $14E4, X 
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
    LDX.w #$2D06 : STX.w $14B0 : INX : STX.w $14B2
    LDX.w #$2D16 : STX.w $14F0 : INX : STX.w $14F2
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

Menu_DrawHeartPieces:
{
  ; Empty heart containter
  LDX.w #$2484 : STX.w $149E ; top left
  LDX.w #$6484 : STX.w $14A0 ; top right 
  LDX.w #$2485 : STX.w $14DE ; bottom left
  LDX.w #$6485 : STX.w $14E0 ; bottom right

  LDA.l $7EF36B
  AND.w #$00FF
  CMP.w #3 : BEQ .top_right
    CMP.w #1 : BEQ .top_left
      BCS .bottom_left
        RTS

  .top_right
  LDX.w #$64AD : STX.w $14A0

  .bottom_left
  LDX.w #$24AE : STX.w $14DE 

  .top_left
  LDX.w #$24AD : STX.w $149E 
  RTS
}

; =========================================================

Menu_DrawMusicNotes:
{
  LDA.l $7EF34C : AND.w #$00FF : CMP.w #$0001 : BCC .no_storms
    LDA.w #$0002 : BRA .draw_storms
  .no_storms
  LDA.w #$0001
  .draw_storms
  STA.w MusicNoteValue
  LDA.w #MusicNoteValue
  LDX.w #menu_offset(17,20)
  LDY.w #QuarterNoteGFX
  JSR DrawMenuItem

  LDA.l $7EF34C : AND.w #$00FF : CMP.w #$0002 : BCC .no_healing
    LDA.w #$03 : BRA .draw_healing
  .no_healing
  LDA.w #$01
  .draw_healing
  STA.w MusicNoteValue
  LDA.w #MusicNoteValue
  LDX.w #menu_offset(17,17)
  LDY.w #QuarterNoteGFX
  JSR DrawMenuItem

  LDA.l $7EF34C : AND.w #$00FF : CMP.w #$0003 : BCC .no_soaring
    LDA.w #$04 : BRA .draw_soaring
  .no_soaring
  LDA.w #$01
  .draw_soaring
  STA.w MusicNoteValue
  LDA.w #MusicNoteValue
  LDX.w #menu_offset(17,14)
  LDY.w #QuarterNoteGFX
  JSR DrawMenuItem

  RTS
}

; =========================================================

DrawYItems:
{ 
  SEP #$30
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
    LDA.w GoldstarOrHookshot : BNE .spoof_hookshot
      LDA #$0001 ; No goldstar, but hookshot
    .spoof_hookshot

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
    LDA.w $030F : BNE .spoof_ocarina
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
    LDA.w FishingOrPortalRod 
    INC A 
    STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
    LDX.w #menu_offset(13,13)
    LDY.w #FishingRodGFX
    JSR DrawMenuItem
  .no_rods

  LDA.w #$7EF34D
  LDX.w #menu_offset(13,16)
  LDY.w #JumpFeatherGFX
  JSR DrawMenuItem

  LDA.w #$7EF35E
  LDX.w #menu_offset(13,19)
  LDY.w #BottlesGFX
  JSR DrawMenuItem

  ; Row 4 -------------------------------------------------

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

  LDA.l $7EF35B
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
      JSR CheckPalaceItemPossession : LDA $02 : BEQ .noTreasureYet
        SEP #$30
        LDA.b #$7E : STA.b $0A
        REP #$30

        LDA.w #$01
        STA.w ShortSpoof
        LDA.w #ShortSpoof
        LDX.w #menu_offset(11,8)
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
      LDX.w #menu_offset(11,2)
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
      LDX.w #menu_offset(11,11)
      LDY.w #MapGFX
      JSR DrawMenuItem

    .dontHaveMap
  .notInPalaceAgain
  
  RTS
}

; =========================================================

; $06EEB6-$06EEDB LOCAL
CheckPalaceItemPossession:
{
  SEP #$30
  
  LDA $040C : LSR A
  
  JSL UseImplicitRegIndexedLocalJumpTable
  
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
      LDX.w #menu_offset(11, 5)
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

Menu_DrawMagicItems:
{ 
  SEP #$30
  LDA.b #$7E : STA.b $0A ; Set up the bank of our indirect address
  REP #$30

  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(7,3)
  LDY.w #BananaGFX
  JSR DrawMenuItem

  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(7,6)
  LDY.w #PineappleGFX
  JSR DrawMenuItem


  LDA.w #$0001
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(7,9)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.w #$0002
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(7,12)
  LDY.w #RingGFX
  JSR DrawMenuItem

  LDA.w #$0003
  STA.w MenuItemValueSpoof : LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(7,15)
  LDY.w #RingGFX
  JSR DrawMenuItem

  RTS
}

; =========================================================