; Map & Travel page (MenuScrollLevelH = $40), fourth page of the menu ring:
; Items -R-> Equipment ($20) -R-> Quest ($00) -R-> Map & Travel ($40) -R-> Items.
; Cells: 0 Map, 1 Travel, 2 Songs. $020B is the cursor. A/Y on Songs opens the
; song popup (MenuFlow_SongOpen, Menu/menu_cursor_flow.asm), which binds a song.
; Map and Travel close the menu and act in Menu_Exit (MenuMapTravel_ExitAction):
; Map opens the existing field/dungeon map module, Travel the existing Soaring
; path. No second map renderer and no new destination list. DBR = $2D.

!MenuMapTravel_RowCount = 2                ; Map|Travel row + Songs row

; ---------------------------------------------------------
; Replaces Menu_Page3_Turn under the flag. A = $01 right, else left.
; In/out M/X=8. C set: a turn began.
MenuMapTravel_Turn:
{
  SEP #$30
  JSL MenuFlow_RecordTurn               ; keeps A/X/Y
  CMP.b #$01 : BEQ .right
  REP #$20
  LDA.w #$FFF8 : STA.w MenuScrollHDirection
  SEP #$20
  LDA.w $0200 : CMP.b #!MENU_STATE_ITEM_SCREEN : BEQ .left_items
  LDA.w MenuScrollLevelH : CMP.b #$40 : BEQ .left_map
  CMP.b #$00 : BNE .to_items            ; Equipment L -> Items
  LDA.b #$20 : BRA .to_right_half       ; Quest L -> Equipment
.left_map
  LDA.b #$00 : BRA .to_right_half       ; Map L -> Quest
.left_items
  LDA.b #$40 : BRA .to_right_half       ; Items L -> Map
.right
  REP #$20
  LDA.w #$0008 : STA.w MenuScrollHDirection
  SEP #$20
  LDA.w $0200 : CMP.b #!MENU_STATE_ITEM_SCREEN : BEQ .right_items
  LDA.w MenuScrollLevelH : CMP.b #$40 : BEQ .to_items ; Map R -> Items
  CMP.b #$00 : BEQ .right_quest
  LDA.b #$00 : BRA .to_right_half       ; Equipment R -> Quest
.right_quest
  LDA.b #$40 : BRA .to_right_half       ; Quest R -> Map
.right_items
  LDA.b #$20                            ; Items R -> Equipment
.to_right_half
  STA.w MenuScrollLevelH
  LDA.b #!MENU_STATE_SCROLL_TO
  BRA .begin
.to_items
  LDA.b #!MENU_STATE_SCROLL_FROM
.begin
  STA.w $0200
  LDA.b #$06 : STA.w $012F
  SEC : RTS
}

; ---------------------------------------------------------
; First frame of the turn onto this page (Menu_Page3_ScrollTo). Out: M/X=8.
MenuMapTravel_Init:
{
  JSL MenuFlow_MapInit                  ; cross, remembered cell, or Map
  RTS
}

; ---------------------------------------------------------
; A = cell; returns its icon variant, zero when the cell is empty.
; Keeps X/Y, M/X=8, Z follows A.
MenuMapTravel_Owned:
{
  PHX
  CMP.b #$02 : BCS .song
  CMP.b #$01 : BEQ .travel
  LDA.b #$01 : BRA .done                ; Map
.travel
  LDA.l $7EF34C : BEQ .done             ; no Ocarina: empty cell
  CMP.b #$04 : LDA.b #$07 : BCC .done   ; grey until Soaring is learned
  LDA.b #$03 : BRA .done
.song
  JSL MenuFlow_SongCell                 ; current song's note (variants 2-7), or 0
.done
  PLX
  ORA.b #$00
  RTS
}

; ---------------------------------------------------------
; State $06 on this page. Start closes; L/R are handled by the caller.
MenuMapTravel_Screen:
{
  SEP #$30
  LDA.b $F4 : BIT.b #$10 : BEQ .no_start
    LDA.b #!MENU_STATE_INIT_SCROLL_DOWN : STA.w $0200
    RTS
  .no_start
  LDA.w $020B : PHA
  JSR MenuMapTravel_Move
  SEP #$30
  PLA : EOR.w $020B : TAX               ; X != 0: the cursor moved this frame
  LDA.w $0200 : CMP.b #!MENU_STATE_STATS_SCREEN : BEQ .select
  RTS                                   ; page turn owns the rest of this frame
.select
  TXA : BNE .moved                      ; A/Y act on the cell the player saw
  JSR MenuMapTravel_Select
.moved
  INC.w $0207                           ; cursor blink
  JSR MenuMapTravel_Draw
  SEP #$30
  LDA.b #$23 : STA.w $0116
  LDA.b #$01 : STA.b $17
  RTS
}

; ---------------------------------------------------------
; Horizontal moves skip empty cells and turn the page at a row edge.
; Vertical moves go to the nearest filled column of the next row up/down
; (wrapping), skipping rows with no filled cell.
MenuMapTravel_Move:
{
  SEP #$30
  LDA.b $F4 : AND.b #$0F : BNE +
  RTS
+
  STA.b $04
  LDX.w $020B
  AND.b #$03 : BEQ .vertical
  STX.b $02
.horizontal
  LDX.b $02
  LDA.b $04 : AND.b #$01 : BEQ .left
  LDA.w .next,X : BRA .candidate
.left
  LDA.w .prev,X
.candidate
  CMP.b #$FF : BEQ .turn
  STA.b $02
  JSR MenuMapTravel_Owned : BEQ .horizontal
  BRA .accept
.turn
  LDA.b $04 : AND.b #$01 : BNE .right
  LDA.b #$FF
.right
  JMP Menu_Page3_Turn
.vertical
  LDA.w MenuMapTravel_Columns,X : STA.b $06
  LDA.w MenuMapTravel_Rows,X : STA.b $05 : STA.b $07  ; start row, row tried
.next_row
  LDA.b $04 : AND.b #$08 : BEQ .down                  ; Up
  LDA.b $07 : DEC : BPL .row_ok
  LDA.b #!MenuMapTravel_RowCount-1 : BRA .row_ok
.down
  LDA.b $07 : INC : CMP.b #!MenuMapTravel_RowCount : BCC .row_ok
  LDA.b #$00
.row_ok
  STA.b $07 : CMP.b $05 : BEQ .stay                   ; no other row has a cell
  TAX
  LDA.b #$FF : STA.b $08 : STA.b $02
  LDA.w .starts,X : TAY
  LDA.w .ends,X : STA.b $09
.scan_row
  TYA : JSR MenuMapTravel_Owned : BEQ .next_cell
  TYX
  LDA.w MenuMapTravel_Columns,X : SEC : SBC.b $06 : BCS .distance
  EOR.b #$FF : INC
.distance
  CMP.b $08 : BCS .next_cell
  STA.b $08 : STY.b $02
.next_cell
  INY : CPY.b $09 : BCC .scan_row
  LDA.b $02 : CMP.b #$FF : BNE .accept
  BRA .next_row
.stay
  RTS
.accept
  LDA.b $02 : STA.w $020B
  STZ.w $0207
  LDA.b #$20 : STA.w $012F
  RTS
.next
  db $01,$FF, $FF                       ; $FF = row edge
.prev
  db $FF,$00, $FF
.starts
  db 0,2
.ends
  db 2,3
}
MenuMapTravel_Rows:
  db 0,0, 1
MenuMapTravel_Columns:                  ; absolute icon column (v4)
  db 9,20, 14

; ---------------------------------------------------------
; A or Y. Songs opens the song popup; Map and Travel close the menu and
; leave a request for Menu_Exit. An unavailable action plays the error sound.
MenuMapTravel_Select:
{
  BIT.b $F6 : BMI .pressed
  LDA.b $F4 : BIT.b #$40 : BEQ .done
.pressed
  LDA.w $020B : JSR MenuMapTravel_Owned : BEQ .error
  LDA.w $020B : CMP.b #$02 : BCS .song
  CMP.b #$01 : BEQ .travel
  JSR MenuMapTravel_CanMap : BCC .error
  LDA.b #$01 : BRA .request
.travel
  JSR MenuMapTravel_CanTravel : BCC .error
  LDA.b #$02
.request
  STA.l MenuMapTravel_Pending
  LDA.b #!MENU_STATE_INIT_SCROLL_DOWN : STA.w $0200
  RTS
.song
  JSL MenuFlow_SongOpen                 ; the popup binds the song
.done
  RTS
.error
  LDA.b #$3C : STA.w $012E
  RTS
}

; ---------------------------------------------------------
; C set when the map module may open from the module in $010C (valid in
; the menu and after Menu_Exit). Same gates as the X-button map paths:
; overworld $09; dungeon $07 with CheckForTingleMaps and a room.
MenuMapTravel_CanMap:
{
  LDA.b $1B : BNE .indoors
  LDA.w $010C : CMP.b #$09 : BNE .no
  SEC : RTS
.indoors
  LDA.w $010C : CMP.b #$07 : BNE .no
  JSL CheckForTingleMaps : BEQ .no
  LDA.b $A0 : BEQ .no
  SEC : RTS
.no
  CLC : RTS
}

; ---------------------------------------------------------
; C set when Song of Soaring would work here: song learned, outdoors,
; not the Dark World (that path is Moosh), normal overworld or an enabled
; special-overworld Soaring area, and no travel bird already active.
MenuMapTravel_CanTravel:
{
  LDA.l $7EF34C : CMP.b #$04 : BCC .no
  LDA.b $1B : BNE .no
  LDA.b $8A : AND.b #$40 : BNE .no
  LDA.w $010C : CMP.b #$0B : BNE .normal
if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
  LDA.b $8A : CMP.b #$80 : BCC .no
  CMP.b #$C0 : BCS .no
  SEC : RTS
else
  BRA .no
endif
.normal
  CMP.b #$09 : BNE .no
  LDA.l TravelSpotsVisited : BEQ .no     ; no visited destination yet
  LDX.b #$04
.bird
  LDA.w $0C4A,X : CMP.b #$27 : BEQ .no
  DEX : BPL .bird
  SEC : RTS
.no
  CLC : RTS
}

; ---------------------------------------------------------
; Called by Menu_Exit after the prior module is restored ($10).
; Runs the request once; the gates are checked again first.
MenuMapTravel_ExitAction:
{
  PHP : SEP #$30
  PHB : PHK : PLB
  LDA.l MenuMapTravel_Pending : BEQ .done
  TAY
  LDA.b #$00 : STA.l MenuMapTravel_Pending
  CPY.b #$01 : BNE .travel
  JSR MenuMapTravel_CanMap : BCC .error
  LDA.b #$03 : STA.l MenuMapTravel_Pending ; reopen this page after the map
  STZ.w $0200
  LDA.b #$07                            ; overworld map
  LDX.b $1B : BEQ +
    LDA.b #$03                          ; dungeon map
  +
  STA.b $11
  LDA.b $10 : STA.w $010C
  LDA.b #$0E : STA.b $10
  BRA .done
.travel
  JSR MenuMapTravel_CanTravel : BCC .error
if !ENABLE_SPECIAL_OVERWORLD_SOARING == 1
  LDA.b $10 : CMP.b #$0B : BNE .bird
    JSL SpecialSoaring_Open
    BRA .done
  .bird
endif
  LDA.b #$3E : STA.w $012E              ; Song of Soaring
  LDY.b #$04
  LDA.b #$27
  JSL AddTravelBird
  STZ.w $03F8
  BRA .done
.error
  LDA.b #$3C : STA.w $012E
.done
  PLB : PLP
  RTL
}

; ---------------------------------------------------------
; Replaces "LDA $F4 : AND #$10" in the Start check of Module07/09
; PlayerControl. Pending 3 (a map opened from this page has closed) reads
; as a Start press, so the menu reopens through the vanilla path; the item
; screen then turns to this page. A map opened with X never sets 3.
; In/out M=8; A and Z as the replaced code.
MenuMapTravel_CheckStart:
{
  LDA.l MenuMapTravel_Pending : CMP.b #$03 : BEQ .reopen
  LDA.b $F4 : AND.b #$10
  RTL
.reopen
  LDA.b #$10
  RTL
}

pushpc
assert read4($0288EC) == $1029F4A5, "Module07 Start check moved"
org $0288EC ; Module07_00_PlayerControl ; @hook module=Menu name=MenuMapTravel_CheckStart kind=jsl target=MenuMapTravel_CheckStart expected_m=8
  JSL MenuMapTravel_CheckStart
assert read4($02A54D) == $1029F4A5, "Module09 Start check moved"
org $02A54D ; Module09_00_PlayerControl ; @hook module=Menu name=MenuMapTravel_CheckStart kind=jsl target=MenuMapTravel_CheckStart expected_m=8
  JSL MenuMapTravel_CheckStart
pullpc

; ---------------------------------------------------------
; v4 layout (make_frame_preserved_v4.py): area name header on row 9,
; MAP | TRAVEL labels on row 11 over their icons, SONGS label on row 16 over
; one Songs cell showing the bound song's note. Footer names the cell under
; the cursor, or the highlighted song while the song popup is open.
MenuMapTravel_Draw:
{
  JSR Menu_DrawBackground
  REP #$30
  LDX.w #$0004
.title
  LDA.w .title_text,X : STA.w $1000+menu_offset(6,14),X  ; columns 14-16, same center as EQUIPMENT
  DEX #2 : BPL .title
  LDX.w #$0004
.map_label
  LDA.w .map_text,X : STA.w $1000+menu_offset(11,8),X
  DEX #2 : BPL .map_label
  LDX.w #$000A
.travel_label
  LDA.w .travel_text,X : STA.w $1000+menu_offset(11,18),X
  DEX #2 : BPL .travel_label
  LDX.w #$0008
.songs_label
  LDA.w .songs_text,X : STA.w $1000+menu_offset(16,13),X
  DEX #2 : BPL .songs_label
  JSR MenuMapTravel_AreaName

  SEP #$30
  LDA.b #$7E : STA.b $0A
  LDY.b #$00
.icons
  PHY
  TYA : JSR MenuMapTravel_Owned
  STA.w MenuItemValueSpoof
  REP #$30
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w MenuMapTravel_Gfx,X : TAY
  LDA.w MenuMapTravel_Pos,X : TAX
  LDA.w #MenuItemValueSpoof
  JSR DrawMenuItem
  SEP #$30
  PLY
  INY : CPY.b #$03 : BCC .icons

  LDA.w $020B : CMP.b #$03 : BCS .no_cursor
  JSR MenuMapTravel_Owned : BEQ .no_cursor
  LDA.w $0207 : AND.b #$20 : BNE .no_cursor
  LDA.w $020B : ASL : TAX
  REP #$30
  LDA.w MenuMapTravel_Pos,X : TAX
  LDA.w #$3060 : JSR Menu_Equipment_Bracket
.no_cursor
  SEP #$30
  JSL MenuFlow_MapName : BMI .no_name   ; Names index, $FF = none
  ASL : TAX
  REP #$30
  LDA.w MenuMapTravel_Names,X : TAX
  LDY.w #$0000
.name
  LDA.w $0000,X : STA.w $1692,Y         ; 14 footer cells, end caps kept
  INX #2 : INY #2 : CPY.w #$001C : BCC .name
.no_name
  JSL MenuFlow_DrawSongPopup            ; only while open
  RTS
.title_text
  dw "MAP"
.map_text
  dw "MAP"
.travel_text
  dw "TRAVEL"
.songs_text
  dw "SONGS"
}

; ---------------------------------------------------------
; Current area name, centered on row 9 (the Map page header). Light World and Abyss names
; ($00-$7F, 16 cells each with the AbyssName pad); special areas show none.
; In/out M/X=16.
MenuMapTravel_AreaName:
{
  LDA.b $1B : AND.w #$00FF : BNE .indoors
  LDA.b $8A : AND.w #$00FF : CMP.w #$0080 : BCS .none
  ASL #5 : CLC : ADC.w #OverworldLocationNames
  BRA .have
.indoors
  LDA.b $A0 : ASL #5 : CLC : ADC.w #DungeonLocationNames
.have
  STA.b $00
  LDY.w #$001E
.trim
  LDA.b ($00),Y : CMP.w #$20F5 : BNE .found
  DEY #2 : BPL .trim
  BRA .none                             ; blank name
.found
  INY #2 : STY.b $02                    ; byte length
  LDA.w #$0040 : SEC : SBC.b $02 : LSR : AND.w #$FFFE
  CLC : ADC.w #menu_offset(9,0) : TAX
  LDY.w #$0000
.copy
  LDA.b ($00),Y : STA.w $1000,X
  INX #2 : INY #2 : CPY.b $02 : BCC .copy
.none
  RTS
}

; Index 0 Map, 1 Travel, 2-7 songs 1-6 (MenuFlow_MapName).
MenuMapTravel_Names:
  dw .map,.travel
  dw Menu_SongNames,Menu_SongNames+32,Menu_SongNames+64,Menu_SongNames+96
  dw Menu_SongNames+128,Menu_SongNames+160
.map
  dw "_____MAP______"
.travel
  dw "____TRAVEL____"
MenuMapTravel_Gfx:
  dw MapGFX,OcarinaGFX,QuarterNoteGFX
; DrawMenuItem offsets (absolute minus row 4, col 4). Map (13,9), Travel (13,20),
; Songs (18,14) absolute.
MenuMapTravel_Pos:
  dw menu_offset(9,5),menu_offset(9,16),menu_offset(14,10)
