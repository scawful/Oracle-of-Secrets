;===========================================================
; Debug Tools (Opt-in via !ENABLE_DEBUG_TOOLS == 1)
;
; Bank $3C ($3CA62A-$3CBFFF; bounded strictly below $3CC000
; Dungeons/attract_royal_graphics.asm).
; Invoked per-frame from P2_Tick (Sprites/Players/player2.asm)
; so it never collides with the $068365 Follower_Main hook.
;
; Features:
;   - Hotkey L+R+X: Non-destructive full testing kit grant
;     (preserves Crystals, GameState, OOSPROG, and OW events).
;   - Hotkey L+R+Select+Start: Reload message & sprite caches.
;   - ReinitDispatcher ($7FF3C0): Bridge-driven cache reload.
;   - WarpDispatcher ($7FF3C4): Bridge-driven area/room warps
;     including Special Overworld ($80-$BF) native $7EC140
;     cached-exit loads and Dungeon Room Fall (Submode $15).
;===========================================================

!BetaRelease                              = $00
!DebugReloadLatch                         = $00FE               ; Uses UNUSED_FE (free RAM) for hotkey debounce
!DEBUG_REINIT                             = 1
!DEBUG_WARP                               = 1

; Reinit bitfield
!REINIT_DIALOG                            = $01
!REINIT_SPRITES                           = $02
!REINIT_OVERLAYS                          = $04
!REINIT_MSGBANK                           = $08
!REINIT_ROOMCACHE                         = $10

; Debug mailbox RAM addresses live in Core/symbols.asm (DBG_REINIT_*/DBG_WARP_*
; at $7FF3C0-$7FF3CF inside vanilla-free UNUSED_7FF180).

!DBG_WARP_ARM_MAGIC       = $A5
!DBG_WARP_STATUS_ARMED    = $5A

CreateMessagePointers                     = $0ED3EB
Sprite_LoadGraphicsProperties             = $00FC41
Sprite_ReloadAll_Overworld                = $09C499
Overworld_ReloadSubscreenOverlay_Interupt = $02AF58

org $3CA62A ; Expanded space for debug tools (Bank $3C, below $3CC000)
DebugTools_Tick:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB
  SEP #$30
  LDA.b #$7E : PHA : PLB

if !DEBUG_REINIT == 1
  JSL ReinitDispatcher
endif
if !DEBUG_WARP == 1
  JSL WarpDispatcher
  JSL WarpPostTransitionCheck
endif

  ; Hotkey: L+R+Select+Start -> reload message pointers + sprite properties
  LDA.w RawJoypad1H : AND.b #$F0 : CMP.b #$30 : BNE .reset_reload
  LDA.w RawJoypad1L : AND.b #$30 : CMP.b #$30 : BNE .reset_reload
  LDA.w !DebugReloadLatch : BNE .skip_reload
  INC.w !DebugReloadLatch
  JSL Debug_ReloadRuntimeCaches
  BRA .skip_reload
  .reset_reload
  STZ.w !DebugReloadLatch
  .skip_reload

  ; Hotkey: L+R+X ($F2 == $70) -> non-destructive full testing kit grant
  LDA.b $F2 : CMP.b #$70 : BEQ .grant_kit
  JMP .end

.grant_kit
if !BetaRelease == 0
  ; Core tools, bombs, masks, armor, bottles, rupees, health, magic
  LDA.b #$50 : STA.l Bombs
  LDA.b #$02 : STA.l MagicPowder
               STA.l Gloves
               STA.l Armor
               STA.l MagicUsage
               STA.l Boomerang
               STA.l Mirror
               STA.l CustomRods ; Portal Rod tier

  LDA.b #$01 : STA.l FireRod
               STA.l IceRod
               STA.l BunnyHood
               STA.l DekuMask
               STA.l ZoraMask
               STA.l WolfMask
               STA.l StoneMask
               STA.l Book
               STA.l Somaria
               STA.l Boots
               STA.l Flippers
               STA.l BottleIndex
               STA.l Hookshot
               STA.l RocsFeather
               STA.l Lamp
               STA.l Hammer
               STA.l Pearl
               STA.l FishingRod
               STA.l PortalRodOwned
               STA.l GoldstarOwned
               STA.l ByrnaOwned
               STA.l BombchuOwned
               STA.l SwitchHookOwned
               STA.l GaroMaskOwned

  LDA.b #$A5 : STA.l GoldstarInventoryVersion
  LDA.b #!BOMBCHU_AMMO_MAX : STA.l BombchuAmmo

  ; Two-slot swords: Story blade lv4 + reforged Heavy Sword, preserving tunic bits
  LDA.b #$04 : STA.l Sword
               STA.l SwordStoryBlade
  LDA.l SwordSlotFlags
  AND.b #!SwordSlot_HeavyEquipped^$FF
  ORA.b #(!SwordSlot_Initialized|!SwordSlot_HeavyOwned|!SwordSlot_HeavyReforged)
  STA.l SwordSlotFlags

  LDA.b #$03 : STA.l Shield
               STA.l Bow
               STA.l Bottle1
  LDA.b #$05 : STA.l Bottle2
  LDA.b #$04 : STA.l Bottle3
  LDA.b #$06 : STA.l Bottle4

  LDA.b #$32 : STA.l Arrows
  LDA.b #$E7 : STA.l Rupees
               STA.l RupeesDisplay
  LDA.b #$03 : STA.l RupeesGoal
               STA.l RupeesDisplay+1
  LDA.b #$07 : STA.l Pendants
  LDA.b #$6E : STA.l Ability
  LDA.b #$A0 : STA.l MAXHP
               STA.l HeartRefill
  LDA.b #$80 : STA.l MagicPower
endif

  ; All Ocarina songs (1-5 via Flute=7, song 6 Epona via SideQuestProg2 bit 1)
  ; plus Sky Soaring token. Preserves Crystals, GameState, OOSPROG & OW events.
  LDA.b #$07 : STA.l Flute
  LDA.l SideQuestProgress2 : ORA.b #!SideQuest2_EponaSong : STA.l SideQuestProgress2
  LDA.b #!SKY_SOARING_LEARNED : STA.l SkySoaringLearned

.end
  PLB
  REP #$30
  PLY : PLX : PLA
  PLP
  RTL
}

; Reuse an unused Arrow table byte range in bank $09 as a return stub.
pushpc
org $099090 ; @hook module=Util
Underworld_LoadSprites_ReturnStub:
  JML Debug_LoadUnderworldSprites_Return
pullpc

org $3CB000
Debug_LoadUnderworldSprites:
{
  ; Underworld_LoadSprites ends with RTS, so we fake a JSR return.
  PEA.w Underworld_LoadSprites_ReturnStub-1 : JML $09C290 ; Underworld_LoadSprites
Debug_LoadUnderworldSprites_Return:
  RTL
}

Debug_ReloadRuntimeCaches:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB

  SEP   #$20
  LDA.b #$7E : PHA : PLB

  REP #$30
  JSL CreateMessagePointers
  JSL Sprite_LoadGraphicsProperties

  SEP   #$20
  LDA.w INDOORS : BNE .indoors
    REP #$30
    JSL Sprite_ReloadAll_Overworld
    BRA .done
  .indoors
    REP #$30
    JSL Debug_LoadUnderworldSprites

  .done
  PLB
  REP #$30
  PLY : PLX : PLA
  PLP
  RTL
}

; ------------------------------------------------------------------------------
; Runtime cache reinit (bridge-driven)
; ------------------------------------------------------------------------------

org $3CB200
ReinitDispatcher:
{
  PHP
  PHA
  PHX
  PHY

  SEP #$30

  ; Only run in safe modes: 0x06 (Underworld Load), 0x07 (Underworld),
  ; 0x09 (Overworld), 0x0B (Special Overworld)
  LDA.l MODE : CMP.b #$06 : BEQ .mode_ok
               CMP.b #$07 : BEQ .mode_ok
               CMP.b #$09 : BEQ .mode_ok
               CMP.b #$0B : BEQ .mode_ok
  JMP .done

.mode_ok
  LDA.l DBG_REINIT_FLAGS : BNE +
  JMP   .done
+

  ; Clear status/error for a fresh run
  LDA.b #$00 : STA.l DBG_REINIT_STATUS : STA.l DBG_REINIT_ERROR

  ; dialog pointers
  LDA.l DBG_REINIT_FLAGS : AND.b #!REINIT_DIALOG : BEQ .skip_dialog
    LDA.b #!REINIT_DIALOG : STA.l DBG_REINIT_LAST
    JSL   Reinit_DialogPointers
    LDA.l DBG_REINIT_STATUS : ORA.b #!REINIT_DIALOG : STA.l DBG_REINIT_STATUS
  .skip_dialog

  ; msgbank (alias to dialog pointers)
  LDA.l DBG_REINIT_FLAGS : AND.b #!REINIT_MSGBANK : BEQ .skip_msgbank
    LDA.b #!REINIT_MSGBANK : STA.l DBG_REINIT_LAST
    JSL   Reinit_DialogPointers
    LDA.l DBG_REINIT_STATUS : ORA.b #!REINIT_MSGBANK : STA.l DBG_REINIT_STATUS
  .skip_msgbank

  ; sprites
  LDA.l DBG_REINIT_FLAGS : AND.b #!REINIT_SPRITES : BEQ .skip_sprites
    LDA.l MODE : CMP.b #$09 : BEQ .sprites_ow
                 CMP.b #$0B : BEQ .sprites_ow
                 CMP.b #$07 : BEQ .sprites_uw
    LDA.l DBG_REINIT_ERROR : ORA.b #!REINIT_SPRITES : STA.l DBG_REINIT_ERROR
    BRA   .skip_sprites
  .sprites_ow
    LDA.b #!REINIT_SPRITES : STA.l DBG_REINIT_LAST
    JSL   Reinit_Sprites_Overworld
    LDA.l DBG_REINIT_STATUS : ORA.b #!REINIT_SPRITES : STA.l DBG_REINIT_STATUS
    BRA   .skip_sprites
  .sprites_uw
    LDA.b #!REINIT_SPRITES : STA.l DBG_REINIT_LAST
    JSL   Reinit_Sprites_Underworld
    LDA.l DBG_REINIT_STATUS : ORA.b #!REINIT_SPRITES : STA.l DBG_REINIT_STATUS
  .skip_sprites

  ; overlays (overworld/special only, avoid mirror warp submodes)
  LDA.l DBG_REINIT_FLAGS : AND.b #!REINIT_OVERLAYS : BEQ .skip_overlays
    LDA.l MODE : CMP.b #$09 : BEQ .overlay_mode_ok
                 CMP.b #$0B : BNE .overlay_err
  .overlay_mode_ok
    LDA.l SUBMODE : CMP.b #$23 : BEQ .overlay_err
                    CMP.b #$24 : BEQ .overlay_err
                    CMP.b #$2C : BEQ .overlay_err
    LDA.b #!REINIT_OVERLAYS : STA.l DBG_REINIT_LAST
    JSL   Reinit_Overlays
    LDA.l DBG_REINIT_STATUS : ORA.b #!REINIT_OVERLAYS : STA.l DBG_REINIT_STATUS
    BRA   .skip_overlays
  .overlay_err
    LDA.l DBG_REINIT_ERROR : ORA.b #!REINIT_OVERLAYS : STA.l DBG_REINIT_ERROR
  .skip_overlays

  ; room cache (underworld load/transition only)
  LDA.l DBG_REINIT_FLAGS : AND.b #!REINIT_ROOMCACHE : BEQ .skip_roomcache
    LDA.l MODE : CMP.b #$06 : BEQ .roomcache_ok
                 CMP.b #$07 : BNE .roomcache_err
    LDA.l SUBMODE : CMP.b #$01 : BEQ .roomcache_ok
                    CMP.b #$02 : BEQ .roomcache_ok
                    CMP.b #$1A : BEQ .roomcache_ok
    BRA .roomcache_err
  .roomcache_ok
    LDA.b #!REINIT_ROOMCACHE : STA.l DBG_REINIT_LAST
    JSL   Reinit_RoomCache
    LDA.l DBG_REINIT_STATUS : ORA.b #!REINIT_ROOMCACHE : STA.l DBG_REINIT_STATUS
    BRA   .skip_roomcache
  .roomcache_err
    LDA.l DBG_REINIT_ERROR : ORA.b #!REINIT_ROOMCACHE : STA.l DBG_REINIT_ERROR
  .skip_roomcache

  LDA.b #$00 : STA.l DBG_REINIT_FLAGS

.done
  PLY
  PLX
  PLA
  PLP
  RTL
}

Reinit_DialogPointers:
{
  PHP
  REP #$30
  JSL CreateMessagePointers
  PLP
  RTL
}

Reinit_Sprites_Overworld:
{
  PHP
  REP #$30
  JSL Sprite_LoadGraphicsProperties
  JSL Sprite_ReloadAll_Overworld
  PLP
  RTL
}

Reinit_Sprites_Underworld:
{
  PHP
  REP #$30
  JSL Sprite_LoadGraphicsProperties
  JSL Debug_LoadUnderworldSprites
  PLP
  RTL
}

Reinit_Overlays:
{
  PHP
  REP #$30
  JSL Overworld_ReloadSubscreenOverlay_Interupt
  PLP
  RTL
}

Reinit_RoomCache:
{
  PHP
  REP #$30
  JSL CustomRoomCollision
  PLP
  RTL
}

; ==============================================================================
; Debug Warp Dispatcher (Bank $3C, $7FF3C4-$7FF3CF mailbox)
; ==============================================================================
; Protocol:
;   1. Write target parameters:
;      - Req 1 (Overworld / Special Overworld warp):
;          DBG_WARP_AREA ($7FF3C5) = $00-$BF
;          DBG_WARP_X_LO/HI ($7FF3C6-$7FF3C7), DBG_WARP_Y_LO/HI ($7FF3C8-$7FF3C9)
;          (If X==0 && Y==0, defaults to the area's camera interior.)
;      - Req 2 (Same-area reposition):
;          DBG_WARP_X_LO/HI, DBG_WARP_Y_LO/HI
;      - Req 3 (Dungeon room fall, requires MODE == $07):
;          DBG_WARP_ROOM_LO/HI ($7FF3CE-$7FF3CF) = 16-bit room ID
;   2. Arm mailbox: DBG_WARP_ARM ($7FF3CD) = $A5, DBG_WARP_STATUS ($7FF3CA) = $5A
;   3. Trigger: DBG_WARP_REQUEST ($7FF3C4) = 1, 2, or 3
;   4. Poll DBG_WARP_STATUS ($7FF3CA) until 3 (complete) or inspect DBG_WARP_ERROR
; ==============================================================================

if !DEBUG_WARP == 1

org $3CB400
WarpDispatcher:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB
  SEP #$30
  LDA.b #$7E : PHA : PLB

  ; Check if a warp is requested (guard against uninitialized garbage)
  LDA.l DBG_WARP_REQUEST : BNE .check_req
  JMP .done
.check_req
  CMP.b #$01 : BEQ .check_arm
  CMP.b #$02 : BEQ .check_arm
  CMP.b #$03 : BEQ .check_arm
    LDA.b #$04 : STA.l DBG_WARP_ERROR  ; Error 4 = invalid request byte
    LDA.b #$00 : STA.l DBG_WARP_STATUS
                 STA.l DBG_WARP_REQUEST
                 STA.l DBG_WARP_ARM
    JMP .done
.check_arm
  LDA.l DBG_WARP_ARM : CMP.b #!DBG_WARP_ARM_MAGIC : BEQ .check_status
    LDA.b #$05 : STA.l DBG_WARP_ERROR  ; Error 5 = not armed
    LDA.b #$00 : STA.l DBG_WARP_STATUS
                 STA.l DBG_WARP_REQUEST
                 STA.l DBG_WARP_ARM
    JMP .done
.check_status
  LDA.l DBG_WARP_STATUS : CMP.b #!DBG_WARP_STATUS_ARMED : BEQ .has_request
    LDA.b #$06 : STA.l DBG_WARP_ERROR  ; Error 6 = not armed (status)
    LDA.b #$00 : STA.l DBG_WARP_STATUS
                 STA.l DBG_WARP_REQUEST
                 STA.l DBG_WARP_ARM
    JMP .done
.has_request
  ; Only allow warps in safe playable modes:
  ; $07 = Underworld, $09 = Overworld, $0B = Special Overworld
  LDA.l MODE : CMP.b #$09 : BEQ .mode_ok
               CMP.b #$0B : BEQ .mode_ok
               CMP.b #$07 : BEQ .mode_ok
    LDA.b #$01 : STA.l DBG_WARP_ERROR  ; Error 1 = unsafe mode
    LDA.b #$00 : STA.l DBG_WARP_REQUEST
                 STA.l DBG_WARP_ARM
    JMP .done

.mode_ok
  ; Only trigger when player has control (SUBMODE == $00)
  LDA.l SUBMODE : BEQ .submode_ok
    JMP .done ; Busy — leave request & arm intact for next frame

.submode_ok
  LDA.b #$00 : STA.l DBG_WARP_ARM
  LDA.b #$02 : STA.l DBG_WARP_STATUS

  LDA.l DBG_WARP_REQUEST
  CMP.b #$02 : BNE + : JMP .same_area_warp : +
  CMP.b #$03 : BNE + : JMP .dungeon_fall_warp : +

  ; --- Request $01: Overworld / Special Overworld area warp ---
  LDA.l DBG_WARP_AREA : CMP.b #$C0 : BCC .area_valid
    LDA.b #$07 : STA.l DBG_WARP_ERROR  ; Error 7 = invalid area (>= $C0)
    LDA.b #$00 : STA.l DBG_WARP_STATUS
                 STA.l DBG_WARP_REQUEST
    JMP .done

.area_valid
  ; Fast mosaic path only for same-world LW/DW -> LW/DW while already in Mode $09.
  ; Special Overworld ($80-$BF), cross-world (LW<->DW), Mode $0B, and Mode $07
  ; all use the native $7EC140 cached-exit Module $08 loader below.
  LDA.l MODE : CMP.b #$09 : BNE .cached_exit_warp
  LDA.l OWSCR : CMP.b #$80 : BCS .cached_exit_warp
  LDA.l DBG_WARP_AREA : CMP.b #$80 : BCS .cached_exit_warp
  EOR.l OWSCR : AND.b #$40 : BNE .cached_exit_warp

  ; Same-world LW/DW mosaic transition
  LDA.l DBG_WARP_AREA
  STA.l OWSCR           ; $7E008A
  STA.l OWSCR2          ; $7E040A

  REP #$20
  LDA.l DBG_WARP_X_LO : STA.l POSX
  LDA.l DBG_WARP_Y_LO : STA.l POSY
  SEP #$20

  LDA.b #$00 : STA.l $7E001B   ; INDOORS = 0
  LDA.b #$07 : STA.l $7E0095   ; Mosaic intensity
               STA.l $7EC011   ; Mosaic cache
  LDA.b #$00 : STA.l $7E011A   ; Clear scroll lock
               STA.l $7E011B
  LDA.b #$24 : STA.l SUBMODE   ; StartMosaicTransition
  LDA.b #$01 : STA.l DBG_WARP_GFX_PENDING
  LDA.b #$02 : STA.l DBG_WARP_STATUS
  LDA.b #$00 : STA.l DBG_WARP_ERROR
               STA.l DBG_WARP_REQUEST
  JMP .done

.cached_exit_warp
  ; Synthesize a full native $32-byte exit cache at $7EC140-$7EC171 and
  ; load via Module $08 ($02E5D4), matching GoronCheckpoint / SpecialSoaring / Boat.
  ; Preserve zero-page scratch $00-$05 on stack.
  REP #$20
  LDA.b $00 : PHA
  LDA.b $02 : PHA
  LDA.b $04 : PHA

  ; Set target area in $8A so NewOverworld_SetCameraBounds populates $0600-$0617
  SEP #$20
  LDA.l DBG_WARP_AREA : STA.b $8A : STA.w $040A
  REP #$20
  SEP #$10
  JSL NewOverworld_SetCameraBounds ; M16/X8 -> populates $0600..$0607, $0610..$0617

  ; Load target Link X ($04) and Link Y ($02); if both 0, pick safe interior ($0604+$80, $0600+$A0)
  LDA.l DBG_WARP_X_LO : STA.b $04
  LDA.l DBG_WARP_Y_LO : STA.b $02
  ORA.b $04 : BNE .have_xy
    LDA.w $0604 : CLC : ADC.w #$0080 : STA.b $04
    LDA.w $0600 : CLC : ADC.w #$00A0 : STA.b $02
.have_xy

  ; Write Area ($C140, $C14C) and main/subscreen ($C142 = $0016)
  LDA.l DBG_WARP_AREA : AND.w #$00FF
  STA.w $C140
  STA.w $C14C
  LDA.w #$0016 : STA.w $C142

  ; Write Link Y ($C148) and Link X ($C14A)
  LDA.b $02 : STA.w $C148
  LDA.b $04 : STA.w $C14A

  ; Camera trigger Y ($C150 = LinkY + $1F) and X ($C152 = LinkX + $07)
  LDA.b $02 : CLC : ADC.w #$001F : STA.w $C150
  LDA.b $04 : CLC : ADC.w #$0007 : STA.w $C152

  ; ScrollY = clamp(LinkY - $0050, $0600, $0602) -> $C144 & $00
  LDA.b $02 : SEC : SBC.w #$0050 : BCC .clamp_sy_lo
  CMP.w $0600 : BCC .clamp_sy_lo
  CMP.w $0602 : BCC .sy_ok
  LDA.w $0602 : BRA .sy_ok
.clamp_sy_lo
  LDA.w $0600
.sy_ok
  STA.w $C144
  STA.b $00

  ; ScrollX = clamp(LinkX - $0078, $0604, $0606) -> $C146 & $02
  LDA.b $04 : SEC : SBC.w #$0078 : BCC .clamp_sx_lo
  CMP.w $0604 : BCC .clamp_sx_lo
  CMP.w $0606 : BCC .sx_ok
  LDA.w $0606 : BRA .sx_ok
.clamp_sx_lo
  LDA.w $0604
.sx_ok
  STA.w $C146
  STA.b $02

  ; TilemapOrigin ($C14E) = (((ScrollY - $0600) & $FFF0) << 3) | (((ScrollX - $0604) & $FFF0) >> 3)
  LDA.b $00 : SEC : SBC.w $0600 : AND.w #$FFF0 : ASL #3 : STA.b $00
  LDA.b $02 : SEC : SBC.w $0604 : AND.w #$FFF0 : LSR #3 : ORA.b $00
  STA.w $C14E

  ; Copy camera bounds $0600-$0606 -> $C154-$C15A and $0610-$0616 -> $C15C-$C162
  LDA.w $0600 : STA.w $C154
  LDA.w $0602 : STA.w $C156
  LDA.w $0604 : STA.w $C158
  LDA.w $0606 : STA.w $C15A
  LDA.w $0610 : STA.w $C15C
  LDA.w $0612 : STA.w $C15E
  LDA.w $0614 : STA.w $C160
  LDA.w $0616 : STA.w $C162

  ; GFX cache words ($C164: $0AA1=$21 DW / $20 LW+SW; $C166 overwritten by loader)
  SEP #$20
  LDA.l DBG_WARP_AREA : CMP.b #$40 : BCC .gfx_lw_sw
  CMP.b #$80 : BCS .gfx_lw_sw
    REP #$20 : LDA.w #$2100 : BRA .store_gfx
.gfx_lw_sw
  REP #$20 : LDA.w #$2000
.store_gfx
  STA.w $C164
  STZ.w $C166

  ; Fresh scroll modifiers ($C168-$C171 = 5 zero words)
  STZ.w $C168 : STZ.w $C16A : STZ.w $C16C : STZ.w $C16E : STZ.w $C170

  ; Trigger native cached-exit load via synthetic cache room !GoronCheckpoint_CacheRoom
  STZ.w $0696 : STZ.w $0698
  LDA.w #!GoronCheckpoint_CacheRoom : STA.b $A0
  STZ.w $010A : STZ.w $04AA
  STZ.w $0FFF

  ; Restore zero-page scratch $00-$05 before switching to 8-bit
  PLA : STA.b $04
  PLA : STA.b $02
  PLA : STA.b $00

  SEP #$20
  ; SavedWorld ($7EF3CA): $40 for Dark World ($40-$7F), $00 for LW ($00-$3F) & SW ($80-$BF)
  LDA.l DBG_WARP_AREA : CMP.b #$40 : BCC .sw_zero
  CMP.b #$80 : BCS .sw_zero
    LDA.b #$40 : BRA .set_world
.sw_zero
  LDA.b #$00
.set_world
  STA.l SavedWorld

  STZ.w $03F0 : STZ.b $3A
  STZ.w $0300 : STZ.w $0301 : STZ.w $037A
  STZ.b $5D : STZ.w $03EF : STZ.w $02E4
  STZ.b $B0 : STZ.b $11
  LDA.b #$80 : STA.b $13
  STZ.b $9B
  LDA.b #$08 : STA.b $10 ; Module $08: LoadOverworldFromUnderworld

  LDA.b #$02 : STA.l DBG_WARP_GFX_PENDING
  LDA.b #$02 : STA.l DBG_WARP_STATUS
  LDA.b #$00 : STA.l DBG_WARP_ERROR
               STA.l DBG_WARP_REQUEST
  JMP .done

.same_area_warp
  ; Same-area reposition (valid in Mode $07, $09, $0B)
  REP #$20
  LDA.l DBG_WARP_X_LO : STA.l POSX
  LDA.l DBG_WARP_Y_LO : STA.l POSY
  SEP #$20
  LDA.b #$03 : STA.l DBG_WARP_STATUS
  LDA.b #$00 : STA.l DBG_WARP_ERROR
               STA.l DBG_WARP_REQUEST
  JMP .done

.dungeon_fall_warp
  ; Request $03: Dungeon room fall via native Submode $15 (requires Mode $07)
  LDA.l MODE : CMP.b #$07 : BEQ .fall_mode_ok
    LDA.b #$02 : STA.l DBG_WARP_ERROR ; Error 2 = room fall requires Mode $07
    LDA.b #$00 : STA.l DBG_WARP_STATUS
                 STA.l DBG_WARP_REQUEST
    JMP .done
.fall_mode_ok
  LDA.b $A0 : STA.b $A2
  LDA.l DBG_WARP_ROOM_LO : STA.b $A0
  LDA.l DBG_WARP_ROOM_HI : STA.b $A1
  LDA.b #$20 : STA.b $5C ; Fall animation timer
  LDA.b #$01 : STA.b $5D ; Falling state
  STZ.b $EE              ; Reset to floor layer 0
  LDA.b #$15 : STA.b $11 ; Submode $15: pit/fall room transition
  LDA.b #$03 : STA.l DBG_WARP_GFX_PENDING
  LDA.b #$02 : STA.l DBG_WARP_STATUS
  LDA.b #$00 : STA.l DBG_WARP_ERROR
               STA.l DBG_WARP_REQUEST

.done
  PLB
  REP #$30
  PLY : PLX : PLA
  PLP
  RTL
}

; ==============================================================================
; WarpPostTransitionCheck
; ==============================================================================
WarpPostTransitionCheck:
{
  PHP
  PHA
  PHX
  PHY

  SEP #$30

  LDA.l DBG_WARP_GFX_PENDING : BEQ .done
  ; Ignore stale pending flag unless a warp is actively in progress
  LDA.l DBG_WARP_STATUS : CMP.b #$02 : BEQ .dispatch
    LDA.b #$00 : STA.l DBG_WARP_GFX_PENDING
    JMP .done

.dispatch
  LDA.l DBG_WARP_GFX_PENDING
  CMP.b #$01 : BEQ .check_mosaic
  CMP.b #$02 : BEQ .check_cached_exit
  CMP.b #$03 : BEQ .check_dungeon_fall
  LDA.b #$00 : STA.l DBG_WARP_GFX_PENDING
  JMP .done

.check_mosaic
  LDA.l MODE : CMP.b #$09 : BNE .done
  LDA.l SUBMODE : BNE .done
  JSL LostWoods_RecalculateScroll
  JSL CheckForChangeGraphicsNormalLoadBoat
  BRA .complete

.check_cached_exit
  LDA.l MODE : CMP.b #$09 : BEQ .cached_sub
               CMP.b #$0B : BNE .done
.cached_sub
  LDA.l SUBMODE : BNE .done
  ; Wait until Module $08 fade-in completes (INIDISP mirror $13 == $0F)
  LDA.l $7E0013 : CMP.b #$0F : BNE .done
  BRA .complete

.check_dungeon_fall
  LDA.l MODE : CMP.b #$07 : BNE .done
  LDA.l SUBMODE : BNE .done

.complete
  LDA.b #$00 : STA.l DBG_WARP_GFX_PENDING
  LDA.b #$03 : STA.l DBG_WARP_STATUS

.done
  PLY
  PLX
  PLA
  PLP
  RTL
}

endif ; !DEBUG_WARP

assert pc() <= $3CC000, "Util/item_cheat.asm exceeded Bank $3C debug allocation ($3CC000)"
