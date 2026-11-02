# Story Canon Beat Sheet

Date: 2026-10-21 (revision 15; internal Power Glove, cut seed-forge quest, optional Lupo and local Lyra Meat)
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

Implementation order and storyboard: [Opening and RC development plan](/Users/scawful/.context/projects/oracle-of-secrets/scratchpad/archive/repo-slim-2026-10-06/repo/Docs/Planning/Plans/opening_and_rc_development_2026-09-23.md). New-game experiment hook comes last; title, summons/arrival, and village sprites come first.

## Core rulings (the seven cruxes)

1. **Farore hides her power in the Meadow Blade until the pedestal scene** `[DECIDED]`.
   `[DECIDED 2026-10-20]` Kydrog abandons his guardian sword first; Farore
   subsequently hides her power inside it. She chooses it because it retains
   a connection to the prison from Kydrog's guardianship `[DECIDED 2026-10-20]`.
   He kidnapped her
   body to force its release. The D3 callout exists, but the older `0x70`
   inventory explicitly identifies the blade as her vessel; intended ambiguity
   needs live-text verification and revision. Keep the earlier callouts
   location-vague so D7 can reveal their source `[DECIDED framing;
   TO-VERIFY / TO-REVISE text]`. `[DECIDED 2026-10-20]`
   Farore reveals the blade's hidden power by helping Link during D7;
   Kydrog learns where it is through that intervention. Body rescued at D7;
   `[DECIDED 2026-10-20]` At the Master Sword pedestal (beat 25), Farore takes
   her power back into herself and keeps the Meadow Blade while Link draws
   the Master Sword. This replaces the power-into-Master-Sword proposal.
2. **The Eon Abyss is the prison** `[DECIDED, partial adoption]`.
   **Villain chain** `[DECIDED 2026-09-26, `Docs/Planning/Status/decisions.org` "Villain chain";
   replaces the earlier "Ganon residue" / garrison reading]`:
   1. Farore warns the island's scholars, then turns to Hyrule; Hyrule sends a
      garrison "to guard the Golden Power" (islanders see an invasion; msg
      `0x112` stands). D3 Kalyxo Castle's occupation lore and the seal story
      are one history.
   2. Farore makes Kydrog, a garrison knight, the prison's guardian.
   3. The prison corrupts him; he dies and rises as the Stalfos Pirate King;
      his dead men are his crew. He abandons the sword (the Meadow Blade).
      Farore subsequently hides her power inside it `[DECIDED 2026-10-20]`;
      this replaces the earlier binding-at-appointment account.
   4. The prison holds the half-revived beast Ganon from the Oracle games'
      failed revival (msg `0x136`). Twinrova hunt essences to finish it and
      die in D5; Kydrog carries the revival on and kidnaps Farore's body to
      force the key.
   5. Kydrog's motive is tragic: the prison promises the Golden Power can
      bring his men back. His pirate-skeleton humor is a coping mechanism for
      his death and his men's deaths.
   Present limitation selected in the 2026-10-20 review: Ganon needs
   Kydrog's guardian access and Farore's Oracle authority to alter his
   imprisonment. `[OPEN]` The exact mechanism and Ganon's failed-revival /
   surviving-consciousness history remain under review; the September 26
   account above is not a mandate for new exposition before that choice.
3. **Dark Link and Kydreeok are both Kydrog's Abyss forms**
   `[DECIDED 2026-10-20]`. Encounter order: Dark Link in the Fortress,
   Kydreeok in the prison, then Ganon. The Golden Power reshapes forms
   (msg `0x15B`); the shadow-Link origin proposal and exact dialogue remain
   open. No TotK dragon-tear mechanic is implied.
4. **Kydreeok finale; player-performed Song of Healing; Ganon confrontation**.
   Fight first, redemption second: sever the heads, they regrow — all heads
   must be down simultaneously to win `[DECIDED mechanics]`. Then the Song of
   Healing frees the knight: Kydreeok is the prison's corruption of him, not
   his heart. Post-healing form: human `[DECIDED 2026-09-26, villain chain]`.
   Ganon's Ganondorf / beast phases remain the established fight direction.
   `[OPEN 2026-10-20]` Reconcile the older literal-breakout staging with his
   need for Farore; healing Kydrog alone is not an established release
   mechanism. Kydrog's voluntary response, biological/spirit status and
   Farore's exact final scene remain open. Multi-character combat
   choreography is not a requirement; fixed NPC transition scenes are the
   bounded proposal.
5. **The three pendant shrines move to the Lyra Sea / East Kalyxo region; their dreams return
   Link to Maple's Abyss hut** `[DECIDED 2026-10-19]`:
   - **Shrine of Wisdom** → pendant → Sea Zora Flippers gift → **D4 Zora Temple**.
     A scripted boat from Kalyxo Docks reaches the Sea Zora before Flippers.
     Wisdom is their shrine, in a separate building from their homes.
     Its dry approach may connect a nearby islet to their settlement. The
     pendant proves Link's heroism: the suspicious Sea Zora grant Flippers
     and warn of River Zora aggression/conflict. Link retains the pendant.
     Flippers allow ordinary swimming toward Kalyxo and limited Lyra exploration;
     rough currents require Zora Link `[DECIDED 2026-10-20]`.
   - **Shrine of Power** → before **D6 Goron Mines**. The guest shrine does
     not contain the Eon Gorons; their story and Rock Meat route are separate.
     Place it east of the desert, accessible with D6-stage items and no
     Hammer `[DECIDED 2026-10-21]`. Shrine of Power is the Power Glove-focused
     dungeon. Keep its internal Power Glove grant; no early Glove or Ember
     Seed/forge grant quest `[DECIDED current direction 2026-10-21]`.
     Rock Meat is hidden on nearby Lyra maps; Eon Goron/Lupo Mountain is optional.
     Exact Meat placement/return is `[OPEN]`; no Mitt/Hammer/Lupo prerequisite.
   - **Shrine of Courage** requires the Somaria Rod (D7 item) → post-D7 only.
     Place it on the jungle island, superseding the glacier suggestion
     `[DECIDED regional direction 2026-10-20]`; exact map/entrance remains open.
   Reuse the guest interiors; each ends in its pendant, distinct from its
   internal item chests. Power keeps its separate Glove and pendant chests;
   the early-Glove/Mitt replacement proposal is superseded by this direction.
   Exact island gates and the revised Goron route remain `[OPEN]`; physical
   relocation and gating require verification. Maku Tree's seven-essence
   direction must distinguish late Courage from Sky's eighth essence.
6. **Sky tower and islands are the required D8, after D7 Dragon Ship**
   `[DECIDED 2026-10-19]`. Somaria remains the Ship's reward and is required in
   Sky. Preserve Ship -> Shrine of Courage / Dream 3 -> Master Sword before
   Sky, then the shorter Fortress and volcano finale.
   `[DECIDED 2026-10-20]` Rescuing Farore on the Ship begins
   a playable partnership through Sky D8, giving her time to provide context
   and helping the Sky islands feel distinct. `[DECIDED 2026-10-20]` Express
   this through selected NPC placements using her available sprite; a
   continuous follower system is not required. Exact placements, useful
   interactions and dialogue remain to be designed. `[DECIDED 2026-10-20]` After Sky, return
   to the Maku Tree with all eight essences; the Maku Seed opens the visible
   obstruction at the Fortress entrance. Plan the Fortress at Abyss `$4B`,
   Kalyxo Castle's counterpart, and Lupo at former Fortress `$5E`.
   This is planning direction, not a claim of changed ROM terrain or exits.
   Exact approaches remain open. The tower is the only
   first entrance; Song of Soaring does not bypass it. Preserve the earlier
   Soaring acquisition and its usefulness throughout the longer late game and
   later revisits. The Watchers built the tower and sky structures; Hyrule's
   garrison later reused the lower floors and abandoned them. Remove the Korok
   Cove test bridge. `cloud_bridge.asm` is existing traversal support; new Sky
   puzzles, item and boss remain `[TO-BUILD]` / `[OPEN]`.
   Implement the scripted Sea Zora boat approach. Power and D6 have no Hammer
   requirement `[DECIDED 2026-10-21]`. Collect Rock Meat near Power in Lyra
   and return to the desert Goron for the existing Mines opening. Lupo/Eon
   Gorons remain optional; exact hiding places/return still need design.
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
| 10 | Guided Ocarina chain: D1 Mushroom → witches / Magic Powder → investigate missing Ranch Girl at Toto Ranch → reveal the strange Cucco temporarily → Ocarina → Mask Salesman at Tail Pond → Song of Healing → Deku Mask | source wiring present; guidance `[DECIDED]`; rendered/player flow `[TO-VERIFY]` | Required hint facts: Twinrova sought essences; Ranch Girl vanished; a strange Cucco appeared; Magic Powder reveals transformed creatures. Current source uses Elder `0x1CB` and Ranch Girl `0x1BE`, replacing the older `0x177`/`0x17D` text. Ranch source sets the Tail Pond objective after the Ocarina receipt. Review the chain for missing Cucco/Powder guidance rather than rewriting connections already present. Maku `0x1C5` is a generic one-crystal reaction; `Core/messages.org` is a review snapshot. |
| 11 | **D2 Tail Palace** → essence 2 | built | maiden msg `0x133` |
| 12 | **Book of Secrets**: library dash knockdown; preserve its gameplay function | item code exists; Journal `[DEFERRED 2026-09-29]` | `Items/book_of_secrets.asm`. The later Journal ruling supersedes the earlier Book-unlocks-Journal plan: remove X:LOG and suspend Journal menu entry points. No replacement Journal access or new pickup setter is selected. Deliver required lore through NPCs, dreams and the environment; Librarian lore `0x199–0x19F` remains material for review. |
| 13 | **D3 Kalyxo Castle** → **Meadow Blade** + essence 3; **Farore's voice calls out** | built; framing `[DECIDED]`; callout text `[TO-VERIFY / TO-REVISE]` | maiden msg `0x134`. Canon name "Meadow Blade". Keep callouts location-vague until Farore helps Link during D7; the older `0x70` inventory currently discloses the vessel (see ruling 1). |

**Glove direction reconciled, 2026-10-21:** no early Glove and no Ember Seed/forge grant quest. The required D3 garden/Compass Glove gate is superseded; required D3 progress must work with Gloves=0. Preserve current Compass placement until any new garden design is chosen. Book remains the library dash pickup. Power grants the Glove; nearby Lyra Meat supports the existing Goron opening without a mandatory Abyss/Lupo trip.

## Act II — The Conspiracy Unravels

| # | Beat | Status | Evidence / notes |
|---|------|--------|------------------|
| 14 | **Docks boat → Sea Zora / dry Wisdom approach → Pendant of Wisdom → Sea Zora trust / Flippers gift**; **Dream 1 via Maple** | gift order `[DECIDED 2026-10-20]`; dream timing/route `[OPEN]`; staging `[TO-BUILD]` | Separate shrine and homes; a connected islet is allowed. The pendant proves heroism; Sea Zora grant Flippers and warn of River Zora aggression/conflict. Link retains it. Current dreams start by speaking to Maple, not by automatic pendant transport; bind a reachable visit and hut wake (`$68` to `$0F` on `$5D`) without assuming a pre-Flippers journey. Dream 1 shows the Captain's guardianship/temptation; revise appointment text so Farore's power is not already in his sword. Ordinary swimming allows Kalyxo return/limited sea; currents require Zora Link. Temporary island Save/Exit respawn stays `[PROPOSED]`. |
| 15 | **D4 Zora Temple** → Zora Mask; Zora conspiracy reveal | built | Requires Shrine of Wisdom + Flippers `[DECIDED]`. Msg `0x135` |
| 16 | Post-D4: Song of Storms; whirlpool dive-warps between worlds | `[IMPLEMENTED]` | `Sprites/Objects/deku_leaf.asm:85-118` → vanilla mirror-warp. `[PROPOSED]` one NPC line: whirlpools = cracks in the weakening seal |
| 17 | **D5 Glacia Estate**: Twinrova — "HE will rise" | `[IMPLEMENTED]` | msgs `0x123`, `0x136` |
| 18 | Defeating Twinrova permanently breaks the Ranch Girl's Cucco curse | `[DECIDED]`, `[TO-BUILD]` | Automatic D5 world-state consequence. No Song of Healing and no instructed return trip. If the player revisits naturally, short reactive dialogue may confirm the change. The former Lost Voice quest and Ranch Girl dream are `[CUT]`; `$1FA` is now allocated to the Eon Owl arrival line. D5 reaction and world-state behavior still need implementation review. |
| 19 | **Shrine of Power east of the desert → Pendant of Power → Dream 2: Farore's appeal to Hyrule** | internal-Glove/no-forge/optional-Lupo direction `[DECIDED 2026-10-21]`; exact exterior/Meat layout `[OPEN]` | Accessible with D6-stage items and no Hammer. Keep Glove chest `$74` and pendant big chest `$73`; nearby Lyra maps supply Rock Meat using basic Glove. No mandatory Mitt/Lupo trip and no Eon Gorons inside. Dream 2 keeps Farore/king/garrison (`0x206–0x20B`). |
| 20 | **D6 Goron Mines**: Goron story, minecarts → essence 6 | built core (carts WIP); Lyra Meat placement `[TO-BUILD]` | No Hammer requirement. Keep the five-Meat opening as working baseline; Meat is near Power in Lyra, with Lupo/Eon Gorons optional `[DECIDED current direction 2026-10-21]`. Shrine of Power precedes D6. Maiden msg `0x137`. |
| 21 | East Kalyxo opens (Hammer); River Zora reconciliation; approach to the **Sky tower** | WIP; Sky D8 order `[DECIDED 2026-10-19]`, `[TO-BUILD]` | The tower east of Korok Cove is the only first Sky entrance. Required Sky progression follows the Ship and needs Somaria. Lower floors are Hylian garrison ruins; upper floors expose Watcher construction. |

## Act III — The Endgame

| # | Beat | Status | Evidence / notes |
|---|------|--------|------------------|
| 22 | Kaepora → **Song of Soaring** → the Dragon Ship | `[IMPLEMENTED]` | msg `0x146`; `Items/ocarina.asm` song 03 |
| 23 | **D7 Dragon Ship**: Farore helps Link and reveals the blade's hidden power to Kydrog → pirate-Kydrog defeated → **Farore freed**; his spirit flees to the Abyss; Somaria Rod | reveal and partnership `[DECIDED 2026-10-20]`; `[TO-BUILD]` | No dragonification here. Finish `kydrog_boss.asm:335-382` scaffold (gated OFF): crystal 7, GameState→3, real rescue scene (replace temp `0x138`). Rescue begins Farore's playable partnership through Sky D8. Her POWER remains in the Blade until beat 25. Exact intervention and Kydrog's revised plan need design. |
| 24 | **Jungle-island Shrine of Courage** (needs Somaria Rod) → **Pendant of Courage** → **Dream 3: the healing revelation** | jungle direction `[DECIDED 2026-10-20]`; late gate/Captain text `[DECIDED]` | Post-D7. Jungle supersedes the glacier suggestion. Exact map/entry remains open. The Captain himself teaches Link that Kydrog can be reached through the Song of Healing. Each pendant dream returns to Maple's Abyss hut. |
| 25 | **Farore reclaims her power and keeps the Meadow Blade; Link draws the Master Sword** (post-D7, pre-D8) | handoff `[DECIDED 2026-10-20]`, `[TO-BUILD]`; sword pull `[IMPLEMENTED-vanilla]` | Not forged — pulled. Meadow Blade caps at L3; the pull grants L4. Farore's power returns to herself, replacing the earlier transfer-into-Master-Sword proposal. Exact staging and the blade's later role remain design work. The old explanation that Kydrog knowingly lured the blade to D7 is superseded by his learning its contents during her D7 intervention. |
| 26 | **D8 Sky tower and islands** -> eighth main-dungeon essence; **Farore participates at selected encounters** | `[DECIDED 2026-10-19/20]`, `[TO-BUILD]` | Somaria is required. Farore uses fixed scene placements rather than continuous following; exact stops and a useful interaction remain design work. Earlier Soaring remains useful through this longer late game and later revisits. Exact puzzles, item and boss remain open; the separate one- or two-room Watchers building is not automatically the boss arena. |
| 27 | **Maku Tree → Maku Seed → shorter Fortress of Secrets**: the Seed clears its visible entrance obstruction; Dark Link is Kydrog | Seed entry and identity `[DECIDED 2026-10-20]`; redesign `[TO-BUILD]` | Return to the Tree after Sky's eighth essence. The Seed replaces the old Master Sword entrance barrier. Plan the Fortress on Abyss `$4B`, mirroring Kalyxo Castle; Lupo moves to old Fortress `$5E`. Exact approaches and physical relocation remain to build/verify. Kydrog becomes Kydreeok at the volcano before room `$00`. The route from Fortress to prison remains design work. |
| 28 | **Kydreeok finale**: sever all heads simultaneously (they regrow) → **Song of Healing finisher** → Kydrog restored | `[DECIDED]`; `[TO-BUILD]` | `kydreeok.asm` exists, zero messages. Post-healing form: human `[DECIDED 2026-09-26]` |
| 29 | **Ganon confrontation** — Ganondorf / beast; Farore's role staged separately | fight direction `[DECIDED]`; transition/binding `[OPEN]`, `[TO-BUILD]` | The older breakout wording needs a cause consistent with Ganon needing others to change his confinement. A short NPC transition and solo fight are the current bounded proposal; simultaneous Farore/Kydrog combat mechanics were not approved. |
| 30 | **Ending**: seal restored; the Abyss begins to heal; credits | `[TO-BUILD]` | Credits hook stubbed in `Overworld/overworld.asm`; no ending text exists. GameState 3 finally gets readers. |
| 31 | **Post-game**: Kydrog Mask in the save | `[CUT 2026-10-18]` | Cut; the Garo mask from the Garo desert replaces it |

## Side content with story weight

- **Underwater south Abyss shrine**: medium, five-room, keyless mini-dungeon
  with a short route and mini-boss `[DECIDED 2026-09-27]`. Exact lore, reward,
  entrance, and Eon Zora Elder role remain open.
- **Korok minigame**: single contained special map (ruling 2026-02-12).
- **Trading sequence**: CUT (ruling 2026-02-12).

## Text debt (not yet reviewed by scawful)

1. Review the maiden voices and essence objective. The orphaned
   `Data/dialogue/maiden_upgrades_dialogue.json` is a draft reference, not the
   authoritative current dialogue.
2. Use the generated dialogue inventory for `0x1CC–0x1F9`; do not copy expanded source into the non-authoritative `messages.org` snapshot.
3. Review D3 prison (`0x1CC–0x1D1`) and Gossip Stone (`0x1D2–0x1D4`) stubs.
   Check D3 callout `$070`: the older inventory snapshot explicitly names the
   blade as Farore's vessel, which conflicts with a player-facing D7 reveal.
   Verify the live vanilla text before writing its replacement.
4. Undocumented Twinrova library msg `$1D` (`twinrova.asm:1105`).
5. Review Wisdom dream `$205` ("Keep the seal, Captain. This blade is its key.")
   and appointment staging against the 2026-10-20 timing ruling: Farore hides
   her power after Kydrog abandons the sword. The appointment must not imply
   her power is already inside it. scawful permits cutscene changes to align
   with the plot synthesis; replacement dialogue remains to be written.

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
7. `[REVIEW OPEN 2026-10-20]` Kydrog's restored human appearance remains the established direction; the older "living human self" wording needs a ruling on biological life versus a spirit's Abyss form. Do not infer a general resurrection power or his crew's restoration.

Late-route open work (2026-10-20): implement the eighth essence award/display/readers, Seed receipt/entry and pedestal handoff scenes; author the required Sky Somaria route; settle Kydrog's post-D7 plan and post-healing choice, the Meadow Blade's later role, relocation approaches and Fortress-to-prison transition. Build the scripted Sea Zora arrival/dry Wisdom/gift route and resolve the pre-D6 Goron route before writing directions. Roc's Cape and Heliarch remain unconfirmed concepts. Current delivery plan: `~/.context/projects/oracle-of-secrets/scratchpad/handoffs/christmas_completion_2026-10-20/PLAN.md`. Current plot and Ridoyie/Yaze writer packet: `~/.context/projects/oracle-of-secrets/scratchpad/handoffs/ridoyie_messages_2026-10-20/`.
