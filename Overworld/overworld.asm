; Overworld.asm

; Random chance of hearts from bush instead of guards
org $1AFBBF : db $0B ; Heart Index
org $1AFBC7 : db $0B ; Heart Index
org $1AFBD7 : db $00

; Remove rain sound effects from beginning
org $02838C : LDA.l $7EF3C5 : CMP.b #$00

; RoomTag_GanonDoor
; Replace SprState == 04 -> .exit
org $01C769 : LDA.w SprState, X : CMP.b #$02

; Credits_LoadNextScene_Overworld
; Skip end cutscene until it's ready
org $0E9889 : LDA #$20 : STA $11 : RTS

; =========================================================
; Special Area Properties

org $0EDE29
{
  ; corresponding warp types that lead to special overworld areas
  dw $01EF, $01EF, $00AD, $00B9

  ; Lost woods, Hyrule Castle Bridge, Entrance to Zora falls, and in Zora Falls...
  dw $002A, $0018, $000F, $0081

  ; Direction Link will face when he enters the special area
  dw $0008, $0008, $0008, $0008

  ; Exit value for the special area. In Hyrule Magic these are those White markers.
  dw $0180, $0181, $0182, $0189
}

; =========================================================
; Exit 180 to Master Sword Area

; Sprite GFX
org $02E811 : db $0C ; PC Address $016811
; Background GFX
org $02E821 : db $2F ; PC Address $016821
; Palette
org $02E831 : db $0A ; PC Address $016831
; Sprite Palette
org $02E841 : db $01 ; PC Address $016841

; =========================================================
; Exit 181 to Bridge Area

; Sprite GFX
org $02E812 : db $25 ; PC Address $016812
; Background GFX
org $02E822 : db $2F ; PC Address $016822
; Palette
org $02E832 : db $0A ; PC Address $016832
; Sprite Palette
org $02E842 : db $08 ; PC Address $016842

; =========================================================
; Exit 182 to Zora's Waterfall

; Sprite GFX
org $02E813 : db $0E ; PC Address $016813
; Background GFX
org $02E823 : db $2F ; PC Address $016823
; Palette
org $02E833 : db $0A ; PC Address $016833
; Sprite Palette
org $02E843 : db $03 ; PC Address $016843
; Disable Zora's Waterfall SFX
org $02C444 : db $55 ; PC Address $014444

; =========================================================

incsrc "Overworld/lost_woods.asm"
print  "End of Overworld/lost_woods.asm   ", pc

org $348000 ; Free space
pushpc
incsrc "Overworld/time_system.asm"
print  "End of Overworld/time_system.asm  ", pc

incsrc "Overworld/overlays.asm"
print  "End of Overworld/overlays.asm     ", pc

incsrc "Overworld/entrances.asm"

incsrc "Overworld/custom_gfx.asm"
print  "End of Overworld/custom_gfx.asm   ", pc
pushpc

incsrc "Overworld/world_map.asm"
print "End of world_map.asm              ", pc

; =========================================================
; Get Lv2 Sword from chest
; Get Lv4 Sword from pedestal

; At 04/87CA, change D0 into 80
org $0987CA : db $80

; Disable wind blowing sfx:
; At 04/45D4, change 09 into 00
org $08C5D4 : db $00

; MasterSword_HandleReceipt
org $0589AF : LDY.b #$03 ; ITEMGET 03

; Module15_0C
; Prevent the game from setting $7EF3C7 to 06
org $029E58 : NOP #6

pullpc
LoadDarkWorldIntro:
{
  ; If we have the old man, set us indoors and dark world
  LDA.l $7EF3C8 : CMP.b #$05 : BNE .not_dw_spawn
    LDA.b #$01 : STA.b $1B
    LDA.b #$40 : STA.l $7EF3CA
    RTL
  .not_dw_spawn
  LDA.l $7EF3C5 : CMP.b #$02 : BNE .continue
    ; Check for maku tree progress flag
    LDA.l $7EF3D6 : CMP.b #$02 : BCS .has_pearl
      STZ.w $1B
      LDA.b #$40 : STA.l $7EF3CA
      RTL
    .continue
  .has_pearl
  ; Check if the player was in a dungeon when they saved
  LDA.b $1B : BNE .indoors
    LDA.l $7EF3CA
   .indoors
  RTL
}
pushpc

; Module05_LoadFile
org $028192 : JSL LoadDarkWorldIntro

; Module05_LoadFile
; Check for goldstar instead of mirror for mountain spawn option
org $0281E2 : LDA.l $7EF342 : CMP.b #$02

; Check for hall of secrets spawn pt flag
org $0281CD : LDA.l $7EF3D6 : CMP.b #$04

; GameOver_FadeAndRevive
org $09F520 : LDA.l $7EF3C5 : CMP.b #$02

pullpc
LoadOverworldPitAreas:
{
  LDA $8A : CMP.b #$0F : BEQ .allow_transition
            CMP.b #$11 : BEQ .allow_transition
            CMP.b #$23 : BEQ .allow_transition
            CMP.b #$57 : BEQ .allow_transition
    SEC ; fall in the pit
    RTL
  .allow_transition
  CLC ; allow transition
  RTL
}

Overworld_GetPitDestination = $1BB860

; DetermineConsequencesOfFalling
org $0794D9
  JSL LoadOverworldPitAreas : BCC .overworld_pit_transition
    JSL $01FFD9 ; TakeDamageFromPit
    RTS
.overworld_pit_transition

org $1AF5C3 : CMP.b #$5E

org $0EF581
EXIT_0EF581:

; FlashGanonTowerPalette
org $0EF587
  LDA.b $8A : CMP.b #$73 : BEQ .on_dark_dm
              CMP.b #$75 : BEQ .on_dark_dm
              CMP.b #$7D : BNE EXIT_0EF581
  .on_dark_dm

org $0EF531
Palettes_GanonTowerFlash:
  dw  $7FFF,  $0884,  $1CC8,  $1DCE,  $3694,  $4718,  $1D4A,  $18AC
  dw  $7FFF,  $1908,  $2D2F,  $3614,  $4EDA,  $471F,  $1D4A,  $390F
  dw  $7FFF,  $34CD,  $5971,  $5635,  $7F1B,  $7FFF,  $1D4A,  $3D54
  dw  $7FFF,  $1908,  $2D2F,  $3614,  $4EDA,  $471F,  $1D4A,  $390F
  dw  $7FFF,  $0884,  $052A,  $21EF,  $3AB5,  $4B39,  $1D4C,  $18AC
; dw  $7FFF,  $0C63,  $40A5,  $5D67, $7EAE, $7F18, $7A6B, $7B5C


; TODO Remove when its confirmed ZS spawn works properly
; Spawn Point 03 - Room 0005
org $02DB74 : dw $0005
org $02DC51 : db $14
org $02DB6E
SpawnPointData:
.room_id
#_02DB6E: dw $0104 ; 0x00 - Link's house   - ROOM 0104
#_02DB70: dw $0012 ; 0x01 - Sanctuary      - ROOM 0012
#_02DB72: dw $0080 ; 0x02 - Prison         - ROOM 0080
#_02DB74: dw $0055 ; 0x03 - Uncle          - ROOM 0055
#_02DB76: dw $0051 ; 0x04 - Throne         - ROOM 0051
#_02DB78: dw $00D0 ; 0x05 - Old man cave   - ROOM 00D0
#_02DB7A: dw $00E4 ; 0x06 - Old man home   - ROOM 00E4

; ---------------------------------------------------------

.camera_scroll_boundaries
#_02DB7C: db $21, $20, $21, $21, $09, $09, $09, $0A ; 0x00 - Link's house
#_02DB84: db $02, $02, $02, $03, $04, $04, $04, $05 ; 0x01 - Sanctuary
#_02DB8C: db $10, $10, $10, $11, $01, $00, $01, $01 ; 0x02 - Prison
#_02DB94: db $0A, $0A, $0A, $0B, $0B, $0A, $0B, $0B ; 0x03 - Uncle
#_02DB9C: db $0A, $0A, $0A, $0B, $02, $02, $02, $03 ; 0x04 - Throne
#_02DBA4: db $1E, $1E, $1E, $1F, $01, $00, $01, $01 ; 0x05 - Old man cave
#_02DBAC: db $1D, $1C, $1D, $1D, $08, $08, $08, $09 ; 0x06 - Old man home

; ---------------------------------------------------------

.horizontal_scroll
#_02DBB4: dw $0900 ; 0x00 - Link's house
#_02DBB6: dw $0480 ; 0x01 - Sanctuary
#_02DBB8: dw $00DB ; 0x02 - Prison
#_02DBBA: dw $0A8E ; 0x03 - Uncle
#_02DBBC: dw $0280 ; 0x04 - Throne
#_02DBBE: dw $0100 ; 0x05 - Old man cave
#_02DBC0: dw $0800 ; 0x06 - Old man home

; ---------------------------------------------------------

.vertical_scroll
#_02DBC2: dw $2110 ; 0x00 - Link's house
#_02DBC4: dw $0231 ; 0x01 - Sanctuary
#_02DBC6: dw $1000 ; 0x02 - Prison
#_02DBC8: dw $0A03 ; 0x03 - Uncle
#_02DBCA: dw $0A22 ; 0x04 - Throne
#_02DBCC: dw $1E8C ; 0x05 - Old man cave
#_02DBCE: dw $1D10 ; 0x06 - Old man home

; ---------------------------------------------------------

.y_coordinate
#_02DBD0: dw $2178 ; 0x00 - Link's house
#_02DBD2: dw $029C ; 0x01 - Sanctuary
#_02DBD4: dw $1041 ; 0x02 - Prison
#_02DBD6: dw $0A70 ; 0x03 - Uncle
#_02DBD8: dw $0A8F ; 0x04 - Throne
#_02DBDA: dw $1EF8 ; 0x05 - Old man cave
#_02DBDC: dw $1D98 ; 0x06 - Old man home

; ---------------------------------------------------------

.x_coordinate
#_02DBDE: dw $0978 ; 0x00 - Link's house
#_02DBE0: dw $04F8 ; 0x01 - Sanctuary
#_02DBE2: dw $0160 ; 0x02 - Prison
#_02DBE4: dw $0B06 ; 0x03 - Uncle
#_02DBE6: dw $02F8 ; 0x04 - Throne
#_02DBE8: dw $01A8 ; 0x05 - Old man cave
#_02DBEA: dw $0878 ; 0x06 - Old man home

; ---------------------------------------------------------

.camera_trigger_y
#_02DBEC: dw $017F ; 0x00 - Link's house
#_02DBEE: dw $00A7 ; 0x01 - Sanctuary
#_02DBF0: dw $0083 ; 0x02 - Prison
#_02DBF2: dw $007B ; 0x03 - Uncle
#_02DBF4: dw $009A ; 0x04 - Throne
#_02DBF6: DW $0103 ; 0x05 - Old man cave
#_02DBF8: dw $0187 ; 0x06 - Old man home

; ---------------------------------------------------------

.camera_trigger_x
#_02DBFA: dw $017F ; 0x00 - Link's house
#_02DBFC: dw $00FF ; 0x01 - Sanctuary
#_02DBFE: dw $0167 ; 0x02 - Prison
#_02DC00: dw $010D ; 0x03 - Uncle
#_02DC02: dw $00FF ; 0x04 - Throne
#_02DC04: dw $017F ; 0x05 - Old man cave
#_02DC06: dw $007F ; 0x06 - Old man home

; ---------------------------------------------------------

.main_GFX
#_02DC08: db $03 ; 0x00 - Link's house
#_02DC09: db $03 ; 0x01 - Sanctuary
#_02DC0A: db $04 ; 0x02 - Prison
#_02DC0B: db $01 ; 0x03 - Uncle
#_02DC0C: db $04 ; 0x04 - Throne
#_02DC0D: db $06 ; 0x05 - Old man cave
#_02DC0E: db $14 ; 0x06 - Old man home

; ---------------------------------------------------------

.floor
#_02DC0F: db $00 ; 0x00 - Link's house
#_02DC10: db $00 ; 0x01 - Sanctuary
#_02DC11: db $FD ; 0x02 - Prison
#_02DC12: db $FF ; 0x03 - Uncle
#_02DC13: db $01 ; 0x04 - Throne
#_02DC14: db $00 ; 0x05 - Old man cave
#_02DC15: db $00 ; 0x06 - Old man home

; ---------------------------------------------------------

.dungeon_id
#_02DC16: db $FF ; 0x00 - Link's house
#_02DC17: db $00 ; 0x01 - Sanctuary
#_02DC18: db $02 ; 0x02 - Prison
#_02DC19: db $FF ; 0x03 - Uncle
#_02DC1A: db $02 ; 0x04 - Throne
#_02DC1B: db $FF ; 0x05 - Old man cave
#_02DC1C: db $FF ; 0x06 - Old man home

; ---------------------------------------------------------

.layer
#_02DC1D: db $00 ; 0x00 - Link's house
#_02DC1E: db $00 ; 0x01 - Sanctuary
#_02DC1F: db $00 ; 0x02 - Prison
#_02DC20: db $01 ; 0x03 - Uncle
#_02DC21: db $00 ; 0x04 - Throne
#_02DC22: db $00 ; 0x05 - Old man cave
#_02DC23: db $01 ; 0x06 - Old man home

; ---------------------------------------------------------

.camera_scroll_controller
#_02DC24: db $00 ; 0x00 - Link's house
#_02DC25: db $22 ; 0x01 - Sanctuary
#_02DC26: db $20 ; 0x02 - Prison
#_02DC27: db $20 ; 0x03 - Uncle
#_02DC28: db $22 ; 0x04 - Throne
#_02DC29: db $02 ; 0x05 - Old man cave
#_02DC2A: db $02 ; 0x06 - Old man home

; ---------------------------------------------------------

.quadrant
#_02DC2B: db $02 ; 0x00 - Link's house
#_02DC2C: db $00 ; 0x01 - Sanctuary
#_02DC2D: db $10 ; 0x02 - Prison
#_02DC2E: db $10 ; 0x03 - Uncle
#_02DC2F: db $00 ; 0x04 - Throne
#_02DC30: db $10 ; 0x05 - Old man cave
#_02DC31: db $02 ; 0x06 - Old man home

; ---------------------------------------------------------

.overworld_door_tilemap
#_02DC32: dw $0816 ; 0x00 - Link's house
#_02DC34: dw $0000 ; 0x01 - Sanctuary
#_02DC36: dw $0000 ; 0x02 - Prison
#_02DC38: dw $0000 ; 0x03 - Uncle
#_02DC3A: dw $0000 ; 0x04 - Throne
#_02DC3C: dw $0000 ; 0x05 - Old man cave
#_02DC3E: dw $0000 ; 0x06 - Old man home

; ---------------------------------------------------------

.entrance_id
#_02DC40: dw $0000 ; 0x00 - Link's house
#_02DC42: dw $0002 ; 0x01 - Sanctuary
#_02DC44: dw $0002 ; 0x02 - Prison
#_02DC46: dw $0032 ; 0x03 - Uncle
#_02DC48: dw $0004 ; 0x04 - Throne
#_02DC4A: dw $004F ; 0x05 - Old man cave
#_02DC4C: dw $0030 ; 0x06 - Old man home

; ---------------------------------------------------------

.song
#_02DC4E: db $07 ; 0x00 - Link's house - SONG 07
#_02DC4F: db $14 ; 0x01 - Sanctuary    - SONG 14
#_02DC50: db $10 ; 0x02 - Prison       - SONG 10
#_02DC51: db $03 ; 0x03 - Uncle        - SONG 03
#_02DC52: db $10 ; 0x04 - Throne       - SONG 10
#_02DC53: db $12 ; 0x05 - Old man cave - SONG 12
#_02DC54: db $12 ; 0x06 - Old man home - SONG 12
