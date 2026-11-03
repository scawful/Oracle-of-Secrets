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
; beam geometry, recoil time.
; Lane B art = lane A frames mirrored (scawful 2026-11-03: "Yes, mirror is fine").
; Allocation A (scawful 2026-11-03): sprite $C3, dungeon spriteset $2D
; (sheets $1F/$0D/$61/$61) on room $96. The boss uses all 4 sheets of OAM
; name table 1 (scawful 2026-11-03: "all 4"). On the scroll into room $96
; Graphics_Transfer DMAs stage 2 to slots 0-1 (VRAM $5000, chars $00-$5F)
; and stage 1 + beam to slots 2-3 (VRAM $5800, chars $80-$FF). Break 2
; DMAs stage 3 over the stage 1 chars ($80-$DF); the beam chars stay.
; Prep writes sprite palette row 6. Break and death art stream later.
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
; SprFrame values (Sprite_D8Boss_Draw). Lane frames: +0 lane A, +1 lane B.
!D8Boss_FrameIdle      = 0
!D8Boss_FrameRecovery  = 1
!D8Boss_FrameSlam      = 2
!D8Boss_FrameTell      = 4
!D8Boss_FrameRise      = 6
!D8Boss_FrameHit       = 8
!D8Boss_FrameBeam      = 9
!D8Boss_BreakHoldTime  = 30   ; frames of stable silhouette after a break
!D8Boss_RecoilTime     = 32   ; frames of shuttered recoil after a credit
!D8Boss_HitsPerStage   = 2    ; decided
!D8Boss_LastStage      = 2    ; stages 0,1,2 (decided: 3 stages)
!D8Boss_SocketX        = 64   ; room-relative pixel, Somaria block center
!D8Boss_SocketY        = 440  ; room-relative pixel, Somaria block center
!D8Boss_SocketTol      = 8    ; pixels, per axis
; Weight lanes = the two halves of the room $96 arena floor (scawful
; 2026-11-03: "Floor halves"). Room-relative pixels like the socket, so
; they do not move with boss placement. Floor measured from the sky test
; render: x 48-207, y 320-463 (bottom-left quadrant y 64-207). Lanes run
; from the boss body bottom (quadrant y 120) to the floor edge.
!D8Boss_LaneAX         = 48   ; lane A left edge
!D8Boss_LaneBX         = 128  ; lane B left edge (floor center)
!D8Boss_LaneY          = 376  ; top edge, both lanes
!D8Boss_LaneW          = 80
!D8Boss_LaneH          = 88
; Stage 3 beam: boss column (x origin, 16 wide), same rows as the lanes
; (scawful 2026-11-03: "Yes, extend beam"). The 6 drawn beam cells reach
; the floor edge with the boss origin at room y 352 (body bottom on the
; lane top), which the room $96 placement below gives.
!D8Boss_BeamW          = 16
!D8Boss_BeamX          = 3    ; beam lane left edge, px right of SprX (drawn cells)
; Room $96 placement (scawful 2026-11-03: "Yes, place it"): sprite data
; is on a 16 px grid, so the room places tile (7,20) = (112,320) and prep
; shifts the origin to (120,352): body centered on floor x 128, body
; bottom on the lane top, body top (origin y -40) below the HUD
; (scawful 2026-11-03: "Move boss down").
!D8Boss_PlaceShiftX    = 8    ; pixels added to X in prep
!D8Boss_PlaceShiftY    = 32   ; pixels added to Y in prep
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
!NbrTiles           = 28  ; Max OAM entries per frame (22 aligned + 6 beam)
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
  LDA.w SprX, X  : CLC : ADC.b #!D8Boss_PlaceShiftX : STA.w SprX, X
  LDA.w SprXH, X :       ADC.b #$00                : STA.w SprXH, X
  LDA.w SprY, X  : CLC : ADC.b #!D8Boss_PlaceShiftY : STA.w SprY, X
  LDA.w SprYH, X :       ADC.b #$00                : STA.w SprYH, X
  STZ.w SprAction, X
  STZ.w SprGfx, X
  STZ.w SprFrame, X
  STZ.w SprFlash, X
  STZ.w D8Boss_Stage, X
  STZ.w D8Boss_Hits, X
  STZ.w D8Boss_Qualified, X
  STZ.w D8Boss_Lane, X
  LDA.w D8Boss_RestTime : STA.w SprTimerA, X ; stage 0 rest
  JSR D8Boss_LoadPalette
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
  JSR D8Boss_SetTellFrame
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
  LDA.b #!D8Boss_FrameRecovery : STA.w SprFrame, X
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
  LDA.b #!D8Boss_FrameHit : STA.w SprFrame, X
  ; Hit feedback: cycle the OAM palette bits every 2 frames.
  LDA.b $1A : AND.b #$0E : STA.w SprFlash, X
  LDA.w SprTimerA, X : BNE .wait
    STZ.w SprFlash, X
    LDA.w D8Boss_Hits, X : CMP.b #!D8Boss_HitsPerStage : BCS .quota
      JMP D8Boss_ToClosed
    .quota
    LDA.w D8Boss_Stage, X : CMP.b #!D8Boss_LastStage : BCS .dead
      INC.w D8Boss_Stage, X
      ; Break 2: stage 3 tiles replace the stage 1 tiles. This frame draws
      ; stage 2 art (chars $00-$5F), so the swap shows no torn frame.
      LDA.w D8Boss_Stage, X : CMP.b #!D8Boss_LastStage : BNE +
        JSR D8Boss_LoadStage3Gfx
      +
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
; Frame for Active: lane A/B slam, or the beam in the last stage.

D8Boss_SetAttackFrame:
{
  LDA.w D8Boss_Stage, X : CMP.b #!D8Boss_LastStage : BCC .slam
    LDA.b #!D8Boss_FrameBeam : STA.w SprFrame, X
    RTS
  .slam
  LDA.w D8Boss_Lane, X : CLC : ADC.b #!D8Boss_FrameSlam : STA.w SprFrame, X
  RTS
}

; Frame for Tell: the lane weight glows for the first half, then rises.

D8Boss_SetTellFrame:
{
  LDA.w D8Boss_Lane, X : CLC : ADC.b #!D8Boss_FrameTell
  LDY.w SprTimerA, X : CPY.b #!D8Boss_TellTime/2 : BCS +
    ADC.b #!D8Boss_FrameRise-!D8Boss_FrameTell
  +
  STA.w SprFrame, X
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
; Weight lanes A/B: fixed floor halves in room pixels (!D8Boss_Lane*).
; Stage 3 beam: boss column x, lane rows y (!D8Boss_BeamW, !D8Boss_Lane*).
; Overlap test: Link_SetupHitBox (Core/sprite_functions.asm) as pos1,
; CheckIfHitBoxesOverlap ($0683E6). Damage: Sprite_AttemptDamageToLink-
; PlusRecoil ($06F41F) reads SprBump ($0CD2) as the damage class and
; respects Link's invulnerability timers ($031F, $037B).

D8Boss_AttackHitTest:
{
  LDA.b $EE : CMP.w SprFloor, X : BNE .miss ; Link on another layer
  JSL Link_SetupHitBox
  ; Rows: lane top to the floor edge, room-relative for weights and beam.
  ; Room base = boss coordinate high byte with bit 0 cleared (rooms are
  ; 512 px, as in the socket test).
  LDA.b #!D8Boss_LaneY&$FF : STA.b pos2_y_low
  LDA.w SprYH, X : AND.b #$FE : CLC : ADC.b #!D8Boss_LaneY>>8 : STA.b pos2_y_high
  LDA.b #!D8Boss_LaneH : STA.b pos2_height
  LDA.w D8Boss_Stage, X : CMP.b #!D8Boss_LastStage : BCC .weight
    ; Beam: the drawn beam lane (frame 9 cells at SprX + !D8Boss_BeamX).
    LDA.b #!D8Boss_BeamBump : STA.w SprBump, X
    LDA.w SprX, X  : CLC : ADC.b #!D8Boss_BeamX : STA.b pos2_x_low
    LDA.w SprXH, X : ADC.b #$00 : STA.b pos2_x_high
    LDA.b #!D8Boss_BeamW : STA.b pos2_size
    BRA .test
  .weight
  ; Weight lane: a fixed floor half.
  LDA.b #!D8Boss_WeightBump : STA.w SprBump, X
  LDY.w D8Boss_Lane, X
  LDA.w .lane_x_low, Y : STA.b pos2_x_low
  LDA.w SprXH, X : AND.b #$FE : CLC : ADC.w .lane_x_high, Y : STA.b pos2_x_high
  LDA.b #!D8Boss_LaneW : STA.b pos2_size
  .test
  JSL CheckIfHitBoxesOverlap : BCC .miss
    JSL Sprite_AttemptDamageToPlayerPlusRecoil
  .miss
  RTS

  .lane_x_low
    db !D8Boss_LaneAX, !D8Boss_LaneBX
  .lane_x_high
    db !D8Boss_LaneAX>>8, !D8Boss_LaneBX>>8
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
; Tile and palette loaders

; One DMA channel 0 transfer to VRAM. Needs 16-bit A, 8-bit X, $2115 and
; $4300 already set.
macro D8Boss_DmaObj(vram, src)
  LDA.w #<vram> : STA.w $2116
  LDA.w #<src> : STA.w $4302
  LDX.b #<src>>>16 : STX.w $4304
  LDA.w #<src>_end-<src> : STA.w $4305
  LDX.b #$01 : STX.w $420B
endmacro

; Long: called from Graphics_Transfer (Sprites/all_sprites.asm) on every
; underworld scroll transition; returns at once outside room $96. The room
; check lives here because bank $30 has no room for it. The screen is
; forced blank for the DMA like ApplyManhandlaGraphics. Any A/X/Y width.
D8Boss_LoadGfx:
{
  PHP
  SEP #$30
  LDA.b $A0 : CMP.b #$96 : BNE .done
  LDA.b $A1 : BNE .done
  REP #$20
  LDX.b #$80 : STX.w $2100
  LDX.b #$80 : STX.w $2115
  LDA.w #$1801 : STA.w $4300
  %D8Boss_DmaObj($5800, D8Boss_Stage1Gfx) ; name table 1, char $80
  %D8Boss_DmaObj($5000, D8Boss_Stage2Gfx) ; name table 1, char $00
  LDX.b #$0F : STX.w $2100
  .done
  PLP
  RTL
}

; Break 2, in game: forced blank for one 3 KB DMA (about 18 black lines on
; one frame), then the brightness from $13 comes back. Called with 8-bit
; A/X/Y.
D8Boss_LoadStage3Gfx:
{
  PHX
  REP #$20
  LDX.b #$80 : STX.w $2100
  LDX.b #$80 : STX.w $2115
  LDA.w #$1801 : STA.w $4300
  %D8Boss_DmaObj($5800, D8Boss_Stage3Gfx) ; over the stage 1 chars $80-$DF
  LDX.b $13 : STX.w $2100
  SEP #$20
  PLX
  RTS
}

; Sprite palette row 6 (CGRAM $E0): colours 1-15 into the fade target
; ($7EC4C0) and the CGRAM mirror ($7EC6C0), then request the upload.
; Row 5 is not used: its high half holds the sword and shield colours.
D8Boss_LoadPalette:
{
  PHX
  REP #$20
  LDX.b #$1C
  .loop
    LDA.l D8Boss_Palette, X
    STA.l $7EC4C2, X
    STA.l $7EC6C2, X
    DEX #2
  BPL .loop
  SEP #$20
  INC.b $15
  PLX
  RTS
}

D8Boss_Palette:
  dw $1043, $1C85, $314C, $1548, $36F5, $1915, $21DC
  dw $2279, $435D, $24C8, $220E, $18AC, $1591, $1A7E, $57DF

; 96 4bpp tiles from the AFS boss art lane (export_d8.py --src pass9), then
; 32 beam tiles (chars $E0-$FF, beam_d8.py). One 4 KB DMA fills chars
; $80-$FF. Bank $2C has no room, so the tiles sit in a fixed slot at the
; tail of the items bank. Items/all_items.asm asserts its stream ends
; before $2BE000 when this flag is on.
pushpc
org $2BE000
D8Boss_Stage1Gfx:
  incbin d8_boss_stage1.bin
  incbin d8_boss_beam.bin
.end
assert pc() <= $2BF000, "D8 boss tiles reached the dream entry FX region ($2BF000)"
pullpc

; Stage 2 tiles (chars $00-$5F), stage 3 tiles (chars $80-$DF, export_d8.py
; export15) and the draw tables of all 3 stages (stage23_d8.py, AFS
; stage23_46). Fixed slot at the tail of the HUD bank; Menu/menu_hud.asm
; asserts its stream ends before $2EC000 when this flag is on.
pushpc
org $2EC000
D8Boss_Stage2Gfx:
  incbin d8_boss_stage2.bin
.end
D8Boss_Stage3Gfx:
  incbin d8_boss_stage3.bin
.end
incsrc d8_boss_draw.asm
assert pc() <= $2F0000, "D8 boss stage 2/3 slot left bank $2E"
pullpc

; =========================================================
; Draw: tables generated by stage23_d8.py (AFS stage23_46), 10 frames per
; stage, frame number = stage * 10 + SprFrame. Props $3D = priority 3,
; palette 6, name table 1. Lane B frames are lane A mirrored (props $7D).
; Frames:
;   0 idle (Closed, Break, Death)   1 recovery (Open: eye open)
;   2/3 slam lane A/B (Active)      4/5 tell lane A/B (Tell, first half)
;   6/7 rise lane A/B (Tell, second half)   8 hit (Recoil)
;   9 beam (stage 3 Active: aligned body + beam to the floor edge)
; Stage 2 rise frames hold the shunt pose. Stage 3 has no mirror: its slam
; and rise frames hold the aligned pose.

Sprite_D8Boss_Draw:
{
  ; %DrawSprite with signed byte x/y offsets, 16-bit entry index (the 3
  ; stages hold about 500 entries) and long table reads (bank $2E).
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer
  LDA.w SprFlash, X : STA $08
  LDA.w D8Boss_Stage, X : ASL : STA $0A : ASL #2 : CLC : ADC $0A
  CLC : ADC.w SprFrame, X
  PHX
  REP #$30
  AND.w #$00FF : TAX
  LDA.l D8Boss_DrawCount, X : AND.w #$00FF : STA $0A ; entries - 1
  TXA : ASL : TAX
  LDA.l D8Boss_DrawStart, X : STA $06
  LDY.w #$0000
  .nextTile
    REP #$20
    LDA $0A : CLC : ADC $06 : TAX
    LDA.l D8Boss_DrawX, X : AND.w #$00FF : CMP.w #$0080 : BCC +
      ORA.w #$FF00
    +
    CLC : ADC $00 : STA ($90), Y
    AND.w #$0100 : STA $0E
    INY
    LDA.l D8Boss_DrawY, X : AND.w #$00FF : CMP.w #$0080 : BCC +
      ORA.w #$FF00
    +
    CLC : ADC $02 : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      ; Put the sprite out of the way
      LDA.b #$F0 : STA ($90), Y : STA $0E
    .on_screen_y
    INY
    LDA.l D8Boss_DrawChr, X : STA ($90), Y
    INY
    LDA.l D8Boss_DrawProps, X : ORA $08 : STA ($90), Y
    PHY
    REP #$20 : TYA : LSR #2 : TAY : SEP #$20
    LDA.l D8Boss_DrawSizes, X : ORA $0F : STA ($92), Y ; store size in oam buffer
    PLY : INY
    DEC $0A : BPL .nextTile ; 8-bit: $0B stays 0
  SEP #$30
  PLX
  RTS
}
