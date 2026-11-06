; Song bank layout (2026-11-05): give every custom song its own ID.
;
; Overworld chain: moved from $1A9EF5 to $20B000 so its auxiliary block can
; grow. The old chain is copied byte for byte from the base ROM (read1 reads
; the unpatched input ROM), then the custom songs re-org on top of the copy.
; Underworld chain: stays at $1B8000; its auxiliary block grows into the
; free run $1BB1D3-$1BB7FF (usdasm bank_1B "FREE ROM").
;
; Upload stream = blocks of (size word, ARAM word, data), ended by size $0000.
;   OW main  ROM $1A9EF5 -> ARAM $D000, size $2DAE (data $1A9EF9)
;   OW aux   ROM $1ACCA7 -> ARAM $2B00, size $0688 (data $1ACCAB)
;   UW main  ROM $1B8000 -> ARAM $D000, size $2CBF (data $1B8004)
;   UW aux   ROM $1BACC3 -> ARAM $2B00, size $050C (data $1BACC7)
; Auxiliary blocks may end at ARAM $3938 (the credits aux block uses that).
; OW-only custom aux may grow up to ARAM $3C00 (sample-pointer block).
;
; Song IDs added here (pointer table = ARAM $D000 + 2*(id-1)):
;   OW $10 Great Sea           OW aux (after Frozen Hyrule / Deku)
;   OW $11 Frozen Hyrule       OW aux tail
;   OW $12 Deku theme          OW aux (intro exposition)
;   UW $0C WW Ganondorf       UW aux tail
;   UW $0D Dungeon Theme      UW aux tail
;   UW $0F Stone Tower v2     UW song $16 slot tail
; Pointer offset = 2*(id-1). asar evaluates math left to right here, so
; the offsets are written as literals.
; UW $0E stays vanilla (v1 songs dropped 2026-11-05).
; OW $11 is not reachable from area music yet (4-bit area slots).
; @source usdasm/bank_00.asm:008901 (LoadIntroSongBank), :008913 (LoadOverworldSongs)
;
; Cold boot ($008901): full SamplePointers chain (incl. vanilla OW), then resend
; $FF until SPC posts $BBAA on $2140/$2141 (Engine_Start clears ports once),
; then LoadOverworldSongs ($008913) for the relocated $20B000 OW bank.

function owrom(a) = a-$1A9EF5+$20B000
function owmain_aram(x) = x-owrom($1A9EF9)+$D000
function owaux_aram(x) = x-owrom($1ACCAB)+$2B00
function uwmain_aram(x) = x-$1B8004+$D000
function uwaux_aram(x) = x-$1BACC7+$2B00

!SongAuxAramLimit = $3938
!SongAuxAramOWLimit = $3C00

SamplePointers = $198000

pushpc

assert read4($008901) == $008500A9, "LoadIntroSongBank header moved"
assert read4($008905) == $018580A9, "LoadIntroSongBank header moved"
assert read4($008909) == $028519A9, "LoadIntroSongBank header moved"
assert read4($00890D) == $88882078, "LoadIntroSongBank header moved"
assert read2($008911) == $6058, "LoadIntroSongBank header moved"

org $008901
  JSL LoadIntroSongBankExpanded
  RTS
  NOP #13
assert pc() == $008913, "Cold intro hook must end immediately before LoadOverworldSongs"

; LoadOverworldSongs: LDA.b #lo : STA $00 : LDA.b #hi : STA $01 : LDA.b #bank : STA $02
assert read1($008913) == $A9 && read1($008914) == $F5, "LoadOverworldSongs moved"
assert read1($008918) == $9E && read1($00891C) == $1A, "LoadOverworldSongs moved"
org $008914 : db owrom($1A9EF5)
org $008918 : db owrom($1A9EF5)>>8
org $00891C : db owrom($1A9EF5)>>16

; Old chain, header through last aux byte. The old terminator is rewritten
; after the new aux songs (Music/all_music.asm).
assert read2($1A9EF5) == $2DAE && read2($1A9EF7) == $D000, "OW main header moved"
assert read2($1ACCA7) == $0688 && read2($1ACCA9) == $2B00, "OW aux header moved"
assert read2($1AD333) == $0000, "OW chain terminator moved"
org $20B000
OWSongChain:
for i = 0..$343E
  db read1($1A9EF5+!i)
endfor
assert pc() == owrom($1AD333)

assert read2($1BACC3) == $050C && read2($1BACC5) == $2B00, "UW aux header moved"
assert read2($1BB1D3) == $0000, "UW chain terminator moved"

org $20EF80
LoadIntroSongBankExpanded:
{
  ; M=8, DB=$00, DP=$00 — entered by JSL from $008901, exits RTL.
  LDA.b #SamplePointers>>0 : STA.b $00
  LDA.b #SamplePointers>>8 : STA.b $01
  LDA.b #SamplePointers>>16
  JSL $00891D

  ; Repeated $FF survives SPC Engine_Start port clear ($F0); stop when Data_Loader
  ; advertises $BBAA (warm SongCommand_FF / LoadSongBank handshake), then $008913.
.restart_wait
  REP #$20
  LDA.w $2140
  CMP.w #$BBAA
  BEQ .restart_ready
  SEP #$20
  LDA.b #$FF : STA.w $2140
  BRA .restart_wait
.restart_ready
  SEP #$20

  JSL $008913
  RTL
}
assert pc() <= $20F000, "Cold intro loader overruns $20F000"

pullpc
