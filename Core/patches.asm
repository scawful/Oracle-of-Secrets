; This file contains all direct patches to the original ROM.
; It is included from Oracle_main.asm.

; Keep the Shrine pendant rewards reproducible from an unedited base ROM.
; Guard both the chest record identity and the accepted old/already-fixed item
; values so a changed chest table fails closed instead of patching a wrong byte.
assert read2($01E9E6) == $8073, "Room $73 big-chest record moved"
assert read1($01E9E8) == $39 || read1($01E9E8) == $3A, "Unexpected room $73 big-chest item"
org $01E9E8 : db $39 ; Pendant of Power: receipt handler sets $7EF374 bit $02

assert read2($01E9F5) == $807A, "Room $7A big-chest record moved"
assert read1($01E9F7) == $38 || read1($01E9F7) == $39, "Unexpected room $7A big-chest item"
org $01E9F7 : db $38 ; Pendant of Wisdom: receipt handler sets $7EF374 bit $01

; D7 (Dragon Ship) has no big-key chest: the Stalfos Knight in room $A2 (NE
; alcove, behind the interior small-key door) drops the Big Key. The drop is a
; sprite-list entry $FD,xx,$E4 after the knight (Underworld_LoadSingleSprite
; $09:C327 -> SprDrop 2 -> sprite $E5 -> item $32). It is the only big-key drop
; in the ROM and chest-table audits do not see it. Fail the build if a sprite
; edit in yaze/ZScream loses it (D7's boss door $C4 would have no key).
; Emits no bytes. Docs/Technical/Dungeon_Tables_Expansion.md section 6.
!D7BK_ptrs #= $090000|read2($09C298)             ; RoomData_SpritePointers (LDA.w operand at $09:C297)
!D7BK_p #= ($090000|read2(!D7BK_ptrs+($A2*2)))+1 ; first entry of room $A2's sprite list
!D7BK_found = 0
while read1(!D7BK_p) != $FF
  if read1(!D7BK_p) == $FD && read1(!D7BK_p+2) == $E4
    !D7BK_found = 1
  endif
  !D7BK_p #= !D7BK_p+3
endwhile
assert !D7BK_found == 1, "D7 room $A2 lost its big-key drop (sprite entry $FD,xx,$E4); D7's boss door $C4 needs it"

; Pit inner-corner objects ($FA2-$FA5) place tile $055 (type $02, solid) and
; tile $07C (type $00, floor) one cell inside the pit or lava. With the Roc's
; Feather these specks stop a jump in mid-air or let Link stand on lava.
; The 2026-09-24 yaze audit found both tiles only inside pits in all 296
; rooms, so both become pit tiles. UnderworldTileTypes is shared by every
; blockset (LoadDefaultTileTypes, #_0E97D9).
assert read1($0E9659+$055) == $02 || read1($0E9659+$055) == $20, "Unexpected tile type for tile $055"
org $0E9659+$055 : db $20
assert read1($0E9659+$07C) == $00 || read1($0E9659+$07C) == $20, "Unexpected tile type for tile $07C"
org $0E9659+$07C : db $20

; D6 room $B8 has pits but holewarp $00, so a fall loaded room $00 (the
; Kydreeok room). List $B8 as a damage-pit room instead: a fall costs one
; heart and respawns Link. Uses the last of five $0123 filler entries in
; RoomsWithPitDamage ($00:990C, 57 words).
assert read2($00997C) == $0123 || read2($00997C) == $00B8, "Unexpected pit-damage table tail"
org $00997C : dw $00B8

; =========================================================
; JumpTableLocal Guard (Black-Screen Prevention)
;
; JumpTableLocal ($008781) expects X/Y=8-bit on entry so that PLY pops 1 byte.
; If a width leak enters with X/Y=16-bit, PLY pops 2 and corrupts the stack,
; frequently manifesting as a hard lock / black screen.
;
; This guard makes the routine self-healing by forcing X/Y=8-bit before the
; first STY/PLY. It does NOT fix the upstream width leak, but it prevents the
; catastrophic failure mode and makes runtime captures actionable.
; =========================================================
if !ENABLE_JUMPTABLELOCAL_GUARD
  org $008781 ; @hook module=Core name=JumpTableLocal_Guard kind=jml target=JumpTableLocal_Guard expected_x=8 expected_m=8
    JML JumpTableLocal_Guard
    NOP

  ; Place the guard routine in known-free space in Bank $2C.
  ; (Bank $3C is used by ZS/ROM data in many builds.)
  org $2CFF00
  JumpTableLocal_Guard:
  {
    SEP #$10    ; Force X/Y=8-bit so PLY pops 1 byte (JSL pushes 3-byte retaddr).
    STY.b $03   ; Original: save caller Y
    PLY         ; Original: pull low byte of return address
    STY.b $00   ; Original: stash it for table base math

    ; Resume original routine at REP #$30 (the instruction after STY $00).
    JML $008786
  }
endif

; UnderworldTransition_ScrollRoom
org $02BE5E ; @hook module=Core name=Graphics_Transfer kind=jsl target=Graphics_Transfer
if !ENABLE_GRAPHICS_TRANSFER_SCROLL_HOOK
  JSL Graphics_Transfer
else
  ; Vanilla is `LDA.b $11` here; CMP #$02 follows at $02BE60.
  LDA.b $11
  NOP #2
endif

; Whirlpool
org $1EEEE4 : JSL DontTeleportWithoutFlippers ; @hook module=Core name=DontTeleportWithoutFlippers kind=jsl target=DontTeleportWithoutFlippers

; SpriteDraw_Roller
org $058EE6 : JSL PutRollerBeneathLink ; @hook module=Core name=PutRollerBeneathLink kind=jsl target=PutRollerBeneathLink

; =========================================================

; Sprite Recoil and Death
; TODO: Sprite_AttemptKillingOfKin
; Kydreeok Head die like Sidenexx
org $06F003 : CMP.b #$CF

; Remove sidenexx death from booki
org $06EFFF : NOP #4

; Make Dark Link die like sidenexx
org $06F003 : CMP.b #$C1

; Make Helmet ChuChu recoil link
org $06F37D : CMP.b #$05

; Make Kydreeok head recoil Link
org $06F381 : CMP.b #$CF

; =========================================================

InCutScene = $7EF303

; Player2JoypadReturn
org $0083F8 ; @hook module=Core name=Player2JoypadReturn_InputClamp kind=patch
  LDA InCutScene : BEQ .notInCutscene
    STZ $F0
    STZ $F2
    STZ $F4
    STZ $F6
    STZ $F8
    STZ $FA ; kill all input
  .notInCutscene
  RTS

assert pc() <= $00841E

; =========================================================

; With !ENABLE_EARLY_GAME_BALANCE the vanilla Heart item returns at $1EF27D
; (base ROM bytes) and Bananas move to shop item type $0E
; (Core/early_game_balance.asm).
if !ENABLE_EARLY_GAME_BALANCE == 0
org $1EF27D ; @hook module=Core
ShopItem_Banana:
{
  JSR $F4CE   ; SpriteDraw_ShopItem
  JSR $FE78   ; Sprite_CheckIfActive_Bank1E
  JSL $1EF4F3 ; Sprite_BehaveAsBarrier
  JSR $F391   ; ShopItem_CheckForAPress
  BCC .exit

    LDA.l Bananas : CMP.b #$0A : BCS .error
    LDA.b #$1E : LDY.b #$00
    JSR $F39E ; ShopItem_HandleCost
    BCC .error

    STZ.w SprState,X
    INC.b Bananas

    LDY.b #$42 : JSR $F366 ; ShopItem_HandleReceipt

  .exit
  RTS
  .error
  JSR $F1A1 ; ShopItem_GiveFailureMessage
}
assert pc() <= $1EF2AB

; =========================================================

; Shop item heart OAM
; SpriteDraw_ShopItem
org $1EF42E
  dw  -4,  16 : db $03, $02, $00, $00 ; 3
  dw  -4,  16 : db $03, $02, $00, $00 ; 3
  dw   4,  16 : db $30, $02, $00, $00 ; 0
  dw   0,   0 : db $E5, $03, $00, $02 ; item
  dw   4,  11 : db $38, $03, $00, $00 ; shadow
endif

; =========================================================

; Octoballoon_FormBabby
; Reduce by half the number of babies spawned
org $06D814 : LDA.b #$02

; SpritePrep_HauntedGroveOstritch
org $068BB2 : NOP #11

; HauntedGroveRabbit_Idle
org $1E9A8F : NOP #5

; MedallionTablet (Goron)
org $05F274 : LDA.l $7EF378 ; Unused SRAM

org $08C2E3 : dw $006F ; BUTTER SWORD DIALOGUE

; Fix the capital 'B' debug item cheat.
org $0CDC26 : db $80 ; replace a $F0 (BEQ) with a $80 (BRA).

; Update Catfish Item Get to Bottle
org $1DE184 : LDA.b #$16 : STA.w $0D90, X

; Follower_Disable
; Don't disable Kiki so we can switch maps with him.
org $09ACF3 : LDA.l $7EF3CC : CMP.b #$0E

; Kiki, don't care if we're not in dark world
org $099FEB : LDA.b $8A : AND.b #$FF

org $1EE48E : NOP #6

; Kiki activate cutscene 3 (tail palace)
org $1EE630 : LDA.b #$03 : STA.w $04C6

; Kid at ranch checks for flute
org $05FF7D : LDA.l $7EF34C : CMP.b #$01

; Kid at ranch: vanilla msg $147 path writes MapIcon ($7EF3C7) = 2 at
; $05FF8F, reachable before D1. The map icon timeline drops that write
; (Docs/Debugging/Issues/world_map_icons_2026-09-26.md).
if !ENABLE_MAP_ICON_TIMELINE == 1
  org $05FF8F : NOP #6
endif

; Raven Damage (LW/DW)
org $068963 : db $81, $84

; Running Man draw palette
org $05E9CD
SpriteDraw_RunningBoy:
  #_05E9CD: dw   0,  -8 : db $2C, $00, $00, $02
  #_05E9D5: dw   0,   0 : db $EE, $0E, $00, $02

  #_05E9DD: dw   0,  -7 : db $2C, $00, $00, $02
  #_05E9E5: dw   0,   1 : db $EE, $4E, $00, $02

  #_05E9ED: dw   0,  -8 : db $2A, $00, $00, $02
  #_05E9F5: dw   0,   0 : db $CA, $0E, $00, $02

  #_05E9FD: dw   0,  -7 : db $2A, $00, $00, $02
  #_05EA05: dw   0,   1 : db $CA, $4E, $00, $02

  #_05EA0D: dw   0,  -8 : db $2E, $00, $00, $02
  #_05EA15: dw   0,   0 : db $CC, $0E, $00, $02

  #_05EA1D: dw   0,  -7 : db $2E, $00, $00, $02
  #_05EA25: dw   0,   1 : db $CE, $0E, $00, $02

  #_05EA2D: dw   0,  -8 : db $2E, $40, $00, $02
  #_05EA35: dw   0,   0 : db $CC, $4E, $00, $02

  #_05EA3D: dw   0,  -7 : db $2E, $40, $00, $02
  #_05EA45: dw   0,   1 : db $CE, $4E, $00, $02

; Sword Barrier Sprite Prep
; Skip overworld flag check, sprite is indoors now
org $06891B : NOP #12

; (SPC upload timeout hook removed – revert to vanilla handshake)

; Early-game balance (default off; see Util/macros.asm).
if !ENABLE_EARLY_GAME_BALANCE == 1
  incsrc "Core/early_game_balance.asm"
endif
