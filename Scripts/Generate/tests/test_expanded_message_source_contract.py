from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


GENERATE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = GENERATE_DIR.parents[1]
sys.path.insert(0, str(GENERATE_DIR))

from validate_expanded_message_source import (  # noqa: E402
    ASM_INCLUDE_PATH,
    BUNDLE_PATH,
    MESSAGE_COUNT,
    MESSAGE_WRAPPER_PATH,
    MessageSourceContractError,
    validate_contract,
)


class ExpandedMessageSourceContractTest(unittest.TestCase):
    def copy_contract(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for relative in (
            BUNDLE_PATH,
            ASM_INCLUDE_PATH,
            MESSAGE_WRAPPER_PATH,
        ):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / relative, destination)
        return temp, root

    def test_repository_contract_is_complete(self) -> None:
        contract = validate_contract(REPO_ROOT)

        self.assertEqual(contract.message_count, MESSAGE_COUNT)
        self.assertGreater(contract.data_size, MESSAGE_COUNT)
        self.assertEqual(len(contract.bundle_sha256), 64)

    def test_bundle_byte_drift_fails_hash_validation(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        bundle_path = root / BUNDLE_PATH
        bundle = json.loads(bundle_path.read_text(encoding="ascii"))
        bundle["messages"][0]["text"] += "!"
        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=True, indent=2, sort_keys=True)
            + "\n",
            encoding="ascii",
        )

        with self.assertRaisesRegex(
            MessageSourceContractError,
            "source hash does not match canonical bundle",
        ):
            validate_contract(root)

    def test_bundle_format_drift_fails_validation(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        bundle_path = root / BUNDLE_PATH
        bundle_path.write_bytes(bundle_path.read_bytes() + b" ")

        with self.assertRaisesRegex(
            MessageSourceContractError,
            "not in deterministic",
        ):
            validate_contract(root)

    def test_bundle_integer_fields_reject_json_numbers_with_fractional_type(
        self,
    ) -> None:
        for field in ("version", "id"):
            with self.subTest(field=field):
                temp, root = self.copy_contract()
                self.addCleanup(temp.cleanup)
                bundle_path = root / BUNDLE_PATH
                bundle = json.loads(bundle_path.read_text(encoding="ascii"))
                if field == "version":
                    bundle["version"] = 1.0
                else:
                    bundle["messages"][0]["id"] = 0.0
                bundle_path.write_text(
                    json.dumps(
                        bundle,
                        ensure_ascii=True,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="ascii",
                )

                with self.assertRaises(MessageSourceContractError):
                    validate_contract(root)

    def test_generated_include_cannot_set_its_own_org(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        include_path = root / ASM_INCLUDE_PATH
        include_path.write_text(
            include_path.read_text(encoding="utf-8").replace(
                "\nMessage_18D:\n",
                "\norg $2F8026\n\nMessage_18D:\n",
                1,
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            MessageSourceContractError,
            "must not contain an org directive",
        ):
            validate_contract(root)

    def test_generated_include_format_drift_fails_validation(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        include_path = root / ASM_INCLUDE_PATH
        include_path.write_text(
            include_path.read_text(encoding="utf-8").replace(
                "Message_18D:\n", "Message_18D:\n\n", 1
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            MessageSourceContractError,
            "body hash does not match",
        ):
            validate_contract(root)


if __name__ == "__main__":
    unittest.main()
