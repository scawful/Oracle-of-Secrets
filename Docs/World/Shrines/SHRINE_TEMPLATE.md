# [Shrine Name]

**Type:** Shrine
**Entrance ID(s):** [0x##, ...]
**Overworld Location:** OW [0x##] - [area name]
**Pendant/Essence:** [Pendant of Power/Courage/Wisdom] or [Essence name]
**Boss:** [Boss name if applicable, otherwise "None"]

---

## Overview

[Brief description of the shrine's purpose and theming]

---

## Room Layout

```
┌─────────────┐
│    0x##     │
│  [Room 1]   │
│   # obj     │
└──────┬──────┘
       │
       ↓ [connection type]
┌─────────────┐
│    0x##     │
│  [Room 2]   │
│   # obj     │
└─────────────┘
```

---

## Room Details

| Room | Name | Objects | Connection | Notes |
|------|------|---------|------------|-------|
| 0x## | Entrance | # | stair/door to 0x## | [description] |
| 0x## | Boss Chamber | # | - | Boss: [name] |

---

## Puzzle/Challenge

[Description of the puzzle or challenge mechanics]

---

## Reward

- **Primary:** [Pendant/Essence name]
- **Items:** [Any chests or collectibles]

---

## Connections

| From | To | Type | Notes |
|------|----|------|-------|
| OW 0x## | 0x## | entrance | [description] |
| 0x## | OW 0x## | exit | [description] |

---

## Generation Notes

**Generated with:** `location_mapper.py --shrine [name]`
**ROM:** [ROM filename]
**Date:** [YYYY-MM-DD]
