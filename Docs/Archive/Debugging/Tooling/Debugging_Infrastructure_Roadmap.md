# Debugging Infrastructure Roadmap

**Created:** 2026-01-25
**Last Updated:** 2026-01-25

> NOTE (2026-02-07): This document contains historical references (skills/MCPs, `state_library.py`, `mesen_cli.sh`).
> The current supported workflow is the Mesen2 OOS fork socket API via `python3 scripts/mesen2_client.py`.
> Start from `RUNBOOK.md` and `Docs/Tooling/Tooling/Root_Cause_Debugging_Workflow.md`.

## Implementation Status

| Phase | Status | Notes |
|-------|--------|-------|
| 1.1 Deprecate Duplicates | **DONE** | 23 duplicates deprecated, 5 unique states remain |
| 1.2 Canon State Capture | Pending | Manual workflow ready |
| 3.1 Hyrule Navigator Skill | **DONE** | Created at `~/.claude/skills/hyrule-navigator/` |
| 4.1 CLI Navigation Command | **DONE** | `mesen2_client.py navigate` added |

## Executive Summary

The oracle-of-secrets debugging infrastructure has solid foundations but suffers from:
1. **State quality crisis** - ~~All 28 states lack verification, many are duplicates~~ **FIXED: 23 duplicates deprecated**
2. **Skill fragmentation** - ~~Navigation modules exist but aren't integrated~~ **FIXED: hyrule-navigator created**
3. **Missing data assets** - World graph for pathfinding doesn't exist
4. **Incomplete automation** - Manual workflows still required for common tasks

---

## Current State Analysis

### Working Components

| Component | Maturity | Notes |
|-----------|----------|-------|
| `mesen2_client_lib/` | Production | Full socket API, state management |
| `campaign/overworld_navigator.py` | Production | A* pathfinding, POI navigation |
| `campaign/collision_navigator.py` | Production | Collision-aware movement |
| `campaign/locations.py` | Complete | 160+ room/area mappings |
| `state_library.py` | Upgraded | Hash validation, canon workflow |
| `oracle-debugger` skill | Framework | Good structure, gaps in execution |

### Critical Gaps

| Gap | Impact | Effort |
|-----|--------|--------|
| No canon states | Can't run reliable tests | Medium (manual capture) |
| No world graph | Can't do cross-area navigation | High (data generation) |
| No hyrule-navigator skill | Skill mentioned but doesn't exist | Medium |
| Hypothesis testing not implemented | Can't auto-test fixes | High |
| Navigation not integrated | Debugger can't move Link autonomously | Low |

---

## Phase 1: State Quality Foundation (Priority: Critical)

### 1.1 Deprecate Broken Baselines

Run backfill and identify duplicates:
```bash
python3 scripts/mesen2_client.py lib-backfill
python3 scripts/mesen2_client.py library --verbose
```

Expected: All 22 baseline/current entries share same MD5 → deprecate all but one alias.

### 1.2 Capture 5 Canon States (Manual)

**Required states for regression testing:**

| ID | Location | Area | Purpose | Tags |
|----|----------|------|---------|------|
| `canon_links_house` | Link's House | 0x23 | Boot reference | `overworld`, `start` |
| `canon_lost_woods` | Lost Woods Center | 0x40 | Transition hotspot | `transition`, `puzzle` |
| `canon_village_west` | Village West | 0x23 | Near boundaries | `transition`, `village` |
| `canon_dungeon_entry` | Zora Temple Entry | 0x06 | Dungeon mode | `dungeon`, `indoor` |
| `canon_dark_world` | Temporal Pyramid | 0xC0 | Cross-world | `dark-world`, `pyramid` |

**Workflow:**
```bash
# 1. Launch and navigate manually
python3 scripts/mesen2_client.py launch

# 2. Save as draft
python3 scripts/mesen2_client.py lib-save "Link's House Start" --captured-by human -t overworld -t start

# 3. Verify and promote
python3 scripts/mesen2_client.py lib-verify <state_id>
```

### 1.3 Update Battery Test

Modify `transition_tester.py` to require canon states:
- Already done: `canon_only=True` default
- TODO: Add `--require-minimum 5` flag to fail if fewer than 5 canon states

---

## Phase 2: World Graph Generation (Priority: High)

### 2.1 Create World Graph Schema

**File:** `Docs/Data/world_graph.json`

```json
{
  "version": 1,
  "generated": "2026-01-25T00:00:00Z",
  "overworld": {
    "screens": [
      {
        "id": "0x00",
        "name": "Loom Ranch",
        "exits": {
          "north": "0x08",
          "south": "0x10",
          "east": "0x01",
          "west": null
        },
        "entrances": [
          {"entrance_id": 5, "destination_room": "0x50", "type": "cave"}
        ]
      }
    ]
  },
  "dungeons": {
    "rooms": [
      {
        "id": "0x06",
        "name": "Zora Temple (Arrghus Boss)",
        "exits": {
          "north": "0x16",
          "stairwell": "0x07"
        }
      }
    ]
  }
}
```

### 2.2 Generate from yaze/z3ed

If yaze has room data extraction:
```bash
z3ed dungeon-export --format json > world_graph_dungeons.json
z3ed overworld-export --format json > world_graph_overworld.json
```

Otherwise, parse from `campaign/locations.py` + manual connectivity mapping.

### 2.3 Integrate with Pathfinder

Extend `campaign/pathfinder.py` to load world graph for multi-screen paths:
```python
def find_cross_area_path(self, from_area: int, to_area: int) -> list[AreaTransition]:
    """Find path between overworld areas using world graph."""
    graph = load_world_graph()
    return self._dijkstra_areas(graph, from_area, to_area)
```

---

## Phase 3: Hyrule Navigator Skill (Priority: Medium)

### 3.1 Create Skill Structure

**Directory:** `~/.claude/skills/hyrule-navigator/`

```
hyrule-navigator/
├── SKILL.md          # Skill documentation
├── config.toml       # Configuration
├── scripts/
│   └── navigator.py  # Main entry point
└── data/
    └── world_graph.json  # Symlink to Docs/Data/
```

### 3.2 Skill Capabilities

```python
# CLI interface
navigator.py goto --area 0x40 --position 512,512
navigator.py goto --poi "lost_woods_center"
navigator.py goto --entrance 0x05
navigator.py path --from 0x23 --to 0x40  # Show path only
```

### 3.3 Integration with oracle-debugger

Add to `~/.claude/skills/oracle-debugger/scripts/debugger.py`:
```python
def navigate_to(self, target: str | tuple[int, int]) -> NavigationResult:
    """Delegate to hyrule-navigator."""
    from hyrule_navigator import Navigator
    nav = Navigator(self.bridge)
    return nav.goto(target)
```

---

## Phase 4: Autonomous Movement Improvements (Priority: Medium)

### 4.1 Movement Command in mesen2_client

Add `move` command for basic autonomous movement:
```bash
python3 scripts/mesen2_client.py move --direction north --distance 100
python3 scripts/mesen2_client.py move --to 512,512
python3 scripts/mesen2_client.py move --to-poi lost_woods_center
```

### 4.2 Safe Movement with Timeout

All movement commands should:
1. Check game mode before/after
2. Detect black screen condition
3. Timeout after N frames
4. Save recovery state before risky movements

```python
class SafeMovement:
    def move_with_recovery(self, target, timeout_frames=300):
        # Save checkpoint
        self.bridge.save_state_slot(99)

        try:
            result = self.navigator.move_to(target, timeout=timeout_frames)
            if result.black_screen:
                # Capture failure state
                self.capture_failure("black_screen_during_movement")
                # Restore checkpoint
                self.bridge.load_state_slot(99)
                return MovementResult.FAILED_BLACK_SCREEN
            return result
        except TimeoutError:
            self.bridge.load_state_slot(99)
            return MovementResult.FAILED_TIMEOUT
```

### 4.3 Input Recording Replay

Integrate `campaign/input_recorder.py` for deterministic replay:
```bash
python3 scripts/mesen2_client.py record --output walk_to_lost_woods.json
python3 scripts/mesen2_client.py replay --input walk_to_lost_woods.json
```

---

## Phase 5: Hypothesis Testing Implementation (Priority: Low)

### 5.1 Memory Patching Framework

Add to `mesen2_client_lib/client.py`:
```python
def apply_hypothesis(self, patches: dict[int, list[int]]) -> None:
    """Apply temporary memory patches for hypothesis testing."""
    for addr, bytes in patches.items():
        self.bridge.write_memory(addr, bytes)

def rollback_hypothesis(self) -> None:
    """Restore from checkpoint."""
    self.bridge.load_state_slot(99)
```

### 5.2 Hypothesis Test Loop

```python
def test_hypothesis(self, hypothesis: Hypothesis, scenario: str) -> HypothesisResult:
    # 1. Load known-failing state
    self.states.load(scenario)

    # 2. Save checkpoint
    self.bridge.save_state_slot(99)

    # 3. Apply patches
    self.apply_hypothesis(hypothesis.patches)

    # 4. Run scenario
    result = self.scenarios.run(scenario)

    # 5. Check if fix worked
    passed = not self.detect.black_screen()

    # 6. Rollback
    self.rollback_hypothesis()

    return HypothesisResult(hypothesis=hypothesis, passed=passed, trace=result.trace)
```

---

## Phase 6: trace-detective Skill (Priority: Low)

### 6.1 Create Trace Analysis Skill

**Directory:** `~/.claude/skills/trace-detective/`

Capabilities:
- Load CPU traces from Mesen2
- Find loops and infinite waits
- Detect mode transitions
- Compare traces against known-good patterns

### 6.2 Pattern Library

Create `~/.claude/skills/trace-detective/patterns/`:
```json
{
  "black_screen_mode_stuck": {
    "pattern": "Mode 0x07 + INIDISP 0x80 for >90 frames",
    "diagnosis": "Submodule not advancing",
    "common_causes": ["SEP/REP mismatch", "Wrong bank", "Bad JSL target"]
  }
}
```

---

## Execution Priority

| Phase | Priority | Effort | Dependencies |
|-------|----------|--------|--------------|
| 1. State Quality | Critical | Low | None |
| 2. World Graph | High | High | yaze exports |
| 3. Hyrule Navigator | Medium | Medium | Phase 2 |
| 4. Movement Improvements | Medium | Medium | Phase 3 |
| 5. Hypothesis Testing | Low | High | Phase 1 |
| 6. Trace Detective | Low | Medium | None |

---

## Success Metrics

- [ ] 5+ canon states with unique MD5 hashes
- [ ] World graph with 160+ overworld screens mapped
- [ ] `hyrule-navigator` skill functional
- [ ] Autonomous navigation test passes (goto poi → arrive)
- [ ] Black screen auto-recovery works
- [ ] At least 1 hypothesis test executed successfully

---

## Related Documents

- [State Quality Roadmap](./State_Quality_Roadmap.md) - Phase 1 details
- [Mesen2 Architecture](./Mesen2_Architecture.md) - Socket API reference
- [Campaign Goals](../Campaign/CampaignLog.md) - Navigation test results
