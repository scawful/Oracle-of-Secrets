; Project-bound BG128 consumer. Included late, outside namespace Oracle.
; No address/default enable: producer must bind code/data ownership first.
assert !PROJECT_BG128_ENABLED == 1
assert !Func02C692 == 1, "BG128 requires the existing area-palette owner"
assert !DISABLE_OVERWORLD == 0, "BG128 requires the existing overworld tint owner"
; Full BG overrides include holes in legacy producers. A composed owner must
; restore those on departure, native save-load and Minish cache restoration.
; This cut intentionally cannot be enabled by supplying only an address.
assert defined("PROJECT_BG128_RESTORE_BOUND")
assert !PROJECT_BG128_RESTORE_BOUND == 1, "BG128 departure/native restore binding missing"
assert defined("PROJECT_BG128_CODE_BASE")
assert defined("PROJECT_BG128_CODE_END")
assert Oracle_ProjectBGPalette_DataEnd > Oracle_ProjectBGPalette_Data
assert Oracle_ProjectBGPalette_Data>>16 == (Oracle_ProjectBGPalette_DataEnd-1)>>16
namespace Oracle
pushpc
org !PROJECT_BG128_CODE_BASE

; Root source-only reservation: exactly [7ECA00,7ECC02), never SRAM.
ProjectBGPalette_NativeReference = $7ECA00
ProjectBGPalette_NativeEffective = $7ECB00
ProjectBGPalette_RestoreState = $7ECC00
ProjectBGPalette_RestoreArea = $7ECC01

; Any M/X. Byte stores only; do not clear/read uninitialized snapshot data.
ProjectBGPalette_Reset:
{
  PHP : SEP #$20 : PHA
  LDA.b #$00 : STA.l ProjectBGPalette_RestoreState
  LDA.b #$FF : STA.l ProjectBGPalette_RestoreArea
  PLA : PLP
  RTL
}

; Composed owner of the EXISTING 008827 site when BG128 is selected. The
; Masks file suppresses its writer in this profile, including Masks opt-out.
ProjectBGPalette_Startup:
{
  JSL ProjectBGPalette_Reset
  if !DISABLE_MASKS == 0
    JML StartupMasks
  else
    LDA.b #$80 : STA.b $13
    RTL
  endif
}

 ; Warm departure differs from destructive Reset: restore a valid source
; snapshot BEFORE invalidating it. Never open a destination transaction here.
; Any M/X; preserve A/P/X/Y/DB/D, with only the reserved flags/buffers written.
ProjectBGPalette_RestoreAndInvalidate:
{
  PHP : REP #$30 : PHA : PHX
  SEP #$20
  LDA.l ProjectBGPalette_RestoreState : CMP.b #$01 : BEQ .valid_capture
  CMP.b #$02 : BNE .invalidate
.valid_capture
  LDA.l ProjectBGPalette_RestoreArea : CMP.b #$C0 : BCS .invalidate
  LDA.b #$00 : STA.l ProjectBGPalette_RestoreState
  REP #$20
  LDX.w #$0000
.restore
  LDA.l ProjectBGPalette_NativeReference, X : STA.l $7EC300, X
  LDA.l ProjectBGPalette_NativeEffective, X : STA.l $7EC500, X
  INX : INX : CPX.w #$0100 : BCC .restore
.invalidate
  JSL ProjectBGPalette_Reset
  REP #$30 : PLX : PLA : PLP
  RTL
}

; Start BEFORE any native partial writer. A second Begin while state00
; does not restore/discard in-progress native writes. Destination may differ
; from the captured source; the departure routine never compares it to 8A.
ProjectBGPalette_Begin:
{
  JSL ProjectBGPalette_RestoreAndInvalidate
  PHP : SEP #$20 : PHA
  ; State00 plus a valid area is an open native transaction, not a capture.
  LDA.l $7E001B : BNE .done
  LDA.l $7E0010 : CMP.b #$05 : BCC .done
  CMP.b #$12 : BCS .done
  LDA.l $7E008A : CMP.b #$C0 : BCS .done
  STA.l ProjectBGPalette_RestoreArea
.done
  PLA : PLP
  RTL
}

; Complete only a native transaction opened for this exact destination.
; Invalid state/area and repeated completion never capture overridden data.
macro ProjectBGPaletteComplete(name, apply)
<name>:
{
  PHP : REP #$30 : PHA : PHX
  SEP #$20
  LDA.l ProjectBGPalette_RestoreState : CMP.b #$02 : BEQ .done
  CMP.b #$00 : BNE .abort
  LDA.l ProjectBGPalette_RestoreArea : CMP.b #$C0 : BCS .done
  CMP.l $7E008A : BNE .abort
  REP #$20
  JSR ProjectBGPalette_Lookup : BEQ .abort
  LDX.w #$0000
.capture
  LDA.l $7EC300, X : STA.l ProjectBGPalette_NativeReference, X
  LDA.l $7EC500, X : STA.l ProjectBGPalette_NativeEffective, X
  INX : INX : CPX.w #$0100 : BCC .capture
  SEP #$20
  LDA.l $7E008A : STA.l ProjectBGPalette_RestoreArea
  LDA.b #$01 : STA.l ProjectBGPalette_RestoreState
  ; ResolveColor accepts only state01; no native write can contaminate it.
  JSL <apply>
  LDA.b #$02 : STA.l ProjectBGPalette_RestoreState
  BRA .done
.abort
  JSL ProjectBGPalette_Reset
.done
  REP #$30 : PLX : PLA : PLP
  RTL
}
endmacro
%ProjectBGPaletteComplete(ProjectBGPalette_CompleteBuffer, ProjectBGPalette_ApplyBuffer)
%ProjectBGPaletteComplete(ProjectBGPalette_CompleteBoth, ProjectBGPalette_ApplyBoth)

; Native entry adapters displace only their verified setup instructions;
; the main copier still executes its original JSR/RTS tail at 1BEEE2.
ProjectBGPalette_IntroReset:
  JSL ProjectBGPalette_Reset
  REP #$30
  LDX.b $C8
  JML $0CC1A4

; Indoor entry must restore even though lookup will reject 1B!=0. The
; original long sprite call is replayed before continuing native producers.
ProjectBGPalette_IndoorDeparture:
  JSL ProjectBGPalette_RestoreAndInvalidate
  JSL $1BEC77
  JML $02C562

ProjectBGPalette_NativeAllBegin:
  JSL ProjectBGPalette_Begin
  REP #$20
  LDX.b #$00
  JML $02C5B6
ProjectBGPalette_WhirlpoolBegin:
  JSL ProjectBGPalette_Begin
  STZ.w $0AA9
  JSL $1BEC9E
  JML $02B4B5
ProjectBGPalette_WhirlpoolComplete:
  JSL $0BFE70
  JSL ProjectBGPalette_CompleteBuffer
  RTL

ProjectBGPalette_NativeMainBegin:
  JSL ProjectBGPalette_Begin
  REP #$21
  LDA.w $0AB3 : ASL
  JML $1BEECD
ProjectBGPalette_NativeAuxBegin:
  JSL ProjectBGPalette_Begin
  ASL : ASL : TAX
  STZ.w $0AA9
  JML $0ED5AE
ProjectBGPalette_NativeHudComplete:
  JSL $1BEE52
  JSL ProjectBGPalette_CompleteBuffer
  RTL

; Internal M16/XY16; A=nonzero byte offset or zero for normal behavior.
; No DP/DB access or WRAM allocation; lookup cannot affect Minish tile types.
ProjectBGPalette_Lookup:
{
  LDA.l $7E001B : AND.w #$00FF : BNE .none
  LDA.l $7E0010 : AND.w #$00FF
  CMP.w #$0005 : BCC .none
  CMP.w #$0012 : BCS .none
  LDA.l $7E008A : AND.w #$00FF : CMP.w #$00C0 : BCS .none
  ASL : TAX
  LDA.l ProjectBGPalette_Data, X
  RTS
.none
  LDA.w #$0000
  RTS
}

; Per-color hook: M16, X=byte destination relative to $7EC300.
; A becomes raw project color for BG only; preserve P/X/Y/DB/D and all DP.
; Native callers then apply their existing time effect exactly once.
ProjectBGPalette_ResolveColor:
{
  PHP : REP #$10 : PHX : PHY
  TAY
  LDA.l ProjectBGPalette_RestoreState : AND.w #$00FF
  CMP.w #$0001 : BNE .done
  LDA.l ProjectBGPalette_RestoreArea : AND.w #$00FF
  PHA
  LDA.l $7E008A : AND.w #$00FF
  CMP $01, S : BEQ .same_area
  PLA
  BRA .done
.same_area
  PLA
  ; Original X is below saved Y on the current stack.
  LDA $03, S : CMP.w #$0100 : BCS .done
  JSR ProjectBGPalette_Lookup : BEQ .done
  ; On stack: offset(1..2), original Y(3..4), original X(5..6).
  PHA
  LDA $05, S : CLC : ADC $01, S : TAX
  PLA
  LDA.l ProjectBGPalette_Data, X : TAY
.done
  TYA : PLY : PLX : PLP
  RTL
}

; Same-size source replacement for existing JSL $1BEEC7 callers. Native
; palette entry keeps its own M8/XY8 exit; full refresh preserves that state.
ProjectBGPalette_LoadMain:
{
  JSL $1BEEC7
  RTL
}

; Full refresh covers the holes the main/aux loaders never write. Preserve
; caller A (including hidden B), P/X/Y/DB/D. No OBJ/CGRAM/hardware writes.
; Normal blanked load updates its buffer; scrolling updates both buffers,
; matching Palette_MultiLoad_NonBuffer rather than changing fade scheduling.
macro ProjectBGPaletteApply(name, both)
<name>:
{
  PHP : REP #$30 : PHA : PHX : PHY
  LDA.l ProjectBGPalette_RestoreState : AND.w #$00FF
  CMP.w #$0001 : BNE .done
  LDA.l $7E0AA8 : BNE .done
  JSR ProjectBGPalette_Lookup : BEQ .done
  LDX.w #$0000
.next
  LDA.w #$0000
  JSL LoadDayNightPaletteEffect
  if <both> == 1
    STA.l $7EC500, X
  endif
  INX : INX : CPX.w #$0100 : BCC .next
.done
  PLY : PLX : PLA : PLP
  RTL
}
endmacro
%ProjectBGPaletteApply(ProjectBGPalette_ApplyBuffer, 0)
%ProjectBGPaletteApply(ProjectBGPalette_ApplyBoth, 1)
assert pc() <= !PROJECT_BG128_CODE_END, "Project BG128 code exceeds owned span"
pullpc

; Single boot-site owner: Masks emits no 008827 write in this profile.
pushpc
org $008827 ; @hook module=Core name=ProjectBGPalette_Startup kind=jsl target=ProjectBGPalette_Startup expected_m=8 expected_x=8
  JSL ProjectBGPalette_Startup
assert pc() == $00882B
assert read4($0CC1A0) == $C8A630C2, "Intro clear entry changed"
org $0CC1A0 ; @hook module=Core name=ProjectBGPalette_IntroReset kind=jml target=ProjectBGPalette_IntroReset
  JML ProjectBGPalette_IntroReset
assert pc() == $0CC1A4
assert read4($02C55E) == $1BEC7722, "Indoor palette entry changed"
org $02C55E ; @hook module=Overworld name=ProjectBGPalette_IndoorDeparture kind=jml target=ProjectBGPalette_IndoorDeparture
  JML ProjectBGPalette_IndoorDeparture
assert pc() == $02C562
assert read4($02C5B2) == $00A220C2, "Native all-palettes prologue changed"
org $02C5B2 ; @hook module=Overworld name=ProjectBGPalette_NativeAllBegin kind=jml target=ProjectBGPalette_NativeAllBegin
  JML ProjectBGPalette_NativeAllBegin
assert pc() == $02C5B6
assert read4($02B4AE) == $220AA99C, "Whirlpool palette prologue changed"
assert read4($02B4B1) == $1BEC9E22, "Whirlpool sprite call changed"
org $02B4AE ; @hook module=Overworld name=ProjectBGPalette_WhirlpoolBegin kind=jml target=ProjectBGPalette_WhirlpoolBegin
  JML ProjectBGPalette_WhirlpoolBegin : NOP #3
assert pc() == $02B4B5
assert read4($02B4D9) == $0BFE7022, "Whirlpool completion changed"
org $02B4D9 ; @hook module=Overworld name=ProjectBGPalette_WhirlpoolComplete kind=jsl target=ProjectBGPalette_WhirlpoolComplete
  JSL ProjectBGPalette_WhirlpoolComplete
assert pc() == $02B4DD
assert read4($1BEEC7) == $B3AD21C2, "Native main prologue changed"
org $1BEEC7 ; @hook module=Overworld name=ProjectBGPalette_NativeMainBegin kind=jml target=ProjectBGPalette_NativeMainBegin
  JML ProjectBGPalette_NativeMainBegin : NOP #2
assert pc() == $1BEECD
assert read4($0ED5A8) == $9CAA0A0A, "Native aux prologue changed"
org $0ED5A8 ; @hook module=Overworld name=ProjectBGPalette_NativeAuxBegin kind=jml target=ProjectBGPalette_NativeAuxBegin
  JML ProjectBGPalette_NativeAuxBegin : NOP #2
assert pc() == $0ED5AE
assert read4($02C617) == $1BEE5222, "Native full palette completion changed"
org $02C617 ; @hook module=Overworld name=ProjectBGPalette_NativeHudComplete kind=jsl target=ProjectBGPalette_NativeHudComplete
  JSL ProjectBGPalette_NativeHudComplete
assert pc() == $02C61B
pullpc
namespace off
