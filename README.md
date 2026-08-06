## 🔗 프로젝트 관련 링크
> <a href="https://lolcivilwarhelper.kro.kr/team-balancer" target="_blank">서비스 URL(운영중)</a>
- <a href="https://github.com/carrotbat410/lol_team_balance_tool_back" target="_blank">백엔드 Repo</a>

<br></br>

## 💻 프로젝트 소개
> 롤 내전 도우미 Ver.2 (FrontEnd)
>
> 롤 내전 도우미에서 소환사를 추가하고 드래그앤드롭으로 팀을 배치해보세요!

<img width="1710" height="865" alt="롤 내전 도우미 메인 화면" src="https://github.com/user-attachments/assets/bd96829e-3325-43f2-9574-e53d474918eb" />

- 롤 내전 게임 시, 참가자를 추가하고 티어 기반으로 균형 있는 팀 결과를 확인할 수 있는 서비스입니다.
- 라이엇 API로 조회된 소환사 정보를 화면에 표시하고, 드래그앤드롭으로 팀 배치를 조정할 수 있습니다.
- 팀짜기 사용법, 커뮤니티, 관리자 페이지, 방문자 통계 화면을 제공합니다.

## 📚 기술 스택

| 기술 | 설명 |
|---|---|
| `Next.js 15.5.20` | React 기반 프론트엔드 애플리케이션 구성 |
| `Fetch API` | Spring Boot 백엔드 REST API 호출 |
| `JWT` | 로그인 토큰 기반 인증 상태 관리 |
| `Cookie / localStorage` | 로그인 상태, 권한, 방문자 ID, 팀 배치 정보 저장 |
| `Docker`, `Docker Compose` | 프론트엔드, 백엔드, MySQL 컨테이너 통합 운영 |
| `GitHub Actions` | CI/CD 자동화 |
| `GHCR` | Docker 이미지 저장소 |

## ⚙ 서비스 아키텍처
<img width="1800" height="1180" alt="lol-civilwar-helper-architecture" src="https://github.com/user-attachments/assets/1951d64a-8043-4f2a-893b-85834914c816" />

## 📁 ERD
<img width="944" height="872" alt="lol-civilwar-helper-erd" src="https://github.com/user-attachments/assets/6534b190-771f-45ea-895a-190d21a24d69" />
