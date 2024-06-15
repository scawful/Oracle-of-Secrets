;=====================================================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda: Ocarina of Time - Lost Woods Theme v1.00
; Original Song by Koji Kondo
; Midi by John Kuzma
; ASM Framework by Zarby89
; Ported by Letterbomb
; Size 0x0246 (582 Decimal)
;=====================================================================================

org $1AADDE; Sections?
LostWoodsTheme: 
!ARAMAddr = $DEE5
dw !ARAMAddr+$0A ; Intro
dw !ARAMAddr+$1A ; Looping
dw $00FF
dw !ARAMAddr+$02 ; Looping Section
dw $0000


.ChannelsIntro
!ARAMC = !ARAMAddr-LostWoodsTheme
dw .Channel0Intro+!ARAMC
dw .Channel1Intro+!ARAMC
dw $0000
dw $0000
dw $0000
dw $0000
dw $0000
dw $0000


.Channels 
!ARAMC = !ARAMAddr-LostWoodsTheme
dw .Channel0+!ARAMC
dw .Channel1+!ARAMC
dw .Channel2+!ARAMC
dw .Channel3+!ARAMC
dw .Channel4+!ARAMC
dw .Channel5+!ARAMC
dw $0000
dw $0000



.Channel0Intro
%SetTempo(86);
%SetChannelVolume($60)
%SetInstrument($13) ; Snare
%SetDurationN($12, $7F) ; 1/16
%CallSubroutine(.sub0100+!ARAMC, 1)
db $00 ; End of the channel



.Channel1Intro
%SetChannelVolume($60)
%SetInstrument($0C) ; Cymbal
%SetDurationN($12, $7F) ; 1/16
%CallSubroutine(.sub0100+!ARAMC, 1)
db $00 ; End of the channel



.Channel0
db $12
%CallSubroutine(.sub0101+!ARAMC, 16)
%CallSubroutine(.sub0102+!ARAMC, 25)
%CallSubroutine(.sub0103+!ARAMC, 4)
%CallSubroutine(.sub0102+!ARAMC, 3)
%CallSubroutine(.sub0104+!ARAMC, 1)
db $00 ; End of the channel


.sub0100
db F5s, Tie, F5s, F5s, F5s, Tie, F5s, F5s, F5s, Tie, $24, F5s, Tie, C6
db $00 ; End

.sub0101
db F5s, Tie, F5s, F5s, F5s, Tie, F5s, Tie
db $00 ; End

.sub0102
db F5s, Tie, F5s, F5s
db $00 ; End

.sub0103
db $48, D6, $12, F5s, Tie, F5s, F5s
db $00 ; End

.sub0104
db F5s, Tie, F5s, F5s, Tie, Tie, F5s, Tie, $48, F5s, F5s
db $00 ; End



.Channel1
db $12
%CallSubroutine(.sub0101+!ARAMC, 16)
%CallSubroutine(.sub0102+!ARAMC, 25)
%CallSubroutine(.sub0103+!ARAMC, 4)
%CallSubroutine(.sub0102+!ARAMC, 3)
%CallSubroutine(.sub0104+!ARAMC, 1)
db $00 ; End of the channel



.Channel2
%SetChannelVolume($9E)
%SetInstrument($0F) ; Harp
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub201+!ARAMC, 4)
%CallSubroutine(.sub202+!ARAMC, 4)
%CallSubroutine(.sub201+!ARAMC, 4)
%CallSubroutine(.sub202+!ARAMC, 4)
db $24
%CallSubroutine(.sub203+!ARAMC, 3)
%CallSubroutine(.sub204+!ARAMC, 2)
%CallSubroutine(.sub205+!ARAMC, 2)
db E2, A2, Tie, A2, E2, B2, Tie, A2, E2, G2s, G2s, G2s, $48, G2s, B4
db $00 ; End of the channel


.sub201
db F2, Tie
db $00 ; End

.sub202
db C2, Tie
db $00 ; End

.sub203
db D2, F2, D2, F2, G1, D2, G1, G2, C2, G2, C2, G2, A1, E2, A1, E2
db $00 ; End

.sub204
db D2, A2, F2, Tie
db $00 ; End

.sub205
db C2, G2, G2, Tie
db $00 ; End



.Channel3
%SetChannelVolume($9E)
%SetInstrument($16) ; Flute
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub301+!ARAMC, 1)
db B4, G4, E4, $48, Tie, Tie, $24, D4, E4, G4, $48, E4, Tie, Tie, $24
%CallSubroutine(.sub301+!ARAMC, 1)
db E5, B4, G4, $48, Tie, Tie, $24, B4, G4, D4, E4, Tie, $48, Tie, Tie				
%CallSubroutine(.subA01+!ARAMC, 8)
db $24, F4, G4, A4, Tie, B4, C5, D5, Tie, E5, F5, $48, G5, Tie, Tie
%CallSubroutine(.subA01+!ARAMC, 8)
db $24, F4, E4, A4, G4, B4, A4, C5, B4, D5, C5, E5, D5, F5, E5, $12, B4, C5, Tie, A4, $48, B4, Tie, Tie, Tie
%CallSubroutine(.subA01+!ARAMC, 4)
db $00 ; End of the channel


.sub301
db F4, A4, B4, Tie, F4, A4, B4, Tie, F4, A4, B4, E5, D5, Tie, B4, C5
db $00 ; End



.Channel4
%SetChannelVolume($9F)
%SetInstrument($18) ; Guitar
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub401+!ARAMC, 1)
%CallSubroutine(.sub402+!ARAMC, 3)
%CallSubroutine(.sub403+!ARAMC, 1)
%CallSubroutine(.sub401+!ARAMC, 1)
%CallSubroutine(.sub402+!ARAMC, 3)
%CallSubroutine(.sub403+!ARAMC, 1)
%SetChannelVolume($9D)
%SetInstrument($09) ; Strings
%CallSubroutine(.sub501+!ARAMC, 1)
db B4, $48, E4, Tie, Tie, $24
%CallSubroutine(.sub501+!ARAMC, 1)
db D5, $48, E5, Tie, Tie, $24
%CallSubroutine(.sub501+!ARAMC, 1)
db B4, $48, E4, Tie, Tie, $24, D4, C4, F4, E4, G4, F4, A4, G4, B4, A4, C5, B4, D5, C5, $12, E5, F5, Tie, D5, $48, E5, Tie, Tie, Tie
%CallSubroutine(.subA01+!ARAMC, 4)
db $00 ; End of the channel


.sub401
db F3, C4, C4, C4
db $00 ; End

.sub402
db F3, A3, A3, A3
db $00 ; End

.sub403
db E3, G3, G3, G3, E3, G3, G3, C3, F3, C4, G3, G3, E3, G3, G3, C3
db $00 ; End



.Channel5
%SetChannelVolume($9D)
%SetInstrument($09) ; Strings
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub401+!ARAMC, 1)
%CallSubroutine(.sub402+!ARAMC, 3)
%CallSubroutine(.sub403+!ARAMC, 1)
%CallSubroutine(.sub401+!ARAMC, 1)
%CallSubroutine(.sub402+!ARAMC, 3)
%CallSubroutine(.sub403+!ARAMC, 1)
%SetChannelVolume($9F)
%SetInstrument($18) ; Guitar
%CallSubroutine(.sub501+!ARAMC, 1)
db B4, $48, E4, Tie, Tie, $24
%CallSubroutine(.sub501+!ARAMC, 1)
db D5, $48, E5, Tie, Tie, $24
%CallSubroutine(.sub501+!ARAMC, 1)
db B4, $48, E4, Tie, Tie, $24, D4, C4, F4, E4, G4, F4, A4, G4, B4, A4, C5, B4, D5, C5, $12, E5, F5, Tie, D5, $48, E5, Tie, Tie, Tie
%CallSubroutine(.subA01+!ARAMC, 4)
db $00 ; End of the channel


.sub501
db D4, E4, F4, Tie, G4, A4, B4, Tie, C5
db $00 ; End


.subA01
db Rest
db $00 ; End



print pc