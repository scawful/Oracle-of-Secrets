; =========================================================
;  Text Routines

'A' = $2550
'B' = $2551
'C' = $2552
'D' = $2553
'E' = $2554
'F' = $2555
'G' = $2556
'H' = $2557
'I' = $2558
'J' = $2559
'K' = $255A
'L' = $255B
'M' = $255C
'N' = $255D
'O' = $255E
'P' = $255F
'Q' = $2560
'R' = $2561
'S' = $2562
'T' = $2563
'U' = $2564
'V' = $2565
'W' = $2566
'X' = $2567
'Y' = $2568
'Z' = $2569
'.' = $256A
':' = $256B
'0' = $2570
'1' = $2571
'2' = $2572
'3' = $2573
'4' = $2574
'5' = $2575
'6' = $2576
'7' = $2577
'8' = $2578
'9' = $2579
'_' = $20F5

; =========================================================

TimeLabels:
  dw "00", "01", "02", "03", "04", "05", "06", "07", "08"
  dw "09", "10", "11", "12", "13", "14", "15", "16", "17"
  dw "18", "19", "20", "21", "22", "23", "24", "25", "26"
  dw "27", "28", "29", "30", "31", "32", "33", "34", "35"
  dw "36", "37", "38", "39", "40", "41", "42", "43", "44"
  dw "45", "46", "47", "48", "49", "50", "51", "52", "53"
  dw "54", "55", "56", "57", "58", "59"

PlaytimeLabel:
  dw "TIME:_____"

Menu_DrawHourDigit:
{
  SEP #$30
  LDA.l TimeState.Hours
  ASL A : ASL A
  TAX
  REP #$30
  LDA.w TimeLabels, X : STA.w $1692+$12
  INX : INX
  LDA.w TimeLabels, X : STA.w $1692+$14
  RTS
}

Menu_DrawMinuteDigit:
{
  SEP #$30
  LDA.l TimeState.Minutes
  ASL A : ASL A
  TAX
  REP #$30
  LDA.w TimeLabels, X : STA.w $1692+$18
  INX : INX
  LDA.w TimeLabels, X : STA.w $1692+$1A
  RTS
}

Menu_DrawPlaytimeLabel:
{
  LDX.w #$10

  .draw2
  LDA.w PlaytimeLabel, X
  STA.w $1692, X
  DEX : DEX : BPL .draw2

  ; Draw the current time based on the time system RAM
  JSR Menu_DrawHourDigit

  ; Draw colon
  LDA.w #$256B
  STA.w $1692+$16

  ; LDX #$18
  JSR Menu_DrawMinuteDigit

  RTS
}

; =========================================================

Menu_ItemNames:
  dw "_____BOW______  "
  dw "__BOOMERANG___  "
  dw "___HOOKSHOT___  "
  dw "____BOMBS_____  "
  dw "_MAGIC_POWDER_  "
  dw "____BOTTLE____  "
  dw "____HAMMER____  "
  dw "_____LAMP_____  "
  dw "___FIRE_ROD___  "
  dw "___ICE_ROD____  "
  dw "MIRROR_OF_TIME  "
  dw "____BOTTLE____  "
  dw "___OCARINA____  "
  dw "BOOK__L:REVEAL  "
  dw "___SOMARIA____  "
  dw "_FISHING_ROD__  "
  dw "_ROCS_FEATHER_  "
  dw "____BOTTLE____  "
  dw "__DEKU_MASK___  "
  dw "__ZORA_MASK___  "
  dw "__WOLF_MASK___  "
  dw "__BUNNY_HOOD__  "
  dw "__STONE_MASK__  "
  dw "____BOTTLE____  "

Menu_MushroomLabel:
Menu_BottleItems:
  dw "___MUSHROOM___  "
  dw "_EMPTY_BOTTLE_  "
  dw "__RED_POTION__  "
  dw "_GREEN_POTION_  "
  dw "_BLUE_POTION__  "
  dw "____FAIRY_____  "
  dw "_____BEE______  "
  dw "__GOOD_BEE____  "
  dw "_MAGIC_BEAN___  "
  dw "_MILK_BOTTLE__  "

Menu_GoldstarLabel:
  dw "__GOLD_STAR___  "

Menu_PortalRodItems:
  dw "__PORTAL_ROD__  "

Menu_SongNames:
  dw "SONG:_STORMS__  "
  dw "SONG:_HEALING_  "
  dw "SONG:_SOARING_  "
  dw "SONG:_TIME____  "

Menu_RingNames:
  dw "____POWER_____  "
  dw "____ARMOR_____  "
  dw "____HEART_____  "
  dw "____LIGHT_____  "
  dw "____BLAST_____  "
  dw "___STEADFAST__  "

Menu_RingDescriptions:
  dw "ATK_UP__DEF_DOWN"
  dw "ATK_DOWN__DEF_UP"
  dw "SLOW_HEART_REGEN"
  dw "SWD_BEAM_2_HRTS_"
  dw "_BOMB_DAMAGE_UP_"
  dw "__NO_KNOCKBACK__"

Menu_RingsFound:
  dw "NEW_RING_FOUND__"

Menu_DrawItemName:
{
  SEP #$30

  ; Double check that we have the item.
  LDY.w $0202
  LDX.w Menu_AddressIndex-1, Y
  LDA.l $7EF300,             X
  CMP.b #$01 : BCS .haveItem
    REP #$30
    RTS
  .haveItem

  LDA.w $0202 : CMP.b #$03 : BEQ .goldstar
                CMP.b #$05 : BEQ .mushroom
                CMP.b #$0D : BEQ .ocarina
                CMP.b #$10 : BEQ .custom_rods
  ; Check if it's a bottle
                CMP.b #$06 : BEQ .bottle_1
                CMP.b #$0C : BEQ .bottle_2
                CMP.b #$12 : BEQ .bottle_3
                CMP.b #$18 : BEQ .bottle_4
  .draw_item
        REP #$30
        LDA.w $0202 : BEQ .no_items
          DEC : ASL #5 : TAX
          LDY.w #$000

          .loop
            LDA.w Menu_ItemNames, X ; Load your text character
            STA.w $1692, Y ; <- into the buffer
            INX : INX
          INY : INY : CPY #$001C : BCC .loop
        .no_items
        RTS

        ; Draw Bottle Description
        .bottle_1
        REP #$30 : LDX #$0000 : JMP .draw_bottle
          .bottle_2
          REP #$30 : LDX #$0001 : JMP .draw_bottle
            .bottle_3
            REP #$30 : LDX #$0002 : JMP .draw_bottle
              .bottle_4
              REP #$30 : LDX #$0003

        .draw_bottle
        JSR DrawBottleNames
        RTS

      .custom_rods
      LDA.w FishingOrPortalRod : CMP.b #$01 : BNE .draw_item
        JSR DrawPortalRodName
        RTS

      .goldstar
      LDA.w GoldstarOrHookshot : CMP.b #$02 : BNE .draw_item
        JSR DrawGoldstarName
        RTS

      .mushroom
      LDA.l $7EF344 : CMP.b #$02 : BCS .draw_item
        JSR DrawMushroomName
        RTS

      .ocarina
      REP #$30

    ; Check the timer and see if we should draw the item name
    LDA $1A : AND.w #$00FF : CMP #$0080 : BCC .draw_item
  LDA $030F : BEQ .draw_item
  LDA $030F : AND.w #$00FF : DEC : ASL #5 : TAX
  LDY.w #$0000

  .draw_ocarina_loop
    LDA.w Menu_SongNames, X : STA.w $1692, Y
  INX #2 : INY #2 : CPY #$001C : BCC .draw_ocarina_loop
  RTS
}

DrawPortalRodName:
{
  REP #$30
  LDX.w #$0000
  LDY.w #$0000

  .draw_portal_rod_loop
    LDA.w Menu_PortalRodItems, X : STA.w $1692, Y
    INX #2 : INY #2
  CPY #$001C : BCC .draw_portal_rod_loop
  RTS
}

DrawBottleNames:
{
  LDA.l $7EF35C, X : AND.w #$00FF
  DEC : ASL #5 : TAX
  LDY.w #$0000

  .draw_bottle_loop
    LDA.w Menu_BottleItems, X : STA.w $1692, Y
    INX #2 : INY #2
  CPY #$001C : BCC .draw_bottle_loop
  RTS
}

DrawMagicRingNames:
{
  REP #$30
  LDA.w $020B : ASL #5 : TAX
  LDY.w #$0000

  .draw_ring_loop
    LDA.w Menu_RingNames, X : STA.w $1692, Y
    INX #2 : INY #2
  CPY #$001C : BCC .draw_ring_loop

  LDA.w $020B : ASL #5 : TAX
  LDY.w #$0000

  .draw_ring_desc_loop
    LDA.w Menu_RingDescriptions, X : STA.w $1590, Y
    INX #2 : INY #2
  CPY #$0020 : BCC .draw_ring_desc_loop

  LDA.l MAGICRINGS : AND.w #$00FF : STA.b $00
  LDA.l FOUNDRINGS : AND.w #$00FF : CMP.b $00 : BEQ +
    LDY.w #$0000
    .draw_found_ring
    LDA.w Menu_RingsFound, Y : STA.w $1692, Y
    INY #2 : CPY #$001C : BCC .draw_found_ring
  +

  SEP #$30
  RTS
}

Menu_CollectibleNames:
  dw "BANANAS:________"
  dw "PINEAPPLES:_____"
  dw "ROCK_MEAT:______"
  dw "SEASHELLS:______"
  dw "HONEYCOMBS:_____"
  dw "DEKU_STICKS:____"

DrawCollectibleNamesAndCount:
{
  REP #$30
  LDA.w $020B : ASL #5 : TAX : LDY.w #$0000

  .draw_loop
    LDA.w Menu_CollectibleNames, X : STA.w $1692, Y
    INX #2 : INY #2
  CPY #$001C : BCC .draw_loop
  SEP #$30
  ; Draw the number of each collectible
  LDA.w $020B : CMP.b #$01 : BEQ .pineapples
                CMP.b #$02 : BEQ .rock_meat
                CMP.b #$03 : BEQ .seashells
                CMP.b #$04 : BEQ .honeycomb
                CMP.b #$05 : BEQ .deku_sticks
    LDA.l Bananas : JMP .draw
  .pineapples
  LDA.l Pineapples : JMP .draw
  .rock_meat
  LDA.l RockMeat : JMP .draw
  .seashells
  LDA.l Seashells : JMP .draw
  .honeycomb
  LDA.l Honeycomb : JMP .draw
  .deku_sticks
  LDA.l DekuSticks
  .draw
  ASL #2 : TAX
  REP #$30
  LDA.w TimeLabels, X : STA.w $1692+$18
  INX : INX
  LDA.w TimeLabels, X : STA.w $1692+$1A
  SEP #$30
  RTS
}

DrawGoldstarName:
{
  REP #$30
  LDX.w #$0000 : LDY.w #$0000
  .draw_goldstar_loop
  LDA.w Menu_GoldstarLabel, X : STA.w $1692, X
  INX #2 : INY #2 : CPY #$001C : BCC .draw_goldstar_loop
  RTS
}

DrawMushroomName:
{
  REP #$30
  LDX.w #$0000 : LDY.w #$0000
  .draw_mushroom_loop
  LDA.w Menu_MushroomLabel, X : STA.w $1692, X
  INX #2 : INY #2 : CPY #$001C : BCC .draw_mushroom_loop
  RTS
}

; =========================================================

DrawLocationName:
{
  REP #$30
  LDA $1B         ; check if indoors or outdoors
  AND.w #$00FF    ; isolate bit
  CMP.w #$01      ; if 1, then indoors
  BEQ .indoors

  LDA.b $8A
  ASL #5
  LDY.w #$000
  TAX

  .draw_overworld_loop
  LDA.w OverworldLocationNames, X ; Load your text character
  STA.w $12CC, Y                  ; Store into the buffer
  INX : INX
  INY : INY : CPY #$0020 : BCC .draw_overworld_loop
  RTS

  .indoors
  LDA.b $A0 ; Load current room
  ASL #5
  TAY
  LDX.w #$0000

  .draw_indoors_loop
  LDA.w DungeonLocationNames, Y : STA.w $12CC, X

  INY : INY
  INX : INX : CPX #$0020 : BCC .draw_indoors_loop
  RTS
}


; =========================================================

Menu_DrawSelect:
{
  REP #$30
  LDX.w #$16

  .loop
  LDA.w SelectItemTXT, X : STA.w $1194, X
  DEX : DEX : BPL .loop

  RTS
}

; =========================================================

Menu_DrawQuestStatus:
{
  REP #$30
  LDX.w #$16

  .loop
  LDA.w QuestStatusTXT, X : STA.w $1194, X
  DEX : DEX : BPL .loop

  RTS
}

; =========================================================

Menu_DrawAreaNameTXT:
{
  REP #$30
  LDX.w #$26

  .loop
  LDA.w AreaNameTXT, X
  STA.w $128C, X

  DEX : DEX
  BPL .loop

  RTS
}

; =========================================================

; Player's Name
; $7EF3D9-$7EF3E4: 6 characters, 16-bit each
;
; Game Character Encoding:
; 00-07: A-H          | 09-0F: J-P        | 20-29: Q-Z
; AF: I (special)     | B1: space/blank
;
; Lowercase (convert to uppercase):
; 2A-2F: a-f → A-F    | 40-41: g-h → G-H  | 42: k → K
; 43: j → J           | 44: i → I         | 45: l → L
; 46-48: m-o → M-O    | 49-4F: p-v → P-V  | 60-63: w-z → W-Z
;
; Numbers: 64-6D: 0-9
; Symbols: 6E-? 6F-! 80-- 81-. 82-, 85-( 86-)
;
; Font tiles: $2550=A, $2551=B, ... $2569=Z, $256A-$2573=0-9
; Space tile: $2417

; =========================================================
; Menu_DrawCharacterName
; Draws the player's name from $7EF3D9 to tilemap at $134C
; Converts game encoding to font tiles, uppercase only
; =========================================================
Menu_DrawCharacterName:
{
  REP #$30
  LDX.w #$000C           ; 6 characters * 2 bytes = $0C

  .loop
    LDA.l $7EF3D9, X     ; Load character code
    AND.w #$00FF         ; Mask to 8-bit
    JSR .convert_char    ; Convert to tile
    STA.w $134C, X
    DEX : DEX
    BPL .loop
    RTS

  ; ----------------------------------------------------------
  ; Subroutine: Convert character code in A to font tile
  ; Returns tile value in A
  ; ----------------------------------------------------------
  .convert_char
    ; Uppercase A-H ($00-$07)
    CMP.w #$0008 : BCC .direct
    ; Uppercase J-P ($09-$0F)
    CMP.w #$0010 : BCC .direct
    ; Q-Z ($20-$29)
    CMP.w #$0020 : BCC .space
    CMP.w #$002A : BCC .qz_range
    ; Lowercase a-f ($2A-$2F)
    CMP.w #$0030 : BCC .lower_af
    ; Gap $30-$3F
    CMP.w #$0040 : BCC .space
    ; Lowercase g-o ($40-$48)
    CMP.w #$0049 : BCC .lower_go
    ; Lowercase p-v ($49-$4F)
    CMP.w #$0050 : BCC .lower_pv
    ; Gap $50-$5F
    CMP.w #$0060 : BCC .space
    ; Lowercase w-z ($60-$63)
    CMP.w #$0064 : BCC .lower_wz
    ; Numbers ($64-$6D)
    CMP.w #$006E : BCC .numbers
    ; Special I ($AF)
    CMP.w #$00AF : BEQ .char_i
    ; Else space
  .space
    LDA.w #$2417 : RTS

  .direct
    CLC : ADC.w #$2550 : RTS

  .qz_range
    SEC : SBC.w #$0010
    CLC : ADC.w #$2550 : RTS

  .lower_af
    SEC : SBC.w #$002A
    CLC : ADC.w #$2550 : RTS

  .lower_go
    ; $40=g, $41=h, $42=k, $43=j, $44=i, $45=l, $46=m, $47=n, $48=o
    ; Use lookup table for this irregular mapping
    SEC : SBC.w #$0040    ; A = 0-8
    ASL A                 ; *2 for word index
    TAY
    LDA.w .go_table, Y : RTS
  .go_table
    dw $2556  ; $40 g -> G
    dw $2557  ; $41 h -> H
    dw $255A  ; $42 k -> K
    dw $2559  ; $43 j -> J
    dw $2558  ; $44 i -> I
    dw $255B  ; $45 l -> L
    dw $255C  ; $46 m -> M
    dw $255D  ; $47 n -> N
    dw $255E  ; $48 o -> O

  .lower_pv
    ; $49-$4F -> P-V ($255F-$2565)
    SEC : SBC.w #$003A
    CLC : ADC.w #$2550 : RTS

  .lower_wz
    ; $60-$63 -> W-Z ($2566-$2569)
    SEC : SBC.w #$004A
    CLC : ADC.w #$2550 : RTS

  .numbers
    ; $64-$6D -> 0-9 ($256A-$2573)
    SEC : SBC.w #$0064
    CLC : ADC.w #$256A : RTS

  .char_i
    LDA.w #$2558 : RTS
}


Menu_DrawButtonPrompt:
{
  REP #$30
  LDX.w #$1E             ; 16 tiles (32 bytes - 2 = $1E)

  .loop
  LDA.w ButtonPromptTXT, X : STA.w $1254, X
  DEX : DEX : BPL .loop

  SEP #$30               ; Restore 8-bit mode before return
  RTS
}

Menu_DrawRingBoxPrompt:
{
  REP #$30
  LDX.w #$1E             ; 16 tiles (32 bytes - 2 = $1E)

  .loop
  LDA.w RingBoxPromptTXT, X : STA.w $1294, X  ; One row below button prompt ($1254 + $40)
  DEX : DEX : BPL .loop

  SEP #$30
  RTS
}
