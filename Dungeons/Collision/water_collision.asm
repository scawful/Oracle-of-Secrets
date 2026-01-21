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

; SRAM Persistence for Water Gate States
; Using available space in $7EF403-$7EF4FD block
WaterGateStates = $7EF411
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
      REP #$30
      LDA.w #WaterGate_Room27_Data : STA.b $00
      LDA.w #WaterGate_Room27_Data>>16 : STA.b $02
      JSR WaterGate_ApplyCollision
      SEP #$30
      BRA .done

  .check_room_25
  ; Room 0x25 - Zora Temple water grate
  CMP.b #$25 : BNE .no_persistence
    LDA.l WaterGateStates : AND.b #$02 : BEQ .no_persistence
      ; Water grate was opened - restore collision
      LDA.b #$02 : STA.w $0403
      REP #$30
      LDA.w #WaterGate_Room25_Data : STA.b $00
      LDA.w #WaterGate_Room25_Data>>16 : STA.b $02
      JSR WaterGate_ApplyCollision
      SEP #$30

  .no_persistence
  .done
  PLB
  RTL
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
; Full coverage: Y=38-40 horizontal (X=5-57), plus vertical channels.
; Formula: offset = (Y * 64) + X

WaterGate_Room27_Data:
{
  ; Tile count: 8 + 7 + 53*3 = 174
  db 174

  ; Vertical channel (Y=12, X=40-47) - 8 tiles
  dw $0328, $0329, $032A, $032B, $032C, $032D, $032E, $032F

  ; Vertical channel (Y=28, X=40-46) - 7 tiles
  dw $0728, $0729, $072A, $072B, $072C, $072D, $072E

  ; Y=38 row (X=5-57) - 53 tiles
  dw $0985, $0986, $0987, $0988, $0989, $098A, $098B, $098C
  dw $098D, $098E, $098F, $0990, $0991, $0992, $0993, $0994
  dw $0995, $0996, $0997, $0998, $0999, $099A, $099B, $099C
  dw $099D, $099E, $099F, $09A0, $09A1, $09A2, $09A3, $09A4
  dw $09A5, $09A6, $09A7, $09A8, $09A9, $09AA, $09AB, $09AC
  dw $09AD, $09AE, $09AF, $09B0, $09B1, $09B2, $09B3, $09B4
  dw $09B5, $09B6, $09B7, $09B8, $09B9

  ; Y=39 row (X=5-57) - 53 tiles
  dw $09C5, $09C6, $09C7, $09C8, $09C9, $09CA, $09CB, $09CC
  dw $09CD, $09CE, $09CF, $09D0, $09D1, $09D2, $09D3, $09D4
  dw $09D5, $09D6, $09D7, $09D8, $09D9, $09DA, $09DB, $09DC
  dw $09DD, $09DE, $09DF, $09E0, $09E1, $09E2, $09E3, $09E4
  dw $09E5, $09E6, $09E7, $09E8, $09E9, $09EA, $09EB, $09EC
  dw $09ED, $09EE, $09EF, $09F0, $09F1, $09F2, $09F3, $09F4
  dw $09F5, $09F6, $09F7, $09F8, $09F9

  ; Y=40 row (X=5-57) - 53 tiles
  dw $0A05, $0A06, $0A07, $0A08, $0A09, $0A0A, $0A0B, $0A0C
  dw $0A0D, $0A0E, $0A0F, $0A10, $0A11, $0A12, $0A13, $0A14
  dw $0A15, $0A16, $0A17, $0A18, $0A19, $0A1A, $0A1B, $0A1C
  dw $0A1D, $0A1E, $0A1F, $0A20, $0A21, $0A22, $0A23, $0A24
  dw $0A25, $0A26, $0A27, $0A28, $0A29, $0A2A, $0A2B, $0A2C
  dw $0A2D, $0A2E, $0A2F, $0A30, $0A31, $0A32, $0A33, $0A34
  dw $0A35, $0A36, $0A37, $0A38, $0A39
}

; =========================================================
; Room 0x25 - Zora Temple Water Grate Room
; =========================================================
; Placeholder - needs actual collision offsets for this room

WaterGate_Room25_Data:
{
  ; Tile count
  db 16  ; Placeholder

  ; Collision offsets - TODO: Fill in based on actual room layout
  dw $0800, $0802, $0804, $0806
  dw $0840, $0842, $0844, $0846
  dw $0880, $0882, $0884, $0886
  dw $08C0, $08C2, $08C4, $08C6
}

print "End of water_collision.asm        ", pc
