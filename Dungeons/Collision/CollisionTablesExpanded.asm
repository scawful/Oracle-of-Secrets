; -----------------------------------------------------------------------------------
; INDOOR EXPANDED COLLISION TABLES
;
; By Jeimuzu & Zarby
; -----------------------------------------------------------------------------------

org $0E942A
    JSL Dungeon_LoadCustomTileAttr
    RTL

org $338000

; *$7142A-$71458 LONG
Dungeon_LoadCustomTileAttr:
{
    ; Loads tile attributes that are specific to a tileset type.
    ; The group loaded is dependent on the value of $0AA2.
    PHB : PHK : PLB
    
    REP #$30
    
    LDA $0AA2 : AND.w #$00FF : ASL A : TAX
    
    LDA group_offsets, X : TAY
    
    LDX.w #$0000

.load_loop

    LDA.w group00, Y : STA.l $7EFF40, X		;	1st block
    LDA.w group00+$40, Y : STA.l $7EFF80, X	;	2nd block
    
    INY #2
    
    INX #2 : CPX.w #$0040 : BNE .load_loop
    
    SEP #$30
    
    PLB
    
    RTL
}


; 00 = No collision
; 01 = Standard collision (deflects projectiles)
; 02 = Standard collision (ignores projectiles)


; -----------------------------------------------------------------------------------
; BLOCKSET COLLISION TABLES
; Table's 05 & 06
; -----------------------------------------------------------------------------------

; Blocksets 00 > 20 (blocksets 21/22/23 in HM = invalid?)
; (0x71000 > 0x71029) [LENGTH: 2A]

; Group 00 = 00 00		Curtains/Vines		Blockset 0; 1; 2; 9
; Group 01 = 80 00		Houses				Blockset 3; 4; 17
; Group 02 = 00 01		Converors			Blockset 5; 6; 7; 10; 15; 16; 18; 20
; Group 03 = 80 01		Deep Water			Blockset 8
; Group 04 = 00 02		Ice Floor			Blockset 11
; Group 05 = 80 02		Slime/Conveyor		Blockset 12
; Group 06 = 00 03		Trinexx Data		Blockset 13
; Group 07 = 80 03		Ganon's Tower		Blockset 14; 19


; -----------------------------------------------------------------------------------
; Blockset Group Offsets (SNES: $E9000-$E9029) (PC: $71000-$71029)
; -----------------------------------------------------------------------------------
group_offsets:
      
;          00            01            02            03             04            05            06           07
    dw group00-offs, group01-offs, group02-offs, group03-offs, group04-offs, group05-offs, group06-offs, group07-offs
;          08            09            10            11             12            13            14           15
    dw group08-offs, group09-offs, group0A-offs, group0B-offs, group0C-offs, group0D-offs, group0E-offs, group0F-offs
;          16            17            18            19             20            21            22           23
    dw group10-offs, group11-offs, group12-offs, group13-offs, group14-offs, group15-offs, group16-offs, group17-offs


offs:
group00:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $6E, $6F, $01, $6C, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $00, $00, $00, $00, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $6E, $6F, $01, $6C, $02, $02, $02, $02, $01, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $01, $00

	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $01, $01, $01, $01 
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles


group01:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $6E, $6F, $01, $6C, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $00, $00, $00, $00, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $6E, $6F, $01, $6C, $02, $02, $02, $02, $01, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $01, $00

	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $01, $01, $01, $01 
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles


group02:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $6E, $6F, $01, $6C, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $00, $00, $00, $00, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $6E, $6F, $01, $6C, $02, $02, $02, $02, $01, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $01, $00

	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $01, $01, $01, $01 
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles


group03:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles
	
	
 ; Goron Mines
group04:
{
  ;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
  ;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
  ; -----------------------------------------------------------------------------------
  db $00, $00, $02, $02, $B6, $B6, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
  db $00, $00, $02, $02, $00, $00, $00, $00, $B0, $B0, $02, $01, $01, $01, $01, $01
  db $00, $00, $00, $00, $00, $00, $00, $00, $B0, $B0, $02, $02, $02, $02, $02, $02
  db $00, $00, $22, $00, $B1, $B1, $B1, $B1, $B1, $B1, $02, $02, $02, $02, $02, $02

  db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles
}
	
group05:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $02, $00

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $00, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles


group06:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $02, $00

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $00, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles


group07:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $02, $00

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $00, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles


group08:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $09, $09, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $00, $00

	db $01, $01, $01, $00, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $08, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $08, $08, $02, $01, $01, $09, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles


group09:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $6E, $6F, $01, $6C, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $00, $00, $00, $00, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $6E, $6F, $01, $6C, $02, $02, $02, $02, $01, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $01, $00

	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $01, $01, $01, $01 
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles


group0A:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $02, $00

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $00, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles


; Glacia Estate
group0B:
{
  ;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
  ;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
  ; -----------------------------------------------------------------------------------
  db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
  db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
  db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
  db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $00, $00

  db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $02, $02, $00, $0F, $00, $00, $00, $02, $02, $02, $02, $02, $02
  db $02, $02, $02, $01, $02, $0E, $08, $08, $08, $08, $0E, $0E, $0E, $0E, $00, $00 ; Animated Tiles
}

group0C:
{
  ;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
  ;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
  ; -----------------------------------------------------------------------------------
    db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
    db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
    db $01, $01, $01, $01, $01, $01, $02, $02, $01, $02, $02, $02, $02, $02, $02, $02
    db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $00, $00

    db $01, $01, $01, $01, $02, $02, $02, $0D, $0D, $02, $02, $02, $02, $02, $02, $02
    db $01, $01, $01, $01, $02, $02, $02, $0D, $0D, $02, $02, $02, $02, $02, $02, $02
    db $02, $02, $02, $02, $02, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
    db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles
}

group0D:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $B2, $B4, $B1, $BB, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $B3, $B5, $B0, $B6, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $00, $00

	db $B1, $B2, $B3, $B4, $B5, $B1, $B0, $02, $BE, $02, $02, $02, $02, $02, $B7, $B8
	db $B0, $B2, $B3, $B4, $B5, $02, $B0, $02, $00, $02, $B1, $BE, $00, $BD, $B9, $BA
	db $02, $02, $B1, $B0, $02, $00, $00, $00, $BD, $BC, $02, $02, $02, $02, $02, $02
	db $00, $00, $00, $00, $00, $0E, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 ; Animated Tiles


group0E:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $00, $00

	db $01, $01, $01, $01, $01, $01, $01, $01, $00, $00, $00, $00, $00, $00, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $01, $00, $00, $00, $00, $00, $00, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $00, $00, $01, $01, $01, $01
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $0E, $0E, $0E, $0E, $68, $69 ; Animated Tiles


group0F:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $02, $00

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $00, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles


group10:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $02, $00

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $00, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles


group11:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles


group12:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $02, $00

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $00, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles


group13:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $00, $00

	db $01, $01, $01, $01, $01, $01, $01, $01, $00, $00, $00, $00, $00, $00, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $01, $00, $00, $00, $00, $00, $00, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $00, $00, $01, $01, $01, $01
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $0E, $0E, $0E, $0E, $68, $69 ; Animated Tiles


group14:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02
	db $00, $00, $22, $00, $00, $00, $00, $00, $00, $00, $02, $02, $00, $00, $02, $00

	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $00, $00, $00, $00, $00, $00, $02, $02, $02, $02, $02, $02
	db $6B, $6A, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $68, $69 ; Animated Tiles


group15:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $6E, $6F, $01, $6C, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $00, $00, $00, $00, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $6E, $6F, $01, $6C, $02, $02, $02, $02, $01, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $01, $00

	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $01, $01, $01, $01 
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles


group16:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $6E, $6F, $01, $6C, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $00, $00, $00, $00, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $6E, $6F, $01, $6C, $02, $02, $02, $02, $01, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $01, $00

	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $01, $01, $01, $01 
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles


group17:

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $02, $02, $02, $02, $02, $02, $6E, $6F, $01, $6C, $02, $01, $01, $01, $01, $01
	db $02, $02, $02, $02, $02, $02, $00, $00, $00, $00, $02, $01, $01, $01, $01, $01
	db $01, $01, $01, $01, $01, $01, $6E, $6F, $01, $6C, $02, $02, $02, $02, $01, $02
	db $00, $00, $22, $00, $00, $00, $02, $02, $02, $02, $02, $02, $00, $00, $01, $00

	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $01, $01, $01, $01, $01, $01, $01, $02, $02, $02, $02, $02, $02, $02, $02, $02
	db $02, $02, $02, $02, $18, $00, $00, $00, $00, $00, $02, $02, $01, $01, $01, $01 
	db $02, $02, $02, $01, $02, $02, $08, $08, $08, $08, $09, $09, $09, $09, $09, $09 ; Animated Tiles

pushpc

; -----------------------------------------------------------------------------------
; Animated Object Graphics
; -----------------------------------------------------------------------------------

; (PC: $01011E) (SNES: $02811E)

; 5D = Deep Water
; 5E = Lava
; 5F = Slime

org $02811E

;		00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
;		 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16
; -----------------------------------------------------------------------------------
	db $5D, $5D, $5D, $5D, $5D, $5D, $5D, $5F, $5D, $5F, $5F, $5E, $5F, $5E, $5E, $5D
	db $5D, $5E, $5D, $5D, $5D, $5D, $5D, $5D
