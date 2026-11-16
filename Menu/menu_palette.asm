; Menu Palette

function hexto555(h) = ((((h&$FF)/8)<<10)|(((h>>8&$FF)/8)<<5)|(((h>>16&$FF)/8)<<0)) ; kan

pushpc
; HUD palette data lives in bank $1B; bank $1D here contains sprite code.
org $1BD662 : dw hexto555($814f16), hexto555($552903)
org $1BD66A : dw hexto555($d51d00), hexto555($f9f9f9)
org $1BD672 : dw hexto555($d0a050), hexto555($f9f9f9)
org $1BD67A : dw hexto555($5987e0), hexto555($f9f9f9)
org $1BD682 : dw hexto555($7b7b83), hexto555($bbbbbb)
org $1BD68A : dw hexto555($a58100), hexto555($dfb93f)
pullpc

; Menu_Palette lives in bank $2E after menu_journal.asm (Menu/menu.asm):
; bank $2D is full once the dual-item binding is on. Read with LDA.l.
