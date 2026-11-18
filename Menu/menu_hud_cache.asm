; =========================================================
; Cached HUD update implementation (bank $2B, included from Items/all_items.asm).
; Bank $2E has only ~53 bytes free before the D8 boss code slot ($2EB800).
; Volatile HUD render cache in UNUSED_7EC900 (Core/ram.asm:5926), after
; OverworldMusicCache ($7EC900-$7EC9BF) and before BombchuPackPending ($7EC9E0).
; =========================================================

HudCache_Init       = $7EC9C0 ; $5A when cache matches $7EC700
HudCache_MaxHP      = $7EC9C1
HudCache_CurHP      = $7EC9C2
HudCache_HeartTile0 = $7EC9C3 ; word at $7EC744 to detect RebuildHUD/blanking
HudCache_MagicCap   = $7EC9C5
HudCache_Magic      = $7EC9C6
HudCache_Rupees     = $7EC9C7 ; word ($7EF362)
HudCache_AmmoItem   = $7EC9C9
HudCache_AmmoVal    = $7EC9CA
HudCache_Keys       = $7EC9CB
HudCache_CodexMask  = $7EC9CC
HudCache_CodexX     = $7EC9CD
HudCache_CodexVer   = $7EC9CE
HudCache_CodexHook  = $7EC9CF
HudCache_CodexRod   = $7EC9D0
HudCache_CodexBow   = $7EC9D1
HudCache_CodexAmmo  = $7EC9D2

!HudHalfMagic   = $7EC72A             ; row 0, cols 21-22 (magic box top)
!HudMagicFill   = $7EC766             ; row 1, cols 19-22
!HudYCount      = $7EC7F6             ; row 3, cols 27-28 (under the Y icon)
!HudYCountRest0 = $A014               ; box bottom strip
!HudYCountRest1 = $207E               ; box bottom piece
!HudRupeeDigits = HudCornerBuffer+4   ; BG3 row 26, cols 4-6
!HudKeyIcon     = HudCornerBuffer+$0A ; BG3 row 26, col 28
!HudKeyDigit    = HudCornerBuffer+$0C ; BG3 row 26, col 29

; Entry: caller P preserved; expects DBR=$0D (for HexToDecimal/HUD_DrawItem).
HUD_Update_Impl:
{
  PHP ; Save caller's P register
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    JSL DreamWisdom_HUDHidden : BCC .draw_with_item
      PLP
      RTL
    .draw_with_item
  endif
  JSL HUD_UpdateItemBox_long
  BRA .after_item_box

  .ignore_item
  PHP ; Save caller's P register
  if !ENABLE_DREAM_WISDOM_SCENE == 1
    JSL DreamWisdom_HUDHidden : BCC .after_item_box
      PLP
      RTL
  endif

  .after_item_box
  SEP #$30

  ; Invalidate cache on cold start or if RebuildHUD/blanking overwrote $7EC744.
  LDA.l HudCache_Init : CMP.b #$5A : BNE .hearts_invalidate
  LDA.l HudCache_MaxHP : BEQ .hearts_invalidate
  REP #$20
  LDA.l $7EC744 : CMP.l HudCache_HeartTile0
  SEP #$20
  BNE .hearts_invalidate
    LDA.l $7EF36C : CMP.l HudCache_MaxHP : BNE .draw_hearts
    LDA.l $7EF36D : CMP.l HudCache_CurHP : BNE .draw_hearts
    JMP .hearts_done ; BEQ is out of range (155 bytes)

  .hearts_invalidate
  LDA.b #$00 : STA.l HudCache_Init

  .draw_hearts
  ; need to draw partial heart still though.
  LDA.b #$FD : STA $0A
  LDA.b #$F9 : STA $0B
  LDA.b #$0D : STA $0C

  LDA.b #$44 : STA $07
  LDA.b #$C7 : STA $08
  LDA.b #$7E : STA $09

  REP #$30

  ; Load Capacity health.
  LDA.l $7EF36C : AND.w #$00FF : STA $00 : STA $02 : STA $04

  ; First, just draw all the empty hearts (capacity health)
  JSL HUD_UpdateHearts_long

  SEP #$30

  LDA.b #$03 : STA $0A
  LDA.b #$FA : STA $0B
  LDA.b #$0D : STA $0C

  LDA.b #$44 : STA $07
  LDA.b #$C7 : STA $08
  LDA.b #$7E : STA $09

  ; Branch if at full health
  LDA.l $7EF36C : CMP.l $7EF36D : BEQ .healthUpdated
    SEC : SBC #$04 : CMP.l $7EF36D : BCS .healthUpdated

  .healthUpdated

  ; A = actual health + 0x03;
  LDA.l $7EF36D : CLC : ADC.b #$03

  REP #$30

  AND.w #$00FC : STA $00 : STA $04

  LDA.l $7EF36C : AND.w #$00FF : STA $02

  ; filling in the full and partially filled hearts (actual health)
  JSL HUD_UpdateHearts_long

  SEP #$20
  LDA.l $7EF36C : STA.l HudCache_MaxHP
  LDA.l $7EF36D : STA.l HudCache_CurHP
  REP #$20
  LDA.l $7EC744 : STA.l HudCache_HeartTile0
  SEP #$20

  .hearts_done
  BRA .after_ignore_entry ; Skip alternate entry's PHP on fall-through

  .ignore_health ; *$6FC09 ALTERNATE ENTRY POINT ; reentry hook
  PHP ; Save caller's P register for alternate entry

  .after_ignore_entry
  SEP #$20
  LDA.l HudCache_Init : CMP.b #$5A : BNE .counters_invalidate
  LDA.l HudCache_MaxHP : BEQ .counters_invalidate
  REP #$20
  LDA.l $7EC744 : CMP.l HudCache_HeartTile0 : BEQ .counters_ready
  .counters_invalidate
  SEP #$20
  LDA.b #$00 : STA.l HudCache_Init

  .counters_ready
  ; Magic amount indicator (normal, 1/2, or 1/4)
  SEP #$20
  LDA.l HudCache_Init : CMP.b #$5A : BNE .draw_magic
  LDA.l $7EF37B : CMP.l HudCache_MagicCap : BNE .draw_magic
  LDA.l $7EF36E : CMP.l HudCache_Magic : BEQ .magic_done

  .draw_magic
  LDA.l $7EF37B : STA.l HudCache_MagicCap
  LDA.l $7EF36E : STA.l HudCache_Magic
  REP #$30
  LDA.l $7EF37B : AND.w #$00FF : CMP.w #$0001 : BCC .normal_magic_meter
    ; draw 1/2 magic meter
    LDA.w #$2851 : STA.l !HudHalfMagic
    LDA.w #$28FA : STA.l !HudHalfMagic+2

  .normal_magic_meter

  ; check player magic (ranges from 0 to 0x7F)
  ; X = ((MP & 0xFF)) + 7) & 0xFFF8)
  LDA.l $7EF36E : AND.w #$00FF : CLC : ADC #$0007 : AND.w #$FFF8 : TAX

  ; these four writes draw the magic power bar based on how much MP you have
  LDA.l (MagicTilemap)+0, X : STA.l !HudMagicFill
  LDA.l (MagicTilemap)+2, X : STA.l !HudMagicFill+2
  LDA.l (MagicTilemap)+4, X : STA.l !HudMagicFill+4
  LDA.l (MagicTilemap)+6, X : STA.l !HudMagicFill+6

  .magic_done
  SEP #$20
  LDA.l ItemBindingSavedX
  CMP.b #$01 : BEQ .codex_ammo_arrows
  CMP.b #$04 : BEQ .codex_ammo_bombs
if !ENABLE_GOLDSTAR_CELL == 1
  CMP.b #$1C : BEQ .codex_ammo_chu
endif
  CMP.b #$06 : BEQ .codex_bottle0
  CMP.b #$0C : BEQ .codex_bottle1
  CMP.b #$12 : BEQ .codex_bottle2
  CMP.b #$18 : BEQ .codex_bottle3
  LDA.b #$00 : BRA .codex_ammo_ready
  .codex_ammo_arrows : LDA.l $7EF377 : BRA .codex_ammo_ready
  .codex_ammo_bombs  : LDA.l $7EF343 : BRA .codex_ammo_ready
if !ENABLE_GOLDSTAR_CELL == 1
  .codex_ammo_chu    : LDA.l BombchuAmmo : BRA .codex_ammo_ready
endif
  .codex_bottle0 : LDA.l $7EF35C : BRA .codex_ammo_ready
  .codex_bottle1 : LDA.l $7EF35D : BRA .codex_ammo_ready
  .codex_bottle2 : LDA.l $7EF35E : BRA .codex_ammo_ready
  .codex_bottle3 : LDA.l $7EF35F
  .codex_ammo_ready
  PHA
  LDA.l HudCache_Init : CMP.b #$5A : BNE .draw_codex
  REP #$20
  LDA.l HudCornerBuffer : CMP.w #$3CA8
  SEP #$20
  BNE .draw_codex
  LDA.l $7E0000+!CurrentMask : CMP.l HudCache_CodexMask : BNE .draw_codex
  LDA.l ItemBindingSavedVersion : CMP.l HudCache_CodexVer : BNE .draw_codex
  LDA.l ItemBindingSavedX : CMP.l HudCache_CodexX : BNE .draw_codex
  LDA.l GoldstarOrHookshot : CMP.l HudCache_CodexHook : BNE .draw_codex
  LDA.l FishingOrPortalRod : CMP.l HudCache_CodexRod : BNE .draw_codex
  LDA.l $7EF340 : CMP.l HudCache_CodexBow : BNE .draw_codex
  LDA $01,S : CMP.l HudCache_CodexAmmo : BNE .draw_codex
    PLA
    BRA .codex_done

  .draw_codex
  PLA : STA.l HudCache_CodexAmmo
  LDA.l $7E0000+!CurrentMask : STA.l HudCache_CodexMask
  LDA.l ItemBindingSavedVersion : STA.l HudCache_CodexVer
  LDA.l ItemBindingSavedX : STA.l HudCache_CodexX
  LDA.l GoldstarOrHookshot : STA.l HudCache_CodexHook
  LDA.l FishingOrPortalRod : STA.l HudCache_CodexRod
  LDA.l $7EF340 : STA.l HudCache_CodexBow
  REP #$30
  JSL HUD_CodexCells                    ; X icon/count, corner icons
  ; HUD_CodexCells writes key icon $2071; force keys block to re-check $FF blanking.
  SEP #$20
  LDA.b #$FE : STA.l HudCache_Keys
  .codex_done

  ; Load how many rupees the player has
  SEP #$20
  LDA.l HudCache_Init : CMP.b #$5A : BNE .draw_rupees
  REP #$20
  LDA.l $7EF362 : CMP.l HudCache_Rupees : BEQ .rupees_done

  .draw_rupees
  REP #$30
  LDA.l $7EF362 : STA.l HudCache_Rupees
  JSL HexToDecimal_long
  REP #$30

  ; The tile index for the rupee digits
  LDA $03 : AND.w #$00FF : ORA.w #$2400 : STA.l !HudRupeeDigits
  LDA $04 : AND.w #$00FF : ORA.w #$2400 : STA.l !HudRupeeDigits+2
  LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA.l !HudRupeeDigits+4

  .rupees_done
  REP #$30

  ; Check bombs / bombchu / arrows once and skip HexToDecimal if unchanged.
if !ENABLE_TRUTHFUL_CONTROLS == 1
  JSL HUD_ItemBoxItem_long
else
  LDA.l $7E0202 : AND.w #$00FF : TAX
endif
  CPX.w #$0004 : BEQ .calc_bombs
if !ENABLE_GOLDSTAR_CELL == 1
  CPX.w #$001C : BEQ .calc_bombchu
endif
  CPX.w #$0001 : BEQ .calc_arrows
  LDA.w #$0000
  BRA .check_ammo_cache

  .calc_bombs
  LDA.l $7EF343 : AND.w #$00FF
  BRA .check_ammo_cache

if !ENABLE_GOLDSTAR_CELL == 1
  .calc_bombchu
  LDA.l BombchuAmmo : AND.w #$00FF
  CMP.w #!BOMBCHU_AMMO_MAX+1 : BCC .check_ammo_cache
  LDA.w #$0000
  BRA .check_ammo_cache
endif

  .calc_arrows
  LDA.l $7EF377 : AND.w #$00FF

  .check_ammo_cache
  SEP #$20
  PHA
  LDA.l HudCache_Init : CMP.b #$5A : BNE .draw_ammo
  TXA : CMP.l HudCache_AmmoItem : BNE .draw_ammo
  LDA $01,S : CMP.l HudCache_AmmoVal : BNE .draw_ammo
    PLA
    BRA .ammo_done

  .draw_ammo
  TXA : STA.l HudCache_AmmoItem
  PLA : STA.l HudCache_AmmoVal
  REP #$30

  ; Clear digit tiles
  LDA.w #!HudYCountRest0 : STA.l !HudYCount
  LDA.w #!HudYCountRest1 : STA.l !HudYCount+2

  CPX.w #$0004 : BEQ .draw_ammo_digits
if !ENABLE_GOLDSTAR_CELL == 1
  CPX.w #$001C : BEQ .draw_ammo_digits
endif
  CPX.w #$0001 : BNE .ammo_done

  .draw_ammo_digits
  LDA.l HudCache_AmmoVal : AND.w #$00FF
  JSL HexToDecimal_long
  REP #$30

  ; The tile index for the first and second bomb/arrow digits
  LDA $04 : AND.w #$00FF : ORA.w #$2400 : STA.l !HudYCount
  LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA.l !HudYCount+2

  .ammo_done
  SEP #$20
  LDA.l HudCache_Init : CMP.b #$5A : BNE .draw_keys
  LDA.l $7EF36F : CMP.l HudCache_Keys : BEQ .keys_done

  .draw_keys
  LDA.l $7EF36F : STA.l HudCache_Keys
  REP #$30
  LDA.w #$007F : STA $05

  ; Load number of Keys Link has
  LDA.l $7EF36F : AND.w #$00FF : CMP.w #$00FF : BEQ .no_keys
    JSL HexToDecimal_long
  .no_keys

  REP #$30

  ; The key digit, which is optionally drawn.
  ; Also check to see if the key spot is blank
  LDA $05 : AND.w #$00FF : ORA.w #$2400 : STA.l !HudKeyDigit
  CMP.w #$247F : BNE .keys_non_blank
    ; If the key digit is blank, also blank out the key icon.
    STA.l !HudKeyIcon
    BRA .keys_done

  .keys_non_blank
    LDA.w #$2071 : STA.l !HudKeyIcon

  .keys_done
  SEP #$20
  LDA.l HudCache_Init : CMP.b #$5A : BEQ .exit
  LDA.l HudCache_MaxHP : BEQ .exit
  REP #$20
  LDA.l $7EC744 : CMP.l HudCache_HeartTile0 : BNE .exit
  SEP #$20
  LDA.b #$5A : STA.l HudCache_Init

  .exit
  PLP ; Restore caller's P register
  RTL
}
