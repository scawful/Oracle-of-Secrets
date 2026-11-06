incsrc "Core/music_macros.asm"

; Chain layout, loader patch and address functions. Must come first: the
; songs below overwrite bytes of the copied overworld chain.
incsrc "Music/song_banks.asm"

; ---------------------------------------------------------
; Overworld main block (ROM owrom($1A9EF9)+, ARAM $D000+)

incsrc "Music/lost_woods_v2.asm"
print  "End of Music/lost_woods_v2.asm    ", pc

; ---------------------------------------------------------
; Overworld auxiliary block (ARAM $2B00+): new songs after the old data.

org $20E43E : assert pc() == owrom($1AD333)
incsrc "Music/frozen_hyrule.asm"
print  "End of Music/frozen_hyrule.asm    ", pc

incsrc "Music/deku_theme.asm"
print  "End of Music/deku_theme.asm       ", pc

incsrc "Music/great_sea.asm"
print  "End of Music/great_sea.asm        ", pc

OWSongChainEnd:
  dw $0000, $0800
assert owaux_aram(OWSongChainEnd) <= !SongAuxAramOWLimit, "OW aux block overruns sample-pointer ARAM"
assert pc() <= $20F000, "OW chain overruns $20F000 (ZS lost woods data)"
assert pc() <= $20EE00, "OW aux songs overrun the NMI area-song remap"
assert pc() <= LoadIntroSongBankExpanded, "OW aux songs overrun cold-loader reservation"

org $20DDB2 : assert pc() == owrom($1ACCA7)
  dw OWSongChainEnd-owrom($1ACCAB)

org $20B022 : assert pc() == owrom($1A9F17)
  dw owaux_aram(GreatSea) ; OW $10

org $20B024 : assert pc() == owrom($1A9EF9+$20)
   dw owaux_aram(FrozenHyruleTheme) ; OW $11

org $20B026 : assert pc() == owrom($1A9EF9+$22)
  dw owaux_aram(GreatDekuTreeTheme) ; OW $12

; ---------------------------------------------------------
; Underworld main block (ROM $1B8004+, ARAM $D000+)

incsrc "Music/color_dungeon_theme.asm"
print  "End of color_dungeon_theme.asm    ", pc

; Song $0F: tail of the song $16 slot (song $17 starts at ARAM $F1D1).
incsrc "Music/stone_tower_temple_v2.asm"
assert pc() <= $1B9C0F+$5C6, "Stone Tower v2 overruns song $17"
print  "End of stone_tower_temple_v2.asm  ", pc

incsrc "Music/song_of_healing.asm"
assert pc() <= $1BA584, "Song of Healing overruns song $1A (ARAM $F580)"
print  "End of Music/song_of_healing.asm  ", pc

; ---------------------------------------------------------
; Underworld auxiliary block (ARAM $2B00+): new songs in the free run
; after the old data, over the old terminator.

org $1BB1D3
incsrc "Music/ww_ganondorf.asm"
incsrc "Music/dungeon_theme.asm"
print  "End of Music/dungeon_theme.asm    ", pc
UWSongChainEnd:
  dw $0000, $0800
assert uwaux_aram(UWSongChainEnd) <= !SongAuxAramLimit, "UW aux block overruns ARAM"
assert pc() <= $1BB800, "UW aux songs overrun the bank $1B free run"

org $1BACC3
  dw UWSongChainEnd-$1BACC7

org $1B8004+$16 : dw uwaux_aram(GanondorfBattle)          ; UW $0C
org $1B8004+$18 : dw uwaux_aram(DungeonTheme)             ; UW $0D
org $1B8004+$1C : dw uwmain_aram(StoneTowerTempleTheme)   ; UW $0F
