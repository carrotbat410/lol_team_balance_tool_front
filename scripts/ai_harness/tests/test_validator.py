from __future__ import annotations

import copy
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stderr

from scripts.ai_harness.common import HarnessError, load_policy
from scripts.ai_harness.validate import (
    validate_ai_workflow_text,
    validate_deploy_workflow_text,
    validate_trusted_pr_workflow_text,
    validate_hooks,
    validate_prompt_manifest,
    validate_policy,
    validate_roles,
    validate_runtime,
    resolve_base,
    main as validate_main,
)


class ValidatorFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy()

    def test_sandbox_relaxation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(".codex", root / ".codex")
            shutil.copytree(".agents/prompts", root / ".agents/prompts")
            path = root / ".codex/agents/implementer.toml"
            path.write_text(path.read_text().replace('sandbox_mode = "workspace-write"', 'sandbox_mode = "danger-full-access"'))
            with self.assertRaises(HarnessError):
                validate_roles(root, self.policy)

    def test_role_filename_normalization_is_rejected(self) -> None:
        altered = copy.deepcopy(self.policy)
        altered["roles"]["planner"]["template"] = ".agents/prompts/Planner.md"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(".codex", root / ".codex")
            shutil.copytree(".agents/prompts", root / ".agents/prompts")
            with self.assertRaises(HarnessError):
                validate_roles(root, altered)

    def test_unapproved_hook_command_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".codex").mkdir()
            hooks = json.loads(Path(".codex/hooks.json").read_text())
            hooks["hooks"]["Stop"][0]["hooks"][0]["command"] = "curl https://example.invalid"
            (root / ".codex/hooks.json").write_text(json.dumps(hooks))
            with self.assertRaises(HarnessError):
                validate_hooks(root, self.policy)

    def test_missing_hook_event_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".codex").mkdir()
            hooks = json.loads(Path(".codex/hooks.json").read_text())
            del hooks["hooks"]["SessionEnd"]
            (root / ".codex/hooks.json").write_text(json.dumps(hooks))
            with self.assertRaises(HarnessError):
                validate_hooks(root, self.policy)

    def test_tracked_runtime_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("/.ai-runtime/\n")
            runtime = root / ".ai-runtime"
            runtime.mkdir()
            (runtime / "leak.json").write_text("{}")
            subprocess.run(["git", "add", "-f", ".ai-runtime/leak.json", ".gitignore"], cwd=root, check=True)
            with self.assertRaises(HarnessError):
                validate_runtime(root)

    def test_deploy_needs_removal_is_rejected(self) -> None:
        text = Path(".github/workflows/deploy-frontend.yml").read_text()
        altered = text.replace("needs: [harness-check, build-and-push]", "needs: build-and-push")
        with self.assertRaises(HarnessError):
            validate_deploy_workflow_text(altered)

    def test_ci_artifact_retention_change_is_rejected(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(text.replace("retention-days: 7", "retention-days: 30"))

    def test_unit_test_step_replaced_by_noop_is_rejected(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        altered = text.replace(
            "run: python3 -m unittest discover -s scripts/ai_harness/tests -p 'test_*.py'",
            "run: true",
        )
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(altered)

    def test_unit_test_noop_with_misleading_comment_is_rejected(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        altered = text.replace(
            "run: python3 -m unittest discover -s scripts/ai_harness/tests -p 'test_*.py'",
            "run: true # python3 -m unittest discover -s scripts/ai_harness/tests -p 'test_*.py'",
        )
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(altered)

    def test_validator_step_replaced_by_noop_is_rejected(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        altered = text.replace("python3 scripts/ai_harness/validate.py --mode ci", "true")
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(altered)

    def test_report_upload_step_removal_is_rejected(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        start = text.index("      - name: 본문 없는 검증 보고서 보존")
        end = text.index("      - name: 정책 검증 실패 반영", start)
        altered = text[:start] + text[end:]
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(altered)

    def test_final_failure_enforcement_removal_is_rejected(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        altered = text.split("      - name: 정책 검증 실패 반영", 1)[0]
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(altered)

    def test_baseline_failure_capture_or_fallback_removal_is_rejected(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        altered = text.replace("        id: baseline\n        continue-on-error: true", "        id: baseline", 1)
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(altered)
        start = text.index("      - name: 기준 실패 보고서 생성")
        end = text.index("      - name: 본문 없는 검증 보고서 보존", start)
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(text[:start] + text[end:])

    def test_final_enforcement_must_include_baseline_failure(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        altered = text.replace("steps.baseline.outcome != 'success' || ", "", 1)
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(altered)

    def test_trusted_pr_gate_cannot_execute_candidate_python(self) -> None:
        text = Path(".github/workflows/ai-harness-trusted-pr.yml").read_text()
        validate_trusted_pr_workflow_text(text)
        altered = text.replace(
            "python3 scripts/ai_harness/validate.py --mode trusted-pr",
            "python3 candidate/scripts/ai_harness/validate.py --mode trusted-pr",
        )
        with self.assertRaises(HarnessError):
            validate_trusted_pr_workflow_text(altered)

    def test_deploy_unit_test_noop_is_rejected(self) -> None:
        text = Path(".github/workflows/deploy-frontend.yml").read_text()
        altered = text.replace(
            "run: python3 -m unittest discover -s scripts/ai_harness/tests -p 'test_*.py'",
            "run: true",
        )
        with self.assertRaises(HarnessError):
            validate_deploy_workflow_text(altered)

    def test_deploy_final_failure_enforcement_removal_is_rejected(self) -> None:
        text = Path(".github/workflows/deploy-frontend.yml").read_text()
        start = text.index("      - name: 정책 검증 실패 반영")
        end = text.index("\n  build-and-push:", start)
        altered = text[:start] + text[end:]
        with self.assertRaises(HarnessError):
            validate_deploy_workflow_text(altered)

    def test_head_parent_workflow_dispatch_guess_is_rejected(self) -> None:
        text = Path(".github/workflows/ai-harness-check.yml").read_text()
        altered = text.replace('${{ inputs.base_commit }}', "$(git rev-parse HEAD^)")
        with self.assertRaises(HarnessError):
            validate_ai_workflow_text(altered)

    def test_policy_and_integrity_rewrite_cannot_move_bootstrap_base(self) -> None:
        altered = copy.deepcopy(self.policy)
        altered["installation_base_commit"] = "a" * 40
        altered["bootstrap"]["base_commit"] = "a" * 40
        # Updating a separate integrity manifest cannot change the compiled baseline check.
        with self.assertRaises(HarnessError):
            validate_policy(altered)

    def test_contract_digest_change_is_rejected_by_prompt_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(".agents/prompts", root / ".agents/prompts")
            shutil.copytree(".codex/agents", root / ".codex/agents")
            contract = root / ".codex/agents/researcher.toml"
            contract.write_text(contract.read_text() + "\n# tampered\n")
            with self.assertRaises(HarnessError):
                validate_prompt_manifest(root, self.policy)

    def test_validator_rejects_symlinked_runtime_before_external_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            outside = Path(outside_directory)
            (root / ".agents/ai-harness").mkdir(parents=True)
            shutil.copy2(".agents/ai-harness/policy.json", root / ".agents/ai-harness/policy.json")
            protected = outside / "protected.json"
            protected.write_text("unchanged")
            before_mode = protected.stat().st_mode
            (root / ".ai-runtime").symlink_to(outside, target_is_directory=True)
            with redirect_stderr(io.StringIO()):
                status = validate_main(
                    [
                        "--mode",
                        "local",
                        "--root",
                        str(root),
                        "--base",
                        "5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773",
                        "--report",
                        ".ai-runtime/reports/ai-harness-report.json",
                    ]
                )
            self.assertEqual(status, 1)
            self.assertEqual(protected.read_text(), "unchanged")
            self.assertEqual(protected.stat().st_mode, before_mode)

    def test_explicit_multi_commit_ancestor_base_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            commits = []
            for index in range(3):
                (root / "file.txt").write_text(str(index))
                subprocess.run(["git", "add", "file.txt"], cwd=root, check=True)
                subprocess.run(
                    [
                        "git",
                        "-c",
                        "user.name=Test",
                        "-c",
                        "user.email=test@example.invalid",
                        "commit",
                        "-qm",
                        f"commit-{index}",
                    ],
                    cwd=root,
                    check=True,
                )
                commits.append(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip())
            self.assertEqual(resolve_base(root, commits[0]), commits[0])
            with self.assertRaises(HarnessError):
                resolve_base(root, "a" * 40)


if __name__ == "__main__":
    unittest.main()
