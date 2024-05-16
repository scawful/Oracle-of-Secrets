;==========================================================
;Long function, return Carry Set if Active
;==========================================================

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
;==========================================================
Sprite_MoveHoriz:
{
    LDA.w $0D50, X : BEQ .no_velocity
    ASL   : ASL : ASL : ASL
    CLC : ADC.w $0D70,X : STA.w $0D70,X

    LDY.b #$00
    LDA.w $0D50, X
    PHP   : LSR : LSR : LSR : LSR : PLP
    BPL   ++

    ORA.b #$F0
    DEY

  ++	ADC.w $0D10,X : STA.w $0D10,X
    TYA : ADC.w $0D30,X : STA.w $0D30,X

  .no_velocity
    RTL
}

;==========================================================

; make the sprite move both directions (also height)
;==========================================================

Sprite_MoveXyz:
	JSL Sprite_MoveAltitude
Sprite_Move:
	JSL Sprite_MoveHoriz
	; no RTL, just continue into Sprite_MoveVert

;==========================================================
; make the sprite move Y axis
;==========================================================

Sprite_MoveVert:
{
    LDA.w $0D40, X : BEQ .no_velocity
    ASL   : ASL : ASL : ASL
    CLC : ADC.w $0D60,X : STA.w $0D60,X

    LDY.b #$00
    LDA.w $0D40, X
    PHP   : LSR : LSR : LSR : LSR : PLP
    BPL   ++

    ORA.b #$F0
    DEY

  ++	ADC.w $0D00,X : STA.w $0D00,X
    TYA : ADC.w $0D20,X : STA.w $0D20,X

  .no_velocity
    RTL
}

;==========================================================
; make the sprite move Z axis (height)
;==========================================================

Sprite_MoveZ:
Sprite_MoveAltitude:
{
    LDA.w $0F80, X : ASL : ASL : ASL : ASL
    CLC : ADC.w $0F90,X : STA.w $0F90,X

    LDA.w $0F80, X : PHP
    LSR   : LSR : LSR : LSR
    PLP   : BPL .positive

    ORA.b #$F0

  .positive
    ADC.w $0F70,X : STA.w $0F70,X

    RTL
}


;==========================================================
; make the sprite bounce toward player (like vitreous)
; Movement, Collision are handled by this function (height:20 = vitreous)
; $09 = speed, $08 = max height
;==========================================================

Sprite_BounceTowardPlayer:
{
	JSL Sprite_MoveAltitude

	DEC.w $0F80,X : DEC.w $0F80,X

	LDA.w $0F70, X : BPL .aloft

	STZ.w $0F70, X

	LDA.b $08 : STA.w $0F80, X ; set height from 08

	;LDA.b $09
  LDA.b #$20

	JSL Sprite_ApplySpeedTowardsPlayer

	LDA.b #$21 : JSL Sound_SetSfx2PanLong

.aloft
	LDA.w $0F70, X : BEQ .dontmove

	JSL Sprite_Move

.dontmove
	RTL
}

; A = Speed
; TODO: Use Y index for height
Sprite_FloatTowardPlayer:
{
    JSL Sprite_ApplySpeedTowardsPlayer

    ; Update horizontal position
    JSL Sprite_MoveHoriz

    ; Update vertical position
    JSL Sprite_MoveVert

    ; Check for tile collisions and adjust if necessary
    JSL Sprite_CheckTileCollision

    ; Maintain altitude (float effect)
    LDA #$10 : STA.w SprHeight, X
    JSL Sprite_MoveAltitude

    RTL
}

Sprite_BounceFromTileCollision:
{
	JSL   Sprite_CheckTileCollision : AND.b #$03 : BEQ ++
	LDA.w $0D50,X : EOR.b #$FF : INC : STA.w $0D50,X
	INC.w $0ED0, X

++ LDA.w $0E70, X : AND.b #$0C : BEQ ++
	LDA.w $0D40,X : EOR.b #$FF : INC : STA.w $0D40,X
	INC.w $0ED0, X

++ RTL
}

; =========================================================
DragYL = $0B7C
DragYH = $0B7D

; Parameters: Y index contains direction to drag player
DragPlayer:
{
    LDA.w .drag_x_low,  Y : CLC : ADC.w DragYL : STA.w DragYL
    LDA.w .drag_x_high, Y : ADC.w DragYH : STA DragYH
    
    LDA.w .drag_y_low,  Y : CLC : ADC.w $0B7E : STA.w $0B7E
    LDA.w .drag_y_high, Y : ADC.w $0B7F : STA.w $0B7F

  .SomariaPlatform_DragLink
    REP #$20
    
    LDA $0FD8 : SEC : SBC.w #$0002
    CMP $22 : BEQ .x_done : BPL .x_too_low
    
    DEC $0B7C
    
    BRA .x_done

  .x_too_low

    INC $0B7C

  .x_done
    ; Changing the modifier adjusts links position in the cart 
    LDA $0FDA : SEC : SBC.w #$0008
    CMP $20 : BEQ .y_done : BPL .y_too_low
    
    DEC $0B7E
    
    BRA .y_done

  .y_too_low

    INC $0B7E

  .y_done

    SEP #$30
        
    RTL

  .drag_x_high
    db 0,   0,  -1,   0

  .drag_x_low
    db 0,   0,  -1,   1

  .drag_y_low
    db -1,   1,   0,   0

  .drag_y_high
    db -1,   0,   0,   0

  ; Alternate drag values provided by Zarby
  ; .drag_x_high
  ; db 0,   0,  -1,   0,  -1
  ; .drag_x_low
  ; db 0,   0,  -1,   1,  -1,   1,   1
  ; .drag_y_low
  ; db -1,   1,   0,   0,  -1,   1,  -1,   1
  ; .drag_y_high
  ; db -1,   0,   0,   0,  -1,   0,  -1,   0
}

; =========================================================

Intro_Dungeon_Main:
{
    ;test to see if we are at a place where a guardian is present
    LDA $0E20 : CMP.b #$92 : BNE .notGuardian
        LDA $0E30 : BEQ .notGuardian

            LDA $1C : AND.b #$FE : STA $1C ;turn off BG2 (Body)

            ;free ram used to check if the sprite ran this frame, if 0, it didn't run
            LDA.b SpriteRanCheck : BEQ .didNotRun
                LDA $1C : ORA.b #$01 : STA $1C ;turn on BG2 (Body)

            .didNotRun
            
            STZ.b SpriteRanCheck

    .notGuardian

    REP #$21 : LDA.w DungeonMainCheck : BNE .intro ;<- load that free ram you are using if it's not zero then we're doing intro thing
        LDA $E2 : RTL ;return to normal intro

    .intro

    PLA ;Pop 2byte from stack
    ;skip all the BGs codes

    SEP #$20
    PLA ;Pop 1 byte from the stack
    JSL $07F0AC ; $3F0AC IN ROM. Handle the sprites of pushed blocks.
    JSL $068328 ;Sprite_Main
    JSL $0DA18E ;PlayerOam_Main
    JSL $0DDB75 ;HUD.RefillLogicLong

    JML $0AFD0C ;FloorIndicator ; $57D0C IN ROM. Handles HUD floor indicator
}

;uses $00 as the Y coordinate and $02 as the X
MoveCamera:
{
  REP #$20

  ;move the camera up or down until a point is reached
  LDA $E8 : CMP $00 : BEQ .dontMoveY ;if equals that point, dont move y

  BCS .CameraBelowPointY
  ;CameraAbovePoint
            ADC.w #$0001 : STA $E8 : STA $E6 : STA $0122 : STA $0124 ;move the camera down by 1
      BRA .dontMoveY

.CameraBelowPointY
      SEC : SBC.w #$0001 : STA $E8 : STA $E6 : STA $0122 : STA $0124 ;move the camera up by 1

.dontMoveY

  ;move the camera right or left until a point is reached
  LDA $E2 : CMP.w $02 : BEQ .dontMoveX ;if equals that point, dont move x

  BCS .CameraBelowPointX ;left
  ;CameraAbovePoint ;right
            ADC.w #$0001 : STA $E2 : STA $E0 : STA $011E : STA $0120 ;move the camera right by 1
      BRA .dontMoveX
  
.CameraBelowPointX
      SEC : SBC.w #$0001 : STA $E2 : STA $E0 : STA $011E : STA $0120 ;move the camera left by 1

.dontMoveX

  ;if link is outside of a certain range of the camera, make him dissapear so he doesnt appear on the other side
  LDA $20 : SEC : SBC $E8 : CMP.w #$00E0 : BCS .MakeLinkInvisible
  LDA $22 : SEC : SBC $E2 : CMP.w #$00E0 : BCS .MakeLinkInvisible

  SEP   #$20
  LDA.b #$00 : STA $4B ;make link visible
  RTS

.MakeLinkInvisible

  SEP   #$20
  LDA.b #$0C : STA $4B ;make link invisible

  RTS
}

MovieEffectTimer = $7EF500 ;0x01

;these need to be the same as the next set
;used to do the HDMA
MovieEffectArray = $F900   ;0x0F
MovieEffectBank  = $7E

;used to set the actual values
MovieEffect0     = $7EF900 ;0x01
MovieEffect1     = $7EF901 ;0x01
MovieEffect2     = $7EF902 ;0x01
MovieEffect3     = $7EF903 ;0x01
MovieEffect4     = $7EF904 ;0x01
MovieEffect5     = $7EF905 ;0x01
MovieEffect6     = $7EF906 ;0x01
MovieEffect7     = $7EF907 ;0x01
MovieEffect8     = $7EF908 ;0x01
MovieEffect9     = $7EF909 ;0x01
MovieEffectA     = $7EF90A ;0x01
MovieEffectB     = $7EF90B ;0x01
MovieEffectC     = $7EF90C ;0x01
MovieEffectD     = $7EF90D ;0x01
MovieEffectE     = $7EF90E ;0x01

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

; =========================================================

MovieEffect:
{
    REP #$20
    LDX #$00 : STX $4350 ;Set the transfer mode into 1 byte to 1 register
    LDX #$00 : STX $4351 ;Set register to 00 ($21 00)

    LDA.w #MovieEffectArray : STA $4352 ;set address of the hdma table
    LDX.b #MovieEffectBank : STX $4354  ;set the bank of HDMA table

    SEP   #$20
    LDA.b #$20 : STA $9B ;Do the HDMA instead of $420C

    ; LDA $9B : ORA #$20 : STA $9B 
    ; LDA.b #$02 : STA $13 ;controls the brightness of the screen

    RTS

    HDMATable: ;values cannot go above 80 or it will read as continuous mode
    db $20, $00 ;for $20 line set screen brightness to 0
    db $50, $0F ;for $A0 line set screen brightness to 15 full
    db $50, $0F ;for $A0 line set screen brightness to 15 full
    db $3F, $00 ;for $20 line set screen brightness to 0
    db $00      ;end the HDMA
}


Link_CheckNewY_ButtonPress_Long:
{
    BIT.b $3A : BVS .fail
    LDA.b $46 : BNE .fail
    LDA.b $F4 : AND.b #$40 : BEQ .fail
    TSB.b $3A
    SEC
    RTL
  .fail
    CLC
    RTL
}

Link_SetupHitBox:
{
  LDA.b #$08 : STA $02 : STA $03
  
  LDA $22 : CLC : ADC.b #$04 : STA $00
  LDA $23 : ADC.b #$00 : STA $08
  
  LDA $20 : ADC.b #$08 : STA $01
  LDA $21 : ADC.b #$00 : STA $09
  
  RTS
}


Sprite_SetupHitBox:
#_06F7EF: LDA.w $0F70,          X
#_06F7F2: BMI .too_high

#_06F7F4: PHY

#_06F7F5: LDA.w $0F60,          X
#_06F7F8: AND.b #$1F
#_06F7FA: TAY

#_06F7FB: LDA.w $0D10,          X
#_06F7FE: CLC
#_06F7FF: ADC.w .offset_x_low,  Y
#_06F802: STA.b $04

#_06F804: LDA.w $0D30,          X
#_06F807: ADC.w .offset_x_high, Y
#_06F80A: STA.b $0A

#_06F80C: LDA.w $0D00,          X
#_06F80F: CLC
#_06F810: ADC.w .offset_y_low,  Y

#_06F813: PHP
#_06F814: SEC
#_06F815: SBC.w $0F70,          X
#_06F818: STA.b $05

#_06F81A: LDA.w $0D20,          X
#_06F81D: SBC.b #$00

#_06F81F: PLP
#_06F820: ADC.w .offset_y_high, Y
#_06F823: STA.b $0B

#_06F825: LDA.w .width,         Y
#_06F828: STA.b $06

#_06F82A: LDA.w .height,        Y
#_06F82D: STA.b $07

#_06F82F: PLY

#_06F830: RTS

; ---------------------------------------------------------

.too_high
#_06F831: LDA.b #$80
#_06F833: STA.b $0A

#_06F835: RTS

.offset_x_low
#_06F72F: db 2   ; 0x00
#_06F730: db 3   ; 0x01
#_06F731: db 0   ; 0x02
#_06F732: db -3  ; 0x03
#_06F733: db -6  ; 0x04
#_06F734: db 0   ; 0x05
#_06F735: db 2   ; 0x06
#_06F736: db -8  ; 0x07
#_06F737: db 0   ; 0x08
#_06F738: db -4  ; 0x09
#_06F739: db -8  ; 0x0A
#_06F73A: db 0   ; 0x0B
#_06F73B: db -8  ; 0x0C
#_06F73C: db -16 ; 0x0D
#_06F73D: db 2   ; 0x0E
#_06F73E: db 2   ; 0x0F

#_06F73F: db 2   ; 0x10
#_06F740: db 2   ; 0x11
#_06F741: db 2   ; 0x12
#_06F742: db -8  ; 0x13
#_06F743: db 2   ; 0x14
#_06F744: db 2   ; 0x15
#_06F745: db -16 ; 0x16
#_06F746: db -8  ; 0x17
#_06F747: db -12 ; 0x18
#_06F748: db 4   ; 0x19
#_06F749: db -4  ; 0x1A
#_06F74A: db -12 ; 0x1B
#_06F74B: db 5   ; 0x1C
#_06F74C: db -32 ; 0x1D
#_06F74D: db -2  ; 0x1E
#_06F74E: db 4   ; 0x1F

; ---------------------------------------------------------

.offset_x_high
#_06F74F: db 0   ; 0x00
#_06F750: db 0   ; 0x01
#_06F751: db 0   ; 0x02
#_06F752: db -1  ; 0x03
#_06F753: db -1  ; 0x04
#_06F754: db 0   ; 0x05
#_06F755: db 0   ; 0x06
#_06F756: db -1  ; 0x07
#_06F757: db 0   ; 0x08
#_06F758: db -1  ; 0x09
#_06F759: db -1  ; 0x0A
#_06F75A: db 0   ; 0x0B
#_06F75B: db -1  ; 0x0C
#_06F75C: db -1  ; 0x0D
#_06F75D: db 0   ; 0x0E
#_06F75E: db 0   ; 0x0F

#_06F75F: db 0   ; 0x10
#_06F760: db 0   ; 0x11
#_06F761: db 0   ; 0x12
#_06F762: db -1  ; 0x13
#_06F763: db 0   ; 0x14
#_06F764: db 0   ; 0x15
#_06F765: db -1  ; 0x16
#_06F766: db -1  ; 0x17
#_06F767: db -1  ; 0x18
#_06F768: db 0   ; 0x19
#_06F769: db -1  ; 0x1A
#_06F76A: db -1  ; 0x1B
#_06F76B: db 0   ; 0x1C
#_06F76C: db -1  ; 0x1D
#_06F76D: db -1  ; 0x1E
#_06F76E: db 0   ; 0x1F

; ---------------------------------------------------------

.width
#_06F76F: db 12  ; 0x00
#_06F770: db 1   ; 0x01
#_06F771: db 16  ; 0x02
#_06F772: db 20  ; 0x03
#_06F773: db 20  ; 0x04
#_06F774: db 8   ; 0x05
#_06F775: db 4   ; 0x06
#_06F776: db 32  ; 0x07
#_06F777: db 48  ; 0x08
#_06F778: db 24  ; 0x09
#_06F779: db 32  ; 0x0A
#_06F77A: db 32  ; 0x0B
#_06F77B: db 32  ; 0x0C
#_06F77C: db 48  ; 0x0D
#_06F77D: db 12  ; 0x0E
#_06F77E: db 12  ; 0x0F

#_06F77F: db 60  ; 0x10
#_06F780: db 124 ; 0x11
#_06F781: db 12  ; 0x12
#_06F782: db 32  ; 0x13
#_06F783: db 4   ; 0x14
#_06F784: db 12  ; 0x15
#_06F785: db 48  ; 0x16
#_06F786: db 32  ; 0x17
#_06F787: db 40  ; 0x18
#_06F788: db 8   ; 0x19
#_06F789: db 24  ; 0x1A
#_06F78A: db 24  ; 0x1B
#_06F78B: db 5   ; 0x1C
#_06F78C: db 80  ; 0x1D
#_06F78D: db 4   ; 0x1E
#_06F78E: db 8   ; 0x1F

; ---------------------------------------------------------

.offset_y_low
#_06F78F: db 0   ; 0x00
#_06F790: db 3   ; 0x01
#_06F791: db 4   ; 0x02
#_06F792: db -4  ; 0x03
#_06F793: db -8  ; 0x04
#_06F794: db 2   ; 0x05
#_06F795: db 0   ; 0x06
#_06F796: db -16 ; 0x07
#_06F797: db 12  ; 0x08
#_06F798: db -4  ; 0x09
#_06F799: db -8  ; 0x0A
#_06F79A: db 0   ; 0x0B
#_06F79B: db -10 ; 0x0C
#_06F79C: db -16 ; 0x0D
#_06F79D: db 2   ; 0x0E
#_06F79E: db 2   ; 0x0F

#_06F79F: db 2   ; 0x10
#_06F7A0: db 2   ; 0x11
#_06F7A1: db -3  ; 0x12
#_06F7A2: db -12 ; 0x13
#_06F7A3: db 2   ; 0x14
#_06F7A4: db 10  ; 0x15
#_06F7A5: db 0   ; 0x16
#_06F7A6: db -12 ; 0x17
#_06F7A7: db 16  ; 0x18
#_06F7A8: db 4   ; 0x19
#_06F7A9: db -4  ; 0x1A
#_06F7AA: db -12 ; 0x1B
#_06F7AB: db 3   ; 0x1C
#_06F7AC: db -16 ; 0x1D
#_06F7AD: db -8  ; 0x1E
#_06F7AE: db 10  ; 0x1F

; ---------------------------------------------------------

.offset_y_high
#_06F7AF: db 0   ; 0x00
#_06F7B0: db 0   ; 0x01
#_06F7B1: db 0   ; 0x02
#_06F7B2: db -1  ; 0x03
#_06F7B3: db -1  ; 0x04
#_06F7B4: db 0   ; 0x05
#_06F7B5: db 0   ; 0x06
#_06F7B6: db -1  ; 0x07
#_06F7B7: db 0   ; 0x08
#_06F7B8: db -1  ; 0x09
#_06F7B9: db -1  ; 0x0A
#_06F7BA: db 0   ; 0x0B
#_06F7BB: db -1  ; 0x0C
#_06F7BC: db -1  ; 0x0D
#_06F7BD: db 0   ; 0x0E
#_06F7BE: db 0   ; 0x0F

#_06F7BF: db 0   ; 0x10
#_06F7C0: db 0   ; 0x11
#_06F7C1: db -1  ; 0x12
#_06F7C2: db -1  ; 0x13
#_06F7C3: db 0   ; 0x14
#_06F7C4: db 0   ; 0x15
#_06F7C5: db 0   ; 0x16
#_06F7C6: db -1  ; 0x17
#_06F7C7: db 0   ; 0x18
#_06F7C8: db 0   ; 0x19
#_06F7C9: db -1  ; 0x1A
#_06F7CA: db -1  ; 0x1B
#_06F7CB: db 0   ; 0x1C
#_06F7CC: db -1  ; 0x1D
#_06F7CD: db -1  ; 0x1E
#_06F7CE: db 0   ; 0x1F

; ---------------------------------------------------------

.height
#_06F7CF: db 14  ; 0x00
#_06F7D0: db 1   ; 0x01
#_06F7D1: db 16  ; 0x02
#_06F7D2: db 21  ; 0x03
#_06F7D3: db 24  ; 0x04
#_06F7D4: db 4   ; 0x05
#_06F7D5: db 8   ; 0x06
#_06F7D6: db 40  ; 0x07
#_06F7D7: db 20  ; 0x08
#_06F7D8: db 24  ; 0x09
#_06F7D9: db 40  ; 0x0A
#_06F7DA: db 29  ; 0x0B
#_06F7DB: db 36  ; 0x0C
#_06F7DC: db 48  ; 0x0D
#_06F7DD: db 60  ; 0x0E
#_06F7DE: db 124 ; 0x0F

#_06F7DF: db 12  ; 0x10
#_06F7E0: db 12  ; 0x11
#_06F7E1: db 17  ; 0x12
#_06F7E2: db 28  ; 0x13
#_06F7E3: db 4   ; 0x14
#_06F7E4: db 2   ; 0x15
#_06F7E5: db 28  ; 0x16
#_06F7E6: db 20  ; 0x17
#_06F7E7: db 10  ; 0x18
#_06F7E8: db 4   ; 0x19
#_06F7E9: db 24  ; 0x1A
#_06F7EA: db 16  ; 0x1B
#_06F7EB: db 5   ; 0x1C
#_06F7EC: db 48  ; 0x1D
#_06F7ED: db 8   ; 0x1E
#_06F7EE: db 12  ; 0x1F