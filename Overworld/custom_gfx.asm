; Boat sheets for wide $38/$39 (Dragon Ship) and wide $30/$31 (Kalyxo Docks,
; which held the ship before the 2026-10-19 split). $8A = parent area.
CheckForChangeGraphicsNormalLoadBoat:
{
if !LYRA_CURRENT_MODE == 1
  ; Current catalog dispatch must not replace native boats, indoors or an
  ; out-of-domain parent. Preserve full A/P before the original fallback.
  PHP : REP #$20 : PHA
  LDA.l $7E001B : AND.w #$00FF : BNE .native
  LDA.l $7E008A : AND.w #$00FF
  CMP.w #!LYRA_CURRENT_FIRST : BCC .native
  CMP.w #!LYRA_CURRENT_END : BCS .native
  PLA : PLP
if !ENABLE_OW_AREA_TILESETS == 1
  JSL AreaTileset_LoadTypes ; Source types before the preserved current sheet owner.
endif
  JML SharedGraphicsNormalLoad
  .native
  PLA : PLP
endif
if !ENABLE_OW_AREA_TILESETS == 1
  JML AreaTileset_Load ; Reuse this callback's original long return frame.
else
  LDA $8A : CMP.b #$38 : BEQ .load
  CMP.b #$30 : BNE .boat_area
  .load
    PHB : PHK : PLB
    JSR ApplyGraphics1
    JSR ApplyGraphics2
if !ENABLE_KALYXO_BOAT == 1
    ; Reuse the catalog consumer after the native dock/ship sheet owner.
    ; Only the explicitly bound docks profile is selected in native mode.
    JSL SharedGraphicsNormalLoad
endif
    PLB
  .boat_area
  RTL
endif
}
CheckForChangeGraphicsNormalLoadBoat_End:

; Shared graphics callbacks retain the native upload schedule.
if !LYRA_CURRENT_MODE == 1 || !ENABLE_KALYXO_BOAT == 1
InvalidateCustomGraphicsCache:
{
  JML SharedGraphicsInvalidateCache
}

; A8/XY16, X=auxiliary slot. Preserve P/X/Y/DBR/D and hidden B. Reads only.
; This recovery also runs after leaving a catalog profile: a native $FF must
; restore the saved underlying sheet while the prior cache holds our sentinel.
ResolveCustomGraphicsTransitionSheet:
{
  PHP
  CMP.b #$FF : BNE .done
  CPX.w #$0003 : BCC .done
  CPX.w #$0007 : BCS .done
  LDA.l $7E04CB, X : CMP.b #$FF : BEQ .restore
    LDA.b #$FF
    BRA .done
  .restore
    LDA.l $7EC2F5, X
  .done
  PLP
  RTL
}

; A16/XY8, native DMA destination/count/schedule remain caller-owned.
SelectCustomGraphicsTransitionSource:
{
  JML SharedGraphicsTransitionSource
}

; A8/XY16, retain the native incremental $50..$5F upload schedule.
SelectShipIncrementalGraphicsSource:
{
  JML SharedGraphicsIncrementalSource
}
endif

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

if !ENABLE_KALYXO_BOAT == 1 && !LYRA_CURRENT_MODE == 0
  ShipBackgroundGraphics:
endif
  BoatBitmap:
  incbin gfx/boat.bin
}

ApplyGraphics2:
{
  %ApplyGraphicsSheet(AdditionalBitmap, $5000)
  RTS

if !ENABLE_KALYXO_BOAT == 1 && !LYRA_CURRENT_MODE == 0
  ShipExtendedGraphics:
endif
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
