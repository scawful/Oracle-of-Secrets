;=====================================================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda: Link's Awakening - Color Dungeon Theme v1.00
; Original Song by Koji Kondo and Yuichi Ozaki
; Midi by Princess Peach Toadstool
; ASM Framework by Zarby89
; Ported by Letterbomb
; Size 0x037F (895 Decimal)
;=====================================================================================

; org $1A9FF8; Sections?
; ColorDungeonTheme: 
; !ARAMAddr = $D0FF
org $1B9C0F; Sections?
ColorDungeonTheme: 
!ARAMAddr = $EC0B
dw !ARAMAddr+$08
dw $00FF
dw !ARAMAddr
dw $0000



.Channels
!ARAMC = !ARAMAddr-ColorDungeonTheme
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
%SetTempo(93);
%SetInstrument($09) ; Strings
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub001+!ARAMC, 4)    ;]
%CallSubroutine(.sub002+!ARAMC, 4)    ;]_____ D6, D6s Row
%CallSubroutine(.sub003+!ARAMC, 4)    ;]
%CallSubroutine(.sub004+!ARAMC, 4)    ;]
%CallSubroutine(.sub005+!ARAMC, 4)    ;]_____ C6, D6 Row
%CallSubroutine(.sub006+!ARAMC, 4)    ;]
%CallSubroutine(.sub007+!ARAMC, 1)    ;]----- Upscale
%CallSubroutine(.sub001+!ARAMC, 4)    ;]
%CallSubroutine(.sub002+!ARAMC, 4)    ;]_____ D6, D6s Row
%CallSubroutine(.sub003+!ARAMC, 4)    ;]
%CallSubroutine(.sub004+!ARAMC, 4)    ;]
%CallSubroutine(.sub005+!ARAMC, 4)    ;]_____ C6, D6 Row
%CallSubroutine(.sub006+!ARAMC, 4)    ;]
%CallSubroutine(.sub007+!ARAMC, 1)    ;]----- Upscale
%CallSubroutine(.sub008+!ARAMC, 4)    ;]
%CallSubroutine(.sub009+!ARAMC, 4)    ;]
%CallSubroutine(.sub010+!ARAMC, 4)    ;]_____ D6 Row
%CallSubroutine(.sub011+!ARAMC, 4)    ;]
%CallSubroutine(.sub012+!ARAMC, 4)    ;]
%CallSubroutine(.sub013+!ARAMC, 4)    ;]
%CallSubroutine(.sub007+!ARAMC, 1)    ;]----- Upscale
db $00 ; End of the channel


.sub001                               ;]
db G4, A4s, D5, D5s                   ;]
db $00 ; End                          ;]
                                      ;]
.sub002                               ;]
db F4s, A4, D5, D5s                   ;]
db $00 ; End                          ;]
                                      ;]----- D6, D6s Row
.sub003                               ;]
db F4, G4s, D5, D5s                   ;]
db $00 ; End                          ;]
                                      ;]
.sub004                               ;]
db E4, G4, D5, D5s                    ;]
db $00 ; End                          ;]

.sub005                               ;]
db D4s, G4, C5, D5                    ;]
db $00 ; End                          ;]
                                      ;]----- C6, D6 Row
.sub006                               ;]
db D4, G4, C5, D5                     ;]
db $00 ; End                          ;]

.sub007                                                                                       ;]
db C4, F4s, A4, C5, F4s, A4, C5, D5s, A4, C5, D5s, C5, D5s, F5s, D5s, F5s, A5, F5s, A5, C6    ;]----- Upscale
db $00 ; End                                                                                  ;]

.sub008                               ;]
db D5, A4s, G4, A4s                   ;]
db $00 ; End                          ;]
                                      ;]
.sub009                               ;]
db D5, A4, F4s, A4                    ;]
db $00 ; End                          ;]
                                      ;]
.sub010                               ;]
db D5, G4s, F4, G4s                   ;]
db $00 ; End                          ;]_____ D6 Row
                                      ;]
.sub011                               ;]
db D5, G4, E4, G4                     ;]
db $00 ; End                          ;]
                                      ;]
.sub012                               ;]
db D5, G4, D4s, G4                    ;]
db $00 ; End                          ;]
                                      ;]
.sub013                               ;]
db D5, G4, D4, G4                     ;]
db $00 ; End                          ;]



.Channel1
%SetInstrument($18) ; Guitar
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub101+!ARAMC, 1)      ;]----- Melody
%CallSubroutine(.sub102+!ARAMC, 1)      ;]----- Upscale
%CallSubroutine(.sub101+!ARAMC, 1)      ;]----- Melody
%CallSubroutine(.sub102+!ARAMC, 1)      ;]----- Upscale
db $48, D3, Tie, Tie, Tie, D3
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db C3s, Tie, A2, Tie, Tie, Tie, C3
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db D3, C3, B2
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db G2, A2, A2s
%CallSubroutine(.subA01+!ARAMC, 4)          ;]----- Tie Repeats
db A2s, C3, A2s, A2
%CallSubroutine(.subA01+!ARAMC, 4)          ;]----- Tie Repeats
db G2, F2s, G2, A2, Tie, Tie, Tie, Rest
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db $00 ; End of the channel


.sub101
db $48, G2, Tie, Tie, Tie, A2s, Tie, D3, Tie, C3s, Tie, F2s, Tie, Tie, Tie, Tie, Tie, F2, Tie, Tie, Tie, Tie, $24, Tie, G2s, $48, Tie, C3s, C3, Tie, E2, Tie, Tie, Tie, Tie, Tie, $24, D2s, D2, $48, D2s, Tie, Tie, G2, $24, Tie, D3s, Tie, Tie, D3, Tie, D2, C2s, $48, D2, Tie, Tie, G2, $24, Tie, D3, Tie, Tie, C3s, Tie
db $00 ; End

;|_________________________________________________________|
                           ;|
                           ;|
                         ;Melody

.sub102                                                                                          ;]
db D2, F2s, A2, F2s, A2, C3, A2, C3, D3s, C3, D3s, F3s, A3, F3s, D3s, C3s, D3s, C3s, A2, F2s     ;]----- Upscale
db $00 ; End                                                                                     ;]



.Channel2
%SetInstrument($18) ; Guitar
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub201+!ARAMC, 4)    ;]
%CallSubroutine(.sub202+!ARAMC, 4)    ;]_____ D6, D6s Row
%CallSubroutine(.sub203+!ARAMC, 4)    ;]
%CallSubroutine(.sub204+!ARAMC, 4)    ;]
%CallSubroutine(.sub205+!ARAMC, 4)    ;]_____ C6, D6 Row
%CallSubroutine(.sub206+!ARAMC, 4)    ;]
%CallSubroutine(.sub207+!ARAMC, 1)    ;]----- Upscale
%CallSubroutine(.sub201+!ARAMC, 4)    ;]
%CallSubroutine(.sub202+!ARAMC, 4)    ;]_____ D6, D6s Row
%CallSubroutine(.sub203+!ARAMC, 4)    ;]
%CallSubroutine(.sub204+!ARAMC, 4)    ;]
%CallSubroutine(.sub205+!ARAMC, 4)    ;]_____ C6, D6 Row
%CallSubroutine(.sub206+!ARAMC, 4)    ;]
%CallSubroutine(.sub207+!ARAMC, 1)    ;]----- Upscale
%SetInstrument($0F) ; Harp
db $48, D6, Tie, Tie, Tie, D6
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db C6s, Tie, A5, Tie, Tie, Tie, C6
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db D6, C6, B5
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db G5, A5, A5s
%CallSubroutine(.subA01+!ARAMC, 4)          ;]----- Tie Repeats
db A5s, C6, A5s, A5
%CallSubroutine(.subA01+!ARAMC, 4)          ;]----- Tie Repeats
db G5, F5s, G5, A5, Tie, Tie, Tie, Rest
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db $00 ; End of the channel


.sub201                               ;]
db G2, A2s, D3, D3s                   ;]
db $00 ; End                          ;]
                                      ;]
.sub202                               ;]
db F2s, A2, D3, D3s                   ;]
db $00 ; End                          ;]
                                      ;]----- D6, D6s Row
.sub203                               ;]
db F2, G2s, D3, D3s                   ;]
db $00 ; End                          ;]
                                      ;]
.sub204                               ;]
db E2, G2, D3, D3s                    ;]
db $00 ; End                          ;]

.sub205                               ;]
db D2s, G2, C3, D3                    ;]
db $00 ; End                          ;]
                                      ;]----- C6, D6 Row
.sub206                               ;]
db D2, G2, C3, D3                     ;]
db $00 ; End                          ;]

.sub207                                                                                       ;]
db C2, F2s, A2, C3, F2s, A2, C3, D3s, A2, C3, D3s, C3, D3s, F3s, D3s, F3s, A3, F3s, A3, C4    ;]----- Upscale
db $00 ; End                                                                                  ;]



.Channel3
%SetChannelVolume($9D)
%SetInstrument($13) ; Snare
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub301+!ARAMC, 4)
%CallSubroutine(.sub302+!ARAMC, 4)
%CallSubroutine(.sub303+!ARAMC, 8)
%CallSubroutine(.sub304+!ARAMC, 6)
db G2, Tie, G2, Tie, G2
%CallSubroutine(.subA01+!ARAMC, 9)
%CallSubroutine(.sub301+!ARAMC, 4)
%CallSubroutine(.sub302+!ARAMC, 4)
%CallSubroutine(.sub303+!ARAMC, 8)
%CallSubroutine(.sub304+!ARAMC, 6)
db G2, Tie, G2, Tie, G2
%CallSubroutine(.subA01+!ARAMC, 9)
%SetInstrument($15) ; Choir
db $48, D5, Tie, Tie, Tie, D5
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db C5s, Tie, A4, Tie, Tie, Tie, C5
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db D5, C5, B4
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db G4, A4, A4s
%CallSubroutine(.subA01+!ARAMC, 4)          ;]----- Tie Repeats
db A4s, C5, A4s, A4
%CallSubroutine(.subA01+!ARAMC, 4)          ;]----- Tie Repeats
db G4, F4s, G4, A4, Tie, Tie, Tie, Rest
%CallSubroutine(.subA01+!ARAMC, 5)          ;]----- Tie Repeats
db $00 ; End of the channel


.sub301
db G2, Tie
db $00 ; End

.sub302
db F2, Tie
db $00 ; End

.sub303
db E2, Tie
db $00 ; End

.sub304
db D2s, Tie
db $00 ; End



.Channel4
%SetInstrument($09) ; Strings
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub401+!ARAMC, 1)      ;]----- Melody
%CallSubroutine(.sub402+!ARAMC, 1)      ;]----- Upscale
%CallSubroutine(.sub401+!ARAMC, 1)      ;]----- Melody
%CallSubroutine(.sub402+!ARAMC, 1)      ;]----- Upscale
%SetInstrument($18) ; Guitar
%CallSubroutine(.sub403+!ARAMC, 4)    ;]
%CallSubroutine(.sub404+!ARAMC, 4)    ;]
%CallSubroutine(.sub405+!ARAMC, 4)    ;]_____ D6 Row
%CallSubroutine(.sub406+!ARAMC, 4)    ;]
%CallSubroutine(.sub407+!ARAMC, 4)    ;]
%CallSubroutine(.sub408+!ARAMC, 4)    ;]
%CallSubroutine(.sub207+!ARAMC, 1)    ;]----- Upscale
db $00 ; End of the channel


.sub401
db $48, G3, Tie, Tie, Tie, A3s, Tie, D4, Tie, C4s, Tie, F3s, Tie, Tie, Tie, Tie, Tie, F3, Tie, Tie, Tie, Tie, $24, Tie, G3s, $48, Tie, C4s, C4, Tie, E3, Tie, Tie, Tie, Tie, Tie, $24, D3s, D3, $48, D3s, Tie, Tie, G3, $24, Tie, D4s, Tie, Tie, D4, Tie, D3, C3s, $48, D3, Tie, Tie, G3, $24, Tie, D4, Tie, Tie, C4s, Tie
db $00 ; End

;|_________________________________________________________|
                           ;|
                           ;|
                         ;Melody

.sub402                                                                                          ;]
db D3, F3s, A3, F3s, A3, C4, A3, C4, D4s, C4, D4s, F4s, A4, F4s, D4s, C4s, D4s, C4s, A3, F3s     ;]----- Upscale
db $00 ; End                                                                                     ;]

.sub403                               ;]
db D3, A2s, G2, A2s                   ;]
db $00 ; End                          ;]
                                      ;]
.sub404                               ;]
db D3, A2, F2s, A2                    ;]
db $00 ; End                          ;]
                                      ;]
.sub405                               ;]
db D3, G2s, F2, G2s                   ;]
db $00 ; End                          ;]_____ D6 Row
                                      ;]
.sub406                               ;]
db D3, G2, E2, G2                     ;]
db $00 ; End                          ;]
                                      ;]
.sub407                               ;]
db D3, G2, D2s, G2                    ;]
db $00 ; End                          ;]
                                      ;]
.sub408                               ;]
db D3, G2, D2, G2                     ;]
db $00 ; End                          ;]



.Channel5
%SetInstrument($09) ; Strings
%SetDurationN($12, $7F) ; 1/16
db Rest, $24
%CallSubroutine(.sub001+!ARAMC, 4)    ;]
%CallSubroutine(.sub002+!ARAMC, 4)    ;]_____ D6, D6s Row
%CallSubroutine(.sub003+!ARAMC, 4)    ;]
%CallSubroutine(.sub004+!ARAMC, 4)    ;]
%CallSubroutine(.sub005+!ARAMC, 4)    ;]_____ C6, D6 Row
%CallSubroutine(.sub006+!ARAMC, 4)    ;]
%CallSubroutine(.sub007+!ARAMC, 1)    ;]----- Upscale
%CallSubroutine(.sub001+!ARAMC, 4)    ;]
%CallSubroutine(.sub002+!ARAMC, 4)    ;]_____ D6, D6s Row
%CallSubroutine(.sub003+!ARAMC, 4)    ;]
%CallSubroutine(.sub004+!ARAMC, 4)    ;]
%CallSubroutine(.sub005+!ARAMC, 4)    ;]_____ C6, D6 Row
%CallSubroutine(.sub006+!ARAMC, 4)    ;]
%CallSubroutine(.sub007+!ARAMC, 1)    ;]----- Upscale
db Rest, $48
%CallSubroutine(.subA01+!ARAMC, 58)    ;]----- Tie Repeats
db $00 ; End of the channel


.subA01               ;]
db Tie                ;]----- Tie Repeats
db $00 ; End          ;]
