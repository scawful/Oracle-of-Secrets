; =========================================================
; Zarby Feather 

org $07AFF8 ; LinkItem_BugCatchingNet
{
    BIT $3A : BVS .return ;if Y or B are already pressed
      LDA $6C : BNE .return ; if we are standing in a dooray or not
        ; Link_CheckNewY_ButtonPress
        JSR $B073 : BCC .return ; Check if we just pressed Y Button  
          JSL LinkItem_JumpFeather
  .return
    RTS
}

; =============================================================================

org $2B8000
NewBookCode:
{
  JSL $07983A ; Reset swim state
  LDA $46 : BNE .cantuseit
  LDA #$02 : STA $5D ; state recoil
  LDA #$01 : STA $4D ; state recoil 2

  ; Length of the jump
  LDA #$20 

  STA $46 

  ; Height of the jump
  LDA #$24 

  ; Set vertical resistance 
  STA $29
  STA $02C7
  ; Set Links direction to right(?)
  LDA #$08 : STA $0340 : STA $67

  ; Reset Link movement offsets 
  STZ $31
  STZ $30

  LDA $F4 : AND #$08 : BEQ .noUp
      LDA #-8 ; Change that -8 if you want higher speed moving up
      STA $27 ; Vertical recoil
  .noUp
  LDA $F4 : AND #$04 : BEQ .noDown
      LDA #8  ; Change that -8 if you want higher speed moving down
      STA $27
  .noDown
  LDA $F4 : AND #$02 : BEQ .noLeft
      LDA #-8 ; Change that -8 if you want higher speed moving left
      STA $28 ; Horizontal recoil
  .noLeft
  LDA $F4 : AND #$01 : BEQ .noRight
      LDA #8  ; Change that 8 if you want higher speed moving right
      STA $28
  .noRight
  .cantuseit
  RTL
}

print  "End of Items/jump_feather.asm     ", pc
pushpc