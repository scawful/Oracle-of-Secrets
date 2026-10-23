; =========================================================
; Kydreeok Head sprite
; Child sprite of the Kydreeok boss: subtype 0 = left head, 1 = right head.
;
; Each frame the head eases toward a pose, an offset from its shoulder
; anchor on the body, and the neck is drawn as a 4-link chain from the
; head back to that anchor (BossKit_DrawChain). There is no neck physics:
; the old Gleeok-style neck ran six ProjectSpeedTowardsEntity + MoveLong
; per head and drew five more PrepOamCoord parts, about 30% of a frame
; for the two heads.
;
; OAM: 2-4 head tiles + 4 neck links = 8 entries at most (!NbrTiles 07).
; RAM: SprMiscA = animation step, SprMiscC = sway phase,
;      SprMiscE/F = attack vector (lunge target or breath step),
;      SprMiscG = breath flames laid, SprTimerA = state time,
;      SprTimerB = animation, SprTimerD = breath pacing,
;      SprTimerE = attack cooldown.
; =========================================================

!SPRID              = Sprite_KydreeokHead
!NbrTiles           = 07  ; Number of tiles used in a frame
!Harmless           = 00  ; 00 = Sprite is Harmful,  01 = Sprite is Harmless
!HVelocity          = 00  ; Is your sprite going super fast? put 01 if it is
!Health             = $C8 ; Number of Health the sprite have
!Damage             = 00  ; (08 is a whole heart), 04 is half heart
!DeathAnimation     = 00  ; 00 = normal death, 01 = no death animation
!ImperviousAll      = 00  ; 00 = Can be attack, 01 = attack will clink on it
!SmallShadow        = 00  ; 01 = small shadow, 00 = no shadow
!Shadow             = 00  ; 00 = don't draw shadow, 01 = draw a shadow
!Palette            = 00  ; Unused in this template (can be 0 to 7)
!Hitbox             = 09  ; 00 to 31, can be viewed in sprite draw tool
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

%Set_Sprite_Properties(Sprite_KydreeokHead_Prep, Sprite_KydreeokHead_Long)

Sprite_KydreeokHead_Long:
{
  PHB : PHK : PLB
  ; Skip the body while in the vanilla dying state (SpriteModule_Die, $0DD0 == 6)
  ; so it cannot cover the death poof; see Sprite_Octorok_Long for details.
  LDA.w SprState, X : CMP.b #$06 : BEQ .no_head
    JSR Sprite_KydreeokHead_Draw
  .no_head

  JSL Sprite_CheckActive : BCC .not_active
    JSR Sprite_KydreeokHead_Main
  .not_active
  PLB
  RTL
}

; Kydreeok_SpawnHead sets the subtype and the position first.
Sprite_KydreeokHead_Prep:
{
  PHB : PHK : PLB
  ; scawful 2026-10-16: 200 HP, touch class 7 (4/3/2 hearts by mail).
  LDA.b #$C8 : STA.w SprHealth, X
  LDA.b #$07 : STA.w SprBump,   X ; bump damage class
  STZ.w SprAction, X              ; KydreeokHead_Rise
  STZ.w SprFrame, X
  STZ.w SprMiscA, X
  STZ.w SprMiscE, X
  STZ.w SprMiscF, X
  STZ.w SprMiscG, X
  LDA.b #$28 : STA.w SprTimerA, X ; grow out of the shoulder
  LDA.b #$40 : STA.w SprTimerE, X ; no attack right after rising
  ; The two heads sway half a cycle apart.
  LDA.w SprSubtype, X : BEQ .left
    LDA.b #$40
  .left
  STA.w SprMiscC, X
  PLB
  RTL
}

; Rest pose by subtype (left, right): an offset from the shoulder anchor.
KydreeokHead_RestX:
  db -20, 20
KydreeokHead_RestY:
  db -28, -28

; 32-step sine, amplitude 8.
KydreeokHead_Sine:
  db  0,  2,  3,  4,  6,  7,  7,  8,  8,  8,  7,  7,  6,  4,  3,  2
  db  0, -2, -3, -4, -6, -7, -7, -8, -8, -8, -7, -7, -6, -4, -3, -2

Sprite_KydreeokHead_Main:
{
  JSL Sprite_DamageFlash_Long
  ; A head growing out of the shoulder cannot be hit yet.
  LDA.w SprAction, X : BEQ .no_contact
    PHX
    JSL Sprite_CheckDamageFromPlayer
    JSL Sprite_CheckDamageToPlayer
    PLX
  .no_contact
  JSR KydreeokHead_Animate

  %SpriteJumpTable(KydreeokHead_Rise,
                   KydreeokHead_Idle,
                   KydreeokHead_LungeWindup,
                   KydreeokHead_LungeStrike,
                   KydreeokHead_BreathWindup,
                   KydreeokHead_BreathFire,
                   KydreeokHead_Recover)

  ; 0x00
  KydreeokHead_Rise:
  {
    JSR KydreeokHead_Anchor
    LDY.w SprSubtype, X
    LDA.w KydreeokHead_RestX, Y : STA.b $08
    LDA.w KydreeokHead_RestY, Y : STA.b $09
    LDA.b #$04 : JSR KydreeokHead_SeekOffset
    LDA.w SprTimerA, X : BNE .rising
      %GotoAction(1)
    .rising
    RTS
  }

  ; 0x01
  KydreeokHead_Idle:
  {
    JSR KydreeokHead_IdleMove
    JMP KydreeokHead_MaybeAttack
  }

  ; 0x02 - rear up (the draw shakes the head), then commit to a target
  KydreeokHead_LungeWindup:
  {
    JSR KydreeokHead_Anchor
    LDY.w SprSubtype, X
    LDA.w KydreeokHead_RestX, Y : STA.b $08
    LDA.b #-48 : STA.b $09
    LDA.b #$02 : JSR KydreeokHead_SeekOffset
    LDA.w SprTimerA, X : BNE .winding
      JSR KydreeokHead_AimAtPlayer
      LDA.b #$0C : STA.w SprTimerA, X
      %GotoAction(3)
    .winding
    RTS
  }

  ; 0x03 - snap to where the player stood when the windup ended
  KydreeokHead_LungeStrike:
  {
    JSR KydreeokHead_Anchor
    LDA.w SprMiscE, X : STA.b $08
    LDA.w SprMiscF, X : STA.b $09
    LDA.b #$01 : JSR KydreeokHead_SeekOffset
    LDA.w SprTimerA, X : BNE .striking
      LDA.b #$14 : STA.w SprTimerA, X
      %GotoAction(6)
    .striking
    RTS
  }

  ; 0x04 - rear back while the fire charges (the draw glows), then aim
  KydreeokHead_BreathWindup:
  {
    JSR KydreeokHead_Anchor
    LDY.w SprSubtype, X
    LDA.w KydreeokHead_RestX, Y : CMP.b #$80 : ROR A : STA.b $08
    LDA.b #-52 : STA.b $09
    LDA.b #$02 : JSR KydreeokHead_SeekOffset
    LDA.w SprTimerA, X : BNE .charging
      ; One 12 px step toward the player, kept for the whole breath.
      LDA.b #$0C : JSL Sprite_ProjectSpeedTowardsPlayer
      LDA.b $01 : STA.w SprMiscE, X
      LDA.b $00 : STA.w SprMiscF, X
      STZ.w SprMiscG, X
      STZ.w SprTimerD, X
      LDA.b #$2A : JSL Sound_SetSfx2PanLong
      %GotoAction(5)
    .charging
    RTS
  }

  ; 0x05 - lay a line of 6 flames along the aim, one every 3 frames.
  ; The flames are garnish (BossKit_FxAtOffset, at most 6 for this head):
  ; no sprite slots, and only one head breathes at a time.
  KydreeokHead_BreathFire:
  {
    JSR KydreeokHead_Anchor
    LDY.w SprSubtype, X
    LDA.w KydreeokHead_RestX, Y : CMP.b #$80 : ROR A
    CLC : ADC.w SprMiscE, X : STA.b $08
    LDA.b #-52 : CLC : ADC.w SprMiscF, X : STA.b $09
    LDA.b #$02 : JSR KydreeokHead_SeekOffset

    LDA.w SprTimerD, X : BNE .wait
      LDA.b #$03 : STA.w SprTimerD, X
      INC.w SprMiscG, X
      ; Flame k sits k steps out from the mouth (8 px below the head).
      STZ.b $00
      LDA.b #$08 : STA.b $01
      LDA.w SprMiscG, X : TAY
      .step
        LDA.b $00 : CLC : ADC.w SprMiscE, X : STA.b $00
        LDA.b $01 : CLC : ADC.w SprMiscF, X : STA.b $01
      DEY : BNE .step
      LDA.b #$30 : STA.b $08
      LDA.b #$06 : STA.b $09
      LDA.b #$10 : JSL BossKit_FxAtOffset
      LDA.w SprMiscG, X : CMP.b #$06 : BCC .wait
        LDA.b #$18 : STA.w SprTimerA, X
        %GotoAction(6)
    .wait
    RTS
  }

  ; 0x06
  KydreeokHead_Recover:
  {
    JSR KydreeokHead_IdleMove
    LDA.w SprTimerA, X : BNE .recovering
      %GotoAction(1)
    .recovering
    RTS
  }
}

; ---------------------------------------------------------
; Pose

; Out: $04 = shoulder anchor X, $06 = anchor Y (16-bit). The anchor rises
; with the body's altitude. Keeps X.
KydreeokHead_Anchor:
{
  LDA.w SprSubtype, X : AND.b #$01 : TAY
  PHX
  LDX.w Kydreeok_Id
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  STA.b $04
  LDA.w .shoulder_x, Y : %BossKit_Sext16() : CLC : ADC.b $04 : STA.b $04
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  STA.b $06
  LDA.w .shoulder_y, Y : %BossKit_Sext16() : CLC : ADC.b $06 : STA.b $06
  LDA.w SprHeight, X : AND.w #$00FF : EOR.w #$FFFF : SEC : ADC.b $06 : STA.b $06
  SEP #$20
  PLX
  RTS

  .shoulder_x
    db -16, 13
  .shoulder_y
    db -24, -24
}

; Ease the head toward anchor + offset.
; In: $04/$06 = anchor (16-bit), $08/$09 = signed offset X/Y,
;     A = ease shift (1 = half the distance per frame, 4 = 1/16).
; Keeps $04-$09.
KydreeokHead_SeekOffset:
{
  STA.b $0A
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  STA.b $0C
  LDA.b $08 : %BossKit_Sext16() : CLC : ADC.b $04
  SEC : SBC.b $0C
  JSR KydreeokHead_EaseStep
  CLC : ADC.b $0C
  SEP #$20
  STA.w SprX, X : XBA : STA.w SprXH, X

  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  STA.b $0C
  LDA.b $09 : %BossKit_Sext16() : CLC : ADC.b $06
  SEC : SBC.b $0C
  JSR KydreeokHead_EaseStep
  CLC : ADC.b $0C
  SEP #$20
  STA.w SprY, X : XBA : STA.w SprYH, X
  RTS
}

; 16-bit A = signed distance. Out: A = distance >> $0A (toward zero),
; at least one pixel while the target is not reached. A stays 16-bit.
KydreeokHead_EaseStep:
{
  CMP.w #$0000 : BEQ .done
  LDY.b $0A
  CMP.w #$8000 : BCS .negative
    .shift_positive
      LSR A
    DEY : BNE .shift_positive
    CMP.w #$0000 : BNE .done
      INC A
    .done
    RTS
  .negative
  EOR.w #$FFFF : INC A
  .shift_negative
    LSR A
  DEY : BNE .shift_negative
  CMP.w #$0000 : BNE .negate
    INC A
  .negate
  EOR.w #$FFFF : INC A
  RTS
}

; Idle pose: rest + sway + a lean toward the player.
KydreeokHead_IdleMove:
{
  INC.w SprMiscC, X
  JSR KydreeokHead_Anchor
  JSR KydreeokHead_Lean
  LDA.w SprMiscC, X : LSR A : LSR A : AND.b #$1F : TAY
  LDA.w KydreeokHead_Sine, Y : CLC : ADC.b $08 : STA.b $08
  ; Y bobs at twice the rate and half the size.
  TYA : ASL A : AND.b #$1F : TAY
  LDA.w KydreeokHead_Sine, Y : CMP.b #$80 : ROR A
  CLC : ADC.b $09 : STA.b $09
  LDY.w SprSubtype, X
  LDA.w KydreeokHead_RestX, Y : CLC : ADC.b $08 : STA.b $08
  LDA.w KydreeokHead_RestY, Y : CLC : ADC.b $09 : STA.b $09
  LDA.b #$03 : JMP KydreeokHead_SeekOffset
}

; In: $04/$06 = anchor. Out: $08/$09 = (player - anchor) / 4,
; clamped to X -16..16 and Y -8..24.
KydreeokHead_Lean:
{
  REP #$20
  LDA.b $22 : SEC : SBC.b $04
  CMP.w #$8000 : ROR A
  CMP.w #$8000 : ROR A
  CMP.w #17 : BMI .x_not_high
    LDA.w #16
  .x_not_high
  CMP.w #-16 : BPL .x_not_low
    LDA.w #-16
  .x_not_low
  STA.b $08
  LDA.b $20 : SEC : SBC.b $06
  CMP.w #$8000 : ROR A
  CMP.w #$8000 : ROR A
  CMP.w #25 : BMI .y_not_high
    LDA.w #24
  .y_not_high
  CMP.w #-8 : BPL .y_not_low
    LDA.w #-8
  .y_not_low
  SEP #$20
  STA.b $09
  RTS
}

; In: $04/$06 = anchor. Out: SprMiscE/F = player - anchor, clamped to
; the neck's reach (X -48..48, Y -16..64).
KydreeokHead_AimAtPlayer:
{
  REP #$20
  LDA.b $22 : SEC : SBC.b $04
  CMP.w #49 : BMI .x_not_high
    LDA.w #48
  .x_not_high
  CMP.w #-48 : BPL .x_not_low
    LDA.w #-48
  .x_not_low
  SEP #$20
  STA.w SprMiscE, X
  REP #$20
  LDA.b $20 : CLC : ADC.w #$0008 : SEC : SBC.b $06
  CMP.w #65 : BMI .y_not_high
    LDA.w #64
  .y_not_high
  CMP.w #-16 : BPL .y_not_low
    LDA.w #-16
  .y_not_low
  SEP #$20
  STA.w SprMiscF, X
  RTS
}

; Face the player: forward when close in X, turned, or far turned.
; Steps the 3-frame cycle every 10 frames.
KydreeokHead_Animate:
{
  JSL Sprite_IsToRightOfPlayer   ; Y = 0: player to the right, $0F = dx
  LDA.b $0F : CPY.b #$00 : BEQ .right
    EOR.b #$FF : INC A
  .right
  CMP.b #20 : BCS .turned
    LDA.b #$00
    BRA .base
  .turned
  CMP.b #64 : LDA.w .near, Y : BCC .base
    LDA.w .far, Y
  .base
  STA.b $00

  LDA.w SprTimerB, X : BNE .hold
    LDA.b #10 : STA.w SprTimerB, X
    LDA.w SprMiscA, X : INC A : CMP.b #$03 : BCC .step
      LDA.b #$00
    .step
    STA.w SprMiscA, X
  .hold
  LDA.w SprMiscA, X : CLC : ADC.b $00 : STA.w SprFrame, X
  RTS

  .near
    db 3, 6
  .far
    db 9, 12
}

; ---------------------------------------------------------
; Attacks

; Idle only. A new attack needs the cooldown, a 1/32 roll and frame
; budget (BossKit_CanSpend).
KydreeokHead_MaybeAttack:
{
  LDA.w SprTimerE, X : BNE .no_attack
  JSL GetRandomInt : AND.b #$1F : BNE .no_attack
  JSL BossKit_CanSpend : BCC .no_attack
  JSL GetRandomInt : AND.b #$07
  CMP.b #$03 : BCC .fireball
  CMP.b #$05 : BCC .lunge
  CMP.b #$07 : BCC .breath
  .no_attack
  RTS

  .fireball
    PHA
    LDA.b #$30 : JSR KydreeokHead_SetCooldown
    PLA : BNE .targeted
    JSR KydreeokHead_IsPhaseTwo : BCC .targeted
      JMP KydreeokHead_SpawnFireballSpread
    .targeted
    JMP KydreeokHead_SpawnFireballTargeted

  .lunge
    LDA.b #$50 : JSR KydreeokHead_SetCooldown
    LDA.b #$12 : STA.w SprTimerA, X
    %GotoAction(2)
    RTS

  .breath
    JSR KydreeokHead_OtherHeadBreathing : BCS .no_attack
    LDA.b #$70 : JSR KydreeokHead_SetCooldown
    LDA.b #$18 : STA.w SprTimerA, X
    %GotoAction(4)
    RTS
}

; A = cooldown in frames; phase two waits 3/4 of it.
KydreeokHead_SetCooldown:
{
  STA.b $00
  JSR KydreeokHead_IsPhaseTwo : BCC .store
    LDA.b $00 : LSR A : LSR A : STA.b $01
    LDA.b $00 : SEC : SBC.b $01 : STA.b $00
  .store
  LDA.b $00 : STA.w SprTimerE, X
  RTS
}

; Carry set in phase two.
KydreeokHead_IsPhaseTwo:
{
  LDY.w Kydreeok_Id
  LDA.w SprMiscD, Y : CMP.b #$02
  RTS
}

; Carry set while the other head winds up or breathes fire.
KydreeokHead_OtherHeadBreathing:
{
  LDY.w Offspring2_Id
  LDA.w SprSubtype, X : BEQ .check
    LDY.w Offspring1_Id
  .check
  JSR Kydreeok_HeadAlive : BCC .no
  LDA.w SprAction, Y : CMP.b #$04 : BCC .no
  CMP.b #$06 : BCS .no
    SEC
    RTS
  .no
  CLC
  RTS
}

KydreeokHead_PrepFireballCoords:
{
  LDA.w SprX, X : STA $00
  LDA.w SprXH, X : STA $01
  LDA.w SprY, X : STA $02
  LDA.w SprYH, X : STA $03
  LDA.w SprHeight, X : STA $04
  RTS
}

KydreeokHead_ConfigureFireball:
{
  LDA.w SprDefl, Y : ORA.b #$08 : STA.w SprDefl, Y
  LDA.b #$04 : STA.w SprBump, Y
  RTS
}

KydreeokHead_SpawnFireballTargeted:
{
  JSR KydreeokHead_PrepFireballCoords
  JSL Sprite_SpawnFireball : BMI .exit
    JSR KydreeokHead_ConfigureFireball
    PHX
    TYX
    JSL Sprite_DirectionToFacePlayer
    LDA.w .speed_x, Y : STA.w SprXSpeed, X
    LDA.w .speed_y, Y : STA.w SprYSpeed, X
    LDA.w SprX, X : CLC : ADC.w .offset_x_low, Y : STA.w SprX, X
    LDA.w SprXH, X : ADC.w .offset_x_high, Y : STA.w SprXH, X
    LDA.w SprY, X : CLC : ADC.w .offset_y_low, Y : STA.w SprY, X
    LDA.w SprYH, X : ADC.w .offset_y_high, Y : STA.w SprYH, X
    PLX
  .exit
  RTS

  .offset_x_low
    db  12, -12,   0,   0
  .offset_x_high
    db   0,  -1,   0,   0
  .offset_y_low
    db   0,   0,  12, -12
  .offset_y_high
    db   0,   0,   0,  -1
  .speed_y
    db   0,   0,  32, -32
  .speed_x
    db  32, -32,   0,   0
}

KydreeokHead_SpawnFireballSpread:
{
  PHX
  JSL Sprite_DirectionToFacePlayer
  STY $0E
  PLX

  LDA.b #$00 : STA $0F
  .spawn_loop
    JSR KydreeokHead_PrepFireballCoords
    JSL Sprite_SpawnFireball : BMI .next
      JSR KydreeokHead_ConfigureFireball
      PHX
      TYX
      LDA.b $0E : ASL A : CLC : ADC.b $0E : CLC : ADC.b $0F : TAY
      LDA.w .spread_speed_x, Y : STA.w SprXSpeed, X
      LDA.w .spread_speed_y, Y : STA.w SprYSpeed, X
      LDY.b $0E
      LDA.w SprX, X : CLC : ADC.w .offset_x_low, Y : STA.w SprX, X
      LDA.w SprXH, X : ADC.w .offset_x_high, Y : STA.w SprXH, X
      LDA.w SprY, X : CLC : ADC.w .offset_y_low, Y : STA.w SprY, X
      LDA.w SprYH, X : ADC.w .offset_y_high, Y : STA.w SprYH, X
      PLX
    .next
    INC $0F
    LDA.b $0F : CMP.b #$03 : BCC .spawn_loop
  RTS

  .offset_x_low
    db  12, -12,   0,   0
  .offset_x_high
    db   0,  -1,   0,   0
  .offset_y_low
    db   0,   0,  12, -12
  .offset_y_high
    db   0,   0,   0,  -1

  .spread_speed_x
    db  32,  32,  32
    db -32, -32, -32
    db  -8,   0,   8
    db  -8,   0,   8
  .spread_speed_y
    db  -8,   0,   8
    db  -8,   0,   8
    db  32,  32,  32
    db -32, -32, -32
}

; ---------------------------------------------------------
; Draw

; A = palette flash bits: the damage flash, plus a glow while charging fire.
KydreeokHead_FlashBits:
{
  LDA.w SprAction, X : CMP.b #$04 : BNE .damage
    LDA.b $1A : AND.b #$06 : ORA.w SprFlash, X
    RTS
  .damage
  LDA.w SprFlash, X
  RTS
}

Sprite_KydreeokHead_Draw:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer

  ; Lunge windup: shake 1 px side to side.
  LDA.w SprAction, X : CMP.b #$02 : BNE .no_shake
    REP #$20
    LDA.b $1A : AND.w #$0002 : DEC A : CLC : ADC.b $00 : STA.b $00
    SEP #$20
  .no_shake

  LDA $0DC0, X : CLC : ADC $0D90, X : TAY;Animation Frame
  LDA .start_index, Y : STA $06
  JSR KydreeokHead_FlashBits : STA $08

  PHX
  ; amount of tiles - 1
  LDX .nbr_of_tiles, Y : LDY.b #$00
  .next_tile

  PHX ; Save current Tile Index?
  ; Add Animation Index Offset
  TXA : CLC : ADC $06

  ; Keep the value with animation index offset?
  PHA : ASL A : TAX

  REP #$20

  LDA $00 : CLC : ADC .x_offsets, X : STA ($90), Y
  AND.w #$0100 : STA $0E  : INY
  LDA $02 : CLC : ADC .y_offsets, X : STA ($90), Y
  CLC   : ADC #$0010 : CMP.w #$0100
  SEP   #$20
  BCC   .on_screen_y

  LDA.b #$F0 : STA ($90), Y ;Put the sprite out of the way
  STA   $0E
  .on_screen_y

  PLX ; Pullback Animation Index Offset (without the *2 not 16bit anymore)
  INY : LDA .chr, X : STA ($90), Y : INY
  LDA .properties, X : ORA $08 : STA ($90), Y

  PHY
  TYA : LSR #2 : TAY
  LDA .sizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
  PLY : INY
  PLX : DEX : BPL .next_tile

  PLX

  JMP KydreeokHead_DrawNeck

  .start_index
    db $00, $02, $04, $06, $0A, $0E, $12, $16, $1A, $1E, $22, $26, $2A, $2E, $32, $36
  .nbr_of_tiles
    db 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3
  .x_offsets
    dw 0, 0
    dw 0, 0
    dw 0, 0
    dw 8, -8, -8, 8
    dw 8, -8, -8, 8
    dw 8, -8, -8, 8
    dw -8, 8, -8, 8
    dw 8, -8, -8, 8
    dw -8, 8, 8, -8

    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw -8, 8, -8, 8
    dw 8, -8, 8, -8
    dw 8, -8, 8, -8
    dw 8, -8, 8, -8
  .y_offsets
    dw -8, 8
    dw -8, 8
    dw -8, 8
    dw 4, 4, -12, -12
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8

    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
  .chr
    db $40, $60
    db $42, $62
    db $44, $64
    db $68, $66, $46, $48
    db $0A, $08, $28, $2A
    db $4C, $4A, $6A, $6C
    db $48, $46, $68, $66
    db $08, $0A, $2A, $28
    db $4C, $4A, $6A, $6C

    db $80, $82, $A0, $A2
    db $84, $86, $A4, $A6
    db $88, $8A, $A8, $AA
    db $80, $82, $A0, $A2
    db $84, $86, $A4, $A6
    db $88, $8A, $A8, $AA
  .properties
    db $39, $39
    db $39, $39
    db $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $79, $79, $79, $79
    db $79, $79, $79, $79
    db $79, $79, $79, $79

    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $39, $39, $39, $39
    db $79, $79, $79, $79
    db $79, $79, $79, $79
    db $79, $79, $79, $79
  .sizes
    db $02, $02
    db $02, $02
    db $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02

    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02
}

; Neck: 4 links from the head back to the shoulder anchor, bowed against
; the sway and sagging 3 px. Y = the next OAM entry after the head tiles.
KydreeokHead_DrawNeck:
{
  PHY
  JSR KydreeokHead_Anchor
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  STA.b $08
  LDA.b $04 : SEC : SBC.b $08
  JSR KydreeokHead_ClampReach
  STA.b $08
  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  STA.b $0A
  LDA.b $06 : SEC : SBC.b $0A
  JSR KydreeokHead_ClampReach
  SEP #$20
  STA.b $05
  LDA.b $08 : STA.b $04

  LDA.w SprMiscC, X : LSR A : LSR A : AND.b #$1F : TAY
  LDA.w KydreeokHead_Sine, Y : EOR.b #$FF : INC A : CMP.b #$80 : ROR A
  STA.b $0C
  LDA.b #$03 : STA.b $0D
  LDA.b #$2E : STA.b $06
  JSR KydreeokHead_FlashBits : ORA.b #$39 : STA.b $07
  PLY
  JSL BossKit_DrawChain
  RTS
}

; 16-bit A: clamp to -120..120 (BossKit_DrawChain's range).
KydreeokHead_ClampReach:
{
  CMP.w #121 : BMI .not_high
    LDA.w #120
  .not_high
  CMP.w #-120 : BPL .not_low
    LDA.w #-120
  .not_low
  RTS
}
