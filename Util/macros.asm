; Defines common macros for the project.

; Set to 1 to enable global debug printing, 0 to disable.
!DEBUG = 1

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
