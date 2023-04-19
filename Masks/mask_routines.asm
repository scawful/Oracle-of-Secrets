; =============================================================================

; no glove color 
org $0DEE24
 db $80

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

org $09912C
AddTransformationCloud:

org $07B073
Link_CheckNewY_ButtonPress:

org $078028
Player_DoSfx2:


; =============================================================================

org $008827
JSL StartupMasks

org $1BEDF9
JSL Palette_ArmorAndGloves ; 4bytes
RTL ; 1byte 
NOP #$01

org $1BEE1B
JSL Palette_ArmorAndGloves_part_two
RTL

; =============================================================================

org $278000
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

CancelMask:
{
  JSL Palette_ArmorAndGloves
  LDA #$10 : STA $BC : STZ $02B2
  RTL
}

; =============================================================================

; Code : 
org $398000
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