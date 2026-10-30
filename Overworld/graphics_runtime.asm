; One catalog-backed consumer for normal entry, scrolling, cache restoration,
; native postconversion staging and incremental uploads. Records and new art
; share one audited LoROM bank. Existing ship/docks payloads retain their labels.
if not(defined("LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED"))
  !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED = 0
endif
assert !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 0 || !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
  assert !LYRA_CURRENT_MODE == 1
  assert defined("LYRA_CURRENT_RESIDENT_ENABLED")
  assert !LYRA_CURRENT_RESIDENT_ENABLED == 1
  assert defined("LYRA_CURRENT_RESIDENT_ABI_VERSION")
  assert !LYRA_CURRENT_RESIDENT_ABI_VERSION == 1
  assert defined("LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE"), "Resident main cache origin is unbound"
  assert defined("LYRA_CURRENT_RESIDENT_MAIN_CACHE_END"), "Resident main cache bound is unbound"
  assert defined("LYRA_CURRENT_RESIDENT_MAIN_CACHE_RESET_BOUND"), "Resident main cache reset is unbound"
  assert !LYRA_CURRENT_RESIDENT_MAIN_CACHE_RESET_BOUND == 1
  assert !LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE >= $7E0000
  assert !LYRA_CURRENT_RESIDENT_MAIN_CACHE_END <= $800000
  assert !LYRA_CURRENT_RESIDENT_MAIN_CACHE_END-!LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE == 4
  assert (!LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE>>16) == ((!LYRA_CURRENT_RESIDENT_MAIN_CACHE_END-1)>>16)
endif
pushpc
if not(defined("LYRA_CURRENT_MODE"))
  !LYRA_CURRENT_MODE = 0
endif
if !LYRA_CURRENT_MODE == 1
  assert defined("LYRA_CURRENT_GFX_ORIGIN")
  assert defined("LYRA_CURRENT_GFX_END")
  org !LYRA_CURRENT_GFX_ORIGIN
  SharedGraphicsRuntimeStart = pc()
  incsrc "Data/Generated/lyra_project/graphics_runtime_tables.asm"
else
org $5B8000
incsrc "Overworld/graphics_runtime_tables.asm"
if !ENABLE_KALYXO_BOAT == 1
  KalyxoDocksSlot3Graphics:
    incbin "gfx/kalyxo_docks_slot3.bin"
endif
endif
!GfxRT_DataBank = !GfxRT_Bank<<16
if !LYRA_CURRENT_MODE == 1
  assert !LYRA_CURRENT_FIRST == $A0
  assert !LYRA_CURRENT_END == $C0
  assert !LYRA_CURRENT_PARENT_COUNT == $C0
  assert !GfxRT_ParentCount == !LYRA_CURRENT_PARENT_COUNT
  assert (!LYRA_CURRENT_GFX_ORIGIN>>16) == !GfxRT_Bank
else
  assert !GfxRT_ParentCount == $A0
  assert !GfxRT_Bank == $5B
endif

; A/XY16, X=result (zero when unbound). No DP or DB assumptions.
SharedGraphicsLookup:
{
  LDA.l $7E001B : AND.w #$00FF : BNE .none
  LDA.l $7E008A : AND.w #$00FF
if !LYRA_CURRENT_MODE == 0 && !ENABLE_KALYXO_BOAT == 1
  CMP.w #$0030 : BNE .none
endif
if !LYRA_CURRENT_MODE == 1
  CMP.w #!LYRA_CURRENT_FIRST : BCC .none
endif
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
  LDA.l !GfxRT_DataBank+!GfxRT_NormalCount, X : TAY
  LDA.l !GfxRT_DataBank+!GfxRT_NormalPtr, X : TAX
  CPY.w #$0000 : BEQ .invalidate
  .next
    SEP #$20
    LDA.b #$80 : STA.l $002115
    LDA.l !GfxRT_DataBank+$0002, X : STA.l $004304
    REP #$20
    LDA.l !GfxRT_DataBank+$0003, X : STA.l $002116
    LDA.w #$1801 : STA.l $004300
    LDA.l !GfxRT_DataBank, X : STA.l $004302
    LDA.l !GfxRT_DataBank+$0005, X : STA.l $004305
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
if !LYRA_CURRENT_MODE == 1
  PHA
endif
  JSR SharedGraphicsMarkCache
if !LYRA_CURRENT_MODE == 1
  PLA
endif
  PLY : PLX : PLP
  RTL
}

SharedGraphicsMarkCache:
{
  JSR SharedGraphicsLookup : BEQ .done
  LDA.l !GfxRT_DataBank+!GfxRT_CacheMask, X : AND.w #$00FF
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
if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
  JSR ResidentGraphicsMarkMainCache
endif
  .done
  RTS
}

if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
; Four constructor-owned bytes, in slot order 0/1/2/7. Never alias the native
; auxiliary or sprite caches. Any M/X; preserve full A/P/X/Y/DB/D.
; Fresh identity transactions must reset BEFORE setting prior native sheets.
ResidentGraphicsResetMainCache:
{
  PHP : REP #$20 : PHA : SEP #$20
  LDA.b #$FF
  STA.l !LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE
  STA.l !LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE+1
  STA.l !LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE+2
  STA.l !LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE+3
  REP #$20 : PLA : PLP
  RTL
}

; Internal M16/XY16. A resolved sheet is 0..254; FF means invalid backup.
; Repeated invalidation must not replace an underlying ID with our sentinel.
macro ResidentGraphicsMarkMain(slot, offset, mask)
  LDA.l !GfxRT_DataBank+!GfxRT_CacheMask, X : AND.w #<mask> : BEQ ?skip
  LDA.l $7E04CB+<slot> : AND.w #$00FF : CMP.w #$00FF : BEQ ?skip
  SEP #$20
  STA.l !LYRA_CURRENT_RESIDENT_MAIN_CACHE_BASE+<offset>
  LDA.b #$FF : STA.l $7E04CB+<slot>
  REP #$20
?skip:
endmacro

ResidentGraphicsMarkMainCache:
{
  JSR SharedGraphicsLookup : BNE .profile
  RTS
  .profile
  %ResidentGraphicsMarkMain(0, 0, $0001)
  %ResidentGraphicsMarkMain(1, 1, $0002)
  %ResidentGraphicsMarkMain(2, 2, $0004)
  %ResidentGraphicsMarkMain(7, 3, $0080)
  RTS
}
endif

; NMI source substitution only: retain native destination/count/schedule.
; A16/XY8 in/out; preserve original A, P/X/Y/DB/D and all scratch memory.
SharedGraphicsTransitionSource:
{
  PHP : REP #$30 : PHX : PHY : PHA
  TAY
  JSR SharedGraphicsLookup : BEQ .done
  LDA.l !GfxRT_DataBank+!GfxRT_TransitionMode, X : AND.w #$00FF
  CMP.w #!GfxRT_ModeRange : BEQ .range
  CMP.w #!GfxRT_ModeStart : BNE .done
    TYA : CMP.l !GfxRT_DataBank+!GfxRT_TransitionStart, X
    BNE .done
    BRA .source
  .range
    TYA : CMP.l !GfxRT_DataBank+!GfxRT_TransitionStart, X : BCC .done
    CMP.l !GfxRT_DataBank+!GfxRT_TransitionEnd, X : BCS .done
  .source
    TYA : SEC : SBC.l !GfxRT_DataBank+!GfxRT_TransitionStart, X : ASL
    PHA
    LDA.l !GfxRT_DataBank+!GfxRT_TransitionSource, X
    CLC : ADC $01,s : STA.l $004302
    PLA
    SEP #$20
    LDA.l !GfxRT_DataBank+$0002+!GfxRT_TransitionSource, X : STA.l $004304
    REP #$20
  .done
  PLA : PLY : PLX : PLP
  RTL
}

; Called after vanilla PrepTransAuxGfx converts native BG slots, before the
; existing caller arms $17/$0710. Copy only sparse declared glyphs; native
; filler and NMI DMA counts remain intact. No extra NMI transfers.
if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
; Same preserved ABI as the auxiliary callback. Called only after main
; conversion, including static sheet7's upper half at $7F3C00.
SharedGraphicsStageNativeMain:
{
  PHP : REP #$30 : PHX : PHY : PHA : PHD
  LDY.w #$0001
  BRL SharedGraphicsStageNative_Setup
}
endif

SharedGraphicsStageNative:
{
  PHP : REP #$30 : PHX : PHY
if !LYRA_CURRENT_MODE == 1
  PHA
endif
  PHD
if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
  LDY.w #$0000
SharedGraphicsStageNative_Setup:
  ; Frame and extent arithmetic are binary; saved P restores caller decimal.
  CLD
endif
  ; Private stack frame: src[3], dst[3], byte count[2], records left[2].
  ; NMI saves D and sets D=0 at $0080CF..$0080D4; its own stack grows below
  ; these locals. Both the caller's D and stack are restored on every exit.
  TSC : SEC : SBC.w #$0010 : TCS : INC : TCD
if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
  STY.b $0A
endif
  JSR SharedGraphicsLookup : BNE .profile
  JMP .done
  .profile
  LDA.l !GfxRT_DataBank+!GfxRT_StagingCount, X : STA.b $08
  BNE .records
  JMP .done
  .records
  LDA.l !GfxRT_DataBank+!GfxRT_StagingPtr, X : TAX
  .next
    LDA.l !GfxRT_DataBank, X : STA.b $00
    LDA.l !GfxRT_DataBank+$0003, X : STA.b $03
    LDA.l !GfxRT_DataBank+$0006, X : STA.b $06
if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
    ; Both conversion owners share records. Patch only their own $7F half;
    ; native filler, animation buffers and every DMA register stay untouched.
    LDA.l !GfxRT_DataBank+$0005, X : AND.w #$00FF
    CMP.w #$007F : BNE .skipRecord
    LDA.b $06 : BEQ .skipRecord
    AND.w #$0001 : BNE .skipRecord
    LDA.b $03 : CMP.w #$4000 : BCS .skipRecord
    CMP.w #$2000 : BCC .auxiliary
      LDA.b $0A : BEQ .skipRecord
      LDA.b $03 : CLC : ADC.b $06 : BCS .skipRecord
      CMP.w #$4001 : BCS .skipRecord
      BRA .selectedRecord
    .auxiliary
      LDA.b $0A : BNE .skipRecord
      LDA.b $03 : CLC : ADC.b $06 : BCS .skipRecord
      CMP.w #$2001 : BCS .skipRecord
    .selectedRecord
endif
    SEP #$20
    LDA.l !GfxRT_DataBank+$0002, X : STA.b $02
    LDA.l !GfxRT_DataBank+$0005, X : STA.b $05
    REP #$20
    LDY.w #$0000
    .copy
      LDA [$00], Y : STA [$03], Y
      INY #2 : CPY.b $06 : BCC .copy
if !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED == 1
    .skipRecord
endif
    TXA : CLC : ADC.w #!GfxRT_StagingRecordSize : TAX
    DEC.b $08 : BNE .next
  .done
  TSC : CLC : ADC.w #$0010 : TCS
  PLD
if !LYRA_CURRENT_MODE == 1
  PLA
endif
  PLY : PLX : PLP
  RTL
}

; Existing incremental source hook, A8/XY16 in/out, X/Y/P/DB/D preserved.
; The fixed late ABI uses native steps $50..$5F and 512-byte chunks.
SharedGraphicsIncrementalSource:
{
  PHP : REP #$30 : PHX : PHY
if !LYRA_CURRENT_MODE == 1
  PHA
endif
  JSR SharedGraphicsLookup : BEQ .native
  LDA.l !GfxRT_DataBank+!GfxRT_LateFirst, X : AND.w #$00FF
  BEQ .native
  SEP #$20
  LDA.l $7E0019 : CMP.b #$50 : BCC .native
  CMP.b #$60 : BCS .native
    REP #$20
    AND.w #$00FF : SEC : SBC.w #$0050 : XBA : ASL
    CLC : ADC.l !GfxRT_DataBank+!GfxRT_LateSource, X : STA.l $004302
    SEP #$20
    LDA.l !GfxRT_DataBank+$0002+!GfxRT_LateSource, X : STA.l $004304
    BRA .done
  .native
    SEP #$20
    LDA.b #$7F : STA.l $004304
  .done
  REP #$30
if !LYRA_CURRENT_MODE == 1
  PLA
endif
  PLY : PLX : PLP
if !LYRA_CURRENT_MODE == 1
  ; Replay the replaced LDA #$7F result, flags and hidden B without
  ; overwriting the selected DMA source bank a second time.
  LDA.b #$7F
endif
  RTL
}
if !LYRA_CURRENT_MODE == 1
  SharedGraphicsRuntimeEnd = pc()
  assert pc() <= !LYRA_CURRENT_GFX_END
else
  assert pc() <= $5C0000
endif
pullpc
