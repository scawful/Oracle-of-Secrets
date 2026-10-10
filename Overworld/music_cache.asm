; Volatile overworld music/ambience cache. M=8 for byte reads/writes.
; Low nibble = music; high nibble = ambience. No SRAM representation.
; C880..C8FF is the moving-wall buffer. C900..C9BF is reserved here;
; C9C0 is exclusive. Ownership was traced against the qualified RC.
; Active count remains160: four64-entry LW phases and96 DW/special entries
; in ROM are unchanged. Tail32 bytes are reserved, not gameplay initialized.
!OverworldMusicCache = $7EC900
!OverworldMusicActiveCount = $00A0
!OverworldMusicCapacity = $00C0
!OverworldMusicLightCount = $0040
!OverworldMusicOtherCount = $0060
!OverworldMusicSpecialIndex = $0080

assert !OverworldMusicCache == $7EC900, "Music cache requires the audited WRAM reservation"
assert !OverworldMusicCache+!OverworldMusicCapacity <= $7EC9C0, "Music cache exceeds its owned reservation"
assert !OverworldMusicCapacity == $00C0, "Music cache reservation must contain192 bytes"
assert !OverworldMusicActiveCount == $00A0, "192-area activation requires a separate ROM table contract"
assert !OverworldMusicLightCount == $0040, "Light World source phase contains64 entries"
assert !OverworldMusicOtherCount == $0060, "Dark/special source table contains96 entries"
assert !OverworldMusicLightCount+!OverworldMusicOtherCount == !OverworldMusicActiveCount
assert !OverworldMusicSpecialIndex < !OverworldMusicActiveCount
assert !OverworldMusicActiveCount <= !OverworldMusicCapacity
assert (!OverworldMusicCache&$FFFF)+!OverworldMusicCapacity <= $10000

pushpc
; Vanilla consumers retained by ZSCustomOverworld. These address operands
; must move with its custom readers and the storm producer/cleanup code.
assert read4($00F401) == $7F5B00BF, "Iris module restoration cache instruction moved"
org $00F401 : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache00F401
assert read4($02AE73) == $7F5B00BF, "Mosaic song check cache instruction moved"
org $02AE73 : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02AE73
assert read4($02B117) == $7F5B00BF, "Mosaic ambience recovery cache instruction moved"
org $02B117 : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02B117
assert read4($02B126) == $7F5B00BF, "Mosaic music recovery cache instruction moved"
org $02B126 : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02B126
assert read4($02B2A1) == $7F5B00BF, "Mirror-warp music cache instruction moved"
org $02B2A1 : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02B2A1
assert read4($02B2AA) == $7F5B00BF, "Mirror-warp ambience cache instruction moved"
org $02B2AA : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02B2AA
assert read4($02B4FE) == $7F5B00BF, "Whirlpool finalization cache instruction moved"
org $02B4FE : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02B4FE
assert read4($02C27D) == $7F5B00BF, "Edge-entry ambience cache instruction moved"
org $02C27D : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02C27D
assert read4($02C28F) == $7F5B00BF, "Edge-entry music cache instruction moved"
org $02C28F : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02C28F
assert read4($0ABC80) == $7F5B00BF, "World-map exit cache instruction moved"
org $0ABC80 : LDA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache0ABC80
assert read4($02C49A) == $7F5B009F, "Light World initializer cache instruction moved"
org $02C49A : STA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02C49A
assert read4($02C4AB) == $7F5B009F, "Dark/special initializer cache instruction moved"
org $02C4AB : STA.l !OverworldMusicCache,X ; @hook module=Overworld kind=patch name=MusicCache02C4AB

; Keep copy limits named and unchanged. No reads beyond the existing tables.
assert read3($02C4A0) == $0040E0 && read3($02C4B1) == $0060C0
org $02C4A0 : CPX.w #!OverworldMusicLightCount
org $02C4B1 : CPY.w #!OverworldMusicOtherCount

; The enabled storm tail replaces this instruction later. Diagnostic storm
; opt-out still needs the separate index80 write at the relocated address.
if !ENABLE_PART0_STORM == 0
  assert read4($02C4B8) == $7F5B808F, "Special-area cache initializer moved"
  org $02C4B8 : STA.l !OverworldMusicCache+!OverworldMusicSpecialIndex
endif
pullpc
