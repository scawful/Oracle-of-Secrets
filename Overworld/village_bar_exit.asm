; =========================================================
; Wayward Village Bar pass-through exit router (Bank $2B, Items/all_items.asm)
;
; Room $0103 left half ($22 < $0700) connects two overworld doorways on OW $23:
;   - South Front Door ($42): $20 >= $2100 inside room $0103
;   - North Backdoor   ($43): $20 <  $2100 inside room $0103
; Right half ($22 >= $0700) belongs to Cottage $44 and stays untouched.
;
; Vanilla LoadOverworldFromUnderworld ($02E4BD) unconditionally restores
; $7EC140-$7EC171 and $0696 from whichever entrance Link entered, sending
; pass-through exits back out the entry door. This precheck refreshes the
; exit cache and $0696/$0698 by the door half Link is leaving before
; LoadCachedEntranceProperties runs.
; Also supplies the OW $23 closed-door cell ($1112) for Room $0106 (Richard
; Shed, Entrance $48) when $0696 is unset so OverworldDoor_ExitOpen opens the
; wooden door cleanly on exit.
; =========================================================

pushpc
org $02E4BD ; @hook module=Overworld name=VillageBar_ExitPrecheck kind=jsl target=VillageBar_ExitPrecheck expected_m=16 expected_x=8
  JSL VillageBar_ExitPrecheck
  NOP
assert pc() == $02E4C2
pullpc

; Entry/Exit: M=16, X=8, DB=$02 (restored on return), N/Z/C matching `LDA $A0 : CMP #$0104`.
VillageBar_ExitPrecheck:
{
  LDA.b $A0 : CMP.w #$0103 : BNE .check_shed
  LDA.b $22 : CMP.w #$0700 : BCS .exit ; Right half ($44 cottage): keep caller cache

  PHB : PHK : PLB
  PHX : PHY

  ; Preserve live sprite sheets ($7EC164-$7EC167) if cache already tracks OW $23.
  LDY.b #$00
  LDA.l $7EC140 : CMP.w #$0023 : BNE .no_preserve
    LDY.b #$01
    LDA.l $7EC164 : PHA
    LDA.l $7EC166 : PHA
  .no_preserve

  LDA.b $20 : CMP.w #$2100 : BCS .front_door

  ; North exit -> Backdoor $43 (back alley)
  LDA.w #$FFFF : STA.w $0696
  STZ.w $0698
  LDX.b #$30
  .copy_back
    LDA.w BarBackdoor_Cache, X
    STA.l $7EC140, X
    DEX : DEX
    BPL .copy_back
  BRA .after_copy

  .front_door
  ; South exit -> Front door $42 (village street)
  LDA.w #$14DA : STA.w $0696
  STZ.w $0698
  LDX.b #$30
  .copy_front
    LDA.w BarFrontdoor_Cache, X
    STA.l $7EC140, X
    DEX : DEX
    BPL .copy_front

  .after_copy
  TYA : AND.w #$00FF : BEQ .no_restore
    PLA : STA.l $7EC166
    PLA : STA.l $7EC164
  .no_restore

  PLY : PLX
  PLB

  .exit
  LDA.b $A0 : CMP.w #$0104
  RTL

  .check_shed
  ; Room $0106 (Richard Shed, Entrance $48): $0F:9D90 is $0000 in current
  ; base ROM, skipping OverworldDoor_ExitOpen on OW $23 exit. Supply the
  ; closed door map16 cell $1112 ((9,34) = $00FB/$00FC) only when unset.
  CMP.w #$0106 : BNE .exit
    LDA.l $7EC140 : CMP.w #$0023 : BNE .exit
    LDA.w $0696 : BNE .exit
    LDA.w #$1112 : STA.w $0696
    STZ.w $0698
    BRA .exit
}

; Captured live $7EC140-$7EC171 (25 words / 50 bytes) on OW $23 -> room $0103.
BarFrontdoor_Cache:
  dw $0023, $0016, $0A28, $0860, $0A88, $08D8, $0023, $114C
  dw $0A97, $08DF, $0800, $0B1E, $0600, $0900, $0720, $0C00
  dw $0500, $0A00, $2000, $0A3F, $0000, $000B, $FFF5, $0000
  dw $0000

BarBackdoor_Cache:
  dw $0023, $0016, $09C9, $0860, $0A29, $08D8, $0023, $0DCC
  dw $0A38, $08DF, $0800, $0B1E, $0600, $0900, $0720, $0C00
  dw $0500, $0A00, $2000, $0A3F, $0000, $FFFA, $0006, $0000
  dw $0000

print "End of village_bar_exit.asm        ", pc
