; This file contains all direct patches to the original ROM.
; It is included from Oracle_main.asm.

; Pot-item lists live in bank $5C. RevealPotItem ($01:E6B2) takes the list
; address from the table at $01:DB69 and the bank from LDA.w #$00bb at
; $01:E6C7. The base ROM carries the operand and the data together
; (Scripts/Rooms/pot_item_bank_migration.py), so the build only checks them:
; writing the operand here onto an unmigrated base would point every room at
; empty bank-$5C data. The 23 unused table words after room $127 point at the
; reserved terminator at $5C:FFFE. Emits no bytes.
assert read1($01E6C7) == $A9 && read1($01E6C9) == $00, "RevealPotItem bank loader at $01:E6C7 changed"
assert read1($01E6C8) == $5C, "Base ROM pot items are not in bank $5C: run Scripts/Rooms/pot_item_bank_migration.py on the base"
assert read2($5CFFFE) == $FFFF, "Pot-item pad terminator at $5C:FFFE was overwritten"
; The operand alone does not prove the table was rewritten: the first and last
; pad words ($01:DDB9, $01:DDE5) hold $FFFE only after the migration.
assert read2($01DDB9) == $FFFE && read2($01DDE5) == $FFFE, "Pot-item table at $01:DB69 is not migrated: pad words do not point at $5C:FFFE"

; Keep the Shrine pendant rewards reproducible from an unedited base ROM.
; Guard both the chest record identity and the accepted old/already-fixed item
; values so a changed chest table fails closed instead of patching a wrong byte.
assert read2($01E9E6) == $8073, "Room $73 big-chest record moved"
assert read1($01E9E8) == $39 || read1($01E9E8) == $3A, "Unexpected room $73 big-chest item"
org $01E9E8 : db $39 ; Pendant of Power: receipt handler sets $7EF374 bit $02

; Shrine of Wisdom (decisions.org 2026-11-18, "Yes, shrine keeper"): a Sea Zora
; keeper in the dry room $9A gives the Flippers (Sprites/NPCs/zora.asm). Link
; swims on to $7A for the pendant; the $9A big chest holds a Piece of Heart.
assert read2($01EA1C) == $809A, "Room $9A big-chest record moved"
assert read1($01EA1E) == $1E || read1($01EA1E) == $38 || read1($01EA1E) == $17, "Unexpected room $9A big-chest item"
org $01EA1E : db $17 ; Piece of Heart (the Flippers come from the shrine keeper)

assert read2($01E9F5) == $807A, "Room $7A big-chest record moved"
assert read1($01E9F7) == $38 || read1($01E9F7) == $39 || read1($01E9F7) == $17, "Unexpected room $7A big-chest item"
org $01E9F7 : db $38 ; Pendant of Wisdom: receipt handler sets $7EF374 bit $01

; Shrine of Wisdom entrance $81 targets room $00CA (layout 4: horizontal split
; with solid divider wall at y=28..36 and intra-room doors at (14,36)/(46,36)).
; Its scrollquad byte ($0F:9B81) must be $20 (horizontal scroll only), not $22:
; with bit 1 ($02) set, camera Y scrolls past $1900 early, so crossing (14,36)
; leaves Link's Y high byte at $19 and lands him at $19DE (south wall softlock).
if read2($0F8000+($81*2)) == $00CA
  assert read1($0F9B81) == $22 || read1($0F9B81) == $20, "Unexpected Entrance $81 scrollquad"
  org $0F9B81 : db $20
endif

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

; D5 Glacia rooms $AF and $BF have holewarp $02 (dead-end room). When their
; pit-reset layouts are enabled, list them as damage-pit rooms so a fall costs
; one heart and respawns Link in the room. Uses the second and third of five
; $0123 filler entries in RoomsWithPitDamage ($00:990C, 57 words); mirrored in
; RoomsWithPitDamage_Ext (Dungeons/sky_pit_damage.asm) when extended scan is on.
if !ENABLE_D5_AF_PIT_RESET == 1
  assert read2($009976) == $0123 || read2($009976) == $00AF, "Unexpected pit-damage table slot"
  org $009976 : dw $00AF
endif
if !ENABLE_D5_BF_PIT_RESET == 1
  assert read2($009978) == $0123 || read2($009978) == $00BF, "Unexpected pit-damage table slot"
  org $009978 : dw $00BF
endif

; D6 room $97 drops into $B8 at the same x/y. Falls from the upper pit's west
; edge (beside the first-key Debirando) land on B8's pit band or a walled
; ledge: a damage loop or a wedge the wall cannon finishes (2026-10-11 runtime,
; beta bc7e0778). List $97 as a damage-pit room instead: a fall costs one heart
; and respawns Link in $97. Uses the fourth of five $0123 filler entries.
assert read2($00997A) == $0123 || read2($00997A) == $0097, "Unexpected pit-damage table slot"
org $00997A : dw $0097

; Module15 (Kydrog's warp to the Eon Abyss) refills the mirror H-scroll table
; with vanilla's pyramid scroll $0778 when the white fade ends. The wave builder
; only rewrites every other scanline, so the rest show BG at $0778 while the
; camera is at Oracle's pyramid ($E2 = $0270): two map edges, then a snap when
; message $35 turns HDMA off. Use the live camera instead.
assert read2($00EF80) == $78A9 || read2($00EF80) == $E2A5, "Unexpected Module15 HDMA refill"
org $00EF80 : LDA.b $E2 : NOP

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

; UnderworldTransition_ScrollRoom
org $02BE5E ; @hook module=Core name=Graphics_Transfer kind=jsl target=Graphics_Transfer
  JSL Graphics_Transfer

; Whirlpool
org $1EEEE4 : JSL DontTeleportWithoutFlippers ; @hook module=Core name=DontTeleportWithoutFlippers kind=jsl target=DontTeleportWithoutFlippers

; SpriteDraw_Roller
org $058EE6 : JSL PutRollerBeneathLink ; @hook module=Core name=PutRollerBeneathLink kind=jsl target=PutRollerBeneathLink

; =========================================================

; Sprite Recoil and Death
; Sprite_AttemptKillingOfKin: vanilla sends $CC ($06EFFF) and $CD ($06F003),
; the Trinexx side heads (Oracle: Booki, Thunder Ghost), to
; Sidenexx_ScreamAndDie ($06F0AC, sets SprAction=$80). Here only Dark Link
; ($C1) goes there; $CC/$CD and Kydreeok heads ($CF) take the generic death
; (SprState 06 -> 00), which Sprite_Kydreeok_CheckIfDead reads. The head has
; no SprAction bit7 handler, so routing $CF here would crash in JumpTableLocal
; (2bcf274f removed that route). Kydrog ($CB) still takes the vanilla
; TrinexxRock_ScreamAndDie at $06EFF8. One org per byte here: a second org on
; $06F003 silently replaced the first.
org $06EFFF ; @hook module=Core name=SpriteDeath_SidenexxKin kind=patch protected_size=6
  NOP #4                  ; was CMP #$CC : BEQ $06F007 (Booki)
  CMP.b #$C1              ; was CMP #$CD (Dark Link); the vanilla BNE stays
assert pc() == $06F005, "Sidenexx death dispatch must end at the vanilla BNE"

; [W3 owner: Sprites] USDASM #Sprite_CheckDamageFromLink_with_recoil ($06F37D): recoil against sword hit for sprite $05 (was #$CD).
org $06F37D : CMP.b #$05

; [W3 owner: Sprites] USDASM #Sprite_CheckDamageFromLink_with_recoil ($06F381): recoil Link on Kydreeok head $CF (was #$CC).
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

; =========================================================

; [W3 owner: Sprites] USDASM Octoballoon_FormBabby ($06D814): reduce spawned baby count 5 -> 2.
org $06D814 : LDA.b #$02

; [W3 owner: Sprites] USDASM SpritePrep_HauntedGroveOstritch ($068BB2): NOP #11 over flute check ($7EF34C) so Haunted Grove ostrich stays visible.
org $068BB2 : NOP #11

; [W3 owner: Sprites] USDASM HauntedGroveRabbit_Idle ($1E9A8F): NOP #5 over bottle/progression gate ($0FDD).
org $1E9A8F : NOP #5

; [W3 owner: Sprites] USDASM SpritePrep_MedallionTablet ($05F274): check unused SRAM $7EF378 instead of $7EF347 so tablet remains active.
org $05F274 : LDA.l $7EF378 ; Unused SRAM

; [W3 owner: Items] USDASM Ancilla35_MasterSwordReceipt ($08C2E3): Butter Sword receipt message $006F (was $0052).
org $08C2E3 : dw $006F ; BUTTER SWORD DIALOGUE

; [W3 owner: Core] USDASM InitializeSaveFile ($0CDC26): patch BEQ .copy_next ($F0) -> BRA ($80) to fix capital 'B' debug item cheat.
org $0CDC26 : db $80 ; replace a $F0 (BEQ) with a $80 (BRA).

; [W3 owner: Sprites] USDASM Catfish_RegurgitateMedallion ($1DE184): swap Catfish drop item $11 (Quake) -> $16 (Bottle).
org $1DE184 : LDA.b #$16 : STA.w $0D90, X

; [W3 owner: Sprites/Followers] USDASM Follower_Disable ($09ACF3): check follower $0E (Kiki/new companion, was #$09/#$0A) before despawning across maps.
org $09ACF3 : LDA.l $7EF3CC : CMP.b #$0E

; [W3 owner: Sprites/Followers] USDASM #Follower_AIVectors ($099FEB): preserve Kiki across Light/Dark world ($8A & $FF instead of $40).
org $099FEB : LDA.b $8A : AND.b #$FF

; [W3 owner: Sprites/Followers] USDASM Kiki_Dormant ($1EE48E): NOP #6 over $02E0 follower check so Kiki stays active.
org $1EE48E : NOP #6

; [W3 owner: Sprites/Followers] USDASM Kiki_WalkOnRoof ($1EE630): trigger Tail Palace cutscene state $03 in $04C6 (was #$01).
org $1EE630 : LDA.b #$03 : STA.w $04C6

; [W3 owner: Sprites] USDASM Sprite_3C_KidInKak ($05FF7D): check flute/ocarina slot $7EF34C >= 1 instead of MapIcon $7EF3C7.
org $05FF7D : LDA.l $7EF34C : CMP.b #$01

; Kid at ranch: vanilla msg $147 path writes MapIcon ($7EF3C7) = 2 at
; $05FF8F, reachable before D1. The map icon timeline drops that write
; (Docs/Debugging/Issues/world_map_icons_2026-09-26.md).
  org $05FF8F : NOP #6

; [W3 owner: Sprites] USDASM SpritePrep_Vitreous ($068963): override LW/DW damage table bytes ($81, $84; was $81, $88).
org $068963 : db $81, $84

; [W3 owner: Sprites] USDASM RunningMan_RunAway ($05E9CD): custom 8-frame Running Boy OAM table (#_05E9CD..#_05EA45).
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

; [W3 owner: Sprites] USDASM SpritePrep_AgahnimsBarrier ($06891B): NOP #12 over overworld check so Sword Barrier works indoors.
org $06891B : NOP #12

; (SPC upload timeout hook removed – revert to vanilla handshake)

; [W3 owner: Items] USDASM PaletteData_sword ($1BD630, 3 words/level: blade mid, blade light, hilt).
; Approved 2026-11-17/18 (QUEUE287, oracle_title_filemenu_2026-11-17/sword_palette_patch.asm): Lv3 Greatblade stays base ROM row.
org $1BD636 ; @hook module=Core name=PaletteData_SwordLv2Meadow kind=data
  dw $32EA, $67F8, $19F6 ; Lv2 Meadow Blade: Farore green, gold hilt
org $1BD642 ; @hook module=Core name=PaletteData_SwordLv4Master kind=data
  dw $7E4E, $6FF4, $1CF5 ; Lv4 Master Sword (pedestal $0589AF): vanilla blue

; Early-game balance ($BB dispatch, shop item redirects, HP overrides).
  incsrc "Core/early_game_balance.asm"
