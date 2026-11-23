-- 서비스 운영 표 (부록) — 작업 기록 · 모델 레지스트리 · 미리 계산한 추천 · 실제 성적 · RAG 문서
-- 모두 파이썬(작업 프로세스 · FastAPI)이 쓰고, Spring 은 04_service_views.sql 의 뷰만 읽는다

-- 작업 한 번 = 한 줄 (수집 · 추천 계산 · 재학습 …). 실패해도 남는다
CREATE TABLE IF NOT EXISTS job_run (
  run_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  job        VARCHAR(40) NOT NULL,
  trigger_by VARCHAR(60) NOT NULL DEFAULT 'schedule',        -- schedule · admin:<이메일> · cli
  started_at DATETIME NOT NULL,
  ended_at   DATETIME NULL,
  status     ENUM('running','ok','fail','skipped') NOT NULL DEFAULT 'running',
  summary    VARCHAR(300) NULL,                              -- 한 줄 요약 (화면에 그대로)
  detail     JSON NULL,
  KEY ix_job_started (job, started_at)
) ENGINE=InnoDB;

-- 모델 레지스트리: 규칙도 한 줄 (rule_yesterday) — 챔피언은 언제나 하나
CREATE TABLE IF NOT EXISTS model_registry (
  version        VARCHAR(40) NOT NULL PRIMARY KEY,           -- reco_v1 · logistic-20261019-0300 · rule_yesterday
  kind           ENUM('rule','logistic','gbm') NOT NULL,
  status         ENUM('candidate','champion','rejected','retired') NOT NULL,
  created_at     DATETIME NOT NULL,
  fit_from       DATE NULL,
  fit_until      DATE NULL,                                  -- 학습에 쓴 마지막 날
  stats_until    DATE NULL,                                  -- 요일 보정 · 평년 수온 계산의 마지막 날 (서비스 특성도 이 날 기준)
  eval_from      DATE NULL,
  eval_until     DATE NULL,
  n_train        INT NULL,
  n_groups       INT NULL,                                   -- 평가한 (품목, 날짜) 묶음 수
  p_at_3         DECIMAL(5,4) NULL,
  hit_at_3       DECIMAL(5,4) NULL,
  ndcg_at_3      DECIMAL(5,4) NULL,
  rule_p_at_3    DECIMAL(5,4) NULL,                          -- 같은 창에서 규칙
  champ_version  VARCHAR(40) NULL,                           -- 비교한 당시 챔피언
  champ_p_at_3   DECIMAL(5,4) NULL,
  diff           DECIMAL(6,4) NULL,                          -- 후보 − 챔피언
  ci_low         DECIMAL(6,4) NULL,
  ci_high        DECIMAL(6,4) NULL,
  per_species    JSON NULL,                                  -- {"방어": {"p": .., "champ": .., "days": ..}, …}
  gates          JSON NULL,                                  -- 교체 조건 5개 각각의 결과와 숫자
  decision       VARCHAR(300) NULL,                          -- 사람이 읽는 한 줄
  features       JSON NULL,
  file_path      VARCHAR(200) NULL,
  promoted_at    DATETIME NULL,
  retired_at     DATETIME NULL,
  KEY ix_registry_status (status)
) ENGINE=InnoDB;

-- 교체 · 거절 · 되돌리기 이력
CREATE TABLE IF NOT EXISTS promotion_log (
  log_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  at           DATETIME NOT NULL,
  action       ENUM('promote','reject','rollback','bootstrap') NOT NULL,
  from_version VARCHAR(40) NULL,
  to_version   VARCHAR(40) NULL,
  actor        VARCHAR(80) NOT NULL,                         -- auto · admin:<이메일> · bootstrap
  reason       VARCHAR(300) NULL
) ENGINE=InnoDB;

-- 미리 계산한 추천: 챔피언과 규칙을 둘 다 저장한다 → 7일 뒤 두 방법의 실제 P@3 을 비교
CREATE TABLE IF NOT EXISTS recommendation (
  rec_date      DATE NOT NULL,
  species       VARCHAR(20) NOT NULL,
  model_version VARCHAR(40) NOT NULL,
  area_id       TINYINT UNSIGNED NOT NULL,
  rnk           TINYINT UNSIGNED NOT NULL,                   -- 1 ~ 후보 수 (전체 순위를 저장 → 성적 계산)
  score         DECIMAL(6,4) NOT NULL,
  usual_kg      INT UNSIGNED NOT NULL,
  reasons       JSON NULL,
  warnings      JSON NULL,
  feats         JSON NULL,                                   -- 설명(RAG)에 쓰는 숫자: 어제 배수 · 7일 평균 배수 · 수온 …
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (rec_date, species, model_version, area_id),
  KEY ix_rec_rank (rec_date, species, model_version, rnk),
  CONSTRAINT fk_rec_area FOREIGN KEY (area_id) REFERENCES area (area_id),
  CONSTRAINT fk_rec_species FOREIGN KEY (species) REFERENCES species (species)
) ENGINE=InnoDB;

-- 순위에서 뺀 권역과 이유 ("왜 우리 동네는 없나")
CREATE TABLE IF NOT EXISTS recommendation_excluded (
  rec_date      DATE NOT NULL,
  species       VARCHAR(20) NOT NULL,
  model_version VARCHAR(40) NOT NULL,
  area_id       TINYINT UNSIGNED NOT NULL,
  reason        VARCHAR(120) NOT NULL,
  PRIMARY KEY (rec_date, species, model_version, area_id)
) ENGINE=InnoDB;

-- 계산 한 번의 정보: 어느 모델을 서비스했나 · 자료는 언제까지였나 · 어제 위판이 얼마나 채워졌나
CREATE TABLE IF NOT EXISTS rec_run (
  rec_date       DATE NOT NULL,
  species        VARCHAR(20) NOT NULL,
  served_version VARCHAR(40) NOT NULL,                       -- 화면에 보이는 쪽 (계산 당시 챔피언)
  data_last_day  DATE NOT NULL,                              -- 위판 자료의 마지막 날 (= rec_date − 1 이 정상)
  yesterday_fill DECIMAL(6,3) NULL,                          -- 어제 위판량 ÷ 최근 28일 판매일 중앙값
  candidates     TINYINT UNSIGNED NOT NULL,
  computed_at    DATETIME NOT NULL,
  PRIMARY KEY (rec_date, species)
) ENGINE=InnoDB;

-- 라벨이 확정된 날의 실제 성적 (모델 · 규칙 각각)
CREATE TABLE IF NOT EXISTS live_eval (
  rec_date      DATE NOT NULL,
  species       VARCHAR(20) NOT NULL,
  model_version VARCHAR(40) NOT NULL,
  p_at_3        DECIMAL(5,4) NOT NULL,
  hit_at_3      DECIMAL(5,4) NOT NULL,
  ndcg_at_3     DECIMAL(5,4) NOT NULL,
  n_labeled     TINYINT UNSIGNED NOT NULL,                   -- 라벨이 있는 권역 수
  good_areas    JSON NULL,                                   -- 실제로 '좋은 날'이었던 권역 이름들
  evaluated_at  DATETIME NOT NULL,
  PRIMARY KEY (rec_date, species, model_version)
) ENGINE=InnoDB;

-- RAG 문서 (특보 · 법령 · 서비스 설명) — 원문은 여기, 색인은 파일(FAISS · BM25)
CREATE TABLE IF NOT EXISTS rag_doc (
  doc_id     VARCHAR(80) NOT NULL PRIMARY KEY,
  kind       ENUM('alert','law','rule','guide','service') NOT NULL,
  title      VARCHAR(200) NOT NULL,
  source     VARCHAR(100) NOT NULL,
  doc_date   DATE NULL,
  body       MEDIUMTEXT NOT NULL,
  meta       JSON NULL,
  loaded_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB
;

-- 관리자 수동 실행 요청 — Spring → FastAPI 가 넣고, 작업 프로세스(worker)가 10초마다 꺼내 실행한다
CREATE TABLE IF NOT EXISTS job_queue (
  queue_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  job          VARCHAR(40) NOT NULL,
  params       JSON NULL,
  requested_by VARCHAR(80) NOT NULL,
  requested_at DATETIME NOT NULL,
  status       ENUM('queued','running','done','fail') NOT NULL DEFAULT 'queued',
  run_id       BIGINT UNSIGNED NULL,
  KEY ix_queue_status (status, queue_id)
) ENGINE=InnoDB
