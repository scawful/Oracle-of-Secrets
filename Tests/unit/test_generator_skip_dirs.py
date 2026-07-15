from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "Scripts" / "Generate"))

from Scripts.Build.verify_feature_flags import _should_skip as skip_feature_flags
from Scripts.Generate.generate_hack_manifest import _should_skip as skip_manifest
from Scripts.Generate.generate_hooks_json import _should_skip as skip_hooks
from Scripts.Generate.tag_org_hooks import _should_skip as skip_tagging


class GeneratorSkipDirsTest(unittest.TestCase):
    def test_all_generators_skip_canonical_tests_root(self) -> None:
        fixture = Path("Tests") / "fixtures" / "synthetic_hook.asm"

        for should_skip in (skip_feature_flags, skip_manifest, skip_hooks, skip_tagging):
            with self.subTest(should_skip=should_skip.__module__):
                self.assertTrue(should_skip(fixture))


if __name__ == "__main__":
    unittest.main()
