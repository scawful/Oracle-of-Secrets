; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = $7A ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 08  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = $07 ; 00 to 31, can be viewed in sprite draw tool
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
!Boss               = 01  ; 00 = normal sprite, 01 = sprite is a boss
%Set_Sprite_Properties(Sprite_Kydreeok_Prep, Sprite_Kydreeok_Long);

; =========================================================

Sprite_Kydreeok_Long:
{
    PHB : PHK : PLB

    JSR Sprite_Kydreeok_Draw
    JSL Sprite_CheckActive : BCC .SpriteIsNotActive  
      JSR Sprite_Kydreeok_Main
      JSR Sprite_Kydreeok_CheckIfDead
      JSR MaybeRespawnHead

    .SpriteIsNotActive
    LDA.w SprState, X : BNE .not_inactive
      JSR ApplyEndPalette
    .not_inactive

    PLB ; Get back the databank we stored previously
    RTL ; Go back to original code
}

; =========================================================

Sprite_Kydreeok_Prep:
{
  PHB : PHK : PLB
    
  LDA   #$40 : STA.w SprTimerA, X
  LDA.b #$08 : STA $36          ; Stores initial movement speeds
  LDA.b #$06 : STA $0428        ; Allows BG1 to move
  LDA.b #$09 : STA.w SprBump,   X ; bump damage type

  ; Cache the origin position of the sprite.
  LDA SprX, X : STA.w SprMiscA, X 
  LDA SprY, X : STA.w SprMiscB, X

  JSR SpawnLeftHead 
  ; JSR SpawnCenterHead
  JSR SpawnRightHead

  STZ.w Neck1_OffsetX : STZ.w Neck1_OffsetY
  STZ.w Neck2_OffsetX : STZ.w Neck2_OffsetY
  STZ.w Neck3_OffsetX : STZ.w Neck3_OffsetY

  JSR ApplyPalette

  ; Final Boss theme 1F 
  LDA #$1F : STA $012C

  PLB
  RTL
}

Sprite_Kydreeok_CheckIfDead:
{
  LDA Offspring1_Id : TAY
  LDA.w SprState, Y : BEQ .offspring1_dead
    JMP .not_dead
  .offspring1_dead

  LDA Offspring2_Id : TAY
  LDA.w SprState, Y : BEQ .offspring2_dead
    JMP .not_dead
  .offspring2_dead

  LDA.w SprMiscD, X : CMP.b #$02 : BEQ .dead
    LDA.b #$02 : STA.w SprMiscD, X
    LDY.b #$01 : JSR ApplyKydreeokGraphics
    JSR SpawnLeftHead 
    JSR SpawnRightHead
    RTS
  .dead
    LDA.b #$60 : STA.w SprTimerA, X
    LDA.b #$05 : STA.w SprAction, X
    LDA.b #$13 : STA $012C
  .not_dead
  RTS
}

; Head may respawn if the other isn't killed in time 
MaybeRespawnHead:
{
  LDA.w Offspring1_Id : TAY 
  LDA.w SprState, Y : BNE .offspring1_alive
      JSL GetRandomInt : AND.b #$7F : BNE .offspring1_alive
        JSR SpawnLeftHead
  .offspring1_alive
  LDA.w Offspring2_Id : TAY
  LDA.w SprState, Y : BNE .offspring2_alive
      JSL GetRandomInt : AND.b #$7F : BNE .offspring2_alive
        JSR SpawnRightHead
    .offspring2_alive
  RTS
}


; =========================================================

Sprite_Kydreeok_Main:
{
  LDA.w SprAction, X
  JSL   UseImplicitRegIndexedLocalJumpTable

  dw Kydreeok_Start        ; 00
  dw Kydreeok_StageControl ; 01
  dw Kydreeok_MoveXandY    ; 02
  dw Kydreeok_MoveXorY     ; 03
  dw Kydreeok_KeepWalking  ; 04
  dw Kydreeok_Dead         ; 05
  dw Kydreeok_Flying       ; 06

  ; -------------------------------------------------------
  ; 0x00
  Kydreeok_Start:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    LDA SprMiscD, X : BNE .go
      LDY #$00
      JSR ApplyKydreeokGraphics
      JSR ApplyPalette
      LDA.b #$01 : STA.w SprMiscD, X
    .go

    JSL Sprite_PlayerCantPassThrough

    LDA SprTimerA,            X : BNE .continue
      TXA : STA Kydreeok_Id
      LDA #$40 : STA.w SprTimerA, X
      %GotoAction(1)
    .continue

    RTS
  }

  ; -------------------------------------------------------
  ; 0x01
  Kydreeok_StageControl:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    STZ.w SprYSpeed : STZ.w SprXSpeed ;set velocitys to 0
    JSL MoveBody
    JSR StopIfOutOfBounds

    LDA SprTimerA, X : BNE .continue
      %GotoAction(2)
    .continue

    RTS
  }

  ; -------------------------------------------------------
  ; 0x02
  Kydreeok_MoveXandY:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    LDA $36
    JSL Sprite_ApplySpeedTowardsPlayer
    JSR StopIfOutOfBounds
    JSL MoveBody

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()

    %GotoAction(4)

    RTS
  }

  ; -------------------------------------------------------
  ; 0x03
  Kydreeok_MoveXorY:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    LDA $36 : STA $00
    JSL Sprite_ApplySpeedTowardsPlayerXOrY
    JSR StopIfOutOfBounds
    JSL MoveBody

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()

    %GotoAction(4)
    RTS
  }

  ; -------------------------------------------------------
  ; 0x04
  Kydreeok_KeepWalking:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 10)

    JSL GetRandomInt : AND.b #$7F : BNE .dont_fly
      LDA.b #$40 : STA.w SprTimerA, X
      %GotoAction(6)
      RTS
    .dont_fly

    PHX
    REP #$20

    ; Use a range of + 0x05 because being exact equal didnt trigger consistently 
    LDA $20 : SBC SprCachedY : CMP.w #$FFFB : BCC .notEqualY
      SEP #$20
      %GotoAction(2) ; Kydreeok_MoveXandY
      BRA .notEqualX
    .notEqualY

    ; Use a range of + 0x05 because being exact equal didnt trigger consistently 
    LDA $22 : SBC SprCachedX : CMP.w #$FFFB : BCC .notEqualX
      SEP #$20
      %GotoAction(2) ; Kydreeok_MoveXandY
    .notEqualX

    SEP #$20
    JSR StopIfOutOfBounds

    ;if both velocities are 0 go back to the Stalk_Player_XORY to re-set the course
    LDA.w SprYSpeed : BNE .notZero
      LDA.w SprXSpeed : BNE .notZero
        %GotoAction(3) ; Kydreeok_MoveXorY
    .notZero

    JSL MoveBody

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()

    PLX ;restores X

    RTS
  }

  Kydreeok_Dead:
  {
    
    LDA $1C : ORA.b #$01 : STA $1C ;turn on BG2 (Body)
    ; Flicker the body every other frame using the timer 
    LDA SprTimerA, X : AND.b #$01 : BEQ .flicker
      LDA $1C : AND.b #$FE : STA $1C ;turn off BG2 (Body)
    .flicker

    ; Spawn the explosion
    LDA.b #$00 ; SPRITE 00
    JSL Sprite_SpawnDynamically
    BMI .no_space

    LDA.b #$0B : STA.w $0AAA
    LDA.b #$04 : STA.w $0DD0,Y
    LDA.b #$03 : STA.w $0E40,Y
    LDA.b #$0C : STA.w $0F50,Y
    LDA.w $0FD8 : STA.w SprX,Y
    LDA.w $0FD9 : STA.w SprXH,Y
    LDA.w $0FDA : STA.w SprY,Y
    LDA.w $0FDB : STA.w SprYH,Y

    LDA.b #$1F
    STA.w $0DF0,Y
    STA.w $0D90,Y

    LDA.b #$02 : STA.w $0F20,Y
      
    .no_space

    LDA SprTimerA, X : BNE .continue
      STZ.w $0422
      STZ.w $0424
      LDA $1C : ORA.b #$01 : STA $1C ;turn on BG2 (Body)
      STZ.w $0DD0, X ; GG
      
    .continue
    RTS
  }

  Kydreeok_Flying:
  {
    %StartOnFrame(0)
    %PlayAnimation(0, 2, 05)

    LDA $36 : CLC : ADC.b #$02
    JSL Sprite_ApplySpeedTowardsPlayer
    JSR StopIfOutOfBounds
    JSL MoveBody

    LDA.b #$04 : STA.w SprHeight, X

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()

    LDA.w SprTimerA, X : BNE .continue
      STZ.w SprHeight, X
      %GotoAction(2)
    .continue
    RTS
  
  }

}

; =========================================================

Offspring1_Neck1_X = $19EA
Offspring1_Neck2_X = $19EC
Offspring1_Neck3_X = $19EE

Offspring1_Neck1_Y = $19EB
Offspring1_Neck2_Y = $19ED
Offspring1_Neck3_Y = $19EF

Offspring2_Neck1_X = $19F0
Offspring2_Neck2_X = $19F2
Offspring2_Neck3_X = $19F4

Offspring2_Neck1_Y = $19F1
Offspring2_Neck2_Y = $19F3
Offspring2_Neck3_Y = $19F5

Offspring3_Neck1_X = $1A78
Offspring3_Neck2_X = $1A7A
Offspring3_Neck3_X = $1A7C

Offspring3_Neck1_Y = $1A79
Offspring3_Neck2_Y = $1A7B
Offspring3_Neck3_Y = $1A7D

SpawnLeftHead:
{
  LDA #$CF

  JSL   Sprite_SpawnDynamically : BMI .return
    TYA   : STA Offspring1_Id
    ;store the sub-type
    LDA.b #$00 : STA $0E30, Y
        
    PHX
    ; code that controls where to spawn the offspring.
    REP #$20
    LDA SprCachedX : SEC : SBC.w #$0010
    SEP #$20
    STA.w SprX, Y : XBA : STA.w SprXH, Y

    REP #$20
    LDA SprCachedY : SEC : SBC.w #$000F
    SEP #$20
    STA.w SprY, Y : XBA : STA.w SprYH, Y

    LDA.w SprX,     Y
    STA.w SprMiscA, Y : STA.w $19EA : STA.w $19EC : STA.w $19EE
    LDA.w SprY, Y : STA.w $19EB : STA.w $19ED : STA.w $19EF : STA.w SprY, Y
    STA.w SprMiscB, Y

    TYX

    STZ.w SprYRound, X
    STZ.w SprXRound, X
    PLX
      
  .return
  RTS
}

; =========================================================

; SpawnCenterHead:
; {
;   LDA #$CF

;   JSL Sprite_SpawnDynamically : BMI .return
;     TYA : STA Offspring3_Id

;     ;store the sub-type
;     LDA.b #$02 : STA $0E30, Y

;     PHX
;     ; code that controls where to spawn the offspring.
;     REP #$20
;     LDA SprCachedX : CLC : ADC.w #$0004
;     SEP #$20
;     STA.w SprX, Y : XBA : STA.w SprXH, Y

;     REP #$20
;     LDA SprCachedY : SEC : SBC.w #$000F
;     SEP #$20
;     STA.w SprY, Y : XBA : STA.w SprYH, Y

;     LDA.w SprX, Y : STA.w SprX, Y
;     STA.w SprMiscA, Y : STA.w $1A78 : STA.w $1A7A : STA.w $1A7C
;     LDA.w SprY, Y : STA.w $1A79 : STA.w $1A7B : STA.w $1A7D : STA.w SprY, Y
;     STA.w SprMiscB, Y

;     TYX

;     STZ.w SprYRound, X
;     STZ.w SprXRound, X
;     PLX

;   .return
;   RTS
; }

; =========================================================

SpawnRightHead:
{
  LDA #$CF
  JSL Sprite_SpawnDynamically : BMI .return
    TYA : STA Offspring2_Id

    ;store the sub-type
    LDA.b #$01 : STA $0E30, Y
    PHX
    ; code that controls where to spawn the offspring.
    REP #$20
    LDA SprCachedX : CLC : ADC.w #$000D
    SEP #$20
    STA.w SprX, Y : XBA : STA.w SprXH, Y

    REP #$20
    LDA SprCachedY : SEC : SBC.w #$000F
    SEP #$20
    STA.w SprY, Y : XBA : STA.w SprYH, Y

    LDA.w SprX, Y : STA.w SprX, Y
    STA.w SprMiscA, Y : STA.w $19F0 : STA.w $19F2 : STA.w $19F4
    LDA.w SprY, Y : STA.w $19F1 : STA.w $19F3 : STA.w $19F5 : STA.w SprY, Y
    STA.w SprMiscB, Y

    TYX

    STZ.w SprYRound, X
    STZ.w SprXRound, X
    PLX
  .return
  RTS
}

; =========================================================
; Originally from Trinexx_MoveBody $1DB2E5

MoveBody:
{
  ; Handle the shell bg movement
  ; Trinexx_MoveBody
  LDA.w SprX, X : PHA
  LDA.w SprY, X : PHA

  JSL Sprite_Move

  PLA
  LDY.b #$00 : SEC : SBC.w SprY, X : STA.w $0310
  BPL .pos_y_low
  DEY

  .pos_y_low
  STY.w $0311

  ; -----------------------------------------------------

  PLA
  LDY.b #$00 : SEC : SBC.w SprX, X : STA.w $0312
  BPL .pos_x_low

  DEY

  .pos_x_low
  STY.w $0313

  ; -----------------------------------------------------

  LDA.b #$01 : STA.w $0428

  LDA.w SprY, X : SEC : SBC.b #$0C : STA.w $0DB0, X

  LDA.w $0B08 : SEC : SBC.w SprX, X
                CLC : ADC.b #$02 
                CMP.b #$04 : BCS .not_at_target

  LDA.w $0B09 : SEC : SBC.w SprY, X 
                CLC : ADC.b #$02
                CMP.b #$04 : BCS .not_at_target

  .adjust_phase ; Unused?
  LDA.b #$30 : STA.w $0DF0, X

  .not_at_target
  ; LayerEffect_Trinexx $0AFEF0
  REP   #$20
  LDA.w $0422 : CLC : ADC.w $0312 : STA.w $0422
  LDA.w $0424 : CLC : ADC.w $0310 : STA.w $0424
  STZ.w $0312 : STZ.w $0310
  SEP   #$20

  RTL
}

; =========================================================

StopIfOutOfBounds:
{
  ; Set A to 00 if outside of certain bounds
  REP #$20
  LDA SprCachedX : CMP.w #$0118 : BCS .not_out_of_bounds_Left
    SEP #$20
    LDA.w SprXSpeed : CMP.b #$7F : BCC .not_out_of_bounds_Left
      LDA.b #-10 : STA.w SprXSpeed : STA.w SprXRound
      LDA $19EA : SEC : SBC #$04 : STA $19EA
      LDA $19EC : SEC : SBC #$04 : STA $19EC
      LDA $19EE : SEC : SBC #$04 : STA $19EE

      LDA $19F0 : SEC : SBC #$04 : STA $19F0
      LDA $19F2 : SEC : SBC #$04 : STA $19F2
      LDA $19F4 : SEC : SBC #$04 : STA $19F4

  .not_out_of_bounds_Left
  SEP #$20

  REP #$20
  LDA SprCachedX : CMP.w #$01D8 : BCC .not_out_of_bounds_Right
    SEP #$20
    LDA.w SprXSpeed : CMP.b #$80 : BCS .not_out_of_bounds_Right
      LDA.b #$00 : STA.w SprXSpeed : STA.w SprXRound
      LDA $19EA : CLC : ADC #$04 : STA $19EA
      LDA $19EC : CLC : ADC #$04 : STA $19EC
      LDA $19EE : CLC : ADC #$04 : STA $19EE

      LDA $19F0 : CLC : ADC #$04 : STA $19F0
      LDA $19F2 : CLC : ADC #$04 : STA $19F2
      LDA $19F4 : CLC : ADC #$04 : STA $19F4

  .not_out_of_bounds_Right
  SEP #$20

  ; Upper bound
  REP #$20
  LDA SprCachedY : CMP.w #$0020 : BCS .not_out_of_bounds_Up
    SEP #$20
    LDA.w SprYSpeed : CMP.b #$7F : BCC .not_out_of_bounds_Up
      LDA.b #$00 : STA.w SprYSpeed : STA.w SprYRound
      LDA $19EA : SEC : SBC #$04 : STA $19EA
      LDA $19EC : SEC : SBC #$04 : STA $19EC
      LDA $19EE : SEC : SBC #$04 : STA $19EE

  .not_out_of_bounds_Up
  SEP #$20

  REP   #$20
  LDA   SprCachedY : CMP.w #$00D0 : BCC .not_out_of_bounds_Down
    SEP #$20
    LDA.w SprYSpeed : CMP.b #$80 : BCS .not_out_of_bounds_Down
        LDA.b #-10 : STA.w SprYSpeed : STA.w SprYRound ; Reverse the direction

        ; Modify the neck position
        ; Makes them move away from each other a bit
        LDA $19EA : SEC : SBC #$04 : STA $19EA
        LDA $19EC : SEC : SBC #$04 : STA $19EC
        LDA $19EE : SEC : SBC #$04 : STA $19EE

        LDA $19F0 : CLC : ADC #$04 : STA $19F0
        LDA $19F2 : CLC : ADC #$04 : STA $19F2
        LDA $19F4 : CLC : ADC #$04 : STA $19F4

  .not_out_of_bounds_Down
  SEP #$20

  RTS
}

; =========================================================

ApplyPalette:
{
    REP #$20 ;Set A in 16bit mode

    ;note, this uses adresses like 7EC300 and not 7EC500 because the game 
    ;will fade the colors into 7EC500 based on the colors found in 7EC300

    LDA #$7FFF : STA $7EC5E2 ;BG2
    LDA #$319B : STA $7EC5E4
    LDA #$15B6 : STA $7EC5E6
    LDA #$369E : STA $7EC5E8
    LDA #$14A5 : STA $7EC5EA
    LDA #$7E56 : STA $7EC5EC
    LDA #$65CA : STA $7EC5EE
    ; LDA #$14A5 : STA $7EC5F0
    ; LDA #$7E56 : STA $7EC5F2 
    ; LDA #$65CA : STA $7EC5F4

    INC $15
 
    SEP #$20 ;Set A in 8bit mode

    RTS
}

ApplyEndPalette:
{
    REP #$20 ;Set A in 16bit mode

    ;note, this uses adresses like 7EC300 and not 7EC500 because the game 
    ;will fade the colors into 7EC500 based on the colors found in 7EC300

    LDA #$1084 : STA $7EC5E2 ;BG2
    LDA #$210D : STA $7EC5E4
    LDA #$3191 : STA $7EC5E6
    LDA #$4E78 : STA $7EC5E8
    LDA #$14A5 : STA $7EC5EA
    LDA #$7E56 : STA $7EC5EC
    LDA #$65CA : STA $7EC5EE
    ; LDA #$14A5 : STA $7EC5F0
    ; LDA #$7E56 : STA $7EC5F2 
    ; LDA #$65CA : STA $7EC5F4

    INC $15
 
    SEP #$20 ;Set A in 8bit mode

    RTS
}

; =========================================================

Sprite_Kydreeok_Draw:
{
    JSL Sprite_PrepOamCoord
    ; JSL Sprite_OAM_AllocateDeferToPlayer
    LDA.b #$08
    JSL OAM_AllocateFromRegionE

    LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
    LDA .start_index, Y : STA $06

    PHX
    LDX   .nbr_of_tiles, Y ;amount of tiles -1
    LDY.b #$00
  .next_tile

    PHX ; Save current Tile Index?
        
    TXA : CLC : ADC $06 ; Add Animation Index Offset

    PHA ; Keep the value with animation index offset?

    ASL A : TAX

    REP #$20

    LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA $0E
    INY
    LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
    CLC   : ADC #$0010 : CMP.w #$0100
    SEP   #$20
    BCC   .on_screen_y

    LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
    STA   $0E
  .on_screen_y

    PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
    INY
    LDA .chr, X : STA ($90), Y
    INY
    LDA .properties, X : STA ($90), Y

    PHY 
        
    TYA : LSR #2 : TAY
        
    LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer
        
    PLY : INY
        
    PLX : DEX : BPL .next_tile

    PLX

    RTS

  .start_index
    db $00, $08, $10
  .nbr_of_tiles
    db 7, 7, 7
  .x_offsets
    dw -20, -20, 20, 20, -16, -16, 16, 16
    dw -20, -36, 20, 36, -16, -16, 16, 16
    dw -20, -20, 20, 20, -16, -16, 16, 16
  .y_offsets
    dw -52, -36, -52, -36, -8, 8, -8, 8
    dw -36, -36, -36, -36, -6, 10, -8, 8
    dw -36, -20, -36, -20, -8, 8, -6, 10
  .chr
    db $CE, $EE, $CE, $EE, $00, $20, $00, $20
    db $0E, $0C, $0E, $0C, $00, $20, $00, $20
    db $CC, $EC, $CC, $EC, $00, $20, $00, $20
  .properties
    db $39, $39, $79, $79, $39, $39, $79, $79
    db $39, $39, $79, $79, $39, $39, $79, $79
    db $39, $39, $79, $79, $39, $39, $79, $79
}

ApplyKydreeokGraphics:
{
    PHX 
    REP #$20               ; A = 16, XY = 8
    LDX #$80 : STX $2100   ; turn the screen off (required)
    LDX #$80 : STX $2115   ; Set the video port register every time we write it increase by 1
    LDA #$5000 : STA $2116 ; Destination of the DMA $5800 in vram <- this need to be divided by 2
    LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register 
                           ; "001 => 2 registers write once (2 bytes: p, p+1)"
    CPY #$01 : BEQ .phase2
      LDA.w #KydreeokGraphics : STA $4302
      LDX.b #KydreeokGraphics>>16 : STX $4304
      JMP .continue
    .phase2
    LDA.w #KydreeokPhase2Graphics : STA $4302
    LDX.b #KydreeokPhase2Graphics>>16 : STX $4304
    .continue
    LDA   #$2000 : STA $4305                ; Size of the transfer 4 sheets of $800 each
    LDX   #$01 : STX $420B                  ; Do the DMA 
    LDX #$0F : STX $2100                    ; Turn the screen back on
    SEP #$30
    PLX
    RTS

  KydreeokGraphics:
    incbin kydreeok.bin

  KydreeokPhase2Graphics:
    incbin kydreeok_phase2.bin
}
