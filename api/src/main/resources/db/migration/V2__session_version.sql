-- 비밀번호 재설정 · 변경 · 탈퇴 때 그 사람의 '다른 세션'을 끊기 위한 번호.
-- 로그인할 때 세션에 이 값을 적어 두고, 요청마다 DB 값과 다르면 그 세션을 버린다 (SessionVersionFilter).
ALTER TABLE users ADD COLUMN session_version INT NOT NULL DEFAULT 0;
