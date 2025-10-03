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
assert pc() <= $07D248

; =========================================================

pullpc
LinkItem_JumpFeather:
{
  JSL Link_ResetSwimmingState
  LDA $46 : BNE .cant_use_it
    LDA #$02 : STA $5D ; set link state recoil
    LDA #$02 : STA $4D ; set jumping state (ledge hop)
    LDA #$20 : STA $46 ; length of the jump
    LDA #$24 ; Height of the jump

    ; Set vertical resistance
    STA $29
    STA $02C7

    ; Set Links direction to right(?)
    LDA #$08 : STA $0340 : STA $67

    ; Reset Link movement offsets
    STZ $31 : STZ $30

    LDA $F4 : AND #$08 : BEQ .no_up
      LDA #-8
      STA $27 ; Vertical recoil
    .no_up
    LDA $F4 : AND #$04 : BEQ .no_down
      LDA #8
      STA $27
    .no_down
    LDA $F4 : AND #$02 : BEQ .no_left
      LDA #-8
      STA $28 ; Horizontal recoil
    .no_left
    LDA $F4 : AND #$01 : BEQ .no_right
      LDA #8
      STA $28
    .no_right
  .cant_use_it
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
  LDA $5D : CMP.b #$02 : BEQ .airborne
    LDA.w .spike_floor_damage, Y : STA.w $0373
  .airborne
  PLB
  RTL

  .spike_floor_damage
    db $08 ; green
    db $08 ; blue
    db $04 ; red
}

%log_end("Items/jump_feather.asm", !LOG_ITEMS)
pushpc
