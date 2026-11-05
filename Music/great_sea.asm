; =========================================================
; The Legend of Zelda: Wind Waker - The Great Sea
; Kenta Nagata, Hajime Wakai, Toru Minegishi, and Koji Kondo
;
; Arrangement notes (2026-11-05 pass):
; - Main loop = 30 bars = one pass of the tympani bass line.
;   Every main channel is exactly 120 beats so nothing is cut off.
; - Intro = 12 bars on all three channels.
; - Choir pad: one held chord tone per bar, chosen to avoid clashes
;   with the trumpet melody.
; - Strings and piano play scawful's chug figure on each bass root;
;   piano is one octave up (ChannelTranspose +12).
; - Echo on choir, strings, piano and trumpet (not the tympani).
; - The earlier support trumpet and drafts are kept below under
;   "if 0" (not assembled).

; Test code to play the song as the game start (Only for Testing)
; Disabled: these orgs patch the ROM header and bank $0C.
; !n = $7F
; org $00FFD7 ; Set rom on 16mb
;   db #$0B
;
; org $3FFFFF ; write at the last position to expand on 2mb
;   db #$00
;
; org $0CC120
;   LDA #$02 : STA $012C
;   STA $2140 : STA $0133 : STA $0130
;   RTL

; Placement (2026-11-05): new overworld-bank song ID $10.
; No vanilla song is replaced. The data sits in the unused tail of the
; old Rain slot right after the Deku theme (label GreatDekuTreeThemeEnd)
; up to ROM $1AAB9F (no other song references these bytes). It starts at
; ROM $1AA7FB / ARAM $D902 when Deku is its original 152 bytes; the
; org below must equal Deku's end (asserted); the ARAM pointers follow it.
; ID $10 pointer = ARAM $D01E = ROM $1A9EF9 + 2*($10-1).
; IDs $10+ are underworld songs once the dungeon bank loads, so play
; $10 only while the overworld bank is loaded.
org $20B022 : assert pc() == owrom($1A9F17)
  dw owmain_aram(GreatSea) ; song $10 = Great Sea

org $20B91E : assert pc() == GreatDekuTreeThemeEnd, "Great Sea must start where Deku ends; update this org"
GreatSea:
{
  !ARAMAddr = owmain_aram(GreatSea)
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
    dw $0000
    dw .MainChannel5_Drums+!ARAMC
    dw $0000
    dw $0000

  ; ---------------------------------------------
  ; Intro Channels (12 bars each)
  {
    .Channel0_Choir
      %SetMasterVolume($C8)
      %SetTempo(86)              ; ~140 BPM (500*86/256 ticks/s, quarter = 72 ticks)
      %EchoVBits($0F, $14, $14)
      %EchoParams($02, $0A, $02)
      %Choir()
      %SetChannelVolume($A0)
      %SetPan($0A)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro_choir00+!ARAMC, 2) ; 3 plays = 12 bars
      db $00

    .Channel1_Strings
      %Strings()
      %SetChannelVolume($B0)
      %SetPan($0C)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro_strings+!ARAMC, 2) ; 3 plays = 12 bars
      db $00

    .Channel2_Piano
      %Piano()
      %SetChannelVolume($A0)
      %SetPan($08)
      %ChannelTranspose($0C)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.intro_lead+!ARAMC, 11) ; 12 plays = 12 bars
      db $00

  }

  ; ---------------------------------------------
  ; Main Channels (30 bars = 120 beats each)
  {

    .MainChannel0_Choir
      %Choir()
      %SetChannelVolume($A0)
      %SetDurationN(!4th, $7F) ; intro_lead left the duration at 1/8
      %CallSubroutine(.main_pad+!ARAMC, 0)
      db $00

    .MainChannel1_Strings
      %Strings()
      %SetChannelVolume($A8)
      %CallSubroutine(.r_Fs+!ARAMC, 1)
      %CallSubroutine(.r_G+!ARAMC, 1)
      %CallSubroutine(.r_A+!ARAMC, 1)
      %CallSubroutine(.r_G+!ARAMC, 1)
      %CallSubroutine(.r_Fs+!ARAMC, 1)
      %CallSubroutine(.r_E+!ARAMC, 1)
      %CallSubroutine(.r_A+!ARAMC, 1)
      %CallSubroutine(.r_D+!ARAMC, 1)
      %CallSubroutine(.r_Fs+!ARAMC, 1)
      %CallSubroutine(.r_G+!ARAMC, 1)
      %CallSubroutine(.r_A+!ARAMC, 1)
      %CallSubroutine(.r_G+!ARAMC, 1)
      %CallSubroutine(.r_Fs+!ARAMC, 0)
      %CallSubroutine(.r_B+!ARAMC, 0)
      %CallSubroutine(.r_As+!ARAMC, 1)
      %CallSubroutine(.r_C+!ARAMC, 1)
      db $00

    .MainChannel2_Piano
      %Piano()
      %SetChannelVolume($98)
      %ChannelTranspose($0C)
      %CallSubroutine(.r_Fs+!ARAMC, 1)
      %CallSubroutine(.r_G+!ARAMC, 1)
      %CallSubroutine(.r_A+!ARAMC, 1)
      %CallSubroutine(.r_G+!ARAMC, 1)
      %CallSubroutine(.r_Fs+!ARAMC, 1)
      %CallSubroutine(.r_E+!ARAMC, 1)
      %CallSubroutine(.r_A+!ARAMC, 1)
      %CallSubroutine(.r_D+!ARAMC, 1)
      %CallSubroutine(.r_Fs+!ARAMC, 1)
      %CallSubroutine(.r_G+!ARAMC, 1)
      %CallSubroutine(.r_A+!ARAMC, 1)
      %CallSubroutine(.r_G+!ARAMC, 1)
      %CallSubroutine(.r_Fs+!ARAMC, 0)
      %CallSubroutine(.r_B+!ARAMC, 0)
      %CallSubroutine(.r_As+!ARAMC, 1)
      %CallSubroutine(.r_C+!ARAMC, 1)
      db $00

    .MainChannel3_Trumpet
      %Trumpet()
      %SetChannelVolume($E8)
      %SetPan($0A)
      %TremoloOn(1, 4, 4)
      %CallSubroutine(.main_trumpet+!ARAMC, 0) ; 111 beats
      %CallSubroutine(.rest9+!ARAMC, 0)        ; 9 beats under the C chord
      db $00

    .MainChannel5_Drums
      %Tympani()
      %SetChannelVolume($B0)
      %SetPan($0A)
      %SetDurationN(!4th, $7F) ; 1/4
      %CallSubroutine(.main_drums+!ARAMC, 0) ; 30 bars
      db $00

  }

  ; ---------------------------------------------

  .rest9
    db !4th, Rest, Rest, Rest, Rest, Rest, Rest, Rest, Rest, Rest
    db $00

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

  ; Choir pad: one chord tone per bar, re-struck each bar.
  .main_pad
    db A3, Tie, Tie, Tie, A3, Tie, Tie, Tie
    db D4, Tie, Tie, Tie, D4, Tie, Tie, Tie
    db C4s, Tie, Tie, Tie, C4s, Tie, Tie, Tie
    db B3, Tie, Tie, Tie, B3, Tie, Tie, Tie
    db A3, Tie, Tie, Tie, A3, Tie, Tie, Tie
    db B3, Tie, Tie, Tie, B3, Tie, Tie, Tie
    db E4, Tie, Tie, Tie, E4, Tie, Tie, Tie
    db D4, Tie, Tie, Tie, D4, Tie, Tie, Tie
    db A3, Tie, Tie, Tie, A3, Tie, Tie, Tie
    db D4, Tie, Tie, Tie, D4, Tie, Tie, Tie
    db C4s, Tie, Tie, Tie, C4s, Tie, Tie, Tie
    db B3, Tie, Tie, Tie, B3, Tie, Tie, Tie
    db A3, Tie, Tie, Tie
    db B3, Tie, Tie, Tie
    db D4, Tie, Tie, Tie, D4, Tie, Tie, Tie
    db E4, Tie, Tie, Tie, E4, Tie, Tie, Tie
    db $00

  ; Strings/piano chug: scawful's main_piano figure, one bar per root.
  .r_Fs
    db !4th, F2s, !8th, Rest, F2s, Rest, !16th, F2s, Rest, F2s, Rest, F2s, Rest
    db $00
  .r_G
    db !4th, G2, !8th, Rest, G2, Rest, !16th, G2, Rest, G2, Rest, G2, Rest
    db $00
  .r_A
    db !4th, A2, !8th, Rest, A2, Rest, !16th, A2, Rest, A2, Rest, A2, Rest
    db $00
  .r_E
    db !4th, E2, !8th, Rest, E2, Rest, !16th, E2, Rest, E2, Rest, E2, Rest
    db $00
  .r_D
    db !4th, D2, !8th, Rest, D2, Rest, !16th, D2, Rest, D2, Rest, D2, Rest
    db $00
  .r_B
    db !4th, B2, !8th, Rest, B2, Rest, !16th, B2, Rest, B2, Rest, B2, Rest
    db $00
  .r_As
    db !4th, A2s, !8th, Rest, A2s, Rest, !16th, A2s, Rest, A2s, Rest, A2s, Rest
    db $00
  .r_C
    db !4th, C3, !8th, Rest, C3, Rest, !16th, C3, Rest, C3, Rest, C3, Rest
    db $00

  ; ---------------------------------------------
  ; Earlier drafts, not assembled.
  if 0
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
  endif

}

print "End of WW Great Sea ", pc
assert pc() <= owrom($1AABA0), "Great Sea overruns the free gap before song $04"
