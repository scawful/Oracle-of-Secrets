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
# Build + overlap check
mesen-agent build
python3 scripts/check_zscream_overlap.py

# Run regression test suite
./scripts/run_regression_tests.sh regression

# Socket API client (preferred)
MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py diagnostics
```
