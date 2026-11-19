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
  ; Skip the body while in the vanilla dying state (SpriteModule_Die, $0DD0 == 6)
  ; so it cannot cover the death poof; see Sprite_Octorok_Long for details.
  LDA.w SprState, X : CMP.b #$06 : BEQ .normal_scrub
  ; While carried ($0A), Sprite_CheckActive returns CLC (requires SprState == $09),
  ; so update the parent scrub's squirming pose here before drawing so frame 0
  ; immediately switches out of hiding into the overhead animation.
  CMP.b #$0A : BNE .draw_body
    LDA.w SprSubtype, X : BNE .draw_body
    LDA.w SprFreeze : ORA.b $11 : BNE .draw_body
      LDA.w WORLDFLAG : BNE .carried_eon
        JSR BusinessScrub_UpdateCarried
        BRA .draw_body
      .carried_eon
        JSR EonScrub_UpdateCarried
  .draw_body
  LDA.w WORLDFLAG : BNE .draw_eon
    JSR Sprite_BusinessScrub_Draw
    BCS .normal_scrub
    BRA .after_draw
  .draw_eon
    JSR Sprite_EonScrub_Draw
    BCS .normal_scrub
  .after_draw
  LDA.w SprSubtype, X : CMP.b #$01 : BNE .normal_scrub
    JSL Sprite_DrawShadow
  .normal_scrub
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    LDA.w WORLDFLAG : BNE .eon
      JSR Sprite_BusinessScrub_Main
      BRA .SpriteIsNotActive
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
    LDA.b #$FF : STA.w SprMiscE, X ; No active PeaShot child yet
    STZ.w SprMiscF, X              ; Not subdued yet (survives Sprite_CheckIfLifted)
    BRA .done
  .pea_shot
    LDA.b #$06 : STA.w SprAction, X ; Pea Shot State
    LDA.b #$20 : STA.w SprPrize, X
  .done
  PLB
  RTL
}

; =========================================================

; Clean carried overhead squirm pose for LW Business Scrub (frames 8..9, max y_offset <= 0).
BusinessScrub_UpdateCarried:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprGfx, X
  ; If re-lifted mid-air out of Action 8, clear SprAction so re-throw triggers fresh throw.
  LDA.w SprAction, X : CMP.b #$08 : BNE .action_ok
    STZ.w SprAction, X
  .action_ok
  LDA.w SprFrame, X
  CMP.b #$08 : BCC .clamp
  CMP.b #$0A : BCC .anim
  .clamp
    LDA.b #$08 : STA.w SprFrame, X
    LDA.b #$06 : STA.w SprTimerB, X
    RTS
  .anim
  %PlayAnimation(8, 9, 6)
  RTS
}

; 0-2 - Spitting
; 3-6 - Spinning
; 7-7 - Crouching
; 8-9 - Dazed / Carried Squirm
; 10-12 - Pea Shooter Anim
; 13 - Hiding
Sprite_BusinessScrub_Main:
{
  LDA.w SprSubtype, X : BNE .dispatch ; PeaShot (subtype 1) skips carry/throw checks
  LDA.w SprState, X : CMP.b #$0A : BNE .not_carried
    JSR BusinessScrub_UpdateCarried
    RTS
  .not_carried
  ; Detect a fresh throw from vanilla CarriedSprite_CheckForThrow ($06DF6D),
  ; which restores SprState to $09 and sets SprTimerF = +4 and XY throw speed.
  LDA.w SprTimerF, X : BEQ .dispatch
    LDA.w SprAction, X : CMP.b #$08 : BEQ .dispatch
      ; Halve pot-throw XY speed (signed) so the scrub lands in clear view
      ; (~4 tiles) with a crisp upward hop arc (SprTimerF = #$18).
      LDA.w SprXSpeed, X : CMP.b #$80 : ROR A : STA.w SprXSpeed, X
      LDA.w SprYSpeed, X : CMP.b #$80 : ROR A : STA.w SprYSpeed, X
      LDA.b #$18 : STA.w SprTimerF, X
      LDA.b #$03 : STA.w SprFrame, X
      LDA.b #$04 : STA.w SprTimerB, X
      %GotoAction(8)
  .dispatch
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw BusinessScrub_Hiding         ; 00
  dw BusinessScrub_Attack         ; 01
  dw BusinessScrub_PostAttack     ; 02
  dw BusinessScrub_Recoil         ; 03
  dw BusinessScrub_Dazed          ; 04
  dw BusinessScrub_Subdued        ; 05

  dw BusinessScrub_PeaShot        ; 06
  dw BusinessScrub_HidingDefeated ; 07
  dw BusinessScrub_Thrown         ; 08

  ; 0x00
  BusinessScrub_Hiding:
  {
    %StartOnFrame(13)
    %PlayAnimation(13,13,1)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect

    JSL Sprite_IsBelowPlayer : TYA
    BNE .is_below_player
      ; Player is south (in front of scrub): pop up if far enough away.
      JSL GetDistance8bit_Long : CMP.b #$24 : BCC .too_close
        LDA.b #$20 : STA.w SprTimerA, X
        STZ.w SprFrame, X
        %GotoAction(1)
      .too_close
      RTS
    .is_below_player
    ; Player is north (behind scrub): stay crouched and allow lifting out of bush.
    ; Action 8 (BusinessScrub_Thrown) owns thrown physics.
    JSL Sprite_CheckIfLifted
    RTS
  }

  ; 0x01
  BusinessScrub_Attack:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,2,8)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect
    LDA.w SprAction, X : CMP.b #$01 : BNE .done

    ; Duck back into bush if Link circles behind (north) or gets close (< $20).
    JSL Sprite_IsBelowPlayer : TYA : BNE .duck
    JSL GetDistance8bit_Long : CMP.b #$20 : BCC .duck

    LDA.w SprTimerA, X : BNE .done
      JSR SpawnPeaShot
      LDA.b #$F0 : STA.w SprTimerA, X
      INC.w SprAction, X
    .done
    RTS

    .duck
    %GotoAction(0)
    RTS
  }

  ; 0x02
  BusinessScrub_PostAttack:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,0,4)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect
    LDA.w SprAction, X : CMP.b #$02 : BNE .done

    ; Duck back into bush if Link circles behind (north), approaches close (< $20),
    ; or post-attack timer expires.
    JSL Sprite_IsBelowPlayer : TYA : BNE .duck
    JSL GetDistance8bit_Long : CMP.b #$20 : BCC .duck
    LDA.w SprTimerA, X : BNE .done
    .duck
    %GotoAction(0)
    .done
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
      LDA #$20 : STA.w SprTimerA, X ; Brief daze after the short spin.
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

    ; Track subdued status in SprMiscF ($0EC0,X): vanilla Sprite_CheckIfLifted
    ; ($06F27C) zeroes SprMiscD ($0E90,X), so SprMiscF survives re-lifting.
    LDA.w SprMiscF, X : BNE .no_talk
      %ShowSolicitedMessage($12D) : BCC .no_talk
        JSR DekuScrub_GiveRandomPrize
        LDA.b #$01 : STA.w SprMiscF, X
        %GotoAction(7)
    .no_talk

    RTS
  }

  ; 0x06
  BusinessScrub_PeaShot:
  {
    %StartOnFrame(10)
    %PlayAnimation(10,12,3)

    JSL BusinessScrub_PeaShotContact

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

  ; 0x07
  BusinessScrub_HidingDefeated:
  {
    %StartOnFrame(13)
    %PlayAnimation(13,13,1)

    JSL Sprite_PlayerCantPassThrough
    JSL Sprite_CheckIfLifted

    RTS
  }

  ; 0x08 - Airborne after being lifted and thrown in any direction.
  BusinessScrub_Thrown:
  {
    %StartOnFrame(3)
    %PlayAnimation(3, 6, 4)

    JSL Sprite_Move
    JSL Sprite_CheckTileCollision
    JSL ThrownSprite_TileAndSpriteInteraction_long

    ; Abort landing transition if thrown into a pit/water or re-lifted mid-air.
    LDA.w SprState, X : CMP.b #$09 : BNE .aloft
    LDA.w SprHeight, X : ORA.w SprTimerF, X : BNE .aloft
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      LDA.w SprMiscF, X : BNE .already_subdued
        LDA.b #$21 : JSL SpriteSFX_QueueSFX2WithPan
        LDA.b #$20 : STA.w SprTimerA, X
        %GotoAction(3) ; Unsubdued toss -> Recoil -> Dazed -> Subdued
        RTS
      .already_subdued
      LDA.b #$0D : STA.w SprFrame, X
      %GotoAction(7) ; Already subdued -> HidingDefeated
    .aloft
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
  ; Validate per-slot child tracker SprMiscE, X (never global Offspring1_Id).
  LDY.w SprMiscE, X
  BMI .done
  CPY.b #$10 : BCS .done
  LDA.w SprState, Y : CMP.b #$09 : BNE .done
  LDA.w SprType, Y : CMP.b #Sprite_BusinessScrub : BNE .done
  LDA.w SprSubtype, Y : CMP.b #$01 : BNE .done
  LDA.w SprYSpeed, Y : BPL .done ; Must be reflected northward (< 0)

  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $08

  LDA.b #$04 : STA.b $02
  STZ.b $03

  LDA.w SprY, X : STA.b $01
  LDA.w SprYH, X : STA.b $09

  PHX
  TYX
  JSL Sprite_SetupHitBox
  PLX

  JSL CheckIfHitBoxesOverlap : BCC .done
    JSL BusinessScrub_BeginRecoil
  .done
  RTS
}

SpawnPeaShot:
{
  LDA.b #Sprite_BusinessScrub
  JSL Sprite_SpawnDynamically : BMI .return ;89
.AltEntry
  LDA.b #$01 : STA.w $0E30, Y
  LDA.b #$06 : STA.w $0D80, Y
  LDA.b #$20 : STA.w SprPrize, Y
  LDA.b #$02 : STA.w SprMiscC, Y
  LDA.b #$01 : STA.w SprBump, Y
  LDA.b #$01 : STA.w SprNbrOAM, Y
  LDA.w SprFloor, X : STA.w SprFloor, Y

  ; Track this child slot on the parent only (keep Offspring1_Id free for bosses).
  TYA : STA.w SprMiscE, X

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

  LDA.b #$10 : STA.w SprYSpeed, X
  STA.w SprYRound, X
  PLX

  .return
  RTS
}

; =========================================================

Sprite_BusinessScrub_Draw:
{
    JSL Sprite_PrepOamCoord : BCC .onscreen
      SEC
      RTS
    .onscreen
    LDA.w SprState, X : CMP.b #$0A : BNE .alloc_defer
      LDA.b #$10 : JSL OAM_AllocateFromRegionC ; Carried: 4 tiles max above Link
      BRA .alloc_done
    .alloc_defer
      JSL Sprite_OAM_AllocateDeferToPlayer
    .alloc_done
    ; Base .properties are pri 2 ($2B/$6B), matching Link on layer 0 ($20).
    ; If carried on layer 1 (SprFloor != 0), promote to pri 3 ($3B/$7B).
    STZ.b $0C
    LDA.w SprState, X : CMP.b #$0A : BNE .have_pri
      LDA.w SprFloor, X : BEQ .have_pri
        LDA.b #$10 : STA.b $0C
    .have_pri

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
    LDA .properties, X : ORA.b $0C : STA ($90), Y

    PHY
    TYA : LSR #2 : TAY
    LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
    PLY : INY
    PLX : DEX : BPL .nextTile

    PLX

    CLC
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
