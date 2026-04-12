# Oracle of Secrets — Dialogue & Messages Subsystem

**Generated:** 2026-03-21
**Scope:** Message format, dialogue engine, control codes, NPC dialogue states, and content status.

---

## Message System Architecture

```mermaid
graph TB
    subgraph "Message Engine (Bank $2F)"
        MSG["Core/message.asm (76KB)<br/>Dialogue engine + all message data"]
        ORG["Core/messages.org<br/>Source dialogue (human-editable)"]
    end

    subgraph "Display Pipeline"
        TRIGGER["Trigger<br/>(NPC interaction / event)"]
        MACRO1["%ShowUnconditionalMessage($ID)<br/>Force display"]
        MACRO2["%ShowSolicitedMessage($ID)<br/>On interaction only"]
        RENDER["Text renderer<br/>(tile-by-tile)"]
        TEXTBOX["Text box<br/>(2-3 lines visible)"]
    end

    subgraph "Control Codes"
        POS["[2] [3] — Line positioning"]
        WAIT["[K] — Button wait"]
        CONT["[V] — Continue same line"]
        SPEED["[S:XX] — Text speed"]
        DELAY["[W:XX] — Wait time"]
        NAME["[L] — Player name"]
        CHOICE["[CH2I] [CH3] — Choice prompts"]
    end

    ORG -->|compile| MSG
    TRIGGER --> MACRO1 & MACRO2
    MACRO1 --> RENDER
    MACRO2 --> RENDER
    RENDER --> TEXTBOX
    TEXTBOX --> POS & WAIT & CONT & SPEED & DELAY & NAME & CHOICE
```

---

## Message Format

Messages are defined in `messages.org` with this format:

```
** <ID> - <Description>
[W:02][S:03]<Text content>
[2]<Line 2 text>
[3]<Line 3 text>
[V]<Continuation text>
[K]<Wait for button>
```

### Control Code Reference

| Code | Meaning | Example |
|------|---------|---------|
| `[2]` | Position to line 2 | `[2]Second line here` |
| `[3]` | Position to line 3 | `[3]Third line here` |
| `[K]` | Wait for button press | End of text block |
| `[V]` | Continue (same box, next page) | Multi-page dialogue |
| `[W:XX]` | Wait XX frames | `[W:02]` = brief pause |
| `[S:XX]` | Set text speed | `[S:03]` = normal speed |
| `[L]` | Insert player name | `Hello, [L]!` |
| `[CH2I]` | 2-choice prompt | Yes/No questions |
| `[CH3]` | 3-choice prompt | Multiple options |

---

## Dialogue State Machine (NPC)

```mermaid
stateDiagram-v2
    [*] --> Idle: NPC spawned
    Idle --> Facing: Player approaches
    Facing --> Talking: A button pressed
    Talking --> MessageDisplay: %ShowSolicitedMessage
    MessageDisplay --> WaitButton: [K] reached
    WaitButton --> NextPage: [V] continues
    WaitButton --> Choice: [CH2I]/[CH3]
    NextPage --> MessageDisplay
    Choice --> BranchA: Option 1
    Choice --> BranchB: Option 2
    BranchA --> Idle
    BranchB --> Idle
    WaitButton --> Idle: End of message
```

---

## Key NPC Dialogue Groups

```mermaid
graph TB
    subgraph "Quest-Critical NPCs"
        MAKU["Maku Tree<br/>Hint cascade by crystal count<br/>Messages: multiple IDs"]
        FARORE["Farore<br/>Pre-capture, post-rescue states<br/>GameState-dependent"]
        PRINCESS["Zora Princess<br/>D4 revelation (Song of Healing)<br/>Message 0C6+"]
        KYDROG["Kydrog<br/>Encounter, boss, redemption"]
        GANON["Ganondorf<br/>D8 voice, final boss, defeat"]
    end

    subgraph "Supporting NPCs"
        ELDER["Village Elder<br/>ElderGuideStage + MapIcon"]
        ZORA_NPC["Zora NPCs<br/>Pre/post-D4 states"]
        RANCH["Ranch Girl<br/>Cursed silent -> restored"]
        SCHOLAR["Scholar<br/>Lore exposition"]
        TINGLE["Tingle<br/>Hints, comic relief"]
    end

    subgraph "Ambient"
        GOSSIP["Gossip Stones (21+)<br/>Foreshadowing layers"]
        VILLAGERS["Villagers<br/>State-dependent dialogue"]
        KOROKS["Koroks (3 variants)<br/>Hide-and-seek minigame"]
    end
```

---

## Foreshadowing Layers

| Layer | Source | Content | Status |
|-------|--------|---------|--------|
| 1 | Gossip Stones | "A king who ruled from darkness...", seal hints | Slots $1D2-$1D4 exist (placeholder bytes). 21 stones written, need message IDs |
| 2 | Scholar/Library | Sealing ritual, priestess sacrifice, portal magic | `scholar_dialogue_rewrite.md` exists |
| 3 | D8 Voice | 4 escalating encounters (philosophy → revelation) | Design only, not implemented |
| 4 | Temporal Pyramid | 3 walk-through visions | Design only |
| 5 | Name Drop | "I am Ganondorf." (Lava Lands) | Design only |

---

## Dialogue Content Status

| Category | Written | In messages.org | In ROM | Tested |
|----------|---------|----------------|--------|--------|
| Core NPC dialogue | Yes | Partial | Partial | Partial |
| Maku Tree hint cascade | Yes | Yes | Yes | Needs verify |
| Zora Princess revelation | Yes | Yes | Partial | No |
| Twinrova boss dialogue | Yes (draft) | No | No | No |
| Kydrog redemption | Yes (draft) | No | No | No |
| Ganondorf dialogue | Yes (draft) | No | No | No |
| D8 Voice encounters | Yes (draft) | No | No | No |
| Gossip Stones (21) | Yes | No | Placeholder | No |
| Ranch Girl restoration | Yes (draft) | No | No | No |
| East Kalyxo reconciliation | Yes (draft) | No | No | No |
| Post-game healing dialogue | Yes (draft) | No | No | No |

---

## Message System Expansion

Bank $2F ($2F8000-$2FFFFF) is the expanded message bank with 32KB capacity. Current usage is significant (76KB message.asm including engine code), but there is room for the planned dialogue additions.

**Key concern:** Message IDs must be unique and sequential. Adding new messages in the middle of the ID space requires updating all subsequent references. The `normalize_dialogue_bundles.py` script helps manage this.
