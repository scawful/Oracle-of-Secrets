  ; This is which room each track should start in if it hasn't already
  ; been given a track.
  ;
  ; Track assignments (from goron_mines_minecart_design.md):
  ;  0: 0x98 Entrance (F1)       — ACTIVE   8: 0xB9 B1 SE          — planned
  ;  1: 0x88 Big Chest (F1)      — ACTIVE   9: 0x78 Miniboss (F1)  — planned
  ;  2: 0x87 West Hall (F1)      — ACTIVE  10: 0x89 East Hall (F1) — planned
  ;  3: 0x88 Big Chest #2 (F1)   — ACTIVE  11: 0xDA B2 East        — planned HIGH
  ;  4: 0x77 NW Hall (F1)        — planned HIGH  12: 0xD9 B2 Mid   — planned HIGH
  ;  5: 0xA8 B1 NW               — planned HIGH  13: 0xD7 B2 West  — planned
  ;  6: 0xB8 B1 SW               — planned HIGH  14: 0x79 NE Hall  — planned
  ;  7: 0xB8 B1 SW #2            — planned        15: 0x97 SW Hall  — planned
  ;                                               16: 0xD8 Pre-Boss — planned HIGH
  ;
  ; Tracks 4-16: Room assignments set, coordinates are ESTIMATES based on
  ; z3ed object layout analysis. Must be finalized when sprites are placed
  ; via yaze sprite editor (coordinates must match sprite placement exactly).
  ;
  ; Guardrail: toggle `!ENABLE_MINECART_PLANNED_TRACK_TABLE` to quickly
  ; enable/disable planned (non-placed) tracks without backing out commits.
  ;
  .TrackStartingRooms
  dw $0098, $0088, $0087, $0088  ; Tracks 0-3  (ACTIVE)
  if !ENABLE_MINECART_PLANNED_TRACK_TABLE == 1
    dw $0077, $00A8, $00B8, $00B8  ; Tracks 4-7  (planned: NW Hall, B1 NW, B1 SW x2)
    dw $00B9, $0078, $0089, $00DA  ; Tracks 8-11 (planned: B1 SE, Miniboss, E Hall, B2 E)
    dw $00D9, $00D7, $0079, $0097  ; Tracks 12-15(planned: B2 Mid, B2 West, NE Hall, SW Hall)
    dw $00D8, $0000, $0000, $0000  ; Track 16 (Pre-Boss), 17-19 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 20-23 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 24-27 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 28-31 reserved
  else
    ; Disable all non-core tracks (4-31). When room==0, Sprite_Minecart_Prep
    ; will self-disable these carts via the room/coord sanity checks.
    dw $0000, $0000, $0000, $0000  ; Tracks 4-7  disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 8-11 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 12-15 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 16-19 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 20-23 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 24-27 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 28-31 disabled
  endif

  ; This is where within the room each track should start in if it hasn't
  ; already been given a position. This is necessary to allow for more
  ; than one stopping point to be in one room.
  ;
  ; Coordinate formula: pixel = room_base + (grid_pos * 8)
  ;   room_base_X = (roomID % 16) * $200
  ;   room_base_Y = (roomID / 16) * $200
  ;
  ; Tracks 4-16: ESTIMATED positions from z3ed object analysis.
  ; These must match final sprite placement coordinates exactly.
  ;
  .TrackStartingX
  dw $1190, $1160, $1300, $1100  ; Tracks 0-3  (ACTIVE — verified)
  if !ENABLE_MINECART_PLANNED_TRACK_TABLE == 1
    dw $0F00, $1070, $1070, $1070  ; Tracks 4-7  (est: 0x77 grid~16, 0xA8 grid~14, 0xB8 grid~14)
    dw $1070, $0F80, $1200, $1570  ; Tracks 8-11 (est: 0xB9 grid~14, 0x78 grid~16, 0x89, 0xDA grid~22)
    dw $1290, $1290, $1200, $0E70  ; Tracks 12-15(est: 0xD9 grid~18, 0xD7, 0x79, 0x97)
    dw $1090, $0000, $0000, $0000  ; Track 16 (est: 0xD8 grid~18), 17-19 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 20-23 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 24-27 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 28-31 reserved
  else
    dw $0000, $0000, $0000, $0000  ; Tracks 4-7  disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 8-11 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 12-15 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 16-19 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 20-23 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 24-27 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 28-31 disabled
  endif

  .TrackStartingY
  dw $1380, $10C9, $1100, $10D0  ; Tracks 0-3  (ACTIVE — verified)
  if !ENABLE_MINECART_PLANNED_TRACK_TABLE == 1
    dw $0EF0, $1590, $1700, $1700  ; Tracks 4-7  (est: 0x77 grid~30, 0xA8 grid~50, 0xB8 grid~51)
    dw $1790, $0F00, $1300, $1A80  ; Tracks 8-11 (est: 0xB9 grid~51, 0x78 grid~32, 0x89, 0xDA grid~16)
    dw $1A80, $1A80, $0F80, $1300  ; Tracks 12-15(est: 0xD9, 0xD7, 0x79, 0x97)
    dw $1A70, $0000, $0000, $0000  ; Track 16 (est: 0xD8 grid~14), 17-19 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 20-23 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 24-27 reserved
    dw $0000, $0000, $0000, $0000  ; Tracks 28-31 reserved
  else
    dw $0000, $0000, $0000, $0000  ; Tracks 4-7  disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 8-11 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 12-15 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 16-19 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 20-23 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 24-27 disabled
    dw $0000, $0000, $0000, $0000  ; Tracks 28-31 disabled
  endif
