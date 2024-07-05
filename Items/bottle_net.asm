; =============================================================================
; Bottle Net Code 
; =============================================================================

!BottleFlag = $0AA6

org $1EFE33
PlayerItem_SpawnFaerie:

org $1EDCCF
PlayerItem_ReleaseBee:

; =============================================================================
; LinkItem_Bottle

org $07A15B
LinkItem_NewBottle:
{ 
  ; Check if we have a bottle or not
  LDA $7EF34F : DEC A : TAX
  LDA $7EF35C, X : BEQ .exit

  ; Check if the bottle is empty 
  CMP.b #$03     : BCC .empty_bottle

  ; Confirm we aren't currently catching
  LDA $030D : BNE .empty_bottle

  ; If no, prepare and call the LinkItem_Bottles routine 
  JSR LinkItem_Bottles
  BRA .exit

.empty_bottle
  ; Otherwise, prepare and call the LinkItem_BugCatchingNet routine
  JSR LinkItem_CatchBottle
  
.exit 
  RTS
}

warnpc $07A249

pullpc

print "       LinkItem_CatchBottle       ", pc

; =============================================================================

pose_id:
  db $0B, $06, $07, $08, $01, $02, $03, $04, $05, $06 ; up
  db $01, $02, $03, $04, $05, $06, $07, $08, $01, $02 ; down
  db $09, $04, $05, $06, $07, $08, $01, $02, $03, $04 ; left
  db $0A, $08, $01, $02, $03, $04, $05, $06, $07, $08 ; right

pose_offset:
  db $00 ; up
  db $0A ; down
  db $14 ; left
  db $1E ; right

; *$3AFF8-$3B072 LOCAL
LinkItem_CatchBottle:
{ 
  BIT $3A : BVS .y_press
  
  LDA $6C : BNE .bottle_exit ; (RTS)
  
  JSR Link_CheckNewY_ButtonPress : BCC .bottle_exit ; (RTS)

  LDA $2F : LSR A : TAY
  LDX pose_offset, Y
  LDA pose_id, X : STA $0300
  LDA.b #$03 : STA $3D
  
  STZ $030D, X
  
  LDA.b #$10 : STA $037A
  LDA.b #$01 : TSB $50
  
  STZ $2E
  
  LDA.b #$32 : JSR Player_DoSfx2

.y_press:
  JSR  $AE65 ; HaltLinkWhenUsingItems
  
  LDA $67 : AND.b #$F0 : STA $67
  DEC $3D : BPL .bottle_exit
  LDX $030D : INX : STX $030D
  LDA.b #$03 : STA $3D
  LDA $2F : LSR A : TAY
  LDA pose_offset, Y : CLC : ADC $030D : TAY
  LDA pose_id, Y : STA $0300
  CPX.b #$0A : BNE .bottle_exit
  
  STZ $030D
  STZ $0300
  
  LDA $3A : AND.b #$80 : STA $3A
  STZ $037A
  
  LDA $50 : AND.b #$FE : STA $50
  LDA.b #$80 : STA $44 : STA $45

.bottle_exit:
NetExit:
  RTS
}

; =============================================================================
print "       LinkItem_Bottles           ", pc
LinkItem_Bottles:
{
  JSR Link_CheckNewY_ButtonPress : BCC NetExit ; (RTS)
  
  LDA.b $3A : AND.b #$BF : STA.b $3A
  
  ; Check if we have a bottle or not
  LDA.l $7EF34F : DEC A : TAX
  
  LDA.l $7EF35C, X : BEQ NetExit  ; (RTS)
  CMP.b #$03       : BCC .LinkItem_UselessBottle
  CMP.b #$03       : BEQ .LinkItem_RedPotion
  CMP.b #$04       : BEQ .LinkItem_GreenPotion
  CMP.b #$05       : BEQ .LinkItem_BluePotion
  CMP.b #$06       : BEQ .fairy
  CMP.b #$09       : BEQ .magic_bean
  CMP.b #$0A       : BEQ .milk_bottle

  BRL .LinkItem_BeeBottle

.milk_bottle
  LDA.l $7EF36C : CMP.l $7EF36D : BEQ .LinkItem_UselessBottle
    JSL Bottle_DrinkMilk
    RTS

.magic_bean
  JSL ReleaseMagicBean
  RTS

.fairy
  BRL .LinkItem_FairyBottle

.LinkItem_RedPotion
  LDA.l $7EF36C : CMP.l $7EF36D : BNE .can_drink_red

.LinkItem_UselessBottle
  BRL LinkGoBeep ; BRL $07A955 Investigate 

.can_drink_red
  LDA.b #$02 : STA.l $7EF35C, X : STZ.w $0301
  
  LDA.b #$04 : STA.b $11
  LDA.b  $10 : STA.w $010C
  LDA.b #$0E : STA.b $10
  LDA.b #$07 : STA.w $0208
  
  JSL $0DFA58
  
  RTS

.LinkItem_GreenPotion
  LDA.l $7EF36E : CMP.b #$80 : BNE .can_drink
  BRL LinkGoBeep

.can_drink
  ; Set the bottle empty
  LDA.b #$02 : STA.l $7EF35C, X : STZ.w $0301

  ; submodule ????
  LDA.b #$08 : STA.b $11
  LDA.b $10 : STA.w $010C
  
  ; Go to text mode
  LDA.b #$0E : STA.b $10
  LDA.b #$07 : STA.w $0208

  JSL $0DFA58 ; RebuildHUD_long 
  BRA .bottle_exit

.LinkItem_BluePotion
  LDA $7EF36C : CMP $7EF36D : BNE .useBluePotion
  LDA $7EF36E : CMP.b #$80 : BNE .useBluePotion
  BRL LinkGoBeep ; BRL $07A955

.useBluePotion
  LDA.b #$02 : STA $7EF35C, X : STZ $0301
  
  ; more submodule code 
  LDA.b #$09 : STA.b $11
  LDA.b  $10 : STA.w $010C

  ; Go to text mode (?)
  LDA.b #$0E : STA.b $10
  LDA.b #$07 : STA.w $0208
  
  JSL $0DFA58 ; RebuildHUD_Long 
  BRA .bottle_exit

.LinkItem_FairyBottle
  STZ.w $0301 : LDA.b #$02 : STA.l $7EF35C, X
  JSL PlayerItem_SpawnFaerie : BPL .released
  BRL LinkGoBeep ; BRL $07A955

.released
  JSL $0DFA58 ; RebuildHUD_Long 
  BRA .bottle_exit

.LinkItem_BeeBottle
  STZ.w $0301
  JSL PlayerItem_ReleaseBee : BPL .bee_spawn_success
  BRL LinkGoBeep ; BRL $07A955

.bee_spawn_success
  LDA.b #$02 : STA.l $7EF35C, X
  JSL $0DFA58 ; RebuildHUD_Long 

.bottle_exit
  RTS
}

LinkGoBeep:
{
  LDA.b #$3C : JSR Player_DoSfx2
  BRA LinkItem_Bottles_bottle_exit
}

Bottle_DrinkMilk:
{
  LDA.b #$28 : STA.l $7EF372 ; Heal 5 hearts
  LDA.b #$02 : STA.l $7EF35C, X : STZ.w $0301
  RTL
}

print  "End of Items/bottle_net.asm       ", pc
pushpc