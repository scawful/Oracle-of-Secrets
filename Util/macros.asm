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

; Prints a message and the current PC value during assembly, but only if !DEBUG is enabled.
; Usage: %print_debug("My message")
macro print_debug(message)
  if !DEBUG == 1
    print "<message> ", pc
  endif
endmacro

; Prints a header for a major section.
; Usage: %log_section("Sprites", !LOG_SPRITES)
macro log_section(name, flag)
    if !DEBUG == 1 && <flag> == 1
        print ""
        print "---  <name>  ---"
        print ""
    endif
endmacro

; Prints a standardized log message for the start of a named block.
; Usage: %log_start("MySprite", !LOG_SPRITES)
macro log_start(name, flag)
    if !DEBUG == 1 && <flag> == 1
        print "$", pc, " > <name>"
    endif
endmacro

; Prints a standardized log message for the end of a named block.
; Usage: %log_end("MySprite", !LOG_SPRITES)
macro log_end(name, flag)
    if !DEBUG == 1 && <flag> == 1
        print "$", pc, " < <name>"
    endif
endmacro
