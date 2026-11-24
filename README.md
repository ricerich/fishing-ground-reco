# 어장 위치 추천 서비스 (fishing-ground-reco)

AI·데이터 기반 해양·수산 서비스 개발자 과정 **U3-P 프로젝트 부록** — 실습에서 설계까지 한 어장 추천을
회원 · 화면 · AI 서버 · 재학습 · RAG 가 모두 돌아가는 서비스로 완성한 참고 구현이다.

> “내일 방어는 어느 권역이 평소보다 잘 잡힐까?” → 권역 14곳 중 Top-3 와 근거 · 경고 · 제외 이유

## 구성

| 폴더 | 무엇 | 기술 | 주소 |
|---|---|---|---|
| `web/` | 화면 | Next.js 16.4 · React 19.3 · TypeScript 6.0 · Tailwind CSS 4.3 | http://localhost:3000 |
| `api/` | 서비스 서버 — 회원 · 추천 조회 · RAG 중계 · 관리자 | Spring Boot 4.1.3 · Java 21 · Gradle | :8080 |
| `ai/` | AI 서버(FastAPI) + 작업 프로세스(수집 · 추천 계산 · 재학습 · 교체) | Python 3.12+ · FastAPI · scikit-learn | :8000 |
| `db/` | 데이터베이스 `reco`(파이썬 소유) 표 · 뷰 | MariaDB 10.11+ | :3306 |
| `docs/` | 교안용 캡처 · 실습 문서 | | |

- 브라우저는 Next.js 와 Spring 만 부른다. FastAPI 는 Spring 이 내부 토큰(`X-Internal-Token`)으로만 부른다.
- 추천은 매일 미리 계산해 표에 넣고, 화면은 표를 읽는다 → AI 서버가 꺼져도 추천은 보인다.
- DB 는 하나, 스키마 둘: `reco`(파이썬 — 수집 · 학습 · 추천) / `app`(Spring — 회원 · 피드백, Flyway). Spring 은 `reco` 의 `v_svc_*` 뷰만 읽는다.

PRD(요구사항 정의)는 별도 문서로 관리한다. 숫자의 출발점은 실습 U3-P5 · P6 결과다 —
시험 P@3 로지스틱 0.606 · 규칙(어제 좋았던 곳) 0.601 · 무작위 0.349, 모델과 규칙은 **같은 수준**.

## 처음 설치 (한 번)

1. MariaDB 10.11 이상, Java 21, Node.js 20.9 이상, Python 3.12 이상, 개발용 메일함 [Mailpit](https://mailpit.axllent.org) 을 설치한다.
2. `.env.example` 을 `.env` 로 복사하고 비밀번호 · `INTERNAL_TOKEN` 을 채운다 (`.env` 는 올리지 않는다).
3. AI 쪽
   ```bash
   cd ai
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip
   .venv/bin/python scripts/init_db.py                # 데이터베이스 reco · app, 계정 reco_ai · reco_api, 표 · 뷰
   .venv/bin/python -m reco.jobs run bootstrap_demo   # 시연 자료 적재 → reco_v1 → 7/1~오늘 추천 → 성적 채점 (약 15초)
   ```
4. 화면 쪽: `cd web && npm install`
5. Spring 은 처음 실행할 때 Gradle 이 라이브러리를 받는다 (`api/gradlew bootRun`).

## 실행

```bash
scripts/start_all.sh                                    # Windows: powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
```

기본 프로필은 `demo,mockoauth` — 시연 로그인과 모의 카카오 · 네이버(:9100)로 키 없이 회원 기능을 모두 돌려 볼 수 있다.
메일은 http://localhost:8025 (Mailpit). 실제 소셜 키로 바꾸는 법은 [2단계 안내](docs/guide/02_회원.md#실제-키로-바꾸기).

http://localhost:3000/status 에서 네 부분이 모두 ‘정상’인지 본 뒤, 통합 점검을 돌린다.

```bash
ai/.venv/bin/python scripts/check_all.py               # 항목별 OK / FAIL (회원 흐름 34개 포함)
```

## 시연 모드

`.env` 의 `DEMO_TODAY=2026-10-15` 는 ‘오늘’을 고정한다. 시연 자료(위판 · 관측)가 2026-10-14 까지라서
늘 같은 화면이 나오고, 작업 프로세스는 정해진 시각의 수집을 하지 않는다(관리자 요청은 실행).
실제 운영은 `DEMO_TODAY` 를 비우고 공공 OpenAPI 키를 넣는다.
시연 모드의 수집은 OpenAPI 대신 받아 둔 원본을 다시 적재하고 기록을 ‘재생’으로 남긴다. 관리자 화면(시연 관리자)에서
거절 · 교체(시연 시나리오) · 되돌리기 · 수집 실패 → 조건 1 거절을 차례로 재현할 수 있다 — [3단계 안내](docs/guide/03_수집_재학습_교체.md#4-세-가지-결과를-화면에서-재현하기-시연).
처음 상태로: `ai/.venv/bin/python -m reco.jobs run bootstrap_demo`

## 교안 캡처

```bash
node scripts/capture/capture.mjs all                   # docs/captures/phase<N>/<번호>-<장면>-pc.png · -mobile.png
```

## 단계

| 단계 | 내용 | 상태 |
|---|---|---|
| 0 | 저장소 · DB · 네 프로세스 health · 실행 스크립트 | 완료 |
| 1 | 추천 미리 계산 · Spring 추천 API · 해도 화면 | 완료 |
| 2 | 회원: 이메일 인증 · 재설정 · 카카오 · 네이버 · 구글 · 계정 연결 · 관리자 — [안내](docs/guide/02_회원.md) | 완료 |
| 3 | 수집 · 재학습 · 자동 교체 · 관리자 화면 — [안내](docs/guide/03_수집_재학습_교체.md) | 완료 |
| 4 | RAG: 추천 근거 설명 · 물어보기 — [안내](docs/guide/04_RAG.md) | 완료 |
| 5 | 추천 성적 · 피드백 · E2E · 통합 점검 | |
