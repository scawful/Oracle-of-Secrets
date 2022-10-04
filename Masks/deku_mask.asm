; ; Hooks : 
incsrc "../Sprites/sprite_functions_hooks.asm"

; org $07A666
; Deku_Entry:
; {
;     LDA.b #$20 : STA $BC
;     STA $7EC178
;     JSL Palette_ArmorAndGloves
;     STZ $0710
;     RTS
; }

org $008A01
  LDA $BC

; org $1BEDF9
; JSL Palette_ArmorAndGloves ; 4bytes
; RTL ; 1byte 
; NOP #$01

; org $1BEE1B
; JSL Palette_ArmorAndGloves_part_two
; RTL

; org $06F40C
; JSL change_sprite : NOP #$01 ; LDA $0E20, X : CMP.b #$61

; ; ; Code : 
; org $308000
; Palette_ArmorAndGloves:
; {
;   LDA.b #$10 
;   STA $BC         ; Load Original Sprite Location
;   REP #$21
;   LDA $7EF35B
;   JSL $1BEDFF     ; Read Original Palette Code
;   RTL
;   .part_two
;   SEP #$30
;       REP #$30
;       LDA $7EF354
;       JSL $1BEE21 ; Read Original Palette Code
;   RTL

;   PHX : PHY : PHA
;   ; Load armor palette
;   PHB : PHK : PLB

;   REP #$20
  
;   ; Check what Link's armor value is.
;   LDA $7EF35B : AND.w #$00FF : TAX
  
;   LDA $1BEC06, X : AND.w #$00FF : ASL A : ADC.w #$F000 : STA $00
;   REP #$10
  
;   LDA.w #$01E2 ; Target SP-7 (sprite palette 6)
;   LDX.w #$000E ; Palette has 15 colors
  
;   TXY : TAX
  
;   LDA.b $BC : AND #$00FF : STA $02

; .loop

;   LDA [$00] : STA $7EC300, X : STA $7EC500, X
  
;   INC $00 : INC $00
  
;   INX #2
  
;   DEY : BPL .loop

;   SEP #$30
  
  
;   PLB
;   INC $15
;   PLA : PLY : PLX
;   RTL
; }

; change_sprite:
; {
;     JSL GetRandomInt : AND #$1F : !ADD #$60 : STA $BC
;     STA $7EC178
;     JSL Palette_ArmorAndGloves
;     STZ $0710

;     LDA $0E20, X : CMP.b #$61 ; Restored Code Bank06.asm(5967) ; LDA $0E20, X : CMP.b #$61 : BNE .not_beamos_laser

;     RTL
; }

; changing the DP address $BC would now* change the bank link's gfx is read from 

; =============================================================================

org $07B073    ; *$3B073-$3B086 LOCAL
Link_CheckNewY_ButtonPress:

org $07A64B
LinkItem_Quake:
  JSR Link_CheckNewY_ButtonPress : BCC .return

  LDA $6C : BNE .return ; doorway

  LDA $0FFC : BNE .return ; cantopen menu

  LDA #$40 : STA $BC

  .return
RTS

org $408000
incbin deku_link.bin