; Paired cell65 inventory transaction, reusing historical CastleAmbushFlags.
; No new save byte or dialogue. Current receipt capture timing is unchanged;
; pending hall staging, patrol sight and wing restrictions remain separate.
if !ENABLE_D3_PRISON_CELL65 == 1

; Called before the existing capture warp commits. Carry1 accepts the capture.
; First capture records the actual sword, while recapture never replaces its
; backup with zero. Only the D3 blade hall or active prison rooms qualify.
D3Prison_CaptureSword:
{
  PHP : SEP #$20
  JSR D3Prison_InPlayerControl : BCC .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasEscaped : BNE .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasBeenCaptured : BEQ .first
  LDA.b $A0 : CMP.b #$64 : BEQ .retry
  CMP.b #$65 : BNE .no
  .retry
  JSL D3Prison_RestartEscape : BCC .no
  PLP : SEC : RTL
  .first
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #!CastleAmbush_AmbushPending : BNE .no
  LDA.b $A0 : CMP.b #$56 : BNE .no
  LDA.l Sword : BEQ .no
  CMP.b #$05 : BCS .no
  LDA.l CastleAmbushFlags : AND.b #$80 : PHA
  LDA.l Sword : ASL #4
  ORA.b #!CastleAmbush_HasBeenCaptured
  ORA $01,S : STA.l CastleAmbushFlags
  PLA
  LDA.b #$00 : STA.l Sword
  PLP : SEC : RTL
  .no
  PLP : CLC : RTL
}

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

D3Prison_RestartEscape:
{
  PHP
  SEP #$20
  ; Older two-bit captures retained their sword and have no backup. Adopt the
  ; actual valid inventory once; never guess a blade for an unarmed/malformed
  ; old save. Existing backed-up transactions retain their original sword.
  LDA.l CastleAmbushFlags : AND.b #$07
  CMP.b #!CastleAmbush_HasBeenCaptured : BNE .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_SwordMask : BNE .backed_up
  LDA.l Sword : BEQ .no
  CMP.b #$05 : BCS .no
  ASL #4 : ORA.l CastleAmbushFlags : STA.l CastleAmbushFlags
  .backed_up
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

D3Prison_Reclaim:
{
  PHP
  SEP #$20
  JSR D3Prison_InPlayerControl : BCC .no
  LDA.l $7E00A0 : CMP.b #$54 : BNE .no
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #!CastleAmbush_HasBeenCaptured : BNE .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_SwordMask
  LSR #4
  BEQ .no
  CMP.b #$05 : BCS .no
  PHA
  LDA.l Sword : CMP.b #$05 : BCS .bad_sword ; includes smith-held $FF
  CMP $01, S : BCS .keep_better_sword
  PLA : STA.l Sword
  BRA .commit
  .keep_better_sword
  PLA
  .commit
  LDA.l CastleAmbushFlags : ORA.b #!CastleAmbush_BladeReclaimed
  STA.l CastleAmbushFlags
  PLP
  SEC
  RTL
  .bad_sword
  PLA
  .no
  PLP
  CLC
  RTL
}

; The outward loader is not player-control module07. Test ownership alone;
; its caller already verifies the exact room55 outward transition.
D3Prison_HasReclaimedSword:
{
  PHP : SEP #$20
  LDA.l CastleAmbushFlags : AND.b #$0F
  CMP.b #(!CastleAmbush_HasBeenCaptured|!CastleAmbush_BladeReclaimed) : BNE .no
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_SwordMask : LSR #4
  BEQ .no
  CMP.b #$05 : BCS .no
  PHA
  LDA.l Sword : CMP.b #$05 : BCS .bad
  CMP $01,S : BCC .bad
  PLA : PLP : SEC : RTL
  .bad
  PLA
  .no
  PLP : CLC : RTL
}

D3Prison_InPlayerControl:
{
  LDA.l $7E0010 : CMP.b #$07 : BNE .no
  LDA.l $7E0011 : BNE .no
  JSR D3Prison_InDungeon
  RTS
  .no
  CLC
  RTS
}

D3Prison_InDungeon:
{
  LDA.l $7E001B : CMP.b #$01 : BNE .no
  LDA.l $7E040C : CMP.b #$10 : BNE .no ; actual Kalyxo Castle slot
  LDA.l $7E00A1 : BNE .no              ; full room ID, not low-byte alias
  SEC
  RTS
  .no
  CLC
  RTS
}

endif
