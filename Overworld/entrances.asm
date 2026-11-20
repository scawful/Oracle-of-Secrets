; =========================================================
; Custom Entrance Tile Types
; Can use eithe vanilla map16 @ $0F8000
; Or ZS Expanded @ $3D8000

if !SPECIAL_OVERWORLD_NATIVE == 1
Map16Definitions = !LYRA_CURRENT_MAP16_DEFINITIONS
else
Map16Definitions = $3D8000
endif
Overworld_DrawMap16_Anywhere = $1BC983
Overworld_MemorizeMap16Change = $0EDD40
Interface_PrepAndDisplayMessage = $0FFDAA
Overworld_EntranceTileIndex = $1BBA71
Overworld_EntranceScreens = $1BB96F
Overworld_Entrance_ID = $1BBB73

pushpc
org $1BBBF4 ; @hook module=Overworld
  JSL Overworld_UseEntranceEntry
  RTL
pullpc

Overworld_UseEntranceEntry:
{
  PHB : PHK : PLB
  JSL Overworld_UseEntrance
  PLB
  RTL
}

Overworld_UseEntrance:
{
  REP #$31

  LDA.b $20 : CLC : ADC.w #$0007 : STA.b $00
  SEC : SBC.w $0708 : AND.w $070A
  ASL #3
  STA.b $06

  LDA.b $22 : LSR #3 : STA.b $02
  SEC : SBC.w $070C : AND.w $070E
  CLC : ADC.b $06

  TAY
  TAX

  LDA.l $7E2000, X
  ASL #3
  TAX

  LDA.b $2F : AND.w #$00FF : BEQ .facing_up_entry
    BRL .not_facing_up
  .facing_up_entry
  ; Active UP-intent gate:
  ; - In live overworld gameplay ($10 == $09), require UP ($08) held in $F0 or
  ;   active Pegasus Boots dash ($0372 != 0). Stops standing still, swinging the
  ;   sword/items, or sword-charge strafing (Left/Right/Down) from opening doors
  ;   or sucking Link into flat-wall doorways.
  ; - In zeroed-RAM standalone unit harnesses ($10 != $09), neutral ($F0&$0F==0)
  ;   still passes while any explicit non-UP direction is rejected.
  LDA.b $F0 : AND.w #$000F : BEQ .up_neutral
  BIT.w #$0008 : BNE .up_input_ok
    BRL .no_door
  .up_neutral
  LDA.b $10 : AND.w #$00FF : CMP.w #$0009 : BNE .up_input_ok
  LDA.w $0372 : AND.w #$00FF : BNE .up_input_ok
    BRL .no_door
  .up_input_ok

if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
    #Lyra_SemanticEntranceSite2:
    JSL Lyra_SemanticEntrance2
else
    LDA.l Map16Definitions+2, X
endif
    AND.w #$41FF : CMP.w #$00E9 : BNE .not_left_plain_door
      TYX
      JSL OverworldDoor_FindOpenStyle : BCS .styled
      BRA .check_right_neighbor
    .not_left_plain_door
    CMP.w #$0149 : BEQ .left_side_castle_door
    CMP.w #$0169 : BEQ .left_side_castle_door

    .check_right_neighbor
    TYX

    LDA.l $7E2002, X
    ASL #3
    TAX

if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
    #Lyra_SemanticNeighborSite0:
    JSL Lyra_SemanticNeighbor0
else
    LDA.l Map16Definitions+0, X
endif
    AND.w #$41FF : CMP.w #$4149 : BEQ .right_side_castle_door

    CMP.w #$4169 : BEQ .right_side_castle_door

if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
    CMP.w #$40E9 : BEQ .right_plain_door
    BRL .check_neighbor_door_type
    .right_plain_door
else
    CMP.w #$40E9 :  BNE .check_door_type
endif

    DEY
    DEY
    TYX
    JSL OverworldDoor_FindOpenStyle : BCS .styled
      ; Never stamp vanilla house open-door tiles ($0DA4/$0DA6) onto non-door
      ; scenery that shares char $00E9/$40E9 (e.g. SW $99 Pirate Ship stairs).
      INY
      INY
      TYX
      LDA.l $7E2002, X
      ASL #3
      TAX
if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
      BRL .check_neighbor_door_type
else
      BRL .check_door_type
endif

    .styled
    PHY
    JSL Overworld_DrawMap16_Persist

    PLA : STA.l $7E2002, X

    LDY.w #$0002
    JSL Overworld_DrawMap16_Anywhere

    SEP #$30

    ; SFX3.15
    LDA.b #$15 : STA.w $012F

    LDA.b #$01 : STA.b $14

    RTL

  .not_facing_up
  BRA .check_door_type

  .right_side_castle_door
  DEY
  DEY

if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
  ; Y now names the legacy left door/registration cell (original Y-2),
  ; but X still names the neighbor definition read at original Y+2.
  ; Keep legacy Y on this call's stack while the gate uses source-query Y.
  PHY
  INY : INY : INY : INY
  BRA .castle_source_context
endif

  .left_side_castle_door
if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
  PHY
  .castle_source_context
endif
  STZ.w $0692 : AND.w #$03FF : CMP.w #$0169 : BNE .open_this_castle_door
    ; With the D7 rescue flag, GameState 3 behaves like 2 here (decisions.org).
    LDA.l $7EF3C5 : AND.w #$000F : CMP.w #$0004
if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
    BCS .check_castle_door_type
else
    BCS .check_door_type
endif
      LDA.w #$0018 : STA.w $0692
  .open_this_castle_door
if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
  PLY ; restore the original door cell before any native door behavior
endif
  TYA : SEC : SBC.w #$0080 : STA.w $0698

  SEP #$20

  ; SFX3.15
  LDA.b #$15 : STA.w $012F

  STZ.b $B0
  STZ.w $0690

  LDA.b #$0C : STA.b $11

  SEP #$30

  RTL

if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
  .check_castle_door_type
  #Lyra_SemanticCastleSite4:
  JSL Lyra_SemanticEntrance4 : AND.w #$01FF : STA.b $00
  #Lyra_SemanticCastleSite6:
  JSL Lyra_SemanticEntrance6 : AND.w #$01FF : STA.b $02
  PLY ; rejected castle queries retain legacy Y for registration lookup
  BRA .door_words_ready
  .check_neighbor_door_type
  #Lyra_SemanticNeighborSite4:
  JSL Lyra_SemanticNeighbor4 : AND.w #$01FF : STA.b $00
  #Lyra_SemanticNeighborSite6:
  JSL Lyra_SemanticNeighbor6 : AND.w #$01FF : STA.b $02
  BRA .door_words_ready
endif
  .check_door_type
if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
  #Lyra_SemanticPlainSite4:
  JSL Lyra_SemanticEntrance4 : AND.w #$01FF : STA.b $00
  #Lyra_SemanticPlainSite6:
  JSL Lyra_SemanticEntrance6 : AND.w #$01FF : STA.b $02
  .door_words_ready
else
  LDA.l Map16Definitions+4, X : AND.w #$01FF : STA.b $00
  LDA.l Map16Definitions+6, X : AND.w #$01FF : STA.b $02
endif

  ; Strict directional doorway gate: north-facing doorways ONLY trigger while
  ; facing UP ($2F == $00). Facing LEFT ($04), RIGHT ($06), or DOWN ($02) never
  ; scans ValidDoorTypesExpanded (stops cheap sideways/downward proximity suction
  ; on flat-wall and symmetric-tile entrances). Only explicit directional special
  ; entrances (Wayward Village Tavern back door facing DOWN) run when $2F != $00.
  LDA.b $2F : AND.w #$00FF : BEQ .facing_up_door_checks
    ; Wayward Village Tavern back entrance (E43 at x=45..46, y=34..35):
    ; works with both legacy $05D3-$05D6 and seamless Palette-7 north eave tiles
    ; (where solid $0D5 ridge stops Link's hitbox at $20=$0A20..$0A2F, cell $115A/$115C).
    CMP.w #$0002 : BNE .reject_non_up
    LDA.b $F0 : AND.w #$000F : BEQ .down_neutral
    BIT.w #$0004 : BNE .down_input_ok
      BRL .no_door
    .down_neutral
    LDA.b $10 : AND.w #$00FF : CMP.w #$0009 : BNE .down_input_ok
    LDA.w $0372 : AND.w #$00FF : BEQ .reject_non_up
    .down_input_ok
    LDA.w $040A : CMP.w #$0023 : BNE .reject_non_up
    CPY.w #$11DA : BEQ .bar_back_direct
    CPY.w #$11DC : BEQ .bar_back_enter
    LDA.b $20 : CMP.w #$0A20 : BCC .reject_non_up
    CPY.w #$115A : BEQ .bar_back_enter
    CPY.w #$115C : BNE .reject_non_up
    .bar_back_enter
      LDY.w #$11DA
    .bar_back_direct
      JMP FindEntrance
    .reject_non_up
      BRL .no_door

  .facing_up_door_checks
if !ENABLE_SKY_OVERWORLD_ROUTE == 1
  ; The selected stone arch is already open. Require its map, trigger cell,
  ; recessed arch depth ($20 - $0708 <= $00E2 so Link steps INTO row 14's
  ; walkable bottom rather than triggering 8px early on row 15), and
  ; original dictionary pair before taking the normal registration lookup.
  ; Source graphics may remap rendered words while retaining these Tile16 IDs.
  LDA.w $040A : CMP.w #$0087 : BNE .scan_door_types
  CPY.w #$071E : BNE .scan_door_types
  LDA.b $00 : CMP.w #$01AD : BNE .scan_door_types
  LDA.b $02 : CMP.w #$01AE : BNE .scan_door_types
  LDA.b $20 : SEC : SBC.w $0708 : CMP.w #$00E3 : BCC .sky87_enter
    BRL .no_door
  .sky87_enter
  JMP FindEntrance
  .scan_door_types
endif

  ; Shrine of Courage ($A6) right arch cell ($046C, cx=54, cy=8):
  ; Y=$046C is $FA8 (right arch), while Y+2=$046E is east jamb $FA5 ($00F8/$00F9).
  LDA.w $040A : CMP.w #$00A6 : BNE .not_courage_right
    CPY.w #$046C : BNE .not_courage_right
    LDA.b $00 : CMP.w #$00F8 : BNE .not_courage_right
    LDA.b $02 : CMP.w #$00F9 : BNE .not_courage_right
    JMP FindEntrance
  .not_courage_right

  ; Shrine of Power ($B0):
  ; - Cave arches ($FF6/$FF7/$FF8 at Ent $03/$05/$0B): centering directly under
  ;   the dark arch $FF7 places Y on $FF7 and Y+2 on east jamb $FF8 ($00EA/$00E9).
  ;   Accept center-aligned X (low nibble < 8) and resolve to registered Y-2.
  ; - Mid temple ($FD1/$FD2/$FD3 at Ent $09, Pos $0AAA): accept right stair half
  ;   ($0AAC, Y+2=$FD3 $00CB/$00CB, low nibble < 8) and resolve to $0AAA.
  LDA.w $040A : CMP.w #$00B0 : BNE .not_power_center
    LDA.b $00 : CMP.w #$00EA : BNE .power_check_mid
    LDA.b $02 : CMP.w #$00E9 : BNE .power_check_mid
    LDA.b $22 : AND.w #$000F : CMP.w #$0008 : BCS .power_reject
    DEY : DEY
    JMP FindEntrance
    .power_check_mid
    CPY.w #$0AAC : BNE .not_power_center
    LDA.b $00 : CMP.w #$00CB : BNE .not_power_center
    LDA.b $02 : CMP.w #$00CB : BNE .not_power_center
    LDA.b $22 : AND.w #$000F : CMP.w #$0008 : BCS .power_reject
    DEY : DEY
    JMP FindEntrance
    .power_reject
    BRL .no_door
  .not_power_center

  ; D4 Zora Temple ($1E) 2-tile-wide recessed doorway ([50..51, 3], $58F):
  ; Vanilla row 7 registers left cell $0164 (cx=50); normalize right alcove cell
  ; $0166 (cx=51) so walking up either half enters with the same follower rules.
  LDA.w $040A : CMP.w #$001E : BNE .not_d4_right
    CPY.w #$0166 : BNE .not_d4_right
    LDY.w #$0164
  .not_d4_right

  ; DW $70 recessed caves ($E19/$E1A, rows 111/114/115): Y is $E19 while Y+2
  ; is east jamb $E1A ($0154/$0155). Allow clean north-facing entry.
  LDA.w $040A : CMP.w #$0070 : BNE .not_dw70_door
    LDA.b $00 : CMP.w #$0154 : BNE .not_dw70_door
    LDA.b $02 : CMP.w #$0155 : BNE .not_dw70_door
    JMP FindEntrance
  .not_dw70_door

  ; Size of ValidDoorTypes
  LDX.w #$0068

  .check_next
    LDA.b $00 : CMP.l ValidDoorTypesExpanded_low, X : BNE .low_byte_fail
      LDA.b $02 : CMP.l ValidDoorTypesExpanded_high, X : BEQ .enter_found

    .low_byte_fail
    DEX
    DEX
  BPL .check_next

  .no_door
  STZ.w $04B8

  .message_received
  SEP #$30

  RTL

  .enter_found
  JMP FindEntrance
}

if !SPECIAL_OVERWORLD_SEMANTIC_ENABLED == 1
#Lyra_SemanticEntranceConsumersEnd:
endif

#Overworld_ForbidEntry:
{
  LDA.w $04B8 : BNE .message_received

  INC.w $04B8

  ; MESSAGE 0005
  LDA.w #$0005 : STA.w $1CF0

  SEP #$30

  JML Interface_PrepAndDisplayMessage
}

FindEntrance:
{
  TYA
  STA.b $00

  LDX.w #$0102

  .next_check
  LDA.b $00

  .tile_fail
  DEX
  DEX
  BMI .check_expanded

  CMP.l Overworld_EntranceTileIndex, X : BNE .tile_fail

  LDA.w $040A : CMP.l Overworld_EntranceScreens, X : BNE .next_check

  JSR .CheckFollowerAllowed : BCC +
    BRL Overworld_ForbidEntry
  +

  TXA
  LSR A
  TAX

  SEP #$20
  LDA.l Overworld_Entrance_ID, X
  BRA .commit_entrance_id

  .check_expanded
  LDX.w #$00FE

  .next_expanded
  LDA.b $00

  .expanded_tile_fail
  DEX
  DEX
  BMI .no_entrance_found

  CMP.l Overworld_ExpandedEntranceTileIndex, X : BNE .expanded_tile_fail

  LDA.w $040A : CMP.l Overworld_ExpandedEntranceScreens, X : BNE .next_expanded

  ; Expanded rows behave like single-entrance rows (>= $0076) for follower checks.
  PHX
  LDX.w #$0076
  JSR .CheckFollowerAllowed
  PLX
  BCC +
    BRL Overworld_ForbidEntry
  +

  TXA
  LSR A
  TAX

  SEP #$20
  LDA.l Overworld_ExpandedEntranceID, X

  .commit_entrance_id
  PHA
if defined("ENABLE_HORSE_FORM")
if !ENABLE_HORSE_FORM == 1
  LDA.w $02B2 : CMP.b #$09 : BNE +
    JSL HorseForm_SilentDismount
  +
endif
endif
  PLA
  STA.w $010E

  STZ.b $4D : STZ.b $46

  LDA.b #$0F : STA.b $10

  LDA.b #$06 : STA.w $010C

  STZ.b $11 : STZ.b $B0

  .no_entrance_found
  SEP #$30

  RTL

  ; Checks whether follower state permits entering (X = word offset, M=16 X=16).
  ; Returns Carry clear if allowed, Carry set if entry must be forbidden.
  .CheckFollowerAllowed
  LDA.l $7EF3D3 : AND.w #$00FF : BNE .follower_ok

  LDA.w $02DA : AND.w #$00FF : CMP.w #$0001 : BEQ .follower_deny

  LDA.l $7EF3CC : AND.w #$00FF : BEQ .follower_ok

  ; FOLLOWER 05 / 0E / 01
  CMP.w #$05 : BEQ .follower_ok
  CMP.w #$0E : BEQ .follower_ok
  CMP.w #$01 : BEQ .follower_ok

  ; FOLLOWER 07 / 08 (single-entrance gate for rows >= $0076)
  CMP.w #$07 : BEQ .check_single_entrance
  CMP.w #$08 : BNE .follower_deny

  .check_single_entrance
  CPX.w #$0076 : BCC .follower_deny

  .follower_ok
  CLC
  RTS

  .follower_deny
  SEC
  RTS
}

; Expanded overworld entrance overflow (rows 129..255; total capacity 256 alongside
; the 129 vanilla editor-owned rows at $1B:B96F/$1B:BA71/$1B:BB73). $FFFF tile index
; indicates an unused slot. Allocated in Bank $5E ($5E:8000-$5E:82FF).
pushpc
org $5E8000
Overworld_ExpandedEntrances_Start:
Overworld_ExpandedEntranceScreens:
  ; DW $63 Windmill dual-arch companion cells alongside vanilla row 41 ($035E):
  ; Y=$035C (checks Y+2=FE6), Y=$0360 (checks Y+2=FE8), Y=$0362 (checks Y+2=FE9) -> Ent $33.
  dw $0063, $0063, $0063
  fillbyte $FF : fill 250
assert pc() == $5E8100, "Overworld_ExpandedEntranceScreens must end at $5E8100"
Overworld_ExpandedEntranceTileIndex:
  dw $035C, $0360, $0362
  fillbyte $FF : fill 250
assert pc() == $5E8200, "Overworld_ExpandedEntranceTileIndex must end at $5E8200"
Overworld_ExpandedEntranceID:
  db $33, $33, $33
  fillbyte $FF : fill 253
assert pc() == $5E8300, "Overworld_ExpandedEntranceID must end at $5E8300"
Overworld_ExpandedEntrances_End:
pullpc

; Open-door art keyed by the closed map16 pair at $7E2000,X / $7E2002,X.
; Entry (.open_door) and the overworld load after an exit ($0696) share it.
; In: M=16 X=16, X = map16 index of the left half.
; Out: carry set with A = open left, Y = open right; carry clear if unknown.
OverworldDoor_FindOpenStyle:
{
  PHX
  LDA.l $7E2002, X : PHA
  LDA.l $7E2000, X : PHA
  LDX.w #OverworldDoorStyles_end-OverworldDoorStyles-8
  .next
    LDA.l OverworldDoorStyles+0, X : CMP 1, S : BNE .skip
    LDA.l OverworldDoorStyles+2, X : CMP 3, S : BEQ .found
  .skip
    TXA : SEC : SBC.w #$0008 : TAX
  BPL .next
  PLA : PLA : PLX
  CLC
  RTL

  .found
  PLA : PLA
  LDA.l OverworldDoorStyles+6, X : TAY
  LDA.l OverworldDoorStyles+4, X
  PLX
  SEC
  RTL
}

; Each $0696 exit door must name its closed pair here, or the open door is
; skipped: stale exit/entrance positions would otherwise paste a doorway over
; unrelated tiles.
OverworldDoorStyles:
  ;  closed L, closed R, open L, open R
  dw $00FB, $00FC, $0DA4, $0DA6 ; house door
  dw $075D, $075E, $0DA4, $0DA6 ; house door, palette 6 panel ($06, $4B)
  dw $05D8, $05D9, $0DA4, $0DA6 ; house door, palette 7 ($23 entrance $42)
  dw $0B82, $0B83, $0FFC, $0FFD ; Kalyxo boat cabin ($38); $38's sheet lacks FE/FF
OverworldDoorStyles_end:

; $02EEE8 opens the exit door at $0696 with fixed house tiles $0DA4/$0DA6.
; M=16 X=16; X = $0696 (below $8000). The bit-15 $0DB4/$0DB5 path is unchanged.
OverworldDoor_ExitOpen:
{
  JSL OverworldDoor_FindOpenStyle : BCC .skip
  PHY
  STA.l $7E2000, X
  JSL Overworld_MemorizeMap16Change
  PLA
  JML $02EF1A ; STA $7E2002,X, memorize, STZ $0696

  .skip
  JML $02EF26 ; STZ $0696
}

pushpc
assert read4($02EEF7) == $9F0DA4A9 && read3($02EEFB) == $7E2000, "Exit open-door draw $02EEF7 moved"
assert read4($02EF1A) == $7E20029F && read3($02EF26) == $06969C, "Exit open-door return sites moved"
org $02EEF7 ; @hook module=Overworld name=OverworldDoor_ExitOpen kind=jml target=OverworldDoor_ExitOpen expected_m=16 expected_x=16 protected_size=7
  JML OverworldDoor_ExitOpen : NOP #3
assert pc() == $02EEFE
pullpc


; $DB8BF-$DB916 - chr types indicating door entrances

ValidDoorTypesExpanded_low:
 dw $00FE, $00C5, $00FE, $0114 ; 00: ???, House Door, ???, ???
 dw $0115, $0175, $0156, $00F5 ; 01:
 dw $00E2, $01EF, $0119, $00FE ; 02: ???, ???, ???, Desert Door
 dw $0172, $0177, $013F, $0172 ; 03:
 dw $0112, $0161, $0172, $014C ; 04: ???, ???, Dam Door, ???
 dw $0156, $01EF, $00FE, $00FE ; 05:
 dw $00FE, $010B, $0173, $0143 ; 06: ???, ???, ???, Tower of Hera
 dw $0149, $0175, $0103, $0100 ; 07:
 dw $01C6, $015E, $0167, $0128 ; 08: Waterfall, ???, ???, ???
 dw $0131, $0112, $016D, $0163 ; 09:
 dw $0173, $00FE, $0113, $0177 ; 10:
 dw $00EA, $013B, $0174, $011B ; 11: Lava Land Large, Lava Land Small, Goron Mines, Docks Boat Door
  dw $0114, $00C5, $00E9, $01A4  ; 12: Docks Deck Hatch 0x572, Wisdom 0x7CD, Power 0xFF6, Windmill Arch 0xFE6/0xFE8 (BL)
  dw $0139                       ; 13: Windmill Right-Arch East Jamb 0xFE9 (BL)

ValidDoorTypesExpanded_high:
 dw $014A, $00C4, $014F, $0115 ; ???, House Door, ???, ???
 dw $0114, $0174, $0155, $00F5 ; 01:
 dw $00EE, $01EB, $0118, $0146 ; ???, ???, ???, Desert Door
 dw $0171, $0155, $0137, $0174 ; 03:
 dw $0173, $0121, $0164, $0155 ; ???, ???, Dam Door, ???
 dw $0157, $0128, $0114, $0123 ; 05:
 dw $0113, $0109, $0118, $0161 ; ???, ???, ???, Tower of Hera
 dw $0149, $0117, $0174, $0101 ; 07:
 dw $01C6, $0131, $0051, $014E ; Waterfall, ???, ???, ???
 dw $0131, $0112, $017A, $0163 ; 09:
 dw $0172, $01BD, $0152, $0167 ; 10:
 dw $00EB, $013A, $0174, $011A
 dw $00FE, $00C5, $00EA, $01A4  ; 12: Docks Deck Hatch 0x572, Wisdom 0x7CD, Power 0xFF6, Windmill Arch 0xFE6/0xFE8 (BR)
 dw $0138                       ; 13: Windmill Right-Arch East Jamb 0xFE9 (BR)
ValidDoorTypesExpanded_end:

assert ValidDoorTypesExpanded_high-ValidDoorTypesExpanded_low == $6A
assert ValidDoorTypesExpanded_end-ValidDoorTypesExpanded_high == $6A

pushpc

; $DB8BF (0x2C entries, 2 bytes each) - valid map8 (CHR) values for entrances (left side)
; $DB917 (0x2C entries, 2 bytes each) - valid map8 (CHR) values for entrances (right side)

; $DB8BF-$DB916 - chr types indicating door entrances
org $1BB8BF
ValidDoorTypes_low:
 dw $00FE, $00C5, $00FE, $0114 ; 00: ???, House Door, ???, ???
 dw $0115, $0175, $0156, $00F5 ; 01:
 dw $00E2, $01EF, $0119, $00FE ; 02: ???, ???, ???, Desert Door
 dw $0172, $0177, $013F, $0172 ; 03:
 dw $0112, $0161, $0172, $014C ; 04: ???, ???, Dam Door, ???
 dw $0156, $01EF, $00FE, $00FE ; 05:
 dw $00FE, $010B, $0173, $0143 ; 06: ???, ???, ???, Tower of Hera
 dw $0149, $0175, $0103, $0100 ; 07:
 dw $01C6, $015E, $0167, $0128 ; 08: Waterfall, ???, ???, ???
 dw $0131, $0112, $016D, $0163 ; 09:
 dw $0173, $00FE, $0113, $0177 ; 10:



ValidDoorTypes_high:
 dw $014A, $00C4, $014F, $0115 ; ???, House Door, ???, ???
 dw $0114, $0174, $0155, $00F5 ; 01:
 dw $00EE, $01EB, $0118, $0146 ; ???, ???, ???, Desert Door
 dw $0171, $0155, $0137, $0174 ; 03:
 dw $0173, $0121, $0164, $0155 ; ???, ???, Dam Door, ???
 dw $0157, $0128, $0114, $0123 ; 05:
 dw $0113, $0109, $0118, $0161 ; ???, ???, ???, Tower of Hera
 dw $0149, $0117, $0174, $0101 ; 07:
 dw $01C6, $0131, $0051, $014E ; Waterfall, ???, ???, ???
 dw $0131, $0112, $017A, $0163 ; 09:
 dw $0172, $01BD, $0152, $0167 ; 10:

pullpc


; 0x00 - OW
; 0x01 - OW 32 - Link's House
; 0x02 - OW 0E - Hall of Secrets
; 0x03 - OW 4B - Shrine of Power
; 0x04 - OW
; 0x05 - OW 4B - Shrine of Power
; 0x06 - OW 15 - Mountain to Witch Shop Cave Start
; 0x07 - OW 0D - Mountain to Witch Shop Cave End
; 0x08 - OW XX - Available
; 0x09 - OW 4B - Shrine of Power
; 0x0A - OW 0B - Kalyxo Castle Secret Courtyard
; 0x0B - OW 4B - Shrine of Power
; 0x0C - OW 50 - Shrine of Courage
; 0x0D - OW 18 - Mushroom House
; 0x0E - OW 18 - Old Woman House
; 0x0F - OW
; 0x10 - OW
; 0x11 - OW 0B - 1/2 Magic Cave
; 0x12 - OW 02 - Hall of Secrets Pyramid Route
; 0x13 - OW 15 - Deluxe Fairy Fountain Pond
; 0x14 - OW 15 - Deluxe Fairy Fountain Start
; 0x15 - OW 2F - Tail Palace
; 0x16 - OW 07 - Snow Mountain Cave East Peak
; 0x17 - OW 05 - Snow Mountain Cave to the East Peak
; 0x18 - OW 40 - Master Sword Cave
; 0x19 - OW 40 - Master Sword Cave
; 0x1A - OW 32 - Beach Cave Route
; 0x1B - OW    - Beach Cave End
; 0x1C - OW 33 - Beach Cave Intro
; 0x1D - OW
; 0x1E - OW 0D - Snow Mountain Cave Start
; 0x1F - OW 05 - Snow Mountain Cave Portal
; 0x20 - OW 0D - Snow Mountain Cave End
; 0x21 - OW 25 - Kalyxo Field Cave Start
; 0x22 - OW 25 - Kalyxo Field Cave River
; 0x23 - OW 25 - Kalyxo Field Cave End
; 0x24 - OW 46 - Final Boss Route
; 0x25 - OW 1E - Zora Temple
; 0x26 - OW 10 - Mushroom Grotto
; 0x27 - OW 36 - Goron Mines
; 0x28 - OW 0B - Kalyxo Castle West Entrance
; 0x29 - OW XX - Available
; 0x2A - OW 0B - Kalyxo Castle Basement Route
; 0x2B - OW 0B - Kalyxo Castle Main Entrance
; 0x2C - OW 18 - Toadstool Woods Log Cave
; 0x2D - OW 40 - Master Sword Cave
; 0x2E - OW 2D - Tail Palace Cave Route Start
; 0x2F - OW 2E - Tail Palace Cave Route End
; 0x30 - OW 07 - Snow Mountain East Peak To West Peak
; 0x31 - OW 04 - Snow Mountain West Peak To East Peak
; 0x32 - OW 0B - Kalyxo Castle Prison Entrance
; 0x33 - OW 63 - Shrine of Wisdom
; 0x34 - OW 06 - Glacia Estate
; 0x35 - OW 38 - Dragon Ship
; 0x36 - OW
; 0x37 - OW 5E - Fortress of Secrets
; 0x38 - OW 11 - Healing Fairy Cave (Exit)
; 0x39 - OW
; 0x3A - OW 1D - Deluxe Fairy Fountain East
; 0x3B - OW 1D - Deluxe Fairy Fountain South
; 0x3C - OW
; 0x3D - OW
; 0x3E - OW 00 - Ranch Shed
; 0x3F - OW 00 - Ocarina Girls House
; 0x40 - OW 23 - Sick Boys House
; 0x41 - OW
; 0x42 - OW 23 - Village Tavern
; 0x43 - OW
; 0x44 - OW 23 - Village House
; 0x45 - OW 1E - Zora Princess House
; 0x46 - OW 23 - Village Shop
; 0x47 - OW
; 0x48 - OW
; 0x49 - OW 23 - Village Library
; 0x4A - OW
; 0x4B - OW 00 - Chicken House
; 0x4C - OW 0D - Witch Shop
; 0x4D - OW
; 0x4E - OW 1E - Zora Temple Waterfall
; 0x4F - OW 43 - Lava Cave Start
; 0x50 - OW 0E - Cave of Secrets
; 0x51 - OW 15 - Rock Heart Piece Cave
; 0x52 - OW 43 - Lava Cave End
; 0x53 - OW
; 0x54 - OW
; 0x55 - OW
; 0x56 - OW
; 0x57 - OW
; 0x58 - OW
; 0x59 - OW 18 - Archery Minigame (SW Log Cabin, Toadstool Woods)
; 0x5A - OW
; 0x5B - OW 0F - Hidden Grave
; 0x5C - OW 0F - Graveyard Waterfall
; 0x5D - OW
; 0x5E - OW
; 0x5F - OW 36 - Mines Shed
; 0x60 - OW 0A - West Hotel
; 0x61 - OW 23 - Village Mayors House
; 0x62 - OW
; 0x63 - OW
; 0x64 - OW 22 - Smiths House
; 0x65 - OW Fortune Teller
; 0x66 - OW Fortune Teller
; 0x67 - Unassigned (Chest Minigame, freed for Lyra Sea)
; 0x68 - OW 18 - Bonzai House
; 0x69 - OW
; 0x6A - OW
; 0x6B - OW 2D - Happy Mask Salesman Shop
; 0x6C - OW
; 0x6D - OW
; 0x6E - OW
; 0x6F - OW
; 0x70 - OW
; 0x71 - OW
; 0x72 - OW
; 0x73 - OW
; 0x74 - OW
; 0x75 - OW
; 0x76 - OW
; 0x77 - OW
; 0x78 - OW
; 0x79 - OW
; 0x7A - OW
; 0x7B - OW
; 0x7C - OW
; 0x7D - OW
; 0x7E - OW
; 0x7F - OW
; 0x80 - OW
