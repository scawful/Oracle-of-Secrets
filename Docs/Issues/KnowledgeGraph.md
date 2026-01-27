# Oracle of Secrets Knowledge Graph

**Created:** 2026-01-24
**Purpose:** Document relationships between USDASM, Oracle of Secrets, YAZE, ZScream, and Mesen2
**Reference:** See `OvernightStatus.md` for current session status

---

## System Overview

```
                    ┌─────────────────┐
                    │  USDASM/Vanilla │
                    │   Disassembly   │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │   ZScream   │   │    Oracle   │   │    YAZE     │
    │  (Editor)   │◄──│  of Secrets │──►│ (Debugger)  │
    └──────┬──────┘   │   (Romhack) │   └──────┬──────┘
           │          └──────┬──────┘          │
           │                 │                 │
           └────────┬────────┴────────┬────────┘
                    ▼                 ▼
             ┌─────────────┐   ┌─────────────┐
             │  Mesen2 OOS │   │  Memory MCP │
             │   (Fork)    │   │   (Graph)   │
             └─────────────┘   └─────────────┘
```

---

## Component Details

### USDASM / Vanilla Disassembly

**Purpose:** Authoritative reference for vanilla ALTTP code behavior

**Locations:**
- Bank-organized ASM files (bank_00.asm through bank_1F.asm)
- RAM/ROM maps
- Symbol tables

**Key AFS Knowledge:**
- `~/.context/knowledge/alttp/routines.json` - Vanilla routine catalog
- `~/.context/knowledge/alttp/symbols.json` - Symbol definitions
- `~/.context/knowledge/alttp/ram_map.md` - RAM layout reference

**Critical Routines:**
| Address | Label | Purpose | Oracle Usage |
|---------|-------|---------|--------------|
| $07D077 | TileDetect_MainHandler | Collision detection | Water collision fix reference |
| $05C66E | Sprite_SpawnProbeAlways | Probe creation | Probe-based detection (planned) |
| $02D8EB | Module_LoadFile | Area transitions | Black screen debugging |
| $0289BF | Intraroom transition | Layer changes | SEP/REP fix location |
| $0AB8F5 | BirdTravel_LoadTargetArea | Camera setup | Warp research target |

---

### Oracle of Secrets

**Purpose:** ALTTP ROM hack - the primary project

**Location:** `~/src/hobby/oracle-of-secrets/`

**Key Systems:**
| System | Bank | Files | Purpose |
|--------|------|-------|---------|
| ZSCustomOverworld | $28 | `Overworld/ZSCustomOverworld.asm` | Extended overworld |
| Time System | $34 | `Overworld/time_system.asm` | Day/night cycle |
| Mask System | $33-$3B | `Masks/*.asm` | Form transformations |
| Menu System | $2D-$2E | `Menu/*.asm` | Custom HUD/menus |
| Sprite Framework | $30-$32 | `Sprites/*.asm` | 60+ custom sprites |
| Dungeon System | $2C | `Dungeons/*.asm` | 7 dungeons + shrines |

**Memory Layout:**
- SRAM: `$7EF300-4FF` - Save data, story progression
- Custom WRAM: `$7E0730+` - Runtime state
- OOSPROG: `$7EF3D6` - Main story flags
- OOSPROG2: `$7EF3C6` - Secondary flags

**Namespace Rules:**
- `namespace Oracle { }` - Most custom code
- ZSCustomOverworld - Outside namespace (global)
- Cross-namespace calls: Use `Oracle_` prefix

---

### ZScream

**Purpose:** ROM editor used to build Oracle of Secrets maps/dungeons

**Integration Points:**
- `ZSCustomOverworld.asm` - ZScream's extended overworld system
- `Util/ZScreamNew/` - ZScream patches included in Oracle
- Exports: Map data, tileset configs, dungeon layouts

**Key ZScream Patches Used:**
- `ZS_Patches/Misc/IntroSkip.asm` - Skip intro sequence
- `ZS_Patches/Sprites/Crystalswitch Conveyor.asm` - Conveyor belt mechanics
- `ZS_Patches/Items/AST Boots.asm` - Boot mechanics

---

### YAZE

**Purpose:** SNES emulator with debugging capabilities and gRPC API

**Location:** `~/src/hobby/yaze/`

**Integration:**
- gRPC service at `src/app/service/`
- MCP bridge at `~/src/tools/yaze-mcp/`
- CLI commands for ROM testing

**Capabilities:**
| Feature | Status | MCP Support |
|---------|--------|-------------|
| ROM loading | Working | Yes |
| Memory read/write | Working | Yes |
| Breakpoints | Working | Yes |
| Save states | Proto defined | **Partial** (bridge needed) |
| Step execution | Working | Yes |

**Integration Gap:**
Save state proto defined in `emulator_service.proto` (SaveState, LoadState, ListStates RPCs).
Bridge wrapper needed for MCP exposure.
See `Mesen2_Debug_Backlog.md` task P1.3.

---

### Mesen2 OOS Fork

**Purpose:** SNES emulator specialized for Oracle debugging with socket API

**Location:** `~/src/hobby/mesen2-oos/`

**Unique Features:**
| Feature | Address/Location | Purpose |
|---------|------------------|---------|
| P_WATCH | SocketServer.cpp | Track processor status changes |
| MEM_BLAME | SocketServer.cpp | Attribute memory writes to PC |
| COLLISION_OVERLAY | WatchHud.cpp | Visualize collision maps |
| GAMESTATE | SocketServer.cpp | ALTTP game state reading |
| Socket API | `/tmp/mesen2-*.sock` | External automation |

**Build Command:**
```bash
cd ~/src/hobby/mesen2-oos
make clean && make
```

**Run Command:**
```bash
~/src/hobby/mesen2-oos/bin/osx-arm64/Release/Mesen
```

---

### Memory MCP (Knowledge Graph)

**Purpose:** Persistent cross-session knowledge storage

**Access:**
```
mcp__memory__search_nodes("Oracle")
mcp__memory__open_nodes(["OracleOfSecrets", "OracleKnownIssues"])
```

**Key Entities:**
| Entity | Type | Content |
|--------|------|---------|
| OracleOfSecrets | ROMHack | Project overview, features, lessons |
| OracleMemoryMap | architecture | Bank assignments, SRAM/WRAM layout |
| OracleSpriteFramework | architecture | Sprite development patterns |
| OracleKnownIssues | reference | Active bugs, gotchas |
| OracleBlackScreenBug | Bug | Current investigation status |
| VanillaProbeSystem | system | Probe sprite behavior |
| ZSCustomOverworld | system | Overworld extension details |

---

## Relationship Matrix

| From | To | Relationship | Notes |
|------|----|--------------|-------|
| Oracle | USDASM | references | Uses vanilla routine documentation |
| Oracle | ZScream | built_with | Dungeon/map editors |
| Oracle | ZSCustomOverworld | extends | Custom overworld system |
| Oracle | Mesen2 | tested_with | Primary emulator |
| Oracle | YAZE | debugged_with | gRPC debugging |
| Mesen2 | Oracle | socket_api | Live state inspection |
| YAZE | Oracle | grpc_api | Breakpoint debugging |
| Memory MCP | All | stores_knowledge | Cross-session context |

---

## Information Flow

### Debugging Workflow

```
1. USDASM Reference
   │
   ▼ Identify vanilla behavior
   │
2. Oracle Source Analysis
   │
   ▼ Locate custom code
   │
3. Mesen2 Live Inspection
   │
   ▼ Capture runtime state
   │
4. YAZE Breakpoint Analysis
   │
   ▼ Trace execution path
   │
5. Memory MCP Storage
   │
   ▼ Persist findings
```

### Build & Test Workflow

```
1. Edit Oracle ASM
   │
   ▼ ./scripts/build_rom.sh 168
   │
2. Static Verification (Tier 1)
   │
   ▼ Check opcodes in ROM
   │
3. Visual Testing (Tier 2)
   │
   ▼ Vanilla Mesen.app
   │
4. Automated Capture (Tier 3)
   │
   ▼ Mesen2 fork socket API
   │
5. Deep Debug (Tier 4)
   │
   ▼ YAZE gRPC + Mesen2 P_WATCH
```

---

## AFS Context Locations

| Purpose | Path |
|---------|------|
| Project knowledge | `~/.context/projects/oracle-of-secrets/knowledge/` |
| Session scratchpad | `~/.context/projects/oracle-of-secrets/scratchpad/` |
| ALTTP reference | `~/.context/knowledge/alttp/` |
| Skills | `~/.context/knowledge/skills/` → `~/.claude/skills/` |

---

## Symbol Cross-References

### Transition-Related Addresses

| Symbol | Address | Source | Used By |
|--------|---------|--------|---------|
| GameMode | $7E0010 | Vanilla | All |
| Submodule | $7E0011 | Vanilla | All |
| INIDISP | $7E001A | Vanilla | Black screen debug |
| Module_LoadFile | $02D8EB | USDASM | Mesen2 breakpoints |
| CheckForFollowerIntraroomTransition | $0289BF | Oracle | SEP/REP fix |
| WarpDispatcher | $3CB400 | Oracle | Debug warp |

### Sprite-Related Addresses

| Symbol | Address | Source | Used By |
|--------|---------|--------|---------|
| SprState | $0D80,X | Vanilla | Probe detection |
| SprTimerD | $0EE0,X | Vanilla | Animation timing |
| Sprite_SpawnProbeAlways | $05C66E | USDASM | Probe research |
| FireProbe | $05C612 | USDASM | Probe research |

---

## Future Integration Points

### Planned

1. **Unified Test Runner**
   - Uses both YAZE and Mesen2
   - State library for test setup
   - Assertions via memory read

2. **Expert Model Integration**
   - Local LMStudio models (din, farore, majora)
   - Specialized knowledge per domain
   - AFS orchestrator routing

3. **Embedding Service**
   - Semantic search across docs
   - Cross-project context retrieval

---

*See also: `OvernightStatus.md`, `Mesen2_Debug_Backlog.md`, `TieredTestingPlan.md`*
