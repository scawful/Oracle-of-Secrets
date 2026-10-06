; =========================================================
; Impa follower hints (!ENABLE_IMPA_FOLLOWER_HINTS)
;
; While Impa follows Link (follower $01, vanilla Zelda), a line plays the
; first time Link enters each box below on the overworld. Route (opening plan
; 2026-09-23): beach -> village blockade -> hole / underground route ->
; Farore in the western forest.
;
; Hook: Follower_HandleTrigger entry ($09A59E, "LDA $11 : BNE .fail_fast").
; Every follower trigger check passes there; the hint check runs first, then
; the two vanilla instructions are replayed. Vanilla's own trigger table
; (Sprites/NPCs/followers.asm, Follower_HandleTriggerData) has a fixed number
; of overworld slots, all used by other followers, so Impa has her own table.
;
; One-shot state is WRAM (lost on power-off; kept through save & quit). A
; saved byte would need an SRAM allocation in Core/sram.asm.
;
; Messages: Data/dialogue/message_registry.json owner impa-follower ($1BF,
; $1C4). Text approved by scawful (2026-09-25/26) and in the slots
; (Docs/Planning/Plans/impa_follower_hints_2026-09-25.md).
; =========================================================

ImpaHint_ShowMessage = $0FFDAA ; RTL, Interface_PrepAndDisplayMessage ($1CF0 = ID)

!ImpaFollowerId  = $01
!ImpaHintMarker  = $A5          ; ImpaHint_Valid value once the flags are set up

; Vanilla free WRAM (Core/ram.asm UNUSED_7FF180). The opening uses
; $7FF300-$7FF331; the 2P PoC $7FF400+.
ImpaHint_Flags = $7FF340        ; bit per hint already shown
ImpaHint_Valid = $7FF341        ; !ImpaHintMarker, else the flags are garbage

!ImpaMsg_Village  = $01BF
!ImpaMsg_Blockade = $01C4
!ImpaMsg_Hole     = $01C8
!ImpaMsg_Forest   = $01C9

pushpc
; Follower_HandleTrigger: LDA.b $11 : BNE .fail_fast (4 bytes)
org $09A59E ; @hook module=Sprites name=ImpaHint_FollowerTrigger kind=jml target=ImpaHint_FollowerTrigger
  JML ImpaHint_FollowerTrigger
assert pc() == $09A5A2

org $3AE800
; Bank $3A layout: opening $3AC000-$3ADFFF; 2P PoC sword/lift $3AE000-$3AE64C;
; Impa hints $3AE800; text shade $3AEA00; early-game balance $3AEC00; 2P PoC $3AF000.

ImpaHint_FollowerTrigger:
{
  PHP
  JSR ImpaHint_Check
  PLP
  LDA.b $11 : BNE .fail_fast              ; replayed vanilla instructions
  JML $09A5A2                             ; Follower_HandleTrigger continues
  .fail_fast
  JML $09A5CD                             ; Follower_HandleTrigger .fail_fast
}

; Overworld box table. Coordinates are world pixels (Link's $22/$20).
; $8A holds the parent ID of a large area.
;   db area, flag bit : dw x0, x1, y0, y1, message
ImpaHint_Table:
  ; Wayward Village from the beach: south strip of the village ($23).
  db $23, $01 : dw 1536, 2559, 2992, 3071, !ImpaMsg_Village
  ; East exit blockade: pirate guard at (2528,2752).
  db $23, $02 : dw 2448, 2559, 2656, 2816, !ImpaMsg_Blockade
  ; Village hole (entrance 128, about (2416,2872)). About 100 px around it,
  ; so the line plays as Link enters the yard, not as he jumps in
  ; (scawful playtest 2026-09-25: the tight box fired too late).
  db $23, $04 : dw 2304, 2512, 2768, 2960, !ImpaMsg_Hole
  ; Western forest ($2A), where Farore waits at (1296,2768).
  db $2A, $08 : dw 1024, 1535, 2560, 3071, !ImpaMsg_Forest
  db $FF

ImpaHint_Check:
{
  PHB : PHK : PLB
  SEP #$30
  LDA.l $7EF3CC : CMP.b #!ImpaFollowerId : BNE .exit
  LDA.b $10 : CMP.b #$09 : BNE .exit      ; overworld play only
  LDA.b $11 : BNE .exit
  LDA.b $1B : BNE .exit

  LDA.l ImpaHint_Valid : CMP.b #!ImpaHintMarker : BEQ .valid
    LDA.b #$00 : STA.l ImpaHint_Flags
    LDA.b #!ImpaHintMarker : STA.l ImpaHint_Valid
  .valid

  LDX.b #$00
  .next
    LDA.w ImpaHint_Table, X : CMP.b #$FF : BEQ .exit
    CMP.b $8A : BNE .skip
    LDA.w ImpaHint_Table+1, X : AND.l ImpaHint_Flags : BNE .skip
    REP #$20
    LDA.b $22
    CMP.w ImpaHint_Table+2, X : BCC .skip16   ; X < x0
    CMP.w ImpaHint_Table+4, X : BEQ .x_ok
    BCS .skip16                               ; X > x1
    .x_ok
    LDA.b $20
    CMP.w ImpaHint_Table+6, X : BCC .skip16   ; Y < y0
    CMP.w ImpaHint_Table+8, X : BEQ .y_ok
    BCS .skip16                               ; Y > y1
    .y_ok
      LDA.w ImpaHint_Table+10, X : STA.w $1CF0
      SEP #$20
      LDA.w ImpaHint_Table+1, X : ORA.l ImpaHint_Flags : STA.l ImpaHint_Flags
      JSL ImpaHint_ShowMessage
      BRA .exit
    .skip16
    SEP #$20
    .skip
    TXA : CLC : ADC.b #$0C : TAX
    BRA .next

  .exit
  PLB
  RTS
}

print "End of Impa follower hints        ", pc
assert pc() <= $3AEA00, "Impa follower hints crossed $3AEA00 (Core/text_shade.asm)"
pullpc
