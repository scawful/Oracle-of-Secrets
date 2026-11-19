; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_Darknut
!NbrTiles           = 03  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = 12  ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 12  ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_Darknut_Prep, Sprite_Darknut_Long)

Sprite_Darknut_Long:
{
  PHB : PHK : PLB
  ; Skip the body while in the vanilla dying state (SpriteModule_Die, $0DD0 == 6)
  ; so it cannot cover the death poof; see Sprite_Octorok_Long for details.
  LDA.w SprState, X : CMP.b #$06 : BEQ .dying
    JSR Sprite_Darknut_Draw
    JSL Sprite_DrawShadow
  .dying
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Darknut_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Darknut_Prep:
{
  PHB : PHK : PLB
  LDA.l Sword : BEQ +
    DEC A
  +
  TAY
  LDA.w .health, Y : STA.w SprHealth, X
if !DISABLE_MASKS == 0
  ; Subtype 1 = armored (Masks/garo_mask.asm); subtype 0 is unchanged.
  JSL Darknut_PrepDefense
else
  LDA.b #$80 : STA.w SprDefl, X
  LDA.b #%01100000 : STA.w SprTileDie, X
endif
  PLB
  RTL

  .health
    db $04, $06, $08, $0A
}

DarknutSpeed = 04

Sprite_Darknut_Main:
{
  ; Throttled 16-bit LOS prober with tile solidity raycast (all 4 facings incl. Up).
  LDA.w SprTimerD, X : BNE .no_probe
  TXA : EOR.b $1A : AND.b #$07 : BNE .no_probe
    JSR Darknut_CheckLineOfSight : BCC .no_probe
      LDA.b #$90 : STA.w SprTimerD, X
  .no_probe

  ; Vanilla guard contact/parry reads the current sprite's weapon offsets.
  JSL Sprite_Darknut_WeaponHitbox
  JSL Guard_ParrySwordAttacks

  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_DamageFlash_Long

  JSL Sprite_CheckIfRecoiling

  ; Taking damage triggers alert
if !DISABLE_MASKS == 0
  JSL Darknut_CheckDamage : BCC .no_dano ; armored: Garo counter only
else
  JSL Sprite_CheckDamageFromPlayer : BCC .no_dano
endif
    LDA.b #$FF : STA.w SprTimerD, X
  .no_dano

  ; SprTimerA triggers chase (used by vanilla guard routines)
  LDA.w SprTimerA, X : BEQ +
    LDA.b #$90 : STA.w SprTimerD, X
  +

  ; SprTimerD > 0 means alerted (from LOS prober, damage, or SprTimerA)
  LDA.w SprTimerD, X : BEQ ++
    LDA.b #$08 : JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_DirectionToFacePlayer
    TYA
    STA.w SprMiscC, X
    STA.w SprMiscE, X
    STA.w SprAction, X
    JSL Guard_ChaseLinkOnOneAxis
    JMP +++
  ++
  JSR Sprite_Darknut_BasicMove
  JSR Goriya_HandleTileCollision
  +++

  JSR Darknut_SyncFrame

  LDA.w SprAction, X
  JSL JumpTableLocal

  dw FaceRight
  dw FaceLeft
  dw FaceDown
  dw FaceUp

  FaceUp:
  {
    %PlayAnimation(0,1,10)
    RTS
  }

  FaceDown:
  {
    %StartOnFrame(2)
    %PlayAnimation(2,3,10)
    RTS
  }

  FaceLeft:
  {
    %StartOnFrame(4)
    %PlayAnimation(4,5,10)
    RTS
  }

  FaceRight:
  {
    %StartOnFrame(6)
    %PlayAnimation(6,7,10)
    RTS
  }
}

; Clamp SprFrame into the 2-frame pair matching SprAction (0=R:6-7, 1=L:4-5, 2=D:2-3, 3=U:0-1).
Darknut_SyncFrame:
{
  LDA.w SprAction, X : AND.b #$03 : TAY
  LDA.w .base_frame, Y : STA.b $00
  LDA.w SprFrame, X : CMP.b $00 : BCC .reset
  SEC : SBC.b $00 : CMP.b #$02 : BCC .ok
.reset
  LDA.b $00 : STA.w SprFrame, X
.ok
  RTS
.base_frame
  db $06, $04, $02, $00
}

; 16-bit line-of-sight prober with 7-step tile solidity raycast.
; Out: Carry set if Link is spotted with clear LOS, clear otherwise. X preserved.
Darknut_CheckLineOfSight:
{
  LDA.b $55 : BEQ .no_cape ; Link invisible under Magic Cape
    CLC : RTS
.no_cape
  LDA.b $1B : BEQ .layer_ok ; Overworld has no indoor floor split
    LDA.w SprFloor, X : CMP.b $EE : BEQ .layer_ok
      CLC : RTS
.layer_ok
  ; 16-bit signed dx = LinkX - SprX ($00), dy = LinkY - SprY ($02)
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  EOR.w #$FFFF : INC A : CLC : ADC.b $22 : STA.b $00
  CLC : ADC.w #$007F : CMP.w #$00FF : BCS .no_sight_16
  SEP #$20

  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  EOR.w #$FFFF : INC A : CLC : ADC.b $20 : STA.b $02
  CLC : ADC.w #$007F : CMP.w #$00FF : BCS .no_sight_16

  ; Close proximity (< 24px on both axes) senses Link regardless of facing
  LDA.b $00 : CLC : ADC.w #$0017 : CMP.w #$002F : BCS .check_facing
  LDA.b $02 : CLC : ADC.w #$0017 : CMP.w #$002F : BCC .in_cone

.check_facing
  SEP #$20
  LDA.w SprAction, X : AND.b #$03
  BEQ .face_right
  CMP.b #$01 : BEQ .face_left
  CMP.b #$02 : BEQ .face_down
.face_up
  REP #$20
  LDA.b $02 : BEQ .in_cone : BPL .no_sight_16
  BRA .in_cone
.face_down
  REP #$20
  LDA.b $02 : BMI .no_sight_16
  BRA .in_cone
.face_left
  REP #$20
  LDA.b $00 : BEQ .in_cone : BPL .no_sight_16
  BRA .in_cone
.face_right
  REP #$20
  LDA.b $00 : BPL .in_cone
.no_sight_16
  SEP #$20
.no_sight
  CLC
  RTS

.in_cone
  ; Signed step_x = dx / 8 ($08), step_y = dy / 8 ($0A)
  LDA.b $00
  CMP.w #$8000 : ROR A
  CMP.w #$8000 : ROR A
  CMP.w #$8000 : ROR A
  STA.b $08
  LDA.b $02
  CMP.w #$8000 : ROR A
  CMP.w #$8000 : ROR A
  CMP.w #$8000 : ROR A
  STA.b $0A

  ; Preserve cached sprite world coordinates around Probe_CheckTileSolidity
  LDA.w $0FD8 : PHA
  LDA.w $0FDA : PHA

  ; Start ray at sprite center (SprX+8, SprY+8) in $0C/$0E
  SEP #$20
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  CLC : ADC.w #$0008 : STA.b $0C
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  CLC : ADC.w #$0008 : STA.b $0E
  SEP #$20

  LDY.b #$07 ; 7 interior sample points (1/8 .. 7/8)
.ray_loop
  REP #$20
  LDA.b $0C : CLC : ADC.b $08 : STA.b $0C : STA.w $0FD8
  LDA.b $0E : CLC : ADC.b $0A : STA.b $0E : STA.w $0FDA
  SEP #$20
  PHY
  JSL Probe_CheckTileSolidity
  PLY
  BCC .step_clear
    LDA.w $0FA5 : CMP.b #$09 : BNE .blocked ; deep water does not block sight
.step_clear
  DEY : BNE .ray_loop

  REP #$20
  PLA : STA.w $0FDA
  PLA : STA.w $0FD8
  SEP #$20
  SEC
  RTS

.blocked
  REP #$20
  PLA : STA.w $0FDA
  PLA : STA.w $0FD8
  SEP #$20
  CLC
  RTS
}

Sprite_Darknut_BasicMove:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw MoveRight
  dw MoveLeft
  dw MoveDown
  dw MoveUp

  MoveUp:
  {
    LDA.b #-DarknutSpeed : STA.w SprYSpeed, X
    STZ.w SprXSpeed, X
    RTS
  }

  MoveDown:
  {
    LDA.b #DarknutSpeed : STA.w SprYSpeed, X
    STZ.w SprXSpeed, X
    RTS
  }

  MoveLeft:
  {
    LDA.b #-DarknutSpeed : STA.w SprXSpeed, X
    STZ.w SprYSpeed, X
    RTS
  }

  MoveRight:
  {
    LDA.b #DarknutSpeed : STA.w SprXSpeed, X
    STZ.w SprYSpeed, X
    RTS
  }
}

Sprite_Darknut_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA DarknutDrawStartIndex, Y : STA $06
if !DISABLE_MASKS == 0
  JSL Darknut_DrawFlash ; armored subtype uses a darker palette
else
  LDA.w SprFlash, X : STA $08
endif

  PHX
  LDX DarknutDrawTileCounts, Y ;amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?

  TXA : CLC : ADC $06 ; Add Animation Index Offset

  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC DarknutDrawXOffsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : CLC : ADC DarknutDrawYOffsets, X : STA ($90), Y
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

  LDA.w .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX

  RTS

  .chr
  db $EF, $E6, $FF
  db $EF, $E6, $FF
  db $E2, $EF, $FF
  db $E2, $EF, $FF
  db $E0, $E8
  db $E4, $E8
  db $E0, $E8
  db $E4, $E8
  .properties
  db $B9, $39, $B9
  db $B9, $79, $B9
  db $39, $39, $39
  db $79, $39, $39
  db $39, $79
  db $39, $79
  db $79, $39
  db $79, $39
  .sizes
  db $00, $02, $00
  db $00, $02, $00
  db $02, $00, $00
  db $02, $00, $00
  db $02, $02
  db $02, $02
  db $02, $02
  db $02, $02
}

DarknutDrawStartIndex:
  db $00, $03, $06, $09, $0C, $0E, $10, $12
DarknutDrawTileCounts:
  db 2, 2, 2, 2, 1, 1, 1, 1
DarknutDrawXOffsets:
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, 0, 0
  dw 0, -12
  dw 0, -12
  dw 0, 12
  dw 0, 12
DarknutDrawYOffsets:
  dw -4, 0, -12
  dw -4, 0, -12
  dw 0, 12, 20
  dw 0, 12, 20
  dw 0, 8
  dw 0, 8
  dw 0, 8
  dw 0, 8
