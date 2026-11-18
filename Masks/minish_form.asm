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
org $078427 : JSR $9BAA ; Link_HandleAPress ; @hook module=Masks name=$9BAA kind=jsr target=$9BAA

pullpc
; Walk onto the portal to shrink or grow (MinishPortal_Tick, bank $3A).
; Leave it before another transformation; no Y, R or D-pad release is required.
LinkState_CheckForMinishForm:
{
  SEP #$30
  JSL MinishPortal_Tick
  REP #$30
  RTS
}

; =========================================================

LinkState_CheckMinishTile:
{
  ; 16-bit A here: mask off $02B3 (item-binding RAM) so only the form byte counts.
  LDA $02B2 : AND.w #$00FF : BEQ .blocked ; no form
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

org $079C32 ; @hook module=Masks
  JSL CheckForMinishLift
