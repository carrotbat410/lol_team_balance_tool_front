from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from scripts.ai_harness.common import HarnessError, load_policy
from scripts.ai_harness.hook_logger import append_log_record, build_log_record


class HookLoggerTests(unittest.TestCase):
    def test_logger_builds_a_new_allowlisted_object(self) -> None:
        payload = {
            "session_id": "raw-session-id",
            "turn_id": "raw-turn-id",
            "hook_event_name": "UserPromptSubmit",
            "prompt": "token=secret owner@example.com /Users/alice/project",
            "transcript_path": "/Users/alice/transcript.jsonl",
            "tool_output": "must not persist",
        }
        record = build_log_record(
            payload,
            salt=b"s" * 32,
            timestamp="2026-01-01T00:00:00Z",
            commit="5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773",
        )
        self.assertEqual(set(record), set(load_policy()["hook"]["allowed_log_fields"]))
        serialized = json.dumps(record)
        for sensitive in ("raw-session-id", "raw-turn-id", "secret", "owner@example.com", "/Users/alice", "tool_output"):
            self.assertNotIn(sensitive, serialized)
        self.assertEqual(record["event"], "UserPromptSubmit")

    def test_subagent_role_is_normalized_without_payload_body(self) -> None:
        record = build_log_record(
            {
                "session_id": "session",
                "turn_id": "turn",
                "hook_event_name": "SubagentStop",
                "agent_type": "reviewer",
                "last_assistant_message": "private response",
            },
            salt=b"s" * 32,
            timestamp="2026-01-01T00:00:00Z",
            commit="5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773",
        )
        self.assertEqual((record["role"], record["stage"], record["status"]), ("Reviewer", "reviewer", "completed"))
        self.assertNotIn("private response", json.dumps(record))

    def test_runtime_log_uses_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".agents/ai-harness").mkdir(parents=True)
            shutil.copy2(".agents/ai-harness/policy.json", root / ".agents/ai-harness/policy.json")
            record = {
                "schema_version": "1.0",
                "timestamp": "2026-01-01T00:00:00Z",
                "run_id": "a" * 24,
                "turn_id": "b" * 24,
                "event": "Stop",
                "role": "Coordinator",
                "stage": "finalize",
                "status": "stopped",
                "git_commit": "c" * 40,
                "policy_digest": "d" * 64,
                "template_manifest_digest": "e" * 64,
                "verification_exit_status": 0,
            }
            path = append_log_record(record, root=root)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_hook_rejects_symlinked_runtime_before_external_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            outside = Path(outside_directory)
            (root / ".agents/ai-harness").mkdir(parents=True)
            shutil.copy2(".agents/ai-harness/policy.json", root / ".agents/ai-harness/policy.json")
            protected = outside / "protected.jsonl"
            protected.write_text("unchanged")
            before_mode = protected.stat().st_mode
            (root / ".ai-runtime").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(HarnessError):
                build_log_record(
                    {"session_id": "session", "hook_event_name": "Stop"},
                    root=root,
                    salt=b"s" * 32,
                    commit="c" * 40,
                )
            self.assertEqual(protected.read_text(), "unchanged")
            self.assertEqual(protected.stat().st_mode, before_mode)


if __name__ == "__main__":
    unittest.main()
