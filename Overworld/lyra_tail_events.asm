; Current-engine tail event dispatch. Included only inside the explicitly
; bounded Lyra current code interval, after its saved-source constants.
; No save-buffer address or migration marker has an implicit default.
assert !LYRA_CURRENT_MODE == 1 && !LYRA_CURRENT_EVENTS_ENABLED == 1
assert !LYRA_CURRENT_EVENTS_BOUND == 1, "Current tail events require a reviewed saved-source binding"
assert !LYRA_CURRENT_EVENT_BASE >= $7EF412 && !LYRA_CURRENT_EVENT_BASE+$20 <= $7EF4FE
assert !LYRA_CURRENT_EVENT_VERSION >= $7EF412 && !LYRA_CURRENT_EVENT_VERSION < $7EF4FE
assert !LYRA_CURRENT_EVENT_VERSION < !LYRA_CURRENT_EVENT_BASE || !LYRA_CURRENT_EVENT_VERSION >= !LYRA_CURRENT_EVENT_BASE+$20
assert !LYRA_CURRENT_EVENT_MARKER > 0 && !LYRA_CURRENT_EVENT_MARKER <= $FF

; All patched event callers enter M8. Keep their A, X/Y, DBR and direct-page
; contract; loads set N/Z from the selected byte and stores preserve flags.
; REP/PLP only widens X temporarily; an X8 caller's high byte is already zero.
Lyra_TailEvent_Load:
{
  PHP : REP #$10
  CPX.w #$00A0 : BCC .legacy
  CPX.w #$00C0 : BCS .legacy
    PLP
    LDA.l !LYRA_CURRENT_EVENT_BASE-$A0, X
    RTL
  .legacy
  PLP
  LDA.l $7EF280, X
  RTL
}

Lyra_TailEvent_Store:
{
  PHP : REP #$10
  CPX.w #$00A0 : BCC .legacy
  CPX.w #$00C0 : BCS .legacy
    PLP
    STA.l !LYRA_CURRENT_EVENT_BASE-$A0, X
    RTL
  .legacy
  PLP
  STA.l $7EF280, X
  RTL
}

; File-load/Continue migration runs before the ordinary spawn selector.
; Preserve full A/X and P, including hidden B, for every caller width.
; The existing vanilla save copy/checksum/new-file clear owns these bytes.
Lyra_TailEvent_MigrateSave:
{
  PHP : REP #$30 : PHA : PHX
  SEP #$20
  LDA.l !LYRA_CURRENT_EVENT_VERSION
  CMP.b #!LYRA_CURRENT_EVENT_MARKER : BEQ .done
    LDX.w #$001F
    LDA.b #$00
    .clear
      STA.l !LYRA_CURRENT_EVENT_BASE, X
      DEX : BPL .clear
    LDA.b #!LYRA_CURRENT_EVENT_MARKER
    STA.l !LYRA_CURRENT_EVENT_VERSION
  .done
  REP #$30 : PLX : PLA : PLP
  RTL
}

pushpc

; Vanilla area-indexed event flag loads (X = $8A)
assert read1($02EF48) == $BF && read3($02EF48+1) == $7EF280, "TailEvent hook $02EF48: unexpected bytes"
org $02EF48 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad02EF48
assert read1($02EF56) == $BF && read3($02EF56+1) == $7EF280, "TailEvent hook $02EF56: unexpected bytes"
org $02EF56 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad02EF56
assert read1($0588DF) == $BF && read3($0588DF+1) == $7EF280, "TailEvent hook $0588DF: unexpected bytes"
org $0588DF : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad0588DF
assert read1($0589A5) == $BF && read3($0589A5+1) == $7EF280, "TailEvent hook $0589A5: unexpected bytes"
org $0589A5 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad0589A5
assert read1($05EF1E) == $BF && read3($05EF1E+1) == $7EF280, "TailEvent hook $05EF1E: unexpected bytes"
org $05EF1E : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad05EF1E
assert read1($05EFFA) == $BF && read3($05EFFA+1) == $7EF280, "TailEvent hook $05EFFA: unexpected bytes"
org $05EFFA : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad05EFFA
assert read1($068D4C) == $BF && read3($068D4C+1) == $7EF280, "TailEvent hook $068D4C: unexpected bytes"
org $068D4C : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad068D4C
assert read1($06BE6A) == $BF && read3($06BE6A+1) == $7EF280, "TailEvent hook $06BE6A: unexpected bytes"
org $06BE6A : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad06BE6A
assert read1($06EFA8) == $BF && read3($06EFA8+1) == $7EF280, "TailEvent hook $06EFA8: unexpected bytes"
org $06EFA8 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad06EFA8
assert read1($099A87) == $BF && read3($099A87+1) == $7EF280, "TailEvent hook $099A87: unexpected bytes"
org $099A87 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad099A87
assert read1($09A6BC) == $BF && read3($09A6BC+1) == $7EF280, "TailEvent hook $09A6BC: unexpected bytes"
org $09A6BC : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad09A6BC
assert read1($0DCCAD) == $BF && read3($0DCCAD+1) == $7EF280, "TailEvent hook $0DCCAD: unexpected bytes"
org $0DCCAD : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad0DCCAD
assert read1($1BC0C6) == $BF && read3($1BC0C6+1) == $7EF280, "TailEvent hook $1BC0C6: unexpected bytes"
org $1BC0C6 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BC0C6
assert read1($1BC20F) == $BF && read3($1BC20F+1) == $7EF280, "TailEvent hook $1BC20F: unexpected bytes"
org $1BC20F : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BC20F
assert read1($1BC902) == $BF && read3($1BC902+1) == $7EF280, "TailEvent hook $1BC902: unexpected bytes"
org $1BC902 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BC902
assert read1($1BCBD8) == $BF && read3($1BCBD8+1) == $7EF280, "TailEvent hook $1BCBD8: unexpected bytes"
org $1BCBD8 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BCBD8
assert read1($1BCD59) == $BF && read3($1BCD59+1) == $7EF280, "TailEvent hook $1BCD59: unexpected bytes"
org $1BCD59 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BCD59
assert read1($1BCE4A) == $BF && read3($1BCE4A+1) == $7EF280, "TailEvent hook $1BCE4A: unexpected bytes"
org $1BCE4A : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BCE4A
assert read1($1BCFE2) == $BF && read3($1BCFE2+1) == $7EF280, "TailEvent hook $1BCFE2: unexpected bytes"
org $1BCFE2 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BCFE2
assert read1($1EE4A6) == $BF && read3($1EE4A6+1) == $7EF280, "TailEvent hook $1EE4A6: unexpected bytes"
org $1EE4A6 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1EE4A6

; Vanilla area-indexed event flag stores (X = $8A, M8 after ORA.b)
assert read1($0589AB) == $9F && read3($0589AB+1) == $7EF280, "TailEvent hook $0589AB: unexpected bytes"
org $0589AB : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore0589AB
assert read1($05F000) == $9F && read3($05F000+1) == $7EF280, "TailEvent hook $05F000: unexpected bytes"
org $05F000 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore05F000
assert read1($06BE70) == $9F && read3($06BE70+1) == $7EF280, "TailEvent hook $06BE70: unexpected bytes"
org $06BE70 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore06BE70
assert read1($06EFAE) == $9F && read3($06EFAE+1) == $7EF280, "TailEvent hook $06EFAE: unexpected bytes"
org $06EFAE : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore06EFAE
assert read1($099A8D) == $9F && read3($099A8D+1) == $7EF280, "TailEvent hook $099A8D: unexpected bytes"
org $099A8D : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore099A8D
assert read1($1BC0CC) == $9F && read3($1BC0CC+1) == $7EF280, "TailEvent hook $1BC0CC: unexpected bytes"
org $1BC0CC : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BC0CC
assert read1($1BC215) == $9F && read3($1BC215+1) == $7EF280, "TailEvent hook $1BC215: unexpected bytes"
org $1BC215 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BC215
assert read1($1BCBDE) == $9F && read3($1BCBDE+1) == $7EF280, "TailEvent hook $1BCBDE: unexpected bytes"
org $1BCBDE : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BCBDE
assert read1($1BCD5F) == $9F && read3($1BCD5F+1) == $7EF280, "TailEvent hook $1BCD5F: unexpected bytes"
org $1BCD5F : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BCD5F
assert read1($1BCE50) == $9F && read3($1BCE50+1) == $7EF280, "TailEvent hook $1BCE50: unexpected bytes"
org $1BCE50 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BCE50
assert read1($1BCFE8) == $9F && read3($1BCFE8+1) == $7EF280, "TailEvent hook $1BCFE8: unexpected bytes"
org $1BCFE8 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BCFE8

pullpc
