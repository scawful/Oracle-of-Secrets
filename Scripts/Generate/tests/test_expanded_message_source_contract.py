from __future__ import annotations

import hashlib
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
    MESSAGE_DATA_END,
    MESSAGE_DATA_START,
    MESSAGE_COUNT,
    MESSAGE_WRAPPER_PATH,
    PROGRESSION_DATA_START,
    PROGRESSION_PATH,
    MessageSourceContractError,
    _encode_bundle_messages,
    _encode_message_text,
    _render_asm_include,
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
            PROGRESSION_PATH,
        ):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / relative, destination)
        return temp, root

    def write_bundle_and_include(
        self, root: Path, bundle: dict[str, object]
    ) -> None:
        bundle_bytes = (
            json.dumps(bundle, ensure_ascii=True, indent=2, sort_keys=True)
            + "\n"
        ).encode("ascii")
        (root / BUNDLE_PATH).write_bytes(bundle_bytes)
        bundle_hash = hashlib.sha256(bundle_bytes).hexdigest()
        (root / ASM_INCLUDE_PATH).write_text(
            _render_asm_include(
                _encode_bundle_messages(bundle),
                bundle_hash,
            ),
            encoding="utf-8",
        )

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

    def test_updated_source_hash_cannot_hide_stale_generated_body(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        bundle_path = root / BUNDLE_PATH
        bundle = json.loads(bundle_path.read_text(encoding="ascii"))
        bundle["messages"][0]["text"] += "!"
        bundle_bytes = (
            json.dumps(bundle, ensure_ascii=True, indent=2, sort_keys=True)
            + "\n"
        ).encode("ascii")
        bundle_path.write_bytes(bundle_bytes)

        include_path = root / ASM_INCLUDE_PATH
        include_lines = include_path.read_text(encoding="utf-8").splitlines()
        include_lines[0] = (
            "; Source bundle SHA-256: "
            f"{hashlib.sha256(bundle_bytes).hexdigest()}"
        )
        include_path.write_text(
            "\n".join(include_lines) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            MessageSourceContractError,
            "does not encode the canonical bundle",
        ):
            validate_contract(root)

    def test_empty_message_round_trips_as_terminator(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        bundle = json.loads(
            (root / BUNDLE_PATH).read_text(encoding="ascii")
        )
        bundle["messages"][0]["text"] = ""
        self.write_bundle_and_include(root, bundle)

        contract = validate_contract(root)

        self.assertEqual(contract.message_count, MESSAGE_COUNT)

    def test_command_arguments_may_equal_terminator_bytes(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        bundle = json.loads(
            (root / BUNDLE_PATH).read_text(encoding="ascii")
        )
        bundle["messages"][0]["text"] = "[W:7F][W:FF]"
        self.write_bundle_and_include(root, bundle)

        contract = validate_contract(root)

        self.assertEqual(contract.message_count, MESSAGE_COUNT)

    def test_command_argument_grammar_matches_source_sync(self) -> None:
        self.assertEqual(
            _encode_message_text("[W:7][W:07]", 0),
            bytes((0x6B, 0x07, 0x6B, 0x07, 0x7F)),
        )
        for text in (
            "[W]",
            "[W:]",
            "[W:ff]",
            "[w:FF]",
            "[W:$7F]",
            "[BANK]",
        ):
            with self.subTest(text=text):
                with self.assertRaises(MessageSourceContractError):
                    _encode_message_text(text, 0)

    def test_expanded_message_allocation_overflow_fails(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        bundle = json.loads(
            (root / BUNDLE_PATH).read_text(encoding="ascii")
        )
        capacity = MESSAGE_DATA_END - MESSAGE_DATA_START + 1
        bundle["messages"][0]["text"] = " " * capacity
        self.write_bundle_and_include(root, bundle)

        with self.assertRaisesRegex(
            MessageSourceContractError,
            "exceeds fixed allocation",
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

    def test_generated_include_crlf_fails_exact_byte_validation(self) -> None:
        temp, root = self.copy_contract()
        self.addCleanup(temp.cleanup)
        include_path = root / ASM_INCLUDE_PATH
        include_path.write_bytes(
            include_path.read_bytes().replace(b"\n", b"\r\n")
        )

        with self.assertRaises(MessageSourceContractError):
            validate_contract(root)

    def test_message_and_progression_allocations_are_disjoint(self) -> None:
        self.assertEqual(MESSAGE_DATA_END + 1, PROGRESSION_DATA_START)
        validate_contract(REPO_ROOT)

    def test_exact_byte_artifacts_force_lf_checkout(self) -> None:
        attributes = (REPO_ROOT / ".gitattributes").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Data/dialogue/expanded_messages.json text eol=lf",
            attributes.splitlines(),
        )
        self.assertIn(
            "Core/Generated/expanded_messages.asm text eol=lf",
            attributes.splitlines(),
        )
        self.assertNotIn(b"\r\n", (REPO_ROOT / BUNDLE_PATH).read_bytes())
        self.assertNotIn(b"\r\n", (REPO_ROOT / ASM_INCLUDE_PATH).read_bytes())


if __name__ == "__main__":
    unittest.main()
