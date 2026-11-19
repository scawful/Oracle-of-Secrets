; =========================================================
; Gust Jar (Minish Cap style) — Logical item $1D ($7EF3AE).
; Replaces Switch Hook on $1D (GustJarOwned = SwitchHookOwned so saves and
; Menu v5 stay 100% compatible with ZERO new SRAM bytes).
; Dispatches from BOTH Y and X via LinkItem_Hookshot -> BeginGoldstarOrHookshot.
;
; Phase 1 (Hold Y or X): 3-tier vacuum inhale cone (40/60/80 px reach) with
; swirling wind-suction OAM puffs, periodic suction SFX, pickup vacuum
; ($D8-$E5), Bomb ($07) / Somaria ($2C) / Statue ($1C) / Ice Block ($D5) pull,
; light/normal enemy pull + nozzle capture, Overworld bush/grass clearing,
; and public GustJar_WindSignal hook for future sand/web/pinwheel puzzles.
;
; Phase 2 (Release Y or X): launches captured enemy/throwable/bomb at high
; speed (damaging enemies on impact, arcing across gaps, warping through
; Portal Rod nodes) and fires a scaling 3-tier Wind Gust Wave that knocks back
; & stuns enemies, pushes bombs/Somaria/statues (including into Portal Rod
; nodes), clears bushes, and deflects light enemy projectiles.
;
; Volatile WRAM ($0273-$027F, 13 bytes in vanilla free RAM $0224-$027F;
; zero overlap with Switch Hook $0268-$0270 or Garo Glide $0271-$0272).
; StartupMasks clears $0271-$027F on boot.
; =========================================================

; Relocated off tight Bank $2B into unused Bank $39 tail ($39F000-$39FFFF,
; 4096 bytes after Minish Link GFX; mirrors low WRAM like Bank $2B).
pushpc
org $39F000

GustJarOwned      = SwitchHookOwned ; $7EF3AE (exact 1 = owned)
!GustJarState     = $0273 ; 0=idle, 1=inhale, 2=blast wave
!GustJarButton    = $0274 ; 1=Y ($F0&$40), 2=X ($F2&$40)
!GustJarCharge    = $0275 ; 0..$60 inhale frames
!GustJarTier      = $0276 ; 1, 2, or 3
!GustJarDir       = $0277 ; facing 0=U, 2=D, 4=L, 6=R
!GustJarCapKind   = $0278 ; 0=none, 1=sprite, 2=ancilla
!GustJarCapSlot   = $0279 ; captured sprite (0..$0F) or ancilla (0..$04) slot
!GustJarWaveTmr   = $027A ; blast wave countdown frames
!GustJarWaveXL    = $027B ; blast wave world X (16-bit)
!GustJarWaveXH    = $027C
!GustJarWaveYL    = $027D ; blast wave world Y (16-bit)
!GustJarWaveYH    = $027E
!GustJarFlags     = $027F ; bit0=wind signal, bit1=launched entity, bit2=pose/facing lock, bit3=blast recoil peak
!GustJarOamAllocA = $0DBA80 ; vanilla OAM_AllocateFromRegionA (shared sprite/ancilla pool, post-Ancilla safe!)
!GustJarOamAllocB = $0DBA84 ; vanilla OAM_AllocateFromRegionB (behind Link)
!GustJarOamAllocC = $0DBA88 ; vanilla OAM_AllocateFromRegionC (top-priority in front of Link)
!GustJarOWTileAct = $1BBD7A ; vanilla HandleItemTileAction_Overworld

assert !GustJarFlags < $0280, "Gust Jar exceeds vanilla free WRAM $0224-$027F"

; Hook LinkOAM_ContinueWithAnimation ($0DA435, M/X=8, DBR=$0D) to drive Link's
; two-hand Gust Jar holding/bracing pose during inhale and recoil follow-through
; without disturbing vanilla movement, collision, sword, or mask form states.
pushpc
org $0DA435 ; @hook module=Items name=GustJar_LinkPoseOamHook kind=jsl target=GustJar_LinkPoseOamHook expected_m=8 expected_x=8
  assert read4($0DA435) == $C003548C && read1($0DA439) == $05, "LinkOAM_ContinueWithAnimation moved"
  JSL GustJar_LinkPoseOamHook
  NOP
assert pc() == $0DA43A
pullpc

GustJar_CodeStart:

; ---------------------------------------------------------
; LinkOAM_ContinueWithAnimation ($0DA435) pose & OAM render hook (M/X=8, DBR=$0D).
; Runs AFTER Sprite_Main ($0683D4 OAM_ResetRegionBases) and Ancilla_Main, so
; Gust Jar's OAM allocations never collide with Somaria Blocks, Bombs, or Portals!
;   1. Overrides Link's pose only while Gust Jar owns pose/facing-lock (bit 2):
;      - Inhale (state=1): Up/Down -> $0E (symmetrical two-hand hold);
;        Left/Right -> $16 (forward-braced two-hand push/hold), mapping walk step $2E
;        smoothly into 0..5 with a subtle Tier 2/3 brace pulse when planted.
;      - Blast follow-through (state=2, bit 2): $18 (braced grab recoil), frame 1
;        lean-back kickback on D/L/R during bit 3 peak, frame 0 on Up & recovery.
;      Shield is hidden ($FF) natively on $0E, $16, and $18.
;   2. Renders Held Minish Cap Gust Jar + Inhale Funnel / Blast Crescent Wave OAM
;      post-Ancilla while preserving Y (pose), $02 (anim frame), and DBR ($0D).
; Exit: $0354 = Y; Z flag reflects CPY #$05 for $0DA43A BEQ .not_recoiling.
; ---------------------------------------------------------
GustJar_LinkPoseOamHook:
{
  LDA.w !GustJarState : BEQ .done
  LDA.w !GustJarFlags : BIT.b #$04 : BEQ .render_oam
  LDA.b $5D : ORA.w $02E0 : BNE .render_oam

  LDA.w !GustJarState : CMP.b #$02 : BEQ .blast_pose

  ; Phase 1 (Inhale): Up/Down -> $0E (symmetrical two-hand hold), Left/Right -> $16 (braced forward push/hold).
  LDY.b #$16
  LDA.b $2F : CMP.b #$04 : BCS + : LDY.b #$0E : +
  LDA.b $2E : BEQ .planted
  - : CMP.b #$06 : BCC .set_frame
    SEC : SBC.b #$06 : BRA -
  .planted
  LDA.w !GustJarTier : CMP.b #$02 : BCC .zero
  LDA.w !GustJarCharge : AND.b #$08 : BEQ .zero
    LDA.b #$01 : BRA .set_frame

  .blast_pose
  ; Phase 2 (Blast Release Follow-Through): crisp braced recoil ($18).
  LDY.b #$18
  LDA.b $2F : BEQ .zero
  LDA.w !GustJarFlags : AND.b #$08 : BEQ .zero
    LDA.b #$01 : BRA .set_frame
  .zero
  LDA.b #$00
  .set_frame
  STA.b $02

  .render_oam
  PHX : PHY
  JSL GustJar_RenderOamPostAncilla
  PLY : PLX

  .done
  STY.w $0354
  CPY.b #$05
  RTL
}

; ---------------------------------------------------------
; Public puzzle hook for sand/web/pinwheel consumers.
; Exit (M=8): A = tier (1..3) if wind active else 0 (Z=1); C=1 blast, C=0 inhale.
; ---------------------------------------------------------
GustJar_WindSignal:
{
  LDA.w !GustJarState : BEQ .idle
  CMP.b #$02 : BEQ .blast
  LDA.w !GustJarTier
  CLC : RTL
  .blast
  LDA.w !GustJarTier
  SEC : RTL
  .idle
  LDA.b #$00
  CLC : RTL
}

; ---------------------------------------------------------
; Entry from BeginGoldstarOrHookshot when %SelectedItem() == #$1D.
; M/X=8. Link_HandleYItem / CheckYButtonPress already set $3A bit 6.
; ---------------------------------------------------------
GustJar_Start:
{
  PHB : PHK : PLB
  JSR GustJar_ContextOk : BCC .refuse
  ; If a previous blast wave is still flying, cleanly replace it.
  LDA.w !GustJarState : BEQ .init
    JSR GustJar_Abort
  .init
  JSR GustJar_ClearVars
  LDA.b #$01 : STA.w !GustJarState
  STA.w !GustJarTier
  LDA.b #$04 : STA.w !GustJarFlags ; bit2 = Link pose & facing-lock active
  LDA.b $2F : AND.b #$06 : STA.w !GustJarDir

  ; Latch physical trigger button (2=X, 1=Y) for hold/release tracking.
  LDA.l ItemBindingButton : CMP.b #$02 : BEQ .use_x
    LDA.b #$01
  .use_x
  STA.w !GustJarButton

  ; Hold stance: claim $3A bit 6, lock facing ($50 bit 0), slow strafe ($5E=$0E),
  ; and suppress sword swing ($02E3) while both hands hold the jar.
  LDA.b #$40 : TSB.b $3A
  JSR GustJar_LockFacing
  LDA.b #$0E : STA.b $5E
  LDA.b #$09 : STA.w $012E ; SFX2.09 crisp wind-intake fwish
  PLB : RTL

  .refuse
  LDA.b #$40 : TRB.b $3A
  PLB : RTL
}

; Shared compact helpers (preserve bank headroom in $39F000-$39FFFF).
GustJar_ClearVars:
{
  LDX.b #$0C
  - : STZ.w !GustJarState, X : DEX : BPL -
  RTS
}
GustJar_LockFacing:
{
  LDA.b #$01 : TSB.b $50
  LDA.w !GustJarDir : STA.b $2F
  LDA.b #$02 : STA.w $02E3
  RTS
}
GustJar_Abs16:
{
  BPL + : EOR.w #$FFFF : INC A : +
  RTS
}
GustJar_LoadSprPos16Y:
{
  LDA.w SprX, Y : STA.b $04 : LDA.w SprXH, Y : STA.b $05
  LDA.w SprY, Y : STA.b $06 : LDA.w SprYH, Y : STA.b $07
  RTS
}
GustJar_LoadAncPos16X:
{
  LDA.w $0C04, X : STA.b $00 : LDA.w $0C18, X : STA.b $01
  LDA.w $0BFA, X : STA.b $02 : LDA.w $0C0E, X : STA.b $03
  RTS
}
GustJar_StoreAncDestX:
{
  LDA.b $04 : STA.w $0C04, X : LDA.b $05 : STA.w $0C18, X
  LDA.b $06 : STA.w $0BFA, X : LDA.b $07 : STA.w $0C0E, X
  RTS
}
GustJar_ModuleOk:
{
  LDA.b $10 : CMP.b #$07 : BEQ .ok
  CMP.b #$09 : BEQ .ok
  CMP.b #$0B : BNE .no
  .ok : SEC : RTS
  .no : CLC : RTS
}
; C=1 if sprite Y is alive (state 9 or $B) and on Link's indoor floor.
GustJar_SprAliveOnFloorY:
{
  LDA.w SprState, Y : CMP.b #$09 : BEQ .alive
  CMP.b #$0B : BNE .no
  .alive
  LDA.b $1B : BEQ .ok
    LDA.w SprFloor, Y : CMP.b $EE : BNE .no
  .ok
  SEC : RTS
  .no
  CLC : RTS
}
; Compute signed ($00=VX, $01=VY) along !GustJarDir from magnitude in A. Preserves X/Y.
GustJar_DirVel:
{
  STZ.b $00 : STZ.b $01
  PHA
  LDA.w !GustJarDir
  BEQ .u : CMP.b #$02 : BEQ .d : CMP.b #$04 : BEQ .l
  PLA : STA.b $00 : RTS
  .l : PLA : EOR.b #$FF : INC A : STA.b $00 : RTS
  .d : PLA : STA.b $01 : RTS
  .u : PLA : EOR.b #$FF : INC A : STA.b $01 : RTS
}

; ---------------------------------------------------------
; Per-frame service from LinkMain_FrameHook (M/X=8, DBR=$07).
; Fast-paths out in 5 cycles when idle.
; ---------------------------------------------------------
GustJar_FrameTick:
{
  LDA.w !GustJarState : BNE .active
  RTL
  .active
  PHB : PHK : PLB
  CMP.b #$01 : BEQ .inhale
  CMP.b #$02 : BEQ .wave
    JSR GustJar_Abort
    PLB : RTL
  .inhale
    JSR GustJar_TickInhale
    PLB : RTL
  .wave
    JSR GustJar_TickWave
    PLB : RTL
}

; ---------------------------------------------------------
; Release Link's Gust Jar pose, facing lock, slow-strafe speed & sword lock.
; Guarded by !GustJarFlags bit 2 so later blast-wave expiry never cancels
; a subsequent sword charge or Pegasus dash started after follow-through.
; ---------------------------------------------------------
GustJar_ReleasePose:
{
  LDA.w !GustJarFlags : BIT.b #$04 : BEQ .done
    AND.b #$F3 : STA.w !GustJarFlags ; clear bit2 (pose/lock) & bit3 (recoil peak)
    LDA.b #$40 : TRB.b $3A
    LDA.b #$01 : TRB.b $50           ; unlock facing direction
    STZ.w $02E3                      ; restore sword immediately
    LDA.b $5E : CMP.b #$06 : BEQ .clr_5e
    CMP.b #$0E : BNE .done
    .clr_5e
    STZ.b $5E
  .done
  RTS
}

; ---------------------------------------------------------
; Immediate safe abort & cleanup (transition, damage, swim, doorway, menu, mask).
; ---------------------------------------------------------
GustJar_Abort:
{
  LDA.w !GustJarState : CMP.b #$01 : BNE .clear_state
  LDA.w !GustJarCapKind : BEQ .clear_state
  CMP.b #$01 : BNE .release_ancilla
    ; Ground captured sprite cleanly and leave short stun.
    LDY.w !GustJarCapSlot : CPY.b #$10 : BCS .clear_state
    LDA.b #$00 : STA.w SprHeight, Y
    LDA.w SprState, Y : CMP.b #$0B : BNE .clear_state
    LDA.b #$10 : STA.w SprStunTimer, Y
    LDA.b #$20 : STA.w SprTimerA, Y
    BRA .clear_state
  .release_ancilla
    LDX.w !GustJarCapSlot : CPX.b #$05 : BCS .clear_state
    LDA.b #$00 : STA.w $029E, X
  .clear_state
  JSR GustJar_ReleasePose
  LDA.b #$40 : TRB.b $3A ; defense-in-depth if aborted mid-init
  JMP GustJar_ClearVars
}

; ---------------------------------------------------------
; C=1 when gameplay context allows active Gust Jar inhaling.
; ---------------------------------------------------------
GustJar_ContextOk:
{
  LDA.l GustJarOwned : CMP.b #$01 : BNE .no
  JSR GustJar_ModuleOk : BCC .no
  LDA.b $11 : ORA.b $6C : ORA.b $5D : ORA.b $4D : ORA.b $46 : ORA.b $3C : BNE .no
  LDA.w $0FFC : ORA.w $02E4 : ORA.w $0308 : BNE .no
  ; Base Link (0), Minish (5), GBC (6), Moosh (7) only.
  LDA.w !CurrentMask : BEQ .ok
  CMP.b #$05 : BCC .no
  CMP.b #$08 : BCS .no
  .ok
  SEC : RTS
  .no
  CLC : RTS
}

; ---------------------------------------------------------
; Phase 1: Hold Button — 3-Tier Vacuum / Inhale Cone.
; ---------------------------------------------------------
GustJar_TickInhale:
{
  JSR GustJar_ContextOk : BCS .ctx_ok
    JMP GustJar_Abort
  .ctx_ok

  ; Check latched button still held (2=X in $F2, 1=Y in $F0).
  LDA.w !GustJarButton : CMP.b #$02 : BEQ .chk_x
    LDA.b $F0 : BRA .chk_bit
  .chk_x
    LDA.b $F2
  .chk_bit
  AND.b #$40 : BNE .held
    JMP GustJar_FireBlast
  .held

  ; Keep hold stance, lock Link facing ($2F = !GustJarDir, $50 bit 0) for true
  ; Minish Cap strafing, and suppress sword swing while both hands hold the jar.
  LDA.b #$40 : TSB.b $3A
  JSR GustJar_LockFacing

  ; Advance charge (0..$60) and compute Tier 1 / 2 / 3.
  LDA.w !GustJarCharge : CMP.b #$60 : BCS .charge_capped
    INC A : STA.w !GustJarCharge
    CMP.b #$18 : BEQ .tier_up
    CMP.b #$38 : BNE .charge_capped
  .tier_up
    LDA.b #$07 : STA.w $012E ; tier-up whoosh cue
  .charge_capped
  LDA.w !GustJarCharge
  CMP.b #$38 : BCS .t3
  CMP.b #$18 : BCS .t2
    LDA.b #$01 : BRA .set_tier
  .t2
    LDA.b #$02 : BRA .set_tier
  .t3
    LDA.b #$03
  .set_tier
  STA.w !GustJarTier

  ; Slow strafe footing: Tier 1 = $0E (1.0 px/f), Tier 2/3 = $06 (0.5 px/f heavy
  ; braced crawl + slower footstep cycle). Expose wind signal at Tier >= 2.
  CMP.b #$02 : BCC .t1_speed
    LDA.b #$01 : TSB.w !GustJarFlags ; expose wind signal (bit2 already set on Start)
    LDA.b #$06 : BRA .set_speed
  .t1_speed
    LDA.b #$0E
  .set_speed
  STA.b $5E

  ; Periodic suction SFX cadence (faster at higher tiers).
  LDA.w !GustJarCharge : AND.b #$07 : BNE .sfx_done
  LDA.w $012E : BNE .sfx_done
  LDA.b #$09 : STA.w $012E ; SFX2.09 suction fwish
  .sfx_done

  ; Compute nozzle world position ($08=X16, $0A=Y16).
  JSR GustJar_ComputeNozzle

  ; Keep captured entity pinned at nozzle (if any).
  JSR GustJar_HoldCaptured

  ; Pull sprites & ancillae in inhale cone.
  JSR GustJar_InhaleSprites
  JSR GustJar_InhaleAncillae

  ; At Tier >= 2 every 8 frames, clear Overworld bushes/tall grass ahead.
  LDA.w !GustJarTier : CMP.b #$02 : BCC .done
  LDA.w !GustJarCharge : AND.b #$07 : BNE .done
    JSR GustJar_CutAheadOverworld
  .done
  RTS
}

; ---------------------------------------------------------
; Compute nozzle world coords into $08..$09 (X) and $0A..$0B (Y).
; ---------------------------------------------------------
GustJar_ComputeNozzle:
{
  LDA.w !GustJarDir : TAX
  REP #$20
  LDA.b $22 : CLC : ADC.w .off_x, X : STA.b $08
  LDA.b $20 : CLC : ADC.w .off_y, X : STA.b $0A
  SEP #$20
  RTS
  ; Indexed by !GustJarDir (0=U, 2=D, 4=L, 6=R).
  .off_x : dw   8,   8,  -6,  22
  .off_y : dw  -4,  24,  10,  10
}

; ---------------------------------------------------------
; Pin captured entity at nozzle ($08/$0A) with subtle suction jitter.
; ---------------------------------------------------------
GustJar_HoldCaptured:
{
  LDA.w !GustJarCapKind : BEQ .done
  CMP.b #$01 : BEQ .hold_sprite
  CMP.b #$02 : BEQ .hold_ancilla
  .drop
  STZ.w !GustJarCapKind
  STZ.w !GustJarCapSlot
  .done
  RTS

  .hold_ancilla
  LDX.w !GustJarCapSlot : CPX.b #$05 : BCS .drop
  LDA.w $0C4A, X : CMP.b #$07 : BNE .drop
  LDA.w $0C5E, X : BNE .drop ; bomb exploded: release!
  LDA.b $08 : STA.w $0C04, X
  LDA.b $09 : STA.w $0C18, X
  LDA.b $0A : STA.w $0BFA, X
  LDA.b $0B : STA.w $0C0E, X
  STZ.w $0C22, X : STZ.w $0C2C, X
  LDA.b #$04 : STA.w $029E, X
  RTS

  .hold_sprite
  LDY.w !GustJarCapSlot : CPY.b #$10 : BCS .drop
  LDA.w SprState, Y : CMP.b #$09 : BEQ .sp_ok
  CMP.b #$0B : BNE .drop
  .sp_ok
  ; Subtle 1 px suction vibration on frame bit 1.
  LDA.b $1A : AND.b #$02 : LSR A : STA.b $00 : STZ.b $01
  REP #$20
  LDA.b $08 : SEC : SBC.w #$0008 : CLC : ADC.b $00 : STA.b $04
  LDA.b $0A : SEC : SBC.w #$0008 : STA.b $06
  SEP #$20
  LDA.b $04 : STA.w SprX, Y : LDA.b $05 : STA.w SprXH, Y
  LDA.b $06 : STA.w SprY, Y : LDA.b $07 : STA.w SprYH, Y
  LDA.b #$00
  STA.w SprXSpeed, Y : STA.w SprYSpeed, Y
  STA.w SprTimerF, Y
  LDA.b #$04 : STA.w SprHeight, Y
  ; Keep enemy frozen in stun state while captured.
  LDA.w SprType, Y : CMP.b #$EC : BEQ .sp_done
  LDA.b #$0B : STA.w SprState, Y
  LDA.b #$30 : STA.w SprStunTimer, Y
  LDA.b #$40 : STA.w SprTimerA, Y
  .sp_done
  RTS
}

; ---------------------------------------------------------
; Cone membership test for point ($00=X16, $02=Y16) relative to Link center.
; In:  $00/$02 = target center X/Y (16-bit); cone range read from !GustJarTier.
; Out: C=1 inside cone ($04 = forward distance low byte); C=0 outside.
; Preserves X and Y.
; ---------------------------------------------------------
GustJar_InCone:
{
  REP #$20
  ; dx = targetX - (LinkX + 8) -> $0C
  LDA.b $22 : CLC : ADC.w #$0008 : STA.b $04
  LDA.b $00 : SEC : SBC.b $04 : STA.b $0C
  ; dy = targetY - (LinkY + 10) -> $0E
  LDA.b $20 : CLC : ADC.w #$000A : STA.b $04
  LDA.b $02 : SEC : SBC.b $04 : STA.b $0E
  SEP #$20

  LDA.w !GustJarDir
  BEQ .up
  CMP.b #$02 : BEQ .down
  CMP.b #$04 : BEQ .left
  ; Right (6): fwd = +dx, perp = dy
  REP #$20
  LDA.b $0C : STA.b $04
  LDA.b $0E
  BRA .check_axes

  .up
  ; Up (0): fwd = -dy, perp = dx
  REP #$20
  LDA.w #$0000 : SEC : SBC.b $0E : STA.b $04
  LDA.b $0C
  BRA .check_axes

  .down
  ; Down (2): fwd = +dy, perp = dx
  REP #$20
  LDA.b $0E : STA.b $04
  LDA.b $0C
  BRA .check_axes

  .left
  ; Left (4): fwd = -dx, perp = dy
  REP #$20
  LDA.w #$0000 : SEC : SBC.b $0C : STA.b $04
  LDA.b $0E

  .check_axes
  ; A = signed perp; take |perp| into $0C.
  JSR GustJar_Abs16
  STA.b $0C

  ; Require 4 <= fwd <= tier cone range (40/60/80 px).
  LDA.b $04 : BMI .out
  CMP.w #$0004 : BCC .out
  PHX : LDX.w !GustJarTier : LDA.w GustJar_ConeRange-1, X : PLX
  AND.w #$00FF
  CMP.b $04 : BCC .out

  ; Half-width = 16 + (fwd >> 2); require |perp| <= half-width.
  LDA.b $04 : LSR #2 : CLC : ADC.w #$0010
  CMP.b $0C : BCC .out
  SEP #$20
  SEC : RTS

  .out
  SEP #$20
  CLC : RTS
}

; ---------------------------------------------------------
; Pull sprites inside the inhale cone (pickups, statues, ice blocks,
; throwables, light/normal enemies) and capture eligible entities at nozzle.
; ---------------------------------------------------------
GustJar_InhaleSprites:
{
  LDY.b #$0F
  .loop
  ; Skip already-captured sprite.
  LDA.w !GustJarCapKind : CMP.b #$01 : BNE .not_cap
    TYA : CMP.w !GustJarCapSlot : BNE .not_cap
      JMP .next
  .not_cap
  JSR GustJar_SprAliveOnFloorY : BCS .floor_ok
    JMP .next
  .floor_ok
  ; Compute sprite center ($00=X+8, $02=Y+8).
  JSR GustJar_LoadSprPos16Y
  REP #$20
  LDA.b $04 : CLC : ADC.w #$0008 : STA.b $00
  LDA.b $06 : CLC : ADC.w #$0008 : STA.b $02
  SEP #$20
  JSR GustJar_InCone : BCC .next

  ; Classify target sprite.
  LDA.w SprType, Y
  ; 1. Drops & Pickups ($D8..$E5: heart, rupees, bombs, magic, arrows, fairy, keys).
  CMP.b #$D8 : BCC .not_pickup
  CMP.b #$E6 : BCS .not_pickup
    LDA.w !GustJarTier : INC A : STA.b $07 ; 2/3/4 px/frame vacuum pull
    JSR GustJar_PullSpriteToLink
    BRA .next
  .not_pickup

  ; 2. Throwable scenery ($EC pot/bush/rock).
  CMP.b #$EC : BNE .not_throwable
    JSR GustJar_TryCaptureOrPullSprite
    BRA .next
  .not_throwable

  ; 3. Movable Statue ($1C, excluding Elegy of Stone echo) & Ice Block ($D5).
  CMP.b #$1C : BNE .not_statue
    LDA.w SprFrame, Y : CMP.b #!Stone_Marker : BEQ .next
  .pull_block
    LDA.b #$01 : STA.b $07
    JSR GustJar_PullSpriteReverseDir
    STZ.w $0642 ; statue recomputes pressure-plate contact
    BRA .next
  .not_statue
  CMP.b #Sprite_IceBlock : BEQ .pull_block

  ; 4. Light/Normal Enemies (filter out bosses, NPCs, portals, harmless/immovable).
  JSR GustJar_IsPullableEnemy : BCC .next
  JSR GustJar_TryCaptureOrPullSprite

  .next
  DEY : BMI .done
  JMP .loop
  .done
  RTS
}

GustJar_ConeRange:
  db 40, 60, 80

; ---------------------------------------------------------
; C=1 if sprite Y is a pullable/pushable normal or light enemy.
; Rejects bosses, NPCs, portals, harmless, impervious, stationary objects.
; ---------------------------------------------------------
GustJar_IsPullableEnemy:
{
  LDA.w SprType, Y
  CMP.b #$03 : BEQ .no ; Portal Rod node
  CMP.b #$1C : BEQ .no ; Statue
  CMP.b #$79 : BEQ .no ; Wild/good bee
  CMP.b #$B2 : BEQ .no ; Friendly bee / Windmill guy
  CMP.b #$D5 : BCS .no ; Ice block, drops, special objects
  LDA.w SprNbrOAM, Y : BMI .no        ; bit 7 = harmless / NPC
  LDA.w SprGfxProps, Y : BIT.b #$40 : BNE .no ; bit 6 = invulnerable / boss
  LDA.w SprDefl, Y : BIT.b #$20 : BNE .no     ; bit 5 = immovable / boss-class
  LDA.w SprHitbox, Y : BIT.b #$40 : BNE .no   ; bit 6 = stationary object
  LDA.w SprHealth, Y : BEQ .no
  CMP.b #$18 : BCS .no                ; high-HP boss/miniboss exclusion
  SEC : RTS
  .no
  CLC : RTS
}

; ---------------------------------------------------------
; Pull sprite Y toward nozzle; capture at mouth if light (HP <= 8 or $EC).
; ---------------------------------------------------------
GustJar_TryCaptureOrPullSprite:
{
  LDA.w !GustJarCapKind : BNE .pull_only
  ; Capture range: forward dist ($04) <= 20 px.
  LDA.b $04 : CMP.b #$15 : BCS .pull_only
  LDA.w SprType, Y : CMP.b #$EC : BEQ .capture
  LDA.w SprHealth, Y : CMP.b #$09 : BCS .pull_only
  .capture
  LDA.b #$01 : STA.w !GustJarCapKind
  TYA : STA.w !GustJarCapSlot
  LDA.b #$13 : STA.w $012F ; SFX3.$13 crisp capture pop cue (not SFX2.$13 Healing!)
  JSR GustJar_HoldCaptured
  RTS
  .pull_only
  LDA.w !GustJarTier : STA.b $07 ; 1/2/3 px/frame pull
  JSR GustJar_PullSpriteToLink
  RTS
}

; ---------------------------------------------------------
; Pull sprite Y toward Link ($22, $20+4) by step $07, respecting $0E70 walls.
; Reuses GustJar_StepSpriteDir (0=U, 2=D, 4=L, 6=R) for identical wall checks.
; ---------------------------------------------------------
GustJar_PullSpriteToLink:
{
  LDA.w SprX, Y : STA.b $0C : LDA.w SprXH, Y : STA.b $0D
  REP #$20
  LDA.b $0C : CMP.b $22
  SEP #$20
  BEQ .do_y
  LDA.b #$06 : BCC + : LDA.b #$04 : + ; Left if SprX > LinkX else Right
  JSR GustJar_StepSpriteDir
  .do_y
  LDA.w SprY, Y : STA.b $0C : LDA.w SprYH, Y : STA.b $0D
  REP #$20
  LDA.b $20 : CLC : ADC.w #$0004 : STA.b $0E
  LDA.b $0C : CMP.b $0E
  SEP #$20
  BEQ .done
  LDA.b #$02 : BCC + : LDA.b #$00 : + ; Up if SprY > LinkY+4 else Down
  JMP GustJar_StepSpriteDir
  .done
  RTS
}

; ---------------------------------------------------------
; Step sprite Y along opposite of !GustJarDir (pull) or along !GustJarDir (push).
; GustJar_PullSpriteReverseDir uses dir ^ 2; GustJar_PushSpriteAlongDir uses dir.
; In: Y = sprite slot, $07 = step pixels. Respects $0E70 wall flags.
; ---------------------------------------------------------
GustJar_PullSpriteReverseDir:
  LDA.w !GustJarDir : EOR.b #$02
  BRA GustJar_StepSpriteDir
GustJar_PushSpriteAlongDir:
  LDA.w !GustJarDir
GustJar_StepSpriteDir:
{
  LSR A : TAX
  LDA.w $0E70, Y : AND.w .wall_bit, X : BNE .blocked
  TXA : BEQ .up : CMP.b #$01 : BEQ .down : CMP.b #$02 : BEQ .left
  ; Right (3)
  LDA.w SprX, Y : CLC : ADC.b $07 : STA.w SprX, Y
  LDA.w SprXH, Y : ADC.b #$00 : STA.w SprXH, Y
  RTS
  .left
  LDA.w SprX, Y : SEC : SBC.b $07 : STA.w SprX, Y
  LDA.w SprXH, Y : SBC.b #$00 : STA.w SprXH, Y
  RTS
  .down
  LDA.w SprY, Y : CLC : ADC.b $07 : STA.w SprY, Y
  LDA.w SprYH, Y : ADC.b #$00 : STA.w SprYH, Y
  RTS
  .up
  LDA.w SprY, Y : SEC : SBC.b $07 : STA.w SprY, Y
  LDA.w SprYH, Y : SBC.b #$00 : STA.w SprYH, Y
  .blocked
  RTS
  .wall_bit : db $08, $04, $02, $01 ; U, D, L, R
}

; ---------------------------------------------------------
; Pull active Bombs ($07) and Somaria Blocks ($2C) in inhale cone.
; Captures Bombs within 20 px of nozzle.
; ---------------------------------------------------------
GustJar_InhaleAncillae:
{
  LDX.b #$04
  .loop
  LDA.w !GustJarCapKind : CMP.b #$02 : BNE .not_cap
    TXA : CMP.w !GustJarCapSlot : BEQ .next
  .not_cap
  LDA.w $0C4A, X
  CMP.b #$2C : BEQ .chk_carry
  CMP.b #$07 : BNE .next
  LDA.w $0C5E, X : BNE .next ; Active Bomb: skip if exploding
  .chk_carry
  LDA.w $0380, X : BNE .next ; Skip if carried by Link

  .check_cone
  JSR GustJar_LoadAncPos16X
  JSR GustJar_InCone : BCC .next

  ; Capture live Bomb within 20 px of nozzle.
  LDA.w $0C4A, X : CMP.b #$07 : BNE .pull_ancilla
  LDA.w !GustJarCapKind : BNE .pull_ancilla
  LDA.b $04 : CMP.b #$15 : BCS .pull_ancilla
    LDA.b #$02 : STA.w !GustJarCapKind
    TXA : STA.w !GustJarCapSlot
    LDA.b #$13 : STA.w $012F ; SFX3.$13 capture pop cue
    JSR GustJar_HoldCaptured
    BRA .next

  .pull_ancilla
  ; Pull ancilla X smoothly toward nozzle along reverse facing (2 px/frame).
  LDA.b #$02 : STA.b $07
  LDA.w !GustJarDir : EOR.b #$02
  JSR GustJar_StepAncillaDir
  STZ.w $0C22, X : STZ.w $0C2C, X

  .next
  DEX : BPL .loop
  RTS
}

; Step ancilla X by $07 pixels along direction A (0=U, 2=D, 4=L, 6=R).
GustJar_StepAncillaDir:
{
  BEQ .up
  CMP.b #$02 : BEQ .down
  CMP.b #$04 : BEQ .left
  ; Right
  LDA.w $0C04, X : CLC : ADC.b $07 : STA.w $0C04, X
  LDA.w $0C18, X : ADC.b #$00 : STA.w $0C18, X
  RTS
  .left
  LDA.w $0C04, X : SEC : SBC.b $07 : STA.w $0C04, X
  LDA.w $0C18, X : SBC.b #$00 : STA.w $0C18, X
  RTS
  .down
  LDA.w $0BFA, X : CLC : ADC.b $07 : STA.w $0BFA, X
  LDA.w $0C0E, X : ADC.b #$00 : STA.w $0C0E, X
  RTS
  .up
  LDA.w $0BFA, X : SEC : SBC.b $07 : STA.w $0BFA, X
  LDA.w $0C0E, X : SBC.b #$00 : STA.w $0C0E, X
  RTS
}

; ---------------------------------------------------------
; Phase 2: Release Button — Fire Gust Blast & Launch Captured Entity!
; ---------------------------------------------------------
GustJar_FireBlast:
{
  JSR GustJar_ComputeNozzle
  LDA.b $08 : STA.w !GustJarWaveXL
  LDA.b $09 : STA.w !GustJarWaveXH
  LDA.b $0A : STA.w !GustJarWaveYL
  LDA.b $0B : STA.w !GustJarWaveYH

  LDA.b #$02 : STA.w !GustJarState
  ; bit0=wind signal, bit2=7-frame follow-through pose/facing lock, bit3=4-frame recoil kickback peak
  LDA.b #$0D : STA.w !GustJarFlags
  LDA.b #$06 : STA.b $5E
  JSR GustJar_LockFacing
  LDX.w !GustJarTier : CPX.b #$04 : BCC +
    LDX.b #$01
  +
  LDA.w GustJar_WaveLife-1, X : STA.w !GustJarWaveTmr
  LDA.b #$07 : STA.w $012E ; SFX2.07 punchy Gust Blast Fwoosh!

  ; Launch captured entity (if any) at high speed along !GustJarDir!
  LDA.w !GustJarCapKind : BEQ .done
  CMP.b #$01 : BEQ .launch_sprite
  CMP.b #$02 : BNE .done

  ; Launch captured Bomb ($07) with arc velocity across gaps/water.
  LDX.w !GustJarCapSlot : CPX.b #$05 : BCS .done
  LDA.w $0C4A, X : CMP.b #$07 : BNE .done
  JSR GustJar_ApplyAncillaBlastVel
  LDA.b #$0A : STA.w $029E, X ; airborne arc
  STZ.w $0BF0, X
  BRA .mark_launched

  .launch_sprite
  LDY.w !GustJarCapSlot : CPY.b #$10 : BCS .done
  LDX.w !GustJarTier : LDA.w GustJar_LaunchSpd-1, X
  JSR GustJar_DirVel
  LDA.b $00 : STA.w SprXSpeed, Y : STA.w SprXRecoil, Y
  LDA.b $01 : STA.w SprYSpeed, Y : STA.w SprYRecoil, Y
  LDA.b #$08 : STA.w SprHeight, Y
  LDA.b #$10 : STA.w SprTimerF, Y ; upward arc velocity
  LDA.b #$0C : STA.w SprRecoil, Y
  .mark_launched
  LDA.b #$02 : TSB.w !GustJarFlags
  .done
  ; OAM (recoil jar + frame-0 blast crescent) renders cleanly post-Ancilla in GustJar_LinkPoseOamHook.
  RTS
}

GustJar_WaveLife:
  db 14, 20, 26
GustJar_LaunchSpd:
  db $38, $44, $50 ; Tier 1 / 2 / 3 launch speed magnitude

; Set ancilla X velocity along !GustJarDir scaled by !GustJarTier.
GustJar_ApplyAncillaBlastVel:
{
  LDA.w !GustJarDir : LSR A : STA.w $0C72, X
  PHX : LDX.w !GustJarTier : LDA.w GustJar_LaunchSpd-1, X : PLX
  JSR GustJar_DirVel
  LDA.b $01 : STA.w $0C22, X
  LDA.b $00 : STA.w $0C2C, X
  RTS
}

; ---------------------------------------------------------
; Phase 2 Per-Frame Update: Advance Gust Wave, Launched Projectile,
; Knockback/Stun, Projectile Deflection, Statue/Bomb/Somaria Push & Portals!
; ---------------------------------------------------------
GustJar_TickWave:
{
  ; Abort cleanly on room/screen transition or non-gameplay module.
  JSR GustJar_ModuleOk : BCC .abort
  LDA.b $11 : BNE .abort

  ; Manage crisp 7-frame blast follow-through pose (4-frame recoil kickback + 3-frame recovery).
  ; Release Link's movement/pose/facing immediately if hurt/interrupted or once 7 frames elapse.
  LDA.w !GustJarFlags : BIT.b #$04 : BEQ .pose_done
    LDA.b $5D : ORA.b $4D : ORA.b $46 : ORA.b $6C : BNE .end_pose
    LDA.w $0FFC : ORA.w $02E4 : ORA.w $0308 : BNE .end_pose
    LDX.w !GustJarTier : LDA.w GustJar_WaveLife-1, X
    SEC : SBC.w !GustJarWaveTmr ; elapsed frames (0..)
    CMP.b #$07 : BCS .end_pose
    CMP.b #$04 : BCC .keep_recoil
      LDA.w !GustJarFlags : AND.b #$F7 : STA.w !GustJarFlags ; clear bit3 -> recovery pose
    .keep_recoil
    JSR GustJar_LockFacing
    LDA.b #$06 : STA.b $5E
    BRA .pose_done
  .end_pose
    JSR GustJar_ReleasePose
  .pose_done

  DEC.w !GustJarWaveTmr : BNE .alive
  .abort
  JMP GustJar_Abort

  .alive
  ; Advance Wave center forward by (Tier + 2) px/frame (3/4/5 px/frame).
  LDA.w !GustJarTier : CLC : ADC.b #$02 : STA.b $07
  STZ.b $08
  LDA.w !GustJarDir
  REP #$20 : AND.w #$00FF
  BEQ .adv_u : CMP.w #$0002 : BEQ .adv_d : CMP.w #$0004 : BEQ .adv_l
  LDA.w !GustJarWaveXL : CLC : ADC.b $07 : STA.w !GustJarWaveXL : BRA .adv_done
  .adv_l : LDA.w !GustJarWaveXL : SEC : SBC.b $07 : STA.w !GustJarWaveXL : BRA .adv_done
  .adv_d : LDA.w !GustJarWaveYL : CLC : ADC.b $07 : STA.w !GustJarWaveYL : BRA .adv_done
  .adv_u : LDA.w !GustJarWaveYL : SEC : SBC.b $07 : STA.w !GustJarWaveYL
  .adv_done
  SEP #$20

  ; Drive launched entity (impact damage + Portal Rod warp!).
  LDA.w !GustJarFlags : BIT.b #$02 : BEQ .no_launched
    JSR GustJar_TickLaunched
  .no_launched

  ; Push/knockback/deflect sprites near wave center.
  JSR GustJar_WaveSprites

  ; Push active Bombs & Somaria Blocks near wave center (+ Portal Rod warp!).
  JSR GustJar_WaveAncillae

  ; Outdoors at Tier >= 2 every 4 frames, clear bushes at wave center.
  LDA.w !GustJarTier : CMP.b #$02 : BCC .draw
  LDA.w !GustJarWaveTmr : AND.b #$03 : BNE .draw
    LDA.w !GustJarWaveYL : STA.b $00
    LDA.w !GustJarWaveYH : STA.b $01
    LDA.w !GustJarWaveXL : STA.b $02
    LDA.w !GustJarWaveXH : STA.b $03
    JSR GustJar_TryCutOverworldFoliage
  .draw
  RTS
}

; ---------------------------------------------------------
; Update launched sprite or bomb: drive forward, check enemy impact,
; and warp cleanly through Portal Rod nodes!
; ---------------------------------------------------------
GustJar_TickLaunched:
{
  LDA.w !GustJarCapKind : CMP.b #$01 : BEQ .sprite
  CMP.b #$02 : BEQ .bomb
  .clear
  LDA.w !GustJarFlags : AND.b #$FD : STA.w !GustJarFlags
  STZ.w !GustJarCapKind
  .done
  RTS

  .bomb
  ; Launched bomb: check Portal Rod node warp.
  LDX.w !GustJarCapSlot : CPX.b #$05 : BCS .clear
  LDA.w $0C4A, X : CMP.b #$07 : BNE .clear
  LDA.w $0C5E, X : BNE .clear
  JSR GustJar_LoadAncPos16X
  JSR GustJar_FindPortalExit : BCC .done
    ; Warp bomb cleanly to counterpart portal exit!
    JSR GustJar_StoreAncDestX
    LDA.b #$30 : STA.w $012F ; SFX3.$30 portal warp zap
    BRA .clear

  .sprite
  LDY.w !GustJarCapSlot : CPY.b #$10 : BCS .clear
  LDA.w SprState, Y : BEQ .clear
  ; Drive launched sprite forward cleanly (respecting wall bits).
  LDA.w !GustJarTier : CLC : ADC.b #$02 : STA.b $07
  JSR GustJar_PushSpriteAlongDir
  ; Check Portal Rod node warp for launched sprite.
  LDA.w SprX, Y : STA.b $00 : LDA.w SprXH, Y : STA.b $01
  LDA.w SprY, Y : STA.b $02 : LDA.w SprYH, Y : STA.b $03
  JSR GustJar_FindPortalExit : BCC .chk_hit
    LDA.b $04 : STA.w SprX, Y : LDA.b $05 : STA.w SprXH, Y
    LDA.b $06 : STA.w SprY, Y : LDA.b $07 : STA.w SprYH, Y
    LDA.b #$30 : STA.w $012F ; SFX3.$30 portal warp zap
    JMP .clear

  .chk_hit
  ; Check impact with another enemy -> deal tier-scaled damage!
  LDX.b #$0F
  .hit_loop
  TXA : CMP.w !GustJarCapSlot : BNE +
    JMP .hit_next
  +
  LDA.w SprState, X : CMP.b #$09 : BEQ .hit_alive
  CMP.b #$0B : BEQ .hit_alive
    JMP .hit_next
  .hit_alive
  PHY : TXY
  JSR GustJar_IsPullableEnemy
  BCC .hit_skip_ply
    JSR GustJar_LoadSprPos16Y
    PLY
  ; Distance check <= 16 px against launched sprite ($00/$02).
  REP #$20
  LDA.b $04 : SEC : SBC.b $00 : JSR GustJar_Abs16
  CMP.w #$0010 : BCS .hit_next16
  LDA.b $06 : SEC : SBC.b $02 : JSR GustJar_Abs16
  CMP.w #$0010 : BCS .hit_next16
  SEP #$20
  ; Impact hit! Damage = Tier * 2 (2 / 4 / 6 HP).
  LDA.w !GustJarTier : ASL A : STA.b $04
  LDA.w SprHealth, X : SEC : SBC.b $04
  BEQ .kill : BCC .kill
    STA.w SprHealth, X
    LDA.b #$0C : STA.w SprRecoil, X
    BRA .impact_sfx
  .kill
    LDA.b #$00 : STA.w SprHealth, X
    LDA.b #$06 : STA.w SprState, X ; vanilla death module
  .impact_sfx
  LDA.b #$08 : STA.w $012E ; smash impact cue
  JMP .clear
  .hit_skip_ply
  PLY
  BRA .hit_next
  .hit_next16
  SEP #$20
  .hit_next
  DEX : BMI .hit_done
  JMP .hit_loop
  .hit_done
  RTS
}

; ---------------------------------------------------------
; Gust Wave vs Sprites: knockback/stun enemies, push statues/ice blocks,
; deflect light enemy projectiles ($0C, $1B, $50, $70, $89, $D1).
; ---------------------------------------------------------
GustJar_WaveSprites:
{
  LDY.b #$0F
  .loop
  LDA.w !GustJarFlags : BIT.b #$02 : BEQ .not_self
    LDA.w !GustJarCapKind : CMP.b #$01 : BNE .not_self
    TYA : CMP.w !GustJarCapSlot : BNE .not_self
      JMP .next
  .not_self
  JSR GustJar_SprAliveOnFloorY : BCS .floor_ok
    JMP .next
  .floor_ok
  ; Within 20 px of (WaveX, WaveY)?
  JSR GustJar_LoadSprPos16Y
  REP #$20
  LDA.b $04 : CLC : ADC.w #$0008 : SEC : SBC.w !GustJarWaveXL : JSR GustJar_Abs16
  CMP.w #$0014 : BCS .next16_near
  LDA.b $06 : CLC : ADC.w #$0008 : SEC : SBC.w !GustJarWaveYL : JSR GustJar_Abs16
  CMP.w #$0014 : BCC +
  .next16_near
    JMP .next16
  +
  SEP #$20

  ; 1. Light enemy projectiles -> deflect/clear!
  LDA.w SprType, Y
  CMP.b #$0C : BEQ .deflect ; Octorok stone
  CMP.b #$1B : BEQ .deflect ; Enemy arrow
  CMP.b #$50 : BEQ .deflect ; Cannonball
  CMP.b #$70 : BEQ .deflect ; Fireball
  CMP.b #$89 : BEQ .deflect ; Mothula beam
  CMP.b #$D1 : BNE .not_proj ; Bunny beam
  .deflect
    LDA.b #$00 : STA.w SprState, Y
    LDA.b #$05 : STA.w $012E ; deflect tink
    BRA .next
  .not_proj

  ; 2. Movable Statue ($1C non-Stone) or Ice Block ($D5) -> push forward!
  CMP.b #$1C : BNE .not_statue
    LDA.w SprFrame, Y : CMP.b #!Stone_Marker : BEQ .next
  .push_block
    LDA.b #$02 : STA.b $07
    JSR GustJar_PushSpriteAlongDir
    STZ.w $0642
    BRA .next
  .not_statue
  CMP.b #Sprite_IceBlock : BEQ .push_block

  ; 3. Normal/Light Enemy -> knockback recoil + brief stun!
  JSR GustJar_IsPullableEnemy : BCC .next
  LDX.w !GustJarTier
  LDA.w .kb_spd-1, X : JSR GustJar_DirVel
  LDA.b $00 : STA.w SprXRecoil, Y
  LDA.b $01 : STA.w SprYRecoil, Y
  LDA.w .kb_tmr-1, X : STA.w SprRecoil, Y
  LDA.b #$0B : STA.w SprState, Y
  LDA.b #$18 : STA.w SprStunTimer, Y
  LDA.b #$40 : STA.w SprTimerA, Y
  BRA .next

  .next16
  SEP #$20
  .next
  DEY : BMI .done
  JMP .loop
  .done
  RTS

  .kb_tmr : db $0C, $10, $14
  .kb_spd : db $28, $38, $48
}

; ---------------------------------------------------------
; Gust Wave vs Ancillae: push Bombs ($07) & Somaria Blocks ($2C) forward,
; and transfer them cleanly through Portal Rod nodes!
; ---------------------------------------------------------
GustJar_WaveAncillae:
{
  LDX.b #$04
  .loop
  LDA.w $0C4A, X
  CMP.b #$2C : BEQ .chk_carry
  CMP.b #$07 : BNE .next_near
  LDA.w $0C5E, X : BNE .next_near
  .chk_carry
  LDA.w $0380, X : BEQ .chk_dist
  .next_near
  JMP .next

  .chk_dist
  JSR GustJar_LoadAncPos16X
  REP #$20
  LDA.b $00 : SEC : SBC.w !GustJarWaveXL : JSR GustJar_Abs16
  CMP.w #$0014 : BCS .next16
  LDA.b $02 : SEC : SBC.w !GustJarWaveYL : JSR GustJar_Abs16
  CMP.w #$0014 : BCS .next16
  SEP #$20

  ; Push forward!
  LDA.w $0C4A, X : CMP.b #$07 : BNE .push_somaria
    JSR GustJar_ApplyAncillaBlastVel
    BRA .chk_portal
  .push_somaria
    LDA.w !GustJarTier : INC A : STA.b $07 ; 2/3/4 px/frame
    LDA.w !GustJarDir : JSR GustJar_StepAncillaDir
    JSR GustJar_LoadAncPos16X

  .chk_portal
  JSR GustJar_FindPortalExit : BCC .next
    JSR GustJar_StoreAncDestX
    LDA.b #$30 : STA.w $012F ; SFX3.$30 portal warp zap
    BRA .next

  .next16
  SEP #$20
  .next
  DEX : BMI .done
  JMP .loop
  .done
  RTS
}

; ---------------------------------------------------------
; Check if point ($00=X16, $02=Y16) enters a live Portal Rod node ($03)
; with a valid opposite-color counterpart ($0632 Blue / $0633 Orange).
; Out: C=1 -> $04=DestX16, $06=DestY16; C=0 -> no portal hit. Preserves X/Y.
; ---------------------------------------------------------
GustJar_FindPortalExit:
{
  PHY
  LDY.b #$0F
  .scan
  LDA.w SprState, Y : CMP.b #$09 : BCC .next_near
  LDA.w SprType, Y : CMP.b #$03 : BNE .next_near ; Sprite_Portal
  LDA.b $1B : BEQ .fl_ok
    LDA.w SprFloor, Y : CMP.b $EE : BNE .next_near
  .fl_ok
  JSR GustJar_LoadSprPos16Y
  REP #$20
  LDA.b $04 : SEC : SBC.b $00 : JSR GustJar_Abs16
  CMP.w #$0010 : BCS .next16
  LDA.b $06 : SEC : SBC.b $02 : JSR GustJar_Abs16
  CMP.w #$0010 : BCS .next16
  SEP #$20

  ; Match Items/portal_rod.asm counterpart validation!
  LDA.w SprSubtype, Y : CMP.b #$01 : BEQ .from_orange
  CMP.b #$02 : BNE .next_near
    LDY.w $0633 : LDA.b #$01 : BRA .chk_pair ; Blue -> exit below Orange
  .next_near
  JMP .next
  .from_orange
    LDY.w $0632 : LDA.b #$02                 ; Orange -> exit right of Blue
  .chk_pair
  CPY.b #$10 : BCS .none
  CMP.w SprSubtype, Y : BNE .none
  LDA.w SprType, Y : CMP.b #$03 : BNE .none
  LDA.w SprState, Y : CMP.b #$09 : BCC .none
  JSR GustJar_LoadSprPos16Y
  LDA.w SprSubtype, Y : CMP.b #$02 : BNE .exit_orange
    ; Exit +16 px right of Blue portal.
    LDA.b $04 : CLC : ADC.b #$10 : STA.b $04
    LDA.b $05 : ADC.b #$00 : STA.b $05
    PLY : SEC : RTS
  .exit_orange
    ; Exit +16 px below Orange portal.
    LDA.b $06 : CLC : ADC.b #$10 : STA.b $06
    LDA.b $07 : ADC.b #$00 : STA.b $07
    PLY : SEC : RTS

  .next16
  SEP #$20
  .next
  DEY : BMI .none
  JMP .scan
  .none
  PLY : CLC : RTS
}

; ---------------------------------------------------------
; Probe 1 tile ahead of nozzle outdoors and cut bush/grass tiles.
; ---------------------------------------------------------
GustJar_CutAheadOverworld:
{
  LDA.b $1B : BNE .skip
  LDA.w !GustJarDir : TAX
  REP #$20
  LDA.b $08 : CLC : ADC.w .ahead_x, X : STA.b $02
  LDA.b $0A : CLC : ADC.w .ahead_y, X : STA.b $00
  SEP #$20
  JMP GustJar_TryCutOverworldFoliage
  .skip
  RTS
  .ahead_x : dw   0,   0, -10,  10
  .ahead_y : dw -10,  10,   0,   0
}

; Cut Overworld bush ($0036/$072A) or tall grass ($037E) at ($02=X16, $00=Y16).
; Mirrors proven Items/fire_burn_bushes.asm O(1) pre-check + vanilla handler.
GustJar_TryCutOverworldFoliage:
{
  LDA.b $1B : BNE .done
  REP #$30
  LDA.b $00 : SEC : SBC.b $E8 : CMP.w #$00E0 : BCS .done16
  LDA.b $02 : SEC : SBC.b $E2 : CMP.w #$0100 : BCS .done16
  LSR.b $02 : LSR.b $02 : LSR.b $02
  LDA.b $00 : SEC : SBC.w $0708 : AND.w $070A : ASL #3 : STA.b $06
  LDA.b $02 : SEC : SBC.w $070C : AND.w $070E : CLC : ADC.b $06 : TAX
  LDA.l $7E2000, X
  CMP.w #$0036 : BEQ .cut
  CMP.w #$072A : BEQ .cut
  CMP.w #$037E : BNE .done16
  .cut
  PHB
  LDA.w $0301 : PHA
  LDA.w $037A : PHA
  LDA.w #$0002 : STA.w $0301 ; sword/cut class for vanilla bush/grass clear
  STZ.w $037A
  SEP #$30
  JSL !GustJarOWTileAct
  REP #$20
  PLA : STA.w $037A
  PLA : STA.w $0301
  SEP #$30
  PLB
  RTS
  .done16
  SEP #$30
  .done
  RTS
}

GustJar_CodeEnd:
print "End of Items/gust_jar.asm ($39)   ", pc
assert pc() <= $3A0000, "Items/gust_jar.asm exceeded Bank $39 tail ($39F000-$39FFFF)"
pullpc

; =========================================================
; Bank $34 ($34E000-$34EFFF): Minish Cap Gust Jar OAM Visuals, NMI VRAM
; Streamer & Custom 4BPP Pixel Art (4 KB dedicated span; zero Bank $39 spill).
; =========================================================
pushpc
org $34E000

; ---------------------------------------------------------
; Unified Post-Ancilla OAM Renderer (called from GustJar_LinkPoseOamHook at
; $0DA435, AFTER $0683D4 OAM_ResetRegionBases, Sprite_Main, and Ancilla_Main).
; Guarantees ZERO OAM overwrite by Somaria Blocks, Bombs, Portals, or Enemies!
; Preserves DBR AND full zero-page $00..$0F (including LinkOAM screen coords
; in $00/$01 and anim frame in $02). Caller preserves X and Y.
; ---------------------------------------------------------
GustJar_RenderOamPostAncilla:
{
  PHB : PHK : PLB
  REP #$20
  LDA.b $00 : PHA : LDA.b $02 : PHA : LDA.b $04 : PHA : LDA.b $06 : PHA
  LDA.b $08 : PHA : LDA.b $0A : PHA : LDA.b $0C : PHA : LDA.b $0E : PHA
  SEP #$20

  LDA.b $11 : BNE .exit
  LDA.b $10 : CMP.b #$07 : BEQ .mod_ok
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BNE .exit
  .mod_ok

  ; 1. Draw Held Minish Cap Gust Jar while Gust Jar owns Link's pose (bit 2).
  LDA.w !GustJarFlags : BIT.b #$04 : BEQ .wind
  LDA.b $5D : ORA.w $02E0 : BNE .wind
    JSR GustJar_DrawHeldJar

  ; 2. Draw Inhale Funnel (state 1) or Blast Crescent Wave (state 2).
  .wind
  LDA.w !GustJarState : CMP.b #$01 : BEQ .inhale
  CMP.b #$02 : BNE .exit
    JSR GustJar_DrawWaveOAM
    BRA .exit
  .inhale
    ; Compute fresh nozzle world coords into ($08,$0A) for DrawInhaleOAM.
    LDA.w !GustJarDir : TAX
    REP #$20
    LDA.b $22 : CLC : ADC.w .noz_x, X : STA.b $08
    LDA.b $20 : CLC : ADC.w .noz_y, X : STA.b $0A
    SEP #$20
    JSR GustJar_DrawInhaleOAM
  .exit
  REP #$20
  PLA : STA.b $0E : PLA : STA.b $0C : PLA : STA.b $0A : PLA : STA.b $08
  PLA : STA.b $06 : PLA : STA.b $04 : PLA : STA.b $02 : PLA : STA.b $00
  SEP #$20
  PLB : RTL

  .noz_x : dw   8,   8,  -6,  22
  .noz_y : dw  -4,  24,  10,  10
}

; Shared Bank $34 OAM/VRAM helpers (DBR=$34, M/X=8).
GustJar_SignExt16:
{
  AND.w #$00FF : BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
  RTS
}
GustJar_IsHighCharge:
{
  LDA.w !GustJarTier : CMP.b #$03 : BCS .yes
  LDA.w !GustJarCapKind : BNE .yes
  CLC : RTS
  .yes
  SEC : RTS
}
GustJar_GetPrio:
{
  LDA.b $EE : AND.b #$03 : TAX
  LDA.w GustJar_OamPrioTbl, X
  RTS
}
GustJar_OamPrioTbl:
  db $20, $10, $30, $20

; C=1 if VRAM $4090/$4190 (tiles $09/$0A/$19/$1A) is safely owned by Gust Jar.
; Preserves X and Y.
GustJar_CanUseItemVram:
{
  LDA.w !GustJarFlags : BIT.b #$04 : BNE .yes
  LDA.b $5D : ORA.w $0301 : ORA.w $037A : ORA.w $0308 : BNE .no
  .yes
  SEC : RTS
  .no
  CLC : RTS
}

; Emit 1 clipped 8x8 OAM sprite at ($00=X, $01=Y) with tile in A, base attr in $07,
; X=slot idx, Y=X*4. Computes animated H/V flip from (X*2 ^ $1A) & $06.
GustJar_EmitWindOam8:
{
  PHA
  TXA : ASL A : EOR.b $1A : AND.b #$06 : ASL #5 : ORA.b $07
  STA.b $06
  PLA
  ; fall through into GustJar_EmitOam8Attr
}
; Emit 1 clipped 8x8 OAM sprite at ($00=X, $01=Y) with tile in A, exact attr in $06,
; X=slot idx, Y=X*4. Advances Y += 4, clears $92[X] = 0 (8x8, X-msb=0).
GustJar_EmitOam8Attr:
{
  PHA
  LDA.b $00 : STA.b ($90), Y : INY
  LDA.b $01 : STA.b ($90), Y : INY
  PLA : STA.b ($90), Y : INY
  LDA.b $06 : STA.b ($90), Y
  PHX : TXY : LDA.b #$00 : STA.b ($92), Y
  TYA : INC A : ASL #2 : TAY : PLX
  RTS
}

; Apply signed 8-bit forward ($05) and perpendicular ($06) offsets relative to
; 16-bit screen anchor ($0C=X16, $0E=Y16) along !GustJarDir.
; Out (M=8): $00 = OAM X, $01 = OAM Y ($F0 if clipped offscreen).
; Preserves X, Y, $02..$0F.
GustJar_ApplyDirOffset16:
{
  REP #$20
  LDA.b $05 : JSR GustJar_SignExt16 : PHA ; stack = signed fwd16
  LDA.b $06 : JSR GustJar_SignExt16 : STA.b $00 ; $00 = signed perp16
  SEP #$20

  LDA.w !GustJarDir
  BEQ .up
  CMP.b #$02 : BEQ .down
  CMP.b #$04 : BEQ .left

  ; Right (6): sx = $0C + fwd, sy = $0E + perp
  REP #$20
  PLA : CLC : ADC.b $0C : PHA
  BRA .horiz_y

  .left
  ; Left (4): sx = $0C - fwd, sy = $0E + perp
  REP #$20
  LDA.b $0C : SEC : SBC.b 1, S : STA.b 1, S
  .horiz_y
  LDA.b $0E : CLC : ADC.b $00
  CMP.w #$00E0 : BCS .clip_pop
  XBA : STA.b $00 ; $01 = sy8
  PLA
  CMP.w #$00F8 : BCS .clip
  SEP #$20
  STA.b $00
  RTS

  .down
  REP #$20
  LDA.b $0E : CLC : ADC.b 1, S : STA.b 1, S
  BRA .vert_x

  .up
  REP #$20
  LDA.b $0E : SEC : SBC.b 1, S : STA.b 1, S
  .vert_x
  LDA.b $0C : CLC : ADC.b $00
  CMP.w #$00F8 : BCS .clip_pop
  STA.b $00 ; $00 = sx8
  PLA
  CMP.w #$00E0 : BCS .clip
  SEP #$20
  STA.b $01
  RTS

  .clip_pop
  PLA
  .clip
  SEP #$20
  LDA.b #$F0 : STA.b $01
  RTS
}

; ---------------------------------------------------------
; Visible Held Minish Cap Gust Jar OAM Sprite (All 4 Directions U/D/L/R).
; Custom 16x16 4BPP art streamed to VRAM $4070/$4170 (OAM tile $07) during NMI
; while Link's Shield is natively hidden ($FF) on poses $0E/$16/$18:
;   - OAM Pal 4 ($08): authentic emerald green pot + radiant Minish gold rim,
;     pulsing cleanly to OAM Pal 2 ($04: glowing wind-sapphire + warm gold)
;     on Tier 3, corked entity, or blast recoil peak!
;   - Up: Region B ($0DBA84) behind Link; D/L/R: Region D ($0DBA8C) in front
;     with custom Minish Cap nozzle mouth suction sheen ($1A/$19) or blast
;     muzzle burst ($A9).
;   - Tier 2/3 suction tremble, swollen belly frame swap & 2px blast kickback.
; Preserves $08..$0B (nozzle world coords needed by DrawInhaleOAM) and DBR.
; ---------------------------------------------------------
GustJar_DrawHeldJar:
{
  ; Compute 16-bit jar screen position ($00=sx16, $02=sy16) so left-edge
  ; facing clips cleanly with X-msb ($03) instead of wrapping across screen.
  LDA.w !GustJarDir : TAX ; X = 0(U), 2(D), 4(L), 6(R)
  REP #$20
  LDA.b $22 : SEC : SBC.b $E2 : CLC : ADC.w .jar_dx, X : STA.b $00
  LDA.b $20 : SEC : SBC.b $E8 : CLC : ADC.w .jar_dy, X : STA.b $02
  SEP #$20

  ; Blast peak recoil kickback (2px back) vs Inhale suction tremble (+/-1px).
  LDA.w !GustJarState : CMP.b #$02 : BNE .inhale_jit
    LDA.w !GustJarFlags : BIT.b #$08 : BEQ .chk_clip
    REP #$20
    LDA.b $00 : CLC : ADC.w .kick_dx, X : STA.b $00
    LDA.b $02 : CLC : ADC.w .kick_dy, X : STA.b $02
    SEP #$20
    BRA .chk_clip

  .inhale_jit
  JSR GustJar_IsHighCharge : BCS .fast_jit
  LDA.w !GustJarTier : CMP.b #$02 : BCC .chk_clip
    LDA.b $1A : AND.b #$04 : BEQ .chk_clip
    LDA.b #$01 : BRA .apply_jit
  .fast_jit
    LDA.b $1A : AND.b #$02 : BEQ + : LDA.b #$01 : BRA .apply_jit : +
    LDA.b #$FF
  .apply_jit
  REP #$20
  JSR GustJar_SignExt16
  CPX.b #$04 : BCS .jit_y
    CLC : ADC.b $00 : STA.b $00 : BRA .jit_done
  .jit_y
    CLC : ADC.b $02 : STA.b $02
  .jit_done
  SEP #$20

  .chk_clip
  ; Allow sx in [-15..255] ($03=hi $03 if <0 else $02) and sy in [0..223].
  REP #$20
  LDA.b $02 : CMP.w #$00E0 : BCS .off16
  LDA.b $00 : BPL .sx_pos
    CMP.w #$FFF1 : BCC .off16
    SEP #$20
    LDA.b #$03 : STA.b $03 ; 16x16 + X-msb=1 (smooth left-edge clip)
    BRA .on_ok
  .sx_pos
  CMP.w #$0100 : BCS .off16
  SEP #$20
  LDA.b #$02 : STA.b $03 ; 16x16, X-msb=0
  BRA .on_ok
  .off16
  SEP #$20
  RTS

  .on_ok
  JSR GustJar_GetPrio : STA.b $04

  ; Jar palette: Pal 4 ($08 emerald/gold), pulsing to Pal 2 ($04 glowing
  ; wind-blue/gold) on blast peak, Tier 3, or corked entity. H-flip Left.
  LDA.w !GustJarState : CMP.b #$02 : BNE .chk_t3
    LDA.w !GustJarFlags : BIT.b #$08 : BNE .blue : BRA .green
  .chk_t3
  JSR GustJar_IsHighCharge : BCC .green
  LDA.b $1A : AND.b #$04 : BEQ .green
  .blue
  LDA.b #$04 : BRA .got_pal
  .green
  LDA.b #$08
  .got_pal
  ORA.b $04
  LDX.w !GustJarDir : CPX.b #$04 : BNE + : ORA.b #$40 : +
  STA.b $05

  ; Facing Up: Region B (4B) behind Link; D/L/R: Region C ($0DBA88, 8B) top-priority
  ; in front of Link (above Somaria Blocks, Bombs & Enemies).
  ; NOTE: Vanilla OAM_AllocateFromRegion* ($0DBB58) returns Y=$90 (non-zero!),
  ; so LDY #$00 MUST occur AFTER the JSL allocator call.
  LDA.w !GustJarDir : BNE .in_front
    LDA.b #$04 : JSL !GustJarOamAllocB
    LDY.b #$00
    LDA.b $00 : STA.b ($90), Y : INY
    LDA.b $02 : STA.b ($90), Y : INY
    LDA.b #$07 : STA.b ($90), Y : INY ; Streamed 16x16 Minish Cap Gust Jar
    LDA.b $05 : STA.b ($90), Y
    LDA.b $03 : STA.b ($92)           ; 16x16 high OAM
    RTS

  .in_front
  LDA.b #$08 : JSL !GustJarOamAllocC
  LDY.b #$00
  ; Slot 0 (8x8): Minish Cap nozzle suction sheen ($1A L/R, $19 Down) during
  ; inhale, muzzle burst ($A9) on blast peak, or hidden ($F0) during recovery.
  LDA.b #$F0 : STA.b $07 ; default clipped Y
  LDA.b #$00 : STA.b $06 ; default mouth X
  LDA.w !GustJarState : CMP.b #$02 : BNE .m_inhale
    LDA.w !GustJarFlags : BIT.b #$08 : BEQ .m_write
    LDA.b #$A9 : PHA
    LDA.b $1A : AND.b #$06 : ASL #5 : ORA.b #$04 : ORA.b $04
    BRA .m_pos

  .m_inhale
  LDA.w !GustJarDir : CMP.b #$02 : BEQ .m_down
    ; Side L/R: custom flared suction-ring sheen ($1A) pulsing V-flip on frame bit 2.
    LDA.b #$1A : PHA
    LDA.b $1A : AND.b #$04 : ASL #5 ; $00 or $80 V-flip
    LDX.w !GustJarDir : CPX.b #$04 : BNE + : ORA.b #$40 : + ; H-flip on Left
    ORA.b #$04 : ORA.b $04
    BRA .m_pos
  .m_down
    ; Down: custom curled air-loop wisp ($19) shimmering at circular mouth.
    LDA.b #$19 : PHA
    LDA.b $1A : AND.b #$06 : ASL #5 : ORA.b #$04 : ORA.b $04

  .m_pos
  PHA ; stack: [attr, tile]
  LDA.w !GustJarDir : TAX ; 2=D, 4=L, 6=R
  REP #$20
  LDA.b $00 : CLC : ADC.w .mouth_dx, X : CMP.w #$00F8 : BCS .m_clip16
  SEP #$20
  STA.b $06
  LDA.b $02 : CLC : ADC.w .mouth_dy, X : CMP.b #$E0 : BCS .m_emit_pop
  STA.b $07
  BRA .m_emit_pop
  .m_clip16
  SEP #$20
  .m_emit_pop
  PLA : TAX ; X = mouth attr
  PLA       ; A = mouth tile
  BRA .m_store

  .m_write
  LDA.b #$A9 : LDX.b #$04
  .m_store
  PHA
  LDA.b $06 : STA.b ($90), Y : INY
  LDA.b $07 : STA.b ($90), Y : INY
  PLA : STA.b ($90), Y : INY
  TXA : STA.b ($90), Y : INY

  ; Slot 1 (16x16): Held Minish Cap Gust Jar (VRAM $4070/$4170 -> tile $07).
  LDA.b $00 : STA.b ($90), Y : INY
  LDA.b $02 : STA.b ($90), Y : INY
  LDA.b #$07 : STA.b ($90), Y : INY
  LDA.b $05 : STA.b ($90), Y
  LDY.b #$00 : LDA.b #$00 : STA.b ($92), Y ; Slot 0 = 8x8 mouth FX
  INY        : LDA.b $03  : STA.b ($92), Y ; Slot 1 = 16x16 Gust Jar
  RTS

  ; Indexed by !GustJarDir (0=U, 2=D, 4=L, 6=R).
  .jar_dx   : dw   0,   0,  -9,   9
  .jar_dy   : dw  -9,  13,   6,   6
  .kick_dx  : dw   0,   0,   2,  -2
  .kick_dy  : dw   2,  -2,   0,   0
  .mouth_dx : dw   0,   4,  -2,  10
  .mouth_dy : dw   0,   9,   4,   4
}

; ---------------------------------------------------------
; Minish Cap Directional Wind-Suction Funnel OAM FX (4/5/6 wind streaks & curls).
; Uses custom 4BPP Minish Cap Inhale Wind Set streamed to VRAM $4090/$4190:
;   - $09: Horizontal tapered wind speed-streak (oriented inward into jar!)
;   - $0A: Vertical swooping airflow ribbon (oriented inward into jar!)
;   - $19: Hollow curled Minish wind wisp / air-loop puff (spinning inward!)
;   - $1A: Flared suction-ring sheen near nozzle mouth!
; ---------------------------------------------------------
GustJar_DrawInhaleOAM:
{
  LDA.w !GustJarTier : CLC : ADC.b #$03 : STA.b $04
  ASL #2
  JSL !GustJarOamAllocA

  JSR GustJar_GetPrio : ORA.b #$04 : STA.b $07 ; BG prio | Pal 2 (white/mint/aqua)

  ; Precompute frame * (Tier + 1) once into $02 (2x / 3x / 4x suction speed).
  LDX.w !GustJarTier : LDA.b $1A
  - : CLC : ADC.b $1A : DEX : BNE -
  STA.b $02

  ; 16-bit nozzle screen anchor centered for 8x8 into ($0C, $0E).
  REP #$20
  LDA.b $08 : SEC : SBC.b $E2 : SEC : SBC.w #$0004 : STA.b $0C
  LDA.b $0A : SEC : SBC.b $E8 : SEC : SBC.w #$0004 : STA.b $0E
  SEP #$20

  LDY.b #$00
  LDX.b #$00
  .part
  LDA.b $02 : CLC : ADC.w .phase_off, X : AND.b #$1F
  EOR.b #$1F : STA.b $03 ; inv: 31 (outer cone) -> 0 (jar mouth)

  ; Forward distance ($05) scaled by Tier (4..42 / 4..66 / 4..81 px).
  LDA.w !GustJarTier : CMP.b #$02 : BCC .d1 : BEQ .d2
    LDA.b $03 : LSR A : STA.b $05
    LDA.b $03 : ASL A : CLC : ADC.b $05 : BRA .d_add
  .d2
    LDA.b $03 : ASL A : BRA .d_add
  .d1
    LDA.b $03 : LSR #2 : CLC : ADC.b $03
  .d_add
  ADC.b #$04 : STA.b $05

  ; Funneling perpendicular offset ($06): tapers +/-15 -> 0 into jar mouth + swirl ripple.
  LDA.b $03 : LSR A : STA.b $06
  LDA.w .lane_sign, X : BEQ .l_zero
  CMP.b #$01 : BEQ .l_ok
    LDA.b $06 : EOR.b #$FF : INC A : STA.b $06 : BRA .l_ok
  .l_zero
    STZ.b $06
  .l_ok
  LDA.b $1A : LSR A : CLC : ADC.b $03 : AND.b #$07 : PHX : TAX
  LDA.w .swirl, X : PLX
  CLC : ADC.b $06 : STA.b $06

  JSR GustJar_ApplyDirOffset16

  ; Select custom Minish Cap inhale tile + inward directional flip:
  ;   - inv < 8:   inner mouth -> $19 (air curl) / $1A (suction sheen)
  ;   - 8 <= inv < 18: mid -> alternating directional streak ($09/$0A) & $19 curl
  ;   - inv >= 18: outer -> directional speed streak ($09 H / $0A V) pointing INWARD!
  LDA.b $03 : CMP.b #$08 : BCC .t_inner
  CMP.b #$12 : BCS .t_streak
    TXA : EOR.b $1A : AND.b #$02 : BNE .t_curl
  .t_streak
    ; Directional inward streak: L/R -> $09 (H-flip when facing Right so tip points Left);
    ; U/D -> $0A (V-flip when facing Down so tip points Up into jar).
    LDA.w !GustJarDir : CMP.b #$04 : BCS .s_horiz
      ; Vertical (0=U -> flow Down $00; 2=D -> flow Up $80)
      LDA.w !GustJarDir : BEQ + : LDA.b #$80 : BRA ++ : + : LDA.b #$00 : ++
      STA.b $05
      LDA.w .lane_sign, X : CMP.b #$02 : BNE + : LDA.b #$40 : TSB.b $05 : +
      LDA.b $05 : ORA.b $07 : STA.b $06
      LDA.b #$0A
      JSR GustJar_EmitOam8Attr
      BRA .next_part
  .s_horiz
    ; Horizontal (4=L -> flow Right $00; 6=R -> flow Left $40)
    LDA.w !GustJarDir : CMP.b #$06 : BNE + : LDA.b #$40 : BRA ++ : + : LDA.b #$00 : ++
    STA.b $05
    LDA.w .lane_sign, X : CMP.b #$02 : BNE + : LDA.b #$80 : TSB.b $05 : +
    LDA.b $05 : ORA.b $07 : STA.b $06
    LDA.b #$09
    JSR GustJar_EmitOam8Attr
    BRA .next_part

  .t_inner
    TXA : EOR.b $1A : AND.b #$02 : BNE .t_sheen
  .t_curl
    LDA.b #$19
    JSR GustJar_EmitWindOam8
    BRA .next_part

  .t_sheen
    LDA.b #$1A
    JSR GustJar_EmitWindOam8

  .next_part
  INX : CPX.b $04 : BCS + : JMP .part : +
  RTS

  .phase_off : db 0, 11, 21, 5, 16, 26
  .lane_sign : db 1, 2, 1, 2, 0, 2
  .swirl     : db 0, 2, 3, 2, 0, -2, -3, -2
}

; ---------------------------------------------------------
; Minish Cap Blast Crescent Wave OAM FX (3/4/5 sprites, ZERO Portal Rod $EE!).
;   - Slot 0 (ALL Tiers): 16x16 directional animated Minish Cap Crescent Air-Gust
;     Wave (VRAM $4090/$4190 -> tile $09, H0/H1 for L/R, V0/V1 for U/D, oriented
;     in direction of travel!). Falls back cleanly to resident white billowing
;     dust cloud $86 if Link starts another $0109 item after follow-through.
;   - Slots 1..Count-1 (8x8, Pal 2): crisp expanding white/mint wing puffs &
;     trailing wind streaks scaling across Tier 1 (2), Tier 2 (3), Tier 3 (4).
; ---------------------------------------------------------
GustJar_DrawWaveOAM:
{
  LDA.w !GustJarTier : CLC : ADC.b #$02 : STA.b $04
  ASL #2
  JSL !GustJarOamAllocA

  JSR GustJar_GetPrio : ORA.b #$04 : STA.b $07 ; BG prio | Pal 2 (white/mint/aqua)

  ; Wave age ($03) & expansion = age >> 2 ($02, 0..6 px).
  LDX.w !GustJarTier
  LDA.l GustJar_WaveLife-1, X : SEC : SBC.w !GustJarWaveTmr : STA.b $03
  LSR #2 : STA.b $02

  ; 16-bit screen anchor centered for 8x8 ($0C, $0E).
  REP #$20
  LDA.w !GustJarWaveXL : SEC : SBC.b $E2 : SEC : SBC.w #$0004 : STA.b $0C
  LDA.w !GustJarWaveYL : SEC : SBC.b $E8 : SEC : SBC.w #$0004 : STA.b $0E
  SEP #$20

  ; --- Slot 0: 16x16 Minish Cap Directional Crescent Wave ($09) or $86 Fallback ---
  LDY.b #$00
  ; Compute 16x16 top-left ($00=sx16, $01=sy8, $05=hi $02/$03) with smooth left clip.
  REP #$20
  LDA.b $0E : SEC : SBC.w #$0004 : CMP.w #$00E0 : BCS .c16_hide
  PHA ; stack = sy16
  LDA.b $0C : SEC : SBC.w #$0004
  BPL .c16_pos
    CMP.w #$FFF1 : BCC .c16_hide_pop
    STA.b $00
    PLA : SEP #$20 : STA.b $01
    LDA.b #$03 : STA.b $05 ; 16x16 + X-msb=1
    BRA .c16_emit
  .c16_pos
  CMP.w #$0100 : BCS .c16_hide_pop
  STA.b $00
  PLA : SEP #$20 : STA.b $01
  LDA.b #$02 : STA.b $05 ; 16x16, X-msb=0
  BRA .c16_emit

  .c16_hide_pop
  PLA
  .c16_hide
  SEP #$20
  LDA.b #$00 : STA.b $00
  LDA.b #$F0 : STA.b $01
  LDA.b #$02 : STA.b $05

  .c16_emit
  JSR GustJar_CanUseItemVram : BCC .c16_fallback
    ; Custom Minish Cap 16x16 Blast Crescent Wave ($09), oriented in travel dir!
    LDA.w !GustJarDir : LSR A : TAX
    LDA.w .wave_flip, X : ORA.b $07 : STA.b $06
    LDA.b #$09
    BRA .c16_write
  .c16_fallback
    ; Graceful fallback if another $0109 item is active: resident white cloud $86!
    LDA.b $1A : AND.b #$06 : ASL #5 : ORA.b $07 : STA.b $06
    LDA.b #$86
  .c16_write
  PHA
  LDA.b $00 : STA.b ($90), Y : INY
  LDA.b $01 : STA.b ($90), Y : INY
  PLA : STA.b ($90), Y : INY
  LDA.b $06 : STA.b ($90), Y : INY
  LDA.b $05 : STA.b ($92) ; Slot 0 = 16x16 ($02 or $03)

  ; --- Slots 1..Count-1: Expanding Airy Wing Puffs & Trailing Wind Streak (8x8) ---
  LDX.b #$01
  .wloop
  ; Tier 2 Slot 3 = trailing breeze streak behind crescent wave.
  CPX.b #$03 : BNE .table_wing
  LDA.w !GustJarTier : CMP.b #$03 : BCS .table_wing
    LDA.b #$F6 : STA.b $05
    STZ.b $06
    LDA.w !GustJarDir : CMP.b #$04 : LDA.b #$CC : BCC .w_draw
    LDA.b #$C2 : BRA .w_draw

  .table_wing
  LDA.w .w_back-1, X : STA.b $05
  LDA.w .w_perp-1, X : CLC : ADC.b $02 : STA.b $06
  TXA : AND.b #$01 : BNE .w_setp ; odd X (1,3) -> +, even X (2,4) -> -
    LDA.b $06 : EOR.b #$FF : INC A : STA.b $06
  .w_setp
  LDA.b $1A : AND.b #$04 : BEQ + : LDA.b #$03 : +
  EOR.w .w_tile-1, X

  .w_draw
  PHA
  JSR GustJar_ApplyDirOffset16
  PLA
  JSR GustJar_EmitWindOam8
  INX : CPX.b $04 : BCC .wloop
  RTS

  ; Directional flip for 16x16 Minish Crescent ($09): U=$80(V), D=$00, L=$40(H), R=$00.
  .wave_flip : db $80, $00, $40, $00
  .w_back    : db $FC, $FC, $F8, $F8
  .w_perp    : db   7,   7,  13,  13
  .w_tile    : db $CE, $CE, $CC, $CC
}

; =========================================================
; NMI VRAM Streamer — chained from Bombchu_NmiUpload (Items/bombchu.asm) right
; before .done exit. Entry: M=8, X=16, DBR=$00; DMA0=$1801, VMAIN=$80.
; Exit: A, X, Y, P, DBR preserved; $4304=$7E, $4302=$0ADC restored cleanly.
; Zero conflict with Sword ($05/$4050) or Somaria Block ($0C/$40C0).
; =========================================================
GustJar_NmiUpload:
{
  PHP : PHA
  LDA.w !GustJarState : BNE .active
    PLA : PLP : RTL
  .active
  ; Stream OBJ VRAM only during gameplay modules ($07 Indoors, $09 OW, $0B Special OW).
  LDA.b $10 : CMP.b #$07 : BEQ .mod_ok
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BEQ .mod_ok
    PLA : PLP : RTL

  .mod_ok
  PHX : PHY
  LDA.b #GustJarWorldGfx>>16 : STA.w $4304

  ; --- Slot 1: Held Minish Cap Gust Jar -> VRAM $4070/$4170 (OAM tile $07, 16x16) ---
  ; Uploaded ONLY while Gust Jar owns pose (bit 2) & Shield is natively hidden ($FF).
  LDA.w !GustJarFlags : BIT.b #$04 : BEQ .slot2
  LDA.b $5D : ORA.w $02E0 : BNE .slot2
    LDA.w !GustJarDir : BEQ .jar_up
    CMP.b #$02 : BEQ .jar_down
    ; Side L/R: swollen belly frame 1 when corked, blast recoil peak, or Tier>=2 pulse.
    LDA.w !GustJarCapKind : BNE .jar_swollen
    LDA.w !GustJarState : CMP.b #$02 : BNE .jar_inhale_side
      LDA.w !GustJarFlags : BIT.b #$08 : BNE .jar_swollen
      BRA .jar_normal
    .jar_inhale_side
    LDA.w !GustJarTier : CMP.b #$02 : BCC .jar_normal
    LDA.b $1A : AND.b #$04 : BNE .jar_swollen
    .jar_normal  : LDA.b #$00 : BRA .jar_dma
    .jar_swollen : LDA.b #$01 : BRA .jar_dma
    .jar_down    : LDA.b #$02 : BRA .jar_dma
    .jar_up      : LDA.b #$03
    .jar_dma
    LDX.w #$4070
    JSR .upload_16x16

  ; --- Slot 2: Minish Cap Wind FX -> VRAM $4090/$4190 (OAM $09/$0A/$19/$1A) ---
  ; Skipped if bit 2 is clear AND another $0109 item ($5D/$0301/$037A/$0308) is active.
  .slot2
  LDA.w !GustJarFlags : BIT.b #$04 : BNE .slot2_go
  LDA.b $5D : ORA.w $0301 : ORA.w $037A : ORA.w $0308 : BNE .restore_dma
  .slot2_go
  LDA.w !GustJarState : CMP.b #$02 : BEQ .wind_blast
    ; State 1 (Inhale): Block 4 = 4x 8x8 Minish Cap Inhale Wind Set ($09/$0A/$19/$1A).
    LDA.b #$04
    BRA .wind_dma
  .wind_blast
    ; State 2 (Blast Wave): Blocks 5/6 (Horizontal H0/H1) or 7/8 (Vertical V0/V1),
    ; alternating every 4 frames via !GustJarWaveTmr bit 2.
    LDA.w !GustJarWaveTmr : AND.b #$04 : LSR #2 ; 0 or 1
    PHA
    LDA.w !GustJarDir : CMP.b #$04 : BCS .blast_h
      PLA : CLC : ADC.b #$07 : BRA .wind_dma
    .blast_h
      PLA : CLC : ADC.b #$05
  .wind_dma
  LDX.w #$4090
  JSR .upload_16x16

  .restore_dma
  SEP #$20
  LDA.b #$7E : STA.w $4304
  REP #$20
  LDA.w $0ADC : STA.w $4302 ; restore animated BG tile DMA source for $008B5C
  SEP #$20
  PLY : PLX : PLA : PLP
  RTL

  ; Upload 16x16 block index A (0..8, 128B each) to VRAM word X (top) and X+$100 (bottom).
  ; Entry: M=8, X=16, DBR=$00, $4304 = GustJarWorldGfx>>16. Exit: M=8, X=16.
  .upload_16x16
  REP #$20
  AND.w #$00FF : ASL #7
  CLC : ADC.w #GustJarWorldGfx : TAY
  STX.w $2116
  STY.w $4302
  LDA.w #$0040 : STA.w $4305
  SEP #$20
  LDA.b #$01 : STA.w $420B
  REP #$20
  TXA : CLC : ADC.w #$0100 : STA.w $2116
  TYA : CLC : ADC.w #$0040 : STA.w $4302
  LDA.w #$0040 : STA.w $4305
  SEP #$20
  LDA.b #$01 : STA.w $420B
  RTS
}

GustJarWorldGfx:
  incbin "Data/graphics/items/gust_jar_world.4bpp"
GustJarWorldGfxEnd:
assert GustJarWorldGfxEnd-GustJarWorldGfx == $0480, "Gust Jar world GFX must be 9 x 16x16 frames (1152B)"
assert (GustJarWorldGfx>>16) == ((GustJarWorldGfxEnd-1)>>16), "Gust Jar DMA source crosses bank"
print "End of GustJar Bank $34 block     ", pc
assert pc() <= $34F000, "Gust Jar Bank $34 NMI upload/GFX exceeded $34E000-$34EFFF"
pullpc
