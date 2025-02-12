CheckForChangeGraphicsNormalLoadBoat:
{
  LDA $8A : CMP.b #$30 : BNE .boat_area
    PHB : PHK : PLB
    JSR ApplyGraphics1
    JSR ApplyGraphics2
    PLB
  .boat_area
  RTL
}

macro ApplyGraphicsSheet(sheet, dest)
  REP #$20                ; A = 16, XY = 8
  LDX #$80 : STX $2115    ; Set the video port register every time we write it increase by 1
  LDA #<dest> : STA $2116 ; Destination of the DMA $7800 in vram <- this need to be divided by 2
  LDA #$1801 : STA $4300  ; DMA Transfer Mode and destination register
                          ; "001 => 2 registers write once (2 bytes: p, p+1)"
  LDA.w #<sheet>     : STA $4302
  LDX.b #<sheet>>>16 : STX $4304
  LDA #$2000 : STA $4305  ; Size of the transfer 4 sheets of $800 each
  LDX #$01 : STX $420B    ; Execute the DMA
  SEP #$30
endmacro

ApplyGraphics1:
{
  %ApplyGraphicsSheet(BoatBitmap, $2C00)
  RTS

  BoatBitmap:
  incbin gfx/boat.bin
}

ApplyGraphics2:
{
  %ApplyGraphicsSheet(AdditionalBitmap, $5000)
  RTS

  AdditionalBitmap:
  incbin gfx/boat2.bin
}

ApplyKorokSpriteSheets:
{
  REP #$20               ; A = 16, XY = 8
  LDX #$80 : STX $2100   ; turn the screen off (required)
  LDX #$80 : STX $2115   ; Set the video port register every time we write it increase by 1
  LDA #$5000 : STA $2116 ; Destination of the DMA $5800 in vram <- this need to be divided by 2
  LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register
  ; "001 => 2 registers write once (2 bytes: p, p+1)"
  LDA.w #KorokSpriteSheets : STA $4302     ; Source address where you want gfx from ROM
  LDX.b #KorokSpriteSheets>>16 : STX $4304
  LDA   #$1800 : STA $4305                 ; size of the transfer 4 sheets of $800 each
  LDX   #$01 : STX $420B                   ; Do the DMA
  LDX #$0F : STX $2100                    ; Turn the screen back on
  SEP #$30

  RTL

  KorokSpriteSheets:
  incbin gfx/korok.bin
}
