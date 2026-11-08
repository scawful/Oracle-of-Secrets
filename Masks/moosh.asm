UpdateMooshPalette:
{
  REP #$30   ; change 16bit mode
  LDX #$001E

  .loop
  LDA.l MooshPalette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30 ; go back to 8 bit mode
  INC $15  ; update the palette
  RTL      ; or RTS depending on where you need it
}

MooshPalette:
  dw $0000, $7FFF, $237E, $46FF, $369E, $14A5, $01FF, $1078
  dw $6E25, $7AEF, $6759, $0A4A, $12EF, $2A5C, $1571, $7A18

Link_HoverIfMooshWantsToDash:
{
  LDA.w !CurrentMask : CMP.b #$07 : BNE .return
    JSL PrepareQuakeSpell
    RTL
  .return
  JSL Link_HandleMovingAnimation_FullLongEntry
  RTL
}

; Shared hover cancellation enters with M=8. Keep the ordinary Deku path;
; Moosh must not enter vanilla recoil with a zero timer or the takeoff bounce.
Moosh_EndHover:
{
  STZ.b $5D
  LDA.w !CurrentMask : CMP.b #$07 : BNE .done
    STZ.b DekuFloating
    STZ.b FallTimer
    LDA.b #$01 : STA.b $46
    LDA.b #$FF : STA.b $29
    STZ.w $02C7
  .done
  RTL
}

; The OAM hook enters with M/X=8, Y=$1C and DBR=$0D. Each direction in
; that animation family has three frames; $02 still contains the walking
; step ($2E), which can exceed two. Use a 0,1,2,1 wing cycle instead, leaving
; $2F to select the direction. Direct-page scratch is owned by the OAM caller.
Moosh_SelectHoverFrame:
{
  LDA.b $1A : LSR #3 : AND.b #$03
  CMP.b #$03 : BNE .store
    LDA.b #$01
  .store
  STA.b $02
  JML $0DA435 ; LinkOAM_ContinueWithAnimation
}
print "End of Masks/moosh.asm            ", pc

org $079093 ; @hook module=Masks
  JSL Link_HoverIfMooshWantsToDash
