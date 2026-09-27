# Menu page 3 ("Masks & Rings"): feasibility study (2026-09-27)

**Verdict: FEASIBLE WITH WORK.** Use a hub layout, `Masks&Rings <- Items -> Quest`.
The item page stays in the left half. Only the right half is repainted, in one
2 KB upload, before each scroll away from Items. No new VRAM or CHR is needed.
Masks remain ordinary Y items. The largest risk is `$0202`: it is the item-grid
cursor, the equipped Y item, and the key that mask, HUD, and name code all read.

This was a read-only study. Nothing was built, run, or edited. In this file,
VERIFIED means the claim was read in source or in the usdasm disassembly.
INFERRED means it is reasoning or rough arithmetic that no runtime test confirmed.

---

## 1. BG layer, tilemaps, upload path

- VERIFIED: the menu draws on BG3. Vanilla sets `BG3SC=$63`: the map base is word
  `$6000` and the map is 64x64 tiles, four 2 KB screens
  (`usdasm/bank_02.asm` `$02C513`). `BG34NBA=$07` puts BG3 CHR at word `$7000`
  (`$02C51D`). Oracle has no write to BG3SC or BG34NBA (grep).
- VERIFIED: screen map, set through `TilemapUpload_HighBytes`
  (`bank_00.asm` `$009888`-`$0098AA`) plus the Oracle patch at `Menu/menu.asm:14-15`:

  | `$0116` | VRAM word | Screen | Contents |
  |---|---|---|---|
  | (HUD, `$16`) | `$6040` | top-left | live HUD. `menu.asm:24` patches the address; `$14A` bytes come from `$7EC700` (`$008B6B`-`$008B84`) |
  | `$24` | `$6400` | top-right | HUD copy, written only at close (`menu.asm:582`) |
  | `$22` | `$6800` | bottom-left | item page (`menu.asm:176`, `:326`) |
  | `$23` | `$6C00` | bottom-right | quest page (`menu.asm:148`) |

  The open animation ends at `$EA=$FF12` (`menu.asm:201`), which shows the bottom
  row of screens. The H-scroll `$E4` wraps at 512 (`menu_scroll.asm:42`).
- VERIFIED upload path: the menu fills the WRAM buffer `$1000-$17FF`, sets
  `$0116` and `$17=1`, and NMI then runs `NMI_UploadTilemap`
  (`bank_00.asm` `$008CB0`-`$008CD8`): one DMA of `$0800` bytes from `$7E1000`
  to `VMADDH=table[$0116]`, followed by `STZ $1000`.
- VERIFIED: in NMI, `NMI_DoUpdates` (tilemap DMA) runs at `$00813E`, before the
  BG3 scroll registers are written at `$0081BA`. An upload and a scroll change made
  in the same frame therefore take effect together.
- **Upload per page turn: one 2 KB DMA, done once before the scroll.** The 256 px
  scroll takes 32 frames at 8 px per frame (`menu_scroll.asm:15,20`) and uploads
  nothing.
- **It fits in one vblank, so no split is needed.** VERIFIED by existing code: the
  item screen already uploads 2 KB every frame (`menu.asm:325-327`), and so do the
  submenus (`:677`, `:948`). INFERRED arithmetic: 2048 B x 8 master cycles is
  about 12 scanlines. Add OAM (about 3 lines), CGRAM when `$15` is set (about 3),
  and the HUD (about 2), for about 20 of the roughly 37 NTSC vblank lines.
- There is no third horizontal slot. The top-right screen `$6400` is idle while the
  menu is open, but it is diagonal to the item page, so it could only serve a
  vertical page flip (see §5 alternatives).
- VERIFIED gotcha: `Menu_ItemScreen` calls `Menu_CheckHScroll`, keeps running, and
  then writes `$0116=$22` at its end (`menu.asm:278`, `:326`). The repaint therefore
  cannot happen inside `Menu_CheckHScroll`. It must happen on the first frame of the
  scroll state (`$05`).
- VERIFIED: the buffer is a single buffer. Today `Menu_ScrollTo` redraws the quest
  page into it only after the scroll ends (`menu.asm:339`). The right-half VRAM
  still holds the quest page that was uploaded at open.

## 2. Icon graphics (CHR)

- VERIFIED: all menu, HUD, and icon tiles come from one BG3 2bpp CHR block.
  Vanilla `LoadDefaultGraphics` loads sheets `$6A`, `$6B`, and `$69` to word `$7000`
  (`bank_00.asm` `$00E322`-`$00E339`). Each sheet is 1024 words
  (`$00E33B`-`$00E368`), so tiles `$000-$17F` fill `$7000-$7BFF`.
- VERIFIED: tiles `$180-$1FB` (`$7C00-$7FEF`) hold the dialogue glyphs, written by
  `NMI_UploadBG3Text` (`$008CE4`-`$008D0A`). BG3 CHR is full: 384 icon/HUD tiles
  plus 128 text tiles.
- VERIFIED: Oracle ASM contains no BG3 CHR load (grep found no `$7000` VRAM writes
  and no `LoadDefaultGraphics` hook). The edited art lives in the base ROM sheets.
- **The CHR is loaded once and shared by every page.** The menu never swaps CHR.
  The ring submenu loads no graphics: it only copies `ring_box.tilemap`
  (`menu_draw.asm:715-745`) and draws `RingGFX` entries (`menu_gfx_table.asm:142-149`,
  tiles `$049/$04A` in 7 palettes).
- **Page 3 needs no new tiles if it reuses the current icons, and nothing can be
  evicted.** Every icon page 3 needs is already resident: Deku `$066/$076`, Bunny
  `$069/$079`, Stone `$0B4-$0C5`, Wolf `$086/$087`, Zora `$088/$089`
  (`menu_gfx_table.asm:38-44`, `:109-120`), rings `$049/$04A`, and book
  `$0A5/$0A6/$0D8/$0D9` (`:81-82`).
- INFERRED: the free-tile count is unknown. A static scan of `Menu/` references
  about 282 of the 384 tiles. Code-computed tiles (digits, hearts, dialogue frame)
  hide the rest, so the true free count is lower. `Menu/tilemaps/sheet.png` is
  from 2021 and stale. Confirm with a sheet dump in yaze before adding any new
  art.
- INFERRED option for new page-3-only art: the dialogue glyph area (tiles
  `$180-$1FB`) is idle while the menu is open, because messages and the menu are
  exclusive submodules of `$0E`. One 2 KB DMA at menu open could load up to 126
  tiles there, and the next message re-renders the glyphs. Before relying on this,
  check at runtime that no persistent BG3 element uses those tiles.

## 3. Mask behaviour today

- VERIFIED: masks are ordinary Y items in grid row 4, cursor IDs `$13-$17`
  (`menu_select_item.asm:13-14`, `:44`, `:75-79`, `:248-252`):

  | Mask | Cursor ID | Item routine |
  |---|---|---|
  | Deku | `$13` | `$11` |
  | Zora | `$14` | `$0F` |
  | Wolf | `$15` | `$08` |
  | Bunny | `$16` | `$10` |
  | Stone | `$17` | `$13` |

  `Menu_Exit` copies `Menu_ItemIndex[$0202]` to `$0303` and `$0304`
  (`menu.asm:459-460`).
- VERIFIED: equipping a mask is equipping its item routine, and that routine runs
  while the mask is the Y item:
  - Deku: `org $07A64B` (`deku_mask.asm:37-62`).
  - Zora: `$07A569` (`zora_mask.asm:53`).
  - Wolf: shares the Ocarina routine and branches on `$0202 != $0D`
    (`wolf_mask.asm:48-70`).
  - Each routine calls `Link_TransformMask` (`mask_routines.asm:300-331`), which
    transforms on an R press read from `$F6` bit `$10` (`:1362-1373`). It sets
    `!CurrentMask=$02B2` and `$BC` and reloads the palette. Y then fires the form
    ability through the same routine (Deku bubble or hover, Wolf dig).
- VERIFIED: code that reads `$0202` as "which mask is equipped":
  - `bunny_hood.asm:71-73`: the run speed needs `$0202==$16`.
  - `minish_form.asm:31-37`: the Minish form is blocked while `$0202` is in `$13..$16`.
  - `mask_routines.asm:265`: on menu exit, the form is kept only when `$0202==$13`.
    Wolf and Bunny therefore reset on every exit. This may be a latent bug; no
    runtime check was made.
  - `menu.asm:104`: `$15` Wolf shovel cleanup.
  - HUD item box: `Menu_AddressIndex-1,X` and `HudItems` `$0DFA93`, 24 entries
    (`menu_hud.asm:253-256`, `:316-324`, `:427-438`).
  - Item names (`menu_text.asm:184-186`, `:203-209`).
- **What changes if masks are chosen on page 3.** Masks stay Y items, so R, Y, and
  every form ability keep working unchanged. This meets the owner's constraint. A
  page-3 selection writes `$0202` to the mask's ID. Two ID plans:
  - **Plan A, for the prototype: keep IDs `$13-$17`.** The item page hides row 4 and
    its navigation skips those slots. No mask or HUD code changes. Row 4 then
    cannot take new items without new IDs.
  - **Plan B, final: renumber the masks to `$19-$1D`.** Row-4 IDs `$13-$17` go to
    new items, and the grid arithmetic (`+6`, wrap at 24,
    `menu_select_item.asm:87-157`) stays valid. Every table indexed by `$0202`
    must grow to 29 entries:
    - `Menu_ItemIndex`, `Menu_AddressIndex`, and `Menu_AddressLong`
    - `Menu_ItemCursorPositions`: the item page must not draw a cursor for
      IDs above `$18`, or it writes to a wild buffer offset
      (`menu.asm:320`, `menu_select_item.asm:165`).
    - `HudItems`: growing it at `$0DFA93` overwrites vanilla `$0DFAC3+`, which
      INFERRED is dead since the vanilla menu was replaced. Moving it to
      bank `$2E` is safer.
    - `Menu_ItemNames`

    Update the checks at `bunny_hood.asm:72`, `minish_form.asm:33-37`,
    `mask_routines.asm:265`, and `menu.asm:104`. Auto-equip scans stop at 24
    (`menu_select_item.asm:291`), which is harmless.
- VERIFIED: page-state fixes needed in both plans:
  - `Menu_Exit` sets `$0303` only when `$E4==0` (`menu.asm:455`). It needs a
    logical-page check so a mask chosen on page 3 is equipped.
  - `Menu_CheckHScroll` treats A as "close menu" (`menu_scroll.asm:9`). Page 3
    needs its own L/R and Start handler so A can equip.

## 4. Palette constraints

- VERIFIED: `Menu_Palette` is 32 words copied to `$7EC502`, which covers BG3
  palettes 0-7 at 3 colors each (`menu_palette.asm:15-45`, `menu.asm:166-172`).
  All 8 palettes are used: icons use `$20xx` through `$3Cxx`. `Menu_Exit` restores
  `$7EC300` to `$7EC500` for 64 bytes (`menu.asm:464-469`).
- During the scroll both halves are on screen, so page 3 must use the same 8 BG3
  palettes. No per-page CGRAM swap is possible without the neighbouring page
  changing color. The mask and ring icons already fit: rings use palettes 0-5
  and 7 (`menu_gfx_table.asm:143-149`), masks palettes 0/3/4/5.
- VERIFIED: mask forms recolor OBJ palette rows (for example `$7EC6E0`,
  `wolf_mask.asm:18`), not BG3, so there is no conflict.

## 5. Size, prototype, and alternatives

**Recommended design (hub):** add a logical-page variable in `MenuScrollLevelH`
(`$7E0731`). It is declared but unused (`Core/symbols.asm:7`; grep found one hit).
- L on Items: state `$05` first draws page 3 into the buffer, uploads `$23`, then
  scrolls left. The right half appears from the left through the wrap.
- R on Items: the same flow with the quest page.
- On page 3 or Quest, L or R returns to Items. The left half was never overwritten,
  so `Menu_ScrollFrom` stays as it is (`menu.asm:382-390`).
- Close from page 3 already works, because the `$24` HUD copy covers `$E4=$100`.
- A true 3-cycle carousel is not recommended: pages would migrate between halves,
  and all 11 hard-coded `$22`/`$23` sites plus every submenu would have to become
  side-aware.

**Size (INFERRED):**
- Files: `Menu/menu.asm`, `menu_scroll.asm`, `menu_draw.asm`,
  `menu_select_item.asm`, `menu_text.asm`, `Config/feature_flags.asm`, and an
  optional new tilemap. Plan B adds `menu_hud.asm`, `Masks/mask_routines.asm`,
  `bunny_hood.asm`, and `minish_form.asm`.
- Code: about 400-700 bytes for Plan A, plus about 150-250 bytes of tables for
  Plan B. A new background adds 2 KB of `incbin`, or 0 bytes if page 3 reuses
  `ring_box.tilemap`.
- Bank `$2D` has about 2.4 KB free. `DungeonLocationNames` sits at `$2D:D16E` with
  296 entries of 32 bytes each, ending near `$2D:F66E` (`Roms/oos168x.sym`, built
  09-19). Put the page-3 code and tilemap in bank `$2E`, which has about 19 KB
  free (last label `$2E:AD7B` plus 2 KB), with a `PHB/PHK/PLB` JSL wrapper as
  `Menu_DrawJournal` does (`menu_journal.asm:585-587`).

**Risk areas:**
1. `$0202` has three roles, and every table indexed by it must grow in step with
   the IDs.
2. The side checks `$E4`/`$E5` mean "quest page" today (`menu.asm:455`, `:1063`,
   `:1076`).
3. The `$0116` override at the end of `Menu_ItemScreen`.
4. Ring SRAM alias: with `!ENABLE_RING_SRAM_RELOCATE=0`, the rings read side-quest
   and Pineapple bytes (`Core/sram.asm:282-283`, `:482-486`). The page-3 ring row
   would show wrong rings until the flag is on.
5. The comment "Ring box graphics don't display correctly on right side"
   (`menu.asm:372-373`). INFERRED cause: `Menu_RingBox` always uploads `$22`
   (`:948`). The right-half page must upload `$23`.

**Minimum prototype:** add `!ENABLE_MENU_PAGE3_STUB` (default 0). With it on, L on
the item page draws the `ring_box.tilemap` background, `Menu_DrawMagicRingsInBox`,
and 5 mask icons through `DrawMenuItem`, uploads `$23`, and scrolls. The stub state
handles only L/R (back to Items) and Start (close), with no cursor and no equip.
Estimate: about 150 bytes. It proves:
- The repaint happens before the scroll with no tearing.
- The page arrives from the correct side.
- Closing from page 3 works.
- `$0202` and `$0303` do not change.

Verify in Mesen2 with the BG3 tilemap viewer at `$6C00`, a mid-scroll screenshot,
and a memory read of `$0202/$0303` after close.

**Alternatives if this is blocked:**
- (a) Masks move to page 3; rings stay a Y submenu. This is the smallest page 3.
- (b) One "Masks" grid slot opens a mask submenu, following the Magic Bag pattern
  (`menu.asm:653-680`). Each mask keeps its own ID, so abilities are unchanged.
  This differs from the rejected single slot cycled with L/R.
- (c) Bottles move to a submenu, which frees 3 slots. It uses the same Magic Bag
  pattern and changes `BottleIndex`.
- (d) Page 3 lives in the top-right screen `$6400` and is shown with a vertical
  flip. No repaint is needed, but it does not feel like a carousel, and the close
  path must recopy the HUD.

## 6. Addendum A: open the Journal from page 3

- VERIFIED: the Journal already opens from several places:
  - X on Items (`menu.asm:247-258`)
  - X on Quest, which uploads `$23` (`:354-370`)
  - X in the ring box (`:1022-1033`)
  - A on the Book slot `$0E` (`:232-243`)
- The only blocker is the return path: `Menu_Journal` chooses where to return
  from `$E5` (`menu.asm:1059-1071`, `:1076-1082`). From page 3 it would redraw the
  quest page. Change it to dispatch on the logical page.
- The cheapest version is an X shortcut on page 3, about 25 bytes copied from the
  stats-screen block. A cursor spot needs a "JOURNAL" tile using `BookGFX` and an
  A handler, about 40-80 bytes. Keep the `Menu_CheckJournalUnlocked` gate
  (`menu.asm:1134-1145`). Risk: low.

## 7. Addendum B: equipment switching on page 3 (shield and armor)

- VERIFIED SRAM: `Shield=$7EF35A` (1-3) and `Armor=$7EF35B` (0-2)
  (`Core/sram.asm:326-327`). Vanilla stores only the current level. There is no
  "owned" record.
- New data: one "owned" byte, for example max armor in bits 0-1 and max shield in
  bits 4-5, in `FreeBlock_Items $7EF310-$33F` (`Core/sram.asm:718`).
  - **Save compatibility:** old saves read 0. On menu open, self-heal with
    `owned = max(owned, current)`.
  - Every shield-steal path must lower "owned" too, or the menu lets the player
    re-equip a stolen shield. Known paths: `anti_kirby.asm:284-287` writes
    `$7EF35A`, and the vanilla Like Like does the same.
  - `CheckPalaceItemPossession` must read "owned" (`menu_draw.asm:600-624`).
- Shield change: call `DecompressShieldGraphics` (`$00D308`) and then
  `Palettes_Load_Shield` (`$1BED29`), the same pair vanilla item receipt calls
  (`bank_09` `$098792-$098796`). INFERRED safe while paused: it decompresses into
  `$7F4000-$7F4BFF`, clear of the bestiary data at `$7F5000`.
- Armor change: write `$7EF35B`, then `JSL $1BEDF9` (Oracle hook to the mask-aware
  `Palette_ArmorAndGloves`, `mask_routines.asm:16-20`, `:97-150`). Damage is read
  directly from `$7EF35B` at `$06F3FB`, `$07BD2E`, `$07C14F`, `$07C76B`,
  `$07CB69`, `$07D23D`, `$089907`, and `player2.asm:851`, so a lower armor takes
  effect immediately.

## 8. Addendum C: tunic color separate from armor, and 2-player

- VERIFIED: the palette is chosen from `$7EF35B` in these places:
  1. `Palettes_Load_LinkArmorAndGloves` `$1BEDF9`. Oracle's `.original_palette`
     runs `LDA $7EF35B : JSL $1BEDFF` (`mask_routines.asm:143-147`).
  2. `RefreshLinkEquipmentPalettes_sword_and_mail` `$0ED6C8`, called from `$0ABA67`
     and `$0AE146`. It bypasses the `$1BEDF9` hook. Oracle already hooks
     `$0ED745` (`time_system.asm:664`).
  3. The GBC form (`gbc_form.asm:10-11`).
  4. P2 (`player2.asm:957-980`).
- The block after `.part_two` in `mask_routines.asm:~157-185` also reads
  `$7EF35B`, but INFERRED it is unreachable because it has no label.
- A cosmetic "tunic color" needs:
  - One SRAM byte, for example `TunicColor` in `FreeBlock_Items`. Value 0 means
    "follow armor", so old saves are unchanged; 1-3 means green, blue, or red.
  - Replacing the palette-side reads at sites 1-3 with a helper that returns the
    tunic color, or the armor value when the byte is 0. Damage keeps reading
    `$7EF35B`, so armor and color separate cleanly.
- P2 conflict (VERIFIED by comment and table; memory note `native-2p-poc`): P2 has
  no OBJ palette row of its own. It shares Link's row 7 and bakes its tunic into
  WRAM tiles by remapping indices 9-12 to other row-7 colors (`player2.asm:950-956`,
  selector table about `:1063-1073`). `P2_TunicVariant` chooses red, or blue when
  P1 wears red mail, from P1's `$7EF35B`.
- Consequences:
  - Switch that read to P1's tunic-color byte.
  - Add a P2 color byte, WRAM or SRAM.
  - P2 can only pick colors that exist in P1's current row-7 palette, so each
    player cannot pick freely. Fully independent colors would need a free OBJ
    palette row, and the memory note says none exists.

## 9. Not verified (needs runtime or a tool)

- The real number of free BG3 CHR tiles (needs a yaze sheet dump).
- Whether tiles `$180-$1FB` are really idle while the menu is open.
- That the pre-scroll repaint is tear-free on hardware and on the SNES Classic.
- The Wolf and Bunny form reset on menu exit (`mask_routines.asm:265`).
- That `$0DFAC3-$0DFAFC` is dead in Oracle.
- The bank `$2D` and `$2E` free space in the current build: the symbol file is
  from 09-19.
