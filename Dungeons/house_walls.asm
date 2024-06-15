
;
; Editor View
; 1 2         -> 1 3 
; 3 4         -> 2 4

; Top Left Corner Layer 1
#obj0B66:
org $00A6B8
  dw $C89E, $489E, $0894, $0892
  dw $889E, $089E, $08B6, $0899
  dw $4893, $08B5, $08A6, $08B7
  dw $0890, $0897, $08B3, $0CAE

; Bottom Left Corner Layer 1
#obj0B86:
  dw $0892, $8894, $C89E, $489E
  dw $0899, $88B6, $889E, $089E
  dw $88B7, $88A6, $88B5, $C893
  dw $8CAE, $88B3, $8897, $8890

; Top Right Corner Layer 1
#obj0BA6:
  dw $0890, $0896, $48B3, $4CAE
  dw $0893, $48B5, $48A6, $48B7
  dw $C89E, $489E, $48B6, $4899
  dw $889E, $089E, $4894, $4892

; Bottom Right Corner Layer 1 
#obj0BC6:
  dw $CCAE, $C8B3, $8896, $8890
  dw $C8B7, $C8A6, $C8B5, $8893
  dw $4898, $C8B6, $C89E, $489E
  dw $4892, $C894, $889E, $089E

; Top Wall Layer 1 
#obj02E8:
org $009E3A
  dw $0890, $0896, $08A2, $0CAC
  dw $4890, $0897, $08A3, $4CAC

#obj02F8:
  dw $8CAC, $88A2, $8896, $C890
  dw $CCAC, $88A3, $8897, $8890

; Left Wall Layer 1 

#obj02C8:
org $009E1A
  dw $0892, $0898, $08A4, $0CAD
  dw $0892, $0899, $08A5, $8CAD

#obj02D8:
  dw $4CAD, $48A4, $4898, $4892
  dw $CCAD, $48A5, $4899, $4892