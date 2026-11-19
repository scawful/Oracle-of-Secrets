; =========================================================
; Menu v5 Extensions (Bank $54, included by Menu/menu_item_bindings.asm).
; All entry points are JSL/RTL. DBR may be $2D/$2B/$54; tilemap writes use
; explicit $7E1000+ long addressing and local data reads use .l addressing so
; every routine is bank-independent.
;
; Reclaimed UI tiles on HUD Sheet $69 (Data/graphics/menu_icons.json):
;   $012B = Cursor C4 Y-badge (TL, pal 7 green $3D2B)
;   $012C = Cursor C4 X-badge (TL pal 3 blue $2D2C; H-flip TR $6D2C)
;   $012D = Cursor C4 thin rounded frame corner (H/V/HV flip for TR/BL/BR)
;   $012E = Cursor C4 thin horizontal frame line (V-flip for bottom)
;   $012F = Cursor C4 thin vertical frame line (H-flip for right)
;   $013F = Cursor C4 bold active L-bracket corner (pal 5 gold $353F)
;   $014F = Centered brown wood vertical divider ($214F)
;   $017A = Centered brown wood horizontal divider ($217A)
;   $017B = Mini-map 8x8 terrain cell block (palette | $217B)
;   $016D = Mini-map Link marker pin ($256D red / $356D gold)
; =========================================================

; Constants (!C4_*, !Menu_DivV/H) are defined at top of Menu/menu_item_bindings.asm.

; ---------------------------------------------------------
; Draw 12-tile Cursor C4 thin rounded frame around an item box.
; In: M/X=16, A = priority+palette bits (e.g. $3C00 green, $2C00 blue, $2400 red),
;     X = cursor offset (as Menu_ItemCursorPositions; TL = $7E1108+X).
; Keeps X; clobbers A.
Menu_C4_DrawFrame_Near:
{
  PHA
  ORA.w #!C4_Corner
  STA.l $7E1108, X                      ; TL
  ORA.w #$4000 : STA.l $7E110E, X       ; TR (H-flip)
  ORA.w #$8000 : STA.l $7E11CE, X       ; BR (HV-flip)
  EOR.w #$4000 : STA.l $7E11C8, X       ; BL (V-flip)
  LDA 1,S : ORA.w #!C4_Horiz
  STA.l $7E110A, X : STA.l $7E110C, X   ; Top edges
  ORA.w #$8000
  STA.l $7E11CA, X : STA.l $7E11CC, X   ; Bottom edges (V-flip)
  PLA : ORA.w #!C4_Vert
  STA.l $7E1148, X : STA.l $7E1188, X   ; Left edges
  ORA.w #$4000
  STA.l $7E114E, X : STA.l $7E118E, X   ; Right edges (H-flip)
  RTS
}

; Draw 4 bold Gold C4 active L-brackets around an item box.
; In: M/X=16, X = cursor offset (TL = $7E1108+X). Keeps X; clobbers A.
Menu_C4_DrawActiveL_Near:
{
  LDA.w #!C4_ActiveL
  STA.l $7E1108, X                      ; TL
  ORA.w #$4000 : STA.l $7E110E, X       ; TR
  ORA.w #$8000 : STA.l $7E11CE, X       ; BR
  EOR.w #$4000 : STA.l $7E11C8, X       ; BL
  RTS
}

; Long entry for Equipment / Quest Songs / Map Spoils equipped marker box.
; In: M/X=16, A = priority+palette bits (e.g. $2400 red),
;     X = DrawMenuItem offset (box TL = $7E10C6+X = $7E1108+(X-$42)).
Menu_C4_DrawEquipBox_Long:
{
  PHA : PHX
  TXA : SEC : SBC.w #$0042 : TAX
  LDA 3,S
  JSR Menu_C4_DrawFrame_Near
  PLX : PLA
  RTL
}

; Long entry for Equipment / Quest Songs / Map Spoils active Gold L-bracket cursor.
; In: M/X=16, X = DrawMenuItem offset (box TL = $7E10C6+X).
Menu_C4_DrawEquipCursor_Long:
{
  PHX
  TXA : SEC : SBC.w #$0042 : TAX
  JSR Menu_C4_DrawActiveL_Near
  PLX
  RTL
}

; =========================================================
; Special Overworld ($80-$BF) Area Names for Map Page Header (row 9).
; Compact 64-byte index table + 17 unique 16-char names (576 bytes total).
; Grounded in Overworld/lyra_edge_guard.asm and Docs/Technical/terminology_glossary.md.
; In: M/X=16, A = $8A ($80..$BF). Out: draws centered name at $7E1000+menu_offset(9,0).
MenuMap_SpecialAreaName_Long:
{
  SEC : SBC.w #$0080
  CMP.w #$0040 : BCS .done
  TAX
  LDA.l .map_index, X : AND.w #$00FF
  ASL #5 : TAX                          ; X = name_id * 32 (byte offset into .names)
  ; Find trimmed length from right (skip trailing $20F5 blanks)
  LDY.w #$001E
  STX.b $00
.trim
  PHX
  TYA : CLC : ADC.b $00 : TAX
  LDA.l .names, X
  PLX
  CMP.w #$20F5 : BNE .found
  DEY #2 : BPL .trim
  BRA .done
.found
  INY #2 : STY.b $02                    ; byte length
  LDA.w #$0040 : SEC : SBC.b $02 : LSR : AND.w #$FFFE
  CLC : ADC.w #menu_offset(9,0) : TAX   ; dest offset in $7E1000
  LDY.w #$0000
.copy
  PHX
  TYA : CLC : ADC.b $00 : TAX
  LDA.l .names, X
  PLX
  STA.l $7E1000, X
  INX #2 : INY #2 : CPY.b $02 : BCC .copy
.done
  RTL

  ; 0=TAIL_WOODS, 1=KOROK_COVE, 2=EAST_GARRISON, 3=SKY_ISLANDS, 4=SKY_TOWER,
  ; 5=ZORA_SANCTUARY, 6=SHRINE_WISDOM, 7=NORTH_REEF, 8=LYRA_SEA, 9=ZORA_QUAY,
  ; 10=KALYXO_COAST, 11=ZORA_COAST, 12=SHRINE_COURAGE, 13=DEKU_COAST,
  ; 14=GORON_DESERT, 15=TOWER_ISLAND, 16=SNOW_ISLAND
.map_index
  db  0,  1,  1,  2,  3,  3,  3,  4     ; $80-$87
  db  8,  1,  1,  2,  3,  3,  3,  3     ; $88-$8F
  db  5,  6,  7,  8,  8,  8,  8,  8     ; $90-$97
  db  5,  9, 10,  8,  8,  8,  8,  8     ; $98-$9F
  db 11, 11,  8,  8,  8,  8, 12, 12     ; $A0-$A7
  db 13, 13,  8,  8,  8,  8, 12, 12     ; $A8-$AF
  db 14, 14,  8,  8,  8, 15,  8,  8     ; $B0-$B7
  db 14, 14,  8,  8,  8, 15, 16, 16     ; $B8-$BF

pushtable
  'A' = $2550
  'B' = $2551
  'C' = $2552
  'D' = $2553
  'E' = $2554
  'F' = $2555
  'G' = $2556
  'H' = $2557
  'I' = $2558
  'J' = $2559
  'K' = $255A
  'L' = $255B
  'M' = $255C
  'N' = $255D
  'O' = $255E
  'P' = $255F
  'Q' = $2560
  'R' = $2561
  'S' = $2562
  'T' = $2563
  'U' = $2564
  'V' = $2565
  'W' = $2566
  'X' = $2567
  'Y' = $2568
  'Z' = $2569
  '_' = $20F5
.names
  dw "TAIL_WOODS______" ;  0
  dw "KOROK_COVE______" ;  1
  dw "EAST_GARRISON___" ;  2
  dw "SKY_ISLANDS_____" ;  3
  dw "SKY_TOWER_______" ;  4
  dw "ZORA_SANCTUARY__" ;  5
  dw "SHRINE_WISDOM___" ;  6
  dw "NORTH_REEF______" ;  7
  dw "LYRA_SEA________" ;  8
  dw "ZORA_QUAY_______" ;  9
  dw "KALYXO_COAST____" ; 10
  dw "ZORA_COAST______" ; 11
  dw "SHRINE_COURAGE__" ; 12
  dw "DEKU_COAST______" ; 13
  dw "GORON_DESERT____" ; 14
  dw "TOWER_ISLAND____" ; 15
  dw "SNOW_ISLAND_____" ; 16
pulltable
}

; =========================================================
; Runtime 8x8 Overworld Mini-Map on Map & Spoils Page (rows 11..18, cols 6..13).
; Renders terrain silhouette for Light World ($00-$3F), Dark World / Eon Abyss
; ($40-$7F), or Special Overworld / Lyra Sea ($80-$BF) using tile $17B, and
; highlights Link's current screen ($8A & $3F) with pulsing marker $16D.
; Indoors ($1B != 0) renders a muted gray 8x8 grid with a gold entrance marker.
; In: any M/X. Out: SEP #$30. Clobbers A/X/Y/$00-$07.
MenuMap_DrawMiniMap_Long:
{
  SEP #$30
  ; Pick terrain table offset ($00 = LW, $40 = DW, $80 = Special OW)
  LDA.b $8A : AND.b #$3F : STA.b $04    ; $04 = Link cell index 0..63
  LDA.b $8A : CMP.b #$80 : BCS .special
  CMP.b #$40 : BCS .abyss
  LDA.b #$00 : BRA .world_ok
.abyss
  LDA.b #$40 : BRA .world_ok
.special
  LDA.b #$80
.world_ok
  STA.b $05                             ; $05 = world table base (0 / 64 / 128)
  LDA.b $1B : STA.b $06                 ; $06 = indoors flag

  ; Iterate 64 cells: Y = cell 0..63, row = Y>>3, col = Y&7.
  ; Dest tilemap offset = menu_offset(11 + row, 6 + col) = $02CC + row*$40 + col*2.
  LDY.b #$00
.cell_loop
  TYA : CMP.b $04 : BEQ .is_link
  LDA.b $06 : BNE .indoor_cell
  TYA : CLC : ADC.b $05 : TAX
  LDA.l .terrain, X : ASL : TAX
  REP #$20
  LDA.l .palettes, X
  BRA .store_tile
.indoor_cell
  REP #$20
  LDA.w #$317B                          ; muted gray grid cell indoors
  BRA .store_tile
.is_link
  LDA.w $0207 : AND.b #$10 : BNE .link_gold
  REP #$20
  LDA.w #$256D                          ; bright red/white Link pin
  BRA .store_tile
.link_gold
  REP #$20
  LDA.w #$356D                          ; bright gold/white pulse
.store_tile
  PHA                                   ; save tile word
  ; Compute X = menu_offset(11 + (Y>>3), 6 + (Y&7))
  TYA : AND.w #$0038 : ASL #3 : STA.b $00 ; row * 64
  TYA : AND.w #$0007 : ASL : CLC : ADC.b $00
  CLC : ADC.w #menu_offset(11,6)
  REP #$10
  TAX
  PLA
  STA.l $7E1000, X
  SEP #$30
  INY : CPY.b #$40 : BCC .cell_loop
  RTL

  ; Terrain palette words for MiniMap_Cell ($017B):
  ; 0 = water/sea (blue $2D7B), 1 = grass/land (green $3D7B),
  ; 2 = desert/beach/mountain (tan $297B), 3 = landmark/castle/shrine (gold $357B),
  ; 4 = lava/fortress (red $257B), 5 = abyss/shadow/sky (gray $317B)
.palettes
  dw $2D7B, $3D7B, $297B, $357B, $257B, $317B

  ; 64-byte terrain grids (row-major 8x8):
.terrain
  ; World 0: Light World — Kalyxo Island ($00-$3F)
  db 1,1,3,1, 2,2,2,2 ; $00-$07 Ranch, Pyramid, Land of Tree, Snow Mountain
  db 1,1,1,3, 3,1,3,5 ; $08-$0F Ranch, Inn, Kalyxo Castle, Potion, Hall of Secrets, Cemetery
  db 1,1,1,3, 3,2,1,3 ; $10-$17 Toadstool Woods, Crossroads, Castle, Mountainside, Shrine
  db 1,1,1,3, 1,1,0,0 ; $18-$1F Toadstool Woods, Crossroads, Castle, Sunken City
  db 1,1,2,3, 3,1,0,0 ; $20-$27 Woods, Swordsmiths, Wayward Village, Sunken City
  db 1,1,1,3, 3,1,1,3 ; $28-$2F Woods, Village Road, Wayward Village, Valley, Tail Palace
  db 0,0,2,2, 2,2,2,2 ; $30-$37 Dragon Ship, Beaches, Garo Desert
  db 0,0,0,2, 2,0,2,2 ; $38-$3F Dragon Ship, Lost Sea, Loom Beach/Waterfall, Garo Desert

  ; World 1: Dark World — Eon Abyss ($40-$7F)
  db 3,3,3,4, 4,4,4,4 ; $40-$47 Temporal Gate, Pyramid of Eons, Lava Lands
  db 3,3,0,4, 4,5,4,4 ; $48-$4F Temporal Gate, Lupo Waterfall, Fortress, Lupo Mtn, Lava
  db 3,5,5,4, 4,5,4,4 ; $50-$57 Shrine Courage, Abyss, Fortress, Lupo Mtn, Lava
  db 5,5,5,5, 5,5,5,5 ; $58-$5F Abyss / Lupo Mtn
  db 5,5,5,1, 1,5,5,5 ; $60-$67 Abyss, Wisdom Swamp, Lupo Mtn
  db 5,5,5,1, 1,5,5,5 ; $68-$6F Abyss, Wisdom Swamp
  db 0,0,0,0, 0,0,2,2 ; $70-$77 Underwater, Abyss Beach
  db 0,0,0,0, 0,0,2,2 ; $78-$7F Underwater, Abyss Beach

  ; World 2: Special Overworld — Lyra Sea / East Kalyxo / Sky Islands ($80-$BF)
  db 1,1,1,3, 5,5,5,3 ; $80-$87 Tail Woods, Korok Cove, Garrison, Sky Islands, Sky Tower
  db 5,1,1,3, 5,5,5,5 ; $88-$8F Curtain, Korok Cove, Garrison, Sky Islands
  db 0,3,0,0, 0,0,0,0 ; $90-$97 Sea Zora, Shrine Wisdom, North Reef, Sea/Clouds
  db 0,0,1,0, 0,0,0,0 ; $98-$9F Sea Zora, Zora Quay, Kalyxo Coast, Sea/Clouds
  db 1,1,0,1, 0,0,3,3 ; $A0-$A7 Zora Coast, Lyra Sea, Shrine of Courage
  db 1,1,1,1, 1,1,3,3 ; $A8-$AF Deku Coast, Islands, Shrine of Courage
  db 2,2,0,1, 1,3,0,0 ; $B0-$B7 Goron Desert, Lyra Sea, Crescent, Tower Island
  db 2,2,0,1, 1,3,5,5 ; $B8-$BF Goron Desert, Harbor, Crescent, Tower, Snow Island
}

; =========================================================
; Select Context Help Popup (State !MENU_STATE_HELP_POPUP = $09).
; Replaces static painted button-hint bars across all 4 pages.
; Triggered by Select ($F4 bit 5 = $20) on Items / Equipment / Quest / Map.
; Dismissed by Select ($F4 bit 5) or B ($F4 bit 7); Start ($F4 bit 4) closes menu.
; Active page is identified directly from $E5 (0=Items) + MenuScrollLevelH
; ($00=Quest, $20=Equipment, $40=Map), using zero new WRAM bytes.
; =========================================================

MenuHelp_Draw_Long:
{
  JSL Menu_DrawBackground_Long
  REP #$30
  ; Title "    HELP    " at row 6, cols 10..21 ($1194)
  LDX.w #$0016
.title
  LDA.l .title_txt, X : STA.l $7E1194, X
  DEX #2 : BPL .title

  ; Horizontal divider at row 11, cols 6..25 ($1000+menu_offset(11,6))
  LDX.w #$0026
  LDA.w #!Menu_DivH
.div
  STA.l $7E1000+menu_offset(11,6), X
  DEX #2 : BPL .div

  ; Footer "__B.SEL:BACK__" at $1692 (14 tiles)
  LDX.w #$001A
.footer
  LDA.l .footer_txt, X : STA.l $7E1692, X
  DEX #2 : BPL .footer

  ; Determine active page index 0..3:
  ;   0 = Items ($E5 == 0)
  ;   1 = Equipment ($E5 != 0, MenuScrollLevelH == $20)
  ;   2 = Quest ($E5 != 0, MenuScrollLevelH == $00)
  ;   3 = Map & Spoils ($E5 != 0, MenuScrollLevelH == $40)
  SEP #$20
  LDA.b $E5 : BEQ .page_items
  LDA.w MenuScrollLevelH : AND.b #$FE
  CMP.b #$20 : BEQ .page_equip
  CMP.b #$40 : BEQ .page_map
  LDA.b #$02 : BRA .have_page
.page_items
  LDA.b #$00 : BRA .have_page
.page_equip
  LDA.b #$01 : BRA .have_page
.page_map
  LDA.b #$03
.have_page
  REP #$30
  AND.w #$00FF : ASL : TAX
  LDA.l .page_offsets, X : STA.b $00    ; byte offset into .items_lines

  ; Draw 6 lines of 18 tiles (36 bytes each) at rows 10, 13, 15, 17, 19, 21, col 7
  LDY.w #$0000                          ; line index * 2 (0..10)
.line_loop
  PHY
  TYX
  LDA.l .line_dests, X : TAX            ; dest offset in $7E1000
  LDY.w #$0000
.char_loop
  PHX
  LDA.b $00 : TAX
  LDA.l .items_lines, X
  PLX
  STA.l $7E1000, X
  INC.b $00 : INC.b $00
  INX #2 : INY #2 : CPY.w #$0024 : BCC .char_loop
  PLY
  INY #2 : CPY.w #$000C : BCC .line_loop

  SEP #$30
  RTL

.line_dests
  dw menu_offset(10,7)
  dw menu_offset(13,7)
  dw menu_offset(15,7)
  dw menu_offset(17,7)
  dw menu_offset(19,7)
  dw menu_offset(21,7)

.page_offsets
  dw 0, 216, 432, 648

pushtable
  'A' = $2550
  'B' = $2551
  'C' = $2552
  'D' = $2553
  'E' = $2554
  'F' = $2555
  'G' = $2556
  'H' = $2557
  'I' = $2558
  'J' = $2559
  'K' = $255A
  'L' = $255B
  'M' = $255C
  'N' = $255D
  'O' = $255E
  'P' = $255F
  'Q' = $2560
  'R' = $2561
  'S' = $2562
  'T' = $2563
  'U' = $2564
  'V' = $2565
  'W' = $2566
  'X' = $2567
  'Y' = $2568
  'Z' = $2569
  '.' = $256A
  ':' = $256B
  '_' = $20F5
.title_txt
  dw "____HELP____"
.footer_txt
  dw "__B.SEL:BACK__"

; 18 tiles per line, 6 lines per page (UI control labels only)
.items_lines
  dw "__ITEMS_CONTROLS__"
  dw "A.Y_:_EQUIP_Y_ITEM"
  dw "X___:_EQUIP_X_ITEM"
  dw "L.R_:_SWITCH_PAGE_"
  dw "B___:_CLOSE_MENU__"
  dw "SEL_:_CLOSE_HELP__"

.equip_lines
  dw "__EQUIPMENT_HELP__"
  dw "A.Y_:_EQUIP_GEAR__"
  dw "A.Y_:_MASK_OR_RING"
  dw "L.R_:_SWITCH_PAGE_"
  dw "B___:_CLOSE_MENU__"
  dw "SEL_:_CLOSE_HELP__"

.quest_lines
  dw "__QUEST_CONTROLS__"
  dw "A.Y_:_SET_OCARINA_"
  dw "DPAD:_PICK_SONG___"
  dw "L.R_:_SWITCH_PAGE_"
  dw "B___:_CLOSE_MENU__"
  dw "SEL_:_CLOSE_HELP__"

.map_lines
  dw "_MAP_SPOILS_HELP__"
  dw "A.Y_:_OPEN_MAP____"
  dw "A___:_USE_SPOIL___"
  dw "L.R_:_SWITCH_PAGE_"
  dw "B___:_CLOSE_MENU__"
  dw "SEL_:_CLOSE_HELP__"
pulltable
}
