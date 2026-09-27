# Overworld warp tile scan (tile behavior 0x4B), Roms/oos168.sfc, 2026-09-26

Read-only static scan. No build, no emulator. Nothing in the repo was edited.

## 1. Method and evidence

1. **Behavior dispatch (VERIFIED).** The overworld tile behavior jump table starts at `$07DA2A`. Entry 0x4B (`$07DAC0`) holds `$DEFF` = `TileBehavior_Warp` (usdasm `bank_07.asm:18381`, handler at `:19328`). A scan of all 256 entries in oos168.sfc finds that **only behavior 0x4B** points to `$DEFF`. The handler bytes in the ROM (`a50a0a0a0a0a0c570360`) match vanilla: they set bit `$10` of `$0357`.
2. **Tile type lookup (VERIFIED).** Link's overworld detection `$07DC2A: JSL Overworld_GetTileTypeAtLocation` (ROM `222e8800`) → `$00882E`. That routine reads the map16 word, applies `AND #$01FF` (ROM at `$00886A` = `29ff01`), then reads `LDA.l $0E9459,X` (ROM `bf59940e`).
   - `OverworldTileTypes` is still at `$0E9459` (PC `0x71459`). It is not relocated, but ZScream edited it heavily: about 150 bytes differ from vanilla.
   - Map16 definitions are **relocated** by ZSCustomOverworld: the ROM reads `LDA.l $BD8000,X` (`bf0080bd` at `$008864`), which is PC `0x1E8000`. That region holds 0x1000 tile16s.
   - Oracle ASM does not touch any of this. A grep for `OverworldTileTypes|0E9459|$0357|NOWARP|Mirror_TryToWarp|07D10x|07A95x` in `*.asm` finds no hooks.
3. **Chars with type 0x4B (VERIFIED).** In oos168.sfc the chars are `0x1DF` and `0x1E2`. Vanilla has only `0x1DF`, so `0x1E2` was changed from `0x02` to `0x4B` by a ZScream edit. The stale `oos168x.sfc` has the same two chars; it differs from the base ROM only at char `0x183`.
4. **Tile16s containing those chars (VERIFIED, python scan of `0x1E8000`, char = word & 0x1FF, the same mask the game uses):**

   | tile16 | quadrants with type 0x4B | words |
   |---|---|---|
   | `0x212` | all 4 (TL,TR,BL,BR) | 1ddf 5ddf 9ddf dddf (vanilla warp pad) |
   | `0x94B` | BR | …, 1ddf |
   | `0x9A5` | BL | …, 5ddf, … |
   | `0x9BB` | TL | dddf, … |
   | `0x9BE` | TR | …, 9ddf, … |
   | `0xBA8` | BR | 0fdf → char 0x3DF, **aliases to 0x1DF via AND #$1FF** |
   | `0xBB6` | TR | 0fe2 → char 0x3E2, **aliases to 0x1E2** |

5. **Placement.** For each tile16 above:
   ```
   z3ed overworld-find-tile --rom Roms/oos168.sfc --tile <id> --format json
   ```
   This searches all three worlds (yaze `src/cli/handlers/game/overworld_inspect.cc:298-343`). Map sizes and parents came from `z3ed overworld-describe-map --screen <id>`.
   - Tool caveat: `z3ed overworld-get-tile` cannot be used to check tiles. It parses x/y as hex, rejects values of 64 or more, and indexes the whole-world array (`overworld_commands.cc:43-71`). So destination tiles were **not** checked.
   - The `yaze-editor` MCP also failed: its configured ROM `build/oracle.sfc` does not exist.
6. **Warp trigger rule (VERIFIED, bytes at `$07D104..$07D15B` equal vanilla).** With the `$0357 & $10` bit set, the warp fires only when all of these hold:
   - Link's Y+8 low nibble is below 4 or at least `0xB`, and X low nibble is below 4 or at least `0xC`.
   - `$031F` = 0 (no hurt flash), `$4D` = 0, `$02DB` (NOWARP) = 0.
   - In the overworld it then does `JSR Mirror_TryToWarp` (`$07A95C`, bytes also vanilla).
7. **Destination rule (VERIFIED from code, not runtime-tested).**
   - `Mirror_TryToWarp.overworld` sets `$11=$23` (mirror warp), `$5D=$14`, `$02DB=1`.
   - `MirrorWarp_Initialize` (`$02B217`, usdasm `bank_02.asm:9135-9170`) aborts if `$8A >= $80`, because special areas cannot warp. Otherwise it runs `$7EF3CA ^= $40` and `$8A = ($8A & $3F) | $7EF3CA`.
   - **Result: same area slot in the other world. Link keeps his X/Y (`$20/$22`).** A Light World pad sends Link to the Dark World/Abyss; a Dark World pad sends Link to the Light World.
   - If the destination spot is solid, `LinkState_CrossingWorlds` (`$07A9B1`) mirror-bonks Link back.

Pixel positions below: world pixel = global tile16 × 16, measured within that world's 4096×4096 space. The area grid is (map & 7, (map & $3F) >> 3), and each area is 0x200 pixels.

## 2. Warp tiles found

| # | Map (world) | Tile16 / local (x,y) | World pixel X,Y (top-left of 16×16) | Destination | Status |
|---|---|---|---|---|---|
| 1 | **$6A (Dark/Abyss)**, small | `0x212` at (19,11) | $0530,$0AB0 | **LW $2A** (Maku Tree area), same X/Y | Placement VERIFIED; destination by rule |
| 2 | $03 (Light), small | `0x212` (10,5) | $06A0,$0050 | DW $43 | VERIFIED placement |
| 3 | $07 (Light), small | `0x212` (7,5) | $0E70,$0050 | DW $47 | VERIFIED placement |
| 4 | $07 (Light), small | `0x212` (25,6) | $0F90,$0060 | DW $47 | VERIFIED placement |
| 5 | $11 (Light), small | `0x212` (8,17) | $0280,$0510 | DW $51 | VERIFIED placement |
| 6 | $17 (Light), small | `0x212` (21,25) | $0F50,$0590 | DW $57 | VERIFIED placement |
| 7 | $25 (Light), small | `0x212` (9,11) | $0A90,$08B0 | DW $65 | VERIFIED placement |
| 8 | $37 (Light), large, parent $36 | `0x212` (22,6) | $0F60,$0C60 | DW $77 (parent $76) | VERIFIED placement |
| 9 | $02 (Light), small | 2×2 of `0x94B`(15,6) `0x9A5`(16,6) `0x9BE`(15,7) `0x9BB`(16,7), warp char only on the inner corners | 16×16 hot zone centered on $0500,$0070 (X $04F8-$0507, Y $0068-$0077) | DW $42 | VERIFIED placement (custom ZScream pad using char 0x1DF) |
| 10 | $31 (Light), large, parent $30 | `0xBA8` (20,24), BR 8×8 only | X $0348-$034F, Y $0D88-$0D8F | DW $71 (parent $70) | INFERRED **accidental** warp spot (char 0x3DF aliases to 0x1DF) |
| 11 | $31 (Light), large, parent $30 | `0xBB6` (17,23), TR 8×8 only | X $0318-$031F, Y $0D70-$0D77 | DW $71 | INFERRED **accidental** warp spot (char 0x3E2 aliases to 0x1E2) |

- No `0x4B` tile16 exists in special areas ($80+), and one would not work there anyway (`MirrorWarp_Initialize` aborts).
- DW $6A is the **only** Dark World/Abyss warp tile.
- Vanilla for comparison: `0x212` appears only once in vanilla map data (map $04 at (16,23)). All 8 Oracle `0x212` placements are ZScream edits.
- Whether each Light World pad is reachable or visible is not known (rocks, overlays and collision were not checked).

## 3. Other world-crossing mechanisms

| Mechanism | Code | Behavior | Status |
|---|---|---|---|
| Whirlpool (Deku Leaf file) | `Sprites/Objects/deku_leaf.asm:85-118` (`Whirlpool_Main`) | While underwater (`$0AAB`) on the whirlpool, it inlines a copy of `Mirror_TryToWarp.overworld`: saves portal coords if in DW, `$11=$23`, `$02DB=1`. Same destination rule (world bit toggled, X/Y kept); skipped when `$10=$0B` (special overworld). Canon beat 16 (`story_canon_beat_sheet.md:149`). The task text named `Items/deku_leaf.asm`; the file is actually `Sprites/Objects/deku_leaf.asm`. | VERIFIED code |
| Vanilla mirror portal sprite `$6C` | `$05AF82+` (ROM bytes vanilla) | Touching it in the Light World (after it arms) sets `$11=$23` and warps back to the DW. It also sets `$7B`, so no new portal is spawned. | VERIFIED code |
| Magic Mirror item | vanilla `LinkItem_Mirror` `$07A91A` | Works only in DW (`$8A&$40`) or indoors. Oracle keeps the vanilla code; whether Link can obtain the item was not checked. | VERIFIED code; availability unknown |
| Kydrog banishment (scripted) | `Sprites/Bosses/kydrog.asm:147-172` (`Kydrog_WarpPlayerAway`) | `$7EF3CA ^= $40`, `$A0=$20`, `$010C=$08`, `$10=$15` (Module15, the vanilla Agahnim mirror-warp module). This sends Link into the Abyss. | Code VERIFIED; exact arrival area/coords NOT traced (Module15 uses exit/overworld load data) |
| File load world routing | `Overworld/overworld.asm:94-115` (`LoadDarkWorldIntro`, hook `$028192`) | Forces `$7EF3CA=$40` (Abyss) on continue while GameState=2 and OOSPROG<2. This is the "Abyss respawn lock". | VERIFIED code |
| Blue/Orange portal sprite | `Sprites/Objects/portal_sprite.asm:211-255` | Teleports within the **same** area/world (copies the other portal's X/Y and camera). The `$11=$2A` write is commented out. Not world-crossing. | VERIFIED code |
| Minish portal (stump) | tile type `0x64` (char `0x1D` in the current table); `Docs/World/Features/Masks/Masks.md:97` | A form change (Minish) on R, not a world change. | VERIFIED table; form code not read |
| ZS area load | `Overworld/ZSCustomOverworld.asm:1843-1846`, `:2589-2592` (`!Func02B391=1`, ROM `$02B391` = ZS code) | Calls `Sprite_ReinitWarpVortex` (`$09AF89`, spawns sprite `$6C`) on every Light World load / mirror-warp arrival. | VERIFIED code |

## 4. Return-portal behavior: yes, a Dark World warp tile spawns a stray portal (VERIFIED from code, not runtime-observed)

1. `Mirror_TryToWarp.overworld` (`$07A97E-$07A997`): `LDA $8A : AND #$40 : STA $7B`. If Link is in the DW, it copies Link's `$20/$21/$22/$23` into `$1ADF/$1AEF/$1ABF/$1ACF` (portal Y/X). If Link is in the LW, the copy is skipped (`.no_mirror_portal`).
2. On arrival, `MirrorWarp_LoadSpritesAndColors_Interupt` (ZS `ZSCustomOverworld.asm:2589-2592`) does `LDA $8A : AND #$40 : BNE .darkWorld : JSL Sprite_ReinitWarpVortex`.
3. `InitializeMirrorPortal` (`$09AF89`, usdasm `bank_09.asm:9616-9655`) kills any existing sprite `$6C` and spawns a new `$6C` at (`$1ABF/$1ACF`, `$1ADF+8/$1AEF`).
4. Result: the DW $6A pad → LW $2A leaves a mirror portal at Link's arrival spot on $2A. Touching it warps Link back to the Abyss (`$05AFC6`).
5. The portal is also re-created on every later Light World area load (ZS `:1843`) at the stale `$1ABF/$1ADF`. In vanilla this is normally filtered by area; that was not traced here.
6. The whirlpool path (deku_leaf) copies the same coordinate block, so a DW→LW whirlpool trip also leaves a portal.
7. A LW→DW warp tile trip leaves **no** new portal, because the coordinates are not updated and the DW never spawns sprite `$6C`.
8. `decisions.org:401-410` (DECIDED 2026-09-26) already plans to replace the $6A pad with a scripted sword warp. Any such warp must avoid `Mirror_TryToWarp`, or must skip `Sprite_ReinitWarpVortex` / move sprite `$6C` away, to avoid the portal.

## 5. Not verified

1. **No runtime test.** Nothing was checked in Mesen2: the warp firing, the bonk, the portal spawn, or the $6A→$2A arrival.
2. **Destination tiles** at the same X/Y in the other world are unchecked, so bonk risk is unknown. The reason is the broken `overworld-get-tile` (see step 5 in section 1).
3. **Reachability** of the Light World pads (#2-#9): whether they are covered by rocks or overlays, sit behind collision, or were meant to be warps.
4. **Rows #10/#11 (map $31):** the aliasing is certain from code (`AND #$01FF` at `$00886A`). Whether Link can stand there, and whether the 4-pixel alignment window can be met on a single 8×8 corner, is not.
5. **Kydrog Module15:** the exact arrival area and coordinates were not traced.
6. **Portal filtering:** whether vanilla/ZS suppresses the stale `$6C` portal in unrelated LW areas after `Sprite_OverworldReloadAll` was not traced (vanilla sprite `$6C` has area checks elsewhere).
7. **Scope:** only oos168.sfc was scanned (and the stale oos168x.sfc for the tile-type table). `Roms/Playtest/oos-play.sfc` was not scanned.
