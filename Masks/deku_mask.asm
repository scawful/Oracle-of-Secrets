; =============================================================================
; Deku Mask 

; ============================================================================= 

; Link Sprite hook
org $008A01
  LDA $BC

; =============================================================================

org $358000
incbin gfx/deku_link.bin

; =============================================================================

org $07F8D1
Link_HandleDekuTransformation:
{
  LDA $5D : CMP.b #$0A : BEQ .continue 
  JSR $82DA

.continue 
  STZ $03F5
  STZ $03F6
  
  ; Link can move.
  CLC
  
  RTS
}

org $07811A 
  JSR Link_HandleDekuTransformation

; =============================================================================

org $07A64B ; formerly Quake
LinkItem_DekuMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A        ; clear the Y button state 

  LDA $6C : BNE .return                 ; in a doorway
  LDA $0FFC : BNE .return               ; can't open menu

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP #$01 : BEQ .unequip   ; is the deku mask on?
  JSL Palette_ArmorAndGloves            ; set the palette 
  LDA #$0A : STA $5D                    ; set control handler to mode "using quake"
  LDA #$35 : STA $BC                    ; put the mask on
  LDA #$01 : STA $02B2
  
  LDA #$00 : STA $03FC
  BRA .return

.unequip
  JSL Palette_ArmorAndGloves
  STZ $5D
  STZ $03FC
  LDA #$10 : STA $BC : STZ $02B2        ; take the mask off

.return
  RTS
}

; =============================================================================

; LinkItem_UsingQuake is 152 (base10) bytes long 
org $07A6D6
LinkItem_UsingQuake: 
{
  JSR $82DA
  JSL LinkItem_UsingDekuMask

  RTS
  NOP #149
  
  print pc
}
; end of UsingQuake is at 07A773

; =============================================================================

org $318000
LinkItem_UsingDekuMask:
{
  JSL CheckIndoorStatus_Long

  LDA.b $F5
  AND.b #$80
  BEQ .dont_toggle_oob

  LDA.w $037F
  EOR.b #$01
  STA.w $037F

.dont_toggle_oob
  STZ.w $02CA
  
  LDA $0345 : BNE .recache
  LDA $4D : BEQ .recoiling
  ; LDA $7EF357 : BEQ .recache
  
  STZ $02E0

; *$383C7 LONG BRANCH LOCATION LinkState_Bunny_recache
.recache
  
  LDA $7EF357 : BEQ .no_pearl_a
  
  STZ $56 
  STZ $4D

.no_pearl_a

  STZ $2E     ; animation steps
  STZ $02E1   ; 
  STZ $50
  
  JSL Player_ResetSwimState
  
  ; Link hit a wall or an enemy hit him, making him go backwards.
  LDA.b #$02 : STA $5D
  
  LDA $7EF357 : BEQ .no_pearl_b
  
  ; this resets link to default state.
  LDA.b #$00 : STA $5D
  
  JSL LoadActualGearPalettes

.no_pearl_b

  BRL .exit 

.recoiling

  LDA $46 : BEQ .wait_maybe_not_recoiling
  ;BRL $0783A1 ; Permabunny mode.

.wait_maybe_not_recoiling

  LDA.b #$FF : STA $24 : STA $25 : STA $29
  STZ $02C6
  
  LDA $034A : BEQ .not_moving
  
  LDA.b #$01 : STA $0335 : STA $0337
  LDA.b #$80 : STA $0334 : STA $0336
  
  ; BRL $9715

.not_moving

  JSL Player_ResetSwimCollision_Long
  JSL Link_HandleYItems_Long ; $39B0E IN ROM
  
  LDA $49 : AND.b #$0F : BNE .movement
  LDA $F0 : AND.b #$0F : BNE .movement
  STA $30 : STA $31 : STA $67 : STA $26
  
  STZ $2E
  
  LDA $48 : AND.b #$F6 : STA $48
  LDX.b #$20 : STX $0371
  
  ; Ledge timer is reset here the same way as for normal link (unbunny).
  LDX.b #$13 : STX $0375
  
  BRA .finish_up

.movement
  
  STA $67 : CMP $26 : BEQ .directions_match
  
  STZ $2A
  STZ $2B
  STZ $6B
  STZ $4B
  
  LDX.b #$20 : STX $0371
  
  ; Ledge timer is reset here the same way as for normal link (unbunny).
  LDX.b #$13 : STX $0375

.directions_match

  STA $26

.finish_up
  JSL Link_HandleDiagonalCollision_Long
  JSL Link_HandleVelocity                      ; $3E245 IN ROM
  JSL Link_HandleCardinalCollision_Long
  JSL Link_HandleMovingAnimation_FullLongEntry ; $3E6A6 IN ROM
  
  STZ $0302
  
  JSL HandleIndoorCameraAndDoors_Long   ; $3E8F0 IN ROM

.exit:

  RTL
}