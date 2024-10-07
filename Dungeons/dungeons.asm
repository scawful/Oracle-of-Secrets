incsrc "Dungeons/keyblock.asm"
print  "End of keyblock.asm               ", pc

; Pendant from chest position
org $098823
  LDY.b #$68

; Disable hardcoded sanctuary song
org $028BE7
  NOP #2

; Fixed color fade-in effect
; TODO: Investigate if this is the best way to fix this.
; Module06_UnderworldLoad
org $028364
{
  LDA.b #$00 ; Fixed color RGB: #808000
  STA.b $9C

  LDA.b #$00 : STA.b $9D

  LDA.b #$00 : STA.b $9E
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
print "End of floor_puzzle.asm           ", pc

incsrc "Dungeons/spike_subtype.asm"

incsrc "Dungeons/attract_scenes.asm"
print  "End of attract_scenes.asm         ", pc

incsrc "Collision/CollisionTablesExpanded.asm"
incsrc "Collision/GlobalCollisionTables.asm"

pullpc ; Bank 0x33

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

print "End of dungeons.asm               ", pc

pushpc

; RoomTag_GetHeartForPrize
; Swap LW/DW check on spawn falling prize
org $01C71B
  LDA.l $7EF37A ; Crystals in LW

org $01C727
  LDA.l $7EF374 ; Pendants in DW

; RoomTag_WaterGate
org $01CBAC
LDA.w #NewWaterOverlayData>>16
STA.b $B9
LDA.w #NewWaterOverlayData>>0
