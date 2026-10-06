; =========================================================
; Village Elder
;
; NARRATIVE ROLE: Town authority figure who provides initial guidance
;   and sets OOSPROG bit 4 (no reader found). Gives the post-D1 hint.
;
; TERMINOLOGY: "Village Elder" = VillageElder
;   - Sets OOSPROG bit 4 on first meeting
;   - OOSPROG bit 4: no reader in ASM (2026-09-26)
;
; STATES:
;   Single state with branch on OOSPROG bit 4
;
; MESSAGES:
;   0x143 - First meeting
;   0x19 - Already met
;   0x1CB - Post-D1 ranch hint (the missing Ranch Girl); replaces vanilla
;           0x177, whose longer text does not fit vanilla text region 2
;
; FLAGS READ:
;   OOSPROG ($7EF3D6) bit 4 - Check if already met
;   $7EF37A bit 1 - Crystal_D1 (Mushroom Grotto complete)
;   $7EF37A bit 4 - Crystal_D2 (Tail Palace complete)
;   ElderGuideStage low nibble - guidance stage
;   MapIcon ($7EF3C7) - guidance marker
;
; FLAGS WRITTEN:
;   OOSPROG |= 0x10 - Elder met flag (bit 4)
;   ElderGuideStage low nibble = 1 (ranch hint delivered)
;   (MapIcon = !MapIcon_TailPond moved to the Ocarina receipt in
;   ranch_girl.asm; beat 10, dialogue audit D3)
;
; NOTE: OOSPROG bit 4 has no reader. Not the Master Sword gate (pedestal,
;   beat 25). See Docs/Technical/sram_flag_analysis.md.
;
; RELATED:
;   - sram.asm (OOSPROG definition)
;   - Docs/Technical/sram_flag_analysis.md (flag investigation)
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
  ; Post-D1 hint: look into the missing Ranch Girl (beat 10). Skipped once
  ; Link owns the Ocarina (the girl is already found).
  LDA.l $7EF37A : AND.b #!Crystal_D1_MushroomGrotto : BEQ .default_dialog
  LDA.l $7EF37A : AND.b #!Crystal_D2_TailPalace : BNE .default_dialog
  LDA.l Flute : BNE .default_dialog
  LDA.l ElderGuideStage : AND.b #$0F : CMP.b #$01 : BCS .default_dialog
    %ShowSolicitedMessage($1CB) : BCC .no_ranch_hint
      LDA.l ElderGuideStage : AND.b #$F0 : ORA.b #$01 : STA.l ElderGuideStage
    .no_ranch_hint
    RTS

  .default_dialog
  %ShowSolicitedMessage($019)
  RTS
}
