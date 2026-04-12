# Oracle of Secrets — Story Framework

**Created:** 2026-03-01
**Status:** Reference Document (proposals from planning session, not all confirmed in code)
**Companion to:** `content_story_planning_review.md`
**Canonical story decisions:** `narrative_design_master_plan.md` (takes precedence on conflicts)

---

## Narrative Structure

Oracle of Secrets follows a **three-act structure** with escalating stakes:

### Act I: The Island's Wounds (D1-D3)

**Theme:** Discovery — Link learns Kalyxo is broken, and someone is pulling the strings.

| Beat | Dungeon | Narrative Function |
|------|---------|-------------------|
| Intro | — | Link arrives on Kalyxo, meets Maku Tree, learns of dimensional rifts |
| D1 Mushroom Grotto | Manhandla | First dungeon, establishes the corruption spreading through nature |
| D2 Tail Palace | Moldorm | Deku Scrub quest (D1 mushroom -> magic powder), Song of Healing taught by Mask Salesman |
| DREAM 1 | — | The Sealing War — vision of Kydrog's origin as a fallen hero |
| D3 Kalyxo Castle | Eyegore Knights | Prison escape sequence, King's Sword obtained, castle occupation revealed |

**Key NPCs:** Maku Tree (guide), Impa (quest giver), Village Elder (local knowledge), Mask Salesman (Song of Healing), Deku Scrub (transformation victim)

**Player understands by end of Act I:** Kalyxo is occupied, rifts connect to the Eon Abyss, someone named Kydrog is behind it.

### Act II: The Conspiracy Unravels (D4-D6 + Shrines)

**Theme:** Revelation — The Zora schism was manufactured, Twinrova serves a greater evil, the Gorons' trust must be earned.

| Beat | Dungeon | Narrative Function |
|------|---------|-------------------|
| D4 Zora Temple | Advanced Arrghus | Zora Princess reveals Kydrog manufactured the Sea/River Zora war |
| SONG OF HEALING | — | Princess's dying revelation; Zora Baby's memory recovered |
| D5 Glacia Estate | Twinrova | Frozen noble estate hides a portal site; Twinrova serves "the King" |
| DREAM 2 | — | Ranch Girl's curse — Twinrova silenced her for witnessing their arrival |
| D6 Goron Mines | King Dodongo | Minecart dungeon; Hammer obtained; Goron trust restored |
| East Kalyxo | — | River Zora reconciliation scene (post-D6, Hammer required) |
| Shrines S1-S3 | S3: Vaati | Pendants collected, Master Sword forged |
| SKY ISLANDS | — | Observatory vision (Dream 3: Ganondorf's imprisonment revealed) |

**Key NPCs:** Zora Princess (truth-teller), Zora Baby (witness), Twinrova (servants of Ganondorf), Ranch Girl (Twinrova's victim), Goron Elder (trust arc), River Zora Elder (reconciliation)

**Player understands by end of Act II:** Kydrog was a puppet. Twinrova works for someone worse. The real enemy is sealed in the Lava Lands. Master Sword is needed.

### Act III: The Endgame (D7-D8 + Final Boss)

**Theme:** Confrontation — Rescue Farore, face Kydrog's true form, hear Ganondorf's name for the first time.

| Beat | Dungeon | Narrative Function |
|------|---------|-------------------|
| D7 Dragon Ship | Kydrog | Rescue Farore; Kydrog defeated; endgame unlocked |
| FARORE RESCUED | — | GameState=$03; shrine guidance active; D8 path opens |
| D8 Fortress of Secrets | Dark Link (mid-boss) | 4 Voice Encounters (Ganondorf taunts, escalating) |
| Temporal Pyramid | — | 3 time visions (Sealing, Kydrog's Fall, Ganondorf on throne) |
| Kydreeok | Kydreeok (boss) | Dragon form of Kydrog; Song of Healing -> Kydrog Mask -> redemption |
| Lava Lands | Ganondorf (final) | "I am Ganondorf." Name drop. 3-phase fight. |

**Key NPCs:** Farore (the Oracle, rescued), Kydrog/Kydreeok (redeemed), Ganondorf (the true villain), Dark Link (Fortress agent)

---

## Character Arcs

### Kydrog (The Fallen Hero)

**Arc:** Antagonist -> Revealed victim -> Redeemed in death
- **Intro (EV-005):** Encounters Link on SW 0x80 Forest Glade, banishes him
- **D7:** Final confrontation as Kydrog the pirate king
- **D8/Kydreeok:** His dragon form — the Abyss unmade him
- **Redemption:** Song of Healing after Kydreeok defeat. Reveals Ganondorf's 3-phase weakness
- **Legacy:** Kydrog Mask (Stalfos Form, mask ID 8)
- **Name:** Deliberately unnamed — "lost to time." Gossip Stones don't speak it.

**Key dialogue:** "I see it now... what I became. He whispered for a hundred years... and I listened."

### Ganondorf (The True Villain)

**Arc:** Unseen presence -> Gradually named -> Final confrontation
- **Act I:** Never mentioned. Kydrog is the visible threat.
- **Act II:** "The King" referenced by Twinrova. Gossip Stones hint at "a king in darkness." Scholar NPCs reference the sealing.
- **D8 Voice:** Taunts Link through 4 escalating encounters. Never identifies himself.
- **Lava Lands:** "I am Ganondorf." First time the name appears in-game.
- **Philosophy:** "Power is wisdom. Wisdom is power. Courage is nothing."
- **Form:** Humanoid wizard-king (not Pig Ganon). Gerudo features, dark armor, cape.
- **Defeat:** "Perhaps I was wrong." Diminished, not redeemed.

**Design decision (locked):** Ganondorf's origin is deliberately ambiguous in-game. The narrative supports both ALTTP-Ganon and OoT-intruder readings.

### Farore (The Oracle)

**Arc:** Captive -> Rescued -> Guide to endgame
- **Intro (EV-005):** Follows Link briefly before Kydrog encounter
- **Captive:** Held on D7 Dragon Ship
- **Rescue (Phase 5-6 of d7_farore_rescue_spec.md):** Post-boss, GameState=$03
- **Post-rescue:** Hall of Secrets NPC (states 8+, not yet implemented)
- **Revelation:** "She was only ever bait to draw you here" (Ganondorf's words)

### Zora Princess (The Truth-Teller)

**Arc:** Imprisoned -> Reveals conspiracy -> Dies at peace
- **D4:** Song of Healing restores her enough to speak
- **Revelation:** Kydrog's pirates wore stolen River Zora armor; letters were forged
- **Legacy:** Her truth enables the East Kalyxo reconciliation

### Ranch Girl (The Witness)

**Arc:** Silent victim -> Dream reveals her curse -> Voice restored post-D5
- **Cursed:** Twinrova silenced her when she witnessed their arrival on Kalyxo
- **Dream 2 (post-D5):** Surreal ranch vision shows the curse being placed
- **Restored:** Song of Healing after defeating Twinrova
- **Key dialogue:** "I tried to warn everyone... but they took my voice before I could speak."

---

## Boss Roster (Confirmed from Data Sheet + Code Audit 2026-03-02)

| Dungeon | Boss | Type | Custom File? | Status |
|---------|------|------|-------------|--------|
| D1 Mushroom Grotto | Manhandla | Vanilla + hook | `manhandla.asm` (hook only) | Works |
| D2 Tail Palace | Moldorm | Vanilla | **None** | Works (vanilla boss, spriteset swap) |
| D3 Kalyxo Castle | Eyegore Knights | Vanilla reskin | **None** | Works (Armos with spriteset swap) |
| D4 Zora Temple | Advanced Arrghus | Vanilla + hook | `arrghus.asm` (adds fireballs) | Works |
| D5 Glacia Estate | Twinrova | Vanilla override | `twinrova.asm` (overrides Blind) | Works |
| D6 Goron Mines | King Dodongo | Vanilla + tuning | `king_dodongo.asm` (HP=40) | Works |
| D7 Dragon Ship | Kydrog | Custom | `kydrog_boss.asm` | Combat works, post-fight rescue gated OFF |
| D8 Fortress | Dark Link | Custom | `dark_link.asm` | Works (mid-boss) |
| D8 Fortress | Kydreeok | Custom | `kydreeok.asm` + `kydreeok_head.asm` | v1 works, v2 spec only |
| S3 Courage | Vaati | Custom | **None — needs new file** | Not implemented |
| Final | Ganondorf | Custom (3-phase) | **None — needs new file** | Design only. `dark_link.asm` subtype 05 has reused Ganon cutscene code (5-state), NOT the designed 3-phase fight. |

**Design philosophy:** D1-D6 use vanilla bosses with spriteset swaps and minor hooks. This is intentional — agent ASM capability is not yet reliable enough for complex boss rewrites, and vanilla bosses are battle-tested. Truly custom bosses (Kydreeok, Ganondorf, Vaati) are reserved for the climax where custom code is justified and will get human review.

---

## Dream Sequences

Dreams serve as "narrative pressure valves" — moments of surreal revelation between dungeon blocks that deepen story without requiring gameplay systems.

| # | Name | Trigger | Content | Priority |
|---|------|---------|---------|----------|
| 1 | The Sealing War | After D2 | Kydrog's origin as a fallen hero; ancient soldier sprite | Critical |
| 2 | Ranch Girl | After D5 | Twinrova cursing Ranch Girl; surreal ranch at night | Critical |
| 3 | Observatory Vision | Sky Islands | Ganondorf's imprisonment; sealing ritual; present danger | Critical |
| 4 | The Reflection | After D3 | Mirror shows Kydrog-as-knight; "same sword, different hands" | Polish |
| 5 | The Giant's Message | After D6 | Shadowed figure; "It is happening again"; prophetic | Polish |

**Infrastructure:** `attract_scenes.asm` base system, `$7EF410` dreams bitfield, `$7EF411` dream state active flag. Prototype hooks exist (BunnyTransformation override at $07:82DA, Moon Pearl check at $07:83D0). `dream_sequences.md` documents hooks and data structures but contains NO dream content in code.

**Narrative scripts:** Dream text/storyboards exist in `narrative_design_master_plan.md` only. No dream scenes are implemented in ASM.

**Implementation approach:** Full cutscene production with custom sprites, palette swaps, and transitions. No dream skip option (dreams are short, narrative important). **Note:** Cutscene ASM is complex — this is NOT safe for agent-only implementation. Requires human review and Mesen2 validation.

---

## Foreshadowing Layers

Ganondorf's name and nature should be gradually revealed before the D8 confrontation:

### Layer 1: Gossip Stones (Ambient, Early-Mid Game)
- "The stones remember a king who ruled from darkness..."
- "Three sacrifices bound the shadow. Three strikes must free it."
- Slots $1D2-$1D4 exist (all 3 are placeholder bytes). Need real text authored and encoded. Additional slots needed beyond these 3 for full coverage.

### Layer 2: Scholar/Library NPCs (Mid Game)
- Scholar in Wayward Village references "the sealing ritual" and "the priestess's sacrifice"
- Library books reference portal magic and the Abyss's origin
- Reference: `scholar_dialogue_rewrite.md`

### Layer 3: D8 Voice Encounters (Late Game)
Four rooms in the Fortress with escalating disembodied voice (Ganondorf, unnamed):
1. **Cryptic presence:** "Another one who thinks courage is a virtue."
2. **Philosophy:** "What is courage without the power to act on it?"
3. **Knowledge:** "I have watched worlds rise and fall. Timelines split and converge."
4. **Nature:** "The beast you are about to face was a hero once."

### Layer 4: Temporal Pyramid Visions (Pre-Final)
Three walk-through visions between D8 and Kydreeok:
1. The Sealing (priestess binding darkness)
2. The Fall (young man in green swallowed by Abyss — Kydrog)
3. The Present (figure on throne speaks "a name you do not recognize")

### Layer 5: Name Drop (Lava Lands)
"I am Ganondorf." First and only time the name appears in-game. Maximum impact through restraint.

---

## Parallel Arcs

Two ancient alliances mend in sequence, reinforcing the theme that Kalyxo's wounds were inflicted by outside forces:

| Arc | Dungeon | Problem | Resolution | Timing |
|-----|---------|---------|------------|--------|
| Zoras | D4 -> East Kalyxo | Schism engineered by Kydrog | Princess's truth + reconciliation | Mid-game |
| Gorons | D6 | Trade routes disrupted | Rock Meat quest + mines reopened | Mid-game |

Both relationships were damaged by outside forces (Hylian occupation, Kydrog's schemes). Link restores both by proving himself trustworthy.

---

## Progression Gating

| Gate | Trigger | Unlocks |
|------|---------|---------|
| D1 complete | Crystal bit | D2 access, mushroom quest |
| D2 complete | Crystal bit | Dream 1 trigger, D3 path |
| D4 complete | Crystal bit, Zora Mask | Song of Storms waterfall, intermediate Zora dialogue |
| D5 complete | Crystal bit | Lava Lands visible (but Master Sword needed), Dream 2 |
| D6 complete | Crystal bit, Hammer | East Kalyxo access (Korok Cove -> River Zora Village) |
| Shrines complete | 3 pendants | Master Sword forged |
| Sky Islands | Post-shrines | Dream 3 (Observatory), Cumuli NPCs |
| D7 complete | GameState=$03, Crystal bit | D8 path, Farore in Hall of Secrets |
| Kydreeok defeated | Kydrog Mask | Lava Lands access with Master Sword |
| Ganondorf defeated | — | Post-game healing Abyss |

---

## Tone Guide

**Act I:** Adventure and discovery. Light tone, NPC humor (Tingle, Mask Salesman). The corruption is present but not overwhelming.

**Act II:** Growing tension. The Zora revelation is emotional (Princess's dying words). Twinrova adds menace. Dream 2 is unsettling. The Goron arc provides a moment of warmth before the endgame.

**Act III:** Dread and catharsis. D8's disembodied voice creates unease. The Temporal Pyramid is solemn. Kydreeok is fury. Kydrog's redemption is catharsis. Ganondorf is cold, calculating, inevitable.

**Post-game:** Quiet hope. The Abyss heals. NPCs reflect on recovery.

---

## Open Items (Proposals, Not Locked)

These items were discussed in the planning session but are NOT confirmed in code or locked docs:

1. **S4 Unnamed Bonus Shrine** — Red Tunic reward listed in data sheet. No design, no rooms, no boss. Purpose unclear.
2. **Cumuli sprites** — Cloud creatures for Sky Islands. Designed but no sprite work started.
3. **Ancient Soldier sprite** — Needed for Dream 1. Custom helmet variant of Link. No sprite work started.
4. **Post-Ganondorf ending sequence** — Escape? Cutscene? Credits? No design doc exists.
5. **Korok Minigame details** — 10 Koroks in Korok Cove, hide-and-seek. Implementation TBD.
6. **D8 room count and layout** — "Skeleton" status. Needs full assessment.
7. **Temporal Pyramid room count** — 3 vision rooms + corridors designed. Could expand.
8. **Voice text rendering style** — Distinct text box for disembodied voice? Technical feasibility unknown.

---

## Cross-References

| Document | Relationship |
|----------|-------------|
| `content_story_planning_review.md` | Session plans and validation gates |
| `narrative_design_master_plan.md` | Canonical story decisions (takes precedence) |
| `endgame_narrative_arc.md` | D8 voice encounters, Temporal Pyramid, Ganondorf speech |
| `d7_farore_rescue_spec.md` | D7 post-boss pipeline |
| `dream_sequences.md` | Dream infrastructure and hooks |
| `kydrog_mask_stalfos_form.md` | Kydreeok redemption -> Kydrog Mask |
| `kydreeok_v2_spec.md` | Kydreeok boss redesign |
| `gossip_stone_additions.md` | Foreshadowing Layer 1 |
| `scholar_dialogue_rewrite.md` | Foreshadowing Layer 2 |
| `rc_content_checklist.md` | Release candidate requirements |
| `Story_Event_Graph.md` | 17 events mapped to code |
