; =========================================================
; Macros

macro PlayerTransform()
  LDY.b #$04 : LDA.b #$23
  JSL   AddTransformationCloud
  LDA.b #$14 
  STA.w $0CF8
  JSL $0DBB67 ; Link_CalculateSFXPan
  ORA.w $0CF8
  STA $012E
endmacro

macro ResetToLinkGraphics()
  STZ   !CurrentMask
  JSL   Palette_ArmorAndGloves
  LDA.b #$10 : STA !LinkGraphics
endmacro

macro CheckNewR_ButtonPress()
  LDA.b $F6 : BIT.b #$10
endmacro

; =========================================================
; Change Link's sprite by setting $BC to the bank with the gfx

; InitializeMemoryAndSRAM
org $008827
  JSL StartupMasks

; Link Sprite hook before game starts
org $008A01
  LDA $BC

; =========================================================
; Change Link's palette based on $02B2 (mask value)

; Palettes_Load_LinkArmorAndGloves
org $1BEDF9
  JSL Palette_ArmorAndGloves ; 4bytes
  RTL                        ; 1byte
  NOP #$01

; Palettes_Load_LinkGloves
org $1BEE1B
  JSL Palette_ArmorAndGloves_part_two
  RTL

; =========================================================

; GameOver_DelayBeforeIris
org $09F347
  JSL ForceResetMask_GameOver

; Module17_SaveAndQuit
org $09F7B5
  JSL ForceResetMask_SaveAndQuit

; =========================================================
; EXPANDED SPACE

org $3A8000
StartupMasks:
{
  ; from vanilla:
  ; bring the screen into force blank after NMI
  LDA.b #$80 : STA $13

  ; set links sprite bank
  LDA #$10 : STA $BC

  RTL
}

ForceResetMask_GameOver:
{
  LDA $02B2 : BEQ .still_link
    CMP.b #$06 : BEQ .gbc_link
      %ResetToLinkGraphics()
      JMP .still_link
    .gbc_link
    JSL UpdateGbcPalette
    LDA #$3B : STA $BC   ; change link's sprite 

  .still_link
  LDA.b #$30
  STA.b $98
  RTL
}

ForceResetMask_SaveAndQuit:
{
  LDA $02B2 : BEQ .still_link
  %ResetToLinkGraphics()
  .still_link
  LDA.b #$0F
  STA.b $95
  RTL
}

; =========================================================

Palette_ArmorAndGloves:
{
  LDA   $02B2 : CMP #$01 : BEQ .deku_mask
  CMP.b #$02 : BEQ .zora_mask
  CMP.b #$03 : BEQ .wolf_mask
  CMP.b #$04 : BEQ .bunny_hood
  CMP.b #$05 : BEQ .minish_form
  CMP.b #$06 : BEQ .gbc_form
  JMP   .original_sprite

  .deku_mask
    ; Load Deku Mask Location
    LDA.b #$35 : STA $BC 
    JSL UpdateDekuPalette
    RTL

  .zora_mask
    ; Load Zora Mask Location
    LDA.b #$36 : STA $BC
    JSL UpdateZoraPalette
    RTL

  .wolf_mask
    ; Load Wolf Mask Location
    LDA.b #$38 : STA $BC 
    JSL $38F000
    RTL

  .bunny_hood
    ; Load Bunny Hood Location
    LDA.b #$37 : STA $BC 
    JSL $37F000
    RTL

  .minish_form
    ; Load Minish Form Location
    LDA.b #$39 : STA $BC : JMP .original_palette

  .gbc_form
    ; Load GBC Link Location
    LDA.b #$3B : STA $BC 
    JSL UpdateGbcPalette
    RTL

  .original_sprite
  ; Load Original Sprite Location
  LDA.b #$10 : STA $BC

  .original_palette
  REP #$21
  LDA $7EF35B ; Link's armor value
  JSL $1BEDFF ; Read Original Palette Code
  RTL

  .part_two
  SEP #$30
    REP   #$30
    LDA.w #$0000  ; Ignore glove color modifier $7EF354
    JSL   $1BEE21 ; Read Original Palette Code
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

; =========================================================
; Overworld Palette Persist


Overworld_CgramAuxToMain_Override:
{
  ; Copies the auxiliary CGRAM buffer to the main one
  ; Causes NMI to reupload the palette.

  REP #$20

  LDX.b #$00

  .loop
  LDA $7EC300, X : STA $7EC500, X
  LDA $7EC340, X : STA $7EC540, X
  LDA $7EC380, X : STA $7EC580, X
  LDA $7EC3C0, X : STA $7EC5C0, X
  LDA $7EC400, X : STA $7EC600, X
  LDA $7EC440, X : STA $7EC640, X
  LDA $7EC480, X : STA $7EC680, X
  LDA $02B2 : BNE .has_mask_palette
    LDA $7EC4C0, X : STA $7EC6C0, X
  .has_mask_palette
  INX #2 : CPX.b #$40 : BNE .loop

  SEP #$20

  ; tell NMI to upload new CGRAM data
  INC $15

  RTL
}

; =========================================================

LinkState_ResetMaskAnimated:
{
  LDA.w $02B2 : BEQ .no_transform
  CMP.b #$01 : BEQ .check_item_slot
  CMP.b #$02 : BEQ .no_transform
  CMP.b #$03 : BEQ .check_item_slot
  CMP.b #$04 : BEQ .check_item_slot
  CMP.b #$05 : BEQ .no_transform
  CMP.b #$06 : BEQ .gbc_form
  
  .check_item_slot
  LDA.w $0202 : SEC : SBC.b #$13 : BEQ .no_transform

  .transform
  %PlayerTransform()
  %ResetToLinkGraphics()

  .gbc_form
  .no_transform
  RTL
}

pushpc

; =========================================================

org $02C769
Overworld_CgramAuxToMain:
  JSL Overworld_CgramAuxToMain_Override
  RTS

; =========================================================
; Change which mask forms have access to the sword.
; =========================================================

; Link_CheckForSwordSwing
org $079CD9
  JSL LinkItem_CheckForSwordSwing_Masks

pullpc
LinkItem_CheckForSwordSwing_Masks:
{
  LDA   $02B2 : BEQ .return 
    CMP.b #$02 : BEQ .return  ; zora mask can use sword
      CMP.b #$06 : BEQ .return ; gbc link can use sword
        LDA #$01
        RTL

  .return
  LDA $3B : AND.b #$10 ; Restore Link_CheckForSwordSwing
  RTL
}

; =========================================================
; Common Mask Transformation Routine
; A = Mask ID
; Carry clear = no transform press/cant use mask

Link_TransformMask:
{
  PHB : PHK : PLB
  PHA ; save mask ID
  %CheckNewR_ButtonPress() : BEQ .return
    LDA $6C : BNE .return   ; in a doorway
    LDA $0FFC : BNE .return ; can't open menu

    %PlayerTransform()
    PLA ; restore mask ID
    TAY
    ; LDA $02B2 
    CPY !CurrentMask : BEQ .unequip ; check if mask is on
      
      STA $02B2 : TAX
      LDA .mask_gfx, X : STA $BC ; set the mask gfx
      JSL Palette_ArmorAndGloves ; set the palette
      STA $02F5                  ; Somaria platform flag, no dash
      PLB : CLC : RTL

    .unequip
    STZ $5D
    STZ $02F5

    %ResetToLinkGraphics()
    PLB : CLC : RTL

  .return
  PLA : PLB : CLC : RTL

  .mask_gfx
    db $00, $35, $36, $38, $37, $39, $3A, $3B
}

; =========================================================

; Modifies the value of the Y register before it indexes the table
; LinkOAM_AnimationStepDataOffsets
; This is used to change the animation during 0x0A (Using Quake Medallion)
DekuLink_SpinOrRecoil:
{
  TAY
  LDA $70 : BEQ .spin
    TYA
    LDY.b #$05 ; Recoil
    JML $0DA435 ; JML $0DA40B
  .spin
  TYA
  LDY.b #$1B ; Spin and die 
  JML $0DA40B
}

pushpc
; Spin and die, LinkOAM_AnimationStepDataOffsets
org $0DA3FD
  JML DekuLink_SpinOrRecoil
pullpc

PrepareMagicBubble:
{
  #_07A049: LDA.b LinkY
  #_07A04B: STA.b $72

  #_07A04D: LDA.b LinkYH
  #_07A04F: STA.b $73

  #_07A051: LDA.b LinkX
  #_07A053: STA.b $74

  #_07A055: LDA.b LinkXH
  #_07A057: STA.b $75

  #_07A059: LDX.b LinkFaceDir

  #_07A05B: LDY.b #$02
  #_07A05D: LDA.b #$09 ; ANCILLA 09
  #_07A05F: JSL $0990A4 ; AncillaAdd_Arrow
  RTL
}

; Based on LinkItem_Quake.allow_quake
PrepareQuakeSpell:
{
  LDA.b #$0A : STA.b $5D ; Set Link to the hover state
  LDA.b #$00 : STA.b $3D ; Clear the animation timer 

  LDA #$00 : STA.w $031C ; Clear the spin animation gfx 
  STZ.w $031D ; Clear the spin animation step
  STZ.w $0324 ; Prevent multiple ancillae from being added
  STZ.b $46 ; Clear the link damage timer 

  ; Set low and high of HOPVZ2
  ; Usually used as the hopping speed for diagonal jumps
  LDA.b #$28 : STA.w $0362 : STA.w $0363 
  STZ.w $0364 ; Clear Z-coordinate for the jump

  STZ $70 ; Clear bomb drop check flag 

  RTL
}

; =========================================================

InitCamera:
{
  LDA.b $22 : STA.b $3F
  LDA.b $23 : STA.b $41
  LDA.b LinkY : STA.b $3E
  LDA.b LinkYH : STA.b $40
  RTS
}

; =========================================================

HandleMovement:
{
  LDA $F0 : AND #$08 : BEQ .not_up
    LDY #$00 
    LDA.w .drag_y_low,  Y : CLC : ADC.w $0B7E : STA.w $0B7E
    LDA.w .drag_y_high, Y : ADC.w $0B7F : STA.w $0B7F
    LDA #$01 : STA $031C
    LDA #$05 : STA $3D
    STZ.w LinkFaceDir
    
  .not_up
  LDA $F0 : AND #$04 : BEQ .not_down
    LDY #$01
    LDA.w .drag_y_low,  Y : CLC : ADC.w $0B7E : STA.w $0B7E
    LDA.w .drag_y_high, Y : ADC.w $0B7F : STA.w $0B7F
    LDA #$02 : STA $031C
    LDA #$05 : STA $3D
    LDA #$02 : STA LinkFaceDir
    
  .not_down
  LDA $F0 : AND #$02 : BEQ .not_left
    LDY #$02
    LDA.w .drag_x_low,  Y : CLC : ADC.w DragYL : STA.w DragYL
    LDA.w .drag_x_high, Y : ADC.w DragYH : STA DragYH
    LDA #$03 : STA $031C
    LDA #$05 : STA $3D
    LDA #$04 : STA LinkFaceDir
    
  .not_left
  LDA $F0 : AND #$01 : BEQ .not_right
    LDY #$03
    LDA.w .drag_x_low,  Y : CLC : ADC.w DragYL : STA.w DragYL
    LDA.w .drag_x_high, Y : ADC.w DragYH : STA DragYH
    LDA #$04 : STA $031C
    LDA #$05 : STA $3D
    LDA #$06 : STA LinkFaceDir
    
  .not_right
  RTS

  .drag_x_high
    db 0,   0,  -1,   0

  .drag_x_low
    db 0,   0,  -1,   1

  .drag_y_low
    db -1,   1,   0,   0

  .drag_y_high
    db -1,   0,   0,   0
}

; =========================================================

DekuLink_HoverBasedOnInput:
{
  PHB : PHK : PLB

  #_0782A7: STZ.b $2A
  #_0782A9: STZ.b $2B
  #_0782AB: STZ.b $6B
  #_0782AD: STZ.b $48

  JSR HandleMovement
  
  JSL Link_HandleCardinalCollision_Long
  JSL Link_HandleVelocityAndSandDrag
  JSL Link_HandleMovingAnimation_FullLongEntry

  STZ.w $0302

  JSL HandleIndoorCameraAndDoors
  
  JSL Link_CancelDash
  
  ; Pos - Cache Pos = difference
  LDA LinkX : SEC : SBC $3F : STA $31
  LDA LinkY : SEC : SBC $3E : STA $30

  LDA $5C : AND #$1F : BNE .continue_me
    DEC $24
  .continue_me
  
  LDA $5C : BEQ .auto_cancel

  LDA $70 : BEQ .no_bomb_drop
    LDA $F0 : AND #%01000000 : BEQ .no_bomb_drop
      LDY.b #$01 : LDA.b #$07 ; ANCILLA 07
      JSL $09811F ; AncillaAdd_Bomb
  .no_bomb_drop

  LDA $F0 : AND #%10000000 : BEQ .no_cancel
    .auto_cancel
    
    ; Reset LinkState to Default
    STZ $5D

    LDA.b #$01 : STA.w $0AAA
    STZ.w $0324 : STZ.w $031C : STZ.w $031D
    STZ.b $50 : STZ.b $3D
    STZ.w $0FC1
    STZ.w $011A : STZ.w $011B : STZ.w $011C : STZ.w $011D

    LDY.b #$00

    LDA.b $3C : BEQ .no_sword_charge
      LDA.b $F0 : AND.b #$80 : TAY
    .no_sword_charge

    STY.b $3A
    STZ.b $5E
    ; Set height at end of hover
    ; This makes it so the landing animation timer looks correct
    ; Floating for a bit, then slowly landing on the ground
    LDA.b #$12 : STA $24 
  .no_cancel

  PLB
  RTL

Ancilla_SFX2_Near:
  JSR Ancilla_SFX_Near
  STA.w $012E
  RTS

Ancilla_SFX_Near:
  STA.w $0CF8
  JSL Link_CalculateSFXPan
  ORA.w $0CF8
  RTS

Ancilla_SFX2_Pan:
  JSR Ancilla_SFX_SetPan
  STA.w $012E
  RTS

Ancilla_SFX_SetPan:
  STA.w $0CF8
  JSL Ancilla_CalculateSFXPan
  ORA.w $0CF8
  RTS

Ancilla_CheckBasicSpriteCollision:
{
  LDY.b #$0F

  .next_sprite
  TYA
  EOR.b $1A
  AND.b #$03

  ORA.w $0F00,Y
  ORA.w $0EF0,Y
  BNE .skip

  LDA.w $0DD0,Y
  CMP.b #$09
  BCC .skip

  LDA.w $0CAA,Y
  AND.b #$02
  BNE .sprite_ignores_priority

  LDA.w $0280,X
  BNE .skip

  .sprite_ignores_priority
  LDA.w $0C7C,X
  CMP.w $0F20,Y
  BNE .skip

  LDA.w $0C4A,X
  CMP.b #$2C ; ANCILLA 2C
  BNE .not_somaria_block

  LDA.w $0E20,Y
  CMP.b #$1E ; SPRITE 1E
  BEQ .skip

  CMP.b #$90 ; SPRITE 90
  BEQ .skip

  .not_somaria_block
  JSR Ancilla_CheckBasicSpriteCollision_Single

  .skip
  DEY
  BPL .next_sprite

  CLC

  RTS
}

; =========================================================

Ancilla_CheckBasicSpriteCollision_Single:
{
  JSR Ancilla_SetupBasicHitBox

  PHY
  PHX

  TYX
  JSL Sprite_SetupHitBoxLong

  PLX
  PLY

  JSL CheckIfHitBoxesOverlap
  BCC .fail

  LDA.w $0E20,Y
  CMP.b #$92 ; SPRITE 92
  BNE .not_king_helma

  LDA.w $0DB0,Y
  CMP.b #$03
  BCC .success

  .not_king_helma
  LDA.w $0E20,Y
  CMP.b #$80 ; SPRITE 80
  BNE .dont_reverse_fire_snake

  LDA.w $0F10,Y
  BNE .dont_reverse_fire_snake

  LDA.b #$18
  STA.w $0F10,Y

  LDA.w $0DE0,Y
  EOR.b #$01
  STA.w $0DE0,Y

  .dont_reverse_fire_snake
  LDA.w $0BA0,Y
  BNE .fail

  LDA.w $0C04,X
  SEC
  SBC.b #$08
  STA.b $04

  LDA.w $0C18,X
  SBC.b #$00
  STA.b $05

  LDA.w $0BFA,X
  SEC
  SBC.b #$08
  PHP

  SEC
  SBC.w $029E,X
  STA.b $06

  LDA.w $0C0E,X
  SBC.b #$00

  PLP
  SBC.b #$00
  STA.b $07

  LDA.b #$50

  PHY
  PHX

  TYX
  JSL Sprite_ProjectSpeedTowardsEntityLong

  PLX
  PLY

  LDA.b $00
  EOR.b #$FF
  STA.w $0F30,Y

  LDA.b $01
  EOR.b #$FF
  STA.w $0F40,Y

  PHX

  LDA.w $0C4A,X

  TYX
  JSL Ancilla_CheckDamageToSprite

  PLX

  .success
  PLA
  PLA

  SEC

  RTS

  .fail
  CLC

  RTS
}

Ancilla_SetupBasicHitBox:
{
  LDA.w $0C04,X
  SEC
  SBC.b #$08
  STA.b $00

  LDA.w $0C18,X
  SBC.b #$00
  STA.b $08

  LDA.w $0BFA,X
  SEC
  SBC.b #$08
  PHP

  SEC
  SBC.w $029E,X
  STA.b $01

  LDA.w $0C0E,X
  SBC.b #$00

  PLP
  SBC.b #$00
  STA.b $09

  LDA.b #$0F
  STA.b $02

  LDA.b #$0F
  STA.b $03

  RTS
}

Ancilla_Move_X:
{
  TXA
  CLC
  ADC.b #$0A
  TAX

  JSR Ancilla_Move_Y

  BRL Ancilla_RestoreIndex
}

; ---------------------------------------------------------

Ancilla_Move_Y:
{
  LDA.w $0C22,X

  ASL A
  ASL A
  ASL A
  ASL A

  CLC
  ADC.w $0C36,X
  STA.w $0C36,X

  LDY.b #$00

  LDA.w $0C22,X
  PHP

  LSR A
  LSR A
  LSR A
  LSR A

  PLP
  BPL .other_way

  ORA.b #$F0
  DEY

  .other_way
  ADC.w $0BFA,X
  STA.w $0BFA,X

  TYA
  ADC.w $0C0E,X
  STA.w $0C0E,X

  RTS
}

; =========================================================

Ancilla_Move_Z:
{
  LDA.w $0294,X

  ASL A
  ASL A
  ASL A
  ASL A

  CLC
  ADC.w $02A8,X
  STA.w $02A8,X

  LDY.b #$00

  LDA.w $0294,X
  PHP

  LSR A
  LSR A
  LSR A
  LSR A

  PLP
  BPL .other_way

  ORA.b #$F0
  DEY

  .other_way
  ADC.w $029E,X
  STA.w $029E,X

  RTS
}


Ancilla_Killa:
  PLA
  PLA

  STZ.w $0C4A,X

  RTS

Ancilla_BoundsCheck:
{
  LDY.w $0C7C,X

  LDA.w .data,Y
  STA.b $04

  LDY.w $0C86,X

  LDA.w $0C04,X
  SEC
  SBC.b $E2
  CMP.b #$F4
  BCS Ancilla_Killa

  STA.b $00

  LDA.w $0BFA,X
  SEC
  SBC.b $E8
  CMP.b #$F0
  BCS Ancilla_Killa

  STA.b $01

  RTS
  .data
    db $20, $10
}

pushpc

LinkOAM_SetEquipmentVRAMOffsets = $0DABE6
LinkOAM_DrawShadow = $0DA857


org $0DA780
LinkOAM_DrawShield:
{
  REP #$30
  JSL LinkOAM_CheckForDrawShield

  NOP #3
  BEQ .no_shield

  LDA.l $7EF35A
  AND.w #$00FF
  BEQ .no_shield

  JSR LinkOAM_SetEquipmentVRAMOffsets
  BCC .shield_continue

  .no_shield
  BRL LinkOAM_DrawShadow

  .shield_continue
}
warnpc $0DA79C

; Hide sword while deku hover
org $0DA5EA
  CMP.w #$0009

pullpc

; Minish, Deku, Wolf don't draw shield
LinkOAM_CheckForDrawShield:
{
  LDA.w $02B2 : AND.w #$00FF : CMP.w #$0005 : BNE +
  .no_shield
  LDA.w #$0000
  RTL
  +
  CMP.w #$0001 : BEQ .no_shield
  CMP.w #$0003 : BEQ .no_shield
  .shield
  RTL
}

pushpc

org $07A94F
  JSL CheckForTwoWayMirror

pullpc

CheckForTwoWayMirror:
{
  LDA.l $7EF374 : CMP.b #$07 : BNE .vanilla_code
    LDA.b #$01
    RTL
  .vanilla_code
  #_07A94F: LDA.b $8A
  #_07A951: AND.b #$40
  RTL
}

CheckNewRButtonPress:
{
  LDA $F6 : BIT #$10 : BEQ .fail

  SEC 
  RTL 

  .fail
  CLC
  RTL
}

print "End of mask_routines.asm          ", pc

; LinkOAM_DrawShield _0DA780