; =========================================================
; The Legend of Zelda: Wind Waker - The Great Sea
; Kenta Nagata, Hajime Wakai, Toru Minegishi, and Koji Kondo

; Test code to play the song as the game start (Only for Testing)
!n = $7F
org $00FFD7 ; Set rom on 16mb
  db #$0B

org $3FFFFF ; write at the last position to expand on 2mb
  db #$00

org $0CC120
  LDA #$02 : STA $012C
  STA $2140 : STA $0133 : STA $0130
  RTL

; !ARAMAddr = $2BB3
org $1A9FF8
GreatSea: 
{
  !ARAMAddr = $D0FF
  dw !ARAMAddr+$0A ; Intro
  dw !ARAMAddr+$1A ; Looping
  dw $00FF
  dw !ARAMAddr+$02 ; Looping Section
  dw $0000

  .ChannelsIntro
  !ARAMC = !ARAMAddr-GreatSea
    dw .Channel0_Choir+!ARAMC
    dw .Channel1_Strings+!ARAMC
    dw .Channel2_Piano+!ARAMC
    dw $0000
    dw $0000
    dw $0000
    dw $0000
    dw $0000

  .Channels
  !ARAMC = !ARAMAddr-GreatSea
    dw .MainChannel0_Choir+!ARAMC
    dw .MainChannel1_Strings+!ARAMC
    dw .MainChannel2_Piano+!ARAMC
    dw .MainChannel3_Trumpet+!ARAMC
    dw .MainChannel4_TrumpetSupport+!ARAMC
    dw .MainChannel5_Drums+!ARAMC
    dw $0000
    dw $0000

  ; ---------------------------------------------
  ; Intro Channels
  {  
    .Channel0_Choir
      %SetMasterVolume($C8)
      %SetTempo(100)
      %Choir()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro_choir00+!ARAMC, 2)
      db $00

    .Channel1_Strings
      %Strings()
      %SetChannelVolume($D8)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro_strings+!ARAMC, 8)
      db $00

    .Channel2_Piano
      %Piano()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro_lead+!ARAMC, 8)
      db $00

  }

  ; ---------------------------------------------
  ; Main Channels
  {

    .MainChannel0_Choir
      %Choir()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.main_choir00+!ARAMC, 8)
      %CallSubroutine(.intro_lead+!ARAMC, 8) ; Change me
      %CallSubroutine(.main_choir00+!ARAMC, 8) ; Change me
      db $00
   
    .MainChannel1_Strings
      %Strings()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.main_piano+!ARAMC, 8)
      %CallSubroutine(.intro_lead+!ARAMC, 8)  ; Change me
      %CallSubroutine(.main_piano+!ARAMC, 4)
      db $00

    .MainChannel2_Piano
      %Piano()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.main_piano+!ARAMC, 8)
      %CallSubroutine(.intro_lead+!ARAMC, 8)
      %CallSubroutine(.main_piano+!ARAMC, 4)
      db $00

    .MainChannel3_Trumpet
      %Trumpet()
      %SetDurationN(!4th, $7F)
      %TremoloOn(1, 4, 4)
      %CallSubroutine(.main_trumpet+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 32)
      %CallSubroutine(.main_trumpet+!ARAMC, 1)
      %TremoloOff()
      db $00

    .MainChannel4_TrumpetSupport
      %Trumpet()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.support_trumpet+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 32)
      %CallSubroutine(.main_piano_support_trumpet+!ARAMC, 1)
      db $00

    .MainChannel5_Drums
      %Tympani()
      %SetChannelVolume($88)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.main_drums+!ARAMC, 32)
      db $00

  }

  ; ---------------------------------------------

  .silence
    db Rest, $00

  .sustain
    db Tie, $00

  .intro_choir00
    db F3s, Tie, Tie, Tie, G3s, Tie, Tie, Tie, F3s, Tie, Tie, Tie, A3, Tie, Tie, Tie
    db $00

  .intro_strings
    db D3, Tie, Tie, Tie
    db E3, Tie, Tie, Tie
    db D3, Tie, Tie, Tie
    db C3s, Tie, Tie, Tie
    db $00

  .intro_lead
    db !8th, D2, A2, D3, !4th, E3, !8th, D3, D3, A2
    db $00

  .main_drums
    db F1s, Tie, Tie, Tie, F1s, Tie, Tie, Tie
    db G1, Tie, Tie, Tie, G1, Tie, Tie, Tie
    db A1, Tie, Tie, Tie, A1, Tie, Tie, Tie
    db G1, Tie, Tie, Tie, G1, Tie, Tie, Tie
    db F1s, Tie, Tie, Tie, F1s, Tie, Tie, Tie
    db E1, Tie, Tie, Tie, E1, Tie, Tie, Tie
    db A1, Tie, Tie, Tie, A1, Tie, Tie, Tie
    db D1, Tie, Tie, Tie, D1, Tie, Tie, Tie
    db F1s, Tie, Tie, Tie, F1s, Tie, Tie, Tie
    db G1, Tie, Tie, Tie, G1, Tie, Tie, Tie
    db A1, Tie, Tie, Tie, A1, Tie, Tie, Tie
    db G1, Tie, Tie, Tie, G1, Tie, Tie, Tie
    db F1s, Tie, Tie, Tie, B1, Tie, Tie, Tie
    db A1s, Tie, Tie, Tie, A1s, Tie, Tie, Tie
    db C2, Tie, Tie, Tie, C2, Tie, Tie, Tie
    db $00

  .main_choir00
    db D3, Tie, D3, Tie, E3, Tie, D3, Tie, D3, Tie, D3, Tie, D3, Tie, C3s, Tie
    db $00

  .main_piano
    db !4th, D1, !8th, Rest, D1, Rest, !16th, D1, Rest, D1, Rest, D1, Rest
    db !4th, D1, !8th, Rest, D1, Rest, !16th, D1, Rest, D1, Rest, D1, Rest
    db !4th, F1s, !8th, Rest, F1s, Rest, !16th, F1s, Rest, F1s, Rest, F1s, Rest
    db !4th, F1s, !8th, Rest, F1s, Rest, !16th, F1s, Rest, F1s, Rest, F1s, Rest
    db !4th, G1, !8th, Rest, G1, Rest, !16th, G1, Rest, G1, Rest, D1, Rest
    db !4th, G1, !8th, Rest, G1, Rest, !16th, G1, Rest, G1, Rest, G1, Rest
    db $00

  .main_piano_support_trumpet
    db !4th, D3, !8th, Rest, D3, Rest, !16th, D3, Rest, D3, Rest, D3, Rest
    db !4th, D3, !8th, Rest, D3, Rest, !16th, D3, Rest, D3, Rest, D3, Rest
    db !4th, F3s, !8th, Rest, F3s, Rest, !16th, F3s, Rest, F3s, Rest, F3s, Rest
    db !4th, F3s, !8th, Rest, F3s, Rest, !16th, F3s, Rest, F3s, Rest, F3s, Rest
    db !4th, G3, !8th, Rest, G3, Rest, !16th, G3, Rest, G3, Rest, D3, Rest
    db !4th, G3, !8th, Rest, G3, Rest, !16th, G3, Rest, G3, Rest, G3, Rest
    db $00

  .main_trumpet
    db !8th, F3s, !16th, Rest, D3
    db !4th, A2, Tie, Tie, Tie, Tie, Tie
    db !16th, D3, A2, D3, F3s, !4th 
    db A3, Tie, Tie, Tie, Tie, Tie, Tie
    db !16th, A3, Rest, G3, F3s

    db !4th, G3, Tie, Tie, Tie, Tie, Tie, Tie, Tie
    db E3, Tie, Tie, Tie, Tie, Tie
    db A2, Tie

    db !16th, B2, Rest, B2, C3s
    db !4th, D3, Tie, Tie, Tie, Tie, Tie, E3
    db D3, Tie, Tie, Tie
    db A2, Tie, Tie, Tie

    db !16th, B2, Rest, B2, C3s
    db !4th, D3, Tie, Tie, Tie, Tie, Tie, E3
    db D3, Tie, Tie, Tie
    db E3, Tie, Tie, Tie
    db !8th, F3s, !16th, Rest, D3

    db !4th, A2, Tie, Tie, Tie, Tie, Tie
    
    db !16th, D3, A2, D3, F3s
    db !4th, A3, Tie, Tie, Tie, Tie, Tie, Tie
    db !16th, A3, Rest, G3, F3s
    db !4th, G3, Tie, Tie, Tie, Tie, Tie, Tie, Tie
    db E3, Tie, Tie, Tie, Tie, Tie

    db !16th, A2, Tie, Tie, Tie
    db !16th, B2, Rest, B2, C3s
    db !4th, D3, Tie, Tie, Tie, Tie, Tie, E3
    db D3, Tie, Tie, Tie
    db E3, Tie, Tie, Tie
    db $00

  .support_trumpet
    db A2, Tie, Tie, Tie, Tie, Tie, Tie, Tie
    db E3, Tie, Tie, Tie

    db D3, Tie, Tie, Tie
    db D3, Tie, Tie, Tie, Tie, Tie, Tie, Tie
    db E3, Tie, Tie
    db !16th, A3, A3, A3
    db !4th, A3, Tie, Tie, Tie

    db Rest, Rest, Rest, Rest
    db !16th, B2, Rest, B2, C3s
    db !4th, D3, Tie, Tie, Tie
    db D3, Tie, Tie, Tie
    db A2, Tie, Tie, Tie

    ; 21 
    db Rest, Rest, Rest, Rest 
    db !16th, B2, Rest, B2, C3s
    db !4th, D3, Tie, Tie
    db B2, Tie, Tie, Tie
    db C3s, Tie, Tie, Tie
    db A2, Tie, Tie, Tie
    db !8th, F3s, !16th, Rest, D3
    db !4th, A2, Tie, Tie ; 26

    db E3, Tie, Tie, Tie
    db D3, Tie, Tie, Tie
    db D3, Tie, Tie
    db !16th, A3, Rest, G3, F3s

    ; 30
    db !4th, G3, Tie, Tie, Tie
    db E3, Tie, Tie
    db !16th, A3, A3, A3
    db !4th, A3, Tie, Tie, Tie

    ; 33
    db Rest, Rest, Rest, Rest
    db !16th, B2, Rest, B2, C3s
    db !4th, D3, Tie, Tie, Tie
    db D3, Tie, Tie, Tie
    db E3, D3, Tie, Tie, Tie

    db Rest, Rest, Rest, Rest
    db !16th, A2s, Rest, A2s, C3
    db !4th, D3, Tie, Tie, Tie
    db !16th, A2s, Rest, A2s, C3
    db !4th, D3, Tie, Tie, Tie
    db E3, D3, Tie, Tie, Tie
    db $00

}

print "End of WW Great Sea ", pc