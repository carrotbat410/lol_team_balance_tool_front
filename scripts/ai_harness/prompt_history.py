from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ai_harness.common import (  # noqa: E402
    HarnessError,
    PROMPT_MANIFEST_PATH,
    REPO_ROOT,
    anonymous_id,
    canonical_json_bytes,
    get_local_salt,
    load_policy,
    prune_runtime,
    read_json,
    reject_forbidden_keys,
    sanitize_value,
    sha256_bytes,
    sha256_file,
    sha256_json,
    utc_timestamp,
    validate_envelope,
    resolve_runtime_path,
    write_private_json,
)


RECORD_KEYS = {
    "schema_version",
    "record_id",
    "created_at",
    "role",
    "contract_path",
    "contract_sha256",
    "template_path",
    "template_sha256",
    "envelope",
    "envelope_sha256",
    "rendered_prompt_sha256",
    "redactions",
}


def load_prompt_manifest(root: Path = REPO_ROOT) -> dict[str, Any]:
    manifest = read_json(root / PROMPT_MANIFEST_PATH)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0":
        raise HarnessError("prompt manifest schema_version must be 1.0")
    if not isinstance(manifest.get("roles"), dict):
        raise HarnessError("prompt manifest roles must be an object")
    return manifest


def assets_for_role(role: str, root: Path = REPO_ROOT) -> tuple[str, str, str, str, str, str]:
    manifest = load_prompt_manifest(root)
    role_config = manifest["roles"].get(role)
    if not isinstance(role_config, dict):
        raise HarnessError(f"unsupported role: {role}")
    relative = role_config.get("template")
    expected_digest = role_config.get("sha256")
    contract_relative = role_config.get("agent_contract")
    expected_contract_digest = role_config.get("contract_sha256")
    if not all(
        isinstance(item, str)
        for item in (relative, expected_digest, contract_relative, expected_contract_digest)
    ):
        raise HarnessError(f"invalid prompt manifest entry for {role}")
    template_path = root / relative
    actual_digest = sha256_file(template_path)
    if actual_digest != expected_digest:
        raise HarnessError(f"template digest mismatch for {role}")
    template = template_path.read_text(encoding="utf-8")
    if template.count("{{canonical_envelope}}") != 1:
        raise HarnessError(f"template for {role} must contain one canonical envelope placeholder")
    contract_path = root / contract_relative
    actual_contract_digest = sha256_file(contract_path)
    if actual_contract_digest != expected_contract_digest:
        raise HarnessError(f"agent contract digest mismatch for {role}")
    contract = contract_path.read_text(encoding="utf-8")
    return relative, template, actual_digest, contract_relative, contract, actual_contract_digest


def render_prompt(template: str, contract: str, envelope: dict[str, Any]) -> str:
    canonical_envelope = canonical_json_bytes(envelope).decode("utf-8")
    rendered_template = template.replace("{{canonical_envelope}}", canonical_envelope)
    return f"<agent_contract>\n{contract}\n</agent_contract>\n\n{rendered_template}"


def build_record(
    raw_envelope: Any,
    role: str,
    *,
    root: Path = REPO_ROOT,
    created_at: str | None = None,
    salt: bytes | None = None,
) -> dict[str, Any]:
    policy = load_policy(root)
    reject_forbidden_keys(raw_envelope, policy["prompt_history"]["forbidden_keys"])
    # Validate caller-authored control characters before redaction can replace
    # the surrounding text and accidentally erase an unsafe byte.
    validate_envelope(raw_envelope, policy)
    sanitized, redactions = sanitize_value(raw_envelope)
    envelope = validate_envelope(sanitized, policy)
    template_path, template, template_digest, contract_path, contract, contract_digest = assets_for_role(role, root)
    envelope_digest = sha256_bytes(canonical_json_bytes(envelope))
    rendered_digest = sha256_bytes(render_prompt(template, contract, envelope).encode("utf-8"))
    local_salt = salt if salt is not None else get_local_salt(root)
    record_id = anonymous_id(local_salt, "prompt-record", f"{envelope['task_id']}:{role}:{envelope_digest}")
    return {
        "schema_version": "1.0",
        "record_id": record_id,
        "created_at": created_at or utc_timestamp(),
        "role": role,
        "contract_path": contract_path,
        "contract_sha256": contract_digest,
        "template_path": template_path,
        "template_sha256": template_digest,
        "envelope": envelope,
        "envelope_sha256": envelope_digest,
        "rendered_prompt_sha256": rendered_digest,
        "redactions": dict(sorted(Counter(redactions).items())),
    }


def verify_record(record: Any, *, root: Path = REPO_ROOT) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise HarnessError("prompt record must be an object")
    if set(record) != RECORD_KEYS:
        raise HarnessError(f"prompt record keys differ from schema: {sorted(set(record) ^ RECORD_KEYS)}")
    if record["schema_version"] != "1.0":
        raise HarnessError("prompt record schema_version must be 1.0")
    policy = load_policy(root)
    reject_forbidden_keys(record["envelope"], policy["prompt_history"]["forbidden_keys"])
    sanitized, newly_found = sanitize_value(record["envelope"])
    if sanitized != record["envelope"] or newly_found:
        raise HarnessError("prompt record contains unsanitized secret or PII data")
    envelope = validate_envelope(record["envelope"], policy)
    role = record["role"]
    template_path, template, template_digest, contract_path, contract, contract_digest = assets_for_role(role, root)
    envelope_digest = sha256_bytes(canonical_json_bytes(envelope))
    rendered_digest = sha256_bytes(render_prompt(template, contract, envelope).encode("utf-8"))
    if record["contract_path"] != contract_path or record["contract_sha256"] != contract_digest:
        raise HarnessError("agent contract metadata mismatch")
    if record["template_path"] != template_path or record["template_sha256"] != template_digest:
        raise HarnessError("prompt template metadata mismatch")
    if record["envelope_sha256"] != envelope_digest:
        raise HarnessError("prompt envelope digest mismatch")
    if record["rendered_prompt_sha256"] != rendered_digest:
        raise HarnessError("rendered prompt digest mismatch")
    if not isinstance(record["redactions"], dict) or not all(
        isinstance(key, str) and isinstance(value, int) and value >= 0
        for key, value in record["redactions"].items()
    ):
        raise HarnessError("invalid redaction summary")
    return {
        "role": role,
        "contract_sha256": contract_digest,
        "template_sha256": template_digest,
        "envelope_sha256": envelope_digest,
        "rendered_prompt_sha256": rendered_digest,
        "approved_scope_digest": sha256_json(
            {"approved_scope": envelope["approved_scope"], "scope_paths": envelope["scope_paths"]}
        ),
        "scope_paths_digest": sha256_json(envelope["scope_paths"]),
        "scope_paths": envelope["scope_paths"],
    }


def _read_input(path_value: str) -> Any:
    if path_value == "-":
        try:
            return json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise HarnessError(f"invalid stdin JSON: {exc}") from exc
    return read_json(Path(path_value))


def command_record(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    policy = load_policy(root)
    prune_runtime(root, policy)
    record = build_record(_read_input(args.input), args.role, root=root)
    output_value = args.output or f".ai-runtime/prompt-history/{record['record_id']}.json"
    output = resolve_runtime_path(root, output_value, "prompt-history")
    write_private_json(output, record)
    print(
        json.dumps(
            {
                "record_id": record["record_id"],
                "role": record["role"],
                "envelope_sha256": record["envelope_sha256"],
                "rendered_prompt_sha256": record["rendered_prompt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = verify_record(read_json(Path(args.record)), root=root)
    print(json.dumps({"status": "ok", **result}, sort_keys=True))
    return 0


def command_render(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    record = read_json(Path(args.record))
    verify_record(record, root=root)
    _, template, _, _, contract, _ = assets_for_role(record["role"], root)
    rendered = render_prompt(template, contract, record["envelope"])
    if args.output == "-":
        sys.stdout.write(rendered)
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and verify sanitized canonical prompt history")
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="sanitize and record a canonical task envelope")
    record.add_argument("--input", required=True, help="JSON envelope path or - for stdin")
    record.add_argument("--role", required=True, choices=("researcher", "planner", "implementer", "reviewer"))
    record.add_argument("--output", help="private output path; defaults under .ai-runtime")
    record.set_defaults(handler=command_record)

    verify = subparsers.add_parser("verify", help="verify template, envelope, and rendered digests")
    verify.add_argument("--record", required=True)
    verify.set_defaults(handler=command_verify)

    render = subparsers.add_parser("render", help="deterministically re-render a sanitized prompt")
    render.add_argument("--record", required=True)
    render.add_argument("--output", required=True, help="output path or - for stdout")
    render.set_defaults(handler=command_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return args.handler(args)
    except HarnessError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
