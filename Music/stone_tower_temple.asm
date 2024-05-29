;=====================================================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda: Majora's Mask - Stone Tower Temple Theme v1.01
; Original Song by Koji Kondo
; Midi by (Unknown)
; ASM Framework by Zarby89
; Ported by Letterbomb
;=====================================================================================

org $1AA763; Sections?
StoneTowerTempleTheme: 
!ARAMAddr = $D86A
dw !ARAMAddr+$08
dw $00FF
dw !ARAMAddr
dw $0000

.Channels
!ARAMC = !ARAMAddr-StoneTowerTempleTheme
dw .Channel0+!ARAMC
dw .Channel1+!ARAMC
dw .Channel2+!ARAMC
dw .Channel3+!ARAMC
dw .Channel4+!ARAMC
dw .Channel5+!ARAMC
dw $0000
dw $0000


.Channel0
%SetMasterVolume($DA)
%SetChannelVolume($BF)
%SetTempo(62);
%SetInstrument($02) ; Tympani
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub1+!ARAMC, 24)
%CallSubroutine(.sub2+!ARAMC, 64)
db $00 ; End of the channel

.sub1
db $48, B1, B1, $24, Tie, C2, F3s, Tie
db $00 ; End

.sub2
db Rest
db $00 ; End


.Channel1
%SetChannelVolume($FF)
%SetInstrument($18) ; Guitar
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub2+!ARAMC, 8)
%CallSubroutine(.sub3+!ARAMC, 1)
%CallSubroutine(.sub4+!ARAMC, 1)
%CallSubroutine(.sub3+!ARAMC, 2)
%CallSubroutine(.sub4+!ARAMC, 1)
%CallSubroutine(.sub3+!ARAMC, 1)
%CallSubroutine(.sub4+!ARAMC, 1)
%CallSubroutine(.sub3+!ARAMC, 1)
%CallSubroutine(.sub4+!ARAMC, 1)
%CallSubroutine(.sub3+!ARAMC, 1)
%CallSubroutine(.sub4+!ARAMC, 1)
%CallSubroutine(.sub3+!ARAMC, 1)
%CallSubroutine(.sub4+!ARAMC, 1)
%CallSubroutine(.sub3+!ARAMC, 1)
db E2, Tie, Tie, Tie
%CallSubroutine(.sub2+!ARAMC, 4)
db $00 ; End of the channel

.sub3
db E2, Tie, Tie, Tie, F2, Tie, D2, Tie
db $00 ; End

.sub4
db E2, Tie, Tie, Tie, F2, Tie, E2, Tie
db $00 ; End


.Channel2
%SetInstrument($09) ; Strings
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub2+!ARAMC, 48)
%CallSubroutine(.sub5+!ARAMC, 5)
%CallSubroutine(.sub2+!ARAMC, 32)
%CallSubroutine(.sub5+!ARAMC, 4)
%CallSubroutine(.sub2+!ARAMC, 32)
db $00 ; End of the channel

.sub5
db A2, E3, A2, E3, A2, E3, F3, Tie, A2, E3, A2, E3, A2, E3, D3, Tie
db $00 ; End


.Channel3
%SetChannelVolume($BA)
%SetInstrument($0D) ; Ocarina
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub2+!ARAMC, 64)
%CallSubroutine(.sub7+!ARAMC, 1)
%CallSubroutine(.sub8+!ARAMC, 1)
%CallSubroutine(.sub7+!ARAMC, 1)
%CallSubroutine(.sub9+!ARAMC, 1)
%CallSubroutine(.sub7+!ARAMC, 1)
%CallSubroutine(.sub8+!ARAMC, 1)
%CallSubroutine(.sub7+!ARAMC, 1)
%CallSubroutine(.sub9+!ARAMC, 1)
%CallSubroutine(.sub2+!ARAMC, 16)
%CallSubroutine(.sub10+!ARAMC, 1)
db B4, E5, Tie
%CallSubroutine(.sub11+!ARAMC, 1)
%CallSubroutine(.sub10+!ARAMC, 1)
db C5, $48, B4, B4, A4, Tie
%CallSubroutine(.sub10+!ARAMC, 1)
db Tie, E5, Tie
%CallSubroutine(.sub11+!ARAMC, 1)
db $24, E5, F5, E5, D5, $48, C5, B4, A4, Tie, Tie, Tie
%CallSubroutine(.sub12+!ARAMC, 2)
db $00 ; End of the channel

.sub7
db $48, A4, C5, B4, $24, Tie, G4, A4, C5
db $00 ; End

.sub8
db $09, B4, C5, $12, B4, A4, Tie, $48, G4, E4
db $00 ; End

.sub9
db $09, B4, C5, B4, Tie, $24, G4, $48, A4, Tie
db $00 ; End

.sub10
db $48, E5, E5, $24, D5, Tie, Tie
db $00 ; End

.sub11
db $24, D5, C5, $48, B4, Tie
db $00 ; End

.sub12
db $48, E5, $24, A5, C6, $12, B5, B5, $48, Tie, G5, $24, E5, A5, C6, $12, B5, $48, B5, $24, Tie, $12, Tie
db $00 ; End


.Channel4
%SetChannelVolume($CA)
%SetInstrument($0F) ; Harp
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub2+!ARAMC, 48)
%CallSubroutine(.sub13+!ARAMC, 1)
db $24, A4, $48, G4, E4
%CallSubroutine(.sub13+!ARAMC, 1)
db $24, G4, $48, A4, Tie
%CallSubroutine(.sub2+!ARAMC, 64)
db $00 ; End of the channel

.sub13
db $48, A4, C5, $12, B4, B4, $48, Tie, $24, G4, A4, C5, $12, B4, B4
db $00 ; End


.Channel5
%SetChannelVolume($BA)
%SetInstrument($15) ; Choir
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub2+!ARAMC, 8)
%CallSubroutine(.sub6+!ARAMC, 15)
db $00 ; End of the channel

.sub6
db A2, Tie, Tie, Tie, Tie, Tie, Tie, Tie
db $00 ; End

print pc