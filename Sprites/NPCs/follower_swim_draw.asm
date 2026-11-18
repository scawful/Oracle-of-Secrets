; Follower swim draw helpers (Q251). Moved from followers.asm (bank $2C) to bank $32
; on 2026-11-18: bank $2C overflowed by 28 bytes with lyra_temple_zora on.
; Bank-neutral: entered by JML/JSL from bank $09 hooks in followers.asm, exit by
; JML/RTL, and read only low WRAM with .w addresses.

; Hide follower OAM completely when FLWNODRAW ($02F9) or Zora Diving ($0AAB) is active.
FollowerDraw_GateCheck:
{
  LDA.w $02F9 : BNE .hide
  LDA.w $0AAB : BNE .hide ; !ZoraDiving
    JML $09A90D
  .hide
  JML $09A90C ; bank $09 RTS
}

; Match Player_Draw ($0D:A2AC): force OBJ priority 2 (#$20) while swimming so
; lower-index follower OAM never sits behind water BG and punches holes in Link.
FollowerDraw_WaterPriority:
{
  LDA.w $0345 : BNE .swim_prio ; DEEPWATER
  LDA.w $1A64, X : BIT.b #$20 : BNE .swim_prio
    AND.b #$0C : ASL #2
    RTL
  .swim_prio
  LDA.b #$20
  RTL
}

; Skip lower-body OAM while follower cached step is in deep water ($1A64,X & #$20;
; $09:AA8E overwrites DP $05 while drawing swim ripples, so index $1A64 via $02CF).
FollowerDraw_SkipSwimBody:
{
  LDX.w $02CF : BPL +
    LDX.b #$00
  +
  LDA.w $1A64, X : BIT.b #$20 : BEQ .draw_body
    JML $09ABF6 ; PLY : PLX : RTS
  .draw_body
  REP #$30
  PHY
  LDA.b $04
  AND.w #$00FF
  JML $09AB9A
}
