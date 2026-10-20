; Included in Ganondorf's bank $2A. Local calls inherit M=8, X/Y=8, DB=$2A.
; SprAction: 0=rally ball, 1=independent shard, 2=harmless dissipation, 3=bat.
; Shards keep the ball's 16px origin; the visible 8px quarter is centered +4,+4.

GanonBall_Main:
{
  LDA.w SprAction, X : BEQ .rally
  CMP.b #$01 : BNE .not_shard
    JMP GanonBall_ShardMain
  .not_shard
  CMP.b #$02 : BNE .not_dissipation
    JMP GanonBall_DissipateMain
  .not_dissipation
  CMP.b #$03 : BNE .kill_now
    JMP GanonBat_Main

  .rally
  ; Validate the slot before any indexed parent access.
  LDY.w SprMiscD, X : CPY.b #$10 : BCS .kill_now
  LDA.w SprState, Y : BEQ .kill_now
  LDA.w SprType, Y : CMP.b #Sprite_Ganondorf : BNE .kill_now
  JSR GanonBall_InsideArena : BCS .kill_now
  LDA.w SprMiscB, X : BNE .to_ganondorf

  JSL Sprite_Move
  JSR GanonBall_CheckBackground : BEQ .outgoing_clear
    JMP GanonBall_Impact
  .outgoing_clear
  JSR GanonBall_CheckSwordReflect : BCS .exit
  JSL Sprite_CheckDamageToPlayer : BCC .exit
    JMP GanonBall_StartDissipation
  .kill_now
  STZ.w SprState, X
  .exit
  RTS

  .to_ganondorf
  JSR GanonBall_AimAtGanondorf
  JSL Sprite_Move
  JSR GanonBall_CheckBackground : BEQ .return_clear
    JMP GanonBall_Impact
  .return_clear
  JSL Sprite_SetupHitBox_Alt
  PHX
  LDA.w SprMiscD, X : TAX
  JSL Sprite_SetupHitBox
  PLX
  JSL CheckIfHitBoxesOverlap : BCC .exit

  LDY.w SprMiscD, X
  LDA.w SprMiscC, X : BEQ .stun_ganondorf
    DEC.w SprMiscC, X
    STZ.w SprMiscB, X
    JSR GanonBall_SpeedUp
    LDA.w SprMiscE, X : JSL Sprite_ApplySpeedTowardsPlayer
    JSR GanonBall_SetReturnFacing
    LDA.b #$05 : JSL SpriteSFX_QueueSFX2WithPan
    LDA.b #$29 : JSL SpriteSFX_QueueSFX3WithPan
    RTS

  .stun_ganondorf
  LDA.w SprAction, Y : CMP.b #$03 : BNE .kill
    LDA.b #$04 : STA.w SprAction, Y
    LDA.b #$A0 : STA.w SprTimerA, Y
    LDA.b #!Ganon_HitsPerStun : STA.w SprMiscA, Y
    LDA.b #$02 : STA.w SprFrame, Y
    LDA.b #$00 : STA.w SprHeight, Y
    LDA.w SprGfxProps, Y : AND.b #$BF : STA.w SprGfxProps, Y
    LDA.b #$FF : STA.w SprMiscD, Y
    LDA.b #$09 : JSL SpriteSFX_QueueSFX3WithPan
  .kill
  STZ.w SprState, X
  RTS
}

GanonBall_ShardMain:
{
  JSR GanonBall_InsideArena : BCS .kill
  LDA.w SprTimerA, X : BEQ .dissipate
  JSL Sprite_Move
  JSR GanonBall_CheckBackground : BNE .dissipate
  ; The native same-layer entry uses this shard's small hitbox/damage class.
  ; It bypasses the rally contact hook; shards can never be returned to Ganon.
  JSL Sprite_CheckDamageToPlayerSameLayer : BCC .exit
  .dissipate
  JMP GanonBall_StartDissipation
  .kill
  STZ.w SprState, X
  .exit
  RTS
}

GanonBall_DissipateMain:
{
  LDA.w SprTimerA, X : BNE .exit
    STZ.w SprState, X
  .exit
  RTS
}

; Reject coordinates outside Link's current 512px room, before native tile
; lookup can wrap its low nine coordinate bits into the opposite room edge.
GanonBall_InsideArena:
{
  LDA.b $1B : BEQ .outside
  LDA.b $A0 : ORA.b $A1 : BNE .outside
  LDA.w SprXH, X : EOR.b $23 : AND.b #$FE : BNE .outside
  LDA.w SprYH, X : EOR.b $21 : AND.b #$FE : BNE .outside
  CLC
  RTS
  .outside
  SEC
  RTS
}

; Return A=direction mask, also SprCollision: U=08,D=04,L=02,R=01.
; Probe both corners of each leading edge. The native grounded collision
; helper overwrites $0FA5 with a center-floor probe, so use its tile reader
; directly and classify the contacted edge instead.
GanonBall_CheckBackground:
{
  STZ.b $09
  LDA.b #$02 : STA.b $0B
  LDA.b #$0E : STA.b $0C
  LDA.w SprAction, X : BEQ .size_ready
    LDA.b #$04 : STA.b $0B
    LDA.b #$0B : STA.b $0C
  .size_ready
  LDA.w SprYSpeed, X : BEQ .horizontal
  BMI .up
    LDA.b #$04 : STA.b $08
    LDA.b $0C : STA.b $0F
    BRA .vertical_probes
  .up
    LDA.b #$08 : STA.b $08
    LDA.b $0B : STA.b $0F
  .vertical_probes
  LDA.b $0B : STA.b $0E
  JSR GanonBall_ProbeOffset : BCS .vertical_hit
  LDA.b $0C : STA.b $0E
  JSR GanonBall_ProbeOffset : BCC .horizontal
  .vertical_hit
  LDA.b $09 : ORA.b $08 : STA.b $09

  .horizontal
  LDA.w SprXSpeed, X : BEQ .done
  BMI .left
    LDA.b #$01 : STA.b $08
    LDA.b $0C : STA.b $0E
    BRA .horizontal_probes
  .left
    LDA.b #$02 : STA.b $08
    LDA.b $0B : STA.b $0E
  .horizontal_probes
  LDA.b $0B : STA.b $0F
  JSR GanonBall_ProbeOffset : BCS .horizontal_hit
  LDA.b $0C : STA.b $0F
  JSR GanonBall_ProbeOffset : BCC .done
  .horizontal_hit
  LDA.b $09 : ORA.b $08 : STA.b $09
  .done
  LDA.b $09 : STA.w SprCollision, X
  RTS
}

; $0E/$0F = positive x/y probe offsets. Native GetTileType_long uses
; $00/01=world Y, $02/03=world X, A=collision floor and returns A/$0FA5.
; It preserves X and does not touch the caller's $08..$0F probe bookkeeping.
GanonBall_ProbeOffset:
{
  LDA.w SprY, X : STA.b $00
  LDA.w SprYH, X : STA.b $01
  LDA.w SprX, X : STA.b $02
  LDA.w SprXH, X : STA.b $03
  REP #$20
  LDA.b $0E : AND.w #$00FF : CLC : ADC.b $02 : STA.b $02
  LDA.b $0F : AND.w #$00FF : CLC : ADC.b $00 : STA.b $00
  SEP #$20
GanonBall_ProbeTile:
  LDA.w SprFloor, X : JSL Sprite_GetTileAttr
  CMP.b #$00 : BEQ .passable
  CMP.b #$1C : BEQ .passable
  CMP.b #$20 : BEQ .passable
  CMP.b #$21 : BEQ .passable
  CMP.b #$22 : BEQ .passable
  ; Lightable torches are background objects with an indexed C0..CF
  ; collision attribute. Native projectile collision intentionally skips them.
  CMP.b #$C0 : BCC .projectile_table
  CMP.b #$D0 : BCC .solid
  .projectile_table
  CMP.b #$10 : BCC .lookup
  CMP.b #$14 : BCS .lookup
    JSL $06E8F6 ; native Sprite_CheckSlopedTileCollision_long
    RTS
  .lookup
  PHX
  TAX
  LDA.l $0DB971, X ; native GeneralizedProjectileTileInteraction
  PLX
  CMP.b #$04 : BEQ .passable ; native OW-only rocks are passable indoors
  CMP.b #$01
  RTS
  .solid
  SEC
  RTS
  .passable
  CLC
  RTS
}

; Collision-only entry: record the inward fan direction before stopping.
; Most impacts use their surface normal; corner hits choose the larger
; incoming speed component. Direction 0=right,1=left,2=down,3=up.
GanonBall_Impact:
{
  JSR GanonBall_SetImpactDirection
  JSR GanonBall_StartDissipation
  LDA.b #$36 : JSL SpriteSFX_QueueSFX3WithPan
GanonBall_ImpactRoll:
  JSL GetRandomInt
  AND.b #$01 : BEQ GanonBall_ImpactNoShards
GanonBall_ImpactSpawnShards:
  LDA.b #$02 : STA.w SprMiscF, X
  .next
  JSR GanonBall_SpawnShard
  DEC.w SprMiscF, X : BPL .next
GanonBall_ImpactNoShards:
  RTS
}

GanonBall_SetImpactDirection:
{
  LDA.w SprCollision, X : AND.b #$03 : BEQ .vertical
  LDA.w SprCollision, X : AND.b #$0C : BEQ .horizontal
  LDA.w SprXSpeed, X : BPL .positive_x
    EOR.b #$FF : INC A
  .positive_x
  STA.b $00
  LDA.w SprYSpeed, X : BPL .positive_y
    EOR.b #$FF : INC A
  .positive_y
  CMP.b $00 : BCS .vertical
  .horizontal
  LDA.w SprXSpeed, X : BMI .right
    LDA.b #$01
    BRA .store
  .right
    LDA.b #$00
    BRA .store
  .vertical
  LDA.w SprYSpeed, X : BMI .down
    LDA.b #$03
    BRA .store
  .down
    LDA.b #$02
  .store
  STA.w SprMiscG, X
  RTS
}

; Action2 is deliberately still a live sprite for the visual. The parent
; tracking pointer is detached now, so it can start its normal lost-ball stomp.
GanonBall_StartDissipation:
{
  LDA.w SprAction, X : STA.w SprMiscE, X
  BNE .detached
  LDY.w SprMiscD, X : CPY.b #$10 : BCS .detached
  LDA.w SprState, Y : BEQ .detached
  LDA.w SprType, Y : CMP.b #Sprite_Ganondorf : BNE .detached
  TXA : CMP.w SprMiscD, Y : BNE .detached
    LDA.b #$FF : STA.w SprMiscD, Y
  .detached
  LDA.b #$02 : STA.w SprAction, X
  LDA.b #$10 : STA.w SprTimerA, X
  LDA.b #$FF : STA.w SprMiscD, X
  ; Bats accept native weapon hits. Cancel their delayed damage before the
  ; engine can replace this harmless puff with a vanilla death/stun module.
  STZ.w SprDeath, X
  STZ.w SprDmgTaken, X
  STZ.w SprRecoil, X
  STZ.w SprFlash, X
  LDA.w SprGfxProps, X : ORA.b #$40 : STA.w SprGfxProps, X
  STZ.w SprXSpeed, X
  STZ.w SprYSpeed, X
  STZ.w SprXRound, X
  STZ.w SprYRound, X
  RTS
}

GanonBall_SpawnShard:
{
  LDA.b #Sprite_GanonBall : JSL Sprite_SpawnDynamically : BPL .spawned
    RTS
  .spawned
  LDA.w SprX, X : STA.w SprX, Y
  LDA.w SprXH, X : STA.w SprXH, Y
  LDA.w SprY, X : STA.w SprY, Y
  LDA.w SprYH, X : STA.w SprYH, Y
  LDA.w SprFloor, X : STA.w SprFloor, Y
  LDA.b #$00
  STA.w SprHeight, Y
  STA.w SprXRound, Y
  STA.w SprYRound, Y
  STA.w SprMiscA, Y
  STA.w SprMiscB, Y
  STA.w SprMiscC, Y
  STA.w SprMiscE, Y
  STA.w SprMiscF, Y
  STA.w SprMiscG, Y
  STA.w SprTimerB, Y
  STA.w SprTimerC, Y
  STA.w SprTimerD, Y
  STA.w SprTimerE, Y
  STA.w SprTimerF, Y
  STA.w SprFlash, Y
  STA.w SprPause, Y
  LDA.b #$FF : STA.w SprMiscD, Y
  LDA.b #$01
  STA.w SprAction, Y
  STA.w SprBump, Y
  ; Harmless-to-weapons, with a native small contact box (8px wide at +4,+4).
  LDA.b #$59 : STA.w SprHitbox, Y
  LDA.b #$C0 : STA.w SprGfxProps, Y
  LDA.b #$46 : STA.w SprDefl, Y
  LDA.b #$40 : STA.w SprNbrOAM, Y
  LDA.b #$28 : STA.w SprTimerA, Y
  ; Each impact has a three-way inward fan. Source fields survive native
  ; allocation, and PHX keeps the current ball slot distinct from the child.
  PHX
  LDA.w SprMiscG, X : ASL A : ASL A
  CLC : ADC.w SprMiscF, X : TAX
  LDA.w .speed_x, X : STA.w SprXSpeed, Y
  LDA.w .speed_y, X : STA.w SprYSpeed, Y
  PLX
  RTS

  .speed_x
  db $18, $18, $18, $00, $E8, $E8, $E8, $00
  db $F0, $00, $10, $00, $F0, $00, $10, $00
  .speed_y
  db $F0, $00, $10, $00, $F0, $00, $10, $00
  db $18, $18, $18, $00, $E8, $E8, $E8, $00
}

; Main ball: existing full 16px art. Dissipation: 8 large ticks, 4 small
; ticks, 4 blinking small ticks. All phases use palette6 and resident tiles.
GanonBall_Draw:
{
  LDA.w SprAction, X : CMP.b #$03 : BNE .orb
    JMP GanonBat_Draw
  .orb
  ; The two authored orb poses pulse faster as the exchange accelerates.
  LDA.w SprMiscE, X : CMP.b #$20 : BCC .slow_pulse
    LDA.b $1A : LSR #2 : BRA .pulse
  .slow_pulse
    LDA.b $1A : LSR #3
  .pulse
  AND.b #$01 : CLC : ADC.b #$03 : STA.w SprFrame, X
  LDA.w SprAction, X : BEQ .large
  CMP.b #$01 : BEQ .small
  CMP.b #$02 : BNE .exit
  LDA.w SprTimerA, X : BEQ .exit
  LDY.w SprMiscE, X : BNE .small_dissipation
  CMP.b #$09 : BCS .large
  .small_dissipation
  CMP.b #$05 : BCS .small
  AND.b #$01 : BNE .exit
  .small
  JSR GanonBall_DrawSmall
  RTS
  .large
  JSR Ganon_DrawFrame
  .exit
  RTS
}

GanonBall_DrawSmall:
{
  JSL Sprite_PrepOamCoord
  JSL Sprite_OAM_AllocateDeferToPlayer
  LDY.b #$00
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0004 : STA.b ($90), Y
  PHA
  AND.w #$0100 : STA.b $0E
  PLA : CLC : ADC.w #$0008 : CMP.w #$0108 : BCS .hide
  LDA.b $02 : CLC : ADC.w #$0004
  PHA
  CLC : ADC.w #$0008 : CMP.w #$0100 : BCS .hide_y
  PLA
  SEP #$20
  INY : STA.b ($90), Y
  INY
  LDA.b $1A : AND.b #$08 : BEQ .tile_a
    LDA.b #GanonBall_TileB
    BRA .tile_ready
  .tile_a
    LDA.b #GanonBall_TileA
  .tile_ready
  STA.b ($90), Y
  INY
  LDA.b #$3D : STA.b ($90), Y
  LDY.b #$00
  LDA.b $0F : STA.b ($92), Y ; x-high only; 8px size bit stays clear
  RTS
  .hide_y
  PLA
  .hide
  SEP #$20
  LDY.b #$01
  LDA.b #$F0 : STA.b ($90), Y
  RTS
}
