# AI 개발 하네스

이 하네스는 저장소의 Researcher → Planner → human approval → Implementer → blind Reviewer 순서에 대한 구조·digest·현재 diff의 일관성을 기록하고 CI에서 검사한다. attestation은 서명된 행위 증명이 아니라 저장소가 제출한 준수 진술이다. 앱 UI, 백엔드, Docker, nginx 동작에는 관여하지 않는다. 정책 파일은 `@.agents/ai-harness/policy.json`이며, 안전에 민감한 runtime root·보존 기간·대상은 코드의 고정 상수와 일치해야 사용된다.

## 설치와 hook 신뢰 승인

Python 3.11 이상과 Git이 필요하며 외부 Python/npm 패키지는 사용하지 않는다. 저장소를 신뢰한 상태에서 Codex를 열고 `/hooks`를 실행해 `@.codex/hooks.json`의 command hook 정의와 hash를 검토한 뒤 승인한다. hook 파일이나 command가 바뀌면 기존 승인은 무효화되므로 다시 검토해야 한다. 승인하지 않은 repo-local hook은 Codex가 건너뛴다.

대상 이벤트는 `UserPromptSubmit`, `SubagentStart`, `SubagentStop`, `Stop`, `SessionEnd`다. 모든 이벤트는 같은 `@scripts/ai_harness/hook_logger.py`를 호출한다. hook은 stdin payload를 그대로 복사하지 않고 필요한 ID와 event/role 상태만 읽어 새 allowlist 객체를 만든다. `Stop`과 `SubagentStop`에도 빈 JSON 객체만 stdout으로 반환한다.

## 데이터 정책

로컬 산출물은 모두 Git에서 제외된 `.ai-runtime` 아래에 기록한다.

- `logs/*.jsonl`: schema version, UTC timestamp, HMAC으로 익명화한 run/turn ID, event, role, stage, status, 현재 commit, policy/template digest, 검증 exit status만 저장한다.
- `prompt-history/*.json`: 정제된 canonical task envelope와 template/envelope/rendered prompt SHA-256 digest를 저장한다. 렌더링 본문은 기본 기록에 포함하지 않는다.
- `state/hmac-salt`: 로컬 32-byte salt다. 디렉터리는 0700, 파일은 0600으로 만든다.
- `reviewer-packets/*.json`: 정제 후 변경이 없음을 확인한 blind packet의 정확한 전달 사본이다.
- `reports/*.json`: 검사 이름과 통과 여부만 담고 prompt, diff, transcript, command output 같은 본문은 담지 않는다.

원본 hook payload, 원문 prompt의 byte-for-byte 사본, 응답 본문, transcript, hidden chain-of-thought, 메시지 배열, tool/command 입출력, 비밀값, 사용자 절대 경로는 lifecycle log에 저장하지 않는다. canonical envelope는 `analysis`, `reasoning`, `chain_of_thought`, `transcript`, `messages`, `tool_output`, `command_output` 등 금지 키가 있으면 거부한다. private key, JWT, token/secret assignment, JSON/YAML의 password, `AWS_SECRET_ACCESS_KEY`, `client_secret`, `private_key`, `apiKey`, `accessToken` 변형, 이메일, 전화번호, `/Users/<name>`·`/home/<name>` 경로는 기록 전에 정제한다.

JSONL은 파일당 5 MiB에서 회전한다. `logs`, `prompt-history`, `reviewer-packets`, `reports`의 보존 기간은 정확히 30일이며 다음 하네스 실행 때 오래된 일반 파일을 제거한다. `.ai-runtime` root나 보존 대상이 절대경로·상위경로·symlink이거나 정책 값이 고정 allowlist와 다르면 chmod, prune, unlink 전에 중단한다. `state/hmac-salt`는 ID의 로컬 연속성에 필요하므로 자동 만료 대상에서 제외하고 해당 로컬 설치 수명 동안 유지한다.

## prompt history 사용

입력 JSON은 `@.agents/ai-harness/schemas/task-envelope.schema.json` 구조를 따른다. `scope_paths`는 비어 있지 않은 repository-relative 목록이며 정확한 파일이나 `directory/**`만 허용한다. 절대경로, `..`, `.ai-runtime`, `.git`, 그 외 wildcard는 거부한다. 다음 명령은 입력을 정제해 role별 tracked template·실제 `@.codex/agents/*.toml` 계약과 결합하고 본문 대신 contract/template/envelope/rendered context digest를 기록한다.

```bash
python3 scripts/ai_harness/prompt_history.py record \
  --input task-envelope.json --role researcher

python3 scripts/ai_harness/prompt_history.py verify \
  --record .ai-runtime/prompt-history/<record-id>.json

python3 scripts/ai_harness/prompt_history.py render \
  --record .ai-runtime/prompt-history/<record-id>.json --output -
```

`render`의 stdout은 정제된 역할 계약과 task 본문을 실제 agent에 전달할 때만 사용한다. 파일로 저장하면 해당 파일의 별도 수명·권한 관리가 필요하다. 역할 계약은 `@.codex/agents/*.toml`에만 있고 `@.agents/prompts/*.md`는 그 계약을 참조한다. prompt manifest와 integrity manifest가 네 계약의 digest를 함께 고정한다.

## workflow attestation 사용

일반 변경은 기준 commit마다 tracked workflow attestation 하나를 추가한다. 예시는 다음 순서다.

```bash
python3 scripts/ai_harness/workflow_attestation.py init \
  --task-id issue-123 --base <base-commit> \
  --output .agents/ai-harness/attestations/issue-123.json

python3 scripts/ai_harness/workflow_attestation.py stage \
  --file .agents/ai-harness/attestations/issue-123.json \
  --stage researcher --context-record .ai-runtime/prompt-history/<record-id>.json

python3 scripts/ai_harness/workflow_attestation.py stage \
  --file .agents/ai-harness/attestations/issue-123.json \
  --stage human_approval --scope approved-scope.json
```

`approved-scope.json`은 `{"approved_scope":["승인 설명"],"scope_paths":["scripts/ai_harness/**"]}` 형태다. Implementer envelope에도 같은 두 필드가 있어야 하며, human approval과 Implementer record의 결합 digest 및 `scope_paths` digest가 모두 일치해야 한다. 일반 workflow finalize는 실제 task diff의 모든 경로가 이 목록에 포함되는지 확인한다.

Reviewer packet 입력은 `original_request`, `acceptance_criteria`, `review_rules`, `final_source_references` 네 필드만 받는다. `task_diff`, `task_patch`, `verification`은 호출자가 제공할 수 없고 `prepare-reviewer-packet`이 지정된 tracked workflow attestation과 현재 기준 commit에서 생성한다. caller-authored prose는 LF와 TAB만 허용하고 그 외 C0/C1 control과 NUL을 거부하며, source reference path는 LF/TAB을 포함한 모든 C0/C1 control을 거부한다. prompt history의 원 요청·인수 조건·source reference에도 같은 정책을 저장 전에 적용한다.

`task_patch`는 같은 diff의 tracked/untracked 추가·수정·삭제와 mode 변경을 경로순으로 표현한 실제 UTF-8 textual patch다. mode `160000` gitlink는 base와 current를 방향별로 모델링한다. gitlink → tree는 gitlink 삭제와 resulting regular tracked/untracked 파일 추가를 모두 기록하고, tree → gitlink는 base descendant 삭제와 gitlink 추가/갱신을 모두 기록한다. current gitlink 아래 checkout 내용은 순회하거나 읽지 않고 superproject index와 안전하게 제한한 Git HEAD metadata의 commit object ID만 사용한다. 일반 파일의 기존 `task_diff` 표현과 digest는 유지하고, 과거에 보이지 않던 gitlink가 있는 경우에만 이 새 coverage로 digest가 달라지는 것이 의도된 호환성 예외다. 변경된 base/current 내용에 binary control, NUL, 비 UTF-8가 있거나 최종 canonical JSON packet과 개행이 2 MiB를 넘으면 출력 파일을 만들기 전에 실패한다.

필수 verification은 packet 준비 전에 모두 `run-verification`으로 성공해야 한다. 각 command는 실행 직전과 직후 canonical task diff digest를 계산하며 값이 달라지면 process가 성공했더라도 실패 record로 남긴다. trusted safe rerun도 같은 전후 일관성 검사를 적용한다. packet에는 command output 대신 attestation의 `command_id`, argv/result digest, exit status, base commit, task diff digest record가 결정적 순서로 들어간다. 호출자 제공 verification, 누락·실패·오래된 record는 거부한다. 금지 key는 nested object까지 재귀 검사하고 source reference는 저장소 안의 symlink가 아닌 regular file과 선택적 symbol/line reference만 허용한다. 수동 필드의 `rationale:`, `command_output:`, `transcript:`, runtime log 경로도 거부한다. 세 evidence 필드까지 조립한 packet 전체에 secret/PII 검사를 다시 적용하며 정제가 한 건이라도 필요하면 fail closed한다. prepare는 이 전체 canonical packet digest를 attestation의 pending 필드에 저장한다. `stage reviewer`는 전달 파일의 전체 digest가 pending 값과 정확히 같을 때만 event를 만들고 그 값을 소비하며, source·verification 변경 뒤 pending 값을 교체할 수 있는 경로는 새 `prepare-reviewer-packet` 실행뿐이다.

Planner와 Implementer도 각 role의 prompt record로 `stage`를 추가한다. Implementer prompt envelope의 `approved_scope` digest는 최신 human approval scope와 일치해야 한다. 각 역할 context digest는 달라야 하고, 승인 scope가 달라지면 새로운 `human_approval` event가 선행돼야 한다. Reviewer 수정-재리뷰 round는 최대 2회다. Reviewer event는 packet의 task diff digest를 기록하므로 리뷰 후 source가 바뀌면 새 Implementer pass와 새 blind Reviewer packet/event 없이 finalize할 수 없다.

검증 결과는 호출자가 exit status를 입력하지 않는다. 정책에 등록된 command ID를 CLI가 직접 실행하고 exit status, 결정적 evidence digest, 실행 당시 task diff를 기록한다. CI mode validator는 이 저장값만 믿지 않고 허용된 명령을 현재 checkout에서 다시 실행해 record와 현재 diff를 대조한다.

```bash
python3 scripts/ai_harness/workflow_attestation.py run-verification \
  --file .agents/ai-harness/attestations/issue-123.json --command-id base_ancestor
python3 scripts/ai_harness/workflow_attestation.py run-verification \
  --file .agents/ai-harness/attestations/issue-123.json --command-id unit_tests
python3 scripts/ai_harness/workflow_attestation.py run-verification \
  --file .agents/ai-harness/attestations/issue-123.json --command-id git_diff_check
python3 scripts/ai_harness/workflow_attestation.py run-verification \
  --file .agents/ai-harness/attestations/issue-123.json --command-id runtime_untracked
python3 scripts/ai_harness/workflow_attestation.py prepare-reviewer-packet \
  --input reviewer-packet-input.json \
  --file .agents/ai-harness/attestations/issue-123.json \
  --base <base-commit> \
  --output .ai-runtime/reviewer-packets/issue-123.json
python3 scripts/ai_harness/workflow_attestation.py stage \
  --file .agents/ai-harness/attestations/issue-123.json \
  --stage reviewer --packet .ai-runtime/reviewer-packets/issue-123.json --status approved
python3 scripts/ai_harness/workflow_attestation.py finalize \
  --file .agents/ai-harness/attestations/issue-123.json --base <base-commit>
```

bootstrap profile은 설치 검증 command ID만 요구하고 일반 workflow profile은 동적인 task base의 ancestor 검사까지 요구한다. validator와 `npm run ai:harness:check`의 자기 성공을 attestation에 선기록하지 않으므로 순환 의존이 없다. `--output`과 `--file`은 `.agents/ai-harness/attestations/*.json`의 repository-relative 직접 자식만 허용하며 절대 경로, `..`, 부모/대상 symlink를 거부하고 atomic write를 사용한다.

`prepare-reviewer-packet`과 `finalize`는 `policy_digest`, `prompt_manifest_digest`, `integrity_manifest_digest`를 호출자 입력 없이 현재 저장소 파일에서 다시 계산한다. packet 준비는 기존 구조·event·verification과 생성된 diff/patch 및 secret/PII 검사를 먼저 통과한 뒤 갱신된 attestation을 원자적으로 저장하므로, `init` 이후 승인 범위 안에서 정책이나 integrity manifest가 바뀌어도 stale digest를 수동 입력하지 않는다.

Reviewer packet의 허용 필드는 정제된 원 요청, 인수 조건, 리뷰 규칙, canonical task diff와 textual patch, 최종 source reference, attested 검증 record뿐이다. task diff와 patch는 base/current bytes 또는 안전한 gitlink object ID를 한 번 캡처한 immutable in-memory snapshot 하나에서 함께 파생한다. packet 조립 뒤 현재 diff를 다시 sampling해 조립 중 source 변경도 fail closed한다. 하네스는 정확한 packet 사본을 로컬 runtime에 만들고 tracked attestation에는 준비 중인 전체 packet digest를 저장한다. Reviewer stage가 그 digest를 소비한 뒤에는 `task_patch`와 `verification`을 포함한 필드별 digest, 전체 packet digest, 기존 task diff digest만 남긴다. Reviewer stage는 전달 사본의 전체 digest와 세 생성 필드를 모두 확인하고, validator는 최종 patch·verification digest와 현재 source를 다시 결합해 변조나 리뷰 후 변경을 거부한다. Researcher/Planner/Implementer 기록, 구현 대화, rationale, runtime log 필드는 거부한다.

현재 최초 설치에만 코드에 고정된 기준 commit `5c333fdb8fa8a1e2a70a856bb43cdbe65bac3773`의 bootstrap attestation을 허용한다. policy 값을 함께 바꿔 이 기준을 이동할 수 없다. bootstrap diff는 하네스 코드·정책·template·test·CI 파일과 승인 계획의 deploy gate, docs/rules, package, `.gitignore` allowlist로 제한되며 앱·임의 파일이 포함되면 실패한다. bootstrap은 과거 lifecycle event나 승인·리뷰를 소급 생성하지 않는다. 이후 기준 commit에는 정상 workflow attestation이 필요하다.

## 로컬 검증과 CI

```bash
npm run ai:harness:test
npm run ai:harness:check
```

validator는 필수 파일, JSON/TOML, role·sandbox, hook event/command allowlist, contract/template/schema/policy digest, `.ai-runtime` 미추적 상태, attestation 상태·scope path·diff digest·CI 재실행 검증, CI workflow, deploy `needs`를 확인한다.

`@.github/workflows/ai-harness-check.yml`은 pull request와 수동 실행에서 일반 test를 수행한다. `@.github/workflows/ai-harness-trusted-pr.yml`은 `pull_request_target`에서 base branch의 validator를 `trusted` 경로에, PR head를 `candidate` 경로에 checkout하고 PR의 Python/test를 실행하지 않은 채 정적 구조·attestation과 trusted 코드에 고정된 safe Git 명령만 검사한다. candidate policy의 command ID나 argv는 성공·실패 경로 어디에서도 실행 자료로 사용하지 않으며, candidate policy 또는 integrity 검사가 실패하면 attestation 재실행 전에 중단하되 본문 없는 실패 report는 계속 만든다. 권한은 `contents: read`뿐이며 secret과 write 권한을 사용하지 않는다. `@.github/workflows/deploy-frontend.yml`은 main에 merge된 workflow의 gate를 선행 job으로 실행한다.

세 gate는 baseline/validator 실패를 수집하고, 정상 report가 없으면 본문 없는 fallback failure report를 만든다. artifact는 `always()`와 `if-no-files-found: error`로 7일 보존하고 마지막 enforcement가 baseline/unit/validator 실패를 job 실패로 반영한다. deploy gate가 실패하면 GHCR login/build/push와 SSH 배포 job은 시작하지 않는다.

PR 기준은 `pull_request.base.sha`, push 기준은 `github.event.before`를 사용한다. `workflow_dispatch`는 `base_commit` input이 필수이며 해당 commit의 존재와 HEAD ancestor 여부를 확인한다. 따라서 PR/push에 여러 commit이 있어도 전체 범위를 검사하며 `HEAD^`로 마지막 commit만 추측하지 않는다. 수동 실행자는 비교하려는 여러 commit 직전의 ancestor SHA를 입력해야 한다.

GitHub branch protection API는 이 설치가 변경하지 않는다. 저장소 관리자는 GitHub ruleset/branch protection에서 `AI harness check / harness-check`와 특히 `AI harness trusted PR gate / trusted-harness-check`를 required workflow/status check로 지정해야 한다. trusted gate가 default branch에 먼저 존재하고 required로 설정돼야 같은 PR이 자기 workflow와 validator를 no-op으로 바꾸는 우회를 base branch 코드가 차단할 수 있다.

## 한계

- repo-local hook은 사용자의 trust 승인과 Codex hook 지원에 의존하며, 사용자가 hook을 비활성화한 실행 자체를 암호학적으로 증명하지 못한다.
- attestation과 digest는 구조·일관성 검사용 준수 진술이지 서명이 아니다. 실제 사람이 승인했는지, fresh blind Reviewer가 수행했는지, 수기 JSON이 정당한 작성자에게서 왔는지는 외부 신뢰 root 없이 암호학적으로 증명하지 못한다.
- PR branch의 validator와 integrity manifest를 함께 바꾸는 행위는 그 branch workflow만으로 암호학적으로 막지 못한다. default branch의 trusted workflow와 required ruleset이 저장소 밖 신뢰 경계를 제공해야 하며, 별도 서명 인프라는 범위 밖이다.
- 정규식 정제는 알려진 private key/JWT/secret assignment/PII 형식을 다루지만 전용 DLP를 대체하지 않는다.
- command hook은 같은 event에서 동시에 실행될 수 있고 lifecycle logging은 실행 차단 보안 경계가 아니다.
- `SessionEnd`는 주 thread 종료 시점에만 실행되고 subagent에는 실행되지 않는다.

## 롤백

1. 먼저 `@.codex/hooks.json`을 제거하거나 `[features].hooks = false`로 설정해 로컬 기록을 중지한다.
2. ruleset에서 일반 gate와 trusted gate의 required status check를 먼저 해제한다.
3. `@.github/workflows/deploy-frontend.yml`에서 `harness-check` job과 두 `needs` 연결을 함께 되돌린다.
4. `@.github/workflows/ai-harness-check.yml`, `@.github/workflows/ai-harness-trusted-pr.yml`, `@.agents/ai-harness`, `@.agents/prompts`, `@scripts/ai_harness`와 문서 연결을 같은 변경으로 되돌린다.
5. 필요하면 Git에서 제외된 `.ai-runtime`을 로컬 보존 정책에 따라 별도로 백업하거나 삭제한다. 이 작업은 원격 DB나 외부 logging 서비스에 영향을 주지 않는다.
