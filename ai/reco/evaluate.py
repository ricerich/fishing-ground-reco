"""실제 성적 — 라벨이 확정된 날(자료 마지막 날 − 7일 이전)의 지난 추천을 채점해 live_eval 에 넣는다.

같은 날 같은 품목에서 챔피언 · 규칙 둘 다 채점한다 → '추천 성적' 화면에서 나란히 보여 준다.
라벨이 있는 권역만 순위에 남긴다(P6 rank.groups 와 같은 규칙: 4곳 이상 · 좋은 날 1곳 이상).
"""
import json

import pandas as pd

from . import config as C
from .dataset import area_day as load_area_day
from .db import connect, upsert
from .rank import one_group
from .retrain import LABEL_STATS_UNTIL
from .trainset import build_trainset


def labels(ad=None) -> tuple[pd.DataFrame, pd.Timestamp]:
    ad = load_area_day() if ad is None else ad
    t = build_trainset(d=ad, train_end=LABEL_STATS_UNTIL)
    last = ad.loc[ad["weight_kg"] > 0, "date"].max()
    matured_end = last - pd.Timedelta(days=C.LABEL_MATURE_DAYS)
    return t[(t["y"].notna()) & (t["date"] <= matured_end)][["area", "species", "date", "y"]], matured_end


def run(since=None) -> dict:
    lab, matured_end = labels()
    with connect() as c, c.cursor() as cur:
        cur.execute("""SELECT r.rec_date, r.species, r.model_version, a.area_name, r.rnk
                       FROM recommendation r JOIN area a ON a.area_id = r.area_id
                       WHERE r.rec_date <= %s AND (%s IS NULL OR r.rec_date >= %s)""",
                    (matured_end.date(), since, since))
        recs = pd.DataFrame(cur.fetchall(), columns=["date", "species", "version", "area", "rnk"])
    if recs.empty:
        return {"evaluated": 0, "matured_end": str(matured_end.date())}
    recs["date"] = pd.to_datetime(recs["date"])
    m = recs.merge(lab, on=["area", "species", "date"], how="inner")
    rows, now = [], C.now().replace(tzinfo=None)
    for (d, sp, v), g in m.groupby(["date", "species", "version"]):
        if len(g) < 4 or g["y"].sum() == 0:
            continue
        g = g.sort_values("rnk")
        s = one_group(g["y"].to_numpy(), 3)
        good = g.loc[g["y"] == 1, "area"].tolist()
        rows.append((d.date(), sp, v, round(s["P"], 4), round(s["Hit"], 4), round(s["NDCG"], 4), len(g),
                     json.dumps(good, ensure_ascii=False), now))
    with connect() as c:
        upsert(c, "live_eval", ["rec_date", "species", "model_version", "p_at_3", "hit_at_3", "ndcg_at_3", "n_labeled",
                                "good_areas", "evaluated_at"], rows, ["rec_date", "species", "model_version"])
    return {"evaluated": len(rows), "matured_end": str(matured_end.date())}
