from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from Scripts.Analysis.extract_story_events import extract_events


class ExtractStoryEventsTest(unittest.TestCase):
    def test_only_parses_canonical_event_index(self) -> None:
        document = """# Story Event Graph

## Event Index

| Event ID | Event Name | Flags Set/Cleared | Locations/Rooms | Scripts/Routines | Text IDs | Evidence | Last Verified | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | Intro | GameState=1 | Loom Beach | StartIntro | 0x1F | intro.asm | 2026-01-01 | Canonical row |

## Tracing Status

| Event | Setter File | Key Line | Verified | Extra | Extra | Extra | Extra | Extra |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | duplicate.asm | line 10 | Code | duplicate | duplicate | duplicate | duplicate | duplicate |
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "Docs" / "Planning" / "Story_Event_Graph.md"
            source.parent.mkdir(parents=True)
            source.write_text(document, encoding="utf-8")

            events = extract_events(root)

        self.assertEqual([event["id"] for event in events], ["EV-001"])
        self.assertEqual(events[0]["name"], "Intro")


if __name__ == "__main__":
    unittest.main()
