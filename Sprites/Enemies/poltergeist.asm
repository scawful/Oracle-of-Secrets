; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_Poltergeist
!NbrTiles           = 4   ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 01  ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 0   ; Unused in this template (can be 0 to 7)
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
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss

%Set_Sprite_Properties(Sprite_Poltergeist_Prep, Sprite_Poltergeist_Long)

Sprite_Poltergeist_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Poltergeist_Draw
  LDA $E0 : CMP #$F0 : BNE .onscreen
    LDA.w SprMiscA, X : BEQ .SpriteIsNotActive
      STZ.w SprState, X ; kill the sprite if offscreen and activated
  .onscreen
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Poltergeist_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Poltergeist_Prep:
{
  PHB : PHK : PLB

  LDA #$00 : STA.w SprHitbox, X ; Persist
  LDA #$00 : STA.w SprDefl, X ; Sprite persist in dungeon
  LDA #$02 : STA.w SprNbrOAM, X ;1 tile by default
  LDA #$01 : STA.w SprAction, X ; by default it's a chair

  LDA.w SprSubtype, X : CMP #$10 : BNE .notPictureFrame
    STZ.w SprMiscA, X
    STZ.w SprAction, X
    JMP .done
  .notPictureFrame

  CMP #$11 : BNE .notAxe
    LDA #$07 : STA.w SprFrame, X
    LDA #$02 : STA.w SprAction, X
    LDA #$04 : STA.w SprNbrOAM, X
    BRA .done
  .notAxe

  CMP #$12 : BNE .notKnife
    LDA #15 : STA.w SprFrame, X
    LDA #$02 : STA.w SprAction, X
    BRA .done
  .notKnife

  CMP #$13 : BNE .notFork
    LDA #37 : STA.w SprFrame, X
    LDA #$02 : STA.w SprAction, X
    BRA .done
  .notFork

  CMP #$14 : BNE .notBed
    LDA #5 : STA.w SprFrame, X
    LDA #$01 : STA.w SprAction, X
    LDA #$06 : STA.w SprNbrOAM, X
    BRA .done
  .notBed

  CMP #$15 : BNE .notDoor
    LDA #36 : STA.w SprFrame, X
    LDA #$01 : STA.w SprAction, X
    LDA #$04 : STA.w SprNbrOAM, X
    LDA.w SprY, X : SEC : SBC #$0C : STA.w SprY, X
    LDA.w SprX, X : CLC : ADC #$08 : STA.w SprX, X
    BRA .done
  .notDoor

  LDA.w SprSubtype, X : AND #$08 : BNE .secondset ;2nd set
    LDA.w SprSubtype, X : CLC : ADC #23 : STA.w SprFrame, X
    BRA .done
  .secondset

  LDA.w SprSubtype, X : AND #$07 : CLC : ADC #30 : STA.w SprFrame, X
  LDA.w SprSubtype, X

  .done
  PLB
  RTL
}

; Subtype:
; 00:chair
; 01:lantern
; 02:(peg switch looks ugly i got colors wrong i think)
; 03:pot
; 04:alt chair1
; 05:alt chair2
; 06:plate
; 07 ---- DO NOT USE WILL TURN SPRITE INTO OVERLORD
; 08:block
; 09:pillar
; 10:barrel
; 11:small vase from shelf
; 12:right wall window
; 13:left wall window
; 14:UNUSED
; 15 ---- DO NOT USE WILL TURN SPRITE INTO OVERLORD
; 16:PictureFrame
; 17:Axe
; 18:Knife
; 19:Fork
; 20:bed
; 21:Shutter door

Sprite_Poltergeist_Main:
{
  LDA.w SprAction, X : JSL JumpTableLocal

  dw PictureFrame
  dw Chair
  dw Axe
  dw SpawnerTester
}

PictureFrame:
{
  JSL Sprite_CheckDamageToPlayer
  REP #$20

  JSR GetLinkDistance16bit : CMP #$0050 : BCS .notcloseenough
    SEP #$20
    LDA #$01 : STA.w SprMiscA, X
    LDA #$02 : STA.w SprHeight, X
  .notcloseenough

  SEP #$20

  LDA.w SprMiscA, X : BNE .chase
    RTS
  .chase

  %PlayAnimation(0, 3, 6)

  LDA #$0A
  JSL Sprite_ApplySpeedTowardsPlayer

  JSL Sprite_MoveLong

  JSL Sprite_CheckDamageFromPlayer : BCC .noShatter
    JMP Shatter
  .noShatter
  RTS
}

GetLinkDistance16bit:
{
  LDA.w SprCachedX ; Sprite X
  SEC : SBC $22 ; - Player X

  BPL +
      EOR #$FFFF : INC
  +

  STA $00 ; Distance X (ABS)

  LDA.w SprCachedY ; Sprite Y
  SEC : SBC $20 ; - Player Y

  BPL +
      EOR #$FFFF : INC
  +

  ; Add it back to X Distance
  CLC : ADC $00 : STA $00 ; distance total X, Y (ABS)

  RTS
}

Chair:
{
  JSL Sprite_CheckDamageToPlayer
  REP #$20

  JSR GetLinkDistance16bit : CMP #$0050 : BCS .notcloseenough
    SEP #$20
    LDA.w SprMiscA, X : BNE +
      LDA #$01 : STA.w SprMiscA, X
    +
  .notcloseenough

  SEP #$20

  LDA.w SprMiscA, X : CMP #$01 : BNE +
    ; Prepare to raise in the air
    LDA.b #$20 : STA.w SprTimerA, X
    INC.w SprMiscA, X
    RTS
  +

  CMP #$02 : BNE +
    ; Prepare to raise in the air
    LDA.w SprTimerA, X : BNE .stillrising
      LDA.b #$10 : STA.w SprTimerA, X
      INC.w SprMiscA, X
      RTS
    .stillrising

    ; OPTIONAL DELAY THE INCREASING SPRHEIGHT WITH TIMER
    LDA.w SprTimerC, X : BNE .optionalTimer
      LDA #$02 : STA.w SprTimerC, X
      INC.w SprHeight, X
    .optionalTimer
    RTS
  +

  CMP #$03 : BNE +
  LDA.w SprTimerA, X : BNE .waitingdelay
  JSL Sprite_MoveLong
  JSL Sprite_CheckDamageToPlayer : BCS Shatter
  JSL Sprite_CheckDamageFromPlayer : BCS Shatter
  ;JSL Sprite_CheckTileCollision : BNE Shatter

  RTS
  +
  RTS
  .waitingdelay
  LDA #$28
  JSL Sprite_ApplySpeedTowardsPlayer

  RTS
}

Shatter:
{
  LDA.b #$A6 : STA.w SprNbrOAM, X
  LDA.b #$1F : JSL Sound_SetSfx2PanLong
  STZ $0DC0, X
  LDA.b #$04 : STA.w SprMiscB, X
  LDA.b #$06 : STA.w SprState, X
  LDA.b #$1F : STA.w SprTimerA, X
  LDA.b #$EC : STA $0E20, X
  LDA.w SprNbrOAM, X : CLC : ADC #$04 : STA.w SprNbrOAM, X
  STZ $0EF0, X
  LDA.b #$80 : STA.w SprMiscB, X
  RTS
}

Axe:
{
  JSL Sprite_CheckDamageToPlayer
  REP #$20
  JSR GetLinkDistance16bit : CMP #$0050 : BCS .notcloseenough
    SEP #$20
    LDA.w SprMiscA, X : BNE +
      LDA #$01 : STA.w SprMiscA, X
    +
  .notcloseenough

  SEP #$20
  LDA.w SprMiscA, X : CMP #$01 : BNE +
    ; Prepare to raise in the air
    LDA.b #$20 : STA.w SprTimerA, X
    INC.w SprMiscA, X

    RTS
  +

  CMP #$02 : BNE +
    ; Prepare to raise in the air
    LDA.w SprTimerA, X : BNE .stillrising
      LDA.b #$10 : STA.w SprTimerA, X
      INC.w SprMiscA, X
      RTS
    .stillrising

    ; OPTIONAL DELAY THE INCREASING SPRHEIGHT WITH TIMER
    LDA.w SprTimerC, X : BNE .optionalTimer
      LDA #$02 : STA.w SprTimerC, X
      INC.w SprHeight, X
    .optionalTimer
    RTS
  +

  CMP #$03 : BNE +
    LDA.w SprSubtype, X : CMP #$11 : BNE .notAxe
      JSR PlayAxe
      BRA .done
    .notAxe

    CMP #$12 : BNE .notKnife
      JSR PlayKnife
      BRA .done
    .notKnife

    JSR PlayFork
    .done

    LDA.w SprTimerA, X : BNE .waitingdelay
      JSL Sprite_MoveLong
      JSL Sprite_CheckDamageToPlayer : BCC +
        JMP Shatter
      +
      JSL Sprite_CheckDamageFromPlayer : BCC +
        JMP Shatter
        JSL Sprite_CheckTileCollision : BEQ +
          JMP Shatter
  +
  RTS

  .waitingdelay

  LDA #$20
  JSL Sprite_ApplySpeedTowardsPlayer

  RTS
}

PlayAxe:
{
  %PlayAnimation(7, 14, 6)
  RTS
}

PlayFork:
{
  %PlayAnimation(37, 44, 6)
  RTS
}

PlayKnife:
{
  %PlayAnimation(15, 22, 6)
  RTS
}

SpawnerTester:
{
  LDA.w SprTimerA, X : BEQ +
      RTS
  +

  LDA #$FF : STA.w SprTimerA, X
  LDA #$00
  JSL Sprite_SpawnDynamically
  JSL Sprite_SetSpawnedCoords
  LDA.w SprMiscD, X : STA.w SprSubtype, Y
  INC.w SprMiscD, X

  ;LDA #$28 : STA.w SprY, X
  LDA #$01 : STA.w SprAction, Y ; by default it's a chair
  LDA.w SprSubtype, Y : CMP #$10 : BNE .notPictureFrame
    LDA #$00
    STA.w SprMiscA, Y
    STA.w SprAction, Y
    BRA .done

  .notPictureFrame

  CMP #$11 : BNE .notAxe
    LDA #$07 : STA.w SprFrame, Y
    LDA #$02 : STA.w SprAction, Y
    BRA .done

  .notAxe

  CMP #$12 : BNE .notKnife
    LDA #15 : STA.w SprFrame, Y
    LDA #$02 : STA.w SprAction, Y
    BRA .done

  .notKnife

  CMP #$13 : BNE .notFork
    LDA #37 : STA.w SprFrame, Y
    LDA #$02 : STA.w SprAction, Y
    BRA .done

  .notFork

  CMP #$14 : BNE .notBed
    LDA #5 : STA.w SprFrame, Y
    LDA #$01 : STA.w SprAction, Y
    BRA .done

  .notBed

  CMP #$14 : BNE .notDoor
    LDA #36 : STA.w SprFrame, Y
    LDA #$01 : STA.w SprAction, Y
    BRA .done

  .notDoor

  LDA.w SprSubtype, Y : AND #$08 : BNE .secondset ;2nd set
    LDA.w SprSubtype, Y : CLC : ADC #23 : STA.w SprFrame, Y
    BRA .done

  .secondset

  LDA.w SprSubtype, Y : AND #$07 : CLC : ADC #30 : STA.w SprFrame, Y
  LDA.w SprSubtype, Y

  .done

  RTS
}


Sprite_Poltergeist_Draw:
{
  LDA.w SprAction, X : CMP #$03 : BNE +
      RTS
  +

  JSL Sprite_PrepOamCoord
  LDA #$08
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

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
      LDA .properties, X : STA ($90), Y

      PHY

      TYA : LSR #2 : TAY

      LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

      PLY : INY
  PLX : DEX : BPL .nextTile

  PLX
  LDA.w SprMiscA, X : BEQ .noshadow
  JSL Sprite_DrawShadow
  .noshadow
  RTS

  .start_index
  db $00, $02, $04, $06, $08, $09, $0F, $15, $16, $17, $18, $19, $1A, $1B, $1C, $1D, $1F, $20, $22, $23, $25, $26, $28, $29, $2A, $2B, $2C, $2D, $2E, $2F, $30, $31, $33, $35, $37, $39, $3B, $3F, $41, $42, $44, $45, $47, $48, $4A

  .nbr_of_tiles
  db 1, 1, 1, 1, 0, 5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 3, 1, 0, 1, 0, 1, 0, 1, 0

  .x_offsets
  dw -8, 8
  dw -8, 8
  dw -8, 8
  dw -8, 8
  dw 0
  dw -8, 8, -8, 8, -8, 8
  dw -4, 12, -4, 20, 4, 12
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 4, 4
  dw 0
  dw 0, 8
  dw 0
  dw 4, 4
  dw 0
  dw 8, 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0, 0
  dw 0, 0
  dw 4, 4
  dw -4, -4
  dw 4, 4
  dw -8, 8, -8, 8
  dw 4, 4
  dw 0
  dw 0, 8
  dw 0
  dw 4, 4
  dw 0
  dw 0, 8
  dw 0

  .y_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0
  dw -12, -12, 4, 4, 12, 12
  dw -4, -4, 12, 12, 12, 12
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0, 8
  dw 0
  dw 4, 4
  dw 0
  dw 8, 0
  dw 0
  dw 4, 4
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0
  dw 0, -16
  dw 8, -8
  dw 0, 8
  dw -12, 4
  dw -12, 4
  dw -4, -4, 12, 12
  dw 8, 0
  dw 0
  dw 4, 4
  dw 0
  dw 0, 8
  dw 0
  dw 4, 4
  dw 0

  .chr
  db $02, $02
  db $00, $00
  db $02, $02
  db $04, $04
  db $2C
  db $0C, $0C, $0E, $0E, $1E, $1E
  db $0A, $0A, $2A, $2A, $2B, $2B
  db $20
  db $24
  db $22
  db $26
  db $20
  db $24
  db $22
  db $26
  db $06, $16
  db $08
  db $3A, $3B
  db $08
  db $06, $16
  db $08
  db $3A, $3B
  db $08
  db $42
  db $40
  db $44
  db $46
  db $60
  db $62
  db $64
  db $66
  db $6A, $4A
  db $6C, $4C
  db $6F, $7F
  db $4E, $4E
  db $4E, $4E
  db $48, $48, $68, $68
  db $07, $17
  db $28
  db $3F, $3E
  db $28
  db $07, $17
  db $28
  db $3E, $3F
  db $28

  .properties
  db $3D, $7D
  db $3D, $7D
  db $3D, $7D
  db $3D, $7D
  db $3D
  db $3D, $7D, $3D, $7D, $3D, $7D
  db $3D, $7D, $3D, $7D, $3D, $7D
  db $39
  db $39
  db $39
  db $39
  db $F9
  db $F9
  db $F9
  db $F9
  db $39, $39
  db $39
  db $39, $39
  db $B9
  db $B9, $B9
  db $F9
  db $79, $79
  db $79
  db $3D
  db $3D
  db $39
  db $3D
  db $3D
  db $3D
  db $39
  db $3D
  db $3D, $3D
  db $3D, $3D
  db $3D, $3D
  db $3D, $BD
  db $7D, $FD
  db $3D, $7D, $3D, $7D
  db $B9, $B9
  db $F9
  db $79, $79
  db $79
  db $39, $39
  db $39
  db $39, $39
  db $B9

  .sizes
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
  db $02
  db $02, $02, $02, $02, $02, $02
  db $02, $02, $00, $00, $00, $00
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $00, $00
  db $02
  db $00, $00
  db $02
  db $00, $00
  db $02
  db $00, $00
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02
  db $02, $02
  db $02, $02
  db $00, $00
  db $02, $02
  db $02, $02
  db $02, $02, $02, $02
  db $00, $00
  db $02
  db $00, $00
  db $02
  db $00, $00
  db $02
  db $00, $00
  db $02
}
