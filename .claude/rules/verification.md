# Verification Rules

- UI/문구 변경: `npm run lint`
- 라우팅/빌드 영향 변경: `npm run build`
- Dockerfile 변경: 가능하면 빌드까지 확인
- nginx/compose 변경: 경로와 upstream 이름이 실제 서비스 이름과 맞는지 확인
- 전체 E2E가 없으므로, 관련 페이지 하나를 직접 확인하는 수동 검증을 허용합니다.
