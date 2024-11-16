; ==============================================
; 1/4         = $48
; 1/4 double  = $6C
; 1/4 triplet = $30
; 1/8         = $24
; 1/8 double  = $36
; 1/8 triplet = $18
; 1/16        = $12
; 1/16 double = $1B
; 1/32        = $09

; db C4, !Tie, !Tie, !Tie : whole note (1/1)
; db C4, !Tie             : half note (1/2)

!4th   = $48
!4thD  = $6C
!4thT  = $30
!8th   = $24
!8thD  = $36
!8thT  = $18
!16th  = $12
!16thD = $1B
!32nd  = $09

; Note Parameters ($01-$7F)
; [xy]
; When $xy &lt; $80
;   $x = Duration Rate (0-7)
;   $y = Velocity Rate (0-15)
; VByte itself means the length of the following note
; (48 = quarter note, usually).

macro SetDuration(v)
db <v>
endmacro

; n default is $7F
macro SetDurationN(v, n)
db <v>, <n>
endmacro

; ==============================================
; N-SPC Instruments

; 00 Noise
; 01 Rain
; 02 Tympani
; 03 Square wave
; 04 Saw wave
; 05 Sine wave (clink)
; 06 Wobbly lead
; 07 Compound saw wave
; 08 Tweet
; 09 Strings A
; 0A Strings B
; 0B Trombone
; 0C Cymbal
; 0D Ocarina
; 0E Chime
; 0F Harp
; 10 Splash
; 11 Trumpet
; 12 Horn
; 13 Snare A
; 14 Snare B
; 15 Choir
; 16 Flute
; 17 Oof
; 18 Piano

macro SetInstrument(v)
db $E0, <v>
endmacro

macro Tympani()
 %SetInstrument($02)
endmacro

macro Trombone()
 %SetInstrument($0B)
endmacro

macro Ocarina()
 %SetInstrument($0D)
endmacro

macro Harp()
 %SetInstrument($0F)
endmacro

macro Splash()
 %SetInstrument($10)
endmacro

macro Trumpet()
 %SetInstrument($11)
endmacro

macro Horn()
 %SetInstrument($12)
endmacro

macro Snare()
 %SetInstrument($13)
endmacro

macro Choir()
 %SetInstrument($15)
endmacro

macro Flute()
 %SetInstrument($16)
endmacro

macro Piano()
 %SetInstrument($18)
endmacro

macro Cymbal()
  %SetInstrument($0C)
endmacro

macro Strings()
  %SetInstrument($09)
endmacro

macro Sawtooth()
  %SetInstrument($04)
endmacro

macro Sine()
  %SetInstrument($05)
endmacro

; ==============================================

macro SetChannelVolume(v)
db $ED, <v>
endmacro

macro SetMasterVolume(v)
db $E5, <v>
endmacro

macro SetTempo(v)
db $E7, <v>
endmacro

; - Play block $yyxx for $zz+1 times.
; - Subroutine call cannot be nested.
; - See also $00
; The block $yyxx is played zz + 1 times. Subroutines cannot be nested.
macro CallSubroutine(addr, repeat)
db $EF
dw <addr>
db <repeat>
endmacro

; Set the left and right position of the sound.
; The range of values is as narrow as 0 to 20
; (the actual setting ratio is defined in the internal table).
; Depending on the version, it depends on whether the large value is left or right.
; The upper 2 bits are used for phase inversion.
; Lower-5bit for pan value (0-20), higher-2bit is used for phase reverse switch.
macro SetPan(v)
db $E1, <v>
endmacro

; The position of the sound fades from the current value to yy over xx time.
macro PanFade(length, dest)
db $E2, <length>, <dest>
endmacro

; Enables vibrato (pitch fluctuation / pitch swing).
; Set zz-sized vibrato at yy speed after xx time.
macro VibratoOn(delay, rate, depth)
db $E3, <delay>, <rate>, <depth>
endmacro

macro VibratoOff()
db $E4
endmacro

; The volume of the entire song fades from the current value to yy over xx time.
macro MasterVolumeFade(length, dest)
db $E6, <length>, <dest>
endmacro

; Specifies the playing speed of the song.
; Value of about 24/60 is written.
macro TempoFade(length, dest)
db $E8, <length>, <dest>
endmacro

; Raises the playing pitch of all channels by xx
; (negative numbers can be specified).
macro GlobalTranspose(tone)
db $E9, <tone>
endmacro

; Raises the playing pitch of a single channel by xx
; (negative numbers can also be specified).
macro ChannelTranspose(tone)
db $EA, <tone>
endmacro

; Enable tremolo (volume fluctuation).
; Set the tremolo of the size of zz to be applied at the speed of yy after xx time.
macro TremoloOn(delay, rate, depth)
db $EB, <delay>, <rate>, <depth>
endmacro

macro TremoloOff()
db $EC
endmacro

macro ChannelVolumeFade(length, dest)
db $EE, <length>, <dest>
endmacro

; After temporarily setting the vibrato depth to 0,
; it will smoothly return to the original value over xx time.
macro VibratoFade(length)
db $F0, <length>
endmacro

; Specifies that subsequent sounds will be
; "higher by zz over yy time after xx time."
; zz is a semitone unit, and you can specify a negative number.
macro PitchEnvelopeTo(delay, length, key)
db $F1, <delay>, <length>, <key>
endmacro

; Specifies that subsequent notes will be
; "played at a pitch that is zz higher than normal,
;  and will return to normal pitch over yy time after xx time."
; zz is a semitone unit, and you can specify a negative number.
macro PitchEnvelopeFrom(delay, length, key)
db $F2, <delay>, <length>, <key>
endmacro

macro PitchEnvelopeOff()
db $F3
endmacro

; Change the pitch slightly.
; Only positive numbers can be specified, so the pitch cannot be lowered.
; xx = Unsigned. Make the pitch xx/256 semitones higher.
macro Tuning(v)
db $F4, <v>
endmacro

; Specifies the channel and volume at which echo is enabled.
; The value set in the register remains the same.
; xx = Echo Switch (EON)
; yy = Echo Left Volume (EVOL (L))
; zz = Echo Right Volume (EVOL (R))
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

; This VCMD is handled at different timing than other VCMDs.
; utter note $90, (wait), set instrument to $01, utter note $92
; $90, $e0 $01, $92
; utter note $90 then change the key immediately to note $91, (wait),
; utter note $92.
; $90, $f9 $00 $01 $91, $92
; utter note $90 then change the key immediately to note $91, (wait),
; set instrument to $01, utter note $92.
; $90, $f9 $00 $01 $91, $e0 01, $92
; <weird example> utter note $90, (wait), set instrument to $01,
; (pitch slide vcmd appears but note $90 has been end), utter note $92.
; $90, $e0 01, $f9 $00 $01 $91, $92

; Smoothly changes the pitch of the sound being pronounced.
; After xx time from play, it will be changed to the zz pitch
; (absolute designation) over yy time.
; If you want to raise or lower the sound in the middle of one note,
; write this command continuously.
; If the pronunciation time is long, you can write it with Thai.

; Normally, after one Note, it waits for the length of the note
; and then processes the next byte, but only this command
; is read and processed immediately.
macro PitchSlide(delay, length, note)
db $F9, <delay>, <length>, <note>
endmacro

; Determines the correspondence between the percussion value and the sound you hear.
macro PercussionPatchBass(instrument)
db $FA, <instrument>
endmacro

; ==============================================

macro PlayQuarterNotes(...)
  if sizeof(...) > 0
    db !4th, <...>
  else
    db !4th
  endif
endmacro

macro PlayEighthNotes(...)
  if sizeof(...) > 0
    db !8th, <...>
  else
    db !8th
  endif
endmacro

macro PlayHalfNotes(...)
  if sizeof(...) > 0
    db !4th, <...>
  else
    db !4th
  endif
  ; db !4th, <note>, $C8
endmacro

macro SustainNoteN(note, num)
  db note
  if num > 1
    db $C8
    %SustainNoteN(note, num - 1)
  endif
endmacro

End  = $00
Tie  = $C8
Rest = $C9

; Percussion Note ($CA-DF)
; VByte itself means percussion note (#).
; Relations between percussion note and SRCN depends on $FA.
; By default, percussion uses the same instrument set as the song,
; and all percussion is keyed on with a note of $A4.
; The starting ID to use for all channels can be redefined by VCMD $FA.


; =========================================================
; Tone Map
;
;       C   C+  D   D+  E   F   F+  G   G+  A   A+  B
; Oc1   80  81  82  83  84  85  86  87  88  89  8A  8B
; Oc2   8C  8D  8E  8F  90  91  92  93  94  95  96  97
; Oc3   98  99  9A  9B  9C  9D  9E  9F  A0  A1  A2  A3
; Oc4   A4  A5  A6  A7  A8  A9  AA  AB  AC  AD  AE  AF
; Oc5   B0  B1  B2  B3  B4  B5  B6  B7  B8  B9  BA  BB
; Oc6   BC  BD  BE  BF  C0  C1  C2  C3  C4  C5  C6  C7

C1   = $80
C1s  = $81
D1   = $82
D1s  = $83
E1   = $84
F1   = $85
F1s  = $86
G1   = $87
G1s  = $88
A1   = $89
A1s  = $8A
B1   = $8B

C2   = $8C
C2s  = $8D
D2   = $8E
D2s  = $8F
E2   = $90
F2   = $91
F2s  = $92
G2   = $93
G2s  = $94
A2   = $95
A2s  = $96
B2   = $97

C3   = $98
C3s  = $99
D3   = $9A
D3s  = $9B
E3   = $9C
F3   = $9D
F3s  = $9E
G3   = $9F
G3s  = $A0
A3   = $A1
A3s  = $A2
B3   = $A3

C4   = $A4
C4s  = $A5
D4   = $A6
D4s  = $A7
E4   = $A8
F4   = $A9
F4s  = $AA
G4   = $AB
G4s  = $AC
A4   = $AD
A4s  = $AE
B4   = $AF

C5   = $B0
C5s  = $B1
D5   = $B2
D5s  = $B3
E5   = $B4
F5   = $B5
F5s  = $B6
G5   = $B7
G5s  = $B8
A5   = $B9
A5s  = $BA
B5   = $BB

C6   = $BC
C6s  = $BD
D6   = $BE
D6s  = $BF
E6   = $C0
F6   = $C1
F6s  = $C2
G6   = $C3
G6s  = $C4
A6   = $C5
A6s  = $C6
B6   = $C7
