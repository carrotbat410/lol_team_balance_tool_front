from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ai_harness.common import (  # noqa: E402
    HarnessError,
    POLICY_PATH,
    PROMPT_MANIFEST_PATH,
    REPO_ROOT,
    anonymous_id,
    canonical_json_bytes,
    ensure_private_directory,
    get_local_salt,
    git_commit,
    load_policy,
    prune_runtime,
    read_json,
    read_stdin_json,
    sha256_file,
    utc_timestamp,
)


EVENT_METADATA = {
    "UserPromptSubmit": ("Coordinator", "intake", "submitted"),
    "SubagentStart": (None, None, "started"),
    "SubagentStop": (None, None, "completed"),
    "Stop": ("Coordinator", "finalize", "stopped"),
    "SessionEnd": ("Coordinator", "session", "ended"),
}
ROLE_NAMES = {
    "researcher": "Researcher",
    "planner": "Planner",
    "implementer": "Implementer",
    "reviewer": "Reviewer",
}


def _role_and_stage(payload: dict[str, Any], event: str) -> tuple[str, str, str]:
    role, stage, status = EVENT_METADATA[event]
    if event in ("SubagentStart", "SubagentStop"):
        raw_agent_type = payload.get("agent_type")
        normalized = raw_agent_type.casefold() if isinstance(raw_agent_type, str) else ""
        role = ROLE_NAMES.get(normalized, "Unknown")
        stage = normalized if normalized in ROLE_NAMES else "subagent"
    assert role is not None and stage is not None
    return role, stage, status


def _verification_exit_status(root: Path) -> int | None:
    report_path = root / ".ai-runtime/reports/ai-harness-report.json"
    if not report_path.is_file() or report_path.is_symlink():
        return None
    try:
        report = read_json(report_path)
    except HarnessError:
        return None
    value = report.get("exit_status") if isinstance(report, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def build_log_record(
    payload: Any,
    *,
    root: Path = REPO_ROOT,
    salt: bytes | None = None,
    timestamp: str | None = None,
    commit: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HarnessError("hook payload must be an object")
    policy = load_policy(root)
    event = payload.get("hook_event_name")
    if event not in EVENT_METADATA or event not in policy["hook"]["events"]:
        raise HarnessError("unsupported hook event")
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise HarnessError("hook payload has no session_id")
    raw_turn_id = payload.get("turn_id")
    if not isinstance(raw_turn_id, str) or not raw_turn_id:
        raw_turn_id = f"{session_id}:{event}"
    role, stage, status = _role_and_stage(payload, event)
    local_salt = salt if salt is not None else get_local_salt(root)
    record = {
        "schema_version": "1.0",
        "timestamp": timestamp or utc_timestamp(),
        "run_id": anonymous_id(local_salt, "run", session_id),
        "turn_id": anonymous_id(local_salt, "turn", raw_turn_id),
        "event": event,
        "role": role,
        "stage": stage,
        "status": status,
        "git_commit": commit or git_commit(root),
        "policy_digest": sha256_file(root / POLICY_PATH),
        "template_manifest_digest": sha256_file(root / PROMPT_MANIFEST_PATH),
        "verification_exit_status": _verification_exit_status(root),
    }
    allowed_fields = set(policy["hook"]["allowed_log_fields"])
    if set(record) != allowed_fields:
        raise HarnessError("logger field allowlist differs from policy")
    return record


def _select_log_path(log_dir: Path, date_stamp: str, line_size: int, max_bytes: int) -> Path:
    index = 0
    while True:
        suffix = "" if index == 0 else f".{index}"
        candidate = log_dir / f"lifecycle-{date_stamp}{suffix}.jsonl"
        if candidate.is_symlink():
            raise HarnessError(f"refusing symlinked lifecycle log: {candidate.name}")
        size = candidate.stat().st_size if candidate.exists() else 0
        if size + line_size <= max_bytes:
            return candidate
        index += 1


def append_log_record(
    record: dict[str, Any],
    *,
    root: Path = REPO_ROOT,
    now: float | None = None,
) -> Path:
    policy = load_policy(root)
    runtime_policy = policy["runtime"]
    log_dir = root / runtime_policy["root"] / "logs"
    ensure_private_directory(log_dir, int(runtime_policy["directory_mode"], 8))
    prune_runtime(root, policy, now=now)
    line = canonical_json_bytes(record) + b"\n"
    if len(line) > int(runtime_policy["max_jsonl_bytes"]):
        raise HarnessError("one lifecycle record exceeds the rotation limit")
    date_stamp = record["timestamp"][:10].replace("-", "")
    path = _select_log_path(log_dir, date_stamp, len(line), int(runtime_policy["max_jsonl_bytes"]))
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, int(runtime_policy["file_mode"], 8))
    try:
        os.fchmod(fd, int(runtime_policy["file_mode"], 8))
        os.write(fd, line)
    finally:
        os.close(fd)
    return path


def main() -> int:
    try:
        payload = read_stdin_json()
        append_log_record(build_log_record(payload))
        # Stop and SubagentStop require JSON stdout; an empty object is valid for every configured event.
        print(json.dumps({}))
        return 0
    except HarnessError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
