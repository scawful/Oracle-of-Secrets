; D3 scene staging is not authored yet. Keep the existing intro patrol's
; delegated call ABI, but do not arrest arbitrary subtype>=5 guards or warp
; to entrance32 (room55, not the planned cell65). The receipt now arms the
; saved transaction in Dungeons/d3_prison_state.asm. A future hall scene
; must call D3Prison_Capture only with a validated cell destination.

if !ENABLE_D3_PRISON_SEQUENCE == 1
Guard_CheckDamageToLink_CaptureWrapper:
{
  JML $06F121 ; Sprite_CheckDamageToLink_long: preserve native Carry/$0FDC
}
endif
