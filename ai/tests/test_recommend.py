"""P6 — 서비스 특성 = 학습 특성 (학습/서비스 어긋남이 없는지) · 순위 지표 손계산"""
import numpy as np
import pandas as pd

from reco.area_day import build
from reco.rank import one_group
from reco.recommend import features_for, recommend
from reco.trainset import FEATURES, build_trainset


def test_one_group_by_hand():
    r = one_group(np.array([0.0, 1.0, 1.0, 0.0, 1.0]), 3)
    assert r["Hit"] == 1 and abs(r["P"] - 2 / 3) < 1e-9
    assert abs(r["NDCG"] - (1 / np.log2(3) + 1 / np.log2(4)) / (1 + 1 / np.log2(3) + 1 / np.log2(4))) < 1e-9


def test_service_features_match_training():
    ad = build()
    D = pd.Timestamp("2026-05-20")
    svc = features_for(D, ad).set_index(["area", "species"])[FEATURES].sort_index()
    t = build_trainset(d=ad.copy())
    trn = t[t["date"] == D].set_index(["area", "species"])[FEATURES].sort_index()
    pd.testing.assert_frame_equal(svc, trn, check_dtype=False)


def test_recommend_shape():
    r = recommend("방어", "2026-05-20", area_day=build(), model=(None, {"name": "rule"}))
    assert [it["rank"] for it in r["items"]] == [1, 2, 3]
    assert r["candidates"] + len(r["excluded"]) <= 14
