# Caves & Grottos

Oracle of Secrets contains 25+ caves organized by region. Most are passage caves connecting overworld areas, while some contain treasures, upgrades, or special encounters.

---

## Cave Types

| Type | Description | Examples |
|------|-------------|----------|
| **Passage** | Connects two overworld areas | Snow Mountain Cave, Beach Cave |
| **Treasure** | Contains chests or collectibles | Rock Heart Piece Cave |
| **Fairy** | Great Fairy or healing fountain | Deluxe Fairy Fountain |
| **Upgrade** | Grants permanent upgrades | 1/2 Magic Cave |
| **Special** | Unique purpose or mechanic | Master Sword Cave, Cave of Secrets |
| **Secret** | Hidden entrances | Hidden Grave |

---

## Caves by Region

### Snowpeak Region (7 caves)

| ID | Name | OW Screens | Type | Notes |
|----|------|------------|------|-------|
| 0x1E | Snow Mountain Cave Start | 0x0D | Passage | Main cave system entry |
| 0x1F | Snow Mountain Cave Portal | 0x05 | Passage | Portal room |
| 0x20 | Snow Mountain Cave End | 0x0D | Passage | Cave exit |
| 0x16 | Snow Mountain Cave East Peak | 0x07 | Passage | To 0x05 |
| 0x17 | Snow Mountain Cave to East Peak | 0x05 | Passage | To 0x07 |
| 0x30 | Snow Mountain East to West Peak | 0x07 | Passage | Peak connector |
| 0x31 | Snow Mountain West to East Peak | 0x04 | Passage | Peak connector |

**Navigation:**
```
      West Peak (0x04)          East Peak (0x07)
           |                         |
         0x31 ←───────────────────→ 0x30
           |                         |
         0x1F ←─────────────────── 0x16/0x17
           |
         0x1E/0x20 (Start/End)
```

---

### Beach/Coast Region (3 caves)

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x1A | Beach Cave Route | 0x32 | Passage | Beach connector |
| 0x1B | Beach Cave End | ?? | Passage | Exit point |
| 0x1C | Beach Cave Intro | 0x33 | Passage | Entry point |

---

### Kalyxo Field Region (3 caves)

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x21 | Kalyxo Field Cave Start | 0x25 | Passage | Field cave entry |
| 0x22 | Kalyxo Field Cave River | 0x25 | Passage | River section |
| 0x23 | Kalyxo Field Cave End | 0x25 | Passage | Exit point |

---

### Forest/Toadstool Region (3 caves)

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x2C | Toadstool Woods Log Cave | 0x18 | Passage | Log entrance |
| 0x2E | Tail Palace Cave Route Start | 0x2D | Passage | To Tail Palace |
| 0x2F | Tail Palace Cave Route End | 0x2E | Passage | Palace connector |

---

### Mountain Region (3 caves)

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x06 | Mountain to Witch Shop Start | 0x15 | Passage | Shortcut to Witch Shop |
| 0x07 | Mountain to Witch Shop End | 0x0D | Passage | Exit near shop |
| 0x51 | Rock Heart Piece Cave | 0x15 | Treasure | **Heart Piece** |

---

### Graveyard Region (2 caves)

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x5B | Hidden Grave | 0x0F | Secret | Hidden entrance |
| 0x5C | Graveyard Waterfall | 0x0F | Special | Waterfall cave |

---

### Lava Land Region (2 caves)

| ID | Name | OW Screen | Type | Notes |
|----|------|-----------|------|-------|
| 0x4F | Lava Cave Start | 0x43 | Passage | Lava region entry |
| 0x52 | Lava Cave End | 0x43 | Passage | Lava region exit |

---

## Special Caves

### Fairy Fountains

| ID | Name | OW Screen | Contents |
|----|------|-----------|----------|
| 0x13 | Deluxe Fairy Fountain Pond | 0x15 | Great Fairy |
| 0x14 | Deluxe Fairy Fountain Start | 0x15 | Fountain entrance |
| 0x3A | Deluxe Fairy Fountain East | 0x1D | East entrance |
| 0x3B | Deluxe Fairy Fountain South | 0x1D | South entrance |
| 0x38 | Healing Fairy Cave | 0x11 | Healing Fairy (exit only) |

### Upgrade Caves

| ID | Name | OW Screen | Reward |
|----|------|-----------|--------|
| 0x11 | 1/2 Magic Cave | 0x0B | Magic meter upgrade |

### Story Caves

| ID | Name | OW Screen | Contents |
|----|------|-----------|----------|
| 0x18 | Master Sword Cave | 0x40 | Master Sword |
| 0x19 | Master Sword Cave (alt) | 0x40 | Alternate entrance |
| 0x2D | Master Sword Cave (alt) | 0x40 | Third entrance |
| 0x50 | Cave of Secrets | 0x0E | Near Hall of Secrets |

---

## Cave Summary Statistics

| Region | Count | Primary Type |
|--------|-------|--------------|
| Snowpeak | 7 | Passage |
| Beach | 3 | Passage |
| Kalyxo Field | 3 | Passage |
| Forest | 3 | Passage |
| Mountain | 3 | Mixed |
| Graveyard | 2 | Special |
| Lava Land | 2 | Passage |
| Fairy | 5 | Special |
| Upgrade/Story | 5 | Special |
| **Total** | **33** | |

---

## See Also

- [LocationRegistry.md](../LocationRegistry.md) - Master location index
- [CAVE_TEMPLATE.md](CAVE_TEMPLATE.md) - Documentation template
- [SpecialAreas/](../SpecialAreas/) - Related special locations
