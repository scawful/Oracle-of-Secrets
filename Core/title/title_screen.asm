; =========================================================
; Oracle title screen, BG2 layer (Concept D: purple/gold vortex,
; Maku Tree silhouette, island basin, gold credit line).
;
; Data comes from export_title_bg2.py (AFS handoff
; oracle_title_filemenu_2026-11-17/gen/). Regenerate the four files in
; this folder with that script; do not hand-edit them.
;
; What this replaces:
; - Stripe set 3 ($14 = 3, uploaded by Intro_TriforceTerminateSpin) now
;   points at OracleTitle_Stripes. Its BG1 half is copied byte for byte
;   from the ROM's title data at $A18000 at build time, so yaze/ZScream
;   BG1 (logo) edits still apply. Its BG2 half is the new map; yaze BG2
;   title edits are ignored while this flag is on.
; - Intro sub 2 ($0CC341) uploads the BG2 tiles into free BG/OBJ char
;   slots and writes palette row 5 plus the SECRETS plate colours (row 2)
;   into the fade target buffer $7EC300. IntroTitleCardPaletteFadeIn
;   brings $7EC500 up to them.
; - Intro subs 7 and 8 rotate row 5 colours 1-8 every 8 frames (vortex).
; =========================================================

pushpc

org $00937D : db OracleTitle_Stripes       ; Stripes14_SourceAddress, entry 3
org $009386 : db OracleTitle_Stripes>>8
org $00938F : db OracleTitle_Stripes>>16

org $0CC341 ; Intro_InitializeTriforcePolyThread ; @hook module=Core
  JSL OracleTitle_Load
org $0CC287 ; Intro_PopSubtitleCard ; @hook module=Core
  JSL OracleTitle_Cycle
org $0CC2D4 ; Intro_TrianglesBeforeAttract ; @hook module=Core
  JSL OracleTitle_Cycle
org $0CEDFA ; Attract_FadeOut.fully_faded ; @hook module=Core
  JSL OracleTitle_RestoreForAttract

org $588000
; Tiles first so every run's source stays inside bank $58.
OracleTitle_Tiles:
  incbin "bg2_tiles.bin"

; dw vram_word, tiles_offset, size (one row per contiguous VRAM slot run)
OracleTitle_Runs:
  incsrc "bg2_runs.asm"
.end

OracleTitle_Pal:
  incbin "bg2_pal.bin"

OracleTitle_Stripes:
  ; BG1 stripe: 4-byte header + 2048-byte map, copied from the title data.
  for i = 0..2052
    db read1($A18000+!i)
  endfor
  ; BG2 stripe: VRAM word $0000, 2048 bytes.
  db $00, $00, $07, $FF
  incbin "bg2_map.bin"
  db $FF

; ---------------------------------------------------------
; Intro sub 2. Force blank is on (sub 1 set it; sub 2 ends by setting $13).
OracleTitle_Load:
{
  JSL $00E384                         ; LoadCommonSprites_long (replaced)
  PHP : PHB
  SEP #$30
  LDA.b $10 : BNE .skip               ; intro module only
  LDA.b $11 : CMP.b #$02 : BEQ .go
              CMP.b #$0A : BEQ .go    ; attract -> title return
.skip
  JMP .done
.go
  LDA.b #$00 : PHA : PLB              ; DB $00: PPU and DMA registers

  ; Start right after vblank so the NMI cannot land between VMADDR and DMA.
  ; About 17 KB takes ~105 scanlines.
  - : LDA.w $4212 : BPL -
  - : LDA.w $4212 : BMI -
  LDA.b #$80 : STA.w $2100            ; force blank
  STA.w $2115                         ; VMAIN: word increment

  REP #$20
  LDX.b #$00
.run
  LDA.l OracleTitle_Runs+0,X : STA.w $2116
  LDA.l OracleTitle_Runs+2,X : CLC : ADC.w #OracleTitle_Tiles&$FFFF : STA.w $4302
  LDA.l OracleTitle_Runs+4,X : STA.w $4305
  LDA.w #$1801 : STA.w $4300          ; A->B, two registers, $2118/$2119
  SEP #$20
  LDA.b #OracleTitle_Tiles>>16 : STA.w $4304
  LDA.b #$01 : STA.w $420B
  REP #$20
  TXA : CLC : ADC.w #$0006 : TAX
  CPX.b #OracleTitle_Runs_end-OracleTitle_Runs : BNE .run

  ; Palette row 5 (BG2) into the fade target.
  LDX.b #$1E
  - : LDA.l OracleTitle_Pal,X : STA.l $7EC3A0,X : DEX : DEX : BPL -

  ; SECRETS plate, row 2: green instead of blue.
  LDA.w #$7BFE : STA.l $7EC344        ; f0fff0 highlight
  LDA.w #$08A1 : STA.l $7EC34A        ; 0c2c14 outline
  LDA.w #$19C5 : STA.l $7EC34C        ; 2c7034 shade
  LDA.w #$26CB : STA.l $7EC34E        ; 58b048 face
.done
  PLB : PLP
  RTL
}

; ---------------------------------------------------------
; Intro subs 7 and 8: rotate BG2 colours 1-8 every 8 frames in both
; palette buffers, so the fade and the live palette stay in step.
OracleTitle_Cycle:
{
  JSL $0CC404                         ; Intro_HandleAllTriforceAnimations (replaced)
  PHP
  SEP #$20
  LDA.b $1A : AND.b #$07 : BNE .done
  REP #$30
  PHX
  LDA.l $7EC3A2 : PHA
  LDX.w #$0000
  - : LDA.l $7EC3A4,X : STA.l $7EC3A2,X : INX : INX : CPX.w #$000E : BNE -
  PLA : STA.l $7EC3B0
  LDA.l $7EC5A2 : PHA
  LDX.w #$0000
  - : LDA.l $7EC5A4,X : STA.l $7EC5A2,X : INX : INX : CPX.w #$000E : BNE -
  PLA : STA.l $7EC5B0
  PLX
  SEP #$20
  INC.b $15                           ; upload palettes this NMI
.done
  PLP
  RTL
}

; ---------------------------------------------------------
; Attract_FadeOut.fully_faded ($0CEDFA): restore the default title/storybook
; VRAM and palette buffers that OracleTitle_Load / OracleTitle_Cycle replaced,
; since Attract_Initialize ($0CEE0C) does not reload BG/OBJ tilesets.
OracleTitle_RestoreForAttract:
{
  JSL $00893D                         ; EnableForceBlank (replaced)
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  LDA.b #$23 : STA.w $0AA1
  LDA.b #$7D : STA.w $0AA3
  LDA.b #$51 : STA.w $0AA2
  LDA.b #$08 : STA.w $0AA4
  JSL $00E2D0                         ; LoadDefaultGraphics
  JSL $00E19B                         ; InitializeTilesets
  LDY.b #$5D
  JSL $00D337                         ; DecompressAnimatedUnderworldTiles
  JSL $02811A                         ; Overworld_LoadAllPalettes_long
  REP #$30
  LDX.w #$007E
  - : LDA.l $7EC340,X : STA.l $7EC540,X : DEX : DEX : BPL -
  PLB : PLP
  RTL
}

; Bank $58 ledger: title code/data $588000-$58EFFF; attract actor choreography
; (Dungeons/attract_royal_scenes.asm) starts at $58F000.
assert pc() <= $58F000

pullpc
