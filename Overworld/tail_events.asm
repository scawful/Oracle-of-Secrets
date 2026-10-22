; Native event flags for tail overworld maps $A0-$BF (Lyra).
; Vanilla indexes $7EF280,X by area ($8A); for $A0-$BF that reaches the item
; extension ($7EF320-33F). These helpers send $A0-$BF to TailEventFlags
; ($7EF4C0-4DF, Core/sram.asm) and every other area to $7EF280,X unchanged.
; Each helper is a 4-byte JSL replacing a 4-byte LDA.l/STA.l $7EF280,X.
; Width-agnostic: caller M/X/C/flags are restored; LDA sets N/Z as before.

TailEvent_Load:
{
  PHP
  REP #$10 ; 8-bit X has XH = 0, so X = $00xx
  CPX.w #$00A0 : BCC .legacy
  CPX.w #$00C0 : BCS .legacy
    PLP
    LDA.l TailEventFlags-$A0, X
    RTL
  .legacy
  PLP
  LDA.l $7EF280, X
  RTL
}

TailEvent_Store:
{
  PHP
  REP #$10
  CPX.w #$00A0 : BCC .legacy
  CPX.w #$00C0 : BCS .legacy
    PLP
    STA.l TailEventFlags-$A0, X
    RTL
  .legacy
  PLP
  STA.l $7EF280, X
  RTL
}

; Old-save initialization. Runs on every file load from LoadCheckpointOrWorld
; (Module05, M8/X8, A free). Saves made before this build have arbitrary bytes
; in $7EF4C0-4DF; clear them once and stamp the version. New files are zeroed
; by vanilla init and get stamped on their first load. Idempotent.
TailEvent_MigrateSave:
{
  LDA.l TailEventVersion : CMP.b #!TailEventVersion_Current : BEQ .done
    PHX
    LDX.b #$1F
    LDA.b #$00
    .clear
      STA.l TailEventFlags, X
      DEX : BPL .clear
    PLX
    LDA.b #!TailEventVersion_Current : STA.l TailEventVersion
  .done
  RTL
}

pushpc

; Vanilla area-indexed event flag loads (X = $8A)
assert read1($02EF48) == $BF && read3($02EF48+1) == $7EF280, "TailEvent hook $02EF48: unexpected bytes"
org $02EF48 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad02EF48
assert read1($02EF56) == $BF && read3($02EF56+1) == $7EF280, "TailEvent hook $02EF56: unexpected bytes"
org $02EF56 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad02EF56
assert read1($0588DF) == $BF && read3($0588DF+1) == $7EF280, "TailEvent hook $0588DF: unexpected bytes"
org $0588DF : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad0588DF
assert read1($0589A5) == $BF && read3($0589A5+1) == $7EF280, "TailEvent hook $0589A5: unexpected bytes"
org $0589A5 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad0589A5
assert read1($05EF1E) == $BF && read3($05EF1E+1) == $7EF280, "TailEvent hook $05EF1E: unexpected bytes"
org $05EF1E : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad05EF1E
assert read1($05EFFA) == $BF && read3($05EFFA+1) == $7EF280, "TailEvent hook $05EFFA: unexpected bytes"
org $05EFFA : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad05EFFA
assert read1($068D4C) == $BF && read3($068D4C+1) == $7EF280, "TailEvent hook $068D4C: unexpected bytes"
org $068D4C : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad068D4C
assert read1($06BE6A) == $BF && read3($06BE6A+1) == $7EF280, "TailEvent hook $06BE6A: unexpected bytes"
org $06BE6A : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad06BE6A
assert read1($06EFA8) == $BF && read3($06EFA8+1) == $7EF280, "TailEvent hook $06EFA8: unexpected bytes"
org $06EFA8 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad06EFA8
assert read1($099A87) == $BF && read3($099A87+1) == $7EF280, "TailEvent hook $099A87: unexpected bytes"
org $099A87 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad099A87
assert read1($09A6BC) == $BF && read3($09A6BC+1) == $7EF280, "TailEvent hook $09A6BC: unexpected bytes"
org $09A6BC : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad09A6BC
assert read1($0DCCAD) == $BF && read3($0DCCAD+1) == $7EF280, "TailEvent hook $0DCCAD: unexpected bytes"
org $0DCCAD : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad0DCCAD
assert read1($1BC0C6) == $BF && read3($1BC0C6+1) == $7EF280, "TailEvent hook $1BC0C6: unexpected bytes"
org $1BC0C6 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad1BC0C6
assert read1($1BC20F) == $BF && read3($1BC20F+1) == $7EF280, "TailEvent hook $1BC20F: unexpected bytes"
org $1BC20F : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad1BC20F
assert read1($1BC902) == $BF && read3($1BC902+1) == $7EF280, "TailEvent hook $1BC902: unexpected bytes"
org $1BC902 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad1BC902
assert read1($1BCBD8) == $BF && read3($1BCBD8+1) == $7EF280, "TailEvent hook $1BCBD8: unexpected bytes"
org $1BCBD8 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad1BCBD8
assert read1($1BCD59) == $BF && read3($1BCD59+1) == $7EF280, "TailEvent hook $1BCD59: unexpected bytes"
org $1BCD59 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad1BCD59
assert read1($1BCE4A) == $BF && read3($1BCE4A+1) == $7EF280, "TailEvent hook $1BCE4A: unexpected bytes"
org $1BCE4A : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad1BCE4A
assert read1($1BCFE2) == $BF && read3($1BCFE2+1) == $7EF280, "TailEvent hook $1BCFE2: unexpected bytes"
org $1BCFE2 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad1BCFE2
assert read1($1EE4A6) == $BF && read3($1EE4A6+1) == $7EF280, "TailEvent hook $1EE4A6: unexpected bytes"
org $1EE4A6 : JSL TailEvent_Load ; @hook module=Overworld kind=jsl name=TailEventLoad1EE4A6

; Vanilla area-indexed event flag stores (X = $8A, M8 after ORA.b)
assert read1($0589AB) == $9F && read3($0589AB+1) == $7EF280, "TailEvent hook $0589AB: unexpected bytes"
org $0589AB : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore0589AB
assert read1($05F000) == $9F && read3($05F000+1) == $7EF280, "TailEvent hook $05F000: unexpected bytes"
org $05F000 : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore05F000
assert read1($06BE70) == $9F && read3($06BE70+1) == $7EF280, "TailEvent hook $06BE70: unexpected bytes"
org $06BE70 : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore06BE70
assert read1($06EFAE) == $9F && read3($06EFAE+1) == $7EF280, "TailEvent hook $06EFAE: unexpected bytes"
org $06EFAE : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore06EFAE
assert read1($099A8D) == $9F && read3($099A8D+1) == $7EF280, "TailEvent hook $099A8D: unexpected bytes"
org $099A8D : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore099A8D
assert read1($1BC0CC) == $9F && read3($1BC0CC+1) == $7EF280, "TailEvent hook $1BC0CC: unexpected bytes"
org $1BC0CC : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore1BC0CC
assert read1($1BC215) == $9F && read3($1BC215+1) == $7EF280, "TailEvent hook $1BC215: unexpected bytes"
org $1BC215 : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore1BC215
assert read1($1BCBDE) == $9F && read3($1BCBDE+1) == $7EF280, "TailEvent hook $1BCBDE: unexpected bytes"
org $1BCBDE : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore1BCBDE
assert read1($1BCD5F) == $9F && read3($1BCD5F+1) == $7EF280, "TailEvent hook $1BCD5F: unexpected bytes"
org $1BCD5F : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore1BCD5F
assert read1($1BCE50) == $9F && read3($1BCE50+1) == $7EF280, "TailEvent hook $1BCE50: unexpected bytes"
org $1BCE50 : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore1BCE50
assert read1($1BCFE8) == $9F && read3($1BCFE8+1) == $7EF280, "TailEvent hook $1BCFE8: unexpected bytes"
org $1BCFE8 : JSL TailEvent_Store ; @hook module=Overworld kind=jsl name=TailEventStore1BCFE8

pullpc
