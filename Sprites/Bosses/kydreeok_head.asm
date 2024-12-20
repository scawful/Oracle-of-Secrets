; =========================================================
; Kydreeok Head sprite
; Child sprite of the Kydreeok boss
; =========================================================

!SPRID              = Sprite_KydreeokHead
!NbrTiles           = 07  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = $C8 ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 09  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 00  ; 01 = your sprite continue to live offscreen
!Statis             = 00  ; 00 = is sprite is alive?, (kill all enemies room)
!CollisionLayer     = 00  ; 01 = will check both layer for collision
!CanFall            = 00  ; 01 sprite can fall in hole, 01 = can't fall
!DeflectArrow       = 00  ; 01 = deflect arrows
!WaterSprite        = 00  ; 01 = can only walk shallow water
!Blockable          = 00  ; 01 = can be blocked by link's shield?
!Prize              = 00  ; 00-15 = the prize pack the sprite will drop from
!Sound              = 00  ; 01 = Play different sound when taking damage
!Interaction        = 00  ; ?? No documentation
!Statue             = 00  ; 01 = Sprite is statue
!DeflectProjectiles = 00  ; 01 = Sprite will deflect ALL projectiles
!ImperviousArrow    = 00  ; 01 = Impervious to arrows
!ImpervSwordHammer  = 00  ; 01 = Impervious to sword and hammer attacks
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss
%Set_Sprite_Properties(Sprite_KydreeokHead_Prep, Sprite_KydreeokHead_Long)

Sprite_KydreeokHead_Long:
{
  PHB : PHK : PLB
  LDA.w SprAction, X : CMP #$05 : BEQ .no_head
    JSR Sprite_KydreeokHead_Draw
  .no_head

  JSL Sprite_CheckActive : BCC .not_active
    JSR Sprite_KydreeokHead_Main
  .not_active
  PLB
  RTL
}

; =========================================================

print "KydreeokHead_Prep: ", pc
Sprite_KydreeokHead_Prep:
{
  PHB : PHK : PLB
  LDA.b #$FF : STA.w SprHealth, X
  LDA.b #$09 : STA.w SprBump,   X ; bump damage type
  STZ.w SprMiscE, X
  PLB
  RTL
}

; =========================================================

SpeedTable:
  db $00, $02, $04, $06, $07, $01, $06, $03
  db 0, -2, -4, -6, -7, -1, -6, -3

Sprite_KydreeokHead_Main:
{
  LDA.w SprAction, X
  JSL   UseImplicitRegIndexedLocalJumpTable

  dw KydreeokHead_ForwardAnim ; 0x00
  dw KydreeokHead_RightAnim   ; 0x01
  dw KydreeokHead_LeftAnim    ; 0x02
  dw KydreeokHead_FarRight    ; 0x03
  dw KydreeokHead_FarLeft     ; 0x04
  dw KydreeokHead_SummonFire  ; 0x05

  ; -------------------------------------------------------
  ; 0x00
  KydreeokHead_ForwardAnim:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,2,10)

    PHX
    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer
    PLX

    JSR KydreeokHead_RotationMove
    JSR RandomlyAttack

    LDA.b #$20 : STA.w SprTimerA, X
    JSL Sprite_IsToRightOfPlayer : TYA : BNE .not_right
      JSR GetDistance8bit : CMP #$0B : BCC .not_far
        %GotoAction(3)
        RTS
      .not_far
      %GotoAction(1)
      RTS
    .not_right
    JSR GetDistance8bit : CMP #$0B : BCC .not_far2
      %GotoAction(4)
      RTS
    .not_far2
    %GotoAction(2)
    RTS
  }

  ; -------------------------------------------------------
  ; 0x01
  KydreeokHead_RightAnim:
  {
    %StartOnFrame(3)
    %PlayAnimation(3,5,10)

    PHX
    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer
    PLX

    JSR KydreeokHead_RotationMove
    JSR RandomlyAttack

    JSL Sprite_IsToRightOfPlayer : TYA : BNE .not_right
      RTS
    .not_right
    %GotoAction(0)
    RTS
  }

  ; -------------------------------------------------------
  ; 0x02
  KydreeokHead_LeftAnim:
  {
    %StartOnFrame(6)
    %PlayAnimation(6,8,10)

    PHX
    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer
    PLX

    JSR KydreeokHead_RotationMove
    JSR RandomlyAttack

    LDA.w SprTimerA, X : BNE .not_yet
      %GotoAction(0)
    .not_yet
    RTS
  }

  ; -------------------------------------------------------
  ; 0x03
  KydreeokHead_FarRight:
  {
    %PlayAnimation(9,11,10)
    %MoveTowardPlayer(15)

    PHX
    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer
    PLX

    JSR KydreeokHead_RotationMove
    JSR RandomlyAttack
    LDA.w SprTimerA, X : BNE .not_done
      %GotoAction(0)
    .not_done
    RTS
  }

  ; -------------------------------------------------------
  ; 0x04
  KydreeokHead_FarLeft:
  {
    %PlayAnimation(12,14,10)
    %MoveTowardPlayer(15)

    PHX
    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer
    PLX

    JSR KydreeokHead_RotationMove
    JSR RandomlyAttack
    LDA.w SprTimerA, X : BNE .not_done
       %GotoAction(0)
    .not_done
    RTS
  }


  KydreeokHead_SummonFire:
  {
    %MoveTowardPlayer(10)

    JSL Sprite_CheckDamageToPlayer
    JSL Sprite_Twinrova_FireAttack
    LDA.w SprTimerA, X : BNE .not_done
      LDA #$00 : STA.w SprState, X
    .not_done
    RTS
  }

}

KydreeokHead_RotationMove:
{
  ; ; Reset targetting mode
  ; LDA.w SprTimerE, X : BNE +
  ;   STZ.w SprMiscE, X
  ; +
  ; LDA.w SprMiscE, X : BEQ .continue_move
  ;   LDA.b #$04
  ;   JSL Sprite_ApplySpeedTowardsPlayer
  ;   JSL Sprite_Move
  ;   JSR MoveWithBody
  ;   RTS
  ; .continue_move

  JSL   GetRandomInt : AND #$0F : TAY
  LDA.w SpeedTable, Y : STA.w SprXSpeed, X : STA $00
  JSL   GetRandomInt : AND #$0F : TAY
  LDA.w SpeedTable, Y : STA.w SprYSpeed, X : STA $01
  ; JSL Sprite_Move

  JSR KydreeokHead_NeckControl
  JSR MoveWithBody

  JSR RotateHeadUsingSpeedValues

  ; JSL GetRandomInt : AND #$7F : BNE .no_independent
  ;   LDA.b #$01 : STA.w SprMiscE, X
  ;   LDA.b #$10 : STA.w SprTimerE, X
  ; .no_independent
  RTS
}

Sprite_KydreeokHead_Damage_Flash:
{
  LDA.w SprMiscE, X : BEQ .dontFlash
    ; Change the palette to the next in the cycle
    LDA.w SprMiscE, X : INC : CMP.b #$08 : BNE .dontReset
      LDA.b #$00
  .dontReset
    STA.w SprMiscE, X
    BRA .flash

  .dontFlash
  STZ.w SprMiscE, X

  .flash
  RTS
}

; =========================================================

CoordinateBasedRotation:
{
  LDA.w Neck_Index : TAY
  ; JSL   GetRandomInt : AND #$04 : TAY
  LDA.w X_Coords, Y : STA.w Neck1_OffsetX
  LDA.w X_Coords, Y : STA.w Neck2_OffsetX
  LDA.w X_Coords, Y : STA.w Neck3_OffsetX
  LDA.w Y_Coords, Y : STA.w Neck1_OffsetY
  LDA.w Y_Coords, Y : STA.w Neck2_OffsetY
  LDA.w Y_Coords, Y : STA.w Neck3_OffsetY
  JSL GetRandomInt : AND #$3F : BNE .dont_increment
    INC.w Neck_Index
  .dont_increment
  CPY #15 : BNE .not_full
    LDA #0 : STA.w Neck_Index
  .not_full
  RTS
}

; Table for X coordinates (based on a radius of 8)
X_Coords:
    db 8, 11,  8,  3, -4, -9, -12, -9
    db -4,  3,  8, 11,  8,  3, -4, -9

; Table for Y coordinates (based on a radius of 8)
Y_Coords:
    db 0, -3, -8, -11, -15, -15, -11, -8
    db -3,  0,  3,  8, 11, 15, 15, 11

; =========================================================

RotateHeadUsingSpeedValues:
{
  LDY.w Neck_Index

  LDA.w SprXSpeed, X : CLC : ADC.w XSpeedSin, Y : ASL : STA.w SprXSpeed, X
  LDA.w SprYSpeed, X : CLC : ADC.w YSpeedSin, Y : ASL : STA.w SprYSpeed, X

  INY : CPY #$3F : BNE .not_full
    LDY.b #$00
  .not_full
  STY.w Neck_Index
  JSL   Sprite_MoveLong
  RTS
}

XSpeedSin:
{
  db 0,   3,   6,   9,  12,  15,  18,  20,  23,  25
  db 27,  28,  30,  31,  31,  32
}

YSpeedSin:
{
  db 32,  32,  31,  31
  db 30,  28,  27,  25,  23,  20,  18,  15,  12,   9
  db 6,   3,   0,  -3,  -6,  -9, -12, -15, -18, -20
  db -23, -25, -27, -28, -30, -31, -31, -32, -32, -32
  db -31, -31, -30, -28, -27, -25, -23, -20, -18, -15
  db -12,  -9,  -6,  -3
  db 0,   3,   6,   9,  12,  15,  18,  20,  23,  25
  db 27,  28,  30,  31,  31,  32,  32,  32,  31,  31
  db 30,  28,  27,  25,  23,  20,  18,  15,  12,   9
  db 6,   3,   0,  -3,  -6,  -9, -12, -15, -18, -20
  db -23, -25, -27, -28, -30, -31, -31, -32, -32, -32
  db -31, -31, -30, -28, -27, -25, -23, -20, -18, -15
  db -12,  -9,  -6,  -3
}

; =========================================================

RandomlyAttack:
{
  JSR Sprite_KydreeokHead_Damage_Flash
  JSL GetRandomInt : AND #$7F : BNE .no_attack
    CLC
    JSL GetRandomInt : AND #$0F : BNE .no_attack
      LDA   #$CF
      JSL   Sprite_SpawnDynamically
      JSL   Sprite_SetSpawnedCoords
      JSL   Fireball_SpawnTrailGarnish
      LDA.b #$05 : STA.w SprAction, Y
      LDA   #$20 : STA.w SprTimerA, Y
  .no_attack
  RTS
}

; =========================================================

MoveWithBody:
{
  LDA.w Kydreeok_Id : TAY
  CPX.w Offspring2_Id : BEQ .neck2_move

    LDA.w SprX, Y : SEC : SBC #$0F
    STA.w SprMiscA, X
    STA.w $19EA : DEC
    STA.w $19EC : DEC
    STA.w $19EE
    ; STA.w SprX, X

    LDA.w SprY, Y : SEC : SBC #$0F
    STA.w SprMiscB, X
    STA.w $19EB
    ; STA.w $19ED
    ; STA.w $19EF
    ; STA.w SprY, X
    RTS

  .neck2_move
    LDA.w SprX, Y : CLC : ADC #$0C
    STA.w SprMiscA, X
    STA.w $19F0 : INC
    STA.w $19F2 : INC
    STA.w $19F4
    ; STA.w SprX, X

    LDA.w SprY, Y : SEC : SBC #$0F
    ; STA.w SprY,     X
    STA.w SprMiscB, X
    STA.w $19F1
    ; STA.w $19F3
    ; STA.w $19F5
  .return
  RTS
}

; =========================================================
; Based on Zarby Gleeok code

Neck1_Control:
{
  ; Set head pos
  LDA $19EE : STA.w SprX, X
  LDA $19EF : STA.w SprY, X

  LDA.w SprX, X : STA.w SprMiscC, X
  LDA.w SprY, X : STA.w SprMiscD, X
  LDA.w SprXSpeed, X : STA $08
  LDA.w SprYSpeed, X : STA $09

  LDA.w $19EA : STA $02 ; x
  LDA.w $19EB : STA $03 ; y

  LDA.w SprX, X : STA $04
  LDA.w SprY, X : STA $05
  JSR   GetDistance8bit : CMP #$08 : BCC .TooCloseToHead ; is body1 too close to the head?
    LDA.w SprX,  X : STA $04 ; dest X
    LDA.w SprXH, X : STA $05 ; dest XH
    LDA.w SprY,  X : STA $06 ; dest Y
    LDA.w SprYH, X : STA $07 ; dest YH

    ; load body position into sprite position
    LDA.w $19EA : STA.w SprX, X
    LDA.w $19EB : STA.w SprY, X

    LDA   #$06
    JSL   Sprite_ProjectSpeedTowardsEntityLong
    LDA.b $01 : STA.w SprXSpeed, X
    LDA.b $00 : STA.w SprYSpeed, X
    JSL   Sprite_MoveLong

    LDA.w SprX, X : STA.w $19EA
    LDA.w SprY, X : STA.w $19EB
  .TooCloseToHead

  ; Do body part 2

  LDA.w $19EC : STA $02 ; x
  LDA.w $19ED : STA $03 ; y

  LDA.w $19EA : STA $04
  LDA.w $19EB : STA $05
  JSR   GetDistance8bit : CMP #$0D : BCC .TooCloseToBodyPart1 ; is body1 too close to the head?
    LDA.w $19EA : STA $04    ; dest X
    LDA.w SprXH, X : STA $05 ; dest XH
    LDA.w $19EB : STA $06    ; dest Y
    LDA.w SprYH, X : STA $07 ; dest YH

    ;load body position into sprite position
    LDA.w $19EC : STA.w SprX, X
    LDA.w $19ED : STA.w SprY, X

    LDA   #$06
    JSL   Sprite_ProjectSpeedTowardsEntityLong
    LDA.b $01 : STA.w SprXSpeed, X
    LDA.b $00 : STA.w SprYSpeed, X
    JSL   Sprite_MoveLong

    LDA.w SprX, X : STA.w $19EC
    LDA.w SprY, X : STA.w $19ED
  .TooCloseToBodyPart1

  ; Do body part 2
  LDA.w $19EE : STA $02 ; x
  LDA.w $19EF : STA $03 ; y

  LDA.w $19EC : STA $04
  LDA.w $19ED : STA $05
  JSR   GetDistance8bit : CMP #$14 : BCC .TooCloseToBodyPart2 ; is body1 too close to the head?
    LDA.w $19EC : STA $04                 ; dest X
    LDA.w SprXH,              X : STA $05 ; dest XH
    LDA.w $19ED : STA $06                 ; dest Y
    LDA.w SprYH,              X : STA $07 ; dest YH
    ;load body position into sprite position
    LDA.w $19EE : STA.w SprX, X
    LDA.w $19EF : STA.w SprY, X

    LDA   #$06
    JSL   Sprite_ProjectSpeedTowardsEntityLong
    LDA.b $01 : STA.w SprXSpeed, X
    LDA.b $00 : STA.w SprYSpeed, X
    JSL   Sprite_MoveLong
    LDA.w SprX,                  X : STA.w $19EE
    LDA.w SprY,                  X : STA.w $19EF
  .TooCloseToBodyPart2

  LDA.w SprMiscC, X : STA.w SprX, X
  LDA.w SprMiscD, X : STA.w SprY, X
  LDA.b $08 : STA.w SprXSpeed, X
  LDA.b $09 : STA.w SprYSpeed, X
  RTS
}

Neck2_Control:
{
  ; Set head pos
  LDA $19F4  : STA.w SprX, X
  LDA $19F5  : STA.w SprY, X

  LDA.w SprX, X : STA.w SprMiscC, X
  LDA.w SprY, X : STA.w SprMiscD, X
  LDA.w SprXSpeed, X : STA $08
  LDA.w SprYSpeed, X : STA $09

  LDA.w $19F0 : STA $02 ; x
  LDA.w $19F1 : STA $03 ; y

  LDA.w SprX, X : STA $04
  LDA.w SprY, X : STA $05
  JSR   GetDistance8bit : CMP #$08 : BCC .TooCloseToHead2 ; is body1 too close to the head?
    LDA.w SprX,               X : STA $04 ; dest X
    LDA.w SprXH,              X : STA $05 ; dest XH
    LDA.w SprY,               X : STA $06 ; dest Y
    LDA.w SprYH,              X : STA $07 ; dest YH
    ; load body position into sprite position
    LDA.w $19F0 : STA.w SprX, X
    LDA.w $19F1 : STA.w SprY, X

    LDA   #$08
    JSL   Sprite_ProjectSpeedTowardsEntityLong
    LDA.b $01 : STA.w SprXSpeed, X
    LDA.b $00 : STA.w SprYSpeed, X
    JSL   Sprite_MoveLong
    LDA.w SprX,                  X : STA.w $19F0
    LDA.w SprY,                  X : STA.w $19F1

  .TooCloseToHead2

  LDA.w $19F2 : STA $02 ; x
  LDA.w $19F3 : STA $03 ; y

  LDA.w $19F0 : STA $04
  LDA.w $19F1 : STA $05
  JSR   GetDistance8bit : CMP #$0D : BCC .TooCloseToBodyPart12 ; is body1 too close to the head?

    LDA.w $19F0 : STA $04                 ; dest X
    LDA.w SprXH,              X : STA $05 ; dest XH
    LDA.w $19F1 : STA $06                 ; dest Y
    LDA.w SprYH,              X : STA $07 ; dest YH
    ;load body position into sprite position
    LDA.w $19F2 : STA.w SprX, X
    LDA.w $19F3 : STA.w SprY, X

    LDA   #$04
    JSL   Sprite_ProjectSpeedTowardsEntityLong
    LDA.b $01 : STA.w SprXSpeed, X
    LDA.b $00 : STA.w SprYSpeed, X
    JSL   Sprite_MoveLong
    LDA.w SprX,                  X : STA.w $19F2
    LDA.w SprY,                  X : STA.w $19F3

  .TooCloseToBodyPart12

  ; Do body part 2
  LDA.w $19F4 : STA $02 ; x
  LDA.w $19F5 : STA $03 ; y

  LDA.w $19F2 : STA $04
  LDA.w $19F3 : STA $05
  JSR   GetDistance8bit : CMP #$14 : BCC .TooCloseToBodyPart22 ; is body1 too close to the head?
    LDA.w $19F2 : STA $04                 ; dest X
    LDA.w SprXH,              X : STA $05 ; dest XH
    LDA.w $19F3 : STA $06                 ; dest Y
    LDA.w SprYH,              X : STA $07 ; dest YH
    ;load body position into sprite position
    LDA.w $19F4 : STA.w SprX, X
    LDA.w $19F5 : STA.w SprY, X

    LDA   #$03
    JSL   Sprite_ProjectSpeedTowardsEntityLong
    LDA.b $01 : STA.w SprXSpeed, X
    LDA.b $00 : STA.w SprYSpeed, X
    JSL   Sprite_MoveLong
    LDA.w SprX,                  X : STA.w $19F4
    LDA.w SprY,                  X : STA.w $19F5
  .TooCloseToBodyPart22

  LDA.w SprMiscC, X : STA.w SprX, X
  LDA.w SprMiscD, X : STA.w SprY, X
  LDA.b $08 : STA.w SprXSpeed, X
  LDA.b $09 : STA.w SprYSpeed, X
  RTS
}

KydreeokHead_NeckControl:
{
  LDA.w SprSubtype, X : BEQ .DoNeck1
    JSR Neck2_Control
    RTS
  .DoNeck1
  JSR Neck1_Control
  RTS
}

; =========================================================

Sprite_KydreeokHead_DrawNeck:
{
  ; Dumb draw neck code
  LDA.w SprSubtype, X : CMP.b #$01 : BEQ .neck2
    LDA.w $19EE : STA.w SprCachedX
    LDA.w $19EF : CLC : ADC.b #$06 : STA.w SprCachedY
    JSR DrawNeckPart

    LDA.w $19EC : STA.w SprCachedX
    LDA.w $19ED : STA.w SprCachedY
    JSR DrawNeckPart
    LDA.w SprCachedY : SEC : SBC.b #$0A : STA.w SprCachedY
    JSR DrawNeckPart

    LDA.w $19EA : STA.w SprCachedX
    LDA.w $19EB : SEC : SBC.b #$04 : STA.w SprCachedY
    JSR DrawNeckPart
    LDA.w SprCachedY : SEC : SBC.b #$0A : STA.w SprCachedY
    JSR DrawNeckPart

    BRA .skipNeck
  .neck2

  LDA.w $19F4 : STA.w SprCachedX
  LDA.w $19F5 : CLC : ADC.b #$06 : STA.w SprCachedY
  JSR DrawNeckPart

  LDA.w $19F2 : STA.w SprCachedX
  LDA.w $19F3 : STA.w SprCachedY
  JSR DrawNeckPart
  LDA.w SprCachedY : SEC : SBC.b #$0A : STA.w SprCachedY
  JSR DrawNeckPart

  LDA.w $19F0 : STA.w SprCachedX
  LDA.w $19F1 : SEC : SBC.b #$04 : STA.w SprCachedY
  JSR DrawNeckPart
  LDA.w SprCachedY : SEC : SBC.b #$0A : STA.w SprCachedY
  JSR DrawNeckPart

  .skipNeck
  LDA.b $08 : STA.w SprCachedX
  LDA.b $09 : STA.w SprCachedY
  .skipNeck2
  RTS
}

DrawNeckPart:
{
  PHY
  JSL Sprite_PrepOamCoord
  PLY

  REP #$20
  LDA $00 : STA ($90), Y : AND.w #$0100 : STA $0E : INY
  LDA $02 : STA ($90), Y : CLC   : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y2
    LDA.b #$F0 : STA ($90), Y ; Put the sprite out of the way
    STA   $0E
  .on_screen_y2
    INY
    LDA #$2E : STA ($90), Y ; Set the Char
    INY
    LDA #$39 : ORA $08 : STA ($90), Y ; Set the Properties

    PHY
    TYA : LSR #2 : TAY
    LDA #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
    PLY : INY

    RTS
}

; =========================================================

Sprite_KydreeokHead_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  LDA.w SprMiscE, X : STA $08

  PHX
  ; amount of tiles - 1
  LDX .nbr_of_tiles, Y : LDY.b #$00
  .next_tile

  PHX ; Save current Tile Index?
  ; Add Animation Index Offset
  TXA : CLC : ADC $06

  ; Keep the value with animation index offset?
  PHA : ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E  : INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA   $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY : LDA .chr, X : STA ($90), Y : INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .next_tile

  PLX

  JMP Sprite_KydreeokHead_DrawNeck

  .start_index
    db $00, $02, $04, $06, $0A, $0E, $12, $16, $1A, $1E, $22, $26, $2A, $2E, $32, $36
  .nbr_of_tiles
    db 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3
  .x_offsets
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 8, -8, -8, 8
    dw 8, -8, -8, 8
    dw 8, -8, -8, 8
    dw -8, 8, -8, 8
    dw 8, -8, -8, 8
    dw -8, 8, 8, -8

    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw 8, -8, 8, -8
    dw 8, -8, 8, -8
    dw 8, -8, 8, -8
  .y_offsets
    dw -8, 8
    dw -8, 8
    dw -8, 8
    dw 4, 4, -12, -12
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8

    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
  .chr
    db $40, $60
    db $42, $62
    db $44, $64
    db $68, $66, $46, $48
    db $0A, $08, $28, $2A
    db $4C, $4A, $6A, $6C
    db $48, $46, $68, $66
    db $08, $0A, $2A, $28
    db $4C, $4A, $6A, $6C

    db $80, $82, $A0, $A2
    db $84, $86, $A4, $A6
    db $88, $8A, $A8, $AA
    db $80, $82, $A0, $A2
    db $84, $86, $A4, $A6
    db $88, $8A, $A8, $AA
  .properties
    db $39, $39
    db $39, $39
    db $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $79, $79, $79, $79
    db $79, $79, $79, $79
    db $79, $79, $79, $79

    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $79, $79, $79, $79
    db $79, $79, $79, $79
    db $79, $79, $79, $79
  .sizes
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02

    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
}

GetDistance8bit:
{
  LDA   $04        ; Sprite X
  SEC   : SBC $02  ; - Player X
  BPL   +
  EOR.b #$FF : INC
  +
  STA   $00        ; Distance X (ABS)

  LDA   $05                 ; Sprite Y
  SEC   : SBC $03           ; - Player Y
  BPL   +
  EOR.b #$FF : INC
  +
  ; Add it back to X Distance
  CLC   : ADC $00 : STA $00 ; distance total X, Y (ABS)
  RTS
}
