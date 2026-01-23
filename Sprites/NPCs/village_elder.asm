; =========================================================
; Village Elder
;
; NARRATIVE ROLE: Town authority figure who provides initial guidance
;   and sets a major story progression flag. Meeting the Elder is a
;   prerequisite for later content (possibly Master Sword related).
;
; TERMINOLOGY: "Village Elder" = VillageElder
;   - Sets OOSPROG bit 4 on first meeting
;   - OOSPROG bit 4 purpose unclear (Master Sword prerequisite?)
;
; STATES:
;   Single state with branch on OOSPROG bit 4
;
; MESSAGES:
;   0x143 - First meeting
;   0x19 - Already met
;
; FLAGS READ:
;   OOSPROG ($7EF3D6) bit 4 - Check if already met
;
; FLAGS WRITTEN:
;   OOSPROG |= 0x10 - Elder met flag (bit 4)
;
; NOTE: The purpose of OOSPROG bit 4 is unclear from the code.
;   It may be a Master Sword prerequisite or general story gate.
;   See sram_flag_analysis.md for investigation notes.
;
; RELATED:
;   - sram.asm (OOSPROG definition)
;   - sram_flag_analysis.md (flag investigation)
; =========================================================

Sprite_VillageElder_Main:
{
  %PlayAnimation(2,3,16)
  JSL Sprite_PlayerCantPassThrough
  REP #$30
  LDA.l OOSPROG : AND.w #$00FF
  SEP #$30
  AND.b #$10 : BNE .already_met
    %ShowSolicitedMessage($143) : BCC .no_message
      LDA.l OOSPROG : ORA.b #$10 : STA.l OOSPROG
    .no_message
    RTS

  .already_met
  %ShowSolicitedMessage($019)
  RTS
}
