# Yaze Oracle Project Experience — Feature Spec

**Date:** 2026-02-08
**Status:** Proposed
**Goal:** Make yaze a daily-driver IDE for Oracle of Secrets, not just an occasional ROM editor.

## Problem

Yaze has strong infrastructure (panel system, room rendering, shortcuts, hack manifest) but the Oracle experience has gaps:

1. **Dungeon presets are vanilla ALTTP** — "Thieves' Town" not "Zora Temple", wrong room lists
2. **No project-level dungeon overview** — can't see all D4 rooms at a glance with actual bitmaps
3. **No zoom on dungeon map** — fixed 64px thumbnails
4. **Only grid-adjacent connections shown** — misses stair/holewarp connections (the real connectivity)
5. **No Oracle menu/shortcuts** — no quick way to jump to dungeon overview, feature flags, etc.
6. **Room names are vanilla** — tooltips say "Empty Clone" instead of "Water Grate Room"
7. **Feature flags aren't easily toggleable** — no GUI to flip flags and rebuild
8. **No build/test status** — can't see if ROM is clean from within yaze

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Oracle Project Config                      │
│  (hack_manifest.json or project.yaze extensions)             │
│                                                               │
│  dungeons[] ─────► DungeonMapPanel (enhanced)                │
│  room_labels{} ──► ResourceLabelProvider                     │
│  feature_flags[] ► FeatureFlagPanel                          │
│  build_pipeline ─► BuildStatusWidget                         │
└─────────────────────────────────────────────────────────────┘
```

## Feature 1: Dungeon Registry in Project Metadata

### What

Add a `dungeons` section to `hack_manifest.json` (or a separate `dungeons.json` loaded by YazeProject) that defines each dungeon with Oracle names, room lists, and stair connections.

### Data Format

```json
{
  "dungeons": [
    {
      "id": "D4",
      "name": "Zora Temple",
      "vanilla_name": "Thieves' Town",
      "rooms": [
        {"id": "0x06", "name": "Arrghus Boss", "grid_row": 0, "grid_col": 6},
        {"id": "0x16", "name": "Swimming Treadmill", "grid_row": 1, "grid_col": 6},
        {"id": "0x25", "name": "Water Grate Room", "grid_row": 2, "grid_col": 5},
        {"id": "0x27", "name": "Water Gate Room", "grid_row": 2, "grid_col": 7},
        {"id": "0x28", "name": "Entrance", "grid_row": 2, "grid_col": 8}
      ],
      "stairs": [
        {"from": "0x28", "to": "0x38"},
        {"from": "0x37", "to": "0x06"},
        {"from": "0x34", "to": "0x25"}
      ],
      "holewarps": [
        {"from": "0x36", "to": "0x26"},
        {"from": "0x26", "to": "0x66"}
      ],
      "features": {
        "water_fill": {"rooms": ["0x25", "0x27"], "sram_address": "0x7EF411"},
        "zora_baby": {"rooms": ["0x25", "0x27"]}
      }
    }
  ]
}
```

### Implementation

- Extend `HackManifest` or add `DungeonRegistry` class loaded by `YazeProject`
- Replace `DungeonMapPanel::DrawDungeonSelector()` hardcoded presets with registry data
- Feed room grid positions from the registry (not auto-layout)
- Source: `d4_room_registry.json` (already generated) can seed this

## Feature 2: Enhanced DungeonMapPanel

### Current State (what exists)

`DungeonMapPanel` (`dungeon_map_panel.h`, 406 lines) already:
- Renders room thumbnails (64x64) via `Room::bg1_buffer().bitmap().texture()`
- Draws grid-adjacent connection lines between rooms
- Click to select → fires `on_room_selected_` callback
- Shows room ID + name in tooltip via `zelda3::GetRoomLabel()`
- Has dungeon preset selector combo box (vanilla ALTTP names)

### Enhancements Needed

#### A. Spatial Layout from Registry

Replace `AutoLayoutRooms()` (naive square grid) with registry-driven positions:

```cpp
void LoadFromDungeonRegistry(const DungeonRegistryEntry& dungeon) {
  dungeon_room_ids_.clear();
  room_positions_.clear();
  // Normalize grid positions to 0-based
  int min_row = INT_MAX, min_col = INT_MAX;
  for (const auto& room : dungeon.rooms) {
    min_row = std::min(min_row, room.grid_row);
    min_col = std::min(min_col, room.grid_col);
  }
  for (const auto& room : dungeon.rooms) {
    int id = room.id;
    dungeon_room_ids_.push_back(id);
    room_positions_[id] = ImVec2(room.grid_col - min_col, room.grid_row - min_row);
  }
  // Store stair/holewarp connections for drawing
  stair_connections_ = dungeon.stairs;
  holewarp_connections_ = dungeon.holewarps;
}
```

#### B. Stair + Holewarp Connection Drawing

Replace the grid-adjacency check with explicit connection data:

```cpp
// Draw stair connections as dashed blue arrows
for (const auto& stair : stair_connections_) {
  DrawConnection(draw_list, stair.from, stair.to,
                 kStairColor, /*dashed=*/true, /*arrow=*/true);
}
// Draw holewarps as dotted red arrows (one-way falls)
for (const auto& hole : holewarp_connections_) {
  DrawConnection(draw_list, hole.from, hole.to,
                 kHolewarpColor, /*dashed=*/false, /*arrow=*/true);
}
// Draw grid-adjacent connections as solid thin lines (door connections)
// ... (keep existing logic for same-row/same-col adjacency)
```

#### C. Zoom with Mouse Wheel

Add a zoom factor that scales thumbnail size:

```cpp
float zoom_ = 1.0f;  // 0.5x to 3.0x

void Draw(bool* p_open) override {
  // Mouse wheel zoom when hovering the canvas
  if (ImGui::IsWindowHovered() && ImGui::GetIO().MouseWheel != 0) {
    zoom_ = std::clamp(zoom_ + ImGui::GetIO().MouseWheel * 0.1f, 0.5f, 3.0f);
  }

  float kRoomWidth = 64.0f * zoom_;
  float kRoomHeight = 64.0f * zoom_;
  // ... rest of drawing uses zoomed sizes
}
```

At zoom > 1.5x, show room names below thumbnails. At zoom > 2.0x, show sprite icons or feature badges (water drop for water rooms, baby icon for ZoraBaby rooms).

#### D. Room Feature Badges

Small icons overlaid on room thumbnails:

```
💧 = Water fill zone (rooms 0x25, 0x27)
👶 = Zora Baby placed
⚔️ = Boss room
🔑 = Has key/big key
⭐ = Entrance
⚠️ = Unconverted palette
```

These come from the dungeon registry `features` section.

## Feature 3: Oracle Room Name Overrides

### What

Load Oracle-specific room names into `ResourceLabelProvider` so ALL tooltips, combo boxes, and labels throughout yaze show "Water Grate Room" instead of "Empty Clone."

### Implementation

The `ResourceLabelProvider` already supports project overrides via `SetProjectLabels()`. Add Oracle room names to the project config:

```json
{
  "resource_labels": {
    "room": {
      "0x06": "Arrghus Boss (D4)",
      "0x25": "Water Grate Room (D4)",
      "0x27": "Water Gate Room (D4)",
      "0x28": "Zora Temple Entrance (D4)",
      "0x37": "Map Chest / Water Fill (D4)",
      "0xA8": "Goron Mines Track Room (D6)",
      "0xB8": "L-Shaped Rail Room (D6)",
      "0xDA": "U-Shape Rail Room (D6)"
    }
  }
}
```

**Source:** The Oracle data sheet CSV (`Docs/Ref/Sheets/Oracle of Secrets Data Sheet - Rooms and Entrances.csv`, column 7) already has all the Oracle room names. A script can extract them into this format.

### Auto-Load

`YazeProject::Open()` already calls `TryLoadHackManifest()`. Extend this to also load resource labels from the manifest or a companion file.

## Feature 4: Oracle Menu and Shortcuts

### Top-Level "Oracle" Menu

```
Oracle
├── Project Dashboard          Ctrl+Shift+O
├── ──────────────────
├── Dungeons
│   ├── D1 Mushroom Grotto     Ctrl+1
│   ├── D2 Tail Palace         Ctrl+2
│   ├── D3 Kalyxo Castle       Ctrl+3
│   ├── D4 Zora Temple         Ctrl+4
│   ├── D5 Glacia Estate       Ctrl+5
│   ├── D6 Goron Mines         Ctrl+6
│   └── D7 Dragon Ship         Ctrl+7
├── ──────────────────
├── Feature Flags...           Ctrl+Shift+F
├── Water Fill Zones...
├── Track Collision...
├── ──────────────────
├── Build ROM                  Ctrl+B
└── Run in Mesen2              Ctrl+R
```

Each "Dungeon" menu item opens the DungeonMapPanel pre-loaded with that dungeon's rooms from the registry. `Ctrl+4` immediately shows the D4 Zora Temple overview with all 16 room thumbnails in their correct grid positions.

### Keyboard Shortcuts

Register in `KeyboardShortcuts` with context `kDungeon`:

| Shortcut | Action | Context |
|----------|--------|---------|
| Ctrl+1..7 | Open dungeon D1-D7 overview | Global |
| Ctrl+Shift+O | Open Oracle dashboard | Global |
| Ctrl+Shift+F | Open feature flag panel | Global |
| Ctrl+B | Build ROM (shell out to build_rom.sh) | Global |
| Ctrl+R | Launch in Mesen2 | Global |
| Z | Toggle zoom mode on dungeon map | Dungeon |
| S | Toggle stair connections visibility | Dungeon |
| H | Toggle holewarp connections visibility | Dungeon |

## Feature 5: Feature Flag Toggle Panel

### What

A panel showing all Oracle feature flags from `hack_manifest.json` with toggle switches. Changing a flag writes to `Config/feature_flags.asm` and triggers a rebuild.

### Implementation

```cpp
class FeatureFlagPanel : public EditorPanel {
  std::string GetId() const override { return "oracle.feature_flags"; }
  std::string GetDisplayName() const override { return "Feature Flags"; }

  void Draw(bool* p_open) override {
    for (auto& flag : hack_manifest_->feature_flags()) {
      bool enabled = flag.value != 0;
      if (ImGui::Checkbox(flag.name.c_str(), &enabled)) {
        flag.value = enabled ? 1 : 0;
        dirty_ = true;
      }
      ImGui::SameLine();
      ImGui::TextDisabled("(%s)", flag.description.c_str());
    }
    if (dirty_ && ImGui::Button("Apply & Rebuild")) {
      WriteFeatureFlags();
      TriggerBuild();
      dirty_ = false;
    }
  }
};
```

## Feature 6: Build Status Widget

### What

A small status bar widget showing ROM build state: last build time, success/failure, ROM hash. Lives in the main status bar.

### Implementation

```cpp
// In status bar drawing:
void DrawBuildStatus() {
  if (build_running_) {
    ImGui::TextColored(ImVec4(1, 1, 0, 1), ICON_MD_BUILD " Building...");
  } else if (build_success_) {
    ImGui::TextColored(ImVec4(0, 1, 0, 1), ICON_MD_CHECK " ROM clean");
  } else {
    ImGui::TextColored(ImVec4(1, 0, 0, 1), ICON_MD_ERROR " Build failed");
  }
  ImGui::SameLine();
  ImGui::TextDisabled("(%s)", last_build_time_.c_str());
}
```

## Implementation Priority

### Phase 1: Room Names + Dungeon Registry (Quick Win)
1. Generate Oracle room labels from data sheet CSV → JSON
2. Load into `ResourceLabelProvider` on project open
3. Add `dungeons` section to hack_manifest (or companion file)
4. Replace `DungeonMapPanel` presets with registry data

### Phase 2: Enhanced DungeonMapPanel (Core Feature)
1. Spatial layout from registry grid positions
2. Stair + holewarp connection arrows
3. Mouse wheel zoom
4. Room feature badges
5. Oracle dungeon names in selector

### Phase 3: Oracle Menu + Shortcuts (UX Polish)
1. Top-level "Oracle" menu
2. Ctrl+1..7 dungeon shortcuts
3. Feature flag panel
4. Build status widget

### Phase 4: Build Integration (Power User)
1. Ctrl+B triggers `build_rom.sh` with output in status bar
2. Ctrl+R launches Mesen2 with current ROM
3. Feature flag toggle → auto-rebuild pipeline

## Dependencies

- `DungeonMapPanel` (exists, needs enhancement)
- `ResourceLabelProvider` (exists, needs Oracle data)
- `KeyboardShortcuts` (exists, needs Oracle shortcuts)
- `MenuBuilder` (exists, needs Oracle menu)
- `HackManifest` (exists, needs dungeon registry extension)
- `PanelManager` + `EditorPanel` (exists, new panels follow pattern)

## Open Questions

1. **Where should the dungeon registry live?** Options: (a) extend `hack_manifest.json`, (b) separate `dungeons.json` in project, (c) embedded in `project.yaze`. Recommendation: (a) since hack_manifest already has rooms/tags.
2. **Should room name overrides come from the CSV or be manually curated?** Both — auto-generate from CSV as baseline, allow manual overrides in project config.
3. **Pan support on dungeon map?** Mouse drag to pan when zoomed in. Low priority but natural for large dungeons.
