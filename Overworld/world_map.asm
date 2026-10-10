; =========================================================
; World Map Module


WorldMapIcon_AdjustCoordinate = $0AC589
WorldMap_HandleSpriteBlink = $0AC51C

pullpc

DrawWisdomPendant:
{
  ; X position
  LDA.b #$08 : STA.l $7EC10B
  LDA.b #$30 : STA.l $7EC10A
  ; Y position
  LDA.b #$07 : STA.l $7EC109
  LDA.b #$01 : STA.l $7EC108

  LDA.b #$60 : STA.b $0D
  LDA.b #$34 : STA.b $0C ; Tile GFX

  LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$0D : STA.l $7EC025
  RTL
}

DrawPowerPendant:
{
  ; X position
  LDA.b #$08 : STA.l $7EC10B
  LDA.b #$0D : STA.l $7EC10A ; Upper nybble control Zoomed low X pos
  ; Y position
  LDA.b #$02 : STA.l $7EC109
  LDA.b #$84 : STA.l $7EC108 ; Upper nybble control Zoomed low Y pos

  LDA.b #$60 : STA.b $0D
  LDA.b #$32 : STA.b $0C ; Tile GFX

  LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$08 : STA.l $7EC025
  RTL
}

DrawCouragePendant:
{
  ; X position
  LDA.b #$00 : STA.l $7EC10B
  LDA.b #$87 : STA.l $7EC10A
  ; Y position
  LDA.b #$04 : STA.l $7EC109
  LDA.b #$01 : STA.l $7EC108
  ; Tile GFX
  LDA.b #$60 : STA.b $0D
  LDA.b #$38 : STA.b $0C
  ; Tile Size
  LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$0A : STA.l $7EC025 ; OAM Slot used
  RTL
}

DrawMasterSwordIcon:
{
  ; X position
  LDA.b #$02 : STA.l $7EC10B
  LDA.b #$FD : STA.l $7EC10A ; Upper nybble control Zoomed low X pos
  ; Y position
  LDA.b #$00 : STA.l $7EC109
  LDA.b #$E4 : STA.l $7EC108 ; Upper nybble control Zoomed low Y pos

  LDA.b #$62 : STA.b $0D
  LDA.b #$34 : STA.b $0C ; Tile GFX

  LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$0B : STA.l $7EC025
  RTL
}

DrawFortressOfSecretsIcon:
{
  ; X position
  LDA.b #$0E : STA.l $7EC10B
  LDA.b #$5E : STA.l $7EC10A
  ; Y position
  LDA.b #$06 : STA.l $7EC109
  LDA.b #$68 : STA.l $7EC108

  LDA.b #$66 : STA.b $0D
  LDA.b #$34 : STA.b $0C ; Tile GFX

  LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$0B : STA.l $7EC025

  RTL
}

DrawFinalBossIcon:
{
  ; X position
  LDA.b #$0E : STA.l $7EC10B
  LDA.b #$5E : STA.l $7EC10A
  ; Y position
  LDA.b #$04 : STA.l $7EC109
  LDA.b #$68 : STA.l $7EC108
  ; Tile GFX (Skull Icon)
  LDA.b #$66 : STA.b $0D
  LDA.b #$34 : STA.b $0C
  ; Tile Size
  LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$0E : STA.l $7EC025 ; OAM Slot used
  RTL
}

DrawHallOfSecretsIcon:
{
  ; X position
  LDA.b #$0D : STA.l $7EC10B
  LDA.b #$34 : STA.l $7EC10A
  ; Y position
  LDA.b #$03 : STA.l $7EC109
  LDA.b #$0E : STA.l $7EC108
  ; Tile GFX
  LDA.b #$68 : STA.b $0D
  LDA.b #$34 : STA.b $0C
  ; Tile Size
  LDA.b #$00 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$07 : STA.l $7EC025
  RTL
}

DrawPyramidIcon:
{
  ; X position
  LDA.b #$05 : STA.l $7EC10B
  LDA.b #$00 : STA.l $7EC10A
  ; Y position
  LDA.b #$00 : STA.l $7EC109
  LDA.b #$54 : STA.l $7EC108

  LDA.b #$68 : STA.b $0D
  LDA.b #$34 : STA.b $0C ; Tile GFX

  LDA.b #$00 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$07 : STA.l $7EC025
  RTL
}

DrawEonEscapeIcon:
{
  LDA.b #$04 : STA.l $7EC10B
  LDA.b #$F4 : STA.l $7EC10A

  LDA.b #$0B : STA.l $7EC109
  LDA.b #$0E : STA.l $7EC108

  LDA.b #$68 : STA.b $0D
  LDA.b #$36 : STA.b $0C ; Tile GFX

  LDA.b #$00 : STA.b $0B ; 02 = 16x16, 00 = 8x8
  LDA.b #$06 : STA.l $7EC025
  RTL
}

; ---------------------------------------------------------
; Map icon timeline (!ENABLE_MAP_ICON_TIMELINE)
; Light World dungeon markers follow story flags instead of the MapIcon
; counter ($7EF3C7), which several NPCs overwrite out of story order.
; Timeline: Docs/Debugging/Issues/world_map_icons_2026-09-26.md.
;
; Crystal bits: Core/sram.asm !Crystal_* (D1 = $02, D6 = $01, fixed
; 2026-09-26). The "Crystal N" draw blocks below use the same bits.
; ---------------------------------------------------------
!MapTimeline_D1 = !Crystal_D1_MushroomGrotto
!MapTimeline_D2 = !Crystal_D2_TailPalace
!MapTimeline_D3 = !Crystal_D3_KalyxoCastle
!MapTimeline_D4 = !Crystal_D4_ZoraTemple
!MapTimeline_D5 = !Crystal_D5_GlaciaEstate
!MapTimeline_D6 = !Crystal_D6_GoronMines
!MapTimeline_D7 = !Crystal_D7_DragonShip

if !ENABLE_MAP_ICON_TIMELINE == 1
; Entry: A (8-bit) = dungeon number 1-7. Any M/X.
; Exit:  C set = draw the marker, C clear = hide it.
;        A clobbered; X, Y, M/X preserved.
; Rule:  hidden once that dungeon's crystal is set; otherwise shown when
;        its reveal crystal is set. D1 shows once the Maku Tree is met
;        (MapIconDraw checks OOSPROG bit 1 first); D2 shows once Link
;        owns the Ocarina ($7EF34C >= 1, beat 10); D7 shows once Link knows
;        the Song of Soaring ($7EF34C >= 4, beat 22; scawful 2026-09-26).
MapTimeline_ShouldDrawDungeon:
{
  PHP
  REP #$10 : PHX
  SEP #$30
  TAX
  LDA.l Crystals : AND.l .crystal_bit-1, X : BNE .hide
  LDA.l .reveal_after-1, X : BEQ .special
    AND.l Crystals : BNE .show
    BRA .hide
  .special
  CPX.b #$01 : BEQ .show
  LDA.l Flute
  CPX.b #$07 : BEQ .soaring
    CMP.b #$01 : BCS .show   ; D2: Ocarina owned
    BRA .hide
  .soaring
    CMP.b #$04 : BCS .show   ; D7: Song of Soaring learned
  .hide
  REP #$10 : PLX
  PLP : CLC
  RTL
  .show
  REP #$10 : PLX
  PLP : SEC
  RTL

  .crystal_bit
  db !MapTimeline_D1, !MapTimeline_D2, !MapTimeline_D3, !MapTimeline_D4
  db !MapTimeline_D5, !MapTimeline_D6, !MapTimeline_D7
  .reveal_after ; $00 = special case above
  db $00, $00, !MapTimeline_D2, !MapTimeline_D3
  db !MapTimeline_D3, !MapTimeline_D3, $00
}
endif

pushpc

; Removed mirror portal draw and pyramid open code
org $0ABF90
MapIconDraw:
{
  ; .dont_draw_link
  LDA.l $7EC108 : PHA
  LDA.l $7EC109 : PHA
  LDA.l $7EC10A : PHA
  LDA.l $7EC10B : PHA

  .draw_prizes
  LDA.b $8A : AND.b #$40 : BEQ .lwprizes
    LDA.l OOSPROG : AND.b #$02 : BNE .check_pendants
      JSL DrawEonEscapeIcon
      JSR HandleMapDrawIcon
      JMP restore_coords_and_exit
    .check_pendants
    LDA.l OOSPROG : AND.b #$10 : BEQ .check_master_sword
      JSL DrawPowerPendant
      JSR HandleMapDrawIcon

      JSL DrawWisdomPendant
      JSR HandleMapDrawIcon

      JSL DrawCouragePendant
      JSR HandleMapDrawIcon
    .check_master_sword
    LDA.l OOSPROG : AND.b #$20 : BEQ .check_fortress
      JSL DrawMasterSwordIcon
      JSR HandleMapDrawIcon
      JMP restore_coords_and_exit
    .check_fortress
    LDA.l OOSPROG : AND.b #$40 : BEQ .check_final_boss
      JSL DrawFortressOfSecretsIcon
      JSR HandleMapDrawIcon
      JMP restore_coords_and_exit
    .check_final_boss
    LDA.l OOSPROG : AND.b #$80 : BEQ .exit_dw
      JSL DrawFinalBossIcon
      JSR HandleMapDrawIcon
    .exit_dw
      JMP restore_coords_and_exit
  .lwprizes

  if !ENABLE_MAP_ICON_TIMELINE == 1
    ; Hall of Secrets: Maku Tree met (bit 1) until Impa is met there (bit 2).
    LDA.l OOSPROG : AND.b #$06 : CMP.b #$02 : BNE +
  else
    LDA.l OOSPROG : CMP.b #$02 : BNE +
  endif
    JSL DrawHallOfSecretsIcon
    JSR HandleMapDrawIcon
  +
  if !ENABLE_MAP_ICON_TIMELINE == 1
    ; Pyramid: after D3 Kalyxo Castle.
    LDA.l Crystals : AND.b #!MapTimeline_D3 : BEQ .main_quest
  else
    LDA.l OOSPROG : AND.b #$10 : BEQ .main_quest
  endif
    JSL DrawPyramidIcon
    JSR HandleMapDrawIcon_noflash
  .main_quest

  if !ENABLE_MAP_ICON_TIMELINE == 1
    ; Before the Maku Tree meeting only the pre-Maku marker shows.
    LDA.l OOSPROG : AND.b #$02 : BNE .draw_crystal_1
  else
  LDA.l MapIcon : CMP.b #$01 : BEQ .draw_crystal_1
                  CMP.b #$02 : BCS .draw_crystals
  endif
                    JSL DrawEonEscapeIcon
                    JSR HandleMapDrawIcon
                    JMP restore_coords_and_exit

  .draw_crystal_1
  ; Draw Crystal 1
  if !ENABLE_MAP_ICON_TIMELINE == 1
    LDA.b #$01 : JSL MapTimeline_ShouldDrawDungeon : BCC .skip_draw_0
  else
  LDA.l $7EF37A : AND #$02 : BNE .skip_draw_0
  endif
    ; X position
    LDA.b #$00 : STA.l $7EC10B
    LDA.b #$87 : STA.l $7EC10A
    ; Y position
    LDA.b #$04 : STA.l $7EC109
    LDA.b #$01 : STA.l $7EC108
    ; Tile GFX
    LDA.b #$64 : STA.b $0D
    LDA.b #$38 : STA.b $0C
    ; Tile Size
    LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
    LDA.b #$0E : STA.l $7EC025 ; OAM Slot used
    JSR HandleMapDrawIcon
  .skip_draw_0
  if !ENABLE_MAP_ICON_TIMELINE == 0
  JMP restore_coords_and_exit
  endif

  .draw_crystals
  ; Draw Crystal 2
  if !ENABLE_MAP_ICON_TIMELINE == 1
    LDA.b #$02 : JSL MapTimeline_ShouldDrawDungeon : BCC .skip_draw_1
  else
  LDA.l $7EF37A : AND #$10 : BNE .skip_draw_1
  endif
    ; X position (2)
    LDA.b #$1E : STA.l $7EC10B
    LDA.b #$A0 : STA.l $7EC10A
    ; Y position (2)
    LDA.b #$09 : STA.l $7EC109
    LDA.b #$74 : STA.l $7EC108

    LDA.b #$64 : STA.b $0D
    LDA.b #$34 : STA.b $0C ; Tile GFX

    LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
    LDA.b #$08 : STA.l $7EC025

    JSR HandleMapDrawIcon
  .skip_draw_1

  ; Draw Crystal 3
  if !ENABLE_MAP_ICON_TIMELINE == 1
    LDA.b #$03 : JSL MapTimeline_ShouldDrawDungeon : BCC .skip_draw_2
  else
  LDA.l $7EF37A : AND #$40 : BNE .skip_draw_2
  endif
    ; X position
    LDA.b #$08 : STA.l $7EC10B
    LDA.b #$10 : STA.l $7EC10A
    ; Y position
    LDA.b #$04 : STA.l $7EC109
    LDA.b #$0E : STA.l $7EC108

    LDA.b #$64 : STA.b $0D
    LDA.b #$34 : STA.b $0C ; Tile GFX

    LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
    LDA.b #$0D : STA.l $7EC025

    JSR HandleMapDrawIcon
  .skip_draw_2

  ; Draw Crystal 4
  if !ENABLE_MAP_ICON_TIMELINE == 1
    LDA.b #$04 : JSL MapTimeline_ShouldDrawDungeon : BCC .skip_draw_3
  else
  LDA.l $7EF37A : AND #$20 : BNE .skip_draw_3
  endif
    ; X position
    LDA.b #$0E : STA.l $7EC10B
    LDA.b #$5E : STA.l $7EC10A
    ; Y position
    LDA.b #$06 : STA.l $7EC109
    LDA.b #$68 : STA.l $7EC108

    LDA.b #$64 : STA.b $0D
    LDA.b #$3C : STA.b $0C ; Tile GFX

    LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
    LDA.b #$0B : STA.l $7EC025

    JSR HandleMapDrawIcon
  .skip_draw_3

  ; Draw Crystal 5
  if !ENABLE_MAP_ICON_TIMELINE == 1
    LDA.b #$05 : JSL MapTimeline_ShouldDrawDungeon : BCC .skip_draw_4
  else
  LDA.l $7EF37A : AND #$04 : BNE .skip_draw_4
  endif
    ; X position
    LDA.b #$0C : STA.l $7EC10B
    LDA.b #$34 : STA.l $7EC10A
    ; Y position
    LDA.b #$00 : STA.l $7EC109
    LDA.b #$0E : STA.l $7EC108

    LDA.b #$64 : STA.b $0D
    LDA.b #$34 : STA.b $0C ; Tile GFX

    LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
    LDA.b #$09 : STA.l $7EC025

    JSR HandleMapDrawIcon
  .skip_draw_4

  ; Draw Crystal 6
  if !ENABLE_MAP_ICON_TIMELINE == 1
    LDA.b #$06 : JSL MapTimeline_ShouldDrawDungeon : BCC .skip_draw_5
  else
  LDA.l $7EF37A : AND #$01 : BNE .skip_draw_5
  endif
    ; X position (6)
    LDA.b #$0D : STA.l $7EC10B
    LDA.b #$05 : STA.l $7EC10A
    ; Y position (6)
    LDA.b #$0D : STA.l $7EC109
    LDA.b #$09 : STA.l $7EC108

    LDA.b #$64 : STA.b $0D
    LDA.b #$32 : STA.b $0C ; Tile GFX

    LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
    LDA.b #$0A : STA.l $7EC025

    JSR HandleMapDrawIcon
  .skip_draw_5

  ; Draw Crystal 7
  if !ENABLE_MAP_ICON_TIMELINE == 1
    LDA.b #$07 : JSL MapTimeline_ShouldDrawDungeon : BCC .skip_draw_6
  else
  LDA.l $7EF37A : AND #$08 : BNE .skip_draw_6
  endif
    ; X position
    LDA.b #$00 : STA.l $7EC10B
    LDA.b #$F4 : STA.l $7EC10A
    ; Y position
    LDA.b #$0D : STA.l $7EC109
    LDA.b #$0E : STA.l $7EC108

    LDA.b #$64 : STA.b $0D
    LDA.b #$32 : STA.b $0C ; Tile GFX

    LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8
    LDA.b #$0C : STA.l $7EC025

    JSR HandleMapDrawIcon
  .skip_draw_6

  JMP restore_coords_and_exit
}

HandleMapDrawIcon:
{
  ; Timer to make it flash
  LDA.b $1A : AND.b #$10 : BNE .skip_draw
    .noflash ; ALTERNATE ENTRY POINT
    JSR WorldMapIcon_AdjustCoordinate
    LDA.l $7EC025 : TAX
    JSR WorldMap_CalculateOAMCoordinates

    BCC .skip_draw
    LDA.l $7EC025 : TAX
    LDA.b #$02
    JSR WorldMap_HandleSpriteBlink
  .skip_draw
  RTS
}

FixMaskPaletteOnExit:
{
  if !ENABLE_KOROK_POLISH == 1
    ; InitializeTilesets just reloaded the area sprite sheets over the Korok
    ; sheets; clear the loaded flag so a Korok reloads them (korok.asm).
    PHP : SEP #$20 : PHA
    LDA.b #$00 : STA.l $7E0AA5
    PLA : PLP
  endif
  JSL Palette_ArmorAndGloves
  LDA.l $7EC229
  RTL
}

assert pc() <= $0AC387

org $0ABC76 ; @hook module=Overworld
  JSL FixMaskPaletteOnExit

org $0AC589
  RTS

org $0AC38A
restore_coords_and_exit:
{
  PLA : STA.l $7EC10B
  PLA : STA.l $7EC10A
  PLA : STA.l $7EC109
  PLA : STA.l $7EC108
  RTS
}

WorldMap_CalculateOAMCoordinates:

; =========================================================
; 0x0C4000 to 0x0C8000 for the map gfx
; patch a new rom with your map data/gfx
; create a new bin file out of these bytes
; 0AC727 (pc: 054727) to 0AD726 (pc: 055726)  0x1000 bytes

; =========================================================
; LW OVERWORLD MAP
; =========================================================

org $008E54 ;STZ $2115 ; @hook module=Overworld
  JSL DMAOwMap
  RTS

org $00E399 ; @hook module=Overworld
  JSL DMAOwMapGfx
  RTL

; =========================================================
; DW OVERWORLD MAP
; =========================================================
org $008FF3
  RTS ; do nothing during DW update, we'll handle it in the LW routine

org $408000 ; @hook module=Overworld
  LWWorldMap_Tiles:
    incbin world_map/LwMapTileset.bin

  LWWorldMap_Gfx:
    incbin world_map/LwMapGfx.bin

org $418000 ; @hook module=Overworld
  DWWorldMap_Tiles:
    incbin world_map/DwMapTileset.bin

  DWWorldMap_Gfx:
    incbin world_map/DwMapGfx.bin

DMAOwMap:
{
  JSL Palette_ArmorAndGloves
  LDA $8A : AND #$40 : BEQ .LWMAP
    JMP .DWMAP
  .LWMAP

  STZ.w $2115

  LDA.b #LWWorldMap_Tiles>>16
  STA.w $4304

  REP #$20

  LDA.w #$1800
  STA.w $4300

  STZ.b $04
  STZ.b $02

  LDY.b #$01
  LDX.b #$00

  .next_quadrant

    LDA.w #$0020
    STA.b $06

    LDA.l .vram_offset,X
    STA.b $00

    .next_row

      LDA.b $00
      STA.w $2116

      CLC
      ADC.w #$0080
      STA.b $00

      LDA.b $02
      CLC
      ADC.w #LWWorldMap_Tiles
      STA.w $4302

      LDA.w #$0020
      STA.w $4305

      STY.w $420B

      CLC
      ADC.b $02
      STA.b $02

      DEC.b $06
    BNE .next_row

    INC.b $04
    INC.b $04

    LDX.b $04
    CPX.b #$08
  BNE .next_quadrant

  SEP #$20

  RTL

  .vram_offset
    dw $0000, $0020, $1000, $1020

  .DWMAP

    STZ.w $2115

    LDA.b #DWWorldMap_Tiles>>16
    STA.w $4304

    REP #$20

    LDA.w #$1800
    STA.w $4300

    STZ.b $04
    STZ.b $02

    LDY.b #$01
    LDX.b #$00

    .next_quadrant2

      LDA.w #$0020
      STA.b $06

      LDA.l .vram_offset,X
      STA.b $00

      .next_row2

        LDA.b $00
        STA.w $2116

        CLC
        ADC.w #$0080
        STA.b $00

        LDA.b $02
        CLC
        ADC.w #DWWorldMap_Tiles
        STA.w $4302

        LDA.w #$0020
        STA.w $4305

        STY.w $420B

        CLC
        ADC.b $02
        STA.b $02

        DEC.b $06
    BNE .next_row2

    INC.b $04
    INC.b $04

    LDX.b $04
    CPX.b #$08
    BNE .next_quadrant2

    SEP #$20

    RTL
}


DMAOwMapGfx:
{
  LDA $8A : AND #$40 : BNE .DWMAP
    LDA.b #LWWorldMap_Gfx>>16 : STA $02

    LDA.b #$80 : STA $2115

    STZ $2116 : STZ $2117

    REP #$10

    LDY.w #LWWorldMap_Gfx : STY $00

    LDY.w #$0000

    .writeChr

        LDA [$00], Y : STA $2119 : INY
        LDA [$00], Y : STA $2119 : INY
        LDA [$00], Y : STA $2119 : INY
        LDA [$00], Y : STA $2119 : INY
    CPY.w #$4000 : BNE .writeChr

    SEP #$10

    RTL

    .DWMAP

    LDA.b #DWWorldMap_Gfx>>16 : STA $02

    LDA.b #$80 : STA $2115

    STZ $2116 : STZ $2117

    REP #$10

    LDY.w #DWWorldMap_Gfx : STY $00

    LDY.w #$0000

    .writeChr2

        LDA [$00], Y : STA $2119 : INY
        LDA [$00], Y : STA $2119 : INY
        LDA [$00], Y : STA $2119 : INY
        LDA [$00], Y : STA $2119 : INY
    CPY.w #$4000 : BNE .writeChr2

    SEP #$10

    RTL
}

org $0ADC27
  DWPalettes:
    incbin world_map/dw_palette.bin
