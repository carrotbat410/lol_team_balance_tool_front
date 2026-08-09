from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ai_harness.common import (  # noqa: E402
    HEX_40,
    INSTALLATION_BASE_COMMIT,
    HarnessError,
    INTEGRITY_MANIFEST_PATH,
    POLICY_PATH,
    PROMPT_MANIFEST_PATH,
    REPO_ROOT,
    git_commit,
    git_output,
    load_policy,
    prune_runtime,
    read_json,
    resolve_runtime_path,
    sha256_file,
    utc_timestamp,
    write_private_json,
    RUNTIME_RETENTION_DAYS,
    RUNTIME_RETENTION_TARGETS,
    RUNTIME_ROOT,
)
from scripts.ai_harness.workflow_attestation import (  # noqa: E402
    attestation_path,
    validate_attestation,
    validate_policy_constants,
)


REQUIRED_FILES = {
    ".codex/hooks.json",
    ".agents/ai-harness/policy.json",
    ".agents/ai-harness/integrity-manifest.json",
    ".agents/ai-harness/schemas/task-envelope.schema.json",
    ".agents/ai-harness/schemas/prompt-record.schema.json",
    ".agents/ai-harness/schemas/lifecycle-log.schema.json",
    ".agents/ai-harness/schemas/workflow-attestation.schema.json",
    ".agents/prompts/manifest.json",
    ".agents/prompts/researcher.md",
    ".agents/prompts/planner.md",
    ".agents/prompts/implementer.md",
    ".agents/prompts/reviewer.md",
    "scripts/ai_harness/common.py",
    "scripts/ai_harness/__init__.py",
    "scripts/ai_harness/hook_logger.py",
    "scripts/ai_harness/prompt_history.py",
    "scripts/ai_harness/workflow_attestation.py",
    "scripts/ai_harness/validate.py",
    "scripts/ai_harness/tests/__init__.py",
    "scripts/ai_harness/tests/test_attestation.py",
    "scripts/ai_harness/tests/test_common.py",
    "scripts/ai_harness/tests/test_hook_logger.py",
    "scripts/ai_harness/tests/test_prompt_history.py",
    "scripts/ai_harness/tests/test_validator.py",
    ".github/workflows/ai-harness-check.yml",
    ".github/workflows/ai-harness-trusted-pr.yml",
    ".github/workflows/deploy-frontend.yml",
    "docs/ai-harness.md",
}
INTEGRITY_FILES = {
    ".codex/hooks.json",
    ".agents/ai-harness/policy.json",
    ".agents/ai-harness/schemas/task-envelope.schema.json",
    ".agents/ai-harness/schemas/prompt-record.schema.json",
    ".agents/ai-harness/schemas/lifecycle-log.schema.json",
    ".agents/ai-harness/schemas/workflow-attestation.schema.json",
    ".agents/prompts/manifest.json",
    ".agents/prompts/researcher.md",
    ".agents/prompts/planner.md",
    ".agents/prompts/implementer.md",
    ".agents/prompts/reviewer.md",
    ".github/workflows/ai-harness-check.yml",
    ".github/workflows/ai-harness-trusted-pr.yml",
    ".github/workflows/deploy-frontend.yml",
    "scripts/ai_harness/common.py",
    "scripts/ai_harness/__init__.py",
    "scripts/ai_harness/hook_logger.py",
    "scripts/ai_harness/prompt_history.py",
    "scripts/ai_harness/workflow_attestation.py",
    "scripts/ai_harness/validate.py",
    "scripts/ai_harness/tests/__init__.py",
    "scripts/ai_harness/tests/test_attestation.py",
    "scripts/ai_harness/tests/test_common.py",
    "scripts/ai_harness/tests/test_hook_logger.py",
    "scripts/ai_harness/tests/test_prompt_history.py",
    "scripts/ai_harness/tests/test_validator.py",
    ".codex/agents/researcher.toml",
    ".codex/agents/planner.toml",
    ".codex/agents/implementer.toml",
    ".codex/agents/reviewer.toml",
}

EXPECTED_VERIFICATION_COMMANDS = {
    "base_ancestor": {
        "argv": ["git", "merge-base", "--is-ancestor", "{base_commit}", "HEAD"],
        "stdout_must_be_empty": True,
        "trusted_pr_safe": True,
    },
    "git_diff_check": {
        "argv": ["git", "diff", "--check"],
        "stdout_must_be_empty": True,
        "trusted_pr_safe": True,
    },
    "runtime_untracked": {
        "argv": ["git", "ls-files", ".ai-runtime/**"],
        "stdout_must_be_empty": True,
        "trusted_pr_safe": True,
    },
    "unit_tests": {
        "argv": [
            "python3",
            "-m",
            "unittest",
            "discover",
            "-s",
            "scripts/ai_harness/tests",
            "-p",
            "test_*.py",
        ],
        "stdout_must_be_empty": False,
        "trusted_pr_safe": False,
    },
}
EXPECTED_VERIFICATION_PROFILES = {
    "bootstrap": ["git_diff_check", "runtime_untracked", "unit_tests"],
    "workflow": ["base_ancestor", "git_diff_check", "runtime_untracked", "unit_tests"],
}


def validate_required_files(root: Path) -> None:
    missing = sorted(relative for relative in REQUIRED_FILES if not (root / relative).is_file())
    if missing:
        raise HarnessError(f"missing required files: {missing}")


def validate_json_toml(root: Path) -> None:
    paths = list((root / ".agents/ai-harness").rglob("*.json"))
    paths += list((root / ".agents/prompts").glob("*.json"))
    paths.append(root / ".codex/hooks.json")
    for path in paths:
        read_json(path)
    for path in (root / ".codex/agents").glob("*.toml"):
        try:
            tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise HarnessError(f"invalid TOML: {path.relative_to(root)}: {exc}") from exc
    try:
        tomllib.loads((root / ".codex/config.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise HarnessError(f"invalid TOML: .codex/config.toml: {exc}") from exc


def validate_policy(policy: dict[str, Any]) -> None:
    validate_policy_constants(policy)
    if policy.get("bootstrap") != {
        "allowed": True,
        "base_commit": INSTALLATION_BASE_COMMIT,
        "attestation": ".agents/ai-harness/attestations/bootstrap.json",
        "retroactive_hook_logs": False,
    }:
        raise HarnessError("bootstrap policy differs from the compiled installation exception")
    runtime = policy.get("runtime", {})
    if runtime.get("root") != RUNTIME_ROOT:
        raise HarnessError("runtime root differs from the compiled repository-local root")
    if runtime.get("retention_days") != RUNTIME_RETENTION_DAYS:
        raise HarnessError("runtime retention must remain 30 days")
    if runtime.get("retention_targets") != list(RUNTIME_RETENTION_TARGETS):
        raise HarnessError("runtime retention targets differ from the compiled allowlist")
    if runtime.get("state_lifetime") != "local-installation":
        raise HarnessError("state lifetime policy must remain separate from expiring runtime artifacts")
    verification = policy.get("verification", {})
    if verification.get("commands") != EXPECTED_VERIFICATION_COMMANDS:
        raise HarnessError("verification command definitions differ from the compiled allowlist")
    if verification.get("profiles") != EXPECTED_VERIFICATION_PROFILES:
        raise HarnessError("verification profiles differ from the compiled allowlist")


def validate_integrity(root: Path) -> None:
    manifest = read_json(root / INTEGRITY_MANIFEST_PATH)
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "files"}:
        raise HarnessError("invalid integrity manifest structure")
    if manifest["schema_version"] != "1.0" or not isinstance(manifest["files"], dict):
        raise HarnessError("invalid integrity manifest version")
    if set(manifest["files"]) != INTEGRITY_FILES:
        raise HarnessError("integrity manifest file set differs from policy")
    for relative, expected in manifest["files"].items():
        if sha256_file(root / relative) != expected:
            raise HarnessError(f"integrity digest mismatch: {relative}")


def validate_roles(root: Path, policy: dict[str, Any]) -> None:
    roles = policy.get("roles")
    if not isinstance(roles, dict) or set(roles) != {"researcher", "planner", "implementer", "reviewer"}:
        raise HarnessError("policy role names are not normalized")
    for role, config in roles.items():
        contract = config["contract"]
        template = config["template"]
        if Path(contract).stem != role or Path(template).stem != role:
            raise HarnessError(f"role filename is not normalized: {role}")
        data = tomllib.loads((root / contract).read_text(encoding="utf-8"))
        if data.get("name") != config["display_name"]:
            raise HarnessError(f"role display name mismatch: {role}")
        if data.get("sandbox_mode") != config["sandbox_mode"]:
            raise HarnessError(f"role sandbox weakened or changed: {role}")
        template_text = (root / template).read_text(encoding="utf-8")
        if f"@{contract}" not in template_text:
            raise HarnessError(f"role template does not reference its tracked contract: {role}")
        if len(template_text.encode("utf-8")) > 4096:
            raise HarnessError(f"role template appears to duplicate the role contract: {role}")

    config = tomllib.loads((root / ".codex/config.toml").read_text(encoding="utf-8"))
    if config.get("features", {}).get("hooks") is not True:
        raise HarnessError("Codex hooks feature must be explicitly enabled")


def validate_prompt_manifest(root: Path, policy: dict[str, Any]) -> None:
    manifest = read_json(root / PROMPT_MANIFEST_PATH)
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "roles"}:
        raise HarnessError("invalid prompt manifest")
    if manifest["schema_version"] != "1.0" or set(manifest["roles"]) != set(policy["roles"]):
        raise HarnessError("prompt manifest roles differ from policy")
    for role, entry in manifest["roles"].items():
        if set(entry) != {"template", "agent_contract", "contract_sha256", "sha256"}:
            raise HarnessError(f"invalid prompt manifest entry: {role}")
        role_policy = policy["roles"][role]
        if entry["template"] != role_policy["template"] or entry["agent_contract"] != role_policy["contract"]:
            raise HarnessError(f"prompt manifest path mismatch: {role}")
        if entry["sha256"] != sha256_file(root / entry["template"]):
            raise HarnessError(f"prompt template digest mismatch: {role}")
        if entry["contract_sha256"] != sha256_file(root / entry["agent_contract"]):
            raise HarnessError(f"agent contract digest mismatch: {role}")


def validate_schemas(root: Path) -> None:
    schema_dir = root / ".agents/ai-harness/schemas"
    for path in schema_dir.glob("*.schema.json"):
        schema = read_json(path)
        if not isinstance(schema, dict) or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise HarnessError(f"unsupported JSON schema declaration: {path.name}")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            raise HarnessError(f"top-level JSON schema must fail closed: {path.name}")


def validate_hooks(root: Path, policy: dict[str, Any]) -> None:
    document = read_json(root / ".codex/hooks.json")
    if not isinstance(document, dict) or set(document) != {"description", "hooks"}:
        raise HarnessError("invalid Codex hooks document")
    hooks = document["hooks"]
    expected_events = set(policy["hook"]["events"])
    if not isinstance(hooks, dict) or set(hooks) != expected_events:
        raise HarnessError("hook event allowlist mismatch")
    allowed_commands = set(policy["hook"]["commands"])
    allowed_types = set(policy["hook"]["handler_types"])
    for event, groups in hooks.items():
        if not isinstance(groups, list) or len(groups) != 1 or not isinstance(groups[0], dict):
            raise HarnessError(f"hook event must have one matcher group: {event}")
        group = groups[0]
        allowed_group_keys = {"hooks", "matcher"}
        if not set(group) <= allowed_group_keys or "hooks" not in group:
            raise HarnessError(f"invalid matcher group fields: {event}")
        if event in ("UserPromptSubmit", "Stop") and "matcher" in group:
            raise HarnessError(f"matcher is not supported for {event}")
        if event in ("SubagentStart", "SubagentStop") and group.get("matcher") != "^(researcher|planner|implementer|reviewer)$":
            raise HarnessError(f"subagent hook matcher mismatch: {event}")
        if event == "SessionEnd" and group.get("matcher") != "^other$":
            raise HarnessError("SessionEnd matcher mismatch")
        handlers = group["hooks"]
        if not isinstance(handlers, list) or len(handlers) != 1 or not isinstance(handlers[0], dict):
            raise HarnessError(f"hook event must have one command handler: {event}")
        handler = handlers[0]
        if set(handler) != {"type", "command", "timeout", "statusMessage"}:
            raise HarnessError(f"hook handler fields differ from allowlist: {event}")
        if handler["type"] not in allowed_types or handler["command"] not in allowed_commands:
            raise HarnessError(f"unapproved hook command or handler type: {event}")
        if handler["timeout"] > policy["hook"]["max_timeout_seconds"]:
            raise HarnessError(f"hook timeout exceeds policy: {event}")


def _job_block(text: str, job: str) -> str:
    match = re.search(rf"(?m)^  {re.escape(job)}:\s*$", text)
    if not match:
        raise HarnessError(f"workflow job is missing: {job}")
    next_match = re.search(r"(?m)^  [A-Za-z0-9_-]+:\s*$", text[match.end() :])
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.start() : end]


def _strip_yaml_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote == '"':
            escaped = True
            continue
        if character in ("'", '"'):
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        if character == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.rstrip()


def _yaml_scalar(value: str) -> str:
    value = _strip_yaml_comment(value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _shell_scalar(value: str) -> str:
    commands: list[str] = []
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        commands.append(_strip_yaml_comment(stripped))
    return "\n".join(command for command in commands if command)


def _workflow_steps(job: str) -> list[tuple[int, dict[str, Any]]]:
    lines = job.splitlines()
    starts = [index for index, line in enumerate(lines) if re.match(r"^      - name:\s*", line)]
    steps: list[tuple[int, dict[str, Any]]] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:end]
        first = re.match(r"^      - name:\s*(.*)$", block[0])
        assert first is not None
        step: dict[str, Any] = {"name": _yaml_scalar(first.group(1))}
        index = 1
        while index < len(block):
            match = re.match(r"^        ([A-Za-z0-9_-]+):(?:\s*(.*))?$", block[index])
            if not match:
                index += 1
                continue
            key, raw_value = match.group(1), match.group(2) or ""
            if raw_value in ("|", "|-", ">", ">-"):
                scalar_lines: list[str] = []
                index += 1
                while index < len(block) and (not block[index].strip() or len(block[index]) - len(block[index].lstrip()) >= 10):
                    line = block[index]
                    scalar_lines.append(line[10:] if len(line) >= 10 else "")
                    index += 1
                step[key] = "\n".join(scalar_lines) if raw_value.startswith("|") else " ".join(
                    line.strip() for line in scalar_lines
                )
                continue
            if raw_value == "":
                nested: dict[str, str] = {}
                index += 1
                while index < len(block):
                    child = re.match(r"^          ([A-Za-z0-9_-]+):\s*(.*)$", block[index])
                    if not child:
                        break
                    nested[child.group(1)] = _yaml_scalar(child.group(2))
                    index += 1
                step[key] = nested
                continue
            step[key] = _yaml_scalar(raw_value)
            index += 1
        steps.append((start, step))
    return steps


def _named_step(steps: list[tuple[int, dict[str, Any]]], name: str) -> tuple[int, dict[str, Any]]:
    matches = [(index, step) for index, step in steps if step.get("name") == name]
    if len(matches) != 1:
        raise HarnessError(f"workflow must contain exactly one step named: {name}")
    return matches[0]


def _require_run(step: dict[str, Any], fragments: tuple[str, ...], description: str) -> str:
    run = step.get("run")
    if not isinstance(run, str):
        raise HarnessError(f"{description} has no actual run scalar")
    actual = _shell_scalar(run)
    if actual.casefold() in ("true", ":") or any(fragment not in actual for fragment in fragments):
        raise HarnessError(f"{description} is missing required executable commands or is a no-op")
    return actual


def _validate_dispatch_input(text: str) -> None:
    required = (
        "workflow_dispatch:",
        "inputs:",
        "base_commit:",
        "required: true",
        "type: string",
    )
    if not all(fragment in text for fragment in required):
        raise HarnessError("workflow_dispatch must require an explicit base_commit input")


def _validate_harness_job(job: str, *, trigger_kind: str) -> None:
    if re.search(r"(?m)^    (?:if:\s*false|continue-on-error:\s*true)\s*$", job):
        raise HarnessError("harness-check job cannot be disabled or made advisory")
    steps = _workflow_steps(job)
    baseline_index, baseline = _named_step(steps, "검증 기준 커밋 결정")
    required_baseline = [
        'git cat-file -e "${base_commit}^{commit}"',
        'git merge-base --is-ancestor "$base_commit" HEAD',
        'echo "base=$base_commit" >> "$GITHUB_OUTPUT"',
        '${{ inputs.base_commit }}',
    ]
    if trigger_kind == "pull_request":
        required_baseline.append("${{ github.event.pull_request.base.sha }}")
    elif trigger_kind == "push":
        required_baseline.append("${{ github.event.before }}")
    else:
        raise HarnessError("unknown harness workflow trigger kind")
    baseline_run = _require_run(baseline, tuple(required_baseline), "baseline step")
    if baseline.get("id") != "baseline" or baseline.get("continue-on-error") != "true" or "HEAD^" in baseline_run:
        raise HarnessError("baseline step does not validate the event-provided ancestor commit")

    unit_index, unit = _named_step(steps, "AI harness 단위 테스트")
    _require_run(unit, ("python3 -m unittest discover -s scripts/ai_harness/tests -p 'test_*.py'",), "unit-test step")
    if unit.get("id") != "unit-tests" or unit.get("continue-on-error") != "true":
        raise HarnessError("unit-test step is missing, advisory, or a no-op")

    validation_index, validation = _named_step(steps, "AI harness 정책 검증")
    _require_run(
        validation,
        (
            "id: validation",
            "python3 scripts/ai_harness/validate.py --mode ci",
            '--base "${{ steps.baseline.outputs.base }}"',
            "--report .ai-runtime/reports/ai-harness-report.json",
        )[1:],
        "validator step",
    )
    if (
        validation.get("id") != "validation"
        or validation.get("continue-on-error") != "true"
        or validation.get("if") != "steps.baseline.outcome == 'success'"
    ):
        raise HarnessError("validator step is missing, advisory, or does not generate the report")

    fallback_index, fallback = _named_step(steps, "기준 실패 보고서 생성")
    _require_run(
        fallback,
        ("mkdir -p .ai-runtime/reports", ".ai-runtime/reports/ai-harness-report.json", "printf"),
        "fallback report step",
    )
    if fallback.get("if") != "always()":
        raise HarnessError("fallback report step must run after every baseline/test/validator outcome")

    artifact_index, artifact = _named_step(steps, "본문 없는 검증 보고서 보존")
    artifact_with = artifact.get("with")
    if (
        artifact.get("if") != "always()"
        or artifact.get("uses") != "actions/upload-artifact@v4"
        or not isinstance(artifact_with, dict)
        or artifact_with.get("path") != ".ai-runtime/reports/ai-harness-report.json"
        or artifact_with.get("retention-days") != "7"
        or artifact_with.get("if-no-files-found") != "error"
    ):
        raise HarnessError("body-free report artifact step is incomplete")

    enforcement_index, enforcement = _named_step(steps, "정책 검증 실패 반영")
    enforcement_if = enforcement.get("if", "")
    if not all(
        fragment in enforcement_if
        for fragment in (
            "always()",
            "steps.baseline.outcome != 'success'",
            "steps.unit-tests.outcome != 'success'",
            "steps.validation.outcome != 'success'",
        )
    ) or _shell_scalar(str(enforcement.get("run", ""))) != "exit 1":
        raise HarnessError("final enforcement step must fail for unit-test or validator failure")
    if not baseline_index < unit_index < validation_index < fallback_index < artifact_index < enforcement_index:
        raise HarnessError("harness-check steps are in an unsafe order")


def validate_ai_workflow_text(text: str) -> None:
    if not re.search(r"(?m)^on:\s*$", text):
        raise HarnessError("AI harness workflow has no on trigger")
    if not re.search(r"(?m)^  pull_request:\s*$", text):
        raise HarnessError("AI harness pull_request trigger is missing")
    _validate_dispatch_input(text)
    if "HEAD^" in text:
        raise HarnessError("workflow must not guess workflow_dispatch baseline from HEAD^")
    _validate_harness_job(_job_block(text, "harness-check"), trigger_kind="pull_request")


def validate_trusted_pr_workflow_text(text: str) -> None:
    if not re.search(r"(?m)^  pull_request_target:\s*$", text):
        raise HarnessError("trusted PR workflow must use pull_request_target")
    permissions = re.search(r"(?m)^permissions:[ \t]*\n((?:  [^\n]+\n)+)\njobs:", text)
    if not permissions or permissions.group(1).strip() != "contents: read":
        raise HarnessError("trusted PR workflow permissions must be exactly contents: read")
    if "secrets." in text or "permissions: write" in text:
        raise HarnessError("trusted PR workflow cannot use secrets or write permissions")
    job = _job_block(text, "trusted-harness-check")
    if re.search(r"(?m)^    (?:if:\s*false|continue-on-error:\s*true)\s*$", job):
        raise HarnessError("trusted PR job cannot be disabled or advisory")
    steps = _workflow_steps(job)
    _, base_checkout = _named_step(steps, "신뢰 기준 코드 체크아웃")
    _, head_checkout = _named_step(steps, "PR head 정적 검사 대상 체크아웃")
    for step, expected_path, expected_ref in (
        (base_checkout, "trusted", "${{ github.event.pull_request.base.sha }}"),
        (head_checkout, "candidate", "${{ github.event.pull_request.head.sha }}"),
    ):
        values = step.get("with")
        if step.get("uses") != "actions/checkout@v4" or not isinstance(values, dict):
            raise HarnessError("trusted PR workflow checkout structure is invalid")
        if values.get("path") != expected_path or values.get("ref") != expected_ref or values.get("fetch-depth") != "0":
            raise HarnessError("trusted PR workflow checkout ref/path is invalid")
        if values.get("persist-credentials") != "false":
            raise HarnessError("trusted PR workflow checkouts must not persist credentials")
    baseline_index, baseline = _named_step(steps, "검증 기준 커밋 결정")
    _require_run(
        baseline,
        (
            'base_commit="${{ github.event.pull_request.base.sha }}"',
            'git cat-file -e "${base_commit}^{commit}"',
            'git merge-base --is-ancestor "$base_commit" HEAD',
            'echo "base=$base_commit" >> "$GITHUB_OUTPUT"',
        ),
        "trusted baseline step",
    )
    if baseline.get("id") != "baseline" or baseline.get("continue-on-error") != "true" or baseline.get("working-directory") != "candidate":
        raise HarnessError("trusted baseline step must capture failures in the candidate checkout")
    validation_index, validation = _named_step(steps, "신뢰 기준 validator로 PR 정적 검증")
    _require_run(
        validation,
        (
            "python3 scripts/ai_harness/validate.py --mode trusted-pr",
            '--root "$GITHUB_WORKSPACE/candidate"',
            '--base "${{ steps.baseline.outputs.base }}"',
            "--report .ai-runtime/reports/ai-harness-report.json",
        ),
        "trusted validator step",
    )
    if (
        validation.get("id") != "validation"
        or validation.get("continue-on-error") != "true"
        or validation.get("if") != "steps.baseline.outcome == 'success'"
        or validation.get("working-directory") != "trusted"
    ):
        raise HarnessError("trusted validator must execute from the base checkout")
    if "candidate/scripts/" in _shell_scalar(str(validation.get("run", ""))):
        raise HarnessError("trusted PR workflow cannot execute PR Python or tests")
    fallback_index, fallback = _named_step(steps, "기준 실패 보고서 생성")
    _require_run(
        fallback,
        ("mkdir -p candidate/.ai-runtime/reports", "candidate/.ai-runtime/reports/ai-harness-report.json", "printf"),
        "trusted fallback report step",
    )
    if fallback.get("if") != "always()":
        raise HarnessError("trusted fallback report must always run")
    artifact_index, artifact = _named_step(steps, "본문 없는 신뢰 검증 보고서 보존")
    values = artifact.get("with")
    if (
        artifact.get("if") != "always()"
        or artifact.get("uses") != "actions/upload-artifact@v4"
        or not isinstance(values, dict)
        or values.get("path") != "candidate/.ai-runtime/reports/ai-harness-report.json"
        or values.get("retention-days") != "7"
        or values.get("if-no-files-found") != "error"
    ):
        raise HarnessError("trusted report artifact step is incomplete")
    enforcement_index, enforcement = _named_step(steps, "신뢰 검증 실패 반영")
    enforcement_if = enforcement.get("if", "")
    if (
        "always()" not in enforcement_if
        or "steps.baseline.outcome != 'success'" not in enforcement_if
        or "steps.validation.outcome != 'success'" not in enforcement_if
        or _shell_scalar(str(enforcement.get("run", ""))) != "exit 1"
    ):
        raise HarnessError("trusted PR final enforcement is incomplete")
    if not baseline_index < validation_index < fallback_index < artifact_index < enforcement_index:
        raise HarnessError("trusted PR steps are in an unsafe order")


def _needs_values(job_block: str) -> set[str]:
    bracket = re.search(r"(?m)^    needs:\s*\[([^]]+)\]\s*$", job_block)
    if bracket:
        return {item.strip().strip("'\"") for item in bracket.group(1).split(",")}
    scalar = re.search(r"(?m)^    needs:\s*([A-Za-z0-9_-]+)\s*$", job_block)
    return {scalar.group(1)} if scalar else set()


def validate_deploy_workflow_text(text: str) -> None:
    if 'branches: ["main"]' not in text:
        raise HarnessError("deploy workflow triggers changed")
    _validate_dispatch_input(text)
    if "HEAD^" in text:
        raise HarnessError("deploy workflow must not guess workflow_dispatch baseline from HEAD^")
    harness = _job_block(text, "harness-check")
    _validate_harness_job(harness, trigger_kind="push")
    build = _job_block(text, "build-and-push")
    deploy = _job_block(text, "deploy")
    if _needs_values(build) != {"harness-check"}:
        raise HarnessError("build-and-push must need harness-check")
    if _needs_values(deploy) != {"harness-check", "build-and-push"}:
        raise HarnessError("deploy must need harness-check and build-and-push")
    forbidden = ("docker/login-action", "docker/build-push-action", "ssh ", "scp ", "secrets.")
    if any(item in harness for item in forbidden):
        raise HarnessError("harness-check job must not access registry, SSH, deployment, or secrets")


def validate_workflows(root: Path) -> None:
    validate_ai_workflow_text((root / ".github/workflows/ai-harness-check.yml").read_text(encoding="utf-8"))
    validate_trusted_pr_workflow_text(
        (root / ".github/workflows/ai-harness-trusted-pr.yml").read_text(encoding="utf-8")
    )
    validate_deploy_workflow_text((root / ".github/workflows/deploy-frontend.yml").read_text(encoding="utf-8"))


def validate_runtime(root: Path) -> None:
    gitignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    if "/.ai-runtime/" not in gitignore:
        raise HarnessError(".ai-runtime is not ignored at repository root")
    tracked = str(git_output(root, "ls-files", ".ai-runtime/**")).strip()
    if tracked:
        raise HarnessError("runtime files are tracked by Git")


def validate_package(root: Path) -> None:
    package = read_json(root / "package.json")
    scripts = package.get("scripts", {})
    expected_test = "python3 -m unittest discover -s scripts/ai_harness/tests -p 'test_*.py'"
    if scripts.get("ai:harness:test") != expected_test:
        raise HarnessError("package ai:harness:test script mismatch")
    check = scripts.get("ai:harness:check", "")
    if "npm run ai:harness:test" not in check or "scripts/ai_harness/validate.py" not in check:
        raise HarnessError("package ai:harness:check script mismatch")


def select_attestation(root: Path, base_commit: str) -> Path:
    matches: list[Path] = []
    directory = root / ".agents/ai-harness/attestations"
    if directory.is_symlink():
        raise HarnessError("attestation directory cannot be a symlink")
    for path in sorted(directory.glob("*.json")):
        relative = path.relative_to(root).as_posix()
        safe_path = attestation_path(root, relative)
        value = read_json(safe_path)
        if isinstance(value, dict) and value.get("base_commit") == base_commit:
            matches.append(safe_path)
    if len(matches) != 1:
        raise HarnessError(f"expected one attestation for baseline, found {len(matches)}")
    return matches[0]


def validate_current_attestation(root: Path, base_commit: str, mode: str) -> None:
    path = select_attestation(root, base_commit)
    policy = load_policy(root)
    rerun_ids: set[str] | None = None
    if mode == "trusted-pr":
        rerun_ids = {
            command_id
            for command_id, config in policy["verification"]["commands"].items()
            if config.get("trusted_pr_safe") is True
        }
    validate_attestation(
        read_json(path),
        root=root,
        base_commit=base_commit,
        rerun_commands=mode in ("ci", "trusted-pr"),
        rerun_command_ids=rerun_ids,
    )


def resolve_base(root: Path, explicit: str | None) -> str:
    candidate = explicit or os.environ.get("AI_HARNESS_BASE_COMMIT")
    if candidate:
        if not HEX_40.fullmatch(candidate):
            raise HarnessError("validation base must be a 40-character lowercase commit id")
        git_output(root, "cat-file", "-e", f"{candidate}^{{commit}}")
        git_output(root, "merge-base", "--is-ancestor", candidate, "HEAD")
        return candidate
    head = git_commit(root)
    dirty = str(git_output(root, "status", "--porcelain", "--untracked-files=all")).strip()
    if dirty and head == INSTALLATION_BASE_COMMIT:
        return INSTALLATION_BASE_COMMIT
    if dirty:
        return head
    raise HarnessError("clean local validation requires --base or AI_HARNESS_BASE_COMMIT; HEAD^ is never guessed")


@dataclass
class ValidationReport:
    mode: str
    base_commit: str
    checks: list[dict[str, str]] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def run(self, name: str, function: Callable[[], None]) -> None:
        try:
            function()
            self.checks.append({"name": name, "status": "passed"})
        except Exception as exc:  # Report every independent control in one run.
            self.checks.append({"name": name, "status": "failed"})
            self.errors.append((name, str(exc)))

    def body_free_json(self) -> dict[str, Any]:
        exit_status = 1 if self.errors else 0
        return {
            "schema_version": "1.0",
            "generated_at": utc_timestamp(),
            "mode": self.mode,
            "base_commit": self.base_commit,
            "status": "failed" if self.errors else "passed",
            "exit_status": exit_status,
            "checks": self.checks,
            "failed_check_names": [name for name, _ in self.errors],
        }


def run_validation(root: Path, mode: str, base_commit: str) -> ValidationReport:
    policy = load_policy(root)
    report = ValidationReport(mode=mode, base_commit=base_commit)
    report.run("python-version", lambda: (_ for _ in ()).throw(HarnessError("Python 3.11+ required")) if sys.version_info < (3, 11) else None)
    report.run("required-files", lambda: validate_required_files(root))
    report.run("json-toml", lambda: validate_json_toml(root))
    report.run("policy-constants", lambda: validate_policy(policy))
    report.run("integrity-digests", lambda: validate_integrity(root))
    report.run("role-contracts", lambda: validate_roles(root, policy))
    report.run("prompt-manifest", lambda: validate_prompt_manifest(root, policy))
    report.run("schemas", lambda: validate_schemas(root))
    report.run("hook-allowlist", lambda: validate_hooks(root, policy))
    report.run("runtime-untracked", lambda: validate_runtime(root))
    report.run("package-scripts", lambda: validate_package(root))
    report.run("workflow-yaml", lambda: validate_workflows(root))
    report.run("workflow-attestation", lambda: validate_current_attestation(root, base_commit, mode))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the repository AI harness and workflow attestation")
    parser.add_argument("--mode", choices=("local", "ci", "trusted-pr"), required=True)
    parser.add_argument("--base")
    parser.add_argument("--report", required=True)
    parser.add_argument("--root", default=str(REPO_ROOT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    report_path: Path | None = None
    try:
        policy = load_policy(root)
        prune_runtime(root, policy)
        report_path = resolve_runtime_path(root, args.report, "reports")
        base_commit = resolve_base(root, args.base)
        report = run_validation(root, args.mode, base_commit)
    except Exception as exc:
        base_commit = args.base or "unresolved"
        report = ValidationReport(mode=args.mode, base_commit=base_commit)
        report.checks.append({"name": "bootstrap", "status": "failed"})
        report.errors.append(("bootstrap", str(exc)))
    if report_path is None:
        print("[FAIL] report: unsafe or unresolved report output path", file=sys.stderr)
        return 1
    write_private_json(report_path, report.body_free_json())
    for name, detail in report.errors:
        print(f"[FAIL] {name}: {detail}", file=sys.stderr)
    if not report.errors:
        print(json.dumps(report.body_free_json(), sort_keys=True))
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
