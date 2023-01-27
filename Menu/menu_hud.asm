; =============================================================================
;  Menu - Headsup Display
; =============================================================================


; ==============================================================================
; Vanilla HUD Hijack 

org $0DFB91
  JSL HUD_Update
  RTS

newIgnoreItemBox:
  JSL HUD_Update
  RTS

org $0DDD21
  JSR newIgnoreItemBox

org $0DF1BC
  JSL HUD_AnimateHeartRefill
  RTS

org $0DFC09
  JSL HUD_Update_ignoreHealth
  RTS

org $0DFC1B
  JSR $F1BC

org $0DDB85
  JSL HUD_Update

org $0DFDAB
  JSL HUD_UpdateHearts
  RTS

; Partial hearts draw position 
org $0DF14F
  SEP #$30
  LDA.b #$44 : STA $00
  LDA.b #$C7 : STA $01
  LDA.b #$7E : STA $02

; ==============================================================================
; New Code Region Starts Here 

org $268000

; ==============================================================================
; Main HUD Update Loop

HUD_Update:
{
  JSR HUD_UpdateItemBox

.ignoreItemBox ; ALTERNATE ENTRY POINT

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

.ignoreHealth ; *$6FC09 ALTERNATE ENTRY POINT ; reentry hook

  REP #$30
  
  ; Magic amount indicator (normal, 1/2, or 1/4)
  LDA $7EF37B : AND.w #$00FF : CMP.w #$0001 : BCC .normalMagicMeter
  
  ; draw 1/2 magic meter 
  LDA.w #$2851 : STA $7EC730
  LDA.w #$28FA : STA $7EC732

.normalMagicMeter

  ; check player magic (ranges from 0 to 0x7F)
  ; X = ((MP & 0xFF)) + 7) & 0xFFF8)
  LDA $7EF36E : AND.w #$00FF : CLC : ADC #$0007 : AND.w #$FFF8 : TAX
  
  ; these four writes draw the magic power bar based on how much MP you have 
  LDA.l (MagicTilemap)+0, X : STA $7EC76A
  LDA.l (MagicTilemap)+2, X : STA $7EC76C
  LDA.l (MagicTilemap)+4, X : STA $7EC76E
  LDA.l (MagicTilemap)+6, X : STA $7EC770
  LDA.l (MagicTilemap)+8, X : STA $7EC772

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
  LDX $0202 : LDA $7EF33F, X : AND.w #$00FF
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
  LDX $0202 : LDA $7EF33F, X : AND.w #$00FF
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
  LDA $7EF36F : AND.w #$00FF : CMP.w #$00FF : BEQ .noKeys
  JSR HexToDecimal
.noKeys
  REP #$30

  ; The key digit, which is optionally drawn.
  ; Also check to see if the key spot is blank
  LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC7A4
  CMP.w #$247F : BNE .dontBlankKeyIcon

  ; If the key digit is blank, also blank out the key icon.
  STA $7EC724
.dontBlankKeyIcon
  SEP #$30

  RTL
}

; =============================================================================

; .full_tile
;   dw $3C5F
; .mostly_full
;   dw $3C4D
; .kinda_full
;   dw $3C4E
; .half_empty
;   dw $3C4F
; .almost_empty
;   dw $3C5E 
; .empty_tile
;   dw $3C4C

MagicTilemap:
  dw $3C4C, $3C4C, $3C4C, $3C4C, $3C4C
  dw $3C4C, $3C4C, $3C4C, $3C4C, $3C5F
  dw $3C4C, $3C4C, $3C4C, $3C4C, $3C4C
  dw $3C4C, $3C4C, $3C4C, $3C4C, $3C4D
  dw $3C4C, $3C4C, $3C4C, $3C4C, $3C4E
  dw $3C4C, $3C4C, $3C4C, $3C5F, $3C5F
  dw $3C4C, $3C4C, $3C4C, $3C4C, $3C5F
  dw $3C4C, $3C4C, $3C4C, $3C4D, $3C5F
  dw $3C4C, $3C4C, $3C4C, $3C4E, $3C5F

  dw $3C4D, $3C5F, $3C5F, $3C5F, $3C5F
  dw $3C4E, $3C5F, $3C5F, $3C5F, $3C5F
  dw $3C4F, $3C5F, $3C5F, $3C5F, $3C5F
  dw $3C5E, $3C5F, $3C5F, $3C5F, $3C5F 
  ; value 78 
  dw $3C5F, $3C5F, $3C5F, $3C5F, $3C5F 
  ; value 80 


; =============================================================================
; *$6F14F-$6F1B2 LOCAL

HUD_HeartDisplayFrames:
  dw $24A3, $24A4, $24A3, $24A0

HUD_AnimateHeartRefill:
{
  SEP #$30
  
  ; $00[3] = $7EC768 (wram address of first row of hearts in tilemap buffer)
  LDA.b #$44 : STA $00
  LDA.b #$C7 : STA $01
  LDA.b #$7E : STA $02
  
  DEC.w $0208 : BNE .return
  
  REP #$30
  
  ; Y = ( ( ( (current_health & 0x00F8) - 1) / 8 ) * 2)
  LDA $7EF36D : AND.w #$00F8 : DEC A : LSR #3 : ASL A : TAY : CMP.w #$0014
  
  BCC .halfHealthOrLess
  
  SBC.w #$0014 : TAY
  
  ; $00[3] = $7EC7A8 (wram address of second row of hearts)
  LDA $00 : CLC : ADC.w #$0040 : STA.b $00

.halfHealthOrLess

  SEP #$30
  LDX.w $0209 : LDA.l $0DFA11, X : STA.w $0208
  TXA : ASL A : TAX
  
  LDA.l HUD_HeartDisplayFrames+0, X : STA.b [$00], Y : INY 
  LDA.l HUD_HeartDisplayFrames+1, X : STA.b [$00], Y
  
  LDA.w $0209 : INC A : AND.b #$03 : STA.w $0209
  BNE .return
  
  SEP #$30
  JSL $0DFA70 ; Rebuild Vanilla 
  STZ $020A

.return
  CLC
  RTS
}

; ============================================================================ 
; *$6FAFD-$6FB90 LOCAL

HUD_UpdateItemBox:
{
  SEP #$30
  ; Dost thou haveth the the bow?
  LDA $7EF340 : BEQ .havethNoBow
  LDX.b #$04
  ; check how many arrows the player has
  LDA $7EF377 : BNE .drawBowItemIcon
  LDX.b #$03
  BRA .drawBowItemIcon

.drawBowItemIcon
  ; values of X correspond to how the icon will end up drawn:
  ; 0x01 - normal bow with no arrows
  ; 0x02 - normal bow with arrows
  ; 0x03 - silver bow with no silver arrows
  ; 0x04 - silver bow with silver arrows
  TXA : STA $7EF340

.havethNoBow
  REP #$30
  LDX $0202 : BEQ .noEquippedItem
  LDA $7EF33F, X : AND.w #$00FF
  CPX.w #$0004 : BNE .bombsNotEquipped
  LDA.w #$0001
  
.bombsNotEquipped
  CPX.w #$0010 : BNE .bottleNotEquipped
  TXY : TAX : LDA $7EF35B, X : AND.w #$00FF : TYX

.bottleNotEquipped
  STA $02
  TXA : DEC A : ASL A : TAX
  LDA $FA93, X : STA $04
  ; LDA.w HudItems, X : STA $04
  LDA $02 : ASL #3 : TAY
  
  ; These addresses form the item box graphics.
  LDA ($04), Y : STA $7EC776 : INY #2
  LDA ($04), Y : STA $7EC778 : INY #2
  LDA ($04), Y : STA $7EC7B6 : INY #2
  LDA ($04), Y : STA $7EC7B8 : INY #2

.noEquippedItem

  RTS
}

; =============================================================================

HUD_UpdateHearts:
{
  ; Draws hearts in a painfully slow loop
  LDX.w #$0000

.nextHeart
  LDA.b $00 : CMP.w #$0008 : BCC .lessThanOneHeart
  ; Notice no SEC was needed since carry is assumedly set.
  SBC.w #$0008 : STA.b $00
  LDY.w #$0004
  JSR .drawHeart
  INX #2
  BRA .nextHeart

.lessThanOneHeart
  CMP.w #$0005 : BCC .halfHeartOrLess
  LDY.w #$0004
  BRA .drawHeart

.halfHeartOrLess
  CMP.w #$0001 : BCC .emptyHeart
  LDY.w #$0002
  BRA .drawHeart

.emptyHeart
  RTS

.drawHeart
  ; Compare number of hearts so far on current line to 10
  CPX.w #$0014 : BCC .noLineChange
  ; if not, we have to move down one tile in the tilemap
  LDX.w #$0000
  LDA.b $07 : CLC : ADC.w #$0040 : STA.b $07

.noLineChange
  LDA.b [$0A], Y : TXY : STA.b [$07], Y
  RTS
}

; =============================================================================

HexToDecimal:
{
    REP #$30
    STZ $0003
    LDX.w #$0000
    LDY.w #$0002
.nextDigit
    CMP $F9F9, Y : BCC .nextLowest10sPlace
    SEC : SBC $F9F9, Y
    INC $03, X
    BRA .nextDigit
.nextLowest10sPlace
    INX : DEY #2
    BPL .nextDigit
    STA $05
    SEP #$30
    LDX.b #$02
.setNextDigitTile
    LDA $03, X : CMP.b #$7F
    BEQ .blankDigit
    ORA.b #$90
.blankDigit
    STA $03, X
    DEX : BPL .setNextDigitTile
    RTS
} 

; =============================================================================

; dw BowsGFX, BoomsGFX, HookGFX
; dw BombsGFX, PowderGFX, BottlesGFX
; dw HammerGFX, LampGFX, Fire_rodGFX
; dw Ice_rodGFX, MirrorGFX, BottlesGFX
; dw OcarinaGFX, BookGFX, SomariaGFX
; dw ByrnaGFX, JumpFeatherGFX, BottlesGFX
; dw DekuMaskGFX, ZoraMaskGFX, WolfMaskGFX
; dw BunnyHoodGFX, StoneMaskGFX, BottlesGFX

; $6FA93-$6FAFC DATA
org $0DFA93
HudItems:
{
  ; bows, boomerang, hookshot, bombs, powder, bottle1
  dw $F629, $F651, $F669, $F679, $F689, $F751
  ; hammer, lamp, fire rod, Ice Rod, mirror, bottle2
  dw $F701, $F6F1, $F6A1, $F6B1, $F7C9, $F751
  ; flute, book, somaria, byrna, feather, bottle3
  dw $F711, $F741, $F799,  $F7A9, $F731, $F751
  ; bombos, quake, ether, stone mask 
  dw $F6E1, $F6C1, $F6D1, $F7B9, $F811, $F751
}

org $0DF651
  dw $2CB8, $2CB9, $2CF5, $2CC9 ; Blue boomerang
  dw $24B8, $24B9, $24F5, $24C9 ; Red boomerang

; =============================================================================
; $6FE77-$6FFC0 

org $0DFE77
HUD_Tilemap:
{
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F
  
  ; magic bar top part
  dw $200B, $200C, $200C, $200C, $200C, $200C
  ; item frame top part 
  dw $206C, $206D, $206E, $206F 

  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $3CA8, $FCA8, $207F, $207F, $207F
  
  ; magic bar
  dw $201B, $344B
  dw $344B, $344B, $344B, $344B
  
   ; item frame left part 
  dw $20DE, $207F, $207F, $20DF
                               
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F

  ; magic bar bottom part 
  dw $A00B, $A00C
  dw $A00C, $A00C, $A00C, $A00C

  ; item frame right part 
  dw $20EE, $207F, $207F, $20EF
                                
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F
  
  ; item frame bottom part
  dw $207C, $207D, $207E, $201D

  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F
}

; ==============================================================================

; $57CE0 DATA
org $0AFCE0
FloorIndicatorNumberHigh:
{
  dw $2508, $2509, $2509, $250A, $250B, $250C, $250D, $251D
  dw $E51C, $250E, $007F
}

; ==============================================================================

; $57CF6 DATA
org $0AFCF6
FloorIndicatorNumberLow:
{
  dw $2518, $2519, $A509, $251A, $251B, $251C, $2518, $A51D
  dw $E50C, $A50E, $007F
}

; ==============================================================================

; *$57D0C-$57DA7 JUMP LOCATION (LONG)
org $0AFD0C
FloorIndicator:
{  
  REP #$30 
  LDA $04A0 : AND.w #$00FF : BEQ .hideIndicator
  INC A : CMP.w #$00C0 : BNE .dontDisable
  ; if the count up timer reaches 0x00BF frames, disable the floor indicator during the next frame.
  LDA.w #$0000
.dontDisable
  STA $04A0
  PHB : PHK : PLB
  LDA.w #$251E : STA $7EC7F0
  INC A        : STA $7EC832
  INC A        : STA $7EC830
  LDA.w #$250F : STA $7EC7F2
  LDX.w #$0000
  
  ; this confused me at first, but it's actually looking at whether $A4[1]
  ; has a negative value $A3 has nothing to do with $A4
  LDA $A3 : BMI .basementFloor
  ; check which floor Link is on.
  LDA $A4 : BNE .notFloor1F
  LDA $A0 : CMP.w #$0002 : BEQ .sanctuaryRatRoom
  SEP #$20
  ; Check the world state
  LDA $7EF3C5 : CMP.b #$02 : BCS .noRainSound
  ; cause the ambient rain sound to occur (indoor version)
  LDA.b #$03 : STA $012D
.noRainSound
  REP #$20
.notFloor1F
.sanctuaryRatRoom
  LDA $A4 : AND.w #$00FF
  BRA .setFloorIndicatorNumber
.basementFloor
  SEP #$20
  ; turn off any ambient sound effects
  LDA.b #$05 : STA $012D
  REP #$20
  INX #2
  LDA $A4 : ORA.w #$FF00 : EOR.w #$FFFF
.setFloorIndicatorNumber

  ASL A : TAY
  
  LDA FloorIndicatorNumberHigh, Y : STA $7EC7F0, X
  LDA FloorIndicatorNumberLow, Y  : STA $7EC830, X
  
  SEP #$30
  
  PLB
  
  ; send a signal indicating that bg3 needs updating
  INC $16
  
  RTL

; *$57D90 ALTERNATE ENTRY POINT
.hideIndicator

  REP #$20
  
  ; disable the display of the floor indicator.
  LDA.w #$007F : STA $7EC7F0 : STA $7EC830 : STA $7EC7F2 : STA $7EC832
  
  SEP #$30
  
  RTL
}