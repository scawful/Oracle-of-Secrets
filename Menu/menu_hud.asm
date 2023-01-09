; =============================================================================
;  Menu - Headsup Display
; =============================================================================


; ==============================================================================
; Vanilla HUD Hijack 

org $0DFB91
  JSL HUD_Update
  RTS

newIgnoreItemBox:
  JSL HUD_Update_ignoreItemBox
  RTS

org $0DDD21
  JSR newIgnoreItemBox

org $0DF1BC
  JSL HUD_AnimateHeartRefill
  RTS

; ==============================================================================
; Main HUD Update Loop

org $268000
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
  LDA $7EF36D : SEC : SBC #$03
  
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
  LDA MagicTilemap+0, X : STA $7EC76C
  LDA MagicTilemap+2, X : STA $7EC76D
  LDA MagicTilemap+4, X : STA $7EC76E
  LDA MagicTilemap+6, X : STA $7EC76F
  
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

  ; Check if the user has bombs equipped
  LDX $0202 
  LDA $7EF33F, X : AND.w #$00FF
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
  LDX $0202 
  LDA $7EF33F, X : AND.w #$00FF
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
  LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC764
  CMP.w #$247F : BNE .dontBlankKeyIcon

  ; If the key digit is blank, also blank out the key icon.
  STA $7EC724
.dontBlankKeyIcon
  SEP #$30

  RTL
}

; =============================================================================
; *$6DB92-$6DD29 BRANCH LOCATION

HUD_RefillLogic:
{
  ; check the refill magic indicator
  LDA $7EF373

  BEQ .doneWithMagicRefill

  ; Check the current magic power level we have.
  ; Is it full?
  LDA $7EF36E : CMP.b #$80

  BCC .magicNotFull
  
  ; If it is full, freeze it at 128 magic pts.
  ; And stop this refilling nonsense.
  LDA.b #$80 : STA $7EF36E
  LDA.b #$00 : STA $7EF373
  
  BRA .doneWithMagicRefill

.magicNotFull

  LDA $7EF373 : DEC A : STA $7EF373
  LDA $7EF36E : INC A : STA $7EF36E
  
  ; if((frame_counter % 4) != 0) don't refill this frame
  LDA $1A : AND.b #$03 : BNE .doneWithMagicRefill
  
  ; Is this sound channel in use?
  LDA $012E : BNE .doneWithMagicRefill
  
  ; Play the magic refill sound effect
  LDA.b #$2D : STA $012E

.doneWithMagicRefill

  REP #$30
  ; Check current rupees (362) against goal rupees (360)
  ; goal refers to how many we really have and current refers to the
  ; number currently being displayed. When you buy something,
  ; goal rupees are decreased by, say, 100, but it takes a while for the 
  ; current rupees indicator to catch up. When you get a gift of 300
  ; rupees, the goal increases, and current has to catch up in the other direction.
  LDA $7EF362
  
  CMP $7EF360 : BEQ .doneWithRupeesRefill
                BMI .addRupees
  DEC A       : BPL .subtractRupees
  
  LDA.w #$0000 : STA $7EF360
  
  BRA .subtractRupees

.addRupees

  ; If current rupees <= 1000 (decimal)
  INC A : CMP.w #1000 : BCC .subtractRupees
  
  ; Otherwise just store 999 to the rupee amount
  LDA.w #999 : STA $7EF360

.subtractRupees

  STA $7EF362
  
  SEP #$30
  
  LDA $012E : BNE .doneWithRupeesRefill
  
  ; looks like a delay counter of some sort between
  ; invocations of the rupee fill sound effect
  LDA $0CFD : INC $0CFD : AND.b #$07 : BNE .skipRupeeSound
  
  LDA.b #$29 : STA $012E

  BRA .skipRupeeSound

.doneWithRupeesRefill

  SEP #$30
  
  STZ $0CFD

.skipRupeeSound

  LDA $7EF375

  BEQ .doneRefillingBombs

  ; decrease the bomb refill counter
  LDA $7EF375 : DEC A : STA $7EF375

  ; use the bomb upgrade index to know what max number of bombs Link can carry is
  LDA $7EF370 : TAY

  ; if it matches the max, you can't have no more bombs, son. It's the law.
  LDA $7EF343 : CMP $DB48, Y : BEQ .doneRefillingBombs
  
  ; You like bombs? I got lotsa bombs!
  INC A : STA $7EF343

.doneRefillingBombs

  ; check arrow refill counter
  LDA $7EF376
  
  BEQ .doneRefillingArrows
  
  LDA $7EF376 : DEC A : STA $7EF376
  
  ; check arrow upgrade index to see how our max limit on arrows, just like bombs.
  LDA $7EF371 : TAY 
  
  LDA $7EF377 : CMP $DB58, Y
  
  ; I reckon you get no more arrows, pardner.
  BEQ .arrowsAtMax
  
  INC A : STA $7EF377

.arrowsAtMax

  ; see if we even have the bow.
  LDA $7EF340
  
  BEQ .doneRefillingArrows
  
  AND.b #$01 : CMP.b #$01
  
  BNE .doneRefillingArrows
  
  ; changes the icon from a bow without arrows to a bow with arrows.
  LDA $7EF340 : INC A : STA $7EF340
  
  JSL $0DDB7F

.doneRefillingArrows

  ; a frozen Link is an impervious Link, so don't beep.
  LDA $02E4
  
  BNE .doneWithWarningBeep
  
  ; if heart refill is in process, we don't beep
  LDA $7EF372
  
  BNE .doneWithWarningBeep
  
  LDA $7EF36C : LSR #3 : TAX
  
  ; checking current health against capacity health to see
  ; if we need to put on that annoying beeping noise.
  LDA $7EF36D : CMP $DB60, X
  
  BCS .doneWithWarningBeep
  
  LDA $04CA
  
  BNE .decrementBeepTimer
  
  ; beep incessantly when life is low
  LDA $012E
  
  BNE .doneWithWarningBeep
  
  LDA.b #$20 : STA $04CA
  LDA.b #$2B : STA $012E

.decrementBeepTimer

  ; Timer for the low life beep sound
  DEC $04CA

.doneWithWarningBeep

  ; if nonzero, indicates that a heart is being "flipped" over
  ; as in, filling up, currently
  LDA $020A
  
  BNE .waitForHeartFillAnimation
  
  ; If no hearts need to be filled, branch
  LDA $7EF372
  
  BEQ .doneRefillingHearts
  
  ; check if actual health matches capacity health
  LDA $7EF36D : CMP $7EF36C
  
  BCC .notAtFullHealth
  
  ; just set health to full in the event it overflowed past 0xA0 (20 hearts)
  LDA $7EF36C : STA $7EF36D
  
  ; done refilling health so deactivate the health refill variable
  LDA.b #$00 : STA $7EF372
  
  BRA .doneRefillingHearts

.notAtFullHealth

  ; refill health by one heart
  LDA $7EF36D : CLC : ADC.b #$08 : STA $7EF36D
  
  LDA $012F
  
  BNE .soundChannelInUse
  
  ; play heart refill sound effect
  LDA.b #$0D : STA $012F

.soundChannelInUse

  ; repeat the same logic from earlier, checking if health's at max and setting it to max
  ; if it overflowed
  LDA $7EF36D : CMP $7EF36C
  
  BCC .healthDidntOverflow
  
  LDA $7EF36C : STA $7EF36D

.healthDidntOverflow

  ; subtract a heart from the refill variable
  LDA $7EF372 : SEC : SBC.b #$08 : STA $7EF372
  
  ; activate heart refill animation
  ; (which will cause a small delay for the next heart if we still need to fill some up.)
  INC $020A
  
  LDA.b #$07 : STA $0208

.waitForHeartFillAnimation

  REP #$30
  
  LDA.w #$FFFF : STA $0E
  
  JSL HUD_Update_ignoreHealth
  
  JSL HUD_AnimateHeartRefill
  
  SEP #$30
  
  INC $16
  
  PLB
  
  RTL

.doneRefillingHearts

  REP #$30
  
  LDA.w #$FFFF : STA $0E
  
  JSL HUD_Update_ignoreItemBox
  
  SEP #$30
  
  INC $16
  
  PLB
  
  RTL
} 

; =============================================================================
; *$6F14F-$6F1B2 LOCAL

HUD_AnimateHeartRefill:
{
  SEP #$30
  
  ; $00[3] = $7EC768 (wram address of first row of hearts in tilemap buffer)
  LDA.b #$44 : STA $00
  LDA.b #$C7 : STA $01
  LDA.b #$7E : STA $02
  
  DEC $0208 : BNE .return
  
  REP #$30
  
  ; Y = ( ( ( (current_health & 0x00F8) - 1) / 8 ) * 2)
  LDA $7EF36D : AND.w #$00F8 : DEC A : LSR #3 : ASL A : TAY : CMP.w #$0014
  
  BCC .halfHealthOrLess
  
  SBC.w #$0014 : TAY
  
  ; $00[3] = $7EC7A8 (wram address of second row of hearts)
  LDA $00 : CLC : ADC.w #$0040 : STA $00

.halfHealthOrLess

  SEP #$30
  
  LDX $0209 : LDA $0DFA11, X : STA $0208
  
  TXA : ASL A : TAX
  
  LDA $0DFA09, X : STA [$00], Y
  
  INY : LDA $0DFA0A, X : STA [$00], Y
  
  LDA $0209 : INC A : AND.b #$03 : STA $0209
  
  BNE .return
  
  SEP #$30
  
  JSL $0DFA70
  
  STZ $020A

.return

  CLC
  
  RTS
}

; ============================================================================ 
; *$6FAFD-$6FB90 LOCAL

HudItems:
  dw BowsGFX
  dw BoomsGFX
  dw HookGFX
  dw BombsGFX
  dw DekuMaskGFX
  dw BottlesGFX
  dw Fire_rodGFX
  dw Ice_rodGFX
  dw LampGFX
  dw HammerGFX
  dw GoronMaskGFX
  dw BottlesGFX
  dw SomariaGFX
  dw ByrnaGFX
  dw BookGFX
  dw JumpFeatherGFX
  dw BunnyHoodGFX 
  dw BottlesGFX
  dw OcarinaGFX
  dw MirrorGFX
  dw ShovelGFX
  dw PowderGFX
  dw StoneMaskGFX
  dw BottlesGFX

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
  ; I used DMA to speed it up in my custom code
  LDX.w #$0000

.nextHeart
  LDA $00 : CMP.w #$0008 : BCC .lessThanOneHeart
  ; Notice no SEC was needed since carry is assumedly set.
  SBC.w #$0008 : STA $00
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
  LDA $07 : CLC : ADC #$0040 : STA $07

.noLineChange
  LDA [$0A], Y : TXY : STA [$07], Y
  RTS
}

; =============================================================================

MagicTilemap:
  dw $3CF5, $3CF5, $3CF5, $3CF5
  dw $3CF5, $3CF5, $3CF5, $3C5F
  dw $3CF5, $3CF5, $3CF5, $3C4C
  dw $3CF5, $3CF5, $3CF5, $3C4D
  dw $3CF5, $3CF5, $3CF5, $3C4E
  dw $3CF5, $3CF5, $3C5F, $3C5E
  dw $3CF5, $3CF5, $3C4C, $3C5E
  dw $3CF5, $3CF5, $3C4D, $3C5E
  dw $3CF5, $3CF5, $3C4E, $3C5E
  dw $3CF5, $3C5F, $3C5E, $3C5E
  dw $3CF5, $3C4C, $3C5E, $3C5E
  dw $3CF5, $3C4D, $3C5E, $3C5E
  dw $3CF5, $3C4E, $3C5E, $3C5E
  dw $3C5F, $3C5E, $3C5E, $3C5E
  dw $3C4C, $3C5E, $3C5E, $3C5E
  dw $3C4D, $3C5E, $3C5E, $3C5E
  dw $3C4E, $3C5E, $3C5E, $3C5E  

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
  dw $207F, $207F, $207F, $207F, $207F, $207F
  
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

; $57CF6 DATA
org $0AFCF6
FloorIndicatorNumberLow:
{
  dw $2518, $2519, $A509, $251A, $251B, $251C, $2518, $A51D
  dw $E50C, $A50E, $007F
}

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