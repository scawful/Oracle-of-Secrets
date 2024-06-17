;=====================================================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda: Majora's Mask - Stone Tower Temple Theme v1.00
; Original Song by Koji Kondo
; Midi by Aaron Ritchie
; ASM Framework by Zarby89
; Ported by Letterbomb
; Size 0x01DC (476 Decimal)
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
%SetMasterVolume($C8)
%SetChannelVolume($C4)
%SetTempo(62);
%SetInstrument($02) ; Tympani
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub001+!ARAMC, 24)
%CallSubroutine(.subA01+!ARAMC, 64)
db $00 ; End of the channel


.sub001
db B1, B1, $24, Tie, C2, $48, F3s
db $00 ; End



.Channel1
%SetInstrument($18) ; Guitar
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.subA01+!ARAMC, 8)
%CallSubroutine(.sub101+!ARAMC, 1)
%CallSubroutine(.sub102+!ARAMC, 1)
%CallSubroutine(.sub101+!ARAMC, 2)
%CallSubroutine(.sub102+!ARAMC, 1)
%CallSubroutine(.sub101+!ARAMC, 1)
%CallSubroutine(.sub102+!ARAMC, 1)
%CallSubroutine(.sub101+!ARAMC, 1)
%CallSubroutine(.sub102+!ARAMC, 1)
%CallSubroutine(.sub101+!ARAMC, 1)
%CallSubroutine(.sub102+!ARAMC, 1)
%CallSubroutine(.sub101+!ARAMC, 1)
%CallSubroutine(.sub102+!ARAMC, 1)
%CallSubroutine(.sub101+!ARAMC, 1)
db E2, Tie, Tie, Tie
%CallSubroutine(.subA01+!ARAMC, 4)
db $00 ; End of the channel


.sub101
db E2, Tie, Tie, Tie, F2, Tie, D2, Tie
db $00 ; End

.sub102
db E2, Tie, Tie, Tie, F2, Tie, E2, Tie
db $00 ; End



.Channel2
%SetChannelVolume($C4)
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.subA01+!ARAMC, 8)
%CallSubroutine(.sub201+!ARAMC, 1)
%CallSubroutine(.sub202+!ARAMC, 1)
%CallSubroutine(.sub201+!ARAMC, 2)
%CallSubroutine(.sub202+!ARAMC, 1)
%CallSubroutine(.sub201+!ARAMC, 1)
%CallSubroutine(.sub202+!ARAMC, 1)
%CallSubroutine(.sub201+!ARAMC, 1)
%CallSubroutine(.sub202+!ARAMC, 1)
%CallSubroutine(.sub201+!ARAMC, 1)
%CallSubroutine(.sub202+!ARAMC, 1)
%CallSubroutine(.sub201+!ARAMC, 1)
%CallSubroutine(.sub202+!ARAMC, 1)
%CallSubroutine(.sub201+!ARAMC, 1)
db E3, Tie, Tie, Tie
%CallSubroutine(.subA01+!ARAMC, 4)
db $00 ; End of the channel


.sub201
db E3, Tie, Tie, Tie, F3, Tie, D3, Tie
db $00 ; End

.sub202
db E3, Tie, Tie, Tie, F3, Tie, E3, Tie
db $00 ; End



.Channel3
%SetInstrument($09) ; Strings
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.subA01+!ARAMC, 48)
%CallSubroutine(.sub301+!ARAMC, 5)
%CallSubroutine(.subA01+!ARAMC, 32)
%CallSubroutine(.sub301+!ARAMC, 4)
%CallSubroutine(.subA01+!ARAMC, 32)
db $00 ; End of the channel


.sub301
db A2, E3, A2, E3, A2, E3, F3, Tie, A2, E3, A2, E3, A2, E3, D3, Tie
db $00 ; End



.Channel4
%SetChannelVolume($C4)
%SetInstrument($0D) ; Ocarina
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.subA01+!ARAMC, 32)
%CallSubroutine(.sub401+!ARAMC, 1)
%CallSubroutine(.sub402+!ARAMC, 1)
%CallSubroutine(.sub401+!ARAMC, 1)
%CallSubroutine(.sub403+!ARAMC, 1)
%CallSubroutine(.sub401+!ARAMC, 1)
%CallSubroutine(.sub402+!ARAMC, 1)
%CallSubroutine(.sub401+!ARAMC, 1)
%CallSubroutine(.sub403+!ARAMC, 1)
%CallSubroutine(.subA01+!ARAMC, 16)
%CallSubroutine(.sub404+!ARAMC, 1)
db B4, E5, Tie
%CallSubroutine(.sub405+!ARAMC, 1)
%CallSubroutine(.sub404+!ARAMC, 1)
db C5, $48, B4, B4, A4, Tie
%CallSubroutine(.sub404+!ARAMC, 1)
db Tie, E5, Tie
%CallSubroutine(.sub405+!ARAMC, 1)
db $24, E5, F5, E5, D5, $48, C5, B4, A4, Tie, Tie, Tie
%CallSubroutine(.sub406+!ARAMC, 2)
db $00 ; End of the channel


.sub401
db A4, C5, B4, $24, Tie, G4, A4, C5
db $00 ; End

.sub402
db $12, B4, B4, $24, A4, $48, G4, E4
db $00 ; End

.sub403
db $12, B4, B4, G4, Tie, $48, A4, Tie
db $00 ; End

.sub404
db E5, E5, $24, D5, Tie, Tie
db $00 ; End

.sub405
db D5, C5, $48, B4, Tie
db $00 ; End

.sub406
db E5, $24, A5, C6, $12, B5, B5, $48, Tie, G5, $24, E5, A5, C6, $12, B5, B5, $24, Tie, $48, Tie
db $00 ; End



.Channel5
%SetChannelVolume($C4)
%SetInstrument($0F) ; Harp
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.subA01+!ARAMC, 48)
%CallSubroutine(.sub501+!ARAMC, 1)
db A4, Tie, $48, G4, E4
%CallSubroutine(.sub501+!ARAMC, 1)
db G4, Tie, $48, A4, Tie
%CallSubroutine(.subA01+!ARAMC, 64)
db $00 ; End of the channel


.sub501
db A4, C5, $12, B4, B4, $24, Tie, Tie, G4, A4, C5, $12, B4, B4
db $00 ; End


.subA01
db Rest
db $00 ; End



warnpc $1AB4D5