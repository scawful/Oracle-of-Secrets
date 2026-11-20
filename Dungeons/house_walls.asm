;
; Editor View
; 1 2         -> 1 3
; 3 4         -> 2 4
;
; These are the live-ROM timber window words (base 34e671c0). Slot 2 is the
; high palette half on underworld main sets, so the glass chars $0AC-$0AE stay
; on palette 3 and every other char stays on palette 2. Mullions are $091
; (north wall) and $093 (west wall); the older beam table had replaced those
; with flipped $090/$092 and had swapped the corner caps onto $09E/$0B3-$0B7.

; Top Left Corner Layer 1
#obj0B66:
org $00A6B8 ; @hook kind=data protected_size=$80 note="House wall corners"
  dw $0894, $0893, $0892, $0893
  dw $0891, $089E, $0898, $0899
  dw $0890, $0896, $08A6, $08A5
  dw $0891, $0897, $08A3, $0CAE

; Bottom Left Corner Layer 1
#obj0B86:
  dw $0892, $0893, $0892, $8894
  dw $0898, $0899, $889E, $8891
  dw $08A4, $88A6, $8896, $8890
  dw $8CAE, $88A3, $8897, $8891

; Top Right Corner Layer 1
#obj0BA6:
  dw $0890, $0896, $08A2, $4CAE
  dw $0891, $0897, $48A6, $48A5
  dw $0890, $489E, $4898, $4899
  dw $4894, $4893, $4892, $4893

; Bottom Right Corner Layer 1
#obj0BC6:
  dw $CCAE, $88A2, $8896, $8890
  dw $48A4, $C8A6, $8897, $8891
  dw $4898, $4899, $C89E, $8890
  dw $4892, $4893, $4892, $C894
assert pc() == $00A738, "House wall corner table size changed"

; Top Wall Layer 1
#obj02E8:
org $009E3A ; @hook kind=data protected_size=$20 note="House top walls"
  dw $0890, $0896, $08A2, $0CAC
  dw $0891, $0897, $08A3, $4CAC
  dw $8CAC, $88A2, $8896, $8890
  dw $CCAC, $88A3, $8897, $8891
assert pc() == $009E5A, "House top wall table size changed"

; Left Wall Layer 1

#obj02C8:
org $009E1A ; @hook kind=data protected_size=$20 note="House left walls"
  dw $0892, $0898, $08A4, $0CAD
  dw $0893, $0899, $08A5, $8CAD
  dw $4CAD, $48A4, $4898, $4892
  dw $CCAD, $48A5, $4899, $4893
assert pc() == $009E3A, "House left wall table size changed"
