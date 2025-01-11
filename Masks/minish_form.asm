; =========================================================
; Minish Form Link
;
; Reacts to Tile ID 64 to transform into Minish Link
; =========================================================

; Overworld Collision Tables
org $07DAF2
  dw LinkState_CheckForMinishForm ; Tile ID 64
  dw LinkState_CheckMinishTile    ; Tile ID 65

; Underworld Collision Tables
org $07D8A0
  dw LinkState_CheckForMinishForm
  dw LinkState_CheckMinishTile

; LinkState_Bunny.not_moving
org $078427 : JSR $9BAA ; Link_HandleAPress

pullpc
LinkState_CheckForMinishForm:
{
  SEP #$30
  LDA.l GameState : BEQ .return
    JSL $0FF979 ; AncillaSpawn_SwordChargeSparkle

    ; Check for the R button (like minish cap)
    JSL CheckNewRButtonPress : BCC .return

      ; Skip the code if you have a mask item out
      LDA $0202

      ; Check if the value in A (from $0202) is LT $13.
      CMP.b #$13 : BCC .continue

      ; Check if the value in A (from $0202) is GTE to $16.
      CMP.b #$17 : BCS .continue
        LDA.b #$3C : STA.w $012E ; Error beep
        JMP .return
      .continue

      LDA   !CurrentMask
      CMP.b #$05 : BEQ .already_minish ; return to human form
      CMP.b #$00 : BEQ .transform
      CMP.b #$06 : BCC .return         ; don't transform if not human
      .transform
      %PlayerTransform()

      LDA #$39 : STA $BC   ; Change link's sprite
      LDA #$05 : STA $02B2 ; Set the current mask form
      BRA .return

      .already_minish
      %PlayerTransform()
      JSL ResetToLinkGraphics

  .return
  REP #$30
  RTS
}

; =========================================================

LinkState_CheckMinishTile:
{
  LDA $02B2 : BEQ .blocked ; no form
    CMP.w #$0007 : BEQ .allowed  ; moosh can fly over
      CMP.w #$0005 : BNE .blocked  ; not minish
      .allowed
        LDA $0A : TSB $0343
        RTS

  .blocked
  LDA $0A : TSB $0E ; Blocked
  RTS
}

; Prevent lifting while minish
CheckForMinishLift:
{
  PHA
  LDA.w $02E0 : BNE .no_lift ; bunny form
  LDA.w $02B2 : CMP.b #$05 : BNE .return
  .no_lift
    PLA
    AND.l $7EF379 : AND.b #$80
    RTL
  .return
  PLA
  AND.l $7EF379
  RTL
}

print  "End of Masks/minish_form.asm      ", pc
pushpc

org $079C32
  JSL CheckForMinishLift
