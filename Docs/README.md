# Oracle of Secrets Documentation

Welcome to the documentation for Oracle of Secrets. This directory is organized to help you find information about the project's architecture, systems, and content.

## Directory Structure

-   `./General/`: High-level project information, including development guidelines and build instructions.
-   `./Core/`: Documentation for the core engine components, such as memory maps, the player engine (`Link.md`), and system interaction analysis.
-   `./Features/`: Detailed analysis of major gameplay features.
    -   `./Features/Items/`: Information on custom and modified items.
    -   `./Features/Masks/`: Details on the mask transformation system.
    -   `./Features/Menu/`: Analysis of the custom menu and HUD.
    -   `./Features/Music/`: Guide to the music system and composition workflow.
-   `./World/`: Information about the game world's construction.
    -   `./World/Overworld/`: Documentation for the overworld engine, including `ZSCustomOverworld` and the time system.
    -   `./World/Dungeons/`: Details on dungeon mechanics and custom features.
-   `./Sprites/`: Analysis of all sprite types, including bosses, NPCs, and interactive objects.
-   `./Tooling/`: Debugging, automation, and emulator integration workflows.
-   `./Guides/`: Step-by-step guides and tutorials, such as the sprite creation guide and the main quest flowchart.

## Key Documents

-   **`Agent/Quickstart.md`**: One-page agent entry (build → preflight → capture → debug).
-   **`General/DevelopmentGuidelines.md`**: Coding standards, architecture, and philosophy.
-   **`Core/MemoryMap.md`**: Comprehensive WRAM/SRAM map.
-   **`Tooling/AgentWorkflow.md`**: Extended workflow details when Quickstart is insufficient.
-   **`Tooling/Oracle_Debugger_Package.md`**: Unified debugging orchestrator (NEW 2026-01).
-   **`Tooling/Root_Cause_Debugging_Workflow.md`**: Six-phase root-cause debugging workflow (Reproduce → Capture → Instrument → Isolate → Map → Document) and tool inventory.
-   **`Tooling/Debugging_Tools_Index.md`**: Comprehensive reference for all debugging tools.
-   **`Testing/README.md`**: Testing infrastructure (suites, tags, module isolation, bisect).
-   **`Testing/SaveStateLibrary.md`**: How to maintain the save-state library for quick regression checks.
-   **`Guides/QuestFlow.md`**: A detailed walkthrough of the main story and side-quest progression.
-   **`Guides/SpriteCreationGuide.md`**: A tutorial for creating new custom sprites.
-   **`World/Overworld/ZSCustomOverworld.md`**: A deep dive into the data-driven overworld engine that powers the game world.

## Debugging & Testing Quick Start

```bash
# Build with automatic smoke tests
./scripts/build_rom.sh 168

# Run regression test suite
./scripts/run_regression_tests.sh regression

# Start unified debugging orchestrator
python3 scripts/oracle_debugger/orchestrator.py --monitor
```
