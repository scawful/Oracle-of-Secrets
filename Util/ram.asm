; ==============================
; RAM in Use
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

base off
