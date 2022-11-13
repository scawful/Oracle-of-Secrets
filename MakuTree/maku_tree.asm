
org $0EDE29
; $75E29-$75E48 DATA
{
    ; corresponding warp types that lead to special overworld areas
    dw $0105, $01EF, $00AD, $00B9
    
    ; Lost woods, Hyrule Castle Bridge, Entrance to Zora falls, and in Zora Falls...
    dw $0000, $002A, $000F, $0081
    
    ; Direction Link will face when he enters the special area
    dw $0008, $0008, $0008, $0008
    
    ; Exit value for the special area. In Hyrule Magic these are those White markers.
    dw $0180, $0181, $0182, $0189
}