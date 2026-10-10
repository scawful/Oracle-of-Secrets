; =========================================================
; Text box shade (!ENABLE_TEXT_BOX_SHADE)
;
; Darkens the scene behind the text window (translucent dark band) so the
; white glyphs stay readable on bright ground. The Oracle font has no frame:
; glyph background is BG3 color 0 (transparent).
;
; How: RunInterface's pointer for $11 = $02 (Module0E_02_RenderText) points
; here. After RenderText runs, HDMA channel 6 writes CGWSEL/CGADSUB per
; scanline: the scene's own values ($99/$9A) above and below the window,
; "subtract fixed color, half" on BG1/BG2/OBJ/backdrop on the window rows.
; Color window 2 ($2128/$2129) limits the band to the window columns. BG3
; (text, HUD) is not in the math, so the glyphs keep full brightness.
;
; Channel 6: vanilla NMI uses channels 0-4 for DMA; vanilla HDMA uses 6/7
; for the iris and warp waves, the Oracle movie effect uses 5. After the
; iris opens, vanilla leaves channel 7 on ($9B = $80), writing window 1
; ($2126/$2127) every line; window 2 is free. The band is skipped when
; channel 6 is on or the scene already uses a color window ($98 bits 4-7).
;
; Limits: on the window rows, subscreen overlays (rain, fog) and translucent
; BG layers are replaced by the band; OBJ palettes 0-3 are never in color
; math (hardware). Text drawn by other modules (cutscene framework calls
; RenderText directly) gets no band.
; =========================================================

TextShade_RenderText = $0EC440   ; Module0E_02_RenderText (RTL)

!TextShadeChannelBit = $40       ; HDMA channel 6 in $9B (HDMAEN mirror)
!TextShadeMarker     = $5A

; Band look. CGWSEL: math only inside the color window, fixed color.
; CGADSUB: subtract + half on BG1, BG2, OBJ, backdrop (not BG3).
!TextShadeCGWSEL  = $10
!TextShadeCGADSUB = $F3

; Window $1CD2 is the VRAM word address of its top-left border tile (BG3 map
; $6000, 32 columns, no vertical scroll). Border: 24 x 8 tiles; text: 21 x 6
; tiles from column +1, row +1. Band: 23 x 8 tiles, 8 px around the text.
!TextShadeWidth  = 23*8-1        ; x1 - x0
!TextShadeHeight = 8*8           ; scanlines

; Vanilla free WRAM (Core/ram.asm UNUSED_7FF180). Opening $7FF300-$7FF331,
; Impa hints $7FF340-$7FF341, 2P PoC $7FF400+.
TextShade_Active  = $7FF350      ; !TextShadeMarker while the band is on
TextShade_Table   = $7FF358      ; HDMA table, 13 bytes used (16 reserved)

pushpc
; RunInterface long pointer table, entry $02.
org $00F878 : db TextShade_Messaging>>0  ; @hook module=Core name=TextShade_PointerLow kind=data
org $00F884 : db TextShade_Messaging>>8  ; @hook module=Core name=TextShade_PointerMid kind=data
org $00F890 : db TextShade_Messaging>>16 ; @hook module=Core name=TextShade_PointerBank kind=data

; Keep the vanilla frame in ordinary scenes. Blended scene layers use the
; same full-width band as TextShade_BuildTable, with transparent frame tiles.
; Displaced instructions: REP #$30 : LDA.w $1CD0 (5 bytes).
org $0ED2AB ; @hook module=Core name=TextShade_OverlayBorderRow kind=jml target=TextShade_BorderRow
  JML TextShade_BorderRow
  NOP
assert pc() == $0ED2B0

org $3AEA00
; Bank $3A: Impa hints end below $3AEA00; early-game balance starts at $3AEC00.

TextShade_Messaging:
{
  JSL TextShade_RenderText
  PHB : PHK : PLB
  PHP
  SEP #$30

  ; RenderText_FinalizeWindow restores $10/$11 on the frame the window
  ; closes, so a changed module means "turn the band off".
  LDA.b $10 : CMP.b #$0E : BNE .off
  LDA.b $11 : CMP.b #$02 : BNE .off

  LDA.l TextShade_Active : CMP.b #!TextShadeMarker : BEQ .update
    LDA.b $9B : AND.b #!TextShadeChannelBit : BNE .done
    LDA.b $98 : BIT.b #$F0 : BNE .done       ; scene uses a color window (iris)
    ORA.b #$80 : STA.b $98                   ; color window 2 on, not inverted
    LDA.b #$01 : STA.w $4360                 ; mode 1: two registers
    LDA.b #$30 : STA.w $4361                 ; $2130 CGWSEL, $2131 CGADSUB
    LDA.b #TextShade_Table&$FF : STA.w $4362
    LDA.b #(TextShade_Table>>8)&$FF : STA.w $4363
    LDA.b #TextShade_Table>>16 : STA.w $4364
    JSR TextShade_BuildTable
    LDA.b $9B : ORA.b #!TextShadeChannelBit : STA.b $9B
    LDA.b #!TextShadeMarker : STA.l TextShade_Active
    BRA .done

  .update
  ; A text command can move the window; the scene can change $99/$9A.
  JSR TextShade_BuildTable
  BRA .done

  .off
  LDA.l TextShade_Active : CMP.b #!TextShadeMarker : BNE .done
    LDA.b $9B : AND.b #!TextShadeChannelBit^$FF : STA.b $9B
    LDA.b $98 : AND.b #$7F : STA.b $98       ; color window 2 off
    LDA.b #$00 : STA.l TextShade_Active

  .done
  PLP
  PLB
  RTL
}

; In: 8-bit A/X/Y. Uses $00-$01.
TextShade_BuildTable:
{
  ; Columns. One color-math setup per scanline: on the band rows, columns
  ; outside the window lose the scene's own math, which shows as bright strips
  ; beside the box when an overlay is up (scawful, 2026-09-26, storm + Impa
  ; hint). So the band spans the full width only when the scene blends a real
  ; layer: $9A bits 0-4 (BG1-BG4, OBJ), e.g. rain/fog overlay 82/72. Backdrop-
  ; only math (bit 5; rooms use 02/20) changes almost nothing on screen, and a
  ; full-width band there reads as a black bar (scawful, 2026-09-26), so those
  ; scenes keep the box: x0 = col * 8, x1 = x0 + width (clamped to 255).
  LDA.b $9A : AND.b #$1F : BEQ .boxed
    STZ.w $2128
    LDA.b #$FF : STA.w $2129
    BRA .rows
  .boxed
  LDA.w $1CD2 : AND.b #$1F : ASL #3 : STA.w $2128
  CLC : ADC.b #!TextShadeWidth : BCC + : LDA.b #$FF : +
  STA.w $2129
  .rows

  ; Rows: y0 = row * 8. row = ($1CD2 >> 5) & $1F.
  REP #$20
  LDA.w $1CD2 : LSR #5 : AND.w #$001F : ASL #3
  SEP #$20
  STA.b $00

  ; Scene rows: the scene uses no color window (checked at open), so its
  ; "inside window" fields meant nowhere and "outside" meant everywhere.
  ; Keep that meaning now that window 2 is on: per 2-bit field (clip 7-6,
  ; prevent 5-4), 01/11 -> 11 (always), 00/10 -> 00 (never).
  LDA.b $99 : AND.b #$0F : STA.b $01
  LDA.b $99 : BIT.b #$40 : BEQ + : LDA.b #$C0 : TSB.b $01 : LDA.b $99 : +
  BIT.b #$10 : BEQ + : LDA.b #$30 : TSB.b $01 : +

  LDX.b #$00
  LDA.b $00 : BEQ .band
  CMP.b #$80 : BCC .top
    LDA.b #$7F : JSR .entry_scene            ; lines 0-126
    LDA.b $00 : SEC : SBC.b #$7F
  .top
  JSR .entry_scene

  .band
  LDA.b #!TextShadeHeight : STA.l TextShade_Table, X
  LDA.b #!TextShadeCGWSEL : STA.l TextShade_Table+1, X
  LDA.b #!TextShadeCGADSUB : STA.l TextShade_Table+2, X
  INX #3
  LDA.b #$01 : JSR .entry_scene              ; rest of the frame: scene values
  LDA.b #$00 : STA.l TextShade_Table, X      ; end of table
  RTS

  ; A = line count. Writes count, scene CGWSEL ($01), $9A; X += 3.
  .entry_scene
  STA.l TextShade_Table, X
  LDA.b $01 : STA.l TextShade_Table+1, X
  LDA.b $9A : STA.l TextShade_Table+2, X
  INX #3
  RTS
}

; Same entry/return contract as vanilla RenderText_DrawBorderRow:
; caller DB=$0E, direct page=$0000; result M/X=16, X advances 52 bytes,
; Y advances 4, $1CD0 advances one tile row, and $0E ends at zero.
; Return through the original bank-$0E RTS so the caller's JSR stays valid.
TextShade_BorderRow:
{
  REP #$30
  LDA.b $9A : AND.w #$001F : BNE .overlay
    LDA.w $1CD0
    JML $0ED2B0                         ; displaced LDA, then vanilla body
  .overlay
  LDA.w $1CD0 : XBA : STA.w $1002, X
  INX #2
  XBA : CLC : ADC.w #$0020 : STA.w $1CD0
  LDA.w #$2F00 : STA.w $1002, X         ; same 24-tile stripe header
  INX #2
  LDA.w #$0018 : STA.b $0E
  LDA.w #$387F                        ; the renderer's transparent fill tile
  .fill
    STA.w $1002, X
    INX #2
    DEC.b $0E : BNE .fill
  INY #4
  JML $0ED2EB                         ; original RTS
}

print "End of text box shade             ", pc
assert pc() <= $3AEC00, "Text box shade crossed $3AEC00 (Core/early_game_balance.asm)"
pullpc
