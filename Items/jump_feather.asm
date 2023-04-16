; =============================================================================
; Zarby Feather 

org $07AFF8
{
  BIT $3A : BVS .return ;if Y or B are already pressed

  LDA $6C : BNE .return ; if we are standing in a dooray or not

  ; Link_CheckNewY_ButtonPress
  JSR $B073 : BCC .return ; Check if we just pressed Y Button  
  JSL NewBookCode

.return
  RTS
}

; =============================================================================

org $218000
NewBookCode:
{
  JSL $07983A ; Reset swim state
  LDA $46 : BNE .cantuseit
  LDA #$02 : STA $5D ; state recoil
  LDA #$01 : STA $4D ; state recoil 2

  LDA #$20 ; Change this to change the length of the jump

  STA $46 

  LDA #$24 ; Change this to change the height of the jump

  STA $29 : STA $02C7
  LDA #$08 : STA $0340 : STA $67
  STZ $31
  STZ $30

  LDA $F4 : AND #$08 : BEQ .noUp
      LDA #-8 ; Change that -8 if you want higher speed moving up
      STA $27
  .noUp
  LDA $F4 : AND #$04 : BEQ .noDown
      LDA #8  ; Change that -8 if you want higher speed moving down
      STA $27
  .noDown
  LDA $F4 : AND #$02 : BEQ .noLeft
      LDA #-8 ; Change that -8 if you want higher speed moving left
      STA $28
  .noLeft
  LDA $F4 : AND #$01 : BEQ .noRight
      LDA #8  ; Change that 8 if you want higher speed moving right
      STA $28
  .noRight
  .cantuseit
  RTL
}
