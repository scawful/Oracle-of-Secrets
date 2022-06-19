; =============================================================================
;  Tilemap Menu background 

Menu_DrawBackground:
{
  REP #$30
  LDX.w #$FE ; $1700-17FF 

.loop
  LDA.w Menu_Tilemap, X
  STA.w $1000, X
  LDA.w Menu_Tilemap+$100, X
  STA.w $1100, X
  LDA.w Menu_Tilemap+$200, X
  STA.w $1200, X
  LDA.w Menu_Tilemap+$300, X
  STA.w $1300, X
  LDA.w Menu_Tilemap+$400, X
  STA.w $1400, X
  LDA.w Menu_Tilemap+$500, X
  STA.w $1500, X
  LDA.w Menu_Tilemap+$600, X
  STA.w $1600, X
  LDA.w Menu_Tilemap+$700, X
  STA.w $1700, X

  DEX : DEX
  BPL .loop

  RTS
}