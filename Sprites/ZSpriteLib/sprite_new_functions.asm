;=================================================================
;Long function, return Carry Set if Active
;=================================================================
Sprite_CheckActive:
{
        ; Deactivates the sprite in certain situations

        LDA $0DD0, X : CMP.b #$09 : BNE .inactive
        
        LDA $0FC1 : BNE .inactive
        
        LDA $11 : BNE .inactive
        
        LDA $0CAA, X : BMI .active
        
        LDA $0F00, X : BEQ .active
    
    .inactive
        CLC
        RTL
    
    .active
        SEC
        RTL
}


; make the sprite move X axis
;===================================================================================================
Sprite_MoveHoriz:
	LDA.w $0D50,X : BEQ .no_velocity
	ASL : ASL : ASL : ASL
	CLC : ADC.w $0D70,X : STA.w $0D70,X

	LDY.b #$00
	LDA.w $0D50,X 
	PHP : LSR : LSR : LSR : LSR : PLP
	BPL ++

	ORA.b #$F0
	DEY

++	ADC.w $0D10,X : STA.w $0D10,X
	TYA : ADC.w $0D30,X : STA.w $0D30,X

.no_velocity
	RTL

;===================================================================================================
; make the sprite move both directions (also height)
;===================================================================================================
Sprite_MoveXyz:
	JSL Sprite_MoveAltitude
Sprite_Move:
	JSL Sprite_MoveHoriz
	; no RTL, just continue into Sprite_MoveVert

;===================================================================================================
; make the sprite move Y axis
;===================================================================================================
Sprite_MoveVert:
	LDA.w $0D40,X : BEQ .no_velocity
	ASL : ASL : ASL : ASL
	CLC : ADC.w $0D60,X : STA.w $0D60,X

	LDY.b #$00
	LDA.w $0D40,X
	PHP : LSR : LSR : LSR : LSR : PLP
	BPL ++

	ORA.b #$F0
	DEY

++	ADC.w $0D00,X : STA.w $0D00,X
	TYA : ADC.w $0D20,X : STA.w $0D20,X

.no_velocity
	RTL

;===================================================================================================
; make the sprite move Z axis (height)
;===================================================================================================
Sprite_MoveZ:
Sprite_MoveAltitude:
	LDA.w $0F80,X : ASL : ASL : ASL : ASL
	CLC : ADC.w $0F90,X : STA.w $0F90,X

	LDA.w $0F80,X : PHP
	LSR : LSR : LSR : LSR
	PLP : BPL .positive

	ORA.b #$F0

.positive
	ADC.w $0F70,X : STA.w $0F70,X

	RTL


;===================================================================================================
; make the sprite bounce toward player (like vitreous)
; Movement, Collision are handled by this function (height:20 = vitreous)
; $09 = speed, $08 = max height
;===================================================================================================
Sprite_BounceTowardPlayer:
	JSL Sprite_MoveAltitude

	DEC.w $0F80,X : DEC.w $0F80,X

	LDA.w $0F70,X : BPL .aloft

	STZ.w $0F70,X

	LDA.b $08 : STA.w $0F80,X ; set height from 08

	;LDA.b $09
  LDA.b #$20

	JSL Sprite_ApplySpeedTowardsPlayer

	LDA.b #$21 : JSL Sound_SetSfx2PanLong

.aloft
	LDA.w $0F70,X : BEQ .dontmove

	JSL Sprite_Move

.dontmove
	RTL

Sprite_BounceFromTileCollision:
	JSL Sprite_CheckTileCollision : AND.b #$03 : BEQ ++
	LDA.w $0D50,X : EOR.b #$FF : INC : STA.w $0D50,X
	INC.w $0ED0,X

++	LDA.w $0E70,X : AND.b #$0C : BEQ ++
	LDA.w $0D40,X : EOR.b #$FF : INC : STA.w $0D40,X
	INC.w $0ED0,X

++	RTL

; ==============================================================================

MovieEffectTimer = $7EF500 ;0x01

;these need to be the same as the next set
;used to do the HDMA
MovieEffectArray = $F900 ;0x0F
MovieEffectBank = $7E

;used to set the actual values
MovieEffect0 = $7EF900 ;0x01
MovieEffect1 = $7EF901 ;0x01
MovieEffect2 = $7EF902 ;0x01
MovieEffect3 = $7EF903 ;0x01
MovieEffect4 = $7EF904 ;0x01
MovieEffect5 = $7EF905 ;0x01
MovieEffect6 = $7EF906 ;0x01
MovieEffect7 = $7EF907 ;0x01
MovieEffect8 = $7EF908 ;0x01
MovieEffect9 = $7EF909 ;0x01
MovieEffectA = $7EF90A ;0x01
MovieEffectB = $7EF90B ;0x01
MovieEffectC = $7EF90C ;0x01
MovieEffectD = $7EF90D ;0x01
MovieEffectE = $7EF90E ;0x01

SetupMovieEffect:
{
    ;setup HDMA RAM
    ;Top Dark Row
    LDA.b #$01 : STA.l MovieEffect0
    LDA.b #$00 : STA.l MovieEffect1

    ;Top Dark Row Buffer
    LDA.b #$1F : STA.l MovieEffect2
    LDA.b #$0F : STA.l MovieEffect3

    ;Middle Unaffected Area
    LDA.b #$50 : STA.l MovieEffect4
    LDA.b #$0F : STA.l MovieEffect5
    LDA.b #$50 : STA.l MovieEffect6
    LDA.b #$0F : STA.l MovieEffect7

    ;Bottom Drak Row Buffer
    LDA.b #$1F : STA.l MovieEffect8
    LDA.b #$0F : STA.l MovieEffect9

    ;Bottom Dark Row
    LDA.b #$01 : STA.l MovieEffectA
    LDA.b #$00 : STA.l MovieEffectB

    ;Below screen 
    LDA.b #$20 : STA.l MovieEffectC
    LDA.b #$0F : STA.l MovieEffectD

    ;End
    LDA.b #$00 : STA.l MovieEffectE

    ;start timer
    LDA.b #$01 : STA.l MovieEffectTimer

    RTS
}

; ; ==============================================================================

MovieEffect:
{
    REP #$20
    LDX #$00 : STX $4350 ;Set the transfer mode into 1 byte to 1 register
    LDX #$00 : STX $4351 ;Set register to 00 ($21 00)

    LDA.w #MovieEffectArray : STA $4352 ;set address of the hdma table
    LDX.b #MovieEffectBank : STX $4354 ;set the bank of HDMA table

    SEP #$20
    LDA.b #$20 : STA $9B ;Do the HDMA instead of $420C

    ; LDA $9B : ORA #$20 : STA $9B 
    ; LDA.b #$02 : STA $13 ;controls the brightness of the screen

    RTS

    HDMATable: ;values cannot go above 80 or it will read as continuous mode
    db $20, $00 ;for $20 line set screen brightness to 0
    db $50, $0F ;for $A0 line set screen brightness to 15 full
    db $50, $0F ;for $A0 line set screen brightness to 15 full
    db $3F, $00 ;for $20 line set screen brightness to 0
    db $00 ;end the HDMA
}