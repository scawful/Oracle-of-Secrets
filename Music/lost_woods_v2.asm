;=====================================================================================
; The Legend of Zelda: A Link to the Past (Custom Music Track)
; The Legend of Zelda: Ocarina of Time - Lost Woods Theme
; Original Song by Koji Kondo
; Midi by John Kuzma
; ASM Framework by Zarby89
; Notes: v1.01 from the 2023 Oracle build (commit 31a8d5a2). Its header said
;   "Ported by Letterbomb"; scawful credits Potentialing (Zeldix days).
; Mix and echo: Letterbomb v1.10 (master $C8, echo $02/$50/$02, channel balance),
;   all channels +5 dB so the song matches the overworld theme loudness.
; Note bytes are unchanged from v1.01. Fits the old v2 slot (582 bytes).
;=====================================================================================

org $20BEE9 : assert pc() == owrom($1AADDE)

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
dw $0000
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
%SetMasterVolume($C8) ; v1.10 master (was $9F)
%SetChannelVolume($98) ; +5 dB makeup, timpani
%SetTempo(85);
%EchoVBits($FF, $00, $00) ; v1.10 echo: all channels
%EchoParams($02, $50, $02) ; v1.10 delay, feedback, filter
%EchoVolumeFade($32, $32, $32) ; v1.10 echo fade-in
%SetInstrument($02) ; Tympani
%SetDurationN($12, $7F) ; 1/16
db F3s, Tie, F3s, F3s, F3s, Tie, F3s, F3s, F3s, Tie, $24, F3s, Tie, C4
db $00 ; End of the channel


.Channel0
%CallSubroutine(.sub1+!ARAMC, 14)
%CallSubroutine(.sub2+!ARAMC, 4)
%CallSubroutine(.sub1+!ARAMC, 1)
db $12, F3s, Tie, F3s, F3s, Tie, Tie, F3s, Tie, $48, F3s, F3s
db $00 ; End of the channel

.sub1
db $12, F3s, Tie, F3s, F3s, $24, F3s, F3s, F3s, $12, F3s, F3s, $24, F3s, F3s
db $00 ; End

.sub2
db $12, F3s, Tie, F3s, F3s, $48, D4
db $00 ; End

.sub11
db Tie
db $00 ; End


.Channel1
%SetChannelVolume($A0) ; v1.10 balance +5 dB makeup (v1.01 was $9A)
%SetInstrument($0D) ; Ocarina
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub3+!ARAMC, 1)
db B5, G5, $48, E5, Tie, $24, Tie, D5, E5, G5, $48, E5, Tie, Tie
%CallSubroutine(.sub3+!ARAMC, 1)
db E6, B5, $48, G5, Tie, $24, Tie, B5, G5, D5, $48, E5, Tie, Tie
%CallSubroutine(.sub9+!ARAMC, 8)
db $24, F5, G5, A5, Tie, B5, C6, D6, Tie, E6, F6, $48, G6, Tie, Tie
%CallSubroutine(.sub9+!ARAMC, 8)
db $24, F5, E5, A5, G5, B5, A5, C6, B5, D6, C6, E6, D6, F6, E6, $12, B5, C6, Tie, A5, $48, B5
%CallSubroutine(.sub11+!ARAMC, 7)
db $00 ; End of the channel

.sub3
db $24, F5, A5, B5, Tie, F5, A5, B5, Tie, F5, A5, B5, E6, D6, Tie, B5, C6
db $00 ; End


.Channel2
%SetChannelVolume($A0) ; v1.10 balance +5 dB makeup (v1.01 default $FF)
%SetInstrument($0F) ; Harp
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub4+!ARAMC, 4)
%CallSubroutine(.sub5+!ARAMC, 4)
%CallSubroutine(.sub4+!ARAMC, 4)
%CallSubroutine(.sub5+!ARAMC, 4)
%CallSubroutine(.sub6+!ARAMC, 3)
%CallSubroutine(.sub7+!ARAMC, 2)
db $24, E3, A3, Tie, A3, E3, B3, Tie, A3, E3, G3s, G3s, G3s, G3s, Tie, B4, Tie
db $00 ; End of the channel

.sub4
db $48, F3, Tie
db $00 ; End

.sub5
db $48, C3, Tie
db $00 ; End

.sub6
db $24, D3, F3, D3, F3, G2, D3, G2, G3, C3, G3, C3, G3, A2, E3, A2, E3
db $00 ; End

.sub7
db $24, D3, A3, F3, Tie
db $00 ; End


.Channel3
%SetChannelVolume($75) ; v1.10 balance +5 dB makeup (v1.01 default $FF)
%SetInstrument($18) ; Guitar
%SetDurationN($24, $7F) ; 1/8
%CallSubroutine(.sub8+!ARAMC, 2)
db $48
%CallSubroutine(.sub9+!ARAMC, 40)
db $00 ; End of the channel

.sub8
db F3, C4, C4, C4, F3, A3, A3, A3, F3, A3, A3, A3, F3, A3, A3, A3, E3, G3, G3, G3, E3, G3, G3, C3, E3, C4, G3, G3, E3, G3, G3, C3
db $00 ; End

.sub9
db Rest
db $00 ; End


.Channel4
%SetChannelVolume($A2) ; counter-melody, v1.01 ratio to the lead (was $9D)
%SetInstrument($18) ; Guitar
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub9+!ARAMC, 32)
%CallSubroutine(.sub10+!ARAMC, 1)
db C5, B4, $48, E4, Tie, Tie
%CallSubroutine(.sub10+!ARAMC, 1)
db $24, C5, D5, $48, E5, Tie, Tie
%CallSubroutine(.sub10+!ARAMC, 1)
db $24, C5, B4, $48, E4, Tie, Tie, $24, D4, C4, F4, E4, G4, F4, A4, G4, B4, A4, C5, B4, D5, C5, $12, E5, F5, Tie, D5, $48, E5
%CallSubroutine(.sub11+!ARAMC, 7)
db $00 ; End of the channel

.sub10
db $24, D4, E4, F4, Tie, G4, A4, B4, Tie
db $00 ; End


.Channel5
%SetChannelVolume($A0) ; v1.10 balance +5 dB makeup (v1.01 default $FF)
%SetInstrument($0F) ; Harp
%SetDurationN($48, $7F) ; 1/4
%CallSubroutine(.sub9+!ARAMC, 32)
%CallSubroutine(.sub4+!ARAMC, 4)
%CallSubroutine(.sub5+!ARAMC, 4)
%CallSubroutine(.sub4+!ARAMC, 4)
%CallSubroutine(.sub5+!ARAMC, 4)
%CallSubroutine(.sub4+!ARAMC, 4)
db $00 ; End of the channel
assert pc() <= owrom($1AADDE)+$246, "Lost Woods overruns its v2 slot"
