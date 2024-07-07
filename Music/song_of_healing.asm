;=====================================================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda: Majora's Mask - Song of Healing Theme v1.00
; Original Song by Koji Kondo
; Midi by RSD and Chris Lakatos
; ASM Framework by Zarby89
; Ported by Letterbomb
; Size 0x0275 (629 Decimal)
;=====================================================================================

org $1BA308; Sections?
SongOfHealingTheme: 
!ARAMAddr = $F304
dw !ARAMAddr+$08
dw $00FF
dw !ARAMAddr
dw $0000



.Channels
!ARAMC = !ARAMAddr-SongOfHealingTheme
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
%SetTempo(56)
%SetInstrument($18) ; Guitar
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub0101+!ARAMC, 2)
%CallSubroutine(.sub0102+!ARAMC, 1)
%CallSubroutine(.sub0103+!ARAMC, 1)
%CallSubroutine(.sub0102+!ARAMC, 1)
%CallSubroutine(.sub0104+!ARAMC, 1)
%CallSubroutine(.sub0105+!ARAMC, 1)
%CallSubroutine(.sub0106+!ARAMC, 1)
%CallSubroutine(.sub0105+!ARAMC, 1)
%CallSubroutine(.sub0107+!ARAMC, 1)
db $00 ; End of the channel



.Channel1
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub0101+!ARAMC, 2)
%CallSubroutine(.sub0102+!ARAMC, 1)
%CallSubroutine(.sub0103+!ARAMC, 1)
%CallSubroutine(.sub0102+!ARAMC, 1)
%CallSubroutine(.sub0104+!ARAMC, 1)
%CallSubroutine(.sub0105+!ARAMC, 1)
%CallSubroutine(.sub0106+!ARAMC, 1)
%CallSubroutine(.sub0105+!ARAMC, 1)
%CallSubroutine(.sub0107+!ARAMC, 1)
db $00 ; End of the channel


.sub0101
db B4, A4, F4, B4, A4, F4, B4, A4, $24, E4, D4, $48, E4, Tie, Tie
db $00 ; End

.sub0102
db F4, C4, B3, F4, C4, B3, F4
db $00 ; End

.sub0103
db E4, $24, B3, A3, $48, B3, Tie, Tie
db $00 ; End

.sub0104
db E4, B4, G4, Tie, Tie, A4, A4, A4, D5, D5, D5
db $00 ; End

.sub0105
db G4, G4, G4, C5, G4, Tie
db $00 ; End

.sub0106
db F4, F4, F4, A4s, A4s, A4s, E4, D4, A4, E4, Tie, Tie, A4, A4, A4, D5, D5, D5
db $00 ; End

.sub0107
db F4, G4, A4, A4s, C5, D5, A4, B4, D5, E5, Tie, Tie, Tie
db $00 ; End



.Channel2
%SetInstrument($18) ; Guitar
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub201+!ARAMC, 3)
%CallSubroutine(.sub202+!ARAMC, 1)
%CallSubroutine(.sub201+!ARAMC, 3)
%CallSubroutine(.sub202+!ARAMC, 1)
%CallSubroutine(.sub203+!ARAMC, 2)
%CallSubroutine(.sub204+!ARAMC, 2)
%CallSubroutine(.sub203+!ARAMC, 2)
%CallSubroutine(.sub204+!ARAMC, 2)
%CallSubroutine(.sub205+!ARAMC, 1)
%CallSubroutine(.sub206+!ARAMC, 1)
%CallSubroutine(.sub207+!ARAMC, 1)
%CallSubroutine(.sub208+!ARAMC, 1)
%CallSubroutine(.sub205+!ARAMC, 1)
%CallSubroutine(.sub206+!ARAMC, 1)
db A2s, F3, A3s, F3, D4, F3, A2s, F3, A3s, F3, D4, F3, B2, F3, A3, F3, D4, A3, E3, Tie, B3, Tie, E4, Tie
db $00 ; End of the channel


.sub201
db F3, C4, Tie, C4, Tie, C4
db $00 ; End

.sub202
db E3, B3, Tie, B3, Tie, B3
db $00 ; End

.sub203
db D3, A3, Tie, A3, Tie, A3
db $00 ; End

.sub204
db C3, G3, Tie, G3, Tie, G3
db $00 ; End

.sub205
db A2s, F3, A3s, F3, D4, F3, A2s, F3, A3s, F3, D4, Tie
db $00 ; End

.sub206
db A2, E3, A3, E3, C4, E3, A2, E3, A3, E3, C4, Tie
db $00 ; End

.sub207
db G2, D3, G3, D3, A3s, D3, G2, D3, G3, D3, A3s, Tie
db $00 ; End

.sub208
db F2, C3, F3, C3, A3, C3, F2, C3, F3, C3, A3, Tie
db $00 ; End



.Channel3
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
db Rest
%CallSubroutine(.sub301+!ARAMC, 2)
%CallSubroutine(.sub302+!ARAMC, 2)
%CallSubroutine(.sub303+!ARAMC, 1)
%CallSubroutine(.sub304+!ARAMC, 1)
%CallSubroutine(.sub303+!ARAMC, 1)
db F3
%CallSubroutine(.subA01+!ARAMC, 5)
db F3, Tie, Tie, E3, Tie
db $00 ; End of the channel


.sub301
db F3, Tie, Tie, Tie, Tie, Tie, F3, Tie, Tie, E3, Tie, Tie
db $00 ; End

.sub302
db A3, Tie, Tie, Tie, Tie, Tie, G3, Tie, Tie, Tie, Tie, Tie
db $00 ; End

.sub303
db F3, Tie, Tie, Tie, Tie, Tie, E3, Tie, Tie, Tie, Tie, Tie
db $00 ; End

.sub304
db D3, Tie, Tie, Tie, Tie, Tie, C3, Tie, Tie, Tie, Tie, Tie
db $00 ; End



.Channel4
%SetInstrument($09) ; Strings
%SetDurationN($24, $7F) ; 1/8
db Rest, $48
%CallSubroutine(.sub401+!ARAMC, 2)
%CallSubroutine(.sub402+!ARAMC, 2)
%CallSubroutine(.sub403+!ARAMC, 1)
%CallSubroutine(.sub404+!ARAMC, 1)
%CallSubroutine(.sub403+!ARAMC, 1)
db A2
%CallSubroutine(.subA01+!ARAMC, 5)
db A2s, Tie, Tie, A2s, Tie, $24, Tie
db $00 ; End of the channel


.sub401
db C3, Tie, Tie, Tie, Tie, Tie, C3, Tie, Tie, B2, Tie, Tie
db $00 ; End

.sub402
db D3, Tie, Tie, Tie, Tie, Tie, C3, Tie, Tie, Tie, Tie, Tie
db $00 ; End

.sub403
db A2, Tie, Tie, Tie, Tie, Tie, G2s, Tie, Tie, Tie, Tie, Tie
db $00 ; End

.sub404
db F2s, Tie, Tie, Tie, Tie, Tie, E2, Tie, Tie, Tie, Tie, Tie
db $00 ; End



.Channel5
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub501+!ARAMC, 2)
%CallSubroutine(.sub502+!ARAMC, 2)
%CallSubroutine(.sub503+!ARAMC, 1)
%CallSubroutine(.sub504+!ARAMC, 1)
%CallSubroutine(.sub503+!ARAMC, 1)
db F2
%CallSubroutine(.subA01+!ARAMC, 5)
db F2, Tie, Tie, E2, Tie, Tie
db $00 ; End of the channel


.sub501
db F2, Tie, Tie, Tie, Tie, Tie, F2, Tie, Tie, E2, Tie, Tie
db $00 ; End

.sub502
db A2, Tie, Tie, Tie, Tie, Tie, G2, Tie, Tie, Tie, Tie, Tie
db $00 ; End

.sub503
db F2, Tie, Tie, Tie, Tie, Tie, E2, Tie, Tie, Tie, Tie, Tie
db $00 ; End

.sub504
db D2, Tie, Tie, Tie, Tie, Tie, C2, Tie, Tie, Tie, Tie, Tie
db $00 ; End


.subA01
db Tie
db $00 ; End
