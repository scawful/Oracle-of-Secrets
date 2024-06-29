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

org $0EF531
Palettes_GanonTowerFlash:
  dw  $7FFF,  $0884,  $1CC8,  $1DCE,  $3694,  $4718,  $1D4A,  $18AC
  dw  $7FFF,  $1908,  $2D2F,  $3614,  $4EDA,  $471F,  $1D4A,  $390F
  dw  $7FFF,  $34CD,  $5971,  $5635,  $7F1B,  $7FFF,  $1D4A,  $3D54
  dw  $7FFF,  $1908,  $2D2F,  $3614,  $4EDA,  $471F,  $1D4A,  $390F
  dw  $7FFF,  $0884,  $052A,  $21EF,  $3AB5,  $4B39,  $1D4C,  $18AC

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
pushpc

pullpc
incsrc "Overworld/entrances.asm"
print  "End of Overworld/entrances.asm    ", pc


pullpc
LoadDarkWorldIntro:
{
  LDA.l $7EF3C5 : CMP.b #$02 : BNE .continue
    ; Check for maku tree progress flag
    LDA.l $7EF3D6 : CMP.b #$02 : BCS .has_pearl 
      STZ.w $1B
      LDA.b #$40 : STA.l $7EF3CA
      RTL
    .continue
  .has_pearl
  LDA.l $7EF3CA
  RTL
}
pushpc

; Module05_LoadFile
org $028192
  JSL LoadDarkWorldIntro

; Module05_LoadFile
; Check for goldstar instead of mirror for mountain spawn option
org $0281E2
  LDA.l $7EF342 : CMP.b #$02

; Check for hall of secrets spawn pt flag
org $0281CD
  LDA.l $7EF3D6 : CMP.b #$04

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

pushpc

incsrc "Overworld/special_areas.asm"

org $0794D9
  ; LDA $8A : CMP #$57 : BEQ .overworld_pit_transition
  JSL LoadOverworldPitAreas : BCC .overworld_pit_transition
  JSL $01FFD9 ; TakeDamageFromPit
  RTS
.overworld_pit_transition

