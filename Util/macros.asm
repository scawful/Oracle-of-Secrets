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
; Set to 1 to enable a feature, 0 to disable (isolation testing).
; Override these via Config/feature_flags.asm (generate with scripts/set_feature_flags.py).
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
!ENABLE_JUMPTABLELOCAL_GUARD         = 1

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
