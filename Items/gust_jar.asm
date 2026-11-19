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
!GustJarFlags     = $027F ; bit0=wind signal (sand/web/pinwheel), bit1=launched entity
!GustJarOamAllocD = $0DBA8C ; vanilla OAM_AllocateFromRegionD
!GustJarOWTileAct = $1BBD7A ; vanilla HandleItemTileAction_Overworld

assert !GustJarFlags < $0280, "Gust Jar exceeds vanilla free WRAM $0224-$027F"

GustJar_CodeStart:

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
  LDA.b #$01 : STA.w !GustJarState
  STA.w !GustJarTier
  STZ.w !GustJarCharge
  STZ.w !GustJarCapKind
  STZ.w !GustJarCapSlot
  STZ.w !GustJarWaveTmr
  STZ.w !GustJarFlags
  LDA.b $2F : AND.b #$06 : STA.w !GustJarDir

  ; Latch physical trigger button (2=X, 1=Y) for hold/release tracking.
  LDA.l ItemBindingButton : CMP.b #$02 : BEQ .use_x
    LDA.b #$01
  .use_x
  STA.w !GustJarButton

  ; Hold stance: keep $3A bit 6 claimed, slow walk/aim speed ($5E=$08).
  LDA.b #$40 : TSB.b $3A
  LDA.b #$08 : STA.b $5E
  LDA.b #$09 : STA.w $012E ; SFX2.09 crisp wind-intake fwish
  PLB : RTL

  .refuse
  LDA.b #$40 : TRB.b $3A
  PLB : RTL
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
  LDA.b #$40 : TRB.b $3A
  LDA.b $5E : CMP.b #$08 : BNE +
    STZ.b $5E
  +
  STZ.w !GustJarState
  STZ.w !GustJarButton
  STZ.w !GustJarCharge
  STZ.w !GustJarTier
  STZ.w !GustJarDir
  STZ.w !GustJarCapKind
  STZ.w !GustJarCapSlot
  STZ.w !GustJarWaveTmr
  STZ.w !GustJarFlags
  RTS
}

; ---------------------------------------------------------
; C=1 when gameplay context allows active Gust Jar inhaling.
; ---------------------------------------------------------
GustJar_ContextOk:
{
  LDA.l GustJarOwned : CMP.b #$01 : BNE .no
  LDA.b $10 : CMP.b #$07 : BEQ .mod_ok
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BNE .no
  .mod_ok
  LDA.b $11 : ORA.b $6C : ORA.b $5D : ORA.b $4D : ORA.b $46 : BNE .no
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

  ; Keep hold stance + track Link facing smoothly.
  LDA.b #$40 : TSB.b $3A
  LDA.b #$08 : STA.b $5E
  LDA.b $2F : AND.b #$06 : STA.w !GustJarDir

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

  ; Expose wind signal flag at Tier >= 2 for sand/web/pinwheel puzzles.
  CMP.b #$02 : BCC .no_sig
    LDA.w !GustJarFlags : ORA.b #$01 : STA.w !GustJarFlags
  .no_sig

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
  LDA.w !GustJarTier : CMP.b #$02 : BCC .draw
  LDA.w !GustJarCharge : AND.b #$07 : BNE .draw
    JSR GustJar_CutAheadOverworld
  .draw
  JSR GustJar_DrawInhaleOAM
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
  LDA.b $1A : AND.b #$02 : LSR A : STA.b $00
  REP #$20
  LDA.b $08 : SEC : SBC.w #$0008
  SEP #$20
  CLC : ADC.b $00 : STA.w SprX, Y
  XBA : ADC.b #$00 : STA.w SprXH, Y
  REP #$20
  LDA.b $0A : SEC : SBC.w #$0008
  SEP #$20
  STA.w SprY, Y : XBA : STA.w SprYH, Y
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
; In:  $00/$02 = target center X/Y (16-bit), $06 = cone range (40/60/80 px).
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
  BPL .perp_pos
    EOR.w #$FFFF : INC A
  .perp_pos
  STA.b $0C

  ; Require 4 <= fwd <= range ($06).
  LDA.b $04 : BMI .out
  CMP.w #$0004 : BCC .out
  LDA.b $06 : AND.w #$00FF
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
  LDX.w !GustJarTier
  LDA.w GustJar_ConeRange-1, X : STA.b $06
  LDY.b #$0F
  .loop
  ; Skip already-captured sprite.
  LDA.w !GustJarCapKind : CMP.b #$01 : BNE .not_cap
    TYA : CMP.w !GustJarCapSlot : BNE .not_cap
      JMP .next
  .not_cap
  LDA.w SprState, Y : CMP.b #$09 : BEQ .alive
  CMP.b #$0B : BEQ .alive
    JMP .next
  .alive
  LDA.b $1B : BEQ .floor_ok
    LDA.w SprFloor, Y : CMP.b $EE : BEQ .floor_ok
      JMP .next
  .floor_ok
  ; Compute sprite center ($00=X+8, $02=Y+8).
  LDA.w SprX, Y : CLC : ADC.b #$08 : STA.b $00
  LDA.w SprXH, Y : ADC.b #$00 : STA.b $01
  LDA.w SprY, Y : CLC : ADC.b #$08 : STA.b $02
  LDA.w SprYH, Y : ADC.b #$00 : STA.b $03
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
    LDA.b #$01 : STA.b $07
    JSR GustJar_PullSpriteReverseDir
    STZ.w $0642 ; statue recomputes pressure-plate contact
    BRA .next
  .not_statue
  CMP.b #Sprite_IceBlock : BNE .not_ice
    LDA.b #$01 : STA.b $07
    JSR GustJar_PullSpriteReverseDir
    STZ.w $0642
    BRA .next
  .not_ice

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
; ---------------------------------------------------------
GustJar_PullSpriteToLink:
{
  ; X axis
  REP #$20
  LDA.w SprX, Y : AND.w #$00FF : STA.b $0C
  LDA.w SprXH, Y : XBA : AND.w #$FF00 : ORA.b $0C
  CMP.b $22 : BEQ .do_y
  BCC .move_right
    ; Sprite is right of Link -> pull left (wall bit 1 = $02).
    SEP #$20
    LDA.w $0E70, Y : AND.b #$02 : BNE .do_y8
    LDA.w SprX, Y : SEC : SBC.b $07 : STA.w SprX, Y
    LDA.w SprXH, Y : SBC.b #$00 : STA.w SprXH, Y
    BRA .do_y8
  .move_right
    ; Sprite is left of Link -> pull right (wall bit 0 = $01).
    SEP #$20
    LDA.w $0E70, Y : AND.b #$01 : BNE .do_y8
    LDA.w SprX, Y : CLC : ADC.b $07 : STA.w SprX, Y
    LDA.w SprXH, Y : ADC.b #$00 : STA.w SprXH, Y
    BRA .do_y8
  .do_y
  SEP #$20
  .do_y8
  ; Y axis (target LinkY + 4)
  REP #$20
  LDA.b $20 : CLC : ADC.w #$0004 : STA.b $0E
  LDA.w SprY, Y : AND.w #$00FF : STA.b $0C
  LDA.w SprYH, Y : XBA : AND.w #$FF00 : ORA.b $0C
  CMP.b $0E : BEQ .done16
  BCC .move_down
    ; Sprite is below Link -> pull up (wall bit 3 = $08).
    SEP #$20
    LDA.w $0E70, Y : AND.b #$08 : BNE .done
    LDA.w SprY, Y : SEC : SBC.b $07 : STA.w SprY, Y
    LDA.w SprYH, Y : SBC.b #$00 : STA.w SprYH, Y
    RTS
  .move_down
    ; Sprite is above Link -> pull down (wall bit 2 = $04).
    SEP #$20
    LDA.w $0E70, Y : AND.b #$04 : BNE .done
    LDA.w SprY, Y : CLC : ADC.b $07 : STA.w SprY, Y
    LDA.w SprYH, Y : ADC.b #$00 : STA.w SprYH, Y
    RTS
  .done16
  SEP #$20
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
  BEQ .up
  CMP.b #$02 : BEQ .down
  CMP.b #$04 : BEQ .left
  ; Right (6): wall bit 0 ($01)
  LDA.w $0E70, Y : AND.b #$01 : BNE .blocked
  LDA.w SprX, Y : CLC : ADC.b $07 : STA.w SprX, Y
  LDA.w SprXH, Y : ADC.b #$00 : STA.w SprXH, Y
  RTS
  .left
  ; Left (4): wall bit 1 ($02)
  LDA.w $0E70, Y : AND.b #$02 : BNE .blocked
  LDA.w SprX, Y : SEC : SBC.b $07 : STA.w SprX, Y
  LDA.w SprXH, Y : SBC.b #$00 : STA.w SprXH, Y
  RTS
  .down
  ; Down (2): wall bit 2 ($04)
  LDA.w $0E70, Y : AND.b #$04 : BNE .blocked
  LDA.w SprY, Y : CLC : ADC.b $07 : STA.w SprY, Y
  LDA.w SprYH, Y : ADC.b #$00 : STA.w SprYH, Y
  RTS
  .up
  ; Up (0): wall bit 3 ($08)
  LDA.w $0E70, Y : AND.b #$08 : BNE .blocked
  LDA.w SprY, Y : SEC : SBC.b $07 : STA.w SprY, Y
  LDA.w SprYH, Y : SBC.b #$00 : STA.w SprYH, Y
  .blocked
  RTS
}

; ---------------------------------------------------------
; Pull active Bombs ($07) and Somaria Blocks ($2C) in inhale cone.
; Captures Bombs within 20 px of nozzle.
; ---------------------------------------------------------
GustJar_InhaleAncillae:
{
  LDX.w !GustJarTier
  LDA.w GustJar_ConeRange-1, X : STA.b $06
  LDX.b #$04
  .loop
  LDA.w !GustJarCapKind : CMP.b #$02 : BNE .not_cap
    TXA : CMP.w !GustJarCapSlot : BEQ .next
  .not_cap
  LDA.w $0C4A, X
  CMP.b #$07 : BEQ .is_bomb
  CMP.b #$2C : BNE .next
  ; Somaria Block: skip if carried by Link.
  LDA.w $0380, X : BNE .next
  BRA .check_cone

  .is_bomb
  ; Active Bomb: skip if exploding or carried by Link.
  LDA.w $0C5E, X : BNE .next
  LDA.w $0380, X : BNE .next

  .check_cone
  LDA.w $0C04, X : STA.b $00
  LDA.w $0C18, X : STA.b $01
  LDA.w $0BFA, X : STA.b $02
  LDA.w $0C0E, X : STA.b $03
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
  LDA.b #$01 : STA.w !GustJarFlags ; wind-blast signal active
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
  LDA.w !GustJarFlags : ORA.b #$02 : STA.w !GustJarFlags
  RTS

  .launch_sprite
  LDY.w !GustJarCapSlot : CPY.b #$10 : BCS .done
  LDA.w !GustJarDir : LSR A : TAX
  LDA.w !GustJarTier : DEC A : ASL #2 : STA.b $00
  TXA : CLC : ADC.b $00 : TAX
  LDA.w GustJar_LaunchVX, X : STA.w SprXSpeed, Y : STA.w SprXRecoil, Y
  LDA.w GustJar_LaunchVY, X : STA.w SprYSpeed, Y : STA.w SprYRecoil, Y
  LDA.b #$08 : STA.w SprHeight, Y
  LDA.b #$10 : STA.w SprTimerF, Y ; upward arc velocity
  LDA.b #$0C : STA.w SprRecoil, Y
  LDA.w !GustJarFlags : ORA.b #$02 : STA.w !GustJarFlags
  .done
  RTS
}

GustJar_WaveLife:
  db 14, 20, 26
; Launch velocities indexed by (tier-1)*4 + dir/2 (U, D, L, R).
GustJar_LaunchVX:
  db $00, $00, $C8, $38 ; Tier 1 (+/- $38)
  db $00, $00, $BC, $44 ; Tier 2 (+/- $44)
  db $00, $00, $B0, $50 ; Tier 3 (+/- $50)
GustJar_LaunchVY:
  db $C8, $38, $00, $00 ; Tier 1
  db $BC, $44, $00, $00 ; Tier 2
  db $B0, $50, $00, $00 ; Tier 3

; Set ancilla X velocity along !GustJarDir scaled by !GustJarTier.
GustJar_ApplyAncillaBlastVel:
{
  PHY
  LDA.w !GustJarDir : LSR A : STA.w $0C72, X : TAY
  LDA.w !GustJarTier : DEC A : ASL #2 : STA.b $00
  TYA : CLC : ADC.b $00 : TAY
  LDA.w GustJar_LaunchVY, Y : STA.w $0C22, X
  LDA.w GustJar_LaunchVX, Y : STA.w $0C2C, X
  PLY
  RTS
}

; ---------------------------------------------------------
; Phase 2 Per-Frame Update: Advance Gust Wave, Launched Projectile,
; Knockback/Stun, Projectile Deflection, Statue/Bomb/Somaria Push & Portals!
; ---------------------------------------------------------
GustJar_TickWave:
{
  ; Abort cleanly on room/screen transition or non-gameplay module.
  LDA.b $10 : CMP.b #$07 : BEQ .mod_ok
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BNE .abort
  .mod_ok
  LDA.b $11 : BNE .abort

  ; Release Link's button-hold lock quickly after 5 follow-through frames.
  LDX.w !GustJarTier : LDA.w GustJar_WaveLife-1, X
  SEC : SBC.b #$05
  CMP.w !GustJarWaveTmr : BCC .keep_lock
    LDA.b #$40 : TRB.b $3A
    LDA.b $5E : CMP.b #$08 : BNE .keep_lock
      STZ.b $5E
  .keep_lock

  DEC.w !GustJarWaveTmr : BNE .alive
  .abort
  JMP GustJar_Abort

  .alive
  ; Advance Wave center forward by (Tier + 2) px/frame (3/4/5 px/frame).
  LDA.w !GustJarTier : CLC : ADC.b #$02 : STA.b $07
  LDA.w !GustJarDir
  BEQ .adv_u
  CMP.b #$02 : BEQ .adv_d
  CMP.b #$04 : BEQ .adv_l
  ; Right
  LDA.w !GustJarWaveXL : CLC : ADC.b $07 : STA.w !GustJarWaveXL
  LDA.w !GustJarWaveXH : ADC.b #$00 : STA.w !GustJarWaveXH
  BRA .adv_done
  .adv_l
  LDA.w !GustJarWaveXL : SEC : SBC.b $07 : STA.w !GustJarWaveXL
  LDA.w !GustJarWaveXH : SBC.b #$00 : STA.w !GustJarWaveXH
  BRA .adv_done
  .adv_d
  LDA.w !GustJarWaveYL : CLC : ADC.b $07 : STA.w !GustJarWaveYL
  LDA.w !GustJarWaveYH : ADC.b #$00 : STA.w !GustJarWaveYH
  BRA .adv_done
  .adv_u
  LDA.w !GustJarWaveYL : SEC : SBC.b $07 : STA.w !GustJarWaveYL
  LDA.w !GustJarWaveYH : SBC.b #$00 : STA.w !GustJarWaveYH
  .adv_done

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
  JSR GustJar_DrawWaveOAM
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
  LDA.w $0C04, X : STA.b $00 : LDA.w $0C18, X : STA.b $01
  LDA.w $0BFA, X : STA.b $02 : LDA.w $0C0E, X : STA.b $03
  JSR GustJar_FindPortalExit : BCC .done
    ; Warp bomb cleanly to counterpart portal exit!
    LDA.b $04 : STA.w $0C04, X : LDA.b $05 : STA.w $0C18, X
    LDA.b $06 : STA.w $0BFA, X : LDA.b $07 : STA.w $0C0E, X
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
  PLY
  BCC .hit_next
  ; Distance check <= 16 px against launched sprite ($00/$02).
  REP #$20
  LDA.w SprX, X : AND.w #$00FF : STA.b $04
  LDA.w SprXH, X : XBA : AND.w #$FF00 : ORA.b $04
  SEC : SBC.b $00 : BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0010 : BCS .hit_next16
  LDA.w SprY, X : AND.w #$00FF : STA.b $04
  LDA.w SprYH, X : XBA : AND.w #$FF00 : ORA.b $04
  SEC : SBC.b $02 : BPL + : EOR.w #$FFFF : INC A : +
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
  LDA.w SprState, Y : CMP.b #$09 : BEQ .alive
  CMP.b #$0B : BEQ .alive
    JMP .next
  .alive
  LDA.b $1B : BEQ .floor_ok
    LDA.w SprFloor, Y : CMP.b $EE : BEQ .floor_ok
      JMP .next
  .floor_ok
  ; Within 20 px of (WaveX, WaveY)?
  REP #$20
  LDA.w SprX, Y : AND.w #$00FF : STA.b $00
  LDA.w SprXH, Y : XBA : AND.w #$FF00 : ORA.b $00
  CLC : ADC.w #$0008 : SEC : SBC.w !GustJarWaveXL
  BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0014 : BCC +
    JMP .next16
  +
  LDA.w SprY, Y : AND.w #$00FF : STA.b $00
  LDA.w SprYH, Y : XBA : AND.w #$FF00 : ORA.b $00
  CLC : ADC.w #$0008 : SEC : SBC.w !GustJarWaveYL
  BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0014 : BCC +
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
    LDA.b #$02 : STA.b $07
    JSR GustJar_PushSpriteAlongDir
    STZ.w $0642
    BRA .next
  .not_statue
  CMP.b #Sprite_IceBlock : BNE .not_ice
    LDA.b #$02 : STA.b $07
    JSR GustJar_PushSpriteAlongDir
    STZ.w $0642
    BRA .next
  .not_ice

  ; 3. Normal/Light Enemy -> knockback recoil + brief stun!
  JSR GustJar_IsPullableEnemy : BCC .next
  LDA.w !GustJarDir : LSR A : TAX
  LDA.w !GustJarTier : DEC A : ASL #2 : STA.b $00
  TXA : CLC : ADC.b $00 : TAX
  LDA.w .kb_x, X : STA.w SprXRecoil, Y
  LDA.w .kb_y, X : STA.w SprYRecoil, Y
  LDX.w !GustJarTier
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
  .kb_x
  db $00, $00, $D8, $28 ; Tier 1 (+/- $28)
  db $00, $00, $C8, $38 ; Tier 2 (+/- $38)
  db $00, $00, $B8, $48 ; Tier 3 (+/- $48)
  .kb_y
  db $D8, $28, $00, $00
  db $C8, $38, $00, $00
  db $B8, $48, $00, $00
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
  CMP.b #$07 : BEQ .bomb
  CMP.b #$2C : BNE .next_near
  LDA.w $0380, X : BNE .next_near
  BRA .chk_dist
  .bomb
  LDA.w $0C5E, X : BNE .next_near
  LDA.w $0380, X : BEQ .chk_dist
  .next_near
  JMP .next

  .chk_dist
  REP #$20
  LDA.w $0C04, X : AND.w #$00FF : STA.b $00
  LDA.w $0C18, X : XBA : AND.w #$FF00 : ORA.b $00
  STA.b $00
  SEC : SBC.w !GustJarWaveXL : BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0014 : BCS .next16
  LDA.w $0BFA, X : AND.w #$00FF : STA.b $02
  LDA.w $0C0E, X : XBA : AND.w #$FF00 : ORA.b $02
  STA.b $02
  SEC : SBC.w !GustJarWaveYL : BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0014 : BCS .next16
  SEP #$20

  ; Push forward!
  LDA.w $0C4A, X : CMP.b #$07 : BNE .push_somaria
    JSR GustJar_ApplyAncillaBlastVel
    BRA .chk_portal
  .push_somaria
    LDA.w !GustJarTier : INC A : STA.b $07 ; 2/3/4 px/frame
    LDA.w !GustJarDir : JSR GustJar_StepAncillaDir
    LDA.w $0C04, X : STA.b $00 : LDA.w $0C18, X : STA.b $01
    LDA.w $0BFA, X : STA.b $02 : LDA.w $0C0E, X : STA.b $03

  .chk_portal
  JSR GustJar_FindPortalExit : BCC .next
    LDA.b $04 : STA.w $0C04, X : LDA.b $05 : STA.w $0C18, X
    LDA.b $06 : STA.w $0BFA, X : LDA.b $07 : STA.w $0C0E, X
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
  REP #$20
  LDA.w SprX, Y : AND.w #$00FF : STA.b $04
  LDA.w SprXH, Y : XBA : AND.w #$FF00 : ORA.b $04
  SEC : SBC.b $00 : BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0010 : BCC +
    JMP .next16
  +
  LDA.w SprY, Y : AND.w #$00FF : STA.b $06
  LDA.w SprYH, Y : XBA : AND.w #$FF00 : ORA.b $06
  SEC : SBC.b $02 : BPL + : EOR.w #$FFFF : INC A : +
  CMP.w #$0010 : BCC +
    JMP .next16
  +
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
  LDA.w SprSubtype, Y : CMP.b #$02 : BNE .exit_orange
    ; Exit +16 px right of Blue portal.
    LDA.w SprX, Y : CLC : ADC.b #$10 : STA.b $04
    LDA.w SprXH, Y : ADC.b #$00 : STA.b $05
    LDA.w SprY, Y : STA.b $06
    LDA.w SprYH, Y : STA.b $07
    PLY : SEC : RTS
  .exit_orange
    ; Exit +16 px below Orange portal.
    LDA.w SprX, Y : STA.b $04
    LDA.w SprXH, Y : STA.b $05
    LDA.w SprY, Y : CLC : ADC.b #$10 : STA.b $06
    LDA.w SprYH, Y : ADC.b #$00 : STA.b $07
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

; ---------------------------------------------------------
; Swirling Wind-Suction OAM FX (3/4/5 puffs rushing inward into nozzle).
; Uses Region D ($0DBA8C) and always-resident OBJ page-0 puff tiles ($CF/$DF).
; ---------------------------------------------------------
GustJar_DrawInhaleOAM:
{
  ; Count = Tier + 2 (3, 4, or 5 puffs); allocate Count * 4 bytes.
  LDA.w !GustJarTier : CLC : ADC.b #$02 : STA.b $04
  ASL #2
  JSL !GustJarOamAllocD

  LDY.b #$00 ; OAM low offset
  LDX.b #$00 ; particle index
  .part
  ; Progress t = (31 - ((frame*3 + idx*7) & 31)) * tier_scale -> rushes INWARD!
  LDA.b $1A : ASL A : CLC : ADC.b $1A : STA.b $00
  TXA : ASL #3 : CLC : ADC.b $00 : AND.b #$1F
  EOR.b #$1F : STA.b $05 ; 31 -> 0 inward!
  LDA.w !GustJarTier : CMP.b #$02 : BCC .dist_ok
    ASL.b $05 ; up to 62 px at Tier 2/3
  .dist_ok
  ; Swirl perpendicular offset from sine-like 8-entry table.
  LDA.b $1A : LSR A : CLC : ADC.b $05 : AND.b #$07 : PHX : TAX
  LDA.w .swirl, X : PLX : STA.b $06

  ; Base screen coords of nozzle ($08-$E2, $0A-$E8).
  LDA.b $08 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $0A : SEC : SBC.b $E8 : STA.b $01
  LDA.w !GustJarDir
  BEQ .p_u
  CMP.b #$02 : BEQ .p_d
  CMP.b #$04 : BEQ .p_l
  ; Right: X += dist, Y += swirl (hide if X wraps past 255)
  LDA.b $00 : CLC : ADC.b $05 : STA.b $00 : BCS .offscreen
  LDA.b $01 : CLC : ADC.b $06 : STA.b $01
  BRA .emit
  .p_l
  ; Left: X -= dist, Y += swirl (hide if X underflows below 0)
  LDA.b $00 : SEC : SBC.b $05 : STA.b $00 : BCC .offscreen
  LDA.b $01 : CLC : ADC.b $06 : STA.b $01
  BRA .emit
  .p_d
  ; Down: Y += dist, X += swirl
  LDA.b $01 : CLC : ADC.b $05 : STA.b $01 : BCS .offscreen
  LDA.b $00 : CLC : ADC.b $06 : STA.b $00
  BRA .emit
  .p_u
  ; Up: Y -= dist, X += swirl
  LDA.b $01 : SEC : SBC.b $05 : STA.b $01 : BCC .offscreen
  LDA.b $00 : CLC : ADC.b $06 : STA.b $00
  BRA .emit
  .offscreen
  LDA.b #$F0 : STA.b $01

  .emit
  LDA.b $00 : STA.b ($90), Y : INY
  LDA.b $01 : STA.b ($90), Y : INY
  TXA : EOR.b $1A : AND.b #$02 : BEQ .tile_a
    LDA.b #$DF : BRA .tile_b
  .tile_a
    LDA.b #$CF
  .tile_b
  STA.b ($90), Y : INY
  LDA.b $1A : AND.b #$04 : ASL #4 : ORA.b #$22 ; prio 2, pal 1, flip flutter
  STA.b ($90), Y : INY

  PHX : TXY : LDA.b #$00 : STA.b ($92), Y
  TYA : INC A : ASL #2 : TAY : PLX
  INX : CPX.b $04 : BCS .done
  JMP .part
  .done
  RTS

  .swirl : db 0, 5, 7, 5, 0, -5, -7, -5
}

; ---------------------------------------------------------
; Gust Blast Wave Crescent OAM FX (3 puffs around WaveX/WaveY).
; ---------------------------------------------------------
GustJar_DrawWaveOAM:
{
  LDA.w !GustJarWaveXL : SEC : SBC.b $E2 : STA.b $00
  LDA.w !GustJarWaveYL : SEC : SBC.b $E8 : STA.b $01
  CMP.b #$E0 : BCS .skip

  LDA.b #$0C ; 3 OAM sprites
  JSL !GustJarOamAllocD
  LDX.b #$00
  LDY.b #$00
  .loop
  LDA.w !GustJarDir : CMP.b #$04 : BCS .vert_spread
    ; Up/Down wave -> spread along X (-8, 0, +8)
    LDA.b $00 : CLC : ADC.w .spread, X : STA.b ($90), Y : INY
    LDA.b $01 : STA.b ($90), Y : INY
    BRA .tile
  .vert_spread
    ; Left/Right wave -> spread along Y (-8, 0, +8)
    LDA.b $00 : STA.b ($90), Y : INY
    LDA.b $01 : CLC : ADC.w .spread, X : STA.b ($90), Y : INY
  .tile
  LDA.b #$CF : CPX.b #$01 : BNE + : LDA.b #$A9 : +
  STA.b ($90), Y : INY
  LDA.b $1A : AND.b #$02 : ASL #5 : ORA.b #$24 ; prio 2, pal 2
  STA.b ($90), Y : INY
  PHX : TXY : LDA.b #$00 : STA.b ($92), Y
  TYA : INC A : ASL #2 : TAY : PLX
  INX : CPX.b #$03 : BCC .loop
  .skip
  RTS
  .spread : db -8, 0, 8
}

GustJar_CodeEnd:
print "End of Items/gust_jar.asm         ", pc
assert pc() <= $3A0000, "Items/gust_jar.asm exceeded Bank $39 tail ($39F000-$39FFFF)"
pullpc
