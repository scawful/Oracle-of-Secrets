;=====================================================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda - Dungeon Theme v1.01
; Original Song by Koji Kondo
; Midi by Zaggarum
; ASM Framework by Zarby89
; Ported by Letterbomb
;=====================================================================================

lorom

org $1B9C0F; Sections?
DungeonTheme: 
!ARAMAddr = $EC0B
dw !ARAMAddr+$08
dw $00FF
dw !ARAMAddr
dw $0000

.Channels
!ARAMC = !ARAMAddr-DungeonTheme
dw .Channel0+!ARAMC
dw .Channel1+!ARAMC
dw .Channel2+!ARAMC
dw .Channel3+!ARAMC
dw .Channel4+!ARAMC
dw .Channel5+!ARAMC
dw $0000
dw $0000


.Channel0
%SetMasterVolume($9F)
%SetTempo(97);
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub1+!ARAMC, 4)
%CallSubroutine(.sub2+!ARAMC, 4)
%CallSubroutine(.sub3+!ARAMC, 4)
%CallSubroutine(.sub4+!ARAMC, 4)
%CallSubroutine(.sub5+!ARAMC, 4)
%CallSubroutine(.sub6+!ARAMC, 4)
%CallSubroutine(.sub7+!ARAMC, 1)
db Rest
db $00 ; End of the channel

.sub1
db G4, D5
db $00 ; End

.sub2
db F4s, D5
db $00 ; End

.sub3
db F4, D5
db $00 ; End

.sub4
db E4, D5
db $00 ; End

.sub5
db D4s, C5
db $00 ; End

.sub6
db D4, C5
db $00 ; End

.sub7
db C4, A4, F4s, C5, A4, D5s, D5s, D5s, A5, A5
db $00 ; End


.Channel1
%SetInstrument($09) ; Strings
%SetDurationN($24, $7F) ; 1/8
db Rest, $48
%CallSubroutine(.sub8+!ARAMC, 4)
%CallSubroutine(.sub9+!ARAMC, 4)
%CallSubroutine(.sub10+!ARAMC, 4)
%CallSubroutine(.sub11+!ARAMC, 4)
%CallSubroutine(.sub12+!ARAMC, 8)
db F4s, C5, A4, D5s, C5, C5, F5s, F5s, F5s, C6
db $00 ; End of the channel

.sub8
db A4s, D5s
db $00 ; End

.sub9
db A4, D5s
db $00 ; End

.sub10
db G4s, D5s
db $00 ; End

.sub11
db G4, D5s
db $00 ; End

.sub12
db G4, D5
db $00 ; End


.Channel2
%SetChannelVolume($CF)
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
db G4, Tie, Tie, Tie, A4s, Tie, D5, Tie, C5s, Tie, F4s
%CallSubroutine(.sub13+!ARAMC, 5)
db $24, F4
%CallSubroutine(.sub13+!ARAMC, 10)
db G4, Tie, Tie, $48, C5s, C5, Tie, $24, E4
%CallSubroutine(.sub13+!ARAMC, 11)
db D4s, D4, D4s
%CallSubroutine(.sub13+!ARAMC, 5)
db G4, Tie, Tie, D5s, Tie, Tie, D5, Tie, D4, C4s, D4
%CallSubroutine(.sub13+!ARAMC, 5)
db G4, Tie, Tie, D5, Tie, Tie, C5s, Tie, D4, F4s, A4, F4s, A4, C5, A4, C5, D5s, C5, D5s, F5s, A5, F5s, D5s, C5, D5s, C5, A4, F4s
db $00 ; End of the channel

.sub13
db Tie
db $00 ; End


.Channel3
%SetInstrument($18) ; Guitar
%SetDurationN($24, $7F) ; 1/8
db Rest, $48, G4
%CallSubroutine(.sub13+!ARAMC, 7)
db F4s
%CallSubroutine(.sub13+!ARAMC, 7)
db F4
%CallSubroutine(.sub13+!ARAMC, 7)
db E4
%CallSubroutine(.sub13+!ARAMC, 7)
db D4s
%CallSubroutine(.sub13+!ARAMC, 7)
db D4
%CallSubroutine(.sub13+!ARAMC, 7)
db Rest
%CallSubroutine(.sub13+!ARAMC, 9)
db $00 ; End of the channel


.Channel4
%SetChannelVolume($CB)
%SetInstrument($13) ; Snare
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub14+!ARAMC, 4)
%CallSubroutine(.sub15+!ARAMC, 4)
%CallSubroutine(.sub16+!ARAMC, 8)
%CallSubroutine(.sub17+!ARAMC, 6)
db G2, Tie, G2, Tie, G2
%CallSubroutine(.sub13+!ARAMC, 9)
db $00 ; End of the channel

.sub14
db G2, Tie
db $00 ; End

.sub15
db F2, Tie
db $00 ; End

.sub16
db E2, Tie
db $00 ; End

.sub17
db D2s, Tie
db $00 ; End


.Channel5
%SetChannelVolume($CF)
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
db G3, Tie, Tie, Tie, A3s, Tie, D4, Tie, C4s, Tie, F3s
%CallSubroutine(.sub13+!ARAMC, 5)
db $24, F3
%CallSubroutine(.sub13+!ARAMC, 10)
db G3, Tie, Tie, $48, C4s, C4, Tie, $24, E3
%CallSubroutine(.sub13+!ARAMC, 11)
db D3s, D3, D3s
%CallSubroutine(.sub13+!ARAMC, 5)
db G3, Tie, Tie, D4s, Tie, Tie, D4, Tie, D3, C3s, D3
%CallSubroutine(.sub13+!ARAMC, 5)
db G3, Tie, Tie, D4, Tie, Tie, C4s, Tie, D3, F3s, A3, F3s, A3, C4, A3, C4, D4s, C4, D4s, F4s, A4, F4s, D4s, C4, D4s, C4, A3, F3s
db $00 ; End