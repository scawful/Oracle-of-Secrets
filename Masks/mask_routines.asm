; no glove color 
org $0DEE24
 db $80

org $09912C
AddTransformationCloud:

org $07B073
Link_CheckNewY_ButtonPress:

org $078028
Player_DoSfx2:

org $278000
StartupMasks:
{
  ; from vanilla:
  ; bring the screen into force blank after NMI
  LDA.b #$80 : STA $13

  ; set links sprite bank 
  LDA #$10 : STA $BC

  RTL 
}

org $008827
JSL StartupMasks
