; Provisional private endpoints. These are ordinary STV2 exit records;
; move both the landing and the boarding trigger by updating this record.
; Area, XY, size and facing are lowered by the existing exit macro.
; No endpoint coordinate occurs in the boat controller.
;
; 0186: Sea Zora receiving shore, map98 tile(12,27), face east (temporary existing dry ground).
; 0187: Kalyxo Docks, parent30/physical31 tile(16,23), face east.
assert (!STV2_EXITS>>16) == $D1, "Private ferry placement bank changed"
assert !STV2_EXITS+(($0186-$0180)*32) == $D184E0, "Island exit slot moved"
org $D184E0
%stv2_exit(0186, $98, $07B0, $00C0, 0, $06)
org $02E807 : db !STV2_FACING_0186
assert !STV2_EXITS+(($0187-$0180)*32) == $D18500, "Docks exit slot moved"
org $D18500
%stv2_exit(0187, $30, $0D70, $0300, 2, $06)
org $02E808 : db !STV2_FACING_0187

; Existing terrain at each endpoint; these differ by area graphics profile.
!Boat_DocksWaterTile = $02CD
!Boat_IslandWaterTile = $02C3
