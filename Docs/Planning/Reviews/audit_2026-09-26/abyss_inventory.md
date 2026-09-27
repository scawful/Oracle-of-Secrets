# Eon Abyss early segment + Dream Hut: factual inventory

Date: 2026-09-26. Read-only. ROM: `Roms/oos168.sfc` (base). No builds, no emulator.
Tags: **V** = VERIFIED (command or file:line given). **D** = DOC-ONLY (doc claim, not checked in data/code).
Coordinates are world pixels unless noted.

## 0. Method and caveats

1. Map data: `z3ed overworld-describe-map --rom=Roms/oos168.sfc --screen 0xNN --format json` for all $40-$7F (V).
2. Sprites: `z3ed overworld-list-sprites` merges all game-state lists, so duplicates are not simultaneous.
   I parsed the ZSOW v3 expanded tables directly (state-1 table PC `0x141578`, state-2 table PC `0x1416B8`,
   pointers into bank $09, 3 bytes `y,x,id`, per yaze `zelda3/overworld/overworld.h:174-175` and
   `overworld_sprite_io.cc:21`). Sprites exist only on parent maps.
3. Which list is live (V, `Overworld/ZSCustomOverworld.asm:5299-5319`, `Overworld/time_system.asm:256-269`):
   phase = `Oracle_CheckIfNight`; GameState 2 daytime -> offset $0140 = **"state 1" list**;
   night (hour >= 18 or < 6) -> offset $0280 = **"state 2" list**. So the early Abyss (GameState 2) uses
   list 1 by day and list 2 by night.
4. Custom vs vanilla sprite identity: `Sprites/sprite_registry_ids.asm` plus `!SPRID` in each sprite file (V).
   Vanilla names from yaze `zelda3/sprite/sprite_names.h`.
5. Expanded messages in `Data/dialogue/expanded_messages.json` are dictionary-compressed (`[D:xx]`).
   Readable text below comes from `Core/messages.org` (source), not decoded ROM bytes. Mark: **V(source)**.
6. Area labels come from `Docs/Dev/Planning/oracle_resource_labels.json` (generated label file) = D.

## 1. Early-segment code gates (V)

- `LoadDarkWorldIntro` `Overworld/overworld.asm:94-116`: outdoor load with GameState==2 and `OOSPROG < 2`
  forces `$7EF3CA=$40` (Dark World). So the lock ends at `OOSPROG>=2`, not at escape (decisions.org
  "respawn lock until escape" says this must change; not yet changed).
- Banishment toggles the world flag: `Sprites/Bosses/kydrog.asm:153` (`$7EF3CA ^= $40`).
- Storm/rain never shows in the Abyss; readers check `$8A` bit 6: `Overworld/storm.asm:23-24` (flag
  `!ENABLE_PART0_STORM = 0`, `Config/feature_flags.asm`).
- Lightning palette flash only on dark DM maps $73/$75/$7D: `Overworld/overworld.asm:165-170`.
- Feature flags touching this segment (V, `Config/feature_flags.asm`): `!ENABLE_EON_OWL_ONE_SHOT = 0`,
  `!ENABLE_ORIGINS_MINISH_PUZZLE = 0`, `!ENABLE_ORACLE_ARRIVAL_SEQUENCE = 0`. No `*DREAM*` flag exists.

## 2. Arrival / Temporal Pyramid: parent $40 (Large: $40,$41,$48,$49)

1. Data (V, describe-map): Large, parent $40. area_graphics $41, area_palette $1E, main_palette $02 ($40)
   / $01 ($41,$48,$49), animated_gfx $5B, no overlay, bg color $0000, sprite gfx set $18.
   area_music `[09,00,00,00]`. Label file: $09 = "Dark World (Eon Abyss)" (D).
   Caveat: origins plan says the GameState-2 music byte reads $00 (D, `origins_plan_2026-09-24.md:267`);
   which of the 4 bytes the DW uses at GameState 2 is not verified.
   Name "Temporal Pyramid": label file (D) and msg $1AA (V source).
2. Sprites (V, table parse):
   - Day (list 1): `$62` Master Sword pedestal (704,160); `$B3` inscription/plaque (704,192);
     `$5A` squirrels (608,240),(784,240),(624,256),(768,256); `$59` birds (624,160),(784,160),(640,128),(768,128);
     `$B8` **Eon Zora** (576,848) listed twice (same coords; duplicate entry in ROM).
   - Night (list 2): `$62`, `$B3`, `$5A` (624,256),(800,240), `$59` (640,128),(768,128). **No Eon Zora at night.**
   - Custom: `$B8` = Zora dispatcher (`Sprites/sprite_registry_ids.asm:45`); with WORLDFLAG!=0 it runs
     Eon Zora (`Sprites/NPCs/zora.asm:62-66`). `$B3` = Oracle pedestal plaque hook (`Sprites/Objects/pedestal.asm:8-9`),
     its area switch handles only $1E/$36/$5E (`pedestal.asm:36-38`), so on $40 it falls through (behavior not traced).
     `$62`, `$59`, `$5A` vanilla. No enemies on $40.
3. Messages:
   - Eon Zora: `$1AA` when `AreaIndex==$40` (`Sprites/NPCs/eon_zora.asm:95-96`). V(source) `Core/messages.org`:
     "Ah, traveler from beyond... you stand near the Temporal Pyramid, a place of beginnings. / The Shrine of
     Origins lies west, a place of ancient power. / Only the small may tread its paths, for the secrets within
     are hidden from the unworthy. / Legends say it grants a relic that holds form steady even in this unstable realm."
     Caveat: the Zora stands at (576,848) = screen $49; the check uses `$8A`. Whether `$8A` holds the parent ($40)
     on a large area is not runtime-verified.
   - Area sign message id = `$A7` (V describe-map) = "Vasu's Ring Shop" (V `z3ed message-read --id 0xA7`).
     Any sign tile on $40 would show that text. Sign tile presence not checked.
   - Telepathy `$35` (Impa) and `$36` (Maku/voice) (V ROM): `$36` already contains the approved landmark rewrite
     "It rests in the Shrine of Origins, west of the great pyramid." (matches
     `Reviews/approved_dialogue_rewrites_2026-09-26.md:110`). Trigger site not traced here.
4. Entrances on $40 (V describe-map + `z3ed dungeon-get-entrance`):
   - `$76` (192,224) -> room $05 Shrine of Origins, music $14, dungeon id $10.
   - `$2D` (880,256) -> room $14 (label "Dragon Ship (Big Key)" D).
   - `$63` (448,608) -> room $116 (label "Pyramid Fairy" D).
   - `$69` (448,64) -> room $10E ("Cave" D).
   - `$18` (960,656) -> room $23 ("Dragon Ship (West Exit to Balcony)" D).
   - Exit records onto $40: rooms $20, $23, $14, $05 (Origins exit Link at (200,216)).
   Whether $2D/$63/$69/$18 are physically reachable in the early segment: not verified (no collision check).
5. Origins interior (V from prior review, re-checked): room $05 has 0 sprites (`z3ed dungeon-list-sprites --room 0x05`).
   `$38` sign (V ROM): "Shrine of Origins / The True Hero will reveal the path forward by pressing the R Button on
   the magical pot." `$5E` Pearl (V ROM): "You found the Moon Pearl! This protects The Hero from the changing effects
   of the Eon Abyss."

## 3. Owl map $50 (Small) and neighbour $51

1. $50 data (V): Small, gfx $43, palette $1E, main pal $01, sprite gfx $0C, music `[09,...]`, sign msg $A7.
   Label file: "Shrine of Courage" (D) - consistent with entrance below.
2. Sprites (V): `$0A` Eon Owl at (352,1280), same in day and night lists (custom, `Sprite_EonOwl = $0A`).
   Code (V `Sprites/NPCs/eon_owl.asm:72-85,113-125`): despawns if `Sword >= 1`; proximity trigger (distance < $28)
   shows `$E6` and flies away. One-shot flag `EonOwlFlags` $7EF3A7 bit 1 is written only if
   `!ENABLE_EON_OWL_ONE_SHOT` (currently 0) -> the Owl reappears on every visit until the sword.
   `!EonOwl_ArrivalTalked` (bit 0, `Core/sram.asm:500`) is defined but **used nowhere** (grep).
3. `$E6` (V ROM, approved rewrite already applied): "Hoo hoo! We meet again, [L]. / This realm is a mirror, a
   reflection of forgotten dreams and shadowed paths. / Though you hold the Moon Pearl, beware, for not all is as it
   seems in the Abyss. / Deep in the Forest of Dreams, just south of here, a sword awaits you, a blade to cut through
   the veil of deception. But remember, young one, even the sharpest blade cannot sever all bonds. Hoo hoo!"
   Note: "We meet again" assumes an earlier Owl meeting that does not exist yet (new first Owl line is approved but
   not written, `approved_dialogue_rewrites_2026-09-26.md:12,113-120`).
4. Entrance (V): `$0C` (224,1072) -> room $53 (label "Shrine of Courage", dungeon id $09, music $11); exit record room $53.
5. $51 (Small, east of $50; sign msg $C2) sprites (V): day `$B9` Bully & ball kid (576,1168), `$0B` Cucco (576,1328);
   night `$B9` only. `$B9` is vanilla (DW bully pair); it shows vanilla-slot messages `$15B-$15E` (V ROM):
   - `$15B` (ball): "Oh? Who are you, stranger? This place is the Eon Abyss, a dark reflection of Kalyxo. / Evil magic has
     twisted it into something sinister and dangerous. / The Golden Power here can change your form to match your heart
     and mind. / I am always changing my mind, so I turned into a ball... But if you find a magic stump, / use the R
     button to shrink and navigate through small spaces in this dark world."
   - `$15C` (ball, post-Pearl): "You didn't change your shape? Well, don't forget, if you want to get through tight
     spaces, stand on a stump and press the R button!"
   - `$15D` (bully): "What do you want?! Do you have something to say to me, little hero?! / I came here seeking the power
     of the Golden Triforce, but now I'm stuck in this twisted form! If I only had the Moon Pearl from the Shrine of
     Origins, I could regain my true shape! I've got every reason to be stressed out! So back off! Go away!"
   - `$15E` (bully, post-Pearl): "WOW! Your shape didn't change! You got the Moon Pearl, huh?"
   Speaker-to-ID mapping follows vanilla bully/ball behavior; no Oracle hook found (grep `15B-15E` in ASM: none).

## 4. Forest of Dreams: parent $58 (Large: $58,$59,$60,$61)

1. Data (V): Large, gfx $43, palette $1E, main pal $01, sprite gfx $13, music `[09,...]`.
   Sign msg `$AF` = "This is the Village Of Outcasts. People without Rupees are not welcome here." (V ROM) - a vanilla
   leftover; any sign here would show it. Name "Forest of Dreams": label file (D) + `$E6` text (V).
2. Sprites (V):
   - Day: `$AA` Like Like x5 (384,1776),(832,2304),(256,2208),(288,1888),(768,2096); `$0E` (640,2496);
     `$52` Collectible (688,1904); `$14` (544,2368).
   - Night: `$AA` x4 (416,1776),(160,1872),(912,1968),(400,2464); `$52`; `$14`; `$1D` Darknut (768,2112).
   - Custom: `$52` Collectible (`Sprites/Objects/collectible.asm`, `!SPRID $52`): on `$8A==$58` draws SwordShield,
     despawns if `$7EF359` (sword) != 0 (`collectible.asm:39-41,65-70`). `$14` = Business Scrub file; WORLDFLAG!=0 runs
     **Eon Scrub** (`Sprites/Enemies/business_scrub.asm:40-56`). `$0E` = Piratian (`Sprites/NPCs/piratian.asm` `!SPRID $0E`;
     vanilla $0E is Snapdragon). `$1D` = Darknut (custom). `$AA` Like Like vanilla.
3. Messages: none from placed NPCs traced (Piratian/Eon Scrub text not checked). Sword pickup = receipt $00 (per review, D).
4. Entrances (V): `$4A` (896,1872) -> room $107 (label "Library"; room $107 holds `$F0` subtype 2 = Librarian, V scan);
   `$66` (448,2032) -> room $122 ("Smith" D); `$62` (688,2432) -> room $114 ("Fairy Fountain" D). Reachability not verified.
   Note: entrance `$4A` is also placed on $4F (3840,832) (V warps list).
5. Gossip Stone GS05 "Forest of Dreams" (D, `Docs/World/Lore/gossip_stones.md:191`, msg `0x1C4` per line 339).
   Data: no gossip-stone sprite on $58, and `0x1C4` in `Core/messages.org` is "Goron Mine Guard (Enough Meat)".

## 5. Return path: $6A (Small)

1. Data (V): Small, gfx $41, palette $1C, main pal $01, sprite gfx $26, music `[09,...]`, sign msg $A7.
   No entrances, no exit records on $6A. Label file calls it "Forest of Dreams" (D).
2. Sprites (V): day `$A8` Anti-Kirby (1456,2800), `$55` Fireball Zora (1296,2992), `$EB` Heart Piece (1120,2624) x2;
   night `$A8` (1456,2832), `$EB`. `$A8` custom (`Sprite_AntiKirby`); `$55`, `$EB` vanilla.
3. Return mechanism: D. `Overworld/storm.asm:13-16` comment: "portal home (DW $6A -> LW $2A, same spot in the other
   world = mirror-warp path; MirrorWarp_Initialize $02B236 sets $7EF3CA to $00)". `world_map_diagram.md:188` and
   `intro_flow_analysis.md:108` say the same. The portal object (tile or sprite) was not identified in data.
4. Messages: none identified.

## 6. Other Abyss maps adjacent to the early route (data V; reachability NOT verified)

Grid: row = (id-$40)/8, col = id%8. $58 block is rows 3-4, cols 0-1; $6A is row 5 col 2. Candidates between them:
- `$5A` (row 3 col 2, gfx $2F, pal $10): day `$0D` Buzzblob x2, `$55`, `$00` Raven, `$08` Octorok(custom); night `$08`,`$00`,`$55`.
- `$62` (row 4 col 2): day `$0D`, `$08` x2, `$00`, `$14` (Eon Scrub); night `$08`, `$00`.
- `$68` (row 5 col 0): day `$1D` Darknut, `$08`; night `$A8`, `$1D`, `$08` x4 (dup coords).
- `$69` (row 5 col 1): day `$08`, `$55`, `$1D`; night `$A8`, `$1D`, `$55` x2.
- `$42` (row 0 col 2, east of $41): day `$EB`, `$B8` (Eon Zora -> `$1AF` Fortress/quest hint, `eon_zora.asm:103-104`).
- `$52` (row 1 col 2): day `$0D` x2, `$55`, `$08`; night `$08`, `$00`.
The "scrub then Anti-Kirby" order before the return is not established by data (scrub is on $58/$62, Anti-Kirby on $6A/$68/$69).
Custom `$08` = Octorok (`Sprites/Enemies/octorok.asm` `!SPRID $08`); `$71` Leever alt is Abyss-specific
(`Sprites/Enemies/leever.asm:1,7`) but no `$71` on the maps above.

## 7. Dream Hut and dream code

1. Maple sprite (V): `$F0` subtype 1 (`Sprites/sprite_registry_ids.asm:11`; `Sprites/NPCs/mermaid.asm` Prep sets
   SprMiscE=1 for subtype 1; handler `Sprites/NPCs/maple.asm`). Included in build: `Sprites/all_sprites.asm:50-52`.
2. Placement (V, scanned rooms $000-$127 with `z3ed dungeon-list-sprites`): Maple is only in **room $0F**
   at tile (22,20). Room $0F: blockset 3, spriteset 13, palette 22, 37 objects, south exit door, no stairs/chests
   (`z3ed dungeon-describe-room --room 0x0F`). Label "Empty Clone" (D).
3. Where the hut is (V, raw ROM tables): exit record 69 = room $0F -> OW map **$5D** (exit table PC `0x15D8A`/`0x15E28`;
   describe-map $5D exit at (2952,1648)). $5D = row 3 col 5, Small, gfx $41, pal $11, sprite gfx $13, sign msg $A7.
   $5D sprites: day `$0E` Piratian, `$71` Leever(alt), `$AA` Like Like; night `$71`, `$B3` x2.
4. **Blocking gap (V):** the door on $5D is entrance `$68` (2944,1648), and entrance `$68` loads **room $11A**
   (raw entrance room table PC `0x14813`: `$68 -> $011A`; label "Bonzai Cave"). Room $11A has the same
   blockset/spriteset/palette as $0F but **0 sprites**. No entrance in `$00-$84` targets room $0F. So in current data
   the hut door opens an empty copy; Maple's room is only an exit target. Needs a runtime check before any work.
   Entrance `$68` music = $19 (label "Zelda Rescue", D).
5. Maple messages (V source `Core/messages.org:1784-1860`, ROM entries exist in expanded JSON at index id-$18D):
   - `$1B3` Intro (solicited, `maple.asm:22`): "Oho-ho! Well, look who stumbled into my Dream Hut! Checking out the Eon
     Abyss, are we? / I'm Maple, yes, that Maple! We've crossed paths before in Holodrum... or was it Labrynna? / Heh, you
     were a bit of a pest on my broom route, but I see you've come a long way! / > Long time no see, Maple! / What is this
     place? / I'll come back later."
   - `$1B4` (`maple.asm:48`): "Ha! You do remember me! Guess all that chasing around left an impression. / Now I've set up
     shop here, diving into dreams instead of crashing brooms. / Feel free to let me poke around in your mind... it could be
     fun! / > Sure, show me a dream. / How does this work? / Maybe some other time."
   - `$1B5` (`maple.asm:64`): "This little haven? I call it my Dream Hut... not super original, but it gets the point
     across. / Here, I tug at the edges of your mind, spinning dreams that might reveal something useful. / Just beware-the
     Eon Abyss takes its toll, even in sleep. Weird stuff happens here."
   - `$1B6` (`maple.asm:93`): "Ooh, I can sense it... that pendant you have there. Perfect for dream-weaving! / Close those
     eyes, Hero. Let's see what secrets are lurking in that noggin of yours."
   - `$1B7` (`maple.asm:104`): "Huh, no spark in sight. No Pendant, no dream, sorry! But hey, roam the Abyss a bit. / I'm sure
     you'll scrounge one up eventually... And when you do, I'll be here, waiting."
   - `$1B8` (`maple.asm:71`): explains three pendants resonate and invoke "dreams of the past"; ends "the Master Sword
     awaits... only the one with the pendants can awaken it... think of these little dreams as stepping stones to your destiny!"
6. Dream code (V `Sprites/NPCs/maple.asm`):
   - State machine lines 1-123: dialogue branches via `$1CE8`; `Maple_Idle` also writes `$7EF351=2` and SFX `$012F=$1B`
     when `$7EF351 != 0` (lines 25-28, purpose not traced).
   - Pendant check lines 76-100: picks the highest pendant whose dream bit is clear. Bits: Wisdom $01 / Power $02 /
     Courage $04 in `Pendants` $7EF374 and `Dreams` $7EF410 (`Core/sram.asm:150-160,384-387`). `CurrentDream` = $0426
     (`Core/symbols.asm:36`). Bug-risk: the Courage branch falls through to `.power` when Courage dream is done even if the
     Power pendant is absent.
   - Sleep: `Sprite_PutLinkToSleep` lines 125-141 (`$5D=$16`, blanket ancilla, blinding-white palette filter).
   - `Link_HandleDreams` lines 143-176 sets the Dreams bit, then `Link_WarpToRoom` (lines 178-194) does a mode `$15`
     room warp to: Wisdom -> room **$61**, Power -> room **$00**, Courage -> room **$31**.
     Room data (V dungeon-list-sprites/describe): $61 = 105 objects + sprite `$76` (vanilla Zelda id), label "Hyrule Castle
     (Main Entrance)"; $00 = sprite `$7A` (= Kydreeok id in Oracle), tag1 61, label "Ganon"; $31 = **0 objects, 0 sprites**.
   - No return-from-dream code exists (no cleanup, no warp back to the hut).
   - `Link_FallIntoDungeon` (lines 197-215) lists entrances $78 "Deku Dream", $79 "Castle Dream", $7A, $81; it has no caller (grep).
   - `Sprites/NPCs/hyrule_dream.asm`: Zelda/King/Soldier poses chosen by ROOM ($51 king, $60 soldier); called from
     Farore's indoor path (`Sprites/NPCs/farore.asm:87-105`). Static idle frames only.
   - `org $068C9C : db $0F` (`maple.asm:217-219`) patches a vanilla sprite property byte (not traced).
7. Planned but absent (V by grep): `Core/dream_sequences.asm`, `Core/dream_triggers.asm`, `Core/sleep_handler.asm`,
   `%SetDreamState` macros, `$7EF411` DREAM_STATE_ACTIVE hooks at `$07:82DA`/`$07:83D0` - all only in
   `Docs/Planning/Plans/dream_sequences.md` (D). `FreeBlock_Dreams` $7EF412-$7EF4FD is free (`Core/sram.asm:741-746`).

## 8. Gaps: docs vs data

1. D says Owl appears twice (decisions.org "Abyss segment" item 2); data has one Owl ($50) and no arrival line or ID.
2. `$E6` opens "We meet again" but no earlier Abyss meeting exists yet.
3. D (`world_map_diagram.md:186-187`, `intro_flow_analysis.md`) says equipment on $60 and "Bunny Link"; data: collectible
   is on parent $58 at (688,1904) (inside the $58 quadrant). Review 2026-09-23 already notes NES/GBC presentation, not bunny.
4. D (`QuestFlow.md:19`) "Exit the pyramid to arrive in the Forest of Dreams" - data: Origins exits onto $40; the forest is $58.
5. Origins plan (D) lists `$B8` Eon Zora in the night list; data: night list for $40 has no `$B8`. Day list has it twice.
6. Beat sheet line 147 (D): "Maple's Dream Hut sits in the open Abyss - visible early". Data: hut exterior is on $5D
   (east-centre Abyss, row 3 col 5), not on the early route; its door loads empty room $11A, not Maple's room $0F.
7. Beat sheet Dream 1 = "The Sealing War / Kydrog-was-the-guardian" (D). Code: Wisdom dream warps to a Hyrule-Castle-labelled
   room $61 with a Zelda sprite; Courage dream room $31 is empty; no dream content, text, or exit exists.
8. `$1B8` promises the Master Sword via pendants; canon (beat sheet) uses the Meadow Blade and essences - story mismatch
   (not a data bug; flag for the dialogue audit).
9. Sign messages: DW default sign text `$A7` = "Vasu's Ring Shop"; $58 sign text `$AF` = "Village Of Outcasts". Harmless only
   if no sign tiles exist on those maps (not checked).
10. GS05 Forest of Dreams gossip stone (D) has no sprite on $58 and its listed ID `0x1C4` is a Goron message.
11. Return portal $6A -> $2A: only code comments/docs; object not located in map data.
12. Respawn lock ends at `OOSPROG>=2` (V code) vs decided "until escape" (D decision) - known, open.
13. `EonOwlFlags` bit 0 (ArrivalTalked) reserved, unused; one-shot flag OFF.

## 9. Suggested runtime checks (not run)

1. Enter the $5D hut door in Mesen: confirm room $11A (empty) vs $0F (Maple).
2. Stand near the $40 Eon Zora (screen $49) and confirm `$1AA` shows (tests `$8A` on large areas).
3. Walk $58 -> $6A and record the portal object and any collision blocks; confirm which maps in section 6 are on the route.
