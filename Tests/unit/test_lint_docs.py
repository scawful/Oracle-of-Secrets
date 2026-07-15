from __future__ import annotations

import unittest

from Scripts.Analysis.lint_docs import LOWERCASE_TEST_ROOT_RE


class LintDocsTest(unittest.TestCase):
    def test_matches_repo_relative_lowercase_test_root(self) -> None:
        self.assertIsNotNone(
            LOWERCASE_TEST_ROOT_RE.search(
                "python3 Scripts/Validate/test_runner.py tests/smoke/lint_pass.json"
            )
        )

    def test_ignores_external_project_test_root(self) -> None:
        self.assertIsNone(
            LOWERCASE_TEST_ROOT_RE.search("cd z3dk && pytest z3dk/tests/test_mx.py")
        )


if __name__ == "__main__":
    unittest.main()
