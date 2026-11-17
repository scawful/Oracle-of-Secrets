; Current native cached-exit contract used by GoronCheckpoint/SpecialSoaring.
; NOT historical STV2 keys0186/0187. No exit/entrance allocation is emitted.
; Bound in QUEUE225: Kalyxo Docks $30/$31 (16, 23) <-> Sea Zora Quay $99 (23, 19).
!KALYXO_BOAT_ENDPOINTS_BOUND = 1
!Boat_DocksFacing = $0006
!Boat_IslandFacing = $0004
!Boat_DocksOpenTile = $0FC0
!Boat_IslandOpenTile = $085E
!Boat_DocksWaterTile = $02CD
!Boat_IslandWaterTile = $02C3

; Emit the native $32-byte payload already consumed at02E5D4. Bounds are
; the eight0600/0610 words; gfx0/gfx1 are AA0..AA3. No custom record format.
macro BoatNativeCache(area, sy, sx, y, x, origin, ty, tx, b0, b1, b2, b3, b4, b5, b6, b7, gfx0, gfx1)
if !KALYXO_BOAT_ENDPOINTS_BOUND == 1
  assert <area> < $C0 && <area> != $FFFF
  assert <sy> != $FFFF && <sx> != $FFFF && <y> != $FFFF && <x> != $FFFF
  assert <origin> != $FFFF && <ty> != $FFFF && <tx> != $FFFF
  assert <b0> != $FFFF && <b1> != $FFFF && <b2> != $FFFF && <b3> != $FFFF
  assert <b4> != $FFFF && <b5> != $FFFF && <b6> != $FFFF && <b7> != $FFFF
  assert <gfx0> != $FFFF && <gfx1> != $FFFF
endif
  dw <area>, $0016, <sy>, <sx>, <y>, <x>, <area>, <origin>
  dw <ty>, <tx>, <b0>, <b1>, <b2>, <b3>, <b4>, <b5>, <b6>, <b7>
  dw <gfx0>, <gfx1>, $0000, $0000, $0000, $0000, $0000
endmacro

macro BoatNativePlacements()
  assert !KALYXO_BOAT_ENDPOINTS_BOUND == 0 || !KALYXO_BOAT_ENDPOINTS_BOUND == 1
if !KALYXO_BOAT_ENDPOINTS_BOUND == 1
  assert !Boat_DocksFacing < 8 && (!Boat_DocksFacing&1) == 0
  assert !Boat_IslandFacing < 8 && (!Boat_IslandFacing&1) == 0
  assert !Boat_DocksOpenTile < $1000 && !Boat_IslandOpenTile < $1000
  assert !Boat_DocksWaterTile < $1000 && !Boat_IslandWaterTile < $1000
  assert !Boat_DocksOpenTile != !Boat_DocksWaterTile
  assert !Boat_IslandOpenTile != !Boat_IslandWaterTile
endif
Boat_Caches:
Boat_DocksCache:
  ; Docks $30/$31 subscreen tile (16, 23) = area tile (48, 23): Y=$0D70, X=$0300
  %BoatNativeCache($0030,$0D1E,$0288,$0D70,$0300,$08D0,$0D8F,$0307,$0C00,$0D1E,$0000,$0300,$0B20,$0E00,$FF00,$0400,$2000,$1C38)
Boat_IslandCache:
  ; Sea Zora Quay $99 tile (23, 19): Y=$0730, X=$0370
  %BoatNativeCache($0099,$06E0,$02F8,$0730,$0370,$071E,$074F,$0377,$0600,$071E,$0200,$0300,$0520,$0800,$0100,$0400,$2000,$2F2B)
Boat_CachesEnd:
  assert Boat_IslandCache-Boat_DocksCache == $32
  assert Boat_CachesEnd-Boat_Caches == $64
Boat_ArrivalFaces: dw !Boat_DocksFacing, !Boat_IslandFacing
Boat_OpenTiles: dw !Boat_DocksOpenTile, !Boat_IslandOpenTile
Boat_ClosedTiles: dw !Boat_DocksWaterTile, !Boat_IslandWaterTile
endmacro
