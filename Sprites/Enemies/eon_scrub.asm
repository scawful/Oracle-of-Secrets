; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_EonScrub
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
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
!Boss               = 00  ; 00 = normal sprite, 01 = sprite is a boss
%Set_Sprite_Properties(Sprite_EonScrub_Prep, Sprite_EonScrub_Long)

; =========================================================

Sprite_EonScrub_Long:
{
  PHB : PHK : PLB

  JSR Sprite_EonScrub_Draw ; Call the draw code
  LDA.w SprSubtype, X : CMP #$01 : BNE .normal_scrub
    JSL Sprite_DrawShadow
  .normal_scrub
  JSL Sprite_CheckActive   ; Check if game is not paused
  BCC .SpriteIsNotActive   ; Skip Main code is sprite is innactive

  JSR Sprite_EonScrub_Main ; Call the main sprite code

  .SpriteIsNotActive
  PLB ; Get back the databank we stored previously
  RTL ; Go back to original code
}

; =========================================================

Sprite_EonScrub_Prep:
{
  PHB : PHK : PLB
    
  LDA SprSubtype, X : CMP #$01 : BNE .normal_scrub
    LDA.b #$06 : STA.w SprAction, X ; Pea Shot State
    LDA.b #$20 : STA.b SprPrize, X
  .normal_scrub 

  PLB
  RTL
}

; =========================================================

; Frame Data
; 0 - Looking left
; 1 - Looking right
; 2 - Idle forward
; 3-6 Pea Shooting Mouth
; 7-10 - Getting Stunned
; 11-12 - Dazed

Sprite_EonScrub_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw EonScrub_Stalking
  dw EonScrub_Attack
  dw EonScrub_PostAttack
  dw EonScrub_Recoil
  dw EonScrub_Dazed
  dw EonScrub_Subdued

  dw EonScrub_PeaShot

  EonScrub_Stalking:
  {
    %PlayAnimation(0,1,16)

    JSL Sprite_PlayerCantPassThrough

    JSL Sprite_IsBelowPlayer : TYA
    CMP #$00 : BNE .is_below_player
      ; Check if the player is too close
      LDA $22 : STA $02
      LDA $20 : STA $03
      LDA SprX, X : STA $04
      LDA SprY, X : STA $05
      JSL GetDistance8bit_Long : CMP.b #$24 : BCC .too_close
        ; The player is below the scrub, so it should pop up
        LDA #$20 : STA.w SprTimerA, X
        %GotoAction(1)
      .too_close
    .is_below_player

    RTS
  }

  EonScrub_Attack:
  {
    %PlayAnimation(2,6,16)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect

    LDA SprTimerA, X : BNE .not_done
      JSR EonScrub_SpawnPeaShot
      LDA #$F0 : STA.w SprTimerA, X
      INC.w SprAction, X
    .not_done

    LDA POSX : STA $02
    LDA POSY : STA $03
    LDA SprX, X : STA $04
    LDA SprY, X : STA $05
    JSL GetDistance8bit_Long : CMP #$18 : BCS .not_too_close
      %GotoAction(0)
    .not_too_close

    RTS
  }

  EonScrub_PostAttack:
  {
    %PlayAnimation(2,2,16)
    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect

    LDA.w SprTimerA, X : BNE +
      %GotoAction(0)
    +
    RTS
  }

  EonScrub_Recoil:
  {
    %PlayAnimation(7,10,16)

    JSL Sprite_PlayerCantPassThrough

    ; Kill the pea shot
    PHX
    LDA Offspring1_Id : TAX
    STZ.w $0DD0, X
    PLX

    ; Play the spinning animation for a bit before proceeding
    LDA SprTimerA, X : BNE .not_done
      LDA #$40 : STA.w SprTimerA, X
      INC.w SprAction, X
    .not_done

    RTS
  }

  EonScrub_Dazed:
  {
    %PlayAnimation(11,12,16)

    JSL Sprite_PlayerCantPassThrough

    LDA SprTimerA, X : BNE .not_done
      %SetHarmless(1)
      INC.w SprAction, X
    .not_done

    RTS
  }

  EonScrub_Subdued:
  {
    %PlayAnimation(2,2,16)

    JSL Sprite_PlayerCantPassThrough

    LDA.w SprMiscD, X : BNE .no_talk  
      
    .no_talk

    RTS
  }

  EonScrub_PeaShot:
  {
    %StartOnFrame(13)
    %PlayAnimation(13,13,3)

    %DoDamageToPlayerSameLayerOnContact()

    JSL Sprite_MoveVert
    JSL Sprite_CheckTileCollision
    LDA.w SprCollision, X : BEQ .no_collision
      STZ.w SprState, X
    .no_collision

    JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
      ; Apply force in the opposite direction
      LDA #-16 : STA.w SprYSpeed, X
    .no_damage
    RTS 

    RTS
  }
}


EonScrub_SpawnPeaShot:
{
  LDA.b #Sprite_EonScrub
  JSL Sprite_SpawnDynamically : BMI .return ;89
    JSR SpawnPeaShot_AltEntry
  .return
  LDA.w Offspring1_Id, X : TAY
  RTS
}

; =========================================================

Sprite_EonScrub_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprFrame, X : TAY ;Animation Frame
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

  RTS


; =========================================================

.start_index
db $00, $02, $04, $06, $08, $0A, $0C, $0E, $10, $12, $14, $16, $18, $1A
.nbr_of_tiles
db 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0
.x_offsets
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0, 0
dw 0
.y_offsets
dw 0, -8
dw 0, -8
dw 0, -12
dw 0, -12
dw 0, -12
dw 0, -12
dw 0, -12
dw 0, -12
dw 0, -12
dw 0, -8
dw 0, -4
dw 0, -16
dw 0, -16
dw 0
.chr
db $20, $0A
db $20, $0A
db $24, $0A
db $22, $0A
db $00, $0A
db $02, $0A
db $04, $0A
db $08, $0A
db $06, $0A
db $28, $0A
db $26, $0A
db $2C, $0C
db $2C, $0C
db $2A
.properties
db $33, $33
db $73, $33
db $33, $33
db $33, $33
db $33, $33
db $33, $33
db $33, $33
db $33, $33
db $33, $33
db $33, $33
db $33, $33
db $33, $33
db $73, $73
db $33
.sizes
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02, $02
db $02
}