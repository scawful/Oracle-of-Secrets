; =============================================================================
;  Oracle of Secrets - Mask Library
; =============================================================================

!CurrentMask  = $02B2
!LinkGraphics = $BC

; =============================================================================

org $09912C
  AddTransformationCloud:

org $07B073
  Link_CheckNewY_ButtonPress:

org $078028
  Player_DoSfx2:

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

org $02A560
  JSL ForceResetWorldMap : NOP

; GameOver_DelayBeforeIris
org $09F347
  JSL ForceResetMask_GameOver

; Module17_SaveAndQuit
org $09F7B5
  JSL ForceResetMask_SaveAndQuit

; =============================================================================
; Change Link's sprite by setting $BC to the bank containing a spritesheet.
; =============================================================================

org $008827
  JSL StartupMasks

; Link Sprite hook before game starts
org $008A01
  LDA $BC

; =============================================================================
; Change Link's palette based on $02B2 (mask value)
; =============================================================================

org $1BEDF9
  JSL Palette_ArmorAndGloves ; 4bytes
  RTL                        ; 1byte
  NOP #$01

org $1BEE1B
  JSL Palette_ArmorAndGloves_part_two
  RTL

; =============================================================================
; EXPANDED SPACE
; =============================================================================

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

; =============================================================================

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
  LDA.b #$35 : STA $BC : JMP   .original_palette

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

; =============================================================================
; Overworld Palette Persist
; =============================================================================

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

; =============================================================================

org $02C769
Overworld_CgramAuxToMain:
{
  JSL Overworld_CgramAuxToMain_Override
  RTS
}

; =============================================================================
; Change which mask forms have access to the sword.
; =============================================================================

org $079CD9
  JSL LinkItem_CheckForSwordSwing_Masks

; =============================================================================

pullpc
LinkItem_CheckForSwordSwing_Masks:
{
  LDA   $02B2 : BEQ .return
  CMP.b #$02 : BEQ .return  ; zora mask can use sword
  CMP.b #$06 : BEQ .return 

  LDA #$01
  RTL

.return
  LDA $3B : AND.b #$10
  RTL
}

; =============================================================================
