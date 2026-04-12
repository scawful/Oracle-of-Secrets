# Oracle of Secrets Documentation

Welcome to the documentation for Oracle of Secrets. This directory is organized to help you find information about the project's architecture, systems, and content.

## Directory Structure

-   `./Debugging/`: Emulator/debugging workflows, testing infrastructure, state libraries, and agent-oriented guides.
-   `./Planning/`: Roadmaps, audits, inventories, and design/planning docs (includes status/handoffs).
-   `./Technical/`: Source-of-truth-ish references (memory maps, architecture notes, technical reference, sheets).
-   `./World/`: Game/content docs (world layout, dungeons/overworld, lore, sprites, features, guides, design).
-   `./Archive/`: Historical docs (not current guidance).

## Key Documents

-   **`../RUNBOOK.md`**: Primary “how do I work on this repo” doc (build → launch → preflight → capture).
-   **`Debugging/README.md`**: Debugging/testing index inside Docs.
-   **`Planning/README.md`**: Planning index (story/design, audits, inventories, status/handoffs).
-   **`Debugging/Agent/Quickstart.md`**: One-page agent entry (build → preflight → capture → debug).
-   **`Technical/MemoryMap.md`**: Comprehensive WRAM/SRAM map.
-   **`World/Guides/QuestFlow.md`**: A walkthrough of the main story and side-quest progression.
-   **`World/Overworld/ZSCustomOverworld.md`**: Overworld engine deep dive.

## Debugging & Testing Quick Start

```bash
# Build + symbol sync + optional reset
Scripts/Build/dev_loop.sh 168 --mesen-sync --reload

# Or compatibility wrapper
./build.sh 168

# Run regression test suite
./Scripts/Validate/run_regression_tests.sh regression

# Launch isolated Mesen2 + attach by instance
./Scripts/Mesen2/mesen2_launch_instance.sh --instance oos-you-debug --owner you --source manual
python3 Scripts/Mesen2/mesen2_client.py --instance oos-you-debug diagnostics
```
