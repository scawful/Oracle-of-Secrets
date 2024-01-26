;===========================================================
; Ice Rod freezes water
; Written by Conn
; 
;===========================================================


IceRodTileRam = $03EF

; Ancilla_CheckTileCollision_Targeted_continue
org $088A5D
  JSL $0EFBA0

org $0EFBA0 ; main code
LinkItem_IceRod: 
{
   ; load native value
  STA $03E4, X : TAY
  
  ; check if you're on overworld 
  LDA $008C : BNE $01
  RTL 

  ; disable other flying object icing water (boomerang, sword beam) 
  LDA $03A3 : CMP #$06 : BEQ $01 
  RTL 
  
  ; check if ice shot #1 only is used (disable 2nd shot to ice) 
  CPX #$04 : BEQ $01 
  RTL 

  ; check if ice shot is on water tiles 
  LDA $03E8 : CMP #$08 : BEQ .on_water_tiles

  ; check if ice shot is on native unused, edited blocks 
  LDA $03E8 : CMP #$03 : BEQ $01 
  RTL
.on_water_tiles
  ; double check if really ice shot is used
  LDA $0303 : CMP #$06 : BEQ $01 
  RTL 

  LDA $0304 : CMP #$06 : BEQ $01 
  RTL 
  
  TXA 
  STA $7ED004 ; store native x value into ram to regain after code

 ; wait for vblank to enable dma transfer
  LDA $4212 : AND #$80 : BEQ $F9 

  REP #$30 
  LDA $2116 : STA $7ED005 ; store native value to regain later 

  ; calculation procedure to get correct x,y coordinates for new tile
  LDA $00 : SEC : SBC $0708 : AND $070A 
  ASL A 
  ASL A 
  ASL A 
  STA $06 
  LDA $02 : SEC : SBC $070C : AND $070E : ORA $06 
  TAX 
  LDA #$00B7 : STA $7E2000, X ; store new 16x16 ice tile into ram (property of tile!)
  CLC : STZ $02 ; calculation procedure to get 8x8 vram map address (look of tile)
  TXA 
  AND #$003F : CMP #$0020 : BCC $05 
  LDA #$0400 : STA $02 
  TXA 
  AND #$0FFF : CMP #$0800 : BCC $07 
  LDA $02 : ADC #$07FF : STA $02 
  TXA 
  AND #$001F : ADC $02 : STA $02 
  TXA 
  AND #$0780 
  LSR A 
  ADC $02 
  STA $2116 ; store vram address for upper tile part (8x16) to $2116
  STA $7ED007
  ; Palette set here
  LDA #$1D83 ; load new ice tiles
  STA $7ED000
  STA $7ED002
  JSR $FD00 ; jsr to dma vram transfer for upper ice tile part
  
  REP #$30 
  LDA $7ED007 ; regain vram address
  ADC #$0020 ; add 20 for lower part (8x16) and store to $2116
  STA $2116 
  JSR $FD00 ; jsr to dma vram transfer for lower ice tile part
  LDA $7ED005 ; regain native register value
  STA $2116
  SEP #$30 
  LDA $7ED004 ; regain native x-value
  TAX 
  RTL 
}


org $0EFD00 ; vram dma transfer
VramDmaTransfer:
{
  LDA #$007E ; load origin of bytes to transfer (7E/d000)
  STA $4304 
  LDA #$D000 
  STA $4302 
  SEP #$30 
  LDA #$18 ; bus
  STA $4301 
  LDA #$04 ; transfer 4 bytes 
  STA $4305 
  LDA #$01 
  STA $4300 
  STA $420B ; make dma transfer
  RTS 
}


; bug fix to not swim through tiles but jump onto them
org $07DC9E
  JSL $0EFC80
  nop

org $0EFC80
  LDA $0A 
  TSB $0343 
  TSB $0348 
  RTL 

; bug fix to stop gliding on shallow water when leaving ice tile 
org $07DD1B 
  JSL $0EFC90
  nop

org $0EFC90
  LDA $0A 
  TSB $0359 
  LDA $0350 
  CMP #$0100 
  BNE $03 
  STZ $034A 
  RTL 


org $0E95DC ; get a 0e written here (first byte) to enable gliding on new tiles
  ASL $5757

org $0F85B8 ; get new tile values (83 1d) written 4 times here
  STA $1D,s 
  STA $1D,s 
  STA $1D,s 
  STA $1D,s
