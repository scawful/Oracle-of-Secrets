; Sky Tower void falls use the damage-pit rule (scawful 2026-11-11 "yes pit
; damage": one heart, back to the room entry, no floor drop; same rule as
; Glacia AF/BF and D6 $97/$B8). Rooms listed in RoomsWithPitDamage never use
; their holewarp byte.
;
; RoomsWithPitDamage ($00:990C, 57 words) is scanned with a fixed LDX #$0070
; at $07:94A5. After D6 $97/$B8 (Core/patches.asm) three $0123 filler slots
; remain and Glacia AF/BF take two, so nine sky rooms cannot fit. The scan is
; retargeted to an extended copy of the table (same lookup, one shared table
; with room to grow). The 52 base rooms are asserted against the base ROM so
; a base-table edit cannot drift from this copy.

!PIT_DAMAGE_EXT_WORDS = (63+!ENABLE_D5_AF_PIT_RESET+!ENABLE_D5_BF_PIT_RESET)
!PIT_DAMAGE_EXT_BYTES = (!PIT_DAMAGE_EXT_WORDS*2)

pushpc
if !ENABLE_D5_AF_PIT_RESET == 1 && !ENABLE_D5_BF_PIT_RESET == 1
  org $33F860 ; @hook module=Dungeons kind=data protected_size=130 name=RoomsWithPitDamageExt
  assert read4($33F860) == 0 && read4($33F8DA) == 0 && read4($33F8DE) == 0, "Extended pit-damage table slot in bank $33 is not free"
elseif !ENABLE_D5_AF_PIT_RESET == 1 || !ENABLE_D5_BF_PIT_RESET == 1
  org $33F860 ; @hook module=Dungeons kind=data protected_size=128 name=RoomsWithPitDamageExt
  assert read4($33F860) == 0 && read4($33F8DA) == 0 && read2($33F8DE) == 0, "Extended pit-damage table slot in bank $33 is not free"
else
  org $33F860 ; @hook module=Dungeons kind=data protected_size=126 name=RoomsWithPitDamageExt
  assert read4($33F860) == 0 && read4($33F8DA) == 0, "Extended pit-damage table slot in bank $33 is not free"
endif
RoomsWithPitDamage_Ext:
  ; base ROM table (oos168 $00:990C..$00:9972), order preserved
  dw $000B, $000E, $0014, $001A, $001C, $001E, $003C, $003F
  dw $0045, $0047, $0048, $0049, $0056, $0059, $005F, $0066
  dw $0067, $0069, $006E, $0071, $0073, $0074, $0075, $0076
  dw $0077, $007B, $007D, $007E, $007F, $0083, $0084, $0085
  dw $0086, $0087, $0089, $008C, $008E, $008F, $00AC, $00B1
  dw $00B4, $00B5, $00B9, $00C4, $00C6, $00C7, $00CB, $00D6
  dw $00D7, $00D8, $00DE, $010B
  ; D6 (Core/patches.asm $00997A/$00997C)
  dw $0097, $00B8
  ; D5 Glacia (Core/patches.asm $009976/$009978)
if !ENABLE_D5_AF_PIT_RESET == 1
  dw $00AF
endif
if !ENABLE_D5_BF_PIT_RESET == 1
  dw $00BF
endif
  ; Sky Tower (SkyRoom_List order)
  dw $0090, $0091, $0092, $0093, $0094, $0095, $00A0, $00B0, $00A7
RoomsWithPitDamage_Ext_end:
assert pc() <= $340000, "Extended pit-damage table overflows bank $33"
assert pc() == $33F860+!PIT_DAMAGE_EXT_BYTES, "Extended pit-damage table size mismatch; update protected_size and the LDX"
assert RoomsWithPitDamage_Ext_end-RoomsWithPitDamage_Ext == !PIT_DAMAGE_EXT_BYTES, "Extended pit-damage table extent mismatch"

; base ROM guard: each copied entry must still match $00:990C (read functions see the input ROM)
assert read2($00990C) == $000B, "Base RoomsWithPitDamage entry 0 changed; update the extended copy"
assert read2($00990E) == $000E, "Base RoomsWithPitDamage entry 1 changed; update the extended copy"
assert read2($009910) == $0014, "Base RoomsWithPitDamage entry 2 changed; update the extended copy"
assert read2($009912) == $001A, "Base RoomsWithPitDamage entry 3 changed; update the extended copy"
assert read2($009914) == $001C, "Base RoomsWithPitDamage entry 4 changed; update the extended copy"
assert read2($009916) == $001E, "Base RoomsWithPitDamage entry 5 changed; update the extended copy"
assert read2($009918) == $003C, "Base RoomsWithPitDamage entry 6 changed; update the extended copy"
assert read2($00991A) == $003F, "Base RoomsWithPitDamage entry 7 changed; update the extended copy"
assert read2($00991C) == $0045, "Base RoomsWithPitDamage entry 8 changed; update the extended copy"
assert read2($00991E) == $0047, "Base RoomsWithPitDamage entry 9 changed; update the extended copy"
assert read2($009920) == $0048, "Base RoomsWithPitDamage entry 10 changed; update the extended copy"
assert read2($009922) == $0049, "Base RoomsWithPitDamage entry 11 changed; update the extended copy"
assert read2($009924) == $0056, "Base RoomsWithPitDamage entry 12 changed; update the extended copy"
assert read2($009926) == $0059, "Base RoomsWithPitDamage entry 13 changed; update the extended copy"
assert read2($009928) == $005F, "Base RoomsWithPitDamage entry 14 changed; update the extended copy"
assert read2($00992A) == $0066, "Base RoomsWithPitDamage entry 15 changed; update the extended copy"
assert read2($00992C) == $0067, "Base RoomsWithPitDamage entry 16 changed; update the extended copy"
assert read2($00992E) == $0069, "Base RoomsWithPitDamage entry 17 changed; update the extended copy"
assert read2($009930) == $006E, "Base RoomsWithPitDamage entry 18 changed; update the extended copy"
assert read2($009932) == $0071, "Base RoomsWithPitDamage entry 19 changed; update the extended copy"
assert read2($009934) == $0073, "Base RoomsWithPitDamage entry 20 changed; update the extended copy"
assert read2($009936) == $0074, "Base RoomsWithPitDamage entry 21 changed; update the extended copy"
assert read2($009938) == $0075, "Base RoomsWithPitDamage entry 22 changed; update the extended copy"
assert read2($00993A) == $0076, "Base RoomsWithPitDamage entry 23 changed; update the extended copy"
assert read2($00993C) == $0077, "Base RoomsWithPitDamage entry 24 changed; update the extended copy"
assert read2($00993E) == $007B, "Base RoomsWithPitDamage entry 25 changed; update the extended copy"
assert read2($009940) == $007D, "Base RoomsWithPitDamage entry 26 changed; update the extended copy"
assert read2($009942) == $007E, "Base RoomsWithPitDamage entry 27 changed; update the extended copy"
assert read2($009944) == $007F, "Base RoomsWithPitDamage entry 28 changed; update the extended copy"
assert read2($009946) == $0083, "Base RoomsWithPitDamage entry 29 changed; update the extended copy"
assert read2($009948) == $0084, "Base RoomsWithPitDamage entry 30 changed; update the extended copy"
assert read2($00994A) == $0085, "Base RoomsWithPitDamage entry 31 changed; update the extended copy"
assert read2($00994C) == $0086, "Base RoomsWithPitDamage entry 32 changed; update the extended copy"
assert read2($00994E) == $0087, "Base RoomsWithPitDamage entry 33 changed; update the extended copy"
assert read2($009950) == $0089, "Base RoomsWithPitDamage entry 34 changed; update the extended copy"
assert read2($009952) == $008C, "Base RoomsWithPitDamage entry 35 changed; update the extended copy"
assert read2($009954) == $008E, "Base RoomsWithPitDamage entry 36 changed; update the extended copy"
assert read2($009956) == $008F, "Base RoomsWithPitDamage entry 37 changed; update the extended copy"
assert read2($009958) == $00AC, "Base RoomsWithPitDamage entry 38 changed; update the extended copy"
assert read2($00995A) == $00B1, "Base RoomsWithPitDamage entry 39 changed; update the extended copy"
assert read2($00995C) == $00B4, "Base RoomsWithPitDamage entry 40 changed; update the extended copy"
assert read2($00995E) == $00B5, "Base RoomsWithPitDamage entry 41 changed; update the extended copy"
assert read2($009960) == $00B9, "Base RoomsWithPitDamage entry 42 changed; update the extended copy"
assert read2($009962) == $00C4, "Base RoomsWithPitDamage entry 43 changed; update the extended copy"
assert read2($009964) == $00C6, "Base RoomsWithPitDamage entry 44 changed; update the extended copy"
assert read2($009966) == $00C7, "Base RoomsWithPitDamage entry 45 changed; update the extended copy"
assert read2($009968) == $00CB, "Base RoomsWithPitDamage entry 46 changed; update the extended copy"
assert read2($00996A) == $00D6, "Base RoomsWithPitDamage entry 47 changed; update the extended copy"
assert read2($00996C) == $00D7, "Base RoomsWithPitDamage entry 48 changed; update the extended copy"
assert read2($00996E) == $00D8, "Base RoomsWithPitDamage entry 49 changed; update the extended copy"
assert read2($009970) == $00DE, "Base RoomsWithPitDamage entry 50 changed; update the extended copy"
assert read2($009972) == $010B, "Base RoomsWithPitDamage entry 51 changed; update the extended copy"

assert read2($0794A6) == $0070, "Unexpected RoomsWithPitDamage scan length"
org $0794A5 : LDX.w #(RoomsWithPitDamage_Ext_end-RoomsWithPitDamage_Ext)-2 ; @hook module=Dungeons kind=data protected_size=3 name=PitDamageScanLength
assert read4($0794AA) == $00990CDF, "Unexpected RoomsWithPitDamage scan compare"
org $0794AA : CMP.l RoomsWithPitDamage_Ext,X ; @hook module=Dungeons kind=data protected_size=4 name=PitDamageScanTable
pullpc
