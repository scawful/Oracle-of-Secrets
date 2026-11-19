; Watch-log completion grants the existing Sky Soaring destination token.
; This file is included only by ENABLE_SPECIAL_OVERWORLD_SOARING. The target
; is deliberately unbound: no message ID, text or teaching site is allocated.
; Set this existing Asar source-define seam only with a registry-backed approved
; message. $0000-$000A are engine/save/choice helpers, never teaching targets.
!SKY_SOARING_WATCH_LOG_MESSAGE ?= $FFFF

if !SKY_SOARING_WATCH_LOG_MESSAGE != $FFFF
assert !SKY_SOARING_WATCH_LOG_MESSAGE >= $000B && !SKY_SOARING_WATCH_LOG_MESSAGE < $FFFF, "Sky watch log needs an explicit non-helper message binding"

; Native initialization clears $1CD0-$1CEF once per conversation. $1CEB is
; otherwise unused (Core/ram.asm JUNK_7E1CEB); choice-helper reparses do NOT
; clear it. It is transient message state, not a new saved progression flag.
; 00=unrelated, 01=original watch log, 02=its terminator acknowledged.
SkyWatchLog_State = $7E1CEB

pushpc
assert read4($0EC4A4) == $7FA930C2 && read1($0EC4A8) == $38, "Watch-log text initialization ABI moved"
org $0EC4A4 ; @hook module=Items name=SkyWatchLog_Initialize kind=jml target=SkyWatchLog_Initialize
  JML SkyWatchLog_Initialize
  NOP
assert pc() == $0EC4A9

assert read4($0ED275) == $D48D04A9 && read1($0ED279) == $1C, "Watch-log terminator ABI moved"
org $0ED275 ; @hook module=Items name=SkyWatchLog_Acknowledge kind=jml target=SkyWatchLog_Acknowledge
  JML SkyWatchLog_Acknowledge
  NOP
assert pc() == $0ED27A

assert read4($0ECA61) == $641CD89C && read1($0ECA65) == $11, "Watch-log finalization ABI moved"
org $0ECA61 ; @hook module=Items name=SkyWatchLog_Finalize kind=jml target=SkyWatchLog_Finalize
  JML SkyWatchLog_Finalize
  NOP
assert pc() == $0ECA66
pullpc

SkyWatchLog_Initialize:
{
  ; Native $0EC4A4: M8/X8, DBR=$0E, DP=0; indexes preserved until the
  ; displaced REP makes them 16-bit. Save C/V across the identity comparisons.
  PHP
  STZ.w $1CEB
  LDA.b $10 : CMP.b #$0E : BNE .done
  LDA.b $11 : CMP.b #$02 : BNE .done
  LDA.b $1B : BNE .done
  LDA.w $010C : CMP.b #$0B : BNE .done
  REP #$20
  LDA.w $1CF0 : CMP.w #!SKY_SOARING_WATCH_LOG_MESSAGE : BNE .done
  SEP #$20
  LDA.b #$01 : STA.l SkyWatchLog_State
  .done
  PLP
  REP #$30 : LDA.w #$387F ; displaced initialization, including N/Z/M/X
  JML $0EC4A9
}

SkyWatchLog_Acknowledge:
{
  ; Only RenderText_Terminate reaches this after its delay and final input.
  ; Choice accept/refuse closes via other sites, so it cannot qualify a read.
  ; Entry M8/X8, DBR=$0E, DP=0; displaced LDA supplies the outgoing A/N/Z.
  PHP
  LDA.l SkyWatchLog_State : CMP.b #$01 : BNE .done
  LDA.b #$02 : STA.l SkyWatchLog_State
  .done
  PLP
  LDA.b #$04 : STA.w $1CD4
  JML $0ED27A
}

SkyWatchLog_Finalize:
{
  ; Native window cleanup, M8/X8, DBR=$0E, DP=0. Preserve A/P/X/Y/DBR;
  ; restore both displaced clears before its normal module-return sequence.
  ; Never read $1CF0 here: native choice drawing reuses it for $09/$0A, etc.
  PHP : PHA
  LDA.l SkyWatchLog_State : PHA
  STZ.w $1CEB             ; consume on every close, including refusal
  PLA : CMP.b #$02 : BNE .done
  LDA.b $10 : CMP.b #$0E : BNE .done
  LDA.b $11 : CMP.b #$02 : BNE .done
  LDA.b $1B : BNE .done
  LDA.w $010C : CMP.b #$0B : BNE .done
  LDA.l SkySoaringLearned : CMP.b #!SKY_SOARING_LEARNED : BEQ .done
  LDA.b #!SKY_SOARING_LEARNED : STA.l SkySoaringLearned
  .done
  PLA : PLP
  STZ.w $1CD8 : STZ.b $11
  JML $0ECA66
}
assert pc() <= $2BE000, "Watch-log lifecycle code reached the D8 boss owner"
endif
