; Only an actual outward exit from room55 completes the existing capture.
; The native loader has selected Module08 but still retains room/dungeon/indoor
; context at02E4A6. Entering a room or executing a Minish tag is not an escape.
; Legacy mode preserves the two-bit transaction. Paired mode requires reclaim.
if !ENABLE_D3_PRISON_SEQUENCE == 1

PrisonEscape_RecordOutwardExit:
{
  ; Native M8/X8, DB02, DP0. STZ changes no flags: preserve A (including B),
  ; P, X/Y, DBR, DP and stack. Caller owns the enclosing PHB/JSR frames.
  PHP : REP #$20 : PHA : SEP #$20
if !ENABLE_D3_PRISON_CELL65 == 1
  LDA.b #$00 : STA.l D3Prison_ExitMessage : STA.l D3Prison_ExitMessage+1
endif
  LDA.b $10 : CMP.b #$08 : BNE .native
  LDA.b $11 : BNE .native
  LDA.b $1B : CMP.b #$01 : BNE .native
  LDA.b $A1 : BNE .native
  LDA.b $A0 : CMP.b #$55 : BNE .native
  LDA.w $040C : CMP.b #$10 : BNE .native
  LDA.l CastleAmbushFlags
  AND.b #(!CastleAmbush_HasBeenCaptured|!CastleAmbush_HasEscaped)
  CMP.b #!CastleAmbush_HasBeenCaptured : BNE .native
if !ENABLE_D3_PRISON_CELL65 == 1
  JSL D3Prison_HasReclaimedSword : BCC .native
endif
  LDA.l CastleAmbushFlags : ORA.b #!CastleAmbush_HasEscaped
  STA.l CastleAmbushFlags
  LDA.b #!Spawn_Sanctuary : STA.l SpawnPoint
if !ENABLE_D3_PRISON_CELL65 == 1
  REP #$20
  LDA.w #!D3Prison_ExitMessageLive : STA.l D3Prison_ExitMessage
  SEP #$20
endif
  .native
  REP #$20 : PLA : PLP
  STZ.b $1B : STZ.w $0458
  RTL
}

pushpc
assert read4($02E4A6) == $589C1B64 && read1($02E4AA) == $04, "Prison outward-loader preimage changed"
org $02E4A6 ; @hook module=Dungeons name=PrisonEscape_RecordOutwardExit kind=jsl target=PrisonEscape_RecordOutwardExit expected_m=8 expected_x=8 protected_size=5
  JSL PrisonEscape_RecordOutwardExit
  NOP
assert pc() == $02E4AB
pullpc
endif
