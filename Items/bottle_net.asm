; =============================================================================
; Bottle Net Code 
; =============================================================================

org $07B073
Link_CheckNewY_ButtonPress:

org $078028
Player_DoSfx2:

org $1EFE33
PlayerItem_SpawnFaerie:

org $1EDCCF
PlayerItem_ReleaseBee:

; =============================================================================
; LinkItem_Bottle

org $07A15B
  JMP $FFA0 ; Local Bank Conditional 

; =============================================================================
; $07FFA0 

org $07FFA0
{
  LDA $030D

  BNE $07FFBD 
  LDA $0300
  BNE $07FFBD 
  LDA $7F5020
  TAX 
  LDA $7EF35B, X
  CMP #$02
  BEQ $07FFBD
  JSR $B073
  JMP $A15E

; 07FFBD 
  JMP $AFF8 ; LinkItem_BugCatchingNet
  JMP $FAF0 ; 
  NOP
  JSR $B073
  STZ $030F
  RTS
}

; =============================================================================
; LinkItem_BugCatchingNet

org $07AFF8
{
  BIT $3A
  BVS $07B029
  LDA $6C
  BNE $07AFB4
  JSR $B073
  BCC $07AFB4
  LDA $2F
  LSR 
  TAY 
  LDX $AFF4,Y
  LDA $AFCC,X
  STA $0300
  LDA #$03
  STA $3D
  STZ $030D
  LDA #$10
  STA $037A
  JSL $8EFEF0
  STZ $2E
  LDA #$32
  JSR $8028
  JSR $AE65
  LDA $67
  AND #$F0
  STA $67
  DEC $3D
  BPL $07B072
  LDX $030D
  INX 
  STX $030D
  LDA #$03
  STA $3D
  LDA $2F
  LSR 
  TAY 
  LDA $AFF4,Y
  CLC 
  ADC $030D
  TAY 
  LDA $AFCC,Y
  STA $0300
  CPX #$0A
  BNE $07B072
  STZ $030D
  STZ $0300
  LDA $3A
  AND #$80
  STA $3A
  STZ $037A
  JSL $8EFEF8
  STA $50
  LDA #$80
  STA $44
  STA $45
  RTS  
}

; 07B073
org $07B073
{
  BIT $3A
  BVS $07B085
  LDA $46
  BNE $07B085
  LDA $F4
  AND #$40
  BEQ $07B085
  TSB $3A
  SEC
  RTS

; 07B085
org $07B085
  CLC
  RTS
}

; $8EFEF0
  LDA #$01
  TSB $50
  STA $0112
  RTL 


; =============================================================================

org $2C8000
LinkItem_NewBottle:
{ 
  ; Check if we have a bottle or not
  LDA $7EF34F : DEC A : TAX
  LDA $7EF35C, X : BEQ .exit
  
  ; Check if the bottle is empty 
  CMP.b #$03     : BCC .empty_bottle

  ; If so, prepare and call the LinkItem_Bottles routine 
  JSR LinkItem_Bottles 

.empty_bottle
  ; Otherwise, prepare and call the LinkItem_BugCatchingNet routien 
  JSR LinkItem_BugCatchingNet

.exit 
  RTL
}

; =============================================================================

; *$3A15B-$3A249 JUMP LOCATION
LinkItem_Bottles:
{
  LDA.b $3A : AND.b #$BF : STA.b $3A
  
  ; Check if we have a bottle or not
  LDA.l $7EF34F : DEC A : TAX
  
  LDA.l $7EF35C, X : BEQ .exit  ; (RTS)
  CMP.b #$03       : BCC .LinkItem_UselessBottle
  CMP.b #$03       : BEQ .LinkItem_RedPotion
  CMP.b #$04       : BEQ .LinkItem_GreenPotion
  CMP.b #$05       : BEQ .LinkItem_BluePotion
  CMP.b #$06       : BEQ .fairy
  
  BRL .LinkItem_BeeBottle

.exit 
  RTS

.fairy:
  BRL .LinkItem_FairyBottle

.LinkItem_RedPotion:
  LDA.l $7EF36C : CMP.l $7EF36D : BNE .can_drink_red

.LinkItem_UselessBottle:
  BRL $07A955 ; LinkGoBeep TODO(scawful): Investigate 

.can_drink_red:
  LDA.b #$02 : STA.l $7EF35C, X : STZ.w $0301
  
  LDA.b #$04 : STA.b $11
  LDA.b  $10 : STA.w $010C
  LDA.b #$0E : STA.b $10
  LDA.b #$07 : STA.w $0208
  
  JSL $0DFA58
  
  RTS

.LinkItem_GreenPotion:
  LDA $7EF36E : CMP.b #$80 : BNE .can_drink
  BRL $07A955 ; LinkGoBeep TODO(scawful): Investigate 

.can_drink:
  LDA $02 : STA $7EF35C, X : STZ $0301
  
  ; submodule ????
  LDA.b #$08 : STA $11
  LDA $10 : STA $010C
  
  ; Go to text mode
  LDA.b #$0E : STA $10
  LDA.b #$07 : STA $0208

  JSL $0DFA58 ; RebuildHUD_long TODO(scawful)
  BRA .bottle_exit

.LinkItem_BluePotion:
  LDA $7EF36C : CMP $7EF36D : BNE .useBluePotion
  LDA $7EF36E : CMP.b #$80 : BNE .useBluePotion
  BRL $07A955

.useBluePotion
  LDA.b #$02 : STA $7EF35C, X : STZ $0301
  
  ; more submodule code 
  LDA.b #$09 : STA.b $11
  LDA.b  $10 : STA.w $010C

  ; Go to text mode (?)
  LDA.b #$0E : STA.b $10
  LDA.b #$07 : STA.w $0208
  
  JSL $0DFA58 ; RebuildHUD_Long TODO(scawful)
  BRA .bottle_exit

.LinkItem_FairyBottle:
  STZ.w $0301
  JSL PlayerItem_SpawnFaerie : BPL .BRANCH_NU
  BRL $07A955

.BRANCH_NU:
  LDA.b #$02 : STA.l $7EF35C, X
  JSL $0DFA58 ; RebuildHUD_Long TODO(scawful)
  BRA .bottle_exit

.LinkItem_BeeBottle:
  STZ.w $0301
  JSL PlayerItem_ReleaseBee : BPL .bee_spawn_success
  BRL $07A955 ; LinkGoBeep 

.bee_spawn_success
  LDA.b #$02 : STA.l $7EF35C, X
  JSL $0DFA58 ; RebuildHUD_Long TODO(scawful)

.bottle_exit:
  RTS
}

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
LinkItem_BugCatchingNet:
{ 
  LDA $2F : LSR A : TAY
  LDX pose_offset, Y
  LDA pose_id, X : STA $0300
  LDA.b #$03 : STA $3D
  
  STZ $030D, X
  
  LDA.b #$10 : STA $037A
  LDA.b #$01 : TSB $50
  
  STZ $2E
  
  ; LDA.b #$32 : JSL Player_DoSfx2

.y_press:

  JSR Unknown ; $3AE65 IN ROM
  
  LDA $67 : AND.b #$F0 : STA $67
  DEC $3D : BPL .BRANCH_BETA
  LDX $030D : INX : STX $030D
  LDA.b #$03 : STA $3D
  LDA $2F : LSR A : TAY
  LDA pose_offset, Y : CLC : ADC $030D : TAY
  LDA pose_id, Y : STA $0300
  CPX.b #$0A : BNE .BRANCH_BETA
  
  STZ $030D
  STZ $0300
  
  LDA $3A : AND.b #$80 : STA $3A
  STZ $037A
  
  LDA $50 : AND.b #$FE : STA $50
  LDA.b #$80 : STA $44 : STA $45

.BRANCH_BETA:

  RTS
}

; *$3AE65-$3AE87 LOCAL
Unknown:
{
  LDA $AD : CMP.b #$02 : BNE .BRANCH_ALPHA
  
  LDA $0322 : AND.b #$03 : CMP.b #$03 : BNE .BRANCH_ALPHA
  
  STZ $30
  STZ $31
  STZ $67
  STZ $2A
  STZ $2B
  STZ $6B

.BRANCH_ALPHA:

  ; Cane of Somaria transit lines?
  LDA $02F5 : BEQ .BRANCH_BETA
  
  STZ $67

  .BRANCH_BETA:

  RTS
}

; =============================================================================
