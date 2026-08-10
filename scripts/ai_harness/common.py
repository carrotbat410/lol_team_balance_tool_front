from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLATION_BASE_COMMIT = "5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773"
POLICY_PATH = Path(".agents/ai-harness/policy.json")
PROMPT_MANIFEST_PATH = Path(".agents/prompts/manifest.json")
INTEGRITY_MANIFEST_PATH = Path(".agents/ai-harness/integrity-manifest.json")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
REVIEWER_PACKET_MAX_BYTES = 2 * 1024 * 1024

ENVELOPE_REQUIRED = {
    "schema_version",
    "task_id",
    "original_request",
    "acceptance_criteria",
    "base_commit",
    "approved_scope",
    "scope_paths",
    "constraints",
}
ENVELOPE_OPTIONAL = {"repository", "source_references"}

BOOTSTRAP_ALLOWED_PREFIXES = (
    ".agents/ai-harness/",
    ".agents/prompts/",
    "scripts/ai_harness/",
)
BOOTSTRAP_ALLOWED_FILES = {
    ".agents/skills/lol-ai-workflow/SKILL.md",
    ".claude/rules/verification.md",
    ".claude/rules/workflow.md",
    ".codex/config.toml",
    ".codex/hooks.json",
    ".github/workflows/ai-harness-check.yml",
    ".github/workflows/ai-harness-trusted-pr.yml",
    ".github/workflows/deploy-frontend.yml",
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "docs/ai-harness.md",
    "package.json",
}

PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
SECRET_KEY_PATTERN = (
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"aws[_-]?secret[_-]?access[_-]?key|private[_-]?key|token|secret|password|passwd)"
)
SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?ix)"
    rf"(?P<prefix>[\"']?{SECRET_KEY_PATTERN}[\"']?\s*[:=]\s*)"
    rf"(?!(?:[\"'])?<redacted:)"
    rf"(?:"
    rf'\"(?P<double>(?:\\.|[^\"\\])*)\"'
    rf"|'(?P<single>(?:\\.|[^'\\])*)'"
    rf"|(?P<bare>(?!<redacted:)[^\s\r\n,;#}}]+)"
    rf")"
)
SECRET_LINE_ASSIGNMENT_RE = re.compile(
    rf"(?im)^(?P<prefix>\s*[\"']?{SECRET_KEY_PATTERN}[\"']?\s*[:=]\s*)"
    rf"(?P<value>(?![\"']?<redacted:)[^\r\n]+)$"
)
EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.I)
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?82[- .]?)?(?:0?1[016789])[- .]?\d{3,4}[- .]?\d{4}(?!\w)"
    r"|(?<!\w)\+\d{1,3}[- .]?\d{2,4}[- .]?\d{3,4}[- .]?\d{4}(?!\w)"
)
USER_PATH_PATTERNS = (
    re.compile(r"/Users/[^/\s]+(?:/[^\s,;:'\"<>]*)?"),
    re.compile(r"/home/[^/\s]+(?:/[^\s,;:'\"<>]*)?"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+(?:\\[^\s,;:'\"<>]*)?"),
)
SENSITIVE_FIELD_KEYS = {
    "apikey",
    "accesstoken",
    "authtoken",
    "clientsecret",
    "awssecretaccesskey",
    "privatekey",
    "token",
    "secret",
    "password",
    "passwd",
}

RUNTIME_ROOT = ".ai-runtime"
RUNTIME_RETENTION_DAYS = 30
RUNTIME_RETENTION_TARGETS = ("logs", "prompt-history", "reports", "reviewer-packets")


class HarnessError(ValueError):
    """A policy, schema, or integrity validation failure."""


@dataclass(frozen=True)
class TaskFileSnapshot:
    mode: str
    object_id: str | None
    content: bytes | None


@dataclass(frozen=True)
class TaskChangeSnapshot:
    path: str
    base: TaskFileSnapshot | None
    current: TaskFileSnapshot | None


@dataclass(frozen=True)
class CanonicalTaskSnapshot:
    base_commit: str
    changes: tuple[TaskChangeSnapshot, ...]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path, *, max_bytes: int = 2 * 1024 * 1024) -> Any:
    if path.stat().st_size > max_bytes:
        raise HarnessError(f"JSON input exceeds {max_bytes} bytes: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"invalid JSON: {path}: {exc}") from exc


def read_stdin_json(*, max_bytes: int = 1024 * 1024) -> Any:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(0, min(65536, max_bytes + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            raise HarnessError(f"stdin JSON exceeds {max_bytes} bytes")
    try:
        return json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"invalid stdin JSON: {exc}") from exc


def validate_runtime_policy(policy: Any, root: Path = REPO_ROOT) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise HarnessError("policy must be a JSON object")
    runtime = policy.get("runtime")
    if not isinstance(runtime, dict):
        raise HarnessError("runtime policy must be an object")
    if runtime.get("root") != RUNTIME_ROOT:
        raise HarnessError("runtime root differs from the compiled repository-local root")
    retention_days = runtime.get("retention_days")
    if (
        not isinstance(retention_days, int)
        or isinstance(retention_days, bool)
        or retention_days <= 0
        or retention_days != RUNTIME_RETENTION_DAYS
    ):
        raise HarnessError("runtime retention must be the compiled positive 30-day value")
    targets = runtime.get("retention_targets")
    if not isinstance(targets, list) or targets != list(RUNTIME_RETENTION_TARGETS):
        raise HarnessError("runtime retention targets differ from the compiled allowlist")

    runtime_path = root.absolute() / RUNTIME_ROOT
    if runtime_path.is_symlink():
        raise HarnessError("runtime root cannot be a symlink")
    if runtime_path.exists() and not runtime_path.is_dir():
        raise HarnessError("runtime root must be a directory")
    for relative in RUNTIME_RETENTION_TARGETS:
        target = runtime_path / relative
        if target.is_symlink():
            raise HarnessError(f"runtime retention target cannot be a symlink: {relative}")
        if target.exists() and not target.is_dir():
            raise HarnessError(f"runtime retention target must be a directory: {relative}")
    return runtime


def load_policy(root: Path = REPO_ROOT) -> dict[str, Any]:
    value = read_json(root / POLICY_PATH)
    if not isinstance(value, dict):
        raise HarnessError("policy must be a JSON object")
    validate_runtime_policy(value, root)
    return value


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


def reject_forbidden_keys(value: Any, forbidden_keys: Iterable[str], path: str = "$") -> None:
    forbidden = {normalize_key(key) for key in forbidden_keys}

    def walk(item: Any, current_path: str) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise HarnessError(f"non-string key at {current_path}")
                if normalize_key(key) in forbidden:
                    raise HarnessError(f"forbidden key at {current_path}.{key}")
                walk(child, f"{current_path}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{current_path}[{index}]")

    walk(value, path)


def reject_unsafe_controls(
    text: str,
    *,
    label: str,
    allow_newline: bool = False,
    allow_tab: bool = False,
) -> None:
    allowed = set()
    if allow_newline:
        allowed.add("\n")
    if allow_tab:
        allowed.add("\t")
    for character in text:
        codepoint = ord(character)
        if character in allowed:
            continue
        if codepoint <= 0x1F or 0x7F <= codepoint <= 0x9F:
            raise HarnessError(f"{label} contains unsafe control character U+{codepoint:04X}")


def _substitute(pattern: re.Pattern[str], text: str, replacement: str, label: str, counts: Counter[str]) -> str:
    def replace(_: re.Match[str]) -> str:
        counts[label] += 1
        return replacement

    return pattern.sub(replace, text)


def sanitize_text(text: str) -> tuple[str, Counter[str]]:
    counts: Counter[str] = Counter()
    sanitized = _substitute(PRIVATE_KEY_RE, text, "<redacted:private_key>", "private_key", counts)
    sanitized = _substitute(JWT_RE, sanitized, "<redacted:jwt>", "jwt", counts)

    def replace_line_assignment(match: re.Match[str]) -> str:
        counts["secret_assignment"] += 1
        return f'{match.group("prefix")}\"<redacted:secret_assignment>\"'

    sanitized = SECRET_LINE_ASSIGNMENT_RE.sub(replace_line_assignment, sanitized)

    def replace_assignment(match: re.Match[str]) -> str:
        counts["secret_assignment"] += 1
        return f'{match.group("prefix")}\"<redacted:secret_assignment>\"'

    sanitized = SECRET_ASSIGNMENT_RE.sub(replace_assignment, sanitized)
    sanitized = _substitute(EMAIL_RE, sanitized, "<redacted:email>", "email", counts)
    sanitized = _substitute(PHONE_RE, sanitized, "<redacted:phone>", "phone", counts)
    for pattern in USER_PATH_PATTERNS:
        sanitized = _substitute(
            pattern,
            sanitized,
            "<redacted:absolute_user_path>",
            "absolute_user_path",
            counts,
        )
    return sanitized, counts


def sanitize_value(value: Any) -> tuple[Any, Counter[str]]:
    counts: Counter[str] = Counter()

    def walk(item: Any) -> Any:
        if isinstance(item, str):
            sanitized, found = sanitize_text(item)
            counts.update(found)
            return sanitized
        if isinstance(item, list):
            return [walk(child) for child in item]
        if isinstance(item, dict):
            sanitized: dict[str, Any] = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    raise HarnessError("JSON object keys must be strings")
                if normalize_key(key) in SENSITIVE_FIELD_KEYS:
                    if child == "<redacted:secret_field>":
                        sanitized[key] = child
                    else:
                        counts["secret_field"] += 1
                        sanitized[key] = "<redacted:secret_field>"
                else:
                    sanitized[key] = walk(child)
            return sanitized
        if item is None or isinstance(item, (bool, int, float)):
            return item
        raise HarnessError(f"unsupported JSON value type: {type(item).__name__}")

    return walk(value), counts


def validate_envelope(value: Any, policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HarnessError("task envelope must be an object")
    reject_forbidden_keys(value, policy["prompt_history"]["forbidden_keys"])
    keys = set(value)
    missing = ENVELOPE_REQUIRED - keys
    extra = keys - ENVELOPE_REQUIRED - ENVELOPE_OPTIONAL
    if missing:
        raise HarnessError(f"task envelope missing keys: {sorted(missing)}")
    if extra:
        raise HarnessError(f"task envelope has unsupported keys: {sorted(extra)}")
    if value["schema_version"] != "1.0":
        raise HarnessError("task envelope schema_version must be 1.0")
    if not isinstance(value["task_id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", value["task_id"]):
        raise HarnessError("task_id must be normalized lowercase ASCII")
    if not isinstance(value["original_request"], str) or not value["original_request"].strip():
        raise HarnessError("original_request must be a non-empty string")
    reject_unsafe_controls(
        value["original_request"],
        label="original_request",
        allow_newline=True,
        allow_tab=True,
    )
    if not HEX_40.fullmatch(value["base_commit"] if isinstance(value["base_commit"], str) else ""):
        raise HarnessError("base_commit must be a 40-character lowercase Git object id")
    for key in ("acceptance_criteria", "approved_scope", "constraints", "source_references"):
        if key in value and (
            not isinstance(value[key], list) or not all(isinstance(item, str) for item in value[key])
        ):
            raise HarnessError(f"{key} must be an array of strings")
    for index, criterion in enumerate(value["acceptance_criteria"]):
        reject_unsafe_controls(
            criterion,
            label=f"acceptance_criteria[{index}]",
            allow_newline=True,
            allow_tab=True,
        )
    for index, reference in enumerate(value.get("source_references", [])):
        reject_unsafe_controls(reference, label=f"source_references[{index}]")
    if "repository" in value and not isinstance(value["repository"], str):
        raise HarnessError("repository must be a string")
    sanitized, _ = sanitize_value(value)
    sanitized["scope_paths"] = validate_scope_paths(sanitized["scope_paths"])
    return sanitized


def validate_scope_paths(value: Any) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise HarnessError("scope_paths must be a non-empty array of repository-relative path patterns")
    normalized: list[str] = []
    for pattern in value:
        if not pattern or "\\" in pattern or pattern.startswith("/") or pattern.endswith("/"):
            raise HarnessError(f"invalid scope path pattern: {pattern!r}")
        wildcard = pattern.endswith("/**")
        raw_path = pattern[:-3] if wildcard else pattern
        relative = Path(raw_path)
        if relative.is_absolute() or not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
            raise HarnessError(f"invalid scope path pattern: {pattern!r}")
        if any(character in raw_path for character in ("*", "?", "[", "]")):
            raise HarnessError(f"only a trailing /** scope wildcard is supported: {pattern!r}")
        if relative.parts[0] in (RUNTIME_ROOT, ".git"):
            raise HarnessError(f"scope path cannot target runtime or Git metadata: {pattern!r}")
        normalized.append(relative.as_posix() + ("/**" if wildcard else ""))
    if len(set(normalized)) != len(normalized):
        raise HarnessError("scope_paths must not contain duplicates")
    return sorted(normalized)


def path_matches_scope(relative: str, scope_paths: Iterable[str]) -> bool:
    for pattern in scope_paths:
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if relative == prefix or relative.startswith(f"{prefix}/"):
                return True
        elif relative == pattern:
            return True
    return False


def ensure_private_directory(path: Path, mode: int = 0o700) -> None:
    runtime_anchor = next((candidate for candidate in (path, *path.parents) if candidate.name == ".ai-runtime"), None)
    stop = runtime_anchor.parent if runtime_anchor is not None else path.parent
    probe = path.absolute()
    while probe != stop.absolute() and probe.parent != probe:
        if probe.exists() and probe.is_symlink():
            raise HarnessError(f"refusing symlinked runtime path component: {probe}")
        probe = probe.parent
    current = path
    missing: list[Path] = []
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    if current.is_symlink():
        raise HarnessError(f"refusing symlinked runtime parent: {current}")
    for directory in reversed(missing):
        directory.mkdir(mode=mode)
    if path.is_symlink() or not path.is_dir():
        raise HarnessError(f"runtime path is not a regular directory: {path}")
    os.chmod(path, mode)


def _reject_symlink_components(path: Path, stop_at: Path) -> None:
    stop = stop_at.resolve()
    try:
        relative = path.absolute().relative_to(stop)
    except ValueError as exc:
        raise HarnessError(f"path escapes allowed root: {path}") from exc
    current = stop
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise HarnessError(f"refusing symlinked path component: {current}")


def resolve_repo_relative_path(root: Path, value: str, allowed_parent: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise HarnessError("path must be repository-relative without parent traversal")
    allowed = Path(allowed_parent)
    if relative.parent != allowed or relative.suffix != ".json":
        raise HarnessError(f"path must be a JSON file directly under {allowed_parent}")
    root_resolved = root.resolve()
    candidate = root_resolved / relative
    _reject_symlink_components(candidate.parent, root_resolved)
    if candidate.exists() and candidate.is_symlink():
        raise HarnessError(f"refusing symlinked target: {relative}")
    return candidate


def resolve_runtime_path(root: Path, value: str, allowed_subdir: str, *, suffix: str = ".json") -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise HarnessError("runtime path must be repository-relative without parent traversal")
    expected_parent = Path(".ai-runtime") / allowed_subdir
    if relative.parent != expected_parent or relative.suffix != suffix:
        raise HarnessError(f"runtime path must be a {suffix} file directly under {expected_parent}")
    root_resolved = root.resolve()
    candidate = root_resolved / relative
    _reject_symlink_components(candidate.parent, root_resolved)
    if candidate.exists() and candidate.is_symlink():
        raise HarnessError(f"refusing symlinked runtime target: {relative}")
    return candidate


def atomic_write_json(path: Path, value: Any, *, private: bool) -> None:
    mode = 0o600 if private else 0o644
    if private:
        ensure_private_directory(path.parent)
    else:
        if not path.parent.exists() or path.parent.is_symlink():
            raise HarnessError(f"unsafe output parent: {path.parent}")
    if path.exists() and path.is_symlink():
        raise HarnessError(f"refusing symlinked output: {path}")
    payload = canonical_json_bytes(value) + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, mode)
        offset = 0
        while offset < len(payload):
            offset += os.write(fd, payload[offset:])
        os.fsync(fd)
        os.close(fd)
        fd = -1
        if path.exists() and path.is_symlink():
            raise HarnessError(f"refusing symlinked output: {path}")
        os.replace(temporary_path, path)
        os.chmod(path, mode)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def write_private_json(path: Path, value: Any) -> None:
    atomic_write_json(path, value, private=True)


def prune_runtime(root: Path, policy: dict[str, Any], *, now: float | None = None) -> list[Path]:
    runtime = validate_runtime_policy(policy, root)
    cutoff = (now if now is not None else time.time()) - int(runtime["retention_days"]) * 86400
    removed: list[Path] = []
    for relative in runtime["retention_targets"]:
        target = root / runtime["root"] / relative
        if not target.exists() or target.is_symlink():
            continue
        for path in target.rglob("*"):
            try:
                if path.is_file() and not path.is_symlink() and path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed.append(path)
            except FileNotFoundError:
                continue
    return removed


def get_local_salt(root: Path = REPO_ROOT) -> bytes:
    state_dir = root / ".ai-runtime/state"
    ensure_private_directory(state_dir)
    salt_path = state_dir / "hmac-salt"
    if salt_path.exists():
        if salt_path.is_symlink() or not salt_path.is_file():
            raise HarnessError("local HMAC salt is not a regular file")
        os.chmod(salt_path, 0o600)
        salt = salt_path.read_bytes()
        if len(salt) != 32:
            raise HarnessError("local HMAC salt has an invalid length")
        return salt
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(salt_path, flags, 0o600)
    try:
        salt = secrets.token_bytes(32)
        os.write(fd, salt)
        os.fchmod(fd, 0o600)
        return salt
    finally:
        os.close(fd)


def anonymous_id(salt: bytes, namespace: str, raw_value: str) -> str:
    return hmac.new(salt, f"{namespace}\0{raw_value}".encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def git_output(root: Path, *args: str, text: bool = True) -> str | bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        raise HarnessError(f"git {' '.join(args)} failed: {detail}") from exc
    return result.stdout


def git_commit(root: Path = REPO_ROOT) -> str:
    commit = str(git_output(root, "rev-parse", "HEAD")).strip()
    if not HEX_40.fullmatch(commit):
        raise HarnessError("HEAD is not a SHA-1 commit id")
    return commit


def _git_tree(root: Path, revision: str) -> dict[str, tuple[str, str]]:
    raw = git_output(root, "ls-tree", "-r", "-z", revision, text=False)
    assert isinstance(raw, bytes)
    result: dict[str, tuple[str, str]] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        if object_type == "blob" or (mode == "160000" and object_type == "commit"):
            result[path_bytes.decode("utf-8", "surrogateescape")] = (mode, object_id)
    return result


def _current_paths(root: Path, *, gitlink_paths: Iterable[str] = ()) -> set[str]:
    args = ["ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    for relative in sorted(set(gitlink_paths)):
        args.extend((f"--exclude={relative}", f"--exclude={relative}/**"))
    raw = git_output(root, *args, text=False)
    assert isinstance(raw, bytes)
    return {item.decode("utf-8", "surrogateescape") for item in raw.split(b"\0") if item}


def _index_gitlinks(root: Path) -> dict[str, str]:
    raw = git_output(root, "ls-files", "--stage", "-z", text=False)
    assert isinstance(raw, bytes)
    result: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        if mode != "160000":
            continue
        relative = path_bytes.decode("utf-8", "surrogateescape")
        if stage != "0":
            raise HarnessError(f"cannot snapshot unmerged gitlink: {relative}")
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", object_id):
            raise HarnessError(f"invalid gitlink object id: {relative}")
        result[relative] = object_id
    return result


def _read_git_metadata(path: Path, *, label: str) -> str:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise HarnessError(f"missing gitlink {label}: {path}") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
        raise HarnessError(f"unsafe gitlink {label}: {path}")
    try:
        return path.read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError) as exc:
        raise HarnessError(f"invalid gitlink {label}: {path}") from exc


def _resolve_gitlink_ref(git_dir: Path, reference: str) -> str:
    current = reference
    for _ in range(8):
        relative = Path(current)
        if (
            not current.startswith("refs/")
            or relative.is_absolute()
            or any(part in ("", ".", "..") for part in relative.parts)
        ):
            raise HarnessError(f"invalid gitlink HEAD reference: {current}")
        loose = git_dir / relative
        _reject_symlink_components(loose, git_dir)
        if loose.exists():
            value = _read_git_metadata(loose, label="reference").strip()
            if value.startswith("ref: "):
                current = value[5:].strip()
                continue
            if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
                return value
            raise HarnessError(f"invalid gitlink reference object id: {current}")
        packed = git_dir / "packed-refs"
        _reject_symlink_components(packed, git_dir)
        if packed.exists():
            for line in _read_git_metadata(packed, label="packed references").splitlines():
                if not line or line.startswith(("#", "^")):
                    continue
                object_id, separator, name = line.partition(" ")
                if separator and name == current and re.fullmatch(
                    r"[0-9a-f]{40}|[0-9a-f]{64}", object_id
                ):
                    return object_id
        raise HarnessError(f"unresolved gitlink HEAD reference: {current}")
    raise HarnessError("gitlink HEAD symbolic reference depth exceeded")


def _gitlink_checkout_head(root: Path, relative: str, index_object_id: str) -> str | None:
    root_resolved = root.resolve()
    checkout = root_resolved / relative
    try:
        info = checkout.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(info.st_mode):
        return None
    _reject_symlink_components(checkout, root_resolved)
    marker = checkout / ".git"
    try:
        marker_info = marker.lstat()
    except FileNotFoundError:
        # An uninitialized submodule checkout is an empty directory whose index
        # gitlink remains the canonical current pointer.
        return index_object_id
    if stat.S_ISLNK(marker_info.st_mode):
        raise HarnessError(f"gitlink metadata cannot be a symlink: {relative}")
    if stat.S_ISDIR(marker_info.st_mode):
        git_dir = marker
        _reject_symlink_components(git_dir, root_resolved)
    elif stat.S_ISREG(marker_info.st_mode):
        marker_text = _read_git_metadata(marker, label="gitdir marker").strip()
        if not marker_text.startswith("gitdir: "):
            raise HarnessError(f"invalid gitlink gitdir marker: {relative}")
        git_dir = (checkout / marker_text[8:].strip()).resolve()
        top_git_dir = Path(
            str(git_output(root, "rev-parse", "--absolute-git-dir")).strip()
        ).resolve()
        modules_dir = top_git_dir / "modules"
        try:
            git_dir.relative_to(modules_dir)
        except ValueError as exc:
            raise HarnessError(f"gitlink gitdir escapes superproject metadata: {relative}") from exc
        _reject_symlink_components(git_dir, top_git_dir)
    else:
        raise HarnessError(f"unsafe gitlink gitdir marker: {relative}")
    if git_dir.is_symlink() or not git_dir.is_dir():
        raise HarnessError(f"gitlink gitdir is not a safe directory: {relative}")
    head_path = git_dir / "HEAD"
    _reject_symlink_components(head_path, git_dir)
    head = _read_git_metadata(head_path, label="HEAD").strip()
    if head.startswith("ref: "):
        return _resolve_gitlink_ref(git_dir, head[5:].strip())
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head):
        raise HarnessError(f"invalid detached gitlink HEAD: {relative}")
    return head


def _current_gitlinks(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative, object_id in _index_gitlinks(root).items():
        current_object_id = _gitlink_checkout_head(root, relative, object_id)
        if current_object_id is not None:
            result[relative] = current_object_id
    return result


def _is_gitlink_descendant(relative: str, gitlink_paths: Iterable[str]) -> bool:
    return any(relative.startswith(f"{gitlink}/") for gitlink in gitlink_paths)


def _current_file(
    root: Path,
    relative: str,
    *,
    gitlinks: dict[str, str] | None = None,
) -> tuple[str, bytes] | None:
    if gitlinks is not None and relative in gitlinks:
        return "160000", gitlinks[relative].encode("ascii")
    path = root / relative
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode):
        return "120000", os.readlink(path).encode("utf-8", "surrogateescape")
    if not stat.S_ISREG(info.st_mode):
        return None
    mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
    return mode, path.read_bytes()


def _git_blob_id(data: bytes, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    digest.update(f"blob {len(data)}\0".encode("ascii"))
    digest.update(data)
    return digest.hexdigest()


def is_diff_digest_excluded(relative: str) -> bool:
    return relative == ".ai-runtime" or relative.startswith(".ai-runtime/") or relative.startswith(
        ".agents/ai-harness/attestations/"
    )


def capture_task_snapshot(root: Path, base_commit: str) -> CanonicalTaskSnapshot:
    if not HEX_40.fullmatch(base_commit):
        raise HarnessError("base commit must be a 40-character lowercase object id")
    base = _git_tree(root, base_commit)
    current_gitlinks = _current_gitlinks(root)
    current_gitlink_paths = set(current_gitlinks)
    current_paths = _current_paths(root, gitlink_paths=current_gitlink_paths)
    changes: list[TaskChangeSnapshot] = []
    for relative in sorted(set(base) | current_paths | current_gitlink_paths):
        if is_diff_digest_excluded(relative):
            continue
        base_item = base.get(relative)
        if relative in current_gitlinks:
            current_item = ("160000", current_gitlinks[relative].encode("ascii"))
        elif _is_gitlink_descendant(relative, current_gitlink_paths):
            # A base tree may have descendants where the current index now has a
            # gitlink. Treat those descendants as deletions without inspecting
            # the current submodule checkout.
            current_item = None
        else:
            current_item = _current_file(root, relative)
        if current_item is None and base_item is None:
            continue
        unchanged = False
        if current_item is not None and base_item is not None:
            current_mode, data = current_item
            if current_mode == "160000":
                unchanged = current_mode == base_item[0] and data.decode("ascii") == base_item[1]
            else:
                algorithm = "sha1" if len(base_item[1]) == 40 else "sha256"
                unchanged = current_mode == base_item[0] and _git_blob_id(data, algorithm) == base_item[1]
        if unchanged:
            continue
        _validate_patch_path(relative)
        base_snapshot = None
        if base_item is not None:
            base_mode, base_object = base_item
            base_snapshot = TaskFileSnapshot(
                mode=base_mode,
                object_id=base_object,
                content=None if base_mode == "160000" else _git_blob(root, base_object),
            )
        current_snapshot = None
        if current_item is not None:
            current_mode, current_content = current_item
            current_snapshot = TaskFileSnapshot(
                mode=current_mode,
                object_id=current_content.decode("ascii") if current_mode == "160000" else None,
                content=None if current_mode == "160000" else current_content,
            )
        changes.append(
            TaskChangeSnapshot(
                path=relative,
                base=base_snapshot,
                current=current_snapshot,
            )
        )
    return CanonicalTaskSnapshot(base_commit=base_commit, changes=tuple(changes))


def task_diff_from_snapshot(snapshot: CanonicalTaskSnapshot) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    for captured in snapshot.changes:
        base_item = captured.base
        current_item = captured.current
        change = {
            "path": captured.path,
            "base_mode": base_item.mode if base_item else None,
            "base_object": base_item.object_id if base_item else None,
            "current_mode": current_item.mode if current_item else None,
            "current_sha256": (
                sha256_bytes(current_item.content)
                if current_item is not None and current_item.mode != "160000" and current_item.content is not None
                else None
            ),
        }
        if current_item is not None and current_item.mode == "160000":
            change["current_object"] = current_item.object_id
        changes.append(change)
    return {"base_commit": snapshot.base_commit, "changes": changes}


def compute_task_diff_snapshot(root: Path, base_commit: str) -> dict[str, Any]:
    return task_diff_from_snapshot(capture_task_snapshot(root, base_commit))


def compute_task_diff_digest(root: Path, base_commit: str) -> str:
    return sha256_json(compute_task_diff_snapshot(root, base_commit))


def _validate_patch_path(relative: str) -> None:
    try:
        relative.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise HarnessError(f"task patch path is not UTF-8: {relative!r}") from exc
    reject_unsafe_controls(relative, label=f"task patch path {relative!r}")


def _validate_patch_content(relative: str, version: str, data: bytes) -> None:
    if b"\0" in data:
        raise HarnessError(f"task patch contains NUL bytes: {relative} ({version})")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HarnessError(f"task patch contains non-UTF-8 content: {relative} ({version})") from exc
    binary_controls = set(range(32)) - {9, 10, 12, 13}
    if any(byte in binary_controls or byte == 127 for byte in data):
        raise HarnessError(f"task patch contains binary control bytes: {relative} ({version})")


def _git_blob(root: Path, object_id: str) -> bytes:
    raw = git_output(root, "cat-file", "blob", object_id, text=False)
    assert isinstance(raw, bytes)
    return raw


def _materialize_patch_file(path: Path, mode: str, data: bytes) -> None:
    if mode == "120000":
        path.symlink_to(data.decode("utf-8"))
        return
    if mode not in ("100644", "100755"):
        raise HarnessError(f"unsupported task patch file mode: {mode}")
    path.write_bytes(data)
    os.chmod(path, 0o755 if mode == "100755" else 0o644)


def _gitlink_patch_content(object_id: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", object_id):
        raise HarnessError("invalid gitlink object id in task patch")
    return f"Subproject commit {object_id}\n".encode("ascii")


def _quoted_patch_path(prefix: str, relative: str) -> str:
    value = f"{prefix}/{relative}"
    if any(character.isspace() or character in ('"', "\\") for character in value):
        return json.dumps(value, ensure_ascii=False)
    return value


def _normalize_patch_headers(output: str, relative: str, *, has_base: bool, has_current: bool) -> str:
    lines = output.splitlines(keepends=True)
    if not lines or not lines[0].startswith("diff --git "):
        raise HarnessError(f"Git did not produce a canonical textual patch for {relative}")
    old_path = _quoted_patch_path("a", relative)
    new_path = _quoted_patch_path("b", relative)
    lines[0] = f"diff --git {old_path} {new_path}\n"
    for index in range(1, len(lines)):
        if lines[index].startswith("@@ "):
            break
        if lines[index].startswith("--- "):
            lines[index] = f"--- {old_path if has_base else '/dev/null'}\n"
        elif lines[index].startswith("+++ "):
            lines[index] = f"+++ {new_path if has_current else '/dev/null'}\n"
    return "".join(lines)


def _diff_materialized_files(
    root: Path,
    relative: str,
    base_item: tuple[str, bytes] | None,
    current_item: tuple[str, bytes] | None,
) -> str:
    with tempfile.TemporaryDirectory(prefix="ai-harness-patch-") as directory:
        temporary = Path(directory)
        old_path = temporary / "old"
        new_path = temporary / "new"
        if base_item is not None:
            _materialize_patch_file(old_path, *base_item)
        if current_item is not None:
            _materialize_patch_file(new_path, *current_item)
        argv = [
            "git",
            "-c",
            "core.quotePath=false",
            "-c",
            "core.fileMode=true",
            "diff",
            "--no-index",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "--text",
            "--full-index",
            "--unified=3",
            "--no-indent-heuristic",
            "--diff-algorithm=myers",
            "--",
            str(old_path) if base_item is not None else os.devnull,
            str(new_path) if current_item is not None else os.devnull,
        ]
        try:
            completed = subprocess.run(
                argv,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            raise HarnessError(f"could not generate task patch for {relative}: {exc}") from exc
        if completed.returncode != 1:
            detail = completed.stderr.decode("utf-8", "replace").strip()
            raise HarnessError(
                f"Git task patch generation failed for {relative} with status "
                f"{completed.returncode}: {detail}"
            )
        try:
            output = completed.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HarnessError(f"Git produced a non-UTF-8 task patch for {relative}") from exc
        return _normalize_patch_headers(
            output,
            relative,
            has_base=base_item is not None,
            has_current=current_item is not None,
        )


def _gitlink_patch_object(
    item: tuple[str, bytes] | None,
    *,
    known_object_id: str | None,
    algorithm: str,
) -> str | None:
    if item is None:
        return None
    mode, data = item
    if mode == "160000":
        object_id = data.decode("ascii")
        _gitlink_patch_content(object_id)
        return object_id
    if known_object_id is not None:
        return known_object_id
    return _git_blob_id(data, algorithm)


def _rewrite_gitlink_patch_headers(
    output: str,
    relative: str,
    base_item: tuple[str, bytes] | None,
    current_item: tuple[str, bytes] | None,
    *,
    base_object_id: str | None,
) -> str:
    base_mode = base_item[0] if base_item else None
    current_mode = current_item[0] if current_item else None
    object_length = len(base_object_id) if base_object_id is not None else 40
    if current_item is not None and current_mode == "160000":
        object_length = len(current_item[1].decode("ascii"))
    algorithm = "sha1" if object_length == 40 else "sha256"
    old_object = _gitlink_patch_object(
        base_item,
        known_object_id=base_object_id,
        algorithm=algorithm,
    )
    new_object = _gitlink_patch_object(
        current_item,
        known_object_id=None,
        algorithm=algorithm,
    )

    lines = output.splitlines(keepends=True)
    body_index = next(
        (index for index, line in enumerate(lines) if line.startswith(("--- ", "+++ ", "@@ "))),
        len(lines),
    )
    header = [
        f"diff --git {_quoted_patch_path('a', relative)} {_quoted_patch_path('b', relative)}\n"
    ]
    if base_item is None:
        assert current_mode is not None
        header.append(f"new file mode {current_mode}\n")
    elif current_item is None:
        header.append(f"deleted file mode {base_mode}\n")
    elif base_mode != current_mode:
        header.extend((f"old mode {base_mode}\n", f"new mode {current_mode}\n"))

    zero = "0" * object_length
    old_display = old_object or zero
    new_display = new_object or zero
    if old_display != new_display:
        mode_suffix = f" {base_mode}" if base_mode is not None and base_mode == current_mode else ""
        header.append(f"index {old_display}..{new_display}{mode_suffix}\n")
    return "".join(header + lines[body_index:])


def _diff_gitlink_change(
    root: Path,
    relative: str,
    base_item: tuple[str, bytes] | None,
    current_item: tuple[str, bytes] | None,
    *,
    base_object_id: str | None,
) -> str:
    def materialize(item: tuple[str, bytes] | None) -> tuple[str, bytes] | None:
        if item is None:
            return None
        mode, data = item
        if mode == "160000":
            return "100644", _gitlink_patch_content(data.decode("ascii"))
        return item

    materialized_base = materialize(base_item)
    materialized_current = materialize(current_item)
    if (
        materialized_base is not None
        and materialized_current is not None
        and materialized_base == materialized_current
    ):
        output = ""
    else:
        output = _diff_materialized_files(
            root,
            relative,
            materialized_base,
            materialized_current,
        )
    return _rewrite_gitlink_patch_headers(
        output,
        relative,
        base_item,
        current_item,
        base_object_id=base_object_id,
    )


def task_patch_from_snapshot(root: Path, snapshot: CanonicalTaskSnapshot) -> str:
    patches: list[str] = []
    for change in snapshot.changes:
        relative = change.path
        _validate_patch_path(relative)
        base_snapshot = change.base
        current_snapshot = change.current
        base_file = None
        if base_snapshot is not None:
            base_content = (
                base_snapshot.object_id.encode("ascii")
                if base_snapshot.mode == "160000" and base_snapshot.object_id is not None
                else base_snapshot.content
            )
            assert base_content is not None
            base_file = (base_snapshot.mode, base_content)
            if base_snapshot.mode != "160000":
                _validate_patch_content(relative, "base", base_content)
        current_file = None
        if current_snapshot is not None:
            current_content = (
                current_snapshot.object_id.encode("ascii")
                if current_snapshot.mode == "160000" and current_snapshot.object_id is not None
                else current_snapshot.content
            )
            assert current_content is not None
            current_file = (current_snapshot.mode, current_content)
        if current_file is not None and current_file[0] != "160000":
            _validate_patch_content(relative, "current", current_file[1])
        if (
            base_file is not None and base_file[0] == "160000"
        ) or (
            current_file is not None and current_file[0] == "160000"
        ):
            patches.append(
                _diff_gitlink_change(
                    root,
                    relative,
                    base_file,
                    current_file,
                    base_object_id=base_snapshot.object_id if base_snapshot else None,
                )
            )
        else:
            patches.append(_diff_materialized_files(root, relative, base_file, current_file))
    return "".join(patches)


def compute_task_patch(root: Path, base_commit: str) -> str:
    return task_patch_from_snapshot(root, capture_task_snapshot(root, base_commit))


def validate_bootstrap_changed_paths(snapshot: dict[str, Any]) -> None:
    if snapshot.get("base_commit") != INSTALLATION_BASE_COMMIT:
        raise HarnessError("bootstrap diff uses the wrong installation baseline")
    changes = snapshot.get("changes")
    if not isinstance(changes, list):
        raise HarnessError("bootstrap diff snapshot has no changes array")
    for item in changes:
        relative = item.get("path") if isinstance(item, dict) else None
        if not isinstance(relative, str):
            raise HarnessError("bootstrap diff contains an invalid path")
        if relative in BOOTSTRAP_ALLOWED_FILES or any(relative.startswith(prefix) for prefix in BOOTSTRAP_ALLOWED_PREFIXES):
            continue
        raise HarnessError(f"bootstrap diff contains a non-harness path: {relative}")


def digest_map(root: Path, relative_paths: Iterable[str]) -> dict[str, str]:
    return {relative: sha256_file(root / relative) for relative in sorted(relative_paths)}
