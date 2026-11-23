# 추천 API 설계 (P6) — 어장 위치 추천 v1

> 화면(UI)은 만들지 않는다. 이 문서는 "무엇을 받고 무엇을 돌려주나 · 언제 계산하나 · 어떻게 지켜보나"를 정한다.
> 몸통 함수는 `reco/recommend.py` 의 `recommend()` — 돌려주는 dict 가 곧 응답 본문이다.

## 1. 한 줄 정의

품목과 날짜를 주면, 그날 **평소의 1.5배 이상 위판될 가능성이 높은 권역 k 곳**을 점수 · 근거 · 경고와 함께 돌려준다.

## 2. 요청

```
GET /api/v1/recommend?species=방어&date=2026-09-16&k=3&min_usual_kg=1000
```

| 이름 | 필수 | 값 | 기본 | 설명 |
|---|---|---|---|---|
| `species` | O | 고등어 · 방어 · 삼치 | | 정확히 같은 이름만 |
| `date` | | YYYY-MM-DD | 오늘 | 자료 마지막 날 + 1일까지 (그 뒤는 '어제 위판'이 없다) |
| `k` | | 1 ~ 14 | 3 | 돌려줄 권역 수 |
| `min_usual_kg` | | 0 이상 | 0 | 평소 위판이 이보다 작은 권역은 뺀다 (P6 미션 A) |

## 3. 응답 (200) — 실제 `recommend()` 출력, 일부 줄임

```json
{
  "species": "방어",
  "date": "2026-09-16",
  "k": 3,
  "model": "reco_v1",
  "generated_at": "2026-09-16T06:30:00",
  "candidates": 3,
  "items": [
    { "rank": 1, "area": "속초·고성", "score": 0.647, "usual_kg": 1720,
      "reasons": ["최근 7일 평균이 평소의 3.8배", "어제 위판이 평소의 5.7배"], "warnings": [] },
    { "rank": 2, "area": "포항·영덕", "score": 0.393, "usual_kg": 17339,
      "reasons": ["최근 7일 평균이 평소의 1.6배", "최근 7일 중 7일 위판"],
      "warnings": ["해상예보 풍속 16m/s — 출항이 어려울 수 있음"] },
    { "rank": 3, "area": "후포·죽변", "score": 0.369, "usual_kg": 4057,
      "reasons": ["최근 7일 평균이 평소의 1.5배", "마지막 위판 1일 전"], "warnings": [] }
  ],
  "excluded": [
    { "area": "부산", "reason": "철이 아님 — 최근 28일 중 위판한 날이 5일 미만" },
    { "area": "마산·진해", "reason": "평소 위판 82kg < 1,000kg" }
  ],
  "notes": ["점수 = '평소의 1.5배 이상 위판될' 확률(모델 추정). 위판 = 팔린 곳 기준이라 실제 어장과 다를 수 있음.",
            "어제 위판은 며칠에 걸쳐 채워진다 — 아침에는 덜 채워진 값으로 계산된다."]
}
```

(풍속 16m/s 는 설명용 예시 값. 실제 서비스에서는 `v_latest_forecast` 의 그날 `ws2` 를 쓴다.)

| 필드 | 뜻 |
|---|---|
| `score` | 0 ~ 1. 권역끼리 **순서**를 정하는 값. "64.7% 확률로 대박"처럼 문장으로 쓰지 않는다(보정 안 됨) |
| `usual_kg` | 평소 = 어제까지 28일 중 팔린 날 위판의 중앙값. 큰 권역인지 작은 권역인지 함께 보여 준다 |
| `reasons` | 로지스틱 회귀의 기여(계수 × 표준화 값)가 큰 특성 2개를 문장으로 |
| `warnings` | 예보 풍속 ≥ 14m/s (P3: 돌풍 14 이상이면 그날 위판 0 이 33%). **순위는 바꾸지 않는다** — 판단은 사람이 |
| `excluded` | 순위에서 뺀 권역과 이유 — "왜 우리 동네는 없나"에 답한다 |

## 4. 오류

| 코드 | 언제 | 본문 예 |
|---|---|---|
| 400 | 품목이 셋 중 하나가 아님 · k 범위 밖 | `{"error": "species", "detail": "품목은 ['고등어', '방어', '삼치'] 중 하나"}` |
| 422 | date 가 자료 마지막 날 + 1 보다 뒤 | `{"error": "date", "detail": "2026-10-15 까지 추천할 수 있음"}` |
| 503 | 어제 수집이 실패(collect_log 에 어제 위판 ok 가 없음) | `{"error": "stale", "detail": "어제 위판 수집 실패 — 규칙 추천만 가능"}` |

모델 파일을 읽지 못하면 오류 대신 **규칙(어제 좋았던 곳)** 으로 답하고 `"model": "rule_yesterday"` 로 표시한다.

## 5. 언제 계산하나 — 미리 계산 + 저장

요청 때마다 계산하지 않는다. 매일 아침 수집(P2 `p2_run_daily.py`, 06:10 — 05시 해상예보 발표 뒤)이 끝나면 06:30 에 3품목 × 14권역을 한 번에 계산해 표에 넣고, API 는 표를 읽기만 한다.

```sql
CREATE TABLE recommendation (
  rec_date   DATE NOT NULL,
  species    VARCHAR(20) NOT NULL,
  area_id    TINYINT UNSIGNED NOT NULL,
  model      VARCHAR(30) NOT NULL,           -- reco_v1 · rule_yesterday
  score      DECIMAL(5,4) NOT NULL,
  rnk        TINYINT UNSIGNED NOT NULL,
  reasons    JSON NULL,
  warnings   JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (rec_date, species, model, area_id),
  CONSTRAINT fk_rec_area FOREIGN KEY (area_id) REFERENCES area (area_id),
  CONSTRAINT fk_rec_species FOREIGN KEY (species) REFERENCES species (species)
) ENGINE=InnoDB;
```

- 모델과 규칙을 **둘 다** 저장한다 → 나중에 위판이 다 채워지면(7일 뒤) 두 방법의 P@3 을 매주 비교할 수 있다.
- 같은 날을 다시 계산하면 덮어쓴다(기본키). 언제 계산했는지는 `created_at`.

## 6. 지켜보기 (운영)

| 무엇을 | 어떻게 | 기준 |
|---|---|---|
| 정확도 | 7일 지난 날의 라벨을 만들어 `recommendation` 과 붙여 P@3 (모델 vs 규칙) | 4주 연속 모델 < 규칙이면 규칙으로 돌림 |
| 입력 | 어제 위판 건수가 평소의 50% 미만이면 경고 | P2 수집 로그 |
| 분포 | `f_rel_lag1` · 수온의 주간 평균이 학습 구간 범위를 벗어나는가 | 새 철 · 새 위판장 |

## 7. 모델 v1 을 고른 이유와 한계 (P6 결과)

- 검증 P@3: 규칙(어제 좋았던 곳) 0.617 · 로지스틱 0.620 · GBM 0.625(씨앗 따라 ±0.015) · MLP 0.620 — **어느 모델도 규칙을 확실히 이기지 못함**(95% 구간이 0 을 걸침).
- 그래서 가장 단순하고 흔들리지 않는 **로지스틱**. 시험 P@3 0.606 vs 규칙 0.601 (차이 +0.005, 구간 −0.022 ~ +0.032).
- 바다 특성만으로는 P@3 0.325 — 무작위(0.363)보다도 낮다. 이 시스템의 힘은 '최근 위판'에서 나온다. "해양 환경 기반"이라는 이름을 발표에서 정직하게 설명할 것.
- 위판 = 팔린 곳. 잡힌 곳이 아니다.

## 8. (선택) FastAPI 로 감싸면

AI 트랙 A5(11/13)에서 배우는 방법 그대로. 이 프로젝트에서는 만들지 않고 모양만 적어 둔다.

```python
@app.get("/api/v1/recommend")
def get_recommend(species: str, date: str | None = None, k: int = 3, min_usual_kg: int = 0):
    row = read_recommendation(date or today(), species)        # 06:30 에 계산해 둔 표
    return row if row else recommend(species, date or today(), k=k, min_usual_kg=min_usual_kg)
```
