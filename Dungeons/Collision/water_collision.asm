; =========================================================
; Water Gate Collision System
; =========================================================
; Updates collision tilemaps ($7F2000) when water fills/drains
; in dungeon rooms. Works with the RoomTag_WaterGate system.
;
; This system provides:
; - Room-indexed collision data tables
; - SRAM persistence for water gate states
; - Integration with vanilla water fill animation completion
;
; =========================================================
; @doc Docs/Issues/WaterCollision_Handoff.md
; @source Derived from vanilla disassembly + runtime tests (see doc)
; @verified UNKNOWN (needs audit)

; SRAM Persistence for Water Gate States
; Defined in Core/sram.asm (uses $7EF411 in $7EF403-$7EF4FD block)
; Bit 0: Zora Temple water gate room (0x27)
; Bit 1: Zora Temple water grate room (0x25)
; Bits 2-7: Reserved for future water gates

; =========================================================
; Water Fill Completion Hook
; =========================================================
; Called from dungeons.asm hook at $01F3D2 when water fill
; animation completes. Original code: STZ.b $1E : STZ.b $1F
;
; NOTE: The org directive is in dungeons.asm to avoid conflicts

IrisSpotlight_ResetTable = $00F427

WaterGate_FillComplete_Hook:
{
  ; Execute original code that was replaced by JML
  STZ.b $1E
  STZ.b $1F
  JSL IrisSpotlight_ResetTable

  ; Apply collision updates for water-filled area
  PHB : PHK : PLB

  SEP #$20
  LDA.b $A0

  ; Room 0x27 - Zora Temple water gate
  CMP.b #$27 : BNE .check_room_25
    REP #$20
    LDA.w #WaterGate_Room27_Data : STA.b $00
    SEP #$20
    LDA.b #WaterGate_Room27_Data>>16 : STA.b $02
    JSR WaterGate_ApplyCollision
    JSR WaterGate_SetPersistenceFlag
    BRA .done

  .check_room_25
  ; Room 0x25 - Zora Temple water grate
  CMP.b #$25 : BNE .done
    REP #$20
    LDA.w #WaterGate_Room25_Data : STA.b $00
    SEP #$20
    LDA.b #WaterGate_Room25_Data>>16 : STA.b $02
    JSR WaterGate_ApplyCollision
    JSR WaterGate_SetPersistenceFlag

  .done
  SEP #$30
  PLB

  ; Return to the instruction after the replaced code (RTL at $01F3DA)
  JML $01F3DA
}

; =========================================================
; Apply Collision Updates
; =========================================================
; Reads collision data from pointer in $00-$02 and writes
; deep water collision (type $08) to $7F2000
;
; Data format:
;   db <tile_count>
;   dw <offset1>, <offset2>, ...  ; Offsets into $7F2000
;
WaterGate_ApplyCollision:
{
  PHB
  PEA.w $7F7F : PLB : PLB  ; Set bank to $7F for collision writes

  SEP #$20
  LDA.b [$00] : STA.b $04  ; Tile count
  STZ.b $05                 ; Clear high byte for 16-bit decrement
  BEQ .done

  REP #$30                  ; 16-bit A and X/Y
  INC.b $00  ; Advance past tile count byte

  LDY.w #$0000

  .next_tile
    LDA.b [$00], Y : TAX
    INY : INY

    ; Write deep water collision (type $08) to both layers
    SEP #$20                ; 8-bit A for collision value
    LDA.b #$08 : STA.w $2000, X  ; COLMAPA
                STA.w $3000, X  ; COLMAPB (layer 2)
    REP #$20                ; 16-bit A for offset reads

    DEC.b $04
    BNE .next_tile

  .done
  SEP #$30                  ; Restore 8-bit A and X/Y
  PLB
  RTS
}

; =========================================================
; Set SRAM Persistence Flag
; =========================================================
; Sets a bit in WaterGateStates based on current room
;
WaterGate_SetPersistenceFlag:
{
  SEP #$20
  LDA.b $A0

  ; Room 0x27 - Zora Temple water gate
  CMP.b #$27 : BNE +
    LDA.l WaterGateStates : ORA.b #$01 : STA.l WaterGateStates
    RTS
  +

  ; Room 0x25 - Zora Temple water grate
  CMP.b #$25 : BNE +
    LDA.l WaterGateStates : ORA.b #$02 : STA.l WaterGateStates
    RTS
  +

  RTS
}

; =========================================================
; Room Load Check for Persistence
; =========================================================
; Call from room load to restore water collision if flag set
;
WaterGate_CheckRoomEntry:
{
  PHB : PHK : PLB
  SEP #$20

  LDA.b $A0

  ; Room 0x27 - Zora Temple water gate
  CMP.b #$27 : BNE .check_room_25
    LDA.l WaterGateStates : AND.b #$01 : BEQ .no_persistence
      ; Water was filled before - restore collision
      LDA.b #$02 : STA.w $0403  ; Set door flag to skip animation
      REP #$20
      LDA.w #WaterGate_Room27_Data : STA.b $00
      SEP #$20
      LDA.b #WaterGate_Room27_Data>>16 : STA.b $02
      JSR WaterGate_ApplyCollision
      SEP #$30
      BRA .done

  .check_room_25
  ; Room 0x25 - Zora Temple water grate
  CMP.b #$25 : BNE .no_persistence
    LDA.l WaterGateStates : AND.b #$02 : BEQ .no_persistence
      ; Water grate was opened - restore collision
      LDA.b #$02 : STA.w $0403
      REP #$20
      LDA.w #WaterGate_Room25_Data : STA.b $00
      SEP #$20
      LDA.b #WaterGate_Room25_Data>>16 : STA.b $02
      JSR WaterGate_ApplyCollision
      SEP #$30

  .no_persistence
  .done
  PLB
  RTL
}

; =========================================================
; Underworld_LoadRoom Exit Hook
; =========================================================
; Replaces BNE/SEP/RTL at $0188DF. If torches remain, jump back
; into the draw loop. Otherwise apply persistent water collision.
Underworld_LoadRoom_ExitHook:
{
  REP #$30
  LDX.b $BA
  LDA.l $7EFB40,X
  CMP.w #$FFFF
  BNE .draw_next_torch

  SEP #$30
  JSL WaterGate_CheckRoomEntry
  PLB
  RTL

  .draw_next_torch
  JML $0188C9
}

; =========================================================
; Collision Data Tables
; =========================================================
; Room-indexed lookup table: 4 bytes per entry (room*4)
; Format: dw <data_pointer>, <bank_byte>
; Empty entries have $0000

WaterGateCollisionTable:
{
  ; Rooms 0x00-0x24 (empty) - 37 rooms * 4 bytes each = 148 bytes
  fillbyte $00
  fill 148

  ; Room 0x25 - Zora Temple water grate room
  dw WaterGate_Room25_Data
  dw WaterGate_Room25_Data>>16

  ; Room 0x26 (empty)
  dw $0000, $0000

  ; Room 0x27 - Zora Temple water gate room
  dw WaterGate_Room27_Data
  dw WaterGate_Room27_Data>>16
}

; =========================================================
; Room 0x27 - Zora Temple Water Gate Room
; =========================================================
; Collision offsets for swimming area after water fills.
;
; IMPORTANT: The game checks collision at Link's position + ~20 pixels Y.
; This means collision data must be placed 2-3 tiles BELOW where Link
; visually stands. Visual water at Y=39-40 requires collision at Y=41-43.
;
; Full coverage: Y=41-43 horizontal (X=5-57), plus vertical channels.
; Formula: offset = (Y * 64) + X

WaterGate_Room27_Data:
{
  ; Tile count: expanded coverage (vertical channels + full 4-row swim mask)
  ; 8 + 7 + (56*4) = 239 tiles
  db 239

  ; Vertical channel (Y=15, X=40-47) - 8 tiles
  ; Shifted from Y=12 to Y=15 to match +3 tile offset
  dw $03E8, $03E9, $03EA, $03EB, $03EC, $03ED, $03EE, $03EF

  ; Vertical channel (Y=31, X=40-46) - 7 tiles
  ; Shifted from Y=28 to Y=31 to match +3 tile offset
  dw $07E8, $07E9, $07EA, $07EB, $07EC, $07ED, $07EE

  ; Main swim area (rows 41-44, cols 5-60) - 56 tiles per row
  ; Link checks collision ~20px below his feet, so we cover a 4-row band.
  dw $0A45, $0A46, $0A47, $0A48, $0A49, $0A4A, $0A4B, $0A4C, $0A4D, $0A4E
  dw $0A4F, $0A50, $0A51, $0A52, $0A53, $0A54, $0A55, $0A56, $0A57, $0A58
  dw $0A59, $0A5A, $0A5B, $0A5C, $0A5D, $0A5E, $0A5F, $0A60, $0A61, $0A62
  dw $0A63, $0A64, $0A65, $0A66, $0A67, $0A68, $0A69, $0A6A, $0A6B, $0A6C
  dw $0A6D, $0A6E, $0A6F, $0A70, $0A71, $0A72, $0A73, $0A74, $0A75, $0A76
  dw $0A77, $0A78, $0A79, $0A7A, $0A7B, $0A7C

  dw $0A85, $0A86, $0A87, $0A88, $0A89, $0A8A, $0A8B, $0A8C, $0A8D, $0A8E
  dw $0A8F, $0A90, $0A91, $0A92, $0A93, $0A94, $0A95, $0A96, $0A97, $0A98
  dw $0A99, $0A9A, $0A9B, $0A9C, $0A9D, $0A9E, $0A9F, $0AA0, $0AA1, $0AA2
  dw $0AA3, $0AA4, $0AA5, $0AA6, $0AA7, $0AA8, $0AA9, $0AAA, $0AAB, $0AAC
  dw $0AAD, $0AAE, $0AAF, $0AB0, $0AB1, $0AB2, $0AB3, $0AB4, $0AB5, $0AB6
  dw $0AB7, $0AB8, $0AB9, $0ABA, $0ABB, $0ABC

  dw $0AC5, $0AC6, $0AC7, $0AC8, $0AC9, $0ACA, $0ACB, $0ACC, $0ACD, $0ACE
  dw $0ACF, $0AD0, $0AD1, $0AD2, $0AD3, $0AD4, $0AD5, $0AD6, $0AD7, $0AD8
  dw $0AD9, $0ADA, $0ADB, $0ADC, $0ADD, $0ADE, $0ADF, $0AE0, $0AE1, $0AE2
  dw $0AE3, $0AE4, $0AE5, $0AE6, $0AE7, $0AE8, $0AE9, $0AEA, $0AEB, $0AEC
  dw $0AED, $0AEE, $0AEF, $0AF0, $0AF1, $0AF2, $0AF3, $0AF4, $0AF5, $0AF6
  dw $0AF7, $0AF8, $0AF9, $0AFA, $0AFB, $0AFC

  dw $0B05, $0B06, $0B07, $0B08, $0B09, $0B0A, $0B0B, $0B0C, $0B0D, $0B0E
  dw $0B0F, $0B10, $0B11, $0B12, $0B13, $0B14, $0B15, $0B16, $0B17, $0B18
  dw $0B19, $0B1A, $0B1B, $0B1C, $0B1D, $0B1E, $0B1F, $0B20, $0B21, $0B22
  dw $0B23, $0B24, $0B25, $0B26, $0B27, $0B28, $0B29, $0B2A, $0B2B, $0B2C
  dw $0B2D, $0B2E, $0B2F, $0B30, $0B31, $0B32, $0B33, $0B34, $0B35, $0B36
  dw $0B37, $0B38, $0B39, $0B3A, $0B3B, $0B3C
}

; =========================================================
; Room 0x25 - Zora Temple Water Grate Room
; =========================================================
; Collision offsets for swimming area after grate opens.
;
; Derived from Layer-2 swim mask objects (0xD9) in room data:
; - Visual water at Y=43, X=5-60 (size=0x0F / 0x07 segments)
; - Apply +2..+4 tile Y offset (TileDetect deep water check)
;
; Rows covered: Y=45-47, X=5-60 (56 tiles per row)

WaterGate_Room25_Data:
{
  ; Tile count
  db 168

  ; Y=45 row (X=5-60) - 56 tiles
  dw $0B45, $0B46, $0B47, $0B48, $0B49, $0B4A, $0B4B, $0B4C
  dw $0B4D, $0B4E, $0B4F, $0B50, $0B51, $0B52, $0B53, $0B54
  dw $0B55, $0B56, $0B57, $0B58, $0B59, $0B5A, $0B5B, $0B5C
  dw $0B5D, $0B5E, $0B5F, $0B60, $0B61, $0B62, $0B63, $0B64
  dw $0B65, $0B66, $0B67, $0B68, $0B69, $0B6A, $0B6B, $0B6C
  dw $0B6D, $0B6E, $0B6F, $0B70, $0B71, $0B72, $0B73, $0B74
  dw $0B75, $0B76, $0B77, $0B78, $0B79, $0B7A, $0B7B, $0B7C

  ; Y=46 row (X=5-60) - 56 tiles
  dw $0B85, $0B86, $0B87, $0B88, $0B89, $0B8A, $0B8B, $0B8C
  dw $0B8D, $0B8E, $0B8F, $0B90, $0B91, $0B92, $0B93, $0B94
  dw $0B95, $0B96, $0B97, $0B98, $0B99, $0B9A, $0B9B, $0B9C
  dw $0B9D, $0B9E, $0B9F, $0BA0, $0BA1, $0BA2, $0BA3, $0BA4
  dw $0BA5, $0BA6, $0BA7, $0BA8, $0BA9, $0BAA, $0BAB, $0BAC
  dw $0BAD, $0BAE, $0BAF, $0BB0, $0BB1, $0BB2, $0BB3, $0BB4
  dw $0BB5, $0BB6, $0BB7, $0BB8, $0BB9, $0BBA, $0BBB, $0BBC

  ; Y=47 row (X=5-60) - 56 tiles
  dw $0BC5, $0BC6, $0BC7, $0BC8, $0BC9, $0BCA, $0BCB, $0BCC
  dw $0BCD, $0BCE, $0BCF, $0BD0, $0BD1, $0BD2, $0BD3, $0BD4
  dw $0BD5, $0BD6, $0BD7, $0BD8, $0BD9, $0BDA, $0BDB, $0BDC
  dw $0BDD, $0BDE, $0BDF, $0BE0, $0BE1, $0BE2, $0BE3, $0BE4
  dw $0BE5, $0BE6, $0BE7, $0BE8, $0BE9, $0BEA, $0BEB, $0BEC
  dw $0BED, $0BEE, $0BEF, $0BF0, $0BF1, $0BF2, $0BF3, $0BF4
  dw $0BF5, $0BF6, $0BF7, $0BF8, $0BF9, $0BFA, $0BFB, $0BFC
}

print "End of water_collision.asm        ", pc
