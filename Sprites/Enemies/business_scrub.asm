; =========================================================
; Business Scrub

!SPRID              = Sprite_BusinessScrub
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 01  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 08  ; Number of Health the sprite have
!Damage             = 04  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 03  ; 00 to 31, can be viewed in sprite draw tool
!Persist            = 01  ; 01 = your sprite continue to live offscreen
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

%Set_Sprite_Properties(Sprite_BusinessScrub_Prep, Sprite_BusinessScrub_Long)

Sprite_BusinessScrub_Long:
{
  PHB : PHK : PLB
  LDA.w WORLDFLAG : BNE .draw_eon
    JSR Sprite_BusinessScrub_Draw
    JMP +
  .draw_eon
  JSR Sprite_EonScrub_Draw
  +
  LDA.w SprSubtype, X : CMP #$01 : BNE .normal_scrub
    JSL Sprite_DrawShadow
  .normal_scrub
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    LDA.w WORLDFLAG : BNE .eon
      JSR Sprite_BusinessScrub_Main
      JMP .SpriteIsNotActive
    .eon
    JSR Sprite_EonScrub_Main
  .SpriteIsNotActive
  PLB
  RTL
}

; =========================================================

Sprite_BusinessScrub_Prep:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : CMP.b #$01 : BEQ .pea_shot
                        CMP.b #$02 : BEQ .cutscene_scrub
  JMP +
  .pea_shot
    LDA.b #$06 : STA.w SprAction, X ; Pea Shot State
    LDA.b #$20 : STA.b SprPrize, X
    JMP +
  .cutscene_scrub
    LDA.b #$08 : STA.w SprAction, X
  +
  PLB
  RTL
}

; =========================================================

; 0-2 - Spitting
; 3-6 - Spinning
; 7-7 - Crouching
; 8-9 - Dazed
; 10-12 - Pea Shooter Anim
; 13 - Hiding
Sprite_BusinessScrub_Main:
{
  LDA.w SprAction, X
  JSL UseImplicitRegIndexedLocalJumpTable

  dw BusinessScrub_Hiding
  dw BusinessScrub_Attack
  dw BusinessScrub_PostAttack
  dw BusinessScrub_Recoil
  dw BusinessScrub_Dazed
  dw BusinessScrub_Subdued

  dw BusinessScrub_PeaShot
  dw BusinessScrub_HidingDefeated

  dw BusinessScrub_CutsceneStart

  ; 0x00
  BusinessScrub_Hiding:
  {
    %StartOnFrame(13)
    %PlayAnimation(13,13,1)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect

    JSL Sprite_IsBelowPlayer : TYA
    CMP #$00 : BNE .is_below_player
        ; Check if the player is too close
        JSL GetDistance8bit_Long : CMP.b #$24 : BCC .too_close
          ; The player is below the scrub, so it should pop up
          LDA #$20 : STA.w SprTimerA, X
          %GotoAction(1)
      .too_close
    RTS
    .is_below_player
    JSL Sprite_CheckIfLifted
    JSL ThrownSprite_TileAndSpriteInteraction_long
    RTS
  }

  ; 0x01
  BusinessScrub_Attack:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,2,8)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect

    LDA.w SprTimerA, X : BNE .not_done
      JSR SpawnPeaShot
      LDA #$F0 : STA.w SprTimerA, X
      INC.w SprAction, X
    .not_done

    JSL GetDistance8bit_Long : CMP #$18 : BCS .not_too_close
      %GotoAction(0)
    .not_too_close
    RTS
  }

  ; 0x02
  BusinessScrub_PostAttack:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,0,4)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect

    LDA.w SprTimerA, X : BNE +
      %GotoAction(0)
    +
    RTS
  }

  ; 0x03
  BusinessScrub_Recoil:
  {
    %StartOnFrame(3)
    %PlayAnimation(3,6,6)

    JSL Sprite_PlayerCantPassThrough

    ; Play the spinning animation for a bit before proceeding
    LDA.w SprTimerA, X : BNE .not_done
      LDA #$40 : STA.w SprTimerA, X
      INC.w SprAction, X
    .not_done

    RTS
  }

  ; 0x04
  BusinessScrub_Dazed:
  {
    %StartOnFrame(8)
    %PlayAnimation(8,9,11)

    JSL Sprite_PlayerCantPassThrough

    LDA.w SprTimerA, X : BNE .not_done
      %SetHarmless(1)
      INC.w SprAction, X
    .not_done

    RTS
  }

  ; 0x05
  BusinessScrub_Subdued:
  {
    %StartOnFrame(7)
    %PlayAnimation(7,7,1)
    JSL Sprite_PlayerCantPassThrough

    LDA.w SprMiscD, X : BNE .no_talk
      %ShowSolicitedMessage($12D) : BCC .no_talk
        JSR DekuScrub_GiveRandomPrize
        LDA.b #$01 : STA.w SprMiscD, X
        %GotoAction(7)
    .no_talk

    RTS
  }

  ; 0x06
  BusinessScrub_PeaShot:
  {
    %StartOnFrame(10)
    %PlayAnimation(10,12,3)

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
  }

  BusinessScrub_HidingDefeated:
  {
    %StartOnFrame(13)
    %PlayAnimation(13,13,1)

    JSL Sprite_CheckIfLifted
    JSL ThrownSprite_TileAndSpriteInteraction_long

    RTS
  }

  BusinessScrub_CutsceneStart:
  {
    ; TODO: Add deku dream cutscene
    RTS
  }
}

; =========================================================

DekuScrub_GiveRandomPrize:
{
  JSL GetRandomInt : AND.b #$03
  TAY
  LDA.w .prizes, Y
  TAY : STZ $02E9
  JSL Link_ReceiveItem

  RTS

  .prizes
    ; heart arrow  10 arrows  magic
    db $42,  $43,   $44,       $45
}

CheckForPeaShotRedirect:
{
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X  : STA.b $08

  LDA.b #$04 : STA.b $02
  STZ $03

  LDA.w SprY, X : STA.b $01
  LDA.w SprYH, X : STA.b $09

  PHX
  LDA.w Offspring1_Id : TAX
  JSL Sprite_SetupHitBox
  PLX

  JSL CheckIfHitBoxesOverlap : BCC .no_dano
    JSR KillPeaShot
    %GotoAction(3)
    RTS
  .no_dano
  ; If the pea shot and deku scrub hitboxes intersect
  ; We will go to recoil
  PHX
  LDA.w Offspring1_Id : TAX
  JSL Sprite_SetupHitBox
  PLX
  JSL CheckIfHitBoxesOverlap : BCC .not_done2
    JSR KillPeaShot
    %GotoAction(3)
    RTS
  .not_done2
  RTS
}

KillPeaShot:
{
  ; Kill the pea shot
  PHX
  LDA.w Offspring1_Id : TAX
  STZ.w SprState, X
  PLX
  RTS
}

SpawnPeaShot:
{
  LDA.b #$14
  JSL Sprite_SpawnDynamically : BMI .return ;89
.AltEntry
  LDA.b #$01 : STA $0E30, Y
  LDA.b #$06 : STA $0D80, Y
  LDA.b #$20 : STA.w SprPrize, Y
  LDA.b #$02 : STA.w SprMiscC, Y
  LDA.b #$01 : STA.w SprBump, Y
  LDA.b #$01 : STA.w SprNbrOAM, Y

  PHX
  ; Spawn Location
  REP #$20
  LDA.w SprCachedX
  SEP #$20
  STA.w SprX, Y : XBA : STA.w SprXH, Y

  REP #$20
  LDA.w SprCachedY : CLC : ADC.w #$000C
  SEP #$20
  STA.w SprY, Y : XBA : STA.w SprYH, Y

  TYX
  STZ.w SprXRound, X

  LDA #$10 : STA.w SprYSpeed, X
  STA.w SprYRound, X

  STX.w Offspring1_Id
  PLX

  .return
  RTS
}

; =========================================================

Sprite_BusinessScrub_Draw:
{
    JSL Sprite_PrepOamCoord
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

    RTS


  .start_index
    db $00, $03, $05, $07, $09, $0B, $0D, $0F, $11, $15, $19, $1A, $1B, $1C
  .nbr_of_tiles
    db 2, 1, 1, 1, 1, 1, 1, 1, 3, 3, 0, 0, 0, 1
  .x_offsets
    dw 0, 0, 8
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 0, 0, -4, 12
    dw 0, 0, -4, 12
    dw 4
    dw 4
    dw 4
    dw 0, 0
  .y_offsets
    dw -8, 8, 8
    dw -8, 0
    dw -8, 0
    dw 0, -8
    dw 0, -16
    dw 0, -8
    dw -8, 0
    dw 0, -8
    dw 0, -8, -8, 0
    dw 0, -8, 0, -8
    dw 4
    dw 4
    dw 4
    dw 0, -4
  .chr
    db $84, $B4, $B5
    db $84, $94
    db $84, $A6
    db $AC, $9C
    db $A8, $88
    db $AA, $9A
    db $98, $A8
    db $AE, $9E
    db $AC, $9C, $87, $87
    db $AC, $9C, $87, $87
    db $86
    db $96
    db $97
    db $94, $84
  .properties
    db $2B, $2B, $2B
    db $2B, $2B
    db $2B, $2B
    db $2B, $2B
    db $2B, $2B
    db $2B, $2B
    db $6B, $6B
    db $2B, $2B
    db $2B, $2B, $2B, $2B
    db $2B, $2B, $2B, $2B
    db $2B
    db $2B
    db $2B
    db $2B, $2B
  .sizes
    db $02, $00, $00
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02, $00, $00
    db $02, $02, $00, $00
    db $00
    db $00
    db $00
    db $02, $02
}
