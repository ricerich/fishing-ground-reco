-- Spring(api) 이 읽는 뷰 — 표 구조가 바뀌어도 이 뷰 이름 · 열 이름은 지킨다 (두 언어 사이의 약속)
-- api 계정(reco_api)은 이 뷰들에만 SELECT 권한이 있다 (ai/scripts/init_db.py)

CREATE OR REPLACE VIEW v_svc_area AS
SELECT area_id, area_name, station_code, station_name, lat, lon FROM area;

-- 화면에 보일 추천: rec_run 이 가리키는 모델(계산 당시 챔피언)의 줄만
CREATE OR REPLACE VIEW v_svc_rec AS
SELECT r.rec_date, r.species, r.model_version, r.rnk, a.area_id, a.area_name, a.lat, a.lon,
       r.score, r.usual_kg, r.reasons, r.warnings, r.feats, r.created_at
FROM recommendation r
JOIN rec_run rr ON rr.rec_date = r.rec_date AND rr.species = r.species AND rr.served_version = r.model_version
JOIN area a ON a.area_id = r.area_id;

CREATE OR REPLACE VIEW v_svc_excluded AS
SELECT e.rec_date, e.species, a.area_name, e.reason
FROM recommendation_excluded e
JOIN rec_run rr ON rr.rec_date = e.rec_date AND rr.species = e.species AND rr.served_version = e.model_version
JOIN area a ON a.area_id = e.area_id;

CREATE OR REPLACE VIEW v_svc_rec_run AS
SELECT rr.rec_date, rr.species, rr.served_version, m.kind AS served_kind, rr.data_last_day,
       rr.yesterday_fill, rr.candidates, rr.computed_at
FROM rec_run rr LEFT JOIN model_registry m ON m.version = rr.served_version;

-- 실제 성적: 서비스한 모델 · 규칙 · (있으면) 무작위 기대값과 나란히
CREATE OR REPLACE VIEW v_svc_live_eval AS
SELECT le.rec_date, le.species, le.model_version, m.kind,
       (le.model_version = rr.served_version) AS served,
       le.p_at_3, le.hit_at_3, le.ndcg_at_3, le.n_labeled, le.good_areas, le.evaluated_at
FROM live_eval le
LEFT JOIN rec_run rr ON rr.rec_date = le.rec_date AND rr.species = le.species
LEFT JOIN model_registry m ON m.version = le.model_version;

CREATE OR REPLACE VIEW v_svc_models AS
SELECT version, kind, status, created_at, fit_from, fit_until, stats_until, eval_from, eval_until, n_train, n_groups,
       p_at_3, hit_at_3, ndcg_at_3, rule_p_at_3, champ_version, champ_p_at_3, diff, ci_low, ci_high,
       per_species, gates, decision, promoted_at, retired_at
FROM model_registry;

CREATE OR REPLACE VIEW v_svc_promotions AS
SELECT log_id, at, action, from_version, to_version, actor, reason FROM promotion_log;

CREATE OR REPLACE VIEW v_svc_jobs AS
SELECT run_id, job, trigger_by, started_at, ended_at, status, summary FROM job_run;

-- 출처별 수집 상태: 마지막 성공 · 최근 7일 성공률 · 마지막 실패 내용
CREATE OR REPLACE VIEW v_svc_collect AS
SELECT source,
       MAX(CASE WHEN status IN ('성공', '늘어남') THEN logged END) AS last_ok,
       SUM(CASE WHEN logged >= NOW() - INTERVAL 7 DAY THEN 1 ELSE 0 END) AS n_7d,
       SUM(CASE WHEN logged >= NOW() - INTERVAL 7 DAY AND status IN ('성공', '늘어남') THEN 1 ELSE 0 END) AS ok_7d,
       SUM(CASE WHEN logged >= NOW() - INTERVAL 1 DAY AND status IN ('성공', '늘어남') THEN n_rows ELSE 0 END) AS rows_24h,
       MAX(CASE WHEN status NOT IN ('성공', '늘어남', '있음') THEN logged END) AS last_fail
FROM collect_log GROUP BY source
;

CREATE OR REPLACE VIEW v_svc_queue AS
SELECT queue_id, job, params, requested_by, requested_at, status, run_id FROM job_queue
