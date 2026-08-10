from __future__ import annotations

import os
import copy
import json
import subprocess
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from scripts.ai_harness.common import (
    HarnessError,
    canonical_json_bytes,
    compute_task_diff_snapshot,
    compute_task_patch,
    load_policy,
    prune_runtime,
    reject_forbidden_keys,
    sanitize_text,
    sanitize_value,
    sha256_json,
    task_patch_from_snapshot,
    validate_envelope,
    validate_runtime_policy,
)
from scripts.ai_harness.workflow_attestation import (
    canonical_reviewer_packet,
    validate_changed_paths_in_scope,
)


BASE_COMMIT = "5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773"


def initialize_git_repository(root: Path, files: dict[str, bytes]) -> str:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    test_email = "test" + "@" + "example.invalid"
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=" + test_email,
            "commit",
            "-qm",
            "init",
        ],
        cwd=root,
        check=True,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def packet_verification(base_commit: str, task_diff_digest: str) -> list[dict[str, object]]:
    policy = load_policy()
    records = []
    for command_id in policy["verification"]["profiles"]["workflow"]:
        argv = [
            value.replace("{base_commit}", base_commit)
            for value in policy["verification"]["commands"][command_id]["argv"]
        ]
        argv_digest = sha256_json(argv)
        record = {
            "command_id": command_id,
            "argv_digest": argv_digest,
            "exit_status": 0,
            "result_digest": "",
            "base_commit": base_commit,
            "task_diff_digest": task_diff_digest,
        }
        record["result_digest"] = sha256_json(
            {
                "command_id": command_id,
                "argv_digest": argv_digest,
                "exit_status": 0,
                "base_commit": base_commit,
                "task_diff_digest": task_diff_digest,
            }
        )
        records.append(record)
    return records


def reviewer_manual_input() -> dict[str, object]:
    return {
        "original_request": "Review the approved harness changes.",
        "acceptance_criteria": ["All controls remain fail closed."],
        "review_rules": ["Report findings with source references."],
        "final_source_references": ["source.py"],
    }


@contextmanager
def packet_repository(*, changed_content: str = "changed\n"):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        source = root / "source.py"
        source.write_text("initial\n")
        subprocess.run(["git", "add", "source.py"], cwd=root, check=True)
        test_email = "test" + "@" + "example.invalid"
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=" + test_email,
                "commit",
                "-qm",
                "init",
            ],
            cwd=root,
            check=True,
        )
        base_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        source.write_text(changed_content)
        task_diff_digest = sha256_json(compute_task_diff_snapshot(root, base_commit))
        attestation = {
            "kind": "workflow",
            "base_commit": base_commit,
            "verification": packet_verification(base_commit, task_diff_digest),
        }
        yield root, base_commit, attestation


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

    def test_task_patch_is_deterministic_and_represents_all_text_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_commit = initialize_git_repository(
                root,
                {
                    "deleted.txt": b"delete me\n",
                    "mode.txt": b"same content\n",
                    "modified.txt": b"before\n",
                },
            )
            (root / "deleted.txt").unlink()
            os.chmod(root / "mode.txt", 0o755)
            (root / "modified.txt").write_text("after\n")
            (root / "untracked.txt").write_text("new file\n")

            first = compute_task_patch(root, base_commit)
            second = compute_task_patch(root, base_commit)
            snapshot = compute_task_diff_snapshot(root, base_commit)

            self.assertEqual(first, second)
            self.assertTrue(
                all(
                    set(change)
                    == {
                        "path",
                        "base_mode",
                        "base_object",
                        "current_mode",
                        "current_sha256",
                    }
                    for change in snapshot["changes"]
                )
            )
            self.assertIn("deleted file mode 100644", first)
            self.assertIn("old mode 100644\nnew mode 100755", first)
            self.assertIn("-before\n+after", first)
            self.assertIn("new file mode 100644", first)
            headers = [
                line for line in first.splitlines() if line.startswith("diff --git ")
            ]
            self.assertEqual(
                headers,
                [
                    "diff --git a/deleted.txt b/deleted.txt",
                    "diff --git a/mode.txt b/mode.txt",
                    "diff --git a/modified.txt b/modified.txt",
                    "diff --git a/untracked.txt b/untracked.txt",
                ],
            )
            with tempfile.TemporaryDirectory() as apply_directory:
                apply_root = Path(apply_directory) / "checkout"
                subprocess.run(
                    ["git", "clone", "-q", str(root), str(apply_root)],
                    check=True,
                )
                subprocess.run(
                    ["git", "apply", "--check", "-"],
                    cwd=apply_root,
                    input=first.encode("utf-8"),
                    check=True,
                )
                subprocess.run(
                    ["git", "apply", "-"],
                    cwd=apply_root,
                    input=first.encode("utf-8"),
                    check=True,
                )
                self.assertFalse((apply_root / "deleted.txt").exists())
                self.assertEqual((apply_root / "modified.txt").read_text(), "after\n")
                self.assertEqual((apply_root / "untracked.txt").read_text(), "new file\n")
                self.assertTrue((apply_root / "mode.txt").stat().st_mode & 0o100)

    def test_task_diff_and_patch_represent_gitlinks_without_checkout_recursion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git_email = "test" + "@" + "example.invalid"
            seed_commit = initialize_git_repository(root, {"seed.txt": b"seed\n"})
            for relative in ("modules/deleted", "modules/updated"):
                subprocess.run(
                    [
                        "git",
                        "update-index",
                        "--add",
                        "--cacheinfo",
                        f"160000,{seed_commit},{relative}",
                    ],
                    cwd=root,
                    check=True,
                )
            test_email = "test" + "@" + "example.invalid"
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=" + test_email,
                    "commit",
                    "-qm",
                    "gitlink base",
                ],
                cwd=root,
                check=True,
            )
            base_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            (root / "modules/deleted").mkdir(parents=True)
            (root / "modules/updated").mkdir(parents=True)
            subprocess.run(
                [
                    "git",
                    "update-index",
                    "--cacheinfo",
                    f"160000,{base_commit},modules/updated",
                ],
                cwd=root,
                check=True,
            )
            (root / "modules/deleted").rmdir()
            subprocess.run(
                [
                    "git",
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"160000,{base_commit},modules/added",
                ],
                cwd=root,
                check=True,
            )
            (root / "modules/added").mkdir(parents=True)

            self.assertFalse((root / "modules/deleted").exists())
            snapshot = compute_task_diff_snapshot(root, base_commit)
            patch = compute_task_patch(root, base_commit)
            self.assertEqual(patch, compute_task_patch(root, base_commit))
            self.assertEqual(list((root / "modules/updated").iterdir()), [])
            self.assertEqual(list((root / "modules/added").iterdir()), [])

            changes = {change["path"]: change for change in snapshot["changes"]}
            self.assertEqual(
                set(changes),
                {"modules/added", "modules/deleted", "modules/updated"},
            )
            self.assertEqual(changes["modules/added"]["current_mode"], "160000")
            self.assertEqual(changes["modules/added"]["current_object"], base_commit)
            self.assertIsNone(changes["modules/added"]["current_sha256"])
            self.assertEqual(changes["modules/deleted"]["base_mode"], "160000")
            self.assertEqual(changes["modules/deleted"]["base_object"], seed_commit)
            self.assertIsNone(changes["modules/deleted"]["current_mode"])
            self.assertEqual(changes["modules/updated"]["base_object"], seed_commit)
            self.assertEqual(changes["modules/updated"]["current_object"], base_commit)

            self.assertIn("new file mode 160000", patch)
            self.assertIn("deleted file mode 160000", patch)
            self.assertIn(f"index {seed_commit}..{base_commit} 160000", patch)
            self.assertIn(f"-Subproject commit {seed_commit}", patch)
            self.assertIn(f"+Subproject commit {base_commit}", patch)
            validate_changed_paths_in_scope(snapshot, ["modules/**"])
            with self.assertRaises(HarnessError):
                validate_changed_paths_in_scope(snapshot, ["modules/updated"])
            with tempfile.TemporaryDirectory() as apply_directory:
                apply_root = Path(apply_directory) / "checkout"
                subprocess.run(
                    ["git", "clone", "-q", str(root), str(apply_root)],
                    check=True,
                )
                subprocess.run(
                    ["git", "apply", "--check", "--index", "-"],
                    cwd=apply_root,
                    input=patch.encode("utf-8"),
                    check=True,
                )

    def test_task_diff_reads_gitlink_head_metadata_without_running_checkout_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            submodule = workspace / "submodule"
            superproject = workspace / "superproject"
            git_email = "test" + "@" + "example.invalid"
            submodule.mkdir()
            superproject.mkdir()
            first_commit = initialize_git_repository(submodule, {"version.txt": b"one\n"})
            (submodule / "version.txt").write_text("two\n")
            subprocess.run(["git", "add", "version.txt"], cwd=submodule, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    f"user.email={git_email}",
                    "commit",
                    "-qm",
                    "second",
                ],
                cwd=submodule,
                check=True,
            )
            second_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=submodule, text=True
            ).strip()
            initialize_git_repository(superproject, {"root.txt": b"root\n"})
            subprocess.run(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    "-q",
                    str(submodule),
                    "modules/live",
                ],
                cwd=superproject,
                check=True,
            )
            subprocess.run(
                ["git", "checkout", "-q", first_commit],
                cwd=superproject / "modules/live",
                check=True,
            )
            subprocess.run(
                ["git", "add", ".gitmodules", "modules/live"],
                cwd=superproject,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    f"user.email={git_email}",
                    "commit",
                    "-qm",
                    "gitlink base",
                ],
                cwd=superproject,
                check=True,
            )
            base_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=superproject, text=True
            ).strip()
            subprocess.run(
                ["git", "checkout", "-q", second_commit],
                cwd=superproject / "modules/live",
                check=True,
            )
            sentinel = workspace / "must-not-exist"
            executable = superproject / "modules/live/untrusted-code"
            executable.write_text(f"#!/bin/sh\ntouch {sentinel}\n")
            executable.chmod(0o755)

            snapshot = compute_task_diff_snapshot(superproject, base_commit)
            patch = compute_task_patch(superproject, base_commit)

            self.assertFalse(sentinel.exists())
            self.assertEqual(len(snapshot["changes"]), 1)
            change = snapshot["changes"][0]
            self.assertEqual(change["path"], "modules/live")
            self.assertEqual(change["base_mode"], "160000")
            self.assertEqual(change["base_object"], first_commit)
            self.assertEqual(change["current_mode"], "160000")
            self.assertEqual(change["current_object"], second_commit)
            self.assertIn(f"-Subproject commit {first_commit}", patch)
            self.assertIn(f"+Subproject commit {second_commit}", patch)

    def test_gitlink_to_tree_emits_link_deletion_and_regular_additions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git_email = "test" + "@" + "example.invalid"
            seed_commit = initialize_git_repository(root, {"seed.txt": b"seed\n"})
            subprocess.run(
                [
                    "git",
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"160000,{seed_commit},component",
                ],
                cwd=root,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    f"user.email={git_email}",
                    "commit",
                    "-qm",
                    "gitlink base",
                ],
                cwd=root,
                check=True,
            )
            base_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            subprocess.run(
                ["git", "update-index", "--force-remove", "component"],
                cwd=root,
                check=True,
            )
            (root / "component").mkdir()
            (root / "component/tracked.txt").write_text("tracked\n")
            subprocess.run(["git", "add", "component/tracked.txt"], cwd=root, check=True)
            (root / "component/untracked.txt").write_text("untracked\n")

            first_snapshot = compute_task_diff_snapshot(root, base_commit)
            second_snapshot = compute_task_diff_snapshot(root, base_commit)
            first_patch = compute_task_patch(root, base_commit)
            second_patch = compute_task_patch(root, base_commit)

            self.assertEqual(first_snapshot, second_snapshot)
            self.assertEqual(first_patch, second_patch)
            changes = {change["path"]: change for change in first_snapshot["changes"]}
            self.assertEqual(
                set(changes),
                {"component", "component/tracked.txt", "component/untracked.txt"},
            )
            self.assertEqual(changes["component"]["base_mode"], "160000")
            self.assertIsNone(changes["component"]["current_mode"])
            self.assertEqual(changes["component/tracked.txt"]["current_mode"], "100644")
            self.assertEqual(changes["component/untracked.txt"]["current_mode"], "100644")
            self.assertIn("deleted file mode 160000", first_patch)
            self.assertIn("diff --git a/component/tracked.txt b/component/tracked.txt", first_patch)
            self.assertIn("diff --git a/component/untracked.txt b/component/untracked.txt", first_patch)
            validate_changed_paths_in_scope(first_snapshot, ["component/**"])
            with tempfile.TemporaryDirectory() as apply_directory:
                apply_root = Path(apply_directory) / "checkout"
                subprocess.run(["git", "clone", "-q", str(root), str(apply_root)], check=True)
                subprocess.run(
                    ["git", "apply", "--check", "--index", "-"],
                    cwd=apply_root,
                    input=first_patch.encode("utf-8"),
                    check=True,
                )

    def test_tree_to_gitlink_deletes_base_descendants_without_reading_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_commit = initialize_git_repository(
                root,
                {
                    "modules/live/one.txt": b"one\n",
                    "modules/live/two.txt": b"two\n",
                },
            )
            subprocess.run(["git", "rm", "-qr", "modules/live"], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"160000,{base_commit},modules/live",
                ],
                cwd=root,
                check=True,
            )
            checkout = root / "modules/live"
            checkout.mkdir(parents=True)
            (checkout / "must-not-read.bin").write_bytes(b"\x00\xff\x01")

            first_snapshot = compute_task_diff_snapshot(root, base_commit)
            second_snapshot = compute_task_diff_snapshot(root, base_commit)
            first_patch = compute_task_patch(root, base_commit)
            second_patch = compute_task_patch(root, base_commit)

            self.assertEqual(first_snapshot, second_snapshot)
            self.assertEqual(first_patch, second_patch)
            changes = {change["path"]: change for change in first_snapshot["changes"]}
            self.assertEqual(
                set(changes),
                {"modules/live", "modules/live/one.txt", "modules/live/two.txt"},
            )
            self.assertEqual(changes["modules/live"]["current_mode"], "160000")
            self.assertEqual(changes["modules/live"]["current_object"], base_commit)
            self.assertIsNone(changes["modules/live/one.txt"]["current_mode"])
            self.assertIsNone(changes["modules/live/two.txt"]["current_mode"])
            self.assertNotIn("must-not-read", first_patch)
            self.assertIn("new file mode 160000", first_patch)
            self.assertIn("deleted file mode 100644", first_patch)
            validate_changed_paths_in_scope(first_snapshot, ["modules/live/**"])
            with tempfile.TemporaryDirectory() as apply_directory:
                apply_root = Path(apply_directory) / "checkout"
                subprocess.run(["git", "clone", "-q", str(root), str(apply_root)], check=True)
                subprocess.run(
                    ["git", "apply", "--check", "--index", "-"],
                    cwd=apply_root,
                    input=first_patch.encode("utf-8"),
                    check=True,
                )

    def test_task_patch_rejects_nul_non_utf8_and_binary_controls(self) -> None:
        for label, content in (
            ("nul", b"text\0tail"),
            ("non-utf8", b"text\xfftail"),
            ("binary-control", b"text\x01tail"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                base_commit = initialize_git_repository(root, {"changed.txt": b"initial\n"})
                (root / "changed.txt").write_bytes(content)
                with self.assertRaises(HarnessError):
                    compute_task_patch(root, base_commit)


class ReviewerPacketSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy()

    def test_packet_generates_patch_and_attested_verification(self) -> None:
        with packet_repository() as (root, base_commit, attestation):
            packet = canonical_reviewer_packet(
                reviewer_manual_input(),
                self.policy,
                root=root,
                base_commit=base_commit,
                attestation=attestation,
            )
            self.assertIn("diff --git a/source.py b/source.py", packet["task_patch"])
            self.assertEqual(
                packet["verification"],
                sorted(attestation["verification"], key=lambda item: item["command_id"]),
            )

    def test_packet_fails_closed_when_source_mutates_between_evidence_stages(self) -> None:
        with packet_repository() as (root, base_commit, attestation):
            source = root / "source.py"

            def mutate_then_render(snapshot_root: Path, snapshot: object) -> str:
                source.write_text("mutated during packet assembly\n")
                return task_patch_from_snapshot(snapshot_root, snapshot)

            with mock.patch(
                "scripts.ai_harness.workflow_attestation.task_patch_from_snapshot",
                side_effect=mutate_then_render,
            ), self.assertRaisesRegex(HarnessError, "source changed"):
                canonical_reviewer_packet(
                    reviewer_manual_input(),
                    self.policy,
                    root=root,
                    base_commit=base_commit,
                    attestation=attestation,
                )

    def test_packet_manual_prose_controls_are_rejected_but_lf_and_tab_are_allowed(self) -> None:
        with packet_repository() as (root, base_commit, attestation):
            for field, value in (
                ("original_request", "unsafe\x00request"),
                ("acceptance_criteria", ["unsafe\x1fcriterion"]),
                ("review_rules", ["unsafe\x85rule"]),
            ):
                with self.subTest(field=field):
                    raw = reviewer_manual_input()
                    raw[field] = value
                    with self.assertRaises(HarnessError):
                        canonical_reviewer_packet(
                            raw,
                            self.policy,
                            root=root,
                            base_commit=base_commit,
                            attestation=attestation,
                        )

            allowed = reviewer_manual_input()
            allowed["original_request"] = "line one\n\tline two"
            allowed["acceptance_criteria"] = ["criterion one\n\tcriterion two"]
            allowed["review_rules"] = ["rule one\n\trule two"]
            packet = canonical_reviewer_packet(
                allowed,
                self.policy,
                root=root,
                base_commit=base_commit,
                attestation=attestation,
            )
            self.assertEqual(packet["original_request"], allowed["original_request"])

    def test_packet_source_reference_rejects_all_controls(self) -> None:
        with packet_repository() as (root, base_commit, attestation):
            for control in ("\x00", "\t", "\n", "\x7f", "\x80"):
                with self.subTest(control=ord(control)):
                    raw = reviewer_manual_input()
                    raw["final_source_references"] = [f"source.py{control}"]
                    with self.assertRaises(HarnessError):
                        canonical_reviewer_packet(
                            raw,
                            self.policy,
                            root=root,
                            base_commit=base_commit,
                            attestation=attestation,
                        )

    def test_packet_rejects_caller_supplied_generated_fields(self) -> None:
        with packet_repository() as (root, base_commit, attestation):
            for field, value in (
                ("task_diff", {}),
                ("task_patch", "forged"),
                ("verification", []),
            ):
                with self.subTest(field=field):
                    raw = reviewer_manual_input()
                    raw[field] = value
                    with self.assertRaises(HarnessError):
                        canonical_reviewer_packet(
                            raw,
                            self.policy,
                            root=root,
                            base_commit=base_commit,
                            attestation=attestation,
                        )

    def test_reviewer_stage_rejects_generated_evidence_tampering(self) -> None:
        with packet_repository() as (root, base_commit, attestation):
            packet = canonical_reviewer_packet(
                reviewer_manual_input(),
                self.policy,
                root=root,
                base_commit=base_commit,
                attestation=attestation,
            )
            for field, value in (
                ("task_diff", {"base_commit": base_commit, "changes": []}),
                ("task_patch", packet["task_patch"] + "tampered\n"),
                ("verification", packet["verification"][:-1]),
            ):
                with self.subTest(field=field):
                    altered = copy.deepcopy(packet)
                    altered[field] = value
                    with self.assertRaises(HarnessError):
                        canonical_reviewer_packet(
                            altered,
                            self.policy,
                            root=root,
                            base_commit=base_commit,
                            attestation=attestation,
                            allow_generated_fields=True,
                        )

    def test_packet_rejects_incomplete_attested_verification(self) -> None:
        with packet_repository() as (root, base_commit, attestation):
            attestation["verification"] = attestation["verification"][:-1]
            with self.assertRaises(HarnessError):
                canonical_reviewer_packet(
                    reviewer_manual_input(),
                    self.policy,
                    root=root,
                    base_commit=base_commit,
                    attestation=attestation,
                )

    def test_packet_rejects_secret_in_generated_patch(self) -> None:
        changed_content = "api_" + 'key = "' + "sensitive-" + 'value"\n'
        with packet_repository(changed_content=changed_content) as (root, base_commit, attestation):
            with self.assertRaises(HarnessError):
                canonical_reviewer_packet(
                    reviewer_manual_input(),
                    self.policy,
                    root=root,
                    base_commit=base_commit,
                    attestation=attestation,
                )

    def test_packet_rejects_payload_over_two_mib(self) -> None:
        with packet_repository() as (root, base_commit, attestation):
            raw = reviewer_manual_input()
            raw["original_request"] = "x" * (2 * 1024 * 1024)
            with self.assertRaises(HarnessError):
                canonical_reviewer_packet(
                    raw,
                    self.policy,
                    root=root,
                    base_commit=base_commit,
                    attestation=attestation,
                )


if __name__ == "__main__":
    unittest.main()
