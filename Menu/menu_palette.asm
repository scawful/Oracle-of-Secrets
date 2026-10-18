; Menu Palette

function hexto555(h) = ((((h&$FF)/8)<<10)|(((h>>8&$FF)/8)<<5)|(((h>>16&$FF)/8)<<0))

pushpc
; HUD palette data lives in bank $1B; bank $1D here contains sprite code.
org $1BD662 : dw hexto555($814f16), hexto555($552903)
org $1BD66A : dw hexto555($d51d00), hexto555($f9f9f9)
org $1BD672 : dw hexto555($d0a050), hexto555($f9f9f9)
org $1BD67A : dw hexto555($5987e0), hexto555($f9f9f9)
org $1BD682 : dw hexto555($7b7b83), hexto555($bbbbbb)
org $1BD68A : dw hexto555($a58100), hexto555($dfb93f)
pullpc

Menu_Palette:
  dw hexto555($814f16)
  dw hexto555($552903)
  dw hexto555($000000)
  dw hexto555($000000) ; transparent
  dw hexto555($d51d00)
  dw hexto555($f9f9f9)
  dw hexto555($000000)
  dw hexto555($000000) ; transparent
  dw hexto555($d0a050)
  dw hexto555($f9f9f9)
  dw hexto555($000000)
  dw hexto555($000000) ; transparent
  dw hexto555($5987e0)
  dw hexto555($f9f9f9)
  dw hexto555($000000)
  dw hexto555($000000) ; transparent
  dw hexto555($7b7b83)
  dw hexto555($bbbbbb)
  dw hexto555($000000)
  dw hexto555($000000) ; transparent
  ; Existing gold artwork keeps its original palette5 colors.
  dw hexto555($a58100)
  dw hexto555($dfb93f)
  dw hexto555($000000)
  dw hexto555($000000) ; transparent
  ; Frame palette6 is preserved exactly (brown outline, dark blue fill).
  dw hexto555($814f16)
  dw hexto555($013e6e)
  dw hexto555($000000)
  dw hexto555($000000) ; transparent
  dw hexto555($15cd34)
  dw hexto555($f9f9f9)
  dw hexto555($000000)