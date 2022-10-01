; =============================================================================
;  headsup display  

org $0DFB91
  JSL Hud_Update
  RTS

newIgnoreItemBox:
  JSL Hud_Update_ignoreItemBox
  RTS

org $0DDD21
  JSR newIgnoreItemBox

; =============================================================================
org $268000
Hud_Update:
{
  JSR Hud_Hud_UpdateItemBox

.ignoreItemBox ; ALTERNATE ENTRY POINT

    SEP #$30
    
    ; need to draw partial heart still though. 
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
    LDA.w #$28F7 : STA $7EC704
    LDA.w #$2851 : STA $7EC706
    LDA.w #$28FA : STA $7EC708

.normalMagicMeter

    ; check player magic (ranges from 0 to 0x7F)
    ; X = ((MP & 0xFF)) + 7) & 0xFFF8)
    LDA $7EF36E : AND.w #$00FF : CLC : ADC #$0007 : AND.w #$FFF8 : TAX
    
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

; =============================================================================

namespace Hud
  incsrc "menu_gfx_table.asm"

HudItems:
  dw BowsGFX : dw BoomsGFX : dw HookGFX
  dw BombsGFX : dw DekuMaskGFX : dw BottlesGFX
  dw HammerGFX : dw LampGFX : dw Fire_rodGFX
  dw Ice_rodGFX : dw GoronMaskGFX : dw BottlesGFX
  dw ShovelGFX : dw JumpFeatherGFX : dw SomariaGFX
  dw ByrnaGFX : dw BunnyHoodGFX  : dw BottlesGFX
  dw PowderGFX : dw BookGFX : dw OcarinaGFX 
  dw MirrorGFX : dw StoneMaskGFX : dw BottlesGFX

Hud_UpdateItemBox:
{
  REP #$30
  LDA.w $0202
  ASL : TAX
  LDY.w HudItems-2, X

  LDA.w $0000,Y : STA.l $7EC778-6
  LDA.w $0002,Y : STA.l $7EC77A-6
  LDA.w $0004,Y : STA.l $7EC7B8-6
  LDA.w $0006,Y : STA.l $7EC7BA-6
  SEP #$30

  RTS
}

namespace off

; =============================================================================

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
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $346C, $346D, $346E, $346F ; item frame top part 
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $34DE, $207F, $207F, $34DF
                                ; item frame left part 
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $34DE, $207F, $207F, $34DF
                                ; item frame right part 
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
                                ; item frame bottom part
  dw $207F, $207F, $207F, $207F, $347C, $347D, $347E, $341D
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F, $207F, $207F, $207F, $207F, $207F, $207F, $207F
  dw $207F
}
