# 서버 이전 핸드오프

이 문서는 기존 서버에서 확인한 운영 정보와 보안 이슈를 바탕으로, 새 서버에 이전할 때 그대로 따라가야 할 기준을 정리한 문서다.

## 목적

- 기존 해킹 이력이 있는 서버를 더 이상 신뢰하지 않는다.
- 새 서버는 기존 서버 파일을 복사하지 않고, **git 원본 + DB 백업 + 새 비밀값** 기준으로 재구성한다.
- 새 서버는 단순 서비스 실행이 아니라 **Docker + CI/CD** 기반으로 운영한다.

## 가장 중요한 원칙

1. 기존 서버의 실행 파일, 빌드 산출물, 홈 디렉토리 통복사는 금지한다.
2. 코드 배포는 반드시 git clone 기준으로 새 서버에 올린다.
3. 비밀값은 가능하면 전부 새로 발급한다.
4. 외부 공개 포트는 `80`, `443`만 남긴다.
5. Node/Next/Spring/MySQL은 직접 포트 공개 대신 reverse proxy 또는 내부 네트워크로만 연결한다.
6. root SSH 로그인은 차단 상태를 유지한다.

## 기존 운영 구조 요약

### 도메인

- 메인 서비스: `lolcivilwarhelper.kro.kr`
- 게임 서비스: `game.lolcivilwarhelper.kro.kr`

### 서비스 역할

- 롤내전도우미 프론트: Next.js
- 롤내전도우미 백엔드: Spring Boot
- 게임 웹: Next.js
- 게임 서버: Node.js + Socket.IO
- DB: MySQL 8 Docker
- 앞단: Nginx

### 기존 내부 포트 구조

- 메인 프론트: `3000`
- 메인 백엔드: `8080`
- 게임 웹: `4000`
- 게임 서버: `5000`
- MySQL: `3306`

### 새 서버 권장 구조

- 외부 공개:
  - `80`
  - `443`
- 내부 통신:
  - main-front: `3000`
  - main-back: `8080`
  - mundo-web: `4000`
  - mundo-game: `5000`
  - mysql: `3306`

즉, 새 서버에서는 `3000/4000/5000/8080/3306`를 외부에 직접 열지 않는다.

## 보안 이력 요약

기존 서버는 실제 침해 흔적이 있었다.

확인된 주요 이슈:

- `c3pool`, `xmrig`, `systemworker`, `let`, `zzh` 등 채굴/드로퍼 계열 흔적 발견
- `root@puppetserver` 비정상 SSH 공개키 존재
- `root` SSH 로그인 차단 적용
- 일부 `next-server` 프로세스가 악성 `nc ... > let` 드로퍼의 부모 역할을 했음
- systemd 파일에 이상한 권한/immutable 속성이 걸려 있던 적이 있음

따라서 새 서버에서는:

- 기존 서버 파일 복사 금지
- SSH 키 재발급
- API 키/JWT/DB 비밀번호 재설정
- 최소 권한 원칙 적용

## 백업해둔 데이터

현재 로컬에 백업해둔 파일:

- DB 덤프:
  - `/Users/leechangmin/Documents/git-repos-carrotbat410/lol_team_balance_tool_front2/lol_team_balance_tool_dump_2026-04-18.sql.gz`
- DB 권한:
  - `/Users/leechangmin/Documents/git-repos-carrotbat410/lol_team_balance_tool_front2/lol_team_balance_tool_grants_2026-04-18.sql`

DB 이름:

- `lol_team_balance_tool`

테이블:

- `summoners`
- `users`

## 새 서버에서 해야 할 일

### 1. OS / 보안 초기 설정

- 새 서버 생성
- 새 SSH 키만 등록
- `PermitRootLogin no`
- 필요 시 `AllowUsers <admin-user>`
- 방화벽/클라우드 인바운드는 `80`, `443`, `22`만 최소 허용

### 2. 런타임 설치

- Docker
- Docker Compose 또는 compose plugin
- Nginx
- Certbot 또는 다른 인증서 자동화 수단

권장:

- 앱 런타임은 호스트에 직접 설치하지 않고 Docker 컨테이너로 운영

### 3. 코드 배포 방식

각 서비스는 반드시 git clone 기준으로 새로 배포:

- `lol_team_balance_tool_front2`
- `lol_team_balance_tool_back`
- `Mundo_dodgeball_game`

기존 서버 디렉토리 복사는 금지.

### 4. DB 복원

새 MySQL 컨테이너 띄운 뒤:

```bash
gunzip -c lol_team_balance_tool_dump_2026-04-18.sql.gz | mysql -u <USER> -p
```

단, 기존 권한 파일은 참고만 하고 그대로 재사용하지 않는 것을 권장한다.

### 5. 환경변수 재작성

기존 값은 참고만 하고, 가능하면 새 값으로 교체:

- DB 비밀번호
- JWT secret
- Riot API key
- 기타 외부 API key

### 6. Nginx reverse proxy

권장 라우팅:

- `https://lolcivilwarhelper.kro.kr` -> 메인 프론트
- `https://lolcivilwarhelper.kro.kr/api` -> 메인 백엔드
- `https://game.lolcivilwarhelper.kro.kr` -> 게임 웹
- `https://game.lolcivilwarhelper.kro.kr/socket.io/` -> 게임 서버

중요:

- 게임 프론트는 배포 시 `:5000` 직접 접속이 아니라 same-origin `/socket.io/` 프록시 구조를 사용해야 한다.

## 게임 서비스 관련 별도 메모

게임 서비스는 현재 로컬 코드에서 다음 방향으로 맞춰져 있다.

- 로컬 개발:
  - 웹 `4000`
  - 게임 서버 `4010`
- 배포:
  - 웹은 `game.lolcivilwarhelper.kro.kr`
  - 소켓은 `window.location.origin + /socket.io`
  - 직접 `https://host:5000` 접근이 아님

즉 새 서버에서도 nginx가 `/socket.io/`를 게임 서버 컨테이너로 프록시해야 한다.

## CI/CD 기준 권장 구조

새 서버에서는 수동 `npm start`, `pnpm start`, `systemd` 직기동보다 아래 구성을 우선한다.

### 추천 구조

- GitHub Actions
- Docker image build
- Registry push
- 서버에서는 docker compose pull + up -d

### 서비스 분리 예시

- `main-front`
- `main-back`
- `mundo-web`
- `mundo-game`
- `mysql`
- `nginx`

### 배포 원칙

- `.env`는 서버 또는 CI secret로 관리
- 컨테이너 이미지는 immutable tag 또는 commit SHA 사용
- compose 파일은 서버에서 관리하되, 앱 코드는 이미지로 배포

## 새 서버 이전 시 체크리스트

### 필수

- [ ] 새 서버 생성
- [ ] 새 SSH 키 등록
- [ ] root SSH 차단
- [ ] Docker/Compose/Nginx 설치
- [ ] 메인 프론트 fresh clone 또는 이미지 배포
- [ ] 메인 백엔드 fresh clone 또는 이미지 배포
- [ ] 게임 프론트 fresh clone 또는 이미지 배포
- [ ] 게임 서버 fresh clone 또는 이미지 배포
- [ ] MySQL 새 컨테이너 생성
- [ ] DB 덤프 복원
- [ ] 새 비밀값 적용
- [ ] Nginx reverse proxy 설정
- [ ] HTTPS 인증서 발급
- [ ] `80/443`만 외부 공개 확인

### 보안

- [ ] `3000/4000/5000/8080/3306` 외부 차단
- [ ] root SSH 비활성화
- [ ] 운영 계정만 허용
- [ ] 불필요한 크론/서비스 없음 확인
- [ ] `/tmp`, `/dev/shm`, 홈 디렉토리 이상 파일 점검

## 다음 서버에서 이 문서를 어떻게 쓸지

새 서버를 띄운 뒤, 아래 요청으로 이어서 작업하면 된다.

예시:

`docs/server-migration-handoff.md를 기준으로 새 서버 이전 작업을 이어서 진행해줘. Docker + CI/CD 기준으로 구성하고, 기존 DB 덤프를 복원하는 순서부터 잡아줘.`

## 비고

이 문서는 “기억” 대체용이다. 다음 작업 시 이 문서를 기준으로 이어가면 된다.
