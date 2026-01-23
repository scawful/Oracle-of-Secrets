# Oracle of Secrets - Agent Instructions

**For all AI agents (Claude, Gemini, Codex)**

---

## Quick Start

1. **Read First:** Check `Docs/GEMINI.md` for the core profile and collaboration strategy
2. **Query Memory:** Search the knowledge graph before starting work
3. **Check Context:** Read relevant knowledge docs from `~/.context/projects/oracle-of-secrets/`
4. **Document Progress:** Update scratchpad and handoff docs during/after work

---

## Knowledge System (IMPORTANT)

### Memory Graph - Query Before Coding

**Always query the memory graph at session start for Oracle work:**

```
mcp__memory__search_nodes("Oracle")
```

**Key entities to check:**
- `OracleOfSecrets` - Project overview, recent issues, lessons learned
- `OracleSRAMLayout` - Save RAM addresses and story flags
- `OracleWRAMLayout` - Working RAM addresses
- `OracleSpriteFramework` - Sprite development patterns
- `OracleVanillaRoutines` - Key vanilla addresses to call
- `OracleKnownIssues` - Active bugs and gotchas
- `Oracle65816Patterns` - Code conventions

**Before modifying vanilla behavior:**
```
mcp__memory__open_nodes(["VanillaProbeSystem", "ZSCustomOverworld"])
```

### AFS Knowledge Docs

**Located at:** `~/.context/projects/oracle-of-secrets/knowledge/`

| Document | When to Read |
|----------|--------------|
| `oracle_quick_reference.md` | Starting any Oracle task |
| `sprite_development_guide.md` | Creating/modifying sprites |
| `debugging_patterns.md` | Investigating bugs, post-regression |

**Read before implementation:**
```
Read ~/.context/projects/oracle-of-secrets/knowledge/oracle_quick_reference.md
```

### Scratchpad & Handoffs

**Located at:** `~/.context/projects/oracle-of-secrets/scratchpad/`

| File | Purpose |
|------|---------|
| `agent_handoff.md` | Cross-session coordination, current status |
| `debugging_session_*.md` | Session logs for complex investigations |

**Always check handoff at session start:**
```
Read ~/.context/projects/oracle-of-secrets/scratchpad/agent_handoff.md
```

---

## Proactive Knowledge Management

### When Starting a Session

1. Query memory graph for relevant entities
2. Read `agent_handoff.md` for current status
3. Check `OracleKnownIssues` for gotchas related to your task
4. Read relevant knowledge docs

### During Work

1. **Before modifying code:** Check memory graph for related systems
2. **After discovering something:** Add observations to relevant entities
3. **If you hit a bug:** Check `debugging_patterns.md` first

### When Finishing

1. **Update memory graph** with new discoveries:
   ```
   mcp__memory__add_observations({
     observations: [{
       entityName: "OracleKnownIssues",
       contents: ["New issue discovered: ..."]
     }]
   })
   ```

2. **Update handoff doc** with session summary
3. **Create issue doc** if bug found: `Docs/Issues/<name>.md`

---

## Code Patterns (Quick Reference)

### Namespace Rules
- Most code: `namespace Oracle { }`
- ZSCustomOverworld: **Outside namespace** (global)
- Cross-namespace: Prefix with `Oracle_`

### Routine Template
```asm
MyRoutine:
{
  PHB : PHK : PLB    ; Required bank setup
  ; ... code ...
  PLB
  RTL
}
```

### SRAM Flags
```asm
%SRAMSetFlag(OOSPROG, !Story_IntroComplete)
%SRAMCheckFlag(OOSPROG, !Story_IntroComplete) : BNE .has_flag
```

### Sprite State Machine
```asm
LDA.w SprAction, X
JSL JumpTableLocal
dw State_Idle, State_Chase, State_Attack
```

---

## Critical Gotchas

### 1. Vanilla Probe System
**WRONG:** `LDA.w SprTimerD, X` for probe detection
**RIGHT:** `LDA.w SprState, X` (vanilla sets `$0D80,X`, not `$0EE0,X`)

### 2. ZSCustomOverworld Transitions
**NEVER** modify coordinates (`$20-$23`) during transition flow.
Use post-transition hooks instead.

### 3. Collision Offsets
`TileDetect_MainHandler` adds +20 pixel Y offset before checking.
Visual water at Y=39 needs collision data at Y=41.

---

## Build & Test

```bash
# Build
cd ~/src/hobby/oracle-of-secrets
./scripts/build_rom.sh 168

# Test
~/src/tools/emu-launch -m Roms/oos168x.sfc

# With debug script
~/src/tools/emu-launch -m Roms/oos168x.sfc scripts/mesen_water_debug.lua
```

---

## Mesen2 Fork

- **Active repo:** `~/src/third_party/forks/Mesen2`
- Do not edit upstream or alternate clones unless explicitly requested
- If multiple clones look active, compare recent activity and ask

---

## Documentation Hierarchy

1. **This file** (`CLAUDE.md`) - Quick agent reference
2. **`Docs/GEMINI.md`** - Full collaboration strategy
3. **`Docs/General/DevelopmentGuidelines.md`** - Architecture rules
4. **`~/.context/projects/oracle-of-secrets/knowledge/`** - Technical references
5. **`~/.context/projects/oracle-of-secrets/scratchpad/`** - Session state
