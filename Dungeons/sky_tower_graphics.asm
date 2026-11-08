; Selected Minish Cap A art through ordinary indoor graphics/palette tables.
; Main08 is inherited from Sky entrance29. Secondary0A changes only the
; first four rooms' floor sheet; the original collision group is retained.
; Rooms94/95/96/A0/B0/A6 retain their secondary groups and palettes. Their
; inherited wall-sheet changes require visual qualification with this profile.

assert !ENABLE_SOURCE_SPRITE_SHEETS == 1, "Sky graphics require source sheets E8/E9"

pushpc

; These existing slots were audited against all regular/spawn entrances,
; room headers, and the direct dream/attract/intro/credits graphics selectors.
assert read2($00E237) == $E073, "Sky main graphics table moved"
assert read4($00E07B) == $0815010A, "Sky source main group changed"
assert read4($00E07F) == $0F1B220E, "Sky source main group changed"
assert read4($00E0B3) == $62100161, "Sky destination main group changed"
assert read4($00E0B7) == $0F1B260E, "Sky destination main group changed"
assert read1($02811F) == $5D && read1($028126) == $5D, "Sky animation group changed"
assert read1($0F9629) == $01, "Sky entrance29 main group changed"

org $00E0B3 ; @hook module=Dungeons kind=data protected_size=8 name=SkyMainGroup08
SkyTower_MainGroup08:
  db $0A, $01, $E8, $08, $0E, $22, $1B, $0F
assert pc() == $00E0BB, "Sky main group size changed"

org $0F9629 ; @hook module=Dungeons kind=data protected_size=1 name=SkyEntrance29Graphics
  db $08

assert read4($00DD9B) == $1B220008, "Sky source secondary group changed"
assert read4($00DDBF) == $1B26000C, "Sky destination secondary group changed"
org $00DDBF ; @hook module=Dungeons kind=data protected_size=4 name=SkySecondaryGroup0A
SkyTower_SecondaryGroup0A:
  db $E9, $00, $22, $1B
assert pc() == $00DDC3, "Sky secondary group size changed"

; The secondary group also indexes the source-owned custom collision table.
; Reuse the existing mapping instead of inheriting group0A's old attributes.
assert group01-offs == $0080 && group0A-offs == $0500, "Sky collision group layout changed"
assert group_offsets == $2C8F21, "Sky collision offset table moved"
org $2C8F35 ; @hook module=Dungeons kind=data protected_size=2 name=SkyCollisionGroup0A
  dw group01-offs

assert read4($0ED474) == $0A030404, "Sky source palette set changed"
assert read4($0ED480) == $140F0002, "Sky destination palette set changed"
assert read2($1BEC67) == $09D8, "Sky global palette14 pointer changed"
org $0ED480 ; @hook module=Dungeons kind=data protected_size=4 name=SkyPaletteSet08
SkyTower_PaletteSet08:
  db $1C, $04, $03, $0A

; Clone global2, preserving every palette half except the preview's row3
; right colors1..7. The four decorative091 cells share this selected half.
org $1BE10C ; @hook module=Dungeons kind=data protected_size=180 name=SkyGlobalPalette14
SkyTower_GlobalPalette14:
  !sky_palette_word = 0
  while !sky_palette_word < 90
    dw read2($1BD89C+(!sky_palette_word*2))
    !sky_palette_word #= !sky_palette_word+1
  endwhile
assert pc() == $1BE1C0, "Sky global palette size changed"

org $1BE13A ; @hook module=Dungeons kind=data protected_size=14 name=SkyFloorColors
  dw $20C7, $210C, $21B4, $2E79, $473D, $63BF, $5DC7

; Room headers are editor-owned. The approved private input must carry these
; eight authoring bytes; ASM never overwrites editor-managed header storage.
assert read2($228A61) == $0A08, "Sky room090 graphics input not assigned"
assert read2($228A6F) == $0A08, "Sky room091 graphics input not assigned"
assert read2($228A7D) == $0A08, "Sky room092 graphics input not assigned"
assert read2($228A8B) == $0A08, "Sky room093 graphics input not assigned"

pullpc
