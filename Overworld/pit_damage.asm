; Pit hole leads to Houlihan room only in area 4F (final boss)
org $0794D9
  LDA $8A : CMP #$4F 
  BEQ .overworld_pit_transition
  JSL $01FFD9 ; TakeDamageFromPit
  RTS

.overworld_pit_transition