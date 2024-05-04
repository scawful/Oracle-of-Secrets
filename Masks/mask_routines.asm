
; =========================================================
; Macros

macro PlayerTransform()
  LDY.b #$04 : LDA.b #$23
  JSL   AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2
endmacro

macro ResetToLinkGraphics()
  STZ   !CurrentMask
  JSL   Palette_ArmorAndGloves
  LDA.b #$10 : STA !LinkGraphics
endmacro

macro CheckNewR_ButtonPress()
  LDA.b $F6 : BIT.b #$10
endmacro

; org $02A560
;   JSL ForceResetWorldMap

; GameOver_DelayBeforeIris
org $09F347
  JSL ForceResetMask_GameOver

; Module17_SaveAndQuit
org $09F7B5
  JSL ForceResetMask_SaveAndQuit

; =========================================================
; Change Link's sprite by setting $BC to the bank containing a spritesheet.
; =========================================================

org $008827
  JSL StartupMasks

; Link Sprite hook before game starts
org $008A01
  LDA $BC

; =========================================================
; Change Link's palette based on $02B2 (mask value)
; =========================================================

org $1BEDF9
  JSL Palette_ArmorAndGloves ; 4bytes
  RTL                        ; 1byte
  NOP #$01

org $1BEE1B
  JSL Palette_ArmorAndGloves_part_two
  RTL

; =========================================================
; EXPANDED SPACE
; =========================================================

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

ForceResetWorldMap:
{
  LDA $7EF280 : BNE .openMap
  PLA : PLA : PLA ; Pop the RTL
  JML $02A571 ; check select button 

  .openMap
  LDA $02B2 : BEQ .still_link
  LDY.b #$04 : LDA.b #$23
  JSL   AddTransformationCloud
  %ResetToLinkGraphics()
  
.still_link
  STZ.w $0200
  LDA #$07
  RTL
}

ForceResetMask_GameOver:
{
  LDA $02B2 : BEQ .still_link
  %ResetToLinkGraphics()
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
  JMP   .original_sprite

.deku_mask
  ; Load Deku Mask Location
  LDA.b #$35 : STA $BC 
  JSL UpdateDekuPalette
  RTL

.zora_mask
  ; Load Zora Mask Location
  LDA.b #$36 : STA $BC : JMP   .original_palette

.wolf_mask
  ; Load Wolf Mask Location
  LDA.b #$38 : STA $BC : JSL   $38F000
  RTL

.bunny_hood
  ; Load Bunny Hood Location
  LDA.b #$37 : STA $BC : JSL   $37F000
  RTL

.minish_form
  ; Load Minish Form Location
  LDA.b #$39 : STA $BC : JMP   .original_palette
  ; RTL

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
; =========================================================

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
pushpc

; =========================================================

org $02C769
Overworld_CgramAuxToMain:
{
  JSL Overworld_CgramAuxToMain_Override
  RTS
}

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
  CMP.b #$06 : BEQ .return 

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
    CPY !CurrentMask : BEQ .unequip ; is the deku mask on?
      
      STA $02B2 ; set the mask ID
      TAX ; save mask ID in X
      LDA .mask_gfx, X : STA $BC    ; put the mask on
      JSL Palette_ArmorAndGloves ; set the palette
      
      STA $02F5             ; Somaria platform flag, no dash.

      PLB
      SEC 
      RTL

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
  JML $0DA435 ;JML $0DA40B
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

; Based on LinkItem_Quake.allow_quake
PrepareQuakeSpell:
{
  ; Ancilla setup stuff, not necessary
  ; #_07A680: LDA.w $0C4A
  ; #_07A683: ORA.w $0C4B
  ; #_07A686: ORA.w $0C4C

  ; This would set link to strafe mode
  ; Probably not necessary
  ; #_07A696: LDA.b #$01
  ; #_07A698: TSB.b $50

  ; TODO: Set a check for the Deku Flower sprite before activating this ability.

  LDA.b #$0A : STA $5D

  #_07A69A: LDA #$00
  #_07A69D: STA.b $3D

  #_07A69F: LDA #$00
  #_07A6A2: STA.w $031C
  #_07A6A5: STZ.w $031D

  #_07A6A8: STZ.w $0324

  #_07A6AB: STZ.b $46

  ; Set the spin and jump animation values.
  #_07A6AD: LDA.b #$28
  #_07A6AF: STA.w $0362
  #_07A6B2: STA.w $0363
  #_07A6B5: STZ.w $0364

  STZ $70
  
  RTL
}

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


  LDA $70 : BEQ .no_bomb_drop
  LDA $F0 : AND #%01000000 : BEQ .no_bomb_drop

  #_07A14F: LDY.b #$01
  #_07A151: LDA.b #$07 ; ANCILLA 07
  #_07A153: JSL $09811F ; AncillaAdd_Bomb

.no_bomb_drop

  LDA $F0 : AND #%10000000 : BEQ .no_cancel

.auto_cancel
  
  ; Reset LinkState to Default
  STZ $5D

  #_08B6A5: LDA.b #$01
  #_08B6A7: STA.w $0AAA

  #_08B6AA: STZ.w $0324
  #_08B6AD: STZ.w $031C
  #_08B6B0: STZ.w $031D

  #_08B6B3: STZ.b $50
  #_08B6B5: STZ.b $3D

  #_08B6B7: STZ.w $0FC1

  #_08B6BA: STZ.w $011A
  #_08B6BD: STZ.w $011B
  #_08B6C0: STZ.w $011C
  #_08B6C3: STZ.w $011D

.no_turtle_rock_trigger
  #_08B6E4: LDY.b #$00

  #_08B6E6: LDA.b $3C
  #_08B6E8: BEQ .no_sword_charge

  #_08B6EA: LDA.b $F0
  #_08B6EC: AND.b #$80
  #_08B6EE: TAY

.no_sword_charge
  #_08B6EF: STY.b $3A

  #_08B6F1: STZ.b $5E
  #_08B6F3: STZ.w $0325
  ; Set height at end of hover
  ; This makes it so the landing animation timer looks correct
  ; Floating for a bit, then slowly landing on the ground
  LDA.b #$12 : STA $24 
.no_cancel

  RTL
}

print "End of mask_routines.asm          ", pc
