; Scene-only graphics in the unused upper part of the custom-ASM bank.
; The base and control contain zero padding here; debug helpers use $3CB000.
pushpc
!AttractRoyal_GfxGuard = 0
while !AttractRoyal_GfxGuard < $2000
  assert read4($3CC000+!AttractRoyal_GfxGuard) == $00000000, "Attract cast allocation is occupied"
  !AttractRoyal_GfxGuard #= !AttractRoyal_GfxGuard+4
endwhile
org $3CC000 ; @hook module=Dungeons name=AttractRoyal_Graphics kind=data protected_size=8192
AttractRoyal_Gfx:
  incbin "Data/attract_royal.4bpp"
AttractRoyal_GfxEnd:
assert pc() == $3CE000
pullpc
