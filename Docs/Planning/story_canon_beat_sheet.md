# Story Canon Beat Sheet

Date: 2026-09-02 (revision 3 — adds the Ranch Girl progression ruling)
Authority: rulings by scawful during the 2026-07-25 plot review and 2026-09-02 Ranch Girl follow-up.
This sheet supersedes conflicting claims in all other narrative docs.

Status tags:
- `[DECIDED]` — creative ruling by scawful; do not contradict.
- `[IMPLEMENTED]` — verified in code/message text (citation given).
- `[PROPOSED]` — Claude suggestion consistent with rulings; needs approval.
- `[TO-BUILD]` — decided or required, not yet in code.
- `[TO-VERIFY]` — believed true, needs ROM/emulator (yaze) confirmation.
- `[OPEN]` — genuinely undecided; listed at the bottom.

Doc canon hierarchy (highest first):
1. This sheet.
2. `Story_Event_Graph.md` (code-traced events).
3. `narrative_design_master_plan.md`, `story_framework.md`,
   `content_story_planning_review.md` (honest-status docs).
4. `story_bible.md`, `dungeon_narratives.md` (rich lore, reconcile downward).
5. `QuestFlow.md` — mostly non-canon, BUT its shrine item-gate interleave and
   library Book beat matched scawful's intent; treat individual claims as
   hypotheses to confirm with scawful, never as authority.

---

## September 23 opening and island-history rulings

Accepted by scawful during the opening storyboard discussion; implementation remains `[TO-BUILD]`.

- `[DECIDED]` The Magic Mirror breakthrough, using Goron crystals and Zora research, triggers Hyrule's interest. Do not assume an established centuries-long portal industry before that interest.
- `[DECIDED]` The Abyss is eerie and poorly understood, with a nostalgic allure that draws explorers toward dangerous, strong retro enemies. The Zora approach it through scholarship, exploration, and their spiritual traditions.
- `[DECIDED]` Farore warns the Zora before turning to Hyrule. Exploration continues despite the warning. Her disclosure of the prison helps cause the occupation, giving all parties morally complicated responsibilities. Exact dates, Zora factions, and how much she knows about Kydrog remain open. Preserve the existing failed-revival residue ruling below.
- `[DECIDED]` Hylian presence brings infrastructure and real benefits alongside control; islanders have mixed views. An eastern garrison/port between Korok Cove and the planned Sea Zora sanctuary is `[PROPOSED]` geography.
- `[DECIDED]` Title/attract scenes cover island history: pre-occupation Kalyxo, discovery, Hylian arrival, occupation, and neglect. Reveal Farore's private role and the prison's contents later.
- `[DECIDED skeleton]` New-game scene: Zora uses the Mirror near the Happy Mask Salesman map's river, explores the Abyss, retreats from an enemy, and returns with a Stalfos following. Farore pleads for help; the goddesses summon Link into the falling/spinning arrival and bed wake-up. Exact divine speaker, effects, and army-access mechanism remain open. This later experiment is distinct from the original discovery.
- `[DECIDED gameplay, 2026-09-23]` Village patrol contact starts at half-heart damage with normal knockback/invulnerability and a brief guard recovery pause. No capture, forced restart, or scripted shove into the hole. Keep NPC approaches safe; verify walls/pit knockback and tune pursuit speed before increasing damage. Implementation and actual damage behavior remain `[TO-BUILD]` / `[TO-VERIFY]`.
- `[DECIDED]` Preserve meeting Farore in the western forest and walking into Kydrog's ambush. Do not capture her before this meeting. The rescue-expedition intro proposal is superseded by the simpler Mirror test.

### Shrine of Origins and first Abyss visit — accepted follow-up

- `[DECIDED]` Preserve the existing Abyss -> Origins -> Owl -> sword/shield -> return sequence and its stump, small-passage, reflection and enemy lessons. Improve the existing content rather than replacing the tutorial.
- `[DECIDED]` Modestly extend Origins by developing its Minish puzzle further. Exact room edits remain open; the rendered empty southwest quadrant is an inspection candidate, not approved expansion space.
- `[DECIDED]` Give the Moon Pearl pickup stronger presentation and acknowledge the user-confirmed NES Link -> GBC Link change in pickup/post-Pearl reactions. Do not describe the visible pre-Pearl form as vanilla Bunny Link.
- `[DECIDED]` First exit from Origins after obtaining the Pearl triggers one brief mysterious disturbance: ambience drops, low rumble/mountain shake, existing fleeing animals react, then quiet and control. A subtle lighting/overlay change is optional pending asset/engine inspection. No explanatory dialogue, visible attacker or explicit eruption. Reuse the animals already associated with the later L4 Master Sword area in the map's top-right corner; preserve their later appearance and sword progression. The event happens once; trigger storage and save/reload semantics require audit. Cause remains unexplained: no ruling that taking the Pearl damages or breaks a seal.
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
   The mindless Ganon residue from the Oracle-games' failed revival (anchored
   by implemented msg `0x136`) festers there — the implicit source of the
   Abyss's corruption. Oracle-series ties stay mostly implicit.
   **Historical grounding** `[DECIDED per review]`: tie the prison to the
   island's history and the Hylian-occupation theme — msg `0x112` already says
   Hyrule invaded Kalyxo "to guard the Golden Power" and the guardians grew
   complacent. Canon reading: the occupation WAS the garrison of the prison;
   D3 Kalyxo Castle's occupation lore and the seal story are one history.
   OoT-timeline "Ganondorf in hiding" framing rejected.
3. **Kydreeok is Kydrog's Abyss form** `[DECIDED — supersedes the TotK
   dragonification framing]`. The Golden Power reshapes you to your heart
   (msg `0x15B`); in Kalyxo he is the Stalfos Pirate King, in the Eon Abyss
   his true corrupted shape is a giant skeletal Gleeok. No dragon-tear
   mechanic — this is the hack's dark-world-transformation logic.
4. **Kydreeok finale; Song of Healing finisher; custom beast coda** `[DECIDED]`.
   Fight first, redemption second: sever the heads, they regrow — all heads
   must be down simultaneously to win `[DECIDED mechanics]`. Then the Song of
   Healing restores him. Post-healing form `[OPEN #7]`: back to Stalfos, or
   his living human self for the farewell (`[PROPOSED]`: human spirit — the
   man from before undeath — for the emotional beat).
   Then the **mindless-beast coda**: the residue, denied its vessel, attacks —
   wordless. **Custom-built boss in the house style** (Twinrova / Kydrog /
   Kydreeok / Vampire Bat standard), NOT vanilla Ganon reuse `[DECIDED —
   scawful overrode the vanilla-reuse proposal]`.
5. **Shrines are hybrid with concrete dungeon gates** `[DECIDED per review]`:
   - **Shrine of Wisdom** + Flippers → required for **D4 Zora Temple**.
   - **Shrine of Power** (meet the Eon Gorons) → required for **D6 Goron Mines**.
   - **Shrine of Courage** requires the Somaria Rod (D7 item) → post-D7 only.
   Enterable early ≠ fully explorable; exact in-ROM gating `[TO-VERIFY]` with
   yaze. Maku Tree 7-crystal "seek Shrines" hint (`maku_tree.asm:29`) must be
   re-aimed at the Shrine of Courage specifically `[TO-BUILD]`.
6. **Sky Islands: full 8-map plan, late-game unlock** `[DECIDED]`.
   scawful already has map sketches — effort is bounded. Access idea
   `[PROPOSED per review]`: **East Kalyxo connects to the Sky Islands**
   (gives the WIP Hammer region a purpose). Mechanism still `[OPEN #4]`
   (Song of Soaring vs. an East Kalyxo route vs. both).
   De-risk rule stands: sky traversal from `cloud_bridge.asm` platform
   sprites, NOT weather-conditional map collision.
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
| 2 | Falling-into-Kalyxo cutscene: Link spinning down over black, goddess voice — OoA/OoS homage | `[DECIDED per review]`, `[TO-BUILD]` | New beat; leads into the telepathic plea |
| 3 | Telepathic plea in Link's house ("Accept our quest") | `[IMPLEMENTED]` | msg `0x1F`; `Dungeons/custom_tag.asm:33-105`. Voice identity stays mysterious `[OPEN #1]` |
| 4 | Impa on Loom Beach: sent by Zelda to find Oracle Farore | `[IMPLEMENTED]` | msg `0x25` |
| 5 | Wayward Village: sneak past Kydrog's stalfos pirates | `[IMPLEMENTED]` | — |
| 6 | Meet Farore at Forest Glade (SW 0x80); Kydrog ambush; Farore taken; Link cast into the Abyss | `[IMPLEMENTED]` + `[TO-VERIFY]` | msg `0x21`; `farore.asm:120-248`; GameState→2 at `farore.asm:221`. Review: the scene choreography likely lives in ROM data not reflected in ASM — reconcile with yaze. **Farore's reunion msg `$0E` is an empty vanilla slot `[TO-BUILD]`** |
| 7 | Abyss tutorial: Bunny → Moon Pearl → Minish; Eon Owl; "Golden Power reshapes you" | `[IMPLEMENTED]` partial | msgs `0x35/0x36`, `0xE6`, `0x15B`. Moon-Pearl/Minish order `[OPEN #2]` |
| 8 | Portal home → Maku Tree briefing; Hall of Secrets | `[IMPLEMENTED]` | msg `0x20`; `maku_tree.asm:132-175` |
| 9 | **D1 Mushroom Grotto** → essence 1 | built | maiden msg `0x132` (dedup opener — Text debt) |
| 10 | Guided Ocarina chain: D1 Mushroom → witches / Magic Powder → investigate missing Ranch Girl at Loom Ranch → reveal the strange Cucco temporarily → Ocarina → Mask Salesman at Tail Pond → Song of Healing → Deku Mask | mechanics `[IMPLEMENTED]`; guidance `[DECIDED]`, `[TO-BUILD]` | Required hint facts: Twinrova sought essences; Ranch Girl vanished; a strange Cucco appeared; Magic Powder reveals transformed creatures. Reuse the guaranteed D1 aftermath plus Village Elder `0x177` as reinforcement. Ranch Girl `0x17D` must point forward to the Mask Salesman. Current Elder `0x177` sends Link to the mask shop and immediately writes `MapIcon_TailPond`; both are `[TO-CHANGE]` because they skip the ranch objective. Maku `0x1C5` is a generic one-crystal reaction in the current expanded source; its Tail Pond description in `Core/messages.org` is stale. Do not rely on knowledge of the ALTTP Easter egg. |
| 11 | **D2 Tail Palace** → essence 2 | built | maiden msg `0x133` |
| 12 | **Book of Secrets**: library dash knockdown → **unlocks the Journal** | `[DECIDED]`, `[TO-BUILD]` | Item code exists (`Items/book_of_secrets.asm`); journal exists (`Menu/menu_journal.asm`). Review ruling: reading the Book grants the journal ability; shift journal entries to unlock from this point; backstory/lore (incl. Kydrog's fall, Librarian deep lore `0x199–0x19F`) can be delivered/collected via the journal system. Wire `Story2_BookOfSecrets` setter on pickup |
| 13 | **D3 Kalyxo Castle** → **Meadow Blade** + essence 3; **Farore's voice calls out** | built; framing `[DECIDED]` | maiden msg `0x134`. Canon name "Meadow Blade". The callout misdirects toward the ship — works as dramatic irony (see ruling 1); keep her lines location-vague |

## Act II — The Conspiracy Unravels

| # | Beat | Status | Evidence / notes |
|---|------|--------|------------------|
| 14 | **Shrine of Wisdom** (+ Flippers) → **Pendant of Wisdom** → **Dream 1: The Sealing War** | `[DECIDED gate]`, dreams `[PROPOSED timing]` | Maple's Dream Hut sits in the open Abyss — visible early, woven in from here (review note). Dream 1 = Kydrog's fall; early sympathy seed |
| 15 | **D4 Zora Temple** → Zora Mask; Zora conspiracy reveal | built | Requires Shrine of Wisdom + Flippers `[DECIDED]`. Msg `0x135` |
| 16 | Post-D4: Song of Storms; whirlpool dive-warps between worlds | `[IMPLEMENTED]` | `deku_leaf.asm:85-118` → vanilla mirror-warp. `[PROPOSED]` one NPC line: whirlpools = cracks in the weakening seal |
| 17 | **D5 Glacia Estate**: Twinrova — "HE will rise" | `[IMPLEMENTED]` | msgs `0x123`, `0x136` |
| 18 | Defeating Twinrova permanently breaks the Ranch Girl's Cucco curse | `[DECIDED]`, `[TO-BUILD]` | Automatic D5 world-state consequence. No Song of Healing and no instructed return trip. If the player revisits naturally, short reactive dialogue may confirm the change. The old AI-authored `$1FA` Lost Voice quest and Ranch Girl dream are `[CUT]`. Current `ranch_girl.asm` has no D5 branch, and the D5 crystal setter still needs runtime tracing. |
| 19 | **Shrine of Power** (meet the **Eon Gorons**) → **Pendant of Power** | `[DECIDED gate]` | Required for D6. The former Ranch Girl Dream 2 attached here is `[CUT 2026-09-02]`. |
| 20 | **D6 Goron Mines**: Rock Meat trust, minecarts → essence 6 | built (carts WIP) | Requires Shrine of Power `[DECIDED]`. Maiden msg `0x137` |
| 21 | East Kalyxo opens (Hammer); River Zora reconciliation; **possible Sky Islands connection** | WIP; sky link `[PROPOSED per review]` | Review: region currently has little meaning — giving it the sky access would anchor it |

## Act III — The Endgame

| # | Beat | Status | Evidence / notes |
|---|------|--------|------------------|
| 22 | Kaepora → **Song of Soaring** → the Dragon Ship | `[IMPLEMENTED]` | msg `0x146`; `Items/ocarina.asm` song 03 |
| 23 | **D7 Dragon Ship**: pirate-Kydrog fight → **Farore fully freed here** `[DECIDED per review]`; his spirit flees to the Abyss; Somaria Rod | `[TO-BUILD]` | No dragonification here. Finish `kydrog_boss.asm:335-382` scaffold (gated OFF): crystal 7, GameState→3, real rescue scene (replace temp `0x138`). Farore NPC active from here; her POWER remains in the Blade until beat 25 |
| 24 | **Shrine of Courage** (needs Somaria Rod) → **Pendant of Courage** → **Dream 3: the healing revelation** | `[DECIDED gate]`, dream `[PROPOSED]` | Post-D7 by construction. Dream 3 reveals the Abyss-form can be REVERSED — the Song of Healing is the key to saving Kydrog |
| 25 | **Master Sword pulled from the pedestal** (post-D7, pre-D8) — **the transfer scene** | mechanics `[IMPLEMENTED-vanilla]`; scene `[PROPOSED]` | Not forged — pulled. Meadow Blade caps at L3; the pull grants L4. Proposed reconciliation: Farore, present and freed, releases her power from the Meadow Blade into the Master Sword as Link draws it — the engine's sword swap becomes the story beat. Also explains why Kydrog lured Link to the ship: the power he needs has been in Link's hand since D3 |
| 26 | **Sky Islands** (late-game; via East Kalyxo and/or Soaring); Observatory | `[DECIDED scope/timing]`, `[TO-BUILD]` | Map sketches exist (scawful). Observatory's story role now flexible — Dream 3 carries the healing reveal; Observatory can deepen the seal/occupation history `[PROPOSED]` |
| 27 | **D8 Fortress of Secrets**: Voice; Dark Link; at the heart Kydrog assumes his **Abyss form — Kydreeok** | Dark Link `[IMPLEMENTED]`; rest `[TO-BUILD]` | `dark_link.asm:962-975`. `[PROPOSED]` the Voice = the residue's mindless hunger — fragments and wants, not sentences |
| 28 | **Kydreeok finale**: sever all heads simultaneously (they regrow) → **Song of Healing finisher** → Kydrog restored | `[DECIDED]`; `[TO-BUILD]` | `kydreeok.asm` exists, zero messages. Post-healing form `[OPEN #7]` |
| 29 | **Mindless-beast coda** — custom house-style boss, wordless; Farore aids | `[DECIDED custom]`, `[TO-BUILD]` | The residue denied its vessel. Design to house standard (Twinrova/Kydrog/Kydreeok tier), scoped as single-encounter |
| 30 | **Ending**: seal restored; the Abyss begins to heal; credits | `[TO-BUILD]` | Credits hook stubbed (`overworld.asm:17`); no ending text exists. GameState 3 finally gets readers |
| 31 | **Post-game**: Kydrog Mask in the save | `[DECIDED]` | Parting gift; post-game only (menu space) |

## Side content with story weight (not yet reviewed by scawful)

- **Underwater south Abyss / Sea Shrine (0x79) / Eon Zora Elder**: sprites
  exist (First Mirror, crystal-mirror lore). Scope `[OPEN #5]`.
- **Korok minigame**: single contained special map (ruling 2026-02-12).
- **Trading sequence**: CUT (ruling 2026-02-12).

## Text debt (not yet reviewed by scawful)

1. Farore reunion line: replace empty vanilla `$0E`.
2. Merge orphaned maiden rewrite (`Data/dialogue/maiden_upgrades_dialogue.json`)
   + dedupe the four copy-pasted maiden openers.
3. Use the generated dialogue inventory for `0x1CC–0x1F9`; do not copy expanded source into the non-authoritative `messages.org` snapshot.
4. Fill D3 prison (`0x1CC–0x1D1`) + Gossip Stone (`0x1D2–0x1D4`) TODO stubs.
5. Undocumented Twinrova library msg `$1D` (`twinrova.asm:1105`).

## Open and resolved review questions

Question numbers remain stable because other planning documents refer to them.

1. `[PARTIALLY RESOLVED 2026-09-23]` Farore pleads; the goddesses answer by summoning Link. `[DECIDED 2026-09-25]` The summons voice (msg `$1F`, "Accept our quest") is the goddesses, unnamed. The payoff of Farore's interrupted line remains open (proposal: `Plans/experiment_scene_storyboard_2026-09-25.md`).
2. Moon Pearl vs. Minish order in the Abyss tutorial.
3. `[RESOLVED 2026-09-02]` Keep the Ranch Girl and Twinrova connection. D5
   breaks her curse automatically. Cut the Song-of-Healing return quest and
   Ranch Girl dream. Explicitly guide the required early trip to Loom Ranch.
4. Sky access mechanism: East Kalyxo route, Song of Soaring, or both.
5. Underwater south Abyss scope (lore area vs. short shrine dungeon).
6. The Eon Abyss's true name (fine to leave unnamed).
7. Kydrog's post-healing form: Stalfos, or living human self for the farewell?
