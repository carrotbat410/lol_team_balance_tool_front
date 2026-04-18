# Workflow Rules

- 수정 전 관련 파일만 읽고, 영향 범위를 한 문장으로 정리합니다.
- UI 수정 후에는 전체 리팩터링보다 해당 화면/컴포넌트만 다룹니다.
- 배포 파일을 수정하면 `deploy/app-server/docker-compose.yml` 과 `deploy/app-server/nginx/default.conf` 를 함께 확인합니다.
- 서버 관련 값은 코드에 직접 박지 말고 build arg 또는 환경변수 흐름을 유지합니다.
- 큰 구조 변경이 아니면 전체 프로젝트를 뒤흔드는 정리는 하지 않습니다.
