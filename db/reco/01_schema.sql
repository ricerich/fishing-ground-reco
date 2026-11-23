-- 어장 위치 추천 — 데이터 구축 스키마 (실습 P4 그대로 + 서비스 표는 03_service.sql)
-- 데이터베이스 reco (파이썬 소유) · MariaDB 10.11 이상 · utf8mb4
-- 실행: ai/scripts/init_db.py 가 데이터베이스 · 계정을 만든 뒤 이 파일을 차례로 실행한다

-- ── 기준 정보 ───────────────────────────────────────────────

-- 1) 권역 = 이 프로젝트의 '어장'. 대표 위치는 권역 조위관측소 좌표 (reco/markets.py 의 AREAS)
CREATE TABLE IF NOT EXISTS area (
  area_id        TINYINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  area_name      VARCHAR(20)  NOT NULL,                 -- 포항·영덕 …
  station_code   VARCHAR(10)  NOT NULL,                 -- 국립해양조사원 DT_0091 …
  station_name   VARCHAR(20)  NOT NULL,
  lat            DECIMAL(8,5) NOT NULL,
  lon            DECIMAL(8,5) NOT NULL,
  fcst_reg_local VARCHAR(10)  NULL,                     -- 기상청 해상국지 예보구역 (P2)
  fcst_reg_broad VARCHAR(10)  NULL,                     -- 기상청 해상광역 예보구역
  UNIQUE KEY uq_area_name (area_name),
  UNIQUE KEY uq_area_station (station_code)
) ENGINE=InnoDB;

-- 2) 위판장: (조합, 위판장) 쌍이 유일. 권역에 넣지 않은 곳(서해 · 내륙)은 area_id = NULL
CREATE TABLE IF NOT EXISTS market (
  market_id   SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  mxtr_nm     VARCHAR(50)  NOT NULL,                    -- 조합 (부산시수산업협동조합)
  csmtmkt_nm  VARCHAR(50)  NOT NULL,                    -- 위판장 (다대위판장)
  area_id     TINYINT UNSIGNED NULL,
  note        VARCHAR(100) NULL,                        -- 검토 메모 (P3 미션)
  UNIQUE KEY uq_market (mxtr_nm, csmtmkt_nm),
  CONSTRAINT fk_market_area FOREIGN KEY (area_id) REFERENCES area (area_id)
) ENGINE=InnoDB;

-- 2-1) 품목: 3개뿐이지만 표로 둔다 — 뷰에서 'SELECT DISTINCT species FROM auction_daily' 를 쓰면 40초 걸린다 (P4 미션)
CREATE TABLE IF NOT EXISTS species (
  species   VARCHAR(20) NOT NULL PRIMARY KEY,           -- 고등어 · 방어 · 삼치
  note      VARCHAR(50) NULL
) ENGINE=InnoDB;

-- 3) 달력: 위판이 없는 날도 '행'이 있어야 0 을 셀 수 있다 (P3 의 '빠진 날 펼치기'를 DB 에서)
CREATE TABLE IF NOT EXISTS calendar (
  d        DATE    NOT NULL PRIMARY KEY,
  weekday  TINYINT NOT NULL,                            -- 0 월 … 6 일 (pandas 와 같게)
  holiday  VARCHAR(30) NULL                             -- 명절 · 공휴일 이름 (팀이 채움)
) ENGINE=InnoDB;

-- ── 사실(fact) 테이블 ─────────────────────────────────────────

-- 4) 위판 하루 집계: 위판장 × 품목 × 날짜 (건별 원본은 data/raw 에 그대로)
CREATE TABLE IF NOT EXISTS auction_daily (
  market_id   SMALLINT UNSIGNED NOT NULL,
  species     VARCHAR(20)  NOT NULL,                    -- 고등어 · 방어 · 삼치 (정확히 같은 이름만)
  sale_date   DATE         NOT NULL,
  weight_kg   DECIMAL(12,1) NOT NULL,
  amount_won  BIGINT UNSIGNED NOT NULL,
  n_rows      INT UNSIGNED NOT NULL,                    -- 위판 건수
  loaded_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (market_id, species, sale_date),          -- 다시 넣어도 중복 없음 (늦게 채워진 위판 → 덮어쓰기)
  KEY ix_auction_date (sale_date, species),
  CONSTRAINT fk_auction_market FOREIGN KEY (market_id) REFERENCES market (market_id),
  CONSTRAINT fk_auction_species FOREIGN KEY (species) REFERENCES species (species)
) ENGINE=InnoDB;

-- 5) 관측 하루 요약: 권역(관측소) × 날짜. 하루 18시간 미만이면 값은 NULL
CREATE TABLE IF NOT EXISTS obs_daily (
  area_id     TINYINT UNSIGNED NOT NULL,
  obs_date    DATE NOT NULL,
  wtem_mean   DECIMAL(5,2) NULL,  wtem_min DECIMAL(5,2) NULL,  wtem_max DECIMAL(5,2) NULL,
  artmp_mean  DECIMAL(5,2) NULL,
  atmpr_mean  DECIMAL(6,2) NULL,
  wspd_mean   DECIMAL(5,2) NULL,
  gust_max    DECIMAL(5,2) NULL,
  tide_range  DECIMAL(6,1) NULL,
  sal_mean    DECIMAL(5,2) NULL,
  hours       TINYINT UNSIGNED NOT NULL,
  PRIMARY KEY (area_id, obs_date),
  CONSTRAINT fk_obs_area FOREIGN KEY (area_id) REFERENCES area (area_id)
) ENGINE=InnoDB;

-- 6) 해상예보: 발표마다 쌓는다 (같은 날을 여러 번 예보 → 발표시각까지 키에 넣어야 덮어쓰지 않는다)
CREATE TABLE IF NOT EXISTS sea_forecast (
  area_id   TINYINT UNSIGNED NOT NULL,
  tm_fc     DATETIME NOT NULL,                          -- 발표 시각
  fc_date   DATE NOT NULL,
  ampm      ENUM('오전','오후') NOT NULL,
  reg_id    VARCHAR(10) NOT NULL,
  wh1 DECIMAL(3,1) NULL, wh2 DECIMAL(3,1) NULL,         -- 파고 m
  ws1 TINYINT UNSIGNED NULL, ws2 TINYINT UNSIGNED NULL, -- 풍속 m/s
  wf        VARCHAR(30) NULL,
  rn_yn     TINYINT NULL,
  PRIMARY KEY (area_id, tm_fc, fc_date, ampm),
  KEY ix_fc_date (fc_date, area_id),
  CONSTRAINT fk_fc_area FOREIGN KEY (area_id) REFERENCES area (area_id)
) ENGINE=InnoDB;

-- 7) 바다낚시지수: 받은 날(collected)마다 6일 예보 1,400건. 장소 → 가까운 권역은 area_id 로
CREATE TABLE IF NOT EXISTS fishing_index (
  collected   DATE NOT NULL,
  place       VARCHAR(40) NOT NULL,
  fc_date     DATE NOT NULL,
  noon        VARCHAR(4) NOT NULL,                      -- 오전 · 오후 · 일
  target_fish VARCHAR(10) NOT NULL,
  area_id     TINYINT UNSIGNED NULL,                    -- 가장 가까운 권역 (적재할 때 계산)
  lat DECIMAL(8,5) NULL, lon DECIMAL(8,5) NULL,
  tide_phase  VARCHAR(10) NULL,                         -- 대조기 · 소조기 …
  max_wave    DECIMAL(4,2) NULL, max_wspd DECIMAL(4,1) NULL, max_wtem DECIMAL(4,1) NULL,
  total_index ENUM('매우나쁨','나쁨','보통','좋음','매우좋음') NOT NULL,
  PRIMARY KEY (collected, place, fc_date, noon, target_fish),
  KEY ix_fi_area (area_id, fc_date),
  CONSTRAINT fk_fi_area FOREIGN KEY (area_id) REFERENCES area (area_id)
) ENGINE=InnoDB;

-- 7-1) 학습용 계층: 권역 × 품목 × 날짜 위판 합 — 적재 뒤 v_area_sales 로 다시 채운다 (reco/load.py)
--      같은 내용의 뷰를 바로 조인하면 40초, 기본키가 있는 테이블로 만들어 두면 0.06초 (P4 실측)
CREATE TABLE IF NOT EXISTS area_sales (
  area_id    TINYINT UNSIGNED NOT NULL,
  species    VARCHAR(20) NOT NULL,
  sale_date  DATE NOT NULL,
  weight_kg  DECIMAL(14,1) NOT NULL,
  amount_won BIGINT UNSIGNED NOT NULL,
  n_rows     INT UNSIGNED NOT NULL,
  PRIMARY KEY (area_id, species, sale_date)
) ENGINE=InnoDB;

-- 8) 수집 로그 (data/collect_log.jsonl)
CREATE TABLE IF NOT EXISTS collect_log (
  log_id   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  logged   DATETIME NOT NULL,
  source   VARCHAR(20) NOT NULL,
  target   VARCHAR(60) NOT NULL,
  status   VARCHAR(10) NOT NULL,
  n_rows   INT NOT NULL,
  seconds  DECIMAL(7,2) NOT NULL,
  note     VARCHAR(200) NULL,
  UNIQUE KEY uq_log (logged, source, target, status)
) ENGINE=InnoDB;
