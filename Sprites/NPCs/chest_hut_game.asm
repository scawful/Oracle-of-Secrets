; =========================================================
; Lyra Sea Chest Hut Minigame ($AB -> Ent $67 -> Room $0118)
; (Included from Sprites/all_sprites.asm, Bank $32)
;
; Implements DECIDED prize pool (decisions.org 2026-11-16):
;   - Rupee gamble across 1 / 20 / 50 / 100 Rupees ($34/$47/$41/$40).
;   - Plus one bonus Seashell ($7EF391, capped at 99) awarded once per save,
;     tracked in Room $0118's persistent room-flag high byte ($0403 / $7EF231
;     bit $40, matching vanilla VoO Chest Game Heart Piece persistence at
;     $01EEAE). Plays SFX3.$0F item fanfare on the one-time Seashell win and
;     vanilla SFX3.$0E on normal rupee chests.
;
; Note: Entry price/chest count (20r/1-chest at $1EF0B7/$1EF0C0) stays aligned
; with vanilla message $017E until scawful approves the 30-Rupee / 2-chest
; host text.
; =========================================================

!ChestHut_SeashellFlag  = $40
!ChestHut_SeashellCap   = 99
!ChestHut_RoomFlagHi    = $7EF231 ; RMFLG118+1 ($7EF000 + $118*2 + 1)
!ChestHut_SfxFanfare    = $0F     ; SFX3.$0F item fanfare

pushpc
assert read4($01EEFF) == $0DBA7122 && read2($01EF03) == $0F29, "Expected vanilla OpenMiniGameChest_LowStake at $01EEFF"
org $01EEFF ; @hook module=Sprites name=ChestHut_RollPrize kind=jml target=ChestHut_RollPrize
  JML ChestHut_RollPrize
  NOP #5
assert pc() == $01EF08, "ChestHut_RollPrize hook must stop before shared .set_prize ($01EF08)"
pullpc

; Entry: M=8, X=8, called only from OpenMiniGameChest when $A0 == #$18 (Room $0118).
; Exits via JML $01EEC5 (FinalizeChestGamePrize) for normal rupee prizes or
; JML $01EED4 (PLB : SEC : RTL) after playing SFX3.$0F on the one-time Seashell bonus.
ChestHut_RollPrize:
{
  JSL GetRandomInt
  AND.b #$0F
  TAX

  ; One-time bonus Seashell on jackpot slots (X & $03 == 0 -> 25% per chest).
  LDA.w $0403
  ORA.l !ChestHut_RoomFlagHi
  AND.b #!ChestHut_SeashellFlag
  BNE .rupee_only
  TXA
  AND.b #$03
  BNE .rupee_only

    ; Mark persistent room flag in both live $0403 and SRAM $7EF231 so even
    ; Save & Quit inside Room $0118 cannot farm a second Seashell.
    LDA.w $0403 : ORA.b #!ChestHut_SeashellFlag : STA.w $0403
    LDA.l !ChestHut_RoomFlagHi : ORA.b #!ChestHut_SeashellFlag : STA.l !ChestHut_RoomFlagHi

    LDA.l Seashells
    CMP.b #!ChestHut_SeashellCap : BCS .seashell_capped
      INC A
      STA.l Seashells
    .seashell_capped

    ; Award 100-Rupee chest receipt alongside the one-time Seashell + item fanfare.
    STX.b $C8
    LDA.b #$40 ; ITEMGET $40 - 100 Rupees
    STA.b $0C
    STZ.b $0D
    LDA.b #$01 : STA.b $14
    LDA.b #!ChestHut_SfxFanfare : STA.w $012F
    JML $01EED4 ; PLB : SEC : RTL

  .rupee_only
  LDA.l ChestHut_RupeePrizes, X
  JML $01EEC5 ; FinalizeChestGamePrize (stores $C8/$0C/$0D/$14, SFX3.$0E, PLB, SEC, RTL)
}

; 16-entry rupee gamble: 5x 1r ($34), 5x 20r ($47), 4x 50r ($41), 2x 100r ($40).
ChestHut_RupeePrizes:
  db $34, $47, $41, $47
  db $34, $40, $47, $34
  db $41, $47, $34, $41
  db $40, $34, $47, $41

print "End of chest_hut_game.asm          ", pc
