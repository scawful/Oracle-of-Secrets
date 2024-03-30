; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = $7A ; The sprite ID you are overwriting (HEX)
!NbrTiles           = 10  ; Number of tiles used in a frame
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

  .SpriteIsNotActive
    PLB ; Get back the databank we stored previously
    RTL ; Go back to original code
}

; =========================================================
; TODO: Handle boss death based on left and right head health

Sprite_Kydreeok_Prep:
{
  PHB : PHK : PLB
    
  LDA   #$40 : STA SprTimerA, X
  LDA.b #$08 : STA $36          ; Stores initial movement speeds
  LDA.b #$06 : STA $0428        ; Allows BG1 to move

  ; Cache the origin position of the sprite.
  LDA SprX, X : STA SprMiscA, X 
  LDA SprY, X : STA SprMiscB, X

  JSR SpawnLeftHead : JSR SpawnRightHead

  STZ.w Neck1_OffsetX : STZ.w Neck1_OffsetY
  STZ.w Neck2_OffsetX : STZ.w Neck2_OffsetY

  PLB
  RTL
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

  ; -------------------------------------------------------
  ; 0x00
  Kydreeok_Start:
  {
      %StartOnFrame(0)
      %PlayAnimation(0, 2, 10)

      JSR ApplyPalette
      JSL Sprite_PlayerCantPassThrough

      LDA SprTimerA,            X : BNE .continue
      TXA : STA Kydreeok_Id
      LDA #$40 : STA SprTimerA, X
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

      PHX

      STZ $0D40 : STZ $0D50 ;set velocitys to 0
      JSR MoveBody

      JSL Sprite_BounceFromTileCollision ; 
      JSR StopIfOutOfBounds

      LDA SprTimerA, X : BNE .continue
        %GotoAction(2)
    .continue

      PLX

      RTS
  }

  ; -------------------------------------------------------
  ; 0x02
  Kydreeok_MoveXandY:
  {
      %StartOnFrame(0)
      %PlayAnimation(0, 2, 10)

      PHX ;saves X so we can use it later

      LDA $36
      JSL Sprite_ApplySpeedTowardsPlayer
      JSL Sprite_BounceFromTileCollision ; JSR StopIfOutOfBounds
      JSR StopIfOutOfBounds
      JSR MoveBody

      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()

      PLX ;restores X

      %GotoAction(4)

      RTS
  }

  ; -------------------------------------------------------
  ; 0x03
  Kydreeok_MoveXorY:
  {
      %StartOnFrame(0)
      %PlayAnimation(0, 2, 10)

      PHX
      LDA $36 : STA $00
      JSR Sprite_ApplySpeedTowardsPlayerXOrY
      JSL Sprite_BounceFromTileCollision     ; JSR StopIfOutOfBounds
      JSR StopIfOutOfBounds
      JSR MoveBody

      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()
      PLX

      %GotoAction(4)
      RTS
  }

  ; -------------------------------------------------------
  ; 0x04
  Kydreeok_KeepWalking:
  {
      %StartOnFrame(0)
      %PlayAnimation(0, 2, 10)

      PHX
      REP #$20

      ; Use a range of + 0x05 because being exact equal didnt trigger consistently 
      LDA $20 : SBC $0FDA : CMP.w #$FFFB : BCC .notEqualY
        
        SEP #$20
        %GotoAction(2) ; Kydreeok_MoveXandY
        BRA .notEqualX

    .notEqualY

      ; Use a range of + 0x05 because being exact equal didnt trigger consistently 
      LDA $22 : SBC $0FD8 : CMP.w #$FFFB : BCC .notEqualX
        SEP #$20
        %GotoAction(2) ; Kydreeok_MoveXandY

    .notEqualX
      SEP #$20
      JSL Sprite_BounceFromTileCollision ; JSR StopIfOutOfBounds

      ;if both velocities are 0 go back to the Stalk_Player_XORY to re-set the course
      LDA $0D40 : BNE .notZero
      LDA $0D50 : BNE .notZero
        %GotoAction(3) ; Kydreeok_MoveXorY

    .notZero

      JSR MoveBody

      JSL Sprite_CheckDamageFromPlayerLong
      %DoDamageToPlayerSameLayerOnContact()

      PLX ;restores X

      RTS
  }

}

; =========================================================

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
    LDA $0FD8 : SEC : SBC.w #$000F
    SEP #$20
    STA $0D10, Y : XBA : STA $0D30, Y

    REP #$20
    LDA $0FDA : SEC : SBC.w #$000F
    SEP #$20
    STA $0D00, Y : XBA : STA $0D20, Y

    LDA.w SprX,     Y
    STA.w SprMiscA, Y : STA.w $19EA : STA.w $19EC : STA.w $19EE
    LDA.w SprY, Y : STA.w $19EB : STA.w $19ED : STA.w $19EF : STA.w SprY, Y
    STA.w SprMiscB, Y

    TYX

    STZ $0D60, X
    STZ $0D70, X
    PLX
        
  .return
    RTS
}

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
    LDA $0FD8 : CLC : ADC.w #$000C
    SEP #$20
    STA $0D10, Y : XBA : STA $0D30, Y

    REP #$20
    LDA $0FDA : SEC : SBC.w #$000F
    SEP #$20
    STA $0D00, Y : XBA : STA $0D20, Y

    LDA.w SprX, Y : STA.w SprX, Y
    STA.w SprMiscA, Y : STA.w $19F0 : STA.w $19F2 : STA.w $19F4
    LDA.w SprY, Y : STA.w $19F1 : STA.w $19F3 : STA.w $19F5 : STA.w SprY, Y
    STA.w SprMiscB, Y

    TYX

    STZ $0D60, X
    STZ $0D70, X
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
    LDA.w $0D10, X : PHA
    LDA.w $0D00, X : PHA

    JSL Sprite_Move

    PLA
    LDY.b #$00 : SEC : SBC.w $0D00, X : STA.w $0310
    BPL .pos_y_low
    DEY

  .pos_y_low
    STY.w $0311

    ; -----------------------------------------------------

    PLA
    LDY.b #$00 : SEC : SBC.w $0D10, X : STA.w $0312
    BPL .pos_x_low

    DEY

  .pos_x_low
    STY.w $0313

    ; -----------------------------------------------------

    LDA.b #$01 : STA.w $0428

    LDA.w $0D00, X : SEC : SBC.b #$0C : STA.w $0DB0, X

    LDA.w $0B08 : SEC : SBC.w $0D10, X
                  CLC : ADC.b #$02 
                  CMP.b #$04 : BCS .not_at_target

    LDA.w $0B09 : SEC : SBC.w $0D00, X 
                  CLC : ADC.b #$02
                  CMP.b #$04 : BCS .not_at_target

  .adjust_phase ; Unused?
    STZ.w $0D80, X
    LDA.b #$30 : STA.w $0DF0, X

  .not_at_target
    ; LayerEffect_Trinexx $0AFEF0
    REP   #$20
    LDA.w $0422 : CLC : ADC.w $0312 : STA.w $0422
    LDA.w $0424 : CLC : ADC.w $0310 : STA.w $0424
    STZ.w $0312 : STZ.w $0310
    SEP   #$20

    RTS
}

; =========================================================

StopIfOutOfBounds:
{
    ; Set A to 00 if outside of certain bounds

    REP #$20
    LDA $0FD8 : CMP.w #$0A22 : BCS .notOutOfBoundsLeft
        SEP #$20
        LDA $0D50 : CMP.b #$7F : BCC .notOutOfBoundsLeft
            LDA.b #-10 : STA $0D50 : STA $0D70
            LDA $19EA : SEC : SBC #$04 : STA $19EA
            LDA $19EC : SEC : SBC #$04 : STA $19EC
            LDA $19EE : SEC : SBC #$04 : STA $19EE

            LDA $19F0 : SEC : SBC #$04 : STA $19F0
            LDA $19F2 : SEC : SBC #$04 : STA $19F2
            LDA $19F4 : SEC : SBC #$04 : STA $19F4

  .notOutOfBoundsLeft
    SEP #$20

    REP #$20
    LDA $0FD8 : CMP.w #$1B00 : BCC .notOutOfBoundsRight
        SEP #$20
        LDA $0D50 : CMP.b #$80 : BCS .notOutOfBoundsRight
            LDA.b #$00 : STA $0D50 : STA $0D70
            LDA $19EA : CLC : ADC #$04 : STA $19EA
            LDA $19EC : CLC : ADC #$04 : STA $19EC
            LDA $19EE : CLC : ADC #$04 : STA $19EE

            LDA $19F0 : CLC : ADC #$04 : STA $19F0
            LDA $19F2 : CLC : ADC #$04 : STA $19F2
            LDA $19F4 : CLC : ADC #$04 : STA $19F4

  .notOutOfBoundsRight
    SEP #$20

    ; Upper bound
    REP #$20
    LDA $0FDA : CMP.w #$0150 : BCS .notOutOfBoundsUp
        SEP #$20
        LDA $0D40 : CMP.b #$7F : BCC .notOutOfBoundsUp
            LDA.b #$00 : STA $0D40 : STA $0D60
            LDA $19EA : SEC : SBC #$04 : STA $19EA
            LDA $19EC : SEC : SBC #$04 : STA $19EC
            LDA $19EE : SEC : SBC #$04 : STA $19EE

  .notOutOfBoundsUp
    SEP #$20

    print "CHECK DOWNS", pc
    REP   #$20
    LDA   $0FDA : CMP.w #$01A0 : BCC .notOutOfBoundsDown
        SEP #$20
        LDA $0D40 : CMP.b #$80 : BCS .notOutOfBoundsDown
            LDA.b #-10 : STA $0D40 : STA $0D60 ; Reverse the direction

            ; Modify the neck position
            ; Makes them move away from each other a bit
            LDA $19EA : SEC : SBC #$04 : STA $19EA
            LDA $19EC : SEC : SBC #$04 : STA $19EC
            LDA $19EE : SEC : SBC #$04 : STA $19EE

            LDA $19F0 : CLC : ADC #$04 : STA $19F0
            LDA $19F2 : CLC : ADC #$04 : STA $19F2
            LDA $19F4 : CLC : ADC #$04 : STA $19F4
            

  .notOutOfBoundsDown
    SEP #$20

    RTS
}

; =========================================================

Sprite_ApplySpeedTowardsPlayerXOrY:
{
    JSL Sprite_IsBelowPlayer : BEQ .playerBelow
        ;playerAbove

        REP #$20
        LDA $0FDA : SEC : SBC $20 : CLC : ADC.w #$0006 : STA $01 ;delta Y
        ;added an extra 6 pixels because aparently if link.y is 6 above sprite.y it is concidered below ¯\_(ツ)_/¯
        SEP #$20

        JSL Sprite_IsToRightOfPlayer : BEQ .playerToTheRight1
            ;playerToTheLeft

            REP #$20
            LDA $0FD8 : SEC : SBC $22 ;delta X
            

            CMP $01 : BCS .XGreaterThanY1
                ;YGreaterThanX
                SEP   #$20
                LDA.b #$00 : SEC : SBC $00 : STA $0D40
                STZ   $0D50
                RTS

            .XGreaterThanY1
                SEP   #$20
                LDA.b #$00 : SEC : SBC $00 : STA $0D50
                STZ   $0D40
                RTS


        .playerToTheRight1
            REP #$20
            LDA $22 : SEC : SBC $0FD8 ;delta X

            CMP $01 : BCS .XGreaterThanY2
                ;YGreaterThanX
                SEP   #$20
                LDA.b #$00 : SEC : SBC $00 : STA $0D40
                STZ   $0D50
                RTS

            .XGreaterThanY2
                SEP   #$20
                LDA.b #$00 : CLC : ADC $00 : STA $0D50
                STZ   $0D40
                RTS


    .playerBelow
        REP #$20
        LDA $20 : SEC : SBC $0FDA : CLC : ADC.w #$0006 : STA $01 ;delta Y
        ;added an extra 6 pixels because aparently if link.y is 6 above sprite.y it is concidered below ¯\_(ツ)_/¯
        SEP #$20

        JSL Sprite_IsToRightOfPlayer : BEQ .playerToTheRight2
            ;playerToTheLeft

            REP #$20
            LDA $0FD8 : SEC : SBC $22 ;delta X

            CMP $01 : BCS .XGreaterThanY3
                ;YGreaterThanX
                SEP   #$20
                LDA.b #$00 : CLC : ADC $00 : STA $0D40
                STZ   $0D50
                RTS

            .XGreaterThanY3
                SEP   #$20
                LDA.b #$00 : SEC : SBC $00 : STA $0D50
                STZ   $0D40
                RTS


        .playerToTheRight2
            REP #$20
            LDA $22 : SEC : SBC $0FD8 ;delta X

            CMP $01 : BCS .XGreaterThanY4
                ;YGreaterThanX
                SEP   #$20
                LDA.b #$00 : CLC : ADC $00 : STA $0D40
                STZ   $0D50
                RTS

            .XGreaterThanY4
                SEP   #$20
                LDA.b #$00 : CLC : ADC $00 : STA $0D50
                STZ   $0D40
                RTS
}

; =========================================================

ApplyPalette:
{
    REP #$20 ;Set A in 16bit mode

    ;note, this uses adresses like 7EC300 and not 7EC500 because the game 
    ;will fade the colors into 7EC500 based on the colors found in 7EC300

    LDA #$7FFF : STA $7EC5E2 ;BG2
    LDA #$318C : STA $7EC5E4
    LDA #$4E73 : STA $7EC5E6
    LDA #$0C79 : STA $7EC5E8
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
    JSL Sprite_OAM_AllocateDeferToPlayer

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
        
    LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
        
    PLY : INY
        
    PLX : DEX : BPL .next_tile

    PLX

    RTS


  .start_index
    db $00, $0A, $14
  .nbr_of_tiles
    db 9, 9, 9
  .x_offsets
    dw -8, -16, -16, -16, -32, 8, 16, 16, 16, 32
    dw -8, -16, -16, -16, -32, 8, 16, 16, 16, 32
    dw -8, -16, -16, -16, -32, 8, 16, 16, 16, 32
  .y_offsets
    dw 8, -8, 8, -36, -36, 8, -8, 8, -36, -36
    dw 8, -5, 11, -38, -38, 8, -8, 8, -39, -38
    dw 8, -8, 8, -36, -36, 8, -5, 11, -36, -36
  .chr
    db $23, $00, $20, $0E, $0C, $23, $00, $20, $0E, $0C
    db $23, $00, $20, $0E, $0C, $23, $00, $20, $0E, $0C
    db $23, $00, $20, $0E, $0C, $23, $00, $20, $0E, $0C
  .properties
    db $39, $39, $39, $39, $39, $79, $79, $79, $79, $79
    db $39, $39, $39, $39, $39, $79, $79, $79, $79, $79
    db $39, $39, $39, $39, $39, $79, $79, $79, $79, $79
  .sizes
    db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
    db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
    db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
}
