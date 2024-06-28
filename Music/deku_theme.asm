;==========================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda: Ocarina of Time - Great Deku Tree Theme v1.00
; Original Song by Koji Kondo
; Midi by Loeder
; ASM Framework by Zarby89
; Ported by Letterbomb
; Size 0x0098 (152 Decimal)
;==========================================================

; TODO: Decide what song to override or use expanded music
; org $1A9FF8; Sections?
GreatDekuTreeTheme: 
!ARAMAddr = $D0FF
dw !ARAMAddr+$08
dw $00FF
dw !ARAMAddr
dw $0000


.Channels
!ARAMC = !ARAMAddr-GreatDekuTreeTheme
dw .Channel0+!ARAMC
dw .Channel1+!ARAMC
dw .Channel2+!ARAMC
dw $0000
dw $0000
dw $0000
dw $0000
dw $0000


.Channel0
%SetMasterVolume($C8)
%SetTempo(45)
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
db Rest
%CallSubroutine(.sub001+!ARAMC, 1)
db C4, Tie, Tie, Rest
%CallSubroutine(.sub001+!ARAMC, 1)
db A4s, G4, Tie, Rest, F4, E4, C4, B3, G3, Tie, G3, $24, A3s, G3s, $48, A3s, Tie, G3s, Tie, G3, Tie, Tie, Tie
db $00 ; End of the channel


.sub001
db C4, C4s, F4, E4
db $00 ; End



.Channel1
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
db Rest
%CallSubroutine(.sub101+!ARAMC, 1)
db G3, Tie, Tie, Rest
%CallSubroutine(.sub101+!ARAMC, 1)
db F4, E4, Tie, Rest, C4, C4s, F4, E4, C4, Tie, Tie, Rest, $24, C3, C3s, D3s, F3, F3s, G3s, A3s, C4s, $48, C4, Tie, Tie
db $00 ; End of the channel


.sub101
db G3, G3s, C4, B3
db $00 ; End



.Channel2
%SetInstrument($11) ; Trumpet
%SetDurationN($48, $7F) ; 1/4
db C3
%CallSubroutine(.subA01+!ARAMC, 7)
db C3s
%CallSubroutine(.subA01+!ARAMC, 7)
db C3
%CallSubroutine(.subA01+!ARAMC, 7)
db C3s, Tie, Tie, Tie, C3, Tie, Tie, Tie
db $00 ; End of the channel


.subA01
db Tie
db $00 ; End



print pc