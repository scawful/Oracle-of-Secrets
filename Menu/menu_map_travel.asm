; Map page (MenuScrollLevelH = $40), fourth page of the menu ring:
; Items -R-> Equipment ($20) -R-> Quest ($00) -R-> Map ($40) -R-> Items.
; Top row right of the 8x8 Mini-Map: Map icon (cell 0, !MapCellPos) plus
; hoverable Dungeon icons (cells 7..9: Chest Key, Big Key, Treasure at
; !DungeonRow). Bottom row: 6 Magic Bag spoils (cells 1..6, Banana..Deku Stick).
; Songs live on the Quest page (QuestSongs_*, Menu/menu_cursor_flow.asm);
; Soaring is played with the Ocarina.
; X anywhere on the page (or A/Y on cell 0) closes the menu and Menu_Exit
; (MenuMapTravel_ExitAction) opens the existing field/dungeon map module.
; A on an owned Spoil (cells 1..6) opens the Spoils Detail/Use Popup
; (!MENU_STATE_SPOIL_POPUP), where A consumes via MagicBag_ConsumeItem. DBR = $2D.

!MapCellPos = menu_offset(11,11)        ; DrawMenuItem offset; absolute (15,15)

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
; State $06 on this page. B/Start close; L/R are handled by the caller.
; X ($F6 bit 6) anywhere on this page launches the full World/Dungeon Map.
MenuMapTravel_Screen:
{
  SEP #$30
  LDA.b $F4 : BIT.b #$90 : BEQ .no_start
    LDA.b #!MENU_STATE_INIT_SCROLL_DOWN : STA.w $0200
    RTS
  .no_start
  LDA.b $F6 : BIT.b #$40 : BEQ .no_x_map
    JSR MenuMapTravel_CanMap : BCC .x_map_err
    LDA.b #$01 : STA.l MenuMapTravel_Pending
    LDA.b #!MENU_STATE_INIT_SCROLL_DOWN : STA.w $0200
    RTS
  .x_map_err
    LDA.b #$3C : STA.w $012E
    BRA .moved
  .no_x_map
  LDA.w $020B : PHA
  JSR MenuMapTravel_Move
  SEP #$30
  PLA : EOR.w $020B : TAX               ; X != 0: the cursor moved this frame
  LDA.w $0200 : CMP.b #!MENU_STATE_STATS_SCREEN : BEQ .select
  RTS                                   ; page turn owns the rest of this frame
.select
  TXA : BNE .moved                      ; A/Y act on the cell the player saw
  JSR MenuMapTravel_Select
  SEP #$30
  LDA.w $0200 : CMP.b #!MENU_STATE_SPOIL_POPUP : BEQ .upload_only
  CMP.b #!MENU_STATE_STATS_SCREEN : BNE .done
.moved
  INC.w $0207                           ; cursor blink
  JSR MenuMapTravel_Draw
.upload_only
  SEP #$30
  LDA.b #$23 : STA.w $0116
  LDA.b #$01 : STA.b $17
.done
  RTS
}

; ---------------------------------------------------------
; Cursor navigation delegated to bank $2B (MenuFlow_MapMove).
; C set on return requests a page turn (A = $01 right, $FF left).
MenuMapTravel_Move:
{
  JSL MenuFlow_MapMove : BCC .done
  JMP Menu_Page3_Turn
.done
  RTS
}

; ---------------------------------------------------------
; A or Y on Map ($020B = 0) closes the menu and leaves the map request for
; Menu_Exit. A ($F6 bit 7; Y never opens/consumes) on an owned Spoil
; ($020B = 1..6) opens the Spoils Detail/Use Popup (!MENU_STATE_SPOIL_POPUP).
; Hovering Dungeon icons ($020B = 7..9) is informational (footer label).
MenuMapTravel_Select:
{
  LDA.w $020B : BNE .supply
  BIT.b $F6 : BMI .pressed
  LDA.b $F4 : BIT.b #$40 : BEQ .done
.pressed
  JSR MenuMapTravel_CanMap : BCC .error
  LDA.b #$01 : STA.l MenuMapTravel_Pending
  LDA.b #!MENU_STATE_INIT_SCROLL_DOWN : STA.w $0200
  RTS
.supply
  CMP.b #$07 : BCS .done
  BIT.b $F6 : BPL .done
  DEC : TAX
  LDA.w Menu_Equipment_CountLow,X : TAX
  LDA.l $7EF300,X : BEQ .error
  LDA.b #$20 : STA.w $012F
  LDA.b #!MENU_STATE_SPOIL_POPUP : STA.w $0200
  JSL MenuSpoil_DrawPopup_Long
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
; Called by Menu_Exit after the prior module is restored ($10).
; Runs a map request (1) once; the gate is checked again first.
MenuMapTravel_ExitAction:
{
  PHP : SEP #$30
  PHB : PHK : PLB
  LDA.l MenuMapTravel_Pending : BEQ .done
  TAY
  LDA.b #$00 : STA.l MenuMapTravel_Pending
  CPY.b #$01 : BNE .done                ; only 1 (open the map) acts here
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

; Overworld map (WorldMap_PlayerControl, $0ABAFB/$0ABB00).
; Vanilla skips $0ABB00 when zoomed in ($0636 != 0), so NOP out that skip
; and check B ($80) / Start ($10) before the zoom gate. When still zoomed in
; ($0636 != 0), ignore X here so .not_switching handles zoom; when zoomed out
; ($0636 == 0), X ($40) exits. A ($F6 bit 7) never exits.
; In/out M=8; Z=0 closes the map, Z=1 keeps it open.
Menu_WorldMapCheckExit:
{
  LDA.b $F4 : AND.b #$90 : BNE .exit
  LDA.l $7E0636 : BNE .stay
    LDA.b $F6 : AND.b #$40
.exit
    RTL
.stay
  LDA.b #$00
  RTL
}

; Dungeon map (DungeonMap_HandleInput, $0AE95E).
; B ($80), Start ($10), or X ($40) exits; A ($F6 bit 7) never exits.
; In/out M=8; Z=0 closes the map, Z=1 keeps it open.
Menu_DungeonMapCheckExit:
{
  LDA.b $F4 : AND.b #$90 : BNE .close
  LDA.b $F6 : AND.b #$40
.close
  RTL
}

pushpc
assert read4($0288EC) == $1029F4A5, "Module07 Start check moved"
org $0288EC ; Module07_00_PlayerControl ; @hook module=Menu name=MenuMapTravel_CheckStart kind=jsl target=MenuMapTravel_CheckStart expected_m=8
  JSL MenuMapTravel_CheckStart
assert read4($02A54D) == $1029F4A5, "Module09 Start check moved"
org $02A54D ; Module09_00_PlayerControl ; @hook module=Menu name=MenuMapTravel_CheckStart kind=jsl target=MenuMapTravel_CheckStart expected_m=8
  JSL MenuMapTravel_CheckStart
assert read4($0ABAFB) == $D00636AD && read1($0ABAFF) == $0A, "WorldMap zoom gate moved"
org $0ABAFB ; WorldMap_PlayerControl ; @hook module=Menu name=Menu_WorldMapZoomGatePatch kind=patch protected_size=5 skip_abi=true
  NOP #5
assert read4($0ABB00) == $4029F6A5, "WorldMap exit check moved"
org $0ABB00 ; WorldMap_PlayerControl ; @hook module=Menu name=Menu_WorldMapCheckExit kind=jsl target=Menu_WorldMapCheckExit expected_m=8 expected_exit_m=8
  JSL Menu_WorldMapCheckExit
assert read4($0AE95E) == $4029F6A5, "DungeonMap_HandleInput exit check moved"
org $0AE95E ; DungeonMap_HandleInput ; @hook module=Menu name=Menu_DungeonMapCheckExit kind=jsl target=Menu_DungeonMapCheckExit expected_m=8 expected_exit_m=8
  JSL Menu_DungeonMapCheckExit
pullpc

; ---------------------------------------------------------
; Menu v5 Map & Spoils page:
;   Title:  " MAP SPOILS " (row 6, cols 10..21)
;   Left:   Runtime 8x8 Overworld Mini-Map (rows 11..18, cols 6..13)
;   Right:  2-line word-wrapped Area Name (rows 11..12, cols 15..26);
;           Map icon (15,15) + hoverable Dungeon icons (ChestKey 15,18;
;           BigKey 15,21; Treasure 15,24) beneath with zero static prompts.
;   Div:    Horizontal wood divider at row 19 (cols 6..25)
;   Bottom: 6 Magic Bag Spoils on row 21 (cols 6,9,13,17,21,24)
MenuMapTravel_Draw:
{
  JSR Menu_DrawBackground
  REP #$30
  LDX.w #$0016
.title
  LDA.w .title_text,X : STA.w $1000+menu_offset(6,10),X
  DEX #2 : BPL .title
  JSR MenuMapTravel_AreaName

  REP #$30
  JSR Menu_DrawBigKey                   ; big key, treasure
  REP #$30
  JSR Menu_DrawBigChestKey
  JSL MenuFlow_MapDraw                  ; mini-map, divider, MAP + 6 spoils, cursor, footer
  RTS
.title_text
  dw "_MAP_SPOILS_"
}

; ---------------------------------------------------------
; Current area name right of the Mini-Map (cols 15..26, rows 11..12,
; wrapping cleanly onto 2 lines at a word boundary when > 12 chars).
; Handles Light World ($00-$3F), Abyss ($40-$7F), Special Overworld ($80-$BF),
; and indoors ($1B != 0). Delegated to Bank $54 (Menu/menu_v5_ext.asm).
; In/out M/X=16.
MenuMapTravel_AreaName:
{
  JSL MenuMap_DrawAreaNameRight_Long
  RTS
}
