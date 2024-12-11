;=====================================================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda: Four Swords Adventures - Frozen Hyrule Theme v1.01
; Original Song by Koji Kondo & Asuka Ohta
; Midi by Matmax14
; ASM Framework by Zarby89
; Ported by Letterbomb
;=====================================================================================

; lorom

; org $1ACCAB; Sections?
FrozenHyruleTheme: 
!ARAMAddr = $EF6D
dw !ARAMAddr+$0A ; Intro
dw !ARAMAddr+$1A ; Looping
dw $00FF
dw !ARAMAddr+$02 ; Looping Section
dw $0000

.ChannelsIntro
!ARAMC = !ARAMAddr-FrozenHyruleTheme
dw .Channel0Intro+!ARAMC
dw .Channel1Intro+!ARAMC
dw .Channel2Intro+!ARAMC
dw $0000
dw $0000
dw $0000
dw $0000
dw $0000

.Channels
!ARAMC = !ARAMAddr-FrozenHyruleTheme
dw .Channel0+!ARAMC
dw .Channel1+!ARAMC
dw .Channel2+!ARAMC
dw .Channel3+!ARAMC
dw .Channel4+!ARAMC
dw .Channel5+!ARAMC
dw $0000
dw $0000


.Channel0Intro
%SetMasterVolume($80)
%SetTempo(80);
%SetInstrument($15) ; Choir
%SetDurationN($48, $7F) ; 1/4
db $E3, $EF, $EF, $CF
%CallSubroutine(.sub1+!ARAMC, 8)
db $E4
db $00 ; End of the channel


.Channel1Intro
%SetInstrument($0F) ; Harp
%SetDurationN($48, $7F) ; 1/4
db Rest
%CallSubroutine(.sub4+!ARAMC, 6)
db $24, Rest, G3, C3
%CallSubroutine(.sub4+!ARAMC, 14)
db $00 ; End of the channel


.Channel2Intro
%SetInstrument($09) ; Strings
%SetDurationN($12, $7F) ; 1/16
db Rest
%CallSubroutine(.sub4+!ARAMC, 32)
%CallSubroutine(.sub21+!ARAMC, 1)
db $00 ; End of the channel


.Channel0
db C3, Tie, Tie, Tie, F2, Tie, Tie, Tie
%CallSubroutine(.sub2+!ARAMC, 1)
%CallSubroutine(.sub1+!ARAMC, 4)
db C3, Tie, Tie, Tie, A2, Tie, Tie, Tie
%CallSubroutine(.sub2+!ARAMC, 1)
%CallSubroutine(.sub1+!ARAMC, 4)
%CallSubroutine(.sub3+!ARAMC, 1)
db C3, Tie, Tie, Tie, G2s, Tie, Tie, Tie
%CallSubroutine(.sub3+!ARAMC, 2)
db C3, Tie, Tie, Tie, C3s, Tie, Tie, Tie, C3, Tie, Tie, Tie, G2, Tie, G2, Tie, A2s, Tie, A2s
%CallSubroutine(.sub4+!ARAMC, 5)
db A2, Tie, Tie, Tie
%CallSubroutine(.sub2+!ARAMC, 1)
db G2, Tie, Tie, Tie, A2s, Tie, Tie, Tie, F3s, Tie, Tie, Tie, F3, Tie, F3, Tie
%CallSubroutine(.sub1+!ARAMC, 8)
db $00 ; End of the channel

.sub1
db C3, Tie
db $00 ; End

.sub2
db G2s, Tie, Tie, Tie, G2, Tie, Tie, Tie
db $00 ; End

.sub3
db A2s, Tie, Tie, Tie
db $00 ; End

.sub4
db Tie
db $00 ; End


.Channel1
db $24, G2
%CallSubroutine(.sub5+!ARAMC, 1)
%CallSubroutine(.sub6+!ARAMC, 1)
%CallSubroutine(.sub7+!ARAMC, 1)
db G2
%CallSubroutine(.sub4+!ARAMC, 6)
db D2, $48, C2, Tie, $24, F2, Tie, Tie, G2, $48, C2, Tie, G2, Tie, $24
%CallSubroutine(.sub5+!ARAMC, 1)
db F3
%CallSubroutine(.sub4+!ARAMC, 6)
db F3
%CallSubroutine(.sub7+!ARAMC, 1)
db G2
%CallSubroutine(.sub4+!ARAMC, 5)
db G2, G2, C3
%CallSubroutine(.sub4+!ARAMC, 7)
db G2
%CallSubroutine(.sub5+!ARAMC, 1)
db D3s
%CallSubroutine(.sub4+!ARAMC, 7)
db F3
%CallSubroutine(.sub4+!ARAMC, 6)
db A2s, G2s
%CallSubroutine(.sub4+!ARAMC, 5)
db G2s, G2s, A2s
%CallSubroutine(.sub4+!ARAMC, 7)
db D3s
%CallSubroutine(.sub4+!ARAMC, 7)
db F3
%CallSubroutine(.sub4+!ARAMC, 7)
db E3
%CallSubroutine(.sub4+!ARAMC, 7)
db D3
%CallSubroutine(.sub4+!ARAMC, 7)
db G3
%CallSubroutine(.sub4+!ARAMC, 6)
db D3, G3
%CallSubroutine(.sub4+!ARAMC, 6)
db D3
%CallSubroutine(.sub4+!ARAMC, 64)
db C2
%CallSubroutine(.sub4+!ARAMC, 14)
db G1, C2
%CallSubroutine(.sub4+!ARAMC, 14)
db $00 ; End of the channel

.sub5
db C3, Tie, Tie, Tie, Tie, Tie, Tie, C3
db $00 ; End

.sub6
db F2, Tie, Tie, Tie, Tie, Tie, Tie, F2
db $00 ; End

.sub7
db G2s, Tie, Tie, Tie, Tie, Tie, Tie, G2s
db $00 ; End


.Channel2
db $12, C4, G4, C5, D5s, D5, D5s, G5, A5s, D6, A5s, G5, D5s, D5, D5s, C5, G4, F3, A4, C5, D5s, G5, D5s, F5, A5, C6, A5, F5, D5s, C5, A4, C5, A4, G3s, G4, F4, G4, C5, G4s, C5, D5s, G5, F5, D5s, C5, G4, F4, G4, C5, G3, D4, F4, G4, A4s, G4, A4s, D5, F5, D5, A4s, G4, F4, D4, F4, D4, C4, Tie, Tie, G4, A4s, G4, A4s, G4, F4, C4, D4s, F4, F5, D5s, F5, G5, D4, D4s, G4, A4s, C5, D5s, G5, A5s, G4, D4, A4s, C5, D5s, G5, $24, A5s, Rest
%CallSubroutine(.sub4+!ARAMC, 48)
db $09
%CallSubroutine(.sub19+!ARAMC, 1)
db G3s, G3s, G3s, G3s, D4, D4, C4, C4, G3s, G3s, G3s, G3s, D4s, D4s, F4, F4, G4, G4, D4s, D4s, F4, F4, C4, C4, D4s, D4s, G3s, G3s, C4, C4, G3s, G3s, A3s, A3s, A3s, A3s, F4, F4, D4, D4, A3s, A3s, G3, G3, A3s, A3s, D4, D4, G4, G4, D4, D4, A3s, A3s, G3, G3, D3, D3, Tie, Tie, F3, F3, Tie, Tie
%CallSubroutine(.sub19+!ARAMC, 1)
db C4s, C4s, C4s, C4s, A3s, A3s, C4s, C4s, E4, E4, C4s, C4s, E4, E4, G4, G4, C5s, C5s, G4, G4, A4s, A4s, E4, E4, C4s, C4s, A3s, A3s, C4s, C4s, A3s, A3s
%CallSubroutine(.sub20+!ARAMC, 2)
db D5, D5, A4, A4, F4s, F4s, D4, D4, C4, C4, Tie, Tie, D4, Tie, Tie, Rest
%CallSubroutine(.sub4+!ARAMC, 29)
db $12, D6, A5s, G5, F5, D5, A4s, G4, A4s, D5, C5, A4, F4, C4, $09, A3, Tie, Tie, C4, Tie, A3, Tie, Tie, $12
%CallSubroutine(.sub12+!ARAMC, 4)
%CallSubroutine(.sub13+!ARAMC, 4)
%CallSubroutine(.sub14+!ARAMC, 4)
db A5, D5s, C5, G4s
%CallSubroutine(.sub15+!ARAMC, 7)
%CallSubroutine(.sub16+!ARAMC, 4)
%CallSubroutine(.sub17+!ARAMC, 4)
%CallSubroutine(.sub18+!ARAMC, 4)
%CallSubroutine(.sub21+!ARAMC, 2)
db $00 ; End of the channel

.sub19
db D4s, D4s, D4s, D4s, G4, G4, F4, F4, D4s, D4s, D4s, D4s, G4, G4, A4s, A4s, D5s, D5s, A4s, A4s, F4, F4, D4s, D4s, A3s, A3s, G3, G3, A3s, A3s, D4s, D4s, F4, F4, F4, F4, A4, A4, C5, C5, F4, F4, A4, A4, C5, C5, F5, F5, A5, A5, F5, F5, C5, C5, A4, A4, C4, C4, A3, A3, C4, C4, A3, A3
db $00 ; End

.sub20
db D4, D4, D4, D4, F4s, F4s, A4, A4
db $00 ; End

.sub12
db C6, G5, D5s, C5
db $00 ; End

.sub13
db A5s, F5, C5, A4s
db $00 ; End

.sub14
db A5, D5s, C5, A4
db $00 ; End

.sub15
db G5s, D5s, C5, G4s
db $00 ; End

.sub16
db G5, D5, A4s, G4
db $00 ; End

.sub17
db F5s, D5, A4, F4s
db $00 ; End

.sub18
db F5, C5, A4, F4
db $00 ; End

.sub21
db F4, G4, A4s, D5, D5s, G5, D5s, C5, D5s, F5, G5, A5, C6, D6s, G6, D6, C6, A5s, G5, D5s, C5, D5s, G5, F5, D5, A4s, G4, F4, D4, A3s, G3
db $00 ; End


.Channel3
%SetInstrument($0D) ; Ocarina
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub10+!ARAMC, 2)
%CallSubroutine(.sub11+!ARAMC, 1)
db G5, $24, F5
%CallSubroutine(.sub4+!ARAMC, 5)
db $12, D5s, F5, $24, G5
%CallSubroutine(.sub4+!ARAMC, 5)
db C5, G5, $12, F5, D5s, $48, D5, Tie, Tie
%CallSubroutine(.sub11+!ARAMC, 1)
db $12, A5s, $24, C6
%CallSubroutine(.sub4+!ARAMC, 6)
db A5s
%CallSubroutine(.sub4+!ARAMC, 5)
db A5, A5s, $12, A5, G5s, $24, A5
%CallSubroutine(.sub4+!ARAMC, 6)
db G5
%CallSubroutine(.sub4+!ARAMC, 15)
db $12, C6, G5, F5, G5
%CallSubroutine(.sub4+!ARAMC, 8)
db C6, Tie, Tie, Tie, A5s, G5, F5, G5
%CallSubroutine(.sub4+!ARAMC, 12)
db A5s, F5, D5s, F5
%CallSubroutine(.sub4+!ARAMC, 8)
db A5s, Tie, Tie, Tie, A5, D5s, D5, D5s
%CallSubroutine(.sub4+!ARAMC, 12)
db G5, D5, C5, D5
%CallSubroutine(.sub4+!ARAMC, 8)
db G5, Tie, Tie, Tie, C6, G5, F5, G5
%CallSubroutine(.sub4+!ARAMC, 8)
db C6, Tie, Tie, Tie, $48, D6, Tie, Tie, Tie, Rest
%CallSubroutine(.sub4+!ARAMC, 22)
db $24, Rest
db $00 ; End of the channel

.sub10
db C5, G5, Tie, Tie, Tie, Tie, C5, G5, C6, $12, A5, A5s, A5, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, F5, $24, G5, Tie, C5, Tie, Tie, Tie, Tie, F5, $12, D5, D5s, D5, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, A4s, $24, C5, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie, Tie
db $00 ; End

.sub11
db $12, G5, A5, $24, A5s, Tie, Tie, Tie, Tie, Tie, G5, A5s, $12, A5
db $00 ; End


.Channel4
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
db Rest
%CallSubroutine(.sub4+!ARAMC, 18)
db $12, Rest, Tie, C5, G5, $48, D5, Tie, Tie, Tie, C5, Tie, G5, Tie, $12, F5
%CallSubroutine(.sub4+!ARAMC, 13)
db D5s, D5, D5s
%CallSubroutine(.sub4+!ARAMC, 15)
db D5
%CallSubroutine(.sub4+!ARAMC, 14)
db D5, C5
%CallSubroutine(.sub4+!ARAMC, 11)
db F5, D5s, D5, C5, $48, D5
%CallSubroutine(.sub4+!ARAMC, 90)
db $24, Rest
db $00 ; End of the channel


.Channel5
%SetChannelVolume($AE)
%SetInstrument($13) ; Snare
%SetDurationN($48, $7F) ; 1/4
db Rest
%CallSubroutine(.sub4+!ARAMC, 23)
db $24, Rest
%CallSubroutine(.sub22+!ARAMC, 128)
%SetChannelVolume($AF)
db C4, Tie, Tie, C4, Tie, C4, $09, C4, Tie, Tie, C4, C4, C4, Tie, C4, $24, A3s, Tie, Tie, A3s, Tie, A3s, $09, A3s, Tie, Tie, A3s, A3s, A3s, Tie, A3s
%CallSubroutine(.sub8+!ARAMC, 1)
%CallSubroutine(.sub9+!ARAMC, 2)
db $24, G3, Tie, Tie, G3, Tie, G3, $09, G3, Tie, Tie, G3, G3, G3, Tie, G3
%CallSubroutine(.sub8+!ARAMC, 1)
db $24, A3, Tie, Tie, G3s, Tie, G3s, $09, G3s, Tie, Tie, G3, Tie, G3s, Tie, Tie, $24, Rest
%CallSubroutine(.sub4+!ARAMC, 29)
db $00 ; End of the channel

.sub8
db $24, A3, Tie, Tie, A3, Tie, A3, $09, A3, Tie, Tie, A3, A3, A3, Tie, A3
db $00 ; End

.sub9
db $24, G3s, Tie, Tie, G3s, Tie, G3s, $09, G3s, Tie, Tie, G3s, G3s, G3s, Tie, G3s
db $00 ; End

.sub22
db F5s
db $00 ; End

print pc
