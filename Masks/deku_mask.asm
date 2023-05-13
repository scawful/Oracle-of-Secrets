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
  ; Check for R button held 
  LDA $F2 : CMP #$10 : BNE .return 

  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A        ; clear the Y button state 

  LDA $6C : BNE .return                 ; in a doorway
  LDA $0FFC : BNE .return               ; can't open menu

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP #$01 : BEQ .unequip   ; is the deku mask on?
  JSL Palette_ArmorAndGloves            ; set the palette 

  LDA.l $7EF359 : STA $0AA5 ; Store the current sword 
  LDA.l $7EF35A : STA $0AAF ; Store the current shield
  LDA.b #$00 : STA $7EF359 : STA $7EF35A ; Clear the sword and shield
  LDA #$02 : STA $7E03FC ; Set the override to Bow (pea shooter)

  LDA #$35 : STA $BC                    ; put the mask on
  LDA #$01 : STA $02B2
  
  BRA .return

.unequip
  JSL Palette_ArmorAndGloves
  STZ $5D

  ; Restore the sword and shield 
  LDA $0AA5 : STA.l $7EF359
  LDA $0AAF : STA.l $7EF35A
  LDA #$00 : STA $7E03FC           ; clear the override
  LDA #$10 : STA $BC : STZ $02B2   ; take the mask off


.return
  RTS
}

; =============================================================================

org $079CD9
  JSL LinkItem_CheckForSwordSwing_Masks

org $07A013
  JSL LinkItem_SlingshotPrepare

; =============================================================================

org $318000
LinkItem_CheckForSwordSwing_Masks:
{

  LDA $02B2 : CMP #$01 : BNE .return

  LDA #$01
  RTL

.return
  LDA $3B : AND.b #$10
  RTL
}

; =============================================================================


; Hooked @ [$07A013]
; $A200
LinkItem_SlingshotPrepare:
{
  LDA #$01 : TSB $50
  LDA $7EF340
  BNE .alpha
  JMP $A270
.alpha 
  CMP #$01
  BNE .void ; unused afaik (RTS?)
  JMP .beta

; $A214
.void


; $A270
.beta
  LDA $7F1060
  CMP #$10
  BEQ $20A27B
  JMP .theta

; $A300
.theta
  LDA $7F502E
  CMP #$01
  BNE .gamma
  RTL 

; $A309
.gamma
  LDA #$01          ; Load the accumulator with hex value 01
  STA $7F502E       ; Store the accumulator value at memory address 7F502E

  PHB               ; Push data bank register on stack
  REP #$30          ; Clear 16-bit accumulator and index registers
    LDX #$A500      ; Load X register with source address
    LDY #$9800      ; Load Y register with destination address
    LDA #$00BF      ; Load the accumulator with the number of bytes to be moved
    MVN $20, $7E    ; Block move negative - moves 00BF bytes from $A500 to $9800
  SEP #$30          ; Set 8-bit accumulator and index registers
  PLB               ; Pull data bank register from stack

.loop
  LDA $4212 : AND #$80 : BNE .loop   ; Wait for VBlank start (beginning of vertical blanking period)
.loop2
  LDA $4212 : AND #$80 : BEQ .loop2  ; Wait for VBlank end

  REP #$30          ; Clear 16-bit accumulator and index registers
    LDA #$A700 : STA $4302  ; Set DMA source address to $A700
    LDA #$42A0 : STA $2116  ; Set VRAM (Video RAM) address to $42A0
  SEP #$30          ; Set 8-bit accumulator and index registers

  LDA #$80 : STA $2115  ; Set VRAM write increment to 2 bytes, and access mode to word access at the specified address
  LDA #$18 : STA $4301  ; Set DMA destination address to $2118 (VRAM data write)
  LDA #$20 : STA $4304  ; Set DMA transfer size to 32 bytes
  LDA #$80 : STA $4305  ; Set DMA transfer size (high byte)
  LDA #$01 : STA $4300  ; Set DMA mode to 1 (2 registers write once)
  STA $420B             ; Start DMA on channel 0

  REP #$30                  ; Clear 16-bit accumulator and index registers
    LDA #$43A0 : STA $2116  ; Set VRAM address to $43A0
    LDA #$A800 : STA $4302  ; Set DMA source address to $A800
  SEP #$30                  ; Set 8-bit accumulator and index registers

  LDA #$80 : STA $2115  ; Set VRAM write increment to 2 bytes, and access mode to word access at the specified address
  LDA #$18 : STA $4301  ; Set DMA destination address to $2118 (VRAM data write)
  LDA #$20 : STA $4304  ; Set DMA transfer size to 32 bytes
  LDA #$80 : STA $4305  ; Set DMA transfer size (high byte)
  LDA #$01 : STA $4300  ; Set DMA mode to 1 (2 registers write once)
  STA $420B             ; Start DMA on channel 0
  RTL                   ; Return from subroutine long

}