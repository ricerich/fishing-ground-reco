"""P5 학습셋 — 평소에 오늘이 섞이지 않는지 · 판단할 수 없는 날이 NaN 인지"""
import numpy as np
import pandas as pd

from reco.trainset import add_baseline, add_features, label


def _toy(n=40):
    dates = pd.date_range("2025-03-03", periods=n, freq="D")          # 월요일 시작
    w = np.full(n, 100.0); w[-1] = 10_000.0                              # 마지막 날만 대박
    return pd.DataFrame({"area": "A", "species": "방어", "date": dates, "weight_kg": w,
                         "weekday": dates.day_of_week, "recent_incomplete": False, "gust_max": 5.0,
                         "wtem_mean": 15.0, "wspd_mean": 2.0, "tide_range": 100.0, "sal_mean": 32.0})


def test_baseline_excludes_today():
    d = add_baseline(_toy())
    assert d["baseline"].iloc[-1] == 100.0                              # 대박 날의 평소에 대박이 없다


def test_label_nan_rules():
    d = add_baseline(_toy())
    d.loc[d.index[30], ["weight_kg", "gust_max"]] = [0.0, 20.0]          # 폭풍인데 0
    y = label(d)
    assert y.iloc[:5].isna().all()                                       # 평소 모름
    assert y[d["weekday"] == 6].isna().all()                             # 일요일
    assert np.isnan(y.iloc[30])
    assert y.iloc[-1] == 1.0


def test_features_use_yesterday_only():
    d = add_features(add_baseline(_toy()))
    assert d["f_rel_lag1"].iloc[-1] == np.log1p(1.0)                     # 어제(100 ÷ 100) — 오늘 대박은 안 보임
