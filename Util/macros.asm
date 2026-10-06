; Defines common macros for the project.

; Set to 1 to enable global debug printing, 0 to disable.
!DEBUG = 1

; --- Module Disable Flags ---
; Set to 1 to DISABLE a module entirely (for bug isolation).
; When disabled, all hooks/patches from that module are excluded from assembly.
; WARNING: Disabling a module may cause linker errors if other modules
;          reference its symbols. See Oracle_main.asm for dependency notes.
!DISABLE_MUSIC     = 0
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
!ENABLE_CUSTOM_ROOM_COLLISION         = 1
!ENABLE_FOLLOWER_TRANSITION_HOOKS     = 1
!ENABLE_GRAPHICS_TRANSFER_SCROLL_HOOK = 1
!ENABLE_WATER_GATE_HOOKS            = 1
!ENABLE_WATER_GATE_ROOMENTRY_RESTORE = 0
!ENABLE_WATER_GATE_OVERLAY_REDIRECT = 1
!ENABLE_MINECART_PLANNED_TRACK_TABLE = 1
!ENABLE_MINECART_CART_SHUTTERS       = 0
!ENABLE_MINECART_LIFT_TOSS           = 0
!ENABLE_D3_PRISON_SEQUENCE           = 0
!ENABLE_D7_FARORE_RESCUE_SEQUENCE    = 0
!ENABLE_OCARINA_SONG_TINT            = 0
!ENABLE_JUMPTABLELOCAL_GUARD         = 1
; RC opening features are enabled by default; disable individually for isolation.
; ATTRACT and ARRIVAL require CUTSCENE_FRAMEWORK (asserted in Oracle_main.asm).
!ENABLE_CUTSCENE_FRAMEWORK           = 1
!ENABLE_CUSTOM_ATTRACT_SEQUENCE      = 1
!ENABLE_ORACLE_ARRIVAL_SEQUENCE      = 1
; New-file Mirror experiment scene before the arrival (Core/Cutscene/experiment.asm).
; Requires ORACLE_ARRIVAL_SEQUENCE (asserted in Oracle_main.asm).
!ENABLE_EXPERIMENT_SCENE            = 1
; Impa follower: position-triggered hints on the Act I route (Sprites/NPCs/impa_hints.asm).
!ENABLE_IMPA_FOLLOWER_HINTS         = 1
; Shrine of Origins: west shutter opens only when Minish Link is in the NE chamber.
!ENABLE_ORIGINS_MINISH_PUZZLE        = 1
; Let Minish Link reopen the Origins shutter after earning the Moon Pearl,
; so the NW chest chamber has a return route (needs ORIGINS_MINISH_PUZZLE).
!ENABLE_ORIGINS_PEARL_RETURN_FIX     = 1
; Pause menu: hide/lock the X:LOG (Journal) and Y:RINGS (Ring Box) entries
; until the Book of Secrets ($7EF34E) / a ring is owned (Menu/*.asm).
!ENABLE_MENU_HIDE_RINGS_JOURNAL_EARLY = 1
; Pause menu + HUD: grey Ocarina icon and a no-song Song Menu state while the
; Ocarina is owned with no song learned ($7EF34C = 1) (Menu/*.asm).
!ENABLE_MENU_OCARINA_BLANK_SLOT      = 1
; Pause menu page 3 "Masks & Rings" (Menu/menu_page3.asm): L (or Y) on Items
; scrolls to a page with the five masks and six rings; the cursor equips masks
; (as Y items, $0202) and equips/unequips rings; X opens the Journal. Masks
; leave the item grid. Needs !ENABLE_RING_SRAM_RELOCATE = 1.
!ENABLE_MENU_PAGE3                   = 1
; Part 0 storm: rain overlay, rain sound and dim world map follow the saved
; storm bit (StoryProgress2 bit 7), set at wake-up, cleared when Link is back
; on Kalyxo after the Abyss; no rain in the Abyss (Overworld/storm.asm).
!ENABLE_PART0_STORM                  = 1
; Native 2-player PoC: pad-2 Start drops in a second Link (Sprites/Players/player2.asm).
!ENABLE_NATIVE_2P_POC                = 1
; Magic rings save to their own bytes ($7EF3A1-3A6, Core/sram.asm RingSaveBlock)
; instead of the legacy addresses that alias SideQuestProgress/2, Pineapples
; and RockMeatCount (Items/magic_rings.asm).
!ENABLE_RING_SRAM_RELOCATE           = 1
; Translucent dark band behind the text window (Core/text_shade.asm, HDMA ch 6).
!ENABLE_TEXT_BOX_SHADE               = 1
; Eon Owl one-shot: each Abyss Owl appearance happens once; after its talk and
; fly-away it does not respawn (EonOwlFlags $7EF3A7, Sprites/NPCs/eon_owl.asm).
!ENABLE_EON_OWL_ONE_SHOT             = 1
; Abyss respawn lock until the escape: outdoor deaths/continues follow the
; saved world ($7EF3CA), so the lock ends at the portal home instead of the
; Maku Tree (LoadDarkWorldIntro, Overworld/overworld.asm).
!ENABLE_ABYSS_RESPAWN_UNTIL_ESCAPE   = 1
; Eon Owl near trigger: the Abyss Owls talk only when Link is within
; !EonOwl_TalkDistance px (Sprites/NPCs/eon_owl.asm), not on area entry.
!ENABLE_EON_OWL_NEAR_TRIGGER         = 1
; Early-game balance: Act I/D1 enemy damage, per-location HP overrides,
; Red Potion 100 rupees (Core/early_game_balance.asm).
!ENABLE_EARLY_GAME_BALANCE          = 1
; Village dog polish: real gravity/velocity toss arc (replaces the flat
; HandleTossedDog height decrement) and an excited tail-wag reaction on
; landing (Sprites/NPCs/village_dog.asm).
!ENABLE_VILLAGE_DOG_POLISH          = 1
; Korok polish: Koroks in Korok Cove stroll a few px left/right near home and
; stop at walls (the walk never ended before), talk from any state, Makar
; uses the Korok palette, variant fixed per placement (no Hollo), and the
; sheets reload after the world map (Sprites/NPCs/korok.asm, world_map.asm).
!ENABLE_KOROK_POLISH                = 1
; World map: Light World dungeon markers follow story flags (crystals,
; Maku Tree, Ocarina) instead of the MapIcon counter $7EF3C7
; (Overworld/world_map.asm, Docs/Debugging/Issues/world_map_icons_2026-09-26.md).
!ENABLE_MAP_ICON_TIMELINE           = 1
; Dream return (decisions.org "DECIDED Abyss fixes follow-ups" item 3, option c):
; a few seconds after one of Maple's dreams lands, Link is reloaded through the
; Dream Hut entrance ($68) so a dream cannot strand him (Sprites/NPCs/maple.asm).
!ENABLE_DREAM_RETURN                = 1
; Sword warp home (decisions.org "Intro Abyss exit: the sword cuts Link
; home"): taking the Forest of Dreams sword (DW $58) plays a spin, sword-up
; and white flash, then reloads Link onto the Maku Tree area ($2A) with
; SavedWorld = $00, which ends the respawn lock and the storm; no portal at
; the arrival (Sprites/Objects/collectible.asm).
!ENABLE_SWORD_WARP_HOME             = 1
; Intro village Stalfos patrol: while GameState < 2, Wayward Village loads
; guard sprites ($42) with the pirate palette, half-heart contact plus a
; recovery pause, tuned chase speed, limited sight and a home box
; (Sprites/Enemies/stalfos_patrol.asm).
!ENABLE_INTRO_STALFOS_PATROL        = 1
; Part00 arrival lines (decisions.org "Arrival lines A/B/C approved"): a
; villager in the house (room $104) says B ($202) on the first wake and B2
; ($203) after a death; Impa opens with $25 (C) instead of the old $1C
; greeting (Core/part00.asm). Line A is in the arrival (opening.asm).
!ENABLE_PART00_ARRIVAL_LINES        = 1
; Part00 checkpoint (decisions.org "Part00 checkpoint after the village
; hole"): while GameState is 0, death/continue no longer reloads the new-file
; save (which replayed the whole intro); it respawns in the house, or at the
; village-hole landing (entrance $80, room $FE) once Link went down the hole
; (Core/part00.asm).
!ENABLE_PART00_CHECKPOINT           = 1
; Part00 night fix: from Farore's meeting (GameState 2) until Kydrog's ambush
; ($7EF300), area sprite lists stay on the day set, which holds Farore and
; Kydrog in the Forest Glade ($80); at night the ambush never loaded and the
; Maku Tree's $20 opened with input locked (Overworld/time_system.asm).
!ENABLE_PART00_NIGHT_FIX            = 1
; M2 pause menu (decisions.org 2026-09-28: "Masks & Rings page after the M1
; playtest: layout A, one ring", "Masks stay Y items"). Active RC defaults on.
; One ring: one worn ring (RingSlot1). A new ring replaces the worn one; A on
; the worn ring takes it off. Ring effects read slot 1 only. File load moves
; an old save's slot 2/3 ring into an empty slot 1 and clears slots 2-3. The
; Quest page draws no rings. Needs !ENABLE_RING_SRAM_RELOCATE = 1.
!ENABLE_ONE_RING                    = 1
; Page 3 layout A (Menu/menu_page3.asm): Items/Quest frame and tabs, masks on
; grid row 1 (5 masks + 1 empty spare cell), rings on grid row 3, red brackets
; on the worn mask and ring, no button prompt. Needs MENU_PAGE3 and ONE_RING.
!ENABLE_MENU_PAGE3_LAYOUT_A         = 1
; Page loop: L and R always move one page, wrapping Masks&Rings <- Items ->
; Quest; the Items "Y:RINGS" prompt and Y shortcut are removed. Needs MENU_PAGE3.
!ENABLE_MENU_PAGE_LOOP              = 1
; Portal Rod cell: the Portal Rod gets Items row 4, column 1 ($0202 = $19);
; the Fishing Rod keeps its cell; no L/R rod switch in play. Ownership byte
; PortalRodOwned $7EF3A6 (Core/sram.asm). Needs MENU_PAGE3.
!ENABLE_PORTAL_ROD_CELL             = 1
; Pause-menu audit fixes (menu_audit_2026-09-28): A+Y no longer opens the old
; Ring Box (with page 3 the state $09 code is removed); the Journal clears
; $0207 when it opens, so L/R turn pages at once; the Quest crystals draw in
; D1-D7 order.
!ENABLE_MENU_AUDIT_FIXES            = 1
;
; Mask controls (decisions.org "Masks stay Y items; Y transforms, R toggles;
; Minish is automatic"): with a mask as the Y item, Y or R puts it on; in the
; form Y runs the form's ability and R changes back; when the Y item stops
; being the worn mask, Link changes back (Masks/mask_routines.asm).
!ENABLE_MASK_Y_TRANSFORM            = 1
; Minish portal (tile $64): stand still about 1 s to shrink, and again to grow
; (charge sparkle while charging); no R. Link must be unmasked to shrink
; (Masks/minish_form.asm, Masks/mask_routines.asm).
!ENABLE_MINISH_AUTO_PORTAL          = 1
; Let GBC Link ($5D = $17, Abyss form before the Pearl) charge the Minish portal
; (needs MINISH_AUTO_PORTAL). Without it the Origins Minish passage is unreachable.
!ENABLE_MINISH_GBC_PORTAL_FIX       = 1
;
; Truthful controls (M3; Codex menu review, accepted by scawful 2026-09-28):
; ring text without the penalties the code never applied; the HUD Y box keeps
; the worn form's mask until the form ends (Zora in water); R toggles the
; Stone Mask and a menu visit keeps it on; the Quest page treasure icon uses
; Oracle's dungeon treasures and the chest key gets its own icon; ring grants
; pick a real unfound ring and Vasu's appraisal clears the found ring.
; Needs MASK_Y_TRANSFORM and RING_SRAM_RELOCATE.
!ENABLE_TRUTHFUL_CONTROLS           = 1

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

if not(defined("ENABLE_MASK_R_BINDING"))
  !ENABLE_MASK_R_BINDING = 1
endif

if not(defined("ENABLE_GOLDSTAR_CELL"))
  !ENABLE_GOLDSTAR_CELL = 1
endif

if not(defined("ENABLE_JOURNAL_DEFERRED"))
  !ENABLE_JOURNAL_DEFERRED = 1
endif

if not(defined("ENABLE_EQUIPMENT_MENU"))
  !ENABLE_EQUIPMENT_MENU = 1
endif
