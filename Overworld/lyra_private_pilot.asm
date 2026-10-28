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
  ; Home receives its own long frame; RTS then consumes ONLY the original
  ; Module08 near frame. No manual stack discard, chooser or map modulo.
  JSL Checkpoint_EnterHome
  RTS
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

pushpc
assert read4($0283C7) == $998582A9, "Module08 entry preimage moved"
org $0283C7 ; @hook module=Overworld name=Lyra_PrivatePilotEntryGate kind=jml target=Lyra_PrivatePilotEntryGate expected_m=8 expected_x=8
  JML Lyra_PrivatePilotEntryGate
assert pc() == $0283CB
assert read4($02B217) == $80C98AA5, "Mirror initialization preimage moved"
org $02B217 ; @hook module=Overworld name=Lyra_PrivatePilotMirrorGate kind=jml target=Lyra_PrivatePilotMirrorGate expected_m=8 expected_x=8
  JML Lyra_PrivatePilotMirrorGate
assert pc() == $02B21B
pullpc
endif
