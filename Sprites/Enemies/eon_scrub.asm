; =========================================================
; Eon Abyss Business Scrub

; Frame Data
; 0 - Looking left
; 1 - Looking right
; 2 - Idle forward
; 3-6 Pea Shooting Mouth
; 7-10 - Getting Stunned
; 11-12 - Dazed

; Clean carried overhead squirm pose for DW Eon Scrub (frames 11..12, max y_offset <= 0).
EonScrub_UpdateCarried:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprGfx, X
  ; If re-lifted mid-air out of Action 8, clear SprAction so re-throw triggers fresh throw.
  LDA.w SprAction, X : CMP.b #$08 : BNE .action_ok
    STZ.w SprAction, X
  .action_ok
  LDA.w SprFrame, X
  CMP.b #$0B : BCC .clamp
  CMP.b #$0D : BCC .anim
  .clamp
    LDA.b #$0B : STA.w SprFrame, X
    LDA.b #$06 : STA.w SprTimerB, X
    RTS
  .anim
  %PlayAnimation(11, 12, 6)
  RTS
}

Sprite_EonScrub_Main:
{
  LDA.w SprSubtype, X : BNE .dispatch ; PeaShot (subtype 1) skips carry/throw checks
  LDA.w SprState, X : CMP.b #$0A : BNE .not_carried
    JSR EonScrub_UpdateCarried
    RTS
  .not_carried
  ; Detect a fresh throw from vanilla CarriedSprite_CheckForThrow ($06DF6D).
  LDA.w SprTimerF, X : BEQ .dispatch
    LDA.w SprAction, X : CMP.b #$08 : BEQ .dispatch
      LDA.w SprXSpeed, X : CMP.b #$80 : ROR A : STA.w SprXSpeed, X
      LDA.w SprYSpeed, X : CMP.b #$80 : ROR A : STA.w SprYSpeed, X
      LDA.b #$18 : STA.w SprTimerF, X
      LDA.b #$07 : STA.w SprFrame, X
      LDA.b #$04 : STA.w SprTimerB, X
      %GotoAction(8)
  .dispatch
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw EonScrub_Stalking            ; 00
  dw EonScrub_Attack              ; 01
  dw EonScrub_PostAttack          ; 02
  dw EonScrub_Recoil              ; 03
  dw EonScrub_Dazed               ; 04
  dw EonScrub_Subdued             ; 05

  dw EonScrub_PeaShot             ; 06
  dw EonScrub_Defeated            ; 07
  dw EonScrub_Thrown              ; 08

  EonScrub_Stalking:
  {
    %PlayAnimation(0,1,16)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect

    JSL Sprite_IsBelowPlayer : TYA
    BNE .is_below_player
      ; Player is south (in front of scrub): pop up if far enough away.
      JSL GetDistance8bit_Long : CMP.b #$24 : BCC .too_close
        LDA.b #$20 : STA.w SprTimerA, X
        LDA.b #$02 : STA.w SprFrame, X
        %GotoAction(1)
      .too_close
      RTS
    .is_below_player
    ; Player is north (behind scrub): stay crouched and allow lifting out of bush.
    JSL Sprite_CheckIfLifted
    RTS
  }

  EonScrub_Attack:
  {
    %PlayAnimation(2,6,16)

    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect
    LDA.w SprAction, X : CMP.b #$01 : BNE .done

    ; Duck back into bush if Link circles behind (north) or gets close (< $20).
    JSL Sprite_IsBelowPlayer : TYA : BNE .duck
    JSL GetDistance8bit_Long : CMP.b #$20 : BCC .duck

    LDA.w SprTimerA, X : BNE .done
      JSR EonScrub_SpawnPeaShot
      LDA.b #$F0 : STA.w SprTimerA, X
      INC.w SprAction, X
    .done
    RTS

    .duck
    STZ.w SprFrame, X
    %GotoAction(0)
    RTS
  }

  EonScrub_PostAttack:
  {
    %PlayAnimation(2,2,16)
    JSL Sprite_PlayerCantPassThrough
    JSR CheckForPeaShotRedirect
    LDA.w SprAction, X : CMP.b #$02 : BNE .done

    ; Duck back into bush if Link circles behind (north), approaches close (< $20),
    ; or post-attack timer expires.
    JSL Sprite_IsBelowPlayer : TYA : BNE .duck
    JSL GetDistance8bit_Long : CMP.b #$20 : BCC .duck
    LDA.w SprTimerA, X : BNE .done
    .duck
    STZ.w SprFrame, X
    %GotoAction(0)
    .done
    RTS
  }

  EonScrub_Recoil:
  {
    %StartOnFrame(7)
    %PlayAnimation(7,10,16)

    JSL Sprite_PlayerCantPassThrough

    ; Play the spinning animation for a bit before proceeding
    LDA.w SprTimerA, X : BNE .not_done
      LDA #$40 : STA.w SprTimerA, X
      INC.w SprAction, X
    .not_done

    RTS
  }

  EonScrub_Dazed:
  {
    %StartOnFrame(11)
    %PlayAnimation(11,12,16)

    JSL Sprite_PlayerCantPassThrough

    LDA.w SprTimerA, X : BNE .not_done
      %SetHarmless(1)
      INC.w SprAction, X
    .not_done

    RTS
  }

  EonScrub_Subdued:
  {
    %PlayAnimation(2,2,16)

    JSL Sprite_PlayerCantPassThrough

    ; Track subdued status in SprMiscF ($0EC0,X) so it survives Sprite_CheckIfLifted.
    LDA.w SprMiscF, X : BNE .no_talk
      %ShowSolicitedMessage($12D) : BCC .no_talk
      JSR DekuScrub_GiveRandomPrize
      LDA.b #$01 : STA.w SprMiscF, X
      STZ.w SprFrame, X
      %GotoAction(7)
    .no_talk
    RTS
  }

  EonScrub_PeaShot:
  {
    %StartOnFrame(13)
    %PlayAnimation(13,13,3)

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

  EonScrub_Defeated:
  {
    %PlayAnimation(0,1,16)
    JSL Sprite_PlayerCantPassThrough
    JSL Sprite_CheckIfLifted
    RTS
  }

  ; 0x08 - Airborne after being lifted and thrown in any direction.
  EonScrub_Thrown:
  {
    %StartOnFrame(7)
    %PlayAnimation(7, 10, 4)

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
      STZ.w SprFrame, X
      %GotoAction(7) ; Already subdued -> EonScrub_Defeated
    .aloft
    RTS
  }
}


EonScrub_SpawnPeaShot:
{
  JMP SpawnPeaShot
}

; =========================================================

Sprite_EonScrub_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .onscreen
    SEC
    RTS
  .onscreen
  LDA.w SprState, X : CMP.b #$0A : BNE .alloc_defer
    LDA.b #$08 : JSL OAM_AllocateFromRegionC ; Carried: 2 tiles max above Link
    BRA .alloc_done
  .alloc_defer
    JSL Sprite_OAM_AllocateDeferToPlayer
  .alloc_done
  ; Base .properties are pri 3 ($33/$73). When carried on layer 0 (SprFloor == 0),
  ; drop to pri 2 ($23/$63) to match Link under roofs/canopies.
  STZ.b $0C
  LDA.w SprState, X : CMP.b #$0A : BNE .have_pri
    LDA.w SprFloor, X : BNE .have_pri
      LDA.b #$10 : STA.b $0C
  .have_pri

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
  LDA .properties, X : EOR.b $0C : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .nextTile

  PLX

  CLC
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
