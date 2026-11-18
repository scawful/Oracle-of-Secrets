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
; @doc Docs/Debugging/Issues/WaterCollision_Handoff.md
; @source Derived from vanilla disassembly + runtime tests (see doc)
; @verified UNKNOWN (needs audit)

; SRAM Persistence for Water Gate States
; Defined in Core/sram.asm (uses $7EF411 in $7EF403-$7EF4FD block)
; Bit 0: Zora Temple water gate room (0x27)
; Bit 1: Zora Temple water grate room (0x25)
; Bits 2-7: Reserved for future water gates

; =========================================================
; Editor-Authored Water Fill Table (Yaze)
; =========================================================
; Yaze serializes painted water fill zones into the ZScream expanded custom
; collision bank and the runtime consumes it directly.
;
; ROM location (SNES): $25:E000..$25:FFFF (reserved 0x2000 bytes)
; ROM location (PC):   $12E000..$12FFFF
;
; Format:
;   db zone_count
;   repeat zone_count:
;     db room_id
;     db sram_bit_mask
;     dw data_offset (relative to table start)
;   then data sections:
;     if !ENABLE_WATER_FILL_16BIT_COUNT: dw tile_count
;     else: db tile_count
;     dw offsets...
;
Oracle_WaterFillTable = $25E000

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

  JSR WaterGate_CompleteRoom

  ; Return to the instruction after the replaced code (RTL at $01F3DA)
  JML $01F3DA
}

; Shared by the animated fill and room $25's lever-operated swim band.
; Clobbers A/X/Y and DP scratch $00-$05; returns M8/X8, preserving D/DB.
WaterGate_CompleteRoom:
{
  ; Apply collision updates for water-filled area
  ;
  ; CRITICAL: do not assume Direct Page (D) is $0000 here. Several callers in
  ; the underworld transition stack run with a non-zero D, and this module uses
  ; DP scratch ($00-$05) and DP reads ($A0). If D is not $0000, those become
  ; accidental writes into unrelated state (including GameMode/SubMode).
  PHD
  REP #$20
  LDA.w #$0000
  TCD
  SEP #$20

  PHB : PHK : PLB

  ; The paired controller owns room $25, regardless of old saved bit $02
  ; or a stale legacy table row. Check the full room ID before either path.
  REP #$20
  LDA.l $7E00A0 : CMP.w #$0025 : BNE .legacy_owner
  JMP .done
.legacy_owner
  SEP #$20
  LDA.b $A1 : BNE .done
  LDA.b $A0

  ; Prefer editor-authored WaterFillTable (yaze) when present.
  JSR WaterFill_FindRoomInTable
  BCC .legacy_fallback
    JSR WaterGate_ApplyCollision
    JSR WaterGate_ApplyRoom27Ladder
    JSR WaterGate_SetPersistenceFlag
    BRA .done

  .legacy_fallback
  ; Back-compat: if the table is missing/uninitialized, fall back to the
  ; original hardcoded D4 room data.
  LDA.b $A0
  CMP.b #$27 : BNE .check_room_25
    REP #$20
    LDA.w #WaterGate_Room27_Data : STA.b $00
    SEP #$20
    LDA.b #WaterGate_Room27_Data>>16 : STA.b $02
    LDA.b #$01 : STA.b $03
    JSR WaterGate_ApplyCollision
    JSR WaterGate_ApplyRoom27Ladder
    JSR WaterGate_SetPersistenceFlag
    BRA .done

  .check_room_25
  CMP.b #$25 : BNE .done
    REP #$20
    LDA.w #WaterGate_Room25_Data : STA.b $00
    SEP #$20
    LDA.b #WaterGate_Room25_Data>>16 : STA.b $02
    LDA.b #$02 : STA.b $03
    JSR WaterGate_ApplyCollision
    JSR WaterGate_SetPersistenceFlag

  .done
  SEP #$30
  PLB
  PLD

  RTS
}

; Room $25 has D9 water flooring, not the D8 window object required by the
; vanilla WaterOff tag. Its lever opens a swim band; draining here would use
; uninitialized HDMA coordinates and then erase the entire BG2 tilemap.
;
; Entry: tag dispatcher, M8/X8, $0E = active tag slot (0=$AE, 1=$AF).
; The lever handles its own animation/SFX. Restore this room's collision on
; its first tag tick after re-entry, without enabling the global load hook.
WaterGate_Room25Tag_Hook:
{
  PHP
  REP #$20
  LDA.l $7E00A0 : CMP.w #$0025 : BNE .vanilla
  SEP #$30

  ; Do not consume the actor-owned $0642 episode or replay the old swim band.
  ; The selected paired room has tag 0; also make a stale WaterOff tag inert.
  BRA .exit

  LDA.l WaterGateStates : AND.b #$02 : BNE .open
  LDA.l $7E0642 : BEQ .exit

  .open
  PHD
  REP #$20
  LDA.w #$0000 : TCD
  SEP #$20

  ; CompleteRoom preserves $0E, D and DB. Only clear the dispatched tag;
  ; room $25 authors WaterOff in slot 0, unlike vanilla's hardcoded $AF.
  JSR WaterGate_CompleteRoom
  LDA.l $7E0403 : ORA.b #$08 : STA.l $7E0403
  LDA.b #$00 : STA.l $7E0642
  LDX.b $0E
  STZ.b $AE, X
  PLD

  .exit
  PLP
  JML $01CA93 ; original tag RTS

  .vanilla
  PLP
  LDA.w $0642 : BEQ .vanilla_exit
  JML $01CA99
  .vanilla_exit
  JML $01CA93
}

; =========================================================
; Water Fill Table Lookup (Yaze)
; =========================================================
; Input:
;   A (8-bit) = room id ($A0)
; Output:
;   C=1 if found, C=0 if not found/invalid
;   $00-$02 = 24-bit pointer to tile data (db|dw tile_count, dw offsets...)
;   $03     = SRAM bit mask for this room (single bit in WaterGateStates)
;
; Clobbers: A, X, $04-$05
; Requires: Direct Page (D) = $0000
WaterFill_FindRoomInTable:
{
  ; Save target room id.
  STA.b $05

  ; zone_count (0 means absent). Treat >8 as absent for safety.
  LDA.l Oracle_WaterFillTable
  BEQ .not_found
  CMP.b #$09 : BCS .not_found
  STA.b $04

  ; Scan entries: [room_id, mask, data_off_lo, data_off_hi] * zone_count
  REP #$10
  LDX.w #$0000

  .next
    LDA.b $04 : BEQ .not_found_x
    LDA.l Oracle_WaterFillTable+1, X
    CMP.b $05 : BEQ .found
    INX : INX : INX : INX
    DEC.b $04
    BRA .next

  .found
    ; SRAM bit mask for this room.
    LDA.l Oracle_WaterFillTable+2, X : STA.b $03

    ; Data pointer: $25:(E000 + data_off)
    LDA.l Oracle_WaterFillTable+4, X
    CLC : ADC.b #$E0
    STA.b $01
    LDA.l Oracle_WaterFillTable+3, X
    STA.b $00
    LDA.b #$25 : STA.b $02

    SEP #$10
    SEC
    RTS

  .not_found_x
  SEP #$10
  .not_found
  STZ.b $00
  STZ.b $01
  STZ.b $02
  STZ.b $03
  CLC
  RTS
}

; =========================================================
; Apply Collision Updates
; =========================================================
; Reads collision data from pointer in $00-$02 and writes
; deep water collision (type $08) to $7F2000
;
; Data format:
;   if !ENABLE_WATER_FILL_16BIT_COUNT: dw <tile_count>
;   else: db <tile_count>
;   dw <offset1>, <offset2>, ...  ; Offsets into $7F2000
;
WaterGate_ApplyCollision:
{
  ; See note in WaterGate_FillComplete_Hook: ensure DP base is $0000 while
  ; using $00-$05 scratch and [$00] indirect addressing.
  PHD
  REP #$20
  LDA.w #$0000
  TCD

  PHB
  PEA.w $7F7F : PLB : PLB  ; Set bank to $7F for collision writes

if !ENABLE_WATER_FILL_16BIT_COUNT == 1
  ; 16-bit count (QUEUE169): word at [$00], then offsets. Cap practical ~2047.
  REP #$30
  LDA.b [$00] : STA.b $04
  ; Advance 24-bit pointer past the count word (page-safe).
  LDA.b $00 : CLC : ADC.w #$0002 : STA.b $00
  LDA.b $04 : BEQ .done
else
  SEP #$20
  LDA.b [$00] : STA.b $04  ; Tile count (8-bit)
  STZ.b $05                 ; Clear high byte for 16-bit decrement
  BEQ .done

  REP #$30                  ; 16-bit A and X/Y
  INC.b $00  ; Advance past tile count byte
endif

  LDY.w #$0000

  .next_tile
    LDA.b [$00], Y : TAX
    INY : INY

    ; Write deep water collision (type $08) to both layers
    SEP #$20                ; 8-bit A for collision value
    LDA.b #$08 : STA.w $2000, X  ; COLMAPA
                STA.w $3000, X  ; COLMAPB (layer 2)
    REP #$20                ; 16-bit A for offset reads

    ; Direct-page 16-bit decrement ($00:$0004..$05, D=$0000); never DEC.w while DBR=$7F.
    DEC.b $04
    BNE .next_tile

  .done
  SEP #$30                  ; Restore 8-bit A and X/Y
  PLB
  PLD
  RTS
}

; =========================================================
; Room $27 Wet Pool-Ladder & West-Stair Stamp
; =========================================================
; When dry, Room $27 Option 2 blocks 0x135@(52,27) via solid COLMAPB ($02) and
; custom 0x1D rail (option A), and leaves COLMAPB row 28 == $02 below 0x133@(25,27).
; Once water fills or restores on re-entry, open rows 27-28 cols 52-55 on both
; COLMAPA ($26F4/$2734) and COLMAPB ($36F4/$3734), and row 28 cols 25-28
; ($2719/$3719) under 0x133@(25,27), so Link can climb both stairs out of
; the filled basin. Preserves P, DB, and $03.
WaterGate_ApplyRoom27Ladder:
{
  PHP
  PHB
  SEP #$20
  LDA.b $A1 : BNE .exit
  LDA.b $A0 : CMP.b #$27 : BNE .exit

  PEA.w $7F7F : PLB : PLB
  LDA.b #$03
  ; 0x135@(52,27) side bumpers (Option 2 v2: cols 52 & 55, aligned under dais stairs cols 52..55)
  STA.w $26F4
  STA.w $26F7
  STA.w $36F4
  STA.w $36F7
  STA.w $2734
  STA.w $2737
  STA.w $3734
  STA.w $3737
  ; 0x133@(25,27) rows 27-28 side bumpers
  STA.w $26D9
  STA.w $26DC
  STA.w $36D9
  STA.w $36DC
  STA.w $2719
  STA.w $271C
  STA.w $3719
  STA.w $371C

  STZ.w $26DA
  STZ.w $26DB
  STZ.w $26F5
  STZ.w $26F6

  LDA.b #$0A
  STA.w $36DA
  STA.w $36DB
  STA.w $36F5
  STA.w $36F6

  LDA.b #$08
  STA.w $2735
  STA.w $2736
  STA.w $3735
  STA.w $3736
  STA.w $271A
  STA.w $271B
  STA.w $371A
  STA.w $371B

.exit
  PLB
  PLP
  RTS
}

; =========================================================
; Set SRAM Persistence Flag
; =========================================================
; Sets a bit in WaterGateStates based on current room
;
WaterGate_SetPersistenceFlag:
{
  ; $03 is the per-room bit mask (from WaterFill_FindRoomInTable or legacy
  ; fallback). If it's zero, do nothing.
  SEP #$20
  LDA.b $03 : BEQ .done
  ORA.l WaterGateStates
  STA.l WaterGateStates
.done
  RTS
}

; =========================================================
; Room Load Check for Persistence
; =========================================================
; Call from room load to restore water collision if flag set
;
WaterGate_CheckRoomEntry:
{
  ; This is called from room-load hooks; it must be ABI-transparent.
  ; Preserve P/A/X/Y/DB/D and restore on exit.
  PHP
  PHB : PHK : PLB
  PHD

  REP #$30
  PHA
  PHX
  PHY

  ; Ensure Direct Page is $0000 before reading DP mirrors ($A0) or using DP
  ; scratch. Several underworld callers run with non-zero D.
  LDA.w #$0000
  TCD

  ; Keep legacy restore from overwriting the paired room after its loader.
  ; This also covers callers when ROOMENTRY_RESTORE is enabled for diagnosis.
  LDA.l $7E00A0 : CMP.w #$0025 : BNE .legacy_owner
  JMP .done
.legacy_owner
  SEP #$20
  LDA.b $A1 : BNE .done
  LDA.b $A0

  ; Prefer editor-authored WaterFillTable (yaze) when present.
  JSR WaterFill_FindRoomInTable
  BCC .legacy_fallback
    LDA.l WaterGateStates : AND.b $03 : BEQ .done
      ; Preserve existing $0403 door/chest bits and mark DoorFlagMasks+1 ($08).
      LDA.w $0403 : ORA.b #$08 : STA.w $0403
      JSR WaterGate_ApplyCollision
      JSR WaterGate_ApplyRoom27Ladder
      BRA .done

  .legacy_fallback
  ; Back-compat: if the table is missing/uninitialized, fall back to the
  ; original hardcoded D4 room data.
  LDA.b $A0

  CMP.b #$27 : BNE .check_room_25
    LDA.l WaterGateStates : AND.b #$01 : BEQ .done
      LDA.w $0403 : ORA.b #$08 : STA.w $0403
      REP #$20
      LDA.w #WaterGate_Room27_Data : STA.b $00
      SEP #$20
      LDA.b #WaterGate_Room27_Data>>16 : STA.b $02
      LDA.b #$01 : STA.b $03
      JSR WaterGate_ApplyCollision
      JSR WaterGate_ApplyRoom27Ladder
      BRA .done

  .check_room_25
  CMP.b #$25 : BNE .done
    LDA.l WaterGateStates : AND.b #$02 : BEQ .done
      LDA.w $0403 : ORA.b #$08 : STA.w $0403
      REP #$20
      LDA.w #WaterGate_Room25_Data : STA.b $00
      SEP #$20
      LDA.b #WaterGate_Room25_Data>>16 : STA.b $02
      LDA.b #$02 : STA.b $03
      JSR WaterGate_ApplyCollision

  .done
  REP #$30
  PLY
  PLX
  PLA
  PLD
  PLB
  PLP
  RTL
}

; =========================================================
; Underworld_LoadRoom Exit Hook
; =========================================================
; Replaces BNE/SEP/RTL at $0188DF. If torches remain, jump back
; into the draw loop. Otherwise apply persistent water collision.
Underworld_LoadRoom_ExitHook:
{
  ; Hooked at $0188DF, replacing:
  ;   BNE .draw_next_torch
  ;   SEP #$30
  ;
  ; On entry, Z reflects the prior `CMP #$FFFF` at $0188DC.
  ; If Z=0, torches remain and we must jump back into the draw loop
  ; without changing A/X/Y/P beyond what vanilla would.
  BNE .draw_next_torch

  ; Vanilla fallthrough: SEP #$30 : RTL
  ; We additionally call WaterGate_CheckRoomEntry, but must not leak
  ; altered flags/registers to the caller (vanilla returns with Z=1).
  SEP #$30

  PHP
  PHA
  PHX
  PHY

  ; Only run persistence restore in the specific water-gate rooms.
  ; This hook runs on *every* underworld room load (torch loop), so we must
  ; avoid invoking custom logic unless we're in the target rooms.
  ;
  ; Room ID is mirrored in $7E00A0 (direct page $A0).
  SEP #$20
  LDA.b $A0
  CMP.b #$27 : BEQ .do_watergate
  CMP.b #$25 : BNE .skip_watergate
.do_watergate
  JSL WaterGate_CheckRoomEntry
.skip_watergate

  PLY
  PLX
  PLA
  PLP

  RTL

  .draw_next_torch
  ; IMPORTANT: Do NOT set SEP here; the vanilla torch draw loop runs in 16-bit mode.
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
; Derived from Layer-2 swim mask objects (0xD9) in room data:
; - Expand each horizontal segment by +2..+4 rows in Y for Link's water probe.
; - This matches the approach used for room 0x25 and keeps visual/collision sync.
;
; Formula: offset = (Y * 64) + X

WaterGate_Room27_Data:
{
  ; Tile count: Room $27 Option 2 (chute rows 15..28 cols 42..44 + basin rows 29..31 cols 5..54)
if !ENABLE_WATER_FILL_16BIT_COUNT == 1
  dw 192
else
  db 192
endif

  dw $03EA, $03EB, $03EC, $042A, $042B, $042C, $046A, $046B, $046C, $04AA
  dw $04AB, $04AC, $04EA, $04EB, $04EC, $052A, $052B, $052C, $056A, $056B
  dw $056C, $05AA, $05AB, $05AC, $05EA, $05EB, $05EC, $062A, $062B, $062C
  dw $066A, $066B, $066C, $06AA, $06AB, $06AC, $06EA, $06EB, $06EC, $072A
  dw $072B, $072C, $0745, $0746, $0747, $0748, $0749, $074A, $074B, $074C
  dw $074D, $074E, $074F, $0750, $0751, $0752, $0753, $0754, $0755, $0756
  dw $0757, $0758, $0759, $075A, $075B, $075C, $075D, $075E, $075F, $0760
  dw $0761, $0762, $0763, $0764, $0765, $0766, $0767, $0768, $0769, $076A
  dw $076B, $076C, $076D, $076E, $076F, $0770, $0771, $0772, $0773, $0774
  dw $0775, $0776
  dw $0785, $0786, $0787, $0788, $0789, $078A, $078B, $078C, $078D, $078E
  dw $078F, $0790, $0791, $0792, $0793, $0794, $0795, $0796, $0797, $0798
  dw $0799, $079A, $079B, $079C, $079D, $079E, $079F, $07A0, $07A1, $07A2
  dw $07A3, $07A4, $07A5, $07A6, $07A7, $07A8, $07A9, $07AA, $07AB, $07AC
  dw $07AD, $07AE, $07AF, $07B0, $07B1, $07B2, $07B3, $07B4, $07B5, $07B6
  dw $07C5, $07C6
  dw $07C7, $07C8, $07C9, $07CA, $07CB, $07CC, $07CD, $07CE, $07CF, $07D0
  dw $07D1, $07D2, $07D3, $07D4, $07D5, $07D6, $07D7, $07D8, $07D9, $07DA
  dw $07DB, $07DC, $07DD, $07DE, $07DF, $07E0, $07E1, $07E2, $07E3, $07E4
  dw $07E5, $07E6, $07E7, $07E8, $07E9, $07EA, $07EB, $07EC, $07ED, $07EE
  dw $07EF, $07F0, $07F1, $07F2, $07F3, $07F4, $07F5, $07F6
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
if !ENABLE_WATER_FILL_16BIT_COUNT == 1
  dw 168
else
  db 168
endif

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

; =========================================================
; Room $27 Object Attribute Row-28 Hook (0x0133@(25,27))
; =========================================================
; Vanilla Underworld_LoadObjectAttribute (.next_water_overlay_a2) writes #$0808
; to row 28 COLMAPA ($7F2040,X / $7F2042,X) AFTER CustomRoomCollision ($01B95B)
; and, on horizontal room transitions, on the frame after CustomRoomCollision.
; Preserve dry walkable floor/bumpers when dry, and wet bumpers/water/ladder
; stamps when wet. Entered with M=16, X=16; preserves Y, M=16, X=16 on RTL.
WaterGate_WaterOverlayA2_Row28:
{
  LDA.l $7E00A0 : CMP.w #$0027 : BNE .vanilla
  LDA.l $7E0403 : AND.w #$0008 : BNE .wet_room27
  ; Dry Room $27: apply vanilla dry AutoStairsNorthMergedStart ($1D single-layer stairs)
  ; on rows 27..29 of 0x0133@(25,27), clearing row 27 COLMAPB $0A and row 29 COLMAPA $08.
  LDA.w #$0002 : STA.l $7F2000,X : STA.l $7F3000,X
  XBA          : STA.l $7F2002,X : STA.l $7F3002,X
  LDA.w #$1D01 : STA.l $7F2040,X : STA.l $7F3040,X
  XBA          : STA.l $7F2042,X : STA.l $7F3042,X
  LDA.w #$1D1D : STA.l $7F2081,X : STA.l $7F3081,X
  RTL
.wet_room27
  ; Wet Room $27: row 28 under 0x0133 gets side bumpers ($03) + deep water ($08) on COLMAPA & COLMAPB,
  ; and re-applies Room $27 0x0135@(52,27) east ladder stamps after object attribute load.
  LDA.w #$0803 : STA.l $7F2040,X : STA.l $7F3040,X
  XBA          : STA.l $7F2042,X : STA.l $7F3042,X
  PHP : PHX : PHY : PHD
  LDA.w #$0000 : TCD
  JSR WaterGate_ApplyRoom27Ladder
  PLD : PLY : PLX : PLP
  RTL
.vanilla
  LDA.w #$0808
  STA.l $7F2040,X
  STA.l $7F2042,X
  RTL
}

pushpc
org $01BC0A ; @hook module=Dungeons name=WaterGate_WaterOverlayA2_Row28 kind=jsl target=WaterGate_WaterOverlayA2_Row28 expected_m=16 expected_x=16 expected_exit_m=16 expected_exit_x=16
  JSL WaterGate_WaterOverlayA2_Row28
  NOP #7
assert pc() == $01BC15
pullpc

print "End of water_collision.asm        ", pc
