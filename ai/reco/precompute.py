"""추천 미리 계산 — (날짜 × 품목)마다 챔피언과 규칙의 전체 순위를 계산해 DB 에 넣는다.

- 화면(Spring)은 이 표를 읽기만 한다 → 빠르고, AI 서버가 꺼져도 추천은 보인다.
- 특성은 학습과 같은 코드(trainset.add_baseline · add_features)로 만든다. 여러 날을 한 번에 계산해도
  날짜 D 의 특성은 D−1 까지의 값만 쓰므로 하루씩 계산한 것(recommend.features_for)과 같다 — 테스트로 확인.
- 챔피언 · 규칙을 둘 다 저장해 두면, 7일 뒤 라벨이 확정됐을 때 두 방법의 실제 성적을 비교할 수 있다.
"""
import json
import math

import numpy as np
import pandas as pd

from . import config as C
from . import registry
from .dataset import area_day as load_area_day
from .db import connect, upsert
from .recommend import _reasons
from .trainset import TRAIN_END, add_baseline, add_features

FEAT_SAY = {"f_rel_lag1": "rel_lag1", "f_rel_mean7": "rel_mean7", "f_sold_days7": "sold_days7",
            "f_days_since_sale": "days_since_sale", "f_wtem_mean_lag1": "wtem", "f_wtem_anom_lag1": "wtem_anom",
            "f_gust_max_lag1": "gust_lag1"}


def _num(v, nd=2):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), nd)


def feats_json(r) -> dict:
    out = {}
    for c, k in FEAT_SAY.items():
        v = r.get(c)
        if c in ("f_rel_lag1", "f_rel_mean7") and v is not None and not pd.isna(v):
            v = np.expm1(v)                                   # log1p 를 되돌려 '평소의 몇 배'로
        out[k] = _num(v)
    return out


def wind_forecast(dates) -> dict:
    """{(날짜, 권역): 그날 예보 최대 풍속}. 예보는 수집한 날부터만 있다 — 없으면 빈 dict (경고 없음)."""
    if not dates:
        return {}
    q = """SELECT f.fc_date, a.area_name, MAX(GREATEST(COALESCE(f.ws1,0), COALESCE(f.ws2,0))) AS ws
           FROM v_latest_forecast f JOIN area a ON a.area_id = f.area_id
           WHERE f.fc_date BETWEEN %s AND %s GROUP BY f.fc_date, a.area_name"""
    with connect() as c, c.cursor() as cur:
        cur.execute(q, (min(dates), max(dates)))
        return {(pd.Timestamp(d), a): float(ws) for d, a, ws in cur.fetchall()}


def yesterday_fill(ad: pd.DataFrame, D: pd.Timestamp, species: str):
    """어제 위판량 ÷ 최근 28일 중 팔린 날의 하루 위판량 중앙값 — 아침에는 1보다 작게 나오기 쉽다(덜 채워짐)."""
    s = ad[ad["species"] == species].groupby("date")["weight_kg"].sum()
    y = s.get(D - pd.Timedelta(days=1))
    past = s[(s.index >= D - pd.Timedelta(days=29)) & (s.index <= D - pd.Timedelta(days=2))]
    past = past[past > 0]
    if y is None or past.empty:
        return None
    return round(float(y / past.median()), 3)


def compute(dates, versions, ad=None, min_usual_kg=0):
    """→ {(D, 품목, 버전): {"items": [...전체 순위], "excluded": [...], "candidates": n}}"""
    dates = [pd.Timestamp(d) for d in dates]
    ad = load_area_day(end=max(dates)) if ad is None else ad
    base = add_baseline(ad)
    feats_by_su: dict = {}
    wind = wind_forecast([d.date() for d in dates]) if C.DATA_SOURCE == "db" else {}
    out = {}
    for v in versions:
        su = registry.stats_until(v) or pd.Timestamp(TRAIN_END)
        if su not in feats_by_su:
            f = add_features(base, su)
            feats_by_su[su] = f[f["date"].isin(dates)]
        F = feats_by_su[su]
        for (D, sp), g in F.groupby(["date", "species"]):
            known = g[g["baseline"].notna()].copy()
            excluded = [{"area": a, "reason": "철이 아님 — 최근 28일 중 위판한 날이 5일 미만"} for a in g.loc[g["baseline"].isna(), "area"]]
            small = known["baseline"] < min_usual_kg
            excluded += [{"area": a, "reason": f"평소 위판 {b:,.0f}kg < {min_usual_kg:,}kg"}
                         for a, b in known.loc[small, ["area", "baseline"]].values]
            known = known[~small]
            items = []
            if len(known):
                known["score"] = registry.score(v, known).values
                contrib = registry.contributions(v, known)
                known = known.sort_values(["score", "area"], ascending=[False, True])
                for rank, (i, r) in enumerate(known.iterrows(), 1):
                    warn = []
                    ws = wind.get((D, r["area"]))
                    if ws is not None and ws >= C.WIND_WARN:
                        warn.append(f"해상예보 풍속 {ws:.0f}m/s — 출항이 어려울 수 있음")
                    items.append({"rank": rank, "area": r["area"], "score": round(float(r["score"]), 4),
                                  "usual_kg": int(round(float(r["baseline"]))), "reasons": _reasons(r, contrib.loc[i]),
                                  "warnings": warn, "feats": feats_json(r)})
            out[(D, sp, v)] = {"items": items, "excluded": excluded, "candidates": len(items)}
    return out, ad


def store(results: dict, served: dict, ad: pd.DataFrame, data_last_day):
    """served = {(D, 품목): 화면에 보일 버전}. 다시 계산하면 덮어쓴다(기본키)."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT area_name, area_id FROM area")
        aid = dict(cur.fetchall())
        recs, excl, runs = [], [], []
        for (D, sp, v), r in results.items():
            d = D.date()
            cur.execute("DELETE FROM recommendation WHERE rec_date=%s AND species=%s AND model_version=%s", (d, sp, v))
            cur.execute("DELETE FROM recommendation_excluded WHERE rec_date=%s AND species=%s AND model_version=%s", (d, sp, v))
            for it in r["items"]:
                recs.append((d, sp, v, aid[it["area"]], it["rank"], it["score"], it["usual_kg"],
                             json.dumps(it["reasons"], ensure_ascii=False), json.dumps(it["warnings"], ensure_ascii=False),
                             json.dumps(it["feats"], ensure_ascii=False)))
            for e in r["excluded"]:
                excl.append((d, sp, v, aid[e["area"]], e["reason"][:120]))
        conn.commit()
        for (D, sp), v in served.items():
            r = results.get((D, sp, v), {"candidates": 0})
            runs.append((D.date(), sp, v, pd.Timestamp(data_last_day).date(), yesterday_fill(ad, D, sp),
                         r["candidates"], C.now().replace(tzinfo=None)))
    with connect() as conn:
        upsert(conn, "recommendation", ["rec_date", "species", "model_version", "area_id", "rnk", "score", "usual_kg",
                                        "reasons", "warnings", "feats"], recs, ["rec_date", "species", "model_version", "area_id"])
        upsert(conn, "recommendation_excluded", ["rec_date", "species", "model_version", "area_id", "reason"], excl,
               ["rec_date", "species", "model_version", "area_id"])
        upsert(conn, "rec_run", ["rec_date", "species", "served_version", "data_last_day", "yesterday_fill", "candidates",
                                 "computed_at"], runs, ["rec_date", "species"])
    return {"recommendation": len(recs), "excluded": len(excl), "rec_run": len(runs)}


def run(dates, served_version=None):
    """날짜들을 계산해 저장. 서비스 버전 = 지금 챔피언(주지 않으면). 규칙은 언제나 함께."""
    champ = served_version or registry.champion()
    versions = list(dict.fromkeys([champ, registry.RULE]))
    results, ad = compute(dates, versions)
    last = ad.loc[ad["weight_kg"] > 0, "date"].max()
    served = {(pd.Timestamp(D), sp): champ for D in dates for sp in C.SPECIES}
    n = store(results, served, ad, last)
    return {"dates": [str(pd.Timestamp(d).date()) for d in dates], "served": champ, **n}
