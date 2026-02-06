;===========================================================
; Debug Hacks
;
; Gives player all items when pressing L (not for main game)
; Bank 0x3C used for code
; WRITTEN: by XaserLE, refactored by scawful
; THANKS TO: -MathOnNapkins' Zelda Doc's
; -wiiqwertyuiop for his Zelda Disassembly
;===========================================================

!BetaRelease                              = $00
!DebugReloadLatch                         = $00FE               ; Uses UNUSED_FE (free RAM) for hotkey debounce
!DEBUG_REINIT                             = 0
!DEBUG_WARP                               = 0                   ; DISABLED - Enable debug warp dispatcher

; Reinit bitfield
!REINIT_DIALOG                            = $01
!REINIT_SPRITES                           = $02
!REINIT_OVERLAYS                          = $04
!REINIT_MSGBANK                           = $08
!REINIT_ROOMCACHE                         = $10

; Debug warp RAM addresses live in Core/symbols.asm (DBG_WARP_*).
; The Python client writes to these, and WarpDispatcher reads/clears them.

!DBG_WARP_ARM_MAGIC       = $A5
!DBG_WARP_STATUS_ARMED    = $5A

; Overwrite JSL executed every frame
org $068365 : JSL $3CA62A ; @hook module=Util name=$3CA62A kind=jsl target=$3CA62A

Follower_Main                             = $099F91
CreateMessagePointers                     = $0ED3EB
Sprite_LoadGraphicsProperties             = $00FC41
Sprite_ReloadAll_Overworld                = $09C499
Overworld_ReloadSubscreenOverlay_Interupt = $02AF58

org                                       $3CA62A               ; Expanded space for our routine ; @hook module=Util
{
if                                        !DEBUG_REINIT == 1
  JSL ReinitDispatcher
endif
if                                        !DEBUG_WARP == 1
  JSL WarpDispatcher
  JSL WarpPostTransitionCheck
endif
  ;LDA.l $7EF3C5 : CMP.b #$02 : BCS .continue ; Check if in main game
  ;JSL Follower_Main
  ;RTL
  ;.continue
  ; Hotkey: L+R+Select+Start -> reload message pointers + sprite properties
  PHP
  SEP #$20
  LDA RawJoypad1H : AND.b #$F0 : CMP.b #$30 : BNE .reset_reload
  LDA RawJoypad1L : AND.b #$30 : CMP.b #$30 : BNE .reset_reload
  LDA !DebugReloadLatch : BNE .skip_reload
  INC !DebugReloadLatch
  JSL Debug_ReloadRuntimeCaches
  BRA .skip_reload
  .reset_reload
  STZ !DebugReloadLatch
  .skip_reload
  PLP

  LDA $F2 : CMP #$70 : BEQ $03 : JMP END ; Check L, R and X button

if !BetaRelease == 0
  ; How many bombs you have. Can exceed 0x50, up to 0xff.
  LDA #$50 : STA Bombs

  LDA #$02 : STA MagicPowder
             STA Gloves

  LDA #$01 : STA FireRod
             STA IceRod

  LDA #$01 : STA BunnyHood

  LDA #$01 : STA DekuMask
  LDA #$01 : STA ZoraMask
  LDA #$01 : STA WolfMask
  LDA #$01 : STA StoneMask

  LDA #$01 : STA Book
  LDA #$01 : STA Somaria
  LDA #$01 : STA Boots
             STA Flippers
             STA WolfMask

  LDA #$04 : STA Sword

  LDA #$03 : STA Shield

  LDA #$02 : STA Armor

  LDA #$01 : STA BottleIndex ; has bottles
  LDA #$03 : STA Bottle1
  LDA #$05 : STA Bottle2
  LDA #$04 : STA Bottle3
  LDA #$06 : STA Bottle4

  ; How many arrows you have. Can exceed 0x70.
  LDA #$32 : STA Arrows

  ; 2 bytes for rupees (goal, for counting up)
  LDA #$E7 : STA Rupees
  LDA #$03 : STA RupeesGoal
  LDA #$07 : STA Pendants
  LDA #$6E : STA Ability
  LDA #$00 : STA Crystals
  LDA #$01 : STA Hookshot
  LDA #$02 : STA MagicUsage

  LDA #$A0 : STA MAXHP

endif
  LDA #$04 : STA Flute
  LDA #$01 : STA RocsFeather
  LDA #$03 : STA Bow
  LDA #$02 : STA Boomerang
             STA Mirror
             STA Byrna

  LDA #$01 : STA Lamp
             ; STA MagicHammer
             STA Pearl

  LDA #$A0 : STA HeartRefill
  LDA #$80 : STA MagicPower

  ; Skip story events, test goron mines
  LDX.b #$36
  LDA.l $7EF280, X
  ORA.b #$20
  STA.l $7EF280, X

  LDA.b #$02 : STA $7EF3C5
  LDA.b #$01 : STA MakuTreeQuest
  LDA.b #%00001010 : STA OOSPROG

END:

  JSL Follower_Main
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

  ; Only run in safe modes: 0x06 (Underworld Load), 0x07 (Underworld), 0x09 (Overworld)
  LDA.l MODE : CMP.b #$06 : BEQ .mode_ok
             CMP.b #$07 : BEQ .mode_ok
             CMP.b #$09 : BEQ .mode_ok
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

  ; overlays (overworld only, avoid mirror warp submodes)
  LDA.l DBG_REINIT_FLAGS : AND.b #!REINIT_OVERLAYS : BEQ .skip_overlays
    LDA.l MODE : CMP.b #$09 : BNE .overlay_err
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
; Debug Warp Dispatcher (Conditionally compiled when !DEBUG_WARP == 1)
; ==============================================================================
; Triggered by writing to DBG_WARP_REQUEST from the Python debug client.
; Performs a proper overworld warp by setting up all necessary RAM and
; triggering a mosaic transition.
;
; Usage from Python:
;   1. Write target area to DBG_WARP_AREA ($7E074D)
;   2. Write target X to DBG_WARP_X_LO/HI ($7E074E-$7E074F)
;   3. Write target Y to DBG_WARP_Y_LO/HI ($7E0750-$7E0751)
;   4. Write 1 to DBG_WARP_REQUEST ($7E074C) to trigger
;   5. Poll DBG_WARP_STATUS ($7E0752) for completion
; ==============================================================================

if !DEBUG_WARP == 1

org $3CB400
WarpDispatcher:
{
  PHP
  PHA
  PHX
  PHY

  SEP #$30

  ; Check if a warp is requested (guard against uninitialized garbage)
  LDA.l DBG_WARP_REQUEST : BNE .check_req
  JMP .done
.check_req
  CMP.b #$01 : BEQ .check_arm
  CMP.b #$02 : BEQ .check_arm
    LDA.b #$04 : STA.l DBG_WARP_ERROR  ; Error 4 = invalid request byte
    LDA.b #$00 : STA.l DBG_WARP_STATUS
    LDA.b #$00 : STA.l DBG_WARP_REQUEST
    LDA.b #$00 : STA.l DBG_WARP_ARM
    JMP .done
.check_arm
  LDA.l DBG_WARP_ARM : CMP.b #!DBG_WARP_ARM_MAGIC : BEQ .check_status
    LDA.b #$05 : STA.l DBG_WARP_ERROR  ; Error 5 = not armed
    LDA.b #$00 : STA.l DBG_WARP_STATUS
    LDA.b #$00 : STA.l DBG_WARP_REQUEST
    LDA.b #$00 : STA.l DBG_WARP_ARM
    JMP .done
.check_status
  LDA.l DBG_WARP_STATUS : CMP.b #!DBG_WARP_STATUS_ARMED : BEQ .has_request
    LDA.b #$06 : STA.l DBG_WARP_ERROR  ; Error 6 = not armed (status)
    LDA.b #$00 : STA.l DBG_WARP_STATUS
    LDA.b #$00 : STA.l DBG_WARP_REQUEST
    LDA.b #$00 : STA.l DBG_WARP_ARM
    JMP .done
.has_request
  LDA.b #$00 : STA.l DBG_WARP_ARM

  ; Only allow warps in safe game modes
  ; 0x09 = Overworld normal play, 0x07 = Dungeon normal play
  LDA.l MODE : CMP.b #$09 : BEQ .mode_ok_ow
               CMP.b #$07 : BEQ .mode_ok_uw
  ; Wrong mode - set error and clear request
  LDA.b #$01 : STA.l DBG_WARP_ERROR
  LDA.b #$00 : STA.l DBG_WARP_REQUEST
  JMP .done

.mode_ok_uw
  ; Dungeon room warps not yet supported - too complex without proper setup
  ; Return error code 2
  LDA.b #$02 : STA.l DBG_WARP_ERROR
  LDA.b #$00 : STA.l DBG_WARP_REQUEST
  JMP .done

.mode_ok_ow
  ; Only allow in submode 0x00 (player control)
  LDA.l SUBMODE : BEQ .submode_ok
  JMP .busy
.submode_ok

  ; Mark warp in progress
  LDA.b #$02 : STA.l DBG_WARP_STATUS

  ; Check if this is a same-area warp (just repositioning)
  ; or a cross-area warp (needs full transition)
  LDA.l DBG_WARP_REQUEST : CMP.b #$02 : BEQ .same_area_warp

  ; Cross-area warp: Check if cross-world BEFORE modifying OWSCR
  ; (LW 0x00-3F, DW 0x40-7F, SW 0x80+)
  LDA.l OWSCR            ; Current area (not yet modified)
  AND.b #$40             ; Get world bit (0=LW, $40=DW)
  STA.l $00              ; Temp store
  LDA.l DBG_WARP_AREA    ; Target area
  AND.b #$40
  CMP.l $00              ; Same world?
  BEQ .same_world_warp

  ; Cross-world warp detected - error out
  ; User must mirror warp first, then warp within that world
  LDA.b #$03 : STA.l DBG_WARP_ERROR  ; Error 3 = cross-world warp
  LDA.b #$00 : STA.l DBG_WARP_REQUEST
  JMP .done

.same_world_warp
  ; Now safe to set target area
  LDA.l DBG_WARP_AREA
  STA.l OWSCR           ; $7E008A - current area
  STA.l OWSCR2          ; $7E040A - area copy

  ; Set Link's position
  REP #$20
  LDA.l DBG_WARP_X_LO   ; 16-bit load (X_LO + X_HI)
  STA.l POSX            ; $7E0022
  LDA.l DBG_WARP_Y_LO   ; 16-bit load (Y_LO + Y_HI)
  STA.l POSY            ; $7E0020
  SEP #$20
  ; Cross-area warp (same world): Use SUBMODE 0x24 (StartMosaicTransition) which chains:
  ; 0x24 -> 0x25 -> 0x26 (LoadAuxGFX) -> 0x27 (TriggerTilemapUpdate)
  ;      -> 0x28 (LoadAndBuildScreen) -> 0x29 (FadeBackInFromMosaic)
  ; This stays in Mode 0x09 and reloads based on $8A (already set above)

  ; Set outdoor flag (we're warping to overworld)
  LDA.b #$00 : STA.l $7E001B   ; INDOORS = 0

  ; Initialize the mosaic effect for transition
  LDA.b #$07 : STA.l $7E0095   ; Start mosaic at max intensity
              STA.l $7EC011   ; Mosaic cache

  ; Clear scroll lock
  LDA.b #$00 : STA.l $7E011A   ; Clear scroll lock low
              STA.l $7E011B   ; Clear scroll lock high

  ; Set submodule to StartMosaicTransition
  ; Mode stays at 0x09 (Overworld), submode drives the reload
  LDA.b #$24 : STA.l SUBMODE

  ; Set flag to trigger post-warp GFX reload when transition completes
  LDA.b #$01 : STA.l DBG_WARP_GFX_PENDING

  ; Mark warp in progress (will be set to complete after GFX reload)
  LDA.b #$02 : STA.l DBG_WARP_STATUS
  LDA.b #$00 : STA.l DBG_WARP_ERROR
              STA.l DBG_WARP_REQUEST
  JMP .done

.same_area_warp
  ; Same-area warp: just move Link, no transition needed
  ; Set Link's position
  REP #$20
  LDA.l DBG_WARP_X_LO
  STA.l POSX
  LDA.l DBG_WARP_Y_LO
  STA.l POSY
  SEP #$20
  ; Mark complete immediately
  LDA.b #$03 : STA.l DBG_WARP_STATUS
  LDA.b #$00 : STA.l DBG_WARP_ERROR
              STA.l DBG_WARP_REQUEST
  JMP .done

.busy
  ; Game is busy with another transition, don't interfere
  ; Leave request pending, it will be processed next frame
  JMP .done

.done
  PLY
  PLX
  PLA
  PLP
  RTL
}

; ==============================================================================
; WarpPostTransitionCheck
; ==============================================================================
; Called every frame to check if a warp transition has completed.
; When the transition finishes (SUBMODE returns to 0) and GFX_PENDING is set,
; this routine reloads the camera scroll and custom GFX for the new area.
; ==============================================================================
WarpPostTransitionCheck:
{
  PHP
  PHA
  PHX
  PHY

  SEP #$30

  ; Check if GFX reload is pending
  LDA.l DBG_WARP_GFX_PENDING : BEQ .done
  ; Ignore stale pending flag unless a warp is actively in progress
  LDA.l DBG_WARP_STATUS : CMP.b #$02 : BEQ .check_mode
    LDA.b #$00 : STA.l DBG_WARP_GFX_PENDING
    JMP .done
.check_mode

  ; Check if we're in overworld mode
  LDA.l MODE : CMP.b #$09 : BNE .done

  ; Check if transition has completed (SUBMODE back to 0)
  LDA.l SUBMODE : BNE .done

  ; Transition complete - recalculate camera scroll based on Link's position
  ; This fixes the camera drift issue from the warp
  JSL LostWoods_RecalculateScroll

  ; Load custom Oracle GFX for the new area (e.g., boat graphics for area 0x30)
  ; CheckForChangeGraphicsNormalLoadBoat is in custom_gfx.asm (same namespace)
  JSL CheckForChangeGraphicsNormalLoadBoat

  ; Clear the pending flag and mark warp complete
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
