; Reversible ferry prototype, ported from b617e7b0 (2026-10-30).
; Reuses current Module08 cached-exit contract, not historical STV2 storage.
; Default OFF; both endpoint caches/underlays remain explicitly unbound.
; No actor, entrance, saved state, graphics profile or whole-hull writer.
; Source review precedes build/native qualification of this composition.

assert !ENABLE_KALYXO_BOAT == 1
assert !ENABLE_CUTSCENE_FRAMEWORK == 1 && !ENABLE_ORACLE_ARRIVAL_SEQUENCE == 1

incsrc "Data/overworld/kalyxo_boat_placements.asm"

; Opening's current stream must finish before this conditional bounded slot.
assert pc() <= $3AD000, "Ferry overlaps opening/experiment stream"
org $3AD000
Boat_CodeStart:

; M8/X8, DBR=$02. Replaces LDA $0112 / ORA $02E4. Carry set means
; boarding took the submodule; the bank-$02 caller branches to its RTS.
Boat_BoardGate:
{
  PHP : REP #$30 : PHA : PHX : PHY
  PHB : PHK : PLB
  SEP #$20
  JSR Boat_TryBoard : BCC .native
    PLB : REP #$30 : PLY : PLX : PLA : PLP
    SEC : RTL
  .native
  PLB : REP #$30 : PLY : PLX : PLA : PLP
  LDA.w $0112 : ORA.w $02E4
  CLC : RTL
}

Boat_TryBoard:
{
if !KALYXO_BOAT_ENDPOINTS_BOUND == 0
  ; A prototype enable is not permission to use placeholder geography.
  CLC : RTS
else
  ; Reaching ordinary player control with our marker means another module
  ; interrupted the scene. No global freeze/input/visibility lock is owned.
  REP #$20
  LDA.l Boat_Marker : CMP.w #!Boat_Magic : BNE .no_stale_scene
    JSR Boat_Clear
  .no_stale_scene
  SEP #$20
  LDA.b $1B : BEQ +
  BRL .refuse
  +
  LDA.w $0112 : ORA.w $02E4 : ORA.w $0FFC : ORA.w $04C6 : BEQ +
  BRL .refuse
  +
  LDA.l FollowerId : BEQ +
  BRL .refuse
  +
  LDA.l SavedWorld : BEQ +
  BRL .refuse
  +
  LDA.b $5D : ORA.b $4B : ORA.b $4D : ORA.w $0308 : BEQ +
  BRL .refuse
  +
  LDA.b $F6 : AND.b #$80 : BNE + ; fresh A press, never held/replayed A
  BRL .refuse
  +
  LDY.w #$0000
  .endpoint
  REP #$20
  TYX
  LDA.l Boat_CacheOffsets, X : TAX
  LDA.l Boat_Caches+0, X : AND.w #$00FF
  STA.b $00
  LDA.b $8A : AND.w #$00FF : CMP.b $00 : BEQ +
  BRL .next
  +
  LDA.b $20 : SEC : SBC.l Boat_Caches+8, X
  CLC : ADC.w #7 : CMP.w #15 : BCC +
  BRL .next
  +
  LDA.b $22 : SEC : SBC.l Boat_Caches+10, X
  CLC : ADC.w #7 : CMP.w #15 : BCC +
  BRL .next
  +
  SEP #$20
  TYX
  LDA.l Boat_ArrivalFaces, X : EOR.b #$02
  CMP.b $2F : BEQ +
  BRL .next8
  +
  STA.l Boat_Face
  TYA : STA.l Boat_Endpoint
  LDA.b $10 : STA.l Boat_SourceModule
  REP #$20
  LDA.b $20 : STA.l Boat_SaveY
  LDA.b $22 : STA.l Boat_SaveX
  TYX
  LDA.l Boat_CacheOffsets, X : TAX
  LDA.l Boat_Caches+8, X : STA.b $20
  LDA.l Boat_Caches+10, X : STA.b $22
  ; Same Map16 transform as GetMap16Tile. Capture once before moving Link.
  LDA.b $20 : CLC : ADC.w #12 : SEC : SBC.w $0708
  AND.w $070A : ASL #3 : STA.b $06
  LDA.b $22 : CLC : ADC.w #8 : LSR #3
  SEC : SBC.w $070C : AND.w $070E : CLC : ADC.b $06
  STA.l Boat_PlankIndex : TAX
  LDA.l $7E2000, X : STA.l Boat_PlankTile
  TYX
  CMP.l Boat_OpenTiles, X : BEQ .underlay_matches
    ; Positions have only been snapped by at most7px; restore before refusal.
    LDA.l Boat_SaveY : STA.b $20
    LDA.l Boat_SaveX : STA.b $22
    SEP #$20
    BRL .refuse
  .underlay_matches
  LDA.w #!Boat_Magic : STA.l Boat_Marker
  LDA.w #$0000 : STA.l Boat_Timer : STA.l Boat_LoadTries
  SEP #$20
  LDA.b #$00 : STA.l Boat_PlankChanged
  LDA.b #$01 : STA.l Boat_State
  LDA.b #$0C : STA.b $10
  SEC : RTS
  .next
  SEP #$20
  .next8
  INY : INY : CPY.w #4 : BCS .refuse
  BRL .endpoint
  .refuse
  CLC : RTS
endif
}

; The existing arrival module dispatches here only with our marker. World
; AI and player input do not run while module $0C owns the scene.
Boat_Module:
{
  PHB : PHK : PLB
  SEP #$30
  LDA.l Boat_State : CMP.b #1 : BEQ .board
  CMP.b #2 : BEQ .depart
  CMP.b #3 : BEQ .load
  CMP.b #4 : BEQ .arrive
  JSR Boat_Cancel : BRA .done
  .board
  JSR Boat_Board : BRA .draw
  .depart
  JSR Boat_Depart : BRA .draw
  .load
  JSR Boat_Load : BRA .done
  .arrive
  JSR Boat_Arrive
  .draw
  JSL Arrival_LinkOAM_Main
  .done
  PLB : RTL
}

Boat_Board:
{
  LDA.b $F4 : AND.b #$80 : BEQ .move
    JMP Boat_Cancel
  .move
  LDA.l Boat_Face : STA.b $2F : LSR A : TAX
  LDA.l Boat_Directions, X : STA.b $26 : STA.b $67
  REP #$20
  TXA : ASL : TAX
  LDA.b $20 : CLC : ADC.l Boat_MoveY, X : STA.b $20
  LDA.b $22 : CLC : ADC.l Boat_MoveX, X : STA.b $22
  LDA.l Boat_Timer : INC A : STA.l Boat_Timer
  CMP.w #12
  SEP #$20
  BCC .animate
    ; One tile, one stripe: bounded well below a whole-hull live stamp.
    REP #$30
    LDA.l Boat_Endpoint : AND.w #$00FF : TAX
    LDA.l Boat_ClosedTiles, X : TAY
    LDA.l Boat_PlankIndex : TAX
    TYA ; existing endpoint terrain, restored exactly on cancellation
    JSL Overworld_DrawMap16_Persist
    SEP #$30
    INC.b $14
    LDA.b #$01 : STA.l Boat_PlankChanged
    LDA.b #$02 : STA.l Boat_State
    STZ.b $26
    RTS
  .animate
  JSL Link_HandleMovingAnimation_FullLongEntry
  RTS
}

Boat_Depart:
{
  LDA.b $F4 : AND.b #$80 : BEQ .fade
    JMP Boat_Cancel
  .fade
  LDA.b $13 : BEQ .cross
  DEC.b $13
  RTS
  .cross
  REP #$30
  LDA.l Boat_Endpoint : AND.w #$00FF : EOR.w #2 : TAX
  JSR Boat_CopyCache
  LDA.w #$0000 : STA.l Boat_LoadTries
  SEP #$30
  STZ.b $11 : STZ.b $B0
  LDA.b #$80 : STA.b $13
  LDA.b #$03 : STA.l Boat_State
  RTS
}

; Preserve Module08's frame schedule and normal loader/graphics ownership.
Boat_Load:
{
  LDA.b #$08 : STA.b $10
  PHB
  LDA.b #$00 : PHA : PLB
  JSL $0283BF
  PLB
  SEP #$30
  LDA.b $10 : CMP.b #$10 : BEQ .loaded
  LDA.b #$0C : STA.b $10
  REP #$20
  LDA.l Boat_LoadTries : INC A : STA.l Boat_LoadTries
  CMP.w #192
  SEP #$20
  BCC .wait
    ; Leave the cutscene and reload the valid source endpoint through the
    ; ordinary engine. No borrowed item, story bit or control lock remains.
    REP #$30
    LDA.l Boat_Endpoint : AND.w #$00FF : TAX
    JSR Boat_CopyCache
    LDA.w #$0000 : STA.l Boat_Marker
    SEP #$30
    STZ.b $11 : STZ.b $B0
    LDA.b #$08 : STA.b $10
  .wait
  RTS
  .loaded
  LDA.b #$0C : STA.b $10
  STZ.b $11 : STZ.b $B0 : STZ.b $4B
  STZ.b $26 : STZ.b $67
  REP #$30
  LDA.l Boat_Endpoint : AND.w #$00FF : EOR.w #2 : TAX
  SEP #$20
  LDA.l Boat_ArrivalFaces, X : STA.b $2F
  SEP #$10
  STZ.b $13
  LDA.b #$04 : STA.l Boat_State
  RTS
}

Boat_Arrive:
{
  LDA.b $13 : CMP.b #$0F : BCS .control
  INC.b $13
  RTS
  .control
  REP #$20
  LDA.w #$0000 : STA.l Boat_Marker
  SEP #$20
  LDA.b $8A : AND.b #$80 : BEQ .native
    LDA.b #$0B : BRA .module
  .native
  LDA.b #$09
  .module
  STA.b $10
  STZ.b $11 : STZ.b $B0 : STZ.b $26 : STZ.b $67
  RTS
}

Boat_Cancel:
{
  JSR Boat_RestorePlank
  REP #$20
  LDA.l Boat_SaveY : STA.b $20
  LDA.l Boat_SaveX : STA.b $22
  SEP #$20
  LDA.l Boat_SourceModule : STA.b $10
  LDA.b #$0F : STA.b $13
  STZ.b $26 : STZ.b $67
  JSR Boat_Clear
  RTS
}

Boat_RestorePlank:
{
  LDA.l Boat_PlankChanged : BEQ .done
  REP #$30
  LDA.l Boat_PlankIndex : TAX
  LDA.l Boat_PlankTile
  JSL Overworld_DrawMap16_Persist
  SEP #$30
  INC.b $14
  .done
  RTS
}

Boat_Clear:
{
  PHP : REP #$20
  LDA.w #$0000 : STA.l Boat_Marker
  PLP : RTS
}

; File-load/Continue may interrupt a scene. Clear transient ownership only;
; normal reload restores the saved map, art, collision and respawn policy.
Boat_ResetSession:
{
  PHP : REP #$20 : PHA
  JSR Boat_Clear
  PLA : PLP : RTL
}

; M16/X16, endpoint byte offset X=0 or2. Native $32-byte cache only.
; Clobbers A/X/Y; caller owns them. Scoped DBR7E copy restores DBR; DP is unchanged.
Boat_CopyCache:
{
  PHB
  SEP #$20
  LDA.b #$7E : PHA : PLB
  REP #$20
  LDA.l Boat_CacheOffsets, X : TAX
  LDY.w #$0000
  .copy
  LDA.l Boat_Caches, X : STA.w $C140, Y
  INX #2 : INY #2 : CPY.w #$0032 : BCC .copy
  LDA.w #!GoronCheckpoint_CacheRoom : STA.b $A0
  ; Same fresh-load flags as the existing cached-exit consumers.
  STZ.w $0696 : STZ.w $0698
  STZ.w $010A : STZ.w $04AA
  SEP #$20 : STZ.b $9B : REP #$20
  PLB
  RTS
}

%BoatNativePlacements()
Boat_CacheOffsets: dw $0000, $0032
Boat_MoveY: dw -1, 1, 0, 0
Boat_MoveX: dw 0, 0, -1, 1
Boat_Directions: db 8, 4, 2, 1
Boat_CodeEnd:
assert pc() <= $3AE000, "Ferry exceeds opening stream bound"

pushpc
; Six replaced bytes. The taken branch lands on the native bank-$02 RTS.
Boat_BoardReturn = $02A570
assert read1(Boat_BoardReturn) == $60, "Native boarding return must remain RTS"
assert read3($02A53C) == $0112AD && read3($02A53F) == $02E40D
org $02A53C ; @hook module=Overworld name=Boat_BoardGate kind=jsl target=Boat_BoardGate expected_m=8 expected_x=8
  JSL Boat_BoardGate
  BCS Boat_BoardReturn
assert pc() == $02A542
pullpc
