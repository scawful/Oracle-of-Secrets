# Oracle of Secrets Gigaleak Integration Plan

How to leverage `~/Code/alttp-gigaleak/` resources for OoS ROM hacking.

## Sprite & Enemy Implementation

### Source Files
| File | Contents | Priority |
|------|----------|----------|
| `2. restorations/poltergeist/` | Complete enemy implementation (11 subtypes) | HIGH |
| `2. restorations/disco_dragon/` | Boss implementation with sprites/music | HIGH |
| `2. restorations/zora_boss/` | Alternative boss variant | MEDIUM |
| `DISASM/jpdasm/bank_06.asm` - `bank_09.asm` | Sprite/enemy code banks | HIGH |

### Poltergeist Subtypes (Templates)
The poltergeist restoration includes 11 object types - each is a template for OoS:
1. Chair - Simple animated furniture
2. Axe - Throwable weapon object
3. Dish - Breakable object
4. Fork/Knife - Projectile enemies
5. Window - Environmental hazard
6. Frame - Decorative with collision
7. Bed - Large multi-tile object
8. Table - Furniture with interaction
9. Ghost - Full enemy AI with patrol/attack

### Implementation Ideas
1. **New Enemy Creation**
   - Study poltergeist ASM structure for enemy template
   - Copy collision table format
   - Adapt sprite property definitions
   - Use music integration pattern (.zsm files)

2. **Boss Development**
   - Reference disco_dragon for multi-phase boss
   - Study sprite data tables (ENMDD format)
   - Adapt graphics loading patterns

## Cut Content Restoration

### Source: glitter_references.txt
| Feature | Description | Complexity |
|---------|-------------|------------|
| **Utau (Sing)** | Music note item, ancilla 14 | MEDIUM |
| **Taberu (Eat)** | Meat/food healing items | LOW |
| **Neru (Sleep)** | Zzz item (exists in opening) | LOW |
| **Odoru (Dance)** | Unused player action | MEDIUM |
| **Aisatsu (Greet)** | NPC interaction action | MEDIUM |
| **Tame Dot** | Charged rod system (ancillae 0E-12) | HIGH |
| **Nicinoru (Pray)** | Single pendant prayer | MEDIUM |

### Implementation Ideas
1. **Quick Wins (Low Complexity)**
   - Add meat/food items as healing alternatives
   - Implement sleep mechanic for inn/bed interactions
   - Use existing sprites with new item IDs

2. **Medium Features**
   - Sing action with music note projectile
   - Dance action for puzzle triggers
   - Greet action for NPC dialogue branches
   - Prayer system for shrine interactions

3. **Advanced Features**
   - Full charged rod system (replaces magic meter temporarily)
   - Multi-phase boss with cut mechanics

## Disassembly Labels

### Source Files
| File | Contents | Use Case |
|------|----------|----------|
| `DISASM/jpdasm/symbols_wram.asm` | RAM variable names | Replace magic numbers |
| `DISASM/jpdasm/bank_*.asm` | Routine labels | Jump target names |
| `alttp_labels.mlb` | Full label database | Reference lookup |

### Key Symbol Categories
```asm
; Player state (from symbols_wram.asm)
$7E0010 - Link's state
$7E0012 - Link's direction
$7E0020 - Link's X position
$7E0022 - Link's Y position

; Item/Equipment
$7E0340 - Current item
$7E0342 - Item state

; Dungeon
$7E0400 - Room ID
$7E0402 - Floor/layer
```

### Implementation Ideas
1. **Code Quality**
   - Replace numeric addresses with symbol names
   - Add official labels to OoS include files
   - Document routines with original Japanese names

2. **Debugging**
   - Use symbol names in debug output
   - Create RAM watch list with labels

## Japanese Source Reference

### Useful Naming Patterns
| Pattern | Meaning | Example |
|---------|---------|---------|
| `zel_*` | Main game code | `zel_char` = character |
| `z-*` | Asset directories | `z-link` = Link sprites |
| `ENMDD` | Enemy data | Sprite tables |
| `ongen` | Sound/audio | Sound bank |
| `mut` | Mutation/change | State transitions |

### Implementation Ideas
1. **Consistent Naming**
   - Adopt Japanese prefixes for OoS code organization
   - Use `oos_*` prefix mirroring `zel_*` pattern
   - Document terminology in project wiki

## Roadmap

### Phase 1: Foundation
- [ ] Review poltergeist enemy structure
- [ ] Extract useful ASM patterns/macros
- [ ] Import relevant symbol definitions
- [ ] Document in OoS coding standards

### Phase 2: Quick Wins
- [ ] Implement food/meat healing items
- [ ] Add sleep interaction for beds/inns
- [ ] Create template enemy from poltergeist

### Phase 3: Cut Content
- [ ] Implement sing action + music note
- [ ] Add dance/greet NPC interactions
- [ ] Design prayer shrine system

### Phase 4: Advanced
- [ ] Charged rod system (if fits OoS design)
- [ ] Multi-phase boss using disco_dragon patterns
- [ ] Custom music integration (.zsm)

## File Organization

Suggested structure for OoS gigaleak integration:
```
Oracle-of-Secrets/
├── Reference/
│   ├── gigaleak_symbols.asm    # Imported symbol definitions
│   ├── enemy_templates.md      # Notes on poltergeist patterns
│   └── cut_content.md          # glitter_references summary
├── Sprites/
│   └── [new sprites based on gigaleak study]
└── docs/
    └── GIGALEAK_INTEGRATION.md # This file
```

## References

- Gigaleak location: `~/Code/alttp-gigaleak/`
- Poltergeist restoration: `~/Code/alttp-gigaleak/2. restorations/poltergeist/`
- Disco dragon: `~/Code/alttp-gigaleak/2. restorations/disco_dragon/`
- Cut content notes: `~/Code/alttp-gigaleak/glitter_references.txt`
- Main disassembly: `~/Code/alttp-gigaleak/DISASM/jpdasm/`
- Symbol definitions: `~/Code/alttp-gigaleak/DISASM/jpdasm/symbols_wram.asm`
