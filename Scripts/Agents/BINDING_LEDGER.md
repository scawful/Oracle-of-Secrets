# Item-binding RAM ledger (QUEUE159)

- Branch: `cursor/binding-ledger-20261115` @`cdc868a7`
- Counts: {"$0202": 110, "$0303": 13, "Menu_Exit": 5, "$0304": 14}
- SavedY: NOT FOUND as label SavedY in *.asm — see NOTES
- Never oos-rc-play; not committed to master directly.

## $0202 (110)

| File | Line | Routine | Access | Width | Text |
|---|---|---|---|---|---|
| `Core/credits_text.asm` | 356 | `?` | ref | ? | `dw $0202 ; row 294 EVOLVINGFETUS` |
| `Core/part00.asm` | 52 | `?` | ref | ? | `!HouseVillager_Msg_B   = $0202` |
| `Overworld/sky_overlay_transition.asm` | 64 | `LyraOverlay_FinishTransition` | ref | ? | `PEA.w $0202 : PLB : PLB` |
| `Dungeons/sky_room_sky_data.asm` | 72 | `SkyRoom_Clouds` | ref | ? | `dw $0202 : db $94` |
| `Menu/menu_select_item.asm` | 137 | `Menu_FindNextItem` | read | 16 | `LDA.w $0202 : INC A` |
| `Menu/menu_select_item.asm` | 141 | `Menu_FindNextItem` | write | 16 | `STA.w $0202` |
| `Menu/menu_select_item.asm` | 166 | `Menu_FindPrevItem` | read | 16 | `LDA.w $0202 : DEC A : BNE .no_reset` |
| `Menu/menu_select_item.asm` | 169 | `Menu_FindPrevItem` | write | 16 | `STA.w $0202` |
| `Menu/menu_select_item.asm` | 192 | `Menu_FindNextDownItem` | read | 8 | `LDA.w $0202 : CLC : ADC.b #$06` |
| `Menu/menu_select_item.asm` | 196 | `Menu_FindNextDownItem` | write | 16 | `STA.w $0202` |
| `Menu/menu_select_item.asm` | 221 | `Menu_FindNextUpItem` | read | 8 | `LDA.w $0202 : SEC : SBC.b #$06` |
| `Menu/menu_select_item.asm` | 227 | `Menu_FindNextUpItem` | write | 16 | `STA.w $0202` |
| `Menu/menu_select_item.asm` | 279 | `Menu_InitItemScreen` | read | 8 | `LDY.w $0202 : BNE .all_good` |
| `Menu/menu_select_item.asm` | 292 | `Menu_InitItemScreen` | write | 8 | `STY.w $0202` |
| `Menu/menu_select_item.asm` | 299 | `Menu_InitItemScreen` | write | 16 | `STZ.w $0202` |
| `Menu/menu_select_item.asm` | 365 | `GotoNextItem_Local` | read | 8 | `LDA $0202 : INC A : CMP.b #$18 : BCC .dont_reset` |
| `Menu/menu_select_item.asm` | 369 | `GotoNextItem_Local` | write | 8 | `STA $0202` |
| `Menu/menu_select_item.asm` | 375 | `DoWeHaveThisItem_Override` | read | 8 | `LDY.w $0202 : LDX.w Menu_AddressLong-1, Y` |
| `Menu/menu_select_item.asm` | 420 | `SearchForEquippedItem_Override` | write | 8 | `STZ $0202 : STZ $0203 : STZ $0204` |
| `Menu/menu_select_item.asm` | 429 | `SearchForEquippedItem_Override` | read | 16 | `LDA.w $0202 : BNE .alreadyEquipped` |
| `Menu/menu_select_item.asm` | 431 | `SearchForEquippedItem_Override` | write | 8 | `LDA.b #$08 : STA $0202` |
| `Menu/menu_select_item.asm` | 492 | `Menu_SplitValidateSelection` | read | 16 | `LDA.w $0202 : JSR .owned : BCS .done` |
| `Menu/menu_select_item.asm` | 499 | `Menu_SplitValidateSelection` | write | 8 | `STY.w $0202` |
| `Menu/menu_select_item.asm` | 565 | `Menu_CustomGridTryPageTurn` | read | 16 | `LDA.w Menu_CustomGridItems,X : CMP.w $0202 : BEQ .scan` |
| `Menu/menu_select_item.asm` | 595 | `Menu_CustomGridMove` | read | 16 | `LDA.w Menu_CustomGridItems,X : CMP.w $0202 : BEQ .located` |
| `Menu/menu_select_item.asm` | 619 | `Menu_CustomGridMove` | write | 16 | `STA.w $0202` |
| `Menu/menu_draw.asm` | 1125 | `Menu_CheckItemHasSubmenu` | read | 16 | `LDA.w $0202  ; Current cursor position/item index` |
| `Menu/menu_equipment.asm` | 177 | `Menu_Equipment_Select` | write | 8 | `LDA.b #$0D : STA.w $0202            ; normal Y item, independent of mask` |
| `Menu/menu_text.asm` | 210 | `Menu_DrawItemName` | read | 8 | `LDY.w $0202` |
| `Menu/menu_text.asm` | 219 | `Menu_DrawItemName` | read | 8 | `LDA.w $0202 : CMP.b #$1B : BCC .not_new_item` |
| `Menu/menu_text.asm` | 230 | `Menu_DrawItemName` | read | 16 | `LDA.w $0202 : AND.w #$00FF : CMP.w #$001C : BNE .new_name_done` |
| `Menu/menu_text.asm` | 243 | `Menu_DrawItemName` | read | 8 | `LDA.w $0202 : CMP.b #$1A : BNE .not_goldstar_cell` |
| `Menu/menu_text.asm` | 247 | `Menu_DrawItemName` | read | 16 | `LDA.w $0202` |
| `Menu/menu_text.asm` | 249 | `Menu_DrawItemName` | read | 8 | `LDA.w $0202 : CMP.b #$03 : BEQ .goldstar` |
| `Menu/menu_text.asm` | 264 | `Menu_DrawItemName` | read | 16 | `LDA.w $0202 : BEQ .no_items` |
| `Menu/menu_hud.asm` | 147 | `HUD_Update` | read | 8 | `LDX   $0202 : LDA $7EF33F, X : AND.w #$00FF` |
| `Menu/menu_hud.asm` | 177 | `HUD_Update` | read | 8 | `LDX   $0202 : LDA $7EF33F, X : AND.w #$00FF` |
| `Menu/menu_hud.asm` | 280 | `HUD_UpdateItemBox` | read | 8 | `LDX $0202 : BEQ .no_equipped_item` |
| `Menu/menu_hud.asm` | 392 | `HUD_ItemBoxItem` | read | 8 | `LDX.w $0202` |
| `Menu/menu_page3.asm` | 169 | `Menu_Page3_ItemScreen` | read | 8 | `LDA.w $0202 : CMP.b #$19 : BNE .items` |
| `Menu/menu_page3.asm` | 170 | `Menu_Page3_ItemScreen` | write | 8 | `LDA.b #$13 : STA.w $0202` |
| `Menu/menu_page3.asm` | 364 | `Menu_Page3_GridFilter` | read | 16 | `LDA.w $0202` |
| `Menu/menu_page3.asm` | 440 | `Menu_Page3_InitCursor` | read | 16 | `LDA.w $0202` |
| `Menu/menu_page3.asm` | 524 | `Menu_Page3_Select` | write | 16 | `STA.w $0202                          ; the Y item, as in the grid` |
| `Menu/menu_page3.asm` | 659 | `Menu_Page3_Draw` | read | 16 | `LDA.w $0202` |
| `Menu/menu_page3.asm` | 789 | `Menu_Page3_Draw` | read | 16 | `LDA.w $0202` |
| `Menu/menu_page3.asm` | 1000 | `Menu_PortalRod_CellToItem` | read | 8 | `LDA.w $0202 : CMP.b #$13 : BNE .done` |
| `Menu/menu_page3.asm` | 1001 | `Menu_PortalRod_CellToItem` | write | 8 | `LDA.b #$19 : STA.w $0202` |
| `Menu/menu.asm` | 159 | `Menu_InitGraphics` | read | 16 | `LDA.w $0202` |
| `Menu/menu.asm` | 294 | `Menu_CheckForSpecialMenus` | read | 8 | `LDA.w $0202 : CMP.b #!MENU_STATE_SCROLL_TO : BNE +` |
| `Menu/menu.asm` | 301 | `Menu_CheckForSpecialMenus` | read | 8 | `LDA.w $0202 : CMP.b #!MENU_STATE_SONG_MENU : BNE ++` |
| `Menu/menu.asm` | 311 | `Menu_CheckForSpecialMenus` | read | 8 | `LDA.w $0202 : CMP.b #!MENU_STATE_JOURNAL : BNE ++` |
| `Menu/menu.asm` | 368 | `Menu_ItemScreen` | read | 16 | `LDA.w $0202 : BNE .have_item` |
| `Menu/menu.asm` | 378 | `Menu_ItemScreen` | read | 16 | `LDA.w $0202 : BEQ .do_no_input` |
| `Menu/menu.asm` | 435 | `Menu_ItemScreen` | read | 16 | `LDA.w $0202 : JSR Menu_Page3_IsMaskItem : BCS .no_grid_cursor` |
| `Menu/menu.asm` | 437 | `Menu_ItemScreen` | read | 16 | `LDA.w $0202 : ASL : TAY` |
| `Menu/menu.asm` | 546 | `Menu_CheckBottle` | read | 8 | `LDA.w $0202 : CMP.b #$06 : BNE .not_first` |
| `Menu/menu.asm` | 550 | `Menu_CheckBottle` | read | 8 | `LDA.w $0202 : CMP.b #!MENU_STATE_MAGIC_BAG : BNE .not_second` |
| `Menu/menu.asm` | 554 | `Menu_CheckBottle` | read | 8 | `LDA.w $0202 : CMP.b #$12 : BNE .not_third` |
| `Menu/menu.asm` | 558 | `Menu_CheckBottle` | read | 8 | `LDA.w $0202 : CMP.b #$18 : BNE .not_any` |
| `Menu/menu.asm` | 588 | `Menu_Exit` | read | 8 | `LDX $0202` |
| `Items/fishing_rod.asm` | 27 | `LinkItem_FishingRodAndPortalRod` | read | 8 | `LDA.w $0202 : CMP.b #$1B : BNE .not_byrna` |
| `Items/fishing_rod.asm` | 35 | `LinkItem_FishingRodAndPortalRod` | read | 8 | `LDA.w $0202 : CMP.b #$19 : BEQ .own_cell_portal_rod` |
| `Items/bombchu.asm` | 70 | `Bombchu_AddBomb` | read | 8 | `LDA.w $0202 : CMP.b #$1C : BEQ .bombchu` |
| `Items/switch_hook.asm` | 161 | `SwitchHook_Init` | read | 8 | `LDA.w $0202 : CMP.b #$1D : BNE .done` |
| `Items/switch_hook.asm` | 231 | `SwitchHook_Tick` | read | 8 | `LDA.w $0202 : CMP.b #$1D : BNE .cancel` |
| `Items/switch_hook.asm` | 651 | `SwitchHook_ContextValid` | read | 8 | `LDA.w $0202 : CMP.b #$1D : BNE .no` |
| `Items/byrna.asm` | 51 | `Byrna_IsSelected` | read | 8 | `LDA.w $0202 : CMP.b #$1B` |
| `Items/goldstar.asm` | 56 | `HookMaskCheck` | read | 8 | `LDA $0202 : AND.w #$00FF : CMP.w #$0003 : BNE .not_mask` |
| `Items/goldstar.asm` | 327 | `LinkOAM_GoldstarWeaponTiles` | read | 16 | `LDA.w $0202 : AND.w #$00FF : CMP.w #$0003 : BEQ +` |
| `Items/goldstar.asm` | 964 | `BeginGoldstarOrHookshot` | read | 8 | `LDA.w $0202 : CMP.b #$1A : BEQ .select_goldstar` |
| `Items/goldstar.asm` | 1010 | `ApplyGoldstarDamageClass` | read | 8 | `LDA.w $0202 : CMP.b #$03 : BNE .return` |
| `Masks/wolf_mask.asm` | 117 | `LinkItem_ShovelAndFlute` | read | 8 | `LDA $0202 : CMP.b #$0D : BNE .use_wolf_mask` |
| `Masks/mask_routines.asm` | 346 | `LinkState_ResetMaskAnimated` | read | 8 | `LDA.w $0202 : CMP.b #$17 : BEQ .keep_55` |
| `Masks/mask_routines.asm` | 369 | `LinkState_ResetMaskAnimated` | read | 8 | `LDA.w $0202 : SEC : SBC.b #$13 : BEQ .no_transform` |
| `Masks/mask_routines.asm` | 443 | `Link_TransformMask` | read | 8 | `CLC : ADC.b #$12 : CMP.w $0202 : BNE .ignore` |
| `Masks/mask_routines.asm` | 517 | `StoneMask_CheckR` | read | 8 | `LDA.w $0202 : CMP.b #$17 : BNE .done` |
| `Masks/mask_routines.asm` | 587 | `MaskControl_CheckYItem` | read | 8 | `CLC : ADC.b #$12 : CMP.w $0202 : BEQ .done` |
| `Masks/mask_binding.asm` | 52 | `MaskBinding_MigrateSelection` | read | 8 | `LDA.w $0202 : CMP.b #$1E : BNE +` |
| `Masks/mask_binding.asm` | 56 | `MaskBinding_MigrateSelection` | read | 8 | `LDA.w $0202 : CMP.b #$13 : BCC .done` |
| `Masks/mask_binding.asm` | 84 | `MaskBinding_MigrateSelection` | write | 8 | `STX.w $0202` |
| `Masks/mask_binding.asm` | 96 | `MaskBinding_IsOcarina` | read | 8 | `LDA.w $0202 : CMP.b #$0D : RTL` |
| `Masks/mask_binding.asm` | 213 | `MaskBinding_Tick` | read | 8 | `LDX.w $0202 : CPX.b #Menu_ItemIndex_End-Menu_ItemIndex : BCS .no_item` |
| `Masks/minish_form.asm` | 42 | `LinkState_CheckForMinishForm` | read | 8 | `LDA $0202` |
| `Masks/bunny_hood.asm` | 79 | `LinkState_BunnyHoodRun` | read | 16 | `LDA.w $0202              ; check the current item` |
| `Sprites/NPCs/garo.asm` | 70 | `Garo_Healing` | read | 8 | `LDA.w $0202 : CMP.b #$0D : BNE .done ; logical Ocarina` |
| `Sprites/Objects/pedestal.asm` | 17 | `CheckForBook` | read | 8 | `LDA.w $0202 : CMP.b #$0F : BNE .not_holding_book` |

## $0303 (13)

| File | Line | Routine | Access | Width | Text |
|---|---|---|---|---|---|
| `Core/link.asm` | 134 | `?` | ref | ? | `LinkItemY    = $0303 ; Currently equipped item on the Y button` |
| `Menu/menu.asm` | 589 | `Menu_Exit` | write | 16 | `LDA.w Menu_ItemIndex, X : STA $0303 : STA.w $0304` |
| `Items/ice_rod.asm` | 38 | `LinkItem_IceRod` | read | 8 | `LDA $0303 : CMP #$06 : BEQ $01` |
| `Items/byrna.asm` | 50 | `Byrna_IsSelected` | read | 8 | `LDA.w $0303 : CMP.b #$0D : BNE .return` |
| `Masks/mask_binding.asm` | 218 | `MaskBinding_Tick` | read | 8 | `CMP.w $0303 : BEQ .done` |
| `Masks/mask_binding.asm` | 219 | `MaskBinding_Tick` | write | 16 | `STA.w $0303` |

## $0304 (14)

| File | Line | Routine | Access | Width | Text |
|---|---|---|---|---|---|
| `Menu/menu.asm` | 589 | `Menu_Exit` | write | 16 | `LDA.w Menu_ItemIndex, X : STA $0303 : STA.w $0304` |
| `Items/ice_rod.asm` | 41 | `LinkItem_IceRod` | read | 8 | `LDA $0304 : CMP #$06 : BEQ $01` |
| `Items/switch_hook.asm` | 162 | `SwitchHook_Init` | read | 8 | `LDA.w $0304 : CMP.b #$0E : BNE .done` |
| `Items/switch_hook.asm` | 232 | `SwitchHook_Tick` | read | 8 | `LDA.w $0304 : CMP.b #$0E : BNE .cancel` |
| `Items/switch_hook.asm` | 650 | `SwitchHook_ContextValid` | read | 8 | `LDA.w $0304 : CMP.b #$0E : BNE .no` |
| `Items/goldstar.asm` | 54 | `HookMaskCheck` | read | 8 | `LDA $0304 : AND.w #$00FF : CMP.w #$000E : BNE .not_mask` |
| `Items/goldstar.asm` | 325 | `LinkOAM_GoldstarWeaponTiles` | read | 16 | `LDA.w $0304 : AND.w #$00FF : CMP.w #$000E : BEQ +` |
| `Items/goldstar.asm` | 1008 | `ApplyGoldstarDamageClass` | read | 8 | `LDA.w $0304 : CMP.b #$0E : BNE .return` |
| `Masks/mask_routines.asm` | 345 | `LinkState_ResetMaskAnimated` | read | 8 | `LDA.w $0304 : CMP.b #$13 : BNE .clear_55` |
| `Sprites/NPCs/garo.asm` | 71 | `Garo_Healing` | read | 8 | `LDA.w $0304 : CMP.b #$08 : BNE .done ; effective flute action` |

## SavedY

No `SavedY` label in Oracle `*.asm`. Likely vanilla name only — search usdasm / menu restore of prior item if needed.

## Menu_Exit (5)

| File | Line | Routine | Access | Width | Text |
|---|---|---|---|---|---|
| `Menu/menu_page3.asm` | 23 | `?` | ref | ? | `;   Menu_Exit copies it to $0303 when the menu closes.` |
| `Menu/menu.asm` | 129 | `Menu_Entry` | call/ref | ? | `dw Menu_Exit               ; 0A` |
| `Menu/menu.asm` | 569 | `Menu_Exit` | label | ? | `Menu_Exit:` |
| `Items/special_soaring.asm` | 25 | `SpecialSoaring_Complete` | ref | ? | `; Normal Menu_Exit calls this after restoring the prior module. Do not` |
| `Masks/mask_routines.asm` | 341 | `LinkState_ResetMaskAnimated` | ref | ? | `; changed, take it off with the poof and sound (Menu_Exit sets $0304 = $0303,` |

## Notes
- Full comment hits retained in `BINDING_LEDGER.json`.
- `$0202` = selected Y-item; `$0303` = effective action (mask binding); `$0304` = in-flight action bookkeeping (`Masks/mask_binding.asm`).
- `Menu_Exit` in `Menu/menu.asm` is the menu close state that copies page-3 selection into `$0303` / syncs `$0304`.
