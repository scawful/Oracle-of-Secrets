; Defines common macros for the project.

; Set to 1 to enable global debug printing, 0 to disable.
!DEBUG = 1

; --- Module Disable Flags ---
; Set to 1 to DISABLE a module entirely (for bug isolation).
; When disabled, all hooks/patches from that module are excluded from assembly.
; WARNING: Disabling a module may cause linker errors if other modules
;          reference its symbols. See Oracle_main.asm for dependency notes.
!DISABLE_MUSIC     = 0

; Intro cutscene song IDs ($012C). Rain stays vanilla $03; Deku uses OW aux $12.
if !DISABLE_MUSIC == 0
  !Song_Rain       = $03
  !Song_DekuTheme  = $12
else
  !Song_Rain       = $03
  !Song_DekuTheme  = $03
endif

!DISABLE_OVERWORLD = 0
!DISABLE_DUNGEON   = 0
!DISABLE_SPRITES   = 0
!DISABLE_MASKS     = 0
!DISABLE_ITEMS     = 0
!DISABLE_MENU      = 0
!DISABLE_PATCHES   = 0

; --- Feature Toggle Flags ---
; Active RC features default to 1. Set to 0 to isolate a defect.
; Override these via Config/feature_flags.asm (generate with Scripts/Build/set_feature_flags.py).
; Source-built sprite sheets; identity sheet $64 owns the audited bank $40 tail.
!ENABLE_SOURCE_SPRITE_SHEETS        = 1
; Sky room sky layer ($A0 proof): sheet EA slot6, row6 colours, BG1 fill.
!ENABLE_SKY_ROOM_SKY                = 1
; Sky overworld source art; the live project ROM carries the Sky maps ($87/$94).
!ENABLE_SKY_OVERWORLD_GRAPHICS      = 1
; Selected Sky map collision and tower entrance recognition. Required once the
; project ROM's room $0090 exit points at Sky map $87 (sky_d8_award.asm assert).
!ENABLE_SKY_OVERWORLD_ROUTE         = 1
; Native Sky calm overlay uses saved page9C graphics/palette; rain stays host.
!ENABLE_SKY_OVERLAY_SOURCE_PROFILE  = 1
; Private D4 room-scoped actor/art prototype; no default behavior change.
!ENABLE_D4_ZORA_REDESIGN            = 1
; BF-only ice block pit reset and reset feedback; room-layout adoption is separate.
!ENABLE_D5_BF_PIT_RESET             = 0
; AF transfer-room pit reset; independent of BF and off until private qualification.
!ENABLE_D5_AF_PIT_RESET             = 0
; 16-bit WaterFillTable tile_count (dw instead of db, capacity >255 tiles for widened $027).
; Default 0 while live $027 has 222 tiles and yaze (water_fill_zone.cc) serializes db counts;
; enable (=1) alongside the yaze dw writer when a >255-tile $027 basin lands.
!ENABLE_WATER_FILL_16BIT_COUNT       = 0
!ENABLE_MINECART_PLANNED_TRACK_TABLE = 1
!ENABLE_MINECART_CART_SHUTTERS       = 0
; Qualified Room97 Bombchu target; tag39/AF binding remains required.
!ENABLE_D6_CHU_GATE_97              = 1
!ENABLE_MINECART_LIFT_TOSS           = 0
!ENABLE_D3_PRISON_SEQUENCE           = 0
!ENABLE_OCARINA_SONG_TINT            = 0
; Aux ABI 1 needs an explicitly bound authoring table; preserve ordinary ROMs.
!ENABLE_OW_AUX_EXTENSION              = 0
!ENABLE_KALYXO_DOCKS_PROFILE          = 0
; Native cached-exit ferry: Kalyxo Docks $30/$31 <-> Sea Zora Quay $99 (bound in
; Data/overworld/kalyxo_boat_placements.asm). Opening arrival is unchanged unless
; Boat_Marker holds !Boat_Magic.
!ENABLE_KALYXO_BOAT                   = 1
; Forest Glade ambush (prototype, off): after Kydrog's msg $21 the glade
; animals flee, a thunder blackout swaps stalfos art into the glade slots,
; stalfos rise around Link, and a mosaic ramp leads into the module $15
; banish (Sprites/Bosses/kydrog.asm).
!ENABLE_GLADE_AMBUSH                = 0
; M2 pause menu (decisions.org 2026-09-28: "Masks & Rings page after the M1
; playtest: layout A, one ring", "Masks stay Y items"). Active RC defaults on.
; One ring: one worn ring (RingSlot1). A new ring replaces the worn one; A on
; the worn ring takes it off. Ring effects read slot 1 only. File load moves
; an old save's slot 2/3 ring into an empty slot 1 and clears slots 2-3. The
; Quest page draws no rings.
!ENABLE_ONE_RING                    = 1
; Page loop: L and R always move one page, wrapping Masks&Rings <- Items ->
; Quest; the Items "Y:RINGS" prompt and Y shortcut are removed.
!ENABLE_MENU_PAGE_LOOP              = 1
; Map page (v4): a fourth page, Items -> Equipment -> Quest -> Map
; -> Items. Map opens the field map; the dungeon row sits under it. The six
; songs move from Equipment to the Quest bottom row. Needs MENU_PAGE3, PAGE_LOOP,
; EQUIPMENT_MENU.
; WRAM: MenuMapTravel_Pending $7E1EFF (Core/symbols.asm).
!ENABLE_MENU_MAP_TRAVEL             = 1
; Lyra/Sky overlay fix: Overworld_ReloadSubscreenOverlay (ZSCustomOverworld,
; $02AF58) skipped the subscreen-overlay table for every area >= $80, so a
; reload on a tail map ($A0-$BF) or during Song of Storms rain on a Sky map
; lost its overlay; and the map16 event overlay jump ($02EF50) indexes a
; 160-entry vector table that tail maps ($A0-$BF) overrun. The reload now
; takes the table path for tail maps and for rain, and the event overlay
; is a no-op for $8A >= $A0 (Overworld/lyra_overlay_fix.asm).
!ENABLE_LYRA_OVERLAY_FIX            = 1
; Garrison/Sky fly list; source preview until T3 native and save proof.
!ENABLE_SPECIAL_OVERWORLD_SOARING   = 0
; D8 Sky boss (sprite $C3, Sprites/Bosses/d8_boss.asm):
; Somaria-socket qualified cycles, credited-hit counter, three stages;
; room $96 uses dungeon spriteset $2D (base ROM PC 0x110AB7).
!ENABLE_D8_FARORE_GRAPHICS          = 0 ; Graphics + presence prototype; no companion control

; Horse Form (!CurrentMask = $09) + Toto Ranch NPC ($2D) + fence jumps:
; Off until prototype art and behavior review are complete.
!ENABLE_HORSE_FORM                  = 1
; Park Epona where Link last dismounted outdoors (any OW area, not Ranch-only).
; Off by default on master; this stack enables it for A5 fold proof. WRAM-only.
!ENABLE_HORSE_PARK_ANYWHERE         = 1



; Epona crowd check + mounted charge (Masks/horse_charge.asm): the song call
; refuses with 5+ active enemies (OAM headroom); charging into an enemy deals
; level-1 sword damage. Armored enemies and bosses are immune. Off until
; native proof.
!ENABLE_HORSE_CROWD_CHARGE          = 0

; Ranch milk: after the Ocarina, the Ranch Girl's later powder reveals offer
; Toto Ranch milk for 30 Rupees (BottleMan messages $187-$18B, no new text)
; instead of the curse reminder $10E. Off until native proof.
!ENABLE_RANCH_MILK                  = 0
; Lyra talkers: talk-only ShopMan ($BB) NPCs on the Lyra crescent island
; (parent $B3); placeholder text, no gates yet (Sprites/NPCs/lyra_talker.asm).
; Needs EARLY_GAME_BALANCE (its $BB dispatch).
!ENABLE_LYRA_TALKERS                = 0
; Lyra temple Zora: Sea Zora $B8 on $90 draws the E7 River Zora front.
; Needs ENABLE_D4_ZORA_REDESIGN and sprite set $8E on $90 (Sprites/NPCs/lyra_temple_zora.asm).
!ENABLE_LYRA_TEMPLE_ZORA            = 0
; Dev/beta testing harness in Bank $3C (Util/item_cheat.asm): non-destructive
; L+R+X kit grant, runtime cache reinit, and WarpDispatcher (including Special
; Overworld $80-$BF cached-exit load and dungeon room fall). Default off so
; shipping ROM bytes are unchanged; opt in with --enable ENABLE_DEBUG_TOOLS.
!ENABLE_DEBUG_TOOLS                 = 0

; --- Section-specific Log Flags ---
; Set these to 1 to see detailed logs for that section, or 0 to hide them.
!LOG_MUSIC     = 1
!LOG_OVERWORLD = 1
!LOG_DUNGEON   = 1
!LOG_SPRITES   = 1
!LOG_MASKS     = 1
!LOG_ITEMS     = 1
!LOG_MENU      = 1

; =========================================================
; print_debug
;
; Purpose: Prints a message and the current PC value during assembly, 
;          but only if !DEBUG is enabled.
;
; Parameters:
;   message: The string to be printed.
; =========================================================
macro print_debug(message)
  if !DEBUG == 1
    print "<message> ", pc
  endif
endmacro

; =========================================================
; log_section
;
; Purpose: Prints a header for a major section during assembly.
;
; Parameters:
;   name: The section name to log.
;   flag: A boolean flag (e.g. !LOG_SPRITES) to control visibility.
; =========================================================
macro log_section(name, flag)
    if !DEBUG == 1 && <flag> == 1
        print ""
        print "---  <name>  ---"
        print ""
    endif
endmacro

; =========================================================
; log_start
;
; Purpose: Prints a standardized log message for the start of a named block.
;
; Parameters:
;   name: The block name.
;   flag: Control flag.
; =========================================================
macro log_start(name, flag)
    if !DEBUG == 1 && <flag> == 1
        print "$", pc, " > <name>"
    endif
endmacro

; =========================================================
; log_end
;
; Purpose: Prints a standardized log message for the end of a named block.
;
; Parameters:
;   name: The block name.
;   flag: Control flag.
; =========================================================
macro log_end(name, flag)
    if !DEBUG == 1 && <flag> == 1
        print "$", pc, " < <name>"
    endif
endmacro

; =========================================================
; OOS_LongEntry / OOS_LongExit
;
; Purpose: Standardize ABI handling for long-entry routines.
;          Preserves P and DB so caller M/X and data bank are restored.
;
; Usage:
;   OOS_LongEntry
;     ; SEP/REP as needed
;   ...
;   OOS_LongExit
; =========================================================
macro OOS_LongEntry()
    PHP
    PHB
    PHK
    PLB
endmacro

macro OOS_LongExit()
    PLB
    PLP
    RTL
endmacro

; =========================================================
; OOS_Hook / OOS_HookMx
;
; Purpose: Standardize hook declarations for hooks.json generation.
;          These macros only set org + emit an @hook tag for tooling.
;
; Usage:
;   %OOS_Hook($02C0C3, jsl, NewOverworld_SetCameraBounds, Overworld_SetCameraBounds)
;   %OOS_HookMx($02C0C3, jsl, NewOverworld_SetCameraBounds, Overworld_SetCameraBounds, 16, 8)
; =========================================================
macro OOS_Hook(addr, kind, target, name)
    org <addr>
    ; @hook module=Util name=<name> kind=<kind> target=<target>
endmacro

macro OOS_HookMx(addr, kind, target, name, expected_m, expected_x)
    org <addr>
    ; @hook module=Util name=<name> kind=<kind> target=<target> expected_m=<expected_m> expected_x=<expected_x>
endmacro

if not(defined("ENABLE_GOLDSTAR_CELL"))
  !ENABLE_GOLDSTAR_CELL = 1
endif

; Build-derived native reader mode. Direct legacy assembly stays disabled.
!SPECIAL_OVERWORLD_NATIVE = 0
; Entrance and trigger readers also assemble without generated native data.
; Only the authenticated experimental compiler may override this later.
!SPECIAL_OVERWORLD_SEMANTIC_ENABLED = 0
