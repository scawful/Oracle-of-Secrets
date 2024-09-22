; =========================================================
; World Map Module

org $0AC589
    WorldMapIcon_AdjustCoordinate:

org $0AC51C
    WorldMap_HandleSpriteBlink:

; Map icon
;   0x00 - Red X on castle    | Save zelda
;   0x01 - Red X on Kakariko  | Talk to villagers about elders
;   0x02 - Red X on Eastern   | Talk to Sahasrahla
;   0x03 - Pendants and MS    | Obtain the master sword
;   0x04 - Master sword on LW | Grab the master sword
;   0x05 - Skull on castle    | Kill Agahnim
;   0x06 - Crystal on POD     | Get the first crystal
;   0x07 - Crystals           | Get all 7 crystals
;   0x08 - Skull on GT        | Climb Ganon's Tower
MAPICON         = $7EF3C7

; .wbs tipm
;   p - Palace of Darkness
;   s - Swamp Palace
;   w - Skull Woods
;   b - Thieves' Town
;   i - Ice Palace
;   m - Misery Mire
;   t - Turtle Rock
CRYSTALS        = $7EF37A

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
  RTS
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

pushpc

; Removed mirror portal draw and pyramid open code
org $0ABF90
MapIconDraw:
{
    ; .dont_draw_link
    LDA.l $7EC108
    PHA

    LDA.l $7EC109
    PHA

    LDA.l $7EC10A
    PHA

    LDA.l $7EC10B
    PHA

    ;-----------------------------------

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

    LDA.l $7EF3C7 : CMP.b #$01 : BEQ .hall_of_secrets
                    CMP.b #$02 : BEQ .draw_secret
                    CMP.b #$03 : BCS .draw_crystals

    .hall_of_secrets
    JSL DrawHallOfSecretsIcon
    JSR HandleMapDrawIcon
    JMP restore_coords_and_exit

    .draw_secret ; Pyramid of Power
    JSL DrawPyramidIcon
    JSR HandleMapDrawIcon_noflash
    JMP .skip_draw_6

    .draw_crystals
    ; Draw Crystal 1 
    LDA.l $7EF37A : AND #$02 : BNE .skip_draw_0
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

    ; Draw Crystal 2
    LDA.l $7EF37A : AND #$10 : BNE .skip_draw_1
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
    LDA.l $7EF37A : AND #$40 : BNE .skip_draw_2
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
    LDA.l $7EF37A : AND #$20 : BNE .skip_draw_3
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
    LDA.l $7EF37A : AND #$04 : BNE .skip_draw_4
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
    LDA.l $7EF37A : AND #$01 : BNE .skip_draw_5
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
    LDA.l $7EF37A : AND #$08 : BNE .skip_draw_6
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
    LDA.b $1A
    AND.b #$10
    BNE .skip_draw ; Timer to make it flash
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
  JSL Palette_ArmorAndGloves
  LDA.l $7EC229
  RTL
}

assert pc() <= $0AC387

org $0ABC76
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
; Gfx Notes

; 0x0C4000 to 0x0C8000 for the map gfx 
; patch a new rom with your map data/gfx 
; create a new bin file out of these bytes 
; OverworldMap.asm you can copy everything from start to line 214
; and 264 to 272 if you want palettes in asm too

; 0AC727 (pc: 054727) to 0AD726 (pc: 055726)  0x1000 bytes 

; =========================================================
; LW OVERWORLD MAP
; =========================================================

org $008E54 ;STZ $2115
    JSL DMAOwMap
    RTS

org $00E399 
    JSL DMAOwMapGfx
    RTL

; =========================================================
; DW OVERWORLD MAP
; =========================================================
org $008FF3
    RTS ; do not do anything during the DW update we'll handle it in the LW routine

org $3D8000
    LWWorldMap_Tiles:
    incbin world_map/LwMapTileset.bin

    LWWorldMap_Gfx:
    incbin world_map/LwMapGfx.bin

org $3E8000
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
