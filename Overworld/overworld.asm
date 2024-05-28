; Overworld.asm

; Spawn Point 03 - Room 0005
org $02DB74
  dw $0005

org $02DC51
  db $14

org $0EF581
EXIT_0EF581:

; FlashGanonTowerPalette
org $0EF587
  LDA.b $8A
  CMP.b #$57 ; OW 43
  BEQ .on_dark_dm
  CMP.b #$57 ; OW 45
  BEQ .on_dark_dm
  CMP.b #$57 ; OW 47
  BNE EXIT_0EF581
  .on_dark_dm

incsrc "Overworld/world_map.asm"

incsrc "Overworld/pit_damage.asm"
print  "End of Overworld/pit_damage.asm   ", pc

incsrc "Overworld/master_sword.asm"
print  "End of master_sword.asm           ", pc

incsrc "Overworld/maku_tree.asm"
print  "End of Overworld/maku_tree.asm    ", pc

incsrc "Overworld/lost_woods.asm"
print  "End of Overworld/lost_woods.asm   ", pc

incsrc "Overworld/time_system.asm"
print  "End of Overworld/time_system.asm  ", pc