; =========================================================
; Toto Ranch milk sale for the Ranch Girl (!ENABLE_RANCH_MILK).
; Included from Items/all_items.asm (bank $2B; banks $30/$32 are full);
; called from RanchGirl_TeachSong after the $187 offer box closes.
; =========================================================

; In: X = sprite slot, $1CE8 = choice (0 = Buy). Same price, bottle rule
; and replies as BottleVendor_BoughtMilkBottle. X preserved.
RanchGirl_SellMilk_Long:
{
  LDA.w $1CE8 : BNE .declined
  REP #$20
  LDA.l $7EF360 : CMP.w #$001E      ; 30 Rupees
  SEP #$20
  BCC .not_enough
  PHX
  LDX.b #$00
  .find
    LDA.l $7EF35C, X : CMP.b #$02 : BEQ .fill   ; $02 = empty bottle
  INX : CPX.b #$04 : BCC .find
  PLX
  %ShowUnconditionalMessage($0033)  ; no bottles available
  RTL
  .fill
  LDA.b #$0A : STA.l $7EF35C, X     ; $0A = milk
  PLX
  REP #$20
  LDA.l $7EF360 : SEC : SBC.w #$001E : STA.l $7EF360
  SEP #$20
  %ShowUnconditionalMessage($0188)  ; thank you
  RTL
  .not_enough
  %ShowUnconditionalMessage($0189)
  RTL
  .declined
  %ShowUnconditionalMessage($018B)  ; come back again
  RTL
}
