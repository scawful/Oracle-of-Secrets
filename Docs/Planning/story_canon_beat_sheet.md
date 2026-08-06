# Story Canon Beat Sheet

Date: 2026-07-25 (revision 2 — incorporates scawful's 19 review annotations)
Authority: rulings by scawful during the 2026-07-25 plot review session.
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

## Core rulings (the six cruxes)

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
| 10 | Ocarina chain: cursed Ranch Girl → Ocarina → Song of Healing → Deku Mask | `[IMPLEMENTED]` | msgs `0x17D`, `0x140/0x141` |
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
| 18 | Ranch Girl's voice restored (Song of Healing, post-D5) | `[OPEN #3]` | Beat originated in AI docs (planned msg `$1FA`); the curse half IS implemented (`0x17D`). Recommend keep as the D5 payoff — scawful to confirm or cut |
| 19 | **Shrine of Power** (meet the **Eon Gorons**) → **Pendant of Power** → **Dream 2: Ranch Girl's Secret** | `[DECIDED gate]`, dream `[PROPOSED timing]` | Required for D6. Dream 2 post-D5 fits (Twinrova just revealed) |
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
3. Document ROM-only msgs `0x1CC–0x1F9` in `messages.org` (46 messages).
4. Fill D3 prison (`0x1CC–0x1D1`) + Gossip Stone (`0x1D2–0x1D4`) TODO stubs.
5. Undocumented Twinrova library msg `$1D` (`twinrova.asm:1105`).

## Open questions

1. Opening telepathic voice identity + the payoff of Farore's interrupted line.
2. Moon Pearl vs. Minish order in the Abyss tutorial.
3. Ranch Girl restoration beat: keep (recommended) or cut?
4. Sky access mechanism: East Kalyxo route, Song of Soaring, or both.
5. Underwater south Abyss scope (lore area vs. short shrine dungeon).
6. The Eon Abyss's true name (fine to leave unnamed).
7. Kydrog's post-healing form: Stalfos, or living human self for the farewell?
