; =========================================================
; The Legend of Zelda: Wind Waker - Ganondorf Battle
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

; org $1BAD7A
; GanondorfBattle:  
; ARAMAddr = $2BB3
org $1A9FF8
print pc
GanondorfBattle: 
{
  !ARAMAddr = $D0FF
  dw !ARAMAddr+$0A ; Intro
  dw !ARAMAddr+$1A ; Looping
  dw $00FF
  dw !ARAMAddr+$02 ; Looping Section
  dw $0000

  .ChannelsIntro
  !ARAMC = !ARAMAddr-GanondorfBattle
    dw .IntroChannel0_Trombone+!ARAMC
    dw .IntroChannel1_ChoirAndTrumpet+!ARAMC
    dw .IntroChannel2_Strings+!ARAMC
    dw .IntroChannel4_TimpaniAndSnare+!ARAMC
    dw .IntroChannel5_Cymbal+!ARAMC
    dw .IntroChannel3_Horn+!ARAMC
    dw $0000
    dw $0000

  .Channels
  !ARAMC = !ARAMAddr-GanondorfBattle
    dw .Channel0_Piano+!ARAMC
    dw .Channel1_Horn+!ARAMC
    dw .Channel2_Trumpet+!ARAMC
    dw .Channel3_TromboneAndCymbal+!ARAMC
    dw .Channel4_Timpani+!ARAMC
    dw .Channel5_Snare+!ARAMC
    dw $0000 ; dw .Channel6+!ARAMC
    dw $0000

  ; ---------------------------------------------
  ; Intro Channels
  {  
    .IntroChannel0_Trombone
      %SetMasterVolume($88)
      %SetTempo(100)
      %Trombone()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro+!ARAMC, 1)
      %CallSubroutine(.strings01+!ARAMC, 1)
      %CallSubroutine(.sustain+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 6)
      db $00

    .IntroChannel1_ChoirAndTrumpet
      %Choir()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro+!ARAMC, 1)
      %Trumpet()
      %CallSubroutine(.strings01+!ARAMC, 1)
      %CallSubroutine(.sustain+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 6)
      db $00

    .IntroChannel2_Strings
      %Strings()
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro+!ARAMC, 1)
      %CallSubroutine(.strings01+!ARAMC, 1)
      %CallSubroutine(.sustain+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 6)
      db $00

    .IntroChannel3_Horn
      %Horn()
      %SetChannelVolume($C8)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro+!ARAMC, 1)
      %CallSubroutine(.strings01+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 6)
      db $00

    .IntroChannel4_TimpaniAndSnare
      %Tympani()
      %SetChannelVolume($C8)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.silence+!ARAMC, 3)
      %CallSubroutine(.drums+!ARAMC, 1)
      %CallSubroutine(.sustain+!ARAMC, 4)
      %Snare()
      %SetDurationN(!32nd, $7F) ; 1/32
      %CallSubroutine(.snare00+!ARAMC, 8)
      db $00

    .IntroChannel5_Cymbal
      %Cymbal()
      %SetChannelVolume($F8)
      %SetDurationN(!4th, $7F) ; 1/4
      %EchoVBits($FF, $1E, $1E)
      %EchoParams($01, $14, $02)
      %CallSubroutine(.silence+!ARAMC, 3)
      %CallSubroutine(.drums+!ARAMC, 1)
      db !4th, G2, Tie, Tie
      %CallSubroutine(.silence+!ARAMC, 8)
      db $00
  }

  ; ---------------------------------------------
  ; Main Channels
  {
    .Channel0_Piano
      %SetMasterVolume($C8)
      %Piano()

      %SetChannelVolume($F8)
      %SetDurationN(!4th, $7F) ; 1/4

      %EchoVBits($FF, $1E, $1E)
      %EchoParams($02, $14, $02)

      %CallSubroutine(.piano01+!ARAMC, 2)
      %CallSubroutine(.piano02+!ARAMC, 1)
      %CallSubroutine(.piano01+!ARAMC, 2)
      %CallSubroutine(.piano02+!ARAMC, 1)
      %CallSubroutine(.piano03+!ARAMC, 1)
      %CallSubroutine(.piano04+!ARAMC, 1)

      %CallSubroutine(.piano02+!ARAMC, 1)
      %CallSubroutine(.piano01+!ARAMC, 1)
      %CallSubroutine(.piano02+!ARAMC, 1)
      %CallSubroutine(.piano01+!ARAMC, 1)
      %CallSubroutine(.piano02+!ARAMC, 1)
      %CallSubroutine(.piano03+!ARAMC, 1)
      %CallSubroutine(.piano04+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 96)
      db $00

    .Channel1_Horn
      %Horn()
      %SetChannelVolume($DC)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.silence+!ARAMC, 4)

        %CallSubroutine(.horn01+!ARAMC, 1)
        %CallSubroutine(.horns02+!ARAMC, 1)
        %CallSubroutine(.horns03+!ARAMC, 1)
        %CallSubroutine(.horns02+!ARAMC, 1)

      %CallSubroutine(.silence+!ARAMC, 72)
      
      db $00

    .Channel2_Trumpet
      %Trumpet()
      %SetChannelVolume($E8)
      %SetDurationN(!4th, $7F) ; 1/4
      
      %CallSubroutine(.silence+!ARAMC, 4)
      
        %CallSubroutine(.horn01+!ARAMC, 1)
        %CallSubroutine(.horns02+!ARAMC, 1)
        %CallSubroutine(.horns03+!ARAMC, 1)
        %CallSubroutine(.horns02+!ARAMC, 1)

      %CallSubroutine(.intro+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 4)
      %CallSubroutine(.intro+!ARAMC, 1)
      %CallSubroutine(.silence+!ARAMC, 96)
      db $00

    .Channel3_TromboneAndCymbal
      %Trombone()
      %SetChannelVolume($BC)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.silence+!ARAMC, 4)
      ; %TremoloOn(10, 4, 50)
        %CallSubroutine(.horn01+!ARAMC, 1)
        %CallSubroutine(.horns02+!ARAMC, 1)
        %CallSubroutine(.horns03+!ARAMC, 1)
        %CallSubroutine(.horns02+!ARAMC, 1)
      ; %TremoloOff()

      %CallSubroutine(.intro+!ARAMC, 1)
        %Cymbal()
        %SetChannelVolume($F8)
        %SetDurationN(!4th, $7F) ; 1/4
        %EchoVBits($FF, $1E, $1E)
        %EchoParams($01, $14, $02)
      %CallSubroutine(.drums+!ARAMC, 1)
      db !4th, G2, Tie, Tie
      %Trombone()
      %CallSubroutine(.silence+!ARAMC, 96)
      
      db $00

    .Channel4_Timpani
      %Tympani()
      %SetChannelVolume($78)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.timpani01+!ARAMC, 12)
      %Choir()
      %SetChannelVolume($A8)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.choir01+!ARAMC, 2)
      db $00

    .Channel5_Snare
      %Snare()
      %SetChannelVolume($8C)
      %SetDurationN(!32nd, $7F) ; 1/32
      %CallSubroutine(.snare01+!ARAMC, 24)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.silence+!ARAMC, 32)
      %SetDurationN(!32nd, $7F) ; 1/32
      %CallSubroutine(.snare01+!ARAMC, 32)
      db $00

  }

  ; ---------------------------------------------

  .silence
    db Rest, $00

  .sustain
    db Tie, $00

  ; 4 bars
  .intro
    db D4s, D4, F4s, F4, Tie, D4s, !16th, D4, Tie, F4s, Tie
    db !4th, F4, !16th, D4s, Tie, D4, Tie, !4th, F4s, F4, Rest
    db $00 ; End

  .snare00
    db E5
    db $00

  .snare01
    db E5, Rest
    db E5, Rest
    db E5, Rest
    db E5, Rest
    db E5, Rest, Rest, Rest
    db E5, Rest, Rest, Rest
    db $00

  .choir01
    db !4th, G3s, Tie, Tie, !8th, D3s, Tie, !4th, G3, Tie, Tie, !8th, F3, Tie
    db !4th, D3s, Tie, Tie, !8th, F3, Tie, !4th, D3, Tie, Tie, Tie
    db $00

  .piano01
    db !8th, G1, C2, A1s, G1,   !4th, C2, C2
    db $00

  .piano02
    db !8th, G1, C2, A1s, G1,   !4th, C2, C2s
    db !8th, G1s, C2s, B1, G1s, !4th, C2s, E2
    db !8th, G1s, C2s, B1, G1s, !4th, C2s, E2
    db !8th, G1, C2, A1s, G1,   !4th, C2, C2s
    db !8th, G1s, C2s, B1, G1s, !4th, C2s, E2
    db !8th, G1s, C2s, B1, G1s, !4th, C2s, E2
    db $00

  .piano03
    db !8th, G1s, C2s, B1, G1s, !4th, C2s, E2
    db !8th, G1s, C2s, B1, G1s, !4th, C2s, !8th, E2, G2, F2
    db !4th, D2s, Tie, C2s
    db $00

  .piano04
    db !8th, E2, G2, F2
    db !4th, D2s, Tie, C2s, Tie, Tie, Tie, Tie, F1
    db $00

  .drums
    db G2, Tie, Tie, G2, Tie, G2, Tie, Tie
    db $00

  .strings01
    db !8th, G3s, A3s, !4th, Rest, !8th, G3, G3s, !4th, D3s, E3
    db !4th, Rest
    db !8th, G3s, A3s, !4th, Rest, !8th, G3, G3s, !4th, D2, F2, Tie
    db $00

  .timpani01
    db !8th, G1, !4th, C2, !8th, G1, !4th, C2, C2, !8th, G1, !4th, C2, !8th, G1, !4th, C2
    db $00

  .horn01
    db !8th, G3, !4th, A3s,      !8th, G3, F3s, !4th, G3
    db !16th, F3s, Tie, G3, Tie, !8th, A3s, B3, !4th, G3
    db !16th, F3, Tie, F3s, Tie, F3, Tie, !8th, D3, C3s, D3, Tie
    db $00

  .horns02
    db !8th, D3, F3, F3s, !4th, A3
    db !8th, G3s, !4th, B3
    db !8th, A3s, !4th, C4s, Tie
    db B3, !8th, A3, A3, !4th, A3s, E3, G3
    db $00
  
  .horns03
    db F3s, G3, Tie, !8th, F3s, G3, !4th, A3s, B3
    db G3, !8th, F3, F3s, F3, !4th, D3, C3s, D3, Tie
    db $00

}

print "End of WW Ganondorf ", pc