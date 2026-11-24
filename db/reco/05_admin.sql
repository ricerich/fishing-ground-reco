-- 3단계: 관리자 화면용 — 몇 번 돌려도 같은 결과(멱등)
-- 수집 상태: '재생'(시연 — 받아 둔 원본 다시 적재) · '없음'(그날 자료가 원래 없음) 도 정상으로 센다

ALTER TABLE promotion_log MODIFY action ENUM('promote','reject','rollback','bootstrap','scenario') NOT NULL;

CREATE OR REPLACE VIEW v_svc_collect AS
SELECT source,
       MAX(CASE WHEN status IN ('성공', '늘어남', '재생') THEN logged END) AS last_ok,
       SUM(CASE WHEN logged >= NOW() - INTERVAL 7 DAY THEN 1 ELSE 0 END) AS n_7d,
       SUM(CASE WHEN logged >= NOW() - INTERVAL 7 DAY AND status IN ('성공', '늘어남', '있음', '재생', '없음') THEN 1 ELSE 0 END) AS ok_7d,
       SUM(CASE WHEN logged >= NOW() - INTERVAL 1 DAY AND status IN ('성공', '늘어남', '재생') THEN n_rows ELSE 0 END) AS rows_24h,
       MAX(CASE WHEN status = '실패' THEN logged END) AS last_fail,
       SUBSTRING_INDEX(GROUP_CONCAT(CASE WHEN status = '실패' THEN CONCAT(target, ' — ', COALESCE(note, '')) END
                                    ORDER BY logged DESC SEPARATOR '\n'), '\n', 1) AS last_fail_note
FROM collect_log GROUP BY source;

-- 최근 수집 기록 한 줄씩 (화면은 최근 것부터 잘라 읽는다)
CREATE OR REPLACE VIEW v_svc_collect_log AS
SELECT log_id, logged, source, target, status, n_rows, seconds, note FROM collect_log;

-- 작업 기록 — 화면이 교체 조건 · 수집 수치를 펼쳐 보도록 detail(JSON) 까지
CREATE OR REPLACE VIEW v_svc_jobs AS
SELECT run_id, job, trigger_by, started_at, ended_at, status, summary, detail FROM job_run;
