; One catalog-backed consumer for normal entry, scrolling, cache restoration,
; native postconversion staging and incremental uploads. Records and new art
; share one audited LoROM bank. Existing ship/docks payloads retain their labels.
pushpc
org $5B8000
incsrc "Overworld/graphics_runtime_tables.asm"

; A/XY16, X=result (zero when unbound). No DP or DB assumptions.
SharedGraphicsLookup:
{
  LDA.l $7E001B : AND.w #$00FF : BNE .none
  LDA.l $7E008A : AND.w #$00FF
  CMP.w #!GfxRT_ParentCount : BCS .none
  ASL : TAX
  LDA.l SharedGraphicsParentProfiles, X : TAX
  RTS
  .none
  LDX.w #$0000
  RTS
}

; Existing normal-entry/map-close/Soaring load sites only. A8/XY8 in/out;
; preserve P/X/Y/DB/D. These sites already own the blanked graphics load.
SharedGraphicsNormalLoad:
{
  PHP : REP #$30 : PHX : PHY
  JSR SharedGraphicsLookup : BNE .profile
  JMP .done
  .profile
  LDA.l $5B0000+!GfxRT_NormalCount, X : TAY
  LDA.l $5B0000+!GfxRT_NormalPtr, X : TAX
  CPY.w #$0000 : BEQ .invalidate
  .next
    SEP #$20
    LDA.b #$80 : STA.l $002115
    LDA.l $5B0002, X : STA.l $004304
    REP #$20
    LDA.l $5B0003, X : STA.l $002116
    LDA.w #$1801 : STA.l $004300
    LDA.l $5B0000, X : STA.l $004302
    LDA.l $5B0005, X : STA.l $004305
    SEP #$20
    LDA.b #$01 : STA.l $00420B
    REP #$20
    TXA : CLC : ADC.w #!GfxRT_NormalRecordSize : TAX
    DEY : BNE .next
  .invalidate
  JSR SharedGraphicsMarkCache
  .done
  REP #$30 : PLY : PLX : PLP
  RTL
}

; Mark only the declared slots, retaining underlying native IDs in the
; already-existing auxiliary cache. No new persistent WRAM or phase flag.
SharedGraphicsInvalidateCache:
{
  PHP : REP #$30 : PHX : PHY
  JSR SharedGraphicsMarkCache
  PLY : PLX : PLP
  RTL
}

SharedGraphicsMarkCache:
{
  JSR SharedGraphicsLookup : BEQ .done
  LDA.l $5B0000+!GfxRT_CacheMask, X : AND.w #$00FF
  LSR #3 : TAY
  LDX.w #$0003
  .next
    TYA : LSR : TAY : BCC .skip
    LDA.l $7E04CB, X : AND.w #$00FF : CMP.w #$00FF
    BEQ .skip
    SEP #$20
    STA.l $7EC2F5, X
    LDA.b #$FF : STA.l $7E04CB, X
    REP #$20
    .skip
    INX : CPX.w #$0007 : BCC .next
  .done
  RTS
}

; NMI source substitution only: retain native destination/count/schedule.
; A16/XY8 in/out; preserve original A, P/X/Y/DB/D and all scratch memory.
SharedGraphicsTransitionSource:
{
  PHP : REP #$30 : PHX : PHY : PHA
  TAY
  JSR SharedGraphicsLookup : BEQ .done
  LDA.l $5B0000+!GfxRT_TransitionMode, X : AND.w #$00FF
  CMP.w #!GfxRT_ModeRange : BEQ .range
  CMP.w #!GfxRT_ModeStart : BNE .done
    TYA : CMP.l $5B0000+!GfxRT_TransitionStart, X
    BNE .done
    BRA .source
  .range
    TYA : CMP.l $5B0000+!GfxRT_TransitionStart, X : BCC .done
    CMP.l $5B0000+!GfxRT_TransitionEnd, X : BCS .done
  .source
    TYA : SEC : SBC.l $5B0000+!GfxRT_TransitionStart, X : ASL
    PHA
    LDA.l $5B0000+!GfxRT_TransitionSource, X
    CLC : ADC $01,s : STA.l $004302
    PLA
    SEP #$20
    LDA.l $5B0002+!GfxRT_TransitionSource, X : STA.l $004304
    REP #$20
  .done
  PLA : PLY : PLX : PLP
  RTL
}

; Called after vanilla PrepTransAuxGfx converts native BG slots, before the
; existing caller arms $17/$0710. Copy only sparse declared glyphs; native
; filler and NMI DMA counts remain intact. No extra NMI transfers.
SharedGraphicsStageNative:
{
  PHP : REP #$30 : PHX : PHY : PHD
  ; Private stack frame: src[3], dst[3], byte count[2], records left[2].
  ; NMI saves D and sets D=0 at $0080CF..$0080D4; its own stack grows below
  ; these locals. Both the caller's D and stack are restored on every exit.
  TSC : SEC : SBC.w #$0010 : TCS : INC : TCD
  JSR SharedGraphicsLookup : BNE .profile
  JMP .done
  .profile
  LDA.l $5B0000+!GfxRT_StagingCount, X : STA.b $08
  BNE .records
  JMP .done
  .records
  LDA.l $5B0000+!GfxRT_StagingPtr, X : TAX
  .next
    LDA.l $5B0000, X : STA.b $00
    LDA.l $5B0003, X : STA.b $03
    LDA.l $5B0006, X : STA.b $06
    SEP #$20
    LDA.l $5B0002, X : STA.b $02
    LDA.l $5B0005, X : STA.b $05
    REP #$20
    LDY.w #$0000
    .copy
      LDA [$00], Y : STA [$03], Y
      INY #2 : CPY.b $06 : BCC .copy
    TXA : CLC : ADC.w #!GfxRT_StagingRecordSize : TAX
    DEC.b $08 : BNE .next
  .done
  TSC : CLC : ADC.w #$0010 : TCS
  PLD : PLY : PLX : PLP
  RTL
}

; Existing incremental source hook, A8/XY16 in/out, X/Y/P/DB/D preserved.
; The fixed late ABI uses native steps $50..$5F and 512-byte chunks.
SharedGraphicsIncrementalSource:
{
  PHP : REP #$30 : PHX : PHY
  JSR SharedGraphicsLookup : BEQ .native
  LDA.l $5B0000+!GfxRT_LateFirst, X : AND.w #$00FF
  BEQ .native
  SEP #$20
  LDA.l $7E0019 : CMP.b #$50 : BCC .native
  CMP.b #$60 : BCS .native
    REP #$20
    AND.w #$00FF : SEC : SBC.w #$0050 : XBA : ASL
    CLC : ADC.l $5B0000+!GfxRT_LateSource, X : STA.l $004302
    SEP #$20
    LDA.l $5B0002+!GfxRT_LateSource, X : STA.l $004304
    BRA .done
  .native
    SEP #$20
    LDA.b #$7F : STA.l $004304
  .done
  REP #$30 : PLY : PLX : PLP
  RTL
}
assert pc() <= $5C0000
pullpc
