# Dungeon Object Rendering State (2025-11-26)

This document outlines the current state of the dungeon object rendering system in `yaze` following recent changes aimed at addressing the emulator preview crash related to handler `$3479` and restoring manual drawing routines.

NOTE: Vanilla disassembly is external. In this workspace, JP gigaleak disassembly lives under `../alttp-gigaleak/DISASM/jpdasm/`. If you generate a US `usdasm` export for address parity, it lives under `../alttp-gigaleak/DISASM/usdasm/`. Adjust paths if your setup differs.

## 1. Manual Draw Routines Restoration

**Status**: **Completed**

The `DrawRightwards2x4_1to15or26` routine in `src/zelda3/dungeon/object_drawer.cc` has been reviewed and confirmed to be in its original, correct implementation state. No modifications were required as the existing code already matched the expected "original pattern" as described in the development plan.

## 2. Emulator Preview Crash Fix (via Manual Fallback)

**Status**: **Completed** (with a manual rendering fallback)

The emulator preview was experiencing a crash/timeout when attempting to render objects via handler `$3479`. While the root cause of the crash (missing WRAM state for the emulator) is still pending in-depth investigation (Phase 1.2 and Phase 2.1 of the plan), a workaround has been implemented:

*   **`ObjectRenderMode` Enum**: A new enum `ObjectRenderMode` has been introduced in `src/app/editor/dungeon/dungeon_canvas_viewer.h`. This enum allows explicit selection of the rendering method:
    *   `Manual`: Uses a simple, native C++ drawing approach.
    *   `Emulator`: Attempts to use the SNES emulator for object rendering.
    *   `Hybrid`: (Future) Placeholder for a mode combining both.
*   **Conditional Rendering**: The `Room::RenderObjectsToBackground()` function in `src/zelda3/dungeon/room.cc` now utilizes this `ObjectRenderMode`.
    *   When `ObjectRenderMode::Manual` is selected, objects are rendered by directly drawing colored rectangles to the bitmap buffer. This provides a visual representation of objects without engaging the potentially crashing emulator-based drawing handlers.
    *   When `ObjectRenderMode::Emulator` (default) or `Hybrid` is selected, the system attempts to use the `ObjectDrawer` (which relies on emulator logic) for rendering.

This implementation allows users to bypass the emulator crash by switching to `Manual` rendering mode, providing a functional preview while the emulator-specific issues are debugged.

## 3. Current Render Mode Integration

*   **`DungeonCanvasViewer`**: The `DungeonCanvasViewer` class (in `dungeon_canvas_viewer.h` and `dungeon_canvas_viewer.cc`) now manages the `ObjectRenderMode` and passes it down to the `Room::RenderRoomGraphics` method.
*   **`Room` Class**: The `Room` class (in `room.h` and `room.cc`) stores the `current_render_mode_` and uses it to decide whether to call `ObjectDrawer` or perform manual rendering within its `RenderObjectsToBackground` method.

## 4. Build Status

The `yaze` application has been successfully rebuilt with these changes. There were minor linker warnings regarding duplicate libraries, but the executable was generated.

## 5. Next Steps (from Plan - Short Term)

*   **Phase 1.2 - WRAM state research for handler $3479**: This involves a deep dive into the `usdasm` (US) or `jpdasm` (JP) disassembly to understand the WRAM variables expected by the problematic drawing handler.
*   **Phase 3 - Basic UI improvements**: Integrate the `ObjectRenderMode` toggle into the UI to allow users to switch between rendering modes.
*   **Phase 5.1-5.2 - Selection and movement**: Begin implementing core object manipulation features in the dungeon canvas.
