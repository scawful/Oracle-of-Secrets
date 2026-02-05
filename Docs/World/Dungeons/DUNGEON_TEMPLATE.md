# [Dungeon Name] - Dungeon Map

**Dungeon ID:** [0x##]
**Boss:** [Boss Name] ([Sprite ID or notes])
**Dungeon Item:** [Item(s) obtained]
**Big Chest:** Room [0x##] ([location description])
**Miniboss:** [Name] in Room [0x##]

---

## Floor Layout

### Floor [N] (Main Level) - [Grid size]

```
                    NORTH
                      ↑
┌─────────┐   ┌─────────┐   ┌─────────┐
│   0x##  │───│   0x##  │───│   0x##  │
│  [name] │   │  [name] │   │  [name] │
│ ### obj │   │ ### obj │   │ ### obj │
│  # door │   │  # door │   │  # door │
└────┬────┘   └────┬────┘   └────┬────┘
     │             │             │
     │[conn type]  │[conn type]  │[conn type]
     │             │             │
```

**Floor N Connections:**

| From | To | Type | Notes |
|------|----|------|-------|
| 0x## | 0x## | stair/hole | Description |

---

### Basement [N]

```
[ASCII layout]
```

**Basement N Connections:**

| From | To | Type |
|------|----|------|
| 0x## | 0x## | stair up |

---

## Progression Path

```
ENTRANCE (0x##)
     │
     ├──→ [First milestone/area]
     │        │
     │        └──→ [Sub-area or key item]
     │
     ├──→ [Second milestone/area]
     │
     └──→ [Boss area]
              │
              └──→ BOSS DEFEATED → Exit
```

---

## Room Statistics

| Room | Obj | Door | Tracks | Role |
|------|-----|------|--------|------|
| 0x## | ### | # | ### | ENTRANCE |
| 0x## | ### | # | ### | MINIBOSS |
| 0x## | ### | # | ### | BIG CHEST |
| 0x## | ### | # | ### | **BOSS** |

**Notes:**
- Track-heavy rooms: [list rooms with significant tracks]
- Key doors: [list rooms with key requirements]

---

## Special Features

### [Feature Name] (if applicable)

- Description of unique mechanics in this dungeon
- Puzzle types used
- Custom collision requirements

---

## See Also

- [[Dungeon]_Tracks.md]([Dungeon]_Tracks.md) - Detailed track layouts (if applicable)
- [Related documentation links]

---

## Generation Notes

**Generated with:** `z3ed dungeon-*` commands
**ROM:** [ROM filename]
**Date:** [YYYY-MM-DD]

### z3ed Commands Used

```bash
# List all objects in a room
z3ed dungeon-list-objects --rom=<path> --room=0x##

# Get room graph/connections
z3ed dungeon-graph --rom=<path> --room=0x##

# Get dungeon group info
z3ed dungeon-group --rom=<path> --dungeon=0x##

# Get ASCII map (if applicable)
z3ed dungeon-map --rom=<path> --room=0x##
```
