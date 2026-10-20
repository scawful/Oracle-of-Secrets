; A pending hall arrest cannot be skipped by leaving while the sprite pool
; lacks two guard slots. Reload the hall before the outdoor loader starts.
; No capture/ownership write, new RAM, or manipulation of return addresses.
if !ENABLE_D3_PRISON_SEQUENCE == 1

; Module08_00_LoadProperties, native M8/X8, DB02, DP0.
; C=1: caller's local RTS aborts this submodule after preparing Module05.
; C=0: A/N/Z reproduce LDA $10; CMP #$08 for the original BNE at $0283D6.
; Both paths preserve X/Y/DB and stack. Native room saves may use DP scratch.
D3Prison_PendingExitGate:
{
  PHP
  PHX : PHY
  LDA.b $10 : CMP.b #$08 : BNE .native
  LDA.b $11 : BNE .native
  JSR D3Prison_InDungeon : BCC .native
  LDA.b $A0 : CMP.b #$56 : BNE .native
  JSL D3Prison_ShouldResumeHall : BCC .native

  ; The old indoor room and dungeon still exist. Keep opened chests/doors
  ; and the current D3 key count before the next Module05 resets room RAM.
  JSL $02B929 ; Underworld_FlagRoomData_Quadrants
  JSL $02A1C7 ; SaveDungeonKeys (no mirror fade or inventory side effects)

  LDA.b #$01 : STA.w $010A ; do not recache interior coordinates as outdoors
  LDA.b #$28 : STA.w $010E ; normal room56 south entrance, pending retained
  STZ.w $010F
  STZ.w $04AA : STZ.w $04AB
  LDA.b #$05 : STA.b $10
  STZ.b $11 : STZ.b $14 : STZ.b $B0
  PLY : PLX
  PLP
  SEC
  RTL

  .native
  PLY : PLX
  PLP
  JSL $02856A ; AdjustLinkBunnyStatus (original call)
  LDA.b $10 : CMP.b #$08
  CLC ; routing result only; original BNE consumes the preserved comparison Z
  RTL
}

pushpc
; @source usdasm/bank_02.asm:Module08_00_LoadProperties, $0283CE-$0283D5
assert read1($0283CE) == $22 && read3($0283CF) == $02856A, "Unexpected Module08 bunny-status call"
assert read2($0283D2) == $10A5 && read2($0283D4) == $08C9, "Unexpected Module08 world selector"
org $0283CE ; @hook module=Dungeons name=D3Prison_PendingExitGate kind=jsl target=D3Prison_PendingExitGate expected_m=8 expected_x=8
  JSL D3Prison_PendingExitGate
  BCC .continue
  RTS ; return from Module08_00's JSR; outer Module08 RTL remains native
  NOP
  .continue
assert pc() == $0283D6
pullpc

endif
