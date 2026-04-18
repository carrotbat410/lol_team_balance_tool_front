# Claude Harness

이 저장소는 롤 내전 도우미 프론트엔드입니다.

## 먼저 읽기
- 프로젝트 개요: @README.md
- 실행/빌드 스크립트: @package.json
- 앱 서버 배포 구성: @deploy/app-server/docker-compose.yml
- nginx 프록시 설정: @deploy/app-server/nginx/default.conf

## 작업 원칙
- 변경은 작고 명확하게 유지합니다.
- 서버/배포 설정을 건드릴 때는 프론트 단독이 아니라 앱 서버 전체 흐름을 같이 확인합니다.
- 이미 있는 문서는 `@파일명`으로 참조하고, 같은 설명을 새로 복붙하지 않습니다.
- 비밀값은 하드코딩하지 않습니다. 예시는 `.env.example` 또는 배포 문서로만 남깁니다.

## 빠른 워크플로우
1. 관련 파일만 읽고 범위를 좁힙니다.
2. 코드 수정 후 최소 검증을 먼저 합니다.
3. 배포 파일을 바꿨다면 nginx 경로와 compose 경로가 맞는지 같이 봅니다.
4. 전체 테스트 대신 관련 검증만 우선 실행합니다.

## 검증 핵심
- 기본 빌드: `npm run build`
- 로컬 개발: `npm run dev`
- 린트: `npm run lint`
- Docker 이미지 확인이 필요하면 `Dockerfile` 기준으로 앱 서버 compose 흐름을 봅니다.

## 도메인 용어
- 롤 내전 도우미: 메인 서비스 전체
- 프론트: 이 저장소의 Next.js 앱
- 백엔드: 별도 Spring Boot 저장소
- 앱 서버: nginx + 프론트 + 백엔드 + 게임 서비스가 함께 도는 서버
- `/team-balancer`: 메인 사용자 진입 경로
- `/api`: 백엔드 프록시 경로

## 자주 하는 판단
- 단순 UI 변경: `npm run lint` 또는 필요한 화면만 수동 확인
- 라우팅/렌더링 변경: `npm run build`
- 배포 설정 변경: `docker-compose.yml`, nginx 설정, 프론트 빌드 인자를 같이 확인

## 가비지 컬렉션
- 커밋/PR 전에 생성 산출물과 임시 파일을 정리합니다.
- 추적하지 않을 것: `.next`, `node_modules`, 로그, OS 잡파일
- 실수로 생성된 덤프/백업/로컬 IDE 파일은 목적이 없으면 남기지 않습니다.

## 세부 규칙
- 워크플로우: @.claude/rules/workflow.md
- 검증: @.claude/rules/verification.md
- 용어: @.claude/rules/domain.md
- 정리 기준: @.claude/rules/garbage-collection.md
