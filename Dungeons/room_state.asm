; =========================================================
; Room-state bit: rooms that stay solved across visits and saves.
; Design: AFS handoffs/room_state_bit_2026-11-17/DESIGN.md
;
; SRAM: RoomSolvedBits ($7EF413, 37 bytes), one bit per room $000-$127.
;   byte = room >> 3, mask = $01 << (room & 7). Saved with the file.
; ROM:  RoomStateMode, one byte per room, generated from Data/room_state.json
;   by Scripts/Generate/generate_room_state_table.py.
;   bits 0-3 mode: 0 none, 1 code-owned (room ASM calls the API),
;                  2 shutters stay open once the room's tag opens them.
;   bit 4: on a solved mode-2 load, clear tag slot $AE.
;   bit 5: on a solved mode-2 load, clear tag slot $AF.
;   Mode 2 holds open shutters in door slots 0-3 only (vanilla draw limit).
;
; Public API (JSL, any M/X, preserves A/X/Y/DB/D, returns carry):
;   RoomState_IsSolved   - carry set if the current room ($A0) is solved.
;   RoomState_MarkSolved - set the current room's bit.
; =========================================================


!RoomStateDungeonMask = $0098C0 ; vanilla DungeonMask, bank $00

pushpc
; Room header load: shutters start closed. Solved mode-2 rooms start open.
assert read3($01B6B2) == $0001A9 && read3($01B6B5) == $04688D, "Header shutter init moved"
org $01B6B2 ; @hook module=Dungeons name=RoomState_InitShutters kind=jsl target=RoomState_InitShutters expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL RoomState_InitShutters
  NOP #2
assert pc() == $01B6B8

; Module07_02_0F entry close of open shutters.
assert read3($028BCA) == $0468EE && read3($028BCD) == $068E9C, "Entry shutter close moved"
org $028BCA ; @hook module=Dungeons name=RoomState_EntryClose kind=jml target=RoomState_EntryClose expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JML RoomState_EntryClose
  NOP #2
assert pc() == $028BD0

; Intraroom (quadrant) transition close. CartShutter97 .vanilla_close also
; lands here when !ENABLE_MINECART_CART_SHUTTERS is on.
assert read3($0289F8) == $0468EE && read3($0289FB) == $068E9C, "Intraroom shutter close moved"
org $0289F8 ; @hook module=Dungeons name=RoomState_IntraroomClose kind=jml target=RoomState_IntraroomClose expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  JML RoomState_IntraroomClose
  NOP #2
assert pc() == $0289FE

; RoomTag_OperateShutters: the tag opened the shutters. Mark mode-2 rooms.
assert read3($01C4A8) == $04689C && read3($01C4AB) == $068E9C, "OperateShutters open moved"
org $01C4A8 ; @hook module=Dungeons name=RoomState_OnShuttersOpened kind=jsl target=RoomState_OnShuttersOpened expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL RoomState_OnShuttersOpened
  NOP #2
assert pc() == $01C4AE
pullpc

; Code and table live in a fixed bank $54 slot (bank $2C is full).
; Ledger: room_state_code in Config/allocation_ownership.json.
pushpc
org $548000
RoomState_CodeStart:

incsrc "Dungeons/generated/room_state_table.asm"

RoomState_BitMask:
  db $01, $02, $04, $08, $10, $20, $40, $80

; ---------------------------------------------------------
; Internal helpers: M16 X16, room id in A. Clobber A and X only.
; ---------------------------------------------------------

; Out: A = mode byte (0 for rooms >= $128).
RoomState_ModeOf:
{
  CMP.w #$0128 : BCS .none
  TAX
  LDA.l RoomStateMode,X : AND.w #$00FF
  RTS
  .none
  LDA.w #$0000
  RTS
}

; Out: carry set if the room's bit is set.
RoomState_TestRoom:
{
  CMP.w #$0128 : BCS .no
  PHA                                  ; 3,S = room
  AND.w #$0007 : TAX
  LDA.l RoomState_BitMask,X : AND.w #$00FF
  PHA                                  ; 1,S = mask
  LDA 3,S : LSR #3 : TAX
  LDA.l RoomSolvedBits,X : AND 1,S
  CMP.w #$0001                         ; carry = bit set
  PLA : PLA                            ; PLA keeps carry
  RTS
  .no
  CLC
  RTS
}

; Sets the room's bit.
RoomState_SetRoom:
{
  CMP.w #$0128 : BCS .out
  PHA                                  ; 3,S = room
  AND.w #$0007 : TAX
  LDA.l RoomState_BitMask,X : AND.w #$00FF
  PHA                                  ; 1,S = mask (low byte)
  LDA 3,S : LSR #3 : TAX
  SEP #$20
  LDA.l RoomSolvedBits,X : ORA 1,S : STA.l RoomSolvedBits,X
  REP #$20
  PLA : PLA
  .out
  RTS
}

; Out: carry set if the current room is mode 2 and solved.
RoomState_CurrentStaysOpen:
{
  LDA.b $A0 : JSR RoomState_ModeOf
  AND.w #$000F : CMP.w #$0002 : BNE .no
  LDA.b $A0 : JMP RoomState_TestRoom
  .no
  CLC
  RTS
}

; ---------------------------------------------------------
; Public API
; ---------------------------------------------------------

RoomState_IsSolved:
{
  PHP : REP #$30 : PHA : PHX
  LDA.b $A0 : JSR RoomState_TestRoom
  PLX : PLA
  BCC .clear
  PLP : SEC
  RTL
  .clear
  PLP : CLC
  RTL
}

RoomState_MarkSolved:
{
  PHP : REP #$30 : PHA : PHX
  LDA.b $A0 : JSR RoomState_SetRoom
  PLX : PLA : PLP
  RTL
}

; ---------------------------------------------------------
; Hook bodies
; ---------------------------------------------------------

; $01B6B2, M16 X16. Replaces LDA #1 : STA $0468. Tags are already in $AE/$AF.
RoomState_InitShutters:
{
  PHX
  JSR RoomState_CurrentStaysOpen : BCC .closed
  LDA.b $A0 : JSR RoomState_ModeOf
  BIT.w #$0010 : BEQ .keep_ae
  SEP #$20 : STZ.b $AE : REP #$20
  .keep_ae
  BIT.w #$0020 : BEQ .keep_af
  SEP #$20 : STZ.b $AF : REP #$20
  .keep_af
  PLX
  STZ.w $0468
  RTL
  .closed
  PLX
  LDA.w #$0001 : STA.w $0468
  RTL
}

; Called from D6BossDoor_LoadFlag .ordinary (vanilla $01B0F3), M16 X16.
; X = door index * 2, Y = slot * 2 (0-6). A solved mode-2 room flags its
; shutter doors open so RoomDraw draws them open ($0468 is already 0).
; Shutter types $18/$44 never set $0400, so nothing is saved by this.
RoomState_FlagSolvedShutter:
{
  PHA : PHX
  LDA.w $0468 : BNE .done
  LDA.w $1980,X : AND.w #$00FF
  CMP.w #$0018 : BEQ .shutter
  CMP.w #$0044 : BNE .done
  .shutter
  JSR RoomState_CurrentStaysOpen : BCC .done
  TYX
  LDA.l !RoomStateDungeonMask,X
  ORA.w $068C : STA.w $068C
  .done
  PLX : PLA
  RTL
}

; $028BCA, Module07_02_0F. Replaces INC $0468 : STZ $068E.
RoomState_EntryClose:
{
  PHP : REP #$30 : PHX
  JSR RoomState_CurrentStaysOpen
  PLX
  BCS .stay_open
  PLP
  INC.w $0468
  STZ.w $068E
  JML $028BD0
  .stay_open
  PLP
  JML $028BD7 ; Underworld_SetBossOrSancMusicUponEntry
}

; $0289F8, UnderworldTransition_Intraroom_TriggerShutters. Same replacement.
RoomState_IntraroomClose:
{
  PHP : REP #$30 : PHX
  JSR RoomState_CurrentStaysOpen
  PLX
  BCS .stay_open
  PLP
  INC.w $0468
  STZ.w $068E
  JML $0289FE
  .stay_open
  PLP
  JML $028A05 ; RTS
}

; $01C4A8, RoomTag_OperateShutters, M16 X16. Replaces STZ $0468 : STZ $068E.
RoomState_OnShuttersOpened:
{
  STZ.w $0468
  STZ.w $068E
  PHX
  LDA.b $A0 : JSR RoomState_ModeOf
  AND.w #$000F : CMP.w #$0002 : BNE .done
  LDA.b $A0 : JSR RoomState_SetRoom
  .done
  PLX
  RTL
}

RoomState_CodeEnd:
assert pc() <= $548800, "Room-state code exceeds its bank $54 slot"
pullpc

