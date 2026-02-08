; Dungeons

incsrc "Dungeons/keyblock.asm"
print  "End of keyblock.asm               ", pc

; Pendant from chest position
org $098823 : LDY.b #$68

; Disable hardcoded sanctuary song
org $028BE7 : NOP #2 ; @hook module=Dungeons name=Sanctuary_Song_Disable kind=patch expected_m=8 expected_x=8

; Fixed color fade-in effect for bed cutscene
; NOTE: This only runs when GameState=0 and specific flag not set (Link's intro)
; Vanilla values restored - previously incorrectly set to all zeros
; Module06_UnderworldLoad bed cutscene block at $028364
org $028364 ; @hook module=Dungeons name=BedCutscene_ColorFix kind=patch expected_m=8 expected_x=8
{
  ; Fixed color for bed cutscene (vanilla values)
  LDA.b #$30 : STA.b $9C   ; COLDATA R component
  LDA.b #$50 : STA.b $9D   ; COLDATA G component
  LDA.b #$80 : STA.b $9E   ; COLDATA B component
  LDA.b #$00
  STA.l $7EC005
  STA.l $7EC006

  JSL $079A2C ; Link_TuckIntoBed
}

incsrc "Dungeons/enemy_damage.asm"
print  "End of enemy_damage.asm           ", pc

incsrc "Dungeons/house_walls.asm"

; Use of Bank 0x2C begins
incsrc "Dungeons/Objects/object_handler.asm"
print  "End of object_handler.asm         ", pc

; Tag: Holes8
incsrc "Dungeons/together_warp_tag.asm"

; Custom Tag: Holes7
; Minish Tag: Holes5
incsrc "Dungeons/custom_tag.asm"

; Tag: Holes0
incsrc "Dungeons/floor_puzzle.asm"
print  "End of floor_puzzle.asm           ", pc

; Crumble Floor Tag: Holes3
incsrc "Dungeons/crumblefloor_tag.asm"

pushpc

incsrc "Dungeons/spike_subtype.asm"

incsrc "Dungeons/attract_scenes.asm"
print  "End of attract_scenes.asm         ", pc

incsrc "Collision/custom_collision.asm"
; water_collision.asm moved to Bank $2C after main dungeon code

incsrc "Collision/CollisionTablesExpanded.asm"
incsrc "Collision/GlobalCollisionTables.asm"

pullpc ; Bank 0x33

TransferDungeonMapGfx:
{
  REP #$20
  LDX #$80 : STX $2100
  LDX #$80 : STX $2115
  LDA #$5000 : STA $2116 ; Destination of the DMA in VRAM
  LDA #$1801 : STA $4300 ; DMA Transfer Mode and destination register
  LDA.w #MapGfx     : STA $4302
  LDX.b #MapGfx>>16 : STX $4304
  LDA #$2000 : STA $4305
  LDX #$01 : STX $420B
  LDX #$0F : STX $2100
  SEP #$30

  LDA.b #$09 : STA.b $14
  RTL

  MapGfx:
    incbin dungeon_maps.bin
}

pushpc
org $0288FF ; @hook module=Dungeons
JSL CheckForTingleMaps : NOP
pullpc

CheckForTingleMaps:
{
  LDA.w $040C : CMP.b #$0C : BEQ .check_mush
                CMP.b #$0A : BEQ .check_tail
                CMP.b #$10 : BEQ .check_castle
                CMP.b #$16 : BEQ .check_zora
                CMP.b #$12 : BEQ .check_glacia
                CMP.b #$0E : BEQ .check_goron
                CMP.b #$18 : BEQ .check_ship
                JMP +
  .check_mush
    LDA.l TingleMaps : AND.b #$01 : BEQ +
      JMP ++
  .check_tail
    LDA.l TingleMaps : AND.b #$02 : BEQ +
      JMP ++
  .check_castle
    LDA.l TingleMaps : AND.b #$04 : BEQ +
      JMP ++
  .check_zora
    LDA.l TingleMaps : AND.b #$08 : BEQ +
      JMP ++
  .check_glacia
    LDA.l TingleMaps : AND.b #$10 : BEQ +
      JMP ++
  .check_goron
    LDA.l TingleMaps : AND.b #$20 : BEQ +
      JMP ++
  .check_ship
    LDA.l TingleMaps : AND.b #$40 : BEQ +
  ++
  LDA.b #$01 : RTL
  +
  LDA.w $040C : CMP.b #$FF : RTL
}

NewWaterOverlayData:
; Horizontal
db $1B, $A1, $C9 ; 0x0C9: Flood water (medium) ⇲ | { 06, 28 } | Size: 0D
db $51, $A1, $C9 ; 0x0C9: Flood water (medium) ⇲ | { 14, 28 } | Size: 05
db $71, $A1, $C9 ; 0x0C9: Flood water (medium) ⇲ | { 1C, 28 } | Size: 05
db $92, $A1, $C9 ; 0x0C9: Flood water (medium) ⇲ | { 24, 28 } | Size: 09
db $A2, $A1, $C9 ; 0x0C9: Flood water (medium) ⇲ | { 24, 28 } | Size: 09
db $C1, $A1, $C9 ; 0x0C9: Flood water (medium) ⇲ | { 28, 0C } | Size: 07

; Vertical
db $A1, $33, $C9 ; 0x0C9: Flood water (medium) ⇲ | { 28, 0C } | Size: 07
db $A1, $72, $C9 ; 0x0C9: Flood water (medium) ⇲ | { 28, 1C } | Size: 06
db $FF, $FF ; End

; Water collision system - placed in Bank $2C after main dungeon code
incsrc "Collision/water_collision.asm"

print "End of dungeons.asm               ", pc

pushpc

; Transfer Dungeon Map Graphics
; Module0E_03_01_00_PrepMapGraphics
org $0AE152 : JSL TransferDungeonMapGfx ; @hook module=Dungeons name=TransferDungeonMapGfx kind=jsl target=TransferDungeonMapGfx

; RoomTag_GetHeartForPrize
; Swap LW/DW check on spawn falling prize
org $01C71B : LDA.l $7EF37A ; Crystals in LW
org $01C727 : LDA.l $7EF374 ; Pendants in DW

RoomTag_OperateWaterFlooring = $01CC95

org $01F195 ; Replace static LDA
LDA $0682

org $01F1C9 ; Replace static LDA
LDA $0682

; Water gate collision write + persistence
org $01F3D2 ; @hook module=Dungeons name=WaterGate_FillComplete_Hook kind=jml target=WaterGate_FillComplete_Hook expected_m=8 expected_x=8
if !ENABLE_WATER_GATE_HOOKS == 1
  JML WaterGate_FillComplete_Hook
  NOP #4 ; Pad to 8 bytes (replaces STZ $1E + STZ $1F + JSL IrisSpotlight_ResetTable)
else
  STZ.b $1E
  STZ.b $1F
  JSL IrisSpotlight_ResetTable
endif

; Underworld_LoadRoom exit hook (torch loop end).
; IMPORTANT:
; We previously installed a JML hook here to run water-gate "room-entry restore"
; logic, but that global hook was implicated in deterministic dungeon transition
; corruption/blackouts.
;
; Persistence restore is now implemented via a safer room-load hook
; (see `Dungeons/Collision/custom_collision.asm`), so we keep this site vanilla.
org $0188DF ; @hook module=Dungeons name=Underworld_LoadRoom_ExitHook kind=patch expected_m=16 expected_x=16
  BNE $0188C9
  SEP #$30


; RoomTag_WaterGate - redirect overlay data to custom water segments
org $01CBAC
if !ENABLE_WATER_GATE_OVERLAY_REDIRECT == 1
  ; Vanilla uses ROM-mirrored banks ($80+). Keep the high-bit set so the tag's
  ; pointer walker always reads from ROM space even when it bankswitches.
  ;
  ; NewWaterOverlayData lives in bank $2C (mirrors at $AC).
  LDA.w #(NewWaterOverlayData>>16)|$0080
  STA.b $B9
  LDA.w #NewWaterOverlayData>>0
  JSR RoomTag_OperateWaterFlooring
else
  ; Vanilla WaterOverlayData pointer (bank $84, addr $EE8B).
  ; Keep as constants so this branch still assembles even when the vanilla
  ; disassembly label isn't available in this codebase.
  LDA.w #$0084
  STA.b $B9
  LDA.w #$EE8B
  JSR RoomTag_OperateWaterFlooring
endif
