; =============================================================================
; Change Link Sprite with $BC
; =============================================================================

org $09912C
  AddTransformationCloud:

org $07B073
  Link_CheckNewY_ButtonPress:

org $078028
  Player_DoSfx2:

; =============================================================================

; Link Sprite hook
org $008A01
  LDA $BC

org $008827
  JSL StartupMasks

org $1BEDF9
  JSL Palette_ArmorAndGloves ; 4bytes
  RTL ; 1byte 
  NOP #$01

org $1BEE1B
  JSL Palette_ArmorAndGloves_part_two
  RTL

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

; =============================================================================

Palette_ArmorAndGloves:
{
  LDA $02B2 : CMP #$01 : BEQ .deku_mask 
  CMP.b #$02 : BEQ .zora_mask
  CMP.b #$03 : BEQ .wolf_mask
  CMP.b #$04 : BEQ .bunny_hood
  CMP.b #$05 : BEQ .minish_form
  JMP .original_sprite

.deku_mask
  LDA.b #$35 : STA $BC         ; Load Deku Mask Location
  JMP .original_palette
  
.zora_mask
  LDA.b #$36 : STA $BC         ; Load Zora Mask Location
  JMP .original_palette

.wolf_mask
  LDA.b #$38 : STA $BC         ; Load Wolf Mask Location
  JSL $38F000
  RTL

.bunny_hood
  LDA.b #$37 : STA $BC         ; Load Bunny Hood Location
  JSL $37F000
  RTL

.minish_form
  LDA.b #$39 : STA $BC         ; Load Minish Form Location
  JMP .original_palette
  RTL

.original_sprite
  LDA.b #$10 : STA $BC         ; Load Original Sprite Location

.original_palette
  REP #$21
  LDA $7EF35B     ; Link's armor value 
  JSL $1BEDFF     ; Read Original Palette Code
  RTL
.part_two
  SEP #$30
    REP #$30
    LDA.w #$0000 ; Ignore glove color modifier $7EF354
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

; =============================================================================
; Overworld Palette Persist 
Overworld_CgramAuxToMain_Override:
{
  ; copies the auxiliary CGRAM buffer to the main one and causes NMI to reupload the palette.
  
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

; =============================================================================

org $02C769
Overworld_CgramAuxToMain:
{
  JSL Overworld_CgramAuxToMain_Override
  RTS
}

; =============================================================================