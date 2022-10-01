org $0DFB91
JSL NewMenuUpdate
RTS

newIgnoreItemBox:
JSL NewMenuUpdate_ignoreItemBox
RTS

org $0DDD21
JSR newIgnoreItemBox

org $268000
NewMenuUpdate:
{
  JSR Hud_UpdateItemBox

; *$6FB94 ALTERNATE ENTRY POINT
.ignoreItemBox

    SEP #$30
    
    ; the hook for optimization was placed here...
    ; need to draw partial heart still though. update: optimization complete with great results
    LDA.b #$FD : STA $0A
    LDA.b #$F9 : STA $0B
    LDA.b #$0D : STA $0C
    
    LDA.b #$68 : STA $07
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
    
    LDA.b #$68 : STA $07
    LDA.b #$C7 : STA $08
    LDA.b #$7E : STA $09
    
    ; Branch if at full health
    LDA $7EF36C : CMP $7EF36D : BEQ .healthUpdated
    
    ; Seems absurd to have a branch of zero bytes, right?
    SBC #$04 : CMP $7EF36D : BCS .healthUpdated

.healthUpdated

    ; A = actual health + 0x03;
    LDA $7EF36D : ADC.b #$03
    
    REP #$30
    
    AND.w #$00FC : STA $00 : STA $04
    
    LDA $7EF36C : AND.w #$00FF : STA $02
    
    ; this time we're filling in the full and partially filled hearts (actual health)
    JSR HUD_UpdateHearts

; *$6FC09 ALTERNATE ENTRY POINT ; reentry hook
.ignoreHealth

    REP #$30
    
    ; Magic amount indicator (normal, 1/2, or 1/4)
    LDA $7EF37B : AND.w #$00FF : CMP.w #$0001 : BCC .normalMagicMeter
    
    ; draws a 1/2 magic meter (note, we could add in the 1/4 magic meter here if 
    ; we really cared about that >_>
    LDA.w #$28F7 : STA $7EC704
    LDA.w #$2851 : STA $7EC706
    LDA.w #$28FA : STA $7EC708

.normalMagicMeter

    ; check how much magic power the player has at the moment (ranges from 0 to 0x7F)
    ; X = ((MP & 0xFF)) + 7) & 0xFFF8)
    LDA $7EF36E : AND.w #$00FF : ADC.w #$0007 : AND.w #$FFF8 : TAX
    
    ; these four writes draw the magic power bar based on how much MP you have    
    LDA MagicTilemap+0, X : STA $7EC746
    LDA MagicTilemap+2, X : STA $7EC786
    LDA MagicTilemap+4, X : STA $7EC7C6
    LDA MagicTilemap+6, X : STA $7EC806
    
    ; Load how many rupees the player has
    LDA $7EF362
    
    JSR HexToDecimal
    
    REP #$30
    
    ; The tile index for the first rupee digit
    LDA $03 : AND.w #$00FF : ORA.w #$2400 : STA $7EC750
    
    ; The tile index for the second rupee digit
    LDA $04 : AND.w #$00FF : ORA.w #$2400 : STA $7EC752
    
    ; The tile index for the third rupee digit
    LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC754
    
    ; Number of bombs Link has.
    LDA $7EF343 : AND.w #$00FF
    
    JSR HexToDecimal
    
    REP #$30
    
    ; The tile index for the first bomb digit
    LDA $04 : AND.w #$00FF : ORA.w #$2400 : STA $7EC758
    
    ; The tile index for the second bomb digit
    LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC75A
    
    ; Number of Arrows Link has.
    LDA $7EF377 : AND.w #$00FF
    
        ; converts hex to up to 3 decimal digits
        JSR HexToDecimal
        
        REP #$30
        
        ; The tile index for the first arrow digit    
        LDA $04 : AND.w #$00FF : ORA.w #$2400 : STA $7EC75E
        
        ; The tile index for the second arrow digit   
        LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA $7EC760
        
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

; ==============================================================================
; Update Items 

HudItems:
  dw BowsGFX
  dw BoomsGFX
  dw HookGFX
  dw BombsGFX
  dw DekuMaskGFX
  dw BottlesGFX
  dw HammerGFX
  dw LampGFX
  dw Fire_rodGFX
  dw Ice_rodGFX
  dw GoronMaskGFX
  dw BottlesGFX
  dw ShovelGFX
  dw JumpFeatherGFX
  dw SomariaGFX
  dw ByrnaGFX
  dw BunnyHoodGFX 
  dw BottlesGFX
  dw PowderGFX
  dw BookGFX
  dw OcarinaGFX
  dw MirrorGFX
  dw StoneMaskGFX
  dw BottlesGFX

Hud_UpdateItemBox:
{
  REP #$30
  LDA.w $0202
  ASL : TAX
  LDY.w HudItems-2, X

  LDA.w $0000,Y : STA.l $7EC778
  LDA.w $0002,Y : STA.l $7EC77A
  LDA.w $0004,Y : STA.l $7EC7B8
  LDA.w $0006,Y : STA.l $7EC7BA
  SEP #$30

  RTS
}

Vanilla_UpdateItemBox:
{
    SEP #$30
    
    ; Dost thou haveth the the bow?
    LDA $7EF340 : BEQ .havethNoBow
    
    ; Dost thou haveth the silver arrows?
    ; (okay I'll stop soon)
    CMP.b #$03 : BCC .havethNoSilverArrows 
    
    ; Draw the arrow guage icon as silver rather than normal wood arrows.
    LDA.b #$86 : STA $7EC71E
    LDA.b #$24 : STA $7EC71F
    LDA.b #$87 : STA $7EC720
    LDA.b #$24 : STA $7EC721
    
    LDX.b #$04
    
    ; check how many arrows the player has
    LDA $7EF377 : BNE .drawBowItemIcon
    
    LDX.b #$03
    
    BRA .drawBowItemIcon

.havethNoSilverArrows

    LDX.b #$02
    
    LDA $7EF377 : BNE .drawBowItemIcon
    
    LDX.b #$01

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
    LDA ($04), Y : STA $7EC74A : INY #2
    LDA ($04), Y : STA $7EC74C : INY #2
    LDA ($04), Y : STA $7EC78A : INY #2
    LDA ($04), Y : STA $7EC78C : INY #2

.noEquippedItem

    RTS
}

; ==============================================================================

HUD_UpdateHearts:
{
    ; Draws hearts in a painfully slow loop
    ; I used DMA to speed it up in my custom code
    ; (but still needs fixing to work on 1/1/1 hardware)
    
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
    
    LDA $07 : ADC.w #$0040 : STA $07

.noLineChange

    LDA [$0A], Y : TXY : STA [$07], Y
    
    RTS
}

; ==============================================================================

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

; ==============================================================================

HexToDecimal:
{
    ; This apparently is a hex to decimal converter for use with displaying numbers
    ; It's obviously slower with larger numbers... should find a way to speed it up. (already done)
    
    REP #$30
    
    STZ $0003
    
    ; The objects mentioned could be rupees, arrows, bombs, or keys.
    LDX.w #$0000
    LDY.w #$0002

.nextDigit

    ; If number of objects left < 100, 10
    CMP $F9F9, Y : BCC .nextLowest10sPlace
    
    ; Otherwise take off another 100 objects from the total and increment $03
    ; $6F9F9, Y THAT IS, 100, 10
    SBC $F9F9, Y
    INC $03, X
    
    BRA .nextDigit

.nextLowest10sPlace

    INX : DEY #2
    
    ; Move on to next digit (to the right)
    BPL .nextDigit
    
    ; Whatever is left is obviously less than 10, so store the digit at $05.
    STA $05
    
    SEP #$30
    
    ; Go through at most three digits.
    LDX.b #$02

; Repeat for all three digits.
.setNextDigitTile

    ; Load each digit's computed value
    LDA $03, X : CMP.b #$7F
    
    BEQ .blankDigit

    ; #$0-9 -> #$90-#$99
    ORA.b #$90

.blankDigit

    ; A blank digit.
    STA $03, X
    
    DEX : BPL .setNextDigitTile
    
    RTS
} 