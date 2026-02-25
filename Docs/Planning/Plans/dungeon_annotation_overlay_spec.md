# Dungeon Annotation Overlay Spec

Yaze dungeon editor overlay for room-level annotations (Pins, Regions, Connections). Schema: `Docs/schemas/dungeon_annotations.schema.json`.

---

## 1. Implementation Phases

### Phase 1: MVP
- Data model: `AnnotationCategory`, `PinAnnotation`, `RegionAnnotation`, `RomAnnotations`
- JSON serialization (nlohmann/json), polymorphic via `"type"` field
- Persistence: `rom_name.annotations.json` sidecar; load on ROM load, save on ROM save
- Annotation panel: Add/Edit/Delete, scrollable list, hit-testing on canvas
- Canvas: draw Pins (circle) and Regions (semi-transparent rect), selection highlight

### Phase 2: Enhancements
- `ConnectionAnnotation` (from_room_id, to_room_id, story_event_node_id)
- Placement modes: Place on Canvas (Pin), Draw on Canvas (Region)
- Drag-to-move (Pin/Region), drag-to-resize (Region)
- Filtering: text search, category dropdown, visibility filter
- Jump to Room, optional Link to Story Event Graph

### Phase 3: Polish
- Distinct icons, connection arrow styling, hover/selection feedback
- Undo/Redo integration, batch edit, copy/paste
- Default colors per category, persist panel layout
- View culling for large annotation counts
- Two-way Story Event Graph integration

---

## 2. Panel Layout

```
+-----------------------------------------------------------------------+
| Annotation Overlay ###                                                |
|-----------------------------------------------------------------------|
| [ Add New Annotation ]                                                |
| Filter: [ ___Text Search___ ] [ Category: All V ] [ Visible: All V ]  |
|-----------------------------------------------------------------------|
| ANNOTATIONS (Count: N)                                                |
| [Pin] R#12 (Bug) "Water gate here"                                    |
| [Region] R#05 (Todo) "Needs palette fix"                              |
| [Conn] R#01 -> R#02 (Design) "Story transition"                       |
|-----------------------------------------------------------------------|
| [ Link to Story Event Graph ]                                         |
+-----------------------------------------------------------------------+
```

- **List interactions:** Click → select + center view; Double-click → Edit; Right-click → context menu
- **Context menu:** Edit, Delete, Toggle Visibility, Jump to Room, Link to Story Event

### New/Edit Dialog

- Type: Pin | Region | Connection (radio)
- Common: Label, Category (Bug/Todo/Note/Design/Story), Color, Visible
- Pin: Room ID, Pos (X,Y) + "Place on Canvas"
- Region: Room ID, Pos, Size + "Draw on Canvas"
- Connection: From Room, To Room, Story Event Node ID (optional)

---

## 3. UX Flow

1. **Open:** Toolbar/View → Annotation Overlay
2. **Create:** Add New Annotation → choose type → fill fields → OK
3. **Edit:** Double-click (list/canvas) or context menu → Edit
4. **Move/Resize:** Drag on canvas (Pin/Region); drag corners for Region
5. **Delete:** Context menu → Delete → confirm
6. **Persistence:** Save ROM → serialize to `rom_name.annotations.json`; Load ROM → deserialize if sidecar exists
7. **Story integration:** Link annotation to Story Event node; jump between graph and dungeon view
