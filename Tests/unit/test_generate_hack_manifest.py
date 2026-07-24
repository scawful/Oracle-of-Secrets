from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "Scripts" / "Generate"))

from generate_hack_manifest import generate_manifest


class HackManifestMessagePolicyTest(unittest.TestCase):
    def test_expanded_messages_require_asm_rebuild_workflow(self) -> None:
        generated_messages = generate_manifest(REPO_ROOT)["messages"]
        tracked_messages = json.loads(
            (REPO_ROOT / "Roms" / "hack_manifest.json").read_text(encoding="utf-8")
        )["messages"]

        self.assertEqual(generated_messages, tracked_messages)

        guidance = generated_messages["editing_guidance"]["expanded_asm_owned"]
        self.assertIn("ASM-owned bank $2F", guidance)
        self.assertIn("Core/message.asm", guidance)
        self.assertIn("Scripts/Build/build_rom.sh 168", guidance)
        self.assertIn("reopen or reload", guidance)

        policy_text = json.dumps(generated_messages)
        self.assertNotIn("message-write", policy_text)
        self.assertNotIn("z3ed", policy_text)


if __name__ == "__main__":
    unittest.main()
