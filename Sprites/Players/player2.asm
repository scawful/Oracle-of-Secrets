; =========================================================
; Native 2-player PoC (native-2p-poc, 2026-09-25)
;
; Pad-2 Start drops in a second Link ("P2"); pad-2 Select+Start leaves.
; P2 is a standalone actor, not a sprite slot: its state lives in WRAM, it
; writes its own OAM entries and streams Link's walk poses into shared OBJ
; tiles with its own DMA. Room and area loads never delete it; after a load
; it respawns next to Link.
;
; Pad 2: D-pad walk, B sword (punch without one), A lift / throw (bushes,
;        pots, rocks, signs), Start pause, Select regroup (warp next to
;        Link), Select+Start leave. Touching drops collects them for the team.
;
; Flag: !ENABLE_NATIVE_2P_POC (Util/macros.asm, default 0).
; Design, budgets and known conflicts:
;   Roms/TestBuilds/native-2p-poc-2026-09-25/DESIGN.md
; =========================================================

if !ENABLE_NATIVE_2P_POC == 1

; ---------------------------------------------------------
; WRAM ($7FF400-$7FF461, $7FF500-$7FF5FF). $7FF180-$7FF7FF is free except $7FF300-$7FF331.

P2_Magic       = $7FF400 ; word, !P2_MAGIC while joined
P2_PadHi       = $7FF402 ; pad 2 held: BYSTudlr ($421B)
P2_PadLo       = $7FF403 ; pad 2 held: AXLR---- ($421A)
P2_NewHi       = $7FF404 ; pad 2 new presses: BYSTudlr
P2_NewLo       = $7FF405 ; pad 2 new presses: AXLR----
P2_X           = $7FF406 ; word, world X (same space as $22)
P2_Y           = $7FF408 ; word, world Y (same space as $20)
P2_SubX        = $7FF40A ; subpixel accumulators
P2_SubY        = $7FF40B
P2_Dir         = $7FF40C ; 0 up, 1 down, 2 left, 3 right ($2F / 2)
P2_Step        = $7FF40D ; 0 standing, 1-8 walking (LinkOAM_AnimationSteps row)
P2_StepTimer   = $7FF40E
P2_Flags       = $7FF40F ; b0 pose upload this frame, b1 respawn pending, b2 blade upload
P2_Pose2       = $7FF410 ; word, pose * 2 (index into Link head/body GFX tables)
P2_LastRoom    = $7FF412 ; word, $A0 indoors or $8A|$8000 outdoors
P2_LastTile    = $7FF434 ; debug: tile type of the last collision probe
P2_AttackTimer = $7FF435 ; frames left in the B attack (0 = not attacking)
P2_HitMask     = $7FF436 ; word, sprite slots already hit by this attack
P2_HopTimer    = $7FF438 ; frames left in a ledge hop (0 = on the ground)
P2_HopDir      = $7FF439
P2_HopZ        = $7FF43A ; drawn height during a hop
P2_HopExtra    = $7FF43B ; extra 2 px steps allowed to find landing ground
P2_ProbeSet    = $7FF43C ; P2_ProbeSolid scratch
P2_ProbeCount  = $7FF43D
P2_LedgeCount  = $7FF43E
P2_ProbeLedge  = $7FF43F ; 1: the last blocked probe was a hoppable ledge
P2_MoveDir     = $7FF440 ; direction of the axis being moved (0-3)
P2_HopFromX    = $7FF441 ; word, where the hop started (restored if no landing)
P2_HopFromY    = $7FF443 ; word
P2_HopCooldown = $7FF445 ; frames ledges stay walls after a failed landing
P2_BufHead     = $7FF446 ; word, source of the head tiles now in P2_GfxBuf
P2_BufBody     = $7FF448 ; word, source of the body tiles now in P2_GfxBuf
P2_BufKey      = $7FF44A ; word, GFX bank | tunic variant << 8 of P2_GfxBuf
P2_HurtTimer   = $7FF44C ; blink / no-damage frames after a hit
P2_RecoilTimer = $7FF44D ; knockback frames left
P2_RecoilDir   = $7FF44E ; knockback direction (0-3)
P2_AttackSword = $7FF44F ; 1: this swing shows the sword, 0: punch
P2_AttackClass = $7FF450 ; damage class of this swing (1 punch, 1-4 sword level)
P2_SwordSrc    = $7FF451 ; word, sword art in bank $7E for this frame
P2_SwordX      = $7FF453 ; word, blade origin on screen
P2_SwordY      = $7FF455 ; word
P2_HitLink     = $7FF457 ; 1: this swing already knocked Link back (PvP)
P2_Held        = $7FF458 ; sprite slot + 1 of the object P2 carries (0 = empty hands)
P2_LiftTimer   = $7FF459 ; frames left in the lift (the object rises in 3 stages)
P2_ThrowTimer  = $7FF45A ; frames left in the throw pose
P2_HeldProp    = $7FF45B ; the carried object's $0E60 bit 4, restored when thrown
P2_SaveY       = $7FF45C ; word, Link's $20 while vanilla lift code runs for P2
P2_SaveX       = $7FF45E ; word, Link's $22
P2_Save2F      = $7FF460 ; Link's $2F
P2_CarryKind   = $7FF461 ; thrown-object kind + 1 P2 carries (0 = none); survives room loads
P2_GfxBuf      = $7FF500 ; 256 bytes: head top, head bottom, body top, body bottom

!P2_MAGIC     = $2B7C   ; random power-on WRAM counts as "not joined"

; OBJ tiles shared with situational vanilla users (DESIGN.md section 5)
!P2_HEAD_CHR  = $0E     ; bird slot, VRAM $40E0 / $41E0
!P2_BODY_CHR  = $24     ; item-get slot, VRAM $4240 / $4340
!P2_SHADOW_CHR = $6C    ; Link's shadow half (common sheet, always loaded)
!P2_HEAD_VRAM = $40E0
!P2_BODY_VRAM = $4240

; Vanilla tables and routines (usdasm names)
!P2_PoseData   = $0D8000 ; LinkOAM_PoseData: head Y, head X, flips per pose
!P2_AnimSteps  = $0D85FB ; LinkOAM_AnimationSteps: pose per animation step (word)
!P2_POKE_STEP  = $60     ; sword-poke row: 3 steps per direction (also indexes the weapon tables)
!P2_LIFT_STEP  = $FC     ; lifting row: 3 steps per direction (LinkOAM_AnimationStepDataOffsets $0D9F10)
!P2_CARRY_STEP = $BC     ; carrying walk: 6 steps per direction ($0D9F0A)
!P2_THROW_STEP = $D4     ; throwing: 6 steps per direction ($0D9F0C)
!P2_WeaponIdx  = $0D8AF1 ; LinkOAM_WeaponGFXIndex: weapon tile set per step
!P2_WeaponTiles = $0D839B ; LinkOAM_WeaponTiles: 3 pieces (tile, attr) per set
!P2_SwordOffY  = $0D8EEF ; LinkOAM_SwordOffsetY per step
!P2_SwordOffX  = $0D90EE ; LinkOAM_SwordOffsetX per step
!P2_SWORD_CHR_ADD = $1B  ; Link's sword tiles $05/$06/$15 -> follower slot $20/$21/$30
!P2_SWORD_VRAM = $4200   ; follower head tiles $20/$21 (bottom row $4300)
!P2_Priority   = $0DA126 ; LinkOAM_ObjectPriority: word per $EE
!P2_HeadGfx    = $009396 ; LinkOAM_HeadAddresses: word per pose*2, bank $10
!P2_BodyGfx    = $0095F4 ; LinkOAM_BodyAddresses
!P2_TileSolid  = $1DF6CF ; GeneralizedSpriteTileInteraction: 0 = walkable
!P2_FollowerMain = $099F91
!P2_SetupHitbox  = $0683EA ; Sprite_SetupHitbox_long: sprite X -> box B ($04-$07,$0A,$0B)
!P2_Overlap      = $0683E6 ; CheckIfHitBoxesOverlap_long: carry set = boxes overlap
!P2_DamageSprite = $06ED25 ; Ancilla_CheckDamageToSprite_preset.apply: A = class, X = sprite
!P2_Absorb       = $06D125 ; Sprite_HandleAbsorptionByPlayer_long: X = drop sprite
!P2_DamageExitHit = $06F3C6 ; Sprite_CheckDamageFromLink: SEC, then SpriteDamage_ExitWith00
!P2_ContactExit   = $06F1BF ; Sprite_CheckDamageToLink.exit_preserve_check (RTS)
!P2_BumpDamage    = $06F427 ; Sprite_BumpDamageGroups: 3 armor columns per damage class

; Lift, carry and throw: vanilla's own routines and tables (Link_PerformThrow
; $07B11C, SpriteModule_Carried $06DE83, CarriedSprite_CheckForThrow $06DF6D)
!P2_LiftOffY     = $07D365 ; LiftableCheckOffset_Y: word per direction
!P2_LiftOffX     = $07D36D ; LiftableCheckOffset_X
!P2_GloveLevel   = $07D375 ; LiftableGloveLevels: per liftable ID
!P2_LiftableID   = $07D37C ; Liftable0368ID: tile type & $0F -> liftable ID
!P2_TossKinds    = $07B1AD ; LinkToss_liftable_tiles: tile type per thrown-object kind
!P2_IdentifyUW   = $01D748 ; Underworld_CheckForAndIDLiftableTile: carry set = liftable, A = type
!P2_LiftUW       = $01D9EC ; Underworld_LiftAndReplaceLiftable: A = type, $00-$03 = X/Y
!P2_LiftOW       = $1BBF9D ; Overworld_HandleLiftableTiles: same outputs
!P2_SpawnTerrain = $068156 ; Sprite_SpawnThrowableTerrain_silently: A = kind, X = new slot (bit 7 = none)
!P2_SFX_LIFT     = $1D     ; SFX2, as Sprite_SpawnThrowableTerrain
!P2_CarryOffXLo  = $06DE4D ; SpriteModule_Carried tables, index dir*4 + lift stage
!P2_CarryOffXHi  = $06DE5D
!P2_CarryOffZ    = $06DE6D
!P2_CarryBobY    = $06DE7D ; 3, 2, 1, 3, 2, 1 by carry-walk frame
!P2_ThrowSpeedX  = $06DF61 ; CarriedSprite_CheckForThrow tables, per direction
!P2_ThrowSpeedY  = $06DF65
!P2_ThrowSpeedZ  = $06DF69
!P2_LIFT_FRAMES  = $18     ; vanilla stages: 16 frames, then 4 + 4
!P2_THROW_FRAMES = $09
!P2_SFX_THROW    = $13     ; SFX3, as CarriedSprite_CheckForThrow

!P2_ATTACK_FRAMES = $0F
!P2_DAMAGE_CLASS  = $01  ; punch: fighter-sword slash row of the damage tables
!P2_HOP_FRAMES    = $10  ; 2 px per frame

!P2_SFX_SWING   = $01   ; SFX2, fighter sword swing (vanilla SwordSwingSFX)
!P2_SFX_HOP     = $20   ; SFX2, Link's ledge hop
!P2_SFX_BONK    = $21   ; SFX2, thump (Sprite_RecoilLinkAndTHUMP)
!P2_SFX_JOIN    = $2D   ; SFX3
!P2_SFX_LEAVE   = $25   ; SFX3

; Bank $3A: opening arrival owns $3AC000-$3ADFFF (Core/Cutscene/opening.asm).
org $3AF000

; =========================================================
; Per-frame tick. Replaces JSL Follower_Main at $068365 (Sprite_Main, after
; OAM_ResetRegionBases) and tail-jumps to it.

P2_Tick:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB : PHK : PLB
  SEP #$30

  JSR P2_ReadPad
  JSR P2_Update
  JSR P2_Draw

  PLB
  REP #$30
  PLY : PLX : PLA
  PLP
  JML !P2_FollowerMain
}

; =========================================================
; Pad 2 goes to private WRAM, never to the vanilla $F1/$F3/$F5/$F7 slots:
; vanilla reads $F5 bit 7 (pad-2 B) at $07810C/$0783A4 to toggle P1 no-clip.

P2_ReadPad:
{
  ; Wait out the auto-joypad read if a lag frame ran into vblank.
  - LDA.l $004212 : LSR : BCS -

  LDA.l $00421B : PHA
  EOR.l P2_PadHi : AND $01,S : STA.l P2_NewHi
  PLA : STA.l P2_PadHi

  LDA.l $00421A : PHA
  EOR.l P2_PadLo : AND $01,S : STA.l P2_NewLo
  PLA : STA.l P2_PadLo

  ; Cutscenes ignore pad 2, like the P1 clamp in Core/patches.asm.
  LDA.l InCutScene : BEQ .done
    LDA.b #$00
    STA.l P2_PadHi : STA.l P2_PadLo
    STA.l P2_NewHi : STA.l P2_NewLo
  .done
  RTS
}

; =========================================================
; Out: carry set = P2 is joined.

P2_IsJoined:
{
  REP #$20
  LDA.l P2_Magic : CMP.w #!P2_MAGIC
  SEP #$20
  BNE .no
    SEC
    RTS
  .no
  CLC
  RTS
}

; Out: carry set = normal overworld/dungeon play (P2 may join, move, leave).

P2_CanAct:
{
  LDA.b $10 : CMP.b #$07 : BEQ .module_ok
              CMP.b #$09 : BNE .no
  .module_ok
  LDA.b $11 : BNE .no
  LDA.w $0FC1 : BNE .no          ; sprites frozen
  LDA.l InCutScene : BNE .no
    SEC
    RTS
  .no
  CLC
  RTS
}

; =========================================================

P2_Update:
{
  JSR P2_IsJoined : BCS .joined
    JSR P2_CanAct : BCC .exit
    LDA.l P2_NewHi : AND.b #$10 : BEQ .exit    ; Start
      REP #$20
      LDA.w #!P2_MAGIC : STA.l P2_Magic
      SEP #$20
      LDA.b #$00 : STA.l P2_Flags
      STA.l P2_Held : STA.l P2_LiftTimer : STA.l P2_ThrowTimer : STA.l P2_CarryKind
      JSR P2_Spawn
      LDA.b #!P2_SFX_JOIN : STA.w $012F
    .exit
    RTS

  .joined
  JSR P2_CheckRoomChange
  JSR P2_CanAct : BCC .exit

  LDA.l P2_PadHi : AND.b #$20 : BEQ .stay      ; Select held
  LDA.l P2_NewHi : AND.b #$10 : BEQ .stay      ; + Start pressed
    JMP P2_Leave

  .stay
  LDA.l P2_Flags : AND.b #$02 : BEQ .placed
    JSR P2_Spawn
    LDA.l P2_Flags : AND.b #$02 : BNE .exit    ; still no free spot beside Link
  .placed

  ; Start alone: pause menu, with vanilla's checks and sequence
  ; (Module09_00_PlayerControl $02A53C).
  LDA.l P2_NewHi : AND.b #$10 : BEQ .no_pause
    LDA.w $0112 : ORA.w $02E4 : ORA.w $0FFC : ORA.w $04C6 : BNE .no_pause
    STZ.w $0200
    LDA.b #$01 : STA.b $11
    LDA.b $10 : STA.w $010C
    LDA.b #$0E : STA.b $10
    RTS
  .no_pause

  LDA.l P2_NewHi : AND.b #$20 : BEQ .no_regroup ; Select alone: regroup
    JSR P2_Spawn
    LDA.b #!P2_SFX_JOIN : STA.w $012F
    RTS
  .no_regroup

  JSR P2_UpdateRecoil : BCS .busy
  JSR P2_UpdateHop : BCS .busy
  JSR P2_UpdateLift : BCS .busy
  LDA.l P2_Held : BNE .walk                    ; hands full: B throws, no attack
  JSR P2_UpdateAttack : BCS .busy
  .walk
  JSR P2_Move
  .busy
  JSR P2_HoldObject
  JSR P2_Pickups
  JSR P2_PvP
  JMP P2_CheckOnScreen
}

P2_Leave:
{
  JSR P2_Drop
  LDA.b #$00
  STA.l P2_Magic : STA.l P2_Magic+1
  STA.l P2_Flags
  STA.l P2_AttackTimer : STA.l P2_HopTimer : STA.l P2_HopZ
  LDA.b #!P2_SFX_LEAVE : STA.w $012F
  RTS
}

; =========================================================
; Sets P2_Flags bit 1 when the room (indoors) or area (outdoors) changed.

P2_CheckRoomChange:
{
  REP #$20
  LDA.b $1B : AND.w #$00FF : BEQ .outdoors
    LDA.b $A0
    BRA .compare
  .outdoors
    LDA.b $8A : AND.w #$00FF : ORA.w #$8000
  .compare
  CMP.l P2_LastRoom : BEQ .same
    STA.l P2_LastRoom
    SEP #$20
    LDA.l P2_Flags : ORA.b #$02 : STA.l P2_Flags
    JMP P2_Stash                               ; a carried object moves with P2
  .same
  SEP #$20
  RTS
}

; =========================================================
; Place P2 beside Link: left, right, below, above, then on Link. If every
; spot is blocked for P2 (Link swimming, in a doorway, on stairs), keep the
; respawn pending: P2 stays hidden and retries next frame. P2 keeps what it
; carries (P2_Stash / P2_Unstash).

P2_Spawn:
{
  LDX.b #$00
  .try
    REP #$20
    LDA.b $22 : CLC : ADC.w .dx,X : STA.b $08
    LDA.b $20 : CLC : ADC.w .dy,X : STA.b $0A
    SEP #$20
    PHX
    LDA.b #$04 : JSR P2_ProbeSolid
    PLX
    BCC .place
    INX #2 : CPX.b #$0A : BCC .try
  LDA.l P2_Flags : ORA.b #$02 : STA.l P2_Flags
  JMP P2_Stash                                 ; hidden: the carried object waits too

  .place
  REP #$20
  LDA.b $08 : STA.l P2_X
  LDA.b $0A : STA.l P2_Y
  SEP #$20
  LDA.b $2F : LSR : STA.l P2_Dir
  LDA.b #$00
  STA.l P2_Step : STA.l P2_StepTimer
  STA.l P2_SubX : STA.l P2_SubY
  STA.l P2_AttackTimer : STA.l P2_HopTimer : STA.l P2_HopZ
  STA.l P2_HopCooldown
  STA.l P2_HurtTimer : STA.l P2_RecoilTimer
  REP #$20
  LDA.w #$FFFF : STA.l P2_BufKey               ; rebuild P2's tiles on the next draw
  SEP #$20
  JSR P2_CheckRoomChange
  LDA.l P2_Flags : AND.b #$FD : STA.l P2_Flags
  JMP P2_Unstash                               ; carried object back overhead

  .dx : dw -16, 16, 0, 0, 0
  .dy : dw 0, 0, 16, -16, 0
}

; Warp back beside Link once the camera leaves P2 behind (it follows P1).

P2_CheckOnScreen:
{
  REP #$20
  LDA.l P2_X : SEC : SBC.b $E2
  CLC : ADC.w #$0010 : CMP.w #$0110 : BCS .off  ; X in [-16, 256)
  LDA.l P2_Y : SEC : SBC.b $E8
  CLC : ADC.w #$0018 : CMP.w #$00F8 : BCS .off  ; Y in [-24, 224)
  SEP #$20
  RTS
  .off
  SEP #$20
  JMP P2_Spawn
}

; =========================================================
; Tile collision with Link's probe layout (TileDetect_Movement, $07CD7B):
; three points on the leading edge for a move, eight for a whole-box check.
; Uses vanilla's sprite walkability table plus player exceptions, and the
; screen edge is a wall, so P2 can't walk out of P1's camera view.
;
; In: A = probe set (0 up, 1 down, 2 left, 3 right, 4 whole box),
;     $08 = X, $0A = Y (candidate position, words).
; Out: carry set = blocked. P2_ProbeLedge = 1 when the block is a ledge that
;      P2 can hop in this direction (all three leading probes on it).
; Clobbers $00-$07 (Sprite_GetTileAttr / Overworld_GetTileTypeAtLocation).

P2_ProbeSolid:
{
  STA.l P2_ProbeSet
  LDA.b #$00 : STA.l P2_LedgeCount : STA.l P2_ProbeLedge
  REP #$20
  LDA.b $08 : SEC : SBC.b $E2 : CMP.w #$00F1 : BCS .offscreen    ; X in [0, 240]
  LDA.b $0A : SEC : SBC.b $E8 : CMP.w #$00C9 : BCS .offscreen    ; Y in [0, 200]
  SEP #$20

  LDA.l P2_ProbeSet : TAX
  LDA.w .count,X : STA.l P2_ProbeCount
  LDA.w .first,X : TAY
  .probe
    REP #$20
    LDA.b $0A : CLC : ADC.w .oy,Y : STA.b $00
    LDA.b $08 : CLC : ADC.w .ox,Y : STA.b $02
    SEP #$20
    PHY
    LDA.b $EE                          ; Link's layer
    JSL Sprite_GetTileAttr             ; A = tile type, exits SEP #$30
    PLY
    STA.l P2_LastTile
    JSR .classify : BCS .blocked
    INY #2
    LDA.l P2_ProbeCount : DEC : STA.l P2_ProbeCount : BNE .probe

  LDA.l P2_LedgeCount : BEQ .clear
    LDA.l P2_ProbeSet : TAX
    LDA.w .count,X : CMP.l P2_LedgeCount : BNE .blocked   ; partial ledge: wall
    LDA.b #$01 : STA.l P2_ProbeLedge
    BRA .blocked
  .clear
  CLC
  RTS
  .offscreen
  SEP #$20
  .blocked
  SEC
  RTS

  ; In: A = tile type. Out: carry set = wall. Counts hoppable ledges.
  .classify
  CMP.b #$09 : BEQ .walkable           ; shallow water
  CMP.b #$22 : BEQ .walkable           ; outdoor stairs (sprite table: solid)
  CMP.b #$08 : BEQ .wall               ; deep water: P2 cannot swim
  CMP.b #$28 : BEQ .ledge_north
  CMP.b #$29 : BEQ .ledge_south
  CMP.b #$2A : BEQ .ledge_side
  CMP.b #$2B : BEQ .ledge_side
  TAX
  LDA.l !P2_TileSolid,X : BNE .wall
  .walkable
  CLC
  RTS
  .ledge_north
  LDA.l P2_ProbeSet : CMP.b #$00 : BNE .wall
  BRA .ledge
  .ledge_south
  LDA.l P2_ProbeSet : CMP.b #$01 : BNE .wall
  BRA .ledge
  .ledge_side
  LDA.l P2_ProbeSet : CMP.b #$02 : BCC .wall
                      CMP.b #$04 : BCS .wall
  .ledge
  LDA.l P2_HopCooldown : BNE .wall             ; just bounced back from this ledge
  LDA.l P2_LedgeCount : INC : STA.l P2_LedgeCount
  CLC
  RTS
  .wall
  SEC
  RTS

  .first : db 0, 6, 12, 18, 24
  .count : db 3, 3, 3, 3, 8
  .ox : dw 1, 8, 14,   1, 8, 14,    1, 1, 1,    14, 14, 14,   1, 8, 14, 1, 8, 14, 1, 14
  .oy : dw 8, 8, 8,    23, 23, 23,  8, 16, 23,  8, 16, 23,    8, 8, 8, 23, 23, 23, 16, 16
}

; =========================================================
; Walk at Link's speed (1.5 px/frame per axis), one axis at a time so P2
; slides along walls. A full ledge on the leading edge starts a hop.

P2_Move:
{
  LDA.l P2_PadHi : AND.b #$0F : STA.b $0C      ; ----udlr
  BNE .input
    LDA.b #$00
    STA.l P2_Step : STA.l P2_StepTimer
    RTS
  .input
  JSR P2_ChooseDir

  LDA.b $0C : AND.b #$03 : BEQ .vertical
    LDA.l P2_SubX : CLC : ADC.b #$80 : STA.l P2_SubX
    LDA.b #$00 : ADC.b #$01 : STA.b $0D        ; 1 px, 2 on carry
    LDA.b #$03 : STA.l P2_MoveDir              ; right
    REP #$20
    LDA.w #$0001 : STA.b $0E
    SEP #$20
    LDA.b $0C : AND.b #$02 : BEQ .h_loop
      LDA.b #$02 : STA.l P2_MoveDir            ; left
      REP #$20
      LDA.w #$FFFF : STA.b $0E
      SEP #$20
    .h_loop
      REP #$20
      LDA.l P2_X : CLC : ADC.b $0E : STA.b $08
      LDA.l P2_Y : STA.b $0A
      SEP #$20
      LDA.l P2_MoveDir : JSR P2_ProbeSolid : BCC .h_clear
        LDA.l P2_ProbeLedge : BEQ .vertical
        JMP P2_StartHop
      .h_clear
      REP #$20
      LDA.b $08 : STA.l P2_X
      SEP #$20
      DEC.b $0D : BNE .h_loop

  .vertical
  LDA.b $0C : AND.b #$0C : BEQ .animate
    LDA.l P2_SubY : CLC : ADC.b #$80 : STA.l P2_SubY
    LDA.b #$00 : ADC.b #$01 : STA.b $0D
    LDA.b #$01 : STA.l P2_MoveDir              ; down
    REP #$20
    LDA.w #$0001 : STA.b $0E
    SEP #$20
    LDA.b $0C : AND.b #$08 : BEQ .v_loop
      LDA.b #$00 : STA.l P2_MoveDir            ; up
      REP #$20
      LDA.w #$FFFF : STA.b $0E
      SEP #$20
    .v_loop
      REP #$20
      LDA.l P2_X : STA.b $08
      LDA.l P2_Y : CLC : ADC.b $0E : STA.b $0A
      SEP #$20
      LDA.l P2_MoveDir : JSR P2_ProbeSolid : BCC .v_clear
        LDA.l P2_ProbeLedge : BEQ .animate
        JMP P2_StartHop
      .v_clear
      REP #$20
      LDA.b $0A : STA.l P2_Y
      SEP #$20
      DEC.b $0D : BNE .v_loop

  .animate
  LDA.l P2_StepTimer : INC : STA.l P2_StepTimer
  CMP.b #$04 : BCC .done
    LDA.b #$00 : STA.l P2_StepTimer
    LDA.l P2_Step : INC
    CMP.b #$09 : BCC .store_step
      LDA.b #$01
    .store_step
    STA.l P2_Step
  .done
  RTS
}

; Keep the facing while its button is held; else first of up, down, left, right.
; In: $0C = ----udlr.

P2_ChooseDir:
{
  LDA.l P2_Dir : TAX
  LDA.w .bit,X : AND.b $0C : BNE .keep
  LDX.b #$00
  - LDA.w .bit,X : AND.b $0C : BNE .set
    INX : CPX.b #$04 : BCC -
  .keep
  RTS
  .set
  TXA : STA.l P2_Dir
  RTS

  .bit : db $08, $04, $02, $01
}

; =========================================================
; Ledge hop: 16 frames at 2 px/frame in P2_MoveDir with a height arc, then
; keep stepping (up to 8 x 2 px) until the whole box stands on clear ground.
; No landing ground in reach: P2 goes back to where the hop started.

P2_StartHop:
{
  REP #$20
  LDA.l P2_X : STA.l P2_HopFromX
  LDA.l P2_Y : STA.l P2_HopFromY
  SEP #$20
  LDA.l P2_MoveDir : STA.l P2_HopDir
  LDA.b #!P2_HOP_FRAMES : STA.l P2_HopTimer
  LDA.b #$08 : STA.l P2_HopExtra
  LDA.b #$00 : STA.l P2_Step : STA.l P2_StepTimer
  LDA.b #!P2_SFX_HOP : STA.w $012E
  RTS
}

; Out: carry set = hopping this frame (no walking or attacking).

P2_UpdateHop:
{
  LDA.l P2_HopTimer : BNE .hopping
  LDA.l P2_HopCooldown : BEQ .ground
    DEC : STA.l P2_HopCooldown
  .ground
  CLC
  RTS

  .hopping
  DEC : STA.l P2_HopTimer
  TAX : LDA.w .z,X : STA.l P2_HopZ
  LDA.l P2_HopDir : ASL : TAX
  REP #$20
  LDA.l P2_X : CLC : ADC.w .dx,X : STA.l P2_X
  LDA.l P2_Y : CLC : ADC.w .dy,X : STA.l P2_Y
  SEP #$20
  LDA.l P2_HopTimer : BNE .airborne
    REP #$20
    LDA.l P2_X : STA.b $08
    LDA.l P2_Y : STA.b $0A
    SEP #$20
    LDA.b #$04 : JSR P2_ProbeSolid : BCC .airborne
    LDA.l P2_HopExtra : BEQ .lost
      DEC : STA.l P2_HopExtra
      LDA.b #$01 : STA.l P2_HopTimer
      BRA .airborne
    .lost
    REP #$20
    LDA.l P2_HopFromX : STA.l P2_X
    LDA.l P2_HopFromY : STA.l P2_Y
    SEP #$20
    LDA.b #$1E : STA.l P2_HopCooldown
  .airborne
  SEC
  RTS

  .dx : dw 0, 0, -2, 2
  .dy : dw -2, 2, 0, 0
  .z  : db 0, 2, 4, 6, 8, 10, 11, 12, 12, 12, 11, 10, 8, 6, 4, 2
}

; =========================================================
; B: a short thrust in P2_Dir using Link's sword-poke poses. With P1's sword
; (same level, same art) it shows the blade; without a sword, or while a
; follower holds the tile slot, it's a punch. P2 stands still while attacking.
; Out: carry set = attacking this frame.

P2_UpdateAttack:
{
  LDA.l P2_AttackTimer : BNE .running
  LDA.l P2_NewHi : AND.b #$80 : BEQ .idle      ; B
    LDA.b #!P2_ATTACK_FRAMES : STA.l P2_AttackTimer
    LDA.b #$00 : STA.l P2_HitMask : STA.l P2_HitMask+1
    STA.l P2_Step : STA.l P2_StepTimer : STA.l P2_HitLink
    JSR P2_ChooseWeapon
    LDA.b #!P2_SFX_SWING : STA.w $012E
    SEC
    RTS
  .idle
  CLC
  RTS

  .running
  DEC : STA.l P2_AttackTimer
  SEC
  RTS
}

; Hits land inside each enemy's own damage check. Sprite_CheckDamageFromLink
; ($06F2B4) is what every enemy, vanilla or custom, calls to ask "did the
; player hit me"; P2_ActionGate runs there, after its layer check. When P2's
; punch box overlaps the sprite during the thrust frames (once per swing), P2
; applies fighter-sword damage ($06ED25, the goldstar's entry) with knockback
; away from P2 and leaves through the vanilla "hit" exit, so the enemy reacts
; exactly as it does to Link's sword (e.g. sea urchins die on contact).
; Otherwise it replays LDA $44 : CMP #$80 and Link's own check continues.
; Entry: JSL from $06F2C2, X = sprite slot, A/X/Y 8-bit, DB = $06.

P2_ActionGate:
{
  PHB : PHK : PLB
  JSR P2_PunchHitsSprite : BCS .p2_hit
  PLB
  LDA.b $44 : CMP.b #$80                       ; replayed; BEQ .no_collision follows
  RTL

  .p2_hit
  LDA.l P2_Dir : TAY
  LDA.w .recoil_y,Y : STA.w $0F30,X
  LDA.w .recoil_x,Y : STA.w $0F40,X
  PHX
  LDA.l P2_AttackClass
  JSL !P2_DamageSprite
  PLX
  PLB
  PLA : PLA : PLA                              ; drop this JSL's return address
  JML !P2_DamageExitHit                        ; SEC : exit with "hit"

  .recoil_y : db $C0, $40, $00, $00
  .recoil_x : db $00, $00, $C0, $40
}

; Out: carry set = P2's punch hits sprite X this frame (marks it as hit).

P2_PunchHitsSprite:
{
  JSR P2_IsJoined : BCC .no
  LDA.l P2_AttackTimer : CMP.b #$0B : BCS .no  ; thrust frames only
                         CMP.b #$04 : BCC .no
  TXA : ASL : TAY
  REP #$20
  LDA.w .bit,Y : AND.l P2_HitMask
  SEP #$20
  BNE .no                                      ; already hit this swing
  PHX
  JSR P2_SetPunchBox
  PLX : PHX
  JSL !P2_SetupHitbox
  JSL !P2_Overlap
  PLX
  BCC .no
  TXA : ASL : TAY
  REP #$20
  LDA.w .bit,Y : ORA.l P2_HitMask : STA.l P2_HitMask
  SEP #$20
  SEC
  RTS
  .no
  CLC
  RTS

  .bit : dw $0001, $0002, $0004, $0008, $0010, $0020, $0040, $0080
         dw $0100, $0200, $0400, $0800, $1000, $2000, $4000, $8000
}

; Box A ($00 x, $08 x hi, $01 y, $09 y hi, $02 w, $03 h) for the hitbox
; routines: a 16x16 square in front of P2.

P2_SetPunchBox:
{
  LDA.l P2_Dir : ASL : CLC : ADC.l P2_AttackSword
  ASL : TAX                                    ; (dir*2 + sword) * 2
  REP #$20
  LDA.l P2_X : CLC : ADC.w .dx,X
  SEP #$20
  STA.b $00 : XBA : STA.b $08
  REP #$20
  LDA.l P2_Y : CLC : ADC.w .dy,X
  SEP #$20
  STA.b $01 : XBA : STA.b $09
  LDA.w .w,X : STA.b $02
  LDA.w .h,X : STA.b $03
  RTS

  ; per direction: punch, then sword (the blade's reach)
  .dx : dw 0, 0,     0, 0,     -12, -20,   12, 12
  .dy : dw -8, -18,  20, 20,   8, 8,       8, 8
  .w  : dw 16, 16,   16, 16,   16, 24,     16, 24
  .h  : dw 16, 24,   16, 24,   16, 16,     16, 16
}

; P2's body box, same layout: 12x16 at the feet half of the sprite.

P2_SetBodyBox:
{
  REP #$20
  LDA.l P2_X : CLC : ADC.w #$0002
  SEP #$20
  STA.b $00 : XBA : STA.b $08
  REP #$20
  LDA.l P2_Y : CLC : ADC.w #$0008
  SEP #$20
  STA.b $01 : XBA : STA.b $09
  LDA.b #$0C : STA.b $02
  LDA.b #$10 : STA.b $03
  RTS
}

; =========================================================
; Drops P2 touches go to the shared inventory, through the same routine that
; collects them for Link: hearts, rupees, bombs, magic, arrows, fairy, small
; key ($D8-$E4). Honors the vanilla pickup delay ($0F10).

P2_Pickups:
{
  LDA.l P2_HopZ : BNE .done                    ; airborne
  LDX.b #$0F
  .next_sprite
    LDA.w SprState,X : BEQ .skip
    LDA.w $0E20,X : CMP.b #$D8 : BCC .skip
                    CMP.b #$E5 : BCS .skip
    LDA.w $0F10,X : BNE .skip
    PHX
    JSR P2_SetBodyBox
    PLX : PHX
    JSL !P2_SetupHitbox
    JSL !P2_Overlap
    PLX
    BCC .skip
      PHX
      JSL !P2_Absorb
      PLX
  .skip
  DEX : BPL .next_sprite
  .done
  RTS
}

; =========================================================
; Damage (shared hearts). Every harmful enemy asks Sprite_CheckDamageToLink
; ($06F145) whether it touched the player; P2_ContactGate runs where that
; routine has just tested Link ($06F16F, carry = overlap). If Link was not
; touched but P2 was, the hit costs the shared hearts through Link's pending
; damage byte $0373 (vanilla amount, Sprite_BumpDamageGroups by the sprite's
; class and P1's armor), so the hurt sound, heart loss and game over are
; vanilla's. Link_ControlHandler also starts Link's own blink frames.
; P2 gets knockback away from the enemy and 58 frames of blinking. An enemy
; touching both players in one frame hurts Link only (the hearts are shared).
; Entry: JSL from $06F16F, X = sprite slot, A/X/Y 8-bit, DB = $06.

P2_ContactGate:
{
  LDA.w $0E40,X : BPL .damage_check            ; bit 7: contact test only
    PLA : PLA : PLA                            ; drop this JSL's return
    JML !P2_ContactExit                        ; RTS, carry = overlap
  .damage_check
  BCS .link_hit                                ; vanilla hurts Link
  PHB : PHK : PLB
  JSR P2_TryHurt
  PLB
  CLC                                          ; no damage to Link
  .link_hit
  RTL
}

P2_TryHurt:
{
  JSR P2_IsJoined : BCS .joined
  .no
  RTS
  .joined
  LDA.l P2_Flags : AND.b #$02 : BNE .no        ; not placed
  LDA.l P2_HurtTimer : BNE .no
  LDA.l P2_HopZ : BNE .no
  LDA.w $0F20,X : CMP.b $EE : BNE .no
  PHX
  JSR P2_SetBodyBox
  PLX : PHX
  JSL !P2_SetupHitbox
  JSL !P2_Overlap
  PLX
  BCC .no

  LDA.w $037B : BNE .no_hearts                 ; Link can't be hurt right now
    LDA.w $0CD2,X : AND.b #$0F : STA.b $00
    ASL : ADC.b $00 : CLC : ADC.l $7EF35B
    PHX : TAX
    LDA.l !P2_BumpDamage,X
    PLX
    CLC : ADC.w $0373 : STA.w $0373
  .no_hearts

  ; knock P2 away from the enemy along the axis it is further off on
  LDA.w $0D10,X : STA.b $00 : LDA.w $0D30,X : STA.b $01
  LDA.w $0D00,X : STA.b $02 : LDA.w $0D20,X : STA.b $03
  REP #$20
  LDA.l P2_X : SEC : SBC.b $00 : STA.b $04     ; dx = P2 - enemy
  BPL .dx_abs
    EOR.w #$FFFF : INC
  .dx_abs
  STA.b $06
  LDA.l P2_Y : SEC : SBC.b $02 : STA.b $08     ; dy
  BPL .dy_abs
    EOR.w #$FFFF : INC
  .dy_abs
  CMP.b $06
  SEP #$20
  BCC .horizontal
    LDA.b $09 : BMI .push_up
    LDA.b #$01 : BRA .set_dir
    .push_up
    LDA.b #$00 : BRA .set_dir
  .horizontal
    LDA.b $05 : BMI .push_left
    LDA.b #$03 : BRA .set_dir
    .push_left
    LDA.b #$02
  .set_dir
  STA.l P2_RecoilDir
  LDA.b #$3A : STA.l P2_HurtTimer
  LDA.b #$08 : STA.l P2_RecoilTimer
  LDA.b #$00 : STA.l P2_AttackTimer
  RTS
}

; Knockback: 8 frames at 2 px, stopped by walls. Also counts down the blink.
; Out: carry set = being knocked back (no walking or attacking).

P2_UpdateRecoil:
{
  LDA.l P2_HurtTimer : BEQ .no_blink
    DEC : STA.l P2_HurtTimer
  .no_blink
  LDA.l P2_RecoilTimer : BNE .recoiling
  CLC
  RTS
  .recoiling
  DEC : STA.l P2_RecoilTimer
  LDA.l P2_RecoilDir : STA.l P2_MoveDir
  ASL : TAX
  REP #$20
  LDA.l P2_X : CLC : ADC.w .dx,X : STA.b $08
  LDA.l P2_Y : CLC : ADC.w .dy,X : STA.b $0A
  SEP #$20
  LDA.l P2_MoveDir : JSR P2_ProbeSolid : BCS .blocked
    REP #$20
    LDA.b $08 : STA.l P2_X
    LDA.b $0A : STA.l P2_Y
    SEP #$20
  .blocked
  SEC
  RTS

  .dx : dw 0, 0, -2, 2
  .dy : dw -2, 2, 0, 0
}

; =========================================================
; P2's tiles. P2 draws with Link's own palette row, so it never touches CGRAM
; (a borrowed row recoloured vanilla's lifted pots, bushes, the bed and some
; NPCs). Its tunic colour comes from the tile data instead: the poses are
; copied from P1's current Link GFX bank ($BC, so P2 takes P1's form: GBC in
; the Abyss, masks) into P2_GfxBuf, and tunic colour indices are rewritten to
; row-7 colours every mail shares. Only a half whose source changed is rebuilt.

P2_PrepareGfx:
{
  JSR P2_TunicVariant : STA.b $0F
  LDA.b $BC : STA.b $0E
  REP #$30
  LDA.b $0E : CMP.l P2_BufKey : BEQ .same_key   ; bank or variant changed:
    STA.l P2_BufKey                               ; rebuild both halves
    LDA.w #$FFFF : STA.l P2_BufHead : STA.l P2_BufBody
  .same_key
  LDA.l P2_Pose2 : TAX
  LDA.l !P2_HeadGfx,X : CMP.l P2_BufHead : BEQ .head_ready
    STA.l P2_BufHead
    STA.b $00 : LDY.w #$0000 : JSR P2_BuildHalf
  .head_ready
  LDA.l P2_Pose2 : TAX
  LDA.l !P2_BodyGfx,X : CMP.l P2_BufBody : BEQ .body_ready
    STA.l P2_BufBody
    STA.b $00 : LDY.w #$0080 : JSR P2_BuildHalf
  .body_ready
  SEP #$30
  RTS
}

; Out: A = tunic variant: 0 none (other forms keep P1's colours), 1 red,
; 2 blue (P1 in red mail), 3 GBC red, 4 GBC gold (P1 in red mail).

P2_TunicVariant:
{
  LDA.b $BC
  CMP.b #$10 : BEQ .mail
  CMP.b #$39 : BEQ .mail                       ; Minish uses Link's mail palette
  CMP.b #$3B : BEQ .gbc
  LDA.b #$00
  RTS
  .mail
  LDA.l $7EF35B : CMP.b #$02 : BEQ .blue
  LDA.b #$01
  RTS
  .blue
  LDA.b #$02
  RTS
  .gbc
  LDA.l $7EF35B : CMP.b #$02 : BEQ .gold
  LDA.b #$03
  RTS
  .gold
  LDA.b #$04
  RTS
}

; Copy one 16x16 half (top row at src, bottom row at src+$200) from bank $BC
; into P2_GfxBuf+Y, then recolour it.
; In: A/X/Y 16-bit, $00 = source address, Y = buffer offset ($00 head,
; $80 body), $0F = tunic variant. Clobbers $00-$0E.

P2_BuildHalf:
{
  STY.b $0C
  TYX
  SEP #$20
  LDA.b $BC : STA.b $02
  REP #$20
  LDY.w #$0000
  - LDA [$00],Y : STA.l P2_GfxBuf,X
    INX #2 : INY #2 : CPY.w #$0040 : BCC -
  LDA.b $00 : CLC : ADC.w #$0200 : STA.b $00
  LDY.w #$0000
  - LDA [$00],Y : STA.l P2_GfxBuf,X
    INX #2 : INY #2 : CPY.w #$0040 : BCC -

  LDA.b $0F : AND.w #$00FF : BNE .recolour
    RTS                                        ; variant 0: plain copy
  .recolour
  DEC : ASL #4 : TAY                           ; selector rows for this variant
  LDX.b $0C
  .row
    ; 4bpp row: planes 0/1 at +0/+1, planes 2/3 at +16/+17. Tunic indices
    ; 9-12 all have plane 3 set, so rows without it are skipped.
    SEP #$20
    LDA.l P2_GfxBuf+17,X : BNE .has_plane3
      JMP .next_row
    .has_plane3
    STA.b $03
    LDA.l P2_GfxBuf+16,X : STA.b $02
    LDA.l P2_GfxBuf+1,X : STA.b $01
    LDA.l P2_GfxBuf,X : STA.b $00
    LDA.b $02 : EOR.b #$FF : AND.b $03 : STA.b $0A   ; q   = p3 & ~p2
    LDA.b $01 : EOR.b #$FF : AND.b $00 : AND.b $0A : STA.b $04 ; m9  (1001)
    LDA.b $00 : EOR.b #$FF : AND.b $01 : AND.b $0A : STA.b $05 ; m10 (1010)
    LDA.b $00 : AND.b $01 : AND.b $0A : STA.b $06            ; m11 (1011)
    LDA.b $00 : ORA.b $01 : EOR.b #$FF : AND.b $02 : AND.b $03 : STA.b $07 ; m12 (1100)
    ORA.b $04 : ORA.b $05 : ORA.b $06
    BNE .has_tunic
      JMP .next_row
    .has_tunic
    EOR.b #$FF : STA.b $08                     ; ~(any tunic pixel)

    LDA.b $04 : AND.w .sel+0,Y : STA.b $0E     ; plane 0
    LDA.b $05 : AND.w .sel+1,Y : TSB.b $0E
    LDA.b $06 : AND.w .sel+2,Y : TSB.b $0E
    LDA.b $07 : AND.w .sel+3,Y : TSB.b $0E
    LDA.b $00 : AND.b $08 : ORA.b $0E : STA.l P2_GfxBuf,X

    LDA.b $04 : AND.w .sel+4,Y : STA.b $0E     ; plane 1
    LDA.b $05 : AND.w .sel+5,Y : TSB.b $0E
    LDA.b $06 : AND.w .sel+6,Y : TSB.b $0E
    LDA.b $07 : AND.w .sel+7,Y : TSB.b $0E
    LDA.b $01 : AND.b $08 : ORA.b $0E : STA.l P2_GfxBuf+1,X

    LDA.b $04 : AND.w .sel+8,Y : STA.b $0E     ; plane 2
    LDA.b $05 : AND.w .sel+9,Y : TSB.b $0E
    LDA.b $06 : AND.w .sel+10,Y : TSB.b $0E
    LDA.b $07 : AND.w .sel+11,Y : TSB.b $0E
    LDA.b $02 : AND.b $08 : ORA.b $0E : STA.l P2_GfxBuf+16,X

    LDA.b $04 : AND.w .sel+12,Y : STA.b $0E    ; plane 3
    LDA.b $05 : AND.w .sel+13,Y : TSB.b $0E
    LDA.b $06 : AND.w .sel+14,Y : TSB.b $0E
    LDA.b $07 : AND.w .sel+15,Y : TSB.b $0E
    LDA.b $03 : AND.b $08 : ORA.b $0E : STA.l P2_GfxBuf+17,X

    .next_row
    REP #$20
    INX #2
    TXA : SEC : SBC.b $0C : AND.w #$0010 : BEQ .same_tile
      TXA : CLC : ADC.w #$0010 : TAX           ; skip the plane 2/3 half
    .same_tile
    TXA : SEC : SBC.b $0C : CMP.w #$0080 : BCS .done
    JMP .row
  .done
  RTS

  ; Target bit k of the new index for source indices 9, 10, 11, 12:
  ; 4 planes x 4 sources per variant ($FF = bit set).
  .sel
  ; 1 red: 9->5 dark, 10->6 tan, 11->14 brown, 12->7 red
  db $FF,$00,$00,$FF,  $00,$FF,$FF,$FF,  $FF,$FF,$FF,$FF,  $00,$00,$FF,$00
  ; 2 blue: 9->5 dark, 10->15 lavender, 11->8 blue, 12->8 blue
  db $FF,$FF,$00,$00,  $00,$FF,$00,$00,  $FF,$FF,$00,$00,  $00,$FF,$FF,$FF
  ; 3 GBC red: 9->7 red, others unchanged
  db $FF,$00,$FF,$00,  $FF,$FF,$FF,$00,  $FF,$00,$00,$FF,  $00,$FF,$FF,$FF
  ; 4 GBC gold: 9->2 gold, others unchanged
  db $00,$00,$FF,$00,  $FF,$FF,$FF,$00,  $00,$00,$00,$FF,  $00,$FF,$FF,$FF
}

; =========================================================
; Out: carry set = a vanilla user owns one of P2's shared OBJ tile slots.

P2_SlotsBusy:
{
  LDA.w $0AF4 : BNE .busy                      ; flute bird (head slot)
  LDX.b #$09
  - LDA.w $0C4A,X
    CMP.b #$1F : BEQ .busy                     ; hookshot/goldstar (head slot)
    CMP.b #$22 : BEQ .busy                     ; item receipt (body slot)
    DEX : BPL -
  LDX.b #$0F
  - LDA.w SprState,X : BEQ .next_sprite
      LDA.w $0E20,X
      CMP.b #$EA : BEQ .busy                   ; heart container item GFX
      CMP.b #$E7 : BEQ .busy                   ; mushroom item GFX (OW $00/$40)
    .next_sprite
    DEX : BPL -
  CLC
  RTS
  .busy
  SEC
  RTS
}

; =========================================================
; Head + body OAM entries, laid out like LinkOAM_DrawPose, and the DMA
; request for this frame's pose.

P2_Draw:
{
  JSR P2_IsJoined : BCS .joined
  .skip
  RTS
  .joined
  LDA.l P2_Flags : AND.b #$02 : BNE .skip      ; respawn pending
  ; Module $0E (text box, item menu scroll): Module0E_Interface runs
  ; Sprite_Main and LinkOAM_Main together ($00F82A), so P2 stays drawn,
  ; frozen, exactly while Link is (hidden during the maps, like Link).
  LDA.b $10 : CMP.b #$07 : BEQ .module_ok
              CMP.b #$09 : BEQ .module_ok
              CMP.b #$0E : BNE .skip
  .module_ok
  LDA.l P2_HurtTimer : AND.b #$02 : BNE .skip  ; blink after a hit
  JSR P2_SlotsBusy : BCS .skip

  ; 4 entries (head, body, shadow left, shadow right), 6 with the blade.
  ; Layered rooms ($0FB3) use regions D/F by floor layer, like
  ; Sprite_TimersAndOAM; otherwise Y-sort against Link: A (in front) when
  ; P2 stands lower, else B.
  LDA.b #$10 : STA.b $0C
  JSR P2_SwordVisible : BCC .size_ready
    LDA.b #$18 : STA.b $0C
  .size_ready
  LDA.w $0FB3 : BEQ .y_sort
    LDA.b $0C
    LDY.b $EE : BEQ .lower_layer
      JSL OAM_AllocateFromRegionF
      BRA .allocated
    .lower_layer
      JSL OAM_AllocateFromRegionD
      BRA .allocated
  .y_sort
  ; carrying or throwing: region B, so the object (region A, drawn after P2)
  ; stays in front of P2 as Link's carried object stays in front of Link
  LDA.l P2_Held : ORA.l P2_ThrowTimer : BEQ .sort_by_y
    LDA.b $0C
    BRA .behind
  .sort_by_y
  REP #$20
  LDA.l P2_Y : CMP.b $20
  SEP #$20
  LDA.b $0C
  BCC .behind
    JSL OAM_AllocateFromRegionA
    BRA .allocated
  .behind
    JSL OAM_AllocateFromRegionB
  .allocated

  JSR P2_PoseStep                              ; REP #$30, A = animation step
  ASL : TAX
  LDA.l !P2_AnimSteps,X                        ; pose
  AND.w #$00FF : STA.b $0C
  ASL : STA.l P2_Pose2
  CLC : ADC.b $0C : TAX                        ; pose * 3
  SEP #$20
  LDA.l !P2_PoseData+0,X : STA.b $0A           ; head Y offset
  LDA.l !P2_PoseData+1,X : STA.b $0B           ; head X offset
  LDA.l !P2_PoseData+2,X : STA.b $04           ; flips: head high, body low
  SEP #$30

  ; priority from Link's layer, palette bits from Link's ($0346 high byte:
  ; row 7, or row 0 in colour-math rooms); the tunic colour is in the tiles
  LDA.b $EE : AND.b #$03 : ASL : TAX
  LDA.l !P2_Priority+1,X : STA.b $05
  LDA.w $0347 : AND.b #$0E : TSB.b $05

  REP #$20
  LDA.l P2_X : SEC : SBC.b $E2 : STA.b $06
  LDA.l P2_HopZ : AND.w #$00FF : STA.b $0C
  LDA.l P2_Y : SEC : SBC.b $E8 : SEC : SBC.b $0C : STA.b $08

  ; blade pieces first (in front of P2), then head, body, shadow
  SEP #$20
  LDY.b #$00
  JSR P2_SwordVisible : BCC .no_sword
    JSR P2_DrawSword
  .no_sword
  REP #$20

  ; head at (X + head X, Y + head Y)
  LDA.b $0B : AND.w #$00FF : CMP.w #$0080 : BCC .dx_positive
    ORA.w #$FF00
  .dx_positive
  CLC : ADC.b $06 : STA.b $00
  LDA.b $0A : AND.w #$00FF : CMP.w #$0080 : BCC .dy_positive
    ORA.w #$FF00
  .dy_positive
  CLC : ADC.b $08 : STA.b $02
  SEP #$20
  LDA.b $04 : AND.b #$F0 : ORA.b $05 : STA.b $0E
  LDA.b #$02 : STA.b $0D                       ; 16x16
  LDA.b #!P2_HEAD_CHR
  JSR P2_WriteEntry

  ; body at (X, Y + 8)
  REP #$20
  LDA.b $06 : STA.b $00
  LDA.b $08 : CLC : ADC.w #$0008 : STA.b $02
  SEP #$20
  LDA.b $04 : ASL #4 : ORA.b $05 : STA.b $0E
  LDA.b #!P2_BODY_CHR
  JSR P2_WriteEntry

  ; shadow: Link's two 8x8 halves at the feet (LinkOAM_ShadowTiles $0D85CF),
  ; on the ground during a hop; palette 4, or 3 while Link uses palette 0
  LDA.l P2_Dir : TAX
  REP #$20
  LDA.w .shadow_dx,X : AND.w #$00FF : CMP.w #$0080 : BCC .shadow_dx_positive
    ORA.w #$FF00
  .shadow_dx_positive
  CLC : ADC.b $06 : STA.b $00
  LDA.w .shadow_dy,X : AND.w #$00FF
  CLC : ADC.l P2_Y : SEC : SBC.b $E8 : STA.b $02
  SEP #$20
  LDA.b $05 : AND.b #$30 : ORA.b #$08 : STA.b $0E
  LDA.w $0347 : BNE .shadow_palette_ok         ; $0346 = $0E00 unless palette 0
    LDA.b $0E : AND.b #$F1 : ORA.b #$06 : STA.b $0E
  .shadow_palette_ok
  STZ.b $0D                                    ; 8x8
  LDA.b #!P2_SHADOW_CHR
  JSR P2_WriteEntry
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0008 : STA.b $00
  SEP #$20
  LDA.b $0E : ORA.b #$40 : STA.b $0E           ; right half: h-flip
  LDA.b #!P2_SHADOW_CHR
  JSR P2_WriteEntry

  JSR P2_PrepareGfx
  LDA.l P2_Flags : ORA.b #$01 : STA.l P2_Flags
  RTS

  .shadow_dx : db 0, 0, -1, 1                  ; LinkOAM_ShadowOffset_X
  .shadow_dy : db 16, 16, 17, 17               ; LinkOAM_ShadowOffset_Y
}

; One OAM entry.
; In: A = tile, $00 = screen X (word), $02 = screen Y (word), $0E = attributes,
;     $0D = size bit ($02 16x16, $00 8x8),
;     Y = byte offset from the allocated ($90). Out: Y advanced by 4.

P2_WriteEntry:
{
  STA.b $0F
  REP #$20
  LDA.b $00 : CLC : ADC.w #$0100 : CMP.w #$0200 : BCS .hide   ; X in [-256, 256)
  LDA.b $02 : CLC : ADC.w #$0020 : CMP.w #$0100 : BCS .hide   ; Y in [-32, 224)
  SEP #$20
  LDA.b $00 : STA ($90),Y : INY
  LDA.b $02 : STA ($90),Y : INY
  LDA.b $0F : STA ($90),Y : INY
  LDA.b $0E : STA ($90),Y : INY
  LDA.b $01 : AND.b #$01 : ORA.b $0D          ; size, X bit 8
  BRA .high_table

  .hide
  SEP #$20
  LDA.b #$F0
  STA ($90),Y : INY
  STA ($90),Y : INY
  INY #2
  LDA.b #$00

  .high_table
  PHY
  PHA
  TYA : LSR #2 : DEC : TAY
  PLA : STA ($92),Y
  PLY
  RTS
}

; =========================================================
; NMI: DMA this frame's head and body rows from P2_GfxBuf into the shared
; OBJ tiles. Replaces LDX $0ADC : STX $4302 at $008B50
; (NMI_DoUpdates.no_update_swagduck), after every vanilla OBJ upload.
; Entry: A 8-bit, X/Y 16-bit, DB $00, VMAIN $80, DMA0 mode $1801.

P2_NmiUpload:
{
  REP #$20
  LDA.l P2_Magic : CMP.w #!P2_MAGIC            ; power-on WRAM is random
  SEP #$20
  BNE .done
  LDA.l P2_Flags : LSR : BCC .done
    ASL : STA.l P2_Flags                       ; clear bit 0
    LDA.b #P2_GfxBuf>>16 : STA.w $4304         ; source: P2_GfxBuf (WRAM)
    REP #$20

    LDA.w #!P2_HEAD_VRAM : STA.w $2116
    LDA.w #P2_GfxBuf+$00 : JSR .dma_row
    LDA.w #!P2_HEAD_VRAM+$0100 : STA.w $2116
    LDA.w #P2_GfxBuf+$40 : JSR .dma_row

    LDA.w #!P2_BODY_VRAM : STA.w $2116
    LDA.w #P2_GfxBuf+$80 : JSR .dma_row
    LDA.w #!P2_BODY_VRAM+$0100 : STA.w $2116
    LDA.w #P2_GfxBuf+$C0 : JSR .dma_row

    SEP #$20
    LDA.b #$7E : STA.w $4304                   ; vanilla's next DMA0 reads bank $7E

    ; blade art (bank $7E, P1's sword level) into the follower head tiles
    LDA.l P2_Flags : AND.b #$04 : BEQ .done
      LDA.l P2_Flags : AND.b #$FB : STA.l P2_Flags
      REP #$20
      LDA.w #!P2_SWORD_VRAM : STA.w $2116
      LDA.l P2_SwordSrc : JSR .dma_row
      LDA.w #!P2_SWORD_VRAM+$0100 : STA.w $2116
      LDA.l P2_SwordSrc : CLC : ADC.w #$0180 : JSR .dma_row
      SEP #$20
  .done
  LDX.w $0ADC : STX.w $4302                    ; replayed vanilla code
  RTL

  ; In: A (16-bit) = source address in P2_GfxBuf's bank. Two tiles, $40 bytes.
  .dma_row
  STA.w $4302
  LDA.w #$0040 : STA.w $4305
  SEP #$20
  LDA.b #$01 : STA.w $420B
  REP #$20
  RTS
}

assert pc() <= $3AFFFF, "native-2p-poc code overflows bank $3A"

; ---------------------------------------------------------
; Sword/PvP/lift block. Bank $3A: opening arrival owns $3AC000-$3ADFFF, Impa
; hints start at $3AE800 (Sprites/NPCs/impa_hints.asm), the main P2 block
; $3AF000-$3AFFFF.
org $3AE000

; Pick this swing's weapon: P1's sword (P2 is an equal second Link), or the
; punch when P1 has none or a follower holds the tile slot the blade uses.

P2_ChooseWeapon:
{
  LDA.b #$00 : STA.l P2_AttackSword
  LDA.b #!P2_DAMAGE_CLASS : STA.l P2_AttackClass
  LDA.l $7EF359 : BEQ .punch                   ; no sword
  CMP.b #$05 : BCS .punch                      ; not a sword level
  LDA.l $7EF3CC : BNE .punch                   ; follower's tiles in use
  LDA.l $7EF359 : STA.l P2_AttackClass         ; slash damage class = level
  LDA.b #$01 : STA.l P2_AttackSword
  .punch
  RTS
}

; Out: carry set = the blade is drawn this frame.

P2_SwordVisible:
{
  LDA.l P2_AttackTimer : BEQ .no
  LDA.l P2_AttackSword : BEQ .no
  SEC
  RTS
  .no
  CLC
  RTS
}

; Two 8x8 blade pieces for the current poke frame, placed and flipped the way
; LinkOAM draws Link's sword (LinkOAM_WeaponTiles: pieces at +0, +8 x, +8 y),
; with the tiles moved into the follower slot. Requests the art DMA.
; In: Y = OAM offset, $05 = P2 attributes (priority used), $06/$08 = P2 screen
; X/Y. Out: Y advanced by 8. Keeps $04-$0B.

P2_DrawSword:
{
  LDA.l P2_AttackTimer
  LDX.b #$00
  CMP.b #$0B : BCS .have_frame
  INX
  CMP.b #$04 : BCS .have_frame
  INX
  .have_frame
  STX.b $0C
  LDA.l P2_Dir : ASL : CLC : ADC.l P2_Dir : CLC : ADC.b $0C
  CLC : ADC.b #!P2_POKE_STEP : TAX             ; per-step table index

  ; art: vertical blade for up/down, horizontal for left/right
  REP #$20
  LDA.w #$9000 : STA.l P2_SwordSrc
  SEP #$20
  LDA.l P2_Dir : CMP.b #$02 : BCC .vertical
    REP #$20
    LDA.w #$91E0 : STA.l P2_SwordSrc
    SEP #$20
  .vertical

  ; blade origin = P2 screen position + LinkOAM_Sword offsets
  LDA.l !P2_SwordOffX,X
  REP #$20
  AND.w #$00FF : CMP.w #$0080 : BCC .ox_positive
    ORA.w #$FF00
  .ox_positive
  CLC : ADC.b $06 : STA.l P2_SwordX
  SEP #$20
  LDA.l !P2_SwordOffY,X
  REP #$20
  AND.w #$00FF : CMP.w #$0080 : BCC .oy_positive
    ORA.w #$FF00
  .oy_positive
  CLC : ADC.b $08 : STA.l P2_SwordY
  SEP #$20

  ; weapon tile set -> offset of its 3 words
  LDA.l !P2_WeaponIdx,X : STA.b $0C
  ASL : CLC : ADC.b $0C : ASL : STA.b $0C      ; set * 6
  LDX.b #$00                                   ; piece 0..2

  .piece
    PHX
    TXA : ASL : CLC : ADC.b $0C : TAX
    LDA.l !P2_WeaponTiles+1,X : STA.b $0E      ; attributes
    LDA.l !P2_WeaponTiles,X : STA.b $0F        ; tile
    PLX
    LDA.b $0E : CMP.b #$FF : BEQ .next_piece   ; empty piece ($FFFF)
    AND.b #$CF : STA.b $0E                     ; keep flips and palette 5,
    LDA.b $05 : AND.b #$30 : TSB.b $0E         ; take P2's priority
    REP #$20
    LDA.l P2_SwordX : STA.b $00
    LDA.l P2_SwordY : STA.b $02
    CPX.b #$01 : BNE .not_right
      LDA.b $00 : CLC : ADC.w #$0008 : STA.b $00
    .not_right
    CPX.b #$02 : BNE .not_below
      LDA.b $02 : CLC : ADC.w #$0008 : STA.b $02
    .not_below
    SEP #$20
    STZ.b $0D                                  ; 8x8
    LDA.b $0F : CLC : ADC.b #!P2_SWORD_CHR_ADD
    PHX
    JSR P2_WriteEntry
    PLX
    .next_piece
    INX : CPX.b #$03 : BCC .piece

  LDA.l P2_Flags : ORA.b #$04 : STA.l P2_Flags
  RTS
}

; =========================================================
; PvP: the two players' attacks knock each other back (no hearts; they are
; shared). P1's sword box is Link's attack point ($45/$44 from
; CalculateSwordHitbox, $44 = $80 when none) as a 16x16 square; P2's is its
; punch/sword box. Link is knocked back the way Sprite_AttemptDamageToLink-
; PlusRecoil does it (speed $18, hop $0C, $46 = $13, $4D = 1), only while he
; is in his normal state and not already recoiling or blinking.

P2_PvP:
{
  JSR P2_LinkHitsP2
  JMP P2_P2HitsLink
}

P2_LinkHitsP2:
{
  LDA.b $44 : CMP.b #$80 : BNE .attacking
  .no
  RTS
  .attacking
  LDA.l P2_HurtTimer : ORA.l P2_RecoilTimer : ORA.l P2_HopZ : BNE .no
  LDA.l P2_Flags : AND.b #$02 : BNE .no

  ; box A: Link's attack point
  LDA.b $45
  REP #$20
  AND.w #$00FF : CMP.w #$0080 : BCC .x_positive
    ORA.w #$FF00
  .x_positive
  CLC : ADC.b $22
  SEP #$20
  STA.b $00 : XBA : STA.b $08
  LDA.b $44
  REP #$20
  AND.w #$00FF : CMP.w #$0080 : BCC .y_positive
    ORA.w #$FF00
  .y_positive
  CLC : ADC.b $20
  SEP #$20
  STA.b $01 : XBA : STA.b $09
  LDA.b #$10 : STA.b $02 : STA.b $03

  ; box B: P2's body (12x16 at the feet half)
  REP #$20
  LDA.l P2_X : CLC : ADC.w #$0002
  SEP #$20
  STA.b $04 : XBA : STA.b $0A
  REP #$20
  LDA.l P2_Y : CLC : ADC.w #$0008
  SEP #$20
  STA.b $05 : XBA : STA.b $0B
  LDA.b #$0C : STA.b $06
  LDA.b #$10 : STA.b $07
  JSL !P2_Overlap : BCC .no

  LDA.b $2F : LSR : STA.l P2_RecoilDir         ; along Link's facing
  LDA.b #$08 : STA.l P2_RecoilTimer
  LDA.b #$20 : STA.l P2_HurtTimer              ; brief blink, no repeat hits
  LDA.b #$00 : STA.l P2_AttackTimer
  LDA.b #!P2_SFX_BONK : STA.w $012E
  RTS
}

P2_P2HitsLink:
{
  LDA.l P2_AttackTimer : CMP.b #$0B : BCS .no  ; thrust frames only
                         CMP.b #$04 : BCC .no
  LDA.l P2_HitLink : BNE .no                   ; once per swing
  LDA.b $5D : BNE .no                          ; Link busy (not default state)
  LDA.b $4D : ORA.w $031F : ORA.w $037B : BNE .no

  JSR P2_SetPunchBox                           ; box A: P2's attack
  ; box B: Link's hurtbox (Link_SetupHitBox $06F70A: 8x8 at X+4, Y+8)
  REP #$20
  LDA.b $22 : CLC : ADC.w #$0004
  SEP #$20
  STA.b $04 : XBA : STA.b $0A
  REP #$20
  LDA.b $20 : CLC : ADC.w #$0008
  SEP #$20
  STA.b $05 : XBA : STA.b $0B
  LDA.b #$08 : STA.b $06 : STA.b $07
  JSL !P2_Overlap : BCC .no

  LDA.b #$01 : STA.l P2_HitLink
  LDA.l P2_Dir : TAX
  LDA.w .recoil_y,X : STA.b $27
  LDA.w .recoil_x,X : STA.b $28
  LDA.b #$0C : STA.b $29 : STA.b $C7
  STZ.b $24 : STZ.b $25
  LDA.b #$13 : STA.b $46
  LDA.b #$01 : STA.b $4D
  LDA.b #!P2_SFX_BONK : STA.w $012E
  .no
  RTS

  .recoil_y : db $E8, $18, $00, $00
  .recoil_x : db $00, $00, $E8, $18
}

; =========================================================
; Lift, carry, throw. A lifts the bush, pot, sign or small rock in front of
; P2; A or B throws it. P2 uses vanilla's own routines: the tile is removed by
; Overworld_HandleLiftableTiles / Underworld_LiftAndReplaceLiftable (with any
; secret under it), and the object is the vanilla thrown-object sprite ($EC)
; from Sprite_SpawnThrowableTerrain. P2 then keeps that sprite in its active
; state ($09) with zero speed and places it over its head every frame
; (SpriteModule_Carried, state $0A, would snap it to Link). Thrown, the
; sprite flies, breaks and hurts enemies exactly as when Link throws it.
; Out: carry set = lifting or in the throw pose (P2 stands still).

P2_UpdateLift:
{
  LDA.l P2_LiftTimer : BEQ .not_lifting
    DEC : STA.l P2_LiftTimer
    SEC
    RTS
  .not_lifting
  LDA.l P2_ThrowTimer : BEQ .not_throwing
    DEC : STA.l P2_ThrowTimer
    SEC
    RTS
  .not_throwing
  LDA.l P2_Held : BEQ .empty_hands
    LDA.l P2_NewLo : ORA.l P2_NewHi : BPL .carry_on   ; A or B
      JSR P2_Throw
      SEC
      RTS
    .carry_on
    CLC
    RTS
  .empty_hands
  LDA.l P2_NewLo : BPL .no_lift                ; A
    JSR P2_TryLift
    LDA.l P2_LiftTimer : BEQ .no_lift
      SEC
      RTS
  .no_lift
  CLC
  RTS
}

; Vanilla's lift routines read Link's position and facing ($20/$22/$2F), so
; P2's are swapped in around the calls, with DB = $07 as from
; Link_PerformThrow ($07B11C). The tile is only removed once the checks pass
; and a sprite slot is free. As in vanilla, a secret under the tile can take
; that last slot, and then there is no object to carry.

P2_TryLift:
{
  LDX.b #$0F
  .find_slot
    LDA.w $0DD0,X : BEQ .slot_free
    DEX : BPL .find_slot
  RTS
  .slot_free

  REP #$20
  LDA.b $20 : STA.l P2_SaveY
  LDA.b $22 : STA.l P2_SaveX
  LDA.l P2_Y : STA.b $20
  LDA.l P2_X : STA.b $22
  SEP #$20
  LDA.b $2F : STA.l P2_Save2F
  LDA.l P2_Dir : ASL : STA.b $2F

  PHB
  LDA.b #$07 : PHA : PLB
  JSR P2_CanLiftHere : BCC .restore
  LDA.b $1B : BEQ .outdoors
    JSL !P2_LiftUW                             ; A = tile type, $00-$03 = X/Y
    BRA .removed
  .outdoors
    JSL !P2_LiftOW
  .removed
  SEC
  .restore
  PLB
  PHP : PHA
  REP #$20
  LDA.l P2_SaveY : STA.b $20
  LDA.l P2_SaveX : STA.b $22
  SEP #$20
  LDA.l P2_Save2F : STA.b $2F
  PLA : PLP
  BCS .spawn
  RTS

  .spawn
  ; tile type -> thrown-object kind, as Link_PerformThrow
  LDX.b #$08
  .next_kind
    CMP.l !P2_TossKinds,X : BEQ .kind
    DEX : BPL .next_kind
  RTS
  .kind
  LDA.b #!P2_SFX_LIFT : STA.w $012E
  TXA
  JSR P2_SpawnHeld : BCC .done
  LDA.b #!P2_LIFT_FRAMES : STA.l P2_LiftTimer
  LDA.b #$00 : STA.l P2_Step : STA.l P2_StepTimer
  .done
  RTS
}

; Spawn the vanilla thrown-object sprite and make it P2's.
; In: A = kind, $00-$03 = X/Y. Out: carry set = P2 holds it (X = slot).

P2_SpawnHeld:
{
  TAY                                          ; kind
  LDA.w $0314 : PHA                            ; the spawn writes Link's "sprite in
  LDA.w $0FB2 : PHA                            ; reach" bytes; keep Link's
  PHB
  LDA.b #$07 : PHA : PLB                       ; as from Link_PerformThrow
  TYA
  JSL !P2_SpawnTerrain                         ; X = new slot
  PLB
  PLA : STA.w $0FB2
  PLA : STA.w $0314
  TXA : BPL .spawned
    CLC
    RTS
  .spawned
  INC : STA.l P2_Held
  LDA.w $0DB0,X : INC : STA.l P2_CarryKind
  LDA.b #$09 : STA.w $0DD0,X                   ; active, not "carried by Link" ($0A)
  LDA.b #$00
  STA.l $7FFA1C,X
  STA.w $0D50,X : STA.w $0D40,X : STA.w $0F80,X
  LDA.w $0E60,X : AND.b #$10 : STA.l P2_HeldProp
  LDA.w $0E60,X : AND.b #$EF : STA.w $0E60,X   ; as SpriteModule_Carried .lifted
  SEC
  RTS
}

; A room or area load deletes every sprite (Sprite_DisableAll), and a hidden
; P2 can't hold anything, so the carried object waits as P2_CarryKind and
; P2_Unstash brings a copy back overhead once P2 stands beside Link again.

P2_Stash:
{
  JSR P2_HeldSlot : BCC .gone
    LDA.b #$00 : STA.w $0DD0,X                 ; still alive: remove it
  .gone
  LDA.b #$00 : STA.l P2_Held : STA.l P2_LiftTimer
  RTS
}

P2_Unstash:
{
  LDA.l P2_CarryKind : BEQ .done
  JSR P2_HeldSlot : BCS .done                  ; still carried (regroup, warp)
  LDA.w $0B9C : PHA
  LDA.b #$FF : STA.w $0B9C                     ; no secret spawns with the copy
  REP #$20
  LDA.l P2_X : STA.b $00
  LDA.l P2_Y : STA.b $02
  SEP #$20
  LDA.l P2_CarryKind : DEC
  JSR P2_SpawnHeld
  PLA : STA.w $0B9C
  BCS .done
    LDA.b #$00 : STA.l P2_CarryKind            ; no free sprite slot: lost
  .done
  RTS
}

; Runs with P2 swapped into $20/$22/$2F and DB = $07 (long addressing only).
; Out: carry set = the tile in front can be lifted: a bush, a pot, a sign
; (not while facing up: that reads it) or a small rock P1's gloves can lift.
; Big rocks are skipped (Link's heavy lift path).

P2_CanLiftHere:
{
  LDA.b $1B : BEQ .outdoors
    JSL !P2_IdentifyUW : BCC .no               ; A = liftable tile type
    BRA .check_type
  .outdoors
    LDA.l P2_Dir : ASL : TAX
    REP #$20
    LDA.l !P2_LiftOffY,X : CLC : ADC.b $20 : STA.b $00
    LDA.l !P2_LiftOffX,X : CLC : ADC.b $22 : STA.b $02
    SEP #$20
    LDA.b $EE
    JSL Sprite_GetTileAttr                     ; A = tile type, exits SEP #$30
    CMP.b #$54 : BNE .check_type
    LDA.l P2_Dir : BEQ .no
    LDA.b #$54
  .check_type
  CMP.b #$50 : BCC .no
  CMP.b #$55 : BCS .no                         ; $55/$56: big rocks
  AND.b #$0F : TAX
  LDA.l !P2_LiftableID,X : TAX
  LDA.l !P2_GloveLevel,X
  SEC : SBC.l $7EF354 : BEQ .yes
  BPL .no                                      ; heavier than P1's gloves allow
  .yes
  SEC
  RTS
  .no
  CLC
  RTS
}

; Keeps the carried object over P2's head with SpriteModule_Carried's
; offsets (P2_Tick runs before the sprites, so it draws where P2 is now).
; Throws it when P2 is hit, like Link's forced throw; lets go when it is gone
; (P1 took it).

P2_HoldObject:
{
  JSR P2_HeldSlot : BCS .held
    LDA.b #$00 : STA.l P2_Held : STA.l P2_LiftTimer : STA.l P2_CarryKind
    RTS
  .held
  LDA.l P2_RecoilTimer : BEQ .keep
    JSR P2_Throw
    LDA.b #$00 : STA.l P2_ThrowTimer
    RTS
  .keep
  STX.b $0F
  JSR P2_LiftStage : STA.b $0C                 ; 0-2 rising, 3 overhead
  LDA.l P2_Dir : ASL #2 : ORA.b $0C : TAX
  LDA.l !P2_CarryOffZ,X : CLC : ADC.l P2_HopZ
  BNE .z_ok
    INC                                        ; Z 0 counts as landed
  .z_ok
  STA.b $0D
  LDA.l !P2_CarryOffXLo,X : STA.b $00
  LDA.l !P2_CarryOffXHi,X : STA.b $01
  JSR P2_CarryFrame : TAX
  LDA.l !P2_CarryBobY,X : STA.b $02
  STZ.b $03
  LDX.b $0F
  REP #$20
  LDA.l P2_X : CLC : ADC.b $00 : STA.b $04
  LDA.l P2_Y : CLC : ADC.w #$0007 : SEC : SBC.b $02 : STA.b $06
  SEP #$20
  LDA.b $04 : STA.w $0D10,X
  LDA.b $05 : STA.w $0D30,X
  LDA.b $06 : STA.w $0D00,X
  LDA.b $07 : STA.w $0D20,X
  LDA.b $0D : STA.w $0F70,X
  LDA.b $EE : STA.w $0F20,X                    ; P2 shares Link's floor
  ; zero speed: ThrownSprite_CheckDamageToSprites skips it. $0F10 stays 0:
  ; if P1 takes it, SpriteModule_Carried reads $0F10 as an escape timer.
  LDA.b #$00 : STA.w $0D50,X : STA.w $0D40,X : STA.w $0F80,X
  STA.w $0F10,X
  STA.w $0E70,X                                ; no wall contact: a ricochet breaks it
  LDA.b #$01 : STA.w $0E90,X                   ; skip its tile collision while carried
  RTS
}

; Throw the carried object in P2's facing (CarriedSprite_CheckForThrow).

P2_Throw:
{
  JSR P2_HeldSlot : BCC .done
  LDA.w $0E60,X : AND.b #$EF : ORA.l P2_HeldProp : STA.w $0E60,X
  LDA.b #$00 : STA.l $7FFA1C,X : STA.w $0F10,X : STA.w $0E90,X
  PHX
  LDA.l P2_Dir : TAX
  LDA.l !P2_ThrowSpeedX,X : STA.b $00
  LDA.l !P2_ThrowSpeedY,X : STA.b $01
  LDA.l !P2_ThrowSpeedZ,X : STA.b $02
  PLX
  LDA.b $00 : STA.w $0D50,X
  LDA.b $01 : STA.w $0D40,X
  LDA.b $02 : STA.w $0F80,X
  LDA.b #!P2_SFX_THROW : STA.w $012F
  LDA.b #!P2_THROW_FRAMES : STA.l P2_ThrowTimer
  .done
  LDA.b #$00 : STA.l P2_Held : STA.l P2_LiftTimer : STA.l P2_CarryKind
  RTS
}

; Let go without throwing (leave): the object falls.

P2_Drop:
{
  JSR P2_HeldSlot : BCC .clear
    LDA.w $0E60,X : AND.b #$EF : ORA.l P2_HeldProp : STA.w $0E60,X
    LDA.b #$00 : STA.w $0F10,X : STA.w $0E90,X
  .clear
  LDA.b #$00
  STA.l P2_Held : STA.l P2_LiftTimer : STA.l P2_ThrowTimer : STA.l P2_CarryKind
  RTS
}

; Out: carry set = P2 carries a live thrown-object sprite, X = its slot.

P2_HeldSlot:
{
  LDA.l P2_Held : BEQ .no
  CMP.b #$11 : BCS .no
  DEC : TAX
  LDA.w $0E20,X : CMP.b #$EC : BNE .no
  LDA.w $0DD0,X : CMP.b #$09 : BNE .no
  SEC
  RTS
  .no
  CLC
  RTS
}

; Out: A = lift stage: 0 (16 frames), 1, 2 (4 frames each), 3 = overhead.

P2_LiftStage:
{
  LDA.l P2_LiftTimer
  LDY.b #$03 : CMP.b #$01 : BCC .done
  DEY : CMP.b #$05 : BCC .done
  DEY : CMP.b #$09 : BCC .done
  DEY
  .done
  TYA
  RTS
}

; Out: A = carrying-walk frame 0-5 for P2_Step (0 standing, 1-8 walking).

P2_CarryFrame:
{
  LDA.l P2_Step : TAX
  LDA.l .frame,X
  RTS

  .frame : db 0, 0, 0, 1, 2, 3, 3, 4, 5
}

; Out: REP #$30, A = index into LinkOAM_AnimationSteps for this frame's pose:
; lift, throw, sword poke, carrying walk, or walk.

P2_PoseStep:
{
  SEP #$30
  LDA.l P2_LiftTimer : BEQ .not_lifting
    JSR P2_LiftStage : STA.b $0C               ; timer running: 0-2
    JSR .dir3
    REP #$30 : AND.w #$00FF : CLC : ADC.w #!P2_LIFT_STEP
    RTS
  .not_lifting
  LDA.l P2_ThrowTimer : BEQ .not_throwing
    LDY.b #$00
    CMP.b #$07 : BCS .throw_frame
    INY
    CMP.b #$04 : BCS .throw_frame
    INY
    .throw_frame
    STY.b $0C
    JSR .dir6
    REP #$30 : AND.w #$00FF : CLC : ADC.w #!P2_THROW_STEP
    RTS
  .not_throwing
  LDA.l P2_AttackTimer : BEQ .not_attacking
    ; wind-up (timer $0B-$0F), thrust ($04-$0A), recover
    LDY.b #$00
    CMP.b #$0B : BCS .poke_frame
    INY
    CMP.b #$04 : BCS .poke_frame
    INY
    .poke_frame
    STY.b $0C
    JSR .dir3
    REP #$30 : AND.w #$00FF : CLC : ADC.w #!P2_POKE_STEP
    RTS
  .not_attacking
  LDA.l P2_Held : BEQ .walking
    JSR P2_CarryFrame : STA.b $0C
    JSR .dir6
    REP #$30 : AND.w #$00FF : CLC : ADC.w #!P2_CARRY_STEP
    RTS
  .walking
  LDA.l P2_Dir : ASL #3 : CLC : ADC.l P2_Dir : CLC : ADC.l P2_Step
  REP #$30 : AND.w #$00FF
  RTS

  .dir3                                        ; A = dir*3 + $0C
  LDA.l P2_Dir : ASL : CLC : ADC.l P2_Dir : CLC : ADC.b $0C
  RTS
  .dir6                                        ; A = dir*6 + $0C
  LDA.l P2_Dir : ASL : CLC : ADC.l P2_Dir : ASL : CLC : ADC.b $0C
  RTS
}

assert pc() <= $3AE800, "native-2p-poc sword/PvP/lift block runs into Impa hints at $3AE800"

incsrc "player2_hooks.asm"

endif
