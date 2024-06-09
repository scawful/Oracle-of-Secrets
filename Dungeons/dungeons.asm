incsrc "Dungeons/keyblock.asm"
print  "End of keyblock.asm               ", pc

; Disable Code
; ------------
org $028BE7
db $EA, $EA

; Load Sanctuary music during Room 02 to 12 transition
; ----------------------------------------------------
;org $028BDA
;db $14

; Room Number (Sanctuary)
;org $028BDE
;db $12

; Load Hyrule Castle music during Room 12 to 02 transition
; --------------------------------------------------------
;org $028BE3
;db $16

; Room Number (Sewers)
;org $028BE5
;db $02

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