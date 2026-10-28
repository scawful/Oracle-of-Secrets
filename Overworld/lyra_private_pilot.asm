; Private A0/A1 separate-screen transition guard. No default enable or state.
; Included inside the existing current-code owner; no new ROM/RAM allocation.
assert !LYRA_CURRENT_MODE == 1
assert !LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED == 1
assert defined("LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND")
assert !LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND == 1, "Private pilot needs an exact selected boundary binding"
assert !Func02A9C4 == 1, "Private pilot needs the precommit transition owner"

; In: M8/X8 at OverworldHandleTransitions, Y=0/2/4/6 (right/left/down/up).
; Out: C set refuses the transition before any map/tilemap/camera mutation.
; Preserve full A/X/Y, other P bits, DBR and DP. Stack only; no state writes.
; This guard does not change overlay data/readers. Native-only transitions
; retain their source behavior; there is no approved native-to-tail scroll seam.
Lyra_PrivatePilotCanScroll:
{
  PHP : CLD : REP #$30 : PHA : PHX : PHY
  TYA : AND.w #$00FF : CMP.w #$0008 : BCS .blocked
  BIT.w #$0001 : BNE .blocked

  LDA.b $8A : AND.w #$00FF : CMP.w #$00A0 : BCC .native
  BEQ .first
  CMP.w #$00A1 : BNE .blocked
  ; A1 may leave only west, with its exact independent-small physical cell.
  CPY.w #$0002 : BNE .blocked
  LDA.w $0700 : CMP.w #$0042 : BNE .blocked
  BRA .allowed
.first
  ; A0 may leave only east. Every other edge, including preserved legacy
  ; geography and outer edges, remains outside this private traversal set.
  CPY.w #$0000 : BNE .blocked
  LDA.w $0700 : CMP.w #$0040 : BNE .blocked
  BRA .allowed
.native
  ; Reproduce the source's true-cell calculation without changing $04/$84.
  ; Existing native targets00..9F are untouched; A0+ requires an entry adapter.
  TYA : TAX
  LDA.b $8A : AND.w #$00C0 : ASL A
  ORA.w $0700 : CLC : ADC.l OverworldScreenIDChange, X
  CMP.w #$0140 : BCS .blocked
.allowed
  REP #$30 : PLY : PLX : PLA : PLP
  CLC : RTL
.blocked
  REP #$30 : PLY : PLX : PLA : PLP
  SEC : RTL
}
Lyra_PrivatePilotCanScroll_End = pc()

; Ingress API only: M16 A=complete requested physical map word.
; C set rejects A2..FFFF; C clear permits preserved native00..9F or A0/A1.
; Preserve full A/X/Y, DP/DBR, stack and all P bits except C. No RAM writes.
; This helper alone grants no ingress. The publisher requires independently
; bound preaccess entry/full/sub/mirror/warp/cold callers before selection.
Lyra_PrivatePilotCanEnter:
{
  PHP : REP #$20 : PHA
  CMP.w #$00A2 : BCS .blocked
  PLA : PLP : CLC : RTL
.blocked
  PLA : PLP : SEC : RTL
}
Lyra_PrivatePilotCanEnter_End = pc()

; The earlier scroll prototype remains independently buildable. Selecting
; ingress requires the joint checkpoint/Home source, never a private copy.
if not(defined("LYRA_PRIVATE_PILOT_INGRESS_ENABLED"))
  !LYRA_PRIVATE_PILOT_INGRESS_ENABLED = 0
endif
if !LYRA_PRIVATE_PILOT_INGRESS_ENABLED == 1
assert !REGIONAL_CHECKPOINTS_ENABLED == 1, "Private entry needs the central checkpoint Home adapter"
assert !REGIONAL_CHECKPOINTS_BOUND == 1, "Private entry needs the reviewed checkpoint source"

; M16/X16. Return the complete physical destination in A, C clear; C set
; means no bounded native exit exists. Preserve X/Y/DBR/DP and other P bits.
; Match native02E4BD dispatch, including its descending highest-row winner.
; Reading a byte-sized EXIT_MAPS field widens only that field; cached map words
; remain full words, so0100 cannot alias native00.
Lyra_PrivatePilotEntryMap:
{
  PHP : REP #$30 : PHX
  LDA.b $A0 : CMP.w #$0104 : BEQ .exitTable
  CMP.w #$0180 : BCS .exitTable
  CMP.w #$0100 : BCC .exitTable
  LDA.l $7EC140 : CMP.w #$00A2 : BCS .missing
  TAX ; cached parent consumed by040A, distinct from physical8A below.
  LDA.l $7EC14C : CMP.w #$00A2 : BCS .missing
  CMP.w #$00A0 : BCS .samePilot
  CPX.w #$00A0 : BCC .found
.samePilot
  ; Separate-screen pilot parents must equal their physical page. Native
  ; parent/child records (e.g36/37) retain their complete original words.
  PHA : TXA : CMP $01,S : BEQ .same
  PLA : BRA .missing
.same
  PLA : BRA .found
.exitTable
  LDX.w #$009C
.next
  CMP.l $02DD8A,X : BEQ .exitFound
  DEX #2 : BPL .next
.missing
  PLX : PLP : SEC : RTL
.exitFound
  TXA : LSR : TAX
  LDA.l $02DE28,X : AND.w #$00FF
.found
  PLX : PLP : CLC : RTL
}
Lyra_PrivatePilotEntryMap_End = pc()

; M8/X8 at Module08_00; the native dispatcher owns a near JSR return frame.
; Cold regional/Goron loads and ordinary indoor exits both enter this submodule
; before LoadOverworldFromUnderworld. No99/1B/map/position/GFX mutation yet.
Lyra_PrivatePilotEntryGate:
{
  PHP : REP #$30 : PHA : PHX : PHY
  ; Module0A shares this native submodule but consumes a separateC100 cache.
  ; Preserve that route exactly; it is not admitted by this Module08 guard.
  LDA.b $10 : AND.w #$00FF : CMP.w #$0008 : BNE .allowed
  JSL Lyra_PrivatePilotEntryMap : BCS .blocked
LyraCall_PrivatePilotEntry = pc()
LyraCall_PrivatePilotColdResume = pc()
  JSL Lyra_PrivatePilotCanEnter : BCS .blocked
.allowed
  PLY : PLX : PLA : PLP
  LDA.b #$82 : STA.b $99
  JML $0283CB
.blocked
LyraPilot_EntryBlocked = pc()
LyraPilot_ColdResumeBlocked = pc()
  PLY : PLX : PLA : PLP
  ; Home receives its own long frame. Return to bank02 before its native
  ; RTS consumes the original Module08 near frame; local RTS keeps bankE0.
  JSL Checkpoint_EnterHome
  JML $02EDC4
}
Lyra_PrivatePilotEntryGate_End = pc()

; Classify the complete current physical map word. Preserve full A/X/Y,
; DBR/DP and every P bit except Carry; do not classify the0700 true-cell index.
Lyra_PrivatePilotCurrentMapAllowed:
{
  PHP : REP #$20 : PHA
  LDA.b $8A
  JSL Lyra_PrivatePilotCanEnter : BCS .blocked
  PLA : PLP : CLC : RTL
.blocked
  PLA : PLP : SEC : RTL
}
Lyra_PrivatePilotCurrentMapAllowed_End = pc()

; M8/X8. Native00..9F follows the original CMP80 branch, including special
; areas. Unsupported tail/invalid words take the native mirror abort BEFORE
; SavedWorld XOR40, map AND3F, palette/GFX work or any destination mutation.
Lyra_PrivatePilotMirrorGate:
{
LyraCall_PrivatePilotMirror = pc()
  JSL Lyra_PrivatePilotCurrentMapAllowed : BCS .blocked
  LDA.b $8A : CMP.b #$80
  JML $02B21B
.blocked
LyraPilot_MirrorBlocked = pc()
  JML $02B21D
}
Lyra_PrivatePilotMirrorGate_End = pc()

; Native near-call replay used ONLY after the Module08 whole-operation
; preflight. PEA supplies an existing native RTL boundary; no allocation at
; that return and no unsafe Home return into0AB948's saved10/0200 context.
Lyra_PrivatePilotFullNativeCall:
  PEA.w $B1F8
  JML $02ED59
Lyra_PrivatePilotFullNativeCall_End = pc()

; Module08_02 owns a near dispatcher frame. Route its ENTIRE operation via
; the same guarded long operation; denial skips its10/B0/11 completion writes.
; Both exits restore bank02 at the pinned native RTS without adding a frame.
Lyra_PrivatePilotFullNearGate:
{
  PHP
LyraCall_PrivatePilotFullLoad = pc()
  JSL Lyra_PrivatePilotCurrentMapAllowed : BCS .blocked
  PLP
  JSL Lyra_PrivatePilotFullNativeCall
  LDA.b #$10 : STA.b $10 : STZ.b $B0 : STZ.b $11
  JML $02EDC4
.blocked
LyraPilot_FullLoadBlocked = pc()
  PLP
  JSL Checkpoint_EnterHome
  JML $02EDC4
}
Lyra_PrivatePilotFullNearGate_End = pc()

; Module09's near submodule return is followed by camera/sprite work. Refuse
; at the WHOLE long module entry, before that near frame exists, so Home can
; return directly to the original long caller without unsafe postprocessing.
; Replay the original SEP30 first, including native X/Y-high truncation.
Lyra_PrivatePilotFullFrameGate:
{
  SEP #$30
  PHP : REP #$30 : PHA : PHX : PHY
  LDA.b $8A : JSL Lyra_PrivatePilotCanEnter : BCS .blocked
  PLY : PLX : PLA : PLP
  LDA.b $11
  JML $02A479
.blocked
  PLY : PLX : PLA : PLP
  JSL Checkpoint_EnterHome
  RTL
}
Lyra_PrivatePilotFullFrameGate_End = pc()

; M16/X16 at the existing overlay SELECT boundary. X is the complete overlay
; page, not the host8A parent or0700 true-cell index. Native00..9F templates
; remain allowed on every host; FF/unselected/invalid words take the existing
; no-overlay branch BEFORE84/8A/8C/scroll mutations or any decompressor call.
; Its native no-overlay completion is the correct whole-operation refusal;
; Home would be wrong while the host is only borrowing an overlay map.
Lyra_PrivatePilotSubGate:
{
  PHP : PHA : TXA
LyraCall_PrivatePilotSubLoad = pc()
  JSL Lyra_PrivatePilotCanEnter : BCS .blocked
  PLA : PLP : CPX.w #$00FF
  JML LyraPilot_SubNativeAllowed
.blocked
LyraPilot_SubLoadBlocked = pc()
  PLA : PLP : CPX.w #$00FF
  JML LyraPilot_SubNativeNoOverlay
}
Lyra_PrivatePilotSubGate_End = pc()

pushpc
assert read4($0283C7) == $998582A9, "Module08 entry preimage moved"
org $0283C7 ; @hook module=Overworld name=Lyra_PrivatePilotEntryGate kind=jml target=Lyra_PrivatePilotEntryGate expected_m=8 expected_x=8
  JML Lyra_PrivatePilotEntryGate
assert pc() == $0283CB
assert read4($02B217) == $80C98AA5, "Mirror initialization preimage moved"
org $02B217 ; @hook module=Overworld name=Lyra_PrivatePilotMirrorGate kind=jml target=Lyra_PrivatePilotMirrorGate expected_m=8 expected_x=8
  JML Lyra_PrivatePilotMirrorGate
assert pc() == $02B21B
assert read4($02B1F0) == $6BED5920, "Native-only full long-operation source moved"
assert read1($02B1F9) == $6B, "Native full-operation far return moved"
assert read1($02EDC4) == $60, "Module08 native near-return instruction moved"
assert read4($02EDB9) == $A9ED5920, "Module08 full-operation preimage moved"
org $02EDB9 ; @hook module=Overworld name=Lyra_PrivatePilotFullNearGate kind=jml target=Lyra_PrivatePilotFullNearGate expected_m=8 expected_x=8
  JML Lyra_PrivatePilotFullNearGate
assert pc() == $02EDBD
assert read4($02A475) == $11A530E2, "Whole outdoor-module preimage moved"
org $02A475 ; @hook module=Overworld name=Lyra_PrivatePilotFullFrameGate kind=jml target=Lyra_PrivatePilotFullFrameGate
  JML Lyra_PrivatePilotFullFrameGate
assert pc() == $02A479
pullpc
endif
