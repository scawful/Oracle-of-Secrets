; =============================================================================
; Zora Mask
; Fairy Flippers RAM Position $7EF33C - 01

; Normal Flippers RAM Position $7ef356 - 01

; =============================================================================

org $07A569
LinkItem_ZoraMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A        ; clear the Y button state 

  LDA $6C : BNE .return                 ; in a doorway
  LDA $0FFC : BNE .return               ; can't open menu

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP #$02 : BEQ .unequip   ; is the zora mask on?
  JSL UpdateZoraPalette
  LDA #$36 : STA $BC
  LDA #$02 : STA $02B2
  BRA .return
.unequip
  JSL Palette_ArmorAndGloves
  LDA #$10 : STA $BC : STZ $02B2        ; take the mask off

.return
  CLC
  RTS
}

; =============================================================================

org $368000
incbin gfx/zora_link.4bpp

; =============================================================================

UpdateZoraPalette:
{
  REP #$30  ; change 16 bit mode
  LDX #$001E

  .loop
  LDA.l zora_palette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30  ; go back to 8 bit mode
  INC $15   ; update the palette
  RTL       
}

; TODO: Change from "bunny palette" to blue zora palette colors 
zora_palette:
  dw #$7BDE, #$7FFF, #$2F7D, #$19B5, #$3A9C, #$14A5, #$19FD, #$14B6
  dw #$55BB, #$362A, #$3F4E, #$162B, #$22D0, #$2E5A, #$1970, #$7616
  dw #$6565, #$7271, #$2AB7, #$477E, #$1997, #$14B5, #$459B, #$69F2
  dw #$7AB8, #$2609, #$19D8, #$3D95, #$567C, #$1890, #$52F6, #$2357, #$0000

; =============================================================================

LinkItem_UsingZoraMask:
{

}

; =============================================================================
; Disassembled/Debugged Code of Conn's Zora Flippers 
; May God Give Me Strength 

; =============================================================================
; 22E2A0
; 
; Description: 
  JSR $E530
  JSL $22E670
  LDA $7F500E
  CMP #$01
  BEQ $22E2B2
  JMP $E2F0
  LDA $F0
  SEC 
  SBC #$0B
  BCS $22E2BC
  JMP $E2F0
  LDA $F0
  SEC 
  SBC #$4B
  BCS $22E2CB
  LDA #$40
  STA $F0
  JMP $879657
  LDA $F0
  SEC 
  SBC #$BB
  BCS $22E2D5
  JMP $E2F0

; =================================================================
; 22E2F0

  LDA $5D
  ASL 
  TAX 
  JMP $878106


; =================================================================
; 22E670

  LDA $7F500E ; probably free ram 
  CMP #$01
  BEQ $22E679
  RTL 
;-------
; Magic draining loop 
  LDA $7EF36E ; Load magic 
  BNE $22E688 ; branch if != 0 
  LDA #$3C
  STA $012E
  JMP $22E141
  LDA $7F500D ; load timer 
  BNE $22E69E ; branch if != 0 
  LDA #$18
  STA $7F500D ; set timer to 18
  LDA $7EF36E ; load magic 
  DEC         ; decrease magic by 1 
  STA $7EF36E ; store new magic 
  RTL 
;-------
  DEC 
  STA $7F500D ; decrease timer 
  RTL 

; =================================================================
; 22E600
; Possibly relevant, unconfirmed 

  LDA $7EF34A
  AND #$00FF
  CMP #$0001
  BEQ $22E611
  LDA $7EF35C,X
  RTL 
;-------
  LDA $7EF33B
  AND #$00FF
  CMP #$0001
  BNE $22E622
  LDA $7EF35C,X
  RTL 
;-------
  SEP #$30
  LDA #$3C
  STA $139F
  STA $13A1
  STA $13DF
  STA $13E1
  REP #$30
  LDA $7EF35C,X
  RTL 

; =================================================================
; 22EF50
; Possibly relevant 

  LDA $7EF3CC
  CMP #$0D
  BEQ $22EF59
  RTL 
