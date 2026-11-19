; =========================================================
; Abyss load spawn menu
;
; Before the endgame every outdoor Abyss load lands at the pyramid (exit room
; $20, Module05_LoadFile $0281AB): SavedWorld is the respawn lock
; (LoadDarkWorldIntro). From GameState 3 (Farore rescued) an outdoor Abyss
; load shows the vanilla spawn-select box with message $21B instead:
;   0 = Eon Abyss    (keeps the Abyss load, spawns outside the Abyss Windmill
;                     via exit room $C9 -> area $63, Exit #39)
;   1 = Kalyxo       (SavedWorld = 0, then the vanilla light world menu
;                     $0184/$0185: Link's House / Hall of Secrets /
;                     Mountain Cave, same gates as a light world load)
; =========================================================

; Called by JML from LoadCheckpointOrWorld .legacy after LoadDarkWorldIntro.
; Entry Z = vanilla $028196 BEQ input (0 = light world). Both exits keep Z.
AbyssSpawnMenu_Check:
{
  PHP
  BEQ .vanilla
  LDA.b $1B : BNE .vanilla
  LDA.l GameState : CMP.b #!GameState_FaroreRescued : BCC .vanilla
  ; Same continue/mosaic gates as the vanilla light world menu ($0281BD).
  LDA.l $7EC011 : BNE .vanilla
  LDA.w $010A : BEQ .show
    LDA.w $04AA : BEQ .vanilla
  .show
  PLP
  REP #$10
  LDX.w #$021B ; MESSAGE 021B
  ; Vanilla tail: STX $1CF0, show the message, enter Module1B_SpawnSelect.
  JML $0281ED
  .vanilla
  PLP
  JML $028196
}

; Module1B_SpawnSelect $028598 (replaces LDA.l $7EF3C8 : PHA).
; Vanilla reaches Module1B only from the light world branch (SavedWorld = 0),
; so SavedWorld != 0 means this menu. $1CF0 is not usable here: the choice
; box rewrites it when the cursor moves.
AbyssSpawnMenu_Select:
{
  LDA.l SavedWorld : BNE .abyss_menu
    LDA.l SpawnPoint : PHA
    JML $02859D

  .abyss_menu
  LDA.w $1CE8 : BNE .light_world
    ; Eon Abyss: spawn outside the Abyss Windmill (exit room $00C9 -> area $63,
    ; Exit #39) using the same outdoor Module08 sequence as $02819C-$0281BC.
    ; Kydrog's initial story warp to the Pyramid ($0281AB) remains unchanged.
    JSL $0DE395 ; SearchForEquippedItem_long
    JSL $0DFA6C ; RebuildHUD_long2
    JSL $0DDD32 ; UpdateEquippedItem_long
    STZ.w $010A
    LDA.b #$C9 : STA.b $A0 ; ROOM 00C9 (Abyss Windmill exit #39 -> area $63)
    STZ.b $A1
    ; The text box shade uses HDMA; Module08 loads with HDMA off.
    STZ.b $9B
    LDA.b #$08 : STA.b $10
    STZ.b $11
    STZ.b $B0
    STZ.w $04AA
    RTL

  .light_world
  ; Step 2: SavedWorld = 0, then the vanilla light world menu. When that box
  ; closes, Module1B runs again and takes the vanilla path above.
  LDA.b #$00 : STA.l SavedWorld
  ; Normal Link form: no GBC hook runs before the underworld entrance.
  LDA.b #$10 : STA.b $BC
  STZ.w $02B2
  ; Same gates as the light world branch as patched in overworld.asm:
  ; Hall of Secrets flag ($0281CD) and goldstar for Mountain Cave ($0281E2).
  LDA.l $7EF3D6 : CMP.b #$04 : BCC .house_only
  REP #$10
  LDX.w #$0185 ; MESSAGE 0185 (House / Hall of Secrets / Mountain Cave)
  LDA.l $7EF342 : CMP.b #$02 : BEQ .show_light_world
    LDX.w #$0184 ; MESSAGE 0184 (House / Hall of Secrets)
  .show_light_world
  ; Vanilla tail: STX $1CF0, show the message, stay in Module1B.
  JML $0281ED

  .house_only
  ; No Hall of Secrets yet: Link's House (spawn $00) without a second box.
  LDA.l SpawnPoint : PHA
  LDA.b #$00 : STA.l SpawnPoint
  STZ.b $B0
  JSL $028208 ; LoadUnderworldRoomRebuildHUD
  PLA : STA.l SpawnPoint
  RTL
}

pushpc
; Module1B_SpawnSelect
assert read4($028598) == $7EF3C8AF || read1($028598) == $5C, "Unexpected spawn read in Module1B_SpawnSelect"
org $028598 : JML AbyssSpawnMenu_Select : NOP ; @hook module=Overworld name=AbyssSpawnMenu_Select kind=jml target=AbyssSpawnMenu_Select expected_m=8 expected_x=8
assert pc() == $02859D
pullpc
