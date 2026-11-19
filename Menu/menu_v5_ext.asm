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
;   $0139 = Portal Rod PR5 45-deg transposed BR wing ($2539, opaque black BG)
;   $013F = Cursor C4 bold active L-bracket corner (pal 5 gold $353F)
;   $014F = Centered brown wood vertical divider ($214F, HUD X|Y)
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
; Shared Area Name Pointer Resolver (Bank $54).
; Resolves a 24-bit pointer in $00..$02 to the 16-tile (32-byte) location name
; for Light World ($00-$3F), Dark World / Abyss ($40-$7F), Special Overworld
; ($80-$BF), or indoors ($1B != 0, indexed by 16-bit $A0).
; In: M/X=16. Out: M/X=16, C set = valid 24-bit ptr in $00..$02, C clear = invalid.
; Clobbers A, X, $00-$02.
MenuMap_ResolveAreaNamePtr_Near:
{
  LDA.b $1B : AND.w #$00FF : BNE .indoors
  LDA.b $8A : AND.w #$00FF : CMP.w #$0080 : BCC .lw_dw
  CMP.w #$00C0 : BCS .invalid
  SEC : SBC.w #$0080 : TAX
  LDA.l SpecialOverworldLocationNameIndex, X : AND.w #$00FF
  ASL #5 : CLC : ADC.w #SpecialOverworldLocationNames : STA.b $00
  SEP #$20
  LDA.b #SpecialOverworldLocationNames>>16 : STA.b $02
  REP #$20
  SEC : RTS
.invalid
  CLC : RTS
.lw_dw
  ASL #5 : CLC : ADC.w #OverworldLocationNames : STA.b $00
  SEP #$20
  LDA.b #OverworldLocationNames>>16 : STA.b $02
  REP #$20
  SEC : RTS
.indoors
  LDA.b $A0 : ASL #5 : CLC : ADC.w #DungeonLocationNames : STA.b $00
  SEP #$20
  LDA.b #DungeonLocationNames>>16 : STA.b $02
  REP #$20
  SEC : RTS
}

; Long entry for Menu/menu_text.asm DrawLocationName (Bank $2D trampoline).
; Writes the 16-tile (32-byte) location name to $7E12CC for LW ($00-$3F),
; Abyss DW ($40-$7F), Special Overworld ($80-$BF), and indoors ($1B != 0).
; Preserves $00-$03 so callers expecting original DrawLocationName scratch
; safety stay unaffected. Out: M/X=16.
Menu_DrawLocationName_Long:
{
  REP #$30
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  JSR MenuMap_ResolveAreaNamePtr_Near
  BCC .done
  LDY.w #$0000
.copy
  LDA.b [$00], Y
  TYX
  STA.l $7E12CC, X
  INY #2 : CPY.w #$0020 : BCC .copy
.done
  PLA : STA.b $02
  PLA : STA.b $00
  RTL
}

; =========================================================
; Map & Spoils Area Name Renderer (right of 8x8 Mini-Map: cols 15..26, rows 11..12).
; Handles Light World ($00-$3F), Abyss ($40-$7F), Special Overworld ($80-$BF),
; and indoors ($1B != 0). Cleanly wraps names > 12 chars onto 2 centered lines
; at the last word boundary so no name ever clips the right frame border (col 27).
; Grounded in Docs/World/LocationRegistry.md, Docs/Dev/Planning/overworld.json,
; Overworld/special_overworld/edge_guard.asm, and live rev5 Special OW layout.
; In/out: M/X=16. Uses $00-$09.
MenuMap_DrawAreaNameRight_Long:
{
  REP #$30
  JSR MenuMap_ResolveAreaNamePtr_Near
  BCC .done_early

  ; Trim trailing $20F5 spaces from 16-tile (32-byte) string.
  LDY.w #$001E
.trim
  LDA.b [$00], Y : CMP.w #$20F5 : BNE .found_len
  DEY #2 : BPL .trim
.done_early
  RTL                                   ; completely blank or invalid name
.found_len
  INY #2 : STY.b $04                    ; $04 = total byte length (2..32)
  CPY.w #$001A : BCS .two_lines         ; >= 26 bytes (>= 13 tiles) -> wrap

  ; Single line on row 11, centered within cols 15..26 (12 tiles = 24 bytes).
  LDA.w #$0018 : SEC : SBC.b $04 : LSR : AND.w #$FFFE
  CLC : ADC.w #menu_offset(11,15) : TAX
  LDY.w #$0000
.copy1
  LDA.b [$00], Y : STA.l $7E1000, X
  INX #2 : INY #2 : CPY.b $04 : BCC .copy1
  RTL

.two_lines
  ; Scan backwards from char 12 (byte $18) to char 1 (byte $02) for word boundary.
  LDY.w #$0018
.find_space
  LDA.b [$00], Y : CMP.w #$20F5 : BEQ .split_at_y
  DEY #2 : CPY.w #$0002 : BCS .find_space
  ; No space found in first 12 chars: defensive split at 12 chars.
  LDA.w #$0018 : STA.b $06 : STA.b $08
  BRA .have_split
.split_at_y
  STY.b $06                             ; $06 = line 1 byte length
  INY #2 : STY.b $08                    ; $08 = line 2 start offset
.have_split
  ; Line 1 on row 11, centered in cols 15..26.
  LDA.w #$0018 : SEC : SBC.b $06 : LSR : AND.w #$FFFE
  CLC : ADC.w #menu_offset(11,15) : TAX
  LDY.w #$0000
.copy_l1
  LDA.b [$00], Y : STA.l $7E1000, X
  INX #2 : INY #2 : CPY.b $06 : BCC .copy_l1

  ; Line 2 on row 12, centered in cols 15..26 (clamped to <= 12 tiles).
  LDA.b $04 : SEC : SBC.b $08 : BEQ .done : BMI .done
  CMP.w #$001A : BCC .len2_ok
  LDA.w #$0018
.len2_ok
  STA.b $06                             ; $06 = line 2 byte length
  CLC : ADC.b $08 : STA.b $04           ; $04 = line 2 end offset
  LDA.w #$0018 : SEC : SBC.b $06 : LSR : AND.w #$FFFE
  CLC : ADC.w #menu_offset(12,15) : TAX
  LDY.b $08
.copy_l2
  LDA.b [$00], Y : STA.l $7E1000, X
  INX #2 : INY #2 : CPY.b $04 : BCC .copy_l2
.done
  RTL
}

; Special Overworld ($80-$BF) 64-entry location index + 17 unique 16-char names.
; Kept in Bank $54 so Bank $2D headroom stays untouched.
; 0=FOREST_GLADE, 1=KOROK_COVE, 2=ROYAL_GARRISON, 3=SKY_ISLANDS, 4=SKY_TOWER,
; 5=SEA_ZORA_TEMPLE, 6=SHRINE_OF_WISDOM, 7=ZORA_COAST, 8=LYRA_SEA,
; 9=ZORA_LAGOON, 10=ZORA_QUAY, 11=COURAGE_ISLAND, 12=DEKU_GROVE,
; 13=GORON_COAST, 14=CRESCENT_ATOLL, 15=PIRATE_SHIP, 16=FROST_GLACIER
SpecialOverworldLocationNameIndex:
.map_index
  db  0,  1,  1,  2,  3,  3,  3,  4     ; $80-$87
  db  0,  1,  1,  2,  3,  3,  3,  3     ; $88-$8F
  db  5,  6,  7,  8,  8,  8,  8,  8     ; $90-$97
  db  9, 10,  8,  8,  8,  8,  8,  8     ; $98-$9F
  db  7,  7,  8,  8,  8,  8, 11, 11     ; $A0-$A7
  db 12, 12,  8,  8,  8,  8, 11, 11     ; $A8-$AF
  db 13, 13,  8, 14, 14, 15,  8,  8     ; $B0-$B7
  db 13, 13,  8, 14, 14, 15, 16, 16     ; $B8-$BF

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
SpecialOverworldLocationNames:
.names
  dw "FOREST_GLADE____" ;  0: $80, $88
  dw "KOROK_COVE______" ;  1: $81/$82/$89/$8A (64x64)
  dw "ROYAL_GARRISON__" ;  2: $83/$8B (32x64)
  dw "SKY_ISLANDS_____" ;  3: $84-$86, $8C-$8F
  dw "SKY_TOWER_______" ;  4: $87
  dw "SEA_ZORA_TEMPLE_" ;  5: $90
  dw "SHRINE_OF_WISDOM" ;  6: $91
  dw "ZORA_COAST______" ;  7: $92, $A0/$A1 (64x32)
  dw "LYRA_SEA________" ;  8: $93-$97, $9A-$9F, $A2-$A5, $AA-$AD, $B2, $B6-$B7, $BA
  dw "ZORA_LAGOON_____" ;  9: $98
  dw "ZORA_QUAY_______" ; 10: $99
  dw "COURAGE_ISLAND__" ; 11: $A6/$A7/$AE/$AF (64x64)
  dw "DEKU_GROVE______" ; 12: $A8/$A9 (64x32)
  dw "GORON_COAST_____" ; 13: $B0/$B1/$B8/$B9 (64x64)
  dw "CRESCENT_ATOLL__" ; 14: $B3/$B4/$BB/$BC (64x64)
  dw "PIRATE_SHIP_____" ; 15: $B5/$BD (32x64)
  dw "FROST_GLACIER___" ; 16: $BE/$BF (64x32)
pulltable

; =========================================================
; Runtime 8x8 Overworld Mini-Map on Map & Spoils Page (rows 11..18, cols 6..13).
; Renders terrain silhouette for Light World ($00-$3F), Dark World / Eon Abyss
; ($40-$7F), or Special Overworld / Lyra Sea ($80-$BF) using tile $17B.
; Outdoors ($1B == 0): resolves the active map's parent and area size
; (0=Small 1x1, 1=Large 2x2, 2=Wide 2x1, 3=Tall 1x2) and highlights ALL cells
; in the footprint as a unified pulsing shape (outer-framed $257B/$357B with
; per-quadrant H/V bevel flips), while Link's active sub-quadrant cell (from
; ($7E0700 & $7E) >> 1 when inside the footprint, else $8A & $3F) displays the
; pulsing Link marker pin ($256D/$356D).
; Indoors ($1B != 0) renders a muted gray 8x8 grid with a single entrance pin.
; In: any M/X. Out: SEP #$30. Clobbers A/X/Y/$00-$0B.
MenuMap_DrawMiniMap_Long:
{
  SEP #$30
  ; Default single-cell state: c0 = $8A & $3F, c1/c2/c3 = $FF, link_cell = c0.
  LDA.b $8A : AND.b #$3F : STA.b $04    ; $04 = c0 (parent cell 0..63)
  STA.b $0A                             ; $0A = Link active sub-quadrant cell
  LDA.b #$FF : STA.b $07 : STA.b $08 : STA.b $09

  ; Pick terrain table offset ($00 = LW, $40 = DW, $80 = Special OW)
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
  BEQ .outdoors
  BRL .footprint_done                   ; indoors: single entrance marker only

.outdoors
  ; Outdoors: resolve parent map and area size (0=Small, 1=Large, 2=Wide, 3=Tall).
  LDA.b $8A
if !SPECIAL_OVERWORLD_NATIVE == 1
  CMP.b #$C0 : BCC .id_ok
  BRL .footprint_done
.id_ok
  TAX
  LDA.l !LYRA_CURRENT_TABLE_parent, X
  TAX
  AND.b #$3F : STA.b $04
  LDA.l !LYRA_CURRENT_TABLE_area_size, X
else
  CMP.b #$A0 : BCC .id_ok
  BRL .footprint_done
.id_ok
  TAX
  LDA.l $288998, X
  TAX
  AND.b #$3F : STA.b $04
  LDA.l $02F88D, X
endif
  CMP.b #$01 : BEQ .size_large
  CMP.b #$02 : BEQ .size_wide
  CMP.b #$03 : BEQ .size_tall
  BRA .check_subcell

.size_wide
  ; Wide (2x1): c1 = c0 + 1 if col < 7.
  LDA.b $04 : AND.b #$07 : CMP.b #$07 : BCS .check_subcell
  LDA.b $04 : INC : STA.b $07
  BRA .check_subcell

.size_tall
  ; Tall (1x2): c2 = c0 + 8 if row < 7 (c0 < $38).
  LDA.b $04 : CMP.b #$38 : BCS .check_subcell
  CLC : ADC.b #$08 : STA.b $08
  BRA .check_subcell

.size_large
  ; Large (2x2): c1 = c0+1 (col<7), c2 = c0+8 (row<7), c3 = c0+9 (both).
  LDA.b $04 : AND.b #$07 : CMP.b #$07 : BCS .large_no_right
  LDA.b $04 : INC : STA.b $07
.large_no_right
  LDA.b $04 : CMP.b #$38 : BCS .check_subcell
  CLC : ADC.b #$08 : STA.b $08
  LDA.b $07 : CMP.b #$FF : BEQ .check_subcell
  LDA.b $08 : INC : STA.b $09

.check_subcell
  ; Resolve Link's active sub-quadrant from ($7E0700 & $7E) >> 1 when it lies
  ; inside {c0, c1, c2, c3}; otherwise keep $8A & $3F (or c0).
  LDA.l $7E0700 : AND.b #$7E : LSR
  CMP.b $04 : BEQ .use_subcell
  CMP.b $07 : BEQ .use_subcell
  CMP.b $08 : BEQ .use_subcell
  CMP.b $09 : BEQ .use_subcell
  LDA.b $0A
  CMP.b $04 : BEQ .footprint_done
  CMP.b $07 : BEQ .footprint_done
  CMP.b $08 : BEQ .footprint_done
  CMP.b $09 : BEQ .footprint_done
  LDA.b $04
.use_subcell
  STA.b $0A

.footprint_done
  ; Iterate 64 cells: Y = cell 0..63, row = Y>>3, col = Y&7.
  ; Dest tilemap offset = menu_offset(11 + row, 6 + col) = $02CC + row*$40 + col*2.
  LDY.b #$00
.cell_loop
  TYA : CMP.b $0A : BEQ .is_link
  CMP.b $04 : BEQ .fp_tl
  CMP.b $07 : BEQ .fp_tr
  CMP.b $08 : BEQ .fp_bl
  CMP.b $09 : BEQ .fp_br
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
.fp_tl
  LDA.b #$00 : BRA .is_footprint
.fp_tr
  LDA.b #$40 : BRA .is_footprint
.fp_bl
  LDA.b #$80 : BRA .is_footprint
.fp_br
  LDA.b #$C0
.is_footprint
  STA.b $0B
  LDA.l $7E0207 : AND.b #$10 : BNE .fp_gold
  LDA.b #$25 : ORA.b $0B : XBA : LDA.b #$7B
  REP #$20
  BRA .store_tile
.fp_gold
  LDA.b #$35 : ORA.b $0B : XBA : LDA.b #$7B
  REP #$20
  BRA .store_tile
.is_link
  LDA.l $7E0207 : AND.b #$10 : BNE .link_gold
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
  INY : CPY.b #$40 : BCS .done
  BRL .cell_loop
.done
  RTL

  ; Terrain palette words for MiniMap_Cell ($017B):
  ; 0 = water/sea (blue $2D7B), 1 = grass/land (green $3D7B),
  ; 2 = desert/beach/mountain (tan $297B), 3 = landmark/castle/shrine (gold $357B),
  ; 4 = lava/fortress (red $257B), 5 = abyss/shadow/sky/ice (gray $317B)
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
  db 1,1,1,3, 5,5,5,3 ; $80-$87 Forest Glade, Korok Cove N, Royal Garrison N, Sky Islands, Sky Tower
  db 5,1,1,3, 5,5,5,5 ; $88-$8F Curtain, Korok Cove S, Royal Garrison S, Sky Islands
  db 3,3,0,0, 0,0,0,0 ; $90-$97 Sea Zora Temple, Shrine of Wisdom, North Reef/Sea
  db 0,2,0,0, 0,0,0,0 ; $98-$9F Zora Lagoon, Zora Quay dock/beach, Lyra Sea
  db 1,1,0,1, 0,0,1,3 ; $A0-$A7 Zora Coast, Lyra Sea + Twin-Tree Isl, Courage Island N + Shrine
  db 1,1,0,0, 1,0,1,1 ; $A8-$AF Deku Grove, Lyra Sea + Green Isl, Courage Island S
  db 2,2,0,1, 1,3,0,0 ; $B0-$B7 Goron Coast N, Lyra Sea, Crescent Atoll N, Pirate Ship N, Sea
  db 2,2,0,1, 1,3,5,5 ; $B8-$BF Goron Coast S, Harbor/Sea, Crescent Atoll S, Pirate Ship S, Frost Glacier
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
  dw "X___:_OPEN_MAP____"
  dw "A___:_INSPECT_USE_"
  dw "L.R_:_SWITCH_PAGE_"
  dw "B___:_CLOSE_MENU__"
  dw "SEL_:_CLOSE_HELP__"
pulltable
}

; =========================================================
; Map & Spoils Hoverable Dungeon Icons + 2D Navigation + Footers + Spoils Popup.
; Cells:
;   0     = World/Dungeon Map icon at (15,15)
;   1..6  = 6 Magic Bag Spoils on row 21 (cols 6,9,13,17,21,24)
;   7     = Chest Key at (15,18) — hoverable when drawn by Menu_DrawBigChestKey
;   8     = Big Key   at (15,21) — hoverable when drawn by Menu_DrawBigKey
;   9     = Treasure  at (15,24) — hoverable when drawn by Menu_DrawBigKey
; =========================================================

; In: A = cell (0..9), M/X=8. Out: C set = hoverable/owned, C clear = absent.
; Preserves A, X, Y, and DP $02-$03.
MenuMap_CellOwned_Long:
{
  SEP #$30
  CMP.b #$07 : BCC .yes                 ; 0 (Map) and 1..6 (Spoils) always hoverable
  CMP.b #$0A : BCS .no                  ; >= 10 invalid
  PHX : PHY : PHA                       ; stack: cell (1,S)
  LDA.l $7E040C : CMP.b #$FF : BEQ .pop_no
  LDA $01,S : CMP.b #$07 : BEQ .chest_key
  ; Cell 8 (Big Key) or 9 (Treasure): check $7EF366 Big Key bit for current palace
  REP #$30
  LDA.l $7E040C : AND.w #$00FF : LSR A : TAX
  LDA.l $7EF366
.bk_shift
  ASL A : DEX : BPL .bk_shift
  SEP #$30
  BCC .pop_no
  LDA $01,S : CMP.b #$08 : BEQ .pop_yes
  ; Cell 9 (Treasure): also require Menu_OracleTreasureOwned ($02 != 0)
  LDA.b $02 : PHA : LDA.b $03 : PHA
  JSL Menu_OracleTreasureOwned_Long     ; exits SEP #$30, sets $02 = 0/1
  LDA.b $02 : TAX
  PLA : STA.b $03 : PLA : STA.b $02
  TXA : BNE .pop_yes
  BRA .pop_no
.chest_key
  REP #$30
  LDA.l $7E040C : AND.w #$00FF : LSR A : TAX
  LDA.l $7EF364
.ck_shift
  ASL A : DEX : BPL .ck_shift
  SEP #$30
  BCS .pop_yes
.pop_no
  PLA : PLY : PLX
.no
  CLC : RTL
.pop_yes
  PLA : PLY : PLX
.yes
  SEC : RTL
}

; Fluid 2D D-pad navigation on Map & Spoils across Top row [0, 7, 8, 9]
; (skipping unowned dungeon icons) and Bottom row [1..6].
; Out: M/X=8, C set = page turn requested (A=$01 right / $FF left), C clear = done.
MenuMap_Move_Long:
{
  SEP #$30
  LDA.w $020B : JSL MenuMap_CellOwned_Long : BCS .valid
  LDA.b #$00 : STA.w $020B
.valid
  LDA.b $F4 : AND.b #$0F : BNE .has_dir
  CLC : RTL
.has_dir
  STA.b $04                             ; $04 = D-pad bits (1=R, 2=L, 4=D, 8=U)
  BIT.b #$03 : BNE .horiz
  ; Vertical move between Top row [0, 7, 8, 9] and Bottom row [1..6]
  LDA.w $020B : BEQ .top_to_bot_0
  CMP.b #$07 : BCS .top_to_bot_dng
  ; Bottom row (1..6) -> nearest owned top-row cell by column distance
  DEC : TAX
  LDA.l .bot_cols, X : STA.b $06
  LDA.b #$FF : STA.b $07                ; best distance
  LDA.b #$00 : STA.b $05                ; best cell (fallback Map 0)
  LDX.b #$00
.scan_top
  LDA.l .top_cells, X : JSL MenuMap_CellOwned_Long : BCC .next_top
  LDA.l .top_cols, X : SEC : SBC.b $06 : BCS .abs_ok
  EOR.b #$FF : INC
.abs_ok
  CMP.b $07 : BCS .next_top
  STA.b $07
  LDA.l .top_cells, X : STA.b $05
.next_top
  INX : CPX.b #$04 : BCC .scan_top
  LDA.b $05 : BRA .accept

.top_to_bot_0
  LDA.b #$03 : BRA .accept              ; Map (0, col 15) -> Rock Meat (3, col 13)
.top_to_bot_dng
  SEC : SBC.b #$03                      ; 7->4, 8->5, 9->6
  BRA .accept

.horiz
  LDA.w $020B : BEQ .horiz_top_0
  CMP.b #$07 : BCS .horiz_top_dng
  ; Bottom row (1..6): step left/right, turn at edges
  TAX
  LDA.b $04 : BIT.b #$01 : BNE .bot_right
  DEX : BNE .accept_x
  BRA .turn_left
.bot_right
  INX : CPX.b #$07 : BCC .accept_x
  BRA .turn_right

.horiz_top_0
  LDX.b #$00 : BRA .horiz_top_step
.horiz_top_dng
  SEC : SBC.b #$06 : TAX                ; 7->1, 8->2, 9->3
.horiz_top_step
  LDA.b $04 : BIT.b #$01 : BNE .top_right
.top_left
  DEX : BMI .turn_left
  LDA.l .top_cells, X : JSL MenuMap_CellOwned_Long : BCC .top_left
  LDA.l .top_cells, X : BRA .accept
.top_right
  INX : CPX.b #$04 : BCS .turn_right
  LDA.l .top_cells, X : JSL MenuMap_CellOwned_Long : BCC .top_right
  LDA.l .top_cells, X : BRA .accept

.accept_x
  TXA
.accept
  STA.w $020B
  STZ.w $0207
  LDA.b #$20 : STA.w $012F
.none
  CLC : RTL
.turn_left
  LDA.b #$FF : SEC : RTL
.turn_right
  LDA.b #$01 : SEC : RTL

.top_cells
  db 0, 7, 8, 9
.top_cols
  db 15, 18, 21, 24
.bot_cols
  db 6, 9, 13, 17, 21, 24
}

; Footer label in $7E1692 (14 tiles) when hovering Map (0) or Dungeon icons (7..9).
; In: A = cell (0, 7, 8, 9), M/X=8. Out: M/X=8.
MenuMap_DrawTopFooter_Long:
{
  SEP #$30
  CMP.b #$07 : BEQ .chest_key
  CMP.b #$08 : BEQ .boss_key
  CMP.b #$09 : BEQ .treasure
  LDA.b $1B : BNE .dng_map
  LDA.b #$00 : BRA .copy
.dng_map
  LDA.b #$01 : BRA .copy
.chest_key
  LDA.b #$02 : BRA .copy
.boss_key
  LDA.b #$03 : BRA .copy
.treasure
  LDA.b #$04
.copy
  REP #$30
  AND.w #$00FF : ASL #2 : STA.b $00
  ASL #3 : SEC : SBC.b $00 : STA.b $00  ; $00 = index * 28
  LDX.w #$0000
.loop
  PHX
  TXA : CLC : ADC.b $00 : TAX
  LDA.l .labels, X
  PLX
  STA.l $7E1692, X
  INX #2 : CPX.w #$001C : BCC .loop
  SEP #$30
  RTL

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
.labels
  dw "__WORLD_MAP___"                   ; 0: Map outdoors
  dw "_DUNGEON_MAP__"                   ; 1: Map indoors
  dw "__CHEST_KEY___"                   ; 2: Chest Key (cell 7)
  dw "___BOSS_KEY___"                   ; 3: Big Key   (cell 8)
  dw "___TREASURE___"                   ; 4: Treasure  (cell 9)
pulltable
}

; =========================================================
; Spoils Detail / Use Popup (!MENU_STATE_SPOIL_POPUP = $11).
; Matches Link_ConsumeMagicBagItem in Items/all_items.asm 100%:
;   0 Banana    (usable=1): CURHP += $10 (+2 hearts)
;   1 Pineapple (usable=1): !RAM_MAGIC = $80 (full magic)
;   2 Rock Meat (usable=0): Goron trade item
;   3 Seashell  (usable=0): Collectible sea find
;   4 Honeycomb (usable=1): Queues 3-bee swarm on menu exit
;   5 Deku Stick(usable=1): Equips held Deku Stick on menu exit
; =========================================================

; In: A = spoil slot 0..5, M/X=8. Out: C set = usable via MagicBag_ConsumeItem.
; Preserves X, Y.
MenuSpoil_IsUsable_Long:
{
  SEP #$30
  PHX
  CMP.b #$06 : BCS .no
  TAX
  LDA.l .usable, X : BEQ .no
  PLX : SEC : RTL
.no
  PLX : CLC : RTL
.usable
  db 1, 1, 0, 0, 1, 1
}

; Draw compact framed Spoils Detail/Use rectangle popup directly over the
; Map & Spoils tilemap in $7E1000 (rows 13..17, cols 5..26, same border style
; as the former tunic selector popup). Leaves header, area name, spoils row,
; cursor, and footer visible around the box.
; DBR = $2D. Out: M/X=8.
!MENU_SPOIL_BOX_TOP    = menu_offset(13,5)
!MENU_SPOIL_BOX_ROW1   = menu_offset(14,5)
!MENU_SPOIL_BOX_ROW2   = menu_offset(15,5)
!MENU_SPOIL_BOX_ROW3   = menu_offset(16,5)
!MENU_SPOIL_BOX_BOTTOM = menu_offset(17,5)
MenuSpoil_DrawPopup_Long:
{
  ; Resolve spoil slot 0..5 from $020B (1..6)
  SEP #$30
  LDA.w $020B : DEC : CMP.b #$06 : BCC .slot_ok
  LDA.b #$00
.slot_ok
  STA.b $0C                             ; $0C = spoil slot 0..5

  REP #$30
  ; Top border (row 13, cols 5..26): $3811, 20x $3821, $7811
  LDX.w #$0000
  LDA.w #$3821
.top_fill
  STA.l $7E1000+!MENU_SPOIL_BOX_TOP+2, X
  INX #2 : CPX.w #$0028 : BCC .top_fill
  LDA.w #$3811 : STA.l $7E1000+!MENU_SPOIL_BOX_TOP
  LDA.w #$7811 : STA.l $7E1000+!MENU_SPOIL_BOX_TOP+42

  ; Bottom border (row 17, cols 5..26): $B811, 20x $B821, $F811
  LDX.w #$0000
  LDA.w #$B821
.bot_fill
  STA.l $7E1000+!MENU_SPOIL_BOX_BOTTOM+2, X
  INX #2 : CPX.w #$0028 : BCC .bot_fill
  LDA.w #$B811 : STA.l $7E1000+!MENU_SPOIL_BOX_BOTTOM
  LDA.w #$F811 : STA.l $7E1000+!MENU_SPOIL_BOX_BOTTOM+42

  ; Interior rows 14, 15, 16: side edges $3820/$7820 + opaque black $3417 fill
  LDX.w #$0000
  LDA.w #$3417
.mid_fill
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW1+2, X
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW2+2, X
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW3+2, X
  INX #2 : CPX.w #$0028 : BCC .mid_fill

  LDA.w #$3820
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW1
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW2
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW3
  LDA.w #$7820
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW1+42
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW2+42
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW3+42

  ; Row 14, cols 7..24: 18-char concise effect line
  LDA.b $0C : AND.w #$00FF : ASL : TAX
  LDA.l .desc_offsets, X : STA.b $00
  LDY.w #$0000
.desc_loop
  LDA.b $00 : TAX
  LDA.l .spoil_desc, X
  TYX
  STA.l $7E1000+!MENU_SPOIL_BOX_ROW1+4, X
  INC.b $00 : INC.b $00
  INY #2 : CPY.w #$0024 : BCC .desc_loop

  ; Row 16, cols 7..24: "__A:USE___B:BACK__" for consumables, "______B:BACK______" otherwise
  SEP #$30
  LDA.b $0C : JSL MenuSpoil_IsUsable_Long
  REP #$30
  LDX.w #$0022
  BCC .act_back
.act_use
  LDA.l .act_use_txt, X : STA.l $7E1000+!MENU_SPOIL_BOX_ROW3+4, X
  DEX #2 : BPL .act_use
  SEP #$30
  RTL
.act_back
  LDA.l .act_back_txt, X : STA.l $7E1000+!MENU_SPOIL_BOX_ROW3+4, X
  DEX #2 : BPL .act_back
  SEP #$30
  RTL

.desc_offsets
  dw 0, 36, 72, 108, 144, 180

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
  '0' = $2570
  '1' = $2571
  '2' = $2572
  '3' = $2573
  '4' = $2574
  '5' = $2575
  '6' = $2576
  '7' = $2577
  '8' = $2578
  '9' = $2579
  '_' = $3417
.act_use_txt
  dw "__A:USE___B:BACK__"
.act_back_txt
  dw "______B:BACK______"
; 18 tiles per spoil (strictly concise single-line mechanical UI labels)
.spoil_desc
  dw "RESTORES_2_HEARTS_"
  dw "REFILLS_ALL_MAGIC_"
  dw "_GORON_TRADE_ITEM_"
  dw "__RARE_SEA_FIND___"
  dw "__SUMMONS_3_BEES__"
  dw "HOLD_TO_LIGHT_FIRE"
pulltable
}
