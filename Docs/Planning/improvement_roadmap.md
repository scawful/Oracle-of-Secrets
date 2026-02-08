# Oracle of Secrets - Improvement Roadmap

**Created:** 2026-01-23
**Status:** Planning

---

## Overview

Based on recent debugging sessions, we've identified four major improvements to enhance code quality, prevent regressions, and enable better agent-assisted development.

---

## Priority 1: Live Debugging Assistant

**Goal:** Agent can connect to Mesen2 during user testing and provide real-time analysis.

### Concept
When user is testing the game, an agent monitors RAM via Mesen2 socket:
- Detects area transitions and reports state
- Watches for anomalies in scroll registers, positions
- Cross-references with known issues in memory graph
- Suggests what to check based on current game state

### Mesen2 Socket API (Available)
```
Socket: /tmp/mesen2-<pid>.sock
Protocol: Newline-delimited JSON

Commands:
- STATE - Basic emulation state
- READ/READ16/READBLOCK - Memory reads
- CPU - Register snapshot
- STATEINSPECT - System + watch HUD text
- BREAKPOINT - Set/manage breakpoints
```

### Implementation Plan
1. Use `python3 scripts/mesen2_client.py assistant` as the entry point (socket API).
2. Define watch profiles per area type:
   - Overworld: $8A, $20-$23, $E1-$E9
   - Dungeon: $A0, $048E, sprite slots
   - Boss: Boss sprite state, health
3. Add pattern detection for known issues:
   - Lost Woods: Scroll register drift
   - Water collision: $7F2000 collision map
4. Integrate with CLI: `python3 scripts/mesen2_client.py assistant`

### Example Session
```
User: "Testing Lost Woods, help me debug"
Agent: [Connects to Mesen2 socket]
Agent: "Connected. Watching area transitions and scroll registers."

[User walks into Lost Woods]
Agent: "Entered area 0x29 (Lost Woods). Scroll: E1=$00, E7=$0A"

[User does invalid combo, exits west]
Agent: "Transition to 0x28. Scroll: E1=$02, E7=$0A.
        WARNING: E1 offset +2 from expected. Camera may be misaligned."
```

---

## Priority 2: Vanilla Behavior Database

**Goal:** Prevent incorrect assumptions about vanilla routine behavior.

### Problem
We assumed vanilla probe sets `SprTimerD`, wasted implementation time. This is preventable with systematic documentation.

### Structure
```yaml
Sprite_SpawnProbeAlways_long:
  address: $05C66E
  bank: 05
  inputs:
    - register: X
      description: Parent sprite slot
    - address: $00-$03
      description: Sprite position (must be set before call)
  outputs:
    - register: Y
      description: Spawned probe slot ($FF if failed)
    - address: $0DB0,Y
      description: Set to X+1 (parent reference)
  side_effects:
    - Sets SprState ($0D80,Y) on contact with Link
    - Does NOT set SprTimerD
  calls:
    - FireProbe ($05C612)
  verified: 2026-01-23
  verified_by: Disassembly tracing
  notes: |
    Probe sprite ID $41 travels toward Link.
    Despawns on wall hit (CheckTileSolidity).
```

### Storage
- YAML files in `~/.context/projects/oracle-of-secrets/knowledge/vanilla/`
- Memory graph entities link to files
- Agents query before using vanilla routines

### Process
1. Before using vanilla routine, check if documented
2. If not documented, trace in disassembly + Mesen2
3. Document actual behavior with verification date
4. Add to memory graph

### Initial Routines to Document
- Sprite_SpawnProbeAlways_long ($05C66E)
- FireProbe ($05C612)
- TileDetect_MainHandler ($07D077)
- Overworld_HandleTransitions
- Guard_ParrySwordAttacks
- Sprite_Move, Sprite_BounceFromTileCollision

---

## Priority 3: Automated Regression Tests

**Goal:** Catch regressions before they reach manual testing.

### Concept
Use save states + Mesen2 socket to create reproducible tests.

### Test Categories
| Category | Example | Assertions |
|----------|---------|------------|
| Transitions | Walk from 0x29 to 0x28 | Area ID, scroll values |
| Sprites | Approach Booki | Detection triggers at correct distance |
| Collision | Step on water tile | Collision value $08 |
| Story | Set flag, verify NPC | Dialogue changes |

### Implementation
```python
# scripts/test_runner.py
class OracleTestRunner:
    def __init__(self, socket_path):
        self.client = Mesen2Client(socket_path)

    def test_lost_woods_exit_west(self):
        self.client.loadstate("states/lost_woods_center.mss")
        self.client.write(0x7E0026, 0x04)  # Push left
        for _ in range(120):
            self.client.frame()
        area = self.client.read(0x7E008A)
        assert area == 0x28, f"Expected 0x28, got {hex(area)}"
        scroll = self.client.read16(0x7E00E1)
        assert scroll < 0x100, f"Scroll too high: {hex(scroll)}"
```

### Save State Library
Location: `~/.context/projects/oracle-of-secrets/states/`

| State | Location | Purpose |
|-------|----------|---------|
| `title_screen.mss` | Title screen | Boot verification |
| `overworld_start.mss` | Starting area | General overworld tests |
| `lost_woods_center.mss` | Area 0x29 center | Transition tests |
| `water_gate_room.mss` | Room 0x27 | Collision tests |
| `booki_nearby.mss` | Near Booki sprite | Detection tests |

---

## Priority 4: Code Quality Standards

### Inline Documentation
Every custom routine needs:
```asm
; =========================================================
; Sprite_Booki_DetectPlayer
;
; Checks if Link is within detection range.
;
; Input:  X = sprite slot
; Output: Carry set if detected
; Uses:   $0E, $0F (distance scratch)
; See:    OracleSpriteFramework (memory graph)
; =========================================================
```

### RAM Address Comments
```asm
LDA.w $0D80, X    ; SprState - set by probe on contact
LDA.w $0EE0, X    ; SprTimerD - general countdown (NOT probe!)
LDA.b $8A         ; Current area ID
```

### Pre-Commit Checks
1. asar syntax validation
2. Check for unbalanced PHB/PLB
3. Warn if modifying addresses in OracleKnownIssues

### Change Impact Tags
Add to files that have known dependencies:
```asm
; DEPENDENCIES: ZSCustomOverworld uses these coordinates
; CAUTION: Do not modify $20-$23 during transition flow
```

---

## Quick Wins (Implement Now)

1. **Socket client library**: Add `scripts/mesen2_client.py` with basic commands
2. **Watch profile**: Create `oracle_debug.watch` for common addresses
3. **Test state**: Create first save state at known-good location
4. **Document one routine**: Fully document `Sprite_SpawnProbeAlways_long`

---

## Integration with Memory Graph

```
mcp__memory__search_nodes("OracleFutureImprovements")

Entities created:
- OracleFutureImprovements (roadmap)

Relations:
- OracleOfSecrets -> PLANNED_FOR -> OracleFutureImprovements
- OracleFutureImprovements -> DEPENDS_ON -> Mesen2MCP
- OracleDebuggingTools -> ENABLES -> OracleFutureImprovements
```

---

## Next Steps

1. [ ] Create `scripts/mesen2_client.py` with basic socket operations
2. [ ] Create first save state at overworld start
3. [ ] Document `Sprite_SpawnProbeAlways_long` fully with verification
4. [ ] Test socket connectivity with running Mesen2 instance
5. [ ] Design assistant mode interaction pattern
