; Native special-overworld palette consumer body. Lifecycle callers own fades.
; No hooks, DMA, HUD, OBJ, column0 or backdrop writes are installed here.
if not(defined("SPECIAL_OVERWORLD_PALETTE_ENABLED"))
  !SPECIAL_OVERWORLD_PALETTE_ENABLED = 0
endif
assert !SPECIAL_OVERWORLD_PALETTE_ENABLED == 0 || !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
if !SPECIAL_OVERWORLD_PALETTE_ENABLED == 1
assert !SPECIAL_OVERWORLD_NATIVE == 1 && !SPECIAL_OVERWORLD_RESIDENT_ENABLED == 1
assert !SPECIAL_OVERWORLD_RESIDENT_FIRST == $0080
assert !SPECIAL_OVERWORLD_RESIDENT_END == $00A0 || !SPECIAL_OVERWORLD_RESIDENT_END == $00C0
assert defined("SPECIAL_OVERWORLD_PALETTE_CODE_BASE")
assert defined("SPECIAL_OVERWORLD_PALETTE_CODE_END")
assert !SPECIAL_OVERWORLD_PALETTE_CODE_BASE == $4DF000
assert !SPECIAL_OVERWORLD_PALETTE_CODE_END == $4E0000
assert defined("SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY")
assert !SPECIAL_OVERWORLD_RESIDENT_PALETTE_STRIDE == 3
assert !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY >= $008000 && !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY <= $FFFFFF
assert !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY&$8000
assert (!SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY>>16) != $7E && (!SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY>>16) != $7F
assert (!SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY&$FFFF)+((!SPECIAL_OVERWORLD_RESIDENT_END-$80)*3) <= $10000
assert Oracle_SpecialOverworldPaletteHoleReference == $7E1E8C
assert Oracle_SpecialOverworldPaletteHoleEffective == $7E1E98
assert Oracle_SpecialOverworldPaletteHoleState == $7E1EA4
assert Oracle_SpecialOverworldPaletteHoleArea == $7E1EA5

; Any native M/X width, DBR and D. Preserve hidden accumulator B, full X/Y,
; flags, DBR/D, native palette scratch00..0B,0AA8 and TimeState tint scratch.
; Stack-local DP16B belongs to this invocation, including nested invocations.
macro SpecialPaletteEnter()
  PHP : REP #$30 : PHA : PHX : PHY : PHD : PHB : CLD
  LDA.l $7E0000 : PHA
  LDA.l $7E0002 : PHA
  LDA.l $7E0004 : PHA
  LDA.l $7E0006 : PHA
  LDA.l $7E0008 : PHA
  LDA.l $7E000A : PHA
  LDA.l TimeState.BlueVal : PHA
  LDA.l TimeState.GreenVal : PHA
  LDA.l TimeState.RedVal : PHA
  LDA.l TimeState.TempColor : PHA
  LDA.l TimeState.SubColor : PHA
  LDA.l $7E0AA8 : PHA
  TSC : SEC : SBC.w #$0010 : TCS : INC : TCD
  SEP #$20 : LDA.b #$00 : PHA : PLB : REP #$20
endmacro
macro SpecialPaletteLeave()
  REP #$30
  TDC : DEC : CLC : ADC.w #$0010 : TCS
  PLA : STA.l $7E0AA8
  PLA : STA.l TimeState.SubColor
  PLA : STA.l TimeState.TempColor
  PLA : STA.l TimeState.RedVal
  PLA : STA.l TimeState.GreenVal
  PLA : STA.l TimeState.BlueVal
  PLA : STA.l $7E000A
  PLA : STA.l $7E0008
  PLA : STA.l $7E0006
  PLA : STA.l $7E0004
  PLA : STA.l $7E0002
  PLA : STA.l $7E0000
  PLB : PLD : PLY : PLX : PLA : PLP
  RTL
endmacro

namespace Oracle
pushpc
org $4DF000
SpecialOverworldPaletteCodeStart:

; State bit7: native reference holes retained. Low6: nesting depth (max63).
; Bit6 is reserved0. Effective words mirror reference holes at Both completion;
; they are NEVER captured from C500, which may already contain a midfade image.
SpecialOverworldPaletteBegin:
{
  %SpecialPaletteEnter()
  LDA.l SpecialOverworldPaletteHoleState : AND.w #$003F : BEQ .outer
  CMP.w #$003F : BCC .nested
  ; Overflow is a caller contract violation: invalidate instead of wrapping.
  JSR SpecialPaletteInvalidate
  JMP .done
.nested
  INC : STA.b $06
  LDA.l SpecialOverworldPaletteHoleState : AND.w #$0080 : ORA.b $06
  SEP #$20 : STA.l SpecialOverworldPaletteHoleState : REP #$20
  JMP .done
.outer
  ; Restore the OLD native reference holes even on departure/indoor rejection.
  ; The new native scene owns all subsequent reference/effective population.
  JSR SpecialPaletteRestoreReferenceHoles
  JSR SpecialPaletteOutdoors : BCC .invalid
  LDA.l $7E008A : CMP.w #!SPECIAL_OVERWORLD_RESIDENT_END : BCC .valid
.invalid
  JSR SpecialPaletteInvalidate
  JMP .done
.valid
  LDA.l SpecialOverworldPaletteHoleState : AND.w #$0080 : ORA.w #$0001
  SEP #$20 : STA.l SpecialOverworldPaletteHoleState : REP #$20
.done
  %SpecialPaletteLeave()
}

SpecialOverworldPaletteReset:
{
  %SpecialPaletteEnter()
  JSR SpecialPaletteInvalidate
  %SpecialPaletteLeave()
}
SpecialPaletteInvalidate:
  SEP #$20
  LDA.b #$00 : STA.l SpecialOverworldPaletteHoleState
  LDA.b #$FF : STA.l SpecialOverworldPaletteHoleArea
  REP #$20
  RTS

; C set only for native overworld palette modules05..11, outdoors. Full map
; bounds are checked separately; an unselected map still needs departure work.
SpecialPaletteOutdoors:
  LDA.l $7E0010 : AND.w #$00FF : CMP.w #$0005 : BCC .no
  CMP.w #$0012 : BCS .no
  LDA.l $7E001B : AND.w #$00FF : BNE .no
  SEC : RTS
.no
  CLC : RTS

; Current native palettes own6/20/14 records. Shared1BEBC6 has16 offsets,
; but animated records1BE604..1BE6C8 end after14; offsets14/15 alias main BG.
; Reject inheritedFF or malformed selectors before invoking native readers.
SpecialPaletteSelectors:
  LDA.l $7E0AB3 : AND.w #$00FF : CMP.w #$0006 : BCS .no
  LDA.l $7E0AB4 : AND.w #$00FF : CMP.w #$0014 : BCS .no
  LDA.l $7E0AB5 : AND.w #$00FF : CMP.w #$0014 : BCS .no
  LDA.l $7E0AB8 : AND.w #$00FF : CMP.w #$000E : BCS .no
  SEC : RTS
.no
  CLC : RTS

SpecialPaletteRestoreReferenceHoles:
{
  LDA.l SpecialOverworldPaletteHoleState : AND.w #$0080 : BEQ .done
  LDA.l SpecialOverworldPaletteHoleArea : AND.w #$00FF
  CMP.w #!SPECIAL_OVERWORLD_RESIDENT_FIRST : BCC .invalid
  CMP.w #!SPECIAL_OVERWORLD_RESIDENT_END : BCS .invalid
  LDX.w #$0000
.next
  LDA.l SpecialOverworldPaletteHoleReference,X : PHA : PHX
  TXA : ASL #4 : CLC : ADC.w #$0050 : TAX
  PLX : STX.b $0A : TAX
  PLA : STA.l $7EC300,X
  LDX.b $0A : INX : INX
  CPX.w #$000C : BCC .next
.done
  RTS
.invalid
  JSR SpecialPaletteInvalidate
  RTS
}

SpecialOverworldPaletteCompleteBuffer:
  %SpecialPaletteEnter()
  LDA.w #$0000 : STA.b $08
  BRA SpecialPaletteComplete
SpecialOverworldPaletteCompleteBoth:
  %SpecialPaletteEnter()
  LDA.w #$0001 : STA.b $08
SpecialPaletteComplete:
{
  LDA.l SpecialOverworldPaletteHoleState : AND.w #$003F : BNE .paired
  JMP .done
.paired
  CMP.w #$0001 : BEQ .outer
  DEC : STA.b $06
  LDA.l SpecialOverworldPaletteHoleState : AND.w #$0080 : ORA.b $06
  SEP #$20 : STA.l SpecialOverworldPaletteHoleState : REP #$20
  JMP .done
.outer
  JSR SpecialPaletteOutdoors : BCC .rejected
  LDA.l $7E008A : CMP.w #!SPECIAL_OVERWORLD_RESIDENT_END : BCS .rejected
  JSR SpecialPaletteSelectors : BCS .outdoors
.rejected
  JSR SpecialPaletteInvalidate
  JMP .done
.outdoors
  ; First resolve a sparse physical page pointer. Never truncate full8A.
  STZ.b $00 : STZ.b $02
  LDA.l $7E008A : CMP.w #!SPECIAL_OVERWORLD_RESIDENT_FIRST : BCC .resolved
  CMP.w #!SPECIAL_OVERWORLD_RESIDENT_END : BCS .resolved
  SEC : SBC.w #!SPECIAL_OVERWORLD_RESIDENT_FIRST
  STA.b $04 : ASL : CLC : ADC.b $04 : TAX
  LDA.l !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY,X : STA.b $00
  LDA.l !SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY+2,X : AND.w #$00FF : STA.b $02
.resolved
  LDA.b $00 : ORA.b $02 : BNE .refresh
  LDA.l SpecialOverworldPaletteHoleState : AND.w #$0080 : BNE .refresh
  JSR SpecialPaletteInvalidate
  JMP .done
.refresh
  ; Force all84 native opaque colors regardless of equality/cache shortcuts.
  ; Native callees require DBR00/D0, return M8/X8, and tint only C300.
  LDA.w #$0000 : STA.l $7E0AA8
  PHD : PEA.w $0000 : PLD
  SEP #$30
  JSL $1BEEC7
  JSL $1BEEE8
  JSL $1BEF0C
  JSL $1BEEA8
  REP #$30 : PLD
  LDA.b $00 : ORA.b $02 : BNE .resident
  ; Departure: restored native reference holes plus refreshed native84.
  JSR SpecialPaletteInvalidate
  BRA .copy_if_both
.resident
  ; Outer Begin removed any prior override. These are native holes, not
  ; currently displayed C500 colors. Capture anew only before applying packed.
  LDX.w #$0000
.capture
  STX.b $0A
  TXA : ASL #4 : CLC : ADC.w #$0050 : TAX
  LDA.l $7EC300,X
  LDX.b $0A : STA.l SpecialOverworldPaletteHoleReference,X
  INX : INX : CPX.w #$000C : BCC .capture
  SEP #$20
  LDA.b #$80 : STA.l SpecialOverworldPaletteHoleState
  LDA.l $7E008A : STA.l SpecialOverworldPaletteHoleArea
  REP #$20
  ; Packed256B palette uses native BG row2..7 slots1..15. Preserve every
  ; column0 and BG row0/1 (HUD). Tint each FINAL derived color exactly once.
  LDY.w #$0042
.color
  LDA.b [$00],Y
  PHY : PHD : PEA.w $0000 : PLD
  TYX : JSL LoadDayNightPaletteEffect
  REP #$30 : PLD : PLY
  INY : INY
  TYA : AND.w #$001F : BNE .same_row
  INY : INY
.same_row
  CPY.w #$0100 : BCC .color
.copy_if_both
  LDA.b $08 : BEQ .done
  ; A Both owner deliberately publishes the completed reference target. This
  ; mirrors the six native holes, never rewinds a displayed midfade snapshot.
  LDX.w #$0000
.mirror
  LDA.l SpecialOverworldPaletteHoleReference,X : STA.l SpecialOverworldPaletteHoleEffective,X
  INX : INX : CPX.w #$000C : BCC .mirror
  LDX.w #$0042
.copy
  LDA.l $7EC300,X : STA.l $7EC500,X
  INX : INX
  TXA : AND.w #$001F : BNE .same_copy_row
  INX : INX
.same_copy_row
  CPX.w #$0100 : BCC .copy
.done
  %SpecialPaletteLeave()
}
SpecialOverworldPaletteCodeEnd:
; Lifecycle adapters own the remainder of this reserved bank from offset500.
assert pc() <= !SPECIAL_OVERWORLD_PALETTE_CODE_BASE+$0500
pullpc
namespace off
endif
