from __future__ import annotations

import argparse
import copy
import hashlib
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.ai_harness.common import (
    INTEGRITY_MANIFEST_PATH,
    POLICY_PATH,
    PROMPT_MANIFEST_PATH,
    HarnessError,
    atomic_write_json,
    compute_task_diff_digest,
    load_policy,
    compute_task_diff_snapshot,
    read_json,
    sha256_file,
    sha256_json,
    validate_bootstrap_changed_paths,
)
from scripts.ai_harness.workflow_attestation import (
    build_parser,
    canonical_reviewer_packet,
    command_finalize,
    command_init,
    command_prepare_reviewer_packet,
    command_run_verification,
    command_stage,
    rerun_verification,
    run_verification_command,
    validate_changed_paths_in_scope,
    validate_attestation,
    validate_event_sequence,
    validate_policy_constants,
    write_attestation,
)


BASE_COMMIT = "5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def packet_metadata(task_diff_digest: str) -> dict[str, object]:
    policy = load_policy()
    records = verification("workflow", task_diff_digest)
    fields = {
        key: f"sha256:{task_diff_digest if key == 'task_diff' else sha256_json(records) if key == 'verification' else digest(key)}"
        for key in sorted(policy["workflow"]["reviewer_packet_allowed_fields"])
    }
    return {
        "field_digests": fields,
        "packet_digest": digest("packet"),
        "task_diff_digest": task_diff_digest,
    }


def event(
    sequence: int,
    stage: str,
    status: str,
    context: str,
    scope: str | None,
    round_number: int,
    *,
    scope_paths: str | None = None,
    prompt_scope: str | None = None,
    task_diff: str | None = None,
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "stage": stage,
        "status": status,
        "context_digest": context,
        "scope_digest": scope,
        "scope_paths_digest": scope_paths,
        "prompt_scope_digest": prompt_scope,
        "task_diff_digest": task_diff,
        "round": round_number,
    }


def verification(
    kind: str, task_diff_digest: str, *, base_commit: str = BASE_COMMIT
) -> list[dict[str, object]]:
    policy = load_policy()
    records = []
    for command_id in policy["verification"]["profiles"][kind]:
        argv = [
            value.replace("{base_commit}", base_commit)
            for value in policy["verification"]["commands"][command_id]["argv"]
        ]
        records.append(
            {
                "command_id": command_id,
                "argv_digest": sha256_json(argv),
                "exit_status": 0,
                "result_digest": sha256_json(
                    {
                        "command_id": command_id,
                        "argv_digest": sha256_json(argv),
                        "exit_status": 0,
                        "base_commit": base_commit,
                        "task_diff_digest": task_diff_digest,
                    }
                ),
                "base_commit": base_commit,
                "task_diff_digest": task_diff_digest,
            }
        )
    return records


def valid_workflow() -> dict[str, object]:
    scope = digest("scope")
    scope_paths = ["scripts/ai_harness/**"]
    scope_paths_digest = sha256_json(scope_paths)
    task_diff = digest("diff")
    packet = packet_metadata(task_diff)
    return {
        "schema_version": "1.0",
        "kind": "workflow",
        "attestation_id": "a" * 24,
        "base_commit": BASE_COMMIT,
        "task_id": "b" * 24,
        "task_diff_digest": task_diff,
        "policy_digest": sha256_file(POLICY_PATH),
        "prompt_manifest_digest": sha256_file(PROMPT_MANIFEST_PATH),
        "integrity_manifest_digest": sha256_file(INTEGRITY_MANIFEST_PATH),
        "approved_scope_digest": scope,
        "approved_scope_paths": scope_paths,
        "approved_scope_paths_digest": scope_paths_digest,
        "events": [
            event(1, "researcher", "completed", digest("researcher"), None, 0),
            event(2, "planner", "completed", digest("planner"), None, 0),
            event(3, "human_approval", "approved", scope, scope, 0, scope_paths=scope_paths_digest),
            event(
                4,
                "implementer",
                "completed",
                digest("implementer"),
                scope,
                0,
                scope_paths=scope_paths_digest,
                prompt_scope=scope,
            ),
            event(
                5,
                "reviewer",
                "approved",
                packet["packet_digest"],
                scope,
                0,
                scope_paths=scope_paths_digest,
                task_diff=task_diff,
            ),
        ],
        "reviewer_packet": packet,
        "prepared_reviewer_packet_digest": None,
        "verification": verification("workflow", task_diff),
        "bootstrap": None,
    }


def reviewer_packet_input(*, include_task_diff: bool) -> dict[str, object]:
    packet: dict[str, object] = {
        "original_request": "Review the approved AI harness changes.",
        "acceptance_criteria": ["All controls remain fail closed."],
        "review_rules": ["Report findings with repository source references."],
        "final_source_references": ["scripts/ai_harness/workflow_attestation.py:canonical_reviewer_packet"],
        "verification": [{"command_id": "git_diff_check", "status": "passed"}],
    }
    if include_task_diff:
        packet["task_diff"] = compute_task_diff_snapshot(Path.cwd(), BASE_COMMIT)
    return packet


def initialize_source_repository(root: Path) -> str:
    git_email = "test" + "@" + "example.invalid"
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "source.py").write_text("initial\n")
    subprocess.run(["git", "add", "source.py"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            f"user.email={git_email}",
            "commit",
            "-qm",
            "init",
        ],
        cwd=root,
        check=True,
    )
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def initialize_command_repository(root: Path) -> tuple[str, str, dict[str, str], Path]:
    for relative in (POLICY_PATH, PROMPT_MANIFEST_PATH, INTEGRITY_MANIFEST_PATH):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(relative).read_bytes())
    smoke_test = root / "scripts/ai_harness/tests/test_smoke.py"
    smoke_test.parent.mkdir(parents=True, exist_ok=True)
    smoke_test.write_text("import unittest\n\nclass SmokeTest(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n")
    (root / "source.py").write_text("initial\n")
    (root / ".gitignore").write_text("/.ai-runtime/\n__pycache__/\n*.pyc\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
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
    base_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    attestation_file = ".agents/ai-harness/attestations/task.json"
    (root / ".agents/ai-harness/attestations").mkdir()
    with redirect_stdout(io.StringIO()):
        command_init(
            argparse.Namespace(
                root=str(root),
                task_id="repository-digest-refresh",
                base=base_commit,
                output=attestation_file,
            )
        )

    attestation_path = root / attestation_file
    attestation = read_json(attestation_path)
    initial_digests = {
        key: attestation[key]
        for key in ("policy_digest", "prompt_manifest_digest", "integrity_manifest_digest")
    }
    approved_scope = ["Harness evidence changes"]
    scope_paths = [
        ".agents/ai-harness/**",
        ".agents/prompts/manifest.json",
        "source.py",
    ]
    scope_digest = sha256_json(
        {"approved_scope": approved_scope, "scope_paths": scope_paths}
    )
    scope_paths_digest = sha256_json(scope_paths)
    attestation["approved_scope_digest"] = scope_digest
    attestation["approved_scope_paths"] = scope_paths
    attestation["approved_scope_paths_digest"] = scope_paths_digest
    attestation["events"] = [
        event(1, "researcher", "completed", digest("command-researcher"), None, 0),
        event(2, "planner", "completed", digest("command-planner"), None, 0),
        event(
            3,
            "human_approval",
            "approved",
            scope_digest,
            scope_digest,
            0,
            scope_paths=scope_paths_digest,
        ),
        event(
            4,
            "implementer",
            "completed",
            digest("command-implementer"),
            scope_digest,
            0,
            scope_paths=scope_paths_digest,
            prompt_scope=scope_digest,
        ),
    ]
    atomic_write_json(attestation_path, attestation, private=False)

    policy = read_json(root / POLICY_PATH)
    atomic_write_json(root / POLICY_PATH, policy, private=False)
    integrity = read_json(root / INTEGRITY_MANIFEST_PATH)
    integrity["files"][POLICY_PATH.as_posix()] = sha256_file(root / POLICY_PATH)
    atomic_write_json(root / INTEGRITY_MANIFEST_PATH, integrity, private=False)
    (root / "source.py").write_text("changed\n")

    packet_input = root / ".ai-runtime/reviewer-input.json"
    atomic_write_json(
        packet_input,
        {
            "original_request": "Review the approved harness changes.",
            "acceptance_criteria": ["Repository digests come from current files."],
            "review_rules": ["Report findings with source references."],
            "final_source_references": ["source.py"],
        },
        private=True,
    )
    return base_commit, attestation_file, initial_digests, packet_input


def run_command_verification(root: Path, attestation_file: str) -> None:
    with redirect_stdout(io.StringIO()):
        for command_id in load_policy(root)["verification"]["profiles"]["workflow"]:
            status = command_run_verification(
                argparse.Namespace(
                    root=str(root), file=attestation_file, command_id=command_id
                )
            )
            if status != 0:
                raise AssertionError(f"verification failed: {command_id}")


class AttestationTests(unittest.TestCase):
    def test_valid_workflow_state_machine(self) -> None:
        result = validate_attestation(valid_workflow(), base_commit=BASE_COMMIT, check_diff=False)
        self.assertEqual(result["kind"], "workflow")

    def test_prepare_and_finalize_refresh_repository_digests_after_init_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_commit, attestation_file, initial_digests, packet_input = (
                initialize_command_repository(root)
            )
            run_command_verification(root, attestation_file)
            packet_output = ".ai-runtime/reviewer-packets/task.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    command_prepare_reviewer_packet(
                        argparse.Namespace(
                            root=str(root),
                            input=str(packet_input),
                            file=attestation_file,
                            base=base_commit,
                            output=packet_output,
                        )
                    ),
                    0,
                )

            prepared = read_json(root / attestation_file)
            current_digests = {
                "policy_digest": sha256_file(root / POLICY_PATH),
                "prompt_manifest_digest": sha256_file(root / PROMPT_MANIFEST_PATH),
                "integrity_manifest_digest": sha256_file(root / INTEGRITY_MANIFEST_PATH),
            }
            self.assertNotEqual(initial_digests, current_digests)
            for key, value in current_digests.items():
                self.assertEqual(prepared[key], value)
            self.assertTrue((root / packet_output).is_file())
            prepared_packet = read_json(root / packet_output)
            self.assertEqual(
                prepared["prepared_reviewer_packet_digest"],
                sha256_json(prepared_packet),
            )

            altered_packet = copy.deepcopy(prepared_packet)
            altered_packet["review_rules"] = ["Use a different sanitized manual rule."]
            altered_packet_path = root / ".ai-runtime/reviewer-packets/altered.json"
            atomic_write_json(altered_packet_path, altered_packet, private=True)
            before_rejected_stage = read_json(root / attestation_file)
            with self.assertRaises(HarnessError):
                command_stage(
                    argparse.Namespace(
                        root=str(root),
                        file=attestation_file,
                        stage="reviewer",
                        packet=str(altered_packet_path),
                        status="approved",
                        round=0,
                    )
                )
            self.assertEqual(read_json(root / attestation_file), before_rejected_stage)

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    command_stage(
                        argparse.Namespace(
                            root=str(root),
                            file=attestation_file,
                            stage="reviewer",
                            packet=str(root / packet_output),
                            status="approved",
                            round=0,
                        )
                    ),
                    0,
                )
            staged = read_json(root / attestation_file)
            self.assertIsNone(staged["prepared_reviewer_packet_digest"])
            self.assertEqual(
                staged["reviewer_packet"]["packet_digest"],
                sha256_json(prepared_packet),
            )
            stale = read_json(root / attestation_file)
            stale.update(initial_digests)
            atomic_write_json(root / attestation_file, stale, private=False)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    command_finalize(
                        argparse.Namespace(
                            root=str(root), file=attestation_file, base=base_commit
                        )
                    ),
                    0,
                )
            finalized = read_json(root / attestation_file)
            for key, value in current_digests.items():
                self.assertEqual(finalized[key], value)
            self.assertEqual(
                finalized["task_diff_digest"], compute_task_diff_digest(root, base_commit)
            )

    def test_prepare_rejects_tampered_state_without_persisting_digest_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_commit, attestation_file, _, packet_input = initialize_command_repository(root)
            run_command_verification(root, attestation_file)
            attestation_path = root / attestation_file
            tampered = read_json(attestation_path)
            tampered["verification"][0]["result_digest"] = "0" * 64
            atomic_write_json(attestation_path, tampered, private=False)
            packet_output = ".ai-runtime/reviewer-packets/tampered.json"

            with self.assertRaises(HarnessError):
                command_prepare_reviewer_packet(
                    argparse.Namespace(
                        root=str(root),
                        input=str(packet_input),
                        file=attestation_file,
                        base=base_commit,
                        output=packet_output,
                    )
                )
            self.assertEqual(read_json(attestation_path), tampered)
            self.assertFalse((root / packet_output).exists())

    def test_source_change_requires_explicit_reprepare_to_replace_pending_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_commit, attestation_file, _, packet_input = initialize_command_repository(root)
            run_command_verification(root, attestation_file)
            first_output = ".ai-runtime/reviewer-packets/first.json"
            with redirect_stdout(io.StringIO()):
                command_prepare_reviewer_packet(
                    argparse.Namespace(
                        root=str(root),
                        input=str(packet_input),
                        file=attestation_file,
                        base=base_commit,
                        output=first_output,
                    )
                )
            first_digest = read_json(root / attestation_file)[
                "prepared_reviewer_packet_digest"
            ]

            (root / "source.py").write_text("changed again\n")
            run_command_verification(root, attestation_file)
            with self.assertRaises(HarnessError):
                command_stage(
                    argparse.Namespace(
                        root=str(root),
                        file=attestation_file,
                        stage="reviewer",
                        packet=str(root / first_output),
                        status="approved",
                        round=0,
                    )
                )
            self.assertEqual(
                read_json(root / attestation_file)["prepared_reviewer_packet_digest"],
                first_digest,
            )

            second_output = ".ai-runtime/reviewer-packets/second.json"
            with redirect_stdout(io.StringIO()):
                command_prepare_reviewer_packet(
                    argparse.Namespace(
                        root=str(root),
                        input=str(packet_input),
                        file=attestation_file,
                        base=base_commit,
                        output=second_output,
                    )
                )
            second_digest = read_json(root / attestation_file)[
                "prepared_reviewer_packet_digest"
            ]
            self.assertNotEqual(first_digest, second_digest)
            self.assertEqual(second_digest, sha256_json(read_json(root / second_output)))

    def test_implementer_before_approval_is_rejected(self) -> None:
        value = valid_workflow()
        value["events"] = [value["events"][0], value["events"][1], value["events"][3]]
        value["events"][2]["sequence"] = 3
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_context_digest_reuse_is_rejected(self) -> None:
        value = valid_workflow()
        value["events"][1]["context_digest"] = value["events"][0]["context_digest"]
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_final_reviewer_event_cannot_leave_prepared_digest_pending(self) -> None:
        value = valid_workflow()
        value["prepared_reviewer_packet_digest"] = digest("unconsumed-packet")
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_implementer_prompt_scope_mismatch_is_rejected(self) -> None:
        value = valid_workflow()
        value["events"][3]["prompt_scope_digest"] = digest("different-scope")
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_blind_packet_violation_is_rejected(self) -> None:
        raw = reviewer_packet_input(include_task_diff=True)
        raw["implementer"] = {"rationale": "must remain blind"}
        with self.assertRaises(HarnessError):
            canonical_reviewer_packet(raw, load_policy(), root=Path.cwd(), base_commit=BASE_COMMIT)

    def test_reviewer_packet_redaction_is_rejected_to_prevent_copy_mismatch(self) -> None:
        raw = reviewer_packet_input(include_task_diff=False)
        raw["original_request"] = {"password": "hunter2"}
        with self.assertRaises(HarnessError):
            canonical_reviewer_packet(
                raw,
                load_policy(),
                root=Path.cwd(),
                base_commit=BASE_COMMIT,
                allow_missing_task_diff=True,
            )

    def test_reviewer_packet_task_diff_mismatch_is_rejected(self) -> None:
        raw = reviewer_packet_input(include_task_diff=True)
        raw["task_diff"] = {"base_commit": BASE_COMMIT, "changes": []}
        with self.assertRaises(HarnessError):
            canonical_reviewer_packet(raw, load_policy(), root=Path.cwd(), base_commit=BASE_COMMIT)

    def test_reviewer_packet_rejects_nested_forbidden_keys_and_output_bodies(self) -> None:
        raw = reviewer_packet_input(include_task_diff=True)
        raw["acceptance_criteria"] = [{"nested": {"transcript": "hidden"}}]
        with self.assertRaises(HarnessError):
            canonical_reviewer_packet(raw, load_policy(), root=Path.cwd(), base_commit=BASE_COMMIT)

    def test_reviewer_packet_enforces_allowed_field_types(self) -> None:
        raw = reviewer_packet_input(include_task_diff=True)
        raw["review_rules"] = "not-an-array"
        with self.assertRaises(HarnessError):
            canonical_reviewer_packet(raw, load_policy(), root=Path.cwd(), base_commit=BASE_COMMIT)
        raw = reviewer_packet_input(include_task_diff=True)
        raw["verification"] = [
            {"command_id": "git_diff_check", "status": "passed", "command_output": "secret output"}
        ]
        with self.assertRaises(HarnessError):
            canonical_reviewer_packet(raw, load_policy(), root=Path.cwd(), base_commit=BASE_COMMIT)

    def test_reviewer_packet_rejects_forbidden_content_markers(self) -> None:
        raw = reviewer_packet_input(include_task_diff=True)
        raw["review_rules"] = ["rationale: include implementation discussion"]
        with self.assertRaises(HarnessError):
            canonical_reviewer_packet(raw, load_policy(), root=Path.cwd(), base_commit=BASE_COMMIT)

    def test_reviewer_packet_rejects_unsafe_source_references(self) -> None:
        for reference in ("/tmp/source.py", "../source.py", ".ai-runtime/logs/private.jsonl"):
            with self.subTest(reference=reference):
                raw = reviewer_packet_input(include_task_diff=True)
                raw["final_source_references"] = [reference]
                with self.assertRaises(HarnessError):
                    canonical_reviewer_packet(raw, load_policy(), root=Path.cwd(), base_commit=BASE_COMMIT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "linked.py").symlink_to(Path.cwd() / "scripts/ai_harness/common.py")
            raw = reviewer_packet_input(include_task_diff=False)
            raw["final_source_references"] = ["linked.py"]
            with self.assertRaises(HarnessError):
                canonical_reviewer_packet(raw, load_policy(), root=root, base_commit=BASE_COMMIT, allow_missing_task_diff=True)

    def test_scope_paths_reject_diff_outside_approval(self) -> None:
        snapshot = {
            "base_commit": BASE_COMMIT,
            "changes": [{"path": "src/app/page.js"}, {"path": "scripts/ai_harness/common.py"}],
        }
        with self.assertRaises(HarnessError):
            validate_changed_paths_in_scope(snapshot, ["scripts/ai_harness/**"])

    def test_source_change_after_reviewer_requires_new_packet(self) -> None:
        value = valid_workflow()
        new_diff = digest("changed-after-review")
        value["task_diff_digest"] = new_diff
        value["verification"] = verification("workflow", new_diff)
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_third_fix_review_is_rejected(self) -> None:
        value = valid_workflow()
        scope = value["approved_scope_digest"]
        scope_paths = value["approved_scope_paths_digest"]
        value["events"] = value["events"][:4] + [
            event(5, "reviewer", "changes_requested", digest("review-0"), scope, 0, scope_paths=scope_paths, task_diff=digest("d0")),
            event(6, "implementer", "completed", digest("fix-1"), scope, 1, scope_paths=scope_paths, prompt_scope=scope),
            event(7, "reviewer", "changes_requested", digest("review-1"), scope, 1, scope_paths=scope_paths, task_diff=digest("d1")),
            event(8, "implementer", "completed", digest("fix-2"), scope, 2, scope_paths=scope_paths, prompt_scope=scope),
            event(9, "reviewer", "changes_requested", digest("review-2"), scope, 2, scope_paths=scope_paths, task_diff=digest("d2")),
            event(10, "implementer", "completed", digest("fix-3"), scope, 3, scope_paths=scope_paths, prompt_scope=scope),
        ]
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_scope_change_without_reapproval_is_rejected(self) -> None:
        value = valid_workflow()
        old_scope = value["approved_scope_digest"]
        scope_paths = value["approved_scope_paths_digest"]
        value["events"] = value["events"][:4] + [
            event(5, "reviewer", "changes_requested", digest("review-0"), old_scope, 0, scope_paths=scope_paths, task_diff=digest("d0")),
            event(
                6,
                "implementer",
                "completed",
                digest("fix-1"),
                digest("new-scope"),
                1,
                scope_paths=scope_paths,
                prompt_scope=digest("new-scope"),
            ),
        ]
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_nonzero_verification_exit_status_is_rejected(self) -> None:
        value = valid_workflow()
        value["verification"][0]["exit_status"] = 1
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_forged_verification_result_digest_is_rejected(self) -> None:
        value = valid_workflow()
        value["verification"][0]["result_digest"] = "0" * 64
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_reviewer_packet_verification_digest_tamper_is_rejected(self) -> None:
        value = valid_workflow()
        value["reviewer_packet"]["field_digests"]["verification"] = f"sha256:{'0' * 64}"
        with self.assertRaises(HarnessError):
            validate_attestation(value, base_commit=BASE_COMMIT, check_diff=False)

    def test_validator_rejects_task_patch_digest_tamper(self) -> None:
        value = valid_workflow()
        expected_patch_digest = value["reviewer_packet"]["field_digests"]["task_patch"][7:]
        validate_event_sequence(
            value,
            load_policy(),
            require_complete=True,
            expected_task_diff_digest=value["task_diff_digest"],
            expected_task_patch_digest=expected_patch_digest,
        )
        with self.assertRaises(HarnessError):
            validate_event_sequence(
                value,
                load_policy(),
                require_complete=True,
                expected_task_diff_digest=value["task_diff_digest"],
                expected_task_patch_digest="0" * 64,
            )

    def test_old_caller_supplied_exit_status_command_is_removed(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["verification", "--file", "x", "--exit-status", "0"])

    def test_run_verification_records_real_process_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "initial.txt").write_text("initial")
            subprocess.run(["git", "add", "initial.txt"], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "init"],
                cwd=root,
                check=True,
            )
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            value = valid_workflow()
            value["base_commit"] = base
            value["kind"] = "bootstrap"
            record = run_verification_command(value, "runtime_untracked", root=root, policy=load_policy())
            self.assertEqual(record["exit_status"], 0)
            self.assertEqual(record["base_commit"], base)

    def test_successful_verification_command_that_mutates_source_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = initialize_source_repository(root)
            value = {"kind": "bootstrap", "base_commit": base, "verification": []}
            policy = copy.deepcopy(load_policy())
            policy["verification"]["commands"]["runtime_untracked"]["argv"] = [
                "python3",
                "-c",
                "from pathlib import Path; Path('source.py').write_text('mutated\\n')",
            ]

            record = run_verification_command(
                value,
                "runtime_untracked",
                root=root,
                policy=policy,
            )

            self.assertEqual(record["exit_status"], 1)
            self.assertEqual(record["task_diff_digest"], compute_task_diff_digest(root, base))
            self.assertNotIn("stdout", record)
            self.assertNotIn("stderr", record)

    def test_trusted_rerun_rejects_successful_command_that_mutates_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = initialize_source_repository(root)
            policy = load_policy()
            value = {"kind": "bootstrap", "base_commit": base, "verification": []}
            value["verification"] = [
                run_verification_command(
                    value,
                    "runtime_untracked",
                    root=root,
                    policy=policy,
                )
            ]
            trusted_policy = copy.deepcopy(policy)
            trusted_policy["verification"]["commands"]["runtime_untracked"]["argv"] = [
                "python3",
                "-c",
                "from pathlib import Path; Path('source.py').write_text('trusted mutation\\n')",
            ]

            with self.assertRaises(HarnessError):
                rerun_verification(
                    value,
                    policy,
                    root=root,
                    command_ids={"runtime_untracked"},
                    execution_policy=trusted_policy,
                )

    def test_ci_rerun_detects_verification_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "initial.txt").write_text("initial")
            subprocess.run(["git", "add", "initial.txt"], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "init"],
                cwd=root,
                check=True,
            )
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            value = {"kind": "bootstrap", "base_commit": base, "verification": []}
            policy = load_policy()
            value["verification"] = [
                run_verification_command(value, "runtime_untracked", root=root, policy=policy)
            ]
            rerun_verification(value, policy, root=root, command_ids={"runtime_untracked"})
            (root / ".ai-runtime").mkdir()
            (root / ".ai-runtime/leak.json").write_text("{}")
            subprocess.run(["git", "add", "-f", ".ai-runtime/leak.json"], cwd=root, check=True)
            with self.assertRaises(HarnessError):
                rerun_verification(value, policy, root=root, command_ids={"runtime_untracked"})

    def test_empty_rerun_command_set_executes_nothing(self) -> None:
        value = {"kind": "workflow", "base_commit": BASE_COMMIT, "verification": []}
        with mock.patch(
            "scripts.ai_harness.workflow_attestation.run_verification_command"
        ) as runner:
            rerun_verification(
                value,
                load_policy(),
                root=Path.cwd(),
                command_ids=set(),
            )
        runner.assert_not_called()

    def test_rerun_can_use_separate_trusted_execution_policy(self) -> None:
        candidate_policy = copy.deepcopy(load_policy())
        candidate_policy["verification"]["commands"]["git_diff_check"]["argv"] = [
            "python3",
            "candidate.py",
        ]
        trusted_policy = load_policy()
        record = next(
            item
            for item in verification("workflow", digest("trusted-diff"))
            if item["command_id"] == "git_diff_check"
        )
        value = {
            "kind": "workflow",
            "base_commit": BASE_COMMIT,
            "verification": [record],
        }
        with mock.patch(
            "scripts.ai_harness.workflow_attestation.run_verification_command",
            return_value=record,
        ) as runner:
            rerun_verification(
                value,
                candidate_policy,
                root=Path.cwd(),
                command_ids={"git_diff_check"},
                execution_policy=trusted_policy,
            )
        self.assertIs(runner.call_args.kwargs["policy"], trusted_policy)

    def test_stale_task_diff_digest_is_rejected(self) -> None:
        with self.assertRaises(HarnessError):
            validate_attestation(valid_workflow(), base_commit=BASE_COMMIT, check_diff=True)

    def test_bootstrap_is_rejected_after_installation_baseline(self) -> None:
        altered = copy.deepcopy(load_policy())
        altered["installation_base_commit"] = "a" * 40
        altered["bootstrap"]["base_commit"] = "a" * 40
        with self.assertRaises(HarnessError):
            validate_policy_constants(altered)

    def test_bootstrap_rejects_non_harness_path(self) -> None:
        snapshot = {"base_commit": BASE_COMMIT, "changes": [{"path": "src/app/page.js"}]}
        with self.assertRaises(HarnessError):
            validate_bootstrap_changed_paths(snapshot)

    def test_attestation_output_rejects_repository_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(HarnessError):
                write_attestation(root, "/tmp/outside.json", valid_workflow())
            with self.assertRaises(HarnessError):
                write_attestation(root, ".agents/ai-harness/attestations/../outside.json", valid_workflow())

    def test_attestation_output_rejects_parent_and_target_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            outside = Path(outside_directory)
            harness = root / ".agents/ai-harness"
            harness.mkdir(parents=True)
            (harness / "attestations").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(HarnessError):
                write_attestation(
                    root,
                    ".agents/ai-harness/attestations/task.json",
                    valid_workflow(),
                )

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            target_dir = root / ".agents/ai-harness/attestations"
            target_dir.mkdir(parents=True)
            outside_file = Path(outside_directory) / "outside.json"
            outside_file.write_text("unchanged")
            (target_dir / "task.json").symlink_to(outside_file)
            with self.assertRaises(HarnessError):
                write_attestation(
                    root,
                    ".agents/ai-harness/attestations/task.json",
                    valid_workflow(),
                )
            self.assertEqual(outside_file.read_text(), "unchanged")


if __name__ == "__main__":
    unittest.main()
