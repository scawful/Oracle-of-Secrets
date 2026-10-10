# Story Canon Beat Sheet

Date: 2026-09-27 (revision 4)
Authority: scawful's rulings, normalized from the decision log and story reviews.
This sheet supersedes conflicting claims in older narrative documents.

Status tags:
- `[DECIDED]` — creative ruling by scawful; do not contradict.
- `[IMPLEMENTED]` — verified in code/message text (citation given).
- `[PROPOSED]` — design suggestion consistent with rulings; needs approval.
- `[TO-BUILD]` — decided or required, not yet in code.
- `[TO-VERIFY]` — believed true, needs ROM/emulator (yaze) confirmation.
- `[OPEN]` — genuinely undecided; listed at the bottom.

Doc canon hierarchy (highest first):
1. This sheet.
2. Newer `DECIDED` entries in `Docs/Planning/Status/decisions.org`; these
   override stale text here until folded into the next revision.
3. Code and ROM evidence for implementation status, not creative intent.
4. `Story_Event_Graph.md` for code-traced events.
5. Older plans and lore documents are reference material only. Treat uncited
   claims in them as proposals, not canon.

---

## September 23 opening and island-history rulings

Accepted by scawful during the opening storyboard discussion; implementation remains `[TO-BUILD]`.

- `[DECIDED]` The Magic Mirror breakthrough, using Goron crystals and Zora research, triggers Hyrule's interest. Do not assume an established centuries-long portal industry before that interest.
- `[DECIDED]` The Abyss is eerie and poorly understood, with a nostalgic allure that draws explorers toward dangerous, strong retro enemies. The Zora approach it through scholarship, exploration, and their spiritual traditions.
- `[DECIDED]` Farore warns the island's scholars before turning to Hyrule. Exploration continues despite the warning. Her disclosure of the prison helps cause the occupation, giving all parties morally complicated responsibilities. She knew Kydrog personally: she made him the prison's guardian (villain chain, crux 2). The garrison arrived decades ago.
- `[DECIDED]` Hylian presence brings infrastructure and real benefits alongside control; islanders have mixed views. An eastern garrison/port between Korok Cove and the planned Sea Zora sanctuary is `[PROPOSED]` geography.
- `[DECIDED]` Title/attract scenes cover island history: pre-occupation Kalyxo, discovery, Hylian arrival, occupation, and neglect. Reveal Farore's private role and the prison's contents later.
- `[DECIDED skeleton]` New-game scene: Zora uses the Mirror near the Happy Mask Salesman map's river, explores the Abyss, retreats from an enemy, and returns with a Stalfos following. Farore pleads for help; the goddesses summon Link into the falling/spinning arrival and bed wake-up. Exact divine speaker, effects, and army-access mechanism remain open. This later experiment is distinct from the original discovery.
- `[DECIDED gameplay, 2026-09-23]` Village patrol contact starts at half-heart damage with normal knockback/invulnerability and a brief guard recovery pause. No capture, forced restart, or scripted shove into the hole. Keep NPC approaches safe; verify walls/pit knockback and tune pursuit speed before increasing damage. Implementation and actual damage behavior remain `[TO-BUILD]` / `[TO-VERIFY]`.
- `[DECIDED]` Preserve meeting Farore in the western forest and walking into Kydrog's ambush. Do not capture her before this meeting. The rescue-expedition intro proposal is superseded by the simpler Mirror test.
- `[DECIDED 2026-09-26]` Arrival: after the fall, one message over black in Impa's voice (line A: she finds Link and has him carried into a villager's house, not hers), then the bed wake-up with a villager line pointing to the beach (B; B2 after a death), then Impa's `$25` opening (C). Text approved in `Docs/Planning/Status/decisions.org` ("Arrival lines A/B/C"). Death/continue after the village-hole route respawns inside that route (checkpoint; exact room `[TO-BUILD]`).

### Shrine of Origins and first Abyss visit — accepted follow-up

- `[DECIDED]` Preserve the existing Abyss -> Origins -> Owl -> sword/shield -> return sequence and its stump, small-passage, reflection and enemy lessons. Improve the existing content rather than replacing the tutorial.
- `[SUPERSEDED 2026-09-26]` ~~Modestly extend Origins by developing its Minish puzzle further.~~ Do not extend Origins: keep the Minish puzzle, add no rooms (`Docs/Planning/Status/decisions.org`, "Abyss segment: fix direction before cutting content").
- `[DECIDED 2026-09-26]` Abyss guidance: `$36` names a landmark (Shrine of Origins west of the pyramid); the Eon Owl appears twice (a new early line on the arrival area pointing to the shrine, then `$E6` after the Pearl pointing to the sword). Text approved in `Docs/Planning/Reviews/approved_dialogue_rewrites_2026-09-26.md`. Death/continue anywhere in the Abyss respawns there until Link escapes (`Docs/Planning/Status/decisions.org`, "Abyss respawn lock"). Then one timed playtest; cut content only if a step is still long.
- `[DECIDED]` Give the Moon Pearl pickup stronger presentation and acknowledge the user-confirmed NES Link -> GBC Link change in pickup/post-Pearl reactions. Do not describe the visible pre-Pearl form as vanilla Bunny Link.
- `[DECIDED]` First exit from Origins after obtaining the Pearl triggers one brief mysterious disturbance: ambience drops, low rumble/mountain shake, existing fleeing animals react, then quiet and control. A subtle lighting/overlay change is optional pending asset/engine inspection. No explanatory dialogue, visible attacker or explicit eruption. Reuse the animals already associated with the later L4 Master Sword area in the map's top-right corner; preserve their later appearance and sword progression. The event happens once; trigger storage and save/reload semantics require audit. Cause remains unexplained: no ruling that taking the Pearl damages or breaks a seal.
- `[DECIDED 2026-09-26/27]` Intro exit: picking up the sword in the Forest of Dreams cuts Link home (short flash/slash, scripted warp to `$2A`), replacing the DW `$6A` warp-tile exit; feasibility `[TO-VERIFY]`. The Abyss opens as six enforced chunks plus the separate underwater route. Keep one Kalyxo pad into the finale region; remove or restrict the other volcano pads. The way back from any chunk is a return portal at Link's arrival spot `[TO-BUILD]`. Seal geography: the pyramid is the lock, the volcano is the prison mouth. One dream follows each pendant and ends in the Dream Hut. Exact maps and gates are in `decisions.org` ("Abyss chunk layout and warp pads").
- `[PROPOSED interpretation]` Pearl steadies Link's form in the Abyss; console generations are not established as literal in-world history. Exact explanatory wording remains draft.

Implementation order and storyboard: [Opening and RC development plan](Plans/opening_and_rc_development_2026-09-23.md). New-game experiment hook comes last; title, summons/arrival, and village sprites come first.

## Core rulings (the seven cruxes)

1. **Farore is the Oracle bound to the Meadow Blade** `[DECIDED]`.
   Kydrog's abandoned knight-sword became her power's vessel; he kidnapped her
   body to force its release. Matches implemented msg `0x70`. Her callouts to
   Link (starting at D3) are deliberately ambiguous — the player assumes
   ship-telepathy; the reveal recontextualizes them as the blade `[DECIDED —
   confirmed working, keep callouts location-vague]`. Body rescued at D7;
   power released at the Master Sword pedestal (beat 25).
2. **The Eon Abyss is the prison** `[DECIDED, partial adoption]`.
   **Villain chain** `[DECIDED 2026-09-26, `Docs/Planning/Status/decisions.org` "Villain chain";
   replaces the earlier "Ganon residue" / garrison reading]`:
   1. Farore warns the island's scholars, then turns to Hyrule; Hyrule sends a
      garrison "to guard the Golden Power" (islanders see an invasion; msg
      `0x112` stands). D3 Kalyxo Castle's occupation lore and the seal story
      are one history.
   2. Farore makes Kydrog, a garrison knight, the prison's guardian and binds
      her power into his sword as the seal's key.
   3. The prison corrupts him; he dies and rises as the Stalfos Pirate King;
      his dead men are his crew. He abandons the sword (the Meadow Blade).
   4. The prison holds the half-revived beast Ganon from the Oracle games'
      failed revival (msg `0x136`). Twinrova hunt essences to finish it and
      die in D5; Kydrog carries the revival on and kidnaps Farore's body to
      force the key.
   5. Kydrog's motive is tragic: the prison promises the Golden Power can
      bring his men back. His pirate-skeleton humor is a coping mechanism for
      his death and his men's deaths.
3. **Kydreeok is Kydrog's Abyss form** `[DECIDED — supersedes the TotK
   dragonification framing]`. The Golden Power reshapes you to your heart
   (msg `0x15B`); in Kalyxo he is the Stalfos Pirate King, in the Eon Abyss
   his true corrupted shape is a giant skeletal Gleeok. No dragon-tear
   mechanic — this is the hack's dark-world-transformation logic.
4. **Kydreeok finale; Song of Healing finisher; Ganon breakout** `[DECIDED]`.
   Fight first, redemption second: sever the heads, they regrow — all heads
   must be down simultaneously to win `[DECIDED mechanics]`. Then the Song of
   Healing frees the knight: Kydreeok is the prison's corruption of him, not
   his heart. Post-healing form: human `[DECIDED 2026-09-26, villain chain]`.
   Then **Ganon breaks out** and alternates between Ganondorf (energy-ball
   volleys) and the beast, per msg `0x15B` "reshapes you to your heart";
   vanilla Ganon parts may be reused `[DECIDED 2026-09-26, `Docs/Planning/Status/decisions.org`;
   replaces the earlier wordless custom-beast coda]`.
5. **Shrines are hybrid with concrete dungeon gates** `[DECIDED per review]`:
   - **Shrine of Wisdom** + Flippers → required for **D4 Zora Temple**.
   - **Shrine of Power** (meet the Eon Gorons) → required for **D6 Goron Mines**.
   - **Shrine of Courage** requires the Somaria Rod (D7 item) → post-D7 only.
   Enterable early ≠ fully explorable; exact in-ROM gating `[TO-VERIFY]` with
   yaze. Maku Tree 7-crystal "seek Shrines" hint (`maku_tree.asm:29`) must be
   re-aimed at the Shrine of Courage specifically `[TO-BUILD]`.
6. **Sky Islands: optional post-D6 route through the East Kalyxo tower**
   `[DECIDED 2026-09-26/27]`. The tower is the only entrance; Song of Soaring
   does not bypass it. The Watchers built the original tower and sky structures;
   Hyrule's garrison later reused the lower floors and abandoned them. The Sky
   provides optional lore and upgrades. Remove the Korok Cove test bridge.
   Sky traversal uses `cloud_bridge.asm` platform sprites, not
   weather-conditional map collision.
7. **The Ranch Girl is a required Ocarina-path witness; D5 ends her curse
   automatically** `[DECIDED 2026-09-02]`.
   The inherited ALTTP Magic-Powder-on-a-Cucco Easter egg can remain as a
   reference, but knowledge of that Easter egg must never be required for
   progression. After D1, a guaranteed story message sends Link to investigate
   the missing Ranch Girl because she may have witnessed Twinrova searching for
   essences. The hint chain must establish that Magic Powder reveals magically
   transformed creatures and that a strange Cucco appeared when the girl
   vanished. The temporary reveal gives Link the Ocarina; Ranch Girl then names
   the Mask Salesman at Tail Pond as the next destination. Set the Tail Pond
   objective only after Link receives the Ocarina, not immediately after D1.
   Defeating Twinrova in D5 permanently breaks the curse. This is automatic:
   no Song of Healing, return objective, item reward, or Ranch Girl dream.
   Ranch Girl may have reactive post-D5 dialogue if the player happens to
   revisit, but the game never asks the player to return.

---

## Act I — The Island's Wounds

| # | Beat | Status | Evidence / notes |
|---|------|--------|------------------|
| 1 | Attract backstory: Hyrule's occupation, the Abyss, Kydrog awakes | `[IMPLEMENTED]` text; `[TO-BUILD]` presentation | msgs `0x112–0x115`. Review: attract scenes need programming for better NPC movement/settings — research the vanilla attract module first |
| 2 | Falling-into-Kalyxo cutscene: Link spinning down over black, goddess voice — OoA/OoS homage | `[DECIDED per review]`, `[TO-BUILD]` | New beat; leads into the telepathic plea. Then Impa's voice on black and the villager wake-up (lines A/B/B2, `[DECIDED 2026-09-26]`, decisions.org) |
| 3 | Telepathic plea in Link's house ("Accept our quest") | `[IMPLEMENTED]` | msg `0x1F`; `Dungeons/custom_tag.asm:33-105`. The speakers are the goddesses, unnamed `[DECIDED 2026-09-25]`. |
| 4 | Impa on Loom Beach: sent by Zelda to find Oracle Farore | `[IMPLEMENTED]` | msg `0x25` |
| 5 | Wayward Village: sneak past Kydrog's stalfos pirates | `[IMPLEMENTED]` | — |
| 6 | Meet Farore at Forest Glade (SW 0x80); Kydrog ambush; Farore taken; Link cast into the Abyss | `[IMPLEMENTED]` + `[TO-VERIFY]` | msgs `0x0E/0x21`; `farore.asm:120-248`; GameState→2 at `farore.asm:221`. Review: the scene choreography likely lives in ROM data not reflected in ASM — reconcile with yaze. The `$0E` reunion line is now present in the base ROM. |
| 7 | Abyss tutorial: changed form → Minish → Moon Pearl (Origins reward); Eon Owl; "Golden Power reshapes you" | `[IMPLEMENTED]` partial | msgs `0x35/0x36`, `0xE6`, `0x15B`. Order `[DECIDED 2026-09-26]`: Minish first, Pearl as the Origins reward, as built (decisions.org; "a bit confusing" note: revisit after the timed Abyss playtest). `$35` (Impa telepathy): Kydrog spared her as a messenger to Zelda; approved text in `Reviews/approved_dialogue_rewrites_2026-09-26.md`. `[DECIDED 2026-09-26]`: `$36` landmark rewrite, Owl twice, respawn lock until escape, Origins not extended (decisions.org) |
| 8 | Portal home → Maku Tree briefing; Hall of Secrets | `[IMPLEMENTED]` | msg `0x20`; `maku_tree.asm:132-175` |
| 9 | **D1 Mushroom Grotto** → essence 1 | built | maiden msg `0x132` (dedup opener — Text debt) |
| 10 | Guided Ocarina chain: D1 Mushroom → witches / Magic Powder → investigate missing Ranch Girl at Toto Ranch → reveal the strange Cucco temporarily → Ocarina → Mask Salesman at Tail Pond → Song of Healing → Deku Mask | mechanics `[IMPLEMENTED]`; guidance `[DECIDED]`, `[TO-BUILD]` | Required hint facts: Twinrova sought essences; Ranch Girl vanished; a strange Cucco appeared; Magic Powder reveals transformed creatures. Reuse the guaranteed D1 aftermath plus Village Elder `0x177` as reinforcement. Ranch Girl `0x17D` must point forward to the Mask Salesman. Current Elder `0x177` sends Link to the mask shop and immediately writes `MapIcon_TailPond`; both are `[TO-CHANGE]` because they skip the ranch objective. Maku `0x1C5` is a generic one-crystal reaction in the current expanded source; its Tail Pond description in `Core/messages.org` is stale. Do not rely on knowledge of the ALTTP Easter egg. |
| 11 | **D2 Tail Palace** → essence 2 | built | maiden msg `0x133` |
| 12 | **Book of Secrets**: library dash knockdown → **unlocks the Journal** | `[DECIDED]`, `[TO-BUILD]` | Item code exists (`Items/book_of_secrets.asm`); journal exists (`Menu/menu_journal.asm`). Review ruling: reading the Book grants the journal ability; shift journal entries to unlock from this point; backstory/lore (incl. Kydrog's fall, Librarian deep lore `0x199–0x19F`) can be delivered/collected via the journal system. Wire `Story2_BookOfSecrets` setter on pickup |
| 13 | **D3 Kalyxo Castle** → **Meadow Blade** + essence 3; **Farore's voice calls out** | built; framing `[DECIDED]` | maiden msg `0x134`. Canon name "Meadow Blade". The callout misdirects toward the ship — works as dramatic irony (see ruling 1); keep her lines location-vague |

## Act II — The Conspiracy Unravels

| # | Beat | Status | Evidence / notes |
|---|------|--------|------------------|
| 14 | **Shrine of Wisdom** (+ Flippers) → **Pendant of Wisdom** → **Dream 1: The Sealing War** | `[DECIDED gate]`; dreams in RC scope `[DECIDED 2026-09-26]` | Maple's Dream Hut is on `$5D` in the Yesterwind chunk. Entrance `$68` loads Maple's `$0F` (runtime-checked 2026-09-28 on b31; the old `$11A` reading used the vanilla `$02` entrance table, but the game uses ZScream's bank `$0F` table). Dream 1 reveals Kydrog's fall and former guardianship; early sympathy seed. |
| 15 | **D4 Zora Temple** → Zora Mask; Zora conspiracy reveal | built | Requires Shrine of Wisdom + Flippers `[DECIDED]`. Msg `0x135` |
| 16 | Post-D4: Song of Storms; whirlpool dive-warps between worlds | `[IMPLEMENTED]` | `Sprites/Objects/deku_leaf.asm:85-118` → vanilla mirror-warp. `[PROPOSED]` one NPC line: whirlpools = cracks in the weakening seal |
| 17 | **D5 Glacia Estate**: Twinrova — "HE will rise" | `[IMPLEMENTED]` | msgs `0x123`, `0x136` |
| 18 | Defeating Twinrova permanently breaks the Ranch Girl's Cucco curse | `[DECIDED]`, `[TO-BUILD]` | Automatic D5 world-state consequence. No Song of Healing and no instructed return trip. If the player revisits naturally, short reactive dialogue may confirm the change. The obsolete `$1FA` Lost Voice quest and Ranch Girl dream are `[CUT]`. Current `ranch_girl.asm` has no D5 branch, and the D5 crystal setter still needs runtime tracing. |
| 19 | **Shrine of Power** (meet the **Eon Gorons**) → **Pendant of Power** | `[DECIDED gate]` | Required for D6. The former Ranch Girl Dream 2 attached here is `[CUT 2026-09-02]`. |
| 20 | **D6 Goron Mines**: Rock Meat trust, minecarts → essence 6 | built (carts WIP) | Requires Shrine of Power `[DECIDED]`. Maiden msg `0x137` |
| 21 | East Kalyxo opens (Hammer); River Zora reconciliation; optional **Sky tower and islands** | WIP; sky route `[DECIDED]`, `[TO-BUILD]` | The tower east of Korok Cove is the only Sky entrance. Lower floors are Hylian garrison ruins; upper floors expose Watcher construction. |

## Act III — The Endgame

| # | Beat | Status | Evidence / notes |
|---|------|--------|------------------|
| 22 | Kaepora → **Song of Soaring** → the Dragon Ship | `[IMPLEMENTED]` | msg `0x146`; `Items/ocarina.asm` song 03 |
| 23 | **D7 Dragon Ship**: pirate-Kydrog fight → **Farore fully freed here** `[DECIDED per review]`; his spirit flees to the Abyss; Somaria Rod | `[TO-BUILD]` | No dragonification here. Finish `kydrog_boss.asm:335-382` scaffold (gated OFF): crystal 7, GameState→3, real rescue scene (replace temp `0x138`). Farore NPC active from here; her POWER remains in the Blade until beat 25 |
| 24 | **Shrine of Courage** (needs Somaria Rod) → **Pendant of Courage** → **Dream 3: the healing revelation** | `[DECIDED gate]`; dream in RC scope `[DECIDED]`, content `[PROPOSED]` | Post-D7 by construction. Dream 3 reveals the Abyss-form can be REVERSED — the Song of Healing is the key to saving Kydrog |
| 25 | **Master Sword pulled from the pedestal** (post-D7, pre-D8) — **the transfer scene** | mechanics `[IMPLEMENTED-vanilla]`; scene `[PROPOSED]` | Not forged — pulled. Meadow Blade caps at L3; the pull grants L4. Proposed reconciliation: Farore, present and freed, releases her power from the Meadow Blade into the Master Sword as Link draws it — the engine's sword swap becomes the story beat. Also explains why Kydrog lured Link to the ship: the power he needs has been in Link's hand since D3 |
| 26 | Optional **Sky Islands** content remains available | `[DECIDED post-D6]`, `[TO-BUILD]` | Not a required endgame beat. The one- or two-room Watchers temple holds lore and an optional item; no Observatory is planned. |
| 27 | **D8 Fortress of Secrets**: Voice; Dark Link; at the heart Kydrog assumes his **Abyss form — Kydreeok** | Dark Link `[IMPLEMENTED]`; rest `[TO-BUILD]` | `dark_link.asm:962-975`. `[PROPOSED]` the Voice = the half-revived Ganon's hunger (villain chain) — fragments and wants, not sentences |
| 28 | **Kydreeok finale**: sever all heads simultaneously (they regrow) → **Song of Healing finisher** → Kydrog restored | `[DECIDED]`; `[TO-BUILD]` | `kydreeok.asm` exists, zero messages. Post-healing form: human `[DECIDED 2026-09-26]` |
| 29 | **Ganon breaks out** — alternates Ganondorf (energy-ball volleys) and the beast; Farore aids | `[DECIDED 2026-09-26]`, `[TO-BUILD]` | Villain chain (`Docs/Planning/Status/decisions.org`). Per msg `0x15B`; vanilla Ganon parts may be reused |
| 30 | **Ending**: seal restored; the Abyss begins to heal; credits | `[TO-BUILD]` | Credits hook stubbed in `Overworld/overworld.asm`; no ending text exists. GameState 3 finally gets readers. |
| 31 | **Post-game**: Kydrog Mask in the save | `[DECIDED]` | Parting gift; post-game only (menu space) |

## Side content with story weight

- **Underwater south Abyss shrine**: medium, five-room, keyless mini-dungeon
  with a short route and mini-boss `[DECIDED 2026-09-27]`. Exact lore, reward,
  entrance, and Eon Zora Elder role remain open.
- **Korok minigame**: single contained special map (ruling 2026-02-12).
- **Trading sequence**: CUT (ruling 2026-02-12).

## Text debt (not yet reviewed by scawful)

1. Merge orphaned maiden rewrite (`Data/dialogue/maiden_upgrades_dialogue.json`)
   + dedupe the four copy-pasted maiden openers.
2. Use the generated dialogue inventory for `0x1CC–0x1F9`; do not copy expanded source into the non-authoritative `messages.org` snapshot.
3. Fill D3 prison (`0x1CC–0x1D1`) + Gossip Stone (`0x1D2–0x1D4`) TODO stubs.
4. Undocumented Twinrova library msg `$1D` (`twinrova.asm:1105`).

## Open and resolved review questions

Question numbers remain stable because other planning documents refer to them.

1. `[PARTIALLY RESOLVED 2026-09-23]` Farore pleads; the goddesses answer by summoning Link. `[DECIDED 2026-09-25]` The summons voice (msg `$1F`, "Accept our quest") is the goddesses, unnamed. The payoff of Farore's interrupted line remains open (proposal: `Plans/experiment_scene_storyboard_2026-09-25.md`).
2. `[RESOLVED 2026-09-26]` Moon Pearl vs. Minish order: Minish first, Pearl as the Origins reward (decisions.org).
3. `[RESOLVED 2026-09-02]` Keep the Ranch Girl and Twinrova connection. D5
   breaks her curse automatically. Cut the Song-of-Healing return quest and
   Ranch Girl dream. Explicitly guide the required early trip to Toto Ranch.
4. `[RESOLVED 2026-09-26]` Sky access: the East Kalyxo tower only.
5. `[RESOLVED 2026-09-27]` Underwater south Abyss scope: medium, five-room,
   keyless mini-dungeon.
6. `[RESOLVED 2026-09-26]` The inhabitants call the Abyss and its central
   village Yesterwind.
7. `[RESOLVED 2026-09-26]` Kydrog's post-healing form: his living human self (villain chain, `Docs/Planning/Status/decisions.org`).
