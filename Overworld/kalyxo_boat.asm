; =========================================================
; Kalyxo ferry: reversible dock event and ordinary exit-record transport.
; Author: Codex
; @source usdasm Module09_00_PlayerControl, Module08_OverworldLoad;
;         Core/Cutscene/experiment.asm's frame-by-frame loader contract.
; @verified UNKNOWN: private candidate qualification required.
;
; No quest bit, parked-boat bit, or island respawn rule. Both endpoints
; offer repeat service. The existing STV2 exit records own area, XY,
; camera and arrival facing. Boarding faces the opposite direction.
; =========================================================

assert !ENABLE_KALYXO_BOAT == 1
assert !ENABLE_SPECIAL_EXIT_TABLE_V2 == 1
assert !ENABLE_CUTSCENE_FRAMEWORK == 1 && !ENABLE_ORACLE_ARRIVAL_SEQUENCE == 1

!Boat_DocksExit = $0187
!Boat_IslandExit = $0186
!Boat_Magic = !BOAT_SCENE_MARKER

; Vanilla-free WRAM after the dream scene ($7FF370-$7FF37F), before 2P.
; Transient only. File-load cancellation never writes saved story state.
Boat_Marker = $7FF380             ; word
Boat_State = $7FF382
Boat_Endpoint = $7FF383           ; 0 docks, 2 island
Boat_Timer = $7FF384              ; word
Boat_SourceModule = $7FF386
Boat_PlankChanged = $7FF387
Boat_SaveY = $7FF388              ; word
Boat_SaveX = $7FF38A              ; word
Boat_PlankIndex = $7FF38C         ; word, Map16 buffer offset
Boat_PlankTile = $7FF38E          ; word, exact original tile
Boat_LoadTries = $7FF390          ; word
Boat_Face = $7FF393

pushpc
org $3AA000
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
  LDA.l Boat_ExitOffsets, X : TAX
  LDA.l STV2_ExitRecords+20, X : AND.w #$00FF
  CMP.b $8A : BEQ +
  BRL .next
  +
  LDA.b $20 : SEC : SBC.l STV2_ExitRecords+6, X
  CLC : ADC.w #7 : CMP.w #15 : BCC +
  BRL .next
  +
  LDA.b $22 : SEC : SBC.l STV2_ExitRecords+8, X
  CLC : ADC.w #7 : CMP.w #15 : BCC +
  BRL .next
  +
  SEP #$20
  LDA.l STV2_ExitRecords+23, X : EOR.b #$02
  CMP.b $2F : BEQ +
  BRL .next8
  +
  STA.l Boat_Face
  TYA : STA.l Boat_Endpoint
  LDA.b $10 : STA.l Boat_SourceModule
  REP #$20
  LDA.b $20 : STA.l Boat_SaveY
  LDA.b $22 : STA.l Boat_SaveX
  LDA.l STV2_ExitRecords+6, X : STA.b $20
  LDA.l STV2_ExitRecords+8, X : STA.b $22
  ; Same Map16 transform as GetMap16Tile. Capture once before moving Link.
  LDA.b $20 : CLC : ADC.w #12 : SEC : SBC.w $0708
  AND.w $070A : ASL #3 : STA.b $06
  LDA.b $22 : CLC : ADC.w #8 : LSR #3
  SEC : SBC.w $070C : AND.w $070E : CLC : ADC.b $06
  STA.l Boat_PlankIndex : TAX
  LDA.l $7E2000, X : STA.l Boat_PlankTile
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
  REP #$20
  LDA.l Boat_Endpoint : AND.w #$00FF : EOR.w #2 : TAX
  LDA.l Boat_ExitKeys, X : STA.b $A0
  LDA.w #$0000 : STA.l Boat_LoadTries
  SEP #$20
  STZ.w $0696 : STZ.w $0697 : STZ.w $0698 : STZ.w $0699
  STZ.w $010A : STZ.w $04AA
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
    REP #$20
    LDA.l Boat_Endpoint : AND.w #$00FF : TAX
    LDA.l Boat_ExitKeys, X : STA.b $A0
    LDA.w #$0000 : STA.l Boat_Marker
    SEP #$20
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
  LDA.l Boat_ExitOffsets, X : TAX
  SEP #$20
  LDA.l STV2_ExitRecords+23, X : STA.b $2F
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

Boat_ExitKeys: dw !Boat_DocksExit, !Boat_IslandExit
Boat_ExitOffsets: dw (!Boat_DocksExit-$0180)*32, (!Boat_IslandExit-$0180)*32
Boat_ClosedTiles: dw !Boat_DocksWaterTile, !Boat_IslandWaterTile
Boat_MoveY: dw -1, 1, 0, 0
Boat_MoveX: dw 0, 0, -1, 1
Boat_Directions: db 8, 4, 2, 1
Boat_CodeEnd:
assert pc() <= $3AB800, "Boat controller overlaps Part00"

; Six replaced bytes. The taken branch lands on the native bank-$02 RTS.
assert read3($02A53C) == $0112AD && read3($02A53F) == $02E40D
org $02A53C ; @hook module=Overworld name=Boat_BoardGate kind=jsl target=Boat_BoardGate expected_m=8 expected_x=8
  JSL Boat_BoardGate
  BCS $02A570
assert pc() == $02A542
pullpc
