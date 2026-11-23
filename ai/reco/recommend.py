"""P6 — 추천 함수: (품목, 날짜 D) → 권역 순위 JSON. 추천 API(docs/추천API_설계.md)의 몸통.

화면은 만들지 않는다. 이 함수가 돌려주는 dict 가 곧 API 응답 본문이다.
- 특성은 D−1 까지의 위판 · 관측만 쓴다 (학습 때와 같은 reco/trainset.py 코드 → 학습/서비스 어긋남 막기)
- 철이 아닌 권역(평소를 모름)은 순위에서 빼고 이유를 적는다
- 해상예보(선택)에서 풍속이 WIND_WARN 이상이면 순위는 그대로 두고 경고를 단다 — 갈지 말지는 사람이 정한다
- 모델 파일이 없으면 규칙('어제 좋았던 곳')으로 대신한다 (fallback)
"""
import json
from datetime import datetime

import numpy as np
import pandas as pd

from . import config as C
from .trainset import FEATURES, TRAIN_END, add_baseline, add_features

MODEL_DIR = C.ROOT / "models"
WIND_WARN = C.WIND_WARN  # m/s — P3: 돌풍 14 이상이면 그날 위판 0 이 33%


def load_model(name="reco_v1"):
    try:
        import joblib
        return joblib.load(MODEL_DIR / f"{name}.joblib"), json.loads((MODEL_DIR / f"{name}.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ImportError):
        return None, {"name": "rule_yesterday", "kind": "rule"}


def features_for(date, area_day=None, stats_until=TRAIN_END) -> pd.DataFrame:
    """D 날 한 줄씩(권역 × 품목) 특성. D 가 자료 끝 다음 날이어도 된다(그날 위판 칸은 비워 둔다).
    stats_until = 모델의 meta.json 값 (평년 수온을 그날까지로 계산 — 학습 때와 같게)."""
    from .dataset import area_day as load_area_day
    D = pd.Timestamp(date)
    d = load_area_day(end=D) if area_day is None else area_day.copy()
    d = d[d["date"] <= D].copy()
    d.loc[d["date"] == D, "weight_kg"] = 0.0           # 오늘 위판은 모른다 — 어떤 값이 있어도 지운다
    f = add_features(add_baseline(d), stats_until or TRAIN_END)
    return f[f["date"] == D]


def _reasons(row, contrib: pd.Series) -> list:
    say = {"f_rel_lag1": lambda v: f"어제 위판이 평소의 {np.expm1(v):.1f}배",
           "f_rel_mean7": lambda v: f"최근 7일 평균이 평소의 {np.expm1(v):.1f}배",
           "f_sold_days7": lambda v: f"최근 7일 중 {v:.0f}일 위판",
           "f_days_since_sale": lambda v: f"마지막 위판 {v:.0f}일 전",
           "f_wtem_mean_lag1": lambda v: f"어제 수온 {v:.1f}℃",
           "f_wtem_anom_lag1": lambda v: f"수온이 평년보다 {v:+.1f}℃"}
    out = []
    for c, v in contrib.sort_values(ascending=False).items():
        if v <= 0 or len(out) == 2:
            break
        if c in say and pd.notna(row[c]):
            out.append(say[c](row[c]))
    return out


def recommend(species: str, date, k=3, area_day=None, wind_fcst: dict | None = None, model=None, min_usual_kg=0) -> dict:
    """min_usual_kg: 평소 위판이 이보다 작은 권역은 뺀다 (작은 권역의 '10배'는 몇 상자뿐 — P6 미션)"""
    if species not in C.SPECIES:
        raise ValueError(f"품목은 {C.SPECIES} 중 하나")
    model, meta = load_model() if model is None else model
    f = features_for(date, area_day)
    f = f[f["species"] == species]
    known = f[f["baseline"].notna()].copy()
    excluded = [{"area": a, "reason": "철이 아님 — 최근 28일 중 위판한 날이 5일 미만"} for a in f.loc[f["baseline"].isna(), "area"]]
    small = known["baseline"] < min_usual_kg
    excluded += [{"area": a, "reason": f"평소 위판 {b:,.0f}kg < {min_usual_kg:,}kg"} for a, b in known.loc[small, ["area", "baseline"]].values]
    known = known[~small]

    if model is not None and len(known):
        known["score"] = model.predict_proba(known[FEATURES])[:, 1]
        imp, sc, lr = model[0], model[1], model[-1]
        z = sc.transform(imp.transform(known[FEATURES]))
        contrib = pd.DataFrame(z * lr.coef_[0], columns=FEATURES, index=known.index)
    else:
        known["score"] = known["f_rel_lag1"].fillna(0)
        contrib = pd.DataFrame({"f_rel_lag1": known["score"]})

    known = known.sort_values(["score", "area"], ascending=[False, True])
    items = []
    for rank, (i, r) in enumerate(known.head(k).iterrows(), 1):
        warn = []
        ws = (wind_fcst or {}).get(r["area"])
        if ws is not None and ws >= WIND_WARN:
            warn.append(f"해상예보 풍속 {ws:.0f}m/s — 출항이 어려울 수 있음")
        items.append({"rank": rank, "area": r["area"], "score": round(float(r["score"]), 3),
                      "usual_kg": round(float(r["baseline"])), "reasons": _reasons(r, contrib.loc[i]), "warnings": warn})
    return {"species": species, "date": str(pd.Timestamp(date).date()), "k": k,
            "model": meta.get("name"), "generated_at": datetime.now().isoformat(timespec="seconds"),
            "candidates": int(len(known)), "items": items, "excluded": excluded,
            "notes": ["점수 = '평소의 1.5배 이상 위판될' 확률(모델 추정). 위판 = 팔린 곳 기준이라 실제 어장과 다를 수 있음.",
                      "어제 위판은 며칠에 걸쳐 채워진다 — 아침에는 덜 채워진 값으로 계산된다."]}
