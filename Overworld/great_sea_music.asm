; Great Sea area music (song $10).
;
; Area music is a 4-bit slot in !OverworldMusicCache, so areas can only name
; songs $01-$0F. Song $10 (Music/great_sea.asm) is reached through alias $0C:
; when the NMI sends song $0C outdoors and the current area's own music slot
; is $0C, the sound chip gets $10 instead. Oracle areas use no $0C today, so
; this is inert until an area (the Lyra Sea tail maps $A0-$BF) sets music $0C.
;
; The vanilla chase theme ($05CC5F, area $18 bolt guard) also sends $0C; that
; area's slot is not $0C, so it keeps the chase theme.
;
; $0133 and $0130 keep $0C so the game's same-song checks still match the
; area slot. Only the value written to APUIO0 changes.
; @source usdasm/bank_00.asm:0080EE (.song_input)

!GreatSeaSongAlias = $0C
!GreatSeaSongId    = $10

NMI_GreatSeaSongRemap:
{
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
}

pushpc
; NMI song input: STA.w APUIO0 : STA.w $0133 (6 bytes). DBR=$00, M=8, X=8.
assert read3($0080F3) == $21408D && read3($0080F6) == $01338D, "NMI song input moved"
org $0080F3 ; @hook module=Overworld name=NMI_GreatSeaSongRemap kind=jsl target=NMI_GreatSeaSongRemap expected_m=8 expected_x=8
  JSL NMI_GreatSeaSongRemap : NOP #2
assert pc() == $0080F9
pullpc

print  "End of great_sea_music.asm        ", pc
