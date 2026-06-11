# Oracle of Secrets — Disassembly Reference

This reference is loaded into the z3cli system prompt and cached by the LLM's KV cache.
Keep it stable (edits invalidate the cache for all subsequent turns).

## ROM Bank Layout

| Bank | Address | Contents |
|------|---------|----------|
| $00 | $008000 | Game core, main loop, NMI, module dispatcher |
| $01 | $018000 | Dungeon engine — room loading, object drawing |
| $02 | $028000 | Overworld/underworld transitions, module loaders |
| $05 | $058000 | Specialized sprites (cutscenes, minigames, traps) |
| $06 | $068000 | Main sprite engine, shared helpers, damage/collision |
| $07 | $078000 | Player (Link) engine — movement, physics, items |
| $08 | $088000 | Ancilla engine (projectiles, effects) |
| $09 | $098000 | Ancilla spawning, item receipt logic |
| $0A | $0A8000 | World map, flute menu |
| $0B | $0B8000 | Overworld environment helpers |
| $0D | $0D8000 | Link animation/OAM data (not code) |
| $0E | $0E8000 | Tile properties, font, credits engine |
| $1B | $1B8000 | Overworld entrances, pits, palettes |
| $1D-$1E | | Boss/advanced enemy AI |
| **$20** | $208000 | **OOS: Expanded Music** |
| $28 | $288000 | OOS: ZSCustomOverworld |
| $2B | $2B8000 | OOS: Items |
| $2C | $2C8000 | OOS: Dungeons |
| $2D | $2D8000 | OOS: Menu |
| $2E | $2E8000 | OOS: HUD |
| $2F | $2F8000 | OOS: Expanded Messages |
| $30-$32 | $308000 | OOS: Sprites |
| $33-$3B | $338000 | OOS: Mask forms (Moosh, Deku, Zora, Bunny, Wolf, Minish, GBC) + routines |
| $34 | $348000 | OOS: Time system, overlays, GFX |
| $3A | $3A8000 | OOS: Mask routines, Deku Bubble ancilla |
| $40-$41 | $408000 | OOS: World maps (LW/DW) |

## Key WRAM Variables

| Address | Label | Description |
|---------|-------|-------------|
| $7E0010 | MODE | Main game module index (Module_MainRouting dispatcher) |
| $7E0011 | SUBMODE | Sub-state for current module |
| $7E001A | FRAME | Frame counter (increments each non-lag frame) |
| $7E001B | INDOORS | 0=outdoors, 1=indoors |
| $7E002F | DIR | Link facing direction (0=U, 2=D, 4=L, 6=R) |
| $7E005D | LINKDO | Link's action state machine ID |
| $7E008A | OWSCR | Current overworld screen ID |
| $7E00A0 | ROOM | Current underworld room ID |
| $7E02E0 | BUNNY | Bunny form flag |
| $7E031F | IFRAMES | Invincibility timer after damage |

### Custom WRAM ($7E0730+ MAP16OVERFLOW region)

| Address | Label | Description |
|---------|-------|-------------|
| $7E0730 | MenuScrollLevelV/H | Menu scroll position |
| $7E0737 | MusicNoteValue | Current music note |
| $7E0739 | GoldstarOrHookshot | Hookshot vs custom Goldstar |
| $7E0745 | FishingOrPortalRod | Fishing Rod vs Portal Rod |
| $7E0746-$7E0754 | DBG_* | Debug bridge: reinit, warp arm/request/coords/status |

### Controllers

| Address | Label | Bits |
|---------|-------|------|
| $F0 | RawJoypad1L | BYSTUDLR |
| $F2 | RawJoypad1H | AXLR---- |
| $F4 | PressPad1L | BYSTUDLR (newly pressed) |
| $F6 | PressPad1H | AXLR---- (newly pressed) |
| $3C | BFLAG | ssss tttt (spin attack / sword timer) |

## Sprite System

16 sprite slots. Each property is a 16-byte array indexed by slot X.

| Address | Label | Purpose |
|---------|-------|---------|
| $0D00/$0D10 | SprY/SprX | Position low bytes |
| $0D20/$0D30 | SprYH/SprXH | Position high bytes |
| $0D40/$0D50 | SprYSpeed/SprXSpeed | Velocity |
| $0D80 | SprAction | Action jump table index |
| $0D90 | SprFrame | GFX frame index |
| $0DC0 | SprGfx | Graphics set |
| $0DD0 | SprState | State (0x00=dead, 0x08=init, 0x09=active, 0x0A=carried, 0x0B=stunned) |
| $0E20 | SprType | Sprite ID |
| $0E30 | SprSubtype | Subtype |
| $0E50 | SprHealth | HP |
| $0E60 | SprGfxProps | nios pppt (impervious, shadow, palette, nametable) |
| $0DF0-$0F80 | SprTimerA-F | Countdown timers (A-C: -1/frame, D-E: -1/frame, F: -2/frame) |
| $0F50 | SprProps | DIWS UUUU (boss death, impervious, water, shadow) |
| $0F60 | SprHitbox | ISPH HHHH (ignore collisions, stasis, persist, hitbox) |

### Sprite struct (asar)

`struct Sprite $7E0BA0` — 60 fields including .yl/.xl/.yh/.xh, .vy/.vx, .action, .frame, .state, .type, .hp, .props, .z/.vz/.sub_vz, misc_a-g, TimerA-E, death_timer, etc.

### Key Sprite Functions

| Address | Function | Purpose |
|---------|----------|---------|
| $06E416 | Sprite_PrepOamCoord | Set OAM coordinates for draw |
| $06F864 | Sprite_OAM_AllocateDeferToPlayer | Draw above/below Link |
| $06F2AA | Sprite_CheckDamageFromPlayer | Check player attacks hitting sprite |
| $06F121 | Sprite_CheckDamageToPlayer | Check sprite contact damage |
| $06EA12 | Sprite_ApplySpeedTowardsPlayer | Set velocity toward player (A=speed) |
| $06EAA0 | Sprite_DirectionToFacePlayer | Returns relative position in $0E/$0F |
| $06E496 | Sprite_CheckTileCollision | Tile collision, sets $0E70,X (----udlr) |
| $1DF65D | Sprite_SpawnDynamically | Spawn sprite (A=ID, set $00-$08 for coords) |
| $0683E6 | CheckIfHitBoxesOverlap | Hitbox overlap test ($00-$0B params) |
| $06DBF0 | Sprite_PrepAndDrawSingleLarge | Draw 16x16 sprite |
| $06DBF8 | Sprite_PrepAndDrawSingleSmall | Draw 8x8 sprite |
| $0DBA71 | GetRandomInt | Random number in A |
| $008781 | UseImplicitRegIndexedLocalJumpTable | Local jump table dispatch |

## SRAM — Progression & Items

| Address | Label | Description |
|---------|-------|-------------|
| $7EF340 | Bow | Bow type (0-4) |
| $7EF343 | Bombs | Bomb count |
| $7EF347-$7EF358 | Masks | ZoraMask, BunnyHood, DekuMask, StoneMask, WolfMask, RocsFeather |
| $7EF359 | Sword | Sword type (0-4) |
| $7EF35A | Shield | Shield type (0-3) |
| $7EF360 | Rupees | Rupee count |
| $7EF36C | MAXHP | Max health (1 heart = 8 HP) |
| $7EF36D | CURHP | Current health |
| $7EF374 | Pendants | Bitfield (Courage, Power, Wisdom) |
| $7EF37A | Crystals | Bitfield (bit 0=D1 Mushroom Grotto ... bit 6=D7 Dragon Ship) |
| $7EF3C5 | GameState | Main progression state |
| $7EF3C6 | OOSPROG2 | Secondary progression `.fbh .zsu` |
| $7EF3D6 | OOSPROG | Primary progression `.fmp h.i.` |
| $7EF398 | Scrolls | Lore scroll bitfield `.dgi zktm` (7 dungeons) |
| $7EF39B | MagicBeanProg | Bean growth `.dts fwpb` |
| $7EF410 | Dreams | Three Dreams bitfield `.cpw` |

## Time System

`struct TimeState $7EE000` — Hours (0-$17), Minutes (0-$3B), Speed, RGB color values for day/night tinting.

## Key Vanilla Entry Points

| Routine | Address | Bank | Purpose |
|---------|---------|------|---------|
| Reset | $008000 | $00 | Boot entry |
| Module_MainRouting | $0080B5 | $00 | Module dispatcher (reads MODE) |
| Interrupt_NMI | $0080C9 | $00 | Per-frame: input, DMA, OAM |
| Sprite_Main | $068328 | $06 | Master sprite loop (16 slots) |
| Sprite_ExecuteSingle | $0684E2 | $06 | Per-sprite state dispatcher |
| SpriteModule_Initialize | $06864D | $06 | Init jump table by sprite type |
| Link_Main | $078000 | $07 | Player logic entry |
| Link_ControlHandler | $07807F | $07 | Player state machine (reads LINKDO) |
| Underworld_LoadRoom | $01873A | $01 | Room loading entry |
| Module06_UnderworldLoad | $02821E | $02 | Transition into dungeon |
| Module07_Underworld | $0287A2 | $02 | Underworld main loop |
| Module08_OverworldLoad | $0283BF | $02 | Overworld loading |

## OOS Namespace & Build

All custom code is in the `Oracle` namespace (Oracle_main.asm). Modules are conditionally included via `!DISABLE_*` flags. Build: `./Scripts/Build/build_rom.sh 168`.

Module include order: Core (link, sram, symbols, message, progression) -> Music -> Overworld -> Dungeon -> Sprites -> Masks -> Items -> Menu -> Patches.

## Conventions

- Addresses: `$XXXX` for WRAM/direct page, `$XXXXXX` for ROM (bank:offset)
- Sprite slot index: register X (0-15)
- 65816 width: SEP #$20 = 8-bit A, REP #$20 = 16-bit A; SEP #$10 = 8-bit X/Y, REP #$10 = 16-bit X/Y
- Hook pattern: `pushpc` / `org $target` / `JSL NewCode` / `pullpc` then `NewCode:` with matching instruction length + `RTL`
- Macros and helpers in `Util/macros.asm`
- Flag checks: `SRAMCheckFlag`, `SRAMSetFlag`, `SRAMClearFlag` macros
