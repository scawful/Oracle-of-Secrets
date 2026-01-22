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

-   **`General/DevelopmentGuidelines.md`**: The primary guide for coding standards, architecture, and best practices. Start here to understand the project's philosophy.
-   **`Core/MemoryMap.md`**: A comprehensive map of custom WRAM and SRAM variables.
-   **`Tooling/AgentWorkflow.md`**: End-to-end workflow for Mesen2/YAZE/z3ed debugging and editing (includes expert-chain multi-step analysis).
-   **`Testing/SaveStateLibrary.md`**: How to maintain the save-state library for quick regression checks.
-   **`Guides/QuestFlow.md`**: A detailed walkthrough of the main story and side-quest progression.
-   **`Guides/SpriteCreationGuide.md`**: A tutorial for creating new custom sprites.
-   **`World/Overworld/ZSCustomOverworld.md`**: A deep dive into the data-driven overworld engine that powers the game world.
