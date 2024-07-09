; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_Manhandla
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 01  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow 
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_Manhandla_Prep, Sprite_Manhandla_Long)

; =========================================================

Sprite_Manhandla_Long:
{
  PHB : PHK : PLB

  JSR Sprite_Manhandla_CheckForNextPhaseOrDeath

  LDA.w SprMiscD, X : CMP.b #$02 : BCC .phase1
    JSR Sprite_BigChuchu_Draw
    JMP .continue
  .phase1
    JSR Sprite_Manhandla_Draw
  .continue
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_Manhandla_Main ; Call the main sprite code
  
  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

pushpc

; Sprite_DoTheDeath#PrepareEnemyDrop.post_death_stuff
org $06FA25
  #_06FA25: LDA.w $0E20,X
  #_06FA28: CMP.b #$88

pullpc

; =========================================================

Sprite_Manhandla_Prep:
{
  PHB : PHK : PLB
    
  LDA.b #$04 : STA $36          ; Stores initial movement speeds
  LDA.b #$06 : STA $0428        ; Allows BG1 to move
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #$80 : STA.w SprHealth, X
  LDA.w SprSubtype, X : STA.w SprAction, X

  PLB
  RTL
}

; If both the heads are dead, it's okay for this sprite to "die"
; Then we transition to the chuchu phase.
Sprite_Manhandla_CheckForNextPhaseOrDeath:
{
  ; All three heads need to be dead before we become big chuchu
  LDA Offspring1_Id : TAY
  LDA.w SprState, Y : BEQ .offspring1_dead
    JMP .not_dead
  .offspring1_dead
  LDA.b #$05 : STA.w $36

  LDA Offspring2_Id : TAY
  LDA.w SprState, Y : BEQ .offspring2_dead
    JMP .not_dead
  .offspring2_dead
  LDA.b #$06 : STA.w $36

  LDA Offspring3_Id : TAY
  LDA.w SprState, Y : BEQ .offspring3_dead
    JMP .not_dead
  .offspring3_dead
  LDA.b #$07 : STA.w $36
  
  LDA.w SprMiscD, X : BNE .phase2
      LDA.b #$01 : STA.w SprMiscD, X 
      LDA.b #$40 : STA.w SprTimerA, X 
      LDA.b #$40 : STA.w SprHealth, X ; Refill the health
      LDA.b #$08 : STA.w SprNbrOAM, X ; Give more OAM 
      LDA.b #$07 : STA.w SprAction, X ; Chuchu Emerge
      LDA.b #$0A : STA.w $36
    .not_dead
    RTS
  .phase2
  LDA.w SprMiscD, X : CMP.b #$03 : BEQ +
    LDA.w SprHealth, X : CMP.b #$04 : BCS .phase2_not_dead
      LDA.b #$50 : STA.w SprTimerA, X 
      LDA.b #$09 : STA.w SprAction, X
      LDA.b #$13 : STA $012C
      LDA.b #$04 : STA.w SprMiscD, X
      LDA.b #$0A : STA.w $36
    .phase2_not_dead
  +
  
  RTS
}

; =========================================================

macro SetLeftHeadPos()
    REP #$20
    LDA SprCachedX : SEC : SBC.w #$0016
    SEP #$20
    STA.w SprX, Y : XBA : STA.w SprXH, Y

    REP #$20
    LDA SprCachedY : SEC : SBC.w #$000F
    SEP #$20
    STA.w SprY, Y : XBA : STA.w SprYH, Y
endmacro 

macro SetRightHeadPos()
    REP #$20
    LDA SprCachedX : CLC : ADC.w #$0016
    SEP #$20
    STA.w SprX, Y : XBA : STA.w SprXH, Y

    REP #$20
    LDA SprCachedY : SEC : SBC.w #$000F
    SEP #$20
    STA.w SprY, Y : XBA : STA.w SprYH, Y
endmacro

macro SetCenterHeadPos() 
    REP #$20
    LDA SprCachedX
    SEP #$20
    STA.w SprX, Y : XBA : STA.w SprXH, Y

    REP #$20
    LDA SprCachedY 
    SEP #$20
    STA.w SprY, Y : XBA : STA.w SprYH, Y
endmacro

Sprite_Manhandla_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw Manhandla_Intro
  dw Manhandla_FrontHead ; 0x01
  dw Manhandla_LeftHead  ; 0x02
  dw Manhandla_RightHead ; 0x03
  dw BigChuchu_Main      ; 0x04 
  dw Flower_Flicker      ; 0x05
  dw Manhandla_Body      ; 0x06
  dw BigChuchu_Emerge    ; 0x07
  dw BigChuchu_Flower    ; 0x08
  dw BigChuchu_Dead      ; 0x09
  dw ChuchuBlast         ; 0x0A

  Manhandla_Intro:
  {
    LDA.w SprSubtype, X : BNE .not_main
      LDA.w SprX, X : SEC : SBC.b #$04 : STA.w SprX, X
      JSR SpawnLeftManhandlaHead
      JSR SpawnRightManhandlaHead
      JSR SpawnCenterMandhandlaHead
      LDA.b #$06 : STA.w SprFrame, X 
      %GotoAction(6) ; Manhandla_Body
      RTS
    .not_main
    
    LDA.w SprSubtype, X : STA.w SprAction, X
    RTS
  }

  Manhandla_FrontHead:
  {
    %PlayAnimation(0,1,16)

    JSL Sprite_Move
    JSL Sprite_DamageFlash_Long

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()

    RTS
  }

  Manhandla_LeftHead:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,16)

    JSL Sprite_Move
    JSL Sprite_DamageFlash_Long

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    
    RTS
  }

  Manhandla_RightHead:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,16)

    PHX
    JSL Sprite_Move
    JSL Sprite_DamageFlash_Long

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    PLX
    
    RTS
  }

  BigChuchu_Main:
  {
    %PlayAnimation(0,2,16)

    LDA.w SprTimerC, X : BEQ +
      RTS
    +

    JSL GetRandomInt : AND.b #$3F : BNE ++
      JSR Chuchu_SpawnBlast
      ; JSR Mothula_SpawnBeams
    ++

    PHX
    JSR Sprite_Manhandla_Move
    JSL Sprite_DamageFlash_Long

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    PLX

    LDY.w Offspring3_Id
    LDA.w SprType, Y : CMP.b #$88 : BNE .not_head3
    LDA.w SprState, Y : BEQ .offspring3_dead
      %SetCenterHeadPos()
      .offspring3_dead
    .not_head3

    RTS
  }

  Flower_Flicker:
  {
    %PlayAnimation(11, 12, 10)
    LDA $1C : ORA.b #$01 : STA $1C ;turn on BG2 (Body)
    ; Flicker the body every other frame using the timer 
    LDA SprTimerA, X : AND.b #$01 : BEQ .flicker
      LDA $1C : AND.b #$FE : STA $1C ;turn off BG2 (Body)
    .flicker

    LDA SprTimerA, X : BNE .continue
      STZ.w $0422
      STZ.w $0424
      LDA $1C : AND.b #$FE : STA $1C ;turn off BG2 (Body)
      %GotoAction($04)

      LDA.b #$10 : STA.w SprTimerC, X
      LDA.b #$8D : STA.w SprHitbox, X 
      
      LDA #$88
      JSL Sprite_SpawnDynamically : BMI .return
        TYA : STA Offspring3_Id

        PHX
        %SetCenterHeadPos()

        LDA.b #$08 : STA.w SprSubtype, Y
        STA.w SprAction, Y
        LDA.b #$20 : STA.w SprHealth, Y
        LDA.b #$07 : STA.w SprNbrOAM, Y

        LDA.w SprY, Y : CLC : ADC.b #$20 : STA.w SprY, Y
        LDA.b #$10 : STA.w SprTimerC, Y

        TYX

        STZ.w SprYRound, X
        STZ.w SprXRound, X
        PLX
        

      .return

    .continue
    RTS
  }

  Manhandla_Body:
  {
    %PlayAnimation(6,8,16)

    PHX
    JSR Sprite_Manhandla_Move
    JSL Sprite_DamageFlash_Long

    JSL GetRandomInt : AND.b #$7F : BNE + 
      JSL GetRandomInt : AND.b #$04 : BNE +
      JSR Mothula_SpawnBeams
    +

    JSL Sprite_CheckDamageFromPlayer
    %DoDamageToPlayerSameLayerOnContact()
    
    LDY.w Offspring1_Id
    LDA.w SprType, Y : CMP.b #$88 : BNE .not_head
    LDA.w SprState, Y : BEQ .offspring1_dead
      %SetLeftHeadPos()
    .offspring1_dead
    .not_head
    LDY.w Offspring2_Id
    LDA.w SprType, Y : CMP.b #$88 : BNE .not_head2
    LDA.w SprState, Y : BEQ .offspring2_dead
      %SetRightHeadPos()
    .offspring2_dead
    .not_head2

    LDY.w Offspring3_Id
    LDA.w SprType, Y : CMP.b #$88 : BNE .not_head3
    LDA.w SprState, Y : BEQ .offspring3_dead
      %SetCenterHeadPos()
      .offspring3_dead
    .not_head3

    PLX 

    RTS
  }

  BigChuchu_Emerge:
  {
    %PlayAnimation(9, 12, 10)

    JSL Sprite_DamageFlash_Long

    LDA.w SprTimerA, X : BNE + 
      LDA.b #$02 : STA.w SprMiscD, X ; Set phase flag 
      LDA.b #$20 : STA.w SprTimerA, X 
      %GotoAction($05)
    +

    RTS
  }

  BigChuchu_Flower:
  {
    %PlayAnimation(12, 12, 1)

    JSL Sprite_DamageFlash_Long

    LDA.w SprTimerC, X : BEQ +
        LDA.w SprY, X : DEC : STA.w SprY, X
    +

    RTS
  }

  BigChuchu_Dead:
  {
    #_068517: LDA.b #$FF
    #_068519: STA.w $0BC0, X
    LDA.b #$04 : STA.w SprState, X 
    STZ.w SprHealth, X
    RTS
  }

  ChuchuBlast:
  {
    %PlayAnimation(3, 4, 4)

    JSL Sprite_Move

    %DoDamageToPlayerSameLayerOnContact()

    RTS
  }
}

Sprite_Manhandla_Move:
{
  LDA.w SprMiscC, X 
  JSL UseImplicitRegIndexedLocalJumpTable

  dw StageControl
  dw MoveXandY
  dw MoveXorY
  dw KeepWalking

  StageControl:
  {
    STZ.w SprYSpeed : STZ.w SprXSpeed ;set velocitys to 0
    JSL MoveBody
    JSR Manhandla_StopIfOutOfBounds
    LDA SprTimerA, X : BNE .continue
      INC.w SprMiscC, X
    .continue
    RTS
  }

  MoveXandY:
  {
    LDA $36
    JSL Sprite_ApplySpeedTowardsPlayer
    JSR Manhandla_StopIfOutOfBounds
    JSL MoveBody

    INC.w SprMiscC, X
    RTS
  }

  MoveXorY:
  {
    LDA $36 : STA $00
    JSL Sprite_ApplySpeedTowardsPlayerXOrY
    JSR Manhandla_StopIfOutOfBounds
    JSL MoveBody

    INC.w SprMiscC, X
    RTS
  }

  KeepWalking:
  {
    PHX
    REP #$20

    ; Use a range of + 0x05 because being exact equal didnt trigger consistently 
    LDA $20 : SBC SprCachedY : CMP.w #$FFFB : BCC .notEqualY
      SEP #$20
      LDA.b #$02 : STA.w SprMiscC, X
      
      BRA .notEqualX
    .notEqualY

    ; Use a range of + 0x05 because being exact equal didnt trigger consistently 
    LDA $22 : SBC SprCachedX : CMP.w #$FFFB : BCC .notEqualX
      SEP #$20
      LDA.b #$02 : STA.w SprMiscC, X
    .notEqualX

    SEP #$20
    JSR Manhandla_StopIfOutOfBounds

    ;if both velocities are 0 go back to the Stalk_Player_XORY to re-set the course
    LDA.w SprYSpeed : BNE .notZero
      LDA.w SprXSpeed : BNE .notZero
        LDA.b #$03 : STA.w SprMiscC, X
    .notZero

    JSL MoveBody

    PLX ;restores X
    RTS
  }
}

Manhandla_StopIfOutOfBounds:
{
  ; Set A to 00 if outside of certain bounds
  REP #$20
  LDA SprCachedX : CMP.w #$153A : BCS .not_out_of_bounds_Left
    SEP #$20
    LDA.w SprXSpeed : CMP.b #$7F : BCC .not_out_of_bounds_Left
      LDA.b #-08 : STA.w SprXSpeed : STA.w SprXRound

  .not_out_of_bounds_Left
  SEP #$20

  REP #$20
  LDA SprCachedX : CMP.w #$15C8 : BCC .not_out_of_bounds_Right
    SEP #$20
    LDA.w SprXSpeed : CMP.b #$80 : BCS .not_out_of_bounds_Right
      LDA.b #$08 : STA.w SprXSpeed : STA.w SprXRound

  .not_out_of_bounds_Right
  SEP #$20

  ; Upper bound
  REP #$20
  LDA SprCachedY : CMP.w #$0B3A : BCS .not_out_of_bounds_Up
    SEP #$20
    LDA.w SprYSpeed : CMP.b #$7F : BCC .not_out_of_bounds_Up
      LDA.b #$08 : STA.w SprYSpeed : STA.w SprYRound

  .not_out_of_bounds_Up
  SEP #$20

  REP   #$20
  LDA   SprCachedY : CMP.w #$0BA6 : BCC .not_out_of_bounds_Down
    SEP #$20
    LDA.w SprYSpeed : CMP.b #$80 : BCS .not_out_of_bounds_Down
        LDA.b #-08 : STA.w SprYSpeed : STA.w SprYRound ; Reverse the direction

  .not_out_of_bounds_Down
  SEP #$20

  RTS
}

; =========================================================

Sprite_Manhandla_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
      
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX 

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E 
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY 
      
  TYA : LSR #2 : TAY
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS


  ; =========================================================

  .start_index
  db $00, $02, $04, $08, $0C, $10, $14, $17, $1A, $1D, $23, $29, $33
  .nbr_of_tiles
  db 1, 1, 3, 3, 3, 3, 2, 2, 2, 5, 5, 9, 7
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 8, 8, 0
  dw 0, 8, 0, 8
  dw 0, -8, -8, 0
  dw 0, -8, 0, -8
  dw -12, -4, 12
  dw -12, -4, 12
  dw 12, 4, -12

  dw -12, -4, -12, -4, 12, 12
  dw -12, -4, -12, -4, 12, 12
  dw -16, -8, -16, -8, 16, 8, 16, 8, -12, 12
  dw -16, -8, -16, -8, 16, 8, 16, 8
  .y_offsets
  dw -8, 8
  dw 0, 16
  dw -4, -4, 12, 12
  dw -4, -4, 12, 12
  dw -4, -4, 12, 12
  dw -4, -4, 12, 12
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, 0, 0

  dw -28, -28, -12, -12, -28, -12
  dw -24, -24, -8, -8, -24, -8
  dw -24, -24, -8, -8, -8, -8, -24, -24, -32, -32
  dw -24, -24, -8, -8, -8, -8, -24, -24
  .chr
  db $00, $20
  db $02, $22
  db $04, $05, $25, $24
  db $07, $08, $27, $28
  db $04, $05, $25, $24
  db $07, $08, $27, $28
  db $40, $41, $40
  db $43, $44, $46
  db $43, $44, $46

  db $4D, $4E, $6D, $6E, $4D, $6D
  db $8D, $8E, $AD, $AE, $8D, $AD
  db $CD, $CE, $ED, $EE, $ED, $EE, $CD, $CE, $AE, $AE
  db $CD, $CE, $ED, $EE, $ED, $EE, $CD, $CE
  .properties
  db $33, $33
  db $33, $33
  db $33, $33, $33, $33
  db $33, $33, $33, $33
  db $73, $73, $73, $73
  db $73, $73, $73, $73
  db $33, $33, $73
  db $33, $33, $73
  db $73, $73, $33

  db $33, $33, $33, $33, $73, $73
  db $33, $33, $33, $33, $73, $73
  db $33, $33, $33, $33, $73, $73, $73, $73, $32, $72
  db $33, $33, $33, $33, $73, $73, $73, $73
  .sizes
  db $02, $02
  db $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02
  db $02, $02, $02

  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02
}

Sprite_BigChuchu_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY ; Animation Frame
  LDA.w .start_index, Y : STA $06
  LDA.w SprFlash, X : STA $08

  PHX
  LDX .nbr_of_tiles, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
      
  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX 

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E 
  INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC : ADC #$0010 : CMP.w #$0100
  SEP #$20
  BCC .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY
  LDA .chr, X : STA ($90), Y
  INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY 
      
  TYA : LSR #2 : TAY
      
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
      
  PLY : INY
      
  PLX : DEX : BPL .nextTile

  PLX

  RTS

  ; =======================================================
  .start_index
  db $00, $09, $12, $1B, $1C
  .nbr_of_tiles
  db 8, 8, 8, 0, 0
  .x_offsets
  dw -12, 4, 20, -12, 4, 12, -12, 4, 12
  dw -12, 4, 20, -12, 4, 12, -12, 4, 12
  dw -12, 4, 20, -12, 4, 12, -8, 8, 16
  dw 0
  dw 0
  .y_offsets
  dw 8, 8, 8, 16, 16, 16, 32, 32, 32
  dw 8, 8, 8, 16, 16, 16, 32, 32, 32
  dw 8, 8, 8, 16, 16, 16, 32, 32, 32
  dw 0
  dw 0
  .chr
  db $80, $82, $84, $90, $92, $93, $B0, $B2, $B3
  db $80, $82, $84, $90, $92, $93, $D0, $D2, $D3
  db $80, $82, $84, $90, $92, $93, $D6, $D8, $D9
  db $88
  db $A8
  .properties
  db $33, $33, $33, $33, $33, $33, $33, $33, $33
  db $33, $33, $33, $33, $33, $33, $33, $33, $33
  db $33, $33, $33, $33, $33, $33, $33, $33, $33
  db $33
  db $33
  .sizes
  db $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02
  db $02
}

Chuchu_SpawnBlast:
{
  PHX
  LDA.b #$88
  JSL Sprite_SpawnDynamically : BMI .return
    
    LDA.b #$0A : STA.w SprSubtype, Y
    STA.w SprAction, Y

    JSL GetRandomInt : AND.b #$01 : TAX

    LDA.w .speed_and_offset_x, X : STA.w SprXSpeed, Y
    LDA.w SprX, Y : CLC : ADC.w .speed_and_offset_x, X : STA.w SprX, Y
    STA.w SprXRound, Y
    LDA.w .speed_y, X : STA.w SprYSpeed, Y
    STA.w SprYRound, Y
    LDA.b #$02 : STA.w SprMiscD, Y
    LDA.b #$00 : STA.w SprTileDie, Y
    LDA.b #$40 : STA.w SprProps, Y
    LDA.b #$04 : STA.w SprFrame, Y 
    LDA.b #$10 : STA.w SprTimerB, Y
    LDA.b #$00 : STA.w SprNbrOAM, Y
    LDA.b #$03 : STA.w SprHitbox, Y

  .return 
  PLX
  RTS


  .speed_and_offset_x
  db -16, 16

  .speed_y
  db  24, 24
}

Mothula_SpawnBeams:
{
  LDA.b #$36 ; SFX3.36
  JSL $0DBB8A ; SpriteSFX_QueueSFX3WithPan

  LDA.b #$02
  STA.w $0FB5

  .next_spawn
  LDA.b #$89 ; SPRITE 89
  JSL Sprite_SpawnDynamically
  BMI .no_space

  JSL Sprite_SetSpawnedCoordinates

  LDA.b $02 : SEC : SBC.b $04

  CLC : ADC.b #$03 : STA.w SprY,Y

  LDA.b #$10 : STA.w $0DF0,Y : STA.w $0BA0,Y

  PHX

  LDX.w $0FB5

  LDA.b $00 : CLC : ADC.w .speed_and_offset_x,X
  STA.w SprX,Y

  LDA.w .speed_and_offset_x,X : STA.w $0D50,Y

  LDA.w .speed_y,X
  STA.w $0D40,Y

  LDA.b #$00
  STA.w $0F70,Y

  PLX

  .no_space
  DEC.w $0FB5
  BPL .next_spawn

  RTS
  .speed_and_offset_x
  db -20,   0,  20

  .speed_y
  db  24,  32,  24
}

SpawnLeftManhandlaHead:
{
  LDA #$88
  JSL   Sprite_SpawnDynamically : BMI .return
    TYA   : STA Offspring1_Id

    PHX
    %SetLeftHeadPos()
    ; store the sub-type
    LDA.b #$03 : STA.w SprSubtype, Y
    STA.w SprAction, Y
    LDA.b #$14 : STA.w SprHealth, Y
    LDA.b #$90 : STA.w SprTileDie, Y
    LDA.w SprGfxProps : ORA.b #$80 : STA.w SprGfxProps, Y
    TYX

    STZ.w SprYRound, X
    STZ.w SprXRound, X
    PLX
      
  .return
  RTS
}

SpawnRightManhandlaHead:
{
  LDA #$88
  JSL Sprite_SpawnDynamically : BMI .return
    TYA : STA Offspring2_Id

    PHX
    %SetRightHeadPos()

    LDA.b #$02
    STA.w SprSubtype, Y
    LDA.b #$14 : STA.w SprHealth, Y
    LDA.b #$90 : STA.w SprTileDie, Y
    LDA.w SprGfxProps : AND.b #$80 : STA.w SprGfxProps, Y
    TYX

    STZ.w SprYRound, X
    STZ.w SprXRound, X
    PLX
  .return
  RTS
}

SpawnCenterMandhandlaHead:
{
  LDA #$88
  JSL Sprite_SpawnDynamically : BMI .return
    TYA : STA Offspring3_Id

    PHX
    %SetCenterHeadPos()

    LDA.b #$01
    STA.w SprSubtype, Y
    LDA.b #$14 : STA.w SprHealth, Y
    LDA.b #$90 : STA.w SprTileDie, Y
    LDA.w SprGfxProps : AND.b #$80 : STA.w SprGfxProps, Y

    TYX

    STZ.w SprYRound, X
    STZ.w SprXRound, X
    PLX
  .return
  RTS
}

ApplyManhandlaPalette:
{
    REP #$20 ;Set A in 16bit mode

    ;note, this uses adresses like 7EC300 and not 7EC500 because the game 
    ;will fade the colors into 7EC500 based on the colors found in 7EC300

    LDA #$7FFF : STA $7EC5E2 ;BG2
    LDA #$08D9 : STA $7EC5E4
    LDA #$1E07 : STA $7EC5E6
    LDA #$4ACA : STA $7EC5E8
    LDA #$14A5 : STA $7EC5EA
    LDA #$133F : STA $7EC5EC
    LDA #$19DF : STA $7EC5EE

    INC $15
 
    SEP #$20 ;Set A in 8bit mode

    RTS
}

ApplyManhandlaGraphics:
{
    PHX 
    REP #$20               ; A = 16, XY = 8
    LDX #$80 : STX $2100   ; turn the screen off (required)
    LDX #$80 : STX $2115   ; Set the video port register every time we write it increase by 1
    LDA #$5000 : STA $2116 ; Destination of the DMA $5800 in vram <- this need to be divided by 2
    LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register 
                           ; "001 => 2 registers write once (2 bytes: p, p+1)"

    LDA.w #ManhandlaGraphics : STA $4302
    LDX.b #ManhandlaGraphics>>16 : STX $4304

    LDA   #$2000 : STA $4305                ; Size of the transfer 4 sheets of $800 each
    LDX   #$01 : STX $420B                  ; Do the DMA 
    LDX #$0F : STX $2100                    ; Turn the screen back on
    SEP #$30
    PLX
    RTS

  ManhandlaGraphics:
    incbin manhandla.bin
}
