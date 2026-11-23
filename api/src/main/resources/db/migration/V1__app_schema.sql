-- app 스키마 (Spring 소유) — Flyway 가 순서대로 한 번씩 실행한다. 이미 실행된 파일은 고치지 말고 V2, V3 … 를 더한다.

-- 회원: 로그인 수단(이메일 · 카카오 · 네이버 · 구글)과 무관한 '사람' 한 명
CREATE TABLE users (
  user_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  email        VARCHAR(190) NULL,                        -- 소셜 계정은 없을 수 있다 (카카오 이메일 미동의 등)
  email_verified BOOLEAN NOT NULL DEFAULT FALSE,
  display_name VARCHAR(60) NOT NULL,
  role         VARCHAR(10) NOT NULL DEFAULT 'USER',      -- USER · ADMIN
  status       VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',    -- PENDING(이메일 인증 전) · ACTIVE · DELETED
  created_at   DATETIME(6) NOT NULL,
  last_login_at DATETIME(6) NULL,
  KEY ix_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 로그인 수단: 한 사람에 여러 개. (provider, provider_user_id) 는 전체에서 하나 → 남의 계정에 연결 못 함
CREATE TABLE user_identity (
  identity_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id          BIGINT NOT NULL,
  provider         VARCHAR(10) NOT NULL,                 -- email · kakao · naver · google
  provider_user_id VARCHAR(190) NOT NULL,                -- email 이면 이메일 주소(소문자)
  provider_email   VARCHAR(190) NULL,
  linked_at        DATETIME(6) NOT NULL,
  UNIQUE KEY uq_identity (provider, provider_user_id),
  UNIQUE KEY uq_user_provider (user_id, provider),       -- 한 사람이 같은 제공자를 둘 연결하지 않음
  CONSTRAINT fk_identity_user FOREIGN KEY (user_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 이메일 로그인의 비밀번호 (BCrypt). 소셜만 쓰는 사람은 줄이 없다
CREATE TABLE password_credential (
  user_id        BIGINT PRIMARY KEY,
  password_hash  VARCHAR(100) NOT NULL,
  changed_at     DATETIME(6) NOT NULL,
  failed_count   INT NOT NULL DEFAULT 0,
  locked_until   DATETIME(6) NULL,
  CONSTRAINT fk_pw_user FOREIGN KEY (user_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 인증 · 재설정 토큰: 원문은 메일에만, DB 에는 SHA-256 해시. 1회용 · 만료
CREATE TABLE auth_token (
  token_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT NOT NULL,
  purpose     VARCHAR(20) NOT NULL,                      -- VERIFY_EMAIL · RESET_PASSWORD
  token_hash  CHAR(64) NOT NULL,
  created_at  DATETIME(6) NOT NULL,
  expires_at  DATETIME(6) NOT NULL,
  used_at     DATETIME(6) NULL,
  UNIQUE KEY uq_token_hash (token_hash),
  KEY ix_token_user (user_id, purpose),
  CONSTRAINT fk_token_user FOREIGN KEY (user_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 관심 품목 · 권역
CREATE TABLE favorite (
  user_id    BIGINT NOT NULL,
  kind       VARCHAR(10) NOT NULL,                       -- species · area
  value      VARCHAR(30) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (user_id, kind, value),
  CONSTRAINT fk_fav_user FOREIGN KEY (user_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 추천 피드백 (도움됨 · 안 됨) — 한 사람이 같은 추천(날짜 · 품목 · 권역)에 한 번
CREATE TABLE rec_feedback (
  feedback_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT NOT NULL,
  rec_date    DATE NOT NULL,
  species     VARCHAR(20) NOT NULL,
  area_name   VARCHAR(20) NOT NULL,
  model_version VARCHAR(40) NOT NULL,
  helpful     BOOLEAN NOT NULL,
  comment     VARCHAR(300) NULL,
  created_at  DATETIME(6) NOT NULL,
  UNIQUE KEY uq_feedback (user_id, rec_date, species, area_name),
  CONSTRAINT fk_fb_user FOREIGN KEY (user_id) REFERENCES users (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- RAG 질문 기록 (U2 qa_log 와 같은 생각)
CREATE TABLE rag_qa_log (
  qa_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id      BIGINT NULL,
  mode         VARCHAR(10) NOT NULL,                     -- ask · explain
  question     VARCHAR(500) NOT NULL,
  answer       TEXT NULL,
  sources      JSON NULL,
  cite_ok      BOOLEAN NULL,
  said_unknown BOOLEAN NULL,
  made_up      INT NULL,                                  -- 지어낸 인용 수
  llm          VARCHAR(60) NULL,
  seconds      DECIMAL(7,2) NULL,
  helpful      BOOLEAN NULL,
  created_at   DATETIME(6) NOT NULL,
  KEY ix_qa_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 관리자 행동 기록 (작업 실행 · 되돌리기)
CREATE TABLE admin_audit (
  audit_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id    BIGINT NOT NULL,
  action     VARCHAR(40) NOT NULL,
  target     VARCHAR(100) NULL,
  detail     VARCHAR(500) NULL,
  created_at DATETIME(6) NOT NULL,
  KEY ix_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
