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
;
; Song IDs added here (pointer table = ARAM $D000 + 2*(id-1)):
;   OW $11 Frozen Hyrule      OW aux tail
;   UW $0C WW Ganondorf       UW aux tail
;   UW $0D Dungeon Theme      UW aux tail
;   UW $0F Stone Tower v2     UW song $16 slot tail
; Pointer offset = 2*(id-1). asar evaluates math left to right here, so
; the offsets are written as literals.
; UW $0E and OW $12 stay vanilla (v1 songs dropped 2026-11-05).
; OW $11 is not reachable from area music yet (4-bit area slots).
; @source usdasm/bank_00.asm:008913 (LoadOverworldSongs)

function owrom(a) = a-$1A9EF5+$20B000
function owmain_aram(x) = x-owrom($1A9EF9)+$D000
function owaux_aram(x) = x-owrom($1ACCAB)+$2B00
function uwmain_aram(x) = x-$1B8004+$D000
function uwaux_aram(x) = x-$1BACC7+$2B00

!SongAuxAramLimit = $3938

pushpc

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

pullpc
