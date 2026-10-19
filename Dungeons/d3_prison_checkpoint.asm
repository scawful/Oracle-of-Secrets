; Captured death/continue returns to cell65 (scawful, 2026-10-19).
; Diagnostic-only while the cell puzzle and capture actors are being authored.
; Restart the unfinished escape unarmed; retain the backed-up blade for its
; table actor. The cold file load cannot depend on the previous room or $1B.
if !ENABLE_D3_PRISON_SEQUENCE == 1

; C=1 for captured or reclaimed, but not escaped/pending/malformed states.
; Native mode, DP=0; preserve P except C, X/Y/DB/SP. A is scratch.
D3Prison_ShouldResumeCell:
{
  PHP
  SEP #$20
  LDA.l CastleAmbushFlags : AND.b #$07
  CMP.b #!CastleAmbush_HasBeenCaptured : BNE .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_SwordMask
  LSR #4
  BEQ .no
  CMP.b #$05 : BCS .no
  LDA.l Sword : CMP.b #$05 : BCS .no ; includes smith-held $FF
  PLP
  SEC
  RTL
  .no
  PLP
  CLC
  RTL
}

; Restart only a valid unfinished escape. Keep the backed-up sword and bit80;
; do not recapture (which would replace the backup with the current sword).
; Idempotent for already-unarmed Link. Eligibility remains read-only above.
; Native mode, DP=0; preserve P except C, X/Y/DB/SP. A is scratch.
D3Prison_RestartEscape:
{
  PHP
  SEP #$20
  JSL D3Prison_ShouldResumeCell : BCC .no
  LDA.l CastleAmbushFlags : AND.b #$F7
  STA.l CastleAmbushFlags
  LDA.b #$00 : STA.l Sword
  PLP
  SEC
  RTL
  .no
  PLP
  CLC
  RTL
}

; Accepted Game Over choice / Module17 Save & Quit, before SaveGameFile.
; Fairy revival and cancel never reach this seam. Replay native cleanup first:
; its STA $005E consumes incoming A. Preserve its full A and returned P.
D3Prison_RestartBeforeSave:
{
  JSL $0BFFBF ; ResetSomeThingsAfterDeath
  PHP
  REP #$20
  PHA
  JSL D3Prison_RestartEscape
  REP #$20
  PLA
  PLP
  RTL
}

; Common regular/spawn entrance join, before drawing/header/sprite loading.
; Native M8/X16, DB02, DP0. Replace LDA80/STA45 and return with exactly that
; A/N/Z result; the next native STA44 still runs. No scratch or index writes.
; The paired room65 recipe supplies the cell and Minish passage at this
; interior position. Entrance32's south-door position would be inside its wall.
D3Prison_ApplyCellProfile:
{
  PHP
  LDA.l $7E0010 : CMP.b #$05 : BNE .native
  JSL D3Prison_ShouldResumeCell : BCS .apply
  .native
  PLP
  LDA.b #$80 : STA.b $45
  RTL
  .apply
  JSL D3Prison_RestartEscape ; also repair older reclaimed saves on cold load
  REP #$20
  LDA.w #$0032 : STA.l $7E010E ; runtime exit bookkeeping, not saved SpawnPoint
  LDA.w #$0065 : STA.l $7E00A0 : STA.l $7E048E
  LDA.w #$0D10
  STA.l $7E00E8 : STA.l $7E00E6 : STA.l $7E0122 : STA.l $7E0124
  LDA.w #$0A00
  STA.l $7E00E2 : STA.l $7E00E0 : STA.l $7E011E : STA.l $7E0120
  STA.l $7E0608 : STA.l $7E060A : STA.l $7E060C
  LDA.w #$0D78 : STA.l $7E0020
  LDA.w #$0A78 : STA.l $7E0022
  ; Native camera triggers are LOCAL within a room; do not translate these.
  LDA.w #$0187 : STA.l $7E0618
  LDA.w #$0189 : STA.l $7E061A
  LDA.w #$007F : STA.l $7E061C
  LDA.w #$0081 : STA.l $7E061E
  LDA.w #$01F8 : STA.l $7E00EC
  LDA.w #$1DEE : STA.l $7E0696
  LDA.w #$0000
  STA.l $7E0698 : STA.l $7E0610 : STA.l $7E0614 : STA.l $7E04AA
  LDA.w #$0110 : STA.l $7E0612
  LDA.w #$0100 : STA.l $7E0616
  ; Entrance32's full camera bounds translated one room row (+0200 Y).
  LDA.w #$0D00 : STA.l $7E0600
  LDA.w #$0C00 : STA.l $7E0602
  LDA.w #$0D10 : STA.l $7E0604 : STA.l $7E0606
  LDA.w #$0B00 : STA.l $7E060E
  SEP #$20
  LDA.b #$00
  STA.l $7E002F : STA.l $7E00A4 : STA.l $7E006C
  STA.l $7E00EE : STA.l $7E0476
  STA.l $7E00A7 : STA.l $7E00A9
  ; Cell65 layout5 has a wide lower half; Module05 does not recalculate this.
  LDA.b #$02 : STA.l $7E00A6 : STA.l $7E0AA1 : STA.l $7E00AA
  LDA.b #$10 : STA.l $7E0132 : STA.l $7E040C
  PLP
  LDA.b #$80 : STA.b $45
  RTL
}

pushpc
org $09F540 ; @hook module=Dungeons name=D3Prison_RestartBeforeSave kind=jsl target=D3Prison_RestartBeforeSave expected_m=8 expected_x=8
  JSL D3Prison_RestartBeforeSave
assert pc() == $09F544
org $02DADB ; @hook module=Dungeons name=D3Prison_ApplyCellProfile kind=jsl target=D3Prison_ApplyCellProfile expected_m=8 expected_x=16
  JSL D3Prison_ApplyCellProfile
assert pc() == $02DADF
pullpc

endif
