; $DB8BF (0x2C entries, 2 bytes each) - valid map8 (CHR) values for entrances (left side)
; $DB917 (0x2C entries, 2 bytes each) - valid map8 (CHR) values for entrances (right side)

; $DB8BF-$DB916 - chr types indicating door entrances
org $1BB8BF
  dw $00FE, $00C5, $00FE, $0114, $0115, $0175, $0156, $00F5
  dw $00E2, $01EF, $0119, $00FE, $0172, $0177, $013F, $0172
  dw $0112, $0161, $0172, $014C, $0156, $01EF, $00FE, $00FE
  dw $00FE, $010B, $0173, $0143, $0149, $0175, $0103, $0100
  dw $01C6 ; Waterfall tile
  dw $015E
  dw $0167
  dw $0128, $0131, $0112, $016D, $0163
  dw $0173, $00FE, $0113, $00A7

; $DB917 - $DB96E
  dw $014A, $00C4, $014F, $0115, $0114, $0174, $0155, $00F5
  dw $00EE, $01EB, $0118, $0146, $0171, $0155, $0137, $0174
  dw $0173, $0121, $0164, $0155, $0157, $0128, $0114, $0123
  dw $0113, $0109, $0118, $0161, $0149, $0171, $0174, $0101
  dw $01C6 ; Waterfall tile
  dw $0131
  dw $0051
  dw $014E, $0131, $0121, $017A, $0163
  dw $0172, $01BD, $0152, $00A7