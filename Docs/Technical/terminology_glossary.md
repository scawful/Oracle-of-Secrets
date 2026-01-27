# Oracle of Secrets: Terminology & Code Glossary

**Status:** Active Reference
**Date:** 2026-01-22
**Purpose:** Map narrative terms to code identifiers, ensure consistency across lore docs and implementation

---

## How to Use This Document

1. **When writing lore:** Use the **Narrative Term** consistently
2. **When writing code:** Use the **Code Identifier** in comments and variable names
3. **When adding NPCs:** Reference the **Sprite File** column for implementation location
4. **When adding dialogue:** Check **Message Range** for ID allocation

---

## Characters & NPCs

### Major Characters

| Narrative Term | Code Identifier | Sprite File | Message Range | Notes |
|----------------|-----------------|-------------|---------------|-------|
| **Kydrog** (Pirate Form) | `Kydrog`, `KydrogNPC` | `kydrog.asm` | 0x21, 0x200+ | D7 boss, pirate lord |
| **Kydreeok** (Dragon Form) | `Kydreeok` | `kydreeok.asm` | 0x200+ | Final boss, 3-head gleeok |
| **The Fallen Knight** | `FallenKnight` | N/A (lore only) | Gossip Stones | Kydrog's living identity |
| **Farore** (Oracle) | `Farore` | `farore.asm` | 0x0E, 0x70, 0x138, 0x220+ | Oracle of Secrets |
| **Maku Tree** | `MakuTree` | `maku_tree.asm` | 0x20, 0x22, 0x13C | Quest hub in Hall of Secrets (OW 0x0E) |
| **Ganondorf** (Sealed) | `Ganondorf` | TBD | 0x240+ | OoT wizard-king, not Pig Ganon |
| **Twinrova** | `Twinrova` | TBD | 0x122, 0x123 | Koume & Kotake, D5 boss |
| **Dark Link** | `DarkLink` | `dark_link.asm` | 0x13E, 0x16F, 0x170, 0x210+ | Knight's rejected heroism |
| **Impa** | `Impa` | `impa.asm` | 0x25-0x27, 0x1E, 0x35-0x36 | Zelda's attendant, guide |

### Zora Characters

| Narrative Term | Code Identifier | Sprite File | Message Range | Notes |
|----------------|-----------------|-------------|---------------|-------|
| **Sea Zora** (Kalyxo) | `Zora`, `SeaZora` | `zora.asm` | 0x1A4-0x1AF | Friendly NPCs |
| **Zora Princess** | `ZoraPrincess` | `zora_princess.asm` | 0xC5, 0xC6 | D4, grants Zora Mask |
| **Eon Zora** (Abyss) | `EonZora` | `eon_zora.asm` | 0x1AA-0x1AF | Friendly Abyss dwellers |
| **Eon Zora Elder** | `EonZoraElder` | `eon_zora_elder.asm` | 0x1F0+ | Sea Shrine guide |
| **River Zora** (Kalyxo) | `RiverZora` | TBD | 0x1C0+ | East Kalyxo, wrongly blamed |
| **River Zora** (Abyss) | `EonRiverZora` | Enemy variant | N/A | Corrupted, hostile |
| **River Zora Elder** | `RiverZoraElder` | TBD | 0x1D0+ | Reconciliation scene |

### Other NPCs

| Narrative Term | Code Identifier | Sprite File | Message Range | Notes |
|----------------|-----------------|-------------|---------------|-------|
| **Zora Baby** | `ZoraBaby`, `Locksmith` | `followers.asm` (0x09) | 0x107-0x10C | D4 follower, princess's attendant |
| **Korok** | `Korok` | `korok.asm` | 0x1D | 3 variants: Makar, Hollo, Rown |
| **Eon Owl** | `EonOwl` | `eon_owl.asm` | 0xE6 | Abyss guide |
| **Kaepora Gaebora** | `KaeporaGaebora` | `eon_owl.asm` | 0x146 | Song of Soaring teacher |
| **Tingle** | `Tingle` | `tingle.asm` | 0x18D-0x198 | Map merchant |
| **Mask Salesman** | `MaskSalesman` | `mask_salesman.asm` | 0xE5, 0xE9, 0x7F-0x82 | Song of Healing teacher |
| **Goron** | `Goron` | `goron.asm` | 0x1A7-0x1A9, 0x1B0-0x1B2 | Mountain dwellers |
| **Piratian** | `Piratian` | `piratian.asm` | 0x1BB | Kydrog's crew (friendly in Abyss?) |

---

## Locations

### Light World (Kalyxo)

| Narrative Term | Map ID | Code Reference | Notes |
|----------------|--------|----------------|-------|
| **Kalyxo Island** | LW 0x00-0x7F | `WORLDFLAG = 0` | Main overworld |
| **Wayward Village** | LW 0x23 | `AreaIndex = $23` | Main settlement |
| **Hall of Secrets** | OW 0x0E | Sanctuary interior | Repurposed vanilla sanctuary; Maku Tree hub |
| **Loom Beach** | LW 0x33 | `AreaIndex = $33` | Intro wake-up location |
| **Mount Snowpeak** | LW northern | TBD | Goron territory |
| **Zora Sanctuary** | LW eastern | TBD | Sea Zora settlement |
| **Korok Cove** | SW 0x182 | Exit ID `0x182` | Waterfall area behind graveyard; leads to East Kalyxo via expanded maps |
| **East Kalyxo** | LW 0x90-9B | `AreaIndex = $90-$9B` | River Zora territory (new) |
| **Sky Islands** | LW 0x84-8F | `AreaIndex = $84-$8F` | Post-D7 weather puzzles |
| **Kalyxo Castle** | LW D3 area | TBD | Hylian occupation HQ |
| **Glacia Estate** | LW D5 area | TBD | Twinrova's lair |

### Dark World (Eon Abyss)

| Narrative Term | Map ID | Code Reference | Notes |
|----------------|--------|----------------|-------|
| **Eon Abyss** | DW 0x00-0x7F | `WORLDFLAG = 1` | Shadow dimension |
| **Temporal Pyramid** | DW 0x40, 0x49 | `AreaIndex = $40, $49` | Seal's heart, intro location |
| **Forest of Dreams** | DW forest area | TBD | Corrupted woods |
| **Lava Lands** | DW northern | `AreaIndex = $??` | Ganondorf's prison |
| **Fortress of Secrets** | DW center-east | TBD | Kydreeok's lair (green temple) |
| **Meadow of Shadows** | Lore only | N/A | Where the knight fell |

### Dungeons

| Narrative Term | Dungeon ID | Essence | Notes |
|----------------|------------|---------|-------|
| **Mushroom Grotto** | D1 | Whispering Vines | Intro dungeon |
| **Tail Palace** | D2 | Celestial Veil | Flying theme |
| **Kalyxo Castle** | D3 | Crown of Shadows | Meadow Blade location |
| **Zora Temple** | D4 | Luminous Mirage | Princess revelation |
| **Glacia Estate** | D5 | Ebon Ember | Twinrova boss |
| **Goron Mines** | D6 | Seismic Whisper | Rock Meat quest |
| **Dragon Ship** | D7 | Demise's Thorn | Kydrog (pirate form) |
| **Fortress of Secrets** | D8 | N/A | Dark Link, Kydreeok |

### Shrines

| Narrative Term | Location | Pendant | Notes |
|----------------|----------|---------|-------|
| **Shrine of Wisdom** | Flooded | Pendant of Wisdom | Requires Flippers |
| **Shrine of Power** | Volcanic | Pendant of Power | Requires Power Glove |
| **Shrine of Courage** | Shadowed | Pendant of Courage | Requires Mirror Shield |
| **Shrine of Origins** | LW 0x40 | Moon Pearl access | Tutorial, Minish form |
| **Sky Shrine** (Observatory) | Sky Islands | Lore/upgrade | Post-D7, weather mechanics |
| **Sea Shrine** (First Mirror) | Eon Abyss 0x79 | Lore/upgrade | Zora history |

---

## Items & Artifacts

| Narrative Term | Item ID | Code Reference | Notes |
|----------------|---------|----------------|-------|
| **Meadow Blade** | Sword Lv2? | `$7EF359` | Fallen knight's sword, D3 |
| **Master Sword** | Sword Lv3+ | `$7EF359 >= 3` | Forged from pendants |
| **Moon Pearl** | Standard | `$7EF357` | Maintains form in Abyss |
| **Magic Mirror** | Standard | `$7EF353` | World travel |
| **Zora Mask** | Item 0x0F | `$7EF302` | Dive underwater |
| **Deku Mask** | TBD | TBD | Minish-like form |
| **Wolf Mask** | TBD | TBD | Dig ability |
| **Fire Rod** | Standard | `$7EF345` | D5 item |
| **Song of Healing** | SongFlag | `$?? SongFlag` | Releases spirits → masks |
| **Song of Storms** | TBD | TBD | Weather control |
| **Song of Soaring** | TBD | TBD | Warp ability |

---

## Story Concepts

### Eras (Timeline)

| Narrative Term | When | Key Events |
|----------------|------|------------|
| **Age of Secrets** | Ancient | Golden age, Ganondorf sealed |
| **Age of Portals** | Centuries ago | Zora crystal-mirror magic developed |
| **Age of Occupation** | Recent past | Hylian suppression of Kalyxo |
| **Present Day** | Post-linked | After Ages/Seasons events |

### Factions

| Narrative Term | Alignment | Code Notes |
|----------------|-----------|------------|
| **Native Kalyxians** | Neutral/Friendly | Gossip Stones are ancestors |
| **Sea Zoras** | Friendly | `Zora`, `SprMiscG = 0` |
| **River Zoras** (Kalyxo) | Friendly (post-reconciliation) | New NPC type needed |
| **River Zoras** (Abyss) | Hostile | Enemy sprite, corrupted |
| **Eon Zoras** | Friendly | `EonZora`, `SprMiscG = 2` |
| **Gorons** | Friendly (after D6) | Trust restored via Rock Meat |
| **Hylian Occupation** | Neutral/Antagonist | Castle guards |
| **Kydrog's Pirates** | Hostile | Stalfos crew |

### Key Narrative Concepts

| Term | Definition | Code/Lore Reference |
|------|------------|---------------------|
| **The Seal** | Ganondorf's imprisonment | Three shrines as anchors |
| **The Crack** | OoT timeline split damage | Sacred Realm → Eon Abyss connection |
| **Crystal-Mirror Magic** | Zora portal technology | Sea Shrine lore |
| **The Schism** | Sea/River Zora conflict | Kydrog's manipulation |
| **Imperial Tool** | Knight's betrayal narrative | Sent by Hyrule to fail |
| **Oracle Bloodline** | Farore's lineage | Connected to seal guardians |
| **Inverted Domain** | Fortress of Secrets | Shadow of Hall of Secrets |

---

## Code Patterns

### Sprite State Machine

```asm
; Standard NPC action states pattern
Sprite_[Name]_Main:
{
  LDA.w SprAction, X
  JSL JumpTableLocal

  dw State0_Idle
  dw State1_Talk
  dw State2_Quest
  ; etc.
}
```

### Dialogue Triggers

```asm
; Solicited (player-initiated)
%ShowSolicitedMessage($XXX)

; Unconditional (automatic)
%ShowUnconditionalMessage($XXX)

; Choice handling
LDA.b $1CE8 : BEQ .yes  ; 0 = first option selected
              BNE .no   ; non-zero = other option
```

### Conditional Dialogue Pattern

```asm
; Check flag before showing message
LDA.l $7EF3XX : AND.b #$YY : BNE .already_done
  %ShowSolicitedMessage($ZZZ)
.already_done
```

### Multi-variant NPC Pattern (see zora.asm)

```asm
; Use SprMiscG to track variant type
LDA.w SprMiscG, X
CMP.b #$01 : BNE .not_variant_1
  JSR Variant1_Handler
  RTS
.not_variant_1
; etc.
```

---

## Message Control Codes

| Code | Effect | Example |
|------|--------|---------|
| `[K]` | Page break, wait for input | End of text block |
| `[V]` | Vertical spacing | Between paragraphs |
| `[2]` | Line break | Within paragraph |
| `[3]` | Line break variant | Within paragraph |
| `[L]` | Link's name | `[L], you must...` |
| `[W:XX]` | Wait duration | `[W:30]` = pause |
| `[S:XX]` | Sound effect | `[S:1B]` = item sound |
| `[CH2I]` | Two-choice prompt | Yes/No |
| `[CH3]` | Three-choice prompt | A/B/C |
| `[C:XX]` | Color code | Text color |
| `[HY0-2]` | Hylian text | Decorative characters |

---

## SRAM Flags Reference

| Address | Name | Purpose |
|---------|------|---------|
| `$7EF300` | KydrogFaroreRemoved | Kydrog/Farore removed after intro |
| `$7EF302` | ZoraMaskObtained | Has Zora Mask |
| `$7EF3C5` | GameState | Main progression tracker |
| `$7EF3C6` | OOSPROG2 | Secondary flags |
| `$7EF3CC` | FollowerType | Current follower (0x01-0x0E) |
| `$7EF3D4` | MakuTreeQuest | Met Maku Tree |
| `$7EF3D6` | OOSPROG | Primary story flags |
| `$7EF410` | Dreams | Dream sequence completion |
| `$7EF37A` | Crystals | Dungeon completion bitfield |

---

## Comment Standard for Sprite Files

All sprite files should include a header comment block:

```asm
; =========================================================
; [Sprite Name]
;
; NARRATIVE ROLE: [Brief description of story function]
; TERMINOLOGY: [Lore term] = [Code identifier]
;
; STATES:
;   0: [State name] - [Description]
;   1: [State name] - [Description]
;   ...
;
; MESSAGES: [Range, e.g., 0x1A4-0x1AF]
; FLAGS: [SRAM flags used]
; RELATED: [Other sprites/files this interacts with]
; =========================================================
```

**Example:**
```asm
; =========================================================
; Eon Zora Elder
;
; NARRATIVE ROLE: Sea Shrine guide, reveals portal magic history
; TERMINOLOGY: "Eon Zora Elder" = EonZoraElder
;
; STATES:
;   0: Idle - Default animation
;   1: Surprised - Reaction animation
;   2: WithRod - Holding ceremonial staff
;
; MESSAGES: 0x1F0-0x1FF (planned)
; FLAGS: None currently
; RELATED: eon_zora.asm, Sea Shrine maps
; =========================================================
```

---

## Quick Reference: Narrative ↔ Code

| When writing about... | Use in lore | Use in code |
|-----------------------|-------------|-------------|
| Kydrog's living self | "The Fallen Knight" | `FallenKnight` (comments only) |
| Pirate Kydrog | "Kydrog, the Pirate King" | `Kydrog`, `KydrogNPC` |
| Dragon Kydrog | "Kydreeok" | `Kydreeok` |
| Friendly Sea Zoras | "Sea Zoras of Kalyxo" | `Zora`, `SeaZora` |
| Friendly Abyss Zoras | "Eon Zoras" | `EonZora` |
| Wrongly blamed Zoras | "River Zoras" | `RiverZora` |
| Corrupted Abyss Zoras | "corrupted River Zoras" | Enemy sprite |
| Ganondorf | "The King of Evil/Darkness" | `Ganondorf` (not in intro) |
| The conflict | "The Schism" | `ZoraSchism` (flag) |
| Kydrog's manipulation | "Kydrog's conspiracy" | N/A (lore only) |
