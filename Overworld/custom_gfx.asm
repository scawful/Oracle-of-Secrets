; Normal-load graphics profiles. $8A is the parent area, A/XY are 8-bit.
; These existing entry/map-close/Soaring call sites upload during the load.
; Scrolling uses the NMI source selectors below, never this direct DMA path.
CheckForChangeGraphicsNormalLoadBoat:
{
  LDA.b $1B : BNE .done
  LDA $8A : CMP.b #$30 : BEQ .docks
  CMP.b #$32 : BEQ .docks
  CMP.b #$38 : BNE .done
    PHB : PHK : PLB
    JSR ApplyGraphics1
    JSR ApplyGraphics2
    PLB
    JSL InvalidateCustomGraphicsCache
    RTL
  .docks
    JSL LoadKalyxoGraphicsNormal
  .done
  RTL
}

macro ApplyGraphicsSheet(sheet, dest, count)
  REP #$20                ; A = 16, XY = 8
  LDX #$80 : STX $2115    ; Set the video port register every time we write it increase by 1
  LDA #<dest> : STA $2116 ; Destination of the DMA $7800 in vram <- this need to be divided by 2
  LDA #$1801 : STA $4300  ; DMA Transfer Mode and destination register
                          ; "001 => 2 registers write once (2 bytes: p, p+1)"
  LDA.w #<sheet>     : STA $4302
  LDX.b #<sheet>>>16 : STX $4304
  LDA #<count> : STA $4305
  LDX #$01 : STX $420B    ; Execute the DMA
  SEP #$30
endmacro

ApplyGraphics1:
{
  %ApplyGraphicsSheet(ShipBackgroundGraphics, $2C00, $2000)
  RTS
}
ShipBackgroundGraphics:
incbin gfx/boat.bin

ApplyGraphics2:
{
  %ApplyGraphicsSheet(ShipExtendedGraphics, $5000, $2000)
  RTS
}
ShipExtendedGraphics:
incbin gfx/boat2.bin

; Runtime art and helpers share the allocated lower half of bank $44.
; Map streams start at $44C000; no payload or code may reach them.
pushpc
org $448000
KalyxoDocksBackgroundGraphics:
incbin gfx/kalyxo_docks_bg.bin
assert pc() == $44A000
KalyxoDocksSlot3Graphics:
incbin gfx/kalyxo_docks_slot3.bin
assert pc() == $44A800

LoadKalyxoGraphicsNormal:
{
  LDA $8A : CMP.b #$32 : BEQ .loom
    %ApplyGraphicsSheet(KalyxoDocksBackgroundGraphics, $2C00, $2000)
    BRA .loaded
  .loom
    %ApplyGraphicsSheet(KalyxoDocksSlot3Graphics, $2C00, $0800)
  .loaded
  JSL InvalidateCustomGraphicsCache
  RTL
}

; ZS tracks the native sheet IDs at $04CB..$04D2. $FF never represents a
; loaded native sheet: it means "keep prior" in the per-area table. Mark only
; overridden slots $FF, retaining their underlying IDs in the existing native
; auxiliary-sheet cache $7EC2F8..$7EC2FB. Leaving a profile then restores its
; native sheets even if the destination also requests "keep prior".
; Entry A/XY=8; preserve X/Y/P. A is scratch. No new persistent WRAM.
InvalidateCustomGraphicsCache:
{
  PHP : PHX : PHY
  LDA.b $1B : BNE .done
  LDA $8A : CMP.b #$30 : BEQ .four
  CMP.b #$38 : BEQ .four
  CMP.b #$32 : BNE .done
    LDY.b #$01
    BRA .start
  .four
    LDY.b #$04
  .start
  LDX.b #$03
  .next
    LDA.w $04CB, X : CMP.b #$FF : BEQ .alreadyMarked
      STA.l $7EC2F5, X
      LDA.b #$FF : STA.w $04CB, X
    .alreadyMarked
    INX
    DEY : BNE .next
  .done
  PLY : PLX : PLP
  RTL
}

; Entry A=table sheet ID, X=slot, A/XY=8. Preserve X/Y. Only an overridden
; auxiliary slot resolves $FF back to its saved native ID. Other $FF entries
; retain ZS's original skip semantics.
ResolveCustomGraphicsTransitionSheet:
{
  CMP.b #$FF : BNE .done
  CPX.b #$03 : BCC .done
  CPX.b #$07 : BCS .done
  LDA.w $04CB, X : CMP.b #$FF : BEQ .restore
    LDA.b #$FF
    RTL
  .restore
    LDA.l $7EC2F5, X
  .done
  RTL
}

; Entry A=VRAM word target, A16/XY8; preserve X/Y and return A16/XY8.
; Called after setting a native $7F DMA source. Replace only whole BG slots
; belonging to the current profile; byte counts and the NMI budget stay native.
SelectCustomGraphicsTransitionSource:
{
  PHA
  LDA.b $1B : AND.w #$00FF : BNE .native
  LDA.b $8A : AND.w #$00FF
  CMP.w #$30 : BEQ .docks
  CMP.w #$32 : BEQ .loom
  CMP.w #$38 : BEQ .ship
  .native
  PLA
  RTL
  .docks
    PLA
    CMP.w #$2C00 : BCC .done
    CMP.w #$3C00 : BCS .done
    SEC : SBC.w #$2C00 : ASL
    CLC : ADC.w #KalyxoDocksBackgroundGraphics : STA.w $4302
    SEP #$20
    LDA.b #KalyxoDocksBackgroundGraphics>>16 : STA.w $4304
    REP #$20
    RTL
  .loom
    PLA
    CMP.w #$2C00 : BNE .done
    LDA.w #KalyxoDocksSlot3Graphics : STA.w $4302
    SEP #$20
    LDA.b #KalyxoDocksSlot3Graphics>>16 : STA.w $4304
    REP #$20
    RTL
  .ship
    PLA
    CMP.w #$2C00 : BCC .done
    CMP.w #$3C00 : BCS .done
    SEC : SBC.w #$2C00 : ASL
    CLC : ADC.w #ShipBackgroundGraphics : STA.w $4302
    SEP #$20
    LDA.b #ShipBackgroundGraphics>>16 : STA.w $4304
    REP #$20
  .done
  RTL
}

; Vanilla NMI incremental uploads use $19=$50..$5F and 512-byte chunks for
; the same VRAM range as boat2.bin. Redirect the source for the outdoor ship
; only, so later sprite preparation cannot overwrite its extended BG art.
; Hook ABI A8/XY16 -> A8/XY16; preserve X/Y. Replaces LDA #$7F : STA $4304.
SelectShipIncrementalGraphicsSource:
{
  LDA.b $1B : BNE .native
  LDA.b $8A : CMP.b #$38 : BNE .native
  LDA.b $19 : CMP.b #$50 : BCC .native
  CMP.b #$60 : BCS .native
    REP #$20
    AND.w #$00FF : SEC : SBC.w #$0050 : XBA : ASL
    CLC : ADC.w #ShipExtendedGraphics : STA.w $4302
    SEP #$20
    LDA.b #ShipExtendedGraphics>>16 : STA.w $4304
    RTL
  .native
    LDA.b #$7F : STA.w $4304
    RTL
}
assert pc() <= $44C000
pullpc

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
