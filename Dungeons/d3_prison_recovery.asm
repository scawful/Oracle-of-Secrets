; Paired prison recovery and key-block bypass guard. No new save field.
if !ENABLE_D3_PRISON_CELL65 == 1
; Object_KeyBlock enters inside OpenItemChest with M16/X16, DP0 and its
; PHB/PHA/PHY still on the stack. Preserve X/Y/DB and return through the native
; exits that unwind that stack; never RTL from this long-jump replacement.
; Only cell65 in D3 is sealed while captured and not yet escaped.
; Sword-backup validity must not permit a carried-key bypass in old saves.
; The ordinary path retains Oracle's small-key behavior, including the adjacent
; high byte of the 16-bit SRAM access. Big Key inventory is never consulted.
D3Prison_CellKeyBlockGate:
{
  LDA.l $7E00A0 : CMP.w #$0065 : BNE .ordinary
  LDA.l $7E001B : AND.w #$00FF : CMP.w #$0001 : BNE .ordinary
  LDA.l $7E040C : AND.w #$00FF : CMP.w #$0010 : BNE .ordinary
  LDA.l CastleAmbushFlags
  AND.w #(!CastleAmbush_HasBeenCaptured|!CastleAmbush_HasEscaped)
  CMP.w #!CastleAmbush_HasBeenCaptured : BEQ .denied
  .ordinary
  LDA.l $7EF36F : AND.w #$00FF : BEQ .denied
  LDA.l $7EF36F
  DEC A
  STA.l $7EF36F
  JML $01EBA6 ; .open_big_key_lock: set room flag and redraw
  .denied
  JML $01EBE1 ; .cannot_open_big_key_lock: unwind and return Carry clear
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
  LDA.w #$0000 : STA.l D3Prison_ExitMessage
  JSL D3Prison_RestartEscape
  REP #$20
  PLA
  PLP
  RTL
}

pushpc
assert read4($09F540) == $0BFFBF22, "Prison save restart preimage changed"
org $09F540 ; @hook module=Dungeons name=D3Prison_RestartBeforeSave kind=jsl target=D3Prison_RestartBeforeSave expected_m=8 expected_x=8
  JSL D3Prison_RestartBeforeSave
pullpc
endif
