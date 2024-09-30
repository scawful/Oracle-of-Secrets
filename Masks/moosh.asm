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
print "End of Masks/moosh.asm            ", pc

org $079093
  JSL Link_HoverIfMooshWantsToDash
