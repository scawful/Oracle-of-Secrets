; D3 prison-wing phase gates. Keep the basement, Mad Batter and original
; entrance/warp records intact. The native room55 outward exit is separate
; from both of these entry paths and remains usable during the escape.
if !ENABLE_D3_PRISON_SEQUENCE == 1

; Persistent unlock, independent of the current sword or temporary form.
; Native DP=0. Preserve A/X/Y/DB and P except C; C=1 means wing open.
; Dungeon includes precede sprite width macros, so use raw SEP here.
D3Prison_WingIsOpen:
{
  PHP
  SEP #$20
  PHA
  LDA.l CastleAmbushFlags : AND.b #!CastleAmbush_HasEscaped
  BEQ .closed
  PLA : PLP : SEC : RTL
  .closed
  PLA : PLP : CLC : RTL
}

; Oracle FindEntrance calls this after selecting the real entrance ID but
; before STA010E or any transition writes. A=entry, M8/X16, DB34, DP0.
; C=0 blocks only the outside entrance32; C=1 keeps the ordinary entry.
; Preserve A/X/Y/DB and P except C. No dialogue, sound or inventory writes.
D3Prison_WingEntranceAllowed:
{
  PHP
  SEP #$20
  PHA
  CMP.b #$32 : BNE .allowed
  LDA.l $7E001B : BNE .allowed
  JSL D3Prison_WingIsOpen : BCS .allowed
  PLA : PLP : CLC : RTL
  .allowed
  PLA : PLP : SEC : RTL
}

; Predicate for the exact room80<->55 pad pair, never holes or stairs.
; Native DP=0. Preserve A/X/Y/DB and P except C; C=1 permits the warp.
D3Prison_WingWarpAllowed:
{
  PHP
  SEP #$20
  PHA
  JSL D3Prison_WingIsOpen : BCS .allowed
  LDA.l $7E001B : CMP.b #$01 : BNE .allowed
  LDA.l $7E040C : CMP.b #$10 : BNE .allowed
  LDA.l $7E00A1 : BNE .allowed
  LDA.l $7E00A0 : CMP.b #$80 : BEQ .from_basement
  CMP.b #$55 : BNE .allowed
  LDA.l $7EC000 : CMP.b #$80 : BEQ .blocked
  BRA .allowed
  .from_basement
  LDA.l $7EC000 : CMP.b #$55 : BNE .allowed
  .blocked
  PLA : PLP : CLC : RTL
  .allowed
  PLA : PLP : SEC : RTL
}

; TileDetect_MainHandler has already confirmed an indoor warp pad and the
; ordinary position/busy conditions. M8/X8, DB07, DP0. JML entry has no
; new return frame. Reject before room-save/module/target writes begin.
; Allowed path replays the original long call and resumes native SFX/warp.
D3Prison_WingWarpGate:
{
  PHP
  JSL D3Prison_WingWarpAllowed : BCS .allowed
  PLP
  JML $07D159 ; native no-warp continuation: clear tall-grass flag
  .allowed
  PLP
  JSL $02B929 ; Underworld_FlagRoomData_Quadrants (original call)
  JML $07D137
}

pushpc
; @source usdasm/bank_07.asm:TileDetect_MainHandler, $07D133-$07D136
assert read4($07D133) == $02B92922, "Unexpected indoor warp room-save call"
org $07D133 ; @hook module=Dungeons name=D3Prison_WingWarpGate kind=jml target=D3Prison_WingWarpGate expected_m=8 expected_x=8
  JML D3Prison_WingWarpGate
assert pc() == $07D137
pullpc

endif
