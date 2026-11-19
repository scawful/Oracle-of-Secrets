; Menu cursor flow (four-page ring, v4): per-page cursor memory, D-pad
; edge crossing onto the matching row of the next page, the direct return
; to the Map page after the field map, and the Quest song row (QuestSongs_*).
; The tunics are Equipment cells (slots 26-28) since 2026-11-18: no popup.
; Assembled in Items bank $2B (Menu bank $2D is full). Every routine is
; called with JSL from bank $2D code, so DBR = $2D: WRAM below $2000 uses
; .w, everything else .l. All routines return with M/X=8.
; WRAM: MenuFlow_* in Core/symbols.asm ($7E02BA-$7E02BF, not saved).

; Visual row (top to bottom) of each Equipment E2 row:
; 0 GEAR (top), 1 Mid (Masks 0-2 | Rings 6-8), 2 Bot (Masks 3-5 | Rings 9-11).
MenuFlow_EquipOrd:
  db 0,1,2,2,0

; In: A = candidate row ordinal, $00 = candidate column. Out: A = cost.
; Cost = |row - source row| * 32 + the column measured from the entry
; edge (turned right: from the left; turned left: from the right).
; Rows 0-3, columns 0-31: the cost fits in 7 bits. M=8. Uses $01.
MenuFlow_Cost:
{
  SEC : SBC.l MenuFlow_CrossRow : INC   ; row - source row
  BPL +
  EOR.b #$FF : INC
+
  ASL #5 : STA.b $01
  LDA.b $00 : EOR.l MenuFlow_CrossDir
  CLC : ADC.b $01
  RTS
}

; ---------------------------------------------------------
; State $01 (Menu_UploadRight). Opens a new menu: clears the cross.
; Opens Map on pending 3 from the field map; otherwise reopens
; the last visited page from MenuFlow_LastPage (0 = Items on left with
; Quest behind it, 1 = Quest, 2 = Equipment, 3 = Map on right with $E4=$0100).
MenuFlow_UploadRight:
{
  SEP #$30
  LDA.b #$00
  STA.l MenuFlow_CrossRow
  LDA.l MenuMapTravel_Pending : CMP.b #$03 : BEQ .map
  LDA.l MenuFlow_LastPage
  CMP.b #$01 : BEQ .quest
  CMP.b #$02 : BEQ .equip
  CMP.b #$03 : BEQ .map
.items_left
  REP #$20
  STZ.b $E4
  SEP #$20
  JSL Menu_Quest_Draw_Long
  SEP #$30
  RTL
.quest
  STZ.w MenuScrollLevelH
  REP #$20
  LDA.w #$0100 : STA.b $E4
  SEP #$20
  JSL Menu_Quest_Init_Long
  JSL Menu_Quest_Draw_Long
  SEP #$30
  RTL
.equip
  LDA.b #$20 : STA.w MenuScrollLevelH
  REP #$20
  LDA.w #$0100 : STA.b $E4
  SEP #$20
  JSL Menu_Equipment_Init_Long
  JSL Menu_Equipment_Draw_Long
  SEP #$30
  RTL
.map
  LDA.b #$40 : STA.w MenuScrollLevelH
  REP #$20
  LDA.w #$0100 : STA.b $E4
  SEP #$20
  JSL MenuFlow_MapInit                  ; clears pending, restores the cell
  JSL MenuMapTravel_Draw_Long
  SEP #$30
  RTL
}

; ---------------------------------------------------------
; Start of state $06 (Menu_Page3_StatsScreen), before its input.
; Remembers MenuFlow_LastPage (1=Quest, 2=Equipment, 3=Map) and the
; Equipment / Map cursors.
MenuFlow_Frame:
{
  SEP #$30
  LDA.w MenuScrollLevelH : AND.b #$FE
  CMP.b #$20 : BEQ .equip
  CMP.b #$40 : BEQ .map
  LDA.b #$01 : STA.l MenuFlow_LastPage
  RTL
.map
  LDA.b #$03 : STA.l MenuFlow_LastPage
  LDA.w $020B : CMP.b #$0A : BCS .done
  INC : STA.l MenuFlow_MapCursor
  RTL
.equip
  LDA.b #$02 : STA.l MenuFlow_LastPage
  LDA.w $020B : CMP.b #$1D : BCS .done
  INC : STA.l MenuFlow_EquipCursor
.done
  RTL
}

; ---------------------------------------------------------
; First line of MenuMapTravel_Turn, before $0200 changes. A = $01 right,
; else left. Records the source row when the D-pad (not L/R) turns the
; page. Quest songs are the bottom row; a cross through Quest with no
; learned song keeps the row.
; Keeps A, X, Y (Items callers use Y afterwards). M/X=8.
MenuFlow_RecordTurn:
{
  PHA : PHX : PHY
  CMP.b #$01 : BEQ +
  LDA.b #$1F
  BRA ++
+
  LDA.b #$00
++
  STA.l MenuFlow_CrossDir
  LDA.b $F6 : AND.b #$30 : BNE .clear   ; L/R: no row to keep
  LDA.w $0200 : CMP.b #$04 : BEQ .items       ; Items (state $04)
  LDA.w MenuScrollLevelH : CMP.b #$40 : BEQ .map
  CMP.b #$20 : BEQ .equip
  LDA.w $020B : CMP.b #$06 : BCS .done  ; Quest, no song: keep
  LDA.b #$03 : BRA .store               ; Quest songs: bottom row
.equip
  LDX.w $020B : CPX.b #$1D : BCS .clear
  LDA.l Menu_Equipment_Rows,X : TAX
  LDA.l MenuFlow_EquipOrd,X
  BRA .store
.map
  LDA.w $020B : BEQ .map_top
  CMP.b #$07 : BCS .map_top             ; Dungeon icons 7..9 live on top row too
  LDA.b #$03 : BRA .store               ; Supplies row: bottom row (ordinal 3)
.map_top
  LDA.b #$00 : BRA .store               ; Map/Dungeon icons: top row (ordinal 0)
.items
  LDX.b #$17
.find
  LDA.l Menu_CustomGridItems,X : CMP.w $0202 : BEQ .found
  DEX : BPL .find
.clear
  LDA.b #$00 : STA.l MenuFlow_CrossRow
  BRA .done
.found
  TXA : LDX.b #$00
.div
  CMP.b #$06 : BCC .row
  SBC.b #$06 : INX : BRA .div           ; C set from CMP
.row
  TXA
.store
  INC : STA.l MenuFlow_CrossRow
.done
  PLY : PLX : PLA
  RTL
}

; ---------------------------------------------------------
; Menu_Equipment_Init, after SwordSlots_Sync. C set: $020B is set.
; A D-pad cross picks the owned slot nearest the source row and the entry
; edge; otherwise the remembered slot, if still owned. C clear: the
; caller's default (bound mask, then the first owned slot).
MenuFlow_EquipRestore:
{
  SEP #$30
  LDA.l MenuFlow_CrossRow : BEQ .memory
  LDA.b #$FF : STA.b $02 : STA.b $03    ; best cost, best slot
  LDX.b #$1C
.scan
  TXA : JSL Menu_Equipment_Owned_Long : BEQ .next
  LDA.l Menu_Equipment_Columns,X : STA.b $00
  PHX
  LDA.l Menu_Equipment_Rows,X : TAX
  LDA.l MenuFlow_EquipOrd,X
  PLX
  JSR MenuFlow_Cost
  CMP.b $02 : BCS .next
  STA.b $02 : STX.b $03
.next
  DEX : BPL .scan
  LDA.b #$00 : STA.l MenuFlow_CrossRow
  LDA.b $03 : BMI .none
  STA.w $020B
  SEC
  RTL
.memory
  LDA.l MenuFlow_EquipCursor : BEQ .none
  DEC : STA.w $020B
  JSL Menu_Equipment_Owned_Long : BEQ .none
  SEC
  RTL
.none
  CLC
  RTL
}

; ---------------------------------------------------------
; MenuMapTravel_Init: first frame on the Map page. D-pad cross picks top
; (0 = Map from left, rightmost owned 9/8/7/0 from right) when source row < 2,
; else bottom edge supply (1 = Banana from left, 6 = Deku Stick from right).
; Otherwise restores remembered MenuFlow_MapCursor (1..10 -> 0..9) if owned,
; or defaults to 0. Clears pending and cross state. M/X=8 out.
MenuFlow_MapInit:
{
  SEP #$30
  STZ.w $0207
  LDA.b #$00
  STA.l MenuMapTravel_Pending
  LDA.l MenuFlow_CrossRow : BEQ .memory
  PHA
  LDA.b #$00 : STA.l MenuFlow_CrossRow
  PLA
  CMP.b #$03 : BCC .top_cross
  LDA.l MenuFlow_CrossDir : BNE .right_edge
  LDA.b #$01 : BRA .set
.right_edge
  LDA.b #$06 : BRA .set
.top_cross
  LDA.l MenuFlow_CrossDir : BEQ .top
  LDA.b #$09
.scan_top_right
  JSL MenuMap_CellOwned_Long : BCS .set
  DEC : CMP.b #$07 : BCS .scan_top_right
.top
  LDA.b #$00 : BRA .set
.memory
  LDA.l MenuFlow_MapCursor : BEQ .top
  CMP.b #$0B : BCS .top
  DEC
  JSL MenuMap_CellOwned_Long : BCC .top
.set
  STA.w $020B
  RTL
}

; ---------------------------------------------------------
; Map & Spoils page cells:
;   0     = World/Dungeon Map icon at (15,15) -> menu_offset(11,11)
;   1..6  = Magic Bag Spoils on row 21, cols 6,9,13,17,21,24 -> menu_offset(17,2/5/9/13/17/20)
;           (4x4 C4 cursor rows 20..23: clear of row 19 divider and row 24 border).
;   7     = Chest Key at (15,18) -> menu_offset(11,14)
;   8     = Big Key   at (15,21) -> menu_offset(11,17)
;   9     = Treasure  at (15,24) -> menu_offset(11,20)
MenuFlow_MapPos:
  dw menu_offset(11,11)
  dw menu_offset(17,2),menu_offset(17,5),menu_offset(17,9)
  dw menu_offset(17,13),menu_offset(17,17),menu_offset(17,20)
  dw menu_offset(11,14),menu_offset(11,17),menu_offset(11,20)

MenuFlow_MapGfx:
  dw MapGFX
  dw BananaGFX,PineappleGFX,RockMeatGFX
  dw SeashellGFX,HoneycombGFX,DekuStickGFX

; ---------------------------------------------------------
; MenuMapTravel_Move: 2D D-pad navigation across Top row (0=Map, 7..9=Dungeon
; icons skipping unowned) and Bottom row (1..6=Spoils). Delegated to Bank $54.
; Out: M/X=8, C set = turn requested (A=$01/$FF), C clear = done.
MenuFlow_MapMove:
{
  JSL MenuMap_Move_Long
  RTL
}

; ---------------------------------------------------------
; End of MenuMapTravel_Draw (DBR = $2D): draws 8x8 Mini-Map, row 19 horizontal
; divider, MAP + 6 supply icons (MenuItemValueSpoof = 1), active 4x4 C4 cursor
; ($0207 bit 5 == 0) over cells 0..9, and $1692 footer label (Map/Dungeon icon
; name or Spoil name + 3-digit stock count). Zero static A:MAP / A:USE prompts.
; Returns M/X=8.
MenuFlow_MapDraw:
{
  ; Runtime 8x8 Overworld Mini-Map on left (rows 11..18, cols 6..13).
  JSL MenuMap_DrawMiniMap_Long

  ; Horizontal wood divider at row 19, cols 6..25.
  REP #$30
  LDX.w #$0026
  LDA.w #$217A
.hdiv
  STA.w $1000+menu_offset(19,6),X
  DEX #2 : BPL .hdiv

  SEP #$30
  LDA.b #$7E : STA.b $0A
  LDA.b #$01 : STA.w MenuItemValueSpoof
  REP #$30
  LDX.w #$0000
.icons
  PHX
  LDA.l MenuFlow_MapGfx,X : TAY
  LDA.l MenuFlow_MapPos,X : TAX
  LDA.w #MenuItemValueSpoof
  JSL DrawMenuItem_Long
  PLX
  INX #2 : CPX.w #$000E : BCC .icons

  SEP #$30
  LDA.w $020B : JSL MenuMap_CellOwned_Long : BCS +
  LDA.b #$00 : STA.w $020B
+
  STA.b $02
  LDA.w $0207 : AND.b #$20 : BNE .no_cursor
  REP #$30
  LDA.b $02 : AND.w #$00FF : ASL : TAX
  LDA.l MenuFlow_MapPos,X : TAX
  JSL Menu_Equipment_Cursor_Long
.no_cursor
  SEP #$30
  LDA.b $02 : BEQ .top_footer
  CMP.b #$07 : BCS .top_footer

  ; Spoils (cells 1..6): name + 3-digit stock count in $1692 footer.
  DEC : STA.b $02                       ; supply slot 0..5
  TAX
  LDA.l Menu_Equipment_CountLow,X : TAX
  LDA.l $7EF300,X : STA.b $03           ; stock count 0..255
  REP #$30
  LDA.b $02 : AND.w #$00FF
  ASL #2 : STA.b $00
  ASL #3 : SEC : SBC.b $00 : TAX        ; slot * 28
  LDY.w #$0000
.supply_footer
  LDA.l Menu_Equipment_SupplyNames,X : STA.w $1692,Y
  INX #2 : INY #2 : CPY.w #$001C : BCC .supply_footer

  LDA.b $03 : AND.w #$00FF
  LDX.w #$06A6
  JSL Menu_Quest_Number3_Long
  SEP #$30
  RTL

.top_footer
  JSL MenuMap_DrawTopFooter_Long
  SEP #$30
  RTL
}

; ---------------------------------------------------------
; Menu_Page3_ScrollFrom, first frame (Items redraw). A D-pad cross moves
; the Items cursor to the owned cell nearest the source row and entry
; edge ($0202 is the cursor, not the Y item; Menu_Bindings_Close restores
; the Y item). Uses $00-$05.
MenuFlow_ItemsEnter:
{
  PHP
  SEP #$30
  LDA.l MenuFlow_CrossRow : BEQ .done
  LDA.b #$FF : STA.b $02 : STA.b $03
  LDA.b #$03 : STA.b $04                ; row of cell X
  LDA.b #$05 : STA.b $05                ; column of cell X
  LDX.b #$17
.scan
  LDA.l Menu_CustomGridItems,X : BEQ .next
  CMP.b #$1B : PHP
  PHX
  TAX : DEX
  LDA.l Menu_AddressLong,X : TAX
  LDA.l $7EF300,X
  PLX : PLP
  BCC .ordinary
  CMP.b #$01 : BNE .next                ; $1B and up: exactly 1
  BRA .owned
.ordinary
  CMP.b #$00 : BEQ .next
.owned
  LDA.b $05 : STA.b $00
  LDA.b $04
  JSR MenuFlow_Cost
  CMP.b $02 : BCS .next
  STA.b $02 : STX.b $03
.next
  DEC.b $05 : BPL +
  LDA.b #$05 : STA.b $05
  DEC.b $04
+
  DEX : BPL .scan
  LDA.b $03 : BMI .clear
  TAX
  LDA.l Menu_CustomGridItems,X : STA.w $0202
.clear
  LDA.b #$00 : STA.l MenuFlow_CrossRow
.done
  PLP
  RTL
}

; ---------------------------------------------------------
; Songs. The six notes sit on the Quest bottom row (Menu_DrawMusicNotes,
; OoT style) in quest order (Menu_SongOrder). On Quest, $020B = highlighted
; slot 0-5 on that row, $FF = none learned.
; Left/Right step through the learned songs; a row edge turns the page
; (Menu_Page3_StatsScreen). A or Y binds the song to the Ocarina.

; In: A = song 1-6, M=8. Out: C set = learned. Keeps A, X, Y.
; In: X = slot 0-5, M/X=8. Out: A = song in the slot, C set = learned.
; Keeps X, Y.
QuestSongs_SlotSong:
{
  LDA.l Menu_SongOrder,X
  JMP MenuFlow_SongOwned
}

MenuFlow_SongOwned:
{
  JSL Ocarina_SongLearned_Long          ; song 6 = Epona bit
  RTS
}

; Out: A = note variant (song + 1) of the bound song, else of the first
; learned song on the row, else 0 (Z follows A). In M/X=8 (QuestSongs_Init).
; Keeps X, Y.
MenuFlow_SongCell:
{
  SEP #$20
  LDA.l $7E0000+CurrentSong
  JSR MenuFlow_SongOwned : BCS .found
  PHX
  LDX.b #$00
.scan
  JSR QuestSongs_SlotSong : BCS .found_x
  INX : CPX.b #$06 : BCC .scan
  PLX
  LDA.b #$00
  RTL
.found_x
  PLX
.found
  INC
  RTL
}


; Menu_Quest_Init. A D-pad cross enters at the edge it came from (turned
; right: the lowest learned song; turned left: the highest). Otherwise the
; bound song, else the lowest learned. The cross row stays for the next
; turn (MenuFlow_RecordTurn overwrites it). M/X=8 out.
QuestSongs_Init:
{
  SEP #$30
  JSL UpdateFluteSong_Long
  SEP #$30
  LDA.l MenuFlow_CrossRow : BEQ .memory
  LDA.l MenuFlow_CrossDir : BNE .highest
  LDX.b #$00
.up
  JSR QuestSongs_SlotSong : BCS .set
  INX : CPX.b #$06 : BCC .up
  BRA .none
.highest
  LDX.b #$05
.down
  JSR QuestSongs_SlotSong : BCS .set
  DEX : BPL .down
  BRA .none
.memory
  JSL MenuFlow_SongCell : BEQ .none     ; A = song + 1
  TAX : LDA.l Menu_SongSlot-2,X : TAX   ; song -> slot
.set
  STX.w $020B
  RTL
.none
  LDA.b #$FF : STA.w $020B
  RTL
}

; Menu_Page3_StatsScreen on Quest, Left or Right pressed. C set: the
; cursor moved to the next learned song (the caller redraws). C clear: no
; learned song that way, the caller turns the page. M/X=8 out.
QuestSongs_Move:
{
  SEP #$30
  LDX.w $020B : CPX.b #$06 : BCS .edge
.step
  LDA.b $F4 : AND.b #$01 : BEQ .left
  INX : CPX.b #$06 : BCS .edge
  BRA .check
.left
  DEX : BMI .edge
.check
  JSR QuestSongs_SlotSong : BCC .step
  STX.w $020B
  STZ.w $0207                           ; show the cursor at once
  LDA.b #$20 : STA.w $012F
  SEC
  RTL
.edge
  CLC
  RTL
}

; Start of Menu_QuestScreen. A or Y binds the highlighted song to the
; Ocarina (Y item), as the old song cells did. C set: input used (the
; caller redraws and skips A's close). M/X=8 out.
QuestSongs_Frame:
{
  SEP #$30
  INC.w $0207                           ; cursor blink
  LDA.w $020B : CMP.b #$06 : BCS .none
  LDA.b $F6 : BMI .bind                 ; A
  LDA.b $F4 : AND.b #$40 : BEQ .none    ; Y
.bind
  LDX.w $020B : LDA.l Menu_SongOrder,X
  STA.w CurrentSong
  STA.l SavedOcarinaSong                ; survives save/reload ($030F does not)
  ; Keep Y's item when Ocarina is already bound to X; otherwise equip Ocarina to Y.
  LDA.l ItemBindingSavedVersion : CMP.b #$01 : BNE .equip_y
  LDA.l ItemBindingSavedX : CMP.b #$0D : BEQ .song_sfx
.equip_y
  LDA.b #$0D : STA.w $0202              ; normal Y item, independent of mask
  STA.l ItemBindingMenuY                ; Menu_Bindings_Close restores $0202 from this
.song_sfx
  STZ.w $0207
  LDA.b #$20 : STA.w $012F
  SEC
  RTL
.none
  CLC
  RTL
}

; End of Menu_Quest_Draw (any M/X in). On the live Quest page (state $06):
; the bound-song marker, the blinking cursor bracket and the highlighted
; song's name in the footer, like the Equipment cells. M/X=8 out.
QuestSongs_DrawCursor:
{
  SEP #$30
  LDA.w $0200 : CMP.b #$06 : BNE .done
  LDA.w MenuScrollLevelH : BNE .done
  LDA.w CurrentSong : DEC : CMP.b #$06 : BCS .no_marker
  INC : JSR MenuFlow_SongOwned : BCC .no_marker
  TAX : LDA.l Menu_SongSlot-1,X         ; song -> slot
  JSR .draw_equipped                    ; full-size 4x4 red C4 rounded frame
.no_marker
  LDA.w $020B : CMP.b #$06 : BCS .done
  LDA.w $0207 : AND.b #$20 : BNE .name
  LDA.w $020B : JSR .draw_active        ; full-size 4x4 Gold C4 L-brackets
.name
  LDX.w $020B : LDA.l Menu_SongOrder,X : DEC
  REP #$30
  AND.w #$00FF : ASL #5 : TAX           ; (song - 1) * 32
  LDY.w #$0000
.char
  LDA.l Menu_SongNames,X : STA.w $1692,Y ; 14 footer cells, end caps kept
  INX #2 : INY #2 : CPY.w #$001C : BCC .char
.done
  SEP #$30
  RTL

; Full-size 4x4 C4 thin rounded red frame around song slot A (0-5). M/X=8 in/out.
.draw_equipped
  ASL : TAX
  REP #$30
  LDA.l Menu_DrawMusicNotes_positions,X : TAX
  LDA.w #$2400
  JSL Menu_C4_DrawEquipBox_Long
  SEP #$30
  RTS

; Full-size 4x4 C4 Gold L-brackets around song slot A (0-5). M/X=8 in/out.
.draw_active
  ASL : TAX
  REP #$30
  LDA.l Menu_DrawMusicNotes_positions,X : TAX
  JSL Menu_C4_DrawEquipCursor_Long
  SEP #$30
  RTS
}
