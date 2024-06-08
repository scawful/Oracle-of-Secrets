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

org $1BEDF9
  JSL Palette_ArmorAndGloves ; 4bytes
  RTL                        ; 1byte
  NOP #$01

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
  LDA.w $02B2
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

CheckDekuFlowerPresence:
{
  REP #$20
    PHX
    CLC        ; Assume sprite ID $B0 is not present
    LDX.b #$10
  .x_loop
    DEX
    
    LDY.b #$04
    .y_loop
      DEY
      LDA.w $0E20, X : AND.w #$00FF : CMP.w #$00C0 : BEQ .set_flag
      BRA .not_b0

    .set_flag
      SEC         ; Set flag indicating sprite ID $B0 is present
      STX.w $02
      BRA   .done

  .not_b0
    CPY.b #$00 : BNE .y_loop
    CPX.b #$00 : BNE .x_loop
  .done
    PLX
    SEP #$20
    RTS
}

; Based on LinkItem_Quake.allow_quake
PrepareQuakeSpell:
{
  ; Find out if the sprite $C0 is in the room
  JSR CheckDekuFlowerPresence : BCC .no_c0

    PHX : LDA $02 : TAX
    JSL Link_SetupHitBox

    ; X is now the ID of the sprite $B0
    JSL Sprite_SetupHitBox
    PLX
    
    JSL CheckIfHitBoxesOverlap : BCC .no_c0

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
  .no_c0
  RTL
}

; =========================================================

HandleCamera:
{
  LDA $22 : SEC : SBC $3F : STA $31
  LDA $20 : SEC : SBC $3E : STA $30
  PHX 
  
  JSL $07E6A6 ; Link_HandleMovingAnimation_FullLongEntry
  JSL $07F42F ; HandleIndoorCameraAndDoors_Long
  
  JSL Player_HaltDashAttack
  PLX 
  RTS
}

; =========================================================

HandleMovement:
{
  ; TODO: Check for collision here and prevent movement

  LDA $F0 : AND #$08 : BEQ .not_up
    LDA $20 : CLC : ADC #-1 : STA $20
    LDY #$00 : JSL DragPlayer
    LDA #$01 : STA $031C
    LDA #$05 : STA $3D
    STZ $2F
    ; TODO: Handle overworld scroll camera gracefully
    ; DEC.b $E8
    ; DEC.w $0618 : DEC.w $0618 
    ; DEC.w $061A : DEC.w $061A
  .not_up
  LDA $F0 : AND #$04 : BEQ .not_down
    LDA $20 : CLC : ADC #1 : STA $20
    LDY #$01 : JSL DragPlayer
    LDA #$02 : STA $031C
    LDA #$05 : STA $3D
    LDA #$02 : STA $2F
    ; INC.b $E8
    ; DEC.w $0618 : DEC.w $0618 
    ; DEC.w $061A : DEC.w $061A
  .not_down
  LDA $F0 : AND #$02 : BEQ .not_left
    LDA $22 : CLC : ADC #-1 : STA $22
    LDY #$02 : JSL DragPlayer
    LDA #$03 : STA $031C
    LDA #$05 : STA $3D
    LDA #$04 : STA $2F
    ; DEC.b $E2
  .not_left
  LDA $F0 : AND #$01 : BEQ .not_right
    LDA $22 : CLC : ADC #1 : STA $22
    LDY #$03 : JSL DragPlayer
    LDA #$04 : STA $031C
    LDA #$05 : STA $3D
    LDA #$06 : STA $2F
    ; INC.b $E2
  .not_right
  RTS
}

; =========================================================

DekuLink_HoverBasedOnInput:
{
  JSR HandleCamera

  LDA $5C : AND #$1F : BNE .continue_me
    DEC $24
  .continue_me
  
  LDA $5C : BEQ .auto_cancel

  JSR HandleMovement

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

    .no_turtle_rock_trigger
    LDY.b #$00

    LDA.b $3C : BEQ .no_sword_charge
      LDA.b $F0 : AND.b #$80 : TAY
    .no_sword_charge

    STY.b $3A
    STZ.b $5E : STZ.w $0325
    ; Set height at end of hover
    ; This makes it so the landing animation timer looks correct
    ; Floating for a bit, then slowly landing on the ground
    LDA.b #$12 : STA $24 
  .no_cancel

  RTL
}

print "End of mask_routines.asm          ", pc

; LinkOAM_DrawShield _0DA780