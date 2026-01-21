# Oracle of Secrets: Narrative & Gameplay Improvement Proposal

**Date:** November 22, 2025
**Status:** Proposed

This document outlines a plan to enhance the story, pacing, lore, and progression of *Oracle of Secrets*. It builds upon the existing `QuestFlow.md` and project tracker (`oracle.org`).

## 1. Pacing & Progression Enhancements

The current progression is linear (Dungeon $\to$ Item $\to$ Dungeon). To improve pacing and mitigate "dungeon fatigue," we propose introducing Narrative Interludes and Exploration Gates.

### 1.1. Narrative Interludes: "Dream Sequences"
**Goal:** Bridge major story arcs and provide exposition without exposition dumps.
**Implementation:** Force a "camping" or "rest" scene after specific dungeons where Link sleeps and experiences a playable dream.

*   **Dream 1: The Sealing War (Post-D2 / Tail Palace)**
    *   **Concept:** A flashback to the "War of the Magi."
    *   **Gameplay:** Link controls an ancient soldier (sprite swap) in a short, scripted battle sequence.
    *   **Lore Reveal:** Witness the origin of Kydrog and his initial sealing, establishing his threat level early on.
    *   **Status:** Todo in `oracle.org`.

*   **Dream 2: The Ranch Girl's Secret (Post-D5 / Glacia Estate)**
    *   **Concept:** A surreal dream involving the Ranch Girl and Twinrova.
    *   **Lore Reveal:** Foreshadows the twist regarding the Ranch Girl's lineage or connection to the witches/Gerudo.

### 1.2. Gossip Stone Network
**Goal:** Guide players through the mid-game lull (Chapter 4: Path to the Castle) and deepen lore.
**Implementation:**
*   **Mechanic:** Stones only speak if the player is wearing the **Mask of Truth** (or repurposed Bunny Hood).
*   **Lore Hook:** The stones are petrified observers from the "Age of Secrets" who whisper forgotten history about the Oracle bloodline and the corruption of the Shrines.
*   **Function:** Provide hints for side-quests (like the Goron Mines requirements) and locations of heart pieces.

## 2. Lore & Dialogue Deepening

### 2.1. Reactive NPC Dialogue
**Goal:** Make the world feel alive and responsive to the player's actions.
**Current State:** NPCs are largely static.
**Proposal:** Update 3-5 key NPCs to check `OOSPROG` flags.
*   **Key NPCs:** Mayor, Potion Shop Witch, Library NPC.
*   **Triggers:** Completion of D3 (Kalyxo Castle) and D6 (Goron Mines).
*   **Example:** After D3, the Mayor comments on the "strange lights vanishing from the castle" rather than his standard welcome text.

### 2.2. The Library of Secrets
**Goal:** Utilize the "Book of Secrets" quest location for world-building.
**Proposal:** Add readable bookshelves in the Wayward Village Library.
*   **Content:** Texts explaining the "Three Shrines" (Power, Wisdom, Courage) and their corruption.
*   **Purpose:** Foreshadows the S1-S3 mini-dungeons and provides context for why Link must visit them.

## 3. Item Utility & Economy

### 3.1. Seashell Mansion & The Cartographer
**Goal:** Give utility to the "Seashells" collectible.
**Proposal:**
*   **NPC:** A "Cartographer" (Tingle-esque) in Zora Village or a distinct coastal house.
*   **Mechanic:** Trade **5 Seashells** to unlock "Secret Locations" on the world map.
*   **Reward:** These map markers reveal hidden grottos or optional Heart Pieces, rewarding exploration.

### 3.2. Honeycomb & Bees
**Goal:** Create synergy between the "Honeycomb" collectible and the "Magic Bean" quest.
**Proposal:**
*   **Interaction:** Using a Honeycomb on the Magic Bean sprout attracts a "Queen Bee."
*   **Effect:** The Queen Bee instantly pollinates and grows the plant, bypassing the 3-day wait timer.
*   **Reward:** Rewards clever players with instant access to the Heart Container/path.

## 4. Boss & Cutscene Polish

### 4.1. Kydrog (The Antagonist)
**Goal:** Establish Kydrog as a character, not just a boss monster.
**Proposal:**
*   **Pre-Fight Monologue:** Kydrog should recognize the "Scent of Farore" on Link, connecting the encounter back to the game's intro cutscene.
*   **Cinematic:** A custom transformation sequence using HDMA wave effects to show his shift from Humanoid/Wizard form to the Kydreeok Dragon form.

### 4.2. Kydreeok (The Final Form)
**Goal:** enhance the mechanical depth of the final fight (per `oracle.org` todos).
**Proposal:**
*   **Neck Stretch Attack:** Implement a "Chain Chomp" style physical lunge to complement the magical fireball spam.
*   **Sprite Logic:** Ensure heads detach and float before reattaching (Stage 2) rather than just popping into existence.

## 5. Technical "Quick Wins"

### 5.1. Journal System
**Priority:** High
**Reasoning:** The game features complex trading sequences (Mushroom $\to$ Powder $\to$ Ocarina). A quest log is essential for modern UX.
**Action:** Prioritize `Menu/menu_journal.asm` implementation.

### 5.2. Dynamic Map Markers
**Priority:** Medium
**Reasoning:** Reduce aimless wandering.
**Action:** Use the `MapIcon` flag system to mark the *region* of the next main objective (e.g., "Something is happening at the Mountain...") without revealing the exact tile.
