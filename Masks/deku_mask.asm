; Hooks 
incsrc "../Sprites/sprite_functions_hooks.asm"
; =============================================================================

org $008A01
  LDA $BC

org $07983A
  Player_ResetSwimState:

org $0ED6C0
  LoadActualGearPalettes:

org $07E245 
  Link_HandleVelocity:

org $07915E
  LinkState_ExitingDash:

org $07E6A6
  Link_HandleMovingAnimation_FullLongEntry:

org $01FF28
  Player_CacheStatePriorToHandler:
  
; =============================================================================

org $07B64F
  Link_HandleDiagonalCollision:

; start of free space in bank07 
org $07F89D
Link_HandleDiagonalCollision_Long:
{
  PHB : PHK : PLB
  JSR Link_HandleDiagonalCollision
  PLB
  RTL
}

; =============================================================================

org $07B7C7
  Link_HandleCardinalCollision:

org $07F8A6
Link_HandleCardinalCollision_Long:
{
  PHB : PHK : PLB
  JSR Link_HandleCardinalCollision
  PLB
  RTL
}

; =============================================================================

org $07E8F0
  HandleIndoorCameraAndDoors:

org $07F8AE
HandleIndoorCameraAndDoors_Long:
{
  PHB : PHK : PLB
  JSR HandleIndoorCameraAndDoors
  PLB
  RTL
}

; =============================================================================

org $07F514
  CheckIndoorStatus:

org $07F8B7
CheckIndoorStatus_Long:
{
  PHB : PHK : PLB
  JSR CheckIndoorStatus
  PLB
  RTL
}

; =============================================================================

org $079873
  Player_ResetSwimCollision:

org $07F8C0
Player_ResetSwimCollision_Long:
{
  PHB : PHK : PLB
  JSR Player_ResetSwimCollision
  PLB
  RTL
}

; =============================================================================

org $079B0E
  Link_HandleYItems:

org $07F8C9
Link_HandleYItems_Long:
{
  PHB : PHK : PLB
  JSR Link_HandleYItems
  PLB
  RTL
}

print pc 

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
  BRA .return

.unequip
  JSL Palette_ArmorAndGloves
  STZ $5D
  LDA #$10 : STA $BC : STZ $02B2        ; take the mask off

.return
  RTS
}

; =============================================================================

; LinkItem_UsingQuake is 152 (base10) bytes long 
org $07A6D6
LinkItem_UsingQuake: 
{
  JSL LinkItem_UsingDekuMask
  NOP #152
  ; 07A6DB
  print pc 
}
; end of UsingQuake is at 07A773

; =============================================================================

org $288000
;incsrc "link_handler.asm"
LinkItem_UsingDekuMask:
{
  SEP #$20
  JSL CheckIndoorStatus_Long
  
  LDA $0345 : BNE .recache
  LDA $4D : BEQ .recoiling
  LDA $7EF357 : BEQ .recache
  
  STZ $02E0

; *$383C7 LONG BRANCH LOCATION LinkState_Bunny_recache
.recache

  STZ $03F7
  STZ $03F5
  STZ $03F6
  
  LDA $7EF357 : BEQ .no_pearl_a
  
  STZ $56
  STZ $4D

.no_pearl_a

  STZ $2E
  STZ $02E1
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
  BRL $0783A1 ; Permabunny mode.

.wait_maybe_not_recoiling

  LDA.b #$FF : STA $24 : STA $25 : STA $29
  STZ $02C6
  
  LDA $034A : BEQ .not_moving
  
  LDA.b #$01 : STA $0335 : STA $0337
  LDA.b #$80 : STA $0334 : STA $0336
  
  BRL $9715

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

; =============================================================================

org $358000
incbin gfx/deku_link.bin

; =============================================================================

org $1BEDF9
JSL Palette_ArmorAndGloves ; 4bytes
RTL ; 1byte 
NOP #$01

org $1BEE1B
JSL Palette_ArmorAndGloves_part_two
RTL

; =============================================================================

; Code : 
org $308000
Palette_ArmorAndGloves:
{
  LDA.b #$10 
  STA $BC         ; Load Original Sprite Location
  REP #$21
  LDA $7EF35B
  JSL $1BEDFF     ; Read Original Palette Code
  RTL
.part_two
  SEP #$30
      REP #$30
      LDA $7EF354
      JSL $1BEE21 ; Read Original Palette Code
  RTL

  PHX : PHY : PHA
  ; Load armor palette
  PHB : PHK : PLB

  REP #$20
  
  ; Check what Link's armor value is.
  LDA $7EF35B : AND.w #$00FF : TAX
  
  LDA $1BEC06, X : AND.w #$00FF : ASL A : ADC.w #$F000 : STA $00
  REP #$10
  
  LDA.w #$01E2 ; Target SP-7 (sprite palette 6)
  LDX.w #$000E ; Palette has 15 colors
  
  TXY : TAX
  
  LDA.b $BC : AND #$00FF : STA $02

.loop

  LDA [$00] : STA $7EC300, X : STA $7EC500, X
  
  INC $00 : INC $00
  
  INX #2
  
  DEY : BPL .loop

  SEP #$30
  
  
  PLB
  INC $15
  PLA : PLY : PLX
  RTL
}

; org $07A666
; Deku_Entry:
; {
;     LDA.b #$20 : STA $BC
    ; STA $7EC178
    ; JSL Palette_ArmorAndGloves
    ; STZ $0710
;     RTS
; }

; org $06F40C
; JSL change_sprite : NOP #$01 ; LDA $0E20, X : CMP.b #$61
