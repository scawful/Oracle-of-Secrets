; ==============================================================================
; Sprites/Enemies/pig_moblin.asm — Endgame Pig Moblin ($9C, GameyFireBro art)
; ==============================================================================
; Armed Sword + Shield Pig Moblin (Data/graphics/sprites/gameyfirebro/pig_moblins)
; wired onto verified 0-placement unused vanilla sprite slot $9C.
; Bank-neutral in Bank $32 (PHB/PHK/PLB, outward calls are JSL).
;
; Subtypes (SprSubtype & 1 -> SprMiscD):
;   0 = Sprite_PigMoblin (Green Fortress Guard):
;       12 HP, half-heart bump ($04), Universal OAM Pal 4 ($08, colors 9..15:
;       brown skin + forest green tunic + gold trim + crimson hilt + steel blade).
;   1 = Sprite_BlueMoblin (Blue Elite Captain):
;       20 HP, full-heart bump ($08), brisker chase/lunge, Universal OAM Pal 2
;       ($04, colors 9..15: copper skin + royal blue armor + gold trim + blade).
;   Note: OAM Pal 4 and Pal 2 colors 9..15 are 100% invariant across Light World,
;   Dungeons, Fortress of Secrets, Ganon's Chamber, and Eon Abyss!
;
; AI State Machine (SprAction):
;   0 = Patrol / March (cardinal patrol, wall turns, LOS aggro, ambush-turn on hit)
;   1 = Alert Chase (dominant-axis pursuit toward Link; enters Telegraph in range)
;   2 = Sword Lunge Telegraph (brief planted stance so player can read & dodge)
;   3 = Sword Charge / Lunge (fast forward surge, SFX2 $03, sword thrusts +3 px)
;   4 = Recovery (brief punish window after lunge before returning to Patrol)
;
; VRAM (5-frame staged NMI DMA <= 256B/frame, chained from LyraSea_NmiUpload
; in Bank $32 — zero Bank $2B cost, 4-cycle fast exit when idle/live):
;   Stage $80 -> $81: $5C00/$5D00 ($C0 UpHead)  & $5C20/$5D20 ($C2 UpBody0)
;   Stage $81 -> $82: $5C40/$5D40 ($C4 DnHead)  & $5C60/$5D60 ($C6 DnBody0)
;   Stage $82 -> $83: $5CC0/$5DC0 ($CC UpBody1) & $5CE0/$5DE0 ($CE DnBody1)
;   Stage $83 -> $84: $5E00/$5F00 ($E0 RtHead)  & $5E20/$5F20 ($E2 RtBody0)
;   Stage $84 -> $01: $5E40/$5F40 ($E4 RtBody1) & $5E60/$5F60 ($E6 Swords)
; Leaves NightPoe ($EC/$EE), Cheep-Cheep ($E8/$EA), Blooper ($C8/$CA),
; Epona ($5000/$5100), Gust Jar ($4070/$4090), Bombchu ($42E0/$43E0),
; Lily Pad ($4420/$4520/$47C0), and pickups ($4600-$47FF) completely untouched.
; ==============================================================================

!SPRID                  = Sprite_PigMoblin
!PIG_MOBLIN_NMI_UPLOAD  = 1
!NbrTiles               = 05  ; 6 slots (4 body+sword pieces + 1 shadow; fits 4-tile poof)
!Harmless               = 00  ; Real enemy: damages Link, sword-killable
!HVelocity              = 00
!Health                 = 12  ; Green Fortress Guard (Subtype 1 boosts to 20)
!Damage                 = 04  ; Half-heart bump (Subtype 1 boosts to $08 full heart)
!DeathAnimation         = 00  ; Standard enemy death poof + prize drop
!ImperviousAll          = 00
!SmallShadow            = 00
!Shadow                 = 00  ; Drawn explicitly via Sprite_DrawShadow (DP $00-$05 safe)
!Palette                = 04  ; Pal 4 for Green; Draw selects Pal 2 for Blue Elite
!Hitbox                 = 00  ; 16x16 enemy hitbox
!Persist                = 00
!Statis                 = 00
!CollisionLayer         = 00
!CanFall                = 00  ; Can be knocked into Fortress pits
!DeflectArrow           = 00
!WaterSprite            = 00
!Blockable              = 00
!Prize                  = 03  ; Hearts / arrows / rupees / bombs
!Sound                  = 00
!Interaction            = 00  ; Standard wall/pit tile collision
!Statue                 = 00
!DeflectProjectiles     = 00
!ImperviousArrow        = 00
!ImpervSwordHammer      = 00
!Boss                   = 00

%Set_Sprite_Properties(Sprite_PigMoblin_Prep, Sprite_PigMoblin_Long)

PigMoblin_CodeStart:

; ------------------------------------------------------------------------------
; Prep: cache subtype (0=Green, 1=Blue Elite), boost Blue stats, queue VRAM.
; ------------------------------------------------------------------------------
Sprite_PigMoblin_Prep:
{
  PHB : PHK : PLB
  LDA.w SprSubtype, X : AND.b #$01 : STA.w SprMiscD, X
  BEQ .prep_common
    ; Blue Elite Captain: 20 HP, full-heart bump damage
    LDA.b #$14 : STA.w SprHealth, X
    LDA.b #$08 : STA.w SprBump, X
.prep_common
  STZ.w SprAction, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprHeight, X
  STZ.w SprMiscB, X ; lunge flag (0=normal, 3=sword extended)
  TXA : ASL #3 : STA.w SprMiscC, X ; staggered walk animation phase
  LDA.b #$28 : STA.w SprTimerA, X
  JSR PigMoblin_FaceLink
  JSR PigMoblin_RequestVram
  PLB
  RTL
}

PigMoblin_RequestVram:
{
  JSR PigMoblin_GetAreaKey
  STA.l PigMoblin_LastArea
  TYA : STA.l PigMoblin_LastInd
  LDA.b #$80 : STA.l PigMoblin_VramState
  RTS
}

PigMoblin_EnsureVram:
{
  LDA.l PigMoblin_VramState : BEQ .need
  JSR PigMoblin_GetAreaKey
  CMP.l PigMoblin_LastArea : BNE .need
  TYA : CMP.l PigMoblin_LastInd : BNE .need
  RTS
.need
  JMP PigMoblin_RequestVram
}

; Out: A = area ($8A) outdoors or room low ($A0) indoors;
;      Y = $00 outdoors or ($80 | ($A1 & $01)) indoors. Preserves X.
PigMoblin_GetAreaKey:
{
  LDA.b $1B : BNE .indoors
    LDA.b $8A
    LDY.b #$00
    RTS
.indoors
  LDA.b $A1 : AND.b #$01 : ORA.b #$80 : TAY
  LDA.b $A0
  RTS
}

; ------------------------------------------------------------------------------
; Main entry: skip custom draw over death poof (SprState == $06).
; ------------------------------------------------------------------------------
Sprite_PigMoblin_Long:
{
  PHB : PHK : PLB
  LDA.w SprState, X : CMP.b #$06 : BEQ .dying
    JSR Sprite_PigMoblin_Draw
.dying
  JSL Sprite_CheckActive : BCC .return
    JSR Sprite_PigMoblin_Main
.return
  PLB
  RTL
}

Sprite_PigMoblin_Main:
{
  JSR PigMoblin_EnsureVram
  INC.w SprMiscC, X

  LDA.w SprAction, X
  BEQ .act_patrol
  CMP.b #$01 : BEQ .act_chase
  CMP.b #$02 : BEQ .act_telegraph
  CMP.b #$03 : BEQ .act_lunge
  JSR PigMoblin_Recovery
  BRA .combat

.act_patrol
  JSR PigMoblin_Patrol
  BRA .combat
.act_chase
  JSR PigMoblin_Chase
  BRA .combat
.act_telegraph
  JSR PigMoblin_Telegraph
  BRA .combat
.act_lunge
  JSR PigMoblin_Lunge

.combat
  JSL Sprite_CheckDamageFromPlayer
  JSL Sprite_CheckDamageToPlayer
  ; Sneak-attack reaction: if hit while patrolling, whirl around and chase Link!
  LDA.w SprRecoil, X : BEQ .done
  LDA.w SprAction, X : BNE .done
    JSR PigMoblin_FaceLink
    LDA.b #$01 : STA.w SprAction, X
    LDA.b #$30 : STA.w SprTimerA, X
.done
  RTS
}

; ------------------------------------------------------------------------------
; Action 0: Patrol / March
; ------------------------------------------------------------------------------
PigMoblin_Patrol:
{
  STZ.w SprMiscB, X
  LDY.w SprMiscD, X
  LDA.w .patrol_spd, Y
  JSR PigMoblin_SetDirSpeed
  JSL Sprite_MoveLong
  JSL Sprite_CheckTileCollision

  LDA.w SprCollision, X : BEQ .chk_los
    ; Turn away from wall (0<->1, 2<->3) and keep patrolling
    LDA.w SprMiscA, X : EOR.b #$01 : STA.w SprMiscA, X
    LDA.b #$24 : STA.w SprTimerA, X
    RTS

.chk_los
  LDA.w SprMiscC, X : AND.b #$07 : BNE .chk_turn
    JSR PigMoblin_CheckAggro : BCC .chk_turn
      JSR PigMoblin_FaceLink
      LDA.b #$01 : STA.w SprAction, X
      LDA.b #$28 : STA.w SprTimerA, X
      RTS

.chk_turn
  LDA.w SprTimerA, X : BNE .done
    ; Cycle facing toward Link or perpendicular patrol direction
    JSR PigMoblin_FaceLink
    LDA.b #$38 : STA.w SprTimerA, X
.done
  RTS

.patrol_spd
  db $0E, $11 ; Green = 0.875 px/f, Blue Elite = 1.0625 px/f
}

; ------------------------------------------------------------------------------
; Action 1: Alert Chase
; ------------------------------------------------------------------------------
PigMoblin_Chase:
{
  STZ.w SprMiscB, X
  LDA.w SprMiscC, X : AND.b #$0F : BNE .move
    JSR PigMoblin_FaceLink
.move
  LDY.w SprMiscD, X
  LDA.w .chase_spd, Y
  JSR PigMoblin_SetDirSpeed
  JSL Sprite_MoveLong
  JSL Sprite_CheckTileCollision

  LDA.w SprCollision, X : BEQ .chk_strike
    ; Blocked by pillar/wall during chase: re-aim toward Link's open axis
    JSR PigMoblin_FaceLink
    LDA.w SprTimerA, X : BNE .done
      STZ.w SprAction, X
      LDA.b #$28 : STA.w SprTimerA, X
      RTS

.chk_strike
  JSR PigMoblin_CheckStrikeRange : BCC .chk_leash
    ; Link is in front within strike range -> plant feet & telegraph sword lunge!
    LDA.b #$02 : STA.w SprAction, X
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    LDY.w SprMiscD, X
    LDA.w .tele_time, Y : STA.w SprTimerA, X
    RTS

.chk_leash
  ; Drop back to Patrol if Link escaped far (> 112 px) and timer expired
  LDA.w SprTimerA, X : BNE .done
    JSR PigMoblin_CalcLinkDelta
    LDA.b $04 : CMP.b #$70 : BCS .drop
    LDA.b $05 : CMP.b #$70 : BCS .drop
      LDA.b #$24 : STA.w SprTimerA, X
      RTS
.drop
  STZ.w SprAction, X
  LDA.b #$30 : STA.w SprTimerA, X
.done
  RTS

.chase_spd
  db $14, $18 ; Green = 1.25 px/f, Blue Elite = 1.5 px/f
.tele_time
  db $0C, $09 ; Green = 12f telegraph, Blue Elite = 9f telegraph
}

; ------------------------------------------------------------------------------
; Action 2: Sword Lunge Telegraph (brief planted stance before thrust)
; ------------------------------------------------------------------------------
PigMoblin_Telegraph:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprMiscB, X
  LDA.w SprTimerA, X : BNE .done
    ; Launch Sword Charge / Lunge!
    LDA.b #$03 : STA.w SprAction, X
    LDA.b #$03 : STA.w SprMiscB, X ; extend sword +3 px forward
    LDA.b #$03 : STA.w $012E       ; SFX2.$03 sword thrust whoosh
    LDY.w SprMiscD, X
    LDA.w .lunge_time, Y : STA.w SprTimerA, X
.done
  RTS

.lunge_time
  db $14, $18 ; Green = 20f lunge, Blue Elite = 24f lunge
}

; ------------------------------------------------------------------------------
; Action 3: Sword Charge / Lunge
; ------------------------------------------------------------------------------
PigMoblin_Lunge:
{
  LDA.b #$03 : STA.w SprMiscB, X
  LDY.w SprMiscD, X
  LDA.w .lunge_spd, Y
  JSR PigMoblin_SetDirSpeed
  JSL Sprite_MoveLong
  JSL Sprite_CheckTileCollision

  LDA.w SprCollision, X : BNE .to_recover
  LDA.w SprTimerA, X : BNE .done
.to_recover
  LDA.b #$04 : STA.w SprAction, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprMiscB, X
  LDY.w SprMiscD, X
  LDA.w .recov_time, Y : STA.w SprTimerA, X
.done
  RTS

.lunge_spd
  db $22, $28 ; Green = 2.125 px/f, Blue Elite = 2.5 px/f
.recov_time
  db $16, $10 ; Green = 22f recovery, Blue Elite = 16f recovery
}

; ------------------------------------------------------------------------------
; Action 4: Post-Lunge Recovery (punish window)
; ------------------------------------------------------------------------------
PigMoblin_Recovery:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprMiscB, X
  LDA.w SprTimerA, X : BNE .done
    STZ.w SprAction, X
    LDA.b #$20 : STA.w SprTimerA, X
.done
  RTS
}

; ------------------------------------------------------------------------------
; Helpers: 16-bit Link delta, facing, LOS aggro, strike range, velocity setter.
; ------------------------------------------------------------------------------
; Out: $00/$01 = signed 16-bit dx (LinkX - SprX), $04 = min(|dx|, 255)
;      $02/$03 = signed 16-bit dy (LinkY - SprY), $05 = min(|dy|, 255)
PigMoblin_CalcLinkDelta:
{
  LDA.w SprX, X : STA.b $00
  LDA.w SprXH, X : STA.b $01
  REP #$20
  LDA.b $22 : SEC : SBC.b $00 : STA.b $00
  BPL .dx_pos
    EOR.w #$FFFF : INC A
.dx_pos
  CMP.w #$0100 : BCC .dx_fit
    LDA.w #$00FF
.dx_fit
  SEP #$20
  STA.b $04

  LDA.w SprY, X : STA.b $02
  LDA.w SprYH, X : STA.b $03
  REP #$20
  LDA.b $20 : SEC : SBC.b $02 : STA.b $02
  BPL .dy_pos
    EOR.w #$FFFF : INC A
.dy_pos
  CMP.w #$0100 : BCC .dy_fit
    LDA.w #$00FF
.dy_fit
  SEP #$20
  STA.b $05
  RTS
}

; Set SprMiscA,X (0=Up, 1=Down, 2=Left, 3=Right) along dominant axis to Link.
PigMoblin_FaceLink:
{
  JSR PigMoblin_CalcLinkDelta
  LDA.b $04 : CMP.b $05 : BCC .vertical
    ; Horizontal dominant
    LDA.b $01 : BMI .left
      LDA.b #$03 : STA.w SprMiscA, X
      RTS
.left
    LDA.b #$02 : STA.w SprMiscA, X
    RTS
.vertical
  LDA.b $03 : BMI .up
    LDA.b #$01 : STA.w SprMiscA, X
    RTS
.up
  STZ.w SprMiscA, X
  RTS
}

; C=1 if Link is within 88px on both axes and aligned within 24px on either axis.
PigMoblin_CheckAggro:
{
  JSR PigMoblin_CalcLinkDelta
  LDA.b $04 : CMP.b #$58 : BCS .no
  LDA.b $05 : CMP.b #$58 : BCS .no
  LDA.b $04 : CMP.b #$18 : BCC .yes
  LDA.b $05 : CMP.b #$18 : BCC .yes
.no
  CLC
  RTS
.yes
  SEC
  RTS
}

; C=1 if Link is directly ahead of facing SprMiscA,X within 40px (perp <= 20px).
PigMoblin_CheckStrikeRange:
{
  JSR PigMoblin_CalcLinkDelta
  LDA.w SprMiscA, X
  BEQ .chk_up
  CMP.b #$01 : BEQ .chk_down
  CMP.b #$02 : BEQ .chk_left

  ; Facing Right (3): dx >= 0, |dx| <= $28, |dy| <= $14
  LDA.b $01 : BMI .no
  LDA.b $04 : CMP.b #$29 : BCS .no
  LDA.b $05 : CMP.b #$15 : BCS .no
  SEC : RTS

.chk_left
  LDA.b $01 : BPL .no
  LDA.b $04 : CMP.b #$29 : BCS .no
  LDA.b $05 : CMP.b #$15 : BCS .no
  SEC : RTS

.chk_down
  LDA.b $03 : BMI .no
  LDA.b $05 : CMP.b #$29 : BCS .no
  LDA.b $04 : CMP.b #$15 : BCS .no
  SEC : RTS

.chk_up
  LDA.b $03 : BPL .no
  LDA.b $05 : CMP.b #$29 : BCS .no
  LDA.b $04 : CMP.b #$15 : BCS .no
  SEC : RTS

.no
  CLC
  RTS
}

; In: A = unsigned speed magnitude. Sets SprXSpeed/SprYSpeed from SprMiscA,X.
PigMoblin_SetDirSpeed:
{
  STA.b $00
  LDA.w SprMiscA, X
  BEQ .up
  CMP.b #$01 : BEQ .down
  CMP.b #$02 : BEQ .left
    ; Right (3)
    LDA.b $00 : STA.w SprXSpeed, X
    STZ.w SprYSpeed, X
    RTS
.left
  LDA.b $00 : EOR.b #$FF : INC A : STA.w SprXSpeed, X
  STZ.w SprYSpeed, X
  RTS
.down
  STZ.w SprXSpeed, X
  LDA.b $00 : STA.w SprYSpeed, X
  RTS
.up
  STZ.w SprXSpeed, X
  LDA.b $00 : EOR.b #$FF : INC A : STA.w SprYSpeed, X
  RTS
}

; ------------------------------------------------------------------------------
; Draw: 4 OAM pieces (16x16 Head + 16x16 Body + 2x 8x8 Sword) + Shadow.
; Preserves DP $00-$05 (Sprite_PrepOamCoord outputs) so Sprite_DrawShadow keeps
; exact screen X ($00/$01) and OAM priority ($05).
; ------------------------------------------------------------------------------
Sprite_PigMoblin_Draw:
{
  ; Never draw unuploaded VRAM while 5-frame NMI stream is in flight.
  LDA.l PigMoblin_VramState : CMP.b #$01 : BNE .skip

  JSL Sprite_PrepOamCoord : BCC .on_screen
.skip
  RTS

.on_screen
  JSL Sprite_OAM_AllocateDeferToPlayer

  ; Base screen X/Y -> $06/$07 and $08/$09 (leaving $00-$05 intact for shadow!)
  LDA.w SprX, X : STA.b $06
  LDA.w SprXH, X : STA.b $07
  LDA.w SprY, X : STA.b $08
  LDA.w SprYH, X : STA.b $09
  REP #$20
  LDA.b $06 : SEC : SBC.b $E2 : STA.b $06
  LDA.b $08 : SEC : SBC.b $E8 : STA.b $08
  SEP #$20

  ; Flash-safe base OAM property: Pal 4 ($08) for Green, Pal 2 ($04) for Blue.
  LDA.b #$08
  LDY.w SprMiscD, X : BEQ .pal_ok
    LDA.b #$04
.pal_ok
  STA.b $0A
  LDA.w SprFlash, X : ASL A : EOR.b $0A : AND.b #$0E : ORA.b #$21 : STA.b $0A

  ; Walk frame (0 or 1): animate during Patrol(0)/Chase(1), stride=1 on Lunge(3).
  LDA.w SprAction, X : CMP.b #$03 : BEQ .frame_lunge
  CMP.b #$02 : BCS .frame_still
    LDA.w SprMiscC, X : LSR #3 : AND.b #$01
    BRA .have_frame
.frame_lunge
  LDA.b #$01
  BRA .have_frame
.frame_still
  LDA.b #$00
.have_frame
  PHA ; stack: [frame]

  LDY.b #$00 ; OAM byte index (0, 4, 8, 12)
  LDA.w SprMiscA, X
  BEQ .dir_up
  CMP.b #$01 : BNE + : JMP .dir_down : +
  CMP.b #$02 : BNE + : JMP .dir_left : +
  JMP .dir_right

; --- Facing UP (0): Slot0=Head, Slot1=Body, Slot2=SwTip(V), Slot3=SwHilt(V) ---
.dir_up
  PLA : PHA ; A = frame (0 or 1), bob = -frame
  EOR.b #$FF : INC A : STA.b $0F ; $0F = bob (0 or -1)
  ; Piece 0: UP Head ($C0, 16x16, dx=0, dy=-4+bob)
  LDA.b #$C0 : STA.b $0B
  STZ.b $0C
  LDA.b #$FC : CLC : ADC.b $0F : STA.b $0D
  LDA.b #$02 : STA.b $0E
  JSR PigMoblin_EmitPiece
  ; Piece 1: UP Body ($C2 F0 / $CC F1, 16x16, dx=-1, dy=+2+bob)
  PLA : PHA : BEQ .up_b0
    LDA.b #$CC : BRA .up_b_set
.up_b0
    LDA.b #$C2
.up_b_set
  STA.b $0B
  LDA.b #$FF : STA.b $0C
  LDA.b #$02 : CLC : ADC.b $0F : STA.b $0D
  LDA.b #$02 : STA.b $0E
  JSR PigMoblin_EmitPiece
  ; Piece 2 & 3: Upward Sword behind shoulder (V-flip $80, dy=-9+bob-lunge)
  LDA.b $0A : ORA.b #$80 : STA.b $0A
  LDA.b #$F7 : STA.b $0B ; blade tip (V-flipped)
  LDA.b #$0C : STA.b $0C
  LDA.b #$F7 : CLC : ADC.b $0F : SEC : SBC.w SprMiscB, X : STA.b $0D
  STZ.b $0E
  JSR PigMoblin_EmitPiece
  LDA.b #$F6 : STA.b $0B ; hilt (V-flipped)
  LDA.b $0D : CLC : ADC.b #$08 : STA.b $0D
  JSR PigMoblin_EmitPiece
  PLA
  JMP .draw_shadow

; --- Facing DOWN (1): Slot0=SwHilt, Slot1=SwTip, Slot2=Head, Slot3=Body ---
.dir_down
  PLA : PHA ; frame 0 -> bob 0, frame 1 -> bob -2
  ASL A : EOR.b #$FF : INC A : STA.b $0F ; $0F = bob (0 or -2)
  ; Piece 0: Sword Hilt ($F6, 8x8, dx=-2, dy=+4+bob+lunge)
  LDA.b #$F6 : STA.b $0B
  LDA.b #$FE : STA.b $0C
  LDA.b #$04 : CLC : ADC.b $0F : CLC : ADC.w SprMiscB, X : STA.b $0D
  STZ.b $0E
  JSR PigMoblin_EmitPiece
  ; Piece 1: Sword Tip ($F7, 8x8, dx=-2, dy=+12+bob+lunge)
  LDA.b #$F7 : STA.b $0B
  LDA.b $0D : CLC : ADC.b #$08 : STA.b $0D
  JSR PigMoblin_EmitPiece
  ; Piece 2: DN Head ($C4, 16x16, dx=0, dy=-8+bob)
  LDA.b #$C4 : STA.b $0B
  STZ.b $0C
  LDA.b #$F8 : CLC : ADC.b $0F : STA.b $0D
  LDA.b #$02 : STA.b $0E
  JSR PigMoblin_EmitPiece
  ; Piece 3: DN Body+Shield ($C6 F0 / $CE F1, 16x16, dx=+1, dy=+2+bob)
  PLA : BEQ .dn_b0
    LDA.b #$CE : BRA .dn_b_set
.dn_b0
    LDA.b #$C6
.dn_b_set
  STA.b $0B
  LDA.b #$01 : STA.b $0C
  LDA.b #$02 : CLC : ADC.b $0F : STA.b $0D
  LDA.b #$02 : STA.b $0E
  JSR PigMoblin_EmitPiece
  JMP .draw_shadow

; --- Facing LEFT (2): H-flip ($40) mirror of RIGHT ---
.dir_left
  LDA.b $0A : ORA.b #$40 : STA.b $0A
  PLA : PHA
  EOR.b #$FF : INC A : STA.b $0F ; bob = 0 or -1
  ; Piece 0: Sword Hilt ($E6, 8x8, dx=-3-lunge, dy=+8+bob)
  LDA.b #$E6 : STA.b $0B
  LDA.b #$FD : SEC : SBC.w SprMiscB, X : STA.b $0C
  LDA.b #$08 : CLC : ADC.b $0F : STA.b $0D
  STZ.b $0E
  JSR PigMoblin_EmitPiece
  ; Piece 1: Sword Tip ($E7, 8x8, dx=-11-lunge, dy=+8+bob)
  LDA.b #$E7 : STA.b $0B
  LDA.b $0C : SEC : SBC.b #$08 : STA.b $0C
  JSR PigMoblin_EmitPiece
  ; Piece 2: RT Head H-flipped ($E0, 16x16, dx=0, dy=-4+bob)
  LDA.b #$E0 : STA.b $0B
  STZ.b $0C
  LDA.b #$FC : CLC : ADC.b $0F : STA.b $0D
  LDA.b #$02 : STA.b $0E
  JSR PigMoblin_EmitPiece
  ; Piece 3: RT Body H-flipped ($E2 F0 / $E4 F1, 16x16, dx=0, dy=+2+bob)
  PLA : BEQ .lf_b0
    LDA.b #$E4 : BRA .lf_b_set
.lf_b0
    LDA.b #$E2
.lf_b_set
  STA.b $0B
  STZ.b $0C
  LDA.b #$02 : CLC : ADC.b $0F : STA.b $0D
  LDA.b #$02 : STA.b $0E
  JSR PigMoblin_EmitPiece
  BRA .draw_shadow

; --- Facing RIGHT (3): Slot0=SwHilt, Slot1=SwTip, Slot2=Head, Slot3=Body ---
.dir_right
  PLA : PHA
  EOR.b #$FF : INC A : STA.b $0F ; bob = 0 or -1
  ; Piece 0: Sword Hilt ($E6, 8x8, dx=+11+lunge, dy=+8+bob)
  LDA.b #$E6 : STA.b $0B
  LDA.b #$0B : CLC : ADC.w SprMiscB, X : STA.b $0C
  LDA.b #$08 : CLC : ADC.b $0F : STA.b $0D
  STZ.b $0E
  JSR PigMoblin_EmitPiece
  ; Piece 1: Sword Tip ($E7, 8x8, dx=+19+lunge, dy=+8+bob)
  LDA.b #$E7 : STA.b $0B
  LDA.b $0C : CLC : ADC.b #$08 : STA.b $0C
  JSR PigMoblin_EmitPiece
  ; Piece 2: RT Head ($E0, 16x16, dx=0, dy=-4+bob)
  LDA.b #$E0 : STA.b $0B
  STZ.b $0C
  LDA.b #$FC : CLC : ADC.b $0F : STA.b $0D
  LDA.b #$02 : STA.b $0E
  JSR PigMoblin_EmitPiece
  ; Piece 3: RT Body ($E2 F0 / $E4 F1, 16x16, dx=0, dy=+2+bob)
  PLA : BEQ .rt_b0
    LDA.b #$E4 : BRA .rt_b_set
.rt_b0
    LDA.b #$E2
.rt_b_set
  STA.b $0B
  STZ.b $0C
  LDA.b #$02 : CLC : ADC.b $0F : STA.b $0D
  LDA.b #$02 : STA.b $0E
  JSR PigMoblin_EmitPiece

.draw_shadow
  ; DP $00-$05 remain untouched from Sprite_PrepOamCoord!
  JSL Sprite_DrawShadow
  RTS
}

; ------------------------------------------------------------------------------
; Emit one 16x16 ($0E=$02) or 8x8 ($0E=$00) OAM piece with true SNES 9-bit X
; clipping. Preserves $00-$0F and X; advances Y by +4.
;   In: $06/$07=baseX, $08/$09=baseY, $0A=prop, $0B=chr, $0C=dx, $0D=dy, $0E=size
; ------------------------------------------------------------------------------
PigMoblin_EmitPiece:
{
  LDA.b $0F : PHA ; preserve caller's bob in $0F without touching X

  LDA.b $0C : BPL .dx_pos
    LDA.b #$FF : BRA .dx_hi
.dx_pos
  LDA.b #$00
.dx_hi
  XBA
  LDA.b $0C
  REP #$20
  CLC : ADC.b $06
  BPL .x_nonneg
    ; Negative X: visible iff >= -15 ($FFF1) for 16x16, or >= -7 ($FFF9) for 8x8
    SEP #$20
    XBA : CMP.b #$FF : BNE .hide_x
    XBA
    PHA
    LDA.b $0E : BNE .clip16
      PLA : CMP.b #$F9 : BCC .hide_x
      BRA .x_neg_ok
.clip16
    PLA : CMP.b #$F1 : BCC .hide_x
.x_neg_ok
    STA.b ($90), Y
    LDA.b $0E : ORA.b #$01 : STA.b $0F ; X-MSB=1 | size
    BRA .do_y

.x_nonneg
  CMP.w #$0100 : BCS .hide_x16
  SEP #$20
  STA.b ($90), Y
  LDA.b $0E : STA.b $0F ; X-MSB=0 | size

.do_y
  INY
  LDA.b $0D : BPL .dy_pos
    LDA.b #$FF : BRA .dy_hi
.dy_pos
  LDA.b #$00
.dy_hi
  XBA
  LDA.b $0D
  REP #$20
  CLC : ADC.b $08
  CMP.w #$00E0 : BCS .hide_y16
  SEP #$20
  STA.b ($90), Y
  BRA .write_tail

.hide_x16
  SEP #$20
.hide_x
  LDA.b #$00 : STA.b ($90), Y
  INY
  BRA .hide_y
.hide_y16
  SEP #$20
.hide_y
  LDA.b #$F0 : STA.b ($90), Y
  STZ.b $0F

.write_tail
  INY
  LDA.b $0B : STA.b ($90), Y
  INY
  LDA.b $0A : STA.b ($90), Y
  PHY
  TYA : LSR #2 : TAY
  LDA.b $0F : STA.b ($92), Y
  PLY
  INY ; advance Y to next OAM slot (+4 total)
  PLA : STA.b $0F ; restore caller's bob
  RTS
}

; ------------------------------------------------------------------------------
; 5-Frame Staged NMI VRAM Streamer — tail-called from LyraSea_NmiUpload (Bank $32).
; Entry: M=8, X=16, DBR=$00; DMA0=$1801, VMAIN=$80. Peak DMA <= 256B/frame.
; Exit:  A, X, Y, P, DBR preserved; $4304=$7E, $4302=$0ADC restored cleanly.
; ------------------------------------------------------------------------------
PigMoblin_NmiUpload:
{
  PHP : PHA
  LDA.l PigMoblin_VramState : BPL .fast_exit

  ; Upload only during active gameplay modules ($07 Indoors, $09 OW, $0B Special OW).
  LDA.b $10 : CMP.b #$07 : BEQ .mod_ok
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BEQ .mod_ok
.fast_exit
  PLA : PLP : RTL

.mod_ok
  PHX : PHY
  LDA.b #PigMoblin_GfxStart>>16 : STA.w $4304

  LDA.l PigMoblin_VramState
  CMP.b #$81 : BEQ .stage2
  CMP.b #$82 : BEQ .stage3
  CMP.b #$83 : BNE + : JMP .stage4 : +
  CMP.b #$84 : BNE + : JMP .stage5 : +

  ; --- Stage 1 ($80 -> $81): UpHead ($C0) + UpBody0 ($C2) ---
  LDX.w #$5C00 : LDY.w #PigMoblin_UpHeadTop  : JSR .dma_row
  LDX.w #$5D00 : LDY.w #PigMoblin_UpHeadBot  : JSR .dma_row
  LDX.w #$5C20 : LDY.w #PigMoblin_UpBody0Top : JSR .dma_row
  LDX.w #$5D20 : LDY.w #PigMoblin_UpBody0Bot : JSR .dma_row
  LDA.b #$81 : STA.l PigMoblin_VramState
  JMP .restore

.stage2
  ; --- Stage 2 ($81 -> $82): DnHead ($C4) + DnBody0 ($C6) ---
  LDX.w #$5C40 : LDY.w #PigMoblin_DnHeadTop  : JSR .dma_row
  LDX.w #$5D40 : LDY.w #PigMoblin_DnHeadBot  : JSR .dma_row
  LDX.w #$5C60 : LDY.w #PigMoblin_DnBody0Top : JSR .dma_row
  LDX.w #$5D60 : LDY.w #PigMoblin_DnBody0Bot : JSR .dma_row
  LDA.b #$82 : STA.l PigMoblin_VramState
  JMP .restore

.stage3
  ; --- Stage 3 ($82 -> $83): UpBody1 ($CC) + DnBody1 ($CE) ---
  LDX.w #$5CC0 : LDY.w #PigMoblin_UpBody1Top : JSR .dma_row
  LDX.w #$5DC0 : LDY.w #PigMoblin_UpBody1Bot : JSR .dma_row
  LDX.w #$5CE0 : LDY.w #PigMoblin_DnBody1Top : JSR .dma_row
  LDX.w #$5DE0 : LDY.w #PigMoblin_DnBody1Bot : JSR .dma_row
  LDA.b #$83 : STA.l PigMoblin_VramState
  BRA .restore

.stage4
  ; --- Stage 4 ($83 -> $84): RtHead ($E0) + RtBody0 ($E2) ---
  LDX.w #$5E00 : LDY.w #PigMoblin_RtHeadTop  : JSR .dma_row
  LDX.w #$5F00 : LDY.w #PigMoblin_RtHeadBot  : JSR .dma_row
  LDX.w #$5E20 : LDY.w #PigMoblin_RtBody0Top : JSR .dma_row
  LDX.w #$5F20 : LDY.w #PigMoblin_RtBody0Bot : JSR .dma_row
  LDA.b #$84 : STA.l PigMoblin_VramState
  BRA .restore

.stage5
  ; --- Stage 5 ($84 -> $01): RtBody1 ($E4) + Swords ($E6/$E7/$F6/$F7) ---
  LDX.w #$5E40 : LDY.w #PigMoblin_RtBody1Top : JSR .dma_row
  LDX.w #$5F40 : LDY.w #PigMoblin_RtBody1Bot : JSR .dma_row
  LDX.w #$5E60 : LDY.w #PigMoblin_SwordsTop  : JSR .dma_row
  LDX.w #$5F60 : LDY.w #PigMoblin_SwordsBot  : JSR .dma_row
  LDA.b #$01 : STA.l PigMoblin_VramState

.restore
  LDA.b #$7E : STA.w $4304
  REP #$20
  LDA.w $0ADC : STA.w $4302
  SEP #$20
  PLY : PLX : PLA : PLP
  RTL

.dma_row
  STX.w $2116
  STY.w $4302
  REP #$20
  LDA.w #$0040 : STA.w $4305
  SEP #$20
  LDA.b #$01 : STA.w $420B
  RTS
}

; ------------------------------------------------------------------------------
; GameyFireBro Armed Pig Moblin 4BPP tiles (1,280 bytes = 10 x 16x16 blocks).
; Source: Data/graphics/sprites/gameyfirebro/pig_moblins/sheet.4bpp
; Remapped to LW/UW/DW/Abyss-invariant OAM colors 9..15 (Pal 4 Green / Pal 2 Blue).
; Verified byte-exact by Tests/test_pig_moblin.py.
; ------------------------------------------------------------------------------
PigMoblin_GfxStart:
PigMoblin_UpHeadTop:
  db $7F,$00,$7F,$3B,$7F,$3F,$3F,$17,$1F,$0F,$3F,$1F,$7F,$1F,$FF,$5F
  db $7F,$7F,$7F,$7F,$7F,$7F,$3F,$3F,$1F,$1F,$3F,$3F,$7F,$7F,$FF,$FF
  db $FF,$00,$FF,$D7,$FF,$FF,$FF,$FA,$FE,$FC,$FF,$FE,$FF,$FE,$FF,$FE
  db $FF,$FF,$DF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF
PigMoblin_UpHeadBot:
  db $FF,$9F,$FF,$4F,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
  db $FF,$FF,$FF,$FF,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
  db $FF,$FE,$FF,$FC,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
  db $FF,$FF,$FF,$FF,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
PigMoblin_UpBody0Top:
  db $00,$00,$7F,$2F,$FF,$4F,$FF,$27,$FF,$59,$FD,$4A,$FE,$53,$FF,$57
  db $00,$00,$7F,$7F,$FF,$FF,$FF,$FF,$E7,$FF,$F7,$FF,$FD,$FF,$F8,$FF
  db $00,$00,$FF,$FF,$FF,$FF,$FF,$FE,$FF,$F9,$FB,$06,$07,$FD,$FF,$F9
  db $00,$00,$FF,$FF,$FF,$FF,$FF,$FF,$FE,$FF,$FD,$FF,$FB,$FF,$07,$FF
PigMoblin_UpBody0Bot:
  db $7F,$27,$3F,$17,$1F,$0F,$1F,$03,$1F,$0C,$1F,$0F,$1F,$01,$00,$00
  db $78,$7F,$38,$3F,$10,$1F,$1C,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$00,$00
  db $FF,$FD,$FF,$CD,$FF,$36,$FF,$B4,$FE,$60,$FF,$00,$FF,$00,$00,$00
  db $03,$FF,$33,$FF,$F9,$FF,$7B,$FF,$FE,$FE,$FF,$FF,$FF,$FF,$00,$00
PigMoblin_DnHeadTop:
  db $FF,$00,$FF,$77,$FF,$7F,$7F,$23,$3F,$11,$7F,$30,$7F,$18,$7E,$09
  db $FF,$FF,$FF,$FF,$FF,$FF,$7F,$7F,$37,$3F,$73,$7F,$59,$7F,$4F,$7F
  db $FF,$00,$FF,$AE,$FF,$FE,$FE,$C4,$FC,$88,$FE,$0C,$FE,$18,$7E,$90
  db $FF,$FF,$BF,$FF,$FF,$FF,$FE,$FE,$EC,$FC,$CE,$FE,$9A,$FE,$F2,$FE
PigMoblin_DnHeadBot:
  db $78,$07,$7A,$05,$78,$07,$FF,$40,$00,$00,$00,$00,$00,$00,$00,$00
  db $4F,$7F,$47,$7F,$67,$7F,$FF,$FF,$00,$00,$00,$00,$00,$00,$00,$00
  db $1E,$E0,$5E,$A0,$21,$DE,$DE,$21,$00,$00,$00,$00,$00,$00,$00,$00
  db $F2,$FE,$FE,$FE,$E1,$FF,$DE,$FF,$00,$00,$00,$00,$00,$00,$00,$00
PigMoblin_DnBody0Top:
  db $F0,$0F,$FF,$80,$EF,$3F,$17,$1F,$17,$1F,$17,$1F,$17,$1F,$07,$1F
  db $CF,$FF,$FF,$FF,$DF,$FF,$0F,$1F,$0F,$1F,$0F,$1F,$0F,$1F,$1F,$1F
  db $42,$BC,$BD,$42,$C3,$3C,$99,$42,$BD,$42,$BD,$42,$99,$42,$C2,$A4
  db $C2,$FE,$BD,$FF,$C3,$FF,$A5,$FF,$81,$FF,$81,$FF,$A5,$FF,$DA,$FE
PigMoblin_DnBody0Bot:
  db $1F,$07,$1F,$18,$1F,$18,$1F,$00,$0F,$00,$00,$00,$00,$00,$00,$00
  db $1F,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$0F,$0F,$00,$00,$00,$00,$00,$00
  db $E4,$98,$F8,$00,$F8,$00,$F0,$00,$C0,$00,$00,$00,$00,$00,$00,$00
  db $E4,$FC,$F8,$F8,$F8,$F8,$F0,$F0,$C0,$C0,$00,$00,$00,$00,$00,$00
PigMoblin_UpBody1Top:
  db $00,$00,$3F,$0F,$7F,$2F,$FF,$47,$FF,$29,$FD,$56,$FE,$5B,$FF,$59
  db $00,$00,$3F,$3F,$7F,$7F,$FF,$FF,$F7,$FF,$FB,$FF,$FD,$FF,$FE,$FF
  db $00,$00,$FF,$FF,$FF,$FF,$FF,$FE,$FF,$F9,$FB,$05,$07,$FC,$FF,$FE
  db $00,$00,$FF,$FF,$FF,$FF,$FF,$FF,$FE,$FF,$FE,$FF,$FB,$FF,$01,$FF
PigMoblin_UpBody1Bot:
  db $FF,$5B,$7F,$1B,$3F,$06,$1F,$02,$07,$00,$0F,$00,$0F,$00,$00,$00
  db $FC,$FF,$7C,$7F,$39,$3F,$1D,$1F,$07,$07,$0F,$0F,$0F,$0F,$00,$00
  db $FF,$FE,$FF,$3E,$FF,$CF,$FF,$DC,$FF,$63,$FF,$0F,$FF,$08,$00,$00
  db $01,$FF,$C1,$FF,$F0,$FF,$E3,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$00,$00
PigMoblin_DnBody1Top:
  db $E0,$1F,$FF,$00,$DF,$BE,$0F,$1E,$0F,$1E,$0F,$1E,$0F,$1E,$0F,$1F
  db $9F,$FF,$FF,$FF,$FF,$FF,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$1F
  db $84,$78,$7A,$84,$86,$78,$32,$84,$7A,$84,$7A,$84,$32,$84,$84,$48
  db $84,$FC,$7A,$FE,$86,$FE,$4A,$FE,$02,$FE,$02,$FE,$4A,$FE,$B4,$FC
PigMoblin_DnBody1Bot:
  db $1F,$0F,$1F,$00,$1F,$00,$1F,$00,$1F,$00,$00,$00,$00,$00,$00,$00
  db $1F,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$1F,$00,$00,$00,$00,$00,$00
  db $C8,$30,$F0,$C0,$F0,$C0,$E0,$00,$80,$00,$00,$00,$00,$00,$00,$00
  db $C8,$F8,$F0,$F0,$D0,$F0,$E0,$E0,$80,$80,$00,$00,$00,$00,$00,$00
PigMoblin_RtHeadTop:
  db $F7,$00,$FF,$77,$FF,$7F,$FF,$1E,$3F,$0F,$3F,$1F,$7F,$3F,$7F,$3F
  db $F7,$F7,$FF,$FF,$FF,$FF,$FF,$FF,$3F,$3F,$3F,$3F,$7F,$7F,$7F,$7F
  db $80,$00,$E0,$80,$F0,$E0,$F8,$60,$F4,$28,$E4,$18,$EC,$90,$E4,$78
  db $80,$80,$E0,$E0,$F0,$F0,$F8,$F8,$FC,$FC,$BC,$FC,$9C,$FC,$7C,$FC
PigMoblin_RtHeadBot:
  db $7F,$3F,$7F,$3F,$3F,$0F,$2F,$10,$00,$00,$00,$00,$00,$00,$00,$00
  db $7F,$7F,$7F,$7F,$3F,$3F,$3F,$3F,$00,$00,$00,$00,$00,$00,$00,$00
  db $E4,$18,$FE,$00,$F9,$76,$FF,$00,$00,$00,$00,$00,$00,$00,$00,$00
  db $1C,$FC,$7E,$FE,$FB,$FF,$FF,$FF,$00,$00,$00,$00,$00,$00,$00,$00
PigMoblin_RtBody0Top:
  db $00,$00,$00,$00,$7F,$3F,$7F,$3F,$3F,$0F,$2F,$10,$2F,$1B,$5F,$3B
  db $00,$00,$00,$00,$7F,$7F,$7F,$7F,$3F,$3F,$3F,$3F,$37,$3F,$67,$7F
  db $00,$00,$00,$00,$E4,$18,$FE,$00,$F9,$76,$FF,$00,$F9,$66,$FB,$84
  db $00,$00,$00,$00,$1C,$FC,$7E,$FE,$FB,$FF,$FF,$FF,$FF,$FF,$FD,$FF
PigMoblin_RtBody0Bot:
  db $5F,$39,$BF,$7F,$CF,$3E,$F0,$4F,$FF,$70,$7F,$38,$3F,$00,$00,$00
  db $67,$7F,$C1,$FF,$F1,$FF,$FF,$FF,$FF,$FF,$7F,$7F,$3F,$3F,$00,$00
  db $FC,$B0,$F8,$74,$F0,$6C,$78,$94,$FC,$00,$F8,$00,$F0,$00,$00,$00
  db $FC,$FC,$F8,$FC,$F0,$FC,$F8,$FC,$FC,$FC,$F8,$F8,$F0,$F0,$00,$00
PigMoblin_RtBody1Top:
  db $00,$00,$00,$00,$1F,$0F,$1F,$0F,$0F,$03,$0B,$04,$0B,$05,$17,$0D
  db $00,$00,$00,$00,$1F,$1F,$1F,$1F,$0F,$0F,$0F,$0F,$0F,$0F,$1B,$1F
  db $00,$00,$00,$00,$F9,$C6,$FF,$C0,$E3,$DC,$FE,$01,$FF,$B8,$FE,$99
  db $00,$00,$00,$00,$C7,$FF,$DF,$FF,$FF,$FF,$FE,$FF,$FF,$FF,$FF,$FF
PigMoblin_RtBody1Bot:
  db $2F,$1D,$2F,$1D,$17,$0C,$0B,$05,$0F,$01,$1F,$00,$1F,$01,$00,$00
  db $33,$3F,$33,$3F,$1B,$1F,$0F,$0F,$0F,$0F,$1F,$1F,$1F,$1F,$00,$00
  db $FC,$A8,$FC,$80,$D8,$20,$90,$60,$D8,$A0,$FC,$00,$FC,$E0,$00,$00
  db $DC,$FC,$FC,$FC,$DC,$FC,$9C,$FC,$DC,$FC,$FC,$FC,$FC,$FC,$00,$00
PigMoblin_SwordsTop:
  db $00,$00,$00,$00,$FF,$00,$B3,$40,$26,$C0,$B3,$40,$EF,$00,$00,$00
  db $00,$00,$00,$00,$FF,$FF,$BC,$FF,$39,$FF,$BC,$FF,$EF,$EF,$00,$00
  db $00,$00,$00,$00,$F8,$00,$FC,$00,$06,$00,$FC,$00,$F8,$00,$00,$00
  db $00,$00,$00,$00,$F8,$F8,$04,$FC,$FA,$FE,$04,$FC,$F8,$F8,$00,$00
PigMoblin_SwordsBot:
  db $3C,$04,$2C,$10,$44,$38,$7C,$00,$2C,$04,$44,$00,$54,$00,$7C,$00
  db $38,$3C,$2C,$3C,$44,$7C,$7C,$7C,$38,$3C,$7C,$7C,$6C,$7C,$44,$7C
  db $6C,$00,$6C,$00,$6C,$00,$6C,$00,$6C,$00,$6C,$00,$38,$00,$10,$00
  db $54,$7C,$54,$7C,$54,$7C,$54,$7C,$54,$7C,$54,$7C,$28,$38,$10,$10
PigMoblin_GfxEnd:

assert PigMoblin_GfxEnd-PigMoblin_GfxStart == $0500, "PigMoblin GFX must be 1280 bytes (10 x 16x16)"
assert (PigMoblin_GfxStart>>16) == ((PigMoblin_GfxEnd-1)>>16), "PigMoblin DMA source crossed bank"

PigMoblin_CodeEnd:
print "Pig Moblin bytes: ", dec(PigMoblin_CodeEnd-PigMoblin_CodeStart)
