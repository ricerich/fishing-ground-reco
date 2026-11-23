-- 학습 · 분석용 뷰 (P4) — P3 의 area_day.csv 를 DB 안에서 만든다

-- 권역 × 품목 × 날짜 위판 합 (팔린 날만) — 적재 뒤 area_sales 테이블로 옮겨 쓴다
CREATE OR REPLACE VIEW v_area_sales AS
SELECT m.area_id, a.species, a.sale_date,
       SUM(a.weight_kg) AS weight_kg, SUM(a.amount_won) AS amount_won, SUM(a.n_rows) AS n_rows
FROM auction_daily a JOIN market m ON m.market_id = a.market_id
WHERE m.area_id IS NOT NULL
GROUP BY m.area_id, a.species, a.sale_date;

-- 권역 × 품목 × 달력 — 안 팔린 날은 0 (CROSS JOIN 으로 빈칸을 만든 뒤 LEFT JOIN)
-- 기간: 위판이 있는 첫날 ~ 마지막 날 (한 줄짜리 b 로 한 번만 계산)
CREATE OR REPLACE VIEW v_area_day AS
SELECT ar.area_name AS area, sp.species, c.d AS date,
       COALESCE(s.weight_kg, 0) AS weight_kg, COALESCE(s.amount_won, 0) AS amount_won, COALESCE(s.n_rows, 0) AS n,
       o.wtem_mean, o.wtem_min, o.wtem_max, o.artmp_mean, o.atmpr_mean, o.wspd_mean, o.gust_max,
       o.tide_range, o.sal_mean, o.hours, c.weekday, c.holiday,
       c.d > b.last_day - INTERVAL 7 DAY AS recent_incomplete
FROM (SELECT MIN(sale_date) AS first_day, MAX(sale_date) AS last_day FROM auction_daily) b
JOIN calendar c ON c.d BETWEEN b.first_day AND b.last_day
CROSS JOIN area ar
CROSS JOIN species sp
LEFT JOIN area_sales s ON s.area_id = ar.area_id AND s.species = sp.species AND s.sale_date = c.d
LEFT JOIN obs_daily o ON o.area_id = ar.area_id AND o.obs_date = c.d;

-- 서비스용: 권역 × 날짜 × 반나절의 '가장 최근 발표' 해상예보
CREATE OR REPLACE VIEW v_latest_forecast AS
SELECT f.* FROM sea_forecast f
JOIN (SELECT area_id, fc_date, ampm, MAX(tm_fc) AS tm_fc FROM sea_forecast GROUP BY area_id, fc_date, ampm) last
  ON last.area_id = f.area_id AND last.fc_date = f.fc_date AND last.ampm = f.ampm AND last.tm_fc = f.tm_fc;
