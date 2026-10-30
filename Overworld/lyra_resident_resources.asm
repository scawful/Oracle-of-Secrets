; Source-only resident resource adapters. The constructor must bind code,
; authenticated resource data and restoration ownership before selection.
!LyraResidentResourcesEnabled = 0
if defined("LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED")
  !LyraResidentResourcesEnabled = !LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED
endif
assert !LyraResidentResourcesEnabled == 0 || !LyraResidentResourcesEnabled == 1
if !LyraResidentResourcesEnabled == 1
assert defined("LYRA_CURRENT_RESIDENT_ENABLED")
assert !LYRA_CURRENT_RESIDENT_ENABLED == 1
assert defined("LYRA_CURRENT_RESIDENT_ABI_VERSION")
assert !LYRA_CURRENT_RESIDENT_ABI_VERSION == 1
assert defined("LYRA_CURRENT_RESIDENT_RESOURCE_CODE_BASE")
assert defined("LYRA_CURRENT_RESIDENT_RESOURCE_CODE_END")
assert defined("LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY")
assert !LYRA_CURRENT_RESIDENT_RESOURCE_CODE_BASE&$8000
assert !LYRA_CURRENT_RESIDENT_RESOURCE_CODE_END > !LYRA_CURRENT_RESIDENT_RESOURCE_CODE_BASE
assert (!LYRA_CURRENT_RESIDENT_RESOURCE_CODE_BASE>>16) == ((!LYRA_CURRENT_RESIDENT_RESOURCE_CODE_END-1)>>16)
assert !LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY&$8000
assert (!LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY&$FFFF)+$0160 <= $10000

namespace Oracle
pushpc
org !LYRA_CURRENT_RESIDENT_RESOURCE_CODE_BASE
ResidentResourceCodeStart = pc()

; Internal A16. All32 entries exist; zero-length prefixes remain selected.
; DBR and D are never consulted. Return A=0/1 with its ordinary N/Z.
ResidentAnimationSelected:
{
  LDA.l $7E001B : AND.w #$00FF : BNE .none
  LDA.l $7E008A : AND.w #$00FF
  CMP.w #$00A0 : BCC .none
  CMP.w #$00C0 : BCS .none
  LDA.w #$0001
  RTS
.none
  LDA.w #$0000
  RTS
}

; A8, either index width. Return A.low=0/1 and loaded N/Z, preserving hidden
; B, every other flag, X/Y/DBR/D and live scratch. $0FC0=$FF records resident
; prefixes, so departure cannot disappear behind a native selector equality.
ResidentAnimationForceTransition:
{
  PHP : REP #$30 : PHA
  LDA.l $7E0FC0 : AND.w #$00FF : CMP.w #$00FF : BEQ .force
  JSR ResidentAnimationSelected
  BRA .result
.force
  LDA.w #$0001
.result
  SEP #$20
  STA $01, S
  REP #$20
  PLA : PLP
  PHA : PLA
  RTL
}

; Any M/X. Preserve the COMPLETE post-native-call state, including hidden B,
; decimal mode and all live scratch. The native decompressor owns full frame
; reconstruction; these records replace only each declared 4bpp prefix.
ResidentAnimationStage:
{
  PHP : REP #$30 : PHA : PHX : PHY : PHD
  CLD
  TSC : SEC : SBC.w #$0010 : TCS : INC : TCD
  JSR ResidentAnimationSelected : BNE .selected
  JMP .done
.selected
  LDA.l $7E008A : AND.w #$00FF : SEC : SBC.w #$00A0
  STA.b $08
  ASL : ASL : CLC : ADC.b $08 : ASL : CLC : ADC.b $08
  STA.b $08 : TAX
  LDA.l !LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY+9, X
  CMP.w #$0401 : BCC .extent
  JMP .done
.extent
  BIT.w #$0001 : BEQ .even
  JMP .done
.even
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
  LDA.l ResidentAnimationDestinations, X : STA.b $03
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

; The real $00D394 entry requires native M8/X8, D=0 and binary arithmetic.
; Its return ABI, scratch writes and native $0400 DMA scheduling are retained.
ResidentAnimationDecompress:
  JSL $00D394
  JML ResidentAnimationStage

ResidentAnimationDestinations:
  dw $A680,$AA80,$AE80
ResidentResourceCodeEnd = pc()
assert pc() <= !LYRA_CURRENT_RESIDENT_RESOURCE_CODE_END
pullpc
namespace off
endif
