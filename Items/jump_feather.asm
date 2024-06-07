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

; =========================================================
; Prevent Link from taking damage while jumping spikes
; The game originally differentiates between your armor 
; for the damage take, however the table has all the same
; values, so it's effectively useless. 

; TileDetect_MainHandler_no_moon_pearl
; org $07D23D
org $07D242
  JSL CheckIfJumpingForSpikeDamage
  NOP #2
warnpc $07D248

; =========================================================

org $2B8000
LinkItem_JumpFeather:
{
  JSL $07983A ; Reset swim state
  LDA $46 : BNE .cantuseit
    LDA #$02 : STA $5D ; set link state recoil
    LDA #$02 : STA $4D ; set jumping state (ledge hop)

    ; Length of the jump
    LDA #$20 : STA $46 

    ; Height of the jump
    LDA #$24 

    ; Set vertical resistance 
    STA $29
    STA $02C7

    ; Set Links direction to right(?)
    LDA #$08 : STA $0340 : STA $67

    ; Reset Link movement offsets 
    STZ $31 : STZ $30

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

; =========================================================
; Y contains our armor value
; Currently requires a very close jump and will still
; damage the player midair if you jump from too far away.

CheckIfJumpingForSpikeDamage:
{
    PHB : PHK : PLB
    ; Check Z pos of Link
    LDA $24 : BNE .airborne
      LDA.w .spike_floor_damage, Y : STA.w $0373
    .airborne
    PLB
    RTL

  .spike_floor_damage
    db $08 ; green
    db $08 ; blue
    db $04 ; red
}

print  "End of Items/jump_feather.asm     ", pc
pushpc