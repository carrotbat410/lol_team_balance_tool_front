# Verification Rules

- 로컬 전체 빌드는 기본적으로 생략하고 최종 빌드는 GitHub Actions에서 검증합니다.
- 문구/주석/README 변경: 빌드와 전체 테스트를 생략합니다.
- CSS/단순 UI 변경: 빌드를 생략하고 필요한 화면만 수동 확인하거나 관련 파일만 검사합니다.
- 작은 JavaScript 로직 변경: 관련 검사나 관련 테스트만 실행합니다.
- 라우팅, Next.js 설정, 빌드 시점 렌더링 변경: `npm run build`
- 의존성, Dockerfile, Docker Compose, 배포 설정 변경: `npm run build` 또는 해당 이미지 빌드를 확인합니다.
- 사용자가 빌드나 전체 테스트를 명시적으로 요청한 경우 실행합니다.
- nginx/compose 변경: 경로와 upstream 이름이 실제 서비스 이름과 맞는지 확인
- AI harness/agent/CI 변경: `npm run ai:harness:check`
- 전체 E2E가 없으므로, 관련 페이지 하나를 직접 확인하는 수동 검증을 허용합니다.
