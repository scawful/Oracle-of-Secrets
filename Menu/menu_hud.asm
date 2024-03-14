; =========================================================
;  Menu - Headsup Display

org $0DFB91 ; UpdateHUDBuffer
  JSL HUD_Update
  RTS

newIgnoreItemBox: ; UpdateHUDBuffer_skip_item
  JSL HUD_Update
  RTS

org $0DDD21 ; RefillLogic_heart_refill_done
  JSR newIgnoreItemBox

org $0DFC09 ; UpdateHUDBuffer_skip_hearts
  JSL HUD_Update_ignore_health
  RTS

org $0DDB85 ; RefreshIcon_long
  JSL HUD_Update

org $0DFDAB ; UpdateHUDBuffer_UpdateHearts
  JSL HUD_UpdateHearts
  RTS

; Partial hearts draw position
org $0DF14F ; AnimateHeartRefill
  SEP   #$30
  LDA.b #$44 : STA $00
  LDA.b #$C7 : STA $01
  LDA.b #$7E : STA $02


; ==========================================================
; Main HUD Update Loop

org $2E8000
HUD_Update:
{
  JSR HUD_UpdateItemBox

  SEP #$30

  ; need to draw partial heart still though.
  LDA.b #$FD : STA $0A
  LDA.b #$F9 : STA $0B
  LDA.b #$0D : STA $0C

  LDA.b #$44 : STA $07
  LDA.b #$C7 : STA $08
  LDA.b #$7E : STA $09

  REP #$30

  ; Load Capacity health.
  LDA $7EF36C : AND.w #$00FF : STA $00 : STA $02 : STA $04

  ; First, just draw all the empty hearts (capacity health)
  JSR HUD_UpdateHearts

  SEP #$30

  LDA.b #$03 : STA $0A
  LDA.b #$FA : STA $0B
  LDA.b #$0D : STA $0C

  LDA.b #$44 : STA $07
  LDA.b #$C7 : STA $08
  LDA.b #$7E : STA $09

  ; Branch if at full health
  LDA $7EF36C : CMP $7EF36D : BEQ .healthUpdated

  ; Seems absurd to have a branch of zero bytes, right?
  SEC : SBC #$04 : CMP $7EF36D : BCS .healthUpdated

.healthUpdated

  ; A = actual health + 0x03;
  LDA $7EF36D : CLC : ADC.b #$03

  REP #$30

  AND.w #$00FC : STA $00 : STA $04

  LDA $7EF36C : AND.w #$00FF : STA $02

  ; filling in the full and partially filled hearts (actual health)
  JSR HUD_UpdateHearts

.ignore_health ; *$6FC09 ALTERNATE ENTRY POINT ; reentry hook

  REP #$30

  ; Magic amount indicator (normal, 1/2, or 1/4)
  LDA $7EF37B : AND.w #$00FF : CMP.w #$0001 : BCC .normal_magic_meter

  ; draw 1/2 magic meter
  LDA.w #$2851 : STA $7EC730
  LDA.w #$28FA : STA $7EC732

.normal_magic_meter

  ; check player magic (ranges from 0 to 0x7F)
  ; X = ((MP & 0xFF)) + 7) & 0xFFF8)
  LDA $7EF36E : AND.w #$00FF : CLC : ADC #$0007 : AND.w #$FFF8 : TAX

  ; these four writes draw the magic power bar based on how much MP you have
  LDA.l (MagicTilemap)+0, X : STA $7EC76C
  LDA.l (MagicTilemap)+2, X : STA $7EC76E
  LDA.l (MagicTilemap)+4, X : STA $7EC770
  LDA.l (MagicTilemap)+6, X : STA $7EC772

  ; Load how many rupees the player has
  LDA $7EF362

  JSR HexToDecimal

  REP #$30

  ; The tile index for the first rupee digit
  LDA $03 : AND.w #$00FF : ORA.w #$2400 : STA $7EC79C

  ; The tile index for the second rupee digit
  LDA $04 : AND.w #$00FF : ORA.w #$2400 : STA $7EC79E

  ; The tile index for the third rupee digit
  LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC7A0

  ; Clear digit tiles
  LDA #$A00C : STA $7EC7B0
  LDA #$A00C : STA $7EC7B2

  ; Check if the user has bombs equipped
  LDX   $0202 : LDA $7EF33F, X : AND.w #$00FF
  CPX.w #$0004 : BNE .not_bombs

  ; Number of bombs Link has.
  LDA $7EF343 : AND.w #$00FF
  JSR HexToDecimal
  REP #$30

  ; The tile index for the first bomb digit
  LDA $04 : AND.w #$00FF : ORA.w #$2400 : STA $7EC7B0

  ; The tile index for the second bomb digit
  LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC7B2

.not_bombs
  ; Check if the user has arrows equipped
  LDX   $0202 : LDA $7EF33F, X : AND.w #$00FF
  CPX.w #$0001 : BNE .not_arrows

  ; Number of Arrows Link has.
  LDA $7EF377 : AND.w #$00FF

  ; converts hex to up to 3 decimal digits
  JSR HexToDecimal
  REP #$30

  ; The tile index for the first arrow digit
  LDA $04 : AND.w #$00FF : ORA.w #$2400 : STA $7EC7B0

  ; The tile index for the second arrow digit
  LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC7B2

.not_arrows
  LDA.w #$007F : STA $05

  ; Load number of Keys Link has
  LDA $7EF36F : AND.w #$00FF : CMP.w #$00FF : BEQ .no_keys
  JSR HexToDecimal
.no_keys
  REP #$30

  ; The key digit, which is optionally drawn.
  ; Also check to see if the key spot is blank
  LDA   $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC7A4
  CMP.w #$247F : BNE .dont_blank_key_icon

  ; TODO: Find the proper index of the key icon, this one is outdated.
  ; If the key digit is blank, also blank out the key icon.
  STA $7EC724

.dont_blank_key_icon
  SEP #$30
  RTL
}

; =========================================================

Full        =  $3C5F
MostlyFull  =  $3C4D
KindaFull   =  $3C4E
HalfEmpty   =  $3C4F
AlmostEmpty = $3C5E
Empty       = $3C4C

MagicTilemap:
  dw Empty, Empty, Empty, Empty
  dw Empty, Empty, Empty, AlmostEmpty
  dw Empty, Empty, Empty, HalfEmpty
  dw Empty, Empty, Empty, KindaFull
  dw Empty, Empty, Empty, MostlyFull
  dw Empty, Empty, AlmostEmpty, Full
  dw Empty, Empty, HalfEmpty, Full
  dw Empty, Empty, KindaFull, Full
  dw Empty, Empty, MostlyFull, Full
  dw Empty, AlmostEmpty, Full, Full
  dw Empty, HalfEmpty, Full, Full
  dw Empty, KindaFull, Full, Full
  dw Empty, MostlyFull, Full, Full
  dw AlmostEmpty, Full, Full, Full
  dw HalfEmpty, Full, Full, Full
  dw KindaFull, Full, Full, Full
  dw MostlyFull, Full, Full, Full

; =========================================================
; *$6FAFD-$6FB90 LOCAL

HUD_UpdateItemBox:
{
  SEP #$30
  ; Dost thou haveth the the bow?
  LDA $7EF340 : BEQ .no_bow

  CMP.b #$03 : BCC .no_silver_arrows

  ; check how many arrows the player has
  LDA   $7EF377 : BNE .draw_bow_item_icon
  LDX.b #$03
  BRA   .draw_bow_item_icon

.no_silver_arrows

  LDX.b #$02
  
  LDA $7EF377 : BNE .draw_bow_item_icon
  
  LDX.b #$01

.draw_bow_item_icon
  ; values of X correspond to how the icon will end up drawn:
  ; 0x01 - normal bow with no arrows
  ; 0x02 - normal bow with arrows
  ; 0x03 - silver bow with no silver arrows
  ; 0x04 - silver bow with silver arrows
  TXA : STA $7EF340

.no_bow
  REP   #$30
  LDX   $0202 : BEQ .no_equipped_item
  LDA   $7EF33F, X : AND.w #$00FF
  CPX.w #$0004 : BNE .bombs_not_equipped
  LDA.w #$0001

.bombs_not_equipped
  CPX.w #$0006 : BNE .bottle1_not_equipped
  JMP   .load_bottle_content

.bottle1_not_equipped
  CPX.w #$000C : BNE .bottle2_not_equipped
  LDA.w #$0002 : JMP   .load_bottle_content

.bottle2_not_equipped
  CPX.w #$0012 : BNE .bottle3_not_equipped
  LDA.w #$0003 : JMP   .load_bottle_content

.bottle3_not_equipped
  CPX.w #$0018 : BNE .bottle_not_equipped
  LDA.w #$0004

.load_bottle_content
  TXY : TAX : LDA $7EF35B, X : AND.w #$00FF : TYX

.bottle_not_equipped
  CPX.w #$000D : BNE .flute_not_equipped
  LDA   $030F

.flute_not_equipped
  CPX.w #$0003 : BNE .hookshot_not_equipped
  LDA.w GoldstarOrHookshot : BEQ .hookshot_not_equipped
  SEC   : SBC.b #$01

.hookshot_not_equipped

  JSR HUD_DrawItem

.no_equipped_item

  RTS
}

HUD_DrawItem:
{
  STA $02
  TXA : DEC A : ASL A : TAX
  LDA $FA93, X : STA $04
  LDA $02 : ASL #3 : TAY

  ; These addresses form the item box graphics.
  LDA ($04), Y : STA $7EC776 : INY #2
  LDA ($04), Y : STA $7EC778 : INY #2
  LDA ($04), Y : STA $7EC7B6 : INY #2
  LDA ($04), Y : STA $7EC7B8 : INY #2

  RTS
}

; =========================================================

HUD_UpdateHearts:
{
  ; Draws hearts in a painfully slow loop
  LDX.w #$0000

.next_heart
  LDA.b $00 : CMP.w #$0008 : BCC .less_than_one_heart
  ; Notice no SEC was needed since carry is assumedly set.
  SBC.w #$0008 : STA.b $00
  LDY.w #$0004
  JSR   .draw_heart
  INX   #2
  BRA   .next_heart

.less_than_one_heart
  CMP.w #$0005 : BCC .half_heart_or_less
  LDY.w #$0004
  BRA   .draw_heart

.half_heart_or_less
  CMP.w #$0001 : BCC .empty_heart
  LDY.w #$0002
  BRA   .draw_heart

.empty_heart
  RTS

.draw_heart
  ; Compare number of hearts so far on current line to 10
  CPX.w #$0014 : BCC .no_line_change
  ; if not, we have to move down one tile in the tilemap
  LDX.w #$0000
  LDA.b $07 : CLC : ADC.w #$0040 : STA.b $07

.no_line_change
  LDA.b [$0A], Y : TXY : STA.b [$07], Y
  RTS
}

; =========================================================

HexToDecimal:
{
    REP   #$30
    STZ   $0003
    LDX.w #$0000
    LDY.w #$0002
.next_digit
    CMP $F9F9,       Y : BCC .next_lowest_10s_place
    SEC : SBC $F9F9, Y
    INC $03,         X
    BRA .next_digit
.next_lowest_10s_place
    INX   : DEY #2
    BPL   .next_digit
    STA   $05
    SEP   #$30
    LDX.b #$02
.set_next_digit_tile
    LDA   $03, X : CMP.b #$7F
    BEQ   .blank_digit
    ORA.b #$90
.blank_digit
    STA $03, X
    DEX : BPL .set_next_digit_tile
    RTS
}

pushpc

; =========================================================

; $6FA93-$6FAFC DATA
org $0DFA93
HudItems:
{
  ; bows, boomerang, hookshot, bombs, powder, bottle1
  dw $F629, $F651, $F669, $F679, $F689, $F751
  ; hammer, lamp, fire rod, ice rod, mirror, bottle2
  dw $F701, $F6F1, $F6A1, $F6B1, $F7C9, $F751
  ; flute, book, somaria, byrna, feather, bottle3
  dw $F859, $F741, $F799, $F7A9, $F731, $F751
  ; deku,   zora,  wolf,  bunny,  stone, bottle4
  dw $F6E1, $F821, $F6D1, $F7B9, $F811, $F751
}

; F711

; TODO: Cleanup this table
org $0DF629
  dw $20F5, $20F5, $20F5, $20F5 ; No bow
	dw $28BA, $28E9, $28E8, $28CB ; Empty bow
	dw $28BA, $28BB, $24CA, $28CB ; Bow and arrows
	dw $28BA, $28E9, $28E8, $28CB ; Empty silvers bow
	dw $28BA, $28BB, $24CA, $28CB ; Silver bow and arrows

; Boomerang
org $0DF651
  dw $20F5, $20F5, $20F5, $20F5 ; No boomerang
  dw $2CB8, $2CB9, $2CC9, $ACB9 ; Blue boomerang
	dw $24B8, $24B9, $24C9, $A4B9 ; Red boomerang

; Hookshot
org $0DF669
  dw $24F5, $24F6, $24C0, $24F5 ; Hookshot
  dw $2C17, $3531, $2D40, $3541 ; Ball & Chain

; Bombs (Unchanged)

; Powder
org $0DF689
  dw $20F5, $20F5, $20F5, $20F5 ; No powder
  dw $2444, $2445, $2446, $2447 ; Mushroom
	dw $283B, $283C, $283D, $283E ; Powder

; Hammer
org $0DF701
  dw $24B6, $24B7, $20C6, $24C7 ; Hammer
  dw $24B6, $24B7, $20C6, $24C7 ; Hammer

; Lamp
org $0DF6F1
  dw $24BC, $24BD, $24CC, $64CC
  
; Fire Rod
org $0DF6B1
 dw $2CB0, $2CBE, $2CC0, $2CC1

; Ice Rod
org $0DF6A1
 dw $24B0, $24B1, $24C0, $24C1

; Mirror
org $0DF7C9
  dw $2C62, $2C63, $2C72, $2C73 ; Mirror
  dw $2C62, $2C63, $2C72, $2C73 ; Mirror

; Ocarina
org $0DF859
  dw $2CD4, $2CD5, $2CE4, $2CE5
  dw $2CD4, $2CD5, $2CE4, $2CE5 ; Blue
  dw $3CD4, $3CD5, $3CE4, $3CE5 ; Green
  dw $24D4, $24D5, $24E4, $24E5 ; Red


; Roc's Feather (Net)
org $0DF731
  dw $2840, $2841, $3C42, $3C43 ; Roc's Feather

; Bottles
org $0DF751
  dw $20F5, $20F5, $20F5, $20F5 ; No bottle
  dw $2044, $2045, $2046, $2047 ; Mushroom
  dw $2837, $2838, $2CC3, $2CD3 ; Empty bottle
  dw $24D2, $64D2, $24E2, $24E3 ; Red potion
  dw $3CD2, $7CD2, $3CE2, $3CE3 ; Green potion
  dw $2CD2, $6CD2, $2CE2, $2CE3 ; Blue potion
  dw $2855, $6855, $2C57, $2C5A ; Fairy
  dw $2837, $2838, $2839, $283A ; Bee
  dw $2837, $2838, $2839, $283A ; Good bee

; Somaria (Unchanged)

; Byrna
org $0DF7A9
  dw $2CDC, $2CDD, $2CEC, $2CED ; Cane of Byrna
  dw $2C82, $2C83, $2C8B, $2C8C ; Fishing Rod


; Deku (Quake)
org $0DF6E1
  dw $20F5, $20F5, $20F5, $20F5 ; No bombos
  dw $2066, $6066, $2076, $6076 ; Deku Mask

; Zora (Moon Pearl Slot)
org $0DF821
  dw $20F5, $20F5, $20F5, $20F5
  dw $2C88, $6C88, $2C89, $6C89
  dw $2C88, $6C88, $2C89, $6C89

; Wolf (Ether)
org $0DF6D1
  dw $3086, $7086, $3087, $7087
  dw $3086, $7086, $3087, $7087
  dw $3086, $7086, $3087, $7087

; Bunny (Cape Slot)
org $0DF7B9
  dw $3469, $7469, $3479, $7479
  dw $3469, $7469, $3479, $7479

; Stone Mask (Flippers Slot)
org $0DF811 
  dw $20F5, $20F5, $20F5, $20F5
  dw $30B4, $30B5, $30C4, $30C5

; =========================================================
; $6FE77-$6FFC0

org    $0DFE77
HUD_Tilemap:
incbin tilemaps/hud.tilemap

; #_02816A: JSL RebuildHUD_Keys

; LoadUnderworldRoomRebuildHUD:
; #_028118: LDA.b #$00 ; reset mosaic level

; ==========================================================

; $57CE0 DATA
org    $0AFCE0
FloorIndicatorNumberHigh:
{
  dw $2508, $2509, $2509, $250A, $250B, $250C, $250D, $251D
  dw $E51C, $250E, $007F
}

; ==========================================================

; $57CF6 DATA
org $0AFCF6
FloorIndicatorNumberLow:
{
  dw $2518, $2519, $A509, $251A, $251B, $251C, $2518, $A51D
  dw $E50C, $A50E, $007F
}

; ==========================================================

; *$57D0C-$57DA7 JUMP LOCATION (LONG)
org $0AFD0C
FloorIndicator:
{
  REP   #$30
  LDA   $04A0 : AND.w #$00FF : BEQ .hide_indicator
  INC   A : CMP.w #$00C0 : BNE .dont_disable
  ; if the count up timer reaches 0x00BF frames
  ; disable the floor indicator during the next frame.
  LDA.w #$0000
.dont_disable
  STA   $04A0
  PHB   : PHK : PLB
  LDA.w #$251E : STA $7EC7F0
  INC   A        : STA $7EC832
  INC   A        : STA $7EC830
  LDA.w #$250F : STA $7EC7F2
  LDX.w #$0000

  ; check whether $A4[1] has a negative value
  ; $A3 has nothing to do with $A4
  LDA   $A3 : BMI .basement_floor

  ; check which floor Link is on.
  LDA   $A4 : BNE .not_floor_1F
  LDA   $A0 : CMP.w #$0002 : BEQ .sanctuary_rat_room
  SEP   #$20

  ; Check the world state
  LDA   $7EF3C5 : CMP.b #$02 : BCS .no_rain_state

  ; cause the ambient rain sound to occur (indoor version)
  LDA.b #$03 : STA $012D

.no_rain_state
  REP #$20
.not_floor_1F
.sanctuary_rat_room
  LDA $A4 : AND.w #$00FF
  BRA .set_floor_indicator_number

.basement_floor
  SEP   #$20
  ; turn off any ambient sound effects
  LDA.b #$05 : STA $012D
  REP   #$20
  INX   #2
  LDA   $A4 : ORA.w #$FF00 : EOR.w #$FFFF

.set_floor_indicator_number

  ASL A : TAY

  LDA FloorIndicatorNumberHigh, Y : STA $7EC7F0, X
  LDA FloorIndicatorNumberLow, Y  : STA $7EC830, X

  SEP #$30

  PLB

  ; send a signal indicating that bg3 needs updating
  INC $16

  RTL

.hide_indicator ; *$57D90 ALTERNATE ENTRY POINT

  REP #$20

  ; disable the display of the floor indicator.
  LDA.w #$007F : STA $7EC7F0 : STA $7EC830 : STA $7EC7F2 : STA $7EC832

  SEP #$30

  RTL
}

pullpc