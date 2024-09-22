; ---------------------------------------------------------

Menu_CheckHScroll:
{
  LDA.b $F4
  BIT.b #$10 : BNE .leave_menu
    LDA.b $F6
    BIT.b #$20 : BNE .left
      BIT.b #$10 : BNE .right
        RTS

    .left

    REP #$20
    LDA.w #$FFF8
    BRA .merge

    .right
    REP #$20
    LDA.w #$0008

    .merge 
    STA.w MenuScrollHDirection

    SEP #$30
    INC.w $0200
    LDA.b #$06 : STA.w $012F
    RTS

  .leave_menu

  LDA.b #$0B : STA.w $0200
  RTS
}

; ---------------------------------------------------------

Menu_ScrollHorizontal:
{
  REP #$21                    ; set A to 16 bit, clear carry flag

  LDA.w $E4                   ; BG3 Horizontal Scroll Value
  ADC.w MenuScrollHDirection  ; Direction set by Menu_CheckHScroll
  AND.w #$01FF                
  STA.b $E4   
  AND.w #$00FF
  BNE .loop

  SEC
  RTS

.loop
  CLC 
  RTS
}

