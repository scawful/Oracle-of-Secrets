; Reflect incoming downward pea shots at the front of an idle human shield.
; Called with M/X=8 and X=projectile slot; preserves X/Y/DBR. Original contact flags on fallback; outgoing nuts cannot hurt Link.
; Uses the vanilla north shield rectangle (Link X+4,Y; 8x4 pixels).
BusinessScrub_PeaShotContact:
{
  PHX
  PHY
  LDA.w SprYSpeed, X : BMI .safe_return
  BEQ .normal_damage
  LDA.l $7EF35A : BEQ .normal_damage ; Any owned shield blocks a nut.
  LDA.b $2F : BNE .normal_damage    ; Downward shot requires facing north.
  LDA.b $5D : ORA.b $3C : ORA.w $02E0 : ORA.w $037B : ORA.w $02B2
  BNE .normal_damage              ; Sword held, bunny, disabled or transformed.
  LDA.w $0308 : BMI .normal_damage
  LDA.b $EE : CMP.w SprFloor, X : BNE .normal_damage

  JSL Sprite_SetupHitBox
  LDA.b $22 : CLC : ADC.b #$04 : STA.b pos1_x_low
  LDA.b $23 : ADC.b #$00 : STA.b pos1_x_high
  LDA.b $20 : STA.b pos1_y_low
  LDA.b $21 : STA.b pos1_y_high
  LDA.b #$08 : STA.b pos1_size
  LDA.b #$04 : STA.b pos1_height
  JSL CheckIfHitBoxesOverlap : BCC .normal_damage

  LDA.b #$F0 : STA.w SprYSpeed, X
  STZ.w SprMiscC, X               ; The reflected shot now travels north.
  LDA.b #$06 : JSL SpriteSFX_QueueSFX2WithPan
  .safe_return
  PLY
  PLX
  CLC
  RTL

  .normal_damage
  PLY
  PLX
  JML Sprite_CheckDamageToPlayerSameLayer
}

; Returned-nut hit: start a dedicated 32-frame spin instead of inheriting
; the remaining post-attack cooldown. Caller has M/X=8, X=Scrub slot,
; DBR=bank30. Preserve X/Y/DBR and consume the existing child projectile.
BusinessScrub_BeginRecoil:
{
  PHX
  LDA.w Offspring1_Id : TAX
  STZ.w SprState, X
  PLX
  ; Match Sprite_BusinessScrub_Long dispatch: only ordinary Scrubs use
  ; the short timer. Eon Scrubs retain the original attack cooldown.
  LDA.w WORLDFLAG : BNE .keep_timer
  LDA.b #$20 : STA.w SprTimerA, X
  .keep_timer
  LDA.b #$03 : STA.w SprAction, X
  RTL
}
