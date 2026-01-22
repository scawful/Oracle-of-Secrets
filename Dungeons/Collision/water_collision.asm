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
  ; Tile count: 8 + 7 + 53*3 = 174
  db 174

  ; Vertical channel (Y=15, X=40-47) - 8 tiles
  ; Shifted from Y=12 to Y=15 to match +3 tile offset
  dw $03E8, $03E9, $03EA, $03EB, $03EC, $03ED, $03EE, $03EF

  ; Vertical channel (Y=31, X=40-46) - 7 tiles
  ; Shifted from Y=28 to Y=31 to match +3 tile offset
  dw $07E8, $07E9, $07EA, $07EB, $07EC, $07ED, $07EE

  ; Y=41 row (X=5-57) - 53 tiles
  ; Link at visual Y=38-39 checks here
  dw $0A45, $0A46, $0A47, $0A48, $0A49, $0A4A, $0A4B, $0A4C
  dw $0A4D, $0A4E, $0A4F, $0A50, $0A51, $0A52, $0A53, $0A54
  dw $0A55, $0A56, $0A57, $0A58, $0A59, $0A5A, $0A5B, $0A5C
  dw $0A5D, $0A5E, $0A5F, $0A60, $0A61, $0A62, $0A63, $0A64
  dw $0A65, $0A66, $0A67, $0A68, $0A69, $0A6A, $0A6B, $0A6C
  dw $0A6D, $0A6E, $0A6F, $0A70, $0A71, $0A72, $0A73, $0A74
  dw $0A75, $0A76, $0A77, $0A78, $0A79

  ; Y=42 row (X=5-57) - 53 tiles
  ; Link at visual Y=39-40 checks here
  dw $0A85, $0A86, $0A87, $0A88, $0A89, $0A8A, $0A8B, $0A8C
  dw $0A8D, $0A8E, $0A8F, $0A90, $0A91, $0A92, $0A93, $0A94
  dw $0A95, $0A96, $0A97, $0A98, $0A99, $0A9A, $0A9B, $0A9C
  dw $0A9D, $0A9E, $0A9F, $0AA0, $0AA1, $0AA2, $0AA3, $0AA4
  dw $0AA5, $0AA6, $0AA7, $0AA8, $0AA9, $0AAA, $0AAB, $0AAC
  dw $0AAD, $0AAE, $0AAF, $0AB0, $0AB1, $0AB2, $0AB3, $0AB4
  dw $0AB5, $0AB6, $0AB7, $0AB8, $0AB9

  ; Y=43 row (X=5-57) - 53 tiles
  ; Link at visual Y=40-41 checks here
  dw $0AC5, $0AC6, $0AC7, $0AC8, $0AC9, $0ACA, $0ACB, $0ACC
  dw $0ACD, $0ACE, $0ACF, $0AD0, $0AD1, $0AD2, $0AD3, $0AD4
  dw $0AD5, $0AD6, $0AD7, $0AD8, $0AD9, $0ADA, $0ADB, $0ADC
  dw $0ADD, $0ADE, $0ADF, $0AE0, $0AE1, $0AE2, $0AE3, $0AE4
  dw $0AE5, $0AE6, $0AE7, $0AE8, $0AE9, $0AEA, $0AEB, $0AEC
  dw $0AED, $0AEE, $0AEF, $0AF0, $0AF1, $0AF2, $0AF3, $0AF4
  dw $0AF5, $0AF6, $0AF7, $0AF8, $0AF9
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
