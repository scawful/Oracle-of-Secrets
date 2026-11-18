; Overworld NMI area-song remaps (outdoors only).
;
; Area music is a 4-bit slot in !OverworldMusicCache, so areas only name $01-$0F.
; Remaps apply only when the NMI request matches the area's authored slot nibble,
; so parent $6F keeps its authored $03 Deku cue. A scripted $03 request in
; another DW area whose slot is not $03 still plays literal Rain.
;
; Rain ($03): DW outdoors areas $40-$7F whose cache nibble is $03 play Deku ($12)
; on the APU while $0133 stays $03 (same pattern as Great Sea $0C/$10). Restores
; selected Rain after intro control without changing area-table data; LW/special
; areas and DW slots other than $03 are unchanged.
;
; Great Sea ($10): alias $0C when the area slot is $0C, including a Lyra Sea
; tail map selecting that slot. Vanilla chase ($0C from area $18) keeps $0C.
; Lyra Sea special maps ($90-$92, $98-$9B) select it by area music $0C in the
; project's special-area table; overlay pages ($93-$97, $9C-$9F) never become the area.
;
; Snowpeak ($11): alias $06 (vanilla prologue, sent only by the intro at
; $0CEE9E) when the area slot is $06. Area music is project data (the native
; overworld Build rejects ASM writes to $02C303-$02C462): Snowpeak LW areas
; $03-$07, phases 1-3, set $56 (ambience 5, alias $06) instead of Death
; Mountain $5D, so the DW $0D areas ($43 lava mountain) keep Death Mountain and
; a mirror warp between the two changes song. A shared $0D alias did not: the
; NMI skips a song equal to $0133 (native, oos168x_snow_v1). Phase 0 keeps $03.
;
; $0133/$0130 keep the logical area slot; only APUIO0 changes.
; @source usdasm/bank_00.asm:0080EE (.song_input)

!GreatSeaSongAlias = $0C
!GreatSeaSongId    = $10
!SnowpeakSongAlias = $06
!SnowpeakSongId    = $11


; Keep the expanded handler out of bank $34's Finale/checkpoint tail.
; The music stream ends before this reservation; the cold loader starts at EF80.
pushpc
org $20EE00
NMI_GreatSeaSongRemap:
{
  CMP.b #!Song_Rain : BNE .great_sea
    PHX
    LDX.b $1B : BNE .rain_plain
    LDX.b $8A
    CPX.b #$40 : BCC .rain_plain
    CPX.b #$80 : BCS .rain_plain
    LDA.l !OverworldMusicCache, X : AND.b #$0F
    CMP.b #!Song_Rain : BNE .rain_plain
      LDA.b #!Song_DekuTheme : STA.w $2140
      LDA.b #!Song_Rain : STA.w $0133
      PLX
      RTL
    .rain_plain
    LDA.b #!Song_Rain
    PLX
    STA.w $2140 : STA.w $0133
    RTL

  .great_sea
  CMP.b #!SnowpeakSongAlias : BEQ .snowpeak
  CMP.b #!GreatSeaSongAlias : BNE .send
    PHX
    LDX.b $1B : BNE .plain                 ; indoors: plain $0C
    LDX.b $8A
    LDA.l !OverworldMusicCache, X : AND.b #$0F
    CMP.b #!GreatSeaSongAlias : BNE .plain ; area is not a Great Sea area
      LDA.b #!GreatSeaSongId : STA.w $2140
      LDA.b #!GreatSeaSongAlias : STA.w $0133
      PLX
      RTL
    .plain
    LDA.b #!GreatSeaSongAlias
    PLX
  .send
  STA.w $2140 : STA.w $0133
  RTL

  .snowpeak
    PHX
    LDX.b $1B : BNE .plain_snow            ; indoors: plain $06
    LDX.b $10
    CPX.b #$08 : BCC .plain_snow           ; intro/file-select/underworld ($00-$07): plain $06
    CPX.b #$11 : BCS .plain_snow           ; attract ($14) / non-OW ($11+): plain $06
    LDX.b $8A
    LDA.l !OverworldMusicCache, X : AND.b #$0F
    CMP.b #!SnowpeakSongAlias : BNE .plain_snow
      LDA.b #!SnowpeakSongId : STA.w $2140
      LDA.b #!SnowpeakSongAlias : STA.w $0133
      PLX
      RTL
    .plain_snow
    LDA.b #!SnowpeakSongAlias
    PLX
    BRA .send
}
assert pc() <= $20EF80, "NMI area-song remap overruns the cold intro loader"
pullpc

pushpc
; NMI song input: STA.w APUIO0 : STA.w $0133 (6 bytes). DBR=$00, M=8, X=8.
assert read3($0080F3) == $21408D && read3($0080F6) == $01338D, "NMI song input moved"
org $0080F3 ; @hook module=Overworld name=NMI_GreatSeaSongRemap kind=jsl target=NMI_GreatSeaSongRemap expected_m=8 expected_x=8
  JSL NMI_GreatSeaSongRemap : NOP #2
assert pc() == $0080F9
pullpc

print  "End of great_sea_music.asm        ", pc
