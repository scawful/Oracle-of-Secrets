; $DB8BF (0x2C entries, 2 bytes each) - valid map8 (CHR) values for entrances (left side)
; $DB917 (0x2C entries, 2 bytes each) - valid map8 (CHR) values for entrances (right side)

; $DB8BF-$DB916 - chr types indicating door entrances
org $1BB8BF
ValidDoorTypes_low:
 dw $00FE, $00C5, $00FE, $0114 ; ???, House Door, ???, ???
 dw $0115, $0175, $0156, $00F5
 dw $00E2, $01EF, $0119, $00FE ; ???, ???, ???, Desert Door
 dw $0172, $0177, $013F, $0172
 dw $0112, $0161, $0172, $014C ; ???, ???, Dam Door, ???
 dw $0156, $01EF, $00FE, $00FE
 dw $00FE, $010B, $0173, $0143 ; ???, ???, ???, Tower of Hera
 dw $0149, $0175, $0103, $0100
 dw $01C6, $015E, $0167, $0128
 dw $0131, $0112, $016D, $0163
 dw $0173, $00FE, $0113, $0177

;---------------------------------------------------------------------------------------------------

ValidDoorTypes_high:
 dw $014A, $00C4, $014F, $0115 ; ???, House Door, ???, ???
 dw $0114, $0174, $0155, $00F5
 dw $00EE, $01EB, $0118, $0146 ; ???, ???, ???, Desert Door
 dw $0171, $0155, $0137, $0174
 dw $0173, $0121, $0164, $0155 ; ???, ???, Dam Door, ???
 dw $0157, $0128, $0114, $0123
 dw $0113, $0109, $0118, $0161
 dw $0149, $0117, $0174, $0101
 dw $01C6, $0131, $0051, $014E
 dw $0131, $0112, $017A, $0163
 dw $0172, $01BD, $0152, $0167