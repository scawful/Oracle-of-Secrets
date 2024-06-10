; Overworld.asm

; Spawn Point 03 - Room 0005
org $02DB74
  dw $0005

org $02DC51
  db $14

; Remove rain sound effects from beginning
org $02838C
LDA.l $7EF3C5
CMP.b #$00

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

incsrc "Overworld/master_sword.asm"
print  "End of master_sword.asm           ", pc

incsrc "Overworld/maku_tree.asm"
print  "End of Overworld/maku_tree.asm    ", pc

incsrc "Overworld/lost_woods.asm"
print  "End of Overworld/lost_woods.asm   ", pc

org $348000 ; Free space
pushpc
incsrc "Overworld/time_system.asm"
print  "End of Overworld/time_system.asm  ", pc

incsrc "Overworld/overlays.asm"
print  "End of Overworld/overlays.asm     ", pc


pullpc
LoadDarkWorldIntro:
{
  LDA.l $7EF3C5 : CMP.b #$02 : BNE .continue
    ; Check for moon pearl
    LDA.l $7EF357 : CMP.b #$01 : BEQ .has_pearl
      STZ.w $1B
      LDA.b #$40 : STA.l $7EF3CA
      RTL
    .continue
  .has_pearl
  LDA.l $7EF3CA
  RTL
}
pushpc

org $028192
  JSL LoadDarkWorldIntro

pullpc

LoadOverworldPitAreas:
{
  LDA $8A : CMP.b #$0F : BEQ .allow_transition
            CMP.b #$57 : BEQ .allow_transition
  SEC ; fall in the pit
  RTL

  .allow_transition
  CLC ; allow transition
  RTL
}

org $0794D9
  ; LDA $8A : CMP #$57 : BEQ .overworld_pit_transition
  JSL LoadOverworldPitAreas : BCC .overworld_pit_transition
  JSL $01FFD9 ; TakeDamageFromPit
  RTS
.overworld_pit_transition

; incsrc "Overworld/special_areas.asm"

