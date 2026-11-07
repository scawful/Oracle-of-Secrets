; =========================================================
; File: Overworld/special_overworld_graphics.asm
; Purpose: Native resident static/animated graphics and cache restoration.
; Source: retained606 graphics_runtime/resident_resources; current ZS callers.
; Verification: synthetic assembly only; CPU/DMA and palette joins pending.
; =========================================================
; Native special-overworld graphics consumers. Derived SharedGraphics22B
; records come from the saved-ROM resource compiler, never a second publisher.
; Default OFF. Palette lifecycle and complete Build admission remain separate.
if not(defined("SPECIAL_OVERWORLD_RESOURCES_ENABLED"))
  !SPECIAL_OVERWORLD_RESOURCES_ENABLED = 0
endif
assert !SPECIAL_OVERWORLD_RESOURCES_ENABLED == 0 || !SPECIAL_OVERWORLD_RESOURCES_ENABLED == 1
if !SPECIAL_OVERWORLD_RESOURCES_ENABLED == 1
assert !SPECIAL_OVERWORLD_NATIVE == 1
assert !SPECIAL_OVERWORLD_RESIDENT_ENABLED == 1
assert !SPECIAL_OVERWORLD_RESIDENT_FIRST == $0080
assert !SPECIAL_OVERWORLD_RESIDENT_END == $00A0 || !SPECIAL_OVERWORLD_RESIDENT_END == $00C0
assert defined("SPECIAL_OVERWORLD_RESOURCE_CODE_BASE")
assert defined("SPECIAL_OVERWORLD_RESOURCE_CODE_END")
assert !SPECIAL_OVERWORLD_RESOURCE_CODE_BASE == $4DC800
assert !SPECIAL_OVERWORLD_RESOURCE_CODE_END == $4DD000
assert defined("SPECIAL_OVERWORLD_TRANSFER_DIRECTORY")
assert defined("LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY")
assert !GfxRT_ABIVersion == 1 && !GfxRT_HeaderSize == 22
assert !GfxRT_NormalRecordSize == 7 && !GfxRT_StagingRecordSize == 8
assert !GfxRT_NormalCount == 0 && !GfxRT_NormalPtr == 2
assert !GfxRT_CacheMask == 4 && !GfxRT_TransitionMode == 5
assert !GfxRT_StagingCount == 13 && !GfxRT_StagingPtr == 15
assert !GfxRT_ModeNative == 3
assert !GfxRT_ParentCount == !SPECIAL_OVERWORLD_RESIDENT_END
assert !GfxRT_Bank >= $00 && !GfxRT_Bank <= $FF
assert !SPECIAL_OVERWORLD_TRANSFER_DIRECTORY >= $008000 && !SPECIAL_OVERWORLD_TRANSFER_DIRECTORY <= $FFFFFF
assert (!SPECIAL_OVERWORLD_TRANSFER_DIRECTORY>>16) == !GfxRT_Bank
assert (!SPECIAL_OVERWORLD_TRANSFER_DIRECTORY&$FFFF)+(!GfxRT_ParentCount*2) <= $10000
assert !SPECIAL_OVERWORLD_TRANSFER_DIRECTORY&$8000
assert (!SPECIAL_OVERWORLD_TRANSFER_DIRECTORY>>16) != $7E && (!SPECIAL_OVERWORLD_TRANSFER_DIRECTORY>>16) != $7F
assert !LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY&$8000
assert !LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY >= $008000 && !LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY <= $FFFFFF
assert (!LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY>>16) != $7E && (!LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY>>16) != $7F
assert (!LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY&$FFFF)+((!SPECIAL_OVERWORLD_RESIDENT_END-!SPECIAL_OVERWORLD_RESIDENT_FIRST)*11) <= $10000
assert Oracle_SpecialOverworldMainCache == $7E1E88
!SpecialGraphicsDataBank = (!GfxRT_Bank<<16)

namespace Oracle
pushpc
org !SPECIAL_OVERWORLD_RESOURCE_CODE_BASE
SpecialOverworldGraphicsCodeStart:

; Internal M16/X16. Full area word, not an eight-bit alias. The emitted
; physical-page directory has zero entries for every unselected legacy area.
SpecialGraphicsLookup:
{
  LDA.l $7E001B : AND.w #$00FF : BNE .none
  LDA.l $7E008A
  CMP.w #!SPECIAL_OVERWORLD_RESIDENT_FIRST : BCC .none
  CMP.w #!SPECIAL_OVERWORLD_RESIDENT_END : BCS .none
  ASL : TAX
  LDA.l !SPECIAL_OVERWORLD_TRANSFER_DIRECTORY, X : TAX
  RTS
.none
  LDX.w #$0000
  RTS
}

; Existing blanked normal-load callback owns channel0 and VRAM. No additional
; NMI transfer is introduced. Preserve full A/P/X/Y, including hidden B; DB/D
; are untouched. Only the authenticated static-prefix runs are uploaded.
SpecialOverworldGraphicsNormalLoad:
{
  PHP : REP #$30 : PHA : PHX : PHY : CLD
  JSR SpecialGraphicsLookup : BNE .profile
  JMP .done
.profile
  LDA.l !SpecialGraphicsDataBank+!GfxRT_NormalCount, X : TAY
  LDA.l !SpecialGraphicsDataBank+!GfxRT_NormalPtr, X : TAX
  CPY.w #$0000 : BEQ .invalidate
.next
  SEP #$20
  LDA.b #$80 : STA.l $002115
  LDA.l !SpecialGraphicsDataBank+2, X : STA.l $004304
  REP #$20
  LDA.l !SpecialGraphicsDataBank+3, X : STA.l $002116
  LDA.w #$1801 : STA.l $004300
  LDA.l !SpecialGraphicsDataBank, X : STA.l $004302
  LDA.l !SpecialGraphicsDataBank+5, X : STA.l $004305
  SEP #$20
  LDA.b #$01 : STA.l $00420B
  REP #$20
  TXA : CLC : ADC.w #!GfxRT_NormalRecordSize : TAX
  DEY : BNE .next
.invalidate
  JSR SpecialGraphicsMarkCache
.done
  REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; Keep native sheet identities while prior-sheet FF forces reload on departure.
; Native auxiliary LASTBGSET0..3 already own C2F8..FB. Main slots use the named
; four-byte reservation; no actor/OBJ cache is touched. Repeated marking cannot
; overwrite an underlying identity with FF.
macro SpecialGraphicsMarkMain(slot, offset, mask)
  LDA.l !SpecialGraphicsDataBank+!GfxRT_CacheMask, X : AND.w #<mask> : BEQ ?skip
  LDA.l $7E04CB+<slot> : AND.w #$00FF : CMP.w #$00FF : BEQ ?skip
  SEP #$20
  STA.l SpecialOverworldMainCache+<offset>
  LDA.b #$FF : STA.l $7E04CB+<slot>
  REP #$20
?skip:
endmacro

SpecialGraphicsMarkCache:
{
  JSR SpecialGraphicsLookup : BNE .profile
  RTS
.profile
  PHX
  LDA.l !SpecialGraphicsDataBank+!GfxRT_CacheMask, X : AND.w #$00FF
  LSR #3 : TAY
  LDX.w #$0003
.next
  TYA : LSR : TAY : BCC .skip
  LDA.l $7E04CB, X : AND.w #$00FF : CMP.w #$00FF : BEQ .skip
  SEP #$20
  STA.l $7EC2F5, X
  LDA.b #$FF : STA.l $7E04CB, X
  REP #$20
.skip
  INX : CPX.w #$0007 : BCC .next
  PLX
  %SpecialGraphicsMarkMain(0, 0, $0001)
  %SpecialGraphicsMarkMain(1, 1, $0002)
  %SpecialGraphicsMarkMain(2, 2, $0004)
  %SpecialGraphicsMarkMain(7, 3, $0080)
.done
  RTS
}

SpecialOverworldGraphicsInvalidateCache:
{
  PHP : REP #$30 : PHA : PHX : PHY
  JSR SpecialGraphicsMarkCache
  PLY : PLX : PLA : PLP
  RTL
}

; Fresh native identity setters run after this reset. This routine owns no
; reset of auxiliary cache identities: native InitTilesets owns those bytes.
SpecialOverworldGraphicsResetMainCache:
{
  PHP : REP #$20 : PHA : SEP #$20
  LDA.b #$FF
  STA.l SpecialOverworldMainCache
  STA.l SpecialOverworldMainCache+1
  STA.l SpecialOverworldMainCache+2
  STA.l SpecialOverworldMainCache+3
  REP #$20 : PLA : PLP
  RTL
}

; M8/X16, X=native slot0..7. Resolve a native inherited FF from the retained
; identity when prior-sheet FF records resident pixels, including departure
; to an unselected area. Return A.low only; hidden B/P/X/Y/DB/D unchanged.
SpecialOverworldGraphicsResolveSheet:
{
  PHP
  CMP.b #$FF : BNE .done
  CPX.w #$0003 : BCC .main
  CPX.w #$0007 : BEQ .main7
  BCS .done
  LDA.l $7E04CB, X : CMP.b #$FF : BEQ .aux
  BRA .invalid
.aux
  LDA.l $7EC2F5, X
  BRA .done
.main
  LDA.l $7E04CB, X : CMP.b #$FF : BNE .invalid
  LDA.l SpecialOverworldMainCache, X
  BRA .done
.main7
  LDA.l $7E04D2 : CMP.b #$FF : BNE .invalid
  LDA.l SpecialOverworldMainCache+3
  BRA .done
.invalid
  LDA.b #$FF
.done
  PLP
  RTL
}

; Postconversion only. Private stack DP, no DMA registers or native filler
; changes. Native NMI saves D and sets DP0 before using its own scratch.
SpecialOverworldGraphicsStageMain:
  PHP : REP #$30 : PHA : PHX : PHY : PHD : CLD
  LDY.w #$0001
  BRA SpecialGraphicsStageSetup
SpecialOverworldGraphicsStageAux:
  PHP : REP #$30 : PHA : PHX : PHY : PHD : CLD
  LDY.w #$0000
SpecialGraphicsStageSetup:
  TSC : SEC : SBC.w #$0010 : TCS : INC : TCD
  STY.b $0A
  JSR SpecialGraphicsLookup : BNE .profile
  JMP .done
.profile
  LDA.l !SpecialGraphicsDataBank+!GfxRT_StagingCount, X : STA.b $08
  BNE .records
  JMP .done
.records
  LDA.l !SpecialGraphicsDataBank+!GfxRT_StagingPtr, X : TAX
.next
  LDA.l !SpecialGraphicsDataBank, X : STA.b $00
  LDA.l !SpecialGraphicsDataBank+3, X : STA.b $03
  LDA.l !SpecialGraphicsDataBank+6, X : STA.b $06
  LDA.l !SpecialGraphicsDataBank+5, X : AND.w #$00FF
  CMP.w #$007F : BNE .skip
  LDA.b $06 : BEQ .skip
  AND.w #$0001 : BNE .skip
  LDA.b $03 : CMP.w #$4000 : BCS .skip
  CMP.w #$2000 : BCC .aux
  LDA.b $0A : BEQ .skip
  LDA.b $03 : CLC : ADC.b $06 : BCS .skip
  CMP.w #$4001 : BCS .skip
  BRA .selected
.aux
  LDA.b $0A : BNE .skip
  LDA.b $03 : CLC : ADC.b $06 : BCS .skip
  CMP.w #$2001 : BCS .skip
.selected
  SEP #$20
  LDA.l !SpecialGraphicsDataBank+2, X : STA.b $02
  LDA.l !SpecialGraphicsDataBank+5, X : STA.b $05
  REP #$20
  LDY.w #$0000
.copy
  LDA [$00], Y : STA [$03], Y
  INY #2 : CPY.b $06 : BCC .copy
.skip
  TXA : CLC : ADC.w #!GfxRT_StagingRecordSize : TAX
  DEC.b $08 : BNE .next
.done
  REP #$30
  TSC : CLC : ADC.w #$0010 : TCS
  PLD : PLY : PLX : PLA : PLP
  RTL

; M8, either index width. Loaded-result N/Z only; full hidden B and remaining
; caller state retained. FF forces native reconstruction on area departure.
SpecialOverworldAnimationForceTransition:
{
  PHP : REP #$30 : PHX : PHY : PHA
  LDA.l $7E0FC0 : AND.w #$00FF : CMP.w #$00FF : BEQ .force
  JSR SpecialGraphicsLookup : BEQ .none
.force
  LDA.w #$0001
  BRA .result
.none
  LDA.w #$0000
.result
  SEP #$20 : STA $01,S
  REP #$20 : PLA : PLY : PLX : PLP
  PHA : PLA
  RTL
}

; Preserve the complete native decompressor's return state. Only the three
; declared 4bpp prefixes replace native A680/AA80/AE80; full0400 upload timing
; and all native animation filler remain owned by the current engine.
SpecialOverworldAnimationStage:
{
  PHP : REP #$30 : PHA : PHX : PHY : PHD : CLD
  TSC : SEC : SBC.w #$0010 : TCS : INC : TCD
  JSR SpecialGraphicsLookup : BNE .selected
  JMP .done
.selected
  LDA.l $7E008A : SEC : SBC.w #!SPECIAL_OVERWORLD_RESIDENT_FIRST
  STA.b $08
  ASL : ASL : CLC : ADC.b $08 : ASL : CLC : ADC.b $08
  STA.b $08 : TAX
  LDA.l !LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY+9, X
  CMP.w #$0401 : BCS .done
  BIT.w #$0001 : BNE .done
  STA.b $06
  LDA.w #$0000 : STA.b $0A
  SEP #$20
  LDA.b #$7E : STA.b $05
  REP #$20
  LDA.b $06 : BEQ .mark
.frame
  LDX.b $08
  LDA.l !LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY, X : STA.b $00
  SEP #$20
  LDA.l !LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY+2, X : STA.b $02
  REP #$20
  LDA.b $0A : ASL : TAX
  LDA.l SpecialAnimationDestinations, X : STA.b $03
  LDY.w #$0000
.copy
  LDA [$00], Y : STA [$03], Y
  INY #2 : CPY.b $06 : BCC .copy
  LDA.b $08 : CLC : ADC.w #$0003 : STA.b $08
  INC.b $0A
  LDA.b $0A : CMP.w #$0003 : BCC .frame
.mark
  SEP #$20
  LDA.b #$FF : STA.l $7E0FC0
.done
  REP #$30
  TSC : CLC : ADC.w #$0010 : TCS
  PLD : PLY : PLX : PLA : PLP
  RTL
}

SpecialOverworldAnimationDecompress:
  ; Current ZSCustomOverworld DecompOwAnimatedTiles alias and usdasm00D394.
  ; Native entry remains M8/X8, binary arithmetic, DP0.
  JSL $00D394
  JML SpecialOverworldAnimationStage
SpecialAnimationDestinations:
  dw $A680,$AA80,$AE80
SpecialOverworldGraphicsCodeEnd:
assert pc() <= !SPECIAL_OVERWORLD_RESOURCE_CODE_END
pullpc
namespace off
endif
