from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ai_harness.common import (  # noqa: E402
    HEX_40,
    HEX_64,
    INSTALLATION_BASE_COMMIT,
    INTEGRITY_MANIFEST_PATH,
    POLICY_PATH,
    PROMPT_MANIFEST_PATH,
    REPO_ROOT,
    HarnessError,
    anonymous_id,
    atomic_write_json,
    canonical_json_bytes,
    compute_task_diff_digest,
    compute_task_diff_snapshot,
    get_local_salt,
    load_policy,
    prune_runtime,
    read_json,
    reject_forbidden_keys,
    resolve_repo_relative_path,
    resolve_runtime_path,
    sanitize_value,
    sha256_file,
    sha256_json,
    validate_bootstrap_changed_paths,
    validate_scope_paths,
    path_matches_scope,
    write_private_json,
)
from scripts.ai_harness.prompt_history import verify_record  # noqa: E402


ATTESTATION_DIRECTORY = ".agents/ai-harness/attestations"
ATTESTATION_KEYS = {
    "schema_version",
    "kind",
    "attestation_id",
    "base_commit",
    "task_id",
    "task_diff_digest",
    "policy_digest",
    "prompt_manifest_digest",
    "integrity_manifest_digest",
    "approved_scope_digest",
    "approved_scope_paths",
    "approved_scope_paths_digest",
    "events",
    "reviewer_packet",
    "verification",
    "bootstrap",
}
EVENT_KEYS = {
    "sequence",
    "stage",
    "status",
    "context_digest",
    "scope_digest",
    "scope_paths_digest",
    "prompt_scope_digest",
    "task_diff_digest",
    "round",
}
PACKET_ATTESTATION_KEYS = {"field_digests", "packet_digest", "task_diff_digest"}
VERIFICATION_KEYS = {
    "command_id",
    "argv_digest",
    "exit_status",
    "result_digest",
    "base_commit",
    "task_diff_digest",
}
ROLE_STAGES = {"researcher", "planner", "implementer", "reviewer"}
PACKET_CONTENT_MARKER_RE = re.compile(
    r"(?i)(?:\b(?:rationale|command[_ -]?output|transcript|runtime[_ -]?logs?)\s*[:=]|\.ai-runtime/)"
)
SOURCE_SYMBOL_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_.-]*|[1-9][0-9]*)$")


def validate_policy_constants(policy: dict[str, Any]) -> None:
    if policy.get("installation_base_commit") != INSTALLATION_BASE_COMMIT:
        raise HarnessError("policy installation baseline differs from the compiled installation baseline")
    bootstrap = policy.get("bootstrap", {})
    if bootstrap.get("base_commit") != INSTALLATION_BASE_COMMIT:
        raise HarnessError("policy bootstrap baseline differs from the compiled installation baseline")


def _reject_packet_content_markers(value: Any, path: str = "$.reviewer_packet") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_packet_content_markers(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_packet_content_markers(child, f"{path}[{index}]")
    elif isinstance(value, str) and PACKET_CONTENT_MARKER_RE.search(value):
        raise HarnessError(f"Reviewer packet embeds forbidden implementation or runtime content at {path}")


def _validate_source_reference(root: Path, reference: Any) -> str:
    if not isinstance(reference, str) or not reference:
        raise HarnessError("final_source_references entries must be non-empty strings")
    path_text = reference
    if "#" in reference:
        path_text, symbol = reference.rsplit("#", 1)
        if not SOURCE_SYMBOL_RE.fullmatch(symbol):
            raise HarnessError(f"invalid source symbol reference: {reference}")
    elif ":" in reference:
        possible_path, possible_symbol = reference.rsplit(":", 1)
        if SOURCE_SYMBOL_RE.fullmatch(possible_symbol):
            path_text = possible_path
        else:
            raise HarnessError(f"invalid source symbol reference: {reference}")
    if not path_text or "\\" in path_text:
        raise HarnessError(f"source reference must use a repository-relative POSIX path: {reference}")
    relative = Path(path_text)
    if relative.is_absolute() or ".." in relative.parts or any(part in ("", ".") for part in relative.parts):
        raise HarnessError(f"source reference escapes the repository: {reference}")
    if relative.parts[0] in (".ai-runtime", ".git"):
        raise HarnessError(f"source reference targets forbidden runtime metadata: {reference}")
    candidate = root.absolute() / relative
    current = root.absolute()
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise HarnessError(f"source reference traverses a symlink: {reference}")
    try:
        info = candidate.lstat()
    except FileNotFoundError as exc:
        raise HarnessError(f"source reference does not exist: {reference}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise HarnessError(f"source reference is not a regular file: {reference}")
    return reference


def _validate_reviewer_packet_shape(packet: dict[str, Any], policy: dict[str, Any], root: Path) -> None:
    if not isinstance(packet["original_request"], str) or not packet["original_request"].strip():
        raise HarnessError("Reviewer packet original_request must be a non-empty string")
    for key in ("acceptance_criteria", "review_rules"):
        value = packet[key]
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            raise HarnessError(f"Reviewer packet {key} must be a non-empty array of strings")
    references = packet["final_source_references"]
    if not isinstance(references, list) or not references:
        raise HarnessError("Reviewer packet final_source_references must be a non-empty array")
    for reference in references:
        _validate_source_reference(root, reference)
    verification = packet["verification"]
    if not isinstance(verification, list) or not verification:
        raise HarnessError("Reviewer packet verification must be a non-empty array")
    allowed_commands = set(policy["verification"]["commands"])
    seen_commands: set[str] = set()
    for item in verification:
        if not isinstance(item, dict) or set(item) != {"command_id", "status"}:
            raise HarnessError("Reviewer packet verification entries only allow command_id and status")
        command_id = item["command_id"]
        if command_id not in allowed_commands or command_id in seen_commands:
            raise HarnessError(f"Reviewer packet has an invalid or duplicate command_id: {command_id}")
        if item["status"] not in ("passed", "failed"):
            raise HarnessError(f"Reviewer packet has an invalid verification status: {command_id}")
        seen_commands.add(command_id)
    _reject_packet_content_markers(packet)


def canonical_reviewer_packet(
    raw_packet: Any,
    policy: dict[str, Any],
    *,
    root: Path,
    base_commit: str,
    allow_missing_task_diff: bool = False,
) -> dict[str, Any]:
    if not isinstance(raw_packet, dict):
        raise HarnessError("Reviewer packet must be an object")
    workflow = policy["workflow"]
    allowed = set(workflow["reviewer_packet_allowed_fields"])
    accepted_keys = [allowed]
    if allow_missing_task_diff:
        accepted_keys.append(allowed - {"task_diff"})
    if set(raw_packet) not in accepted_keys:
        extra = sorted(set(raw_packet) - allowed)
        missing = sorted(allowed - set(raw_packet))
        raise HarnessError(f"Reviewer packet fields invalid; extra={extra}, missing={missing}")
    forbidden = list(policy["prompt_history"]["forbidden_keys"]) + list(
        workflow["reviewer_packet_forbidden_fields"]
    )
    reject_forbidden_keys(raw_packet, forbidden, "$.reviewer_packet")
    sanitized, redactions = sanitize_value(raw_packet)
    if sanitized != raw_packet or redactions:
        raise HarnessError("Reviewer packet contains secret or PII; prepare and deliver one exact sanitized copy")
    packet = dict(raw_packet)
    _validate_reviewer_packet_shape(packet, policy, root)
    expected_task_diff = compute_task_diff_snapshot(root, base_commit)
    if "task_diff" not in packet:
        packet["task_diff"] = expected_task_diff
    elif packet["task_diff"] != expected_task_diff:
        raise HarnessError("Reviewer packet task_diff does not match the current task diff")
    return packet


def reviewer_packet_attestation(packet: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    allowed = set(policy["workflow"]["reviewer_packet_allowed_fields"])
    if set(packet) != allowed:
        raise HarnessError("Reviewer packet differs from the field allowlist")
    task_diff = packet["task_diff"]
    if not isinstance(task_diff, dict):
        raise HarnessError("Reviewer packet task_diff must be a canonical diff snapshot")
    task_diff_digest = sha256_json(task_diff)
    return {
        "field_digests": {key: f"sha256:{sha256_json(packet[key])}" for key in sorted(allowed)},
        "packet_digest": sha256_json(packet),
        "task_diff_digest": task_diff_digest,
    }


def validate_packet_attestation(packet: Any, policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, dict) or set(packet) != PACKET_ATTESTATION_KEYS:
        raise HarnessError("attested Reviewer packet metadata has an invalid schema")
    fields = packet["field_digests"]
    allowed = set(policy["workflow"]["reviewer_packet_allowed_fields"])
    if not isinstance(fields, dict) or set(fields) != allowed:
        raise HarnessError("attested Reviewer packet fields differ from the allowlist")
    for key, value in fields.items():
        if not isinstance(value, str) or not value.startswith("sha256:") or not HEX_64.fullmatch(value[7:]):
            raise HarnessError(f"Reviewer packet field is not a SHA-256 digest: {key}")
    if not HEX_64.fullmatch(packet["packet_digest"] if isinstance(packet["packet_digest"], str) else ""):
        raise HarnessError("invalid Reviewer packet digest")
    if not HEX_64.fullmatch(
        packet["task_diff_digest"] if isinstance(packet["task_diff_digest"], str) else ""
    ):
        raise HarnessError("invalid Reviewer packet task diff digest")
    if fields["task_diff"] != f"sha256:{packet['task_diff_digest']}":
        raise HarnessError("Reviewer packet task_diff field digest is inconsistent")
    return packet


def _validate_common(attestation: Any, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(attestation, dict):
        raise HarnessError("attestation must be an object")
    if set(attestation) != ATTESTATION_KEYS:
        raise HarnessError(f"attestation keys differ from schema: {sorted(set(attestation) ^ ATTESTATION_KEYS)}")
    if attestation["schema_version"] != "1.0":
        raise HarnessError("attestation schema_version must be 1.0")
    if attestation["kind"] not in ("workflow", "bootstrap"):
        raise HarnessError("attestation kind must be workflow or bootstrap")
    if (
        not isinstance(attestation["attestation_id"], str)
        or len(attestation["attestation_id"]) != 24
        or any(character not in "0123456789abcdef" for character in attestation["attestation_id"])
    ):
        raise HarnessError("invalid attestation_id")
    if not HEX_40.fullmatch(attestation["base_commit"] if isinstance(attestation["base_commit"], str) else ""):
        raise HarnessError("invalid attestation base_commit")
    for key in (
        "task_diff_digest",
        "policy_digest",
        "prompt_manifest_digest",
        "integrity_manifest_digest",
    ):
        if not HEX_64.fullmatch(attestation[key] if isinstance(attestation[key], str) else ""):
            raise HarnessError(f"invalid {key}")
    if attestation["approved_scope_digest"] is not None and not HEX_64.fullmatch(
        attestation["approved_scope_digest"] if isinstance(attestation["approved_scope_digest"], str) else ""
    ):
        raise HarnessError("invalid approved_scope_digest")
    if attestation["approved_scope_paths_digest"] is not None and not HEX_64.fullmatch(
        attestation["approved_scope_paths_digest"]
        if isinstance(attestation["approved_scope_paths_digest"], str)
        else ""
    ):
        raise HarnessError("invalid approved_scope_paths_digest")
    if attestation["approved_scope_paths"]:
        normalized_scope_paths = validate_scope_paths(attestation["approved_scope_paths"])
        if normalized_scope_paths != attestation["approved_scope_paths"]:
            raise HarnessError("approved scope paths are not canonical")
        if attestation["approved_scope_paths_digest"] != sha256_json(normalized_scope_paths):
            raise HarnessError("approved scope paths digest mismatch")
    elif attestation["approved_scope_paths_digest"] is not None:
        raise HarnessError("empty approved scope paths cannot have a digest")
    policy = load_policy(root)
    validate_policy_constants(policy)
    if attestation["policy_digest"] != sha256_file(root / POLICY_PATH):
        raise HarnessError("stale attestation policy digest")
    if attestation["prompt_manifest_digest"] != sha256_file(root / PROMPT_MANIFEST_PATH):
        raise HarnessError("stale attestation prompt manifest digest")
    if attestation["integrity_manifest_digest"] != sha256_file(root / INTEGRITY_MANIFEST_PATH):
        raise HarnessError("stale attestation integrity manifest digest")
    if not isinstance(attestation["events"], list) or not isinstance(attestation["verification"], list):
        raise HarnessError("attestation events and verification must be arrays")
    return attestation, policy


def _verification_argv(policy: dict[str, Any], command_id: str, base_commit: str) -> list[str]:
    config = policy["verification"]["commands"].get(command_id)
    if not isinstance(config, dict) or not isinstance(config.get("argv"), list):
        raise HarnessError(f"unknown verification command id: {command_id}")
    argv = [item.replace("{base_commit}", base_commit) for item in config["argv"]]
    if not argv or not all(isinstance(item, str) and item for item in argv):
        raise HarnessError(f"invalid argv for verification command id: {command_id}")
    return argv


def _required_verification_ids(policy: dict[str, Any], kind: str) -> set[str]:
    profiles = policy["verification"]["profiles"]
    required = profiles.get(kind)
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise HarnessError(f"missing verification profile for {kind}")
    return set(required)


def validate_verification(
    attestation: dict[str, Any],
    policy: dict[str, Any],
    *,
    require_complete: bool,
    current_task_diff_digest: str,
) -> None:
    required_ids = _required_verification_ids(policy, attestation["kind"])
    seen: set[str] = set()
    for item in attestation["verification"]:
        if not isinstance(item, dict) or set(item) != VERIFICATION_KEYS:
            raise HarnessError("invalid verification attestation entry")
        command_id = item["command_id"]
        if command_id not in required_ids:
            raise HarnessError(f"unapproved verification command id: {command_id}")
        if command_id in seen:
            raise HarnessError(f"duplicate verification command id: {command_id}")
        seen.add(command_id)
        argv = _verification_argv(policy, command_id, attestation["base_commit"])
        if item["argv_digest"] != sha256_json(argv):
            raise HarnessError(f"verification argv digest mismatch: {command_id}")
        if item["base_commit"] != attestation["base_commit"]:
            raise HarnessError(f"verification base commit mismatch: {command_id}")
        if item["task_diff_digest"] != current_task_diff_digest:
            raise HarnessError(f"verification predates the final task diff: {command_id}")
        if item["exit_status"] != 0:
            raise HarnessError(f"verification did not succeed: {command_id}")
        expected_result_digest = sha256_json(
            {
                "command_id": command_id,
                "argv_digest": item["argv_digest"],
                "exit_status": item["exit_status"],
                "base_commit": item["base_commit"],
                "task_diff_digest": item["task_diff_digest"],
            }
        )
        if item["result_digest"] != expected_result_digest:
            raise HarnessError(f"verification result digest mismatch: {command_id}")
    if require_complete and seen != required_ids:
        raise HarnessError(f"missing verification command ids: {sorted(required_ids - seen)}")


def run_verification_command(
    attestation: dict[str, Any], command_id: str, *, root: Path, policy: dict[str, Any]
) -> dict[str, Any]:
    if command_id not in _required_verification_ids(policy, attestation["kind"]):
        raise HarnessError(f"command id is not required for {attestation['kind']}: {command_id}")
    argv = _verification_argv(policy, command_id, attestation["base_commit"])
    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise HarnessError(f"could not execute verification command id {command_id}: {exc}") from exc
    status = completed.returncode
    config = policy["verification"]["commands"][command_id]
    if config.get("stdout_must_be_empty") and completed.stdout.strip():
        status = 1
    task_diff_digest = compute_task_diff_digest(root, attestation["base_commit"])
    argv_digest = sha256_json(argv)
    record = {
        "command_id": command_id,
        "argv_digest": argv_digest,
        "exit_status": status,
        "result_digest": "",
        "base_commit": attestation["base_commit"],
        "task_diff_digest": task_diff_digest,
    }
    record["result_digest"] = sha256_json(
        {
            "command_id": command_id,
            "argv_digest": argv_digest,
            "exit_status": status,
            "base_commit": attestation["base_commit"],
            "task_diff_digest": task_diff_digest,
        }
    )
    return record


def rerun_verification(
    attestation: dict[str, Any],
    policy: dict[str, Any],
    *,
    root: Path,
    command_ids: set[str] | None = None,
) -> None:
    records = {item["command_id"]: item for item in attestation["verification"]}
    selected = command_ids or _required_verification_ids(policy, attestation["kind"])
    if not selected <= set(records):
        raise HarnessError(f"cannot rerun missing verification records: {sorted(selected - set(records))}")
    for command_id in sorted(selected):
        actual = run_verification_command(attestation, command_id, root=root, policy=policy)
        if actual != records[command_id]:
            raise HarnessError(f"CI re-execution differs from verification record: {command_id}")


def _event(attestation: dict[str, Any], index: int, stage: str, status: str, round_number: int) -> dict[str, Any]:
    events = attestation["events"]
    if index >= len(events):
        raise HarnessError(f"workflow is missing {stage} event")
    event = events[index]
    if not isinstance(event, dict) or set(event) != EVENT_KEYS:
        raise HarnessError(f"invalid event schema at sequence {index + 1}")
    if event["sequence"] != index + 1:
        raise HarnessError("workflow event sequence is not contiguous")
    if event["stage"] != stage or event["status"] != status or event["round"] != round_number:
        raise HarnessError(f"unexpected workflow event at sequence {index + 1}")
    return event


def _validate_event_fields(event: dict[str, Any], index: int) -> None:
    if set(event) != EVENT_KEYS or event.get("sequence") != index + 1:
        raise HarnessError(f"invalid event schema at sequence {index + 1}")
    if event.get("stage") not in ROLE_STAGES | {"human_approval"}:
        raise HarnessError(f"invalid workflow stage at sequence {index + 1}")
    if not HEX_64.fullmatch(event.get("context_digest") if isinstance(event.get("context_digest"), str) else ""):
        raise HarnessError(f"invalid context digest at sequence {index + 1}")
    for key in ("scope_digest", "scope_paths_digest", "prompt_scope_digest", "task_diff_digest"):
        value = event.get(key)
        if value is not None and not HEX_64.fullmatch(value if isinstance(value, str) else ""):
            raise HarnessError(f"invalid {key} at sequence {index + 1}")
    if not isinstance(event.get("round"), int) or event["round"] < 0:
        raise HarnessError(f"invalid round at sequence {index + 1}")


def validate_event_sequence(
    attestation: dict[str, Any],
    policy: dict[str, Any],
    *,
    require_complete: bool,
    expected_task_diff_digest: str,
) -> None:
    events = attestation["events"]
    if not events:
        if require_complete:
            raise HarnessError("workflow attestation has no stage events")
        return
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise HarnessError(f"invalid event at sequence {index + 1}")
        _validate_event_fields(event, index)

    expected_prefix = (
        ("researcher", "completed", 0),
        ("planner", "completed", 0),
        ("human_approval", "approved", 0),
        ("implementer", "completed", 0),
    )
    for index, expected in enumerate(expected_prefix):
        if index >= len(events):
            if require_complete:
                raise HarnessError(f"workflow is missing {expected[0]} event")
            return
        _event(attestation, index, *expected)

    current_scope = events[2]["scope_digest"]
    current_scope_paths_digest = events[2]["scope_paths_digest"]
    if current_scope is None or events[2]["context_digest"] != current_scope:
        raise HarnessError("human approval must attest the approved scope digest")
    if current_scope_paths_digest is None:
        raise HarnessError("human approval must attest structured scope paths")
    if events[3]["scope_digest"] != current_scope or events[3]["prompt_scope_digest"] != current_scope:
        raise HarnessError("Implementer prompt scope differs from the latest human-approved scope")
    if events[3]["scope_paths_digest"] != current_scope_paths_digest:
        raise HarnessError("Implementer prompt scope paths differ from the latest human approval")

    seen_context: dict[str, str] = {}
    for event in events:
        if event["stage"] == "human_approval":
            continue
        prior_stage = seen_context.get(event["context_digest"])
        if prior_stage is not None:
            raise HarnessError(f"workflow context digest reused by {prior_stage} and {event['stage']}")
        seen_context[event["context_digest"]] = event["stage"]

    index = 4
    round_number = 0
    final_review: dict[str, Any] | None = None
    while index < len(events):
        review = events[index]
        if review["stage"] != "reviewer" or review["round"] != round_number:
            raise HarnessError("Reviewer must follow each Implementer pass")
        if review["status"] not in ("approved", "changes_requested"):
            raise HarnessError("invalid Reviewer result")
        if review["scope_digest"] != current_scope or review["task_diff_digest"] is None:
            raise HarnessError("Reviewer event is not bound to the approved scope and task diff")
        if review["scope_paths_digest"] != current_scope_paths_digest:
            raise HarnessError("Reviewer event scope paths differ from the latest human approval")
        if review["prompt_scope_digest"] is not None:
            raise HarnessError("Reviewer event cannot claim an Implementer prompt scope")
        final_review = review
        index += 1
        if review["status"] == "approved" and index == len(events):
            break
        if round_number >= int(policy["workflow"]["fix_review_limit"]):
            raise HarnessError("fix-review limit exceeded")
        round_number += 1
        if index < len(events) and events[index]["stage"] == "human_approval":
            approval = events[index]
            if approval["status"] != "approved" or approval["round"] != round_number:
                raise HarnessError("invalid scope reapproval event")
            if approval["scope_digest"] is None or approval["context_digest"] != approval["scope_digest"]:
                raise HarnessError("scope reapproval has no canonical scope digest")
            current_scope = approval["scope_digest"]
            current_scope_paths_digest = approval["scope_paths_digest"]
            if current_scope_paths_digest is None:
                raise HarnessError("scope reapproval has no structured scope paths")
            index += 1
        if index >= len(events):
            if require_complete:
                raise HarnessError("Reviewer findings or post-review changes were not implemented")
            return
        implementer = events[index]
        if (
            implementer["stage"] != "implementer"
            or implementer["status"] != "completed"
            or implementer["round"] != round_number
        ):
            raise HarnessError("Reviewer findings or post-review changes must return to the Implementer")
        if implementer["scope_digest"] != current_scope or implementer["prompt_scope_digest"] != current_scope:
            raise HarnessError("Implementer prompt scope changed without human reapproval")
        if implementer["scope_paths_digest"] != current_scope_paths_digest:
            raise HarnessError("Implementer prompt scope paths changed without human reapproval")
        index += 1

    if require_complete and (final_review is None or final_review["status"] != "approved"):
        raise HarnessError("workflow has no final Reviewer approval")
    if attestation["approved_scope_digest"] != current_scope:
        raise HarnessError("attestation approved_scope_digest is stale")
    if attestation["approved_scope_paths_digest"] != current_scope_paths_digest:
        raise HarnessError("attestation approved_scope_paths_digest is stale")
    if final_review is not None:
        packet = validate_packet_attestation(attestation["reviewer_packet"], policy)
        if final_review["context_digest"] != packet["packet_digest"]:
            raise HarnessError("final Reviewer context is not the exact blind packet digest")
        if final_review["task_diff_digest"] != packet["task_diff_digest"]:
            raise HarnessError("final Reviewer event and packet task diff digests differ")
        if packet["task_diff_digest"] != expected_task_diff_digest:
            raise HarnessError("source changed after the final blind Reviewer packet")


def validate_changed_paths_in_scope(snapshot: dict[str, Any], scope_paths: list[str]) -> None:
    normalized = validate_scope_paths(scope_paths)
    changes = snapshot.get("changes")
    if not isinstance(changes, list):
        raise HarnessError("task diff snapshot has no changes array")
    outside_scope = [
        item.get("path")
        for item in changes
        if not isinstance(item, dict)
        or not isinstance(item.get("path"), str)
        or not path_matches_scope(item["path"], normalized)
    ]
    if outside_scope:
        raise HarnessError(f"task diff contains paths outside human-approved scope: {outside_scope}")


def validate_attestation(
    attestation: Any,
    *,
    root: Path = REPO_ROOT,
    base_commit: str,
    require_complete: bool = True,
    check_diff: bool = True,
    rerun_commands: bool = False,
    rerun_command_ids: set[str] | None = None,
) -> dict[str, Any]:
    attestation, policy = _validate_common(attestation, root)
    if attestation["base_commit"] != base_commit:
        raise HarnessError("stale attestation base commit")
    current_snapshot = compute_task_diff_snapshot(root, base_commit) if check_diff else None
    current_digest = sha256_json(current_snapshot) if current_snapshot is not None else attestation["task_diff_digest"]
    if attestation["task_diff_digest"] != current_digest:
        raise HarnessError("stale attestation task diff digest")
    validate_verification(
        attestation,
        policy,
        require_complete=require_complete,
        current_task_diff_digest=current_digest,
    )
    if rerun_commands:
        rerun_verification(attestation, policy, root=root, command_ids=rerun_command_ids)
    if attestation["kind"] == "bootstrap":
        if base_commit != INSTALLATION_BASE_COMMIT:
            raise HarnessError("bootstrap attestation is forbidden for this baseline")
        if current_snapshot is not None:
            validate_bootstrap_changed_paths(current_snapshot)
        expected = {"installation_only": True, "retroactive_hook_logs": False}
        if attestation["bootstrap"] != expected:
            raise HarnessError("invalid bootstrap attestation metadata")
        if attestation["events"] or attestation["reviewer_packet"] is not None:
            raise HarnessError("bootstrap must not forge historical workflow or hook records")
        if (
            attestation["approved_scope_digest"] is not None
            or attestation["approved_scope_paths"] != []
            or attestation["approved_scope_paths_digest"] is not None
        ):
            raise HarnessError("bootstrap must not claim a historical approved scope")
    else:
        if attestation["bootstrap"] is not None:
            raise HarnessError("normal workflow attestation cannot contain bootstrap metadata")
        validate_event_sequence(
            attestation,
            policy,
            require_complete=require_complete,
            expected_task_diff_digest=current_digest,
        )
        scope_paths = validate_scope_paths(attestation["approved_scope_paths"])
        if current_snapshot is not None:
            validate_changed_paths_in_scope(current_snapshot, scope_paths)
    return {"kind": attestation["kind"], "base_commit": base_commit, "task_diff_digest": current_digest}


def new_attestation(task_id: str, base_commit: str, *, root: Path = REPO_ROOT) -> dict[str, Any]:
    if not HEX_40.fullmatch(base_commit):
        raise HarnessError("invalid base commit")
    if not task_id:
        raise HarnessError("task_id is required")
    policy = load_policy(root)
    validate_policy_constants(policy)
    salt = get_local_salt(root)
    return {
        "schema_version": "1.0",
        "kind": "workflow",
        "attestation_id": anonymous_id(salt, "attestation", f"{task_id}:{base_commit}"),
        "base_commit": base_commit,
        "task_id": anonymous_id(salt, "task", task_id),
        "task_diff_digest": compute_task_diff_digest(root, base_commit),
        "policy_digest": sha256_file(root / POLICY_PATH),
        "prompt_manifest_digest": sha256_file(root / PROMPT_MANIFEST_PATH),
        "integrity_manifest_digest": sha256_file(root / INTEGRITY_MANIFEST_PATH),
        "approved_scope_digest": None,
        "approved_scope_paths": [],
        "approved_scope_paths_digest": None,
        "events": [],
        "reviewer_packet": None,
        "verification": [],
        "bootstrap": None,
    }


def attestation_path(root: Path, value: str) -> Path:
    return resolve_repo_relative_path(root, value, ATTESTATION_DIRECTORY)


def write_attestation(root: Path, value: str, attestation: dict[str, Any]) -> Path:
    path = attestation_path(root, value)
    atomic_write_json(path, attestation, private=False)
    return path


def _load_attestation(root: Path, value: str) -> tuple[Path, dict[str, Any]]:
    path = attestation_path(root, value)
    return path, read_json(path)


def _context_from_record(
    path: str, expected_role: str, root: Path, base_commit: str
) -> tuple[str, str, str, list[str]]:
    record = read_json(Path(path))
    verified = verify_record(record, root=root)
    if verified["role"] != expected_role:
        raise HarnessError(f"prompt record role is not {expected_role}")
    envelope = record["envelope"]
    if envelope["base_commit"] != base_commit:
        raise HarnessError("prompt record base commit differs from the attestation")
    return (
        verified["rendered_prompt_sha256"],
        verified["approved_scope_digest"],
        verified["scope_paths_digest"],
        verified["scope_paths"],
    )


def command_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    attestation = new_attestation(args.task_id, args.base, root=root)
    write_attestation(root, args.output, attestation)
    print(json.dumps({"status": "ok", "attestation_id": attestation["attestation_id"]}, sort_keys=True))
    return 0


def command_prepare_reviewer_packet(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    policy = load_policy(root)
    prune_runtime(root, policy)
    packet = canonical_reviewer_packet(
        read_json(Path(args.input)),
        policy,
        root=root,
        base_commit=args.base,
        allow_missing_task_diff=True,
    )
    output = resolve_runtime_path(root, args.output, "reviewer-packets")
    write_private_json(output, packet)
    print(json.dumps({"status": "ok", "packet_digest": sha256_json(packet)}, sort_keys=True))
    return 0


def command_stage(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    path, attestation = _load_attestation(root, args.file)
    if attestation.get("kind") != "workflow":
        raise HarnessError("stages can only be added to a workflow attestation")
    policy = load_policy(root)
    round_number = args.round
    scope_digest = attestation.get("approved_scope_digest")
    scope_paths_digest = attestation.get("approved_scope_paths_digest")
    prompt_scope_digest = None
    task_diff_digest = None
    if args.stage == "human_approval":
        raw_scope = read_json(Path(args.scope))
        reject_forbidden_keys(raw_scope, policy["prompt_history"]["forbidden_keys"])
        sanitized_scope, _ = sanitize_value(raw_scope)
        if not isinstance(sanitized_scope, dict) or set(sanitized_scope) != {"approved_scope", "scope_paths"}:
            raise HarnessError("approved scope must contain only approved_scope and scope_paths")
        approved_scope = sanitized_scope["approved_scope"]
        if not isinstance(approved_scope, list) or not all(isinstance(item, str) for item in approved_scope):
            raise HarnessError("approved_scope must be a JSON array of strings")
        scope_paths = validate_scope_paths(sanitized_scope["scope_paths"])
        context_digest = scope_digest = sha256_json(
            {"approved_scope": approved_scope, "scope_paths": scope_paths}
        )
        scope_paths_digest = sha256_json(scope_paths)
        attestation["approved_scope_digest"] = scope_digest
        attestation["approved_scope_paths"] = scope_paths
        attestation["approved_scope_paths_digest"] = scope_paths_digest
        status = "approved"
    elif args.stage == "reviewer":
        packet = canonical_reviewer_packet(
            read_json(Path(args.packet)),
            policy,
            root=root,
            base_commit=attestation["base_commit"],
        )
        packet_metadata = reviewer_packet_attestation(packet, policy)
        context_digest = packet_metadata["packet_digest"]
        task_diff_digest = packet_metadata["task_diff_digest"]
        status = args.status
        if status not in ("approved", "changes_requested"):
            raise HarnessError("Reviewer status must be approved or changes_requested")
        attestation["reviewer_packet"] = packet_metadata
    else:
        context_digest, record_scope_digest, record_scope_paths_digest, record_scope_paths = _context_from_record(
            args.context_record,
            args.stage,
            root,
            attestation["base_commit"],
        )
        status = "completed"
        if args.stage in ("researcher", "planner"):
            scope_digest = None
            scope_paths_digest = None
        else:
            prompt_scope_digest = record_scope_digest
            if scope_digest is None:
                raise HarnessError("Implementer cannot run before human approval")
            if prompt_scope_digest != scope_digest:
                raise HarnessError("Implementer prompt approved_scope differs from the latest human approval")
            if record_scope_paths_digest != scope_paths_digest or record_scope_paths != attestation["approved_scope_paths"]:
                raise HarnessError("Implementer prompt scope_paths differ from the latest human approval")
    event = {
        "sequence": len(attestation["events"]) + 1,
        "stage": args.stage,
        "status": status,
        "context_digest": context_digest,
        "scope_digest": scope_digest,
        "scope_paths_digest": scope_paths_digest,
        "prompt_scope_digest": prompt_scope_digest,
        "task_diff_digest": task_diff_digest,
        "round": round_number,
    }
    attestation["events"].append(event)
    validate_event_sequence(
        attestation,
        policy,
        require_complete=False,
        expected_task_diff_digest=compute_task_diff_digest(root, attestation["base_commit"]),
    )
    atomic_write_json(path, attestation, private=False)
    print(json.dumps({"status": "ok", "sequence": event["sequence"]}, sort_keys=True))
    return 0


def command_run_verification(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    path, attestation = _load_attestation(root, args.file)
    policy = load_policy(root)
    record = run_verification_command(attestation, args.command_id, root=root, policy=policy)
    attestation["verification"] = [
        item for item in attestation["verification"] if item.get("command_id") != args.command_id
    ]
    attestation["verification"].append(record)
    attestation["verification"].sort(key=lambda item: item["command_id"])
    atomic_write_json(path, attestation, private=False)
    print(
        json.dumps(
            {"status": "ok" if record["exit_status"] == 0 else "failed", "command_id": args.command_id},
            sort_keys=True,
        )
    )
    return record["exit_status"]


def command_finalize(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    path, attestation = _load_attestation(root, args.file)
    attestation["task_diff_digest"] = compute_task_diff_digest(root, args.base)
    validate_attestation(attestation, root=root, base_commit=args.base, require_complete=True)
    atomic_write_json(path, attestation, private=False)
    print(json.dumps({"status": "ok", "task_diff_digest": attestation["task_diff_digest"]}, sort_keys=True))
    return 0


def command_verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    _, attestation = _load_attestation(root, args.file)
    result = validate_attestation(attestation, root=root, base_commit=args.base)
    print(json.dumps({"status": "ok", **result}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and validate AI workflow attestations")
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--task-id", required=True)
    init.add_argument("--base", required=True)
    init.add_argument("--output", required=True)
    init.set_defaults(handler=command_init)

    packet = subparsers.add_parser("prepare-reviewer-packet")
    packet.add_argument("--input", required=True)
    packet.add_argument("--base", required=True)
    packet.add_argument("--output", required=True)
    packet.set_defaults(handler=command_prepare_reviewer_packet)

    stage = subparsers.add_parser("stage")
    stage.add_argument("--file", required=True)
    stage.add_argument(
        "--stage",
        required=True,
        choices=("researcher", "planner", "human_approval", "implementer", "reviewer"),
    )
    stage.add_argument("--status", default="approved")
    stage.add_argument("--round", type=int, default=0)
    stage.add_argument("--context-record")
    stage.add_argument("--scope")
    stage.add_argument("--packet")
    stage.set_defaults(handler=command_stage)

    verification = subparsers.add_parser("run-verification")
    verification.add_argument("--file", required=True)
    verification.add_argument("--command-id", required=True)
    verification.set_defaults(handler=command_run_verification)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--file", required=True)
    finalize.add_argument("--base", required=True)
    finalize.set_defaults(handler=command_finalize)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--file", required=True)
    verify.add_argument("--base", required=True)
    verify.set_defaults(handler=command_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return args.handler(args)
    except (HarnessError, TypeError, FileNotFoundError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
