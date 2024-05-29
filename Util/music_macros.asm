macro SetChannelVolume(v)
db $ED, <v>
endmacro

macro SetMasterVolume(v)
db $E5, <v>
endmacro

macro SetTempo(v)
db $E7, <v>
endmacro

; 00 Unknown
; 01 Rain
; 02 Tympani
; 03 Square wave
; 04 Saw wave
; 05 Sine wave
; 06 Double saw wave 1
; 07 Double save wave 2
; 08 Tweet
; 09 Strings
; 0A Same as 9
; 0B Trombone
; 0C Cymbal
; 0D Ocarina
; 0E Chime
; 0F harp
; 10 Splash
; 11 Trumpet
; 12 Horn
; 13 Snare
; 14 Same as 13
; 15 Choir
; 16 Flute
; 17 Oof
; 18 Guitar

macro SetInstrument(v)
db $E0, <v>
endmacro

macro CallSubroutine(addr, repeat)
db $EF
dw <addr>
db <repeat>
endmacro

macro SetPan(v)
db $E1, <v>
endmacro

macro PanFade(length, dest)
db $E2, <length>, <dest>
endmacro

macro VibratoOn(delay, rate, depth)
db $E3, <delay>, <rate>, <depth>
endmacro

macro VibratoOff()
db $E4
endmacro

macro MasterVolumeFade(length, dest)
db $E6, <length>, <dest>
endmacro

macro TempoFade(length, dest)
db $E8, <length>, <dest>
endmacro

macro GlobalTranspose(tone)
db $E9, <tone>
endmacro

macro ChannelTranspose(tone)
db $EA, <tone>
endmacro

macro TremoloOn(delay, rate, depth)
db $EB, <delay>, <rate>, <depth>
endmacro

macro TremoloOff()
db $EC
endmacro

macro ChannelVolumeFade(length, dest)
db $EE, <length>, <dest>
endmacro

macro VibratoFade(length)
db $F0, <length>
endmacro

macro PitchEnvelopeTo(delay, length, key)
db $F1, <delay>, <length>, <key>
endmacro

macro PitchEnvelopeFrom(delay, length, key)
db $F2, <delay>, <length>, <key>
endmacro

macro PitchEnvelopeOff()
db $F3
endmacro

macro Tuning(v)
db $F4, <v>
endmacro

macro EchoVBits(switch, left, right)
db $F5, <switch>, <left>, <right>
endmacro

macro EchoOff()
db $F6
endmacro

macro EchoParams(delay, feedback, filter)
db $F7, <delay>, <feedback>, <filter>
endmacro

macro EchoVolumeFade(length, left, right)
db $F8, <length>, <left>, <right>
endmacro

macro PitchSlide(delay, length, note)
db $F9, <delay>, <length>, <note>
endmacro

macro PercussionPatchBass(instrument)
db $FA, <instrument>
endmacro

;1/4 = $48
;1/4 double = $6C
;1/4 triplet = $30
;1/8 = $24
;1/8 double = $36
;1/8 triplet = $18
;1/16 = $12
;1/16 double = $1B
;1/32 = $09
; To make a whole note you tie 4 1/4 so something like
;%SetDuration(48)
;db !C4, !Tie, !Tie, !Tie ; will play a whole note (1/1)
;db !C4, !Tie ; will play a half note (1/2)

macro SetDuration(v) ; $48 = 1/4, $24 = 1/8, $12 = 1/16, $09 = 1/32
db <v>
endmacro

macro SetDurationN(v, n) ; n default is $7F
db <v>, <n>
endmacro

End = $00
Rest = $C9
Tie = $C8

C1 = $80
C1s = $81
D1 = $82
D1s = $83
E1 = $84
F1 = $85
F1s = $86
G1 = $87
G1s = $88
A1 = $89
A1s = $8A
B1 = $8B


C2 = $8C
C2s = $8D
D2 = $8E
D2s = $8F
E2 = $90
F2 = $91
F2s = $92
G2 = $93
G2s = $94
A2 = $95
A2s = $96
B2 = $97


C3 = $98
C3s = $99
D3 = $9A
D3s = $9B
E3 = $9C
F3 = $9D
F3s = $9E
G3 = $9F
G3s = $A0
A3 = $A1
A3s = $A2
B3 = $A3

C4 = $A4
C4s = $A5
D4 = $A6
D4s = $A7
E4 = $A8
F4 = $A9
F4s = $AA
G4 = $AB
G4s = $AC
A4 = $AD
A4s = $AE
B4 = $AF

C5 = $B0
C5s = $B1
D5 = $B2
D5s = $B3
E5 = $B4
F5 = $B5
F5s = $B6
G5 = $B7
G5s = $B8
A5 = $B9
A5s = $BA
B5 = $BB

C6 = $BC
C6s = $BD
D6 = $BE
D6s = $BF
E6 = $C0
F6 = $C1
F6s = $C2
G6 = $C3
G6s = $C4
A6 = $C5
A6s = $C6
B6 = $C7