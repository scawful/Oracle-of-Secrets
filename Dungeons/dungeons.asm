incsrc "Dungeons/keyblock.asm"
print  "End of keyblock.asm               ", pc

incsrc "Dungeons/sanctuary_transition.asm"

incsrc "Dungeons/entrances.asm"
print  "End of entrances.asm              ", pc

incsrc "Dungeons/enemy_damage.asm"
print  "End of enemy_damage.asm           ", pc

incsrc "Collision/CollisionTablesExpanded.asm"
incsrc "Collision/GlobalCollisionTables.asm"

pullpc ; Bank 0x33

; incsrc "Dungeons/house_walls.asm"

; Pendant from chest position
org $098823
  LDY.b #$68

; Use of Bank 0x2C begins
incsrc "Dungeons/Objects/object_handler.asm"
print  "End of object_handler.asm         ", pc

incsrc "Dungeons/together_warp_tag.asm"
incsrc "Dungeons/spike_subtype.asm"

incsrc "Dungeons/house_tag.asm"
print  "End of house_tag.asm              ", pc

incsrc "Dungeons/floor_puzzle.asm"
print  "End of floor_puzzle.asm           ", pc