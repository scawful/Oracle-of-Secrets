if !ENABLE_D3_PRISON_ARMORY == 1
  assert !ENABLE_D3_PRISON_CELL65 == 1, "Armory requires paired prison cell65 data"
  assert !ENABLE_WALL_PROFILE_SELECTOR == 1, "Armory requires room-specific graphics profiles"
endif
; Bounded prison code reservation. Bank34 is full with the selected Sky code;
; never spill into adjacent tables or the editor's bank3C data.
; This claims only52:8000–9FFF. Upper bank52 remains outside this reservation.
if !ENABLE_D3_PRISON_SEQUENCE == 1
if !ENABLE_D3_PRISON_CELL65 == 1
assert !DISABLE_OVERWORLD == 0 && !DISABLE_DUNGEON == 0 && !DISABLE_SPRITES == 0 && !DISABLE_MASKS == 0, "Cell65 requires its gameplay modules"
assert !ENABLE_MINISH_AUTO_PORTAL == 1, "Cell65 requires its Minish portal mechanic"
endif
pushpc
!prison_code_guard = $528000
while !prison_code_guard < $52A000
  assert read2(!prison_code_guard) == 0, "Prison code reservation is occupied in editable base"
  !prison_code_guard #= !prison_code_guard+2
endwhile
org $528000 ; @hook module=Dungeons kind=patch name=PrisonSequenceCode protected_size=8192
Prison_SequenceCodeBegin:
incsrc "Dungeons/d3_prison_dialogue.asm"
incsrc "Dungeons/d3_prison_inventory.asm"
incsrc "Dungeons/d3_prison_cell65.asm"
incsrc "Dungeons/d3_prison_blade.asm"
incsrc "Dungeons/prison_escape.asm"
incsrc "Dungeons/d3_prison_hall.asm"
incsrc "Dungeons/d3_prison_patrol.asm"
incsrc "Dungeons/d3_prison_pending_exit.asm"
incsrc "Dungeons/d3_prison_thief.asm"
incsrc "Dungeons/d3_prison_recovery.asm"
incsrc "Dungeons/d3_prison_wing.asm"
incsrc "Dungeons/d3_prison_boss_gate.asm"
Prison_SequenceCodeEnd:
assert pc() <= $52A000, "Prison code exceeds its bounded bank52 reservation"
pullpc
endif
