; Current native cached-exit contract used by GoronCheckpoint/SpecialSoaring.
; NOT historical STV2 keys0186/0187. No exit/entrance allocation is emitted.
; World pixels and full native camera/cache values must come from the selected
; current landing. The corrected left boat is NOT the old physical31 anchor.
!KALYXO_BOAT_ENDPOINTS_BOUND = 0
!Boat_DocksFacing = $FFFF
!Boat_IslandFacing = $FFFF
!Boat_DocksOpenTile = $FFFF
!Boat_IslandOpenTile = $FFFF
!Boat_DocksWaterTile = $FFFF
!Boat_IslandWaterTile = $FFFF

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
  ; Unbound: area,scrollY/X,LinkY/X,origin,triggersY/X,bounds8,gfx2.
  %BoatNativeCache($FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF)
Boat_IslandCache:
  %BoatNativeCache($FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF,$FFFF)
Boat_CachesEnd:
  assert Boat_IslandCache-Boat_DocksCache == $32
  assert Boat_CachesEnd-Boat_Caches == $64
Boat_ArrivalFaces: dw !Boat_DocksFacing, !Boat_IslandFacing
Boat_OpenTiles: dw !Boat_DocksOpenTile, !Boat_IslandOpenTile
Boat_ClosedTiles: dw !Boat_DocksWaterTile, !Boat_IslandWaterTile
endmacro
