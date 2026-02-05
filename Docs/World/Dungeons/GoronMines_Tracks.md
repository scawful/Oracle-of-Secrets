# Goron Mines - Minecart Track Layouts

Track objects use **Object ID 0x31** with subtypes defined by the `size` field.

## Subtype Reference

| Size | Type | Description |
|------|------|-------------|
| 0 | LeftRight | Horizontal track (no floor) |
| 1 | UpDown | Vertical track (no floor) |
| 2 | TopLeft | Corner: enters top, exits left |
| 3 | TopRight | Corner: enters top, exits right |
| 4 | BottomLeft | Corner: enters bottom, exits left |
| 5 | BottomRight | Corner: enters bottom, exits right |
| 6 | UpDownFloor | Vertical track with floor |
| 7 | LeftRightFloor | Horizontal track with floor |
| 8-11 | Corners+Floor | Corner variants with floor |
| 12 | FloorAny | Junction/crossover |
| 14 | TrackAny | Generic track segment |

---

## Room Track Counts

| Room | Track Objects | Primary Pattern |
|------|---------------|-----------------|
| 0x78 | **145** | Complex grid with crossings |
| 0x87 | 84 | Y=26 and Y=34 lines + verticals |
| 0xD8 | 74 | Two horizontal lines + corners |
| 0x98 | 27 | Single horizontal at Y=49 |
| 0x88 | 23 | Single horizontal at Y=26 |
| 0xC8 | 0 | Boss room - no tracks |

---

## Room 0x78 (Lanmolas Miniboss) - Most Complex

145 track objects forming a grid pattern:

```
    Y=18: Horizontal line with corners at X=8 (TL) and X=54 (TR)
          Verticals at X=20, X=31, X=42

    Y=32: Full horizontal span with junctions

    Y=46: Horizontal line with corners at X=8 (BL) and X=54 (BR)

Vertical columns at:
    X=8:  Y=18-46 (left edge)
    X=20: Y=16-46 (inner left)
    X=31: Y=16-50 (center)
    X=42: Y=12-46 (inner right)
    X=54: Y=18-46 (right edge)
```

**Track Schematic:**
```
     8        20       31       42       54
     |        |        |        |        |
18 --+--------+--------+--------+--------+--
     |        |        |        |        |
     |        |        |        |        |
32 --+--------+--------+--------+--------+--
     |        |        |        |        |
     |        |        |        |        |
46 --+--------+--------+--------+--------+--
```

---

## Room 0x87 (West Hall)

84 track objects:

**Horizontal Lines:**
- Y=26: X=14 to X=62 (main upper track)
- Y=34: X=14 to X=44 (lower track)
- Y=48: X=16 to X=48 (bottom track)

**Vertical Sections:**
- X=16: Y=48-62 (corner down from Y=48)
- X=44: Y=0-34 (right vertical, connects upper/lower)

**Key Feature:** T-junction at (44, 26) marked as "TrackAny"

---

## Room 0xD8 (Pre-Boss)

74 track objects:

**Horizontal Lines:**
- Y=14: X=13 to X=52 (upper)
- Y=40: X=0 to X=33 (middle)
- Y=47: X=17 to X=33 (lower-mid)
- Y=54: X=17 to X=55 (bottom)

**Corners:**
- (17, 47): TopLeft corner
- (17, 54): BottomLeft corner
- (33, 40): TopRight corner

---

## Room 0x98 (Entrance)

27 track objects - single horizontal line:

```
Y=49: X=0 to X=52

Track types:
- X=0-10: LeftRight (no floor)
- X=12-52: LeftRightFloor (with floor)
```

Simple entry track for the minecart.

---

## Room 0x88 (Big Chest)

23 track objects - single horizontal line:

```
Y=26: X=0 to X=44 (all LeftRightFloor)
```

---

## Room 0xC8 (Boss Room)

**No track objects.** Boss arena is track-free.

---

## Using z3ed to Query Tracks

```bash
# List all objects in a room
z3ed dungeon-list-objects --rom=Roms/oos168x.sfc --room=0x78

# Filter for track objects (ID 0x31 = 49 decimal) with Python
z3ed dungeon-list-objects --rom=Roms/oos168x.sfc --room=0x78 | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  [print(f'({o[\"x\"]},{o[\"y\"]}) size={o[\"size\"]}') \
   for o in d['Dungeon Room Objects']['objects'] if o['id']==0x31]"
```
