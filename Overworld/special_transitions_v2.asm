; =========================================================
; Special transitions v2: table-driven overworld trigger and exit records
;
; Lyra tail full support, phases P2 and P3. Two independent flags, both 0
; by default (Util/macros.asm). With both at 0 this file is not included
; and the ROM is byte-identical to the build without it.
;
;   !ENABLE_SPECIAL_TRIGGER_TABLE_V2 (P2)
;     $0EDE57 (inside the trigger-tile routine at $0EDE49) jumps to
;     STV2_TriggerSearch, which searches STV2_TriggerRows instead of the
;     4 fixed rows at $0EDE29. The first 4 rows are those native rows, so
;     with no link rows the behavior is unchanged. A row can also require
;     a true area (the 16x16 screen inside a large area), which the native
;     table cannot express: $8A is the parent ID on large areas.
;
;   !ENABLE_SPECIAL_EXIT_TABLE_V2 (P3)
;     $02E4C4 (LoadOverworldFromUnderworld exit-ID dispatch) jumps to
;     STV2_ExitLookup. Exit IDs $0180-$018F with a v2 record load that
;     record; every other ID takes the native path unchanged. Each record
;     also writes its arrival facing into LoadSpecialOverworld .direction
;     ($02E801 + ID - $0180). Link rows (light world -> $A0+) need this flag.
;     LoadSpecialOverworld reads only .direction by slot; the ZSCO interrupt
;     at $02E931 takes graphics, palette and camera bounds from $8A for every
;     ID except $0180/$0181.
;
; Rollback: set the flag back to 0. Tables live in bank $2A (!STV2_BASE);
; moving them is one define. Build ledger:
; ~/.context/projects/oracle-of-secrets/scratchpad/handoffs/
;   lyra_tail_full_support_2026-10-29/LEDGER.md
;
; Layout at !STV2_BASE:
;   +$0000 directory (magic "STV2", version, feature bits, counts, pointers)
;   +$0020 trigger rows, 32 x 16 bytes
;   +$0220 return rows, 32 x 16 bytes (P4; empty)
;   +$0420 exit records, 16 x 32 bytes, slot = ID - $0180
;   +$0800 code
;
; Trigger row (16 bytes):
;   +0 dw char     top-left 8x8 char of the tile16 ($BD8000 & $01FF)
;   +2 dw parent   $8A (parent ID on large areas)
;   +4 dw area     true area (($0700 >> 1) | ($8A & $C0)), $FFFF = any
;   +6 dw dir      $67 for the transition: 8 up, 4 down, 2 left, 1 right
;   +8 dw exit_id  stored to $A0
;   +10 6 bytes reserved (0)
;
; Exit record (32 bytes), same fields as UnderworldExitData ($02DD8A):
;   +0 dw key (= exit ID, 0 = empty slot)  +2 dw vertical scroll
;   +4 dw horizontal scroll  +6 dw y  +8 dw x  +10 dw exit VRAM address
;   +12 dw camera trigger y  +14 dw camera trigger x
;   +16 dw door graphic  +18 dw door graphic location
;   +20 db overworld ID  +21 db scroll mod y  +22 db scroll mod x
;   +23 db facing ($2F: 0 up, 2 down, 4 left, 6 right)  +24 8 bytes reserved
; =========================================================

if not(defined("STV2_BASE"))
  if !ENABLE_KALYXO_BOAT == 1
    ; Private 4MiB candidate. Bank2A stays editor-owned.
    !STV2_BASE = $D18000
  else
    !STV2_BASE = $AA8000
  endif
endif

; Link rows. $B0/$B8 stay 0: Lyra_PrivatePilotFullFrameGate ($02A475) and
; Lyra_PrivatePilotCanEnter reject $8A >= $A2 until prepare admits them.
if not(defined("STV2_LINK_27_A0"))
  !STV2_LINK_27_A0 = 1
endif
if not(defined("STV2_LINK_37_B0"))
  !STV2_LINK_37_B0 = 0
endif
if not(defined("STV2_LINK_3F_B8"))
  !STV2_LINK_3F_B8 = 0
endif

; Placeholder trigger char and direction until the trigger tile16 is placed.
; $01EF is the char of the native trigger tile on $2A and $18.
if not(defined("STV2_LINK_CHAR"))
  !STV2_LINK_CHAR = $01EF
endif
if not(defined("STV2_LINK_DIR"))
  !STV2_LINK_DIR = $01
endif

!STV2_TRIGGERS = !STV2_BASE+$0020
!STV2_RETURNS = !STV2_BASE+$0220
!STV2_EXITS = !STV2_BASE+$0420
!STV2_CODE = !STV2_BASE+$0800

!STV2_FEATURES #= (!ENABLE_SPECIAL_TRIGGER_TABLE_V2&1)|((!ENABLE_SPECIAL_EXIT_TABLE_V2&1)<<1)

; ---------------------------------------------------------
; %stv2_exit(id, ow, y, x, large, facing)
; id: 4 hex digits, no "$" (0183). ow: overworld ID ($8A; parent ID for a
; large area). y/x: Link's landing position in world pixels. large: 1 for a
; large area. Scroll, camera and VRAM fields use the yaze automatic exit
; formula (src/zelda3/overworld/overworld_exit.h). Must precede any
; %stv2_trigger that names the same id.
; ---------------------------------------------------------
macro stv2_exit(id, ow, y, x, large, facing)
  assert $<id> >= $0180 && $<id> <= $018F, "STV2 exit <id>: ID must be $0180-$018F"
  assert $<id> != $0180 && $<id> != $0181 && $<id> != $0182 && $<id> != $0189, "STV2 exit <id>: native record exists"
  assert not(defined("STV2_EXIT_<id>")), "STV2 exit <id>: declared twice"
  assert <facing> == 0 || <facing> == 2 || <facing> == 4 || <facing> == 6, "STV2 exit <id>: facing must be 0, 2, 4 or 6"
  assert read1($02E801+$<id>-$0180) == $00, "STV2 exit <id>: .direction slot is not free"
  !STV2_EXIT_<id> = 1
  !stv2_mx #= (<ow>&$07)<<9
  !stv2_my #= ((<ow>&$38)>>3)<<9
  assert <large> >= 0 && <large> <= 3, "STV2 exit <id>: size must be small/large/wide/tall"
  !stv2_xsize #= 256
  !stv2_ysize #= 256
  if <large> == 1 || <large> == 2
    !stv2_xsize #= 768
  endif
  if <large> == 1 || <large> == 3
    !stv2_ysize #= 768
  endif
  !stv2_xs #= clamp(<x>-120, !stv2_mx, !stv2_mx+!stv2_xsize)
  !stv2_ys #= clamp(<y>-80, !stv2_my, !stv2_my+!stv2_ysize+32)
  !stv2_cx #= clamp(<x>+7, !stv2_mx+127, !stv2_mx+127+!stv2_xsize)
  !stv2_cy #= clamp(<y>+31, !stv2_my+111, !stv2_my+143+!stv2_ysize)
  !stv2_vram #= (((!stv2_ys-!stv2_my)&$FFF0)<<3)|(((!stv2_xs-!stv2_mx)&$FFF0)>>3)
  pushpc
  if !ENABLE_KALYXO_BOAT == 1
    assert (!STV2_EXITS>>16) == $D1, "Private ferry exit records must stay in bank $D1"
    org !STV2_EXITS+(($<id>-$0180)*32) ; @manifest-org-bank=$D1
  else
    assert (!STV2_EXITS>>16) == $AA, "Legacy STV2 record bank changed"
    org !STV2_EXITS+(($<id>-$0180)*32) ; @manifest-org-bank=$AA
  endif
    dw $<id>, !stv2_ys, !stv2_xs, <y>, <x>, !stv2_vram, !stv2_cy, !stv2_cx
    dw $0000, $0000
    db <ow>, $00, $00, <facing>
  assert (($02E801+$<id>-$0180)>>16) == $02, "STV2 direction leaves bank $02"
  org $02E801+$<id>-$0180 ; @manifest-org-bank=$02
    db <facing>
  pullpc
endmacro

; ---------------------------------------------------------
; %stv2_trigger(char, parent, area, dir, id)
; id: 4 hex digits, no "$". Needs a v2 exit record or a native special exit.
; ---------------------------------------------------------
macro stv2_trigger(char, parent, area, dir, id)
  assert <char> <= $01FF, "STV2 trigger <id>: char must fit $01FF"
  assert <dir> == 1 || <dir> == 2 || <dir> == 4 || <dir> == 8, "STV2 trigger <id>: dir must be 1, 2, 4 or 8 (0 never ends the shift loop)"
  if not(defined("STV2_EXIT_<id>"))
    assert $<id> == $0180 || $<id> == $0181 || $<id> == $0182 || $<id> == $0189, "STV2 trigger <id>: no exit record for this ID"
  endif
  dw <char>, <parent>, <area>, <dir>, $<id>, $0000, $0000, $0000
endmacro

pushpc

; ---------------------------------------------------------
; Exit records (P3). Placeholder landings on each tail map's west side.
; ---------------------------------------------------------
org !STV2_EXITS
  fillbyte $00 : fill 16*32

if !ENABLE_SPECIAL_EXIT_TABLE_V2 == 1
  if !STV2_LINK_27_A0 == 1
    %stv2_exit(0183, $A0, $0900, $0040, 0, $06)
  endif
  if !STV2_LINK_37_B0 == 1
    %stv2_exit(0184, $B0, $0D00, $0040, 0, $06)
  endif
  if !STV2_LINK_3F_B8 == 1
    %stv2_exit(0185, $B8, $0F00, $0040, 0, $06)
  endif
  if !ENABLE_KALYXO_BOAT == 1
    incsrc "../Data/overworld/kalyxo_boat_placements.asm"
  endif
endif

; ---------------------------------------------------------
; Directory
; ---------------------------------------------------------
org !STV2_BASE
STV2_Directory:
  db $53, $54, $56, $32         ; "STV2" (a string literal would go through the message char table)
  dw $0001                      ; version
  dw !STV2_FEATURES             ; bit 0 trigger hook, bit 1 exit hook
STV2_TriggerCount:
  dw (STV2_TriggerRowsEnd-STV2_TriggerRows)/16
STV2_ReturnCount:
  dw (STV2_ReturnRowsEnd-STV2_ReturnRows)/16
  dw 16                         ; exit slots
  dl STV2_TriggerRows
  dl STV2_ReturnRows
  dl STV2_ExitRecords
  padbyte $00 : pad !STV2_TRIGGERS

; ---------------------------------------------------------
; Trigger rows. Searched last to first, like the native table.
; Rows 0-3 mirror Overworld/overworld.asm (org $0EDE29 pools).
; ---------------------------------------------------------
STV2_TriggerRows:
  %stv2_trigger($01EF, $002A, $FFFF, 8, 0180)
  %stv2_trigger($01EF, $0018, $FFFF, 8, 0181)
  %stv2_trigger($00AD, $000F, $FFFF, 8, 0182)
  %stv2_trigger($00B9, $0081, $FFFF, 8, 0189)
if !ENABLE_SPECIAL_EXIT_TABLE_V2 == 1
  if !STV2_LINK_27_A0 == 1
    ; Goron Mines (parent $1E), screen $27 -> $A0
    %stv2_trigger(!STV2_LINK_CHAR, $001E, $0027, !STV2_LINK_DIR, 0183)
  endif
  if !STV2_LINK_37_B0 == 1
    ; Goron Mines (parent $36), screen $37 -> $B0
    %stv2_trigger(!STV2_LINK_CHAR, $0036, $0037, !STV2_LINK_DIR, 0184)
  endif
  if !STV2_LINK_3F_B8 == 1
    ; Goron Mines (parent $36), screen $3F -> $B8
    %stv2_trigger(!STV2_LINK_CHAR, $0036, $003F, !STV2_LINK_DIR, 0185)
  endif
endif
STV2_TriggerRowsEnd:
  assert pc() <= !STV2_RETURNS, "STV2 trigger rows exceed 32"
  padbyte $00 : pad !STV2_RETURNS

; read2() sees the base ROM, not Overworld/overworld.asm's pool writes, so
; rows 0-3 are compared with the assembled $0EDE29 pools after the build
; (LEDGER.md, verification step).

; ---------------------------------------------------------
; Return rows (P4). Empty.
; ---------------------------------------------------------
STV2_ReturnRows:
STV2_ReturnRowsEnd:
  padbyte $00 : pad !STV2_EXITS

org !STV2_EXITS
STV2_ExitRecords:

; ---------------------------------------------------------
; Code
; ---------------------------------------------------------
org !STV2_CODE

; Entry from $0EDE57 by JML. M=16 X=16, $00 = char under Link (& $01FF).
; Stack holds the JSL return of the trigger routine; DBR is the caller's.
; Found path matches native $0EDE6E-$0EDE95; exit is native $0EDE97.
STV2_TriggerSearch:
{
  LDA.l STV2_TriggerCount : ASL #4 : TAX
  .next
  TXA : BEQ .exit
  SEC : SBC.w #16 : TAX
  LDA.b $00 : CMP.l STV2_TriggerRows+0, X : BNE .next
  LDA.b $8A : CMP.l STV2_TriggerRows+2, X : BNE .next
  LDA.l STV2_TriggerRows+4, X : CMP.w #$FFFF : BEQ .found
  LDA.w $0700 : LSR A : EOR.l STV2_TriggerRows+4, X : AND.w #$003F : BNE .next
  LDA.b $8A : EOR.l STV2_TriggerRows+4, X : AND.w #$00C0 : BNE .next
  .found
  LDA.l STV2_TriggerRows+8, X : STA.b $A0
  SEP #$20
  LDA.l STV2_TriggerRows+6, X : STA.b $67 : STA.w $0410 : STA.w $0416
  LDX.w #$0004
  .shift
  DEX : LSR A : BCC .shift
  STX.w $0418 : STX.w $069C
  LDA.b #$17 : STA.b $11
  LDA.b #$0B : STA.b $10
  .exit
  SEP #$30
  RTL
}

; Entry from $02E4C4 by JML. M=16 X=8, DBR=$02, A = $A0 (exit ID).
; IDs $0180-$018F with a v2 record replay native $02E4DD-$02E589 from the
; record and continue at $02E58A (PLB) with M=16 X=8. Others continue at
; native $02E4C9 (A < $0180) or $02E4D4 (table search, A = $A0).
STV2_ExitLookup:
{
  CMP.w #$0180 : BCS .special
  JML $02E4C9
  .miss
  SEP #$10
  LDA.b $A0
  .native_table
  JML $02E4D4
  .special
  CMP.w #$0190 : BCS .native_table
  REP #$10
  SEC : SBC.w #$0180 : ASL #5 : TAX
  LDA.l STV2_ExitRecords+0, X : CMP.b $A0 : BNE .miss
  LDA.l STV2_ExitRecords+2, X
  STA.b $E6 : STA.b $E8 : STA.w $0122 : STA.w $0124
  LDA.l STV2_ExitRecords+4, X
  STA.b $E0 : STA.b $E2 : STA.w $011E : STA.w $0120
  LDA.l STV2_ExitRecords+6, X : STA.b $20
  LDA.l STV2_ExitRecords+8, X : STA.b $22
  LDA.l STV2_ExitRecords+10, X : STA.b $84
  SEC : SBC.w #$0400 : AND.w #$0F80 : ASL A : XBA : STA.b $88
  LDA.b $84 : SEC : SBC.w #$0010 : AND.w #$003E : LSR A : STA.b $86
  LDA.l STV2_ExitRecords+12, X : STA.w $0618 : DEC A : DEC A : STA.w $061A
  LDA.l STV2_ExitRecords+14, X : STA.w $061C : DEC A : DEC A : STA.w $061E
  LDA.w #$0002 : STA.b $2F
  LDA.l STV2_ExitRecords+16, X : STA.w $0696
  LDA.l STV2_ExitRecords+18, X : STA.w $0698
  SEP #$20
  LDA.l STV2_ExitRecords+20, X : STA.b $8A : STA.w $040A
  STZ.b $8B : STZ.w $040B
  LDA.l STV2_ExitRecords+21, X : STA.w $0624 : STZ.w $0625
  ASL A : BCC .positive_camera_y
  DEC.w $0625
  .positive_camera_y
  LDA.l STV2_ExitRecords+22, X : STA.w $0628 : STZ.w $0629
  ASL A : BCC .positive_camera_x
  DEC.w $0629
  .positive_camera_x
  REP #$20
  LDA.w #$0000 : SEC : SBC.w $0624 : STA.w $0626
  LDA.w #$0000 : SEC : SBC.w $0628 : STA.w $062A
  SEP #$10
  JML $02E58A
}

assert pc() <= !STV2_BASE+$8000, "STV2 code overflows its bank"

; ---------------------------------------------------------
; Hooks
; ---------------------------------------------------------
if !ENABLE_SPECIAL_TRIGGER_TABLE_V2 == 1
  ; Trigger routine: LDX.w #$0008 : LDA.b $00 (search setup). The native
  ; loop at $0EDE5C-$0EDE6D is entered only by falling through here.
  assert read4($0EDE57) == $A50008A2, "trigger search setup moved"
  assert read1($0EDE5B) == $00, "trigger search setup moved"
  assert read3($0EDE97) == $6B30E2, "trigger routine exit moved"
  org $0EDE57 : JML STV2_TriggerSearch ; @hook module=Overworld name=STV2_TriggerSearch kind=jml target=STV2_TriggerSearch expected_m=16 expected_x=16 expected_exit_m=8 expected_exit_x=8 protected_size=5
  NOP
  assert pc() == $0EDE5C
endif

if !ENABLE_SPECIAL_EXIT_TABLE_V2 == 1
  ; LoadOverworldFromUnderworld: CMP.w #$0180 : BCS .custom_exit
  assert read4($02E4C4) == $B00180C9, "exit ID dispatch moved"
  assert read1($02E4C8) == $0B, "exit ID dispatch moved"
  assert read2($02E4D4) == $9EA2, "exit table search moved"
  assert read1($02E58A) == $AB, "exit field sequence end moved"
  org $02E4C4 : JML STV2_ExitLookup ; @hook module=Overworld name=STV2_ExitLookup kind=jml target=STV2_ExitLookup expected_m=16 expected_x=8 expected_exit_m=16 expected_exit_x=8 protected_size=5
  NOP
  assert pc() == $02E4C9
endif

pullpc
