# Story/Lore Rule Provenance Audit — Oracle of Secrets

Date: 2026-09-26. Read-only audit. Repo `/Users/scawful/src/hobby/oracle-of-secrets`
(branch `cursor/rg353p-workshop-host`, heavily dirty tree).

**Main finding:** nothing in the repo is **primary** evidence of a scawful story ruling.
- `Docs/Planning/Status/decisions.org` has **0 DECIDED** entries (6 OPEN).
- No `> **Review:**` stamps and no `.plan-reviews/` directory exist.
- No local transcript records the "2026-07-25 plot review". The "19 review annotations"
  that `story_canon_beat_sheet.md` rev 2 cites are not stored anywhere I could find.
- Every story commit carries the `scawful` git identity, including bulk agent doc dumps.
  So git authorship does not prove scawful wrote a line.

Every "scawful ruling" is therefore a **secondary record**: an agent's note that
scawful ruled. I split class A to show this:
- **A1** = primary evidence. None found.
- **A2** = a dated, itemized agent record of a scawful ruling.

## Provenance facts for the authority documents

| Doc | Provenance |
|---|---|
| `Docs/Planning/story_canon_beat_sheet.md` | **Untracked** (`??`). mtime/birth 2026-09-25 18:22. The only git copy is rev 2 (dated 2026-07-25), inside `eeff76df` "chore(preservation): snapshot protected Oracle worktree" (2026-08-06, branch `codex/oracle-dirty-integration`). That is a snapshot, not an authored change. The current header says "revision 3 — 2026-09-02" but the file also holds 09-23 and 09-25 content. |
| `AGENTS.md` rule 4 (line 37-39) | Not in any authored commit. It first appears in the same `eeff76df` preservation snapshot (+3 lines), so it was written by an agent session between 07-25 and 08-06. Today it is an uncommitted `M` again. |
| `decisions.org` | Untracked. Created 2026-09-26 08:19. Only OPEN items. |
| `story_bible.md` "RESOLVED"/"locked" items | `e1b77971` (2026-02-01, "revise story bible v2.0": two-villain-track, pocket-dimension Abyss) and `ec43f1c9` (2026-02-06 bulk "docs: update plans, lore…", "Update story bible with locked decisions"). Both are agent-style bulk commits with no scawful quote. |
| `story_framework.md`, `content_story_planning_review.md` | Created 2026-03-01 in a Claude planning session. `memory/session-notes-2026-02-03.md:33-34` says "Key decisions locked"; the 03-02 pass was "User-verified", but only for code-state facts. |

---

## 1. Summary counts per class

Counts are rules or claims I audited, not every sentence.

| Class | Count | Notes |
|---|---|---|
| A1 (primary evidence) | **0** | No DECIDED in decisions.org, no Review stamps, no quoted scawful commit |
| A2 (dated agent record of a scawful ruling) | **~49** | ~38 distinct rulings behind 42 `[DECIDED…]` tags in the beat sheet, plus 7 in `experiment_scene_storyboard_2026-09-25.md`, 1 RC-definition ruling (`opening_and_rc_development_2026-09-23.md:57`), 2 "ruling 2026-02-12" items (beat sheet:166-167), 1 "user-verified" note (03-02). About 8 of these also carry AI elaborations inside the `[DECIDED]` text (listed in section 2). |
| B (verified in code/ROM) | **16** | Spot-checked with grep and with `z3ed message-read --rom=Roms/oos168x.sfc` (section 4b) |
| C (AI inference stated as rule/lock/canon) | **24** | Top 10 in section 2. The rest are listed after them. |
| X (contradictions) | **16** | Section 3 |

Beat-sheet citation spot-check: 20 of 22 message IDs exist in `Core/messages.org`. `$0E`
is correctly flagged empty. Code citations `farore.asm:221`, `kydrog_boss.asm:335`,
`maku_tree.asm:29`, `twinrova.asm:1105`, `deku_leaf.asm:85` and `custom_tag.asm:33` resolve.
**Stale:** the credits hook `overworld.asm:17` is now `:29-31`, as
`rc_inventory_2026-09-23/README.md:39` already notes.

---

## 2. Top 10 most consequential class-C rules

| # | Rule | Where stated | Why it looks inferred | What it blocks/shapes |
|---|---|---|---|---|
| 1 | "Do not introduce Ganondorf-origin or two-villain plotlines" | `AGENTS.md:37-39`; copied to `~/.context/.../handoffs/oos_task_prompts_2026-09-25.md:44-45`, `claude_rc_test_handoff_2026-09-25.md:42` | The beat sheet never says "two-villain". This is an agent's generalization of rulings 2 and 4. The phrase "two-villain" comes from the Feb **AI** "two-villain-track structure" (`story_bible.md:98`, `kydrog_arc.md:6-12`, commit `e1b77971`) and inverts it. It first appears in a preservation snapshot, not an authored commit. | Drives the proposed rewrite of ROM msg `0x1AD` (`Reviews/dialogue_audit_2026-09-26.md:131`). Scores Impa options as "the two-villain trap scawful has ruled against" (`impa_role_brainstorm_2026-09-26.md:62`), which attributes this rule to scawful. Loaded into every agent via AGENTS/CLAUDE. |
| 2 | Doc canon hierarchy: beat sheet > Story_Event_Graph > narrative_design_master_plan/story_framework/content_review > story_bible > QuestFlow ("its shrine interleave … matched scawful's intent") | `story_canon_beat_sheet.md:15-23` | Agent-authored ranking with no ruling attached. It ranks `narrative_design_master_plan.md` as "honest-status", but that doc's own header says SUPERSEDED (lines 3-9). | Decides which doc wins every conflict below. Keeps `story_framework.md` (Ganondorf finale) above `story_bible.md`. |
| 3 | "Canon reading: the occupation WAS the garrison of the prison; D3 occupation lore and the seal story are one history" | `story_canon_beat_sheet.md:63-67` (inside `[DECIDED per review]`) | The review note asked to "tie the prison to the island's history". The "canon reading" is the agent's interpretation. It conflicts with the 09-23 ruling (Farore's disclosure causes the occupation) and with ROM text (X5). | Shapes attract-scene narration (beat 1), D3 lore, and the Farore reveal in `RC_MASTER_PLAN.md:101`. |
| 4 | MEMORY "Story Decisions (Locked)": Ganondorf origin ambiguous; three-wish Triforce rejected; Zora Princess ≠ D4 maiden; GFX sheet FULL → Triforce icons stay | `memory/MEMORY.md:102-106` | All four trace to the Feb AI story bible (`story_bible.md:439-441`, commit `ec43f1c9`), which has no scawful quote. The first one assumes Ganondorf is in the plot, which the beat sheet now rejects. | Loaded into every Claude session in this repo as "Locked". |
| 5 | "Design decision (locked): Ganondorf's origin is deliberately ambiguous" + "Canonical story decisions: narrative_design_master_plan.md (takes precedence)" | `Plans/story_framework.md:6, 91` | Created 2026-03-01 by an agent. It points precedence at a doc that later declared itself superseded. There is no superseded banner on story_framework itself. | Keeps a full Ganondorf Act III (lines 57-62, 80-100, 161-187) available to any agent reading it. |
| 6 | Vaati is the Shrine of Courage (S3) boss | `Plans/content_story_planning_review.md:16,40,169`; `story_framework.md:132`; `agent_handoff.md` task 3 "S3 Vaati + Courage pendant path"; `MEMORY.md:72` "S3 Vaati reward path" | Not in the beat sheet. No ruling cited. `rc_inventory_2026-09-23/README.md` found no Vaati source, and S3 room `$07` holds a Vitreous-family sprite. | #3 item on the current RC task list. |
| 7 | "Before `$20B`, Ganondorf is NEVER named", plus the drafted "I am Ganondorf" speech and the ID allocation plan | `Plans/critical_path_dialogue_script.md:561, 897` | Status "Draft for human review", yet written as rules. The ROM already names Ganon in `0x16F` (z3ed-verified) and `0x136`, and Ganondorf in `0x1AD` (messages.org). | Reserves message IDs for a finale the beat sheet rejects. |
| 8 | story_bible "Resolved Questions": Abyss = pocket dimension formed by seal pressure; Kydrog "cultivated by Ganondorf"; post-game "after Ganondorf is re-sealed"; Kydrog unnamed; Ranch Girl "cursed into silence" | `World/Lore/story_bible.md:433-442`; `essence_maiden_presentation.md:63-66` enforces them | "RESOLVED" with no source except other AI docs (e.g., "Decided in narrative_design_master_plan.md"). The bible still says "Status: Active Development" with no superseded banner. | Maiden-dialogue rewrite rules (`essence_maiden_presentation.md:64-66`). Also Gemini prompt packs (`scratchpad/gemini_prompts_2026-02-12.md`). |
| 9 | Dreams are a "canon list" to "land before content-locked RC"; Dream 3 = Observatory/Ganondorf "implement first" | `~/.context/.../agent_handoff.md:101`; `Planning/lore_implementation.md:206-217` | The beat sheet tags Dream 1 timing and Dream 3 content as `[PROPOSED]` (lines 138, 153). The handoff promotes them to canon, and lore_implementation still ranks the rejected Ganondorf dream first. | RC scope and task ordering. |
| 10 | "Story Documents (complete, locked)": narrative_design_master_plan, endgame_narrative_arc, Story_Event_Graph | `Plans/content_story_planning_review.md:77-82, 240` | Agent label from 2026-03-01. Two of the three are now superseded or contradicted. `endgame_narrative_arc.md` has no banner and describes a Ganondorf finale. | Tells agents a Ganondorf endgame doc is locked. |

**Other class-C items**, short form:
- `[DECIDED]` blocks with embedded AI elaborations. The ruling itself may be A2; the add-on reasoning is C:
  - Ruling 3 justification "dark-world-transformation logic" (`beat_sheet:69-73`).
  - Beat 23 "his spirit flees to the Abyss" (`:152`).
  - Beat 25 "transfer scene" reasoning, which explains Kydrog luring Link (`:154`, tagged PROPOSED but stated as fact).
  - Beat 12 "Librarian deep lore … via the journal" (`:131`).
  - Ruling 5 "Maku 7-crystal hint must be re-aimed" (`:88-89`).
- `Story_Event_Graph.md:33`, EV-016 "Canonical: Impa grants Mirror in Hall of Secrets" with evidence "Design decision (user confirmation)" 2026-01-24. No record. It may conflict with the 09-23 Mirror-origin ruling.
- `dungeon_narratives.md:21` states the Abyss tutorial order (Moon Pearl found, teaches Minish) as fact, while the beat sheet has it OPEN #2.
- `kydrog_mask_stalfos_form.md:5`: the Kydrog Mask grants a playable Stalfos Form before a Ganondorf fight (see X11).
- `content_story_planning_review.md:9-20`, "Design Decisions (Resolved 2026-03-01)":
  - "Ganondorf Name — gradual revelation" is C.
  - D1-D3 vanilla bosses is A2-weak (user-verified 03-02).
- `story_bible.md:159`: the three-wish rejection. Plausible, but unsourced.
- `impa_role_brainstorm_2026-09-26.md:62`: "scawful has ruled against" two-villain. This attributes C rule #1 to scawful.

---

## 3. Contradictions (X)

| # | Topic | Side A (file:line) | Side B (file:line) | Code/ROM tiebreak |
|---|---|---|---|---|
| X1 | Final villain | Beat sheet: Kydreeok finale → Song of Healing → wordless residue coda, no vanilla Ganon (`story_canon_beat_sheet.md:74-83, 156-158`) | Ganondorf 3-phase final at Lava Lands: `story_framework.md:57-62, 80-91`; `endgame_narrative_arc.md:5, 172`; `critical_path_dialogue_script.md:561`; `story_bible.md:97-98`; `content_story_planning_review.md:95-99`; `kydrog_mask_stalfos_form.md:148, 158` | Kydreeok body is in final room `$00` (per `rc_inventory_2026-09-23`). No ganondorf.asm. Supports the beat sheet. |
| X2 | Master Sword | "Not forged — pulled" (`beat_sheet:154`) | "Master Sword forged" (`story_framework.md:42, 213`; `content_story_planning_review.md:95`; `narrative_design_master_plan.md:540, 584`) | Pedestal receipt patched to ITEMGET `$03` (`Overworld/overworld.asm:75-86`, per rc_inventory). Pull is implemented. |
| X3 | Dream 3 | Healing revelation, `[PROPOSED]` (`beat_sheet:153`) | Observatory: Ganondorf imprisonment (`story_framework.md:43, 147`; `lore_implementation.md:208`; `content_story_planning_review.md:96`) | None in code (dreams are infra only). |
| X4 | Which doc is canonical | `narrative_design_master_plan.md:3-9` SUPERSEDED; beat sheet is top (`beat_sheet:16`) | `story_framework.md:6, 253` says narrative_design_master_plan "takes precedence"; `content_story_planning_review.md:77, 240` "locked" | — |
| X5 | Why Hyrule came / Farore's role | 09-23 `[DECIDED]`: Farore warns the Zora, turns to Hyrule, and her disclosure helps cause the occupation (`beat_sheet:33`). Ruling 2: occupation = prison garrison (`:64-67`). | ROM `0x136` (z3ed-verified): "Farore was wise in hiding out here, but the arrival of the Hylian forces drew attention to her presence". ROM `0x112`: Hylians invaded driven by legends of the Golden Power. | ROM text contradicts the newest ruling. Needs a text change or a reconciliation. |
| X6 | Ganondorf named in shipped text | AGENTS rule 4 (`AGENTS.md:39`); ruling 2 "OoT-timeline 'Ganondorf in hiding' framing rejected" (`beat_sheet:68`) | `Core/messages.org:1714-1716` msg `0x1AD` "he fell to the tricks of Ganondorf, king of thieves"; `0x16F` "moreso than Ganon" (ROM-verified); `MEMORY.md:103` assumes Ganondorf exists | `0x1AD` is expanded (z3ed max id 396), so **ROM text is not verified**, and messages.org is a stale snapshot. |
| X7 | Two villains | `AGENTS.md:39` forbids two-villain plotlines | `story_bible.md:97-98` "Two villain tracks converge"; `kydrog_arc.md:6-12` "Two-Villain-Track Structure (2.0)"; `essence_maiden_presentation.md:28, 65` requires maidens to fit it | — |
| X8 | Dungeon numbering | D1 Mushroom Grotto, D2 Tail Palace, D3 Kalyxo Castle, D4 Zora Temple, D7 Dragon Ship (`beat_sheet:128-152`; `oracle-progression.md:56-62`) | `~/.context/knowledge/hobby/oracle-of-secrets.md:575-581`: D1 Tail Palace, D2 Mushroom Grotto, D3 "prison", D4 "Water Gate dungeon", D7 Kalyxo Castle | `Core/sram.asm:112-118` `!Crystal_D1_MushroomGrotto` … `!Crystal_D7_DragonShip` (also HEAD `:104-110`). The knowledge file is wrong. |
| X9 | What the Abyss is | Ruling 2 "The Eon Abyss is the prison" (`beat_sheet:58`) | story_bible v2: pocket dimension formed by seal pressure (`e1b77971`; enforced at `essence_maiden_presentation.md:66`) | ROM `0x15B`: "a dark reflection of Kalyxo" |
| X10 | Opening voice | `beat_sheet:182` `[DECIDED 2026-09-25]` goddesses, unnamed; `experiment_scene_storyboard_2026-09-25.md:7-8` | `beat_sheet:122` (beat 3 row) "Voice identity stays mysterious `[OPEN #1]`" (stale row, same file) | ROM `0x1F` "Accept our quest" (neutral) |
| X11 | Kydrog Mask | Post-game only, parting gift (`beat_sheet:160`) | Grants playable Stalfos Form right after Kydreeok, before the Ganondorf fight (`kydrog_mask_stalfos_form.md:5, 148-158`) | — |
| X12 | Zora Princess placement | Mid-dungeon, after the big key, NOT the maiden (`MEMORY.md:105`; `story_bible` via `ec43f1c9`) | `Sprites/NPCs/zora.asm:12` comment "D4 boss room"; `ZoraTemple_Map.md:37, 528` "room 0x105 is outside the D4 room range" | `zora.asm:57` dispatches on ROOM `$0105` (B). Location is still unresolved. |
| X13 | Meadow Blade level | "Meadow Blade caps at L3; the pull grants L4" `[IMPLEMENTED-vanilla]` (`beat_sheet:154`) | `Sprites/Enemies/custom_guard.asm:61` "Meadow Blade (sword level 2)"; `QuestFlow.md:83` "Lv2 Sword" | ITEMGET `$03` is consistent with L4 at the pedestal. The source of L3 is unverified. |
| X14 | GameState=2 setter | `Story_Event_Graph.md:50` "GameState=$02 setter NOT found" | `Sprites/NPCs/farore.asm:221` `LDA #$02 : STA $7EF3C5` | Code confirms the setter exists. Event graph is stale. |
| X15 | Ranch Girl | Cucco curse, broken automatically at D5, no return quest (`beat_sheet:99-114, 143`) | `story_bible.md:436` "cursed into silence"; old Lost Voice `$1FA` quest (cut per `narrative_design_master_plan.md:614`) | `ranch_girl.asm` has no D5 branch (beat sheet `:143`) |
| X16 | Beat sheet self-consistency | Header "revision 3 — 2026-09-02" (`:3-4`) | Body contains 2026-09-23 and 2026-09-25 rulings (`:27-45, 182`). File untracked. Credits citation stale (`:159`) | — |

---

## 4. Class A rulings confirmed, with their evidence

### 4a. A1 (primary evidence): **none found**
I searched:
- `decisions.org`
- Review stamps, `.plan-reviews/`
- git history (`-S` on key phrases)
- local Claude transcripts for this repo, including the worktree dirs
- `~/.context/projects/oracle-of-secrets/scratchpad/{sessions,handoffs}`
- `~/src/folio`

The 07-25 review, the 09-02 Ranch Girl follow-up and the 09-23 discussion likely took place in cloud sessions (`cse_…`). `memory/cloud-session-logs.md` says those are readable through RemoteTrigger `get_run_log` from the main session. That is the one place primary evidence might still exist.

### 4b. A2 (dated agent record of a scawful ruling), strongest first
| Ruling | Recorded at | Corroboration |
|---|---|---|
| Opening scene rev 2: skip with Start; Stalfos rises from the ground; arrival voice = goddesses, unnamed; M1a/M1b approved, M2 = option A; portal rules stay in flux; new GBC-style Abyss Stalfos sprite; Kalyxo shots keep the pirate look | `Plans/experiment_scene_storyboard_2026-09-25.md:5-12, 44-51` | Itemized, dated, answers numbered questions. Strongest record. |
| RC definition: all main dungeons, shrines and ending playable; no content lock | `Plans/opening_and_rc_development_2026-09-23.md:57` "User ruling (2026-09-23)" | — |
| 09-23 opening/island-history set (Mirror breakthrough triggers Hyrule's interest; Abyss eerie; Farore warns the Zora; mixed views of Hylians; attract covers island history; new-game Mirror scene skeleton; patrol half-heart damage; keep western-forest meeting and ambush) | `beat_sheet:29-38` "Accepted by scawful during the opening storyboard discussion" | `opening_and_rc_development_2026-09-23.md:20, 32` "Accepted outline/skeleton" |
| Origins follow-up (keep Abyss→Origins→Owl sequence; extend the Minish puzzle modestly; stronger Moon Pearl presentation, **user-confirmed NES→GBC Link**; one post-Pearl disturbance) | `beat_sheet:40-45` | Same session record |
| Ranch Girl ruling 7: guided Ocarina witness; D5 breaks the curse automatically; no return quest, no dream | `beat_sheet:99-114, 184` `[DECIDED 2026-09-02]` | `narrative_design_master_plan.md:614` banner (same agent lineage, not independent) |
| Farore bound to the Meadow Blade; D3 callouts stay location-vague ("confirmed working") | `beat_sheet:52-57` | **B:** ROM `0x70` "it is I, Farore, bound within the Meadow Blade" (z3ed) |
| Custom house-style beast coda, not vanilla Ganon ("scawful overrode the vanilla-reuse proposal") | `beat_sheet:79-83` | Most specific attribution in the 07-25 set |
| Kydreeok = Kydrog's Abyss form; sever-all-heads mechanic; Song of Healing finisher | `beat_sheet:69-78, 157` | `kydreeok.asm:80-120` head regrowth (per rc_inventory) |
| Shrine gates: Wisdom+Flippers → D4; Power → D6; Courage needs Somaria (post-D7) | `beat_sheet:84-89` `[DECIDED per review]` | `QuestFlow.md:85-127` chapter order matches, as the beat sheet itself notes |
| Sky Islands, full 8-map, late-game; Farore freed at D7; Book of Secrets unlocks the Journal; Kydrog Mask post-game | `beat_sheet:91-95, 131, 152, 155, 160` | No independent record |
| Korok minigame is a single special map; trading sequence CUT (ruling 2026-02-12) | `beat_sheet:166-167` | No independent record |

### 4c. B facts verified this audit (tiebreakers)
- Crystal bits and dungeon identities: `Core/sram.asm:112-118` (HEAD `:104-110`).
- GameState=2 is set at `Sprites/NPCs/farore.asm:221`.
- D7 rescue is gated OFF: `Sprites/Bosses/kydrog_boss.asm:335`.
- ROM text read with `z3ed message-read --rom=Roms/oos168x.sfc`:

  | Msg | Content |
  |---|---|
  | `0x70` | Farore bound within the Meadow Blade |
  | `0x136` | failed Ganon revival; Farore was hiding |
  | `0x15B` | Abyss is a "dark reflection"; Golden Power changes your form |
  | `0x1F` | "Accept our quest" |
  | `0x25` | Impa sent by Zelda |
  | `0x35` | Impa "had to flee", now in the Hall of Secrets |
  | `0x16F` | "moreso than Ganon" |

- `0x112` comes from `Core/messages.org:900` (snapshot only).
- Zora Princess dispatch is on ROOM `$0105` (`zora.asm:57`).
- `Menu_DrawTriforceIcons` exists (`Menu/menu.asm:137`).

---

## 5. Questions scawful must answer (one line each)

1. Did you rule all 7 beat-sheet "core rulings" yourself, and can you point to the 07-25 session (cloud `cse_` id) holding your 19 annotations?
2. Is Ganondorf in the story at all: keep or rewrite ROM msg `0x1AD` ("tricks of Ganondorf") and `0x16F` ("than Ganon")?
3. Keep, reword, or drop AGENTS.md rule 4 ("no Ganondorf-origin or two-villain plotlines"), since an agent wrote it?
4. Who brought Hyrule to Kalyxo: Farore's disclosure (09-23 ruling), or a legend-driven invasion while Farore hid (msgs `0x112`/`0x136`)?
5. Is Vaati the Shrine of Courage boss, or is that cut?
6. Are Dream 1 (Sealing War) and Dream 3 (healing revelation) in RC scope, or proposals only?
7. Kydrog Mask: post-game keepsake only, or a playable Stalfos Form?
8. Zora Princess: inside D4 or in the separate room `0x105`, and is she distinct from the D4 maiden?
9. Sword ladder: Meadow Blade = L2 at D3, then where does L3 come from before the pedestal's L4?
10. Delete the four MEMORY.md "Story Decisions (Locked)" lines and mark story_bible/story_framework/endgame_narrative_arc/critical_path_dialogue_script SUPERSEDED, making the (committed) beat sheet the only authority?
