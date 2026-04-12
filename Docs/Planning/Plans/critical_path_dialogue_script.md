# Oracle of Secrets — Critical Path Dialogue Script

**Created:** 2026-03-02 (SP-01)
**Status:** Draft for human review
**Purpose:** All critical path dialogue in game order, revised for 32-char SNES line width, with message ID assignments.
**Line width:** 32 characters max per line (SNES dialogue box constraint)
**Format:** `[K]` = page break (player presses A), `[V]` = new text box variant

---

## ID Allocation Plan

### Existing Ranges (DO NOT REASSIGN)
- $18D-$1BB: Original expanded dialogue
- $1BC-$1C4: Sequential walker padding (keep as filler)
- $1C5-$1CA: Maku Tree hint cascade (4 real, 3 placeholder for SP-02)
- $1CC-$1D1: D3 Prison sequence (placeholder)
- $1D2-$1D4: Gossip Stone placeholder (STALE — relocating to $1FA+)
- $1D5-$1D8: Windmill Guy (real text)
- $1D9-$1DF: Gap fillers (available for critical path)
- $1E0-$1F9: Imported NPC dialogue (real text)

### New Allocations (This Script)
- $1D9-$1DF: Critical path messages (7 slots, repurposing gap fillers)
- $1FA-$21A: Critical path + gossip stone expansion (~33 slots)

### Gossip Stones (Relocated from $1C0-$1D4)
- $20B-$21F: Gossip Stone block (21 stones)
- See Section 10 for full gossip allocation.

---

## 1. Zora Princess — Enhanced Revelation (D4)

**Context:** After defeating Advanced Arrghus, Link plays Song of Healing for the dying Zora Princess. She reveals the Zora schism was manufactured.
**Replaces:** Current message $0C6 (vanilla short text)
**Assign:** Keep $0C6 (vanilla slot, enhanced text)
**NOTE:** This is a vanilla message ID — encoding must go through z3ed or direct ROM patch, not message.asm expanded bank.

```
Thank you, hero. My soul
can be free now... but
yours cannot rest yet.[K]

[V]There is a truth I must
share before I go.

The River Zoras did not
take me.[K]

[V]It was Kydrog's pirates,
wearing scales torn from
our murdered kin.

I saw them. I saw the
letters he forged to
poison my father's heart.[K]

[V]The waters of our falls
hide the last untouched
chamber. Call the storm,
and the path opens.[K]

[V]Please... end this war
of lies. Let my people
know peace before this
island falls...
```

**Lines:** 22 | **Pages:** 5 | **Tone:** Solemn, urgent, dying confession

---

## 2. Zora Baby — D4 Reaction

**Context:** Zora Baby reacts to the Princess's revelation. Remembers details that confirm the conspiracy.
**Assign:** $1D9

```
I... I remember now.

The scales... they did
not smell like the
Eastern waters.[K]

[V]They smelled like salt
and ash. Like the pirate
ships.
```

**Lines:** 8 | **Pages:** 2 | **Tone:** Dawning horror, childlike clarity

---

## 3. Twinrova — D5 Boss Dialogue (4 messages)

**Context:** Twinrova encounter in Glacia Estate. Four phases of dialogue during the boss fight.

### 3a. Trap Reveal
**Assign:** $1DA

```
Hohoho! Foolish boy!
You stumbled right into
our trap![K]

[V]Another hero clutching
that old blade. How
nostalgic. You will join
its owner soon!
```

**Lines:** 8 | **Pages:** 2 | **Tone:** Cackling menace, OoT callback

### 3b. Mid-Fight (after phase 1)
**Assign:** $1DB

```
More resilient than we
expected...[K]

[V]But the path is OPEN
now! The puppet did his
work well. Nothing you
do here matters!
```

**Lines:** 7 | **Pages:** 2 | **Tone:** Dismissive, revealing "puppet" = Kydrog

### 3c. Near-Defeat
**Assign:** $1DC

```
Impossible! We will NOT
fail again! Not when we
are so close![K]

[V]Unlike last time...
the seal truly weakens.
HE will rise!
```

**Lines:** 7 | **Pages:** 2 | **Tone:** Desperate, "last time" = vague Ages/Seasons reference

### 3d. Defeat (Ambiguous Exit)
**Assign:** $1DD

```
You think this is
victory?

We are servants of the
King. We cannot truly
be destroyed...[K]

[V]Go on, hero. Walk
through the portal.
See what awaits...
```

**Lines:** 9 | **Pages:** 2 | **Tone:** Ominous, invites player to Lava Lands portal

---

## 4. Maku Tree — Lava Lands Telepathy (Post-D5)

**Context:** After defeating Twinrova, Link exits east and discovers the Lava Lands portal. Maku Tree contacts Link telepathically.
**Assign:** $1DE

```
That rift... it leads to
the heart of the Abyss.[K]

[V]The Lava Lands, where
the ancient evil sleeps.

This is what Twinrova
sought. A direct path
to their master.[K]

[V]Without the Master
Sword, you cannot face
what waits there.

Gather your strength
first.
```

**Lines:** 13 | **Pages:** 3 | **Tone:** Grave warning, establishes Master Sword requirement

---

## 5. Sea Zora — Intermediate Dialogue (Post-D4)

**Context:** Sea Zora NPCs update after D4, reflecting the Princess's revelation. Gated by D4 crystal bit.
**Assign:** $1DF

```
The princess spoke to
you? We have heard
whispers of what she
revealed.[K]

[V]Can it be true?

The River Zoras claim
they have been waiting
for this proof. Perhaps
we should... listen.
```

**Lines:** 10 | **Pages:** 2 | **Tone:** Uncertain hope, tentative openness

---

## 6. Ranch Girl — Voice Restored (Post-D5)

**Context:** After defeating Twinrova, Song of Healing restores Ranch Girl's voice. She was cursed silent for witnessing Twinrova's arrival.
**Assign:** $1FA

```
You saw it too, did
you not? What they did
to me.[K]

[V]I tried to warn
everyone... but they
took my voice before
I could speak.[K]

[V]Thank you for freeing
me. And for ending them.
```

**Lines:** 10 | **Pages:** 3 | **Tone:** Quiet relief, trauma acknowledged simply

---

## 7. River Zora Elder — Reconciliation (Post-D6, East Kalyxo)

**Context:** Link delivers the Princess's message and Zora Mask to the River Zora Elder. Two-part dialogue.

### 7a. Before Evidence
**Assign:** $1FB

```
So... you carry the
Princess's final words.
And her mask...[K]

[V]Show me this evidence,
outsider.
```

**Lines:** 6 | **Pages:** 2 | **Tone:** Guarded, suspicious

### 7b. After Proof
**Assign:** $1FC

```
...All these years.

We mourned our dead and
cursed our kin. And it
was HIM. The Pirate
King.[K]

[V]You have given us
something more precious
than treasure.

You have given us our
names back.[K]

[V]The waters between our
peoples can flow again.
In her memory, we offer
you this gift...
```

**Lines:** 15 | **Pages:** 3 | **Tone:** Grief releasing into gratitude

---

## 8. D8 Voice Encounters (4 messages)

**Context:** Unnamed disembodied voice (Ganondorf) taunts Link through 4 rooms in the Fortress of Secrets. Escalating from cryptic to philosophical to personal.

### 8a. Voice Room 1 — Cryptic Presence
**Assign:** $1FD

```
...You carry the mark of
the forest on you.[K]

[V]How quaint.

Another one who thinks
courage is a virtue.
```

**Lines:** 7 | **Pages:** 2 | **Tone:** Cold amusement, "another one" = Kydrog came before

### 8b. Voice Room 2 — Philosophy
**Assign:** $1FE

```
Tell me, hero.

What is courage without
the power to act on it?[K]

[V]A man once came here
with courage enough to
fill an ocean.

It did not save him.
```

**Lines:** 9 | **Pages:** 2 | **Tone:** Probing, "a man" = Kydrog unnamed

### 8c. Voice Room 3 — Knowledge
**Assign:** $1FF

```
I have watched worlds
rise and fall. Timelines
split and converge.[K]

[V]You are not the first.
You will not be the last.

But you are...
interesting.
```

**Lines:** 8 | **Pages:** 2 | **Tone:** Detached, timeline anomaly hint

### 8d. Voice Room 4 — Nature (Pre-Boss)
**Assign:** $200

```
The beast you are about
to face was a hero once.[K]

[V]Courage made him.
The Abyss unmade him.

And I... I merely
watched.
```

**Lines:** 7 | **Pages:** 2 | **Tone:** Feigned innocence, "merely watched" is a lie

---

## 9. Temporal Pyramid Visions (3 messages)

**Context:** Between D8 and Kydreeok, Link walks through 3 time visions. Narrated text boxes over scripted sprite scenes.

### 9a. Vision 1 — The Sealing (Past)
**Assign:** $201

```
You see a woman in white
standing before a great
darkness.[K]

[V]Her hands glow with
golden light. The
darkness screams as
chains of light bind it.[K]

[V]The woman falls to her
knees, spent.

The seal holds.
```

**Lines:** 11 | **Pages:** 3 | **Tone:** Reverent, mythic weight

### 9b. Vision 2 — The Fall (Past)
**Assign:** $202

```
A young man in green
stands at the edge of
the Abyss.[K]

[V]His sword gleams.
His eyes burn.

He steps forward. The
darkness swallows him
whole.[K]

[V]His scream fades to
silence.

Then... laughter.
Not his.
```

**Lines:** 12 | **Pages:** 3 | **Tone:** Dread, "young man in green" = Kydrog as failed hero

### 9c. Vision 3 — The Present
**Assign:** $203

```
You see yourself
standing in a dark
throne room.[K]

[V]A figure sits upon
the throne. It speaks
a name you do not
recognize.[K]

[V]The vision shatters.
```

**Lines:** 9 | **Pages:** 3 | **Tone:** Chilling brevity, unnamed name = Ganondorf

---

## 10. Pre-Kydreeok Voice Taunt

**Context:** Final voice message before the Kydreeok boss fight.
**Assign:** $204

```
Go on, then.

Show me what your
courage is worth against
what mine created.
```

**Lines:** 5 | **Pages:** 1 | **Tone:** Challenge, "mine created" = Ganondorf made Kydreeok

---

## 11. Kydrog — Redemption Dialogue (2 messages)

**Context:** After Kydreeok is defeated, Kydrog's spirit emerges. Song of Healing sequence.

### 11a. Pre-Song (Kydrog speaks)
**Assign:** $205

```
...Link.

I remember now. The
green of the forest.
The weight of a sword
on my back.[K]

[V]I was like you, once.
Before the Abyss took
everything I was.[K]

[V]The connection between
this realm and the
Sacred Realm... I can
sever it.[K]

[V]But I need your help.
Play the Song of
Healing. Let me do this
one last thing.
```

**Lines:** 16 | **Pages:** 4 | **Tone:** Weary clarity, redemption request

### 11b. Post-Song (During severing)
**Assign:** $206

```
The thread is cut.[K]

[V]He can no longer
retreat to the Sacred
Realm when his power
fails him.[K]

[V]You will face him with
no safety net. And
neither will he.[K]

[V]Take this mask. What I
was... it may yet serve
what you must become.
```

**Lines:** 12 | **Pages:** 4 | **Tone:** Solemn resolve, passing the torch

---

## 12. Kydrog — Final Words & Boss Hint

**Context:** Kydrog fades after giving the mask. His last words hint at Ganondorf's 3-phase weakness.
**Assign:** $207

```
I see it now... what I
became. He whispered for
a hundred years... and
I listened.[K]

[V]Strike when the seal
flickers. Three times.
Only three. That is
how they bound him.[K]

[V]...I remember the
meadow. The flowers
before the shadow.

Tell them... tell them
I tried...
```

**Lines:** 14 | **Pages:** 3 | **Tone:** Fading, final breath, mechanical hint embedded in emotion

---

## 13. Lava Lands — Stone Signs (3 messages)

**Context:** Carved stone warnings on the path to Ganondorf's throne room. Terse, ominous.

### 13a. Stone 1 (Entrance)
**Assign:** $208

```
Turn back.
```

**Lines:** 1 | **Pages:** 1

### 13b. Stone 2 (Midway)
**Assign:** $209

```
There is nothing for
you here but ash.
```

**Lines:** 2 | **Pages:** 1

### 13c. Stone 3 (Before Throne)
**Assign:** $20A

```
You were warned.
```

**Lines:** 1 | **Pages:** 1

---

## 14. Ganondorf — Pre-Battle Speech (Throne Room)

**Context:** The name drop. Ganondorf reveals himself for the first time. This is THE speech. Must land perfectly.
**Assign:** $20B (multi-page, single message ID with [K] breaks)

**EDITORIAL NOTE:** This speech is long (~30 lines). At SNES encoding this may need 2 message IDs if the byte count exceeds single-message limits. Splitting at the philosophy section is the natural break point.

### Part 1: Introduction
**Assign:** $20B

```
So. You are the one who
broke my dragon.[K]

[V]...No. Not broke.
Freed. How sentimental.[K]

[V]I am Ganondorf.[K]

[V]You do not know that
name. But it knows you.
It has known every hero
who carried that mark
on their hand.
```

**Lines:** 11 | **Pages:** 4 | **Tone:** Cold, measured, the name lands like a hammer

### Part 2: Philosophy & Stakes
**Assign:** $20C

```
You think courage makes
you special. It does
not.[K]

[V]Courage is the refuge
of those too simple to
acquire power.[K]

[V]Power is wisdom.
Wisdom is power.
Courage is nothing.[K]

[V]The priestess who
sealed this realm thought
her courage would hold.
It did not. Her bloodline
carries the same flaw.
```

**Lines:** 14 | **Pages:** 4 | **Tone:** Contemptuous philosophy, Farore/priestess link

### Part 3: The Trap
**Assign:** $20D

```
Your Oracle. Farore.

She was only ever bait
to draw you here.[K]

[V]Because I do not need
her. I do not need you.

I need the Triforce
shard you carry in
your hand.[K]

[V]And you have delivered
it to me.
```

**Lines:** 11 | **Pages:** 3 | **Tone:** Trap sprung, maximum menace

---

## 15. Ganondorf — Battle Dialogue (3 messages)

**Context:** Phase transition dialogue during the 3-phase fight. Brief — player is in combat.

### 15a. After Phase 1 Hit
**Assign:** $20E

```
That sword... it burns
with their sacrifice.[K]

[V]No matter. The seal
weakens still. I have
waited centuries. I can
wait longer.
```

**Lines:** 7 | **Pages:** 2

### 15b. After Phase 2 Hit
**Assign:** $20F

```
ENOUGH!

I will not be denied
again! The portal opens
at my command![K]

[V]The worlds merge at
my will!
```

**Lines:** 7 | **Pages:** 2 | **Tone:** Rage, losing control

### 15c. Phase 3 Defeat
**Assign:** $210

```
This cannot... I am
eternal...[K]

[V]The seal... the seal
holds...

NO--!
```

**Lines:** 5 | **Pages:** 2 | **Tone:** Desperate, broken

---

## 16. Ganondorf — Post-Defeat

**Context:** After the final blow. The thematic resolution.
**Assign:** $211

```
...Impossible.

I have crossed timelines.
I have unmade heroes.[K]

[V]I have bent the Sacred
Realm to my will.

And yet... this. Again.[K]

[V]...Courage.

Perhaps I was wrong.
```

**Lines:** 10 | **Pages:** 3 | **Tone:** Quiet admission, NOT redemption — diminishment

---

## 17. D7 Kydrog — Defeat Message (Pre-Rescue)

**Context:** Temporary message shown when Kydrog is defeated in D7. Currently using $0138 as placeholder.
**Assign:** $1BC (repurpose from padding — this is the D7 defeat slot per `d7_farore_rescue_spec.md`)

```
The pirate king falls
silent. The ship groans
beneath you.[K]

[V]From deeper in the
hold, a voice calls
out...

Farore.
```

**Lines:** 8 | **Pages:** 2 | **Tone:** Transition beat, bridges to Farore rescue

---

## 18. Farore — Rescue Speech (D7 Crystal Maiden Slot)

**Context:** Farore speaks after being freed from captivity. Crystal maiden flow.
**Assign:** $0138 (existing vanilla maiden slot — needs real text to replace generic)

```
Hero... you came.

I knew you would. The
Maku Tree whispered of
your courage through
the roots of the world.[K]

[V]Kydrog kept me here
to weaken the seal.
My blood... the blood
of the priestess...[K]

[V]It holds the seal
together. Without me,
it would have shattered.[K]

[V]Take this crystal.
The island remembers
its guardians now. Go
to the Hall of Secrets.
I will meet you there.
```

**Lines:** 18 | **Pages:** 4 | **Tone:** Relief, exposition, sets up endgame

---

## 19. Farore — Hall of Secrets (Post-Rescue)

**Context:** First visit to Hall of Secrets after GameState=$03. Farore's post-rescue exposition.
**Assign:** $1BD (per d7_farore_rescue_spec.md allocation)

```
You have freed me, but
the seal weakens still.[K]

[V]The one who whispered
to Kydrog for a hundred
years... he waits in the
Lava Lands.[K]

[V]Seek the ancient
Shrines. The pendants
will forge the blade
that can end this.[K]

[V]The Master Sword is
your only hope against
what waits below.
```

**Lines:** 13 | **Pages:** 4 | **Tone:** Urgent guidance, shrine quest launcher

---

## 20. Eon Zora Elder — Post-Game

**Context:** After defeating Ganondorf, the Eon Abyss begins to heal. Optional NPC dialogue.
**Assign:** $1BE (last slot in d7_farore_rescue_spec.md proposed range)

```
The darkness lifts,
slowly.

We feel it too... the
weight easing.[K]

[V]Perhaps in time, our
world will remember
what light looks like.[K]

[V]Thank you, hero of
Kalyxo.
```

**Lines:** 10 | **Pages:** 3 | **Tone:** Quiet hope, closure

---

## Summary Table

| ID | Section | Character | Context | Pages |
|----|---------|-----------|---------|-------|
| $0C6 | 1 | Zora Princess | D4 revelation (vanilla slot) | 5 |
| $0138 | 18 | Farore | D7 rescue (vanilla maiden slot) | 4 |
| $1BC | 17 | Narrator | D7 Kydrog defeat transition | 2 |
| $1BD | 19 | Farore | Hall of Secrets post-rescue | 4 |
| $1BE | 20 | Eon Zora Elder | Post-game healing | 3 |
| $1D9 | 2 | Zora Baby | D4 reaction | 2 |
| $1DA | 3a | Twinrova | D5 trap reveal | 2 |
| $1DB | 3b | Twinrova | D5 mid-fight | 2 |
| $1DC | 3c | Twinrova | D5 near-defeat | 2 |
| $1DD | 3d | Twinrova | D5 defeat exit | 2 |
| $1DE | 4 | Maku Tree | Lava Lands telepathy | 3 |
| $1DF | 5 | Sea Zora | Post-D4 intermediate | 2 |
| $1FA | 6 | Ranch Girl | Voice restored post-D5 | 3 |
| $1FB | 7a | River Zora Elder | Before evidence | 2 |
| $1FC | 7b | River Zora Elder | After proof | 3 |
| $1FD | 8a | Voice (Ganondorf) | D8 Room 1 — cryptic | 2 |
| $1FE | 8b | Voice (Ganondorf) | D8 Room 2 — philosophy | 2 |
| $1FF | 8c | Voice (Ganondorf) | D8 Room 3 — knowledge | 2 |
| $200 | 8d | Voice (Ganondorf) | D8 Room 4 — nature | 2 |
| $201 | 9a | Narrator | Vision 1 — sealing | 3 |
| $202 | 9b | Narrator | Vision 2 — the fall | 3 |
| $203 | 9c | Narrator | Vision 3 — present | 3 |
| $204 | 10 | Voice (Ganondorf) | Pre-Kydreeok taunt | 1 |
| $205 | 11a | Kydrog | Pre-Song redemption | 4 |
| $206 | 11b | Kydrog | Post-Song severing | 4 |
| $207 | 12 | Kydrog | Final words + hint | 3 |
| $208 | 13a | Stone sign | Lava Lands entrance | 1 |
| $209 | 13b | Stone sign | Lava Lands midway | 1 |
| $20A | 13c | Stone sign | Lava Lands pre-throne | 1 |
| $20B | 14a | Ganondorf | Speech part 1 — intro | 4 |
| $20C | 14b | Ganondorf | Speech part 2 — philosophy | 4 |
| $20D | 14c | Ganondorf | Speech part 3 — trap | 3 |
| $20E | 15a | Ganondorf | After Phase 1 | 2 |
| $20F | 15b | Ganondorf | After Phase 2 | 2 |
| $210 | 15c | Ganondorf | Phase 3 defeat | 2 |
| $211 | 16 | Ganondorf | Post-defeat reflection | 3 |

**Total: 36 messages (2 vanilla slots + 34 new expanded)**

---

## Gossip Stones — Relocated ID Block

**Range:** $212-$226 (21 stones)
**Status:** Text drafted in `gossip_stones.md` and `gossip_stone_additions.md`. Needs consolidation and human review before encoding.
**Action:** Update `gossip_stones.md` registry to use $212-$226 instead of $1C0-$1D4. Resolve conflicting text between gossip_stones.md and gossip_stone_additions.md.

This is SP-05/SP-11 scope — not included in this script.

---

## Not Included (Deferred to Other SPs)

| Content | SP | Reason |
|---------|-----|--------|
| Maku Tree hints ($1C8, $1C9, $1CB) | SP-02 | Separate encoding session |
| Dream narration text (Dreams 1-5) | SP-03/04 | Depends on cutscene design decisions |
| Gossip Stone full text (21 stones) | SP-05/11 | Polish layer, not critical path |
| D3 Prison dialogue ($1CC-$1D1) | SP-10 | Supporting NPC scope |
| Zora Baby journey dialogue (D4) | SP-10 | Supporting NPC scope |
| Impa dialogue | SP-10 | Supporting NPC scope |

---

## Editorial Notes

1. **Ganondorf speech split:** The throne room speech is split into 3 message IDs ($20B-$20D). This avoids single-message byte overflow and provides natural dramatic pacing. Part 1 ends on "I am Ganondorf" — the name hangs in the air before Part 2 begins the philosophy.

2. **Kydrog redemption pacing:** The pre-Song and post-Song are separate messages because the Song of Healing plays between them. The final words ($207) are a third message that plays as Kydrog fades — this is where the mechanical hint ("Three times") lives, embedded in emotional context so it doesn't feel like a tutorial.

3. **Voice encounters:** All 4 use the same unnamed speaker. Implementation should use a distinct text box style (no portrait, possibly different border color) to distinguish from normal NPC dialogue. Technical feasibility TBD.

4. **Vanilla slot overrides ($0C6, $0138):** These require z3ed or direct ROM patching, not message.asm expansion. They should be handled in a separate encoding session with care not to break vanilla message table indexing.

5. **"He" vs naming Ganondorf:** Before $20B, Ganondorf is NEVER named. Twinrova says "the King" and "HE." The Voice never identifies itself. Stone signs are anonymous. The name drop at "I am Ganondorf" in $20B should be the first and only time the name appears. All prior dialogue has been reviewed to enforce this.

---

## Validation Checklist (Gate 1)

- [ ] Human review: tone, pacing, character voice consistency
- [ ] Verify all lines are 32 chars or fewer
- [ ] Confirm no Ganondorf name appears before $20B
- [ ] Cross-check with `narrative_design_master_plan.md` for lore consistency
- [ ] Confirm message ID ranges don't conflict with existing encoded messages
- [ ] Review Kydrog hint ($207) — is "three times" clear enough as a game mechanic hint?
