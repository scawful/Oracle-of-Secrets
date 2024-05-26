; Overworld.asm

; Module15_0C
; Change overlay that Impa activates after intro
org $029E2E
#_029E2E: LDA.l $7EF2A3
#_029E32: ORA.b #$20
#_029E34: STA.l $7EF2A3

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