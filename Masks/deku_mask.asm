; =============================================================================
;   Deku Mask
; =============================================================================

org    $358000
incbin gfx/deku_link.bin

; =============================================================================

org $07B0AB
LinkItem_EvaluateMagicCost:

org    $07A64B           ; formerly Quake
LinkItem_DekuMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .continue

  LDX.b #$01
  
  JSR LinkItem_EvaluateMagicCost : BCC .return
  
  LDA.b #$0A : STA $5D

  RTS

.continue
  ; Check for R button held
  %CheckNewR_ButtonPress() : BEQ .return

  LDA $6C : BNE .return   ; in a doorway
  LDA $0FFC : BNE .return ; can't open menu

  %PlayerTransform()

  LDA $02B2 : CMP #$01 : BEQ .unequip ; is the deku mask on?
  JSL Palette_ArmorAndGloves          ; set the palette

  LDA.l $7EF35A : STA $0AAF ; Store the current shield
  LDA.b #$00 : STA $7EF35A  ; Clear the shield

  LDA #$35 : STA $BC   ; put the mask on
  LDA #$01 : STA $02B2 ; set the deku mask flag
  STA $02F5 ; Somaria platform flag, no dash.

  BRA .return

.unequip
  STZ $5D
  ; Restore the shield
  LDA $0AAF : STA.l $7EF35A
  STZ $02F5

  %ResetToLinkGraphics()

.return
  RTS
}

; =========================================================

org $07E370
  LinkHop_FindArbitraryLandingSpot:

org $07A6D6
LinkState_UsingQuake:
{


}
warnpc $07A779

org $318000
; org $07A013
;   JSL LinkItem_SlingshotPrepare

; Hooked @ [$07A013]
; $A200
LinkItem_SlingshotPrepare:
{
  LDA #$01 : TSB $50
  LDA $7EF340

  BNE .alpha
  JMP .beta  ; $A270
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
  LDA #$01    ; Load the accumulator with hex value 01
  STA $7F502E ; Store the accumulator value at memory address 7F502E

  PHB      ; Push data bank register on stack
  REP #$30 ; Clear 16-bit accumulator and index registers
    LDX #$A500   ; Load X register with source address
    LDY #$9800   ; Load Y register with destination address
    LDA #$00BF   ; Load the accumulator with the number of bytes to be moved
    MVN $20, $7E ; Block move negative - moves 00BF bytes from $A500 to $9800
  SEP #$30 ; Set 8-bit accumulator and index registers
  PLB      ; Pull data bank register from stack

.loop
  LDA $4212 : AND #$80 : BNE .loop ; Wait for VBlank start (beginning of vertical blanking period)
.loop2
  LDA $4212 : AND #$80 : BEQ .loop2 ; Wait for VBlank end

  REP #$30 ; Clear 16-bit accumulator and index registers
    LDA #$A700 : STA $4302 ; Set DMA source address to $A700
    LDA #$42A0 : STA $2116 ; Set VRAM (Video RAM) address to $42A0
  SEP #$30 ; Set 8-bit accumulator and index registers

  LDA #$80 : STA $2115 ; Set VRAM write increment to 2 bytes, and access mode to word access at the specified address
  LDA #$18 : STA $4301 ; Set DMA destination address to $2118 (VRAM data write)
  LDA #$20 : STA $4304 ; Set DMA transfer size to 32 bytes
  LDA #$80 : STA $4305 ; Set DMA transfer size (high byte)
  LDA #$01 : STA $4300 ; Set DMA mode to 1 (2 registers write once)
  STA $420B            ; Start DMA on channel 0

  REP #$30 ; Clear 16-bit accumulator and index registers
    LDA #$43A0 : STA $2116 ; Set VRAM address to $43A0
    LDA #$A800 : STA $4302 ; Set DMA source address to $A800
  SEP #$30 ; Set 8-bit accumulator and index registers

  LDA #$80 : STA $2115 ; Set VRAM write increment to 2 bytes, and access mode to word access at the specified address
  LDA #$18 : STA $4301 ; Set DMA destination address to $2118 (VRAM data write)
  LDA #$20 : STA $4304 ; Set DMA transfer size to 32 bytes
  LDA #$80 : STA $4305 ; Set DMA transfer size (high byte)
  LDA #$01 : STA $4300 ; Set DMA mode to 1 (2 registers write once)
  STA $420B            ; Start DMA on channel 0
  RTL

}


; =============================================================================

org $07811A
  JSR Link_HandleDekuTransformation

pullpc                         ; Bank 07 Free Space from minish_form
Link_HandleDekuTransformation: ; Link_HandleBunnyTransformation
{
  ; Check if using Quake Medallion
  LDA $5D : CMP.b #$0A : BEQ .continue
  JSR $82DA

.continue
  STZ $03F5
  STZ $03F6

  ; Link can move.
  CLC

  RTS
}

print "End of Masks/deku_mask.asm        ", pc
pushpc
