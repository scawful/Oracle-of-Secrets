; =========================================================
; Oracle file select, BG1 restyle (option E, "Maku Hollow"):
; bark walls with a leaf canopy and vines, a gold carved header
; plate, a dark heartwood panel. Layout, text and the fairy cursor
; are unchanged. Default on (Util/macros.asm).
;
; Data comes from fileselect_build.py (AFS handoff
; oracle_title_filemenu_2026-11-17/gen/). Regenerate the fs_* files
; in this folder with that script; do not hand-edit them.
;
; What this replaces:
; - FileSelect_UploadLinoleum ($0CCE1B) now copies a 32x32 bark map
;   instead of the linoleum pattern. File select, copy, erase and name
;   entry all call it.
; - FileSelect_InitializeGFX ($0CCDE6) still runs LoadFileSelectGraphics,
;   then uploads the bark, frame and plate chars into BG1 char slots
;   (VRAM $2000-$3FFF) and writes CGRAM rows 2 and 5 plus BG3 text
;   colours 25-26 into both palette buffers.
; - Four FancyBackgroundTileMap words: the header interior fill (rows 3
;   and 4) and the header's bottom corners (row 6).
;
; The plate face and the panel are transparent BG1 pixels. BG3 text is
; priority 0, so in mode 1 any opaque BG1 pixel hides it. The gold and
; heartwood colours come from the backdrop instead: colour math adds
; the fixed colour to a black CGRAM 0, and HDMA channels 6 and 7 set
; the fixed colour per scanline (gold gradient on the plate lines,
; heartwood grain on the panel lines). HDMA to CGRAM itself is not
; used: a palette DMA that overruns vblank would land at the wrong
; CGRAM address. EnableForceBlank clears $9B, so the HDMA stops on its
; own when a file loads; OracleFS_Linoleum turns it back on for file
; select, copy, erase and name entry. The COLDATA mirrors stay black,
; so a leftover backdrop-add in $9A adds nothing.
; =========================================================

pushpc

org $0CCE1B ; FileSelect_UploadLinoleum ; @hook module=Core
  JSL OracleFS_Linoleum
  RTS

org $0CCDE6 ; FileSelect_InitializeGFX, JSL LoadFileSelectGraphics ; @hook module=Core
  JSL OracleFS_LoadGfx

; FancyBackgroundTileMap words (vanilla value in the comment).
org $0CE200 : dw $35AF                ; header row 3 fill ($347F)
org $0CE216 : dw $3587                ; header row 4 fill ($347F)
org $0CE250 : dw $35AE                ; header row 6, col 2 ($35AB)
org $0CE276 : dw $75AE                ; header row 6, col 21 ($75AC)

org $598000
OracleFS_Tiles:
  incbin "fs_tiles.bin"

; dw vram_word, tiles_offset, size (one row per contiguous char run)
OracleFS_Runs:
  incsrc "fs_runs.asm"
.end

OracleFS_Map:
  incbin "fs_map.bin"                 ; 1024 BG1 map words, VRAM $1000

OracleFS_Pal:
  incbin "fs_pal.bin"                 ; CGRAM row 2 (bark, leaves), row 5 (frame)

OracleFS_TextPal:
  incbin "fs_text_pal.bin"            ; CGRAM 25 outline, 26 fill (BG3 palette 6)

; Fixed colour per scanline: channel 6 mode 2 (count, R|$20, G|$40),
; channel 7 mode 0 (count, B|$80). Both target COLDATA ($2132).
OracleFS_HdmaRG:
  incbin "fs_hdma_rg.bin"
OracleFS_HdmaB:
  incbin "fs_hdma_b.bin"

; ---------------------------------------------------------
; Callers enter with REP #$30 and DB $0C. They append stripes at
; $1006,X, so return X = $0800 like the vanilla routine.
OracleFS_Linoleum:
{
  LDA.w #$0010 : STA.l $7E1002        ; stripe to VRAM word $1000
  LDA.w #$FF07 : STA.l $7E1004        ; 2048 bytes
  LDX.w #$0000
  - : LDA.l OracleFS_Map,X : STA.l $7E1006,X
  INX : INX : CPX.w #$0800 : BNE -
  ; Backdrop: add the fixed colour, set per line by HDMA channels 6-7
  ; (the NMI copies $9B to HDMAEN and $99/$9A/$9C-$9E to colour math).
  LDA.w #$3202 : STA.l $004360        ; mode 2, B bus $2132
  LDA.w #OracleFS_HdmaRG : STA.l $004362
  LDA.w #$3200 : STA.l $004370        ; mode 0, B bus $2132
  LDA.w #OracleFS_HdmaB : STA.l $004372
  SEP #$20
  LDA.b #OracleFS_HdmaRG>>16 : STA.l $004364 : STA.l $004374
  STZ.b $99                           ; CGWSEL: math always on, add fixed colour
  LDA.b #$20 : STA.b $9A              ; CGADSUB: add on the backdrop only
  STA.b $9C                           ; COLDATA mirrors: black
  LDA.b #$40 : STA.b $9D
  LDA.b #$80 : STA.b $9E
  LDA.b #$C0 : TSB.b $9B
  REP #$20
  LDX.w #$0800                        ; vanilla exit values
  LDA.w #$0400 : STA.b $00
  RTL
}

; ---------------------------------------------------------
; Force blank is on: LoadFileSelectGraphics writes VRAM directly.
OracleFS_LoadGfx:
{
  JSL $00E4E9                         ; LoadFileSelectGraphics (replaced)
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB              ; DB $00: PPU and DMA registers

  ; Start right after vblank so the NMI cannot land between VMADDR and DMA.
  - : LDA.w $4212 : BPL -
  - : LDA.w $4212 : BMI -
  LDA.b #$80 : STA.w $2100            ; force blank
  STA.w $2115                         ; VMAIN: word increment

  REP #$20
  LDX.b #$00
.run
  LDA.l OracleFS_Runs+0,X : STA.w $2116
  LDA.l OracleFS_Runs+2,X : CLC : ADC.w #OracleFS_Tiles&$FFFF : STA.w $4302
  LDA.l OracleFS_Runs+4,X : STA.w $4305
  LDA.w #$1801 : STA.w $4300          ; A->B, two registers, $2118/$2119
  SEP #$20
  LDA.b #OracleFS_Tiles>>16 : STA.w $4304
  LDA.b #$01 : STA.w $420B
  REP #$20
  TXA : CLC : ADC.w #$0006 : TAX
  CPX.b #OracleFS_Runs_end-OracleFS_Runs : BNE .run

  ; Rows 2 and 5 into both buffers (fade target and live).
  LDX.b #$1E
  - : LDA.l OracleFS_Pal,X : STA.l $7EC340,X : STA.l $7EC540,X
  LDA.l OracleFS_Pal+$20,X : STA.l $7EC3A0,X : STA.l $7EC5A0,X
  DEX : DEX : BPL -

  ; Black backdrop: the fixed colour supplies the plate and panel.
  LDA.w #$0000 : STA.l $7EC300 : STA.l $7EC500

  ; BG3 palette 6 colours 1-2: file names, labels and header text.
  LDA.l OracleFS_TextPal+0 : STA.l $7EC332 : STA.l $7EC532
  LDA.l OracleFS_TextPal+2 : STA.l $7EC334 : STA.l $7EC534

  SEP #$20
  INC.b $15                           ; upload palettes this NMI
  PLB : PLP
  RTL
}

pullpc
