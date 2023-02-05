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
Sprite_Bouncetowardplayer:
	JSL Sprite_MoveAltitude

	DEC.w $0F80,X : DEC.w $0F80,X

	LDA.w $0F70,X : BPL .aloft

	STZ.w $0F70,X

	LDA.b $08 : STA.w $0F80,X ; set height from 08

	LDA.b $09

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