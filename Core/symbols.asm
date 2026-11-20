; =========================================================
; WRAM in Use
; Vanilla-free block (usdasm UNUSED_7E1E70, 0x90 bytes). Until 2026-10-19
; this block sat at $7E0730, inside the minecart track tables
; ($0728-$07E7, Sprites/Objects/minecart.asm): ResetTrackVars zeroed it on
; every underworld entry and track 4-15 writes landed on these bytes.
org $008000
base $7E1E70
{
MenuScrollLevelV:         skip 1
MenuScrollLevelH:         skip 1
MenuScrollHDirection:     skip 2
MenuItemValueSpoof:       skip 2
ShortSpoof:               skip 1
MusicNoteValue:           skip 2
GoldstarOrHookshot:       skip 1
Neck_Index:               skip 1
Neck1_OffsetX:            skip 1
Neck1_OffsetY:            skip 1
Neck2_OffsetX:            skip 1
Neck2_OffsetY:            skip 1
Neck3_OffsetX:            skip 1
Neck3_OffsetY:            skip 1
Offspring1_Id:            skip 1
Offspring2_Id:            skip 1
Offspring3_Id:            skip 1
Kydreeok_Id:              skip 1
FishingOrPortalRod:       skip 1
SongTintTimer:            skip 1  ; Frames remaining for song color tint
SongTintColor:            skip 1  ; SongTint_Table entry index of the running tint
; Persistent across graphics loads; reset/restore owner joins gated resources.
SpecialOverworldMainCache: skip 4 ; Underlying native sheets for slots 0/1/2/7
; Native BG column8 history only; palette lifecycle consumer remains unbound.
; Six words follow BG rows2..7: relative palette offsets50/70/90/B0/D0/F0.
SpecialOverworldPaletteHoleReference: skip 12
SpecialOverworldPaletteHoleEffective: skip 12
SpecialOverworldPaletteHoleState: skip 1 ; Reset to0 before any capture/read.
SpecialOverworldPaletteHoleArea: skip 1  ; Reset toFF; validate full8A first.
GanondorfFight:           skip 1  ; $7E1EA6 finale: 0 none, 1 Ganondorf spawned, 2 defeated, 3 beast alive (door shut)
BossReinject:             skip 1  ; $7E1EA7 fairy revive in room $00: bosses re-inject their graphics next frame, then clear it
FinaleBeat:               skip 1  ; $7E1EA8 0 Kydreeok not dead yet, N>1 placeholder beat counting down, 1 Ganondorf may spawn
WallSel_Buffer:           skip 32 ; $7E1EA9-$7E1EC8 Dungeons/wall_profile_selector.asm span window (read via $01:1EA9 mirror)
SongTintContext:          skip 2  ; $7E1EC9 $1B and area ($8A) or room ($A0) the tint started in
assert pc() <= $7E1F00, "Core/symbols.asm WRAM block overflows free RAM $7E1E70-$7E1EFF"
}
base off

; Kalyxo ferry transient tail. Keep the legacy 91-byte block invariant.
!Boat_Magic = $B04F
base $7E1ECB
{
Boat_Marker:             skip 2 ; 7E1ECB; owned only by ferry module0C
Boat_State:              skip 1
Boat_Endpoint:           skip 1 ; endpoint word-table offset0 or2
Boat_Timer:              skip 2
Boat_SourceModule:       skip 1
Boat_PlankChanged:       skip 1
Boat_SaveY:              skip 2
Boat_SaveX:              skip 2
Boat_PlankIndex:         skip 2
Boat_PlankTile:          skip 2
Boat_LoadTries:          skip 2
Boat_Face:               skip 1
Boat_TransientEnd:       skip 0
assert Boat_Marker == $7E1ECB && Boat_TransientEnd == $7E1EDE
assert pc() <= $7E1F00, "Ferry transient state exceeds its bounded WRAM tail"
}
base off

; Glade ambush Abyss landing (!ENABLE_GLADE_AMBUSH, Sprites/Bosses/kydrog.asm).
; Vanilla-unused $7E02B8-$7E02B9 (usdasm UNUSED_7E02B8/B9, zero at boot); the
; item binding bytes end at $7E02B7. The $7E1E70 block has no room: the ferry
; block starts at $7E1ECB. Not persistent; no bulk owner clears it.
AbyssLanding = $7E02B8 ; state (0 off, 1 armed, 2 mosaic, 3 pan); +1 = camera rows left
assert AbyssLanding+2 <= $7E02C0

; Menu cursor flow (Menu/menu_cursor_flow.asm; Items in
; Menu/menu_item_bindings.asm and Menu/menu_select_item.asm).
; Vanilla-unused $7E02BA-$7E02BE (usdasm UNUSED_7E02BA-BE, zero at boot).
; Not persistent: the cursors last across menu opens until power-off.
MenuFlow_EquipCursor = $7E02BA ; Equipment slot + 1 (0 = none)
MenuFlow_MapCursor   = $7E02BB ; Map cell + 1 (0 = none)
MenuFlow_CrossRow    = $7E02BC ; D-pad page cross: source row ordinal + 1 (0 = none)
MenuFlow_CrossDir    = $7E02BD ; 0 = turned right (land left), $1F = turned left
MenuFlow_ItemsCursor = $7E02BE ; Items cursor item ID (0 = none / follow Y)
MenuFlow_LastPage    = $7E02BF ; Last visited pause menu page (0=Items, 1=Quest, 2=Equip, 3=Map)
assert AbyssLanding+2 == MenuFlow_EquipCursor
assert MenuFlow_LastPage+1 <= $7E02C0

if !ENABLE_HORSE_FORM == 1
base $7E1EDE
{
Horse_Marker:            skip 2
Horse_State:             skip 1
Horse_JumpTimer:         skip 1
Horse_JumpCooldown:      skip 1
Horse_JumpDir:           skip 1
Horse_JumpZ:             skip 1
Horse_AnimTimer:         skip 1
Horse_Frame:             skip 1
Horse_UploadedFrame:     skip 1
Horse_NpcActive:         skip 1
Horse_NpcFrame:          skip 1
Horse_NpcUploadedFrame:  skip 1
Horse_PalLoaded:         skip 1
Horse_DismountCooldown:  skip 1
Horse_HasAnchor:         skip 1
Horse_JumpStep:          skip 1
Horse_PushTimer:         skip 1
Horse_JumpStartX:        skip 2
Horse_JumpStartY:        skip 2
Horse_JumpEndX:          skip 2
Horse_JumpEndY:          skip 2
Horse_AnchorX:           skip 2
Horse_AnchorY:           skip 2
Horse_NpcSlot:           skip 1
Horse_InteractDelay:     skip 1
if !ENABLE_HORSE_PARK_ANYWHERE == 1
Horse_AnchorArea:        skip 1   ; $8A of parked outdoor dismount (WRAM-only)
endif
Horse_TransientEnd:      skip 0
assert Horse_Marker == $7E1EDE
if !ENABLE_HORSE_PARK_ANYWHERE == 1
assert Horse_TransientEnd == $7E1EFF
else
assert Horse_TransientEnd == $7E1EFE
endif
assert pc() <= $7E1F00, "Horse transient state exceeds its bounded WRAM tail"
}
base off
endif

; Dual-item binding volatile state. The 2026-11-14 grant at $7E1EDE was
; later taken by the Horse Form transient block, so these four bytes moved to
; vanilla-unused $7E02B3-$7E02B6 (usdasm UNUSED_7E02B3..B6; ancilla arrays end
; at $02B1, $02B2 is !CurrentMask). Never cleared by a bulk owner here; reset
; explicitly on file load or action cancellation; not persistent.
ItemBindingCursor  = $7E02B3
ItemBindingLogical = $7E02B4
ItemBindingAction  = $7E02B5
ItemBindingButton  = $7E02B6
; Menu session only: the Y item while the menu cursor browses in $0202.
; Written on every menu open, read on close; never read in gameplay.
ItemBindingMenuY   = $7E02B7
assert ItemBindingCursor == $7E02B3 && ItemBindingButton+1 == ItemBindingMenuY
assert ItemBindingMenuY+1 == $7E02B8

; 2-item HUD layout corner cells. 14 bytes in the
; vanilla-free $7EC84A-$7EC87F gap after the RebuildHUD copy ($7EC700+$14A).
; +0..+8 = rupee icon (2) + 3 digits for BG3 $6342 (screen row 26, cols 2-6);
; +$0A..+$0D = key icon + digit for BG3 $635C (row 26, cols 28-29).
; Written by HUD_Update every HUD frame, read by HUD_NMIUpload and the menu
; close scroll. Not persistent; not cleared by any bulk owner.
HudCornerBuffer    = $7EC84A
HudCornerBufferEnd = HudCornerBuffer+14
assert HudCornerBufferEnd <= $7EC880

; Bottom-center 12-hour Sun/Moon HUD clock buffer + dirty-check cache.
; Contiguous with HudCornerBuffer so HUD_NMIUpload streams all three
; row-26 segments without reloading DMA0ADDRL.
; +0..+$0B = 6 tilemap words for BG3 $634D (screen row 26, cols 13-18):
;   2-digit hour (10..12): [Icon][1][0..2][:][M10][M1]
;   1-digit hour (1..9):   [$207F][Icon][1..9][:][M10][M1]
; +$0C = HudClockLastHours, +$0D = HudClockLastMinutes (dirty cache).
HudClockBuffer      = HudCornerBufferEnd ; $7EC858..$7EC863 (6 tiles = 12 bytes)
HudClockLastHours   = HudClockBuffer+12  ; $7EC864
HudClockLastMinutes = HudClockBuffer+13  ; $7EC865
HudClockBufferEnd   = HudClockBuffer+14  ; $7EC866
assert HudClockBuffer == $7EC858 && HudClockBufferEnd == $7EC866

; Epona carrot stamina meter buffers centered above the bottom clock
; (BG3 rows 24-25, cols 14-18 -> VRAM $630E/$632E). Contiguous after
; HudClockBufferEnd inside the unused $7EC84A-$7EC87F gap.
!Horse_CarrotHudWramDefined = 1
HudCarrotTopBuffer  = HudClockBufferEnd      ; $7EC866..$7EC86F (5 tiles = 10 bytes)
HudCarrotBotBuffer  = HudCarrotTopBuffer+10  ; $7EC870..$7EC879 (5 tiles = 10 bytes)
HudCarrotBufferEnd  = HudCarrotBotBuffer+10  ; $7EC87A
HudChrCache         = HudCarrotBufferEnd     ; $7EC87A: bits0-1 Sun(1)/Moon(2), bit7 Carrots CHR resident
HudChrContext       = HudChrCache+1          ; $7EC87B: cached $10 module for CHR invalidation
HudChrCacheEnd      = HudChrCache+2          ; $7EC87C
assert HudCarrotTopBuffer == $7EC866 && HudCarrotBotBuffer == $7EC870
assert HudChrCacheEnd <= $7EC880

; Burnable doorway webs (Sprites/Objects/dungeon_web.asm). 16-bit per-room
; mask across all 320 underworld rooms ($000-$13F) in vanilla-free UNUSED_7EC900
; after music_cache_reservation ($7EC900-$7EC9BF) and BombchuPackPending ($7EC9E0).
; Cleared on file load ($02816C) and Overworld load ($0283EA); not saved to SRAM.
DungeonWeb_BurnedMask    = $7ECA00
DungeonWeb_BurnedMaskEnd = DungeonWeb_BurnedMask+$0280
assert DungeonWeb_BurnedMaskEnd == $7ECC80

; Non-Ranch Magic Bean Flower/Bean dynamic Page 1 OAM/VRAM cache
; (Sprites/NPCs/bean_vendor.asm). Transient WRAM inside vanilla-free UNUSED_7EC900
; after DungeonWeb_BurnedMaskEnd ($7ECC80); cleared/guarded by $424E magic. Not saved to SRAM.
!MAGIC_BEAN_WRAM_DEFINED = 1
MagicBean_WramStart      = $7ECC80
MagicBean_Magic          = $7ECC80 ; word: $424E ("BN") initialized marker
MagicBean_ReqMask        = $7ECC82 ; byte: bits 0..2 requested non-Ranch blocks (FlowerTop/Bot/Bean)
MagicBean_ResidentMask   = $7ECC83 ; byte: bits 0..2 uploaded & valid in Page 1 VRAM
MagicBean_PendingUpload  = $7ECC84 ; byte: bits 0..2 allocated, waiting NMI backup+upload
MagicBean_PendingRestore = $7ECC85 ; byte: bits 0..2 displaced, waiting NMI backup restore
MagicBean_TrackCount     = $7ECC86 ; byte: tracked non-Ranch MagicBean OAM spans this frame (0..8)
MagicBean_BlockSlot      = $7ECC87 ; 3 bytes: Page 1 sheet slot index 0..3 ($7EC2FC+s) for k=0..2
MagicBean_BlockChr       = $7ECC8A ; 3 bytes: Page 1 OAM top-left char ($00..$EE) for k=0..2
MagicBean_BackupSheet    = $7ECC8D ; 3 bytes: $7EC2FC+slot sheet ID at allocation/backup ($FF=none)
MagicBean_HoldFrames     = $7ECC90 ; 3 bytes: idle hysteresis countdown before restoring block k
MagicBean_TrackMask      = $7ECC93 ; 8 bytes: required block bitmask per tracked OAM span (0..7)
MagicBean_TrackOff       = $7ECC9B ; 16 bytes: 8 x 16-bit OAM buffer offsets ($0000..$01FC)
MagicBean_TrackEnd       = $7ECCAB ; 16 bytes: 8 x 16-bit exclusive OAM buffer end offsets
MagicBean_Occ            = $7ECCBB ; 8 bytes: 64-block Page 1 OAM occupancy bitmask (FrameEndScan)
MagicBean_BackupBuf      = $7ECCC3 ; 3 x 132 = 396 bytes ($018C): 2B prefetch + 64B row0 + 2B + 64B row1
MagicBean_Scratch0       = $7ECE4F ; 4 bytes: local FrameEndScan / NmiUpload scratch (zero DP use)
MagicBean_Scratch1       = $7ECE50
MagicBean_Scratch2       = $7ECE51
MagicBean_Scratch3       = $7ECE52
MagicBean_WramEnd        = $7ECE53
assert MagicBean_BackupBuf+396 == MagicBean_Scratch0
assert MagicBean_WramEnd <= $7ECE60

; Map page: the map request made on the page, run once by Menu_Exit.
; Separate conditional owner after the horse tail. $7E1EFE is Horse_AnchorArea
; when park-anywhere is on (the menu cleared her park on every open), so this
; byte sits at $7E1EFF.
base $7E1EFF
{
MenuMapTravel_Pending:   skip 1 ; 0 none, 1 field map, 3 map open: reopen page
assert MenuMapTravel_Pending == $7E1EFF
assert pc() <= $7E1F00, "Map page pending byte exceeds its bounded WRAM tail"
}
base off

; Explicit bounded aliases for the reserved palette history; no consumer yet.
SpecialOverworldPaletteHoleCache = $7E1E8C
SpecialOverworldPaletteHoleCacheEnd = $7E1EA6
assert SpecialOverworldPaletteHoleCache == SpecialOverworldPaletteHoleReference
assert SpecialOverworldPaletteHoleCacheEnd == SpecialOverworldPaletteHoleArea+1
assert SpecialOverworldPaletteHoleCacheEnd-SpecialOverworldPaletteHoleCache == 26

; SongTint_Table entry indexes (Items/ocarina.asm).
!SongTint_Healing = $00
!SongTint_Secrets = $01

if !ENABLE_HORSE_PARK_ANYWHERE == 1
; Off-Ranch parked Epona (Masks/horse_park_anywhere.asm). Her NPC cells
; replace sprite VRAM $5000-$51FF (page1 chars $00-$1F); the native cells
; are copied here first and written back. UNUSED_7F5000 has $0800 free.
Horse_OffDma   = $7F5000 ; VRAM read lands here: duplicated first word + buffer
Horse_OffBuf   = $7F5002 ; $0400 bytes, copy of VRAM $5000-$51FF
Horse_OffState = $7F5402 ; $A1 saved, $A2 Epona cells in VRAM, else native
Horse_OffClear = $7F5403 ; frames with no other page1 $00-$1F OAM user
Horse_OffSheet = $7F5404 ; $7EC2FC when the copy was taken
Horse_OffOam   = $7F5405 ; word: $0800-$09E0 OAM base of sprite $2D this frame (0 = none)
endif

; Epona overhaul transient WRAM ($7F5670-$7F57FF inside UNUSED_7F5000,
; leaving $7F5408-$7F5409 to AbyssGbc_LoadedStyle/PalStyle, $7F540A-$7F540C
; to NightPoe_Vram*, $7F540D-$7F540F to LyraSea_Vram*, $7F5410-$7F545F to
; HorseGame_*, and $7F5460-$7F5663 to KORL_Dock*).
NightPoe_VramState      = $7F540A ; 0=idle, $80=pending NMI DMA, $01=live in VRAM $5EC0/$5EE0
NightPoe_LastArea       = $7F540B ; cached $8A (OW) or $A0 low byte (UW)
NightPoe_LastInd        = $7F540C ; cached $00 (OW) or $80|($A1&1) (UW)
LyraSea_VramState       = $7F540D ; 0=idle, $80=stage1 Cheep, $81=stage2 Blooper, $01=live
LyraSea_LastArea        = $7F540E ; cached $8A (OW) or $A0 low byte (UW)
LyraSea_LastInd         = $7F540F ; cached $00 (OW) or $80|($A1&1) (UW)
!Horse_OverhaulWramDefined = 1
Horse_AnchorDir         = $7F5670 ; saved $2F facing (0=N, 2=S, 4=W, 6=E; $FF=unset)
Horse_Carrots           = $7F5671 ; current stamina carrots (0..5)
Horse_SpurTimer         = $7F5672 ; active spur decay frames (0 = base canter)
Horse_RegenTimer        = $7F5673 ; frames until next carrot restores
Horse_HudState          = $7F5674 ; cached HUD state ($FF=uninit, 0=cleared, $80|N=mounted)
Horse_JumpPrevX         = $7F5675 ; word: pre-JumpTick Link X for camera delta $31
Horse_JumpPrevY         = $7F5677 ; word: pre-JumpTick Link Y for camera delta $30
Horse_JumpCamActive     = $7F5679 ; 1 when JumpTick updated coords needing camera scroll sync
Horse_PrioCacheX        = $7F567A ; word: cached Link X for FencePriority fast skip
Horse_PrioCacheY        = $7F567C ; word: cached Link Y for FencePriority fast skip
Horse_PrioCacheDir      = $7F567E ; cached $2F for FencePriority fast skip
Horse_PrioCacheArea     = $7F567F ; cached $8A for FencePriority fast skip
Horse_PrioCacheState    = $7F5680 ; cached Horse_State for FencePriority fast skip
Horse_PrioCacheResult   = $7F5681 ; cached priority result (0 or 1)
Horse_PrioCacheValid    = $7F5682 ; 1 when FencePriority cache matches current frame
Horse_TrampleCacheX     = $7F5683 ; word: cached (LinkX & $FFF8) for bush trample fast skip
Horse_TrampleCacheY     = $7F5685 ; word: cached (LinkY & $FFF8) for bush trample fast skip
Horse_TrampleCacheDir   = $7F5687 ; cached ($F0 & $0F) for bush trample fast skip
Horse_TrampleCacheArea  = $7F5688 ; cached $8A for bush trample fast skip
Horse_TrampleCacheValid = $7F5689 ; 1 when trample grid cell already cleared
Horse_NpcLastDir        = $7F568A ; last NPC direction uploaded/drawn
Horse_PalCachedColor    = $7F568B ; word: cached tinted HorsePalette+12
Horse_PalCachedHour     = $7F568D ; cached TimeState.Hours for palette check
Horse_PalCacheValid     = $7F568E ; 1 when palette cache populated
Horse_NorthCacheValid   = $7F568F ; 1 when north solid base cache valid
Horse_NorthCacheRes     = $7F5690 ; cached north solid base result (0/1)
Horse_NorthCacheArea    = $7F5691 ; cached $8A for north solid base
Horse_NorthCacheY8      = $7F5692 ; word: cached ($20-4)>>3
Horse_NorthCacheXL      = $7F5694 ; word: cached ($22+2)>>3
Horse_NorthCacheXR      = $7F5696 ; word: cached ($22+13)>>3
Horse_NorthCacheT16L    = $7F5698 ; word: cached Tile16 at left north probe
Horse_NorthCacheT16R    = $7F569A ; word: cached Tile16 at right north probe
Horse_CgiCacheValid        = $7F569C ; 1 when 16-slot ConstrainGroundInput fallback cache initialized
Horse_FrameFenceCheckedDir = $7F569D ; dir (0..3) cleared by CheckFenceJump this frame, or $FF
Horse_CgiCache             = $7F56A0 ; 16 slots * 8 bytes ($7F56A0..$7F571F): x8,y8,tile16,area,attr
Horse_SafeTile16Cache      = $7F5720 ; 32 slots * 4 bytes ($7F5720..$7F579F): tile16,area,clear
Horse_SafeTile16Valid      = $7F57A0 ; 1 when SafeTile16Cache initialized
Horse_PrioFenceCacheHdr    = $7F57A1 ; word: (valid<<8) | $8A for 2x3 PriorityFence cache
Horse_PrioFenceCacheRes    = $7F57A3 ; cached 2x3 PriorityFence result (0=none, 1=hit)
Horse_PrioFenceCacheXZ     = $7F57A4 ; word: ($22 & $FFF0) | x_zone
Horse_PrioFenceCacheYZ     = $7F57A6 ; word: ($20 & $FFF0) | y_zone
!Horse_PolishWramDefined   = 1
Horse_Momentum             = $7F57A8 ; gallop acceleration ramp 0..24 (0=standstill, 24=full stride)
Horse_PrevMoveDir          = $7F57A9 ; previous frame cardinal facing ($2F: 0,2,4,6; $FF=unset)
Horse_PrevDpad             = $7F57AA ; previous frame D-pad nibble ($F0 & $0F) for smooth diagonal banking
Horse_CgiCache_End         = $7F57AB ; last byte used by Epona in UNUSED_7F5000
assert Horse_CgiCache_End < $7F57FC, "Epona transient WRAM collided with PigMoblin_Vram* ($7F57FC)"
PigMoblin_VramState        = $7F57FC ; 0=idle, $80..$84=5-stage NMI DMA, $01=live
PigMoblin_LastArea         = $7F57FD ; cached $8A (OW) or $A0 low byte (UW)
PigMoblin_LastInd          = $7F57FE ; cached $00 (OW) or $80|($A1&1) (UW)

; PLACEHOLDER for the Song of Healing beat between Kydreeok and Ganondorf (decisions.org canon
; order: Kydreeok, Song frees Kydrog, Ganon). Until that scene exists, Ganondorf waits this many
; door-gate frames (3 s) after the Kydreeok body is dismissed. Replace with the real beat's flag.
!FinaleBeat_Frames = $B4

; =========================================================

function RGBto555(R,G,B) = ((R/8)<<10)|((G/8)<<5)|(B/8) ; zarby
function menu_offset(y,x) = (y*64)+(x*2)

; Current Dream ID (0x00-0x03)
CurrentDream   = $0426

; Dream return timer (!ENABLE_DREAM_RETURN, Sprites/NPCs/maple.asm).
; 0 = no dream in progress; else ticks (4 frames each) until Link is
; reloaded through the Dream Hut entrance. Vanilla-unused byte (Core/ram.asm).
DreamReturnTimer = $0427

; Pending consumable action requested from menu (0 = none, 1 = Honeycomb swarm, 2 = Deku Stick).
; Uses former vanilla-unused byte $0434; Core/ram.asm records this owner.
PendingSupplyAction      = $0434
!SUPPLY_ACTION_NONE      = $00
!SUPPLY_ACTION_HONEYCOMB = $01
!SUPPLY_ACTION_DEKUSTICK = $02

; Wisdom dream scene (!ENABLE_DREAM_WISDOM_SCENE, Sprites/NPCs/dream_wisdom.asm).
; Subtypes of the two staged $73 actors; room data never produces them.
; WRAM $7FF370-$7FF37F is taken (vanilla-free UNUSED_7FF180, Core/ram.asm;
; the text shade ends at $7FF367, the 2P PoC starts at $7FF400).
!DreamWisdom_SubCaptain = $D1
!DreamWisdom_SubFarore  = $D2
DreamWisdom_Marker   = $7FF370 ; word: $D1A5 while the scene owns Link (garbage-safe)
DreamWisdom_Watchdog = $7FF372 ; word
DreamWisdom_Save99   = $7FF374 ; $99,$9A,$9C,$9D,$9E during the flash
DreamWisdom_Flash    = $7FF379 ; nonzero while the flash is on

; Power dream scene (!ENABLE_DREAM_POWER_SCENE, Sprites/NPCs/dream_power.asm).
; Two more staged $73 actors; the scene uses the Wisdom marker and locks.
!DreamPower_SubKing   = $D3
!DreamPower_SubFarore = $D4
!DreamPower_WakeLive = $D2A6
; Wisdom fall (!ENABLE_DREAM_WISDOM_FALL): the Captain's men ($D5-$D7, one
; subtype each: sprite init clears SprMiscA) and Kydrog's silhouette ($D8).
!DreamPower_SubMan0       = $D5
!DreamPower_SubSilhouette = $D8
DreamPower_WakeLine  = $7FF37A ; word: !DreamPower_WakeLive = Maple says D2.06 in the hut

; BossKit (Sprites/Bosses/boss_kit.asm) uses WRAM $7FF380-$7FF384 in the same
; vanilla-free UNUSED_7FF180 block: the boss frame load meter and earthquake.
; BossDirector (Sprites/Bosses/boss_director.asm) uses $7FF388-$7FF39D after
; it: the boss attack token, rest, hit grace, cooldowns and 8 boss bytes.
; Attract storybook (Core/Cutscene/attract_storybook.asm) uses $7FF3A0-$7FF3AF.
;
; Debug tools mailbox (!ENABLE_DEBUG_TOOLS, Util/item_cheat.asm): WRAM
; $7FF3C0-$7FF3CF (reserved block $7FF3C0-$7FF3DF before 2P PoC $7FF400).
; Relocated from legacy $7E0730-$7E075F which overlapped minecart track tables.
DBG_REINIT_FLAGS      = $7FF3C0 ; bitfield: 01 dialog, 02 sprites, 04 overlays, 08 msgbank, 10 roomcache
DBG_REINIT_STATUS     = $7FF3C1 ; completed bits
DBG_REINIT_ERROR      = $7FF3C2 ; failed bits
DBG_REINIT_LAST       = $7FF3C3 ; last bit executed
DBG_WARP_REQUEST      = $7FF3C4 ; 0=idle, 1=overworld/special warp, 2=same-area xy, 3=dungeon room fall
DBG_WARP_AREA         = $7FF3C5 ; target overworld/special area ($00-$BF)
DBG_WARP_X_LO         = $7FF3C6 ; target Link X (16-bit LE)
DBG_WARP_X_HI         = $7FF3C7
DBG_WARP_Y_LO         = $7FF3C8 ; target Link Y (16-bit LE)
DBG_WARP_Y_HI         = $7FF3C9
DBG_WARP_STATUS       = $7FF3CA ; $5A=armed, 2=in progress, 3=complete
DBG_WARP_ERROR        = $7FF3CB ; 0=ok, 1=bad mode, 2=bad req/mode, 4=bad req, 5=unarmed, 6=bad status, 7=bad area
DBG_WARP_GFX_PENDING  = $7FF3CC ; 0=none, 1=mosaic, 2=cached-exit, 3=dungeon fall
DBG_WARP_ARM          = $7FF3CD ; write $A5 to arm
DBG_WARP_ROOM_LO      = $7FF3CE ; target dungeon room ID (16-bit LE, req=3)
DBG_WARP_ROOM_HI      = $7FF3CF
assert DBG_WARP_ROOM_HI < $7FF400

; Heavy Sword / Goronblade Hurricane Spin volatile state (Items/heavy_sword.asm).
; Uses 3 bytes of vanilla-free UNUSED_7FF180 ($7FF3D0-$7FF3D2, strictly < $7FF400).
; Not saved to SRAM; self-clears whenever Link is not spinning or dizzy.
HeavySword_HurricaneActive = $7FF3D0 ; 0 = normal spin, 1 = steerable Hurricane Spin active
HeavySword_HurricaneRevs   = $7FF3D1 ; extra Hurricane revolutions completed this spin (0..4)
HeavySword_DizzyTimer      = $7FF3D2 ; Wind Waker dizzy recovery countdown (0..45 frames)
assert HeavySword_DizzyTimer < $7FF400

; Current Song
CurrentSong    = $030F

; 01 - Song of Healing
; 02 - Song of Time
; 03 - Song of Storms
SongFlag       = $FE

; Overlay camera cache variable
CameraCache    = $0632

; =========================================================
; The record format for the low table is 4 bytes:
;   byte OBJ*4+0: xxxxxxxx
;   byte OBJ*4+1: yyyyyyyy
;   byte OBJ*4+2: cccccccc
;   byte OBJ*4+3: vhoopppN

; The record format for the high table is 2 bits:
;   bit 0/2/4/6 of byte OBJ/4: X
;   bit 1/3/5/7 of byte OBJ/4: s

; Xxxxxxxxx = X position of the sprite. signed but see below.
; yyyyyyyy  = Y position of the sprite.
; cccccccc  = First tile of the sprite.
; N         = Name table of the sprite. See below for VRAM address calculation
; ppp       = Palette of the sprite. The first palette index is 128+ppp*16.
; oo        = Sprite priority. See below for details.
; h/v       = Horizontal/Vertical flip flags.
; s         = Sprite size flag. See below for details.

OamPtr       = $90
OamPtrH      = $92
OamBackup   = $0FEC

; =========================================================
; Sprite RAM

SprY         = $0D00
SprX         = $0D10
SprYH        = $0D20
SprXH        = $0D30

SprYSpeed    = $0D40
SprXSpeed    = $0D50

SprYRound    = $0D60
SprXRound    = $0D70

SprCachedX   = $0FD8
SprCachedY   = $0FDA

SprAction    = $0D80 ; Indexes the action jump table
SprFrame     = $0D90 ; Indexes the SprGfx for drawing
SprGfx       = $0DC0 ; Determine the GFX used for the sprite

SprMiscA     = $0DA0 ; Direction, position, or other misc usage
SprMiscB     = $0DB0 ; Prober parent sprite ID, misc
SprMiscC     = $0DE0 ; Cardinal direction the sprite is facing
SprMiscD     = $0E90 ; Pikit stolen item, misc usage
SprMiscE     = $0EB0 ; Head direction 0123 -> udlr
SprMiscF     = $0EC0 ; Clones
SprMiscG     = $0ED0 ; Probe whistle sfx

SprCustom    = $1CC0 ;

; Used in sprite state 0x03 (falling in water)
; used as delay in most of the sprites
SprDelay     = $0E80
SprFlash     = $0B89 ; Enemy color flash buffer

SprTimerA    = $0DF0 ; Action,    decreased by 1 each frame
SprTimerB    = $0E00 ; Animation, decreased by 1 each frame
SprTimerC    = $0E10 ;            decreased by 1 each frame
SprTimerD    = $0EE0 ;            decreased by 1 each frame
SprTimerE    = $0F10 ;            decreased by 1 each frame
SprTimerF    = $0F80 ; Gravity,   decreased by 2 each frame

SprSlot      = $0FA0 ; Current sprite slot being executed

SprStunTimer = $0B58 ; counts down from 0xFF

SprPause     = $0F00 ; Inactive if nonzero
SprFloor     = $0F20 ; 0 (top layer), 1 (bottom layer)
SprType      = $0E20 ; Sprite ID
SprSubtype   = $0E30 ; Sprite subtype

; hmwo oooo
;   o - define the number of OAM slots used by the sprite
;   w - Causes enemies to go towards the walls
;   m - Master sword ceremony sprite flag
;   h - If set, harmless. Unset you take damage from contact.
SprNbrOAM    = $0E40
SprHealth    = $0E50

; 0x00 - Sprite is dead, totally inactive
; 0x01 - Sprite falling into a pit with generic animation.
; 0x02 - Sprite transforms into a puff of smoke, often producing an item
; 0x03 - Sprite falling into deep water (optionally making a fish jump up?)
; 0x04 - Death mode for bosses
; 0x05 - Sprite falling into a pit that has a special animation
; 0x06 - Death Mode for normal creatures.
; 0x08 - Sprite is being spawned at load time.
;      An initialization routine will be run for one frame,
;      and then move on to the active state (0x09) next frame.
; 0x09 - Sprite is in the normal, active mode.
; 0x0A - Sprite is being carried by the player.
; 0x0B - Sprite is frozen and / or stunned.
SprState     = $0DD0

; nios pppt
;   n - if set, don't draw extra death anim
;   i - impervious to attacks and collision (0: normal | 1: clink)
;   o - shadow size (0: normal | 1: small)
;   s - shadow (0: no shadow | 1: shadow)
;   p - palette used for OAM props
;   t - name table used for OAM props
SprGfxProps  = $0E60

; Direction of sprite collision with wall
SprCollision = $0E70

; Definitely closely tied to the process of a sprite taking damage.
; Seems to serve as a palette cycling index, or a state variable.
; When this value is positive
; 0x80 -  Signal that the recoil process has finished
;         and will terminate during this frame.
SprRecoil    = $0EA0 ; Recoil Timer

; abbbbbbb:
;   a - start death timer
;   b - death timer
SprDeath     = $0EF0

SprYRecoil   = $0F30
SprXRecoil   = $0F40

; DIWS UUUU
;   D - boss death
;   I - Impervious to all attacks
;   W - Water slash
;   S - Draw Shadow
;   U - Unused
SprProps     = $0F50

; ISPH HHHH
;   I - ignore collisions
;   S - Statis (not alive eg beamos)
;   P - Persist code still run outside of camera
;   H - Hitbox
SprHitbox    = $0F60
SprHeight    = $0F70 ; Distance from the shadow
SprHeightS   = $0F90 ; Distance from the shadow subpixel
SprFreeze    = $0FC1 ; Seems to freeze sprites

; Primarily deals with bump damage
; tzpd bbbb
;   t - TODO
;   z - High priority target for bees to give hints
;   p - Powder interaction (0: normal | 1: ignore)
;   d - Behavior when a boss spawns (0: die | 1: live)
;   b - bump damage class
;   Bump damage classes are read from a table at $06F42D
;   Each table entry has 3 values, for green, blue, and red mails
;   class   g    b    r
;   0x00    2    1    1
;   0x01    4    4    4
;   0x02    0    0    0
;   0x03    8    4    2
;   0x04    8    8    8
;   0x05   16    8    4
;   0x06   32   16    8
;   0x07   32   24   16
;   0x08   24   16    8
;   0x09   64   48   24
SprBump      = $0CD2

; Damage sprite is enduring
SprDmgTaken       = $0CE2

; Sprite Deflection Properties
;   abcdefgh
;   a - If set, sprite is active
;   b - Same as bit 'a' for Zora.
;   c - Never queried, pushable interaction flag
;   d - If hit from front, deflect Ice Rod, Somarian missile,
;       boomerang, hookshot, and sword beam, and arrows stick in
;       it harmlessly.  If bit 1 is also set, frontal arrows will
;       instead disappear harmlessly.
;   e - If set, sprite collides with less tiles than usual
;   f - If set, impervious to sword and hammer type attacks
;   g - If set, impervious to arrows, but may have other additional meanings.
;   h - Handles behavior with previous deaths flagged in $7FDF80 (0: default | 1: ignore)
SprDefl      = $0CAA

; iwbs pppp
;   i - disable tile interaction
;   w - something water
;   b - sprite is blocked by shield
;   s - taking damage sfx to use TODO name
;   p - prize pack
SprPrize     = $0BE0

; tttt a.bp
;   t - tile interaction hitbox
;   a - deflect arrows TODO VERIFY
;   b - boss death
;   p - Sprite ignores falling into a pit when frozen?
SprTileDie   = $0B6B

; For sprites that interact with speical objects (arrows in particular)
; the special object will identify its type to the sprite via this location.
SprSpecial   = $0BB0

; If nonzero, ancillae do not interact with the sprite
; Bulletproof
SprBulletproof = $0BA0

SprRoom      = $0C9A ;X W Contains the area or room id the sprite has been loaded in
SprDrop      = $0CBA ;X W 00: Drop nothing, 01: drop normal key, 03: Drop green rupee, OtherValues: Drop big key

; Overlord
OverlordId   = $0B00
OverlordX    = $0B08
OverlordXH   = $0B10
OverlordY    = $0B18
OverlordYH   = $0B20

OverlordTimerA = $0B28
OverlordTimerB = $0B30
OverlordTimerC = $0B38

; =========================================================
; Sprite Functions

SpriteData_OAMProp = $0DB359

; Clear all properties for sprites
SpritePrep_ResetProperties = $0DB871

; set the oam coordinate for the sprite draw
Sprite_PrepOamCoord =  $06E416

; Draw the sprite depending of the position of the player
; (if he has to be over or under link)
Sprite_OAM_AllocateDeferToPlayer = $06F864

OAM_AllocateFromRegionA = $0DBA80 ; Above
OAM_AllocateFromRegionB = $0DBA84 ; Below
OAM_AllocateFromRegionC = $0DBA88 ; Above
OAM_AllocateFromRegionD = $0DBA8C ; Above
OAM_AllocateFromRegionE = $0DBA90 ; Above
OAM_AllocateFromRegionF = $0DBA94 ; Above

Sprite_DrawMultiple_quantity_preset = $05DF70

; check if the sprite is getting damage from player or items
Sprite_CheckDamageFromPlayer = $06F2AA

; check if the sprite is touching the player to damage
Sprite_CheckDamageToPlayer = $06F121

; damage the player everywhere on screen?
Sprite_AttemptDamageToPlayerPlusRecoil = $06F41F

; makes all the sprites on screen shaking
ApplyRumbleToSprites = $0680FA

Sprite_MoveLong = $1D808C

Sprite_ProjectSpeedTowardsPlayer = $06EA1A

Sprite_Decelerate_X = $05E657
Sprite_Decelerate_Y = $05E666

; =========================================================
; returns carry clear if there was no overlap
; args:
pos1_x_low    = $00
pos1_y_low    = $01
pos1_size     = $02
pos1_height   = $03

pos2_x_low    = $04
pos2_y_low    = $05
pos2_size     = $06
pos2_height   = $07

pos1_x_high   = $08
pos1_y_high   = $09
pos2_x_high   = $0A
pos2_y_high   = $0B

ans_low     = $0F
ans_high    = $0C

CheckIfHitBoxesOverlap = $0683E6

; $0FD8 = sprite's X coordinate
; $0FDA = sprite's Y coordinate
Sprite_Get16BitCoords_Local = $0684C1
Sprite_Get_16_bit_Coords = $0684BD

; load / draw a 16x16 sprite
Sprite_PrepAndDrawSingleLarge = $06DBF0

; load / draw a 8x8 sprite
Sprite_PrepAndDrawSingleSmall = $06DBF8

; draw shadow (requires additional oam allocation)
Sprite_DrawShadow = $06DC54

Sprite_DrawWaterRipple = $059FFA
Sprite_DrawRippleIfInWater = $1EFF8D

; check if the sprite is colliding with a solid tile set $0E70, X
; ----udlr , u = up, d = down, l = left, r = right
Sprite_CheckTileCollision = $06E496
Sprite_CheckTileCollision_long = $06E496

; $00[0x02]  - Entity Y coordinate
; $02[0x03?] - Entity X coordinate
; $0FA5      - Tile ID result
Sprite_GetTileAttr = $06E87B

; check if the sprite is colliding with a solid sloped tile
Sprite_CheckSlopedTileCollision = $06E8FD

; set the velocity x,y towards the player (A = speed)
Sprite_ApplySpeedTowardsPlayer = $06EA12

; \return $0E is low byte of player_y_pos - sprite_y_pos
; \return $0F is low byte of player_x_pos - sprite_x_pos
Sprite_DirectionToFacePlayer = $06EAA0

; if Link is to the left of the sprite, Y = 1, otherwise Y = 0.
Sprite_IsToRightOfPlayer = $06EACD

; return Y=1 sprite is below player, otherwise Y = 0
Sprite_IsBelowPlayer = $06EAE4

; $06 = sprite's Y coordinate
; $07 = sprite's X coordinate
Sprite_IsBelowLocation = $06EB1D

; check damage done to player if they collide on same layer
Sprite_CheckDamageToPlayerSameLayer = $06F129

; check damage done to player if they collide even if they are not on same layer
Sprite_CheckDamageToPlayerIgnoreLayer = $06F131

; play a sound loaded in A
Sound_SetSfx1PanLong = $0DBB6E
Sound_SetSfx2PanLong = $0DBB7C
Sound_SetSfx3PanLong = $0DBB8A

; =========================================================
; spawn a new sprite on screen, A = sprite id
; when using this function you have to set the position yourself
; these values belong to the sprite who used that function not the new one
; $00 low x, $01 high x
; $02 low y, $03 high y
; $04 height, $05 low x (overlord)
; $06 high x (overlord), $07 low y (overlord)
; $08 high y (overlord)
Sprite_SpawnDynamically = $1DF65D
Sprite_SpawnDynamically_slot_limited = $1DF65F

Sprite_SetSpawnedCoords = $09AE64
Sprite_SetSpawnedCoordinates = $09AE64

; move the sprite if he stand on a conveyor belt
Sprite_ApplyConveyorAdjustment = $1D8010

; Setup sprite hitbox for comparison with scrap ram
Sprite_SetupHitBoxLong = $0683EA

; player can't pass through the sprite
Sprite_BehaveAsBarrier = $1EF4F3
Sprite_PlayerCantPassThrough = $1EF4F3

; player can't hookshot to that sprite
Sprite_CancelHookshot = $0FF540
Sprite_NullifyHookshotDrag = $0FF540

; show a message box without any condition
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
Sprite_ShowMessageUnconditional = $05E219

; show a message if we press A and face the sprite
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
Sprite_ShowSolicitedMessage = $05E1A7
Sprite_ShowSolicitedMessageIfPlayerFacing = $05E1A7

; show a message if we touch the sprite
; should be used with Sprite_PlayerCantPassThrough
; A = low byte of message ID to use.
; Y = high byte of message ID to use.
Sprite_ShowMessageOnContact = $05E1F0
Sprite_ShowMessageFromPlayerContact = $05E1F0

; Parameters: Stack, A
JumpTableLocal = $008781
UseImplicitRegIndexedLocalJumpTable = $008781

EnableForceBlank = $00893D

Snitch_SpawnGuard = $09C02F

Sprite_KillFriends = $09EF56

Sprite_KillSelf = $09F1F8

Dungeon_SpriteInducedTilemapUpdate = $01E7A9

; =========================================================
; $04 = X
; $05 = HighX
; $06 = Y
; $07 = HighY
;   A = Speed
; \return $00 - Y Velocity
; \return $01 - X Velocity

Sprite_ProjectSpeedTowardsEntityLong = $06EA22

; =========================================================
; Guard and Prober functions
; SprMiscB contains the ID of the parent sprite to alert

Guard_ChaseLinkOnOneAxis = $05C542
Guard_ParrySwordAttacks = $06EB5E
Probe_CheckTileSolidity = $0DC26E

ProbeAndSparkCheckDirXSpeed = $05C359
ProbeAndSparkCheckDirYSpeed = $05C361
ProbeAndSparkXSpeed = $05C369
ProbeAndSparkYSpeed = $05C371

ColinearDirections = $05C381
OrthogonalDirections = $05C389
ColinearNextDirections = $05C391
OrthogonalNextDirections = $05C399

Sprite_SpawnProbeAlways_long = $05C66E

Sprite_TrackBodyToHead = $05DCA2

; =========================================================
; Misc long functions

GetRandomInt = $0DBA71

Sprite_SpawnFireball = $0DDA06
Sprite_SpawnSmallSplash = $1EA820
Sprite_SpawnSparkleGarnish = $058008
Sprite_SpawnPoofGarnish = $05AB9C

Sprite_CheckIfLifted = $06AA0C

Sprite_TransmuteToBomb = $06AD50

Sprite_RepelDash = $079291

Sprite_LoadGfxProperties = $00FC41

ThrownSprite_TileAndSpriteInteraction_long = $06DFF2

Overworld_DrawMap16_Persist = $1BC97C

; =========================================================
; Local functions which may be useful for sprites
; Sprite_AttemptZapDamage - 06EC02

; =========================================================
; Misc RAM

FrameCounter = $1A ; value that is increasing every frame
Indoor       = $1B ; 0: outside, 1: indoor
UpdPalFlag   = $15 ; Update all palettes $7EC500-$7EC700 if non-zero

RoomIndex    = $A0 ; Return the current room ID
AreaIndex    = $8A ; Return the current overworld area ID

MsgChoice    = $1CE8 ; Choice made in a message box

; D3 Prison Sequence Message IDs (expanded bank)
!Msg_GuardCaptureTaunt   = $1CC
!Msg_PrisonWakeUp        = $1CD
!Msg_PrisonCellDesc      = $1CE
!Msg_CellmateHint1       = $1CF
!Msg_CellmateHint2       = $1D0
!Msg_PostEscapeFlavor    = $1D1

; set the mosaic setting ($2106) XXXXDCBA
;   [ABCD BG1/BG2/BG3/BG4][X size of the mosaic pixels 0-16]
Mosaic       = $95

DungeonMainCheck = $021B
SpriteRanCheck = $8E

; Underworld:
;    Flags sprite deaths in underworld based on slot.
;    Indexed by 2 * room ID.
; Overworld:
;    Holds ID+1 of sprite with each position being assigned a unique byte
;    0x00 indicates no sprite in this slot
UWDEATH         = $7FDF80

RebuildHUD_long = $0DFA58

ForcePrizeDrop_long = $06FA54

TileDetect_BigArea_long = $07CF0A

Follower_Initialize = $099EFC

HandleFollowersAfterMirroring = $07AAA2

; =========================================================
; Controllers

; BYSTUDLR
;   [B BButton][Y YButton]
;   [SSelect Button][TStart Button]
;   [UDLR dpad buttons Up, Down, Left, Right]
RawJoypad1L  = $F0
; AXLRIIII
;   [A AButton][X Xbutton][L LButton][R RButton][I = controller ID]
RawJoypad1H  = $F2

; BYSTUDLR
;  [B BButton][Y YButton]
;  [SSelect Button][TStart Button]
;  [UDLR dpad buttons Up, Down, Left, Right]
PressPad1L   = $F4

; AXLRIIII
;  [A AButton][X Xbutton]
;  [L LButton][R RButton][I = controller ID]
PressPad1H   = $F6

ButtonAFlag  = $3B ; bit7: Button A is down (A-------)

; Timer for B button
; ssss tttt
;   s - spin attack in action; set to 0x9
;   t - sword swing timer
;       0x00 - No swing
;      —0x08 - Sword swing
;       0x09 - Sword primed
;      —0x0C - Poking wall
;
; Also used as a 16-bit countdown for various cutscenes:
;   Ether tablet:  0x00C0
;   Bombos tablet: 0x00E0
;   Desert tablet: 0x0001
BFLAG           = $3C

; =========================================================
; Ancilla

AnciOAMPrior = $0280 ; Ancilla oam priority if non zero use highest priority for draw
AnciColTimer = $028A ; Ancilla collision timer to prevent doing collision code too often set to 06 after a collision
AnciZSpeed   = $0294 ; Ancilla Z Speed
AnciHeight   = $029E ; Ancilla Height how far it is from its shadow
AnciHeightH  = $02A8 ; Ancilla Height hight byte how far it is from its shadow

AnciMiscA    = $0BF0 ; This can be used to do anything in ancilla
AnciMiscB    = $0C54 ; This can be used to do anything in ancilla
AnciMiscC    = $0C5E ; This can be used to do anything in ancilla (often used to track item received)
AnciMiscD    = $0C72 ; This can be used to do anything in ancilla (often used to track direction)

; General use variable for ancillae. Only intended for front slots.
; LENGTH: 0x05
AnciMiscJ    = $03CA

; General use variable for ancillae.
; LENGTH: 0x0A
ANC0MISCB    = $0385

AnciTimerA   = $0C68 ; This is a timer, value is decreased by 1 every frame

AnciY        = $0BFA ; Position Y of the ancilla (Up to Down)
AnciX        = $0C04 ; Position X of the ancilla (Left to Right)
AnciYH       = $0C0E ; High (often determine the room) Position Y of the ancilla (Up to Down)
AnciXH       = $0C18 ; High (often determine the room) Position X of the ancilla (Left to Right)
AnciXSpeed   = $0C22 ; Y Speed of the ancilla can go negative to go up
AnciYSpeed   = $0C2C ; X Speed of the ancilla can go negative to go left
AnciLayer    = $0C7C ; return the floor where the ancilla is
AnciOamBuf   = $0C86 ; Oam buffer?
AnciOAMNbr   = $0C90 ; Number of OAM slots used

AnciYsub     = $0C36 ; sub pixel for Y position for ancilla
AnciXsub     = $0C40 ; sub pixel for X position for ancilla

; Ancilla IDs
; db $00 ; 0x00 - NOTHING
; db $08 ; 0x01 - SOMARIA BULLET
; db $0C ; 0x02 - FIRE ROD SHOT
; db $10 ; 0x03 - UNUSED
; db $10 ; 0x04 - BEAM HIT
; db $04 ; 0x05 - BOOMERANG
; db $10 ; 0x06 - WALL HIT
; db $18 ; 0x07 - BOMB
; db $08 ; 0x08 - DOOR DEBRIS
; db $08 ; 0x09 - ARROW
; db $08 ; 0x0A - ARROW IN THE WALL
; db $00 ; 0x0B - ICE ROD SHOT
; db $14 ; 0x0C - SWORD BEAM_BOUNCE
; db $00 ; 0x0D - SPIN ATTACK FULL CHARGE SPARK
; db $10 ; 0x0E - BLAST WALL EXPLOSION
; db $28 ; 0x0F - BLAST WALL EXPLOSION
; db $18 ; 0x10 - BLAST WALL EXPLOSION
; db $10 ; 0x11 - ICE ROD WALL HIT
; db $10 ; 0x12 - BLAST WALL EXPLOSION
; db $10 ; 0x13 - ICE ROD SPARKLE
; db $10 ; 0x14 - BAD POINTER
; db $0C ; 0x15 - SPLASH
; db $08 ; 0x16 - HIT STARS
; db $08 ; 0x17 - SHOVEL DIRT
; db $50 ; 0x18 - ETHER SPELL
; db $00 ; 0x19 - BOMBOS SPELL
; db $10 ; 0x1A - POWDER DUST
; db $08 ; 0x1B - SWORD WALL HIT
; db $40 ; 0x1C - QUAKE SPELL
; db $00 ; 0x1D - SCREEN SHAKE
; db $0C ; 0x1E - DASH DUST
; db $24 ; 0x1F - HOOKSHOT
; db $10 ; 0x20 - BLANKET
; db $0C ; 0x21 - SNORE
; db $08 ; 0x22 - ITEM GET
; db $10 ; 0x23 - LINK POOF
; db $10 ; 0x24 - GRAVESTONE
; db $04 ; 0x25 - BAD POINTER
; db $0C ; 0x26 - SWORD SWING SPARKLE
; db $1C ; 0x27 - DUCK
; db $00 ; 0x28 - WISH POND ITEM
; db $10 ; 0x29 - MILESTONE ITEM GET
; db $14 ; 0x2A - SPIN ATTACK SPARKLE A
; db $14 ; 0x2B - SPIN ATTACK SPARKLE B
; db $10 ; 0x2C - SOMARIA BLOCK
; db $08 ; 0x2D - SOMARIA BLOCK FIZZ
; db $20 ; 0x2E - SOMARIA BLOCK FISSION
; db $10 ; 0x2F - LAMP FLAME
; db $10 ; 0x30 - BYRNA WINDUP SPARK
; db $10 ; 0x31 - BYRNA SPARK
; db $04 ; 0x32 - BLAST WALL FIREBALL
; db $00 ; 0x33 - BLAST WALL EXPLOSION
; db $80 ; 0x34 - SKULL WOODS FIRE
; db $10 ; 0x35 - MASTER SWORD GET
; db $04 ; 0x36 - FLUTE
; db $30 ; 0x37 - WEATHERVANE EXPLOSION
; db $14 ; 0x38 - CUTSCENE DUCK
; db $10 ; 0x39 - SOMARIA PLATFORM POOF
; db $00 ; 0x3A - BIG BOMB EXPLOSION
; db $10 ; 0x3B - SWORD UP SPARKLE
; db $00 ; 0x3C - SPIN ATTACK CHARGE SPARKLE
; db $00 ; 0x3D - ITEM SPLASH
; db $08 ; 0x3E - RISING CRYSTAL
; db $00 ; 0x3F - BUSH POOF
; db $10 ; 0x40 - DWARF POOF
; db $08 ; 0x41 - WATERFALL SPLASH
; db $78 ; 0x42 - HAPPINESS POND RUPEES
; db $80 ; 0x43 - GANONS TOWER CUTSCENE
AnciType     = $0C4A

AncillaInit_SetCoordsAndExit = $0980C3
Ancilla_PrepOAMCoord_long = $08F6D9
Ancilla_SetOAM_XY_long = $08F6FE
Ancilla_GetRadialProjection_long = $08FB23

Ancilla_CheckForAvailableSlot = $0FF577
Ancilla_CheckInitialTile_A = $099DD3

Ancilla_CheckSpriteCollision_long = $088DA2

Ancilla_CheckTileCollision_long = $08923B
Ancilla_CheckTileCollision_Class2_long = $089243

Ancilla_CalculateSFXPan = $0DBB5E

Ancilla_CheckDamageToSprite = $06ECB7

; Table of ancilla properties
AncillaObjectAllocation = $08806F

AncillaAdd_BombosSpell = $08AF66
AncillaAdd_FireRodShot = $0880B3
AncillaAdd_Snoring = $0980C8
AncillaAdd_Bomb = $09811F
AncillaAdd_Boomerang = $09820F
AncillaAdd_BoomerangAsClink = $098345
AncillaAdd_DugUpFlute = $098C73
AncillaAdd_ChargedSpinAttackSparkle = $098CB1
AncillaAdd_ExplodingWeatherVane = $098D11
AncillaAdd_CutsceneDuck = $098D90
AncillaAdd_SomariaPlatformPoof = $098DD2
AncillaAdd_SuperBombExplosion = $098DF9

ConfigureRevivalAncillae = $098E4E

AncillaAdd_CaneOfByrnaInitSpark = $098EE0
AncillaAdd_LampFlame = $098F1C
AncillaAdd_ShovelDirt = $098F5B
AncillaAdd_BlastWallFireball = $099031
AncillaAdd_Arrow = $0990A4
AncillaAdd_CapePoof = $09912C
AncillaAdd_BushPoof = $0991C3
AncillaAdd_EtherSpell = $0991FC
AncillaAdd_VictorySpin = $0992AC
AncillaAdd_MagicPowder = $0992F0
AncillaAdd_WallTapSpark = $099395
AncillaAdd_SwordSwingSparkle = $0993C2
AncillaAdd_QuakeSpell = $099589
AncillaAdd_IceRodShot = $099863
AncillaAdd_Splash = $0998FC
AncillaAdd_Hookshot = $099B10
AncillaAdd_Blanket = $098091

AddHappinessPondRupees = $098AE0

DeleteBoomAndByrnaSparks = $0FFD86

Sparkle_PrepOAMFromRadial = $08DA17

Fireball_SpawnTrailGarnish = $09B020

SpriteSFX_QueueSFX2WithPan = $0DBB7C
SpriteSFX_QueueSFX3WithPan = $0DBB8A
