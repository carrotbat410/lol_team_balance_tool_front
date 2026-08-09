from __future__ import annotations

import copy
import hashlib
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from scripts.ai_harness.common import (
    INTEGRITY_MANIFEST_PATH,
    POLICY_PATH,
    PROMPT_MANIFEST_PATH,
    HarnessError,
    load_policy,
    compute_task_diff_snapshot,
    sha256_file,
    sha256_json,
    validate_bootstrap_changed_paths,
)
from scripts.ai_harness.workflow_attestation import (
    build_parser,
    canonical_reviewer_packet,
    rerun_verification,
    run_verification_command,
    validate_changed_paths_in_scope,
    validate_attestation,
    validate_policy_constants,
    write_attestation,
)


BASE_COMMIT = "5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def packet_metadata(task_diff_digest: str) -> dict[str, object]:
    policy = load_policy()
    fields = {
        key: f"sha256:{task_diff_digest if key == 'task_diff' else digest(key)}"
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


def verification(kind: str, task_diff_digest: str) -> list[dict[str, object]]:
    policy = load_policy()
    records = []
    for command_id in policy["verification"]["profiles"][kind]:
        argv = [
            value.replace("{base_commit}", BASE_COMMIT)
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
                        "base_commit": BASE_COMMIT,
                        "task_diff_digest": task_diff_digest,
                    }
                ),
                "base_commit": BASE_COMMIT,
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


class AttestationTests(unittest.TestCase):
    def test_valid_workflow_state_machine(self) -> None:
        result = validate_attestation(valid_workflow(), base_commit=BASE_COMMIT, check_diff=False)
        self.assertEqual(result["kind"], "workflow")

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
