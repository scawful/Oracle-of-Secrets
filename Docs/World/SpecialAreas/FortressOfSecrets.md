# Fortress of Secrets

**Type:** Special Area / Final Dungeon
**Entrance ID:** 0x37
**OW Screen:** 0x5E
**Purpose:** Final dungeon and climactic confrontation

---

## Overview

The Fortress of Secrets is the final dungeon in Oracle of Secrets. It serves as the culmination of the player's journey and contains the final boss encounter.

---

## Access Requirements

To enter the Fortress of Secrets, the player must:

1. Collect all three Pendants (Power, Courage, Wisdom)
2. Obtain the Master Sword
3. Complete all seven dungeons
4. Acquire [specific key items TBD]

---

## Dungeon Structure

```
┌─────────────────────┐
│    FINAL BOSS       │
│       ROOM          │
└─────────┬───────────┘
          │
┌─────────┴───────────┐
│    PRE-BOSS AREA    │
│   (Boss Key Door)   │
└─────────┬───────────┘
          │
    [Multiple floors
     to be mapped]
          │
┌─────────┴───────────┐
│      ENTRANCE       │
│     (OW 0x5E)       │
└─────────────────────┘
```

---

## Room Discovery

*Room layout pending discovery. Use:*

```bash
python3 location_mapper.py --discover 0x37
```

---

## Key Items

### Required to Enter
- All three Pendants
- Master Sword
- [TBD items]

### Found Inside
- Boss Key
- Dungeon Map
- Compass
- [TBD items]

---

## Final Boss

**Boss Name:** TBD
**Boss Room:** TBD

The final boss encounter takes place at the top of the fortress.

---

## Thematic Connection

The Fortress of Secrets mirrors the Hall of Secrets:
- Hall = Sanctuary of Light (Farore)
- Fortress = Stronghold of Darkness (Antagonist)

---

## Technical Notes

- May use extended room IDs (Oracle's expanded dungeon format)
- Custom boss arena tileset
- Special music tracks

---

## See Also

- [SpecialAreas/index.md](index.md) - Special area overview
- [HallOfSecrets.md](HallOfSecrets.md) - Narrative counterpart
- [../Dungeons/](../Dungeons/) - Other dungeons
