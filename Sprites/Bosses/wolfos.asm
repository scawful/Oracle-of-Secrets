; =========================================================
; Wolfos & Ice Wolfos Sprite ($A9)
;
; 3-Variant Hierarchy (auto-detected in Prep or selected via SprSubtype):
;   Variant 1 — Standard Enemy Wolfos (Oracle Cobalt Blue / Royal Indigo, Pal 5):
;     - Default combat Wolfos outside Kalyxo Castle ($0B, $1A..$1C) & Snowpeak ($03..$07)
;       and in all indoor/dungeon rooms other than Wolfos Cave ($0120).
;     - 30 HP, 1 heart contact damage, normal death & prize drop (never despawns on WolfMask).
;     - Explicit override: SprSubtype = $03.
;   Variant 2 — Castle Mask-Quest Wolfos (Steel-Grey / Gold, Pal 5 — matches Wolf Mask $CC):
;     - Auto-detected on Kalyxo Castle ($0B) & Castle Quest areas ($1A..$1C), or SprSubtype = $04.
;     - 30 effective HP (+20 overkill buffer); subdues -> Song of Healing -> Wolf Mask ($7EF358);
;       despawns permanently once WolfMask != 0.
;   Variant 3 — Ice Wolfos (White / Lavender-Ice / Gold-Eyed, Pal 6):
;     - Mount Snowpeak ($03..$07) Outdoors or SprSubtype = $01: Roving Ice Wolfos (36 HP).
;     - Wolfos Cave Room $0120 or SprSubtype = $02: Alpha Ice Wolfos Mini-Boss (48 HP,
;       Frost Enrage at <= 24 HP, dual V-spread 8x8 mouth Frost Shards, opens Room $120 shutter).
;   Child Projectile — SprSubtype = $80:
;     - Compact 8x8 Frost Shard ($88/$89/$98, n=1, Pal 2 icy cyan/blue) spawned directly in
;       front of Ice Wolfos's jaws/mouth; Statis=1, compact hitbox $05, shield-blockable.
;
; Combat Rhythm (OoT / Majora's Mask inspired):
;   Smooth Diagonal Stalk (with obstacle wall-slide) -> Curved Flanking Circle Orbit
;   (tangent + radial spacing spring, instant wall-hit reversal) <-> Frontal Claw Guard
;   (clinks normal frontal sword; bypassed by flanks/back, Spin Attack, Fire Rod, Lamp,
;   Bombs, Boomerang, Hookshot) -> Micro-Coil 4-Dir Telegraph -> Fast Aimed Claw Lunge
;   (+ compact 8x8 mouth Frost Shard on Ice Wolfos) -> Vulnerable Recovery -> Stagger /
;   Wall-Aware Pivot DodgeHop.
;
; Elemental Profile (Ice Wolfos via DMGTABLE $7F6A90):
;   - Weak to Fire Rod / Lamp (16 HP melt!) and Bombos (64 HP)
;   - Immune to Ice Rod and Ether; Arrows deflected; Boomerang/Hookshot stun.
; =========================================================

!SPRID              = Sprite_Wolfos
!NbrTiles           = 03  ; 0-based: 4 OAM tiles max per frame
!Harmless           = 00  ; 00 = Harmful
!HVelocity          = 00
!Health             = 30  ; Base HP ($1E) for Standard Wolfos
!Damage             = 01  ; $08/$04/$02 (1 heart Green / 1/2 Blue / 1/4 Red)
!DeathAnimation     = 00  ; Normal vanilla death poof
!ImperviousAll      = 00
!SmallShadow        = 00
!Shadow             = 00  ; Built-in ground shadow in GameyFireBro art
!Palette            = 00  ; Per-instance palette via SprMiscG ($0A std / $0C ice)
!Hitbox             = 00  ; Standard 16x16 body hitbox
!Persist            = 00
!Statis             = 00  ; Counts toward kill-all-enemies room shutters
!CollisionLayer     = 00
!CanFall            = 00
!DeflectArrow       = 00
!WaterSprite        = 00
!Blockable          = 00
!Prize              = 01  ; Standard prize pack on defeat
!Sound              = 00
!Interaction        = 00
!Statue             = 00
!DeflectProjectiles = 00
!ImperviousArrow    = 01  ; Deflects standard arrows
!ImpervSwordHammer  = 00
!Boss               = 00
%Set_Sprite_Properties(Sprite_Wolfos_Prep, Sprite_Wolfos_Long)

; =========================================================
; Constants & RAM Assignments
; =========================================================

; Variant flags stored in SprMiscA, X ($0DA0,X)
!WolfosFlag_Ice     = $01 ; Ice Wolfos variant (art/palette/frost lunge/fire weakness)
!WolfosFlag_Alpha   = $02 ; Mini-Boss Ice Wolfos (48 HP, enrage phase, dual shards)
!WolfosFlag_Quest   = $04 ; Castle Wolf Mask quest (despawns when WolfMask!=0, subdues)
!WolfosFlag_Enraged = $08 ; Alpha Ice Wolfos Phase 2 (< 50% HP)

; SprMiscB, X ($0DB0,X) bit layout:
;   bit 0 ($01): Circle orbit direction (0 = CW, 1 = CCW)
;   bit 1 ($02): Circle consecutive wall-hit guard (breaks corner stalls cleanly)
;   bit 4 ($10): Subdued dialogue ($023) already shown

; Other Sprite RAM slots:
;   SprMiscC ($0DE0,X): Cached previous HP for hit detection
;   SprMiscD ($0E90,X): Scratch / secondary shard spread mode (0=direct, 1=+V, 2=-V)
;   SprMiscE ($0EB0,X): Facing direction (0=Right, 1=Left, 2=Down, 3=Up)
;   SprMiscF ($0EC0,X): Lunge frost-shard fired flag / hurt scratch
;   SprMiscG ($0ED0,X): Per-instance OAM palette bits ($0A=Pal 5 Blue/Grey, $0C=Pal 6 Ice)
;   SprTimerA ($0DF0,X): Current combat phase timer
;   SprTimerB ($0E00,X): Animation cadence timer
;   SprTimerC ($0E10,X): Attack cooldown timer
;   SprTimerD ($0EE0,X): Guard cooldown (combat) / HealPulse & Brandish hold (quest)
;   SprTimerE ($0F10,X): Telegraph micro-coil / enrage shimmer timer

; AI Action IDs (SprAction, X)
!WolfosAct_Stalk     = $00
!WolfosAct_Circle    = $01
!WolfosAct_Guard     = $02
!WolfosAct_DodgeHop  = $03
!WolfosAct_Telegraph = $04
!WolfosAct_Lunge     = $05
!WolfosAct_Recover   = $06
!WolfosAct_Stagger   = $07
!WolfosAct_Subdued   = $08
!WolfosAct_HealPulse = $09
!WolfosAct_GrantMask = $0A
!WolfosAct_Dismiss   = $0B

; Subtype IDs (SprSubtype, X)
!WolfosSub_Default   = $00 ; Auto-detect from area/room
!WolfosSub_IceRoving = $01 ; Explicit Roving Ice Wolfos (White/Ice, 36 HP)
!WolfosSub_IceAlpha  = $02 ; Explicit Alpha Ice Wolfos (White/Ice, 48 HP, Enrage)
!WolfosSub_StdBlue   = $03 ; Explicit Standard Enemy Wolfos (Oracle Blue, 30 HP)
!WolfosSub_QuestGrey = $04 ; Explicit Castle Mask-Quest Wolfos (Steel-Grey, Wolf Mask)
!WolfosSub_IceShard  = $80 ; Child 8x8 frost shard projectile (bit 7 set)

; Combat Tuning
!Wolfos_StdHP        = $1E ; 30 HP (Blue Standard Enemy Wolfos)
!Wolfos_QuestHP      = $32 ; 50 HP total - 20 HP safety buffer = 30 effective HP
!Wolfos_IceHP        = $24 ; 36 HP (roving Snowpeak Ice Wolfos)
!Wolfos_AlphaHP      = $30 ; 48 HP (Room $120 Ice Rod Guardian / Subtype 2)
!Wolfos_EnrageHP     = $18 ; 24 HP (50% of Alpha)
!Wolfos_SubdueHP     = $15 ; Quest Wolfos subdues when HP < 21 (cannot overkill!)

!Wolfos_StalkSpdStd  = $10
!Wolfos_StalkSpdIce  = $14
!Wolfos_CircleSpdStd = $0F
!Wolfos_CircleSpdIce = $13
!Wolfos_DodgeSpdStd  = $1A
!Wolfos_DodgeSpdIce  = $1E
!Wolfos_LungeSpdStd  = $24
!Wolfos_LungeSpdIce  = $28
!Wolfos_LungeSpdRage = $2C
!Wolfos_CoilSpd      = $06 ; Crisp 1-2px predatory coil-back during opening Telegraph
!Wolfos_ShardSpeed   = $40 ; Significantly faster than lunge so frost shards streak cleanly ahead!

!Wolfos_GuardDur     = $1C ; 28 frames
!Wolfos_DodgeDur     = $12 ; 18 frames
!Wolfos_CoilDur      = $06 ; 6-frame micro-coil at start of Telegraph
!Wolfos_TeleDurStd   = $18 ; 24 frames
!Wolfos_TeleDurIce   = $14 ; 20 frames
!Wolfos_TeleDurRage  = $10 ; 16 frames
!Wolfos_LungeDurStd  = $16 ; 22 frames (identical all 4 dirs)
!Wolfos_LungeDurIce  = $1A ; 26 frames (identical all 4 dirs)
!Wolfos_RecovDurStd  = $22 ; 34 frames punishable window
!Wolfos_RecovDurIce  = $1C ; 28 frames punishable window
!Wolfos_StaggerDur   = $0E ; 14 frames hurt recoil
!Wolfos_HealPulseDur = $50 ; 80 frames Song of Healing shimmer
!Wolfos_BrandishDur  = $3C ; 60 frames Wolf Mask brandish hold

; DMGTABLE row for Sprite_Wolfos ($A9): $7F6000 + ($A9 * 16) = $7F6A90
!Wolfos_DmgTableRow  = $7F6A90

; =========================================================
; Long Entry Point
; =========================================================

Sprite_Wolfos_Long:
{
  PHB : PHK : PLB
  ; Child Ice Shard projectile dispatches before Wolfos body logic.
  LDA.w SprSubtype, X : BMI .ice_shard

  ; Skip body draw during vanilla dying poof (SprState == $06).
  LDA.w SprState, X : CMP.b #$06 : BEQ .dying
    JSR Sprite_Wolfos_Draw
  .dying
  JSL Sprite_CheckActive : BCC .inactive
    JSR Sprite_Wolfos_CheckIfDefeated
    JSR Sprite_Wolfos_Main
  .inactive
  PLB
  RTL

  .ice_shard
  LDA.w SprState, X : CMP.b #$06 : BEQ .shard_dying
    JSR Wolfos_IceShard_Draw
  .shard_dying
  JSL Sprite_CheckActive : BCC .shard_inactive
    JSR Wolfos_IceShard_Main
  .shard_inactive
  PLB
  RTL
}

; =========================================================
; Sprite Prep & Variant Detection
; =========================================================

Sprite_Wolfos_Prep:
{
  PHB : PHK : PLB

  ; Child Ice Shards are configured by their parent spawner.
  LDA.w SprSubtype, X : BPL .body_prep
    PLB
    RTL
  .body_prep

  ; Determine variant flags -> A -> SprMiscA, X
  ; Explicit SprSubtype overrides ($01..$04) skip location auto-detection.
  LDY.w SprSubtype, X
  BEQ .auto_detect
    CPY.b #!WolfosSub_IceRoving : BNE .not_sub1
      LDA.b #!WolfosFlag_Ice : BRA .store_flags
    .not_sub1
    CPY.b #!WolfosSub_IceAlpha : BNE .not_sub2
      LDA.b #(!WolfosFlag_Ice|!WolfosFlag_Alpha) : BRA .store_flags
    .not_sub2
    CPY.b #!WolfosSub_StdBlue : BNE .not_sub3
      LDA.b #$00 : BRA .store_flags
    .not_sub3
    CPY.b #!WolfosSub_QuestGrey : BNE .auto_detect
      LDA.b #!WolfosFlag_Quest : BRA .store_flags

  .auto_detect
  LDA.b #$00
  LDY.b $1B : BNE .check_indoor_room
    ; Outdoors: Mount Snowpeak areas $03..$07 -> Roving Ice Wolfos
    LDY.b $8A
    CPY.b #$03 : BCC .check_castle_quest
    CPY.b #$08 : BCS .check_castle_quest
      LDA.b #!WolfosFlag_Ice
      BRA .store_flags
    .check_castle_quest
    ; Outdoors: Kalyxo Castle ($0B) & Castle Quest Grounds ($1A/$1B/$1C) -> Grey Mask-Quest Wolfos
    CPY.b #$0B : BEQ .is_castle_quest
    CPY.b #$1A : BCC .store_flags
    CPY.b #$1D : BCS .store_flags
    .is_castle_quest
      LDA.b #!WolfosFlag_Quest
      BRA .store_flags

  .check_indoor_room
  ; Indoors: Room $0120 (Wolfos Cave — Ice Rod Guardian) -> Alpha Ice Wolfos!
  LDY.b $A1 : CPY.b #$01 : BNE .store_flags
  LDY.b $A0 : CPY.b #$20 : BNE .store_flags
    LDA.b #(!WolfosFlag_Ice|!WolfosFlag_Alpha)

  .store_flags
  STA.w SprMiscA, X

  ; Bug #1 fix: Quest Wolfos despawns permanently once WolfMask ($7EF358) != 0.
  BIT.b #!WolfosFlag_Quest : BEQ .do_spawn
    LDA.l WolfMask : BEQ .do_spawn
      STZ.w SprState, X
      PLB
      RTL

  .do_spawn
  STZ.w SprAction, X
  STZ.w SprFrame, X
  STZ.w SprMiscB, X
  STZ.w SprMiscD, X
  STZ.w SprMiscF, X
  STZ.w SprTimerB, X
  STZ.w SprTimerD, X
  STZ.w SprTimerE, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprFlash, X

  ; 4 OAM slots (0-based = 3), persist + impervious to arrows, guard bit OFF.
  LDA.b #$03 : STA.w SprNbrOAM, X
  LDA.b #$82 : STA.w SprDefl, X
  LDA.b #$20 : STA.w SprTimerA, X
  LDA.b #$24 : STA.w SprTimerC, X

  ; Configure Ice Wolfos vs Castle Quest Grey Wolfos vs Standard Blue Wolfos.
  LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Ice : BEQ .prep_non_ice
    ; Variant 3: Ice Wolfos (Roving 36 HP / Alpha 48 HP, OAM Pal 6)
    BIT.b #!WolfosFlag_Alpha : BEQ .roving_hp
      LDA.b #!Wolfos_AlphaHP
      BRA .set_ice_hp
    .roving_hp
      LDA.b #!Wolfos_IceHP
    .set_ice_hp
    STA.w SprHealth, X
    STA.w SprMiscC, X
    LDA.b #$03 : STA.w SprBump, X      ; 2 hearts Green / 1 Blue / 1/2 Red
    LDA.b #$0C : STA.w SprMiscG, X     ; OAM Palette 6 (White/Lavender-Ice/Gold)
    JSR Wolfos_ApplyIcePalette
    JSR Wolfos_SetIceDamageTable
    BRA .upload_art

  .prep_non_ice
    LDA.b #$01 : STA.w SprBump, X      ; 1 heart Green / 1/2 Blue / 1/4 Red
    LDA.b #$0A : STA.w SprMiscG, X     ; OAM Palette 5 (Blue Std or Steel-Grey Quest)
    JSR Wolfos_SetStdDamageTable
    LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Quest : BEQ .prep_std_blue
      ; Variant 2: Castle Mask-Quest Wolfos (Steel-Grey / Gold, matches Wolf Mask)
      LDA.b #!Wolfos_QuestHP           ; 30 effective HP + 20 HP overkill buffer
      STA.w SprHealth, X
      STA.w SprMiscC, X
      JSR Wolfos_ApplyQuestPalette
      BRA .upload_art

  .prep_std_blue
    ; Variant 1: Standard Enemy Wolfos (Oracle Cobalt Blue / Royal Indigo)
    LDA.b #!Wolfos_StdHP
    STA.w SprHealth, X
    STA.w SprMiscC, X
    JSR Wolfos_ApplyBluePalette

  .upload_art
  JSR Wolfos_ApplyGraphics
  JSR Wolfos_FacePlayer
  JSR Wolfos_SyncWalkFrame

  PLB
  RTL
}

; =========================================================
; Defeat / Subdue & Alpha Enrage Check
; =========================================================

Sprite_Wolfos_CheckIfDefeated:
{
  LDA.w SprMiscA, X
  BIT.b #!WolfosFlag_Quest : BEQ .check_alpha_enrage

  ; Quest Wolfos: enter Subdued instead of dying when HP drops below 5.
  LDA.w SprAction, X : CMP.b #!WolfosAct_Subdued : BCS .done
    LDA.w SprHealth, X : CMP.b #!Wolfos_SubdueHP : BCS .done
      LDA.b #!WolfosAct_Subdued : STA.w SprAction, X
      LDA.b #$09 : STA.w SprState, X    ; Prevent vanilla death poof
      LDA.b #$40 : STA.w SprHealth, X : STA.w SprMiscC, X
      %SetHarmless(1)
      LDA.w $0E60, X : ORA.b #$40 : STA.w $0E60, X ; ImperviousAll while subdued
      JSR Wolfos_GuardOff
      STZ.w SprXSpeed, X
      STZ.w SprYSpeed, X
      STZ.w SprFlash, X
      LDA.w SprMiscB, X : AND.b #$EF : STA.w SprMiscB, X ; Reset subdued msg bit
      LDA.b #$02 : STA.w SprMiscE, X    ; Face front
      STZ.w SprFrame, X
      LDA.b #$1B : JSL Sound_SetSfx3PanLong ; Subdued chime
      RTS

  .check_alpha_enrage
  BIT.b #!WolfosFlag_Alpha : BEQ .done
  BIT.b #!WolfosFlag_Enraged : BNE .done
    LDA.w SprHealth, X : BEQ .done
    CMP.b #!Wolfos_EnrageHP+1 : BCS .done
      LDA.w SprMiscA, X : ORA.b #!WolfosFlag_Enraged : STA.w SprMiscA, X
      LDA.b #$18 : STA.w SprTimerE, X
      LDA.b #$26 : JSL Sound_SetSfx3PanLong ; Fierce enrage howl
      LDA.b #$0F : JSL Sound_SetSfx2PanLong ; Frost burst chime
      JSR Wolfos_SpawnFrostBurst
  .done
  RTS
}

; =========================================================
; Main State Machine ($00..$0B)
; =========================================================

Sprite_Wolfos_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw Wolfos_Act_Stalk     ; $00 - Approach & read player
  dw Wolfos_Act_Circle    ; $01 - True OoT flank circling
  dw Wolfos_Act_Guard     ; $02 - Frontal claw guard (flank/spin/item bypass)
  dw Wolfos_Act_DodgeHop  ; $03 - Crisp evasive backhop
  dw Wolfos_Act_Telegraph ; $04 - 4-dir crouch/snarl windup telegraph
  dw Wolfos_Act_Lunge     ; $05 - Fast 4-dir claw lunge (+ frost shard on Ice)
  dw Wolfos_Act_Recover   ; $06 - Punishable recovery opening
  dw Wolfos_Act_Stagger   ; $07 - Crisp hurt stagger & counter pivot
  dw Wolfos_Act_Subdued   ; $08 - Castle quest subdued, awaits Song of Healing
  dw Wolfos_Act_HealPulse ; $09 - Song of Healing shimmer & sparkles
  dw Wolfos_Act_GrantMask ; $0A - Wolf Mask brandish hold above Link's hands
  dw Wolfos_Act_Dismiss   ; $0B - Clean finish & despawn
}

; ---------------------------------------------------------
; $00: Stalk — Smooth diagonal prowl with obstacle wall-slide & close-range spacing
; ---------------------------------------------------------
Wolfos_Act_Stalk:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_ProcessCombatDamage : BCS .done
  JSL Sprite_CheckDamageToPlayerSameLayer
  JSR Wolfos_FacePlayerSmooth
  JSR Wolfos_CheckTriggerGuard : BCS .done

  JSR Wolfos_ComputeDeltaToPlayer ; A = clamped Manhattan dist
  CMP.b #$38 : BCS .check_circle
    ; Within lunge reach and cooldown ready -> Telegraph!
    LDA.w SprTimerC, X : BNE .check_too_close
      JSR Wolfos_EnterTelegraph
      RTS

  .check_too_close
  ; If Link crowds inside 28px while cooldown ticks, backhop or circle cleanly!
  CMP.b #$1C : BCS .check_circle
    LDA.w SprTimerA, X : BNE .quick_circle
      JSR Wolfos_EnterDodgeHop
      RTS
    .quick_circle
    LDA.b #$20 : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Circle : STA.w SprAction, X
    RTS

  .check_circle
  CMP.b #$52 : BCS .approach
    LDA.w SprTimerA, X : BNE .approach
      ; Enter curved OoT flank Circle with random orbit direction
      JSL GetRandomInt : AND.b #$01 : STA.b $0E
      LDA.w SprMiscB, X : AND.b #$FC : ORA.b $0E : STA.w SprMiscB, X
      LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Ice : BNE .ice_circ_dur
        LDA.b #$2E : BRA .set_circ
      .ice_circ_dur
        LDA.b #$26
      .set_circ
      STA.w SprTimerA, X
      LDA.b #!WolfosAct_Circle : STA.w SprAction, X
      RTS

  .approach
  JSR Wolfos_GetStalkSpeed
  JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_CheckTileCollision : BEQ .stalk_move
    JSR Wolfos_SteerAroundObstacle
  .stalk_move
  JSL Sprite_Move
  JSR Wolfos_AnimateWalk
  .done
  RTS
}

; ---------------------------------------------------------
; $01: Circle — Curved flanking orbit (tangent + radial spacing spring)
;               with instant wall-hit reversal & anti-corner stall
; ---------------------------------------------------------
Wolfos_Act_Circle:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_ProcessCombatDamage : BCC .not_hit
    RTS
  .not_hit
  JSL Sprite_CheckDamageToPlayerSameLayer
  JSR Wolfos_FacePlayerSmooth
  JSR Wolfos_CheckTriggerGuard : BCC .no_guard
    RTS
  .no_guard

  JSR Wolfos_ComputeDeltaToPlayer ; A = clamped Manhattan dist
  STA.b $0C                       ; Pass current dist to ApplyCircleVelocity
  CMP.b #$5C : BCC .in_orbit_range
    ; Link backed off -> resume predatory stalking
    LDA.b #$14 : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Stalk : STA.w SprAction, X
    RTS

  .in_orbit_range
  ; Opportunistic pounce: if cooldown ready & inside sweet range during late beat
  LDA.w SprTimerA, X : BEQ .orbit_done
  CMP.b #$10 : BCS .do_orbit
  LDA.w SprTimerC, X : BNE .do_orbit
  LDA.b $0C : CMP.b #$34 : BCS .do_orbit
    JSR Wolfos_EnterTelegraph
    RTS

  .orbit_done
    ; Orbit beat complete -> lunge if ready, else swap orbit & stalk
    LDA.w SprTimerC, X : BNE .re_stalk
      JSR Wolfos_EnterTelegraph
      RTS
    .re_stalk
    LDA.w SprMiscB, X : EOR.b #$01 : AND.b #$FD : STA.w SprMiscB, X
    LDA.b #$18 : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Stalk : STA.w SprAction, X
    RTS

  .do_orbit
  JSR Wolfos_ApplyCircleVelocity
  JSL Sprite_CheckTileCollision : BEQ .clear_wall_bit
    ; Wall/cliff hit while orbiting -> flip CW/CCW immediately and recompute!
    LDA.w SprMiscB, X : BIT.b #$02 : BNE .corner_break
      EOR.b #$01 : ORA.b #$02 : STA.w SprMiscB, X
      JSR Wolfos_ApplyCircleVelocity
      JSL Sprite_Move
      JSR Wolfos_AnimateWalk
      RTS
    .corner_break
    ; Blocked on both arcs (tight corner) -> break into lunge or stalk pivot!
    AND.b #$FD : EOR.b #$01 : STA.w SprMiscB, X
    LDA.w SprTimerC, X : BNE .corner_to_stalk
      JSR Wolfos_EnterTelegraph
      RTS
    .corner_to_stalk
    LDA.b #$12 : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Stalk : STA.w SprAction, X
    RTS

  .clear_wall_bit
  LDA.w SprMiscB, X : AND.b #$FD : STA.w SprMiscB, X
  JSL Sprite_Move
  JSR Wolfos_AnimateWalk
  .done
  RTS
}

; ---------------------------------------------------------
; $02: Guard — Frontal claw guard against normal sword swings.
;      Immediately drops guard if Link flanks/backstabs or uses Spin Attack!
; ---------------------------------------------------------
Wolfos_Act_Guard:
{
  ; Spin Attack ($3C high nibble != 0) shatters guard!
  LDA.b $3C : AND.b #$F0 : BNE .drop_guard
  ; Only guard when Link is in the 90-deg frontal cone!
  JSR Wolfos_IsLinkInFront : BCC .drop_guard
    JSR Wolfos_GuardOn
    BRA .check_damage
  .drop_guard
    JSR Wolfos_GuardOff

  .check_damage
  JSR Wolfos_ProcessCombatDamage : BCS .done
  JSL Sprite_PlayerCantPassThrough
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  JSR Wolfos_SetGuardFrame

  LDA.w SprTimerA, X : BNE .done
    ; Guard beat finished -> release guard, set guard cooldown, counter or hop!
    JSR Wolfos_GuardOff
    LDA.b #$22 : STA.w SprTimerD, X
    JSR Wolfos_ComputeDeltaToPlayer
    CMP.b #$3C : BCS .back_to_stalk
      JSL GetRandomInt : AND.b #$01 : BNE .counter_lunge
        JSR Wolfos_EnterDodgeHop
        RTS
      .counter_lunge
        JSR Wolfos_EnterTelegraph
        RTS
    .back_to_stalk
    LDA.b #$1C : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Stalk : STA.w SprAction, X
  .done
  RTS
}

; ---------------------------------------------------------
; $03: DodgeHop — Crisp evasive backhop with lateral wall-pivot
; ---------------------------------------------------------
Wolfos_Act_DodgeHop:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_ProcessCombatDamage : BCS .done
  JSL Sprite_PlayerCantPassThrough
  JSL Sprite_CheckTileCollision : BEQ .hop_move
    ; Back hit a wall/cliff -> pivot 90 deg laterally around Link instead of grinding!
    LDA.w SprMiscB, X : EOR.b #$01 : STA.w SprMiscB, X
    AND.b #$01 : BNE .pivot_ccw
      LDA.w SprXSpeed, X : PHA
      LDA.w SprYSpeed, X : STA.w SprXSpeed, X
      PLA : EOR.b #$FF : INC A : STA.w SprYSpeed, X
      BRA .hop_move
    .pivot_ccw
      LDA.w SprXSpeed, X : PHA
      LDA.w SprYSpeed, X : EOR.b #$FF : INC A : STA.w SprXSpeed, X
      PLA : STA.w SprYSpeed, X
  .hop_move
  JSL Sprite_Move
  JSR Wolfos_FacePlayer
  JSR Wolfos_SetGuardFrame

  LDA.w SprTimerA, X : BNE .done
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    LDA.w SprTimerC, X : BNE .to_circle
      JSR Wolfos_ComputeDeltaToPlayer
      CMP.b #$48 : BCS .to_circle
        JSR Wolfos_EnterTelegraph
        RTS
    .to_circle
    LDA.b #$24 : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Circle : STA.w SprAction, X
  .done
  RTS
}

; ---------------------------------------------------------
; $04: Telegraph — Predatory micro-coil crouch/snarl windup before Lunge
; ---------------------------------------------------------
Wolfos_Act_Telegraph:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_ProcessCombatDamage : BCS .done
  JSL Sprite_CheckDamageToPlayerSameLayer

  ; First 6 frames (SprTimerE > 0): subtle 1-2px coil-back & live tracking!
  LDA.w SprTimerE, X : BEQ .coil_locked
    JSR Wolfos_FacePlayer
    JSL Sprite_CheckTileCollision : BNE .coil_locked
      JSL Sprite_Move
      BRA .tele_pose
  .coil_locked
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X

  .tele_pose
  JSR Wolfos_SetTelegraphFrame

  ; Readable telegraph pulse flash (safe: never clobbers real hurt flash)
  LDA.w SprDeath, X : BNE .keep_hurt_flash
    LDA.w SprTimerA, X : AND.b #$02 : ASL A : STA.w SprFlash, X
  .keep_hurt_flash

  LDA.w SprTimerA, X : BNE .done
    STZ.w SprFlash, X
    JSR Wolfos_StartLunge
  .done
  RTS
}

; ---------------------------------------------------------
; $05: Lunge — Aimed high-speed claw dash (+ 8x8 mouth Frost Shard on Ice Wolfos)
; ---------------------------------------------------------
Wolfos_Act_Lunge:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_ProcessCombatDamage : BCS .done
  JSL Sprite_CheckDamageToPlayerSameLayer
  JSR Wolfos_SetLungeFrame

  ; Smooth landing deceleration on final 4 frames of lunge
  LDA.w SprTimerA, X : CMP.b #$04 : BNE .check_trail
    LDA.w SprXSpeed, X : CMP.b #$80 : ROR A : STA.w SprXSpeed, X
    LDA.w SprYSpeed, X : CMP.b #$80 : ROR A : STA.w SprYSpeed, X

  .check_trail
  ; Periodic dash dust (Standard/Quest) or frost mist trail (Ice Wolfos)
  LDA.w SprTimerA, X : AND.b #$03 : CMP.b #$02 : BNE .move_lunge
    LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Ice : BNE .frost_trail
      LDA.b #$10 : STA.b $08
      LDA.b #$03 : STA.b $09
      LDA.b #$14 : JSL BossKit_FxAtSprite ; KakKidDashDust
      BRA .move_lunge
    .frost_trail
      LDA.b #$1C : STA.b $08
      LDA.b #$04 : STA.b $09
      LDA.b #$05 : JSL BossKit_FxAtSprite ; SimpleSparkle frost mist
  .move_lunge

  JSL Sprite_CheckTileCollision : BNE .end_lunge
  JSL Sprite_Move

  LDA.w SprTimerA, X : BNE .done
  .end_lunge
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    JSR Wolfos_GuardOff
    LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Ice : BNE .ice_recov
      LDA.b #!Wolfos_RecovDurStd : BRA .set_recov
    .ice_recov
      LDA.b #!Wolfos_RecovDurIce
    .set_recov
    STA.w SprTimerA, X
    LDA.b #!WolfosAct_Recover : STA.w SprAction, X
  .done
  RTS
}

; ---------------------------------------------------------
; $06: Recover — Clean vulnerable counterattack window after Lunge
; ---------------------------------------------------------
Wolfos_Act_Recover:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_ProcessCombatDamage : BCS .done
  JSL Sprite_PlayerCantPassThrough
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  JSR Wolfos_SetRecoverFrame

  LDA.w SprTimerA, X : BNE .done
    ; Set attack cooldown (faster when enraged Alpha Ice Wolfos)
    LDA.w SprMiscA, X
    BIT.b #!WolfosFlag_Enraged : BNE .rage_cd
    BIT.b #!WolfosFlag_Ice : BNE .ice_cd
      LDA.b #$28 : BRA .set_cd
    .ice_cd
      LDA.b #$1C : BRA .set_cd
    .rage_cd
      LDA.b #$14
    .set_cd
    STA.w SprTimerC, X
    LDA.w SprMiscB, X : EOR.b #$01 : STA.w SprMiscB, X
    LDA.b #$24 : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Circle : STA.w SprAction, X
  .done
  RTS
}

; ---------------------------------------------------------
; $07: Stagger — Crisp hurt recoil reaction, then hop or circle
; ---------------------------------------------------------
Wolfos_Act_Stagger:
{
  JSR Wolfos_GuardOff
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckIfRecoiling
  JSL Sprite_BounceFromTileCollision
  JSL Sprite_Move
  JSL Sprite_PlayerCantPassThrough
  LDA.w SprHealth, X : STA.w SprMiscC, X

  LDA.w SprTimerA, X : BNE .done
    JSL GetRandomInt : AND.b #$01 : BNE .hop_out
      LDA.b #$20 : STA.w SprTimerA, X
      LDA.b #!WolfosAct_Circle : STA.w SprAction, X
      RTS
    .hop_out
      JSR Wolfos_EnterDodgeHop
  .done
  RTS
}

; ---------------------------------------------------------
; $08: Subdued — Castle Quest Wolfos subdued; awaits Song of Healing
; ---------------------------------------------------------
Wolfos_Act_Subdued:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprFrame, X
  JSL Sprite_PlayerCantPassThrough

  ; Gentle spirit sparkle cue while waiting to be healed
  LDA.b $1A : AND.b #$0F : BNE .check_msg
    LDA.b #$18 : STA.b $08
    LDA.b #$02 : STA.b $09
    LDA.b #$05 : JSL BossKit_FxAtSprite
  .check_msg

  ; Show subdued message $023 once automatically; re-readable with A.
  LDA.w SprMiscB, X : BIT.b #$10 : BNE .solicited
    %ShowUnconditionalMessage($23)
    LDA.w SprMiscB, X : ORA.b #$10 : STA.w SprMiscB, X
    BRA .check_song
  .solicited
    %ShowSolicitedMessage($23)

  .check_song
  ; Only Song of Healing ($01) heals the Wolfos soul!
  LDA.b SongFlag : CMP.b #$01 : BNE .done
    STZ.b SongFlag
if !ENABLE_OCARINA_SONG_TINT == 1
    LDA.b #!SongTint_Healing : JSL SongTint_Start
endif
    %PreventPlayerMovement()
    LDA.b #$31 : JSL Sound_SetSfx2PanLong ; Fairy healing chime
    LDA.b #!Wolfos_HealPulseDur : STA.w SprTimerD, X
    LDA.b #!WolfosAct_HealPulse : STA.w SprAction, X
  .done
  RTS
}

; ---------------------------------------------------------
; $09: HealPulse — Dramatic healing glow & rising sparkles before Wolf Mask
; ---------------------------------------------------------
Wolfos_Act_HealPulse:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprFrame, X

  ; Shimmer Wolfos during healing pulse
  LDA.w SprTimerD, X : LSR A : LSR A : AND.b #$03 : STA.w SprFlash, X

  ; Spawn rising healing sparkles every 8 frames
  LDA.w SprTimerD, X : AND.b #$07 : BNE .wait_pulse
    JSL GetRandomInt : AND.b #$0F : SEC : SBC.b #$08 : STA.b $00
    LDA.b #$F8 : STA.b $01
    LDA.b #$1A : STA.b $08
    LDA.b #$04 : STA.b $09
    LDA.b #$12 : JSL BossKit_FxAtOffset ; Garnish12_Sparkle
  .wait_pulse

  LDA.w SprTimerD, X : BNE .done
    STZ.w SprFlash, X
    ; Place Wolf Mask cleanly above Link's raised hands (16-bit safe borrow!)
    LDA.w POSX : STA.w SprX, X
    LDA.w POSXH : STA.w SprXH, X
    LDA.w POSY : SEC : SBC.b #$10 : STA.w SprY, X
    LDA.w POSYH : SBC.b #$00 : STA.w SprYH, X

    LDA.b #16 : STA.w SprFrame, X
    LDA.b #$01 : STA.w BRANDISH
    LDA.b #$01 : STA.l WolfMask
    LDA.b #$0F : JSL Sound_SetSfx3PanLong ; Classic item fanfare
    %ShowUnconditionalMessage($10F)
    LDA.b #!Wolfos_BrandishDur : STA.w SprTimerD, X
    LDA.b #!WolfosAct_GrantMask : STA.w SprAction, X
  .done
  RTS
}

; ---------------------------------------------------------
; $0A: GrantMask — Hold Wolf Mask brandish cleanly above Link's hands
; ---------------------------------------------------------
Wolfos_Act_GrantMask:
{
  LDA.b #16 : STA.w SprFrame, X
  LDA.b #$01 : STA.w BRANDISH

  ; Keep mask aligned above Link and emit celebratory sparkle
  LDA.w SprTimerD, X : AND.b #$0F : BNE .wait_hold
    LDA.b #$16 : STA.b $08
    LDA.b #$03 : STA.b $09
    LDA.b #$05 : JSL BossKit_FxAtSprite
  .wait_hold

  LDA.w SprTimerD, X : BNE .done
    LDA.b #!WolfosAct_Dismiss : STA.w SprAction, X
  .done
  RTS
}

; ---------------------------------------------------------
; $0B: Dismiss — Clear brandish, restore player control, despawn cleanly
; ---------------------------------------------------------
Wolfos_Act_Dismiss:
{
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w BRANDISH
  %AllowPlayerMovement()
  LDA.b #$18 : STA.b $08
  LDA.b #$04 : STA.b $09
  LDA.b #$12 : JSL BossKit_FxAtSprite
  STZ.w SprState, X
  STZ.w SprAction, X
  STZ.w SprHealth, X
  RTS
}

; =========================================================
; Combat Transition & Helper Routines
; =========================================================

; Explicit Guard bit control on SprDefl, X ($0CAA,X bit 2 = ImpervSwordHammer).
; Replaces buggy %SetImpervious(0) macro which did EOR #$00 (no-op!).
Wolfos_GuardOn:
{
  LDA.w SprDefl, X : ORA.b #$04 : STA.w SprDefl, X
  RTS
}

Wolfos_GuardOff:
{
  LDA.w SprDefl, X : AND.b #$FB : STA.w SprDefl, X
  RTS
}

; Check if Link is swinging a normal sword in front of Wolfos -> enter Guard.
; Out: Carry SET if transitioned to Guard, Carry CLEAR otherwise.
Wolfos_CheckTriggerGuard:
{
  LDA.w SprTimerD, X : BNE .no_guard  ; Guard cooldown active
  LDA.b $3C : BEQ .no_guard           ; Not swinging
  BIT.b #$F0 : BNE .no_guard          ; Spin attack breaks guard!
  CMP.b #$09 : BCS .no_guard          ; Only active swing frames 1..8
  JSR Wolfos_IsLinkInFront : BCC .no_guard
    JSR Wolfos_GuardOn
    STZ.w SprXSpeed, X
    STZ.w SprYSpeed, X
    LDA.b #!Wolfos_GuardDur : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Guard : STA.w SprAction, X
    JSR Wolfos_SetGuardFrame
    LDA.b #$05 : JSL Sound_SetSfx2PanLong ; Guard raise clink
    SEC
    RTS
  .no_guard
  CLC
  RTS
}

; Enter Telegraph state with subtle 6-frame predator micro-coil backstep
Wolfos_EnterTelegraph:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_FacePlayer
  ; Compute subtle slow coil-back velocity away from Link (~1-2px recoil crouch)
  LDA.b #!Wolfos_CoilSpd : JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_InvertSpeed_XY
  LDA.b #!Wolfos_CoilDur : STA.w SprTimerE, X

  LDA.w SprMiscA, X
  BIT.b #!WolfosFlag_Enraged : BNE .rage_tele
  BIT.b #!WolfosFlag_Ice : BNE .ice_tele
    LDA.b #!Wolfos_TeleDurStd : STA.w SprTimerA, X
    LDA.b #$04 : JSL Sound_SetSfx3PanLong ; Fierce Wolfos snarl
    BRA .set_tele
  .ice_tele
    LDA.b #!Wolfos_TeleDurIce : STA.w SprTimerA, X
    LDA.b #$0F : JSL Sound_SetSfx2PanLong ; Crisp frost charge chime
    JSR Wolfos_SpawnFrostBurst
    BRA .set_tele
  .rage_tele
    LDA.b #!Wolfos_TeleDurRage : STA.w SprTimerA, X
    LDA.b #$0F : JSL Sound_SetSfx2PanLong
    JSR Wolfos_SpawnFrostBurst
  .set_tele
  LDA.b #!WolfosAct_Telegraph : STA.w SprAction, X
  JSR Wolfos_SetTelegraphFrame
  RTS
}

; Launch symmetric 4-dir Lunge (+ compact 8x8 mouth Frost Shards for Ice Wolfos!)
Wolfos_StartLunge:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_FacePlayer

  ; Pick lunge speed and identical 4-direction duration
  LDA.w SprMiscA, X
  BIT.b #!WolfosFlag_Enraged : BNE .rage_lunge
  BIT.b #!WolfosFlag_Ice : BNE .ice_lunge
    LDA.b #!Wolfos_LungeDurStd : STA.w SprTimerA, X
    LDA.b #!Wolfos_LungeSpdStd
    BRA .apply_lunge_vel
  .ice_lunge
    LDA.b #!Wolfos_LungeDurIce : STA.w SprTimerA, X
    LDA.b #!Wolfos_LungeSpdIce
    BRA .apply_lunge_vel
  .rage_lunge
    LDA.b #!Wolfos_LungeDurIce : STA.w SprTimerA, X
    LDA.b #!Wolfos_LungeSpdRage

  .apply_lunge_vel
  ; Aim smoothly toward Link (diagonal or cardinal) at high lunge speed
  JSL Sprite_ApplySpeedTowardsPlayer
  LDA.b #$06 : JSL Sound_SetSfx3PanLong ; Claw lunge swoosh!

  ; Ice Wolfos fires compact 8x8 Frost Shard directly from its jaws!
  ; Phase 1: 1 direct aimed shard; Enraged Alpha Phase 2: 2 symmetric V-spread shards!
  LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Ice : BEQ .set_lunge_act
    BIT.b #!WolfosFlag_Enraged : BNE .rage_dual_shards
      LDA.b #$00 : JSR Wolfos_SpawnIceShard ; Phase 1: direct aimed mouth shard
      BRA .set_lunge_act
    .rage_dual_shards
      LDA.b #$01 : JSR Wolfos_SpawnIceShard ; Phase 2 Enraged: +angle V-spread shard
      LDA.b #$02 : JSR Wolfos_SpawnIceShard ; Phase 2 Enraged: -angle V-spread shard

  .set_lunge_act
  LDA.b #!WolfosAct_Lunge : STA.w SprAction, X
  JSR Wolfos_SetLungeFrame
  RTS
}

; Enter crisp Dodge Backhop away from Link (fixes stale A=$02 speed bug!)
Wolfos_EnterDodgeHop:
{
  JSR Wolfos_GuardOff
  JSR Wolfos_FacePlayer
  LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Ice : BNE .ice_dodge
    LDA.b #!Wolfos_DodgeSpdStd : BRA .set_dodge_spd
  .ice_dodge
    LDA.b #!Wolfos_DodgeSpdIce
  .set_dodge_spd
  JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_InvertSpeed_XY ; Hop AWAY from Link at full dodge speed!
  LDA.b #!Wolfos_DodgeDur : STA.w SprTimerA, X
  LDA.b #!WolfosAct_DodgeHop : STA.w SprAction, X
  LDA.b #$13 : JSL Sound_SetSfx3PanLong ; Crisp leap SFX
  ; Dust/frost puff at takeoff
  LDA.b #$12 : STA.b $08
  LDA.b #$03 : STA.b $09
  LDA.b #$14 : JSL BossKit_FxAtSprite
  RTS
}

; Process player damage & detect any HP drop (swords, spin, bombs, Fire Rod, Lamp).
; Out: Carry SET if state transitioned (to Stagger or Subdued), Carry CLEAR otherwise.
Wolfos_ProcessCombatDamage:
{
  JSL Sprite_DamageFlash_Long
  JSL Sprite_CheckIfRecoiling
  JSL Sprite_CheckDamageFromPlayer

  ; Check if Quest Wolfos just hit subdue threshold
  LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Quest : BEQ .check_hp_drop
    LDA.w SprHealth, X : CMP.b #!Wolfos_SubdueHP : BCS .check_hp_drop
      JSR Sprite_Wolfos_CheckIfDefeated
      SEC
      RTS

  .check_hp_drop
  LDA.w SprHealth, X : CMP.w SprMiscC, X : BCS .no_hit
    ; Compute damage dealt = prev_hp - new_hp
    LDA.w SprMiscC, X : SEC : SBC.w SprHealth, X : STA.b $0E
    LDA.w SprHealth, X : STA.w SprMiscC, X

    ; Massive elemental hit (>= 12 HP -> Fire Rod / Lamp / Bombos melt!)
    LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Ice : BEQ .check_alive
    LDA.b $0E : CMP.b #$0C : BCC .check_alive
      JSR Wolfos_SpawnFrostBurst
      LDA.b #$21 : JSL Sound_SetSfx3PanLong ; Heavy boss-hit crunch

    .check_alive
    ; Preserve vanilla death poof timer ($0DF0) if this hit killed the sprite!
    LDA.w SprState, X : CMP.b #$09 : BNE .killed
    JSR Wolfos_GuardOff
    LDA.b #$1E : STA.w SprTimerD, X ; Brief guard lockout after taking a hit
    LDA.b #!Wolfos_StaggerDur : STA.w SprTimerA, X
    LDA.b #!WolfosAct_Stagger : STA.w SprAction, X
    .killed
    SEC
    RTS

  .no_hit
  CLC
  RTS
}

; =========================================================
; 16-Bit Spatial Math & Circle Orbit Helpers
; =========================================================

; Compute true 16-bit delta from Wolfos to Link (zero 8-bit wrap bug!).
; Out: $00-$01 = signed dx (LinkX - SprX), $02-$03 = signed dy (LinkY - SprY)
;      $04-$05 = |dx|, $06-$07 = |dy|
;      A = clamped 8-bit Manhattan distance ($00..$FF). Keeps X.
Wolfos_ComputeDeltaToPlayer:
{
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  REP #$20
  STA.b $08
  LDA.b $22 : SEC : SBC.b $08 : STA.b $00
  BPL .dx_pos
    EOR.w #$FFFF : INC A
  .dx_pos
  STA.b $04

  SEP #$20
  LDA.w SprYH, X : XBA : LDA.w SprY, X
  REP #$20
  STA.b $08
  LDA.b $20 : SEC : SBC.b $08 : STA.b $02
  BPL .dy_pos
    EOR.w #$FFFF : INC A
  .dy_pos
  STA.b $06

  CLC : ADC.b $04
  CMP.w #$0100 : BCC .fits
    LDA.w #$00FF
  .fits
  SEP #$20
  RTS
}

; Return current Stalk speed in A (faster for Ice & Enraged Alpha).
Wolfos_GetStalkSpeed:
{
  LDA.w SprMiscA, X
  BIT.b #!WolfosFlag_Enraged : BNE .rage
  BIT.b #!WolfosFlag_Ice : BNE .ice
    LDA.b #!Wolfos_StalkSpdStd : RTS
  .ice
    LDA.b #!Wolfos_StalkSpdIce : RTS
  .rage
    LDA.b #!Wolfos_StalkSpdIce+2 : RTS
}

; Update SprMiscE, X with exact 4-way facing toward Link (0=R, 1=L, 2=D, 3=U).
Wolfos_FacePlayer:
{
  JSR Wolfos_ComputeDeltaToPlayer
  REP #$20
  LDA.b $04 : CMP.b $06 : BCC .vertical
    ; Horizontal dominant
    LDA.b $00 : BPL .face_right
      SEP #$20
      LDA.b #$01 : STA.w SprMiscE, X ; Left
      RTS
    .face_right
      SEP #$20
      LDA.b #$00 : STA.w SprMiscE, X ; Right
      RTS
  .vertical
    LDA.b $02 : BPL .face_down
      SEP #$20
      LDA.b #$03 : STA.w SprMiscE, X ; Up
      RTS
    .face_down
      SEP #$20
      LDA.b #$02 : STA.w SprMiscE, X ; Down
      RTS
}

; Anti-jitter facing for continuous movement (Stalk/Circle):
; Uses a 6px hysteresis band so 45-degree diagonal prowling never flickers!
Wolfos_FacePlayerSmooth:
{
  JSR Wolfos_ComputeDeltaToPlayer
  LDA.w SprMiscE, X : CMP.b #$02 : BCS .currently_vert
    ; Currently horizontal -> switch to vertical only if |dy| > |dx| + 6
    REP #$20
    LDA.b $04 : CLC : ADC.w #$0006 : CMP.b $06 : BCC .go_vert
    .go_horiz
      LDA.b $00 : BPL .horiz_right
        SEP #$20 : LDA.b #$01 : STA.w SprMiscE, X : RTS
      .horiz_right
        SEP #$20 : LDA.b #$00 : STA.w SprMiscE, X : RTS
  .currently_vert
    ; Currently vertical -> switch to horizontal only if |dx| > |dy| + 6
    REP #$20
    LDA.b $06 : CLC : ADC.w #$0006 : CMP.b $04 : BCC .go_horiz
    .go_vert
      LDA.b $02 : BPL .vert_down
        SEP #$20 : LDA.b #$03 : STA.w SprMiscE, X : RTS
      .vert_down
        SEP #$20 : LDA.b #$02 : STA.w SprMiscE, X : RTS
}

; Slide smoothly around walls/cliffs while Stalking instead of grinding!
; In: A = collision bitmask from Sprite_CheckTileCollision ($03=H wall, $0C=V wall).
Wolfos_SteerAroundObstacle:
{
  STA.b $0D
  JSR Wolfos_ComputeDeltaToPlayer
  JSR Wolfos_GetStalkSpeed : STA.b $0E

  LDA.b $0D : BIT.b #$03 : BEQ .check_vert_wall
  BIT.b #$0C : BNE .cornered
    ; Horizontal wall hit, vertical axis open -> slide vertically toward Link
    STZ.w SprXSpeed, X
    LDA.b $03 : BMI .slide_up
      LDA.b $0E : STA.w SprYSpeed, X : RTS
    .slide_up
      LDA.b $0E : EOR.b #$FF : INC A : STA.w SprYSpeed, X : RTS

  .check_vert_wall
  LDA.b $0D : BIT.b #$0C : BEQ .cornered
    ; Vertical wall hit, horizontal axis open -> slide horizontally toward Link
    STZ.w SprYSpeed, X
    LDA.b $01 : BMI .slide_left
      LDA.b $0E : STA.w SprXSpeed, X : RTS
    .slide_left
      LDA.b $0E : EOR.b #$FF : INC A : STA.w SprXSpeed, X : RTS

  .cornered
  LDA.w SprMiscB, X : EOR.b #$01 : STA.w SprMiscB, X
  JSL Sprite_BounceFromTileCollision
  RTS
}

; Check if Link is within 56px AND inside the 90-degree frontal cone of SprMiscE.
; Out: Carry SET = in front (guardable), Carry CLEAR = flank/back/far.
Wolfos_IsLinkInFront:
{
  JSR Wolfos_ComputeDeltaToPlayer
  CMP.b #$38 : BCS .not_front ; >= 56px away

  LDA.w SprMiscE, X
  BEQ .check_right
  CMP.b #$01 : BEQ .check_left
  CMP.b #$02 : BEQ .check_down
  ; Up ($03): dy < 0 and |dy| >= |dx|
  REP #$20
  LDA.b $02 : BPL .not_front16
  LDA.b $06 : CMP.b $04 : BCC .not_front16
  SEP #$20 : SEC : RTS

  .check_right ; dx >= 0 and |dx| >= |dy|
  REP #$20
  LDA.b $00 : BMI .not_front16
  LDA.b $04 : CMP.b $06 : BCC .not_front16
  SEP #$20 : SEC : RTS

  .check_left ; dx < 0 and |dx| >= |dy|
  REP #$20
  LDA.b $00 : BPL .not_front16
  LDA.b $04 : CMP.b $06 : BCC .not_front16
  SEP #$20 : SEC : RTS

  .check_down ; dy >= 0 and |dy| >= |dx|
  REP #$20
  LDA.b $02 : BMI .not_front16
  LDA.b $06 : CMP.b $04 : BCC .not_front16
  SEP #$20 : SEC : RTS

  .not_front16
  SEP #$20
  .not_front
  CLC
  RTS
}

; Compute curved flanking orbital velocity around Link (CW/CCW via SprMiscB bit 0).
; Blends tangential orbit with a radial spacing spring (using dist in $0C):
;   - dist >= $3E: +1/2 inward pull (curves smoothly into strike range)
;   - dist <  $24: -1/2 outward push (maintains clean spacing)
;   - sweet spot : +1/4 gentle centripetal pull (true circular arc, no outward drift!)
Wolfos_ApplyCircleVelocity:
{
  LDA.w SprMiscA, X
  BIT.b #!WolfosFlag_Enraged : BNE .rage_cspd
  BIT.b #!WolfosFlag_Ice : BNE .ice_cspd
    LDA.b #!Wolfos_CircleSpdStd : BRA .get_vec
  .ice_cspd
    LDA.b #!Wolfos_CircleSpdIce : BRA .get_vec
  .rage_cspd
    LDA.b #!Wolfos_CircleSpdIce+2
  .get_vec
  JSL Sprite_ApplySpeedTowardsPlayer

  ; Save radial vector (rx, ry) in ($0A, $0B)
  LDA.w SprXSpeed, X : STA.b $0A
  LDA.w SprYSpeed, X : STA.b $0B

  ; Pure tangent (tx, ty) -> ($0D, $0E)
  LDA.w SprMiscB, X : AND.b #$01 : BNE .ccw
    ; CW: tx = ry, ty = -rx
    LDA.b $0B : STA.b $0D
    LDA.b $0A : EOR.b #$FF : INC A : STA.b $0E
    BRA .blend_radial
  .ccw
    ; CCW: tx = -ry, ty = rx
    LDA.b $0B : EOR.b #$FF : INC A : STA.b $0D
    LDA.b $0A : STA.b $0E

  .blend_radial
  LDA.b $0C
  CMP.b #$3E : BCS .pull_in_half
  CMP.b #$24 : BCC .push_out_half
    ; Sweet spot ($24..$3D): +1/4 inward centripetal pull
    LDA.b $0A : CMP.b #$80 : ROR A : CMP.b #$80 : ROR A
    CLC : ADC.b $0D : STA.w SprXSpeed, X
    LDA.b $0B : CMP.b #$80 : ROR A : CMP.b #$80 : ROR A
    CLC : ADC.b $0E : STA.w SprYSpeed, X
    RTS

  .pull_in_half
    ; Too far (>= $3E): +1/2 inward pull
    LDA.b $0A : CMP.b #$80 : ROR A
    CLC : ADC.b $0D : STA.w SprXSpeed, X
    LDA.b $0B : CMP.b #$80 : ROR A
    CLC : ADC.b $0E : STA.w SprYSpeed, X
    RTS

  .push_out_half
    ; Too close (< $24): -1/2 outward push
    LDA.b $0A : CMP.b #$80 : ROR A : STA.b $0F
    LDA.b $0D : SEC : SBC.b $0F : STA.w SprXSpeed, X
    LDA.b $0B : CMP.b #$80 : ROR A : STA.b $0F
    LDA.b $0E : SEC : SBC.b $0F : STA.w SprYSpeed, X
    RTS
}

; =========================================================
; Moonwalk-Free Directional Animation & Pose Sync
; =========================================================

; Snap SprFrame, X into valid walk range for SprMiscE, X (0=R, 1=L, 2=D, 3=U).
Wolfos_SyncWalkFrame:
{
  LDY.w SprMiscE, X
  LDA.w SprFrame, X
  CMP.w .min_frame, Y : BCC .snap
  CMP.w .max_plus1, Y : BCC .ok
  .snap
    LDA.w .min_frame, Y : STA.w SprFrame, X
  .ok
  RTS
  .min_frame : db 6, 9, 0, 3
  .max_plus1 : db 9, 12, 3, 6
}

; Advance walk animation strictly within the current facing's 3-frame range.
Wolfos_AnimateWalk:
{
  JSR Wolfos_SyncWalkFrame
  LDA.w SprTimerB, X : BNE .done
    LDY.w SprMiscE, X
    LDA.w SprFrame, X : INC A
    CMP.w Wolfos_SyncWalkFrame_max_plus1, Y : BCC .store
      LDA.w Wolfos_SyncWalkFrame_min_frame, Y
    .store
    STA.w SprFrame, X
    LDA.w SprMiscA, X : BIT.b #!WolfosFlag_Ice : BNE .fast_anim
      LDA.b #$08 : BRA .set_t
    .fast_anim
      LDA.b #$06
    .set_t
    STA.w SprTimerB, X
  .done
  RTS
}

; Pose helpers indexed by SprMiscE, X (0=Right, 1=Left, 2=Down, 3=Up)
Wolfos_SetGuardFrame:
{
  LDY.w SprMiscE, X
  LDA.w .frames, Y : STA.w SprFrame, X
  RTS
  .frames : db 12, 14, 0, 3
}

Wolfos_SetTelegraphFrame:
{
  LDY.w SprMiscE, X
  LDA.w .frames, Y : STA.w SprFrame, X
  RTS
  .frames : db 12, 14, 1, 4
}

Wolfos_SetLungeFrame:
{
  LDY.w SprMiscE, X
  LDA.w .frames, Y : STA.w SprFrame, X
  RTS
  .frames : db 13, 15, 2, 5
}

Wolfos_SetRecoverFrame:
{
  LDY.w SprMiscE, X
  LDA.w .frames, Y : STA.w SprFrame, X
  RTS
  .frames : db 6, 9, 0, 3
}

; =========================================================
; Ice Wolfos Frost Burst Garnish & Ice Shard Projectile
; =========================================================

; Spawn 4 crisp frost sparkles around Ice Wolfos (telegraph / enrage / melt).
; Note: BossKit_FxAtOffset -> BossKit_SpawnFx clobbers Y with the free garnish
; slot index, so Y MUST be preserved around every call!
Wolfos_SpawnFrostBurst:
{
  PHY
  LDY.b #$03
  .loop
    LDA.w .ox, Y : STA.b $00
    LDA.w .oy, Y : STA.b $01
    LDA.b #$16 : STA.b $08
    LDA.b #$06 : STA.b $09
    PHY
    LDA.b #$05 : JSL BossKit_FxAtOffset ; SimpleSparkle
    PLY
    DEY : BPL .loop
  PLY
  RTS
  .ox : db $F6, $0A, $00, $00
  .oy : db $00, $00, $F4, $0C
}

; Spawn a compact 8x8 Frost Shard directly in front of Ice Wolfos's mouth.
; In: A = 0 (direct aimed), 1 (+angle V-spread), or 2 (-angle V-spread).
Wolfos_SpawnIceShard:
{
  STA.w SprMiscD, X
  LDA.b #Sprite_Wolfos
  JSL Sprite_SpawnDynamically : BPL .got_slot
    RTS
  .got_slot

  ; Explicit child projectile setup (oos-sprite-forge invariant)
  LDA.b #!WolfosSub_IceShard : STA.w SprSubtype, Y
  LDA.b #$00 : STA.w SprAction, Y
  TXA : STA.w SprMiscA, Y              ; Parent Wolfos slot
  LDA.b #$00 : STA.w SprNbrOAM, Y      ; 1 OAM tile (compact 8x8)
  LDA.b #$45 : STA.w SprHitbox, Y      ; Statis=1 (bit 6) + compact 8x4 hitbox $05
  LDA.b #$01 : STA.w SprHealth, Y
  LDA.b #$01 : STA.w SprBump, Y        ; 1 heart Green / 1/2 Blue
  LDA.b #$40 : STA.w $0E60, Y          ; ImperviousAll
  LDA.b #$56 : STA.w SprDefl, Y        ; DeflectProj + ImpervSword/Arrow
  LDA.b #$20 : STA.w SprPrize, Y       ; Blockable by shield!
  LDA.b #$00 : STA.w SprTileDie, Y
  STA.w SprHeight, Y
  LDA.b #$FF : STA.w SprBulletproof, Y
  LDA.b #$3C : STA.w SprTimerA, Y      ; 60-frame lifetime

  ; First place at parent center so aiming is ALWAYS forward (even at point-blank!)
  LDA.w SprX, X : STA.w SprX, Y
  LDA.w SprXH, X : STA.w SprXH, Y
  LDA.w SprY, X : STA.w SprY, Y
  LDA.w SprYH, X : STA.w SprYH, Y

  ; Aim velocity toward Link on the child slot (preserve parent X & child Y!)
  PHX
  PHY
  LDA.w SprMiscD, X : PHA
  TYX
  LDA.b #!Wolfos_ShardSpeed : JSL Sprite_ApplySpeedTowardsPlayer
  PLA : BEQ .aim_done
    ; Enraged Alpha symmetric V-spread (±3/8 perp: ~20.5 deg each side, 41 deg V)
    PHA
    LDA.w SprXSpeed, X : STA.b $00
    LDA.w SprYSpeed, X : STA.b $01
    ; $02 = (vy >> 2) + (vy >> 3)
    LDA.b $01 : CMP.b #$80 : ROR A : CMP.b #$80 : ROR A : STA.b $02
    CMP.b #$80 : ROR A : CLC : ADC.b $02 : STA.b $02
    ; $03 = (vx >> 2) + (vx >> 3)
    LDA.b $00 : CMP.b #$80 : ROR A : CMP.b #$80 : ROR A : STA.b $03
    CMP.b #$80 : ROR A : CLC : ADC.b $03 : STA.b $03
    PLA : CMP.b #$01 : BNE .spread_neg
      ; +angle: vx' = vx - dy_perp, vy' = vy + dx_perp
      LDA.b $00 : SEC : SBC.b $02 : STA.w SprXSpeed, X
      LDA.b $01 : CLC : ADC.b $03 : STA.w SprYSpeed, X
      BRA .aim_done
    .spread_neg
      ; -angle: vx' = vx + dy_perp, vy' = vy - dx_perp
      LDA.b $00 : CLC : ADC.b $02 : STA.w SprXSpeed, X
      LDA.b $01 : SEC : SBC.b $03 : STA.w SprYSpeed, X
  .aim_done
  PLY
  PLX

  ; Offset shard directly in front of Ice Wolfos's open mouth (16-bit safe!)
  ; Indexed by SprMiscE, X (0=Right, 1=Left, 2=Down, 3=Up)
  LDA.w SprMiscE, X : ASL A : STA.b $04
  LDA.w SprXH, X : XBA : LDA.w SprX, X
  PHY
  LDY.b $04
  REP #$20
  CLC : ADC.w .mouth_dx, Y
  SEP #$20
  PLY
  STA.w SprX, Y : XBA : STA.w SprXH, Y

  LDA.w SprYH, X : XBA : LDA.w SprY, X
  PHY
  LDY.b $04
  REP #$20
  CLC : ADC.w .mouth_dy, Y
  SEP #$20
  PLY
  STA.w SprY, Y : XBA : STA.w SprYH, Y
  RTS

  .mouth_dx : dw $0014, $FFF4, $0004, $0004 ; R:+20, L:-12, D:+4,  U:+4
  .mouth_dy : dw $0003, $0003, $000C, $FFF5 ; R:+3,  L:+3,  D:+12, U:-11
}

; Child Ice Shard Main Update
Wolfos_IceShard_Main:
{
  ; Despawn immediately if parent Wolfos is gone/dead or lifetime expired
  LDY.w SprMiscA, X
  LDA.w SprState, Y : CMP.b #$09 : BNE .burst
  LDA.w SprTimerA, X : BEQ .burst

  JSL Sprite_Move
  JSL Sprite_CheckTileCollision : BNE .burst
  JSL Sprite_CheckDamageToPlayerSameLayer : BCS .burst

  ; Leave frosty sparkle trail every 8 frames
  LDA.w SprTimerA, X : AND.b #$07 : BNE .done
    LDA.b #$10 : STA.b $08
    LDA.b #$03 : STA.b $09
    LDA.b #$05 : JSL BossKit_FxAtSprite
  .done
  RTS

  .burst
  LDA.b #$14 : STA.b $08
  LDA.b #$04 : STA.b $09
  LDA.b #$05 : JSL BossKit_FxAtSprite
  STZ.w SprState, X
  RTS
}

; Child Ice Shard Compact 8x8 Draw (ice_wolfos.4bpp n=1 tiles $88/$89/$98!)
Wolfos_IceShard_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    RTS
  .on_screen
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDY.b #$00
  REP #$20
  LDA.b $00 : STA ($90), Y
  AND.w #$0100 : STA.b $0E
  INY
  LDA.b $02 : STA ($90), Y
  CLC : ADC.w #$0008 : CMP.w #$0100
  SEP #$20
  BCC .vis_y
    LDA.b #$F0 : STA ($90), Y
  .vis_y

  INY
  ; Compact 8x8 diamond frost shard ($88 <-> $89 twinkling every 4 frames),
  ; switching to miniature crystal shatter ($98) on the final 6 frames!
  LDA.w SprTimerA, X : CMP.b #$06 : BCS .live_chr
    LDA.b #$98 : BRA .store_chr
  .live_chr
    LDA.b $1A : AND.b #$04 : BNE .glint_chr
      LDA.b #$88 : BRA .store_chr
    .glint_chr
      LDA.b #$89
  .store_chr
  STA ($90), Y

  INY
  ; Spin H/V flip every 4 frames, Pri 2 ($20), OAM Pal 2 ($04 icy cyan/blue), n=1 ($01)
  LDA.b $1A : AND.b #$0C : ASL #4 : ORA.b #$25
  STA ($90), Y

  LDA.b $0F : STA ($92) ; Compact 8x8 (size bit 1 = 0) + X bit 8
  RTS
}

; =========================================================
; DMGTABLE Setup ($7F6A90..$7F6A9F)
; =========================================================

Wolfos_SetStdDamageTable:
{
  PHX
  LDX.b #$0F
  .loop
    LDA.w .tbl, X : STA.l !Wolfos_DmgTableRow, X
    DEX : BPL .loop
  PLX
  RTS
  ;    BA   D1   D2   D3   D4   HM   AR   HS   BM   SA   PD   FR   IR   BB   ET   QU
  .tbl
  db $03, $01, $01, $01, $01, $03, $00, $01, $01, $02, $00, $04, $04, $01, $03, $01
}

Wolfos_SetIceDamageTable:
{
  PHX
  LDX.b #$0F
  .loop
    LDA.w .tbl, X : STA.l !Wolfos_DmgTableRow, X
    DEX : BPL .loop
  PLX
  RTS
  ;    BA   D1   D2   D3   D4   HM   AR   HS   BM   SA   PD   FR   IR   BB   ET   QU
  ; FR=$05 (16 HP melt!), BB=$02 (64 HP!), IR=$00 & ET=$00 (Ice Immune!)
  .tbl
  db $03, $01, $01, $01, $01, $03, $00, $01, $01, $02, $00, $05, $00, $02, $00, $01
}

; =========================================================
; 3-Variant Palette & Unified 4BPP Art Uploaders
; =========================================================

; Variant 1 — Upload Oracle Cobalt Blue / Royal Indigo palette (7 colors = 14 B)
; into OAM Pal 5 low half ($7EC6A2 / $7EC4A2); Link's Sword C9..C11 untouched!
Wolfos_ApplyBluePalette:
{
  PHX
  REP #$30
  LDX.w #$000C
  .loop
    LDA.l Wolfos_BluePalette, X
    STA.l $7EC6A2, X
    STA.l $7EC4A2, X
    DEX : DEX : BPL .loop
  SEP #$30
  LDA.b #$01 : STA.b $15
  PLX
  RTS
}

; Variant 2 — Upload Castle Mask-Quest Steel-Grey / Gold palette (7 colors = 14 B)
; into OAM Pal 5 low half ($7EC6A2 / $7EC4A2); Link's Sword C9..C11 untouched!
Wolfos_ApplyQuestPalette:
{
  PHX
  REP #$30
  LDX.w #$000C
  .loop
    LDA.l Wolfos_QuestPalette, X
    STA.l $7EC6A2, X
    STA.l $7EC4A2, X
    DEX : DEX : BPL .loop
  SEP #$30
  LDA.b #$01 : STA.b $15
  PLX
  RTS
}

; Variant 3 — Upload Ice Wolfos White / Lavender-Ice / Gold palette (7 colors = 14 B)
; into OAM Pal 6 low half ($7EC6C2 / $7EC4C2); C8..C15 untouched!
Wolfos_ApplyIcePalette:
{
  PHX
  REP #$30
  LDX.w #$000C
  .loop
    LDA.l Wolfos_IcePalette, X
    STA.l $7EC6C2, X
    STA.l $7EC4C2, X
    DEX : DEX : BPL .loop
  SEP #$30
  LDA.b #$01 : STA.b $15
  PLX
  RTS
}

; DMA GameyFireBro's unified 4BPP Wolfos/Ice Wolfos sheets (4,096 B = $1000)
; to OBJ nametable 1 slots 2 & 3 (VRAM $5800..$5FFF -> OAM $80..$FF).
; Restores INIDISPQ ($13) instead of hardcoded $0F to prevent fade-in flash!
Wolfos_ApplyGraphics:
{
  PHX
  LDA.b #$80 : STA.w $2100 ; Forced blank for safe VRAM DMA
  STA.w $2115              ; VMAIN increment on high byte
  REP #$20
  LDA.w #$5800 : STA.w $2116
  LDA.w #$1801 : STA.w $4300
  LDA.w #Wolfos_Art4bpp : STA.w $4302
  LDA.w #$1000 : STA.w $4305
  SEP #$20
  LDA.b #Wolfos_Art4bpp>>16 : STA.w $4304
  LDA.b #$01 : STA.w $420B
  LDA.b $13 : STA.w $2100  ; Restore engine INIDISP shadow cleanly
  PLX
  RTS
}

; =========================================================
; Sprite Body Draw Routine (oos-sprite-forge compliant)
;
; Frames:
;   0-2:   Front / Down (0=idle/guard/subdued, 1=snarl telegraph, 2=lunge)
;   3-5:   Back / Up    (3=idle/guard, 4=claws telegraph, 5=lunge)
;   6-8:   Walk Right   (GameyFireBro sleek 3-frame trot)
;   9-11:  Walk Left    (H-flipped)
;   12-13: Attack Right (12=crouch guard/telegraph, 13=jaw-open lunge)
;   14-15: Attack Left  (14=crouch guard/telegraph, 15=jaw-open lunge)
;   16:    Wolf Mask    ($CC, 1 tile, .nbr_of_tiles = 0!)
; Note: Unused blank tiles $88 (Frames 8/11) and $8C (Frames 12/14) are omitted
;       so the 8x8 Frost Shard tiles ($88/$89/$98) stay 100% isolated from body frames.
; =========================================================

Sprite_Wolfos_Draw:
{
  JSL Sprite_PrepOamCoord : BCC .on_screen
    RTS
  .on_screen
  JSL Sprite_OAM_AllocateDeferToPlayer

  LDA.w SprGfx, X : CLC : ADC.w SprFrame, X : TAY
  LDA.w .start_index, Y : STA.b $06

  ; Correct per-instance palette + intact damage flash (oos-sprite-forge):
  ; $08 = ((SprFlash << 1) ^ SprMiscG) & $0E (never corrupts nametable bit!)
  LDA.w SprFlash, X : ASL A : EOR.w SprMiscG, X : AND.b #$0E : STA.b $08

  PHX
  LDX.w .nbr_of_tiles, Y ; 0-based count (tiles - 1)
  LDY.b #$00
  .nextTile
    PHX
    TXA : CLC : ADC.b $06
    PHA
    ASL A : TAX

    REP #$20
    LDA.b $00 : CLC : ADC.w .x_offsets, X : STA ($90), Y
    AND.w #$0100 : STA.b $0E
    INY
    LDA.b $02 : CLC : ADC.w .y_offsets, X : STA ($90), Y
    CLC : ADC.w #$0010 : CMP.w #$0100
    SEP #$20
    BCC .on_screen_y
      LDA.b #$F0 : STA ($90), Y
      STA.b $0E
    .on_screen_y

    PLX
    INY
    LDA.w .chr, X : STA ($90), Y
    INY
    LDA.w .properties, X : ORA.b $08 : STA ($90), Y

    PHY
    TYA : LSR #2 : TAY
    LDA.b #$02 : ORA.b $0F : STA ($92), Y ; 16x16 size + X bit 8
    PLY : INY
    PLX : DEX : BPL .nextTile

  PLX
  RTS

  .start_index
  db $00, $02, $04, $06, $08, $0A, $0C, $10, $14, $17, $1B, $1F, $22, $25, $28, $2B, $2E
  .nbr_of_tiles
  db 1, 1, 1, 1, 1, 1, 3, 3, 2, 3, 3, 2, 2, 2, 2, 2, 0
  .x_offsets
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 0, 0
  dw 8, -8, -8, 8
  dw -8, 8, 8, -8
  dw 8, -8, 8
  dw -8, 8, 8, -8
  dw 8, -8, -8, 8
  dw -8, 8, -8
  dw -8, 8, 8
  dw -8, 8, 8
  dw 8, -8, -8
  dw 8, -8, -8
  dw 0
  .y_offsets
  dw 0, -16
  dw 0, -16
  dw 0, -16
  dw 0, -16
  dw 0, -16
  dw 0, -16
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw -16, 0, 0
  dw 0, 0, -16, -16
  dw 0, 0, -16, -16
  dw -16, 0, 0
  dw 0, 0, -16
  dw 0, 0, -16
  dw 0, 0, -16
  dw 0, 0, -16
  dw 0
  .chr
  db $E0, $C0
  db $E4, $C4
  db $E6, $C6
  db $E2, $C2
  db $E8, $C8
  db $EA, $CA
  db $A2, $A0, $80, $82
  db $A4, $A6, $86, $84
  db $8A, $A8, $AA
  db $A2, $A0, $80, $82
  db $A4, $A6, $86, $84
  db $8A, $A8, $AA
  db $AC, $AE, $8E
  db $EC, $EE, $CE
  db $AC, $AE, $8E
  db $EC, $EE, $CE
  db $CC ; Wolf Mask
  ; Palette bits 3..1 cleared ($21 normal / $61 H-flip); SprMiscG supplies OAM pal!
  .properties
  db $21, $21
  db $21, $21
  db $21, $21
  db $21, $21
  db $21, $21
  db $21, $21
  db $21, $21, $21, $21
  db $21, $21, $21, $21
  db $21, $21, $21
  db $61, $61, $61, $61
  db $61, $61, $61, $61
  db $61, $61, $61
  db $21, $21, $21
  db $21, $21, $21
  db $61, $61, $61
  db $61, $61, $61
  db $21
}

; =========================================================
; Embedded 3-Variant Palettes & 4BPP Sprite Sheets
; =========================================================

; Variant 1 — Standard Enemy Wolfos (OAM Pal 5 C1..C7): Oracle Cobalt Blue / Royal Indigo
Wolfos_BluePalette:
  dw $7FFF, $02BF, $00B6, $4D06, $14A5, $7ED2, $65CA

; Variant 2 — Castle Mask-Quest Wolfos (OAM Pal 5 C1..C7): Steel-Grey / Gold (Wolf Mask)
Wolfos_QuestPalette:
  dw $7FFF, $02BF, $00B6, $460D, $14A5, $5694, $39AB

; Variant 3 — Ice Wolfos (OAM Pal 6 C1..C7): White / Lavender-Ice / Gold-Eyed
Wolfos_IcePalette:
  dw $7FFF, $02BF, $00B6, $7E56, $14A5, $7FDD, $6AD5

; 4,096 bytes ($1000) generated by Scripts/Generate/build_ice_wolfos_art.py
Wolfos_Art4bpp:
  incbin "Data/graphics/sprites/ice_wolfos.4bpp"
