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
