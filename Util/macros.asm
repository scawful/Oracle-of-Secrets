; Defines common macros for the project.

; Set to 1 to enable debug printing, 0 to disable.
!DEBUG = 1

; Prints a message and the current PC value during assembly, but only if !DEBUG is enabled.
; Usage: %print_debug("My message")
macro print_debug(message)
  if !DEBUG == 1
    print "<message> ", pc
  endif
endmacro
