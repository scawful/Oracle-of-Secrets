; =========================================================
; Sprite Properties
; =========================================================

!SPRID              = Sprite_Booki
!NbrTiles           = 05  ; 4 death poof + 1 body + 1 shadow (allocates 6 slots)
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

%Set_Sprite_Properties(Sprite_Booki_Prep, Sprite_Booki_Long)

Sprite_Booki_Long:
{
  PHB : PHK : PLB
  ; Keep drawing the body while SpriteModule_Die ($0DD0 == 6) counts SprTimerA
  ; down from $1F to $0A (in Region A slots after SpriteDeath_DrawPoof).
  LDA.w SprState, X : CMP.b #$06 : BNE .draw
    LDA.w SprTimerA, X : CMP.b #$0A : BCC .dying
  .draw
  JSR Sprite_Booki_Draw : BCS .dying
    JSL Sprite_DrawShadow
  .dying
  JSL Sprite_CheckActive : BCC .SpriteIsNotActive
    JSR Sprite_Booki_Main
  .SpriteIsNotActive
  PLB
  RTL
}

Sprite_Booki_Prep:
{
  PHB : PHK : PLB
  LDA.l Sword : BEQ +
    DEC A
  +
  TAY
  LDA.w .health, Y : STA.w SprHealth, X
  STZ.w SprMiscB, X
  PLB
  RTL

  .health
    db $04, $08, $10, $18
}

Sprite_Booki_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw StalkPlayer
  dw HideFromPlayer
  dw HiddenFromPlayer
  dw ApproachPlayer

  StalkPlayer:
  {
    %PlayAnimation(0,1,16)
    JSR Sprite_Booki_Move
    RTS
  }

  HideFromPlayer:
  {
    %PlayAnimation(0,4,16)
    LDA.w SprTimerA, X : BNE +
      INC.w SprAction, X
    +
    RTS
  }

  HiddenFromPlayer:
  {
    %PlayAnimation(4,4,16)
    JSR Sprite_Booki_Move
    JSL GetRandomInt : AND.b #$03 : BEQ +
      INC.w SprAction, X
    +
    RTS
  }

  ApproachPlayer:
  {
    %PlayAnimation(5,9,16)
    JSR Sprite_Booki_Move
    RTS
  }
}

Sprite_Booki_Move:
{
  JSL Sprite_Move
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckIfRecoiling

  JSL Sprite_IsToRightOfPlayer : CPY.b #$01 : BNE .ToRight
    LDA.b #$01 : STA.w SprMiscC, X
    JMP .Continue
  .ToRight
  STZ.w SprMiscC, X
  .Continue

  JSL Sprite_CheckDamageToPlayer
  JSL Sprite_CheckDamageFromPlayer : BCC .no_damage
    LDA.b #$01 : STA.w SprMiscB, X
  .no_damage

  LDA.w SprMiscB, X
  JSL JumpTableLocal

  dw SlowFloat
  dw FloatAway

  SlowFloat:
  {
    ; Float toward player while unseen
    LDY #$04
    JSL GetRandomInt : AND.b #$04
    JSL Sprite_FloatTowardPlayer

    ; Throttled 16-bit LOS check: Link facing Booki or right next to it with clear LOS
    TXA : EOR.b $1A : AND.b #$03 : BNE .NotTooClose
    JSR Booki_PlayerCanSeeUs : BCC .NotTooClose
      LDA.b #$01 : STA.w SprMiscB, X
      LDA.b #$20 : STA.w SprTimerA, X
      %GotoAction(1)
    .NotTooClose

    RTS
  }

  FloatAway:
  {
    ; Smooth flee vector away from player (avoid per-frame speed inversion jitter)
    LDA.b #$06 : JSL Sprite_ApplySpeedTowardsPlayer
    JSL Sprite_InvertSpeed_XY

    ; Return to stalking once Link looks away, moves behind a wall, or leaves range
    TXA : EOR.b $1A : AND.b #$03 : BNE .StillSeen
    JSR Booki_PlayerCanSeeUs : BCS .StillSeen
      STZ.w SprMiscB, X
      %GotoAction(0)
    .StillSeen

    RTS
  }
}

; 16-bit line-of-sight check: returns Carry set if Link is within range,
; either facing Booki ($2F) or within close proximity (< 26px), with clear LOS.
; Out: Carry set = seen, Carry clear = unseen/blocked. X preserved.
Booki_PlayerCanSeeUs:
{
  LDA.b $1B : BEQ .layer_ok
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

  ; Close proximity (< 26px on both axes) triggers shy flee regardless of Link facing
  LDA.b $00 : CLC : ADC.w #$0019 : CMP.w #$0033 : BCS .check_facing
  LDA.b $02 : CLC : ADC.w #$0019 : CMP.w #$0033 : BCC .check_los

.check_facing
  ; Link $2F: 0=Up (SprY<=LinkY -> dy>=0), 2=Down (dy<=0), 4=Left (dx>=0), 6=Right (dx<=0)
  SEP #$20
  LDA.b $2F : AND.b #$06
  BEQ .link_up
  CMP.b #$02 : BEQ .link_down
  CMP.b #$04 : BEQ .link_left
.link_right
  REP #$20
  LDA.b $00 : BEQ .check_los : BPL .no_sight_16
  BRA .check_los
.link_left
  REP #$20
  LDA.b $00 : BMI .no_sight_16
  BRA .check_los
.link_down
  REP #$20
  LDA.b $02 : BEQ .check_los : BPL .no_sight_16
  BRA .check_los
.link_up
  REP #$20
  LDA.b $02 : BPL .check_los
.no_sight_16
  SEP #$20
.no_sight
  CLC
  RTS

.check_los
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

  LDA.w $0FD8 : PHA
  LDA.w $0FDA : PHA

  SEP #$20
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  CLC : ADC.w #$0008 : STA.b $0C
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  CLC : ADC.w #$0008 : STA.b $0E
  SEP #$20

  LDY.b #$07
.ray_loop
  REP #$20
  LDA.b $0C : CLC : ADC.b $08 : STA.b $0C : STA.w $0FD8
  LDA.b $0E : CLC : ADC.b $0A : STA.b $0E : STA.w $0FDA
  SEP #$20
  PHY
  JSL Probe_CheckTileSolidity
  PLY
  BCC .step_clear
    LDA.w $0FA5 : CMP.b #$09 : BNE .blocked
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


; =========================================================

Sprite_Booki_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    SEC
    RTS
  .on_screen
  LDA.w SprState, X : CMP.b #$06 : BEQ .alloc_done
    JSL Sprite_OAM_AllocateDeferToPlayer
  .alloc_done

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : CMP.b #$0A : BCC .frame_ok
    LDA.b #$00
  .frame_ok
  TAY ; Animation Frame
  LDA .start_index, Y : STA $06

  LDA.w SprState, X : CMP.b #$06 : BEQ .dying_flash
    LDA.w SprFlash, X : ASL A : BRA .apply_flash
  .dying_flash
    LDA.w SprFlash, X
  .apply_flash
  AND.b #$0E : STA $08
  LDA.w SprMiscC, X : STA $09

  PHX
  LDX .nbr_of_tiles, Y ; amount of tiles -1
  LDY.b #$00
  .nextTile

  PHX ; Save current Tile Index?
  TXA : CLC : ADC $06 ; Add Animation Index Offset
  PHA ; Keep the value with animation index offset?

  ASL A : TAX

  REP #$20

  LDA $00 : STA ($90), Y
  AND.w #$0100 : STA $0E
  INY
  LDA $02 : STA ($90), Y
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

  LDA.b $09 : BEQ .ToRight
  LDA.b #$29 : JMP .Prop
  .ToRight
  LDA.b #$69
  .Prop
  EOR $08 : STA ($90), Y

  PHY

  TYA : LSR #2 : TAY

  LDA.b #$02 : ORA $0F : STA ($92), Y ; store size in oam buffer

  PLY : INY

  PLX : DEX : BPL .nextTile

  PLX
  CLC
  RTS


  ; =========================================================

  .start_index
  db $00, $01, $02, $03, $04, $05, $06, $07, $08, $09
  .nbr_of_tiles
  db 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  .chr
  db $0E
  db $0C
  db $0A
  db $2C
  db $2E
  db $2E
  db $0A
  db $2C
  db $0C
  db $0E
}
