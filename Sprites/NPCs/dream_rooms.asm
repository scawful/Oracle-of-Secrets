; =========================================================
; Dream rooms: each dream room draws with its own BG sheets
;
; Link_WarpToRoom (maple.asm) lands every dream through Module07_15, a
; warp-pad swap that reloads the room header but never uploads BG sheets,
; so a dream room kept the hut's eight (entrance $68: 61 01 13 07 0E 23 1C
; 0F). DreamRoom_LoadSheets loads the room's own set. The Wisdom scene calls
; it from DreamWisdom_Stage (dream_wisdom.asm); DreamRoom_Stage calls it for
; Power (room $00) and Courage (room $31).
;
; Main set = the header blockset ($0AA2), the way the editors preview a room.
; It matches the main GFX of the entrance that normally leads into each
; dream room (ROM data 2026-10-16; Oracle's relocated entrance tables: room
; words $0F:8000, main GFX bytes $0F:9600, read at $02DA74):
;   Wisdom  $51 <- entrance $74, $02   Power $00 <- $7B, $13
;   Courage $31 <- entrance $78, $07
; Recheck that table if a dream room's header or entrance changes.
;
; !ENABLE_DREAM_ROOM_SHEETS (needs !ENABLE_DREAM_RETURN): DreamRoom_Stage
; for Power and Courage. The shared loader also assembles for
; !ENABLE_DREAM_WISDOM_SCENE. Art, objects, landing spots and the dream
; return are unchanged.
; =========================================================

if !ENABLE_DREAM_ROOM_SHEETS == 1
assert !ENABLE_DREAM_RETURN == 1, "ENABLE_DREAM_ROOM_SHEETS requires ENABLE_DREAM_RETURN"

; ---------------------------------------------------------
; JSL from Part00_RoomSprites .end_of_list, every underworld room load.
; M = 8, X = 8, DB = $09. Keeps $00/$02 (list pointer, next free slot).
DreamRoom_Stage:
{
  LDA.b $10 : CMP.b #$07 : BNE .done
  LDA.b $11 : CMP.b #$15 : BNE .done      ; Link_WarpToRoom's swap only
  JSL DreamReturn_IsDreaming : BCC .done
  LDX.w CurrentDream : BEQ .done          ; Wisdom: DreamWisdom_Stage
  CPX.b #$03 : BCS .done
  LDA.w $048F : BNE .done                 ; room being loaded
  LDA.w $048E : CMP.l Link_WarpToRoom_room, X : BNE .done
  JSL DreamRoom_LoadSheets
  .done
  RTL
}
endif

if !ENABLE_DREAM_ROOM_SHEETS == 1 || !ENABLE_DREAM_WISDOM_SCENE == 1

!DR_InitTilesets = $00E19B ; InitializeTilesets (vanilla, JSL/RTL)

; ---------------------------------------------------------
; Room-sprite load in Module07_15 step 3: palettes already black, before the
; tilemap uploads and the fade-in. M = 8, X = 8 on entry and exit.
; $13 first: lag NMIs write INIDISP from $13. The hut return (Module06,
; entrance $68) reloads its own $0AA1 and sheets.
DreamRoom_LoadSheets:
{
  PHB : PHK : PLB
  LDA.b $13 : PHA
  LDA.b #$80 : STA.b $13 : STA.w $2100
  LDA.w $0AA2 : STA.w $0AA1
  JSL !DR_InitTilesets
  SEP #$30
  JSR DreamRoom_ClearPPU
  PLA : STA.b $13
  PLB
  RTL
}

; ---------------------------------------------------------
; Lag NMIs in the next Module07_15 steps turn the display back on without
; uploading anything (they skip NMI_DoUpdates), so the PPU would show the
; hut's HUD and Link for a few frames. Upload the HUD buffer and a hidden OAM
; now, under forced blank, as NMI_DoUpdates does ($008B67, $008BB0).
; M = 8, X = 8 on entry and exit; X preserved.
DreamRoom_ClearPPU:
{
  PHX
  REP #$10
  LDA.b #$F0
  LDX.w #$01FC
  .oam
    STA.w $0801, X                        ; every OAM entry's Y offscreen
    DEX : DEX : DEX : DEX
    BPL .oam
  LDA.b #$80 : STA.w $2115                ; VMAIN: word increment
  LDX.w $0219 : STX.w $2116               ; HUD tilemap address
  LDX.w #$1801 : STX.w $4300              ; DMA0: words to $2118
  LDX.w #$C700 : STX.w $4302
  LDA.b #$7E : STA.w $4304
  LDX.w #$014A : STX.w $4305
  LDA.b #$01 : STA.w $420B
  STZ.w $2102 : STZ.w $2103               ; OAMADDR 0
  LDX.w #$0400 : STX.w $4300              ; DMA0: bytes to $2104
  LDX.w #$0800 : STX.w $4302
  STZ.w $4304
  LDX.w #$0220 : STX.w $4305
  LDA.b #$01 : STA.w $420B
  SEP #$10
  PLX
  RTS
}
endif
