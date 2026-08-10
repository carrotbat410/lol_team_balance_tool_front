from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.ai_harness.common import HarnessError
from scripts.ai_harness.prompt_history import build_record, verify_record
from scripts.ai_harness.tests.test_common import envelope


class PromptHistoryTests(unittest.TestCase):
    def test_record_sanitizes_and_verifies_all_digests(self) -> None:
        value = envelope()
        value["original_request"] = "Contact owner@example.com and use token=do-not-store at /Users/alice/repo"
        record = build_record(value, "researcher", created_at="2026-01-01T00:00:00Z", salt=b"s" * 32)
        serialized = str(record)
        self.assertNotIn("owner@example.com", serialized)
        self.assertNotIn("do-not-store", serialized)
        self.assertNotIn("/Users/alice", serialized)
        self.assertGreater(record["redactions"]["email"], 0)
        result = verify_record(record)
        self.assertEqual(result["rendered_prompt_sha256"], record["rendered_prompt_sha256"])

    def test_digest_tampering_is_rejected(self) -> None:
        record = build_record(envelope(), "planner", created_at="2026-01-01T00:00:00Z", salt=b"s" * 32)
        tampered = copy.deepcopy(record)
        tampered["rendered_prompt_sha256"] = "0" * 64
        with self.assertRaises(HarnessError):
            verify_record(tampered)

    def test_forbidden_prompt_history_key_is_rejected(self) -> None:
        value = envelope()
        value["analysis"] = "hidden reasoning"
        with self.assertRaises(HarnessError):
            build_record(value, "implementer", salt=b"s" * 32)

    def test_manual_text_controls_are_rejected_before_prompt_record_storage(self) -> None:
        secret_assignment = "token" + "=secret" + "\x00value"
        for field, value in (
            ("original_request", "unsafe\x00request"),
            ("original_request", secret_assignment),
            ("acceptance_criteria", ["unsafe\x1fcriterion"]),
            ("acceptance_criteria", ["unsafe\x85criterion"]),
            ("source_references", ["AGENTS.md\n"]),
            ("source_references", ["AGENTS.md\t"]),
        ):
            with self.subTest(field=field, value=value):
                candidate = envelope()
                candidate[field] = value
                with self.assertRaises(HarnessError):
                    build_record(candidate, "implementer", salt=b"s" * 32)

    def test_prompt_prose_allows_line_feed_and_tab(self) -> None:
        value = envelope()
        value["original_request"] = "line one\n\tline two"
        value["acceptance_criteria"] = ["criterion one\n\tcriterion two"]
        record = build_record(value, "implementer", salt=b"s" * 32)
        self.assertEqual(record["envelope"]["original_request"], value["original_request"])

    def test_role_templates_produce_distinct_context_digests(self) -> None:
        digests = {
            build_record(envelope(), role, created_at="2026-01-01T00:00:00Z", salt=b"s" * 32)[
                "rendered_prompt_sha256"
            ]
            for role in ("researcher", "planner", "implementer", "reviewer")
        }
        self.assertEqual(len(digests), 4)

    def test_contract_change_invalidates_prompt_reproduction_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(".agents", root / ".agents")
            shutil.copytree(".codex/agents", root / ".codex/agents")
            record = build_record(
                envelope(),
                "reviewer",
                root=root,
                created_at="2026-01-01T00:00:00Z",
                salt=b"s" * 32,
            )
            contract = root / ".codex/agents/reviewer.toml"
            contract.write_text(contract.read_text() + "\n# changed\n")
            with self.assertRaises(HarnessError):
                verify_record(record, root=root)


if __name__ == "__main__":
    unittest.main()
