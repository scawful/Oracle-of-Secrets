; Functional Equipment: slots 0-4 masks, 5-10 rings, 11-14 songs, 15-17 gear.
; $020B is only the cursor; BoundMask, RingSlot1 and CurrentSong are selections.
; No preview fixture or ownership spoof controls availability. DBR = $2D.
Menu_Equipment_Init:
{
  SEP #$30
  JSL UpdateFluteSong_Long
  STZ.w $0207
  LDA.l BoundMask : DEC : CMP.b #$05 : BCS .first
  STA.w $020B
  JSR Menu_Equipment_Owned : BNE .done
.first
  LDA.b #$00
.scan
  STA.w $020B
  JSR Menu_Equipment_Owned : BNE .done
  LDA.w $020B : INC : CMP.b #$12 : BCC .scan
  LDA.b #$FF : STA.w $020B             ; empty inventory has no cursor
.done
  RTS
}

; A = slot; returns the bounded icon variant, zero when unavailable.
; Keeps X/Y, 8-bit A/X/Y. Rings are available only after appraisal.
Menu_Equipment_Owned:
{
  PHX
  CMP.b #$05 : BCS .ring
  TAX
  LDA.w .mask_address,X : TAX
  LDA.l $7EF300,X : BEQ .done
  LDA.b #$01 : BRA .done
.ring
  CMP.b #$0B : BCS .song
  SEC : SBC.b #$05 : TAX
  LDA.w Menu_Page3_RingBits,X : AND.l MAGICRINGS : BEQ .done
  TXA : INC #2 : BRA .done
.song
  CMP.b #$0F : BCS .gear
  SEC : SBC.b #$0A                    ; song 1-4 < Ocarina progression
  CMP.l $7EF34C : BCS .none
  INC : BRA .done                    ; colored note variants 2-5
.gear
  CMP.b #$12 : BCS .none
  SEC : SBC.b #$0F : TAX
  LDA.l $7EF354,X : BEQ .done         ; glove, shoes, flippers
  CPX.b #$00 : BNE .boolean
  CMP.b #$03 : BCC .done
  LDA.b #$02 : BRA .done
.boolean
  LDA.b #$01 : BRA .done
.none
  LDA.b #$00
.done
  PLX
  ORA.b #$00                         ; PLX must not determine caller's Z
  RTS
.mask_address
  db $49,$47,$58,$48,$52
}

; Horizontal movement wraps within the row and skips unowned entries.
; Vertical movement finds the nearest owned column in the next nonempty row.
Menu_Equipment_Move:
{
  SEP #$30
  LDA.w $020B : CMP.b #$12 : BCC .valid
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
  LDA.w .next,X : BRA .candidate
.left
  LDA.w .prev,X
.candidate
  STA.b $02
  CMP.w $020B : BEQ .done
  JSR Menu_Equipment_Owned : BEQ .horizontal
  BRA .accept
.vertical
  LDA.w Menu_Equipment_Columns,X : STA.b $06
  LDA.b #$03 : STA.b $07              ; inspect other three rows only
.next_row
  LDA.b $04 : AND.b #$04 : BEQ .up
  LDA.b $05 : INC : BRA .row
.up
  LDA.b $05 : DEC
.row
  AND.b #$03 : STA.b $05 : TAX
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
  db 1,2,3,4,0, 6,7,8,9,10,5, 12,13,14,11, 16,17,15
.prev
  db 4,0,1,2,3, 10,5,6,7,8,9, 14,11,12,13, 17,15,16
.starts
  db 0,5,11,15
.ends
  db 5,11,15,18
}
Menu_Equipment_Rows:
  db 0,0,0,0,0, 1,1,1,1,1,1, 2,2,2,2, 3,3,3
Menu_Equipment_Columns:
  db 7,10,13,17,20, 7,10,13,17,20,23, 7,10,13,17, 7,10,13

Menu_Equipment_Select:
{
  BIT.b $F6 : BMI .pressed
  LDA.b $F4 : BIT.b #$40 : BEQ .done
.pressed
  LDA.w $020B : JSR Menu_Equipment_Owned : BEQ .error
  LDA.w $020B : CMP.b #$05 : BCS .ring
  INC : STA.l BoundMask               ; binding does not transform
  BRA .sound
.ring
  CMP.b #$0B : BCS .song
  SEC : SBC.b #$03                    ; slots 5-10 -> ring IDs 2-7
  JMP Menu_Page3_ToggleRing
.song
  CMP.b #$0F : BCS .done              ; gear is informational
  SEC : SBC.b #$0A : STA.w CurrentSong
  STA.l SavedOcarinaSong              ; survives save/reload ($030F does not)
  LDA.b #$0D : STA.w $0202            ; normal Y item, independent of mask
.sound
  LDA.b #$22 : STA.w $012F
  LDA.b #$20 : STA.w $0207
.done
  RTS
.error
  LDA.b #$3C : STA.w $012E
  RTS
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
  LDA.w .masks,X : STA.w $1000+menu_offset(9,6),X
  LDA.w .rings,X : STA.w $1000+menu_offset(13,6),X
  LDA.w .songs,X : STA.w $1000+menu_offset(17,6),X
  LDA.w .gear,X  : STA.w $1000+menu_offset(21,6),X
  DEX #2 : BPL .labels
  SEP #$30
  LDA.b #$7E : STA.b $0A
  LDY.b #$00
.icons
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
  INY : CPY.b #$12 : BCC .icons

  LDA.l BoundMask : DEC : CMP.b #$05 : BCS .no_mask
  JSR .marker
.no_mask
  LDA.l RingSlot1 : SEC : SBC.b #$02 : CMP.b #$06 : BCS .no_ring
  CLC : ADC.b #$05 : JSR .marker
.no_ring
  JSL UpdateFluteSong_Long
  LDA.w CurrentSong : BEQ .no_song
  CLC : ADC.b #$0A : JSR .marker
.no_song
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
.masks
  dw "MASKS"
.rings
  dw "RINGS"
.songs
  dw "SONGS"
.gear
  dw "GEAR_"
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
  LDA.w $020B : CMP.b #$0F : BCC .table
  CMP.b #$0F : BNE .table
  LDA.l $7EF354 : CMP.b #$02 : BCC .table
  REP #$30
  LDX.w #.mitt : BRA .copy
.table
  LDA.w $020B : ASL : TAX
  REP #$30
  LDA.w Menu_Equipment_Names,X : TAX
.copy
  LDY.w #$0000
.loop
  LDA.w $0000,X : STA.w $1692,Y
  INX #2 : INY #2 : CPY.w #$001C : BCC .loop
.done
  SEP #$30
  RTS
.mitt
  dw "_TITANS_MITT__"
}
Menu_Equipment_GearNames:
  dw "_POWER_GLOVE__"
  dw "PEGASUS_SHOES_"
  dw "___FLIPPERS___"
Menu_Equipment_Names:
  dw Menu_ItemNames+(18*32),Menu_ItemNames+(19*32),Menu_ItemNames+(20*32) ; asar math is left to right: keep the parentheses
  dw Menu_ItemNames+(21*32),Menu_ItemNames+(22*32)
  dw Menu_RingNames,Menu_RingNames+32,Menu_RingNames+64
  dw Menu_RingNames+96,Menu_RingNames+128,Menu_RingNames+160
  dw Menu_SongNames,Menu_SongNames+32,Menu_SongNames+64,Menu_SongNames+96
  dw Menu_Equipment_GearNames,Menu_Equipment_GearNames+28,Menu_Equipment_GearNames+56
Menu_Equipment_Gfx:
  dw DekuMaskGFX,ZoraMaskGFX,WolfMaskGFX,BunnyHoodGFX,StoneMaskGFX
  dw RingGFX,RingGFX,RingGFX,RingGFX,RingGFX,RingGFX
  dw QuarterNoteGFX,QuarterNoteGFX,QuarterNoteGFX,QuarterNoteGFX
  dw PowerGloveGFX,PegasusBootsGFX,FlippersGFX
Menu_Equipment_Pos:
  dw menu_offset(6,3),menu_offset(6,6),menu_offset(6,9),menu_offset(6,13),menu_offset(6,16)
  dw menu_offset(10,3),menu_offset(10,6),menu_offset(10,9),menu_offset(10,13),menu_offset(10,16),menu_offset(10,19)
  dw menu_offset(14,3),menu_offset(14,6),menu_offset(14,9),menu_offset(14,13)
  dw menu_offset(18,3),menu_offset(18,6),menu_offset(18,9)
