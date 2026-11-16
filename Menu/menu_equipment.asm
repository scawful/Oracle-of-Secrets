; Functional Equipment: slots 0-5 masks, 6-11 rings, 12-17 songs, 18-23 supplies,
; 24 story blade, 25 heavy sword (GEAR band, logical row 4).
; v4 bands, top to bottom: GEAR, MASKS, RINGS, then SONGS or SUPPLIES.
; Songs leave band 3 when Map & Travel is on; supplies may then take it.
; $020B is only the cursor; BoundMask, RingSlot1 and CurrentSong are selections.
; No preview fixture or ownership spoof controls availability. DBR = $2D.
; Supplies retain slots/counts but stay hidden until their menu is enabled.
; This is a build policy, not a new save byte or an inventory migration.
if not(defined("MENU_EQUIPMENT_SUPPLIES_VISIBLE"))
  !MENU_EQUIPMENT_SUPPLIES_VISIBLE = 0
endif
assert !ENABLE_MENU_MAP_TRAVEL == 1 || !MENU_EQUIPMENT_SUPPLIES_VISIBLE == 0, "Songs and Supplies share Equipment band 3"
; Two-slot swords: Sword ($7EF359) is the equipped combat/graphics level.
; Sword-slot logic, names and placeholders live in menu_sword_slots.asm
; (Items bank $2B; Menu banks $2D/$2E are full).

Menu_Equipment_Init:
{
  SEP #$30
  JSL SwordSlots_Sync
  JSL UpdateFluteSong_Long
  STZ.w $0207
  LDA.l BoundMask : DEC : CMP.b #$06 : BCS .first
  STA.w $020B
  JSR Menu_Equipment_Owned : BNE .done
.first
  LDA.b #$00
.scan
  STA.w $020B
  JSR Menu_Equipment_Owned : BNE .done
  LDA.w $020B : INC : CMP.b #$1A : BCC .scan
  LDA.b #$FF : STA.w $020B             ; no valid owned entry has no cursor
.done
  RTS
}

; A = slot; returns the bounded icon variant, zero when unavailable.
; Keeps X/Y, 8-bit A/X/Y. Rings require appraisal; hidden supplies are unavailable.
Menu_Equipment_Owned:
{
  PHX
  CMP.b #$06 : BCS .ring
  TAX
  CPX.b #$05 : BNE .legacy_mask
  LDA.l GaroMaskOwned : CMP.b #$01 : BNE .none
  BRA .done
.legacy_mask
  LDA.w .mask_address,X : TAX
  LDA.l $7EF300,X : BEQ .done
  LDA.b #$01 : BRA .done
.ring
  CMP.b #$0C : BCS .song
  SEC : SBC.b #$06 : TAX
  LDA.w Menu_Page3_RingBits,X : AND.l MAGICRINGS : BEQ .done
  TXA : INC #2 : BRA .done
.song
  CMP.b #$12 : BCS .supplies
if !ENABLE_MENU_MAP_TRAVEL == 1
  BRA .none                          ; songs live on the Map & Travel page
else
  SEC : SBC.b #$0B                    ; song 1-6 < Ocarina progression
endif
  CMP.l $7EF34C : BCS .none
  INC : BRA .done                    ; colored note variants 2-7
.supplies
  CMP.b #$18 : BCS .sword
if !MENU_EQUIPMENT_SUPPLIES_VISIBLE == 1
  LDA.b #$01 : BRA .done             ; count never indexes the one-variant icon
else
  BRA .none
endif
.sword
  JSL SwordSlots_Variant : BRA .done
.none
  LDA.b #$00
.done
  PLX
  ORA.b #$00                         ; PLX must not determine caller's Z
  RTS
.mask_address
  db $49,$47,$58,$48,$52,$AF
}

; A = valid supply slot 18-23; returns its byte quantity. Keeps X/Y, M/X=8.
Menu_Equipment_SupplyCount:
{
  PHX
  SEC : SBC.b #$12 : TAX
  LDA.w Menu_Equipment_CountLow,X : TAX
  LDA.l $7EF300,X
  PLX
  ORA.b #$00                         ; report count's Z, not restored X's Z
  RTS
}

; Horizontal movement skips unowned entries, then turns the page at the row edge.
; Vertical movement finds the nearest owned column in the next nonempty row.
Menu_Equipment_Move:
{
  SEP #$30
  LDA.w $020B : CMP.b #$1A : BCC .valid
  LDA.b $F4 : AND.b #$03 : BNE .turn
  JMP Menu_Equipment_Init
.valid
  LDA.b $F4 : AND.b #$0F : BNE +
  RTS
+
  STA.b $04
  LDX.w $020B
  LDA.w Menu_Equipment_Rows,X : STA.b $05
  LDA.b $04 : AND.b #$03 : BEQ .vertical
  LDA.w $020B : STA.b $02
.horizontal
  LDX.b $02
  LDA.b $04 : AND.b #$01 : BEQ .left
  CPX.b #$18 : BCS .gear_right
  LDA.w Menu_Equipment_Columns,X : CMP.b #$17 : BEQ .turn ; last column
  LDA.w .next,X : BRA .candidate
.gear_right
  CPX.b #$19 : BEQ .turn             ; heavy sword is the GEAR row's last cell
  LDA.b #$19 : JSR Menu_Equipment_Owned : BEQ .turn
  LDA.b #$19 : BRA .candidate
.left
  LDA.w Menu_Equipment_Columns,X : CMP.b #$07 : BEQ .turn ; first column
  LDA.w .prev,X
.candidate
  STA.b $02
  JSR Menu_Equipment_Owned : BEQ .horizontal
  BRA .accept
.turn
  LDA.b $F4 : AND.b #$01 : BNE .right
  LDA.b #$FF
.right
  JMP Menu_Page3_Turn
.vertical
  LDA.w Menu_Equipment_Columns,X : STA.b $06
  LDA.b #$04 : STA.b $07              ; inspect other four rows only
.next_row
  LDA.b $04 : AND.b #$04 : BEQ .up
  LDA.b $05 : INC : BRA .row
.up
  LDA.b $05 : DEC
.row
  CMP.b #$FF : BNE +
  LDA.b #$04                          ; up from masks -> GEAR (row 4)
+
  CMP.b #$05 : BCC +
  LDA.b #$00                          ; down from GEAR -> masks
+
  STA.b $05 : TAX
  LDA.b #$FF : STA.b $08 : STA.b $02
  LDA.w .starts,X : TAY
  LDA.w .ends,X : STA.b $09
.scan_row
  TYA : JSR Menu_Equipment_Owned : BEQ .next_cell
  TYX
  LDA.w Menu_Equipment_Columns,X : SEC : SBC.b $06 : BCS .distance
  EOR.b #$FF : INC
.distance
  CMP.b $08 : BCS .next_cell
  STA.b $08 : STY.b $02
.next_cell
  INY : CPY.b $09 : BCC .scan_row
  LDA.b $02 : CMP.b #$FF : BNE .accept
  DEC.b $07 : BNE .next_row
  RTS
.accept
  LDA.b $02 : STA.w $020B
  STZ.w $0207
  LDA.b #$20 : STA.w $012F
.done
  RTS
.next
  db 1,2,3,4,5,0, 7,8,9,10,11,6, 13,14,15,16,17,12, 19,20,21,22,23,18, 25,24
.prev
  db 5,0,1,2,3,4, 11,6,7,8,9,10, 17,12,13,14,15,16, 23,18,19,20,21,22, 25,24
.starts
  db 0,6,12,18,24
.ends
  db 6,12,18,24,26
}
Menu_Equipment_Rows:
  db 0,0,0,0,0,0, 1,1,1,1,1,1, 2,2,2,2,2,2, 3,3,3,3,3,3, 4,4
Menu_Equipment_Columns:
  db 7,10,13,17,20,23, 7,10,13,17,20,23, 7,10,13,17,20,23, 7,10,13,17,20,23, 7,10

Menu_Equipment_Select:
{
  BIT.b $F6 : BMI .pressed
  LDA.b $F4 : BIT.b #$40 : BEQ .done
.pressed
  LDA.w $020B : JSR Menu_Equipment_Owned : BEQ .error
  LDA.w $020B : CMP.b #$18 : BCS .sword
  CMP.b #$06 : BCS .ring
  INC : STA.l BoundMask               ; binding does not transform
  BRA .sound
.ring
  CMP.b #$0C : BCS .song
  SEC : SBC.b #$04                    ; slots 6-11 -> ring IDs 2-7
  JMP Menu_Page3_ToggleRing
.song
  CMP.b #$12 : BCS .supplies
  SEC : SBC.b #$0B : STA.w CurrentSong
  STA.l SavedOcarinaSong              ; survives save/reload ($030F does not)
  LDA.b #$0D : STA.w $0202            ; normal Y item, independent of mask
.sound
  LDA.b #$20 : STA.w $012F
  LDA.b #$20 : STA.w $0207
.done
  RTS
.supplies
  LDA.b $F6 : BIT.b #$80 : BEQ .done ; Y may select above, but never consumes
  LDA.w $020B : PHA
  SEC : SBC.b #$12 : STA.w $020B     ; existing handlers use indices 0-5
  JSR MagicBag_ConsumeItem
  SEP #$30
  PLA : STA.w $020B                  ; restore Equipment's cursor after use
  RTS
.error
  LDA.b #$3C : STA.w $012E
  RTS
.sword                               ; Owned already refused the smith-held $FF
  JSL SwordSlots_Select : BRA .sound
}

Menu_Equipment_Draw:
{
  JSR Menu_DrawBackground
  REP #$30
  LDX.w #$0010
.title
  LDA.w .title_text,X : STA.w $1000+menu_offset(6,11),X
  DEX #2 : BPL .title
  LDX.w #$0008
.labels
  LDA.w .gear,X : STA.w $1000+menu_offset(9,6),X
  LDA.w .masks,X : STA.w $1000+menu_offset(13,6),X
  LDA.w .rings,X : STA.w $1000+menu_offset(17,6),X
if !ENABLE_MENU_MAP_TRAVEL == 0
  LDA.w .songs,X : STA.w $1000+menu_offset(21,6),X
endif
  DEX #2 : BPL .labels
  JSR Menu_Equipment_Gear
if !MENU_EQUIPMENT_SUPPLIES_VISIBLE == 1
  LDX.w #$000E
.supplies_label
  LDA.w .supplies,X : STA.w $1000+menu_offset(21,6),X
  DEX #2 : BPL .supplies_label
endif
  SEP #$30
  LDA.b #$7E : STA.b $0A
  LDY.b #$00
.icons
if !ENABLE_MENU_MAP_TRAVEL == 0
  CPY.b #$12 : BCS .next_icon        ; band 3 holds songs; supplies are hidden
else
  CPY.b #$0C : BCC .draw_icon
  CPY.b #$12 : BCC .next_icon        ; songs live on the Map & Travel page
.draw_icon
endif
  PHY
  TYA : JSR Menu_Equipment_Owned
  STA.w MenuItemValueSpoof
  REP #$30
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w Menu_Equipment_Gfx,X : TAY
  LDA.w Menu_Equipment_Pos,X : TAX
  LDA.w #MenuItemValueSpoof
  JSR DrawMenuItem
  SEP #$30
  PLY
.next_icon
  INY : CPY.b #$18 : BCC .icons

  JSR Menu_Equipment_UsePrompt

  LDA.l BoundMask : DEC : CMP.b #$06 : BCS .no_mask
  JSR .marker
.no_mask
  LDA.l RingSlot1 : SEC : SBC.b #$02 : CMP.b #$06 : BCS .no_ring
  CLC : ADC.b #$06 : JSR .marker
.no_ring
  JSL UpdateFluteSong_Long
  LDA.w CurrentSong : BEQ .no_song
  CLC : ADC.b #$0B : JSR .marker
.no_song
  JSL SwordSlots_MarkerSlot : JSR .marker                        ; Owned hides it while the smiths hold Sword
  LDA.w $020B : JSR Menu_Equipment_Owned : BEQ .no_cursor
  LDA.w $0207 : AND.b #$20 : BNE .no_cursor
  LDA.w $020B : ASL : TAX
  REP #$30
  LDA.w Menu_Equipment_Pos,X : TAX
  LDA.w #$3060 : JSR Menu_Equipment_Bracket
.no_cursor
  SEP #$30
  JSR Menu_Equipment_Name
  RTS
.marker
  TAX
  JSR Menu_Equipment_Owned : BEQ .return
  TXA : ASL : TAX
  REP #$30
  LDA.w Menu_Equipment_Pos,X : TAX
  LDA.w #$2460 : JSR Menu_Equipment_Bracket
  SEP #$30
.return
  RTS
.title_text
  dw "EQUIPMENT"
.gear
  dw "GEAR_"
.masks
  dw "MASKS"
.rings
  dw "RINGS"
.songs
  dw "SONGS"
.supplies
  dw "SUPPLIES"
}

; GEAR band: story blade, heavy sword (cursor slots 24/25), then passive
; shield, tunic, glove, boots, flippers (display only). Passive variants come
; from Menu_Quest_GearVariant, the same SRAM reads Quest used before v4.
Menu_Equipment_Gear:
{
  SEP #$30
  JSL SwordSlots_Sync
  LDA.b #$7E : STA.b $0A              ; DrawMenuItem reads the variant from $7E
  LDY.b #$00
.icons
  PHY
  CPY.b #$02 : BCS .passive
  TYA : CLC : ADC.b #$18 : JSR Menu_Equipment_Owned
  BRA .variant
.passive
  LDA.w .quest_slot,Y : JSR Menu_Quest_GearVariant
.variant
  STA.w MenuItemValueSpoof
  REP #$30
  TYA : AND.w #$00FF : ASL : TAX
  LDA.w .gfx,X : TAY
  LDA.w .pos,X : TAX
  LDA.w #MenuItemValueSpoof
  JSR DrawMenuItem
  SEP #$30
  PLY
  INY : CPY.b #$07 : BCC .icons
  RTS
.quest_slot
  db $00,$00,$13,$14,$0F,$10,$11     ; -, -, shield, tunic, glove, boots, flippers
.pos
  dw menu_offset(6,3),menu_offset(6,6),menu_offset(6,9),menu_offset(6,12)
  dw menu_offset(6,15),menu_offset(6,18),menu_offset(6,21)
.gfx
  dw SwordGFX,SwordGFX,ShieldGFX,TunicGFX,PowerGloveGFX,PegasusBootsGFX,FlippersGFX
}

; Only the three implemented foods advertise Use, and only with stock.
; Menu_DrawBackground clears the prompt when another cell is selected.
Menu_Equipment_UsePrompt:
{
if !MENU_EQUIPMENT_SUPPLIES_VISIBLE == 0
  RTS
endif
  LDA.w $020B : SEC : SBC.b #$12 : CMP.b #$06 : BCS .done
  CMP.b #$02 : BCC .count
  CMP.b #$04 : BNE .done
.count
  LDA.w $020B : JSR Menu_Equipment_SupplyCount : BEQ .done
  REP #$30
  LDX.w #$0008
.text
  LDA.w .prompt,X : STA.w $1000+menu_offset(21,20),X
  DEX #2 : BPL .text
  SEP #$30
.done
  RTS
.prompt
  dw "A:USE"
}

; Two-row brackets use existing corner tiles beside the icon, leaving the
; group label above and following row untouched. X is the icon draw offset.
Menu_Equipment_Bracket:
{
  STA.w $1106,X
  ORA.w #$4000 : STA.w $110C,X
  ORA.w #$8000 : STA.w $114C,X
  EOR.w #$4000 : STA.w $1146,X
  RTS
}

; Footer has exactly 14 interior cells. Never overwrite its end caps.
Menu_Equipment_Name:
{
  LDA.w $020B : JSR Menu_Equipment_Owned : BEQ .done
  LDA.w $020B : ASL : TAX
  CPX.b #$30 : BCC .name
  JSL SwordSlots_Name : BRA .done    ; sword names live in bank $2E
.name
  REP #$30
  LDA.w Menu_Equipment_Names,X : TAX
  LDY.w #$0000
.loop
  LDA.w $0000,X : STA.w $1692,Y
  INX #2 : INY #2 : CPY.w #$001C : BCC .loop
  SEP #$30
  LDA.w $020B : CMP.b #$12 : BCC .done
  JSR Menu_Equipment_SupplyCount
  REP #$30
  AND.w #$00FF
  LDX.w #$06A6                       ; $1692 + 10 name cells, relative to $1000
  JSR Menu_Quest_Number3
.done
  SEP #$30
  RTS
}
; Ten name cells, three quantity cells (drawn above), one final blank.
Menu_Equipment_SupplyNames:
  dw "BANANA________"
  dw "PINEAPPLE_____"
  dw "ROCK_MEAT_____"
  dw "SEASHELL______"
  dw "HONEYCOMB_____"
  dw "DEKU_STICK____"
Menu_Equipment_CountLow:
  db $8B,$8D,$8F,$91,$93,$95
Menu_Equipment_Names:
  dw Menu_ItemNames+(18*32),Menu_ItemNames+(19*32),Menu_ItemNames+(20*32) ; asar math is left to right: keep the parentheses
  dw Menu_ItemNames+(21*32),Menu_ItemNames+(22*32),Menu_GaroLabel
  dw Menu_RingNames,Menu_RingNames+32,Menu_RingNames+64
  dw Menu_RingNames+96,Menu_RingNames+128,Menu_RingNames+160
  dw Menu_SongNames,Menu_SongNames+32,Menu_SongNames+64,Menu_SongNames+96
  dw Menu_SongNames+128,Menu_SongNames+160
  dw Menu_Equipment_SupplyNames,Menu_Equipment_SupplyNames+28,Menu_Equipment_SupplyNames+56
  dw Menu_Equipment_SupplyNames+84,Menu_Equipment_SupplyNames+112,Menu_Equipment_SupplyNames+140
Menu_Equipment_Gfx:
  dw DekuMaskGFX,ZoraMaskGFX,WolfMaskGFX,BunnyHoodGFX,StoneMaskGFX,GaroMaskGFX
  dw RingGFX,RingGFX,RingGFX,RingGFX,RingGFX,RingGFX
  dw QuarterNoteGFX,QuarterNoteGFX,QuarterNoteGFX,QuarterNoteGFX,QuarterNoteGFX,QuarterNoteGFX
  dw BananaGFX,PineappleGFX,RockMeatGFX,SeashellGFX,HoneycombGFX,DekuStickGFX
Menu_Equipment_Pos:
  dw menu_offset(10,3),menu_offset(10,6),menu_offset(10,9),menu_offset(10,13),menu_offset(10,16),menu_offset(10,19)
  dw menu_offset(14,3),menu_offset(14,6),menu_offset(14,9),menu_offset(14,13),menu_offset(14,16),menu_offset(14,19)
  dw menu_offset(18,3),menu_offset(18,6),menu_offset(18,9),menu_offset(18,13),menu_offset(18,16),menu_offset(18,19)
  dw menu_offset(18,3),menu_offset(18,6),menu_offset(18,9)
  dw menu_offset(18,13),menu_offset(18,16),menu_offset(18,19)
  dw menu_offset(6,3),menu_offset(6,6)
