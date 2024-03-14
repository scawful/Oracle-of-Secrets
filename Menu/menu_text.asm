; =============================================================================
;  Text Routines
; =============================================================================

; Alphabet manual writing function
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

; =============================================================================

ScrollsLabel:
  dw "SCROLLS:_"

DrawScrollsLabel:
  LDX.w #$10

.draw2
  LDA.w ScrollsLabel, X
  STA.w $140C, X 
  DEX : DEX : BPL .draw2

  RTS

; =============================================================================

PlaytimeLabel:
  dw "PLAYTIME:_"

Menu_DrawPlaytimeLabel:
{
  LDX.w #$10

.draw2
  LDA.w PlaytimeLabel, X
  STA.w $1692, X 
  DEX : DEX : BPL .draw2

  ; ; Starting at 0 = $2570 we draw the hours 
  ; ; Get hours 
  ; LDA $7EE000 
  
  ; ; CLC : ADC #$2570 

  
  ; STA.w $1692+#$12 ; First digit of hour 

  ; STA.w $1692+#$14 ; Second digit of hour 

  ; ; Get minutes
  ; LDA $7EE001 
  ; ; CLC : ADC #$2570
  ; STA.w $1692+#$16  ; First digit of minute
  ; STA.w $1692+#$18 ; Second digit of minute

  RTS
}

; =============================================================================

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
  dw "_SECRET_TOME__  "
  dw "___SOMARIA____  "
  ; dw "____BYRNA_____  "
  dw "_FISHING_ROD__  "
  dw "_ROCS_FEATHER_  "
  dw "____BOTTLE____  "
  dw "__DEKU_MASK___  "
  dw "__ZORA_MASK___  "
  dw "__WOLF_MASK___  "
  dw "__BUNNY_HOOD__  "
  dw "__STONE_MASK__  "
  dw "____BOTTLE____  "

Menu_BottleItems:
  dw "___MUSHROOM___  "
  dw "_EMPTY_BOTTLE_  "
  dw "__RED_POTION__  "
  dw "_GREEN_POTION_  "
  dw "_BLUE_POTION__  "
  dw "____FAIRY_____  "
  dw "__GOOD_BEE____  "

Menu_GoldstarLabel:
  dw "__GOLD_STAR___  "

Menu_SongNames:
  dw "SONG:_SOARING_  "
  dw "SONG:_HEALING_  "
  dw "SONG:_STORMS__  "

Menu_DrawItemName:
{
  SEP #$30
  LDA.w $0202 : CMP.b #$03 : BEQ .goldstar
  LDA.w $0202 : CMP.b #$0D : BEQ .ocarina
  ; Check if it's a bottle
  LDA.w $0202 : CMP.b #$06 : BEQ .bottle_1
  LDA.w $0202 : CMP.b #$0C : BEQ .bottle_2
  LDA.w $0202 : CMP.b #$12 : BEQ .bottle_3
  LDA.w $0202 : CMP.b #$18 : BEQ .bottle_4
  
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

.goldstar
  LDA GoldstarOrHookshot : CMP.b #$02 : BNE .draw_item
  JSR MaybeDrawGoldstarName
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

MaybeDrawGoldstarName: 
{
    REP #$30
    LDX.w #$0000
    LDY.w #$0000
  .draw_goldstar_loop
    LDA.w Menu_GoldstarLabel, X
    STA.w $1692, X : INX #2 : INY #2 : CPY #$001C : BCC .draw_goldstar_loop
    RTS
}

; =============================================================================

DrawLocationName:
{
  REP #$30
  LDA $1B 		    ; check if indoors or outdoors 
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


; =============================================================================

Menu_DrawSelect:
{
  REP #$30
  LDX.w #$16

.loop
  LDA.w SelectItemTXT, X : STA.w $1194, X
  DEX #2 : BPL .loop

  RTS
}

; =============================================================================

Menu_DrawQuestStatus:
{
  REP #$30
  LDX.w #$16

.loop
  LDA.w QuestStatusTXT, X : STA.w $1194, X
  DEX #2 : BPL .loop

  RTS
}

; =============================================================================

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

; =============================================================================
    
; Player's Name
; $3D9-$3E4: See appendix for listing of character codes. 
; Note each of the six letters is represented by a 16-bit number.
;
; 00-A 01-B 02-C 03-D 04-E 05-F 06=G 07-H 
; 08-I^ 09-J 0A-K 0B-L 0C-M 0D-N OE-O OF-P 
; 10-?? 20-Q 21-R 22-S 23-T 24-U 25-V 
; 26-W 27-X 28-Y 29-Z 
;
; 2A-a 2B-b-2C-c 2D-d 2E-e 2F-f 40-g 41-h 
; 42-k 43-j 44-i 45-l 46-m 47-n 48-o 49-p 
; 4A-q 4B-r 4C-s 4D-t 4E-u 4F-v 60-w 61-x 62-y 63-z
;
; 64-0 65-1 66-2 67-3 68-4 69-5 6A-6 6B-7 6C-8 6D-9 6E-"?" 6F-"!"
; 80-"-"
; 81-"." 
; 82-"," 
; 85-"(" 86-")" 
;
; B1-blank^
;
; ^This code is not the canon encoding of this character. ex. AF is the proper "I". 08 is not.

Menu_DrawCharacterName:
{
  REP #$30
  LDX.w #$C

.draw_name_loop
  ; Player's Name in memory, indexed by X 
  LDA.l $7EF3D9, X
  
  ; Check if the character is the special encoding for "I" first.
  CMP.w #$AF : BEQ .fix_i 

  ; Check if it is the gap between the P and Q characters 
  CMP.w #$10 : BCC .write_to_screen ; handle P, Q gap
  SBC.b #$10
  CLC
  CMP.w #$2A : BCS .fix_lowercase 
  
.write_to_screen
  CLC : ADC #$2550
  ; STA.w $138C, X
  STA.w $134C, X
  DEX : DEX : BPL .draw_name_loop

  RTS

.fix_i
  LDA.w #$08 : BRA .write_to_screen 

.fix_lowercase
  ; TODO: Convert the lowercase value of 2A or greater inside of the 
  ; accumulator and convert it to an uppercase value. 
  LDA.w #$1D : BRA .write_to_screen
}