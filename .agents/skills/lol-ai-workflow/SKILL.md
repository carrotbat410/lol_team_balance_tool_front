---
name: lol-ai-workflow
description: Coordinate plan-first development for the LoL Civil War Helper by delegating fresh Researcher, Planner, Implementer, and blind Reviewer subagents. Use for feature development, bug fixes, refactoring, database changes, authentication or authorization work, deployment changes, security hardening, and other code modifications that require human plan approval and independent review. Do not use for simple explanations or read-only status questions.
---

# AI Development Workflow

Run the main thread as the Coordinator. Never simulate independent roles in the main context when subagents are available.

- Do not spawn another Coordinator. The main thread must create and route each role subagent directly.
- Spawn every role with a fresh context (`fork_context=false` when the host exposes that option).
- Prefer the matching custom agent from `.codex/agents/`.
- If the host cannot select a custom agent by name, read the matching TOML file and include its role contract in the fresh subagent prompt. Do not fall back to role-playing inside the Coordinator context.

## 1. Establish the baseline

- Read `@AGENTS.md`, `@CLAUDE.md`, and the smallest relevant project documentation.
- Record the original user request verbatim enough to preserve its acceptance intent.
- Capture the existing Git status and distinguish pre-existing user changes from task changes. Never revert or include unrelated work.
- Classify the initial risk as low, medium, or high. Treat database, authentication, authorization, secrets, infrastructure, deployment, destructive actions, and production changes as high risk.
- Create a sanitized canonical task envelope with `scripts/ai_harness/prompt_history.py`; never persist the raw prompt, transcript, reasoning, or tool/command input and output.

## 2. Delegate research

- Spawn a fresh `researcher` subagent in read-only mode.
- Send only the original request, repository location, baseline state, and relevant known constraints.
- Wait for its report. Keep raw exploration noise out of the main thread.
- Verify that the report distinguishes evidence from inference.
- Render the Researcher prompt from `.agents/prompts/manifest.json` and retain only its sanitized prompt record and digests under `.ai-runtime`.

## 3. Delegate planning

- Spawn a fresh `planner` subagent in read-only mode.
- Send the original request, acceptance intent, baseline state, and Researcher report.
- Require an approval-ready plan with scope, files, ordered steps, risks, verification, and rollback.
- Do not let the Planner edit files or contact the Implementer.
- Use a role-specific prompt record; do not reuse the Researcher context digest.

## 4. Apply the human approval gate

- Present the Planner output to the user in concise Korean.
- Stop before implementation and wait for explicit approval or requested revisions.
- Treat approval as applying only to the presented scope. Route revisions back through a fresh or continued planning pass as appropriate.
- Do not make the user copy the plan between threads. The Coordinator owns all routing.
- Record a sanitized approved-scope object with both the approval summary and explicit repository-relative `scope_paths`. Any scope text or path change requires another human approval event.

## 5. Delegate implementation

- After approval, spawn a fresh `implementer` subagent.
- Send the original request, approved plan, baseline state, repository rules, and only the evidence needed to execute the plan.
- Do not send hidden planning discussion or unrelated context.
- Require the Implementer to preserve existing changes, stay within scope, and return changed files plus verification evidence.
- If implementation discovers an unapproved high-risk expansion, return to the human approval gate.
- Refuse to start or attest the Implementer before a valid approval event.

## 6. Build a blind review packet

Run every required verification command through `run-verification` on the current workflow attestation before packet preparation. Then create the packet input with only the four caller-authored fields below:

- Original user request
- Acceptance criteria
- Repository rules relevant to review
- Relevant final source references

`prepare-reviewer-packet` must load that workflow attestation and generate the remaining evidence itself:

- Canonical task diff metadata
- Canonical textual task patch for the same diff
- Successful required verification command records from the attestation

Create a minimal packet containing only:

- Original user request
- Acceptance criteria
- Repository rules relevant to review
- Task-specific final diff metadata and textual patch, excluding baseline changes
- Relevant final source references
- Attested verification command records

Exclude Researcher notes, Planner output, Implementer prompts, implementation conversation, attempts, rationale, and AI work logs.

Generate the exact sanitized packet copy with `prepare-reviewer-packet`, deliver that same copy, and bind its full digest as the pending prepared packet in the tracked attestation; do not store packet bodies there. `stage reviewer` must consume that exact prepared digest, and only another explicit prepare command may replace it after source or verification changes. Diff metadata and patch must come from one immutable source snapshot, and packet assembly must fail closed if a final source sample changed. Packet generation must also fail closed for unsafe manual-field controls, secret/PII redaction, binary or non-UTF-8 changes, NUL bytes, or a final packet over 2 MiB.

## 7. Delegate independent review

- Spawn a fresh `reviewer` subagent in read-only mode.
- Send only the blind review packet.
- Require findings-first output ordered by severity, with evidence and file references.
- Do not let the Reviewer edit code or contact the Implementer.

## 8. Resolve findings

- If material findings exist, send only the actionable findings and approved scope to the Implementer.
- After fixes, build a new blind review packet and use a fresh Reviewer pass.
- Limit automatic fix-review loops to two. Escalate unresolved conflicts or scope changes to the user.
- Use a fresh context digest for every fix and review pass.
- Any source change after a Reviewer event requires a new Implementer pass and a fresh blind Reviewer packet/event.

## 9. Close the task

- Report implemented behavior, review outcome, verification, and residual risks.
- Commit, push, deploy, mutate production, or delete data only when the user explicitly requests it.
- Never claim independent review if a fresh Reviewer subagent was unavailable. State the limitation clearly.
- Finalize the workflow attestation and run `npm run ai:harness:check` before reporting completion.
- Record verification only through `run-verification`; never accept a caller-supplied exit status. Treat any task diff digest change across a command, including a trusted safe rerun, as verification failure.
- Treat attestation as a structural consistency statement, not cryptographic proof that a human or independent Reviewer performed an action.
