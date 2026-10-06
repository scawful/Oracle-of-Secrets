; =========================================================
; Early-game balance (!ENABLE_EARLY_GAME_BALANCE)
;
; scawful + Chris playtest 2026-09-25: early enemies hit too hard, healing is
; hard to afford. Proposal and decisions:
; Docs/Planning/Plans/enemy_balance_proposal_2026-09-26.md.
;
; 1. Damage classes (SpriteData_Bump $0DB266, low nibble). Damage per class,
;    green/blue/red mail, in 1/8 hearts (Sprite_BumpDamageGroups $06F427):
;      1 = 4/4/4 (half heart)   3 = 8/4/2 (1 heart on green)
;      4 = 8/8/8 (1 heart)      6 = 32/16/8 (4 hearts on green)
;    These are per sprite ID, so they apply everywhere the sprite is placed.
;    Sea Urchin ($AE) is an Oracle sprite: its HP/damage change is in
;    Sprites/Enemies/sea_urchin.asm under the same flag.
; 2. Per-location HP overrides: EnemyBalance_HPOverrides below. Add a row to
;    give one sprite ID a different HP in one room, area or dungeon.
; 3. Red Potion: 150 -> 100 rupees.
; 4. Shops: the Standard Stock middle item is the vanilla Heart again
;    (10 rupees; Core/patches.asm skips its Banana patch under this flag), except
;    in shop room !ShopBananaRoom, which sells Bananas
;    (30 rupees) as the new shop item type !ShopItemBanana.
; =========================================================

pushpc

; ---------------------------------------------------------
; 1. Damage classes (bump byte: high bits kept, all are $0x today)
org $0DB266+$9B : db $03   ; Wizzrobe (D1): class 6 -> 3
org $0DB266+$20 : db $04   ; Sluggula (D1): class 6 -> 4
org $0DB266+$23 : db $01   ; Red Bari (D1/D2): class 3 -> 1

; ---------------------------------------------------------
; 3. Red Potion price (ShopItem_RedPotion150) and its price digits
;    (SpriteDraw_ShopItem group 0: "1" "5" "0" -> "1" "0" "0").
org $1EF183 : LDA.b #100
org $1EF3C2 : db $30       ; middle digit tile: $13 "5" -> $30 "0"

; ---------------------------------------------------------
; 2. HP overrides. SpritePrep_LoadProperties ($0DB818) loads HP from
;    SpriteData_Health with DBR = $0D, Y = sprite ID, X = slot.
;    LDA.w SpriteData_Health,Y : STA.w $0E50,X (6 bytes)
org $0DB829 ; @hook module=Core name=EnemyBalance_LoadHealth kind=jsl target=EnemyBalance_LoadHealth
  JSL EnemyBalance_LoadHealth
  NOP #2
assert pc() == $0DB82F

; ---------------------------------------------------------
; 4. Shops (see the header). Standard Stock rooms: $011F (Wayward Village
;    shop, entrance $46), $0112 (Eon Abyss shop, entrance $58, DW $46), $00FF.
;    Entrance $6B (Tail Pond) opens the Mask Salesman half of $011F, where the
;    counter cannot be reached.
!ShopBananaRoom     = $0112
!ShopItemBanana     = $0E

; SpritePrep_Shopkeeper_StandardStock: LDA.b #$00 : LDY.b #$07 (4 bytes)
org $068C72 ; @hook module=Core name=ShopBalance_StandardStock kind=jml target=ShopBalance_StandardStock
  JML ShopBalance_StandardStock
assert pc() == $068C76

; Sprite_BB_Shopkeeper: LDA.w $0E80,X (3 bytes); the JSL JumpTableLocal
; after it stays, so every other type runs vanilla.
org $1EEEEF ; @hook module=Core name=ShopBalance_Dispatch1E kind=patch
  JMP.w ShopBalance_Dispatch1E
assert pc() == $1EEEF2

; Bank $1E free space ($FF in the base ROM). The shop helpers end in RTS, so
; bank $3A code reaches them through these JSL stubs (DBR stays $1E).
org $1EFFDE
ShopBalance_Dispatch1E:
  LDA.w $0E80,X : CMP.b #!ShopItemBanana : BEQ .banana
  JMP.w $EEF2                              ; JSL JumpTableLocal, A = type
  .banana
  JSL ShopBalance_Banana
  RTS
ShopBalance_CheckForAPress: JSR $F391 : RTL   ; ShopItem_CheckForAPress
ShopBalance_HandleCost:     JSR $F39E : RTL   ; ShopItem_HandleCost
ShopBalance_HandleReceipt:  JSR $F366 : RTL   ; ShopItem_HandleReceipt
ShopBalance_FailureMessage: JSR $F1A1 : RTL   ; ShopItem_GiveFailureMessage
assert pc() <= $1F0000, "Shop stubs crossed the end of bank $1E"

org $3AEC00
; Bank $3A: text box shade ends below $3AEC00; 2P PoC main block starts at $3AF000.

; Out: $0E50,X = HP. Keeps A/X/Y widths (8-bit), DBR = $0D.
; Sprites whose own Prep writes $0E50 later ignore these overrides.
EnemyBalance_LoadHealth:
{
  LDA.w $B173,Y : STA.w $0E50,X          ; replaced code (SpriteData_Health)
  PHX
  LDX.b #$00
  .next
    LDA.l EnemyBalance_HPOverrides, X : CMP.b #$FF : BEQ .done
    TYA : CMP.l EnemyBalance_HPOverrides, X : BNE .skip
    LDA.l EnemyBalance_HPOverrides+1, X
    BEQ .room
    DEC A : BEQ .area
    ; scope 2: dungeon ($040C)
      LDA.w $040C : CMP.l EnemyBalance_HPOverrides+2, X : BNE .skip
      BRA .match
    .area
      LDA.b $1B : BNE .skip                ; overworld only
      LDA.b $8A : CMP.l EnemyBalance_HPOverrides+2, X : BNE .skip
      BRA .match
    .room
      LDA.b $1B : BEQ .skip                ; underworld only
      REP #$20
      LDA.b $A0 : CMP.l EnemyBalance_HPOverrides+2, X
      SEP #$20
      BNE .skip
    .match
    LDA.l EnemyBalance_HPOverrides+4, X
    PLX
    STA.w $0E50,X
    RTL
    .skip
    INX #5
    BRA .next
  .done
  PLX
  RTL
}

; Standard Stock prep: Red Potion, then Heart or Banana, then Bombs.
ShopBalance_StandardStock:
{
  LDA.b #$00 : LDY.b #$07 : JSL $1EF1B3    ; ShopKeeper_SpawnShopItem: Red Potion
  LDY.b #$0A                               ; Heart
  REP #$20
  LDA.b $A0 : CMP.w #!ShopBananaRoom
  SEP #$20
  BNE +
    LDY.b #!ShopItemBanana
  +
  JML $068C7C                              ; SpritePrep_Shopkeeper_SpawnItemAndBombs
}

; Shop item $0E: Bananas (was ShopItem_Banana at $1EF27D in Core/patches.asm).
; In: X = sprite slot, DBR = $1E.
ShopBalance_Banana:
{
  ; SpriteDraw_ShopItem indexes its OAM groups by type - 7 (7 groups), so
  ; draw our own group. The tabulated draw reads ($08) through DBR.
  PHB : PHK : PLB
  REP #$20
  LDA.w #ShopBalance_BananaOAM&$FFFF : STA.b $08
  LDA.w #$0005 : STA.b $06
  SEP #$30
  JSL $05DF75                              ; SpriteDraw_Tabulated_player_deferred
  PLB

  ; Sprite_CheckIfActive_Bank1E ($1EFE78), inline.
  LDA.w $0DD0,X : CMP.b #$09 : BNE .exit
  LDA.w $0FC1 : BNE .exit
  LDA.b $11 : BNE .exit
  LDA.w $0CAA,X : BMI .active
  LDA.w $0F00,X : BNE .exit
  .active
  JSL $1EF4F3                              ; Sprite_BehaveAsBarrier
  JSL ShopBalance_CheckForAPress : BCC .exit
  LDA.l Bananas : CMP.b #$0A : BCS .error
  LDA.b #30 : LDY.b #$00
  JSL ShopBalance_HandleCost : BCC .error
  STZ.w $0DD0,X
  LDA.l Bananas : INC A : STA.l Bananas    ; old code did INC.b $8B (direct page)
  LDA.b #$0A : STA.w $0E80,X               ; receipt message table is type - 7
  LDY.b #$42 : JSL ShopBalance_HandleReceipt
  .exit
  RTL
  .error
  JSL ShopBalance_FailureMessage
  RTL
}

ShopBalance_BananaOAM:
  dw  -4,  16 : db $03, $02, $00, $00 ; 3
  dw  -4,  16 : db $03, $02, $00, $00 ; 3
  dw   4,  16 : db $30, $02, $00, $00 ; 0
  dw   0,   0 : db $E5, $03, $00, $02 ; banana
  dw   4,  11 : db $38, $03, $00, $00 ; shadow

; First matching row wins. Sprite ID $FF ends the table.
;   db sprite ID, scope : dw scope ID : db HP
;   scope 0 = underworld room ($A0), 1 = overworld area ($8A),
;         2 = dungeon ($040C)
EnemyBalance_HPOverrides:
  db $91, 0 : dw $0033 : db 24   ; Stalfos Knight, D1 room $33 (D2 keeps 64)
  db $FF

print "End of early-game balance         ", pc
assert pc() <= $3AF000, "Early-game balance crossed $3AF000 (2P PoC)"
pullpc
