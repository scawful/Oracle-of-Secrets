# ASM lore-comment audit vs. canon (2026-09-26)

Read-only review. No repo file was edited. Canon source: DECIDED entries in
`Docs/Planning/Status/decisions.org` (cited as "DEC: <heading>") and
`Docs/Planning/Reviews/approved_dialogue_rewrites_2026-09-26.md` (cited as "APPROVED").
Scope: `Sprites/ Core/ Items/ Masks/ Dungeons/ Overworld/ Menu/` (excluding `Core/Generated`,
`Util/ZScreamNew`). Skipped by request: `Sprites/NPCs/farore.asm`, `Sprites/Bosses/kydrog.asm` headers.

Method: every file containing `NARRATIVE ROLE` (16 files, 14 in scope), every header comment
block (first 60 lines) mentioning story/character terms (141 files scanned), plus a
body-wide grep of comment lines for villain-chain, dream, seal, name and race terms.

Severity: **C** = contradicts a DECIDED entry; **O** = overstates (presents unconfirmed
agent lore as fact); **S** = stale fact / wrong name / dangling ref.

## Findings by file

### Sprites/NPCs/eon_zora.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 4-7 | `; NARRATIVE ROLE: Friendly NPCs in the Eon Abyss who provide hints,` / `;   lore, and guidance. They are temporally displaced Sea Zoras from` / `;   before the Schism existed, which is why they remain unified while` / `;   their surface kin war.` | O | No DECIDED entry for a "Schism", time displacement or a Zora war. DEC "Yesterwind": residents call the realm Yesterwind; APPROVED 0x0AF sign ("Rest a while, traveler. We all did.") says they are people who came and stayed. DEC "Dialogue style": people of Kalyxo first, no race-centric lore. | `; NARRATIVE ROLE: Friendly Abyss residents (their name for the realm:`<br>`;   Yesterwind) who give location hints and flavor lore. Backstory not`<br>`;   decided; canon: Docs/Planning/Status/decisions.org.` |
| 10-12 | `;   - NOT the same as corrupted River Zoras (those are enemies)` / `;   - Friendly NPCs who remember "what the Zoras were meant to be"` / `;   - Guardians of the boundary between worlds` | C/O | "Guardian" of the prison/boundary is Kydrog (DEC "Villain chain" 2: Farore made Kydrog the prison's guardian). "Corrupted River Zoras" and "what the Zoras were meant to be" are unconfirmed. | `;   - Not the River Zora enemy sprite`<br>(delete the other two lines) |
| 26 | `;   0x1AD - Underwater area (Kydrog lore)` | C (target text) | Label is fine, but message 0x1AD (`Core/messages.org:1709`) says Kydrog "fell to the tricks of Ganondorf" and "the goddesses cast him into the Abyss". DEC "Villain chain" 2-3: the prison corrupted him, not Ganondorf; DEC "Kydrog-was-the-guardian reveal is a dream": that reveal belongs to Dream 1. | `;   0x1AD - Underwater area (Kydrog lore; text contradicts canon, rewrite pending)` |

### Sprites/NPCs/eon_zora_elder.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 4-7 | `; NARRATIVE ROLE: Ancient Eon Abyss Zora who guides Link to the Sea` / `;   Shrine (First Mirror). Reveals the history of crystal-mirror magic` / `;   and why Kydrog targeted the Zoras - their united magic could seal` / `;   the rifts he uses to travel between worlds.` | C | DEC "Villain chain": Farore sealed the prison; Kydrog was its guardian, corrupted by it, and kidnaps Farore to force the key; his motive is the prison's promise to bring his men back. Nothing about Kydrog targeting Zoras or using rifts. APPROVED $1C0: the Mirror was built by "miners and river scholars" (not a Zora "First Mirror"). Sea Shrine scope is `[OPEN #5]` in the beat sheet. | `; NARRATIVE ROLE: Elder of the Abyss residents near the Sea Shrine`<br>`;   (map 0x79). Planned guide for that side area; scope and lore not`<br>`;   decided (beat sheet OPEN #5).` |
| 11-12 | `;   - Eon Zoras are temporally displaced - exist before the Schism` / `;   - Guardians of the First Mirror and portal magic knowledge` | O | Same as eon_zora.asm 4-7 and 10-12. | delete both lines |
| 23 | `;   - Post-shrine lore about the seal` | O | The seal's lore is fixed by DEC "Seal geography" (pyramid = lock, volcano = mouth) and is shown in Dream 1 (DEC "Kydrog-was-the-guardian reveal is a dream"); an Elder seal-lore line is not planned. | `;   - Post-shrine line (content not decided)` |
| 30 | `;   - shrine_cosmology.md (lore context)` | S | Bare name; file is `Docs/World/Lore/shrine_cosmology.md` and is not a canon source. | `;   - Docs/World/Lore/shrine_cosmology.md (agent notes, not canon)` |

### Sprites/NPCs/zora.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 6-7 | `;   The Zora race is divided by the Schism - Sea Zoras in Kalyxo,` / `;   Eon Zoras in the Abyss, and the Princess in D4 (Zora Temple).` | O | "Schism" is not in any DECIDED entry; DEC "Dialogue style" asks not to over-focus on races. | `;   Variants: Kalyxo Zora NPCs, Abyss residents, and the Zora`<br>`;   Princess in D4 (Zora Temple).` |
| 10-11 | `;   - "Sea Zora" - Kalyxo NPCs (friendly after reconciliation)` / `;   - "Eon Zora" - Abyss NPCs (temporally displaced, friendly)` | O | "Reconciliation" and "temporally displaced" are unconfirmed (beat 21 reconciliation is WIP in the beat sheet, not a DEC entry). | `;   - "Sea Zora" - Kalyxo NPCs`<br>`;   - "Eon Zora" - Abyss NPCs` |
| 47-48 | `;   - sram_flag_analysis.md (Zora reconciliation flags)` / `;   - jiggly-spinning-newt.md (Zora conflict resolution plan)` | S | `jiggly-spinning-newt.md` does not exist (not in repo, not in `~/.claude/plans/`). `sram_flag_analysis.md` exists at `Docs/Technical/`. | `;   - Docs/Technical/sram_flag_analysis.md` (drop the jiggly line) |

### Sprites/NPCs/zora_princess.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 4-7 | `; NARRATIVE ROLE: D4 (Zora Temple) quest NPC. The imprisoned princess` / `;   reveals the truth about Kydrog's manipulation of the Zora conflict` / `;   when Link plays the Song of Healing. Her dying words expose that` / `;   the River Zoras were framed by Kydrog's pirates wearing stolen scales.` | O | Presents an unwritten plot as fact: current 0xC6 is only "Thank you so much. My soul can be free now..." (see the file's own TODO). No DEC entry for a framing/stolen-scales plot. DEC "Villain chain" 3: the crew are Kydrog's dead men. | `; NARRATIVE ROLE: D4 (Zora Temple) quest NPC. Song of Healing frees`<br>`;   her spirit; she gives the Zora Mask. A Kydrog "conspiracy" line is`<br>`;   planned (beat 15) but not written or decided.` |
| 10-12 | `;   - Part of the Sea Zora faction` / `;   - Sister conflict: Sea Zoras vs River Zoras (The Schism)` / `;   - Resolution: Princess's revelation starts reconciliation arc` | O | Unconfirmed faction/Schism lore; DEC "Dialogue style". | delete lines 10-12 |
| 22 | `;   0xC6 - Death/revelation dialogue (enhance for Kydrog conspiracy)` | O | Same. | `;   0xC6 - Thanks after healing (story line not decided)` |
| 31 | `;   - East Kalyxo reconciliation scene (post-D4)` | O | Not a DEC entry, not a file. | delete |

### Sprites/NPCs/goron.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 6-7 | `;   Eon Abyss (Dark World), Gorons provide lore and hints about the` / `;   ancient world before Kydrog's corruption.` | C | DEC "Villain chain" 3 + DEC "When did the garrison arrive": Kydrog was corrupted by the prison decades ago; the Abyss is not "the ancient world before Kydrog's corruption". Actual 0x1B0-0x1B2 are Shrine of Power / Power Glove hints. | `;   Eon Abyss (Dark World), the Eon Gorons give Shrine of Power hints`<br>`;   (beat 19; DEC "Beat sheet crux 5").` |
| 11-12 | `;   - "Eon Goron" - Dark World variant, temporal echoes` / `;   - Rock Meat quest parallels Zora reconciliation arc` | O | Unconfirmed lore. | `;   - "Eon Goron" - Dark World variant (Shrine of Power hints)` (drop line 12) |
| 46 | `;   - rock_meat.asm (trade item)` | S | No `rock_meat.asm`; Rock Meat is in `Sprites/Objects/collectible.asm`. | `;   - Sprites/Objects/collectible.asm (Rock Meat pickup)` |
| 48 | `;   - narrative_lockdown.md (Goron arc parallels Zora arc)` | S | File does not exist anywhere. | delete, or `;   - Docs/Planning/Status/decisions.org (story rulings)` |

### Sprites/NPCs/impa.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 4-7 | `; NARRATIVE ROLE: Replaces Zelda's ALTTP role as the intro guide who` / `;   leads Link through the early game. In Oracle of Secrets, Impa serves` / `;   as the Sheikah guide who introduces Link to the island and is removed` / `;   as a follower during the Kydrog encounter.` | C | DEC "Impa's arc": Kydrog spares her on purpose as a messenger to Zelda; she stays in the Hall of Secrets as guide and link to Zelda. DEC "Impa is the rescue voice on black". | `; NARRATIVE ROLE: Zelda's Sheikah envoy, sent to find Farore. She is the`<br>`;   rescue voice on black, guides Link through the intro, and is spared`<br>`;   by Kydrog as a messenger to Zelda ($21/$35). Afterwards she stays in`<br>`;   the Hall of Secrets as guide. Canon: decisions.org ("Impa's arc").` |
| 40 | `;   - farore.asm (takes over guide role after Impa)` | C | Farore is kidnapped at the same encounter; Impa remains the guide (DEC "Impa's arc"). | `;   - farore.asm (kidnapped by Kydrog in the same scene)` |

### Sprites/NPCs/impa_hints.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 18-20 | `; Messages: Data/dialogue/message_registry.json owner impa-follower. The` / `; slots still hold placeholder text; the drafts wait for scawful's approval` / `; (Docs/Planning/Plans/impa_follower_hints_2026-09-25.md).` | S | APPROVED "Impa follower hints $1BF/$1C4/$1C8/$1C9": approved 2026-09-26 (with a changed $1C9). Only $1C4 is in `Data/dialogue/expanded_messages.json` so far. | `; Messages: ... owner impa-follower. Text approved 2026-09-26`<br>`; (Docs/Planning/Reviews/approved_dialogue_rewrites_2026-09-26.md);`<br>`; apply via expanded_messages.json + z3ed message-source-sync.` |

### Sprites/NPCs/maku_tree.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 5-7 | `;   story. The Maku Tree is the guardian of Kalyxo Island and provides` / `;   dungeon guidance after the intro sequence. Serves as the "oracle"` / `;   figure who points Link toward the next objective.` | O | Farore is the Oracle of Secrets (DEC "Villain chain"); "guardian" is Kydrog's role. Calling the Maku Tree the "oracle" figure muddles both. | `;   story. Gives dungeon guidance after Link returns from the Abyss`<br>`;   (beat 8).` |
| 10, 12 | `;   - Guardian spirit of Kalyxo Island` / `;   - First major NPC after Kydrog encounter` | O/S | Same "guardian" issue; the Maku meeting follows the Abyss escape (DEC "Intro Abyss exit: the sword cuts Link home" to $2A), not the encounter itself. | `;   - Kalyxo's great tree`<br>`;   - First NPC after the Abyss escape (sword warp to LW 0x2A)` |
| 29 | `;   0x1CA - 7 crystals: endgame, seek Shrines` | C | DEC "Beat sheet crux 5": Wisdom gates D4, Power gates D6; only Courage is post-D7. At 7 crystals only the Shrine of Courage remains. | `;   0x1CA - 7 crystals: endgame (retarget to Shrine of Courage; TO-BUILD)` |
| 30-31 | `;   0x1C8 - RESERVED` / `;   0x1C9 - RESERVED` | S | $1C8/$1C9 are now Impa follower hints (APPROVED; `impa_hints.asm`). | `;   0x1C8/0x1C9 - used by impa_hints.asm (not Maku)` |
| 49 | `;   - narrative_lockdown.md (story structure)` | S | File does not exist. | `;   - Docs/Planning/Status/decisions.org (story rulings)` |

### Sprites/NPCs/ranch_girl.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 4-7 | `; NARRATIVE ROLE: Side quest NPC who gives Link the Ocarina.` / `;   The "Chicken Easter Egg" refers to the Cucco` / `;   attack sequence that triggers her appearance. This is the prerequisite` / `;   for the Mask Salesman's Song of Healing quest.` | C | DEC "Beat sheet crux 7": guided (critical-path) chain: post-D1 message -> the ranch (now "Toto Ranch", DEC "Dialogue audit" D1); Magic Powder reveals the Cucco; Ocarina; she names the Mask Salesman; D5 Twinrova defeat lifts the curse. The trigger is Magic Powder (vanilla ChickenLady hook), not a Cucco attack. | `; NARRATIVE ROLE: Toto Ranch girl, cursed into a Cucco by Twinrova.`<br>`;   Magic Powder reveals her briefly; she gives the Ocarina and names the`<br>`;   Mask Salesman (beat 10). The curse lifts when Twinrova falls (D5).`<br>`;   Canon: decisions.org ("Beat sheet crux 7").` |
| 10 | `;   - Appears after Cucco attack sequence` | C | Same. | `;   - Appears when Magic Powder hits the cursed Cucco` |
| 24 | `;   0x17D - First meeting (curse broken, gives Ocarina)` | C | Curse lifts at D5, not here (crux 7). | `;   0x17D - First meeting (powder reveal, gives Ocarina)` |
| 28 | `;   SideQuestProg2 \|= 0x01 - Ranch Girl transformed back` | C | Same. | `;   SideQuestProg2 \|= 0x01 - Ranch Girl revealed (Ocarina given)` |
| 39 | `;   - cucco.asm (triggers her appearance)` | S | No `cucco.asm` exists. | delete, or `;   - vanilla ChickenLady ($1AFECF), Magic Powder trigger` |
| 53 | `    ; Set journal flag: Ranch Girl transformed back (curse broken)` | C | Same as 24. | `    ; Set journal flag: Ranch Girl revealed (curse lifts at D5)` |

### Sprites/NPCs/mask_salesman.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 6 | `;   quest chain. Appears after Link obtains the Ocarina from Ranch Girl.` | S | Code has `NoOcarina` state and sets `SideQuest_MetMaskSalesman` when Link has no Ocarina, so he is present before. Crux 7: the Ranch Girl names him. | `;   quest chain. Asks for an Ocarina; after the Ranch Girl's Ocarina`<br>`;   (beat 10) he teaches the Song of Healing.` |

### Sprites/NPCs/village_elder.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 5-6 | `;   and sets a major story progression flag. Meeting the Elder is a` / `;   prerequisite for later content (possibly Master Sword related).` | O | DEC "Seal geography" 1/4: the Master Sword is the lock at the Temporal Pyramid pedestal, pulled at beat 25; no Elder gate. No code reads OOSPROG bit 4 (`!Story_VillageElderMet`/`!Story_MasterSword` are defined, never used). | `;   and sets OOSPROG bit 4 (no reader found). Gives the post-D1 hint.` |
| 10 | `;   - OOSPROG bit 4 purpose unclear (Master Sword prerequisite?)` | O | Same. | `;   - OOSPROG bit 4: no reader in ASM (2026-09-26)` |
| 32-34 | `; NOTE: The purpose of OOSPROG bit 4 is unclear from the code.` / `;   It may be a Master Sword prerequisite or general story gate.` / `;   See sram_flag_analysis.md for investigation notes.` | O | Same. | `; NOTE: OOSPROG bit 4 has no reader. Not the Master Sword gate (pedestal,`<br>`;   beat 25). See Docs/Technical/sram_flag_analysis.md.` |

### Sprites/NPCs/korok.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 5-6 | `;   East Kalyxo regions. They provide hints, side content, and connect` / `;   the game to Wind Waker-era Zelda lore. Multiple visual variants` | O | No DEC entry ties the game to Wind Waker lore; DEC "Dialogue style" (people of Kalyxo). | `;   East Kalyxo regions. They provide hints and side content. Multiple`<br>`;   visual variants` |
| 13 | `;   - Forest guardians, evolved from Kokiri` | O | Unconfirmed lore. | delete |
| 43 | `;   - jiggly-spinning-newt.md (10 Korok hide-and-seek plan)` | S | File does not exist; beat sheet: "Korok minigame: single contained special map (ruling 2026-02-12)". | `;   - Korok minigame: single special map (beat sheet, 2026-02-12 ruling)` |

### Sprites/NPCs/deku_scrub.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 13 | `;   - Quest parallels Zora Princess revelation in D4` | O | "Revelation" plot unconfirmed (see zora_princess.asm). | `;   - Same Song of Healing -> mask pattern as the Zora Princess (D4)` |

### Sprites/NPCs/maple.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 211 | `  db $78 ; 0x00 - Deku Dream` | C | DEC "Dream structure": CurrentDream 0 = Wisdom -> Dream 1 "The Sealing War". | `  db $78 ; 0x00 - Wisdom: Dream 1 "The Sealing War" (placeholder room)` |
| 212 | `  db $79 ; 0x01 - Castle Dream` | C | CurrentDream 1 = Power -> Dream 2 "The Oracle's Choice". | `  db $79 ; 0x01 - Power: Dream 2 "The Oracle's Choice" (placeholder room)` |
| 213 | `  db $7A ; 0x02 -` | S | CurrentDream 2 = Courage -> Dream 3. | `  db $7A ; 0x02 - Courage: Dream 3 "The Healing Revelation" (placeholder)` |

### Core/sram.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 84-85 | `!Story_VillageElderMet     = $10  ; bit 4 - Elder met (Master Sword?)` / `!Story_MasterSword         = $10  ; bit 4 - (alias, same as above)` | O | See village_elder.asm; DEC "Seal geography". | `; bit 4 - Elder met (no reader)` and `; bit 4 - legacy alias, not a Master Sword gate` |
| 128 | `!SideQuest2_RanchGirl      = $01  ; bit 0 - Transformed back` | C | DEC "Beat sheet crux 7": curse lifts at D5. | `; bit 0 - Revealed by powder, Ocarina given` |
| 155-160 | `; Dreams Bits ($7EF410)` / `!Dream_Wisdom = $01 ; bit 0` ... | S (enhance) | Correct but unnamed; worth pinning the DEC mapping. | `; bit 0 - Dream 1 "The Sealing War"` / `; bit 1 - Dream 2 "The Oracle's Choice"` / `; bit 2 - Dream 3 "The Healing Revelation"` |
| 321 | `Boots = $7EF355 ; 1=Pegasus Boots (also needs Ability bit)` | S | DEC "Dialogue audit" D3: name is "Pegasus Shoes". | `; 1=Pegasus Shoes (also needs Ability bit)` |

### Sprites/NPCs/bug_net_kid.asm

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 2 | `; Gives the Boots if the player plays the Song of Healing` | S | DEC "Dialogue audit" D3: "Pegasus Shoes". | `; Gives the Pegasus Shoes if the player plays the Song of Healing` |
| 50 | `  ; Give Link the Boots` | S | Same. | `  ; Give Link the Pegasus Shoes` |

### Menu/menu_journal.asm (comment only)

| Line | Current comment | Sev | Why | Proposed replacement |
|---|---|---|---|---|
| 251 | `; GameState = $02 (Farore intro)` | S | `Core/sram.asm:74`: GameState $02 = "Sent to Eon Abyss" (after Kydrog). | `; GameState bit 1 (sent to the Abyss)` |

## Adjacent findings (in-game text, not comments; outside the requested scope)

These strings contradict DECIDED entries and are referenced by the comments above.

| Location | Text | Conflict |
|---|---|---|
| `Core/messages.org:1709` msg 0x1AD | "...he fell to the tricks of Ganondorf, king of thieves ... the goddesses cast him into the Abyss" | DEC "Villain chain" 2-3 (prison corrupted him; garrison knight chosen by Farore); DEC "Kydrog-was-the-guardian reveal is a dream". |
| `Core/messages.org` msgs 0x1B1, 0x1B2 | "Rock Sirloins" | DEC "Dialogue audit" D2: "Rock Meat". |
| `Menu/menu_journal.asm` `Entry_GoronQuest` | "5 ROCK SIRLOINS" | Same. |
| `Menu/menu_journal.asm` `Entry_CurseBroken` | "THE POWDER BROKE THE CURSE! ... TAUGHT ME THE SONG OF STORMS" | Crux 7 (curse lifts at D5); Song of Storms comes from the Windmill Guy post-D4 (`windmill_guy.asm`, beat 16). |

## Dangling references

| File:line | Reference | Status |
|---|---|---|
| `Sprites/NPCs/goron.asm:48` | `narrative_lockdown.md` | Missing everywhere (repo, `~/.claude/plans/`). |
| `Sprites/NPCs/maku_tree.asm:49` | `narrative_lockdown.md` | Missing. |
| `Sprites/NPCs/zora.asm:48` | `jiggly-spinning-newt.md` | Missing (also cited by `Docs/Technical/narrative_feasibility.md:10` as `~/.claude/plans/...`, which does not exist). |
| `Sprites/NPCs/korok.asm:43` | `jiggly-spinning-newt.md` | Missing. |
| `Sprites/NPCs/goron.asm:46` | `rock_meat.asm` | No such file; Rock Meat lives in `Sprites/Objects/collectible.asm`. |
| `Sprites/NPCs/ranch_girl.asm:39` | `cucco.asm` | No such file. |
| `Sprites/NPCs/eon_zora.asm:35`, `eon_zora_elder.asm:30` | `shrine_cosmology.md` | Exists at `Docs/World/Lore/shrine_cosmology.md` (bare name; agent lore, not canon). |
| `Sprites/NPCs/zora.asm:47`, `village_elder.asm:34,38` | `sram_flag_analysis.md` | Exists at `Docs/Technical/sram_flag_analysis.md` (bare name). |
| `Overworld/ZSCustomOverworld.asm:84,5635` | `Docs/Debugging/Issues/lost_woods_camera_desync.md` | Moved to `Docs/Debugging/Issues/archive/` (non-lore). |
| `Core/message.asm:48,53` | allocation notes `$1BC-$1C4, $1C8-$1C9 ... reserved padding`, `$1D9-$1DF: reserved` | Stale (non-lore): $1BF/$1C4/$1C8/$1C9 = Impa hints, $1C0-$1C3 = attract narration, $1D9-$1DF = experiment scene. |

## Files checked and fine (no lore conflict)

- `Sprites/NPCs/tingle.asm` (line 6 "hints at broader Zelda universe connections" is harmless flavor)
- `Sprites/NPCs/windmill_guy.asm`, `eon_owl.asm`, `followers.asm`, `hyrule_dream.asm` (no lore header), `mermaid.asm`, `bean_vendor.asm`, `vasu.asm`, `piratian.asm`, `fortune_teller.asm`, `bottle_vendor.asm`, `village_dog.asm`
- `Sprites/Bosses/twinrova.asm`, `kydrog_boss.asm`, `kydreeok.asm`, `kydreeok_head.asm`, `dark_link.asm`, `manhandla.asm`, `octoboss.asm`, `wolfos.asm`, `vampire_bat.asm`, `king_dodongo.asm`, `lanmola.asm`, `arrghus.asm`
- `Sprites/Enemies/custom_guard.asm` (Meadow Blade in D3), `eon_scrub.asm`, `leever.asm`; `Sprites/Objects/pedestal.asm`, `minecart.asm`, `data/minecart_tracks.asm`
- `Core/Cutscene/experiment.asm`, `Core/Cutscene/opening.asm`, `Core/progression.asm`, `Core/patches.asm`, `Core/symbols.asm`, `Core/sram.asm` crystal block (D1/D6 already fixed per DEC "World map dungeon icons")
- `Overworld/storm.asm`, `overworld.asm` (respawn lock cites DEC), `world_map.asm` (icon timeline matches DEC), `overlays.asm`, `entrances.asm`
- `Dungeons/custom_tag.asm`, `attract_scenes.asm`, `Maps/all_maps.asm`, `Collision/water_collision.asm`
- `Items/*` (all), `Masks/*` (all), `Menu/menu.asm`, `menu_map_names.asm`
- Skipped by request: `Sprites/NPCs/farore.asm`, `Sprites/Bosses/kydrog.asm`
