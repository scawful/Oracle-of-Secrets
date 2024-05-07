; 0x0C4000 to 0x0C8000 for the map gfx so you patch a new rom with your map data/gfx and you create a new bin file out of these bytes 
; OverworldMap.asm you can copy everything from start to line 214 i think
; and 264 to 272 if you want palettes in asm too

; 0AC727 (pc: 054727)
; to 0AD726 (pc: 055726) 
; it should be 0x1000 bytes big
; ==============================================================================
; LW OVERWORLD MAP
; ==============================================================================

org $008E54 ;STZ $2115
    JSL DMAOwMap
    RTS

org $00E399 
    JSL DMAOwMapGfx
    RTL

; ==============================================================================
; DW OVERWORLD MAP
; ==============================================================================
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

org $0AC589
    WorldMapIcon_AdjustCoordinate:

org $0AC51C
    WorldMap_HandleSpriteBlink:

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

;Removed mirror portal draw code

;Removed pyramid open code?

;---------------------------------------------------------------------------------------------------

    .draw_prizes
    LDA.b $8A : AND.b #$40 : BEQ .lwprizes
        ; X position
        LDA.b #$00 : STA.l $7EC10B
        LDA.b #$89 : STA.l $7EC10A ; Upper nybble control Zoomed low X pos
        ; Y position
        LDA.b #$00 : STA.l $7EC109
        LDA.b #$E4 : STA.l $7EC108 ; Upper nybble control Zoomed low Y pos
        ; Tile GFX
        LDA.b #$66 : STA.b $0D
        LDA.b #$34 : STA.b $0C
        ; Tile Size
        LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8 
        LDA.b #$0E : STA.l $7EC025 ; OAM Slot used

        JSR HandleMapDrawIcon

        JMP restore_coords_and_exit

    .lwprizes

    ; Draw Amulet 1
    LDA.l $7EF374 : AND #$04 : BNE .skip_draw_0
        ; X position
        LDA.b #$0E : STA.l $7EC10B
        LDA.b #$3E : STA.l $7EC10A
        ; Y position
        LDA.b #$04 : STA.l $7EC109
        LDA.b #$68 : STA.l $7EC108
        ; Tile GFX
        LDA.b #$60 : STA.b $0D
        LDA.b #$38 : STA.b $0C
        ; Tile Size
        LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8 
        LDA.b #$0E : STA.l $7EC025 ; OAM Slot used
        JSR HandleMapDrawIcon

    .skip_draw_0


    ; Draw Amulet 2
    LDA.l $7EF374 : AND #$02 : BNE .skip_draw_1
        ; X position
        LDA.b #$0D : STA.l $7EC10B
        LDA.b #$05 : STA.l $7EC10A
        ; Y position
        LDA.b #$0D : STA.l $7EC109
        LDA.b #$09 : STA.l $7EC108

        LDA.b #$60 : STA.b $0D
        LDA.b #$34 : STA.b $0C ; Tile GFX

        LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8 
        LDA.b #$0D : STA.l $7EC025

        JSR HandleMapDrawIcon

    .skip_draw_1

    ; Draw Amulet 3
    LDA.l $7EF374 : AND #$01 : BNE .skip_draw_2
        ; X position
        LDA.b #$09 : STA.l $7EC10B
        LDA.b #$34 : STA.l $7EC10A
        ; Y position
        LDA.b #$00 : STA.l $7EC109
        LDA.b #$0E : STA.l $7EC108

        LDA.b #$60 : STA.b $0D
        LDA.b #$32 : STA.b $0C ; Tile GFX

        LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8 
        LDA.b #$0C : STA.l $7EC025

        JSR HandleMapDrawIcon

    .skip_draw_2


    ; Draw Amulet 4
    ; LDA.l $7EF37A : AND #$01 : BNE .skip_draw_3
    ;     ; X position
    ;     LDA.b #$00 : STA.l $7EC10B
    ;     LDA.b #$87 : STA.l $7EC10A
    ;     ; Y position
    ;     LDA.b #$06 : STA.l $7EC109
    ;     LDA.b #$01 : STA.l $7EC108

    ;     LDA.b #$60 : STA.b $0D
    ;     LDA.b #$3C : STA.b $0C ; Tile GFX

    ;     LDA.b #$02 : STA.b $0B ; 02 = 16x16, 00 = 8x8 
    ;     LDA.b #$0B : STA.l $7EC025

    ;     JSR HandleMapDrawIcon

    ; .skip_draw_3

    ; ; Draw Flute X
    ; LDA.l $7EF34C : CMP #$01 : BNE .skip_draw_flute
    ;     ; X position
    ;     LDA.b #$09 : STA.l $7EC10B
    ;     LDA.b #$00 : STA.l $7EC10A
    ;     ; Y position
    ;     LDA.b #$02 : STA.l $7EC109
    ;     LDA.b #$74 : STA.l $7EC108

    ;     LDA.b #$68 : STA.b $0D
    ;     LDA.b #$3C : STA.b $0C ; Tile GFX

    ;     LDA.b #$00 : STA.b $0B ; 02 = 16x16, 00 = 8x8 
    ;     LDA.b #$0A : STA.l $7EC025

    ;     JSR HandleMapDrawIcon_noflash

    ; .skip_draw_flute

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

org $0ABC76
  JSL FixMaskPaletteOnExit

; warnpc $0AC387

org $0AC589
  RTS

org $0AC38A
{
    restore_coords_and_exit:
    PLA
    STA.l $7EC10B

    PLA
    STA.l $7EC10A

    PLA
    STA.l $7EC109

    PLA
    STA.l $7EC108

    RTS
}

WorldMap_CalculateOAMCoordinates: