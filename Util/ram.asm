; =========================================================
; WRAM in Use
org $008000
base $7E0730 ; MAP16OVERFLOW free ram region

MenuScrollLevelV: skip 1
MenuScrollLevelH: skip 1
MenuScrollHDirection: skip 2
MenuItemValueSpoof: skip 2
ShortSpoof: skip 1 
MusicNoteValue: skip 2
OverworldLocationPointer: skip 2
HasGoldstar: skip 1
GoldstarOrHookshot: skip 1
Neck_Index: skip 1
Neck1_OffsetX: skip 1
Neck1_OffsetY: skip 1
Neck2_OffsetX: skip 1
Neck2_OffsetY: skip 1
Offspring1_Id: skip 1
Offspring2_Id: skip 1
Offspring3_Id: skip 1
Kydreeok_Id: skip 1
SomariaOrByrna: skip 1

base off

; =========================================================
; SRAM in Use

FishingRod = $7EF38A