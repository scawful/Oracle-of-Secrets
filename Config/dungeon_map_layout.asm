; Shared authoring/runtime contract for the optional D8 six-column map.
; The descriptor is authored data: builds validate it, never install it.
; v1 bytes: "OOSDMAP",0, version1, slots14, rows5, reserved0,
;          columns[14] (slot2=6; all other slots=5), reserved[6]=0.
; An absent descriptor retains the legacy 5x5 layout for every map.
!DUNGEON_MAP_LAYOUT = $52F000
!DUNGEON_MAP_LAYOUT_SIZE = $0020
!DUNGEON_MAP_CODE = $52E000
!DUNGEON_MAP_CODE_END = $52F000
