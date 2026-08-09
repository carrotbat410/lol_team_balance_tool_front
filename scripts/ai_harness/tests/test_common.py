from __future__ import annotations

import os
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path

from scripts.ai_harness.common import (
    HarnessError,
    canonical_json_bytes,
    load_policy,
    prune_runtime,
    reject_forbidden_keys,
    sanitize_text,
    sanitize_value,
    validate_envelope,
    validate_runtime_policy,
)


BASE_COMMIT = "5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773"


def envelope() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "task_id": "ai-harness-test",
        "original_request": "Implement the approved harness.",
        "acceptance_criteria": ["Keep metadata only."],
        "repository": "lol_team_balance_tool_front2",
        "base_commit": BASE_COMMIT,
        "approved_scope": ["scripts/ai_harness"],
        "scope_paths": [".agents/**", ".github/workflows/ai-harness-check.yml", "scripts/ai_harness/**"],
        "constraints": ["standard library only"],
        "source_references": ["AGENTS.md"],
    }


class CommonSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy()

    def test_canonical_json_is_deterministic(self) -> None:
        self.assertEqual(canonical_json_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')

    def test_forbidden_keys_are_rejected_recursively(self) -> None:
        forbidden = self.policy["prompt_history"]["forbidden_keys"]
        for key in ("analysis", "reasoning", "chain_of_thought", "transcript", "messages", "tool_output", "command_output"):
            with self.subTest(key=key), self.assertRaises(HarnessError):
                reject_forbidden_keys({"safe": [{key: "must not persist"}]}, forbidden)

    def test_secret_and_pii_are_redacted(self) -> None:
        private_key = "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----"
        jwt = "eyJabcde.eyJfghij.signature123"
        original = (
            f"{private_key} jwt={jwt} token=plain-secret "
            "owner@example.com 010-1234-5678 /Users/alice/private/project"
        )
        sanitized, counts = sanitize_text(original)
        for sensitive in ("abc123", jwt, "plain-secret", "owner@example.com", "010-1234-5678", "/Users/alice"):
            self.assertNotIn(sensitive, sanitized)
        for label in ("private_key", "jwt", "secret_assignment", "email", "phone", "absolute_user_path"):
            self.assertGreaterEqual(counts[label], 1)

    def test_json_quoted_and_yaml_secret_forms_are_redacted(self) -> None:
        value = {
            "password": "hunter2",
            "nested": (
                '{"password" : "two words", "apiKey": "json-secret", "client_secret": \'client value\'}\n'
                "AWS_SECRET_ACCESS_KEY: aws value\n"
                "accessToken = 'quoted access value'\n"
                '"private_key" : "private value"\n'
                "secret: yaml-secret\n\'token\': \'quoted-secret\'"
            ),
        }
        sanitized, counts = sanitize_value(value)
        serialized = str(sanitized)
        for secret in (
            "hunter2",
            "two words",
            "json-secret",
            "client value",
            "aws value",
            "quoted access value",
            "private value",
            "yaml-secret",
            "quoted-secret",
        ):
            self.assertNotIn(secret, serialized)
        self.assertGreaterEqual(counts["secret_field"], 1)
        self.assertGreaterEqual(counts["secret_assignment"], 8)

    def test_runtime_policy_rejects_untrusted_paths_before_mutation(self) -> None:
        policy = load_policy()
        for key, value in (
            ("root", "/tmp/outside"),
            ("root", "../outside"),
            ("retention_days", -1),
            ("retention_targets", ["../../outside"]),
        ):
            with self.subTest(key=key, value=value):
                altered = copy.deepcopy(policy)
                altered["runtime"][key] = value
                with tempfile.TemporaryDirectory() as directory:
                    outside = Path(directory) / "outside.txt"
                    outside.write_text("unchanged")
                    before_mode = outside.stat().st_mode
                    with self.assertRaises(HarnessError):
                        validate_runtime_policy(altered, Path(directory) / "repository")
                    self.assertEqual(outside.read_text(), "unchanged")
                    self.assertEqual(outside.stat().st_mode, before_mode)

    def test_runtime_symlink_targets_are_rejected_before_prune(self) -> None:
        policy = load_policy()
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            outside = Path(outside_directory)
            old = outside / "old.json"
            old.write_text("unchanged")
            os.utime(old, (time.time() - 40 * 86400, time.time() - 40 * 86400))
            (root / ".ai-runtime").mkdir()
            (root / ".ai-runtime/logs").symlink_to(outside, target_is_directory=True)
            before_mode = outside.stat().st_mode
            with self.assertRaises(HarnessError):
                prune_runtime(root, policy)
            self.assertEqual(old.read_text(), "unchanged")
            self.assertEqual(outside.stat().st_mode, before_mode)

    def test_runtime_retention_expires_artifacts_but_preserves_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = load_policy()
            old_time = time.time() - 31 * 86400
            targets = ["logs/old.jsonl", "prompt-history/old.json", "reports/old.json", "reviewer-packets/old.json"]
            for relative in targets + ["state/hmac-salt"]:
                path = root / ".ai-runtime" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("old")
                os.utime(path, (old_time, old_time))
            removed = prune_runtime(root, policy, now=time.time())
            self.assertEqual(len(removed), len(targets))
            self.assertTrue((root / ".ai-runtime/state/hmac-salt").exists())

    def test_envelope_rejects_unknown_key(self) -> None:
        value = envelope()
        value["unapproved"] = "no"
        with self.assertRaises(HarnessError):
            validate_envelope(value, self.policy)


if __name__ == "__main__":
    unittest.main()
