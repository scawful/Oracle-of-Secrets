  ; This is which room each track should start in if it hasn't already
  ; been given a track.
  ;
  ; Track assignments (from goron_mines_minecart_design.md):
  ;  0: 0x98 Entrance (F1)       — ACTIVE   8: 0xB9 B1 SE          — planned
  ;  1: 0x88 Big Chest (F1)      — ACTIVE   9: 0x78 Miniboss (F1)  — BLOCKED (no collision)
  ;  2: 0x87 West Hall (F1)      — ACTIVE  10: 0x89 East Hall (F1) — planned
  ;  3: 0x88 Big Chest #2 (F1)   — ACTIVE  11: 0xDA B2 East        — planned HIGH
  ;  4: 0x77 NW Hall (F1)        — planned HIGH  12: 0xD9 B2 Mid   — planned HIGH
  ;  5: 0xA8 B1 NW               — planned HIGH  13: 0xD7 B2 West  — planned
  ;  6: 0xB8 B1 SW               — planned HIGH  14: 0x79 NE  — BLOCKED (no collision)
  ;  7: 0xB8 B1 SW #2            — planned HIGH  15: 0x97 SW  — planned
  ;                                               16: 0xD8 Pre-Boss — planned HIGH
  ;
  ; Coordinates derived from ROM collision data audit (2026-02-13):
  ;   - Tracks 0-3: Active, verified from sprite persistence
  ;   - Tracks 4-16: Aligned to actual stop tiles in ROM bank $A5
  ;   - Tracks 6,7: 0xB8 has track tiles but ZERO stop tiles (needs editor fix)
  ;   - Tracks 9,14: Rooms 0x78/0x79 have no custom collision data at all
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

  ; Starting X/Y coordinates for each track's initial spawn position.
  ;
  ; Coordinate formula: WRAM = room_base + (tile_pos * 8)
  ;   room_base_X = (roomID % 16) * $200
  ;   room_base_Y = (roomID / 16) * $200
  ;
  ; Active tracks (0-3): Corrected to match stop tiles in ROM.
  ; Planned tracks (4-16): Aligned to stop tiles found in ROM collision
  ;   data at bank $A5 (audited 2026-02-13). Place sprites at these exact
  ;   coordinates in yaze sprite editor.
  ;
  ;   Track  Room  Stop tile       Tile(X,Y)  Stop type
  ;   ─────  ────  ──────────────  ─────────  ─────────
  ;     0    0x98  (50,48)         (50, 48)   BA STOP_W   ✓ verified
  ;     1    0x88  (44,26)         (44, 26)   BA STOP_W   ✓ Y fixed (was $10C9)
  ;     2    0x87  (14,26)         (14, 26)   B9 STOP_E   ✓ X fixed (was $1300)
  ;     3    0x88  (44,26)         (44, 26)   BA STOP_W   NOTE: shares stop w/ T1
  ;     4    0x77  (16,21)         (16, 21)   B7 STOP_S
  ;     5    0xA8  (14,44)         (14, 44)   B7 STOP_S
  ;     6    0xB8  (14, 2)         (14,  2)   B7 STOP_S
  ;     7    0xB8  (14,32)         (14, 32)   B8 STOP_N
  ;     8    0xB9  (34,12)         (34, 12)   B7 STOP_S
  ;     9    0x78  BLOCKED         ( —,  —)   no collision data
  ;    10    0x89  (48,16)         (48, 16)   B7 STOP_S
  ;    11    0xDA  (52,10)         (52, 10)   B7 STOP_S
  ;    12    0xD9  (11,16)         (11, 16)   B9 STOP_E
  ;    13    0xD7  (53,12)         (53, 12)   BA STOP_W
  ;    14    0x79  BLOCKED         ( —,  —)   no collision data
  ;    15    0x97  ( 8,44)         ( 8, 44)   B7 STOP_S
  ;    16    0xD8  (14,14)         (14, 14)   B9 STOP_E
  ;
  .TrackStartingX
  dw $1190, $1160, $0E70, $1160  ; Tracks 0-3  (ACTIVE — T2 X fixed, T3 aligned to T1 stop)
  if !ENABLE_MINECART_PLANNED_TRACK_TABLE == 1
    dw $0E80, $1070, $1070, $1070  ; Tracks 4-7  (0x77 t16, 0xA8 t14, 0xB8 t14 x2)
    dw $1310, $0F80, $1380, $15A0  ; Tracks 8-11 (0xB9 t34, 0x78 TBD, 0x89 t48, 0xDA t52)
    dw $1258, $0FA8, $1200, $0E40  ; Tracks 12-15(0xD9 t11, 0xD7 t53, 0x79 TBD, 0x97 t8)
    dw $1070, $0000, $0000, $0000  ; Track 16 (0xD8 t14), 17-19 reserved
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
  dw $1380, $10D0, $10D0, $10D0  ; Tracks 0-3  (ACTIVE — T1 Y fixed, T2 Y fixed, T3 aligned)
  if !ENABLE_MINECART_PLANNED_TRACK_TABLE == 1
    dw $0EA8, $1560, $1610, $1700  ; Tracks 4-7  (0x77 t21, 0xA8 t44, 0xB8 t2, 0xB8 t32)
    dw $1660, $0F00, $1080, $1A50  ; Tracks 8-11 (0xB9 t12, 0x78 TBD, 0x89 t16, 0xDA t10)
    dw $1A80, $1A60, $0F80, $1360  ; Tracks 12-15(0xD9 t16, 0xD7 t12, 0x79 TBD, 0x97 t44)
    dw $1A70, $0000, $0000, $0000  ; Track 16 (0xD8 t14), 17-19 reserved
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
