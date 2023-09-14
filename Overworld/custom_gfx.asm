org $0AB917 ; after most of the area loading after calling the bird takes place
    JSL CheckForChangeGraphicsNormalLoad

org $028492 ; after leaving a dungeon
    JSL CheckForChangeGraphicsNormalLoad

org $00E19B
    InitTilesets:

; ==============================================================================

org $3F8000
CheckForChangeGraphicsNormalLoad:
{
  JSL InitTilesets ;calls $00E19B that was replaced
  
  LDA $8A : CMP.b #$30 : BNE .boat_area

  PHB : PHK : PLB

  JSR ApplyGraphics1
  
  PLB

  RTL ;goes back to normal

  .boat_area

  RTL
}

; ==============================================================================

ApplyGraphics1:
{
  REP #$20                      ; A = 16, XY = 8
  LDX #$80 : STX $2115          ; Set the video port register every time we write it increase by 1
  LDA #$2C00 : STA $2116        ; Destination of the DMA $5800 in vram <- this need to be divided by 2
  LDA #$1801 : STA $4300        ; DMA Transfer Mode and destination register 
                                ; "001 => 2 registers write once (2 bytes: p, p+1)"
  LDA.w #BoatBitmap : STA $4302 ; Source address where you want gfx from ROM
  LDX.b #BoatBitmap>>16 : STX $4304
  LDA #$2000 : STA $4305        ; size of the transfer 4 sheets of $800 each
  LDX #$01 : STX $420B          ; Do the DMA 

  SEP #$30

  RTS

  BoatBitmap:
  incbin gfx/boat.bin
}

; ==============================================================================

