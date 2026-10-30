; Maintained native whirlpool route data.
; Source path: Data/overworld/whirlpool_placements.asm
; Eight native route slots; transport rows 0..8 remain untouched.
; Imported data fixture SHA256: 3a9daf80b032e983d8ff95c8faab9803a778ae66b9366678ee1099fbd4f690c1
pushpc

macro whirlpool_route(slot, source, destination, y, x, vram, scroll_y, scroll_x, camera_y, camera_x, mod_y, mod_x)
  assert <slot> >= 0 && <slot> < 8, "Whirlpool slot is outside 0..7"
  assert not(defined("WHIRLPOOL_SLOT_<slot>")), "Duplicate whirlpool slot"
  !WHIRLPOOL_SLOT_<slot> = 1
  assert <source> >= 0 && <source> < $C0 && <source> != $1B, "Unsupported source parent"
  assert <destination> >= 0 && <destination> < $C0, "Unsupported arrival parent"
  assert <x> >= 0 && <x> <= $0FF8 && <y> >= 0 && <y> <= $0FF8, "Invalid arrival position"
  !WHIRLPOOL_SOURCE_<slot> = <source>
  !WHIRLPOOL_DESTINATION_<slot> = <destination>
  !WHIRLPOOL_VRAM_<slot> = <vram>
  !WHIRLPOOL_SCROLL_Y_<slot> = <scroll_y>
  !WHIRLPOOL_SCROLL_X_<slot> = <scroll_x>
  !WHIRLPOOL_Y_<slot> = <y>
  !WHIRLPOOL_X_<slot> = <x>
  !WHIRLPOOL_CAMERA_Y_<slot> = <camera_y>
  !WHIRLPOOL_CAMERA_X_<slot> = <camera_x>
  !WHIRLPOOL_MOD_Y_<slot> = <mod_y>
  !WHIRLPOOL_MOD_X_<slot> = <mod_x>
endmacro

; Source ABI assertions. This patch adds data only; no hooks or allocations.
assert read4($02B478) == $02ED0822, "Whirlpool call changed"
assert read2($02ED0D) == $10A2, "Eight-slot lookup changed"
assert read4($02ED13) == $02ECF8DF, "Whirlpool source table moved"

%whirlpool_route(0, $000A, $0018, $0858, $02D0, $1048, $080A, $024A, $086B, $02D0, $FFFA, $0006)
%whirlpool_route(1, $0035, $000F, $0260, $0E88, $0080, $0212, $0E02, $0273, $0E88, $000A, $FFFA)
%whirlpool_route(2, $0033, $0015, $04C8, $0A30, $0380, $047A, $0A00, $04DB, $0A7F, $FFF6, $FFFA)
%whirlpool_route(3, $0015, $0033, $0F78, $07B0, $18A4, $0F1E, $072A, $0F8B, $07B0, $FFF6, $0006)
%whirlpool_route(4, $0018, $000A, $02D8, $0460, $0400, $028A, $0400, $02EB, $047F, $FFF6, $000E)
%whirlpool_route(5, $000F, $0035, $0C58, $0B20, $0012, $0C0A, $0A9A, $0C6F, $0B20, $FFFA, $0000)
%whirlpool_route(6, $007F, $0055, $0598, $0AE8, $088C, $051E, $0A62, $058F, $0AE8, $FFF6, $FFFA)
%whirlpool_route(7, $0055, $0076, $0F90, $0C98, $1882, $0F1E, $0C12, $0F8F, $0C98, $FFFA, $0000)

assert defined("WHIRLPOOL_SLOT_0"), "Missing whirlpool slot 0"
assert defined("WHIRLPOOL_SLOT_1"), "Missing whirlpool slot 1"
assert defined("WHIRLPOOL_SLOT_2"), "Missing whirlpool slot 2"
assert defined("WHIRLPOOL_SLOT_3"), "Missing whirlpool slot 3"
assert defined("WHIRLPOOL_SLOT_4"), "Missing whirlpool slot 4"
assert defined("WHIRLPOOL_SLOT_5"), "Missing whirlpool slot 5"
assert defined("WHIRLPOOL_SLOT_6"), "Missing whirlpool slot 6"
assert defined("WHIRLPOOL_SLOT_7"), "Missing whirlpool slot 7"
; Literal origins let the manifest validate every emitted native table.
; Destination tables start at row9; bird/event rows0..8 are untouched.
org $02ECF8
  dw !WHIRLPOOL_SOURCE_0, !WHIRLPOOL_SOURCE_1, !WHIRLPOOL_SOURCE_2, !WHIRLPOOL_SOURCE_3, !WHIRLPOOL_SOURCE_4, !WHIRLPOOL_SOURCE_5, !WHIRLPOOL_SOURCE_6, !WHIRLPOOL_SOURCE_7
org $02EAF7
  dw !WHIRLPOOL_DESTINATION_0, !WHIRLPOOL_DESTINATION_1, !WHIRLPOOL_DESTINATION_2, !WHIRLPOOL_DESTINATION_3, !WHIRLPOOL_DESTINATION_4, !WHIRLPOOL_DESTINATION_5, !WHIRLPOOL_DESTINATION_6, !WHIRLPOOL_DESTINATION_7
org $02EB19
  dw !WHIRLPOOL_VRAM_0, !WHIRLPOOL_VRAM_1, !WHIRLPOOL_VRAM_2, !WHIRLPOOL_VRAM_3, !WHIRLPOOL_VRAM_4, !WHIRLPOOL_VRAM_5, !WHIRLPOOL_VRAM_6, !WHIRLPOOL_VRAM_7
org $02EB3B
  dw !WHIRLPOOL_SCROLL_Y_0, !WHIRLPOOL_SCROLL_Y_1, !WHIRLPOOL_SCROLL_Y_2, !WHIRLPOOL_SCROLL_Y_3, !WHIRLPOOL_SCROLL_Y_4, !WHIRLPOOL_SCROLL_Y_5, !WHIRLPOOL_SCROLL_Y_6, !WHIRLPOOL_SCROLL_Y_7
org $02EB5D
  dw !WHIRLPOOL_SCROLL_X_0, !WHIRLPOOL_SCROLL_X_1, !WHIRLPOOL_SCROLL_X_2, !WHIRLPOOL_SCROLL_X_3, !WHIRLPOOL_SCROLL_X_4, !WHIRLPOOL_SCROLL_X_5, !WHIRLPOOL_SCROLL_X_6, !WHIRLPOOL_SCROLL_X_7
org $02EB7F
  dw !WHIRLPOOL_Y_0, !WHIRLPOOL_Y_1, !WHIRLPOOL_Y_2, !WHIRLPOOL_Y_3, !WHIRLPOOL_Y_4, !WHIRLPOOL_Y_5, !WHIRLPOOL_Y_6, !WHIRLPOOL_Y_7
org $02EBA1
  dw !WHIRLPOOL_X_0, !WHIRLPOOL_X_1, !WHIRLPOOL_X_2, !WHIRLPOOL_X_3, !WHIRLPOOL_X_4, !WHIRLPOOL_X_5, !WHIRLPOOL_X_6, !WHIRLPOOL_X_7
org $02EBC3
  dw !WHIRLPOOL_CAMERA_Y_0, !WHIRLPOOL_CAMERA_Y_1, !WHIRLPOOL_CAMERA_Y_2, !WHIRLPOOL_CAMERA_Y_3, !WHIRLPOOL_CAMERA_Y_4, !WHIRLPOOL_CAMERA_Y_5, !WHIRLPOOL_CAMERA_Y_6, !WHIRLPOOL_CAMERA_Y_7
org $02EBE5
  dw !WHIRLPOOL_CAMERA_X_0, !WHIRLPOOL_CAMERA_X_1, !WHIRLPOOL_CAMERA_X_2, !WHIRLPOOL_CAMERA_X_3, !WHIRLPOOL_CAMERA_X_4, !WHIRLPOOL_CAMERA_X_5, !WHIRLPOOL_CAMERA_X_6, !WHIRLPOOL_CAMERA_X_7
org $02EC07
  dw !WHIRLPOOL_MOD_Y_0, !WHIRLPOOL_MOD_Y_1, !WHIRLPOOL_MOD_Y_2, !WHIRLPOOL_MOD_Y_3, !WHIRLPOOL_MOD_Y_4, !WHIRLPOOL_MOD_Y_5, !WHIRLPOOL_MOD_Y_6, !WHIRLPOOL_MOD_Y_7
org $02EC29
  dw !WHIRLPOOL_MOD_X_0, !WHIRLPOOL_MOD_X_1, !WHIRLPOOL_MOD_X_2, !WHIRLPOOL_MOD_X_3, !WHIRLPOOL_MOD_X_4, !WHIRLPOOL_MOD_X_5, !WHIRLPOOL_MOD_X_6, !WHIRLPOOL_MOD_X_7
pullpc
