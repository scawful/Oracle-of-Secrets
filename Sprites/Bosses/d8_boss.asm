; =========================================================
; D8 Sky boss — mechanics prototype (first playable slice)
;
; Gated by !ENABLE_D8_BOSS (default 0). Included from the bank $2C sprite
; stream in Sprites/all_sprites.asm. No room places this sprite: native
; tests spawn it by savestate + RAM poke (see the AFS mech17 NOTES.md).
;
; Decided rules (scawful 2026-11-03):
;   - A Somaria block resting on one fixed socket qualifies the cycle.
;     Only a qualified cycle lowers and opens the eye for one credited
;     sword punish. An unqualified cycle attacks, closes and resets.
;     The block is not a reflector and not a platform.
;   - A credited hit shatters the block.
;   - Hit counter, not HP: 2 credited punishes per stage, any sword.
;     Contact frames within one opening count once (the eye closes on
;     the first credit). 3 stages, then death.
;   - Stage 1 one marked weight slam, stage 2 one remaining weight shunt,
;     stage 3 one fixed lane beam. Weights bump class $05, beam $06.
;   - Each stage break drops one vanilla small magic jar ($DF).
;   - A fairy revival keeps the stage, hit count and credited damage
;     (sprite RAM is not reset). It cancels the current attack and resumes
;     at a closed neutral pose followed by a full tell (D8Boss_Long).
;   - Death hands off to the existing Sky award (Dungeons/sky_d8_award.asm).
; Proposals (named constants below): socket position, all frame timings,
; lane geometry, recoil time, sprite ID $C3, placeholder CHR.
;
; Credit mechanism: !ImperviousAll = 01 keeps HP untouched
; (Sprite_CalculateSwordDamage $06ED3F returns at once when $0E60 bit 6 is
; set). !ImpervSwordHammer = 01 makes Sprite_CheckDamageFromLink ($06F2B4)
; take the tink path at $06F3A2 ($0CAA bit 2). In the Open state only, bit 2
; is cleared for the call, so carry set means the sword reached the zap path
; at $06F3A9, which is the credited hit. The tink path also returns carry
; set, so carry is ignored outside the Open state.
;
; The boss never calls Sprite_CheckDamageToPlayer: the shell has no contact
; damage. Only the marked lane / beam boxes hurt Link.
; =========================================================

Sprite_D8Boss = $C3

; =========================================================
; Named constants (proposals unless noted)

!D8Boss_TellTime       = 40   ; frames, every stage
!D8Boss_BreakHoldTime  = 30   ; frames of stable silhouette after a break
!D8Boss_RecoilTime     = 32   ; frames of shuttered recoil after a credit
!D8Boss_HitsPerStage   = 2    ; decided
!D8Boss_LastStage      = 2    ; stages 0,1,2 (decided: 3 stages)
!D8Boss_SocketX        = 64   ; room-relative pixel, Somaria block center
!D8Boss_SocketY        = 440  ; room-relative pixel, Somaria block center
!D8Boss_SocketTol      = 8    ; pixels, per axis
!D8Boss_SomariaBlock   = $2C  ; ancilla ID, Ancilla2C_SomariaBlock
!D8Boss_SomariaFizz    = $2D  ; ancilla ID, Ancilla2D_SomariaBlockFizz
!D8Boss_SocketSFX      = $25  ; SFX3, same as the socket door open sound
!D8Boss_JarID          = $DF  ; vanilla small magic jar (decided)
!D8Boss_JarDropY       = 24   ; pixels below the boss origin
!D8Boss_JarZSpeed      = $18  ; $0F80 upward speed for the drop bounce
!D8Boss_WeightBump     = $05  ; damage class: 2 / 1 / 1/2 hearts (decided)
!D8Boss_BeamBump       = $06  ; damage class: 4 / 2 / 1 hearts (decided)

; Sprite RAM use
D8Boss_Stage     = SprMiscA   ; $0DA0: 0..2
D8Boss_Hits      = SprMiscB   ; $0DB0: credited punishes in this stage
D8Boss_Qualified = SprMiscC   ; $0DE0: 1 while a block rests on the socket
D8Boss_Lane      = SprMiscE   ; $0EB0: weight lane 0/1, flips every cycle

; =========================================================
; Sprite properties

!SPRID              = Sprite_D8Boss
!NbrTiles           = 08  ; Max OAM entries per frame (body 4 + beam 4)
!Harmless           = 00
!HVelocity          = 00
!Health             = 100 ; Unused: ImperviousAll keeps HP untouched
!Damage             = 00  ; SprBump is set per attack before damage
!DeathAnimation     = 00
!ImperviousAll      = 01  ; HP never changes; credits are counted instead
!SmallShadow        = 00
!Shadow             = 00
!Palette            = 00
!Hitbox             = 09  ; 24x24 at (-4,-4) (Sprite_SetupHitBox table)
!Persist            = 01
!Statis             = 00
!CollisionLayer     = 00
!CanFall            = 00
!DeflectArrow       = 01
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 00
!Sound              = 00
!Interaction        = 00
!Statue             = 00
!DeflectProjectiles = 00
!ImperviousArrow    = 01
!ImpervSwordHammer  = 01  ; tink while closed; cleared per frame when open
!Boss               = 01
%Set_Sprite_Properties(Sprite_D8Boss_Prep, Sprite_D8Boss_Long)

; =========================================================

Sprite_D8Boss_Long:
{
  PHB : PHK : PLB
  ; Only draw while active ($0DD0 == $09); the explode module owns death.
  LDA.w SprState, X : CMP.b #$09 : BNE .skip_draw
    ; Link died this frame: Link_Main stores HP 0 before Sprite_Main runs,
    ; and module $12 never runs sprites, so this pose holds through a fairy
    ; revival. This runs before Sprite_CheckActive, which fails while $11
    ; is set. Recoil, Break and Death (4-6) finish so a credit is not lost.
    LDA.l CurrentHealth : BNE .link_alive
      LDA.w SprAction, X : CMP.b #$04 : BCS .link_alive
        JSR D8Boss_ToClosed
    .link_alive
    JSR Sprite_D8Boss_Draw
  .skip_draw
  JSL Sprite_CheckActive : BCC .inactive
    JSR Sprite_D8Boss_Main
  .inactive
  PLB
  RTL
}

; =========================================================

Sprite_D8Boss_Prep:
{
  ; Heart prize already collected ($0403 bit 7): do not spawn.
  %BossPrep_ExitIfDefeated()
  PHB : PHK : PLB
  LDA.w SprDefl, X : ORA.b #$80 : STA.w SprDefl, X ; keep running offscreen
  STZ.w SprAction, X
  STZ.w SprGfx, X
  STZ.w SprFrame, X
  STZ.w SprFlash, X
  STZ.w D8Boss_Stage, X
  STZ.w D8Boss_Hits, X
  STZ.w D8Boss_Qualified, X
  STZ.w D8Boss_Lane, X
  LDA.w D8Boss_RestTime : STA.w SprTimerA, X ; stage 0 rest
  PLB
  RTL
}

; =========================================================
; Per-stage timing tables (frames), indexed by D8Boss_Stage.

D8Boss_ActiveTime:
  db 12, 18, 24
D8Boss_OpenTime:
  db 90, 90, 96
D8Boss_RestTime:
  db 30, 24, 30

; =========================================================
; State machine
;
; | # | State  | Exit                                                    |
; | 0 | Closed | rest timer ends -> Tell, lane flips                     |
; | 1 | Tell   | tell timer ends -> Active                               |
; | 2 | Active | timer ends: qualified -> Open, else -> Closed           |
; | 3 | Open   | credit -> Recoil (block shatters); timeout -> Closed     |
; | 4 | Recoil | hits < 2 -> Closed; stage < 2 -> Break; else -> Death   |
; | 5 | Break  | hold ends -> Tell                                       |
; | 6 | Death  | vanilla boss death; explode module takes over           |

Sprite_D8Boss_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw D8Boss_Closed ; 0x00
  dw D8Boss_Tell   ; 0x01
  dw D8Boss_Active ; 0x02
  dw D8Boss_Open   ; 0x03
  dw D8Boss_Recoil ; 0x04
  dw D8Boss_Break  ; 0x05
  dw D8Boss_Death  ; 0x06
}

; ---------------------------------------------------------

D8Boss_Closed:
{
  STZ.w SprFrame, X
  JSR D8Boss_UpdateSocket
  JSL Sprite_CheckDamageFromPlayer ; tink feedback only; carry ignored
  LDA.w SprTimerA, X : BNE .wait
    LDA.w D8Boss_Lane, X : EOR.b #$01 : STA.w D8Boss_Lane, X
    LDA.b #!D8Boss_TellTime : STA.w SprTimerA, X
    %GotoAction(1)
  .wait
  RTS
}

; ---------------------------------------------------------

D8Boss_Tell:
{
  JSR D8Boss_SetAttackFrame
  JSR D8Boss_UpdateSocket
  JSL Sprite_CheckDamageFromPlayer ; tink feedback only; carry ignored
  LDA.w SprTimerA, X : BNE .wait
    LDY.w D8Boss_Stage, X
    LDA.w D8Boss_ActiveTime, Y : STA.w SprTimerA, X
    %GotoAction(2)
  .wait
  RTS
}

; ---------------------------------------------------------

D8Boss_Active:
{
  JSR D8Boss_SetAttackFrame
  JSR D8Boss_UpdateSocket
  JSL Sprite_CheckDamageFromPlayer ; tink feedback only; carry ignored
  JSR D8Boss_AttackHitTest
  LDA.w SprTimerA, X : BNE .wait
    ; The attack is over. A block resting on the socket now qualifies.
    LDA.w D8Boss_Qualified, X : BEQ .unqualified
      LDY.w D8Boss_Stage, X
      LDA.w D8Boss_OpenTime, Y : STA.w SprTimerA, X
      %GotoAction(3)
      RTS
    .unqualified
    JMP D8Boss_ToClosed
  .wait
  RTS
}

; ---------------------------------------------------------

D8Boss_Open:
{
  LDA.b #$01 : STA.w SprFrame, X
  ; Accept one sword hit: clear "impervious to sword/hammer" for this call.
  LDA.w SprDefl, X : AND.b #$FB : STA.w SprDefl, X
  JSL Sprite_CheckDamageFromPlayer
  ; LDA/AND/ORA/STA leave carry intact.
  LDA.w SprDefl, X : ORA.b #$04 : STA.w SprDefl, X
  BCC .no_credit
    ; $0301 & $0A: hammer in use (same test as $06F2DD). Not credited.
    LDA.w $0301 : AND.b #$0A : BNE .no_credit
    ; $037A & $10: fist/net swing (Items/fist_damage.asm FistBump2). Not credited.
    LDA.w $037A : AND.b #$10 : BNE .no_credit
      JSR D8Boss_ShatterBlock
      INC.w D8Boss_Hits, X
      STZ.w D8Boss_Qualified, X
      STZ.w SprFrame, X
      LDA.b #!D8Boss_RecoilTime : STA.w SprTimerA, X
      %GotoAction(4)
      RTS
  .no_credit
  LDA.w SprTimerA, X : BNE .wait
    JMP D8Boss_ToClosed
  .wait
  RTS
}

; ---------------------------------------------------------

D8Boss_Recoil:
{
  STZ.w SprFrame, X
  ; Placeholder hit feedback: cycle the OAM palette bits every 2 frames.
  LDA.b $1A : AND.b #$0E : STA.w SprFlash, X
  LDA.w SprTimerA, X : BNE .wait
    STZ.w SprFlash, X
    LDA.w D8Boss_Hits, X : CMP.b #!D8Boss_HitsPerStage : BCS .quota
      JMP D8Boss_ToClosed
    .quota
    LDA.w D8Boss_Stage, X : CMP.b #!D8Boss_LastStage : BCS .dead
      INC.w D8Boss_Stage, X
      STZ.w D8Boss_Hits, X
      STZ.w D8Boss_Qualified, X
      JSR D8Boss_DropJar
      LDA.b #!D8Boss_BreakHoldTime : STA.w SprTimerA, X
      %GotoAction(5)
      RTS
    .dead
    %GotoAction(6)
  .wait
  RTS
}

; ---------------------------------------------------------

D8Boss_Break:
{
  ; Harmless hold: no socket check, no attack box. Shell still tinks.
  STZ.w SprFrame, X
  JSL Sprite_CheckDamageFromPlayer ; tink feedback only; carry ignored
  LDA.w SprTimerA, X : BNE .wait
    LDA.w D8Boss_Lane, X : EOR.b #$01 : STA.w D8Boss_Lane, X
    LDA.b #!D8Boss_TellTime : STA.w SprTimerA, X
    %GotoAction(1)
  .wait
  RTS
}

; ---------------------------------------------------------
; Mirrors the vanilla boss death branch (Sprite_KillFriends at $06F05E,
; $06F062-$06F06F, Sprite_BossScreamAndDisableMenu $06F087-$06F093).
; SpriteModule_Explode ($09ED9F) then runs; Explode_VerifyPrizing ($09EE0F)
; spawns the heart container ($EA) once the screen is clear (type $C3 is
; below $D6). Picking it up sets $0403 bit 7, which SkyD8_HeartPrizeTag
; (Dungeons/sky_d8_award.asm, hook $01C709) turns into the Sky crystal when
; the room header carries the heart-prize tag.

D8Boss_Death:
{
  JSL Sprite_KillFriends
  LDA.b #$04 : STA.w SprState, X
  STZ.w SprFrame, X
  STZ.w SprFlash, X
  LDA.b #$FF : STA.w SprTimerA, X : STA.w SprDeath, X
  INC.w $0FFC
  STZ.w $012F
  LDA.b #$22 : JSL SpriteSFX_QueueSFX3WithPan
  RTS
}

; ---------------------------------------------------------

D8Boss_ToClosed:
{
  STZ.w D8Boss_Qualified, X
  STZ.w SprFrame, X
  LDY.w D8Boss_Stage, X
  LDA.w D8Boss_RestTime, Y : STA.w SprTimerA, X
  %GotoAction(0)
  RTS
}

; ---------------------------------------------------------
; Frame for Tell/Active: weight lane A/B in stages 0-1, beam in stage 2.

D8Boss_SetAttackFrame:
{
  LDA.w D8Boss_Stage, X : CMP.b #!D8Boss_LastStage : BCC .weight
    LDA.b #$04 : STA.w SprFrame, X
    RTS
  .weight
  LDA.w D8Boss_Lane, X : CLC : ADC.b #$02 : STA.w SprFrame, X
  RTS
}

; =========================================================
; Socket qualification
;
; D8Boss_Qualified follows the socket each frame in Closed/Tell/Active:
; set while a block rests there (SFX on the first frame), cleared when it
; leaves. Active's last frame reads it.

D8Boss_UpdateSocket:
{
  JSR D8Boss_FindSocketedBlock : BCC .absent
    LDA.w D8Boss_Qualified, X : BNE .done
      LDA.b #$01 : STA.w D8Boss_Qualified, X
      %PlaySFX2(!D8Boss_SocketSFX)
    .done
    RTS
  .absent
  STZ.w D8Boss_Qualified, X
  RTS
}

; ---------------------------------------------------------
; Return carry set and Y = ancilla slot when a live Somaria block rests on
; the socket. Same block gates as RoomTag_SomariaSocketDoor
; (Dungeons/custom_tag.asm; Ancilla2C .run_trigger $08E3A3) without the
; switch-tile test ($03DB): the socket is a position, not a switch tile.
; Block center: X = $0C18:$0C04, Y = $0C0E:$0BFA (probe offsets are +/-4).
; Clobbers A, Y. X is preserved.

D8Boss_FindSocketedBlock:
{
  BIT.w $0308 : BMI .none ; Link is carrying: no block is resting
  LDY.b #$04
  .next_slot
    LDA.w $0C4A, Y : CMP.b #!D8Boss_SomariaBlock : BNE .skip_slot
    LDA.w $0394, Y : BNE .skip_slot ; spawn delay not over
    LDA.w $03C5, Y : BNE .skip_slot
    LDA.w $0380, Y : BNE .skip_slot
    LDA.w $029E, Y : BEQ .grounded  ; altitude $00 or $FF = resting
    CMP.b #$FF : BNE .skip_slot
    .grounded
    LDA.w $0C18, Y : XBA : LDA.w $0C04, Y
    REP #$20
    AND.w #$01FF : SEC : SBC.w #!D8Boss_SocketX : BPL +
      EOR.w #$FFFF : INC A
    +
    CMP.w #!D8Boss_SocketTol+1
    SEP #$20
    BCS .skip_slot
    LDA.w $0C0E, Y : XBA : LDA.w $0BFA, Y
    REP #$20
    AND.w #$01FF : SEC : SBC.w #!D8Boss_SocketY : BPL +
      EOR.w #$FFFF : INC A
    +
    CMP.w #!D8Boss_SocketTol+1
    SEP #$20
    BCS .skip_slot
      SEC
      RTS
  .skip_slot
    DEY : BPL .next_slot
  .none
  CLC
  RTS
}

; ---------------------------------------------------------
; Credited hit: shatter the live Somaria block wherever it is. Link may have
; lifted and moved it after the cycle qualified; it still shatters. Mirrors
; SomariaBlock_FizzleAway ($08E9B2-$08E9E5) on that ancilla slot.

D8Boss_ShatterBlock:
{
  LDY.b #$04
  .next_slot
    LDA.w $0C4A, Y : CMP.b #!D8Boss_SomariaBlock : BEQ .found
    DEY : BPL .next_slot
  RTS
  .found
  PHX
  TYX
  LDA.b $5E : CMP.b #$12 : BNE .keep_speed
    STZ.b $48
    STZ.b $5E
  .keep_speed
  STZ.w $0646
  LDA.b #!D8Boss_SomariaFizz : STA.w $0C4A, X
  STZ.w $03B1, X
  STZ.w $0C54, X
  STZ.w $0C5E, X
  STZ.w $039F, X
  STZ.w $03A4, X
  STZ.w $03EA, X
  TXA : INC A : CMP.w $02EC : BNE .not_tracked
    STZ.w $02EC
    LDA.w $0308 : AND.b #$80 : STA.w $0308
  .not_tracked
  PLX
  RTS
}

; =========================================================
; Attack hit test (Active state only)
;
; Lane box relative to the boss origin (SprX/SprY), 16-bit signed offsets.
; Index 0 = weight lane A, 1 = weight lane B, 2 = stage 3 beam lane.
; Overlap test: Link_SetupHitBox (Core/sprite_functions.asm) as pos1,
; CheckIfHitBoxesOverlap ($0683E6). Damage: Sprite_AttemptDamageToLink-
; PlusRecoil ($06F41F) reads SprBump ($0CD2) as the damage class and
; respects Link's invulnerability timers ($031F, $037B).

D8Boss_AttackHitTest:
{
  LDA.b $EE : CMP.w SprFloor, X : BNE .miss ; Link on another layer
  LDA.w D8Boss_Stage, X : CMP.b #!D8Boss_LastStage : BCC .weight
    LDY.b #$02
    LDA.b #!D8Boss_BeamBump
    BRA .have_lane
  .weight
  LDY.w D8Boss_Lane, X
  LDA.b #!D8Boss_WeightBump
  .have_lane
  STA.w SprBump, X
  JSL Link_SetupHitBox
  LDA.w SprX, X  : CLC : ADC.w .x_low, Y  : STA.b pos2_x_low
  LDA.w SprXH, X :       ADC.w .x_high, Y : STA.b pos2_x_high
  LDA.w SprY, X  : CLC : ADC.w .y_low, Y  : STA.b pos2_y_low
  LDA.w SprYH, X :       ADC.w .y_high, Y : STA.b pos2_y_high
  LDA.w .width, Y  : STA.b pos2_size
  LDA.w .height, Y : STA.b pos2_height
  JSL CheckIfHitBoxesOverlap : BCC .miss
    JSL Sprite_AttemptDamageToPlayerPlusRecoil
  .miss
  RTS

  ;        lane A      lane B      beam
  .x_low
    db $E8,        $08,        $00   ; -24, +8, 0
  .x_high
    db $FF,        $00,        $00
  .y_low
    db $10,        $10,        $18   ; +16, +16, +24
  .y_high
    db $00,        $00,        $00
  .width
    db 32,         32,         16
  .height
    db 80,         80,         64
}

; ---------------------------------------------------------
; Stage break: one vanilla small magic jar ($DF) below the boss.

D8Boss_DropJar:
{
  LDA.b #!D8Boss_JarID
  JSL Sprite_SpawnDynamically : BMI .no_slot
    JSL Sprite_SetSpawnedCoordinates
    LDA.w SprY, Y  : CLC : ADC.b #!D8Boss_JarDropY : STA.w SprY, Y
    LDA.w SprYH, Y : ADC.b #$00 : STA.w SprYH, Y
    LDA.w SprFloor, X : STA.w SprFloor, Y
    LDA.b #$00 : STA.w $0B58, Y ; no despawn countdown
    LDA.b #!D8Boss_JarZSpeed : STA.w $0F80, Y
  .no_slot
  RTS
}

; =========================================================
; Placeholder draw. CHR/palette are not allocated (spriteset unapproved).
; Names follow the boss art SEGMENT_LABELS indices:
;   0 BODY, 1 S1_PART_NW, 2 LID, 3 S2_PART_SE, 4 S3_PART_SW, 5 BEAM,
;   6 B1_DROP_NE, 7 B1_DROP_SW, 8 B2_DROP_NW, 9 B2_DROP_SE, 10 DEATH_CORE,
;   11-15 DEATH_SHARD_SW/NW/NE/S/SE, 16-19 DEATH_CELL_NW/NE/SW/SE.
; Frames:
;   0 closed : BODY (seg 0) top + LID (seg 2) bottom, 4 tiles
;   1 open   : BODY (seg 0) with open eye, 4 tiles
;   2 lane A : closed body + weight S1_PART_NW (seg 1) over lane A
;   3 lane B : closed body + weight S2_PART_SE (seg 3) over lane B
;   4 beam   : closed body + BEAM (seg 5) x4 down the beam lane

Sprite_D8Boss_Draw:
{
  %DrawSprite()

  .start_index
    db $00, $04, $08, $0D, $12
  .nbr_of_tiles
    db 3, 3, 4, 4, 7
  .x_offsets
    dw -8, 8, -8, 8                      ; 0 closed
    dw -8, 8, -8, 8                      ; 1 open
    dw -8, 8, -8, 8, -16                 ; 2 lane A
    dw -8, 8, -8, 8, 16                  ; 3 lane B
    dw -8, 8, -8, 8, 0, 0, 0, 0          ; 4 beam
  .y_offsets
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8
    dw -8, -8, 8, 8, 32
    dw -8, -8, 8, 8, 32
    dw -8, -8, 8, 8, 24, 40, 56, 72
  .chr
    db $00, $02, $20, $22                ; seg 0 BODY / seg 2 LID
    db $04, $06, $24, $26                ; seg 0 BODY, eye open
    db $00, $02, $20, $22, $08           ; + seg 1 S1_PART_NW
    db $00, $02, $20, $22, $0A           ; + seg 3 S2_PART_SE
    db $00, $02, $20, $22, $0C, $0C, $0C, $0C ; + seg 5 BEAM
  .properties
    db $3B, $3B, $3B, $3B
    db $3B, $3B, $3B, $3B
    db $3B, $3B, $3B, $3B, $3B
    db $3B, $3B, $3B, $3B, $3B
    db $3B, $3B, $3B, $3B, $3B, $3B, $3B, $3B
  .sizes
    db $02, $02, $02, $02
    db $02, $02, $02, $02
    db $02, $02, $02, $02, $02
    db $02, $02, $02, $02, $02
    db $02, $02, $02, $02, $02, $02, $02, $02
}
