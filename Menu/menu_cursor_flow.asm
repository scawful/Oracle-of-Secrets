; Menu cursor flow (Map & Travel ring, v4): per-page cursor memory, D-pad
; edge crossing onto the matching row of the next page, the direct return
; to Map & Travel after the field map, and the worn-tunic popup.
; Assembled in Items bank $2B (Menu bank $2D is full). Every routine is
; called with JSL from bank $2D code, so DBR = $2D: WRAM below $2000 uses
; .w, everything else .l. All routines return with M/X=8.
; WRAM: MenuFlow_* in Core/symbols.asm ($7E02BA-$7E02BE, not saved).

; Visual row (top to bottom) of each Equipment logical row:
; 0 masks, 1 rings, 2 songs, 3 supplies (both in the last band), 4 GEAR (top).
MenuFlow_EquipOrd:
  db 1,2,3,3,0

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
; State $01 (Menu_UploadRight). Opens a new menu: clears the cross and
; the popup. After the field map (pending 3) the right half is Map &
; Travel, shown from the first frame ($E4 = $0100); Menu_Page3_ItemScreen
; then goes straight to state $06. Otherwise the right half is Quest.
MenuFlow_UploadRight:
{
  SEP #$30
  LDA.b #$00
  STA.l MenuFlow_CrossRow
  STA.l MenuFlow_TunicPopup
  LDA.l MenuMapTravel_Pending : CMP.b #$03 : BNE .quest
  LDA.b #$40 : STA.w MenuScrollLevelH
  REP #$20
  LDA.w #$0100 : STA.b $E4
  SEP #$20
  JSL MenuFlow_MapInit                  ; clears pending, restores the cell
  JSL MenuMapTravel_Draw_Long
  SEP #$30
  RTL
.quest
  JSL Menu_Quest_Draw_Long
  SEP #$30
  RTL
}

; ---------------------------------------------------------
; Start of state $06 (Menu_Page3_StatsScreen), before its input.
; Remembers the Equipment / Map & Travel cursor. While the tunic popup is
; open it takes all input: C set = input used, redraw Equipment.
MenuFlow_Frame:
{
  SEP #$30
  LDA.w MenuScrollLevelH : CMP.b #$40 : BNE .not_map
  LDA.w $020B : CMP.b #$08 : BCS .pass
  INC : STA.l MenuFlow_MapCursor
.pass
  CLC
  RTL
.not_map
  CMP.b #$20 : BNE .pass
  LDA.w $020B : CMP.b #$1B : BCS .popup
  INC : STA.l MenuFlow_EquipCursor
.popup
  LDA.l MenuFlow_TunicPopup : BPL .pass
  AND.b #$07 : TAX                      ; X = highlighted colour
  LDA.b $F6 : BPL .no_a
  TXA : JSL Tunic_SetWorn
  BRA .close_sound
.no_a
  LDA.b $F4 : AND.b #$90 : BNE .close   ; B or Start
  LDA.b $F4 : AND.b #$0C : BEQ .used
  AND.b #$08 : BEQ .down
  DEX : BPL .store
  LDA.l Armor : TAX                     ; Up from green: last owned
  BRA .store
.down
  INX : TXA : CMP.l Armor : BEQ .store : BCC .store
  LDX.b #$00                            ; Down past the last owned: green
.store
  TXA : ORA.b #$80 : STA.l MenuFlow_TunicPopup
  BRA .sound
.close_sound
  LDA.b #$00 : STA.l MenuFlow_TunicPopup
.sound
  LDA.b #$20 : STA.w $012F
  BRA .used
.close
  LDA.b #$00 : STA.l MenuFlow_TunicPopup
.used
  SEP #$30
  SEC
  RTL
}

; ---------------------------------------------------------
; First line of MenuMapTravel_Turn, before $0200 changes. A = $01 right,
; else left. Records the source row when the D-pad (not L/R) turns the
; page. Quest has no cursor: a cross through it keeps the row.
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
  CMP.b #$20 : BNE .done                ; Quest: keep
  LDX.w $020B : CPX.b #$1B : BCS .clear
  LDA.l Menu_Equipment_Rows,X : TAX
  LDA.l MenuFlow_EquipOrd,X
  BRA .store
.map
  LDX.w $020B : CPX.b #$08 : BCS .clear
  LDA.l MenuMapTravel_Rows,X
  BRA .store
.items
if !ENABLE_GOLDSTAR_CELL == 1
  LDX.b #$17
.find
  LDA.l Menu_CustomGridItems,X : CMP.w $0202 : BEQ .found
  DEX : BPL .find
endif
.clear
  LDA.b #$00 : STA.l MenuFlow_CrossRow
  BRA .done
if !ENABLE_GOLDSTAR_CELL == 1
.found
  TXA : LDX.b #$00
.div
  CMP.b #$06 : BCC .row
  SBC.b #$06 : INX : BRA .div           ; C set from CMP
.row
  TXA
endif
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
  LDX.b #$1A
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
; MenuMapTravel_Init: first frame on Map & Travel. Cross: nearest owned
; cell to the source row and entry edge. Else the remembered cell if
; owned, else Map (always owned).
MenuFlow_MapInit:
{
  SEP #$30
  JSL UpdateFluteSong_Long
  SEP #$30
  STZ.w $0207
  LDA.b #$00 : STA.l MenuMapTravel_Pending
  LDA.l MenuFlow_CrossRow : BEQ .memory
  LDA.b #$FF : STA.b $02
  STZ.b $03                             ; Map is always owned
  LDX.b #$07
.scan
  TXA : JSL MenuMapTravel_Owned_Long : BEQ .next
  LDA.l MenuMapTravel_Columns,X : STA.b $00
  LDA.l MenuMapTravel_Rows,X
  JSR MenuFlow_Cost
  CMP.b $02 : BCS .next
  STA.b $02 : STX.b $03
.next
  DEX : BPL .scan
  LDA.b #$00 : STA.l MenuFlow_CrossRow
  LDA.b $03
  BRA .set
.memory
  LDA.l MenuFlow_MapCursor : BEQ .set   ; 0 = none: Map
  DEC
  JSL MenuMapTravel_Owned_Long : BNE +
  LDA.b #$00
  BRA .set
+
  LDA.l MenuFlow_MapCursor : DEC
.set
  STA.w $020B
  RTL
}

if !ENABLE_GOLDSTAR_CELL == 1 && !ENABLE_DUAL_ITEM_BINDING_PROTOTYPE == 1
; ---------------------------------------------------------
; Menu_Page3_ScrollFrom, first frame (Items redraw). A D-pad cross moves
; the Items cursor to the owned cell nearest the source row and entry
; edge. Only with dual binding: there $0202 is the cursor, not the Y
; item (Menu_Bindings_Close restores the Y item). Uses $00-$05.
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
endif

; ---------------------------------------------------------
; A on the tunic cell (SwordSlots_Select): open the popup on the worn colour.
MenuFlow_TunicOpen:
{
  JSL Tunic_GetWorn
  SEP #$30
  ORA.b #$80 : STA.l MenuFlow_TunicPopup
  RTL
}

; ---------------------------------------------------------
; Tunic popup, drawn last by SwordSlots_MarkerSlot while open: a small box
; centred under the GEAR band, rows 14 to 16+n, columns 8-23 (n = last
; owned colour). One line per owned colour with the existing
; GREEN/BLUE/RED TUNIC names; the marker shows the highlighted line.
; The tunic cell and the footer stay visible. Uses $08-$0E.
!MENUFLOW_POPUP_TOP  = menu_offset(14,8)
!MENUFLOW_POPUP_LINE = menu_offset(15,8)
MenuFlow_DrawPopup:
{
  REP #$30
  LDA.l Armor : AND.w #$00FF
  CMP.w #$0003 : BCC +
  LDA.w #$0002
+
  STA.b $0E                             ; last line
  LDY.w #!MENUFLOW_POPUP_TOP
  LDA.w #$3811 : LDX.w #$3821
  JSR .edge
  STZ.b $0C
.line
  LDA.b $0C : ASL #6 : CLC : ADC.w #!MENUFLOW_POPUP_LINE : TAY
  LDA.w #$3820 : STA.w $1000,Y
  LDA.w #$7820 : STA.w $101E,Y
  LDA.l MenuFlow_TunicPopup : AND.w #$0007 : CMP.b $0C : BEQ +
  LDA.w #$3417 : BRA ++
+
  LDA.w #$6419                          ; marker
++
  STA.w $1002,Y
  LDA.b $0C : ASL #2 : STA.b $0A
  ASL #3 : SEC : SBC.b $0A              ; line * 28
  CLC : ADC.w #84 : TAX                 ; GREEN/BLUE/RED_TUNIC rows
  LDA.w #13 : STA.b $08
.char
  LDA.l SwordSlots_Name_names,X
  CMP.w #$20F5 : BNE +
  LDA.w #$3417
+
  STA.w $1004,Y
  INX #2 : INY #2
  DEC.b $08 : BNE .char                ; columns 10-22
  INC.b $0C
  LDA.b $0C : CMP.b $0E : BEQ .line : BCC .line
  ASL #6 : CLC : ADC.w #!MENUFLOW_POPUP_LINE : TAY
  LDA.w #$B811 : LDX.w #$B821
  JSR .edge
  SEP #$30
  RTL

; Y = row offset at column 8, A = left corner, X = edge tile. The right
; corner is the left one flipped.
.edge
  STA.w $1000,Y
  ORA.w #$4000 : STA.w $101E,Y
  TXA
  LDX.w #$000E
-
  STA.w $1002,Y
  INY #2
  DEX : BNE -
  RTS
}
