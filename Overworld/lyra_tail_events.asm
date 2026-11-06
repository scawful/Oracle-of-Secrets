; Current-engine tail event dispatch. Included only inside the explicitly
; bounded Lyra current code interval, after its saved-source constants.
; No save-buffer address or migration marker has an implicit default.
assert !LYRA_CURRENT_MODE == 1 && !LYRA_CURRENT_EVENTS_ENABLED == 1
assert !LYRA_CURRENT_EVENTS_BOUND == 1, "Current tail events require a reviewed saved-source binding"
assert !LYRA_CURRENT_EVENT_BASE == Oracle_LyraCurrentTailFlags
assert !LYRA_CURRENT_EVENT_VERSION == Oracle_LyraCurrentTailVersion
assert !LYRA_CURRENT_EVENT_BASE >= $7EF412 && !LYRA_CURRENT_EVENT_BASE+$20 <= $7EF4FE
assert !LYRA_CURRENT_EVENT_VERSION >= $7EF412 && !LYRA_CURRENT_EVENT_VERSION < $7EF4FE
assert !LYRA_CURRENT_EVENT_VERSION < !LYRA_CURRENT_EVENT_BASE || !LYRA_CURRENT_EVENT_VERSION >= !LYRA_CURRENT_EVENT_BASE+$20
assert !LYRA_CURRENT_EVENT_MARKER > 0 && !LYRA_CURRENT_EVENT_MARKER <= $FF

; Stores and most loads enter M8; the hidden-item read at1BC902 is M16 and
; immediately masks with0002. Keep each caller's A width, X/Y, DBR and D;
; loads set N/Z from the selected byte/word and stores preserve flags.
; REP/PLP only widens X temporarily; an X8 caller's high byte is already zero.
Oracle_Lyra_TailEvent_Load:
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

Oracle_Lyra_TailEvent_Store:
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
Oracle_Lyra_TailEvent_MigrateSave:
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
assert read4($02EF48) == $7EF280BF || read4($02EF48) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $02EF48: unexpected bytes"
org $02EF48 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad02EF48
assert read4($02EF56) == $7EF280BF || read4($02EF56) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $02EF56: unexpected bytes"
org $02EF56 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad02EF56
assert read4($0588DF) == $7EF280BF || read4($0588DF) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $0588DF: unexpected bytes"
org $0588DF : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad0588DF
assert read4($0589A5) == $7EF280BF || read4($0589A5) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $0589A5: unexpected bytes"
org $0589A5 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad0589A5
assert read4($05EF1E) == $7EF280BF || read4($05EF1E) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $05EF1E: unexpected bytes"
org $05EF1E : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad05EF1E
assert read4($05EFFA) == $7EF280BF || read4($05EFFA) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $05EFFA: unexpected bytes"
org $05EFFA : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad05EFFA
assert read4($068D4C) == $7EF280BF || read4($068D4C) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $068D4C: unexpected bytes"
org $068D4C : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad068D4C
assert read4($06BE6A) == $7EF280BF || read4($06BE6A) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $06BE6A: unexpected bytes"
org $06BE6A : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad06BE6A
assert read4($06EFA8) == $7EF280BF || read4($06EFA8) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $06EFA8: unexpected bytes"
org $06EFA8 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad06EFA8
assert read4($099A87) == $7EF280BF || read4($099A87) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $099A87: unexpected bytes"
org $099A87 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad099A87
assert read4($09A6BC) == $7EF280BF || read4($09A6BC) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $09A6BC: unexpected bytes"
org $09A6BC : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad09A6BC
assert read4($0DCCAD) == $7EF280BF || read4($0DCCAD) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $0DCCAD: unexpected bytes"
org $0DCCAD : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad0DCCAD
assert read4($1BC0C6) == $7EF280BF || read4($1BC0C6) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $1BC0C6: unexpected bytes"
org $1BC0C6 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BC0C6
assert read4($1BC20F) == $7EF280BF || read4($1BC20F) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $1BC20F: unexpected bytes"
org $1BC20F : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BC20F
assert read4($1BC902) == $7EF280BF || read4($1BC902) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $1BC902: unexpected bytes"
; A word read can include the adjacent flag/version byte. This exact mask
; discards that high byte; no M16 tail store is supported or installed.
assert read3($1BC906) == $000229, "TailEvent M16 load must retain low-bit mask"
org $1BC902 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=16 name=TailEventLoad1BC902
assert read4($1BCBD8) == $7EF280BF || read4($1BCBD8) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $1BCBD8: unexpected bytes"
org $1BCBD8 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BCBD8
assert read4($1BCD59) == $7EF280BF || read4($1BCD59) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $1BCD59: unexpected bytes"
org $1BCD59 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BCD59
assert read4($1BCE4A) == $7EF280BF || read4($1BCE4A) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $1BCE4A: unexpected bytes"
org $1BCE4A : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BCE4A
assert read4($1BCFE2) == $7EF280BF || read4($1BCFE2) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $1BCFE2: unexpected bytes"
org $1BCFE2 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1BCFE2
assert read4($1EE4A6) == $7EF280BF || read4($1EE4A6) == ((Lyra_TailEvent_Load<<8)|$22), "TailEvent hook $1EE4A6: unexpected bytes"
org $1EE4A6 : JSL Lyra_TailEvent_Load ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventLoad1EE4A6

; Vanilla area-indexed event flag stores (X = $8A, M8 after ORA.b)
assert read4($0589AB) == $7EF2809F || read4($0589AB) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $0589AB: unexpected bytes"
org $0589AB : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore0589AB
assert read4($05F000) == $7EF2809F || read4($05F000) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $05F000: unexpected bytes"
org $05F000 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore05F000
assert read4($06BE70) == $7EF2809F || read4($06BE70) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $06BE70: unexpected bytes"
org $06BE70 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore06BE70
assert read4($06EFAE) == $7EF2809F || read4($06EFAE) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $06EFAE: unexpected bytes"
org $06EFAE : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore06EFAE
assert read4($099A8D) == $7EF2809F || read4($099A8D) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $099A8D: unexpected bytes"
org $099A8D : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore099A8D
assert read4($1BC0CC) == $7EF2809F || read4($1BC0CC) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $1BC0CC: unexpected bytes"
org $1BC0CC : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BC0CC
assert read4($1BC215) == $7EF2809F || read4($1BC215) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $1BC215: unexpected bytes"
org $1BC215 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BC215
assert read4($1BCBDE) == $7EF2809F || read4($1BCBDE) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $1BCBDE: unexpected bytes"
org $1BCBDE : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BCBDE
assert read4($1BCD5F) == $7EF2809F || read4($1BCD5F) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $1BCD5F: unexpected bytes"
org $1BCD5F : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BCD5F
assert read4($1BCE50) == $7EF2809F || read4($1BCE50) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $1BCE50: unexpected bytes"
org $1BCE50 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BCE50
assert read4($1BCFE8) == $7EF2809F || read4($1BCFE8) == ((Lyra_TailEvent_Store<<8)|$22), "TailEvent hook $1BCFE8: unexpected bytes"
org $1BCFE8 : JSL Lyra_TailEvent_Store ; @hook module=Overworld kind=jsl expected_m=8 name=TailEventStore1BCFE8

pullpc
