; =========================================================
; Portal Sprite
; =========================================================

!SPRID              = Sprite_Portal
!NbrTiles           = 00  ; Native allocation uses tiles minus one: one 16x16 tile
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 00  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this Portal (can be 0 to 7)
!Hitbox             = 00  ; 00 to 31, can be viewed in sprite draw tool
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
%Set_Sprite_Properties(Sprite_Portal_Prep, Sprite_Portal_Long)

Sprite_Portal_Long:
{
  PHB : PHK : PLB
  JSR Sprite_Portal_Draw
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Portal_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Portal_Prep:
{
  PHB : PHK : PLB
  ; Bit 7 keeps the portal active off camera.
  LDA.b #$80 : STA.w SprDefl, X
  LDA.w SprHitbox, X : AND.b #$C0 : STA.w SprHitbox, X
  STZ.w SprTileDie, X
  LDA.b #$FF : STA.w SprBulletproof, X
  PLB
  RTL
}

; =========================================================
; FREE RAM: 0x08

BluePortal_X      = $7E06F8
BluePortal_Y      = $7E06F9
OrangePortal_X    = $7E06FA
OrangePortal_Y    = $7E06FB

BlueActive        = $7E06FC
OrangeActive      = $7E06FD
; OrangePortal_Y_Low  = $7E06FE
; OrangePortal_Y_High = $7E06FF

OrangeSpriteIndex = $7E0633
BlueSpriteIndex   = $7E0632

Sprite_Portal_Main:
{
  LDA.w SprAction, X
  JSL   JumpTableLocal

  dw StateHandler
  dw BluePortal
  dw OrangePortal

  dw BluePortal_WarpDungeon
  dw OrangePortal_WarpDungeon

  dw BluePortal_WarpOverworld
  dw OrangePortal_WarpOverworld

  StateHandler:
  {
    ; Reject before changing the live pair or publishing the new portal.
    JSR RejectOnTileCollision
    LDA.w SprState, X : BEQ .rejected
    JSR CheckForDismissPortal

    LDA $7E0FA6 : BNE .BluePortal
      LDA #$01 : STA $0307
      TXA : STA.w OrangeSpriteIndex
      LDA.w SprY, X : STA.w OrangePortal_X
      LDA.w SprX, X : STA.w OrangePortal_Y
      LDA.b #$01 : STA.w SprSubtype, X
      %GotoAction(2)
      RTS
    .BluePortal
    LDA #$02 : STA $0307
    TXA : STA.w BlueSpriteIndex
    LDA.w SprY, X : STA.w BluePortal_X
    LDA.w SprX, X : STA.w BluePortal_Y
    LDA.b #$02 : STA.w SprSubtype, X
    %GotoAction(1)
    .rejected
    RTS
  }

  BluePortal:
  {
    %StartOnFrame(0)
    %PlayAnimation(0,1,8)

    LDA $11 : CMP.b #$2A : BNE .not_warped_yet
      STZ $11
    .not_warped_yet
    CLC

    LDA.w SprTimerD, X : BNE .NoOverlap
    JSR Portal_CheckCounterpart : BCC .NoOverlap
      JSL Link_SetupHitBox
      JSL $0683EA          ; Sprite_SetupHitbox_long
      JSL CheckIfHitBoxesOverlap : BCC .NoOverlap
      CLC
      LDA $1B : BEQ .outdoors
      %GotoAction(3) ; BluePortal_WarpDungeon
    .NoOverlap
    RTS

    .outdoors
    %GotoAction(5) ; BluePortal_WarpOverworld
    RTS
  }

  OrangePortal:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,8)
    LDA $11 : CMP.b #$2A : BNE .not_warped_yet
      STZ $11
    .not_warped_yet
    CLC
    LDA.w SprTimerD, X : BNE .NoOverlap
    JSR Portal_CheckCounterpart : BCC .NoOverlap
    JSL Link_SetupHitBox
    JSL $0683EA          ; Sprite_SetupHitbox_long

    JSL CheckIfHitBoxesOverlap : BCC .NoOverlap
    CLC
    ; JSL $01FF28 ; Player_CacheStatePriorToHandler

    LDA $1B : BEQ .outdoors
      %GotoAction(4) ; OrangePortal_WarpDungeon
      .NoOverlap
      RTS

    .outdoors
    %GotoAction(6) ; OrangePortal_WarpOverworld
    RTS
  }

  BluePortal_WarpDungeon:
  {
    JSR Portal_CheckCounterpart : BCS .valid_counterpart
      %GotoAction(1)
      RTS
    .valid_counterpart
    JSR Portal_CheckWarpContext : BCS .valid_context
      %GotoAction(1)
      RTS
    .valid_context

    ; Recover in the current quarter/layer, never the room-entry quarter.
    ; Native cache capture preserves X/Y/DB and returns with M=8.
    JSL $01FF28 ; CacheCameraProperties
    LDA.w SprY,  Y : STA $7EC184
    LDA.w SprYH, Y : STA $7EC185
    LDA.w SprX,  Y : STA $7EC186
    LDA.w SprXH, Y : STA $7EC187
    LDA.b #$40 : STA.w SprTimerD, Y
    STZ.b $B0 ; Begin native Module07_14 at its camera-recovery stage.
    LDA.b #$14 : STA.b $11
    %GotoAction(1)
    RTS
  }

  OrangePortal_WarpDungeon:
  {
    JSR Portal_CheckCounterpart : BCS .valid_counterpart
      %GotoAction(2)
      RTS
    .valid_counterpart
    JSR Portal_CheckWarpContext : BCS .valid_context
      %GotoAction(2)
      RTS
    .valid_context

    ; Recover in the current quarter/layer, never the room-entry quarter.
    ; Native cache capture preserves X/Y/DB and returns with M=8.
    JSL $01FF28 ; CacheCameraProperties
    LDA.w SprY,  Y : STA $7EC184
    LDA.w SprYH, Y : STA $7EC185
    LDA.w SprX,  Y : STA $7EC186
    LDA.w SprXH, Y : STA $7EC187
    LDA.b #$40 : STA.w SprTimerD, Y
    STZ.b $B0 ; Begin native Module07_14 at its camera-recovery stage.
    LDA.b #$14 : STA.b $11
    %GotoAction(2)
    RTS
  }

  BluePortal_WarpOverworld:
  {
    JSR Portal_CheckCounterpart : BCS .valid_counterpart
      %GotoAction(1)
      RTS
    .valid_counterpart
    JSR Portal_CheckWarpContext : BCS .valid_context
      %GotoAction(1)
      RTS
    .valid_context

    ; The validated target is visible in the current camera context.
    ; Copy both bytes and retain the current overworld bounds and camera.
    LDA.w SprY,  Y : STA.b $20
    LDA.w SprYH, Y : STA.b $21
    LDA.w SprX,  Y : STA.b $22
    LDA.w SprXH, Y : STA.b $23
    LDA.b #$40 : STA.w SprTimerD, Y
    LDA.b #$01 : STA.b $5D
    %GotoAction(1)
    RTS
  }

  OrangePortal_WarpOverworld:
  {
    JSR Portal_CheckCounterpart : BCS .valid_counterpart
      %GotoAction(2)
      RTS
    .valid_counterpart
    JSR Portal_CheckWarpContext : BCS .valid_context
      %GotoAction(2)
      RTS
    .valid_context

    ; The validated target is visible in the current camera context.
    ; Copy both bytes and retain the current overworld bounds and camera.
    LDA.w SprY,  Y : STA.b $20
    LDA.w SprYH, Y : STA.b $21
    LDA.w SprX,  Y : STA.b $22
    LDA.w SprXH, Y : STA.b $23
    LDA.b #$40 : STA.w SprTimerD, Y
    LDA.b #$01 : STA.b $5D
    %GotoAction(2)
    RTS
  }
}

; Carry set only for a live portal of the opposite color in slot Y.
; The overlap and queued warp both check: a slot can disappear between frames.
Portal_CheckCounterpart:
{
  LDA.w SprSubtype, X : CMP.b #$02 : BEQ .from_blue
    CMP.b #$01 : BNE .invalid
    LDY.w BlueSpriteIndex
    LDA.b #$02
    BRA .check_slot
  .from_blue
    LDY.w OrangeSpriteIndex
    LDA.b #$01
  .check_slot
  CPY.b #$10 : BCS .invalid
  CMP.w SprSubtype, Y : BNE .invalid
  LDA.w SprType, Y : CMP.b #Sprite_Portal : BNE .invalid
  LDA.w SprState, Y : CMP.b #$09 : BNE .invalid
    SEC
    RTS
  .invalid
  CLC
  RTS
}

; Interim RC transport boundary: both full target coordinates must stay on
; Link's current 256px pages and inside the current 256x224 viewport. A full
; 16px landing must fit. Far/offscreen targets remain paired but cannot warp.
; Entry M=8/X=8, X=source, Y=validated counterpart. X/Y/DB/DP and all P except
; returned carry are preserved. A is scratch; this helper makes no RAM writes.
Portal_CheckWarpContext:
{
  PHP
  LDA.w SprXH, Y : CMP.b $23 : BNE .invalid
  LDA.w SprYH, Y : CMP.b $21 : BNE .invalid
  LDA.w SprFloor, Y : CMP.b $EE : BNE .invalid

  LDA.w SprYH, Y : XBA : LDA.w SprY, Y
  REP #$20
  SEC : SBC.b $E8 : CMP.w #$00D1 : BCS .invalid
  SEP #$20
  LDA.w SprXH, Y : XBA : LDA.w SprX, Y
  REP #$20
  SEC : SBC.b $E2 : CMP.w #$00F1 : BCS .invalid
  PLP
  SEC
  RTS
  .invalid
  PLP
  CLC
  RTS
}

CheckForDismissPortal:
{
  ; Blue starts a fresh pair; orange replaces orange and retains one blue.
  ; Derive ownership from live actors, never the cached count/slot handles.
  ; The old decrement-only path forgot the new blue and leaked every fifth cast.
  PHX
  PHY
  TXA : PHA ; Exclude this accepted source from the bounded identity scan.
  LDA.b #$FF : STA.w BlueSpriteIndex : STA.w OrangeSpriteIndex
  LDA.b #$01 : STA.w $06FE ; Count the accepted source before retained partners.
  LDX.b #$0F
  .next_slot
    TXA : CMP $01,S : BEQ .skip
    LDA.w SprState, X : CMP.b #$09 : BNE .skip
    LDA.w SprType, X : CMP.b #Sprite_Portal : BNE .skip
    LDA.w SprSubtype, X : CMP.b #$01 : BEQ .dismiss
                          CMP.b #$02 : BNE .skip
    LDA $7E0FA6 : BNE .dismiss ; A blue cast clears both previous colors.
    LDA.w BlueSpriteIndex : CMP.b #$FF : BNE .dismiss
      TXA : STA.w BlueSpriteIndex
      INC.w $06FE
      BRA .skip
    .dismiss
      STZ.w SprState, X
    .skip
    DEX : BPL .next_slot
  PLA
  PLY
  PLX
  RTS
}

RejectOnTileCollision:
{
  LDA.w SprY, X : AND #$F8 : STA.b $00 : LDA.w SprYH, X : STA.b $01
  LDA.w SprX, X : AND #$F8 : STA.b $02 : LDA.w SprXH, X : STA.b $03

  ; Fetch tile attributes based on current coordinates
  LDA.b #$00 : JSL Sprite_GetTileAttr

  ; Load the tile index
  LDA $0FA5 : CLC : CMP.b #$00 : BEQ .not_out_of_bounds
                    CMP.b #$48 : BEQ .not_out_of_bounds

    ; Clear the sprite and make an error sound
    LDA #$3C ; SFX2.3C Error beep
    STA $012E ; Queue sound effect

    LDA #$00 : STA.w SprState, X

  .not_out_of_bounds
  RTS
}

Sprite_Portal_Draw:
{
  ; Pending/rejected placements own no visible tile yet.
  LDA.w SprAction, X : BNE .accepted
    RTS
  .accepted
  JSL Sprite_PrepOamCoord : BCC .check_viewport
    RTS
  .check_viewport
  ; Native Prep allows a wide margin for large sprites. This is one 16x16
  ; tile: do not consume a defer-to-Link slot when all of it is offscreen.
  REP #$20
  LDA $00 : CLC : ADC.w #$000F : CMP.w #$010F : BCS .clipped
  LDA $02 : CLC : ADC.w #$000F : CMP.w #$00EF : BCC .draw_on_screen
  .clipped
    SEP #$20
    RTS
  .draw_on_screen
  SEP #$20
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06

  PHX
  LDX   .nbr_of_tiles, Y ;amount of tiles -1
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

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .start_index
    db $00, $01, $02, $03
  .nbr_of_tiles
    db 0, 0, 0, 0
  .x_offsets
    dw 0
    dw 0
    dw 0
    dw 0
  .y_offsets
    dw 0
    dw 0
    dw 0
    dw 0
  .chr
    db $EE
    db $EE
    db $EE
    db $EE
  .properties
    db $24
    db $64
    db $22
    db $62
}
