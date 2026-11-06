; Shared deck pixels stay compatible while $30/$32 are visible together.
; Boats and aux $15 are committed only at normal transition stage $08.
if !ENABLE_KALYXO_DOCKS_PROFILE == 1
assert !ENABLE_OW_AUX_EXTENSION == 1, "Docks profile requires aux ABI 1"
pushpc

assert read1($02C242) == $22, "Finalize-entry animation call moved"
!DocksFinishOriginal = read3($02C243)
org $02C242 ; @hook module=Overworld name=DocksFinishTransition kind=jsl target=DocksFinishTransition protected_size=4
  JSL DocksFinishTransition
assert pc() == $02C246

org $448000
DocksGraphics:
incbin "Overworld/gfx/kalyxo_docks_bg.bin"
assert pc() == $44A000

; No new state or upload mechanism: use native sheet caches, conversion
; scratch $7F0000-$7F1FFF, and the existing two-sheet NMI request fields.
org $44A000
DocksNormalLoad:
{
  LDA.b $1B : BNE .native
  LDA.b $8A : CMP.b #$30 : BEQ .docks
  CMP.b #$32 : BEQ .beach
  .native
  JML CheckForChangeGraphicsNormalLoadBoat
  .docks
  %ApplyGraphicsSheet(DocksGraphics, $2C00)
  JSL DocksMarkNativeCache
  RTL
  .beach
  %ApplyGraphicsSpan(DocksGraphics+$0160, $2CB0, $0020)
  %ApplyGraphicsSpan(DocksGraphics+$0180, $2CC0, $0020)
  %ApplyGraphicsSpan(DocksGraphics+$01E0, $2CF0, $0020)
  %ApplyGraphicsSpan(DocksGraphics+$02C0, $2D60, $0020)
  %ApplyGraphicsSpan(DocksGraphics+$03A0, $2DD0, $0020)
  %ApplyGraphicsSpan(DocksGraphics+$03E0, $2DF0, $0020)
  JSL DocksMarkNativeCache
  RTL
}

; Normal-load callers return M/X8. Preserve the native ID before marking
; a slot dirty, so an inherited $FF table entry can restore that native sheet.
DocksMarkNativeCache:
{
  PHP : PHX : PHY
  LDY.b #$04
  LDA.b $8A : CMP.b #$32 : BNE +
    LDY.b #$01
  +
  LDX.b #$03
  .next
    LDA.w $04CB, X : CMP.b #$FF : BEQ .marked
      STA.l $7EC2F5, X
      LDA.b #$FF : STA.w $04CB, X
    .marked
    INX
    DEY : BNE .next
  PLY : PLX : PLP
  RTL
}

; A=table ID, X=slot, M/X8. Preserve X/Y and leave ordinary IDs unchanged.
DocksResolveTransitionSheet:
{
  ; Native destination sheets can corrupt the still-visible beach too.
  ; Hold its actual native sheets until stage08 commits the full raw profile.
  CPX.b #$03 : BCC .requested
  CPX.b #$07 : BCS .requested
  PHA
  LDA.b $1B : BNE .restoreRequested
  LDA.b $10 : CMP.b #$09 : BNE .restoreRequested
  LDA.b $8A : CMP.b #$30 : BNE .restoreRequested
  LDA.b $11 : CMP.b #$01 : BCC .restoreRequested
  CMP.b #$08 : BCS .restoreRequested
  PLA
  LDA.w $04CB, X : CMP.b #$FF : BNE .done
  LDA.l $7EC2F5, X
  RTL
  .restoreRequested
  PLA
  .requested
  CMP.b #$FF : BNE .done
  CPX.b #$03 : BCC .done
  CPX.b #$07 : BCS .done
  LDA.w $04CB, X : CMP.b #$FF : BEQ .restore
    LDA.b #$FF
    RTL
  .restore
  LDA.l $7EC2F5, X
  .done
  RTL
}

; PrepTransAuxGFX already converted native data. Replace only CB/CC/CF/
; D6/DD/DF with accepted LOW-half deck pixels; foliage and palettes stay native.
DocksPatchSharedDeckBuffer:
{
  LDA.b $1B : BNE .done
  LDA.b $8A : CMP.b #$30 : BEQ .patch
  CMP.b #$32 : BNE .done
  .patch
  PHP : PHX
  REP #$30
  LDX.w #$0000
  .next
    LDA.l DocksGraphics+$0160, X : STA.l $7F0160, X
    LDA.l DocksGraphics+$0180, X : STA.l $7F0180, X
    LDA.l DocksGraphics+$01E0, X : STA.l $7F01E0, X
    LDA.l DocksGraphics+$02C0, X : STA.l $7F02C0, X
    LDA.l DocksGraphics+$03A0, X : STA.l $7F03A0, X
    LDA.l DocksGraphics+$03E0, X : STA.l $7F03E0, X
    INX : INX
    CPX.w #$0020 : BCC .next
  SEP #$30
  PLX : PLP
  .done
  RTL
}

; M16, X width unchanged, A=BG1 selector. Carry set means retain the old
; palette while the outgoing beach remains visible in a normal scroll.
DocksDeferAuxPalette:
{
  CMP.w #$0015 : BNE .load
  PHA
  LDA.b $1B : AND.w #$00FF : BNE .restore
  LDA.b $10 : AND.w #$00FF : CMP.w #$0009 : BNE .restore
  LDA.b $8A : AND.w #$00FF : CMP.w #$0030 : BNE .restore
  LDA.b $11 : AND.w #$00FF : CMP.w #$0001 : BCC .restore
  CMP.w #$0008 : BCS .restore
  PLA : SEC
  RTL
  .restore
  PLA
  .load
  CLC
  RTL
}

; Replaces the existing stage08 animation JSL. Native prep ended at phase8.
; Two native-sized 4KiB requests keep the beach offscreen before boat upload.
; PhaseFF means complete; NewLoadTransAuxGFX resets it for the next crossing.
DocksFinishTransition:
{
  LDA.b $1B : BNE .native
  LDA.b $8A : CMP.b #$30 : BNE .native
  LDA.w $0CF3 : CMP.b #$FF : BEQ .native
  CMP.b #$01 : BEQ .second
  CMP.b #$08 : BCS .first
  .native
  JML !DocksFinishOriginal
  .first
  JSL $1BEEE8
  INC.b $15
  REP #$30
  LDX.w #$0000
  .copyFirst
    LDA.l DocksGraphics, X : STA.l $7F0000, X
    INX : INX
    CPX.w #$1000 : BCC .copyFirst
  LDA.w #$2C00 : STA.w $04D3
  LDA.w #$0000 : STA.w $04D5
  LDA.w #$3000 : STA.w $04D9
  LDA.w #$0800 : STA.w $04DB
  LDA.w #$0800 : STA.w $04D7 : STA.w $04DD
  SEP #$30
  LDA.b #$06 : STA.b $17 : STA.w $0710
  LDA.b #$01 : STA.w $0CF3
  RTL
  .second
  REP #$30
  LDX.w #$1000
  .copySecond
    LDA.l DocksGraphics, X : STA.l $7F0000, X
    INX : INX
    CPX.w #$2000 : BCC .copySecond
  LDA.w #$3400 : STA.w $04D3
  LDA.w #$1000 : STA.w $04D5
  LDA.w #$3800 : STA.w $04D9
  LDA.w #$1800 : STA.w $04DB
  LDA.w #$0800 : STA.w $04D7 : STA.w $04DD
  SEP #$30
  LDA.b #$06 : STA.b $17 : STA.w $0710
  JSL DocksMarkNativeCache
  LDA.b #$FF : STA.w $0CF3
  RTL
}
assert pc() <= $44B000, "Docks helpers exceed their allocation"
pullpc
endif
