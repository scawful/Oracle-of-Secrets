; =========================================================
; return carry set if active

Sprite_CheckActive:
{
  ; Deactivates the sprite in certain situations
  LDA.w SprState, X : CMP.b #$09 : BNE .inactive
    LDA.w SprFreeze : BNE .inactive
      LDA $11 : BNE .inactive
        LDA.w SprDefl, X : BMI .active
          LDA.w SprPause, X : BEQ .active
  .inactive
  CLC
  RTL
  .active
  SEC
  RTL
}

; =========================================================
; make the sprite move X axis

Sprite_MoveHoriz:
{
  LDA.w SprXSpeed, X : BEQ .no_velocity
    ASL   : ASL : ASL : ASL
    CLC : ADC.w SprXRound, X : STA.w SprXRound, X

    LDY.b #$00
    LDA.w SprXSpeed, X
    PHP   : LSR : LSR : LSR : LSR : PLP
    BPL   ++

    ORA.b #$F0
    DEY

    ++	ADC.w SprX, X : STA.w SprX, X
    TYA : ADC.w SprXH, X : STA.w SprXH, X

  .no_velocity
  RTL
}

; =========================================================
; make the sprite move both directions (also height)

Sprite_MoveXyz:
	JSL Sprite_MoveAltitude
Sprite_Move:
	JSL Sprite_MoveHoriz
	; no RTL, just continue into Sprite_MoveVert

; =========================================================
; make the sprite move Y axis

Sprite_MoveVert:
{
  LDA.w SprYSpeed, X : BEQ .no_velocity
    ASL : ASL : ASL : ASL
    CLC : ADC.w $0D60,X : STA.w $0D60,X

    LDY.b #$00
    LDA.w SprYSpeed, X
    PHP   : LSR : LSR : LSR : LSR : PLP
    BPL   ++

    ORA.b #$F0
    DEY

    ++	ADC.w SprY,X : STA.w SprY,X
    TYA : ADC.w SprYH,X : STA.w SprYH,X

  .no_velocity
  RTL
}

; =========================================================
; make the sprite move Z axis (height)

Sprite_MoveZ:
Sprite_MoveAltitude:
{
  LDA.w SprTimerF, X : ASL : ASL : ASL : ASL
  CLC : ADC.w $0F90, X : STA.w $0F90, X

  LDA.w SprTimerF, X : PHP
  LSR   : LSR : LSR : LSR
  PLP   : BPL .positive
    ORA.b #$F0
  .positive
  ADC.w SprHeight,X : STA.w SprHeight,X

  RTL
}


; =========================================================
; make the sprite bounce toward player
; movement, collision are handled by this function 
; $09 = speed, $08 = max height ( e.g. height:20 = vitreous)


Sprite_BounceTowardPlayer:
{
	JSL Sprite_MoveAltitude
	DEC.w SprTimerF, X : DEC.w SprTimerF, X
	LDA.w SprHeight, X : BPL .aloft
    STZ.w SprHeight, X
    LDA.b $08 : STA.w SprTimerF, X ; set height from 08
    LDA.b $09 : JSL Sprite_ApplySpeedTowardsPlayer
    ; LDA.b #$21 : JSL Sound_SetSfx2PanLong
  .aloft
  LDA.w SprHeight, X : BEQ .dontmove
    JSL Sprite_Move
  .dontmove
	RTL
}

; A = Speed
Sprite_FloatTowardPlayer:
{
  ; Maintain altitude (float effect)
  TYA : STA.w SprHeight, X
  JSL Sprite_MoveAltitude

  JSL Sprite_ApplySpeedTowardsPlayer

  ; Update horizontal position
  JSL Sprite_MoveHoriz

  ; Update vertical position
  JSL Sprite_MoveVert

  RTL
}

Sprite_FloatAwayFromPlayer:
{
  JSL Sprite_InvertSpeed_XY
  JSL Sprite_MoveAltitude
  JSL Sprite_Move
  RTL
}

Sprite_BounceFromTileCollision:
{
  JSL   Sprite_CheckTileCollision : AND.b #$03 : BEQ ++
    LDA.w SprXSpeed, X : EOR.b #$FF : INC : STA.w SprXSpeed, X

  ++ LDA.w SprCollision, X : AND.b #$0C : BEQ ++
      LDA.w SprYSpeed, X : EOR.b #$FF : INC : STA.w SprYSpeed, X

  ++ RTL
}

; =========================================================

Sprite_BounceOffWall:
  LDA.w SprCollision, X : AND.b #$03 : BEQ .no_horizontal_collision
    JSL Sprite_InvertSpeed_X
  .no_horizontal_collision
  LDA.w SprCollision, X : AND.b #$0C : BEQ .no_vertical_collision
    JSL Sprite_InvertSpeed_Y
  .no_vertical_collision
  RTL

; =========================================================

Sprite_InvertSpeed_XY:
  JSL Sprite_InvertSpeed_Y

; =========================================================

Sprite_InvertSpeed_X:
  LDA.w SprXSpeed, X
  EOR.b #$FF
  INC A
  STA.w SprXSpeed, X

  RTL

; =========================================================

Sprite_InvertSpeed_Y:
  LDA.w SprYSpeed,X
  EOR.b #$FF
  INC A
  STA.w SprYSpeed,X

  RTL

; =========================================================

Sprite_SelectNewDirection:
{
  JSL GetRandomInt : AND.b #$07 : TAY
  LDA.w .speed_x, Y : STA.w SprXSpeed, X
  LDA.w .speed_y, Y : STA.w SprYSpeed, X
  LDA.w .timers, Y : STA.w SprTimerA, X
  RTL

  .speed_x
    db  8,  6, -6,  8, -6,  6,  0,  0

  .speed_y
    db  0,  6,  6,  0, -6, -6,  0,  0

  .timers
    db 48, 48, 48, 48, 48, 48, 64, 64
}

; =========================================================
; Parameters: Y index contains direction to drag player
; 0 = up, 1 = down, 2 = left, 3 = right

DragYL = $0B7C
DragYH = $0B7D
DragXL = $0B7E
DragXH = $0B7F

DragPlayer:
{
  LDA.w .drag_x_low,  Y : CLC : ADC.w DragYL : STA.w DragYL
  LDA.w .drag_x_high, Y : ADC.w DragYH : STA DragYH

  LDA.w .drag_y_low,  Y : CLC : ADC.w DragXL : STA.w DragXL
  LDA.w .drag_y_high, Y : ADC.w DragXH : STA.w DragXH

  .SomariaPlatform_DragLink
  REP #$20

  LDA SprCachedX : SEC : SBC.w #$0002
  CMP $22 : BEQ .x_done : BPL .x_too_low
      DEC.w DragYL
      BRA .x_done
    .x_too_low
    INC.w DragYL

  .x_done
  ; Changing the modifier adjusts links position in the cart 
  LDA SprCachedY : SEC : SBC.w #$0008
  CMP $20 : BEQ .y_done : BPL .y_too_low
      DEC.w DragXL
      BRA .y_done
    .y_too_low
    INC.w DragXL

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

Sprite_DamageFlash_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Damage_Flash

  PLB
  RTL
}

; =========================================================

Sprite_Damage_Flash:
{
  LDA $0EF0, X : BEQ .dontFlash
    ; Change the palette to the next in the cycle
    LDA.w SprFlash, X : INC : CMP.b #$08 : BNE .dontReset
      LDA.b #$00
    
  .dontReset
    STA.w SprFlash, X
    BRA .flash

.dontFlash
  STZ.w SprFlash, X

.flash
  RTS
}

; =========================================================

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

; =========================================================

Link_SetupHitBox:
{
  LDA.b #$08 : STA $02 : STA $03
  
  LDA $22 : CLC : ADC.b #$04 : STA $00
  LDA $23 : ADC.b #$00 : STA $08
  
  LDA $20 : ADC.b #$08 : STA $01
  LDA $21 : ADC.b #$00 : STA $09
  
  RTL
}

; =========================================================

Sprite_SetupHitBox:
{
  PHB : PHK : PLB
  LDA.w SprHeight, X : BMI .too_high
    PHY
    LDA.w $0F60, X : AND.b #$1F : TAY
    LDA.w SprX, X : CLC : ADC.w .offset_x_low, Y : STA.b $04

    LDA.w SprXH, X : ADC.w .offset_x_high, Y : STA.b $0A

    LDA.w SprY, X : CLC : ADC.w .offset_y_low, Y

    PHP
    SEC : SBC.w SprHeight, X : STA.b $05
    LDA.w SprYH, X : SBC.b #$00

    PLP
    ADC.w .offset_y_high, Y : STA.b $0B

    LDA.w .width, Y : STA.b $06
    LDA.w .height, Y : STA.b $07
    PLY
    PLB
    RTL

  .too_high
  LDA.b #$80 : STA.b $0A
  PLB
  RTL

.offset_x_low
  db 2   ; 0x00
  db 3   ; 0x01
  db 0   ; 0x02
  db -3  ; 0x03
  db -6  ; 0x04
  db 0   ; 0x05
  db 2   ; 0x06
  db -8  ; 0x07
  db 0   ; 0x08
  db -4  ; 0x09
  db -8  ; 0x0A
  db 0   ; 0x0B
  db -8  ; 0x0C
  db -16 ; 0x0D
  db 2   ; 0x0E
  db 2   ; 0x0F

  db 2   ; 0x10
  db 2   ; 0x11
  db 2   ; 0x12
  db -8  ; 0x13
  db 2   ; 0x14
  db 2   ; 0x15
  db -16 ; 0x16
  db -8  ; 0x17
  db -12 ; 0x18
  db 4   ; 0x19
  db -4  ; 0x1A
  db -12 ; 0x1B
  db 5   ; 0x1C
  db -32 ; 0x1D
  db -2  ; 0x1E
  db 4   ; 0x1F

; ---------------------------------------------------------

.offset_x_high
  db 0   ; 0x00
  db 0   ; 0x01
  db 0   ; 0x02
  db -1  ; 0x03
  db -1  ; 0x04
  db 0   ; 0x05
  db 0   ; 0x06
  db -1  ; 0x07
  db 0   ; 0x08
  db -1  ; 0x09
  db -1  ; 0x0A
  db 0   ; 0x0B
  db -1  ; 0x0C
  db -1  ; 0x0D
  db 0   ; 0x0E
  db 0   ; 0x0F

  db 0   ; 0x10
  db 0   ; 0x11
  db 0   ; 0x12
  db -1  ; 0x13
  db 0   ; 0x14
  db 0   ; 0x15
  db -1  ; 0x16
  db -1  ; 0x17
  db -1  ; 0x18
  db 0   ; 0x19
  db -1  ; 0x1A
  db -1  ; 0x1B
  db 0   ; 0x1C
  db -1  ; 0x1D
  db -1  ; 0x1E
  db 0   ; 0x1F

; ---------------------------------------------------------

.width
  db 12  ; 0x00
  db 1   ; 0x01
  db 16  ; 0x02
  db 20  ; 0x03
  db 20  ; 0x04
  db 8   ; 0x05
  db 4   ; 0x06
  db 32  ; 0x07
  db 48  ; 0x08
  db 24  ; 0x09
  db 32  ; 0x0A
  db 32  ; 0x0B
  db 32  ; 0x0C
  db 48  ; 0x0D
  db 12  ; 0x0E
  db 12  ; 0x0F

  db 60  ; 0x10
  db 124 ; 0x11
  db 12  ; 0x12
  db 32  ; 0x13
  db 4   ; 0x14
  db 12  ; 0x15
  db 48  ; 0x16
  db 32  ; 0x17
  db 40  ; 0x18
  db 8   ; 0x19
  db 24  ; 0x1A
  db 24  ; 0x1B
  db 5   ; 0x1C
  db 80  ; 0x1D
  db 4   ; 0x1E
  db 8   ; 0x1F

; ---------------------------------------------------------

.offset_y_low
  db 0   ; 0x00
  db 3   ; 0x01
  db 4   ; 0x02
  db -4  ; 0x03
  db -8  ; 0x04
  db 2   ; 0x05
  db 0   ; 0x06
  db -16 ; 0x07
  db 12  ; 0x08
  db -4  ; 0x09
  db -8  ; 0x0A
  db 0   ; 0x0B
  db -10 ; 0x0C
  db -16 ; 0x0D
  db 2   ; 0x0E
  db 2   ; 0x0F

  db 2   ; 0x10
  db 2   ; 0x11
  db -3  ; 0x12
  db -12 ; 0x13
  db 2   ; 0x14
  db 10  ; 0x15
  db 0   ; 0x16
  db -12 ; 0x17
  db 16  ; 0x18
  db 4   ; 0x19
  db -4  ; 0x1A
  db -12 ; 0x1B
  db 3   ; 0x1C
  db -16 ; 0x1D
  db -8  ; 0x1E
  db 10  ; 0x1F

; ---------------------------------------------------------

.offset_y_high
  db 0   ; 0x00
  db 0   ; 0x01
  db 0   ; 0x02
  db -1  ; 0x03
  db -1  ; 0x04
  db 0   ; 0x05
  db 0   ; 0x06
  db -1  ; 0x07
  db 0   ; 0x08
  db -1  ; 0x09
  db -1  ; 0x0A
  db 0   ; 0x0B
  db -1  ; 0x0C
  db -1  ; 0x0D
  db 0   ; 0x0E
  db 0   ; 0x0F

  db 0   ; 0x10
  db 0   ; 0x11
  db -1  ; 0x12
  db -1  ; 0x13
  db 0   ; 0x14
  db 0   ; 0x15
  db 0   ; 0x16
  db -1  ; 0x17
  db 0   ; 0x18
  db 0   ; 0x19
  db -1  ; 0x1A
  db -1  ; 0x1B
  db 0   ; 0x1C
  db -1  ; 0x1D
  db -1  ; 0x1E
  db 0   ; 0x1F

; ---------------------------------------------------------

.height
  db 14  ; 0x00
  db 1   ; 0x01
  db 16  ; 0x02
  db 21  ; 0x03
  db 24  ; 0x04
  db 4   ; 0x05
  db 8   ; 0x06
  db 40  ; 0x07
  db 20  ; 0x08
  db 24  ; 0x09
  db 40  ; 0x0A
  db 29  ; 0x0B
  db 36  ; 0x0C
  db 48  ; 0x0D
  db 60  ; 0x0E
  db 124 ; 0x0F

  db 12  ; 0x10
  db 12  ; 0x11
  db 17  ; 0x12
  db 28  ; 0x13
  db 4   ; 0x14
  db 2   ; 0x15
  db 28  ; 0x16
  db 20  ; 0x17
  db 10  ; 0x18
  db 4   ; 0x19
  db 24  ; 0x1A
  db 16  ; 0x1B
  db 5   ; 0x1C
  db 48  ; 0x1D
  db 8   ; 0x1E
  db 12  ; 0x1F
}

; =========================================================

Sprite_ApplySpeedTowardsPlayerXOrY:
{
  JSL Sprite_IsBelowPlayer : BEQ .player_below
    ;playerAbove

    REP #$20
    ; if link.y is 6 above sprite.y it is considered below
    LDA SprCachedY : SEC : SBC $20 : CLC : ADC.w #$0006 : STA $01 ;delta Y
    SEP #$20

    JSL Sprite_IsToRightOfPlayer : BEQ .player_to_the_Right1
      ;player_to_the_Left
      REP #$20
      LDA SprCachedX : SEC : SBC $22 ; delta X
      
      CMP $01 : BCS .XGreaterThanY1
        ;YGreaterThanX
        SEP   #$20
        LDA.b #$00 : SEC : SBC $00 : STA.w SprYSpeed
        STZ.w SprXSpeed
        RTL

      .XGreaterThanY1
        SEP   #$20
        LDA.b #$00 : SEC : SBC $00 : STA.w SprXSpeed
        STZ.w SprYSpeed
        RTL

  .player_to_the_Right1
      REP #$20
      LDA $22 : SEC : SBC SprCachedX ; delta X

      CMP $01 : BCS .XGreaterThanY2
        ;YGreaterThanX
        SEP   #$20
        LDA.b #$00 : SEC : SBC $00 : STA.w SprYSpeed
        STZ.w SprXSpeed
        RTL

      .XGreaterThanY2
        SEP   #$20
        LDA.b #$00 : CLC : ADC $00 : STA.w SprXSpeed
        STZ.w SprYSpeed
        RTL


  .player_below
      REP #$20
      ; if link.y is 6 above sprite.y it is considered below
      LDA $20 : SEC : SBC SprCachedY : CLC : ADC.w #$0006 : STA $01 ; delta Y
      SEP #$20

      JSL Sprite_IsToRightOfPlayer : BEQ .player_to_the_Right2
        ;player_to_the_Left
        REP #$20
        LDA SprCachedX : SEC : SBC $22 ; delta X

        CMP $01 : BCS .XGreaterThanY3
          ;YGreaterThanX
          SEP   #$20
          LDA.b #$00 : CLC : ADC $00 : STA.w SprYSpeed
          STZ.w SprXSpeed
          RTL

        .XGreaterThanY3
          SEP   #$20
          LDA.b #$00 : SEC : SBC $00 : STA.w SprXSpeed
          STZ.w SprYSpeed
          RTL


      .player_to_the_Right2
        REP #$20
        LDA $22 : SEC : SBC SprCachedX ; delta X

        CMP $01 : BCS .XGreaterThanY4
          ;YGreaterThanX
          SEP   #$20
          LDA.b #$00 : CLC : ADC $00 : STA.w SprYSpeed
          STZ.w SprXSpeed
          RTL

        .XGreaterThanY4
          SEP   #$20
          LDA.b #$00 : CLC : ADC $00 : STA.w SprXSpeed
          STZ.w SprYSpeed
          RTL
}

; =========================================================

GetDistance8bit_Long:
{
  LDA   $04        ; Sprite X
  SEC   : SBC $02  ; - Player X
  BPL   +
  EOR.b #$FF : INC
  +
  STA   $00        ; Distance X (ABS)

  LDA   $05        ; Sprite Y
  SEC   : SBC $03  ; - Player Y
  BPL   +
  EOR.b #$FF : INC
  +
  ; Add it back to X Distance
  CLC   : ADC $00 : STA $00 ; distance total X, Y (ABS)
  RTL
}


; =========================================================

Intro_Dungeon_Main:
{
  LDA $0E20 : CMP.b #$92 : BNE .not_sprite_body_boss
      LDA $0E30 : BEQ .not_sprite_body_boss
 LDA $1C : AND.b #$FE : STA $1C ;turn off BG2 (Body)

 ; free ram used to check if the sprite ran this frame, if 0, it didn't run
 LDA.b SpriteRanCheck : BEQ .didNotRun
     LDA $1C : ORA.b #$01 : STA $1C ;turn on BG2 (Body)

 .didNotRun
 
 STZ.b SpriteRanCheck

  .not_sprite_body_boss

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

; =========================================================

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

; =========================================================

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