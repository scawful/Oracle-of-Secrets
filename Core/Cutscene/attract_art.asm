; Illustrated Hyrule prologue before the title-idle history sequence.
; Module $14 keeps its original phases 0-9; $0A-$0C own this card only.
; No SRAM or new WRAM: $0200 is the existing attract countdown.

if !ENABLE_TITLE_LINK_ART == 1
pushpc
; Module_MainRouting: replace only Module14's three pointer bytes.
org $008075 : db AttractArt_Module>>0  ; @hook module=Cutscene name=AttractArt_ModuleLow kind=data
org $008091 : db AttractArt_Module>>8  ; @hook module=Cutscene name=AttractArt_ModuleMid kind=data
org $0080AD : db AttractArt_Module>>16 ; @hook module=Cutscene name=AttractArt_ModuleBank kind=data

; New source-owned bank, beyond the existing $40/$41 world-map assets.
; The selected base ends before this bank; no editor data is replaced.
org $428000
AttractArt_Module:
{
  ; Main routing enters M/X=8, DP=0, with one long return frame.
  ; Bank $42 has no hardware/WRAM mirror, so use DB=0, not PHK/PLB.
  LDA.b $22 : CMP.b #$01 : BEQ .initialize
              CMP.b #$0A : BCC .vanilla
              CMP.b #$0D : BCS .vanilla
  PHB : LDA.b #$00 : PHA : PLB

  ; Match vanilla attract controls, including a press during fade-in.
  LDA.b $F4 : AND.b #$90 : BNE .skip
  LDA.b $22 : CMP.b #$0A : BEQ .fade_in
              CMP.b #$0B : BEQ .hold

  LDA.b $13 : BEQ .resume
  DEC.b $13
  BRA .return

  .fade_in
  LDA.b $13 : CMP.b #$0F : BEQ .next_phase
  INC.b $13
  BRA .return

  .hold
  REP #$20
  DEC.w $0200
  SEP #$20
  BNE .return
  .next_phase
  INC.b $22
  .return
  PLB
  RTL

  .initialize
  PHB : LDA.b #$00 : PHA : PLB
  JSR AttractArt_Initialize
  PLB
  RTL

  .resume
  JSR AttractArt_Restore
  PLB
  ; Enter directly: vanilla clears $20-$70, then advances phase 0 to 3.
  ; Passing phase 1 through our wrapper again would replay the card.
  JML $0CEE0C

  .skip
  JSR AttractArt_Restore
  ; Attract_SkipToFileSelect decrements brightness before checking zero.
  LDA.b #$01 : STA.b $13
  LDA.b #$09 : STA.b $22
  PLB
  JML $0CF700

  .vanilla
  JML $0CEDAD
}

AttractArt_Initialize:
{
  JSL $00893D ; EnableForceBlank: $13/INIDISP=$80, HDMA disabled
  STZ.b $14
  STZ.b $95
  STZ.b $96 : STZ.b $97 : STZ.b $98
  STZ.b $99 : STZ.b $9A : STZ.b $9B
  STZ.w $420C
  STZ.w $212C : STZ.w $212D
  STZ.w $212E : STZ.w $212F
  STZ.w $2130 : STZ.w $2131
  LDA.b #$01 : STA.b $94 : STA.w $2105
  STA.b $1C : STA.w $212C
  STZ.b $1D
  STZ.b $1E : STZ.b $1F
  LDA.b #$60 : STA.w $2107 ; BG1 map: VRAM byte $C000
  LDA.b #$20 : STA.w $210B ; BG1 chars: byte $0000; retain BG2 base
  STZ.w $210D : STZ.w $210D
  STZ.w $210E : STZ.w $210E
  REP #$20
  STZ.w $011E : STZ.w $0120
  STZ.w $0122 : STZ.w $0124
  STZ.b $E4 : STZ.b $EA
  LDA.w #$1801 : STA.w $4300
  LDA.w #$0000 : STA.w $2116
  LDA.w #AttractArt_Tiles : STA.w $4302
  LDA.w #AttractArt_TilesEnd-AttractArt_Tiles : STA.w $4305
  SEP #$20
  LDA.b #$80 : STA.w $2115
  LDA.b #AttractArt_Tiles>>16 : STA.w $4304
  LDA.b #$01 : STA.w $420B
  REP #$20
  LDA.w #$6000 : STA.w $2116
  LDA.w #AttractArt_Map : STA.w $4302
  LDA.w #$0800 : STA.w $4305
  SEP #$20
  LDA.b #AttractArt_Map>>16 : STA.w $4304
  LDA.b #$01 : STA.w $420B

  ; Use HUD palette 0: vanilla initialization reloads all its 16 colors.
  REP #$20
  LDX.b #$1E
  .palette
  LDA.l AttractArt_Palette,X
  STA.l $7EC300,X
  STA.l $7EC500,X
  DEX : DEX : BPL .palette
  LDA.w #$00F0 : STA.w $0200 ; four-second hold, apart from fades
  SEP #$20
  INC.b $15
  STZ.b $13
  LDA.b #$0A : STA.b $22
  LDA.b #$06 : STA.w $012C ; same Legends theme as the history sequence
  RTS
}

AttractArt_Restore:
{
  JSL $00893D
  LDA.b #$22 : STA.w $210B
  LDA.b #$13 : STA.w $2107
  LDA.b #$03 : STA.w $2108
  LDA.b #$09 : STA.b $94 : STA.w $2105
  REP #$20
  STZ.w $011E : STZ.w $0120
  STZ.w $0122 : STZ.w $0124
  STZ.b $E4 : STZ.b $EA
  SEP #$20
  RTS
}

AttractArt_Tiles:
  incbin "Core/Cutscene/Assets/link_hyrule_intro/link_hyrule_intro.bin"
AttractArt_TilesEnd:
assert AttractArt_TilesEnd-AttractArt_Tiles <= $4000, "Intro art would replace inherited attract graphics"
AttractArt_Map:
  incbin "Core/Cutscene/Assets/link_hyrule_intro/link_hyrule_intro.map"
AttractArt_MapEnd:
assert AttractArt_MapEnd-AttractArt_Map == $0800
AttractArt_Palette:
  incbin "Core/Cutscene/Assets/link_hyrule_intro/link_hyrule_intro.pal"
AttractArt_PaletteEnd:
assert AttractArt_PaletteEnd-AttractArt_Palette == $0020
assert pc() <= $430000, "Illustrated attract prologue crossed its source-owned bank"
pullpc
endif
